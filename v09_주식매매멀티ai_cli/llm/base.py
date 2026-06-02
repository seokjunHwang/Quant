"""LLM 호출 추상화 — 모든 LLM 호출의 단일 게이트.

매수자가 CLI ↔ API swap 시 이 Protocol 만 다시 구현하면 됨.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class LLMResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    model: str = ""
    raw: dict = field(default_factory=dict)


class LLMError(Exception):
    """LLM 호출 실패의 기본 에러."""


class RateLimitError(LLMError):
    """레이트 리밋 도달 — 큐잉/쿨다운 트리거."""


class LLMRunner(Protocol):
    """모든 LLM 호출이 통과하는 단일 인터페이스."""

    name: str  # "claude-opus-4-7" | "anthropic-api" | "mock" 등

    async def call(
        self,
        *,
        system: str,
        user: str,
        model: str = "claude-opus-4-7",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        cache_prefix: str | None = None,
    ) -> LLMResponse:
        ...
