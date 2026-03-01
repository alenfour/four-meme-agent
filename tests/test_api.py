"""
Integration tests for four.meme API (no real wallet needed for public endpoints).
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.four_meme.api import FourMemeClient
from src.four_meme.auth import FourMemeAuth


@pytest.mark.asyncio
async def test_public_sys_config():
    """four.meme /v1/public/sys/config should return contract addresses."""
    # Uses a dummy auth — only public endpoint tested here
    auth = FourMemeAuth(
        wallet_address="0x0000000000000000000000000000000000000001",
        private_key="0x" + "a" * 64,
    )
    client = FourMemeClient(auth)
    try:
        config = await client.get_sys_config()
        assert isinstance(config, dict)
        assert "raisedTokens" in config or "contractAddress" in config or len(config) > 0
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_public_ticker():
    auth = FourMemeAuth(
        wallet_address="0x0000000000000000000000000000000000000001",
        private_key="0x" + "a" * 64,
    )
    client = FourMemeClient(auth)
    try:
        data = await client.get_ticker()
        assert isinstance(data, dict)
    finally:
        await client.close()
