"""
four.meme Authentication Module
Handles nonce generation and wallet-signed login flow.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct

logger = logging.getLogger(__name__)

BASE_URL = "https://four.meme/meme-api"


@dataclass
class AuthSession:
    access_token: str
    wallet_address: str
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=23))

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }


class FourMemeAuth:
    """
    Manages authentication with four.meme API.

    Flow:
        1. GET  /v1/public/user/login/nonce  → receive nonce
        2. Sign "You are sign in Meme {nonce}" with private key
        3. POST /v1/public/user/login        → receive access_token
    """

    def __init__(
        self,
        wallet_address: str,
        private_key: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.wallet_address = wallet_address.lower()
        self._private_key = private_key
        self._client = client
        self._session: Optional[AuthSession] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    async def get_nonce(self) -> str:
        client = await self._get_client()
        resp = await client.get(
            f"{BASE_URL}/v1/public/user/login/nonce",
            params={"walletAddress": self.wallet_address},
        )
        resp.raise_for_status()
        data = resp.json()
        nonce = data["data"]
        logger.debug("Received nonce: %s", nonce)
        return nonce

    def _sign_message(self, nonce: str) -> str:
        message = f"You are sign in Meme {nonce}"
        msg = encode_defunct(text=message)
        signed = Account.sign_message(msg, private_key=self._private_key)
        return signed.signature.hex()

    async def login(self) -> AuthSession:
        nonce = await self.get_nonce()
        signature = self._sign_message(nonce)

        client = await self._get_client()
        resp = await client.post(
            f"{BASE_URL}/v1/public/user/login",
            json={
                "walletAddress": self.wallet_address,
                "signature": signature,
                "nonce": nonce,
                "loginType": "ETH",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        token = data["data"]["accessToken"]
        self._session = AuthSession(
            access_token=token,
            wallet_address=self.wallet_address,
        )
        logger.info("Authenticated as %s", self.wallet_address)
        return self._session

    async def get_session(self) -> AuthSession:
        if self._session is None or self._session.is_expired:
            await self.login()
        return self._session

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
