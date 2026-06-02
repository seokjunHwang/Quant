"""yfinance 기반 US 주식 시세 수집 (지연 무료)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from connectors.base import Connector, DataItem

log = logging.getLogger(__name__)


@dataclass
class YfinanceConnector:
    name: str = "yfinance"
    kinds: tuple[str, ...] = ("price",)

    async def fetch(self, *, ticker: str, kind: str) -> list[DataItem]:
        if kind != "price":
            return []
        # yfinance 는 동기 — 별도 스레드에서 실행
        return await asyncio.to_thread(self._fetch_price_sync, ticker)

    def _fetch_price_sync(self, ticker: str) -> list[DataItem]:
        try:
            import yfinance as yf
        except ImportError:
            log.warning("yfinance 가 설치되지 않음 — pip install yfinance")
            return []

        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d", interval="1d")
            if hist.empty:
                return []
            items: list[DataItem] = []
            for i, (ts, row) in enumerate(hist.iterrows(), start=1):
                items.append(DataItem(
                    id=f"yf{i}",
                    kind="price",
                    ticker=ticker,
                    value={"open": float(row["Open"]), "high": float(row["High"]),
                           "low": float(row["Low"]),  "close": float(row["Close"]),
                           "volume": int(row["Volume"]), "date": ts.isoformat()},
                    unit="USD",
                    source_url=f"https://finance.yahoo.com/quote/{ticker}",
                ))
            return items
        except Exception as e:
            log.warning("yfinance fetch 실패 ticker=%s: %s", ticker, e)
            return []
