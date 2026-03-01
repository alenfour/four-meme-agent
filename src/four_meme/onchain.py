"""
BSC On-chain Module
Submits token creation transactions to four.meme's TokenManager2 contract.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from web3 import Web3
from web3.middleware import geth_poa_middleware

logger = logging.getLogger(__name__)

# four.meme TokenManager2 on BSC Mainnet
TOKEN_MANAGER2_ADDRESS = "0x5c952063c7fc8610FFDB798152D69F0B9550762b"

# Minimal ABI — only createToken is needed
TOKEN_MANAGER2_ABI = [
    {
        "inputs": [
            {"internalType": "bytes", "name": "createArg", "type": "bytes"},
            {"internalType": "bytes", "name": "signature", "type": "bytes"},
        ],
        "name": "createToken",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "token", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "creator", "type": "address"},
            {"indexed": False, "internalType": "string", "name": "name", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "symbol", "type": "string"},
        ],
        "name": "TokenCreated",
        "type": "event",
    },
]

BSC_MAINNET_RPC = "https://bsc-dataseed1.binance.org/"
BSC_TESTNET_RPC = "https://data-seed-prebsc-1-s1.binance.org:8545/"


@dataclass
class TxResult:
    tx_hash: str
    token_address: Optional[str]
    gas_used: int
    block_number: int

    @property
    def bscscan_url(self) -> str:
        return f"https://bscscan.com/tx/{self.tx_hash}"


class BSCChain:
    """
    Handles BSC interactions — signing and submitting createToken() transactions.
    """

    def __init__(
        self,
        private_key: str,
        rpc_url: str = BSC_MAINNET_RPC,
        gas_price_gwei: float = 3.0,
    ) -> None:
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to BSC node: {rpc_url}")

        self.account = self.w3.eth.account.from_key(private_key)
        self.wallet_address = self.account.address
        self.gas_price_wei = self.w3.to_wei(gas_price_gwei, "gwei")

        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(TOKEN_MANAGER2_ADDRESS),
            abi=TOKEN_MANAGER2_ABI,
        )
        logger.info(
            "BSCChain ready — wallet: %s | block: %d",
            self.wallet_address,
            self.w3.eth.block_number,
        )

    @property
    def balance_bnb(self) -> float:
        raw = self.w3.eth.get_balance(self.wallet_address)
        return float(self.w3.from_wei(raw, "ether"))

    def _decode_token_address_from_receipt(self, receipt) -> Optional[str]:
        try:
            logs = self.contract.events.TokenCreated().process_receipt(receipt)
            if logs:
                return logs[0]["args"]["token"]
        except Exception:
            pass
        return None

    async def submit_create_token(
        self,
        create_arg: str,
        signature: str,
        value_bnb: float = 0.0,
        gas_limit: int = 500_000,
    ) -> TxResult:
        """
        Send createToken(createArg, signature) to TokenManager2.
        create_arg and signature come from the four.meme API response.
        """
        nonce = self.w3.eth.get_transaction_count(self.wallet_address, "pending")
        value_wei = self.w3.to_wei(value_bnb, "ether")

        # Decode hex strings if prefixed
        arg_bytes = bytes.fromhex(create_arg.removeprefix("0x"))
        sig_bytes = bytes.fromhex(signature.removeprefix("0x"))

        tx = self.contract.functions.createToken(arg_bytes, sig_bytes).build_transaction(
            {
                "from": self.wallet_address,
                "nonce": nonce,
                "gas": gas_limit,
                "gasPrice": self.gas_price_wei,
                "value": value_wei,
                "chainId": 56,  # BSC Mainnet
            }
        )

        signed = self.w3.eth.account.sign_transaction(tx, self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        tx_hash_hex = tx_hash.hex()
        logger.info("Tx sent: %s — waiting for receipt...", tx_hash_hex)

        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt.status != 1:
            raise RuntimeError(f"Transaction reverted: {tx_hash_hex}")

        token_address = self._decode_token_address_from_receipt(receipt)
        result = TxResult(
            tx_hash=tx_hash_hex,
            token_address=token_address,
            gas_used=receipt.gasUsed,
            block_number=receipt.blockNumber,
        )
        logger.info(
            "Token deployed at %s | gas used: %d | block: %d",
            token_address,
            result.gas_used,
            result.block_number,
        )
        return result
