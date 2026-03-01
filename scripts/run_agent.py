#!/usr/bin/env python3
"""
four.meme Agentic Mode — Autonomous Token Launcher
===================================================
Full autonomous loop: market scan → concept generation → ranking →
image generation → API submission → on-chain tx → memory recording.

Usage:
    python scripts/run_agent.py
    python scripts/run_agent.py --dry-run        # Skip on-chain tx
    python scripts/run_agent.py --theme "AI cat" # Force theme
    python scripts/run_agent.py --once           # Single launch then exit
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# ── path setup ───────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.agent.brain import AgentBrain
from src.agent.memory import AgentMemory
from src.agent.strategy import LaunchStrategy, MarketAnalyzer
from src.four_meme.api import FourMemeClient, FourMemeAPIError
from src.four_meme.auth import FourMemeAuth
from src.four_meme.onchain import BSCChain
from src.image.generator import MemeImageGenerator
from src.utils.wallet import derive_address, validate_private_key

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("four-meme-agent")

# ── config from env ───────────────────────────────────────────────────────────
PRIVATE_KEY = os.environ["WALLET_PRIVATE_KEY"]
LLM_API_BASE = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
LLM_API_KEY = os.environ["LLM_API_KEY"]
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
IMAGE_BACKEND = os.getenv("IMAGE_BACKEND", "dalle")
BSC_RPC = os.getenv("BSC_RPC_URL", "https://bsc-dataseed1.binance.org/")
LOOP_INTERVAL = int(os.getenv("LOOP_INTERVAL_SECONDS", "600"))  # 10 min default
MEMORY_PATH = os.getenv("MEMORY_PATH", "agent_memory.json")


async def launch_one_token(
    api: FourMemeClient,
    brain: AgentBrain,
    chain: BSCChain,
    image_gen: MemeImageGenerator,
    memory: AgentMemory,
    strategy: LaunchStrategy,
    market_analyzer: MarketAnalyzer,
    theme: str | None,
    dry_run: bool,
) -> bool:
    """Execute one full launch cycle. Returns True if token was launched."""

    # 1. Check strategy
    balance = chain.balance_bnb
    decision = strategy.should_launch_now(balance)
    if not decision.should_launch:
        logger.info("Strategy: NOT launching. Reason: %s", decision.reason)
        if decision.delay_seconds:
            logger.info("Waiting %ds before next check...", decision.delay_seconds)
            await asyncio.sleep(decision.delay_seconds)
        return False

    logger.info("Strategy: LAUNCH approved. Balance: %.4f BNB", balance)

    # 2. Market context
    logger.info("Scanning market context...")
    market = await market_analyzer.get_context()
    logger.info(
        "Market: %d trending tokens | keywords: %s",
        len(market.trending_tokens),
        ", ".join(market.trending_keywords[:5]),
    )

    # 3. Generate concepts
    logger.info("Generating token concepts...")
    concepts = await brain.generate_token_concepts(market, count=3, theme=theme)
    if not concepts:
        logger.error("Brain returned no concepts — skipping cycle")
        return False
    logger.info("Generated %d concepts: %s", len(concepts), [c.symbol for c in concepts])

    # 4. Rank concepts
    ranked = await brain.rank_concepts(concepts, market)
    best = ranked[0]
    logger.info(
        "Best concept: %s (%s) | virality: %s",
        best.name, best.symbol, best.expected_virality,
    )

    # 5. Decide raise amount
    raise_bnb = await brain.decide_raise_amount(best, market, balance)
    logger.info("Raise amount: %.4f BNB", raise_bnb)

    # 6. Generate image
    logger.info("Generating token image...")
    image_path = await image_gen.generate(
        prompt=best.image_prompt,
        symbol=best.symbol,
        backend=IMAGE_BACKEND,
    )
    logger.info("Image: %s", image_path)

    # 7. Upload image
    logger.info("Uploading image to four.meme...")
    img_url = await api.upload_image(image_path)

    # 8. Create token via API
    logger.info("Requesting token creation args from four.meme API...")
    try:
        create_result = await api.create_token(
            name=best.name,
            symbol=best.symbol,
            description=best.description,
            img_url=img_url,
            raised_amount=raise_bnb,
        )
    except FourMemeAPIError as e:
        logger.error("API error during token creation: %s", e)
        return False

    create_arg = create_result["createArg"]
    signature = create_result["signature"]

    if dry_run:
        logger.info("[DRY RUN] Would submit on-chain with:")
        logger.info("  createArg: %s...", create_arg[:40])
        logger.info("  signature: %s...", signature[:40])
        logger.info("  value:     %.4f BNB", raise_bnb)
        logger.info("[DRY RUN] Token: %s (%s)", best.name, best.symbol)
        logger.info("[DRY RUN] Description: %s", best.description)
        return True

    # 9. Submit on-chain
    logger.info("Submitting createToken() to BSC...")
    tx = await chain.submit_create_token(
        create_arg=create_arg,
        signature=signature,
        value_bnb=raise_bnb,
    )
    logger.info(
        "SUCCESS! Token deployed: %s | tx: %s | bscscan: %s",
        tx.token_address,
        tx.tx_hash,
        tx.bscscan_url,
    )
    logger.info("Twitter hook: %s", best.twitter_hook)

    # 10. Record in memory
    record = memory.record_launch(
        token_name=best.name,
        token_symbol=best.symbol,
        tx_hash=tx.tx_hash,
        token_address=tx.token_address,
        raise_amount_bnb=raise_bnb,
        gas_used=tx.gas_used,
    )

    # 11. Reflect
    reflection_raw = await brain.reflect_on_launch(
        best,
        {"tx_hash": tx.tx_hash, "token_address": tx.token_address, "gas_used": tx.gas_used},
    )
    logger.info("Reflection: %s", reflection_raw[:200])

    strategy.record_launch()
    logger.info("Memory: %s", memory.summary())
    return True


async def main(args: argparse.Namespace) -> None:
    if not validate_private_key(PRIVATE_KEY):
        logger.error("Invalid WALLET_PRIVATE_KEY in .env")
        sys.exit(1)

    wallet = derive_address(PRIVATE_KEY)
    logger.info("Agent wallet: %s", wallet)

    # Init components
    auth = FourMemeAuth(wallet_address=wallet, private_key=PRIVATE_KEY)
    api = FourMemeClient(auth)
    chain = BSCChain(private_key=PRIVATE_KEY, rpc_url=BSC_RPC)
    brain = AgentBrain(api_base=LLM_API_BASE, api_key=LLM_API_KEY, model=LLM_MODEL)
    image_gen = MemeImageGenerator(
        openai_api_base=LLM_API_BASE,
        openai_api_key=LLM_API_KEY,
        backend=IMAGE_BACKEND,
    )
    memory = AgentMemory.load(MEMORY_PATH)
    strategy = LaunchStrategy(brain=brain)
    market_analyzer = MarketAnalyzer(api)

    logger.info("four.meme Agentic Mode started | dry_run=%s | once=%s", args.dry_run, args.once)
    logger.info("Memory: %s", memory.summary())

    try:
        if args.once:
            await launch_one_token(
                api, brain, chain, image_gen, memory,
                strategy, market_analyzer, args.theme, args.dry_run,
            )
        else:
            # Autonomous loop
            while True:
                try:
                    launched = await launch_one_token(
                        api, brain, chain, image_gen, memory,
                        strategy, market_analyzer, args.theme, args.dry_run,
                    )
                    wait = LOOP_INTERVAL if launched else 60
                    logger.info("Sleeping %ds before next cycle...", wait)
                    await asyncio.sleep(wait)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.exception("Cycle error: %s — retrying in 60s", e)
                    await asyncio.sleep(60)
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
    finally:
        await api.close()
        await brain.close()
        await image_gen.close()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="four.meme Agentic Mode — Autonomous Token Launcher")
    p.add_argument("--dry-run", action="store_true", help="Skip on-chain transaction")
    p.add_argument("--once", action="store_true", help="Run one cycle then exit")
    p.add_argument("--theme", type=str, default=None, help="Force a theme for token concepts")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
