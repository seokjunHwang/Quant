from fastapi import APIRouter, Depends, Query

from app.dependencies import get_dynamodb, get_config

router = APIRouter()


@router.get("/klines")
async def get_klines(
    symbol: str = Query(..., example="BTCUSDT"),
    interval: str = Query("1d", example="1d"),
    limit: int = Query(500, le=1500),
    db=Depends(get_dynamodb),
    config=Depends(get_config),
):
    """OHLCV 캔들 데이터 조회. DynamoDB 캐시 우선, 미스 시 Binance에서 fetch."""
    # TODO: implement candle_repo.get_klines + binance fallback
    return {"symbol": symbol, "interval": interval, "data": []}


@router.get("/ticker")
async def get_ticker(
    symbol: str = Query(..., example="BTCUSDT"),
):
    """24시간 티커 정보."""
    # TODO: implement binance_service.get_ticker
    return {"symbol": symbol, "lastPrice": 0, "priceChange24h": 0, "volume24h": 0}


@router.get("/orderbook")
async def get_orderbook(
    symbol: str = Query(..., example="BTCUSDT"),
    limit: int = Query(20, le=100),
):
    """오더북 조회."""
    # TODO: implement binance_service.get_orderbook
    return {"symbol": symbol, "bids": [], "asks": []}


@router.get("/symbols")
async def get_symbols():
    """거래 가능한 심볼 목록."""
    # TODO: implement binance_service.get_exchange_info
    return {"symbols": []}
