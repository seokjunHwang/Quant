"""CLI 백엔드 — subprocess로 claude CLI 호출 (v05 패턴)."""
from .backend import LLMBackend, LLMResponse


class ClaudeCLI(LLMBackend):
    def __init__(self, model: str = "claude-opus-4-7"):
        self.model = model

    def call(self, system, prompt, schema=None, allowed_tools=None,
             temperature=0.0, max_tokens=8192) -> LLMResponse:
        # TODO: subprocess.run(["claude", "-p", prompt, "--system-prompt", system, ...])
        # TODO: schema 있으면 프롬프트에 박고 jsonschema 검증
        # TODO: stdout 파싱해서 usage 채우기 (cost_usd=0 고정)
        raise NotImplementedError
