"""
AI Agent wrappers — 두 CLI(Claude / Gemini)를 동일 인터페이스로 감싼다.
둘 다 OAuth 구독 인증을 사용하므로 API key 없이 동작한다.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class Turn:
    speaker: str
    text: str


def build_prompt(name: str, system: str, history: list[Turn]) -> str:
    """매 턴마다 system + 전체 히스토리 + 다음 발화 지시를 하나의 prompt로 합친다."""
    parts = [f"[너의 정체성]\n{system}\n"]
    if history:
        parts.append("[지금까지의 대화]")
        for t in history:
            parts.append(f"{t.speaker}: {t.text}")
        parts.append("")
    parts.append(
        f"[너({name})의 다음 발언을 한국어로 2~4문장으로 자연스럽게 작성해라. "
        f"발언 본문만 출력하고, 이름표('Claude:' 등)나 따옴표는 붙이지 마라.]"
    )
    return "\n".join(parts)


class Agent:
    name: str
    model: str

    def ask(self, history: list[Turn], system: str) -> str:
        raise NotImplementedError


class ClaudeAgent(Agent):
    name = "Claude"
    model = "claude-sonnet-4-6"

    def ask(self, history: list[Turn], system: str) -> str:
        prompt = build_prompt(self.name, system, history)
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", self.model],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr[:300]}")
        return result.stdout.strip()


class GeminiAgent(Agent):
    name = "Gemini"
    model = "gemini-3.1-pro-preview"

    # Gemini CLI가 stdout 앞에 찍는 무해한 노이즈 라인들
    _NOISE = (
        "Keychain initialization",
        "FileKeychain",
        "Loaded cached credentials",
    )

    def ask(self, history: list[Turn], system: str) -> str:
        prompt = build_prompt(self.name, system, history)
        result = subprocess.run(
            ["gemini", "-p", prompt, "-m", self.model],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Gemini CLI failed: {result.stderr[:300]}")
        lines = [
            line for line in result.stdout.splitlines()
            if not any(noise in line for noise in self._NOISE)
        ]
        return "\n".join(lines).strip()
