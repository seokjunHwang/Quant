"""LLM 백엔드 추상화 — agents는 이 인터페이스만 보고 호출."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    content: Any
    raw: dict = field(default_factory=dict)
    usage: dict = field(default_factory=dict)
    backend: str = ""


class LLMBackend(ABC):
    @abstractmethod
    def call(
        self,
        system: str,
        prompt: str,
        schema: dict | None = None,
        allowed_tools: list[str] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        ...
