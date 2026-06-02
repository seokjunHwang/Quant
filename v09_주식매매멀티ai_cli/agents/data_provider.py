"""데이터 제공자 — 어젠다의 required_data 를 Connector 로 수집."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from agents.base import Agent, AgentContext
from connectors import Connector, DataItem

log = logging.getLogger(__name__)

# required_data 키 → connector 호출 kind 매핑
KIND_MAP = {
    "price_1d": "price",
    "price_5d": "price",
    "news_24h": "news",
    "filings_24h": "filing",
    "funding_rate": "funding",
    "open_interest": "open_interest",
    "macro_calendar": "macro",
}


@dataclass
class DataProvider(Agent):
    async def collect(self, ctx: AgentContext, *, connectors: dict[str, Connector]) -> list[dict]:
        agenda = ctx.agenda
        ticker = agenda["ticker"]
        asset_class = agenda["asset_class"]
        cn = connectors.get(asset_class)
        if cn is None:
            log.warning("connector 없음: asset_class=%s", asset_class)
            return []

        seen_kinds: set[str] = set()
        results: list[DataItem] = []
        for req in agenda.get("required_data", []):
            kind = KIND_MAP.get(req)
            if not kind or kind in seen_kinds:
                continue
            seen_kinds.add(kind)
            items = await cn.fetch(ticker=ticker, kind=kind)
            results.extend(items)

        # id 재부여 (v1, v2, ...) — evidence_refs 에서 참조
        for i, item in enumerate(results, start=1):
            item.id = f"v{i}"
        return [item.as_dict() for item in results]
