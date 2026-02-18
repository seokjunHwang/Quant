from fastapi import APIRouter, Depends, Query

from app.dependencies import get_dynamodb

router = APIRouter()


@router.get("/results")
async def get_backtest_results(
    asset: str | None = Query(None),
    phase: str | None = Query(None),
    limit: int = Query(20, le=100),
    db=Depends(get_dynamodb),
):
    """백테스팅 결과 조회."""
    # TODO: implement backtest_repo.query
    return {"results": []}


@router.post("/run")
async def run_backtest(
    strategy_ids: list[str] | None = None,
    phase: str = Query("quick-scan"),
    asset: str = Query("BTCUSDT"),
    db=Depends(get_dynamodb),
):
    """백테스팅 실행 트리거."""
    # TODO: trigger ai/pipeline/backtester
    return {"task_id": "", "status": "started"}
