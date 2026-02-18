"""Market endpoints — OHLCV candle data from Binance public API."""

import httpx
from fastapi import APIRouter, Query

router = APIRouter()

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"


@router.get("/klines")
async def get_klines(
    symbol: str = Query("BTCUSDT", example="BTCUSDT"),
    interval: str = Query("1d", example="1d"),
    limit: int = Query(500, le=1500),
):
    """OHLCV candle data from Binance."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            BINANCE_KLINES_URL,
            params={"symbol": symbol.upper(), "interval": interval, "limit": limit},
        )
        resp.raise_for_status()
        raw = resp.json()

    # Binance format: [openTime, O, H, L, C, volume, closeTime, ...]
    data = []
    for k in raw:
        data.append({
            "time": int(k[0]) // 1000,  # Unix seconds for Lightweight Charts
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        })

    return {"symbol": symbol, "interval": interval, "data": data}


@router.get("/ticker")
async def get_ticker(symbol: str = Query("BTCUSDT")):
    """24h ticker info."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.binance.com/api/v3/ticker/24hr",
            params={"symbol": symbol.upper()},
        )
        resp.raise_for_status()
        t = resp.json()

    return {
        "symbol": t["symbol"],
        "lastPrice": float(t["lastPrice"]),
        "priceChange24h": float(t["priceChangePercent"]),
        "volume24h": float(t["quoteVolume"]),
    }


@router.get("/orderbook")
async def get_orderbook(
    symbol: str = Query("BTCUSDT"),
    limit: int = Query(20, le=100),
):
    """Order book."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.binance.com/api/v3/depth",
            params={"symbol": symbol.upper(), "limit": limit},
        )
        resp.raise_for_status()
        return resp.json()


@router.get("/symbols")
async def get_symbols():
    """Available trading symbols."""
    return {
        "symbols": [
            {"symbol": "BTCUSDT", "base": "BTC", "quote": "USDT"},
            {"symbol": "ETHUSDT", "base": "ETH", "quote": "USDT"},
            {"symbol": "SOLUSDT", "base": "SOL", "quote": "USDT"},
            {"symbol": "XRPUSDT", "base": "XRP", "quote": "USDT"},
        ]
    }
