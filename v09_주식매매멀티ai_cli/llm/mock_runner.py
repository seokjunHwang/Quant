"""테스트·골든 시나리오용 mock — claude 호출 없이 결정론적 응답."""

from __future__ import annotations

from dataclasses import dataclass, field

from llm.base import LLMResponse, LLMRunner


@dataclass
class MockRunner:
    name: str = "mock"
    canned: dict[str, str] = field(default_factory=dict)  # cache_prefix → 응답 텍스트
    default_text: str = "[MOCK] verified[1], @bull 의 진입 논리에 동의하나 stop 위치 재고 필요."

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
        text = self.canned.get(cache_prefix or "", self.default_text)
        return LLMResponse(
            text=text,
            input_tokens=len(system) // 4 + len(user) // 4,
            output_tokens=len(text) // 4,
            cost_usd=0.0,
            latency_ms=10,
            model=model,
            raw={"mock": True},
        )
