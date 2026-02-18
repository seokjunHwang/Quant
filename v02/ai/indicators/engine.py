"""Indicator computation engine.

Central dispatch for computing technical indicators on OHLCV data.
Used by both the backend (for chart rendering) and the pipeline (for backtesting).
"""

import pandas as pd

from ai.indicators.registry import INDICATOR_REGISTRY


def compute_indicators(
    df: pd.DataFrame,
    indicator_ids: list[str],
    params_override: dict[str, dict] | None = None,
) -> dict[str, list[dict]]:
    """Compute multiple indicators on OHLCV DataFrame.

    Args:
        df: DataFrame with columns [open, high, low, close, volume] and DatetimeIndex.
        indicator_ids: List of registered indicator IDs (e.g., ["RSI_14", "MACD", "BB_20"]).
        params_override: Optional per-indicator parameter overrides.

    Returns:
        Dict mapping indicator_id to list of {time, value, ...} dicts.
    """
    results = {}
    params_override = params_override or {}

    for ind_id in indicator_ids:
        entry = INDICATOR_REGISTRY.get(ind_id)
        if entry is None:
            continue

        func = entry["func"]
        default_params = entry.get("default_params", {})
        params = {**default_params, **params_override.get(ind_id, {})}

        try:
            series_data = func(df, **params)
            results[ind_id] = series_data
        except Exception as e:
            results[ind_id] = {"error": str(e)}

    return results


def list_available_indicators() -> list[dict]:
    """Return catalog of all registered indicators."""
    catalog = []
    for ind_id, entry in INDICATOR_REGISTRY.items():
        catalog.append({
            "id": ind_id,
            "name": entry.get("name", ind_id),
            "category": entry.get("category", "unknown"),
            "params": entry.get("default_params", {}),
            "output_type": entry.get("output_type", "line"),
        })
    return catalog
