"""테스트·골든 시나리오용 — 결정론적 raw 데이터."""

from __future__ import annotations

from dataclasses import dataclass

from connectors.base import Connector, DataItem


@dataclass
class MockConnector:
    name: str = "mock"
    kinds: tuple[str, ...] = ("price", "news", "funding")

    async def fetch(self, *, ticker: str, kind: str) -> list[DataItem]:
        if kind == "price":
            return [DataItem(
                id="m1", kind="price", ticker=ticker,
                value={"current": 182.4, "high_24h": 184.0, "low_24h": 180.1, "change_pct_24h": 0.8},
                unit="USD", source_url=f"https://mock.local/{ticker}/price",
            )]
        if kind == "news":
            return [DataItem(
                id="m2", kind="news", ticker=ticker,
                value=f"{ticker} 관련 가상 뉴스 — AI 인프라 수요 지속.",
                source_url=f"https://mock.local/{ticker}/news/1",
            )]
        if kind == "funding":
            return [DataItem(
                id="m3", kind="funding", ticker=ticker,
                value={"funding_rate_pct": -0.012, "open_interest_usd": 1.2e9},
                unit="%", source_url=f"https://mock.local/{ticker}/funding",
            )]
        return []
