from fastapi import APIRouter, Depends, Header

from app.dependencies import get_dynamodb

router = APIRouter()


@router.post("/orders")
async def place_order(
    order: dict,
    x_session_token: str = Header(...),
    db=Depends(get_dynamodb),
):
    """주문 실행 (Binance Futures)."""
    # TODO: decrypt API keys, call binance_service.place_order
    return {"order_id": "", "status": "pending"}


@router.delete("/orders/{order_id}")
async def cancel_order(
    order_id: str,
    symbol: str,
    x_session_token: str = Header(...),
):
    """주문 취소."""
    # TODO: implement binance_service.cancel_order
    return {"order_id": order_id, "status": "CANCELED"}


@router.get("/orders")
async def get_open_orders(
    symbol: str | None = None,
    x_session_token: str = Header(...),
):
    """미체결 주문 목록."""
    # TODO: implement binance_service.get_open_orders
    return {"orders": []}


@router.get("/positions")
async def get_positions(x_session_token: str = Header(...)):
    """활성 포지션 목록."""
    # TODO: implement binance_service.get_positions
    return {"positions": []}


@router.get("/account")
async def get_account(x_session_token: str = Header(...)):
    """계정 잔액 정보."""
    # TODO: implement binance_service.get_account
    return {"totalBalance": 0, "availableBalance": 0, "totalUnrealizedProfit": 0}
