"""config.yml 의 data.sources 에 따라 Connector 매핑 반환."""

from __future__ import annotations

from connectors.base import Connector
from connectors.coingecko_connector import CoingeckoConnector
from connectors.mock_connector import MockConnector
from connectors.yfinance_connector import YfinanceConnector


def build_connectors(config: dict) -> dict[str, Connector]:
    """asset_class → Connector 매핑.

    "stock" → yfinance, "crypto" → coingecko, "mock" → 모든 kind mock.
    """
    use_mock = config.get("runner", {}).get("type") == "mock"
    if use_mock:
        m = MockConnector()
        return {"stock": m, "crypto": m}

    sources = (config.get("data") or {}).get("sources", {})
    stock = YfinanceConnector() if sources.get("quotes", "yfinance") == "yfinance" else MockConnector()
    crypto = CoingeckoConnector() if sources.get("crypto", "coingecko") == "coingecko" else MockConnector()
    return {"stock": stock, "crypto": crypto}
