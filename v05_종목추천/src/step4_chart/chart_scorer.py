from __future__ import annotations
"""
Step 4-2: 코드 기반 차트 점수 산출.
indicators.py 결과를 룰 기반으로 세분화 채점 (Claude 호출 없음).

점수 구성 (0~100):
  - RSI 구간         0~20
  - 볼린저 위치       0~15
  - MACD 신호        0~15
  - 거래량 비율       0~15
  - 추세 정합        0~15
  - 모멘텀           0~10
  - 지지/저항 위치    0~10
"""

import logging

logger = logging.getLogger(__name__)


def score_rsi(rsi: float) -> tuple[float, str]:
    """RSI 구간 점수 (0~20) + 해석."""
    if rsi <= 25:
        return 20.0, "극과매도 — 반등 기대"
    elif rsi <= 30:
        return 17.0, "과매도 — 반등 가능"
    elif rsi <= 40:
        return 14.0, "약과매도 — 매수 관심"
    elif rsi <= 55:
        return 12.0, "중립 하단"
    elif rsi <= 65:
        return 10.0, "중립 상단"
    elif rsi <= 70:
        return 6.0, "과매수 접근 — 주의"
    elif rsi <= 80:
        return 3.0, "과매수 — 차익실현 구간"
    else:
        return 0.0, "극과매수 — 고점 경계"


def score_bollinger(bb_pct: float) -> tuple[float, str]:
    """볼린저밴드 위치 점수 (0~15)."""
    if bb_pct <= 0.05:
        return 15.0, "하단 이탈 — 과매도 반등 기대"
    elif bb_pct <= 0.15:
        return 13.0, "하단 근접 — 매수 기회"
    elif bb_pct <= 0.30:
        return 10.0, "하단~중간 — 상승 여력"
    elif bb_pct <= 0.50:
        return 8.0, "중간 — 중립"
    elif bb_pct <= 0.70:
        return 6.0, "중간~상단 — 추세 유지"
    elif bb_pct <= 0.85:
        return 4.0, "상단 접근 — 과열 주의"
    elif bb_pct <= 0.95:
        return 2.0, "상단 근접 — 과열"
    else:
        return 0.0, "상단 돌파 — 극과열"


def score_macd(macd_cross: str, macd_hist_trend: str = "flat") -> tuple[float, str]:
    """MACD 크로스 + 히스토그램 추세 점수 (0~15)."""
    if macd_cross == "golden":
        return 15.0, "골든크로스 — 강한 매수 신호"
    elif macd_cross == "approaching_golden":
        return 11.0, "골든크로스 임박 — 매수 준비"
    elif macd_cross == "none":
        if macd_hist_trend == "rising":
            return 9.0, "크로스 없으나 히스토그램 상승"
        elif macd_hist_trend == "falling":
            return 4.0, "크로스 없고 히스토그램 하락"
        return 5.0, "중립"
    elif macd_cross == "approaching_dead":
        return 2.0, "데드크로스 임박 — 매도 준비"
    else:  # dead
        return 0.0, "데드크로스 — 매도 신호"


def score_volume(volume_ratio: float, trend: str) -> tuple[float, str]:
    """거래량 비율 점수 (0~15)."""
    if volume_ratio >= 3.0:
        if trend == "uptrend":
            return 15.0, "거래량 폭증 + 상승추세 — 강한 매수세"
        elif trend == "downtrend":
            return 5.0, "거래량 폭증 + 하락 — 투매 가능"
        return 10.0, "거래량 폭증 — 변동성 확대"
    elif volume_ratio >= 2.0:
        if trend == "uptrend":
            return 13.0, "거래량 급증 + 상승 — 매수세 유입"
        return 8.0, "거래량 급증"
    elif volume_ratio >= 1.5:
        return 9.0, "거래량 증가 — 관심 증가"
    elif volume_ratio >= 1.0:
        return 6.0, "평균 거래량"
    elif volume_ratio >= 0.5:
        return 3.0, "거래량 부진 — 관심 저조"
    else:
        return 0.0, "거래 극히 부진"


def score_trend(trend: str, price_change_5d: float, price_change_20d: float) -> tuple[float, str]:
    """추세 정합 점수 (0~15)."""
    score = 0.0
    signals = []

    # 기본 추세
    if trend == "uptrend":
        score += 7
        signals.append("상승추세")
    elif trend == "sideways":
        score += 3
        signals.append("횡보")
    else:
        score += 0
        signals.append("하락추세")

    # 5일 모멘텀 — 추세 방향과 일치하는지
    if trend == "uptrend" and price_change_5d > 0:
        score += 4
        signals.append(f"5일 {price_change_5d:+.1f}% 추세 일치")
    elif trend == "downtrend" and price_change_5d > 3:
        score += 5  # 하락추세에서 반등 — 오히려 매수기회
        signals.append(f"하락추세 내 반등 +{price_change_5d:.1f}%")
    elif price_change_5d > 0:
        score += 2
    elif price_change_5d < -5:
        signals.append(f"5일 급락 {price_change_5d:.1f}%")

    # 20일 중기 추세
    if price_change_20d > 10:
        score += 4
        signals.append("20일 강세")
    elif price_change_20d > 0:
        score += 2
    elif price_change_20d < -10:
        signals.append("20일 약세")

    return min(15.0, score), " / ".join(signals)


