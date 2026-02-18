"""Stage 3: Conversion verifier.

Generates signals from converted Python code and visualizes them on a chart
so the user can compare with TradingView and approve/reject.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

from ai.pipeline.converter import load_converted_module, PINE_DIR, CONVERTED_DIR
from ai.pipeline.backtester.data_fetcher import fetch_ohlcv
from ai.pipeline.utils.db import PipelineDB
from ai.pipeline.utils.logger import get_logger

logger = get_logger("verifier")

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


def verify_indicator(
    indicator_id: str,
    asset: str = "BTC/USDT",
    timeframe: str = "1d",
    recent_bars: int = 100,
    output_html: bool = True,
) -> dict:
    """Run converted code on recent data and generate verification chart.

    Args:
        indicator_id: Name of the indicator (filename without extension).
        asset: Asset to test on.
        timeframe: Timeframe.
        recent_bars: Number of recent bars to show.
        output_html: Whether to save plotly HTML chart.

    Returns:
        Dict with signal statistics and chart path.
    """
    # Load module
    module = load_converted_module(indicator_id)
    if module is None:
        return {"error": f"Could not load converted module: {indicator_id}"}

    # Fetch data (extra bars for indicator warmup)
    warmup = 200
    total_bars = recent_bars + warmup
    df = fetch_ohlcv(asset, timeframe, start="2020-01-01", end="2026-12-31")

    if len(df) < recent_bars:
        return {"error": f"Not enough data: {len(df)} bars (need {recent_bars})"}

    # Generate signals
    try:
        params = getattr(module, "METADATA", {}).get("default_params", {})
        df_signals = module.generate_signals(df, **params)
    except Exception as e:
        return {"error": f"Signal generation failed: {e}"}

    # Take only recent bars for display
    df_display = df_signals.tail(recent_bars).copy()

    # Signal statistics
    signals = df_display.get("signal", pd.Series(dtype=int))
    total = len(df_display)
    buy_count = (signals == 1).sum()
    sell_count = (signals == -1).sum()
    signal_freq = (buy_count + sell_count) / total if total > 0 else 0

    stats = {
        "indicator_id": indicator_id,
        "asset": asset,
        "bars_analyzed": total,
        "buy_signals": int(buy_count),
        "sell_signals": int(sell_count),
        "signal_frequency": round(signal_freq, 4),
        "has_nan": int(signals.isna().sum()),
    }

    # Warnings
    warnings = []
    if signal_freq < 0.001:
        warnings.append("Very low signal frequency (<0.1%) — may indicate conversion issue")
    if signal_freq > 0.5:
        warnings.append("Very high signal frequency (>50%) — signals on every other bar")
    if buy_count == 0 and sell_count == 0:
        warnings.append("No signals generated at all — conversion likely failed")

    # Check for consecutive same-direction signals
    if len(signals) > 1:
        consecutive = (signals != 0) & (signals == signals.shift(1))
        if consecutive.sum() > total * 0.3:
            warnings.append("Many consecutive same-direction signals — may need debouncing")

    stats["warnings"] = warnings

    # Generate chart
    if output_html:
        chart_path = _generate_chart(df_display, indicator_id, asset, module)
        stats["chart_path"] = str(chart_path)
        logger.info(f"Chart saved: {chart_path}")

    # Print summary
    logger.info(f"Verification for {indicator_id}:")
    logger.info(f"  Bars: {total}, Buy signals: {buy_count}, Sell signals: {sell_count}")
    logger.info(f"  Signal frequency: {signal_freq:.2%}")
    for w in warnings:
        logger.warning(f"  ⚠ {w}")

    return stats


def _generate_chart(
    df: pd.DataFrame,
    indicator_id: str,
    asset: str,
    module,
) -> Path:
    """Generate plotly candlestick chart with buy/sell markers."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=[f"{indicator_id} — {asset}", "Volume"],
    )

    dates = df.index

    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="OHLCV",
        ),
        row=1, col=1,
    )

    # Buy signals
    if "signal" in df.columns:
        buys = df[df["signal"] == 1]
        sells = df[df["signal"] == -1]

        if len(buys) > 0:
            fig.add_trace(
                go.Scatter(
                    x=buys.index,
                    y=buys["low"] * 0.995,
                    mode="markers",
                    marker=dict(symbol="triangle-up", size=12, color="green"),
                    name=f"Buy ({len(buys)})",
                ),
                row=1, col=1,
            )

        if len(sells) > 0:
            fig.add_trace(
                go.Scatter(
                    x=sells.index,
                    y=sells["high"] * 1.005,
                    mode="markers",
                    marker=dict(symbol="triangle-down", size=12, color="red"),
                    name=f"Sell ({len(sells)})",
                ),
                row=1, col=1,
            )

    # Volume
    colors = ["green" if c >= o else "red" for c, o in zip(df["close"], df["open"])]
    fig.add_trace(
        go.Bar(x=dates, y=df["volume"], marker_color=colors, name="Volume", opacity=0.5),
        row=2, col=1,
    )

    fig.update_layout(
        height=800,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        title=f"Signal Verification: {indicator_id} on {asset}",
    )

    # Save
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    chart_path = REPORTS_DIR / f"verify_{indicator_id}.html"
    fig.write_html(str(chart_path))

    return chart_path


def approve_indicator(indicator_id: str):
    """Mark indicator as verified in the database."""
    db = PipelineDB()
    db.update_indicator_status(
        indicator_id, "verified", verified_at=datetime.now().isoformat()
    )
    logger.info(f"Approved: {indicator_id} → status=verified")


def reject_indicator(indicator_id: str, reason: str = ""):
    """Mark indicator as failed. Reason is logged for future reconversion."""
    db = PipelineDB()
    db.update_indicator_status(indicator_id, "failed")
    logger.info(f"Rejected: {indicator_id} → status=failed (reason: {reason})")
