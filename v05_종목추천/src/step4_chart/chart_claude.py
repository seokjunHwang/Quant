from __future__ import annotations
"""
Step 4-2: 차트 분석 (코드 기반 채점).
기술적 지표 → 룰 기반 점수 (Claude 호출 없음 — 24회 절약).
"""

import logging

from src.step4_chart.chart_scorer import calc_chart_score

logger = logging.getLogger(__name__)


def analyze_chart_claude(
    ticker: str,
    name: str,
    theme: str,
    market: str,
    chart_indicators: dict,
) -> dict:
    """
    기술적 지표 → 코드 룰 기반 차트 점수 + 매매 타이밍.
    (기존 Claude CLI 호출을 코드 채점으로 대체)
    """
    result = calc_chart_score(chart_indicators)
    result["ticker"] = ticker
    return result


def analyze_charts_batch(
    candidates: list[dict],
    ohlcv_map: dict,
    max_stocks: int = 40,
) -> list[dict]:
    """
    후보 종목 차트 일괄 분석 (코드 기반 — 즉시 완료).
    """
    from src.step4_chart.indicators import analyze_chart

    targets = candidates[:max_stocks]
    results = []

    for i, stock in enumerate(targets):
        ticker = stock.get("ticker", "")
        name = stock.get("name", ticker)
        theme = stock.get("theme", "")
        market = stock.get("market", "us")

        df = ohlcv_map.get(ticker)
        indicators = analyze_chart(df) if df is not None else {}

        logger.info(f"  [{i+1}/{len(targets)}] {name}({ticker}) 차트 채점...")
        try:
            result = analyze_chart_claude(ticker, name, theme, market, indicators)
            result["raw_indicators"] = indicators
            results.append(result)
        except Exception as e:
            logger.warning(f"  [{ticker}] 차트 채점 실패: {e}")
            results.append({
                "ticker": ticker,
                "chart_score": 50,
                "timing": "관망",
                "chart_summary": f"채점 오류: {e}",
                "signals": [],
                "warnings": [],
                "score_breakdown": {},
                "raw_indicators": indicators,
            })

    return results
