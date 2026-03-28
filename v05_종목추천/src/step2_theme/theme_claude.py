from __future__ import annotations
"""
Step 2: Claude CLI로 테마 판단.
뉴스 + 매크로 수치 → 오늘 유효 테마 + 수혜 섹터 + 후보 종목 방향.
"""

import json
import logging

from src.utils.claude_cli import ask_claude

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """당신은 주식시장 테마 분석 전문가입니다.
아래 오늘의 시장 데이터를 분석하여 단타/스윙 관점에서 유효한 테마와 수혜 종목 방향을 제시하세요.

=== 시장 데이터 ===
{market_data}

=== 매크로 지표 ===
{macro_data}

아래 JSON 형식으로 반환하세요:
{{
  "analysis_date": "날짜",
  "market_summary": "오늘 시장 전체 분위기 2~3줄",
  "themes": [
    {{
      "theme_name": "테마명",
      "trading_type": "단타/스윙/둘다",
      "strength": "강/중/약",
      "reason": "왜 오늘 이 테마가 유효한지 근거",
      "duration": "당일/2~3일/1주일+",
      "sectors_kr": ["국장 수혜 섹터"],
      "sectors_us": ["미장 수혜 섹터"],
      "tickers_hint_kr": ["국장 관련 예시 종목 2~3개"],
      "tickers_hint_us": ["미장 관련 예시 종목 2~3개"],
      "risk": "이 테마의 리스크 요인"
    }}
  ],
  "avoid_sectors": [
    {{"sector": "섹터명", "reason": "피해야 하는 이유"}}
  ],
  "overall_strategy": "오늘 전체 매매 전략 한 줄 요약"
}}

규칙:
- themes는 3~5개 (강도 순 정렬)
- 근거 없는 테마는 제외
- 단타는 당일~2일, 스윙은 1주일+ 기준"""


def analyze_themes(
    news_data: dict,
    macro_data: dict,
    market: str = "all",
) -> dict:
    """
    뉴스 + 매크로 → 테마 판단.

    Args:
        news_data: Step 1 뉴스 수집 결과
        macro_data: Step 1 매크로 수치
        market: "kr" | "us" | "all"
    """
    # 매크로 요약 텍스트
    macro_lines = []
    for k, v in macro_data.items():
        if isinstance(v, dict) and "price" in v:
            macro_lines.append(
                f"- {k}: {v['price']} ({v.get('change_pct', 0):+.1f}%)"
            )
    macro_text = "\n".join(macro_lines) if macro_lines else "데이터 없음"

    # 뉴스 요약 텍스트
    market_text = json.dumps(news_data, ensure_ascii=False, indent=2)
    # 너무 길면 자르기
    if len(market_text) > 8000:
        market_text = market_text[:8000] + "\n...(truncated)"

    prompt = PROMPT_TEMPLATE.format(
        market_data=market_text,
        macro_data=macro_text,
    )

    logger.info("Analyzing themes via Claude CLI...")
    result = ask_claude(prompt, expect_json=True, context="step2_theme")
    return result


def format_themes_summary(themes_data: dict) -> str:
    """테마 분석 결과를 터미널 출력용 텍스트로 변환."""
    lines = [f"\n  시장 요약: {themes_data.get('market_summary', '')}",
             f"  전략: {themes_data.get('overall_strategy', '')}",
             ""]
    for t in themes_data.get("themes", []):
        lines.append(
            f"  [{t.get('strength','?')}] {t.get('theme_name','')} "
            f"({t.get('trading_type','')} / {t.get('duration','')})"
        )
        lines.append(f"    → {t.get('reason','')[:60]}")
    return "\n".join(lines)
