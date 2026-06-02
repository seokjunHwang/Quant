"""검수자 — rules/auditor_rules.yml 기반 코드 룰 평가.

LLM 호출 없음 — 결정론적 룰만 적용. 매수자가 자유롭게 룰 확장 가능.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from agents.base import Agent, AgentContext

log = logging.getLogger(__name__)


@dataclass
class Auditor(Agent):
    rules_path: Path = Path("rules/auditor_rules.yml")

    def _load_rules(self) -> dict:
        return yaml.safe_load(self.rules_path.read_text(encoding="utf-8"))

    def audit(self, raw_items: list[dict]) -> list[dict]:
        rules = self._load_rules()
        verified: list[dict] = []
        for item in raw_items:
            reasons = _check_item(item, rules)
            cross_count = sum(1 for r in raw_items if r.get("kind") == item.get("kind"))
            audited = {
                **item,
                "audit_pass": not reasons,
                "cross_check_sources": cross_count,
                "notes": "; ".join(reasons) if reasons else item.get("notes", ""),
            }
            verified.append(audited)

        # 통과한 것만 유지 (반려는 별도 retry 단계에서 처리)
        passed = [v for v in verified if v["audit_pass"]]
        log.info("audit: %d/%d 통과", len(passed), len(verified))
        return passed


def _check_item(item: dict, rules: dict) -> list[str]:
    reasons: list[str] = []

    for f in rules.get("required_fields", []):
        if not item.get(f):
            reasons.append(f"필수 필드 누락: {f}")

    url = item.get("source_url", "")
    if rules.get("source_url", {}).get("must_be_https") and not url.startswith("https://"):
        reasons.append("source_url HTTPS 아님")

    fresh_minutes = (rules.get("freshness") or {}).get(item.get("kind"))
    if fresh_minutes:
        try:
            fetched = datetime.fromisoformat(item["fetched_at"].replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - fetched).total_seconds() / 60
            if age > fresh_minutes:
                reasons.append(f"신선도 초과: {age:.0f}분 > {fresh_minutes}분")
        except (ValueError, KeyError):
            reasons.append("fetched_at 파싱 실패")

    if item.get("kind") in rules.get("unit_required_for_kinds", []) and not item.get("unit"):
        reasons.append("단위 누락")

    return reasons
