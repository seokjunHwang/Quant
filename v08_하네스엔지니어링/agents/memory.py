"""Step 4 — 지식화.
   검수 실패/성공 로그를 분석해 Rule.md에 negative constraint를 새긴다."""
from core.backend import LLMBackend

MEMORY_PERSONA = """너는 룰 큐레이터다. 검수 결과에서 재발 방지에 쓸 negative constraint만 추출한다.
형식: [RULE-XXX] (날짜) DO NOT: 행동. REASON: 사유."""


class Memory:
    def __init__(self, backend: LLMBackend, rule_path: str):
        self.backend = backend
        self.rule_path = rule_path

    def run(self, review: dict, failure_log: list) -> str:
        # TODO: 신규 룰 추출 → 기존 룰과 모순 검사 → Rule.md append
        # TODO: Rule.history.jsonl에 변경 이력 기록
        resp = self.backend.call(
            system=MEMORY_PERSONA,
            prompt=f"REVIEW:\n{review}\n\nFAILURES:\n{failure_log}",
            allowed_tools=[],
            temperature=0.0,
        )
        return resp.content
