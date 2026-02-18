from fastapi import APIRouter

from app.api.v1 import market, signals, strategies, backtest, trading, indicators, auth
from app.api.ws import price_stream, signal_stream

api_router = APIRouter()

# REST endpoints
api_router.include_router(market.router, prefix="/market", tags=["Market"])
api_router.include_router(signals.router, prefix="/signals", tags=["Signals"])
api_router.include_router(strategies.router, prefix="/strategies", tags=["Strategies"])
api_router.include_router(backtest.router, prefix="/backtest", tags=["Backtest"])
api_router.include_router(trading.router, prefix="/trading", tags=["Trading"])
api_router.include_router(indicators.router, prefix="/indicators", tags=["Indicators"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])

# WebSocket endpoints
api_router.include_router(price_stream.router, prefix="/ws", tags=["WebSocket"])
api_router.include_router(signal_stream.router, prefix="/ws", tags=["WebSocket"])
