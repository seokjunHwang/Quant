from fastapi import APIRouter, Depends, Query

from app.dependencies import get_dynamodb

router = APIRouter()


@router.get("")
async def get_signals(
    symbol: str | None = Query(None),
    limit: int = Query(50, le=200),
    db=Depends(get_dynamodb),
):
    """AI 시그널 목록 조회."""
    # TODO: implement signal_repo.query
    return {"signals": []}


@router.get("/latest")
async def get_latest_signals(db=Depends(get_dynamodb)):
    """각 심볼의 최신 시그널 조회."""
    # TODO: implement signal_repo.get_latest_per_symbol
    return {"signals": []}


@router.post("/trigger")
async def trigger_signal_run(
    symbols: list[str] | None = None,
    db=Depends(get_dynamodb),
):
    """AI 시그널 생성 수동 트리거."""
    # TODO: trigger ai/signals/xgboost_signal.py
    return {"task_id": "", "status": "queued"}
