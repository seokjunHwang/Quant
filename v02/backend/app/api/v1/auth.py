from fastapi import APIRouter, Depends

from app.dependencies import get_dynamodb

router = APIRouter()


@router.post("/keys")
async def store_api_keys(
    payload: dict,
    db=Depends(get_dynamodb),
):
    """Binance API 키 암호화 저장 + JWT 세션 토큰 발급."""
    # TODO: encrypt keys, store in v02_user_sessions, return JWT
    return {"session_token": "", "expires_at": ""}


@router.delete("/keys")
async def clear_api_keys(db=Depends(get_dynamodb)):
    """저장된 API 키 삭제."""
    # TODO: delete from v02_user_sessions
    return {"status": "cleared"}


@router.get("/verify")
async def verify_session():
    """세션 유효성 검증."""
    # TODO: decode JWT, check session exists
    return {"valid": False, "testnet": True}
