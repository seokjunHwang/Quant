"""Step 1 — 청사진 설계자.
   Rule.md + 외부 컨텍스트 읽고 JSON 청사진만 뽑는다."""
from core.backend import LLMBackend

ARCHITECT_PERSONA = """너는 설계자다. 코드를 짜지 마라.
주어진 태스크와 룰을 보고 JSON 청사진(스키마, 단계, 입출력)만 산출한다."""


class Architect:
    def __init__(self, backend: LLMBackend):
        self.backend = backend

    def run(self, task: str, rules: str, context: str = "") -> dict:
        # TODO: 청사진 스키마 정의 후 schema 인자로 전달
        resp = self.backend.call(
            system=ARCHITECT_PERSONA,
            prompt=f"TASK:\n{task}\n\nRULES:\n{rules}\n\nCONTEXT:\n{context}",
            allowed_tools=["Read", "WebSearch"],
            temperature=0.3,
        )
        return resp.content
