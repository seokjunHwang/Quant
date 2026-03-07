"""
Step 1: Trend Discovery — Perplexity API로 현재 핫한 투자 테마를 발굴하고 랭킹.

테마 랭킹 기준 (5항목, 각 20점 = 100점 만점):
  1. 자금 쏠림 강도 — 관련 ETF/섹터에 자금이 얼마나 몰리는가
  2. 지속 기간 전망 — 단기 이벤트(~5점) / 중기 1-3개월(~12점) / 장기 6개월+(~18점)
  3. 수혜 경로 명확성 — 테마 → 기업 매출 증가로 이어지는 로직이 명확한가
  4. 정책/규제 순풍 — 정부 예산, 규제완화, 보조금 등 정책 지원 여부
  5. 시장 컨센서스 — 애널리스트/미디어 관심도
"""

import json
import logging

import httpx

from app.config import settings
from app.models.schemas import TrendTheme

logger = logging.getLogger(__name__)

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

THEME_DISCOVERY_PROMPT = """You are an expert financial market analyst specializing in thematic investing.

Identify the top {count} trending investment themes in the current global market RIGHT NOW.

Focus on themes where small/mid-cap stocks ($100M-$10B market cap) can benefit the most.
Consider: geopolitical events, policy changes, technology shifts, sector rotations, macro trends.

For each theme, score on these criteria (0-20 points each):
1. Capital Flow Intensity (urgency_score): How much capital is actively flowing into this sector NOW. ETF inflows, sector volume spikes.
2. Duration Outlook (duration_score): Expected duration. Flash event=5, short 1-4 weeks=8, medium 1-3 months=12, long 6+ months=18.
3. Revenue Path Clarity (clarity_score): How directly does this theme translate to company earnings growth.
4. Policy/Regulatory Tailwind (policy_score): Government support, budget increases, deregulation, subsidies.
5. Market Consensus (consensus_score): Wall Street analyst coverage, major media attention level.

IMPORTANT: Return ONLY a valid JSON array, no other text. Example format:
[
  {{
    "rank": 1,
    "theme": "Defense & Military Drones",
    "description": "Brief description of why this theme is hot",
    "urgency_score": 18,
    "duration_score": 14,
    "clarity_score": 17,
    "policy_score": 16,
    "consensus_score": 15,
    "total_score": 80,
    "reasoning": "Detailed reasoning with specific recent events, data points"
  }}
]

Return exactly {count} themes, ranked by total_score descending."""


def _parse_json_response(text: str) -> list[dict]:
    """AI 응답에서 JSON 배열을 추출."""
    text = text.strip()

    # ```json ... ``` 블록 처리
    if "```" in text:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            text = text[start:end]

    # 순수 JSON이 아닌 경우 배열 부분만 추출
    if not text.startswith("["):
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            text = text[start:end]

    return json.loads(text)


def discover_themes(count: int | None = None) -> list[TrendTheme]:
    """
    Perplexity API를 사용해 현재 핫한 투자 테마를 발굴.

    Returns:
        테마 리스트 (total_score 내림차순)
    """
    count = count or settings.TOP_THEMES_COUNT

    if not settings.PERPLEXITY_API_KEY:
        logger.error("PERPLEXITY_API_KEY is not configured")
        return []

    prompt = THEME_DISCOVERY_PROMPT.format(count=count)

    try:
        response = httpx.post(
            PERPLEXITY_URL,
            headers={
                "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar-pro",
                "messages": [
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
            },
            timeout=60.0,
        )
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        raw_themes = _parse_json_response(content)

        themes = []
        for item in raw_themes:
            # total_score 재계산 (AI가 잘못 합산할 수 있으므로)
            calculated_total = (
                item.get("urgency_score", 0)
                + item.get("duration_score", 0)
                + item.get("clarity_score", 0)
                + item.get("policy_score", 0)
                + item.get("consensus_score", 0)
            )
            item["total_score"] = calculated_total

            themes.append(TrendTheme(**item))

        # total_score 내림차순 정렬 + rank 재부여
        themes.sort(key=lambda t: t.total_score, reverse=True)
        for i, theme in enumerate(themes):
            theme.rank = i + 1

        logger.info(f"Discovered {len(themes)} themes: {[t.theme for t in themes]}")
        return themes

    except httpx.HTTPStatusError as e:
        logger.error(f"Perplexity API HTTP error: {e.response.status_code} - {e.response.text}")
        return []
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f"Failed to parse Perplexity response: {e}")
        return []
    except Exception as e:
        logger.error(f"Trend discovery failed: {e}")
        return []
