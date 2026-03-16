"""
Step 4: 세력 흔적 패턴 감지.

명세서 기준:
  +5: 저거래량 횡보 후 거래량 폭발
  +4: 갭다운 후 빠른 회복
  +4: 52주 박스권 상단 반복 터치
  +3: 일봉 아랫꼬리 연속 출현
  +3: 갭업 후 첫 눌림
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def detect_volume_breakout(df: pd.DataFrame, lookback: int = 20) -> dict:
    """
    저거래량 횡보 후 거래량 폭발 (+5점).

    조건:
    - 최근 lookback일의 거래량 평균이 60일 평균보다 낮음 (횡보)
    - 최근 2일 거래량이 평균의 2배+ (폭발)
    """
    if len(df) < 60:
        return {"detected": False, "score": 0}

    vol = df["volume"]
    avg_60 = vol.iloc[-60:].mean()
    avg_recent = vol.iloc[-lookback:-2].mean()
    latest_2d = vol.iloc[-2:].mean()

    # 횡보 + 폭발
    was_quiet = avg_recent < avg_60 * 0.8
    is_explosive = latest_2d > avg_60 * 2.0

    detected = was_quiet and is_explosive
    return {
        "detected": detected,
        "score": 5 if detected else 0,
        "detail": f"quiet_ratio={avg_recent/avg_60:.2f}, explosion={latest_2d/avg_60:.1f}x",
    }


def detect_gap_down_recovery(df: pd.DataFrame) -> dict:
    """
    갭다운 후 빠른 회복 (+4점).

    조건: 최근 5일 내 갭다운(-2%+) 발생 후 같은 날 또는 익일 회복.
    """
    if len(df) < 10:
        return {"detected": False, "score": 0}

    for i in range(-5, 0):
        if i >= len(df):
            continue

        prev_close = df["close"].iloc[i - 1]
        open_price = df["open"].iloc[i]
        close_price = df["close"].iloc[i]

        gap_pct = (open_price - prev_close) / prev_close

        if gap_pct < -0.02:  # 2%+ gap down
            recovery = (close_price - open_price) / abs(open_price - prev_close)
            if recovery > 0.5:  # Recovered 50%+ of the gap
                return {
                    "detected": True,
                    "score": 4,
                    "detail": f"gap={gap_pct:.1%}, recovery={recovery:.0%}",
                }

    return {"detected": False, "score": 0}


def detect_resistance_touches(df: pd.DataFrame, window: int = 60) -> dict:
    """
    52주 박스권 상단 반복 터치 (+4점).

    조건: 최근 window일 내 최고가 근처(98%+)에 3회+ 접근.
    """
    if len(df) < window:
        return {"detected": False, "score": 0}

    recent = df.iloc[-window:]
    high_level = recent["high"].max()
    threshold = high_level * 0.98

    touches = (recent["high"] >= threshold).sum()
    detected = touches >= 3

    return {
        "detected": detected,
        "score": 4 if detected else 0,
        "detail": f"resistance_touches={touches}, level={high_level:.2f}",
    }


def detect_lower_wicks(df: pd.DataFrame, count: int = 3) -> dict:
    """
    일봉 아랫꼬리 연속 출현 (+3점).

    조건: 최근 count일 연속 아랫꼬리 비율이 전체 봉 대비 40%+
    """
    if len(df) < count + 1:
        return {"detected": False, "score": 0}

    recent = df.iloc[-count:]
    consecutive_wicks = 0

    for _, row in recent.iterrows():
        body_top = max(row["open"], row["close"])
        body_bottom = min(row["open"], row["close"])
        total_range = row["high"] - row["low"]

        if total_range == 0:
            continue

        lower_wick = body_bottom - row["low"]
        wick_ratio = lower_wick / total_range

        if wick_ratio >= 0.4:
            consecutive_wicks += 1

    detected = consecutive_wicks >= count
    return {
        "detected": detected,
        "score": 3 if detected else 0,
        "detail": f"wick_candles={consecutive_wicks}/{count}",
    }


def detect_gap_up_pullback(df: pd.DataFrame) -> dict:
    """
    갭업 후 첫 눌림 (+3점).

    조건: 최근 5일 내 갭업(+2%+) 발생 후 현재 눌림 구간.
    """
    if len(df) < 10:
        return {"detected": False, "score": 0}

    for i in range(-5, -1):
        prev_close = df["close"].iloc[i - 1]
        open_price = df["open"].iloc[i]

        gap_pct = (open_price - prev_close) / prev_close

        if gap_pct > 0.02:  # 2%+ gap up
            # Check if price is pulling back but still above pre-gap level
            current = df["close"].iloc[-1]
            gap_high = df["high"].iloc[i]

            pullback_from_high = (gap_high - current) / gap_high
            still_above_gap = current > prev_close

            if 0.02 < pullback_from_high < 0.10 and still_above_gap:
                return {
                    "detected": True,
                    "score": 3,
                    "detail": f"gap={gap_pct:.1%}, pullback={pullback_from_high:.1%}",
                }

    return {"detected": False, "score": 0}


def score_patterns(df: pd.DataFrame) -> dict:
    """
    전체 세력 흔적 패턴 점수 합산.

    Returns:
        {"total": int, "patterns": [...]}
    """
    if df is None or len(df) < 10:
        return {"total": 0, "patterns": []}

    detectors = [
        ("volume_breakout", detect_volume_breakout),
        ("gap_down_recovery", detect_gap_down_recovery),
        ("resistance_touches", detect_resistance_touches),
        ("lower_wicks", detect_lower_wicks),
        ("gap_up_pullback", detect_gap_up_pullback),
    ]

    total = 0
    patterns = []

    for name, detector in detectors:
        try:
            result = detector(df)
            if result["detected"]:
                total += result["score"]
                patterns.append({
                    "pattern": name,
                    "score": result["score"],
                    "detail": result.get("detail", ""),
                })
        except Exception as e:
            logger.warning(f"Pattern [{name}] detection failed: {e}")

    return {"total": total, "patterns": patterns}
