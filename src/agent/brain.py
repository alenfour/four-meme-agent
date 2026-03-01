"""
Agent Brain — LLM-powered decision engine.
Uses OpenAI-compatible API to generate token concepts, evaluate market trends,
and decide launch parameters autonomously.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class TokenConcept:
    name: str
    symbol: str
    description: str
    narrative: str          # internal reasoning (not posted on-chain)
    image_prompt: str       # prompt for image generation
    twitter_hook: str       # tweet text for launch
    risk_score: float       # 0.0 = safe, 1.0 = degen
    expected_virality: str  # LOW / MEDIUM / HIGH / MOON

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "symbol": self.symbol,
            "description": self.description,
            "image_prompt": self.image_prompt,
            "twitter_hook": self.twitter_hook,
            "risk_score": self.risk_score,
            "expected_virality": self.expected_virality,
        }


@dataclass
class MarketContext:
    trending_tokens: list[dict] = field(default_factory=list)
    trending_keywords: list[str] = field(default_factory=list)
    gas_price_gwei: float = 3.0
    bnb_price_usd: float = 0.0
    recent_launches: int = 0

    def to_prompt_fragment(self) -> str:
        keywords = ", ".join(self.trending_keywords[:10]) or "none"
        trending = [f"${t.get('symbol', '?')}" for t in self.trending_tokens[:5]]
        return (
            f"Current trending tokens: {', '.join(trending)}\n"
            f"Hot keywords on BSC meme market: {keywords}\n"
            f"BNB price: ${self.bnb_price_usd:.2f}\n"
            f"Recent launches in last hour: {self.recent_launches}"
        )


class AgentBrain:
    """
    LLM-powered brain that drives all creative and strategic decisions.

    Responsibilities:
        - Generate viral token concepts based on market context
        - Score and rank multiple concepts
        - Decide launch timing and raise amount
        - Generate image prompts for meme creation
        - Reflect on past launches and adapt strategy
    """

    SYSTEM_PROMPT = """You are an elite crypto meme strategist and AI agent operating on four.meme,
the leading BSC meme launchpad. Your mission: identify viral opportunities and create tokens
that capture community attention.

You think like a degen trader but act with precision. You understand:
- What makes memes go viral (cultural hooks, timing, humor, narrative)
- BSC community sentiment and trends
- How bonding curve mechanics affect early buyer behavior
- The psychology of FOMO and community formation

Always respond with valid JSON only. No markdown, no explanation outside JSON."""

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str = "gpt-4o",
        temperature: float = 0.9,
        max_retries: int = 3,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self._http = httpx.AsyncClient(timeout=120)

    async def _chat(self, messages: list[dict], temperature: Optional[float] = None) -> str:
        resp = await self._http.post(
            f"{self.api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature or self.temperature,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _parse_json(self, raw: str) -> Any:
        raw = raw.strip()
        # strip markdown code fences if model ignores json_object mode
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)

    async def generate_token_concepts(
        self,
        market: MarketContext,
        count: int = 3,
        theme: Optional[str] = None,
    ) -> list[TokenConcept]:
        """Generate N token concepts based on current market context."""
        theme_hint = f"Focus on the theme: {theme}." if theme else "Be creative — any viral angle."

        user_msg = f"""
{market.to_prompt_fragment()}

Generate {count} distinct token concepts for four.meme. {theme_hint}

Each concept must be unique, culturally resonant, and have strong meme potential.

Return JSON:
{{
  "concepts": [
    {{
      "name": "Full Token Name",
      "symbol": "TICKER",
      "description": "Token description (max 200 chars, shown on four.meme)",
      "narrative": "Internal reasoning: why this will go viral",
      "image_prompt": "Detailed DALL-E/SD prompt for the token logo",
      "twitter_hook": "Launch tweet (max 280 chars, no hashtags spam)",
      "risk_score": 0.0,
      "expected_virality": "MEDIUM"
    }}
  ]
}}
"""
        raw = await self._chat([
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ])
        data = self._parse_json(raw)
        concepts = []
        for c in data.get("concepts", []):
            try:
                concepts.append(TokenConcept(**c))
            except TypeError as e:
                logger.warning("Skipping malformed concept: %s", e)
        return concepts

    async def rank_concepts(
        self,
        concepts: list[TokenConcept],
        market: MarketContext,
    ) -> list[TokenConcept]:
        """Re-rank concepts by predicted success probability."""
        concepts_json = json.dumps([c.to_dict() for c in concepts], indent=2)
        user_msg = f"""
Market context:
{market.to_prompt_fragment()}

Here are token concepts to evaluate:
{concepts_json}

Rank them by predicted launch success. Consider: narrative strength, symbol memorability,
description quality, cultural timing, and meme potential.

Return JSON:
{{
  "ranked_symbols": ["BEST", "SECOND", "THIRD"],
  "reasoning": "Brief explanation of ranking"
}}
"""
        raw = await self._chat([
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ], temperature=0.3)
        data = self._parse_json(raw)
        ranked_symbols = data.get("ranked_symbols", [])
        symbol_map = {c.symbol: c for c in concepts}
        ranked = [symbol_map[s] for s in ranked_symbols if s in symbol_map]
        # Append any not in ranking at end
        ranked += [c for c in concepts if c.symbol not in ranked_symbols]
        return ranked

    async def decide_raise_amount(
        self,
        concept: TokenConcept,
        market: MarketContext,
        wallet_balance_bnb: float,
    ) -> float:
        """Decide how much BNB to seed-raise for the token launch."""
        user_msg = f"""
Wallet balance: {wallet_balance_bnb:.4f} BNB
Token: {concept.name} ({concept.symbol})
Virality prediction: {concept.expected_virality}
Risk score: {concept.risk_score}
{market.to_prompt_fragment()}

Decide the optimal BNB raise amount for this token launch on four.meme.
Consider that higher raise = faster bonding curve completion but higher cost.
Typical range: 0 (no seed) to 10 BNB.

Return JSON:
{{
  "raise_amount_bnb": 0.5,
  "reasoning": "Why this amount"
}}
"""
        raw = await self._chat([
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ], temperature=0.2)
        data = self._parse_json(raw)
        amount = float(data.get("raise_amount_bnb", 0))
        return min(amount, wallet_balance_bnb * 0.8)  # Never spend > 80% of balance

    async def reflect_on_launch(
        self,
        concept: TokenConcept,
        tx_result: dict,
        post_launch_data: Optional[dict] = None,
    ) -> str:
        """Generate a reflection on the launch to improve future decisions."""
        user_msg = f"""
Launched token: {concept.name} ({concept.symbol})
Transaction: {tx_result}
Post-launch market data (if available): {json.dumps(post_launch_data or {}, indent=2)}

Reflect on this launch:
1. What went well?
2. What could be improved?
3. What market signals should be watched for the next launch?

Return JSON:
{{
  "reflection": "...",
  "key_learnings": ["learning 1", "learning 2"],
  "next_action": "WAIT | LAUNCH_AGAIN | CHANGE_STRATEGY"
}}
"""
        raw = await self._chat([
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ], temperature=0.4)
        return raw

    async def close(self) -> None:
        await self._http.aclose()
