"""
Gemini AI Client — Primary + Fallback 모델 자동 전환.

Primary:  gemini-2.5-flash-preview-05-20
Fallback: gemini-2.0-flash-lite
"""

import json
import logging
import time

from google import genai
from google.genai import types

from src.utils.config import GEMINI_API_KEY, GEMINI_FALLBACK_MODEL, GEMINI_PRIMARY_MODEL

logger = logging.getLogger(__name__)

# Module-level client (singleton)
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def generate(
    prompt: str,
    *,
    system_instruction: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 8192,
    json_mode: bool = False,
) -> str:
    """
    Gemini API 호출. Primary 실패 시 Fallback 자동 전환.

    Returns:
        응답 텍스트
    """
    client = _get_client()

    config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    if system_instruction:
        config.system_instruction = system_instruction
    if json_mode:
        config.response_mime_type = "application/json"

    # Try primary, then fallback
    for model_name in [GEMINI_PRIMARY_MODEL, GEMINI_FALLBACK_MODEL]:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            text = response.text
            if text:
                logger.debug(f"[{model_name}] Response: {len(text)} chars")
                return text.strip()

            logger.warning(f"[{model_name}] Empty response, trying fallback...")

        except Exception as e:
            logger.warning(f"[{model_name}] Error: {e}")
            if model_name == GEMINI_FALLBACK_MODEL:
                raise
            time.sleep(1)

    raise RuntimeError("Both Gemini models failed")


def generate_json(
    prompt: str,
    *,
    system_instruction: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 8192,
) -> list | dict:
    """
    Gemini 호출 후 JSON 파싱까지 처리.
    """
    text = generate(
        prompt,
        system_instruction=system_instruction,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=True,
    )

    # Clean up markdown fences if present
    if "```" in text:
        start = text.find("[") if "[" in text else text.find("{")
        end = max(text.rfind("]"), text.rfind("}")) + 1
        if start != -1 and end > start:
            text = text[start:end]

    return json.loads(text)
