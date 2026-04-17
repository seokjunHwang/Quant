"""
AI끼리 대화 — Claude(Sonnet 4.6) ↔ Gemini(3.1 Pro Preview) 자유 토론 테스트.

규칙:
- 주제: 간단한 자기소개 후 서로 한 가지씩 질문하기
- 턴 수: 각자 2번씩 (총 4턴)
- Claude 선공
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from agents import ClaudeAgent, GeminiAgent, Turn


SYSTEM_PROMPT = (
    "너는 다른 회사가 만든 또 다른 AI와 직접 대화 중이다. "
    "이번 대화의 목표는: (1) 첫 발화에서 너 자신을 한두 문장으로 간단히 소개하고, "
    "(2) 상대방에게 궁금한 점을 한 가지 질문하는 것이다. "
    "이후 턴에서는 상대 질문에 답하면서 대화를 자연스럽게 이어가라. "
    "말투는 친근하고 솔직하게, 거창한 미사여구 없이."
)

TURNS_PER_AGENT = 2
LOG_DIR = Path(__file__).parent / "logs"


def main() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

    claude = ClaudeAgent()
    gemini = GeminiAgent()
    # Claude가 먼저, 이후 교대 (총 4턴)
    order = [claude, gemini] * TURNS_PER_AGENT

    print("=" * 60)
    print(f"AI vs AI Chat Test")
    print(f"  Claude: {claude.model}")
    print(f"  Gemini: {gemini.model}")
    print(f"  Turns:  {len(order)} (각자 {TURNS_PER_AGENT}회)")
    print(f"  Log:    {log_path}")
    print("=" * 60)
    print()

    history: list[Turn] = []
    for i, agent in enumerate(order, start=1):
        print(f"--- Turn {i}/{len(order)} · {agent.name} ---")
        t0 = time.time()
        try:
            text = agent.ask(history, SYSTEM_PROMPT)
        except Exception as e:
            print(f"[ERROR] {agent.name}: {e}")
            break
        latency = round(time.time() - t0, 2)

        print(text)
        print(f"(⏱ {latency}s)\n")

        history.append(Turn(speaker=agent.name, text=text))
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "turn": i,
                "speaker": agent.name,
                "model": agent.model,
                "latency_sec": latency,
                "text": text,
            }, ensure_ascii=False) + "\n")

    print("=" * 60)
    print(f"Done. {len(history)} turns saved to {log_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
