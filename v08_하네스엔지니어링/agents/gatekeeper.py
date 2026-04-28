"""Step 3 — 검수자.
   청사진 제약과 산출물 일치 여부 검증 + 샌드박스 동적 실행."""
from core.backend import LLMBackend

GATEKEEPER_PERSONA = """너는 검수자다. 청사진과 산출물이 일치하는지 깐깐하게 본다.
실패 시 무엇이 왜 틀렸는지 구조화해서 보고한다."""


class Gatekeeper:
    def __init__(self, backend: LLMBackend, sandbox=None):
        self.backend = backend
        self.sandbox = sandbox

    def run(self, blueprint: dict, artifact: str) -> dict:
        # TODO: 코드 산출물이면 sandbox.run(artifact) 동적 테스트
        # TODO: 정적 검증 + 동적 결과를 합쳐 pass/fail + 사유 반환
        resp = self.backend.call(
            system=GATEKEEPER_PERSONA,
            prompt=f"BLUEPRINT:\n{blueprint}\n\nARTIFACT:\n{artifact}",
            allowed_tools=[],
            temperature=0.0,
        )
        return resp.content
