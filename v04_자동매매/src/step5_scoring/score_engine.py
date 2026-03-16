"""
Step 5: 통합 스코어링 엔진.

점수 구성 (100점 + VIX 보너스 10점):
  - 로직체인 매칭 강도: 30점
  - 스마트머니 시그널: 20점
  - 거래량/수급 신호: 20점
  - 차트 기술적 스코어: 20점
  - VIX 가산점: +10점 (별도)
  - 리스크 패널티: -10점
"""

import logging
from datetime import datetime

from src.utils.config import VIX_BONUS_RANGES

logger = logging.getLogger(__name__)


def calc_logic_chain_score(
    matched_chains: list[dict],
    scenarios: list[dict],
) -> float:
    """
    로직체인 매칭 강도 (0~30점).

    = 최고 유사도 × 체인 intensity × historical_accuracy
    """
    if not matched_chains and not scenarios:
        return 0.0

    score = 0.0

    if matched_chains:
        best = matched_chains[0]
        similarity = best.get("similarity", 0)
        intensity_mult = {"high": 1.0, "medium": 0.7, "low": 0.4}.get(
            best.get("intensity", "medium"), 0.7
        )
        accuracy = best.get("historical_accuracy", 0.5) or 0.5

        score = similarity * intensity_mult * accuracy * 30

    elif scenarios:
        # No chain match, but AI scenarios exist → lower score
        best = scenarios[0]
        probability = best.get("probability", 0.3)
        score = probability * 15  # Max 15 if no DB match

    return round(min(score, 30), 2)


def calc_smart_money_score(smart_money_result: dict, ticker: str) -> float:
    """
    스마트머니 시그널 (0~20점).

    - 내부자 매수: +8
    - 거래량 급증: +7
    - 공매도 급감: +5
    """
    score = 0.0

    # Insider trades for this ticker
    insider_trades = [
        t for t in smart_money_result.get("insider_trades", [])
        if t.get("ticker") == ticker
    ]
    if insider_trades:
        score += min(8, len(insider_trades) * 4)

    # Volume surge for this ticker
    surges = [
        s for s in smart_money_result.get("volume_surges", [])
        if s.get("ticker") == ticker
    ]
    if surges:
        ratio = surges[0].get("surge_ratio", 1)
        score += min(7, (ratio - 1) * 3.5)

    # Low short interest = bullish
    si = smart_money_result.get("short_interest", {}).get(ticker)
    if si:
        short_pct = si.get("short_pct_float", 50)
        if short_pct < 5:
            score += 5
        elif short_pct < 10:
            score += 3
        elif short_pct < 15:
            score += 1

    return round(min(score, 20), 2)


def calc_volume_score(stock_info: dict) -> float:
    """
    거래량/수급 신호 (0~20점).

    - volume_ratio (20일 평균 대비): 최대 15점
    - institutional_pct: 최대 5점
    """
    score = 0.0

    ratio = stock_info.get("volume_ratio", 1.0)
    if ratio >= 3.0:
        score += 15
    elif ratio >= 2.0:
        score += 10
    elif ratio >= 1.5:
        score += 7
    elif ratio >= 1.2:
        score += 3

    inst_pct = stock_info.get("institutional_pct", 0)
    if inst_pct >= 80:
        score += 5
    elif inst_pct >= 60:
        score += 3
    elif inst_pct >= 40:
        score += 1

    return round(min(score, 20), 2)


def calc_chart_score(technical_result: dict, pattern_result: dict) -> float:
    """
    차트 기술적 스코어 (0~20점).

    = technical indicators (max 12) + patterns (max 8)
    """
    tech = min(technical_result.get("total", 0), 12)
    pattern = min(pattern_result.get("total", 0), 8)
    return round(min(tech + pattern, 20), 2)


def calc_vix_bonus(vix_data: dict) -> float:
    """VIX 가산점 (0~10점)."""
    vix_val = vix_data.get("vix", 0)

    for r in VIX_BONUS_RANGES:
        if vix_val <= r.get("max", 999):
            return float(r.get("bonus", 0))

    return 0.0


def calc_risk_penalty(stock_info: dict) -> float:
    """
    리스크 패널티 (0 ~ -10점).

    - 이미 30%+ 급등: -5
    - 공매도 30%+: -3
    - 어닝 직전: -2
    """
    penalty = 0.0

    # High short interest risk
    if stock_info.get("short_pct", 0) > 30:
        penalty -= 3

    return round(max(penalty, -10), 2)


def score_stock(
    ticker: str,
    stock_info: dict,
    matched_chains: list[dict],
    scenarios: list[dict],
    smart_money_result: dict,
    vix_data: dict,
    technical_result: dict,
    pattern_result: dict,
) -> dict:
    """
    단일 종목 통합 스코어링.

    Returns:
        {
            "ticker": str,
            "total_score": float,
            "breakdown": {...},
            "recommendation": str,
        }
    """
    logic = calc_logic_chain_score(matched_chains, scenarios)
    smart = calc_smart_money_score(smart_money_result, ticker)
    volume = calc_volume_score(stock_info)
    chart = calc_chart_score(technical_result, pattern_result)
    vix_bonus = calc_vix_bonus(vix_data)
    risk = calc_risk_penalty(stock_info)

    total = logic + smart + volume + chart + vix_bonus + risk

    # Confidence level
    if total >= 75:
        confidence = "high"
    elif total >= 55:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "ticker": ticker,
        "name": stock_info.get("name", ticker),
        "total_score": round(total, 2),
        "breakdown": {
            "logic_chain_score": logic,
            "smart_money_score": smart,
            "volume_score": volume,
            "chart_score": chart,
            "vix_bonus": vix_bonus,
            "risk_penalty": risk,
        },
        "confidence": confidence,
        "sector": stock_info.get("sector", "Unknown"),
        "market_cap": stock_info.get("market_cap", 0),
        "current_price": stock_info.get("current_price", 0),
        "timestamp": datetime.now().isoformat(),
    }


def rank_stocks(scored_stocks: list[dict]) -> list[dict]:
    """점수순 정렬 + 순위 부여."""
    ranked = sorted(scored_stocks, key=lambda x: x["total_score"], reverse=True)
    for i, stock in enumerate(ranked):
        stock["rank"] = i + 1
    return ranked
