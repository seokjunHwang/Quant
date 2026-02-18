from fastapi import HTTPException, status


class NotFoundError(HTTPException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class AuthError(HTTPException):
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class BinanceAPIError(HTTPException):
    def __init__(self, detail: str = "Binance API error"):
        super().__init__(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
