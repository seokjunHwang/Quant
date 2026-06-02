"""토론 오케스트레이터 — 6역할을 묶어 1회 토론을 끝까지 진행한다."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from agents import Auditor, DataProvider, Debater, Moderator
from agents.base import AgentContext
from connectors import build_connectors
from llm import build_runner
from storage import Repository

log = logging.getLogger(__name__)


@dataclass
class DebateResult:
    run_id: str
    transcript: dict
    saved_path: Path


async def run_debate(
    *,
    config: dict,
    ticker: str,
    asset_class: str,
    event_type: str = "manual",
) -> DebateResult:
    started = datetime.now(timezone.utc).isoformat()
    repo = Repository.from_config(config)
    runner = build_runner(config)
    connectors = build_connectors(config)

    moderator = Moderator(
        persona_path=Path("personas/moderator.md"),
        temperature=config["agents"]["moderator"].get("temperature", 0.3),
    )
    data_provider = DataProvider(
        persona_path=Path("personas/data_provider.md"),
        temperature=config["agents"]["data_provider"].get("temperature", 0.0),
    )
    auditor = Auditor(
        persona_path=Path("personas/auditor.md"),
        temperature=config["agents"]["auditor"].get("temperature", 0.0),
        rules_path=Path(config["agents"]["auditor"].get("rules", "rules/auditor_rules.yml")),
    )
    debaters: list[Debater] = []
    for d_cfg in config.get("debaters", []):
        debaters.append(Debater(
            persona_path=Path(d_cfg["persona"]),
            temperature=d_cfg.get("temperature", 0.7),
            debater_id=d_cfg["id"],
        ))

    ctx = AgentContext(run_id=repo.new_run_id(), config=config, runner=runner)

    # ① + ② AGENDA
    ctx.agenda = await moderator.build_agenda(
        ctx, ticker=ticker, asset_class=asset_class, event_type=event_type,
    )
    log.info("agenda: %s", ctx.agenda)

    # ③ DATA + AUDIT (retry 포함)
    rules = yaml.safe_load(Path("rules/auditor_rules.yml").read_text(encoding="utf-8"))
    max_retry = rules.get("retry", {}).get("max_attempts", 2)
    for attempt in range(1, max_retry + 2):
        raw_items = await data_provider.collect(ctx, connectors=connectors)
        verified = auditor.audit(raw_items)
        if verified:
            ctx.verified_data = verified
            break
        log.warning("audit 통과 0건 — retry %d/%d", attempt, max_retry)
    if not ctx.verified_data:
        log.warning("verified_data 비어있음 — 토론자에게 '없음' 안내 후 계속")

    # ④ DEBATE
    stop_reason: str | None = None
    max_rounds = config.get("debate", {}).get("max_rounds", 5)
    for round_idx in range(1, max_rounds + 1):
        for d in debaters:
            try:
                turn = await d.speak(ctx, round_idx=round_idx)
            except Exception as e:
                log.exception("토론자 %s 실패: %s", d.debater_id, e)
                continue
            ctx.turns.append(turn)
            log.info("turn r=%d %s: %s", round_idx, d.debater_id, turn["text"][:80])

        stop_reason = moderator.stop_check(ctx, round_idx=round_idx)
        if stop_reason:
            log.info("종료: %s @ round %d", stop_reason, round_idx)
            break

    stop_reason = stop_reason or "max_rounds"

    # ⑤ FINALIZE
    final_report = await moderator.final_summary(ctx, stop_reason=stop_reason)

    # ⑥ SAVE
    transcript = _build_transcript(ctx, final_report=final_report, started=started)
    saved_path = repo.save(transcript)
    return DebateResult(run_id=ctx.run_id, transcript=transcript, saved_path=saved_path)


def _build_transcript(ctx: AgentContext, *, final_report: dict, started: str) -> dict:
    total_cost = sum(t.get("cost_usd", 0.0) for t in ctx.turns)
    total_tokens = sum(
        t.get("input_tokens", 0) + t.get("output_tokens", 0) for t in ctx.turns
    )
    return {
        "run_id": ctx.run_id,
        "agenda": ctx.agenda,
        "verified_data": ctx.verified_data,
        "turns": ctx.turns,
        "final_report": final_report,
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "started_at": started,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "config_snapshot": {
            "runner": ctx.config.get("runner", {}),
            "debate": ctx.config.get("debate", {}),
            "agents": list(ctx.config.get("agents", {}).keys()),
            "debaters": [d["id"] for d in ctx.config.get("debaters", [])],
        },
    }
