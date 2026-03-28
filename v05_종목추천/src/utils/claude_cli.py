from __future__ import annotations
"""
Claude CLI subprocess 래퍼.
claude -p "..." --output-format json --allowedTools WebSearch
"""

import json
import logging
import subprocess
from src.utils.config import now_kst
from pathlib import Path

from src.utils.config import DATA_DIR

logger = logging.getLogger(__name__)
CLAUDE_LOG = DATA_DIR / "logs" / "claude_usage.jsonl"


def ask_claude(
    prompt: str,
    *,
    expect_json: bool = True,
    allow_search: bool = False,
    timeout: int = 120,
    context: str = "",
) -> dict | list | str:
    """
    Claude CLI 호출.

    Args:
        prompt: 프롬프트 텍스트
        expect_json: True면 result 필드를 JSON 파싱해서 반환
        allow_search: WebSearch 툴 허용 여부
        timeout: 타임아웃 (초)
        context: 로그용 컨텍스트

    Returns:
        expect_json=True → dict/list
        expect_json=False → str
    """
    cmd = ["claude", "-p", prompt, "--output-format", "json"]
    if allow_search:
        cmd += ["--allowedTools", "WebSearch"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            logger.error(f"Claude CLI error: {result.stderr[:200]}")
            raise RuntimeError(f"Claude CLI failed: {result.stderr[:200]}")

        raw = json.loads(result.stdout)

        if raw.get("is_error"):
            raise RuntimeError(f"Claude error: {raw.get('result', '')}")

        # 사용량 로깅
        _log_usage(raw, context)

        text = raw.get("result", "").strip()

        if not expect_json:
            return text

        return _extract_json(text)

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Claude CLI timeout ({timeout}s)")
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        if not expect_json:
            return text
        raise


def _extract_json(text: str) -> dict | list:
    """
    텍스트에서 JSON 블록을 추출해 파싱.
    ```json ... ``` 코드블록 우선, 없으면 { } / [ ] 범위를 직접 탐색.
    여러 후보 중 가장 긴 것부터 시도.
    """
    # 1) ```json ... ``` 또는 ``` ... ``` 코드블록 우선 추출
    import re
    code_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text)
    candidates = [b.strip() for b in code_blocks if b.strip().startswith(("{", "["))]

    # 2) 코드블록 없으면 { } [ ] 범위 탐색 (가장 바깥 괄호 기준)
    if not candidates:
        for opener, closer in [("{", "}"), ("[", "]")]:
            start = text.find(opener)
            if start == -1:
                continue
            # rfind로 가장 마지막 닫는 괄호 사용
            end = text.rfind(closer)
            if end > start:
                candidates.append(text[start:end + 1])

    # 3) 긴 것부터 파싱 시도
    candidates.sort(key=len, reverse=True)
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    # 4) 전체 텍스트 파싱 시도
    return json.loads(text)


def _log_usage(raw: dict, context: str) -> None:
    CLAUDE_LOG.parent.mkdir(parents=True, exist_ok=True)
    usage = raw.get("usage", {})
    cost = raw.get("total_cost_usd", 0)
    entry = {
        "timestamp": now_kst().isoformat(),
        "context": context,
        "cost_usd": cost,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "model": list(raw.get("modelUsage", {}).keys())[0] if raw.get("modelUsage") else "unknown",
    }
    with open(CLAUDE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_claude_usage() -> dict:
    """누적 Claude CLI 사용량 반환."""
    if not CLAUDE_LOG.exists():
        return {"total_cost_usd": 0, "this_month_cost_usd": 0, "total_calls": 0}

    total_cost = month_cost = total_calls = 0
    month_prefix = now_kst().strftime("%Y-%m")

    with open(CLAUDE_LOG, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
                total_cost += e.get("cost_usd", 0)
                total_calls += 1
                if e.get("timestamp", "").startswith(month_prefix):
                    month_cost += e.get("cost_usd", 0)
            except Exception:
                pass

    return {
        "total_calls": total_calls,
        "total_cost_usd": round(total_cost, 4),
        "this_month_cost_usd": round(month_cost, 4),
    }
