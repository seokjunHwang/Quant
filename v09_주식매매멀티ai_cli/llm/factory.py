"""config.yml 의 runner.type 에 따라 적절한 LLMRunner 반환."""

from __future__ import annotations

from llm.base import LLMRunner
from llm.cli_runner import ClaudeCodeCLIRunner
from llm.mock_runner import MockRunner


def build_runner(config: dict) -> LLMRunner:
    runner_cfg = config.get("runner", {})
    rtype = runner_cfg.get("type", "claude_cli")

    if rtype == "claude_cli":
        return ClaudeCodeCLIRunner(
            binary=runner_cfg.get("cli_binary", "claude"),
            default_model=runner_cfg.get("default_model", "claude-opus-4-7"),
            timeout_seconds=runner_cfg.get("timeout_seconds", 120),
        )
    if rtype == "mock":
        return MockRunner()
    if rtype == "anthropic_api":
        # 매수자가 API 모드 원할 때 — 별도 구현 (Phase 7+)
        raise NotImplementedError(
            "anthropic_api runner 는 매수자 요청 시 구현. "
            "현재는 claude_cli 또는 mock 만 지원."
        )
    raise ValueError(f"알 수 없는 runner.type: {rtype}")
