"""
four.meme REST API Client
Wraps all private + public endpoints needed for token creation.
"""
from __future__ import annotations

import logging
import mimetypes
import os
from pathlib import Path
from typing import Any, Optional

import httpx

from .auth import FourMemeAuth

logger = logging.getLogger(__name__)

BASE_URL = "https://four.meme/meme-api"


class FourMemeAPIError(Exception):
    def __init__(self, status_code: int, message: str, path: str = "") -> None:
        self.status_code = status_code
        self.path = path
        super().__init__(f"[{status_code}] {path}: {message}")


class FourMemeClient:
    """
    Async HTTP client for four.meme backend API.
    All authenticated endpoints auto-refresh token when expired.
    """

    def __init__(self, auth: FourMemeAuth) -> None:
        self.auth = auth
        self._http = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=60,
            headers={
                "User-Agent": "four-meme-agent/1.0",
                "Origin": "https://four.meme",
                "Referer": "https://four.meme/",
            },
        )

    async def _get_headers(self) -> dict:
        session = await self.auth.get_session()
        return session.headers

    def _raise_for_api_error(self, data: dict, path: str) -> None:
        code = data.get("code", 0)
        msg = data.get("msg", "unknown error")
        if code != 200 and code != 0:
            raise FourMemeAPIError(code, msg, path)

    # ── Public endpoints ──────────────────────────────────────────────────────

    async def get_sys_config(self) -> dict:
        resp = await self._http.get("/v1/public/sys/config")
        resp.raise_for_status()
        data = resp.json()
        self._raise_for_api_error(data, "/v1/public/sys/config")
        return data["data"]

    async def get_ticker(self, page: int = 1, page_size: int = 20) -> dict:
        resp = await self._http.get(
            "/v1/public/ticker",
            params={"pageNo": page, "pageSize": page_size, "status": "TRADING"},
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def get_token_detail(self, token_address: str) -> dict:
        resp = await self._http.get(
            "/v1/public/token/detail",
            params={"address": token_address},
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

    # ── Private endpoints ─────────────────────────────────────────────────────

    async def upload_image(self, image_path: str | Path) -> str:
        """Upload an image and return the imgUrl string."""
        path = Path(image_path)
        mime = mimetypes.guess_type(str(path))[0] or "image/png"
        headers = await self._get_headers()
        # Remove Content-Type for multipart; httpx sets it automatically
        headers.pop("Content-Type", None)

        with open(path, "rb") as f:
            resp = await self._http.post(
                "/v1/private/tool/upload",
                files={"file": (path.name, f, mime)},
                headers=headers,
            )
        resp.raise_for_status()
        data = resp.json()
        self._raise_for_api_error(data, "/v1/private/tool/upload")
        img_url = data["data"]["url"]
        logger.info("Uploaded image → %s", img_url)
        return img_url

    async def create_token(
        self,
        name: str,
        symbol: str,
        description: str,
        img_url: str,
        twitter: str = "",
        telegram: str = "",
        website: str = "",
        raised_token_symbol: str = "BNB",
        raised_amount: float = 0,
    ) -> dict:
        """
        Call /v1/private/token/create to get (createArg, signature).
        These must then be submitted on-chain to TokenManager2.createToken().
        """
        headers = await self._get_headers()
        payload = {
            "name": name,
            "symbol": symbol,
            "description": description,
            "imgUrl": img_url,
            "twitter": twitter,
            "telegram": telegram,
            "website": website,
            "raisedTokenSymbol": raised_token_symbol,
            "raisedAmount": str(raised_amount),
        }
        logger.debug("Creating token: %s (%s)", name, symbol)
        resp = await self._http.post(
            "/v1/private/token/create",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        self._raise_for_api_error(data, "/v1/private/token/create")
        result = data["data"]
        logger.info(
            "Token creation args received for %s — ready to submit on-chain", symbol
        )
        return result  # {"createArg": ..., "signature": ...}

    async def get_my_tokens(self) -> list[dict]:
        headers = await self._get_headers()
        resp = await self._http.get(
            "/v1/private/token/my/list", headers=headers
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("list", [])

    async def close(self) -> None:
        await self._http.aclose()
        await self.auth.close()
