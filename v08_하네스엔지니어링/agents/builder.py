"""Step 2 — 순수 구현 매니저.
   청사진 그대로만 코드/텍스트 생성. 임의 판단 금지."""
from core.backend import LLMBackend

BUILDER_PERSONA = """너는 구현자다. 청사진에 적힌 것만 수행한다.
설계에 없는 추측, 추가 기능, 리팩토링 일체 금지."""


class Builder:
    def __init__(self, backend: LLMBackend):
        self.backend = backend

    def run(self, blueprint: dict) -> str:
        resp = self.backend.call(
            system=BUILDER_PERSONA,
            prompt=f"BLUEPRINT:\n{blueprint}",
            allowed_tools=[],
            temperature=0.0,
        )
        return resp.content
