"""Backtesting engine — pure pandas/numpy implementation.

Takes a DataFrame with OHLCV + signal column and simulates trading.
Uses vectorbt if available, falls back to custom implementation.
"""

import numpy as np
import pandas as pd

from ai.pipeline.backtester.metrics import (
    total_return,
    annual_return,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
    win_rate,
    profit_factor,
    composite_score,
)
from ai.pipeline.utils.logger import get_logger

logger = get_logger("backtester")

# Try to import vectorbt, fall back to custom engine
try:
    import vectorbt as vbt
    HAS_VBT = True
except ImportError:
    HAS_VBT = False


class BacktestResult:
    """Container for backtest results."""

    def __init__(self, metrics: dict, equity_curve: pd.Series | None = None, trades: pd.DataFrame | None = None):
        self.metrics = metrics
        self.equity_curve = equity_curve
        self.trades = trades

    def summary(self) -> str:
        m = self.metrics
        lines = [
            f"  Total Return:   {m.get('total_return_pct', 0):>8.2f}%",
            f"  Annual Return:  {m.get('annual_return_pct', 0):>8.2f}%",
            f"  Benchmark:      {m.get('benchmark_return_pct', 0):>8.2f}%",
            f"  Excess Return:  {m.get('excess_return_pct', 0):>8.2f}%",
            f"  Max Drawdown:   {m.get('max_drawdown_pct', 0):>8.2f}%",
            f"  Sharpe Ratio:   {m.get('sharpe_ratio', 0):>8.4f}",
            f"  Sortino Ratio:  {m.get('sortino_ratio', 0):>8.4f}",
            f"  Total Trades:   {m.get('total_trades', 0):>8d}",
            f"  Win Rate:       {m.get('win_rate_pct', 0):>8.2f}%",
            f"  Profit Factor:  {m.get('profit_factor', 0):>8.4f}",
            f"  Composite:      {m.get('composite_score', 0):>8.2f}",
        ]
        return "\n".join(lines)


def _simulate_trades(
    close: pd.Series,
    signals: pd.Series,
    initial_capital: float,
    commission_rate: float,
    slippage_rate: float,
) -> tuple[pd.Series, pd.DataFrame]:
    """Simulate long-only trading based on signals.

    Returns:
        (equity_curve, trades_df) where trades_df has columns [entry_date, exit_date, entry_price, exit_price, pnl, bars_held]
    """
    cash = initial_capital
    position = 0.0  # Number of shares/units held
    entry_price = 0.0
    entry_date = None

    equity = []
    trades = []

    for i in range(len(close)):
        price = close.iloc[i]
        date = close.index[i]
        sig = signals.iloc[i]

        if sig == 1 and position == 0:
            # BUY: enter position
            cost_per_unit = price * (1 + slippage_rate)
            commission = cash * commission_rate
            available = cash - commission
            position = available / cost_per_unit
            entry_price = cost_per_unit
            entry_date = date
            cash = 0.0

        elif sig == -1 and position > 0:
            # SELL: exit position
            sell_price = price * (1 - slippage_rate)
            proceeds = position * sell_price
            commission = proceeds * commission_rate
            cash = proceeds - commission

            pnl = cash - initial_capital if len(trades) == 0 else cash - (trades[-1].get("_cum_cash", initial_capital))
            actual_pnl = (sell_price / entry_price - 1) * 100

            trades.append({
                "entry_date": entry_date,
                "exit_date": date,
                "entry_price": round(entry_price, 4),
                "exit_price": round(sell_price, 4),
                "pnl": round(cash - (initial_capital if len(trades) == 0 else equity[-1] if equity else initial_capital), 4),
                "return_pct": round(actual_pnl, 4),
                "bars_held": i - (close.index.get_loc(entry_date) if entry_date in close.index else 0),
                "_cum_cash": cash,
            })

            position = 0.0
            entry_price = 0.0

        # Calculate current equity
        if position > 0:
            equity.append(position * price)
        else:
            equity.append(cash if cash > 0 else initial_capital)

    equity_series = pd.Series(equity, index=close.index)

    # Clean up trades
    trades_df = pd.DataFrame(trades)
    if not trades_df.empty and "_cum_cash" in trades_df.columns:
        trades_df = trades_df.drop(columns=["_cum_cash"])

    return equity_series, trades_df