def score_momentum(price_change_5d: float, price_change_20d: float) -> tuple[float, str]:
    """모멘텀 점수 (0~10)."""
    score = 5.0  # 기준점

    # 단기 가속도
    if price_change_5d > 10:
        score += 3
    elif price_change_5d > 5:
        score += 2
    elif price_change_5d > 0:
        score += 1
    elif price_change_5d < -10:
        score -= 3
    elif price_change_5d < -5:
        score -= 2
    elif price_change_5d < 0:
        score -= 1

    # 중기-단기 괴리 (mean reversion)
    gap = price_change_5d - price_change_20d
    if gap > 15:  # 단기 과열
        score -= 2
        desc = "단기 과열 (5일 >> 20일)"
    elif gap < -15:  # 단기 과매도
        score += 2
        desc = "단기 과매도 (5일 << 20일)"
    else:
        desc = f"5d:{price_change_5d:+.1f}% / 20d:{price_change_20d:+.1f}%"

    return max(0, min(10.0, score)), desc


def score_support_resistance(
    current_price: float,
    support: float,
    resistance: float,
) -> tuple[float, str]:
    """지지/저항 위치 점수 (0~10)."""
    if resistance == support:
        return 5.0, "지지=저항 (데이터 부족)"

    # 현재가가 지지-저항 범위 내 어디에 있는지 (0=지지, 1=저항)
    position = (current_price - support) / (resistance - support)

    if position <= 0.1:
        return 10.0, f"지지선({support}) 근접 — 반등 기대"
    elif position <= 0.25:
        return 8.0, f"지지선 부근 — 매수 관심"
    elif position <= 0.50:
        return 6.0, "중간 구간"
    elif position <= 0.75:
        return 4.0, "저항선 접근"
    elif position <= 0.90:
        return 2.0, f"저항선({resistance}) 부근 — 돌파 여부 관건"
    else:
        return 1.0, f"저항선 돌파 시도 중 — 성공 시 급등, 실패 시 되돌림"


def calc_chart_score(indicators: dict) -> dict:
    """
    지표 → 세분화 차트 점수 (0~100) + 타이밍 판정.

    Args:
        indicators: indicators.analyze_chart() 결과

    Returns:
        {
            "chart_score": 0~100,
            "timing": "매수적기/매수관심/관망/매도관심/매도적기",
            "chart_summary": "2줄 요약",
            "signals": ["포지티브 신호"],
            "warnings": ["주의 사항"],
            "score_breakdown": {
                "rsi": {"score": .., "max": 20, "reason": ..},
                "bollinger": ...,
                "macd": ...,
                "volume": ...,
                "trend": ...,
                "momentum": ...,
                "support_resistance": ...,
            },
            "entry_condition": "진입 조건",
            "stop_loss": "손절 기준",
            "target_price": "목표가",
        }
    """
    if not indicators:
        return _empty_result()

    rsi = indicators.get("rsi", 50)
    bb_pct = indicators.get("bb_pct", 0.5)
    macd_cross = indicators.get("macd_cross", "none")
    macd_hist_trend = indicators.get("macd_hist_trend", "flat")
    volume_ratio = indicators.get("volume_ratio", 1.0)
    trend = indicators.get("trend", "sideways")
    price_change_5d = indicators.get("price_change_5d", 0)
    price_change_20d = indicators.get("price_change_20d", 0)
    current_price = indicators.get("current_price", 0)
    support = indicators.get("support", 0)
    resistance = indicators.get("resistance", 0)

    # 각 항목 채점
    rsi_score, rsi_reason = score_rsi(rsi)
    bb_score, bb_reason = score_bollinger(bb_pct)
    macd_score, macd_reason = score_macd(macd_cross, macd_hist_trend)
    vol_score, vol_reason = score_volume(volume_ratio, trend)
    trend_score, trend_reason = score_trend(trend, price_change_5d, price_change_20d)
    mom_score, mom_reason = score_momentum(price_change_5d, price_change_20d)
    sr_score, sr_reason = score_support_resistance(current_price, support, resistance)

    total = rsi_score + bb_score + macd_score + vol_score + trend_score + mom_score + sr_score

    # 신호/경고 분류
    signals = []
    warnings = []

    for score, reason, threshold in [
        (rsi_score, rsi_reason, 14),
        (bb_score, bb_reason, 10),
        (macd_score, macd_reason, 11),
        (vol_score, vol_reason, 10),
        (trend_score, trend_reason, 10),
    ]:
        if score >= threshold:
            signals.append(reason)
        elif score <= 3:
            warnings.append(reason)

    # 타이밍 판정
    timing = _determine_timing(total, signals, warnings)

    # 진입/손절/목표 자동 산출
    entry, stop_loss, target = _calc_trade_levels(
        current_price, support, resistance, timing, trend, bb_pct,
    )

    # 요약 생성
    chart_summary = _generate_summary(total, timing, signals, warnings, trend, rsi)

    return {
        "chart_score": round(total, 1),
        "timing": timing,
        "chart_summary": chart_summary,
        "signals": signals,
        "warnings": warnings,
        "score_breakdown": {
            "rsi": {"score": rsi_score, "max": 20, "reason": rsi_reason},
            "bollinger": {"score": bb_score, "max": 15, "reason": bb_reason},
            "macd": {"score": macd_score, "max": 15, "reason": macd_reason},
            "volume": {"score": vol_score, "max": 15, "reason": vol_reason},
            "trend": {"score": trend_score, "max": 15, "reason": trend_reason},
            "momentum": {"score": mom_score, "max": 10, "reason": mom_reason},
            "support_resistance": {"score": sr_score, "max": 10, "reason": sr_reason},
        },
        "entry_condition": entry,
        "stop_loss": stop_loss,
        "target_price": target,
    }


