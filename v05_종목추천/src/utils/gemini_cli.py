from __future__ import annotations
"""
Gemini CLI subprocess 래퍼 (구독 OAuth 인증, API key 불필요).
gemini -p "..." -m gemini-3.1-pro-preview

호출 횟수는 data/logs/gemini_cli_usage.jsonl 에 누적된다.
Claude CLI 래퍼와 동일한 패턴.
"""

import json
import logging
import re
import subprocess
import time

from src.utils.config import DATA_DIR, now_kst

logger = logging.getLogger(__name__)
GEMINI_CLI_LOG = DATA_DIR / "logs" / "gemini_cli_usage.jsonl"

DEFAULT_MODEL = "gemini-3.1-pro-preview"

# Gemini CLI가 stdout 앞에 찍는 무해한 노이즈 라인들
_NOISE_PREFIXES = (
    "Keychain initialization",
    "Using FileKeychain",
    "Loaded cached credentials",
)


def ask_gemini_cli(
    prompt: str,
    *,
    expect_json: bool = True,
    model: str = DEFAULT_MODEL,
    timeout: int = 900,
    context: str = "",
) -> dict | list | str:
    """
    Gemini CLI 호출.

    Args:
        prompt: 프롬프트 텍스트
        expect_json: True면 응답 텍스트에서 JSON 추출 후 dict/list 반환
        model: 사용 모델 (기본 gemini-3.1-pro-preview)
        timeout: 타임아웃(초)
        context: 로깅용 컨텍스트 라벨

    Returns:
        expect_json=True → dict/list
        expect_json=False → str
    """
    cmd = ["gemini", "-p", prompt, "-m", model]

    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        _log_usage(model, context, success=False, latency=time.time() - t0,
                   error="timeout")
        raise RuntimeError(f"Gemini CLI timeout ({timeout}s)")

    latency = round(time.time() - t0, 2)

    if result.returncode != 0:
        err = (result.stderr or "")[:300]
        _log_usage(model, context, success=False, latency=latency, error=err)
        logger.error(f"Gemini CLI error: {err}")
        raise RuntimeError(f"Gemini CLI failed: {err}")

    text = _strip_noise(result.stdout).strip()
    _log_usage(model, context, success=True, latency=latency)

    if not expect_json:
        return text

    return _extract_json(text)


def _strip_noise(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines()
        if not any(line.startswith(p) or p in line for p in _NOISE_PREFIXES)
    )


def _extract_json(text: str) -> dict | list:
    """
    Gemini CLI 응답 텍스트에서 JSON을 추출.
    1) ```json ... ``` 코드블록 우선
    2) 가장 바깥 { } 또는 [ ] 범위
    3) 후보들 중 가장 긴 것부터 파싱 시도
    """
    code_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text)
    candidates = [b.strip() for b in code_blocks if b.strip().startswith(("{", "["))]

    if not candidates:
        for opener, closer in [("{", "}"), ("[", "]")]:
            start = text.find(opener)
            if start == -1:
                continue
            end = text.rfind(closer)
            if end > start:
                candidates.append(text[start:end + 1])

    candidates.sort(key=len, reverse=True)
    for cand in candidates:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue

    # 마지막 시도: 전체 텍스트
    return json.loads(text)


def _log_usage(
    model: str,
    context: str,
    *,
    success: bool,
    latency: float,
    error: str = "",
) -> None:
    GEMINI_CLI_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": now_kst().isoformat(),
        "context": context,
        "model": model,
        "success": success,
        "latency_sec": round(latency, 2),
    }
    if error:
        entry["error"] = error
    with open(GEMINI_CLI_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_gemini_cli_usage() -> dict:
    """누적 Gemini CLI 호출수 반환 (오늘/이번달/전체, 성공·실패 분리)."""
    if not GEMINI_CLI_LOG.exists():
        return {
            "total_calls": 0, "today_calls": 0, "this_month_calls": 0,
            "today_failures": 0, "daily_quota": 1500,
            "today_remaining": 1500,
        }

    today_prefix = now_kst().strftime("%Y-%m-%d")
    month_prefix = now_kst().strftime("%Y-%m")
    total = today = month = today_fail = 0

    with open(GEMINI_CLI_LOG, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            total += 1
            ts = e.get("timestamp", "")
            if ts.startswith(today_prefix):
                today += 1
                if not e.get("success", True):
                    today_fail += 1
            if ts.startswith(month_prefix):
                month += 1

    return {
        "total_calls": total,
        "today_calls": today,
        "this_month_calls": month,
        "today_failures": today_fail,
        "daily_quota": 1500,                  # Google AI Pro 구독 한도
        "today_remaining": max(0, 1500 - today),
    }
