"""진행자 — 어젠다 발행, 종료 판정, 최종 요약."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from agents.base import Agent, AgentContext

log = logging.getLogger(__name__)


@dataclass
class Moderator(Agent):
    async def build_agenda(self, ctx: AgentContext, *, ticker: str,
                           asset_class: str, event_type: str) -> dict:
        user = (
            f"종목={ticker}, asset_class={asset_class}, event={event_type}.\n"
            "이 토론의 focus 1~3개와 required_data 를 JSON 한 줄로만 답하시오. "
            'agenda.schema.json 의 enum 만 사용:\n'
            '{"focus":["..."], "required_data":["price_1d","news_24h"]}'
        )
        resp = await self.llm_call(ctx.runner, user=user, cache_prefix="moderator:agenda")
        parsed = _extract_json(resp.text) or {"focus": ["recent_price_action"],
                                              "required_data": ["price_1d"]}
        return {
            "run_id": ctx.run_id,
            "ticker": ticker,
            "asset_class": asset_class,
            "event_type": event_type,
            "focus": parsed.get("focus", []),
            "required_data": parsed.get("required_data", ["price_1d"]),
            "created_at": _now_iso(),
        }

    def stop_check(self, ctx: AgentContext, *, round_idx: int) -> str | None:
        """순수 룰 평가 — LLM 호출 없음."""
        debate_cfg = ctx.config.get("debate", {})
        max_rounds = debate_cfg.get("max_rounds", 5)

        if round_idx >= max_rounds:
            return "max_rounds"

        # 직전 라운드 발언들 (토론자 3명)
        recent = [t for t in ctx.turns if t["round"] == round_idx and t["speaker"] in ("bull", "bear", "quant")]
        if len(recent) < 3:
            return None

        # stalled: 직전 2 라운드의 발언이 너무 유사 (단순 부분문자열 검사)
        if round_idx >= 2 and debate_cfg.get("early_stop_on_stall", True):
            prev = [t for t in ctx.turns if t["round"] == round_idx - 1 and t["speaker"] in ("bull", "bear", "quant")]
            if prev and _similarity_high(recent, prev):
                return "stalled"

        # consensus: 단순화된 휴리스틱 — 토론자 발언에 같은 키워드(buy/sell/hold)가 다수
        if debate_cfg.get("early_stop_on_consensus", True):
            actions = [_action_keyword(t["text"]) for t in recent]
            if actions.count(actions[0]) == 3 and actions[0]:
                return "consensus"

        return None

    async def final_summary(self, ctx: AgentContext, *, stop_reason: str) -> dict:
        turns_text = "\n".join(
            f"[R{t['round']}/{t['speaker']}] {t['text']}"
            for t in ctx.turns if t["speaker"] in ("bull", "bear", "quant")
        )
        user = (
            f"종료 사유: {stop_reason}\n다음 토론 기록을 4줄 이내로 요약하시오.\n"
            "형식: '합의 사항 / 미해결 쟁점 / 무효화 조건' 3섹션.\n\n"
            f"{turns_text}"
        )
        resp = await self.llm_call(ctx.runner, user=user, cache_prefix="moderator:final")
        return {"stop_reason": stop_reason, "summary": resp.text}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _similarity_high(a: list[dict], b: list[dict]) -> bool:
    """간단 휴리스틱: 같은 speaker 쌍의 발언이 50% 이상 토큰 중복."""
    by_speaker = {t["speaker"]: t["text"] for t in a}
    for t in b:
        prev_text = by_speaker.get(t["speaker"])
        if not prev_text:
            continue
        a_tokens = set(prev_text.split())
        b_tokens = set(t["text"].split())
        if not a_tokens or not b_tokens:
            continue
        overlap = len(a_tokens & b_tokens) / max(len(a_tokens), len(b_tokens))
        if overlap > 0.5:
            return True
    return False


def _action_keyword(text: str) -> str:
    t = text.lower()
    for kw in ("buy", "매수", "long"):
        if kw in t:
            return "buy"
    for kw in ("sell", "매도", "short"):
        if kw in t:
            return "sell"
    for kw in ("hold", "관망", "보유"):
        if kw in t:
            return "hold"
    return ""
