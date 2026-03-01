"""
Agent Memory — persistent state across launch cycles.
Stores past launches, learnings, and strategy evolution.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LaunchRecord:
    timestamp: str
    token_name: str
    token_symbol: str
    tx_hash: str
    token_address: Optional[str]
    raise_amount_bnb: float
    gas_used: int
    reflection: Optional[str] = None
    peak_market_cap_usd: Optional[float] = None
    holder_count: Optional[int] = None
    status: str = "LAUNCHED"  # LAUNCHED | GRADUATED | RUGGED | UNKNOWN


@dataclass
class AgentMemory:
    """Persists agent state to a JSON file between runs."""

    launches: list[LaunchRecord] = field(default_factory=list)
    learnings: list[str] = field(default_factory=list)
    total_bnb_spent: float = 0.0
    total_gas_spent: int = 0
    successful_launches: int = 0
    _path: Path = field(default=Path("agent_memory.json"), repr=False)

    @classmethod
    def load(cls, path: str | Path = "agent_memory.json") -> "AgentMemory":
        p = Path(path)
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            launches = [LaunchRecord(**r) for r in data.get("launches", [])]
            mem = cls(
                launches=launches,
                learnings=data.get("learnings", []),
                total_bnb_spent=data.get("total_bnb_spent", 0.0),
                total_gas_spent=data.get("total_gas_spent", 0),
                successful_launches=data.get("successful_launches", 0),
                _path=p,
            )
            logger.info("Memory loaded: %d past launches", len(launches))
            return mem
        return cls(_path=p)

    def save(self) -> None:
        data = {
            "launches": [asdict(r) for r in self.launches],
            "learnings": self.learnings,
            "total_bnb_spent": self.total_bnb_spent,
            "total_gas_spent": self.total_gas_spent,
            "successful_launches": self.successful_launches,
            "last_updated": datetime.utcnow().isoformat(),
        }
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def record_launch(
        self,
        token_name: str,
        token_symbol: str,
        tx_hash: str,
        token_address: Optional[str],
        raise_amount_bnb: float,
        gas_used: int,
    ) -> LaunchRecord:
        record = LaunchRecord(
            timestamp=datetime.utcnow().isoformat(),
            token_name=token_name,
            token_symbol=token_symbol,
            tx_hash=tx_hash,
            token_address=token_address,
            raise_amount_bnb=raise_amount_bnb,
            gas_used=gas_used,
        )
        self.launches.append(record)
        self.total_bnb_spent += raise_amount_bnb
        self.total_gas_spent += gas_used
        self.successful_launches += 1
        self.save()
        return record

    def add_learning(self, learning: str) -> None:
        self.learnings.append(f"[{datetime.utcnow().isoformat()}] {learning}")
        if len(self.learnings) > 100:
            self.learnings = self.learnings[-100:]
        self.save()

    def get_recent_launches(self, n: int = 5) -> list[LaunchRecord]:
        return self.launches[-n:]

    def summary(self) -> str:
        return (
            f"Total launches: {len(self.launches)} | "
            f"Successful: {self.successful_launches} | "
            f"BNB spent: {self.total_bnb_spent:.4f} | "
            f"Learnings: {len(self.learnings)}"
        )
