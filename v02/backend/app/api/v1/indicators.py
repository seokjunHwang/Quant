"""Indicator endpoints — compute indicators on OHLCV data and return chart-ready data."""

import sys
import importlib
from pathlib import Path

import httpx
import pandas as pd
from fastapi import APIRouter, Query

router = APIRouter()

# Add v02 root to path so we can import ai modules
# indicators.py is at v02/backend/app/api/v1/indicators.py → 5 parents = v02/
_v02_root = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_v02_root) not in sys.path:
    sys.path.insert(0, str(_v02_root))

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"

# Registry of converted Pine Script indicators (name → module path)
CONVERTED_INDICATORS = {
    "SR_BREAKS": {
        "module": "ai.indicators.converted.SR_breaks_n_retests",
        "name": "SR Breaks & Retests",
        "category": "pattern",
        "description": "Support/Resistance zones with breakout/retest detection",
    },
}

# Built-in indicators from the existing engine
BUILTIN_INDICATORS = ["RSI_14", "MACD", "BB_20", "EMA_20", "EMA_50", "ADX", "ATR_14", "OBV"]


async def _fetch_ohlcv(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    """Fetch OHLCV from Binance and return as DataFrame."""
    # Fetch extra bars for indicator warmup
    fetch_limit = min(limit + 200, 1500)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            BINANCE_KLINES_URL,
            params={"symbol": symbol.upper(), "interval": interval, "limit": fetch_limit},
        )
        resp.raise_for_status()
        raw = resp.json()

    df = pd.DataFrame(raw, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "buy_base", "buy_quote", "ignore",
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("timestamp")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    return df[["open", "high", "low", "close", "volume"]]


@router.get("")
async def get_indicator_data(
    symbol: str = Query("BTCUSDT", example="BTCUSDT"),
    interval: str = Query("1d"),
    indicators: str = Query("SR_BREAKS", example="SR_BREAKS,RSI_14"),
    limit: int = Query(500, le=1500),
):
    """Compute indicator data for chart overlay."""
    indicator_ids = [i.strip() for i in indicators.split(",")]

    # Fetch OHLCV data
    df = await _fetch_ohlcv(symbol, interval, limit)

    results = {}

    for ind_id in indicator_ids:
        if ind_id in CONVERTED_INDICATORS:
            # Load and compute converted Pine Script indicator
            info = CONVERTED_INDICATORS[ind_id]
            try:
                mod = importlib.import_module(info["module"])
                chart_data = mod.get_chart_data(df)
                results[ind_id] = chart_data
            except Exception as e:
                results[ind_id] = {"error": str(e)}

        elif ind_id in BUILTIN_INDICATORS:
            # Use existing indicator engine
            try:
                from ai.indicators.engine import compute_indicators
                data = compute_indicators(df, [ind_id])
                results[ind_id] = data.get(ind_id, [])
            except Exception as e:
                results[ind_id] = {"error": str(e)}

        else:
            results[ind_id] = {"error": f"Unknown indicator: {ind_id}"}

    return results


@router.get("/catalog")
async def get_indicator_catalog():
    """Available indicators list — built-in + converted Pine Scripts."""
    catalog = []

    # Converted indicators
    for ind_id, info in CONVERTED_INDICATORS.items():
        catalog.append({
            "id": ind_id,
            "name": info["name"],
            "category": info["category"],
            "description": info["description"],
            "source": "pine_converted",
        })

    # Built-in indicators
    for ind_id in BUILTIN_INDICATORS:
        catalog.append({
            "id": ind_id,
            "name": ind_id.replace("_", " "),
            "category": "builtin",
            "source": "builtin",
        })

    return {"indicators": catalog}
