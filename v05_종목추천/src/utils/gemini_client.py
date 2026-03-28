from __future__ import annotations
"""
Gemini AI Client — Primary 3회 재시도 + Fallback.
Google Search grounding 지원.
검색 쿼리 수 → data/logs/search_usage.jsonl 기록.
"""

import json
import logging
import time
from src.utils.config import now_kst
from pathlib import Path

from google import genai
from google.genai import types

from src.utils.config import DATA_DIR, GEMINI_API_KEY, GEMINI_FALLBACK_MODEL, GEMINI_PRIMARY_MODEL

logger = logging.getLogger(__name__)

_client: genai.Client | None = None
SEARCH_LOG = DATA_DIR / "logs" / "search_usage.jsonl"


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY not set")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _log_search(model: str, query_count: int, context: str) -> None:
    SEARCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SEARCH_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": now_kst().isoformat(),
            "model": model,
            "search_queries": query_count,
            "context": context,
        }, ensure_ascii=False) + "\n")


def get_search_usage() -> dict:
    if not SEARCH_LOG.exists():
        return {"total": 0, "this_month": 0, "free_remaining": 5000}
    total = this_month = 0
    month_prefix = now_kst().strftime("%Y-%m")
    with open(SEARCH_LOG, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
                q = e.get("search_queries", 0)
                total += q
                if e.get("timestamp", "").startswith(month_prefix):
                    this_month += q
            except Exception:
                pass
    return {
        "total": total,
        "this_month": this_month,
        "free_remaining": max(0, 5000 - this_month),
        "overage": max(0, this_month - 5000),
        "overage_cost_usd": round(max(0, this_month - 5000) / 1000 * 14, 4),
    }


def generate(
    prompt: str,
    *,
    system_instruction: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 8192,
    json_mode: bool = False,
    use_search: bool = False,
    search_context: str = "",
) -> str:
    client = _get_client()
    config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    if system_instruction:
        config.system_instruction = system_instruction
    if json_mode:
        config.response_mime_type = "application/json"
    if use_search:
        config.tools = [types.Tool(google_search=types.GoogleSearch())]

    attempts = [
        (GEMINI_PRIMARY_MODEL, 1),
        (GEMINI_PRIMARY_MODEL, 2),
        (GEMINI_PRIMARY_MODEL, 3),
        (GEMINI_FALLBACK_MODEL, 1),
    ]

    for model_name, attempt in attempts:
        is_last = model_name == GEMINI_FALLBACK_MODEL
        try:
            response = client.models.generate_content(
                model=model_name, contents=prompt, config=config,
            )
            text = response.text
            if text:
                if use_search:
                    try:
                        meta = response.candidates[0].grounding_metadata
                        q = len(meta.web_search_queries or []) if meta else 1
                    except Exception:
                        q = 1
                    _log_search(model_name, q, search_context)
                return text.strip()
            logger.warning(f"[{model_name}] Empty response (attempt {attempt})")
        except Exception as e:
            logger.warning(f"[{model_name}] Error (attempt {attempt}): {e}")
            if is_last:
                raise
        if not is_last:
            time.sleep(2 ** attempt)

    raise RuntimeError("All Gemini attempts failed")


def generate_json(
    prompt: str,
    *,
    system_instruction: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 8192,
    use_search: bool = False,
    search_context: str = "",
) -> list | dict:
    text = generate(
        prompt,
        system_instruction=system_instruction,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=True,
        use_search=use_search,
        search_context=search_context,
    )
    if "```" in text:
        start = text.find("[") if "[" in text else text.find("{")
        end = max(text.rfind("]"), text.rfind("}")) + 1
        if start != -1 and end > start:
            text = text[start:end]
    return json.loads(text)