def _determine_timing(total: float, signals: list, warnings: list) -> str:
    """점수 + 신호/경고 조합으로 타이밍 판정."""
    if total >= 75 and len(signals) >= 3:
        return "매수적기"
    elif total >= 60 and len(signals) >= 2:
        return "매수관심"
    elif total <= 25 and len(warnings) >= 3:
        return "매도적기"
    elif total <= 35 and len(warnings) >= 2:
        return "매도관심"
    else:
        return "관망"


def _calc_trade_levels(
    current_price: float,
    support: float,
    resistance: float,
    timing: str,
    trend: str,
    bb_pct: float,
) -> tuple[str, str, str]:
    """진입/손절/목표 자동 산출."""
    if not current_price or not support:
        return "데이터 부족", "-", "-"

    if timing in ("매수적기", "매수관심"):
        # 진입: 현재가 또는 지지선 부근
        if bb_pct < 0.3:
            entry = f"현재가({current_price:,.0f}) 부근 즉시 or 지지선({support:,.0f}) 근접 시"
        else:
            entry = f"눌림 시 {support:,.0f}~{current_price:,.0f} 구간"

        # 손절: 지지선 -2~3%
        stop = support * 0.97
        stop_loss = f"{stop:,.0f} (지지선 -3%)"

        # 목표: 저항선 또는 +5~10%
        if resistance > current_price * 1.02:
            target = f"{resistance:,.0f} (저항선) ~ {current_price * 1.10:,.0f} (+10%)"
        else:
            target = f"{current_price * 1.05:,.0f} ~ {current_price * 1.10:,.0f} (+5~10%)"

    elif timing in ("매도적기", "매도관심"):
        entry = "신규 진입 비추천"
        stop_loss = "-"
        target = f"보유 시 {support:,.0f} 이탈 시 손절"
    else:
        entry = f"지지선({support:,.0f}) 확인 후 진입 또는 저항선({resistance:,.0f}) 돌파 시"
        stop = support * 0.97
        stop_loss = f"{stop:,.0f} (지지선 -3%)"
        target = f"{resistance:,.0f} (저항선)"

    return entry, stop_loss, target


def _generate_summary(
    total: float,
    timing: str,
    signals: list,
    warnings: list,
    trend: str,
    rsi: float,
) -> str:
    """차트 상황 요약 텍스트."""
    trend_kr = {"uptrend": "상승추세", "downtrend": "하락추세", "sideways": "횡보"}
    parts = [f"차트점수 {total:.0f}/100 ({timing})."]

    if signals:
        parts.append(f"긍정: {', '.join(signals[:2])}.")
    if warnings:
        parts.append(f"주의: {', '.join(warnings[:2])}.")

    parts.append(f"{trend_kr.get(trend, '횡보')}, RSI {rsi:.0f}.")
    return " ".join(parts)


def _empty_result() -> dict:
    return {
        "chart_score": 50,
        "timing": "관망",
        "chart_summary": "차트 데이터 없음",
        "signals": [],
        "warnings": ["OHLCV 데이터 수집 실패"],
        "score_breakdown": {},
        "entry_condition": "데이터 부족",
        "stop_loss": "-",
        "target_price": "-",
    }
