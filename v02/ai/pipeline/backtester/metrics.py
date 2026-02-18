"""Performance metrics for backtest evaluation."""

import numpy as np
import pandas as pd


def total_return(equity_curve: pd.Series) -> float:
    return (equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) * 100


def annual_return(equity_curve: pd.Series, trading_days: int = 252) -> float:
    total_days = len(equity_curve)
    total_ret = equity_curve.iloc[-1] / equity_curve.iloc[0]
    return (total_ret ** (trading_days / total_days) - 1) * 100


def max_drawdown(equity_curve: pd.Series) -> float:
    peak = equity_curve.cummax()
    drawdown = (equity_curve - peak) / peak
    return drawdown.min() * 100


def sharpe_ratio(
    returns: pd.Series, risk_free_rate: float = 0.04, trading_days: int = 252
) -> float:
    excess = returns - risk_free_rate / trading_days
    if excess.std() == 0:
        return 0.0
    return (excess.mean() / excess.std()) * np.sqrt(trading_days)


def sortino_ratio(
    returns: pd.Series, risk_free_rate: float = 0.04, trading_days: int = 252
) -> float:
    excess = returns - risk_free_rate / trading_days
    downside = returns[returns < 0]
    if len(downside) == 0 or downside.std() == 0:
        return 0.0
    return (excess.mean() / downside.std()) * np.sqrt(trading_days)


def win_rate(trades: pd.DataFrame) -> float:
    if len(trades) == 0:
        return 0.0
    wins = (trades["pnl"] > 0).sum()
    return (wins / len(trades)) * 100


def profit_factor(trades: pd.DataFrame) -> float:
    if len(trades) == 0:
        return 0.0
    gross_profit = trades.loc[trades["pnl"] > 0, "pnl"].sum()
    gross_loss = abs(trades.loc[trades["pnl"] < 0, "pnl"].sum())
    if gross_loss == 0:
        return float("inf")
    return gross_profit / gross_loss


def composite_score(metrics: dict, weights: dict | None = None) -> float:
    """Calculate weighted composite score."""
    w = weights or {
        "sharpe": 0.3,
        "excess_return": 0.2,
        "win_rate": 0.2,
        "consistency": 0.15,
        "mdd_inverse": 0.15,
    }

    # Normalize each metric to 0-100 range
    s_sharpe = min(max(metrics.get("sharpe_ratio", 0) * 30, 0), 100)
    s_excess = min(max(metrics.get("excess_return_pct", 0), 0), 100)
    s_winrate = metrics.get("win_rate_pct", 0)
    s_consistency = max(100 - metrics.get("consistency_std", 50), 0)
    s_mdd = max(100 + metrics.get("max_drawdown_pct", -50), 0)

    return (
        w["sharpe"] * s_sharpe
        + w["excess_return"] * s_excess
        + w["win_rate"] * s_winrate
        + w["consistency"] * s_consistency
        + w["mdd_inverse"] * s_mdd
    )
