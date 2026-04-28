"""API 백엔드 — anthropic SDK 호출."""
from .backend import LLMBackend, LLMResponse


class ClaudeAPI(LLMBackend):
    def __init__(self, model: str = "claude-opus-4-7"):
        self.model = model
        # TODO: self.client = anthropic.Anthropic()

    def call(self, system, prompt, schema=None, allowed_tools=None,
             temperature=0.0, max_tokens=8192) -> LLMResponse:
        # TODO: schema 있으면 tool_use 강제, 없으면 일반 텍스트
        # TODO: cache_control 적용 (Rule.md 등 누적 컨텍스트)
        # TODO: usage 채우기 (실제 비용 계산)
        raise NotImplementedError
