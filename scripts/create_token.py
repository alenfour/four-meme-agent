#!/usr/bin/env python3
"""
Manual Token Creator — Single token launch without AI agent.
Useful for testing the API + on-chain flow manually.

Usage:
    python scripts/create_token.py \
        --name "Test Token" \
        --symbol "TEST" \
        --description "Just a test" \
        --image path/to/image.png \
        --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.four_meme.api import FourMemeClient
from src.four_meme.auth import FourMemeAuth
from src.four_meme.onchain import BSCChain
from src.utils.wallet import derive_address

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main(args: argparse.Namespace) -> None:
    private_key = os.environ["WALLET_PRIVATE_KEY"]
    wallet = derive_address(private_key)
    logger.info("Wallet: %s", wallet)

    auth = FourMemeAuth(wallet_address=wallet, private_key=private_key)
    api = FourMemeClient(auth)
    chain = BSCChain(private_key=private_key)

    try:
        # Upload image
        img_path = args.image
        if not img_path or not Path(img_path).exists():
            logger.error("Image file not found: %s", img_path)
            sys.exit(1)

        logger.info("Uploading image: %s", img_path)
        img_url = await api.upload_image(img_path)
        logger.info("Image URL: %s", img_url)

        # Get create args from API
        logger.info("Requesting token creation args...")
        result = await api.create_token(
            name=args.name,
            symbol=args.symbol,
            description=args.description,
            img_url=img_url,
            twitter=args.twitter or "",
            telegram=args.telegram or "",
            website=args.website or "",
            raised_amount=args.raise_bnb,
        )

        create_arg = result["createArg"]
        signature = result["signature"]
        logger.info("createArg: %s...", create_arg[:60])
        logger.info("signature: %s...", signature[:60])

        if args.dry_run:
            logger.info("[DRY RUN] Skipping on-chain submission")
            return

        # Submit on-chain
        logger.info("Submitting to BSC...")
        tx = await chain.submit_create_token(
            create_arg=create_arg,
            signature=signature,
            value_bnb=args.raise_bnb,
        )
        logger.info("Token deployed!")
        logger.info("  Address:  %s", tx.token_address)
        logger.info("  Tx hash:  %s", tx.tx_hash)
        logger.info("  BSCScan:  %s", tx.bscscan_url)
        logger.info("  Gas used: %d", tx.gas_used)
        logger.info("  Block:    %d", tx.block_number)

    finally:
        await api.close()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--symbol", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--image", required=True, help="Path to token image")
    p.add_argument("--twitter", default="")
    p.add_argument("--telegram", default="")
    p.add_argument("--website", default="")
    p.add_argument("--raise-bnb", type=float, default=0.0, dest="raise_bnb")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
