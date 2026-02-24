"""TradingView 스타일 차트 렌더링."""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from .engine import Div


# 색상
_COL = {
    "regular_bullish": "#26a69a",
    "hidden_bullish": "#4dd0e1",
    "regular_bearish": "#ef5350",
    "hidden_bearish": "#ff8a65",
}
_BG = "#131722"
_GRID = "#1e222d"
_TXT = "#787b86"


def chart(
    df: pd.DataFrame,
    rsi: pd.Series,
    signals: list[Div],
    pl_pivots: dict,
    ph_pivots: dict,
    ticker: str,
    bars: int = 150,
):
    """
    TradingView 스타일 캔들스틱 + RSI + 다이버전스 차트.

    Args:
        df: OHLCV DataFrame
        rsi: RSI Series
        signals: 다이버전스 시그널 리스트
        pl_pivots: 피봇 로우 {confirm: pivot}
        ph_pivots: 피봇 하이 {confirm: pivot}
        ticker: 종목명
        bars: 차트에 표시할 최근 봉 수
    """
    start = max(0, len(df) - bars)
    d = df.iloc[start:]
    r = rsi.iloc[start:]
    off = start
    x = np.arange(len(d))

    fig, (ax, axr) = plt.subplots(
        2, 1, figsize=(22, 12),
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.04},
    )
    fig.set_facecolor(_BG)
    for a in [ax, axr]:
        a.set_facecolor(_BG)
        a.tick_params(colors=_TXT, labelsize=7)
        for sp in a.spines.values():
            sp.set_color(_GRID)
        a.grid(True, color=_GRID, lw=0.5, alpha=0.5)

    # 캔들스틱
    up = d["close"].values >= d["open"].values
    dn = ~up
    ax.bar(x[up], (d["close"].values - d["open"].values)[up],
           bottom=d["open"].values[up], width=0.55, color="#26a69a", lw=0)
    ax.bar(x[dn], (d["open"].values - d["close"].values)[dn],
           bottom=d["close"].values[dn], width=0.55, color="#ef5350", lw=0)
    ax.vlines(x[up], d["low"].values[up], d["high"].values[up], color="#26a69a", lw=0.7)
    ax.vlines(x[dn], d["low"].values[dn], d["high"].values[dn], color="#ef5350", lw=0.7)

    # RSI
    axr.plot(x, r.values, color="#bb86fc", lw=1)
    axr.axhline(70, color="#ef5350", lw=0.5, ls="--", alpha=0.5)
    axr.axhline(30, color="#26a69a", lw=0.5, ls="--", alpha=0.5)
    axr.fill_between(x, 70, r.values, where=r.values >= 70, alpha=0.08, color="#ef5350")
    axr.fill_between(x, 30, r.values, where=r.values <= 30, alpha=0.08, color="#26a69a")
    axr.set_ylim(15, 85)
    axr.set_ylabel("RSI", color=_TXT, fontsize=9)

    # 피봇 마커
    for _, pv in pl_pivots.items():
        cx = pv - off
        if 0 <= cx < len(d):
            axr.plot(cx, r.iloc[cx], "^", color="#26a69a", ms=4, alpha=0.35)
    for _, pv in ph_pivots.items():
        cx = pv - off
        if 0 <= cx < len(d):
            axr.plot(cx, r.iloc[cx], "v", color="#ef5350", ms=4, alpha=0.35)

    # 다이버전스 라인 + 라벨
    pr = d["high"].max() - d["low"].min()
    for s in signals:
        cx, px = s.idx - off, s.prev_idx - off
        if cx < 0 or cx >= len(d) or px < 0 or px >= len(d):
            continue
        c = _COL[s.type]
        ls = "-" if "regular" in s.type else "--"
        bull = "bullish" in s.type

        yc = d["low"].iloc[cx] if bull else d["high"].iloc[cx]
        yp = d["low"].iloc[px] if bull else d["high"].iloc[px]
        ax.plot([px, cx], [yp, yc], color=c, lw=2, ls=ls, alpha=0.9, zorder=5)
        ax.plot([px, cx], [yp, yc], "o", color=c, ms=4, zorder=6)

        axr.plot([px, cx], [r.iloc[px], r.iloc[cx]], color=c, lw=2, ls=ls, alpha=0.9, zorder=5)
        axr.plot([px, cx], [r.iloc[px], r.iloc[cx]], "o", color=c, ms=3, zorder=6)

        ly = yc - pr * 0.02 if bull else yc + pr * 0.02
        ax.annotate(
            s.label, xy=(cx, yc), xytext=(cx, ly),
            fontsize=7.5, fontweight="bold", color="white", ha="center",
            va="top" if bull else "bottom",
            bbox=dict(boxstyle="round,pad=0.2", fc=c, ec="none", alpha=0.95),
            zorder=10,
        )

    # X축
    step = max(1, len(d) // 25)
    axr.set_xticks(x[::step])
    axr.set_xticklabels(
        [d.index[i].strftime("%m/%d") for i in x[::step]], fontsize=7, color=_TXT,
    )
    ax.set_xticks([])
    ax.set_xlim(-1, len(d))
    axr.set_xlim(-1, len(d))

    n_bull = sum(1 for s in signals if "bullish" in s.type and 0 <= s.idx - off < len(d))
    n_bear = sum(1 for s in signals if "bearish" in s.type and 0 <= s.idx - off < len(d))
    ax.set_title(
        f"{ticker}  |  4H  |  RSI Divergence  |  Bull {n_bull}  Bear {n_bear}",
        color="white", fontsize=13, fontweight="bold", pad=10, loc="left",
    )
    ax.legend(
        handles=[
            mpatches.Patch(color="#26a69a", label="Regular Bull"),
            mpatches.Patch(color="#4dd0e1", label="Hidden Bull"),
            mpatches.Patch(color="#ef5350", label="Regular Bear"),
            mpatches.Patch(color="#ff8a65", label="Hidden Bear"),
        ],
        loc="upper right", fontsize=7, facecolor=_BG, edgecolor=_GRID, labelcolor="white",
    )
    plt.tight_layout()
    plt.show()