def run_backtest(
    df: pd.DataFrame,
    signal_col: str = "signal",
    initial_capital: float = 10000,
    commission_pct: float = 0.05,
    slippage_pct: float = 0.1,
    scoring_weights: dict | None = None,
) -> BacktestResult:
    """Run a backtest on signal data.

    Args:
        df: DataFrame with OHLCV + signal column.
            signal: 1=buy, -1=sell, 0=hold
        signal_col: Name of the signal column.
        initial_capital: Starting capital.
        commission_pct: Commission per trade in percent.
        slippage_pct: Slippage per trade in percent.
        scoring_weights: Weights for composite score.

    Returns:
        BacktestResult with metrics dict, equity curve, and trades.
    """
    if signal_col not in df.columns:
        raise ValueError(f"Signal column '{signal_col}' not found in DataFrame")

    close = df["close"].astype(float)
    signals = df[signal_col].fillna(0).astype(int)

    if (signals == 1).sum() == 0:
        logger.warning("No entry signals found — returning empty result")
        return BacktestResult(metrics=_empty_metrics())

    # Run simulation
    commission_rate = commission_pct / 100
    slippage_rate = slippage_pct / 100

    equity, trades_df = _simulate_trades(
        close, signals, initial_capital, commission_rate, slippage_rate
    )

    # Daily returns
    daily_returns = equity.pct_change().dropna()
    daily_returns = daily_returns.replace([np.inf, -np.inf], 0)

    # Benchmark: buy & hold
    bh_return = (close.iloc[-1] / close.iloc[0] - 1) * 100

    # Trade statistics
    n_trades = len(trades_df)
    wr = 0.0
    pf_ratio = 0.0
    avg_trade_return = 0.0
    avg_holding_days = 0.0

    if n_trades > 0:
        trades_for_metrics = pd.DataFrame({"pnl": trades_df["pnl"]})
        wr = win_rate(trades_for_metrics)
        pf_ratio = profit_factor(trades_for_metrics)
        avg_trade_return = trades_df["return_pct"].mean() if "return_pct" in trades_df.columns else 0
        avg_holding_days = trades_df["bars_held"].mean() if "bars_held" in trades_df.columns else 0

    total_ret = total_return(equity)
    annual_ret = annual_return(equity)
    mdd = max_drawdown(equity)
    sharpe = sharpe_ratio(daily_returns)
    sortino = sortino_ratio(daily_returns)
    calmar = annual_ret / abs(mdd) if mdd != 0 else 0.0

    metrics = {
        "total_return_pct": round(total_ret, 4),
        "annual_return_pct": round(annual_ret, 4),
        "benchmark_return_pct": round(bh_return, 4),
        "excess_return_pct": round(total_ret - bh_return, 4),
        "max_drawdown_pct": round(mdd, 4),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "calmar_ratio": round(calmar, 4),
        "total_trades": n_trades,
        "win_rate_pct": round(wr, 4),
        "profit_factor": round(pf_ratio, 4),
        "avg_trade_return_pct": round(avg_trade_return, 4),
        "avg_holding_period_days": round(avg_holding_days, 2),
    }

    metrics["composite_score"] = round(
        composite_score(metrics, scoring_weights), 4
    )

    return BacktestResult(metrics=metrics, equity_curve=equity, trades=trades_df)


def run_backtest_from_signals_func(
    df: pd.DataFrame,
    signals_func,
    params: dict | None = None,
    **backtest_kwargs,
) -> BacktestResult:
    """Convenience: apply a generate_signals function, then backtest."""
    params = params or {}
    df_with_signals = signals_func(df, **params)
    return run_backtest(df_with_signals, **backtest_kwargs)


def _empty_metrics() -> dict:
    return {
        "total_return_pct": 0.0,
        "annual_return_pct": 0.0,
        "benchmark_return_pct": 0.0,
        "excess_return_pct": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "calmar_ratio": 0.0,
        "total_trades": 0,
        "win_rate_pct": 0.0,
        "profit_factor": 0.0,
        "avg_trade_return_pct": 0.0,
        "avg_holding_period_days": 0.0,
        "composite_score": 0.0,
    }
