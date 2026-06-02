"""Connector Protocol — 외부 데이터 소스 추가 시 이 인터페이스 구현."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass
class DataItem:
    """검수 전 raw data 한 단위. verified_data.schema.json 의 부분집합."""

    id: str
    kind: str  # price | filing | news | funding | open_interest | macro
    ticker: str
    value: Any
    source_url: str
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    unit: str = ""
    notes: str = ""

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "ticker": self.ticker,
            "value": self.value,
            "unit": self.unit,
            "source_url": self.source_url,
            "fetched_at": self.fetched_at,
            "notes": self.notes,
        }


class Connector(Protocol):
    """단일 데이터 소스 추상화."""

    name: str
    kinds: tuple[str, ...]  # 어떤 kind 를 제공하는지 (price, news, funding 등)

    async def fetch(self, *, ticker: str, kind: str) -> list[DataItem]:
        ...
