"""RSI 다이버전스 탐지 엔진."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Div:
    """다이버전스 시그널."""
    type: str       # regular_bullish / hidden_bullish / regular_bearish / hidden_bearish
    label: str      # Bull / H.Bull / Bear / H.Bear
    idx: int        # 현재 피봇 bar index
    prev_idx: int   # 이전 피봇 bar index
    price: float
    rsi: float
    prev_price: float
    prev_rsi: float


def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's smoothing RSI (TradingView/Pine 방식)."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    ag = gain.rolling(period, min_periods=period).mean()
    al = loss.rolling(period, min_periods=period).mean()
    for i in range(period, len(close)):
        ag.iloc[i] = (ag.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
        al.iloc[i] = (al.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period
    return 100.0 - 100.0 / (1.0 + ag / al)


def find_pivots(series: pd.Series, lbl: int, lbr: int, mode: str) -> dict[int, int]:
    """
    RSI 피봇 탐지. 반환: {confirm_bar: pivot_bar}
    mode: "low" 또는 "high"
    """
    out = {}
    v = series.values
    for i in range(lbl, len(v) - lbr):
        if np.isnan(v[i]):
            continue
        L, R = v[i - lbl:i], v[i + 1:i + 1 + lbr]
        if len(L) < lbl or len(R) < lbr:
            continue
        if np.any(np.isnan(L)) or np.any(np.isnan(R)):
            continue
        if mode == "low":
            ok = np.all(v[i] <= L) and np.all(v[i] < R)
        else:
            ok = np.all(v[i] >= L) and np.all(v[i] > R)
        if ok:
            out[i + lbr] = i
    return out


def detect(
    df: pd.DataFrame,
    rsi_period: int = 14,
    lbl: int = 5,
    lbr: int = 5,
    rng_lo: int = 5,
    rng_hi: int = 60,
    lookback: int = 2,
) -> tuple[list[Div], pd.Series, dict, dict]:
    """
    RSI 다이버전스 탐지.

    Args:
        df: OHLCV DataFrame
        rsi_period: RSI 계산 기간
        lbl: 피봇 좌측 확인 봉수
        lbr: 피봇 우측 확인 봉수
        rng_lo: 피봇 간 최소 간격 (봉)
        rng_hi: 피봇 간 최대 간격 (봉)
        lookback: 이전 N개 피봇까지 비교 (1=직전만, 2+=건너뛰며 비교)

    Returns:
        (시그널 리스트, RSI Series, 피봇로우 dict, 피봇하이 dict)
    """
    d = df.copy()
    d.columns = [c.lower() for c in d.columns]
    rsi = calc_rsi(d["close"], rsi_period)
    pl = find_pivots(rsi, lbl, lbr, "low")
    ph = find_pivots(rsi, lbl, lbr, "high")
    sigs: list[Div] = []

    # Bullish (피봇 로우 비교)
    spl = sorted(pl.items())
    for i in range(1, len(spl)):
        cc, cp = spl[i]
        for back in range(1, min(lookback + 1, i + 1)):
            pc, pp = spl[i - back]
            gap = cc - pc
            if gap < rng_lo:
                continue
            if gap > rng_hi:
                break
            c_p, p_p = d["low"].iloc[cp], d["low"].iloc[pp]
            c_r, p_r = rsi.iloc[cp], rsi.iloc[pp]
            if c_p < p_p and c_r > p_r:
                sigs.append(Div("regular_bullish", "Bull", cp, pp, c_p, c_r, p_p, p_r))
                break
            elif c_p > p_p and c_r < p_r:
                sigs.append(Div("hidden_bullish", "H.Bull", cp, pp, c_p, c_r, p_p, p_r))
                break

    # Bearish (피봇 하이 비교)
    sph = sorted(ph.items())
    for i in range(1, len(sph)):
        cc, cp = sph[i]
        for back in range(1, min(lookback + 1, i + 1)):
            pc, pp = sph[i - back]
            gap = cc - pc
            if gap < rng_lo:
                continue
            if gap > rng_hi:
                break
            c_p, p_p = d["high"].iloc[cp], d["high"].iloc[pp]
            c_r, p_r = rsi.iloc[cp], rsi.iloc[pp]
            if c_p > p_p and c_r < p_r:
                sigs.append(Div("regular_bearish", "Bear", cp, pp, c_p, c_r, p_p, p_r))
                break
            elif c_p < p_p and c_r > p_r:
                sigs.append(Div("hidden_bearish", "H.Bear", cp, pp, c_p, c_r, p_p, p_r))
                break

    sigs.sort(key=lambda s: s.idx)
    return sigs, rsi, pl, ph
