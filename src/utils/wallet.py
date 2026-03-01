"""Wallet utility helpers."""
from __future__ import annotations

from eth_account import Account


def derive_address(private_key: str) -> str:
    """Derive checksummed wallet address from private key."""
    acct = Account.from_key(private_key)
    return acct.address


def validate_private_key(private_key: str) -> bool:
    try:
        Account.from_key(private_key)
        return True
    except Exception:
        return False
