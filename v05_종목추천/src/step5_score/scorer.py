from __future__ import annotations
"""
Step 5-1: 최종 종합 점수 계산.
테마 관련성 + 차트 + 수급 + 재무 → 종합 점수.
"""

import logging
from src.utils.config import SCORING

logger = logging.getLogger(__name__)

# 기본 가중치 (settings.yaml 우선)
DEFAULT_WEIGHTS = {
    "theme_relevance": 30,
    "chart": 30,
    "supply_demand": 20,
    "financial": 20,
}

STRENGTH_SCORES = {"강": 90, "중": 70, "약": 50}


def calc_theme_score(stock: dict) -> float:
    """테마 관련성 점수 (0~100)."""
    strength = stock.get("theme_strength", "중")
    base = STRENGTH_SCORES.get(strength, 70)

    # 리서치 결과 보정
    research = stock.get("research", {})
    momentum = research.get("momentum", "neutral")
    if momentum == "bullish":
        base += 10
    elif momentum == "bearish":
        base -= 15

    # 호재 수
    catalysts = research.get("catalysts", [])
    high_impact = sum(1 for c in catalysts if c.get("impact") == "high" and c.get("type") == "호재")
    base += high_impact * 5

    return min(100, max(0, base))


def calc_supply_demand_score(stock: dict) -> float:
    """수급 점수: 거래량 비율 + 추세 (0~100)."""
    chart_result = stock.get("chart_result", {})
    indicators = chart_result.get("raw_indicators", {})

    vol_ratio = indicators.get("volume_ratio", 1.0)
    trend = indicators.get("trend", "sideways")

    score = 50.0

    # 거래량 급증
    if vol_ratio >= 3.0:
        score += 25
    elif vol_ratio >= 2.0:
        score += 15
    elif vol_ratio >= 1.5:
        score += 8
    elif vol_ratio < 0.5:
        score -= 10

    # 추세
    if trend == "uptrend":
        score += 15
    elif trend == "downtrend":
        score -= 15

    return min(100, max(0, score))


def calc_final_score(stock: dict) -> dict:
    """
    종합 점수 계산.

    Args:
        stock: {
            "ticker": ..., "name": ..., "theme": ..., "theme_strength": ...,
            "research": {...},          # step3 결과
            "chart_result": {...},      # step4 결과
            "financial_score": 0~100,  # step3 재무
            "dart_risk": {...},
        }

    Returns:
        stock with "final_score", "score_detail" added
    """
    weights = SCORING if SCORING else DEFAULT_WEIGHTS

    theme_score = calc_theme_score(stock)
    chart_score = stock.get("chart_result", {}).get("chart_score", 50)
    supply_score = calc_supply_demand_score(stock)
    financial_score = stock.get("financial_score", 50)

    w_theme = weights.get("theme_relevance", 30) / 100
    w_chart = weights.get("chart", 30) / 100
    w_supply = weights.get("supply_demand", 20) / 100
    w_financial = weights.get("financial", 20) / 100

    weighted = (
        theme_score * w_theme
        + chart_score * w_chart
        + supply_score * w_supply
        + financial_score * w_financial
    )

    # DART 패널티
    dart_penalty = stock.get("dart_risk", {}).get("risk_score", 0)

    final = round(weighted + dart_penalty, 1)

    return {
        **stock,
        "final_score": final,
        "score_detail": {
            "theme": round(theme_score, 1),
            "chart": round(chart_score, 1),
            "supply_demand": round(supply_score, 1),
            "financial": round(financial_score, 1),
            "dart_penalty": dart_penalty,
            "weighted_sum": round(weighted, 1),
        },
    }


def rank_stocks(stocks: list[dict]) -> list[dict]:
    """최종 점수 순 정렬."""
    scored = [calc_final_score(s) for s in stocks]
    scored.sort(key=lambda x: x.get("final_score", 0), reverse=True)
    for i, s in enumerate(scored):
        s["rank"] = i + 1
    return scored
