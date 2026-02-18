from fastapi import APIRouter, Depends, Query

from app.dependencies import get_dynamodb

router = APIRouter()


@router.get("")
async def get_indicator_data(
    symbol: str = Query(..., example="BTCUSDT"),
    interval: str = Query("1d"),
    indicators: str = Query(..., example="RSI_14,MACD,BB_20"),
    limit: int = Query(500, le=1500),
    db=Depends(get_dynamodb),
):
    """차트에 표시할 지표 데이터 계산/조회."""
    indicator_ids = [i.strip() for i in indicators.split(",")]
    # TODO: indicator_service.compute(symbol, interval, indicator_ids, limit)
    return {ind_id: [] for ind_id in indicator_ids}


@router.get("/catalog")
async def get_indicator_catalog():
    """사용 가능한 지표 목록 조회."""
    # TODO: load from ai/indicators/registry.py
    return {"indicators": []}
