"""CoinGecko 공개 API (무료 티어)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from connectors.base import Connector, DataItem

log = logging.getLogger(__name__)

# 흔히 쓰는 매핑 (필요 시 확장)
SYMBOL_TO_ID = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}


@dataclass
class CoingeckoConnector:
    name: str = "coingecko"
    kinds: tuple[str, ...] = ("price",)

    async def fetch(self, *, ticker: str, kind: str) -> list[DataItem]:
        if kind != "price":
            return []
        return await asyncio.to_thread(self._fetch_price_sync, ticker)

    def _fetch_price_sync(self, ticker: str) -> list[DataItem]:
        try:
            import requests
        except ImportError:
            log.warning("requests 가 설치되지 않음")
            return []

        coin_id = SYMBOL_TO_ID.get(ticker.upper())
        if not coin_id:
            log.warning("CoinGecko: 알 수 없는 심볼 %s", ticker)
            return []

        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {"vs_currency": "usd", "ids": coin_id}
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return []
            d = data[0]
            return [DataItem(
                id="cg1",
                kind="price",
                ticker=ticker.upper(),
                value={
                    "current": d.get("current_price"),
                    "high_24h": d.get("high_24h"),
                    "low_24h":  d.get("low_24h"),
                    "change_pct_24h": d.get("price_change_percentage_24h"),
                    "volume_24h": d.get("total_volume"),
                    "market_cap": d.get("market_cap"),
                },
                unit="USD",
                source_url=f"https://www.coingecko.com/en/coins/{coin_id}",
            )]
        except Exception as e:
            log.warning("CoinGecko fetch 실패: %s", e)
            return []
