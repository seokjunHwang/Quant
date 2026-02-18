from fastapi import APIRouter, Depends, Query

from app.dependencies import get_dynamodb

router = APIRouter()


@router.get("")
async def list_strategies(
    status: str | None = Query(None),
    limit: int = Query(20, le=100),
    db=Depends(get_dynamodb),
):
    """전략 파이프라인 결과 목록."""
    # TODO: implement strategy_repo.list
    return {"strategies": []}


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str, db=Depends(get_dynamodb)):
    """전략 상세 정보."""
    # TODO: implement strategy_repo.get
    return {"strategy_id": strategy_id}


@router.get("/{strategy_id}/backtest")
async def get_strategy_backtest(strategy_id: str, db=Depends(get_dynamodb)):
    """전략 백테스팅 결과."""
    # TODO: implement backtest_repo.get_by_strategy
    return {"strategy_id": strategy_id, "results": []}
