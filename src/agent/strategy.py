"""
Launch Strategy Module
Orchestrates market analysis, timing decisions, and launch sequencing.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Optional

from ..four_meme.api import FourMemeClient
from .brain import AgentBrain, MarketContext

logger = logging.getLogger(__name__)

TRENDING_KEYWORDS_POOL = [
    "AI", "agent", "degen", "moon", "pump", "frog", "pepe", "cat", "dog",
    "bnb", "four", "meme", "based", "gigachad", "sigma", "wojak", "chad",
    "honk", "goat", "bull", "bear", "whale", "shrimp", "diamond", "hands",
]


@dataclass
class LaunchDecision:
    should_launch: bool
    reason: str
    best_concept_index: int = 0
    delay_seconds: int = 0


class MarketAnalyzer:
    """Pulls real-time market context from four.meme public APIs."""

    def __init__(self, client: FourMemeClient) -> None:
        self.client = client

    async def get_context(self) -> MarketContext:
        try:
            ticker_data = await self.client.get_ticker(page=1, page_size=50)
            tokens = ticker_data.get("list", [])

            # Extract trending keywords from token names/symbols
            text_blob = " ".join(
                f"{t.get('name', '')} {t.get('symbol', '')}" for t in tokens
            ).lower()
            keywords = [kw for kw in TRENDING_KEYWORDS_POOL if kw.lower() in text_blob]
            if not keywords:
                keywords = random.sample(TRENDING_KEYWORDS_POOL, 5)

            return MarketContext(
                trending_tokens=tokens[:10],
                trending_keywords=keywords,
                recent_launches=len(tokens),
            )
        except Exception as e:
            logger.warning("Market data fetch failed: %s — using defaults", e)
            return MarketContext(
                trending_keywords=random.sample(TRENDING_KEYWORDS_POOL, 5),
            )


class LaunchStrategy:
    """
    Decides WHEN and WHAT to launch based on market conditions and agent memory.
    """

    def __init__(
        self,
        brain: AgentBrain,
        min_balance_bnb: float = 0.05,
        max_launches_per_hour: int = 3,
        cooldown_seconds: int = 300,
    ) -> None:
        self.brain = brain
        self.min_balance_bnb = min_balance_bnb
        self.max_launches_per_hour = max_launches_per_hour
        self.cooldown_seconds = cooldown_seconds
        self._launch_timestamps: list[float] = []

    def _launches_in_last_hour(self) -> int:
        now = time.time()
        self._launch_timestamps = [t for t in self._launch_timestamps if now - t < 3600]
        return len(self._launch_timestamps)

    def record_launch(self) -> None:
        self._launch_timestamps.append(time.time())

    def should_launch_now(self, balance_bnb: float) -> LaunchDecision:
        if balance_bnb < self.min_balance_bnb:
            return LaunchDecision(
                should_launch=False,
                reason=f"Balance too low: {balance_bnb:.4f} BNB < {self.min_balance_bnb} BNB minimum",
            )
        launches_this_hour = self._launches_in_last_hour()
        if launches_this_hour >= self.max_launches_per_hour:
            return LaunchDecision(
                should_launch=False,
                reason=f"Rate limit: {launches_this_hour}/{self.max_launches_per_hour} launches this hour",
                delay_seconds=self.cooldown_seconds,
            )
        return LaunchDecision(
            should_launch=True,
            reason="Conditions met — proceeding with launch",
        )
