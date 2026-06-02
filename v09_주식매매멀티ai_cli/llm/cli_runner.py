"""Claude Code CLI 헤드리스 모드 (`claude -p`) 래퍼.

매수자 인계 시 이 클래스만 AnthropicAPIRunner 로 교체하면 API 모드로 전환.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass

from llm.base import LLMError, LLMResponse, LLMRunner, RateLimitError

log = logging.getLogger(__name__)


@dataclass
class ClaudeCodeCLIRunner:
    """`claude -p` subprocess 호출. 구독 OAuth 사용."""

    name: str = "claude-cli"
    binary: str = "claude"
    default_model: str = "claude-opus-4-7"
    timeout_seconds: int = 120

    def __post_init__(self) -> None:
        if os.environ.get("ANTHROPIC_API_KEY"):
            # 환경변수가 있으면 구독 무시하고 API 결제 — 명시적 경고
            log.warning(
                "ANTHROPIC_API_KEY 가 설정돼 있습니다. Claude Code 는 구독 대신 API 로 결제됩니다. "
                "비용을 피하려면: unset ANTHROPIC_API_KEY"
            )

    async def call(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.7,  # CLI 는 temperature 직접 지원 안 함 (메타데이터 기록용)
        max_tokens: int = 1024,    # CLI 는 max_tokens 직접 지원 안 함 (메타데이터 기록용)
        cache_prefix: str | None = None,
    ) -> LLMResponse:
        model = model or self.default_model
        cmd = [
            self.binary,
            "-p",
            "--output-format", "json",
            "--no-session-persistence",
            "--system-prompt", system,
            "--model", model,
            "--tools", "",                  # 도구 사용 차단 — 순수 텍스트 응답만
            "--permission-mode", "dontAsk", # 권한 프롬프트 차단
            user,
        ]

        start = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError as e:
            proc.kill()
            raise LLMError(f"claude -p timeout {self.timeout_seconds}s") from e

        latency_ms = int((time.monotonic() - start) * 1000)

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")
            if "rate" in err.lower() and "limit" in err.lower():
                raise RateLimitError(err.strip())
            raise LLMError(f"claude exit={proc.returncode}: {err.strip()}")

        return self._parse(stdout.decode("utf-8"), model, latency_ms)

    def _parse(self, raw_output: str, model: str, latency_ms: int) -> LLMResponse:
        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError as e:
            raise LLMError(f"claude json 파싱 실패: {e}\n원본: {raw_output[:500]}") from e

        # Claude Code CLI --output-format json 응답:
        #   { "result": "...", "session_id": "...", "total_cost_usd": 0.0,
        #     "usage": { "input_tokens": ..., "output_tokens": ..., ... } }
        text = payload.get("result", "") or payload.get("text", "")
        usage = payload.get("usage", {}) or {}

        return LLMResponse(
            text=text.strip(),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            cost_usd=payload.get("total_cost_usd", 0.0),
            latency_ms=latency_ms,
            model=model,
            raw=payload,
        )
