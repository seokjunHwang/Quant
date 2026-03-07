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

    # AI API Keys
    PERPLEXITY_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Trend scan settings
    TREND_SCAN_INTERVAL_HOURS: int = 24
    TOP_THEMES_COUNT: int = 5
    STOCKS_PER_THEME: int = 10

    # Market cap range (USD)
    MIN_MARKET_CAP: int = 100_000_000       # $100M
    MAX_MARKET_CAP: int = 10_000_000_000    # $10B

    # Validation thresholds
    MIN_AVG_DAILY_VALUE: int = 500_000      # $500K
    MAX_WARNING_COUNT: int = 2              # 3+ → auto remove
    HIGH_SHORT_INTEREST: float = 30.0       # 30%+

    model_config = {"env_prefix": "V03_", "env_file": ".env"}


settings = Settings()
