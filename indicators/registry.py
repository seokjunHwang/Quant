"""Indicator registry — maps indicator IDs to compute functions.

Each indicator function has the signature:
    func(df: pd.DataFrame, **params) -> list[dict]

Output format varies by type:
- line: [{"time": "2024-01-01", "value": 65.3}, ...]
- multi: [{"time": "2024-01-01", "upper": 110, "middle": 100, "lower": 90}, ...]
- histogram: [{"time": "2024-01-01", "value": 0.5, "color": "#26a69a"}, ...]
"""

from ai.indicators.definitions.momentum import (
    compute_rsi,
    compute_macd,
    compute_stochastic,
)
from ai.indicators.definitions.trend import (
    compute_ema,
    compute_sma,
    compute_bollinger_bands,
    compute_adx,
)
from ai.indicators.definitions.volume import (
    compute_obv,
    compute_volume_ma,
)
from ai.indicators.definitions.volatility import (
    compute_atr,
)

INDICATOR_REGISTRY: dict[str, dict] = {
    # Momentum
    "RSI_14": {
        "func": compute_rsi,
        "name": "RSI",
        "category": "momentum",
        "default_params": {"length": 14},
        "output_type": "line",
    },
    "MACD": {
        "func": compute_macd,
        "name": "MACD",
        "category": "momentum",
        "default_params": {"fast": 12, "slow": 26, "signal": 9},
        "output_type": "multi",
    },
    "STOCH": {
        "func": compute_stochastic,
        "name": "Stochastic",
        "category": "momentum",
        "default_params": {"k": 14, "d": 3},
        "output_type": "multi",
    },
    # Trend
    "EMA_20": {
        "func": compute_ema,
        "name": "EMA 20",
        "category": "trend",
        "default_params": {"length": 20},
        "output_type": "line",
    },
    "EMA_50": {
        "func": compute_ema,
        "name": "EMA 50",
        "category": "trend",
        "default_params": {"length": 50},
        "output_type": "line",
    },
    "SMA_200": {
        "func": compute_sma,
        "name": "SMA 200",
        "category": "trend",
        "default_params": {"length": 200},
        "output_type": "line",
    },
    "BB_20": {
        "func": compute_bollinger_bands,
        "name": "Bollinger Bands",
        "category": "trend",
        "default_params": {"length": 20, "std": 2.0},
        "output_type": "multi",
    },
    "ADX": {
        "func": compute_adx,
        "name": "ADX",
        "category": "trend",
        "default_params": {"length": 14},
        "output_type": "line",
    },
    # Volume
    "OBV": {
        "func": compute_obv,
        "name": "OBV",
        "category": "volume",
        "default_params": {},
        "output_type": "line",
    },
    "VOL_MA": {
        "func": compute_volume_ma,
        "name": "Volume MA",
        "category": "volume",
        "default_params": {"length": 20},
        "output_type": "line",
    },
    # Volatility
    "ATR_14": {
        "func": compute_atr,
        "name": "ATR",
        "category": "volatility",
        "default_params": {"length": 14},
        "output_type": "line",
    },
}


def register_indicator(ind_id: str, entry: dict) -> None:
    """Dynamically register a new indicator (e.g., from pine_converted/)."""
    INDICATOR_REGISTRY[ind_id] = entry
