"""토론자 베이스 — Bull/Bear/Quant 공통 로직.

페르소나 파일과 temperature 만 다르므로 단일 클래스로 처리.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agents.base import Agent, AgentContext

log = logging.getLogger(__name__)


@dataclass
class Debater(Agent):
    debater_id: str = "bull"  # bull | bear | quant

    async def speak(self, ctx: AgentContext, *, round_idx: int) -> dict:
        user = _build_prompt(ctx, debater_id=self.debater_id, round_idx=round_idx)
        resp = await self.llm_call(
            ctx.runner, user=user,
            cache_prefix=f"persona:{self.debater_id}",
        )

        text = resp.text.strip()
        quotes = _extract_quotes(text)
        evidence = _extract_evidence_refs(text)

        return {
            "round": round_idx,
            "speaker": self.debater_id,
            "model": resp.model,
            "temperature": self.temperature,
            "text": text,
            "quotes": quotes,
            "evidence_refs": evidence,
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "cost_usd": resp.cost_usd,
            "latency_ms": resp.latency_ms,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


def _build_prompt(ctx: AgentContext, *, debater_id: str, round_idx: int) -> str:
    output_cfg = ctx.config.get("output", {})
    max_chars = output_cfg.get("max_chars_per_turn", 280)
    lang = output_cfg.get("language", "ko")

    verified_block = "\n".join(
        f"- {v['id']} ({v['kind']}) {v['ticker']}: {json.dumps(v['value'], ensure_ascii=False)} {v.get('unit','')}"
        for v in ctx.verified_data
    ) or "(검증된 데이터 없음 — '없음'으로 답하시오)"

    prev_turns = [t for t in ctx.turns if t.get("speaker") in ("bull", "bear", "quant")]
    history_block = "\n".join(
        f"[R{t['round']}/{t['speaker']}] {t['text']}"
        for t in prev_turns[-6:]
    ) or "(첫 라운드)"

    others = [o for o in ("bull", "bear", "quant") if o != debater_id]
    quote_req = f"이전 발언에서 최소 1개 이상 인용 (@{others[0]}: ... 또는 @{others[1]}: ...)."

    lang_note = "한국어로 답하시오." if lang == "ko" else "Answer in English."

    return (
        f"## 토론 라운드 {round_idx}\n"
        f"종목: {ctx.agenda['ticker']} ({ctx.agenda['asset_class']})\n"
        f"focus: {', '.join(ctx.agenda.get('focus', []))}\n\n"
        f"## 검증된 데이터 (verified[])\n{verified_block}\n\n"
        f"## 이전 발언\n{history_block}\n\n"
        f"## 규칙\n"
        f"- {max_chars}자 이내\n"
        f"- verified[] 외 추측 금지 — 없으면 '없음'\n"
        f"- {quote_req}\n"
        f"- 본인 무효화 조건 1줄 포함\n"
        f"- {lang_note}\n"
        f"발언만 출력 (메타 설명 X)."
    )


_QUOTE_RE = re.compile(r"@(bull|bear|quant|moderator|data_provider|auditor)\s*[:：][^@\n]{0,100}")
_EVIDENCE_RE = re.compile(r"\bv\d+\b")


def _extract_quotes(text: str) -> list[str]:
    return [m.group(0).strip() for m in _QUOTE_RE.finditer(text)]


def _extract_evidence_refs(text: str) -> list[str]:
    return list(dict.fromkeys(_EVIDENCE_RE.findall(text)))  # 중복 제거, 순서 유지
