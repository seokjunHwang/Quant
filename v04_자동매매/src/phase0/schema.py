"""Logic Chain data schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class LogicChain:
    chain_id: str
    category: str  # 금리/통화정책, 지정학/전쟁, 무역/관세, 원자재/에너지, 기술/규제, 실적/어닝시즌
    event: str
    causal_path: str  # 화살표로 연결된 인과 경로
    beneficiary_sectors: list[str] = field(default_factory=list)
    victim_sectors: list[str] = field(default_factory=list)
    intensity: str = "medium"  # high / medium / low
    time_horizon: str = "1~3일"  # 즉각 / 1~3일 / 1주일+
    reaction_speed: str = "즉각반응"  # 즉각반응 / 1~3일 / 1주일+
    pre_signals: list[str] = field(default_factory=list)
    historical_accuracy: float | None = None
    created_at: str = field(default_factory=lambda: date.today().isoformat())
    source: str = "gemini_generated"

    def to_dict(self) -> dict:
        return {
            "chain_id": self.chain_id,
            "category": self.category,
            "event": self.event,
            "causal_path": self.causal_path,
            "beneficiary_sectors": self.beneficiary_sectors,
            "victim_sectors": self.victim_sectors,
            "intensity": self.intensity,
            "time_horizon": self.time_horizon,
            "reaction_speed": self.reaction_speed,
            "pre_signals": self.pre_signals,
            "historical_accuracy": self.historical_accuracy,
            "created_at": self.created_at,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> LogicChain:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_embedding_text(self) -> str:
        """벡터화용 텍스트. pre_signals + event + causal_path를 결합."""
        parts = [
            f"Event: {self.event}",
            f"Path: {self.causal_path}",
            f"Pre-signals: {', '.join(self.pre_signals)}",
            f"Beneficiary: {', '.join(self.beneficiary_sectors)}",
            f"Victim: {', '.join(self.victim_sectors)}",
        ]
        return " | ".join(parts)
