from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["http://localhost:3101"]

    # Scan settings
    SCAN_INTERVAL_HOURS: int = 4
    FETCH_DAYS: int = 180
    MAX_WORKERS: int = 10

    # RSI Divergence parameters (matches Pine Script)
    RSI_PERIOD: int = 14
    PIVOT_LOOKBACK_LEFT: int = 5
    PIVOT_LOOKBACK_RIGHT: int = 3
    RANGE_UPPER: int = 50
    RANGE_LOWER: int = 5

    model_config = {"env_prefix": "V03_", "env_file": ".env"}


settings = Settings()
