from fastapi import APIRouter

from app.api.chart import router as chart_router
from app.api.screener import router as screener_router
from app.api.stocks import router as stocks_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(screener_router)
api_router.include_router(stocks_router)
api_router.include_router(chart_router)
