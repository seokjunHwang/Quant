from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "TradingPipeline API"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # AWS DynamoDB
    aws_region: str = "ap-northeast-2"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    dynamodb_endpoint_url: str | None = None  # Local DynamoDB용
    dynamodb_table_prefix: str = "v02_"

    # Binance
    binance_testnet: bool = True
    binance_base_url: str = "https://testnet.binancefuture.com"
    binance_ws_url: str = "wss://fstream.binancefuture.com"

    # AI
    ai_service_mode: str = "internal"  # "internal" | "subprocess" | "http"
    ai_service_url: str = "http://localhost:8001"
    anthropic_api_key: str = ""

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_expire_hours: int = 24
    encryption_key: str = ""  # AES-256 key for API key storage

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "env_prefix": "V02_"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
