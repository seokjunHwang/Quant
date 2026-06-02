"""Agent 공통 베이스 — 페르소나 로딩, LLM 호출 헬퍼."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from llm import LLMResponse, LLMRunner

log = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """토론 진행 중 모든 Agent 가 공유하는 컨텍스트."""

    run_id: str
    config: dict
    runner: LLMRunner
    agenda: dict = field(default_factory=dict)
    verified_data: list[dict] = field(default_factory=list)
    turns: list[dict] = field(default_factory=list)


@dataclass
class Agent:
    """모든 Agent 의 베이스. 페르소나 .md 를 system prompt 로 사용."""

    persona_path: Path
    model: str = "claude-opus-4-7"
    temperature: float = 0.7

    def system_prompt(self) -> str:
        return self.persona_path.read_text(encoding="utf-8")

    async def llm_call(
        self,
        runner: LLMRunner,
        *,
        user: str,
        cache_prefix: str | None = None,
    ) -> LLMResponse:
        return await runner.call(
            system=self.system_prompt(),
            user=user,
            model=self.model,
            temperature=self.temperature,
            cache_prefix=cache_prefix or f"persona:{self.persona_path.stem}",
        )
