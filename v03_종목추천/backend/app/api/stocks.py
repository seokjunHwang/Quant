from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.scanner import load_stock_pool

router = APIRouter(prefix="/stocks", tags=["stocks"])


class StockPoolResponse(BaseModel):
    total: int
    stocks: list[dict]


@router.get("", response_model=StockPoolResponse)
async def get_stocks(
    market: str | None = Query(None, description="US or KR"),
    category: str | None = Query(None, description="Category filter"),
    pool_type: str | None = Query(None, description="core or trending"),
):
    """Get stock pool with optional filtering."""
    stocks = load_stock_pool(market)

    if category:
        stocks = [s for s in stocks if s["category"] == category]
    if pool_type:
        stocks = [s for s in stocks if s["pool_type"] == pool_type]

    return StockPoolResponse(total=len(stocks), stocks=stocks)
