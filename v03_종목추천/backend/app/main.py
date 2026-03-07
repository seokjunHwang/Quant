import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.core.scanner import run_scan
from app.core.trend_scanner import run_trend_scan

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def scheduled_scan():
    """Scheduled scan job — runs every SCAN_INTERVAL_HOURS."""
    logger.info("Scheduled RSI scan triggered")
    try:
        result = run_scan()
        logger.info(f"Scheduled RSI scan done: {result.signals_found} signals found")
    except Exception as e:
        logger.error(f"Scheduled RSI scan failed: {e}")


def scheduled_trend_scan():
    """Scheduled trend scan — runs every TREND_SCAN_INTERVAL_HOURS."""
    logger.info("Scheduled trend scan triggered")
    try:
        result = run_trend_scan()
        logger.info(
            f"Scheduled trend scan done: {len(result.themes)} themes, "
            f"{len(result.final_rankings)} ranked stocks"
        )
    except Exception as e:
        logger.error(f"Scheduled trend scan failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting v03 RSI Divergence Screener + Trend Discovery")

    scheduler.add_job(
        scheduled_scan,
        "interval",
        hours=settings.SCAN_INTERVAL_HOURS,
        id="rsi_scan_job",
    )

    if settings.PERPLEXITY_API_KEY and settings.ANTHROPIC_API_KEY:
        scheduler.add_job(
            scheduled_trend_scan,
            "interval",
            hours=settings.TREND_SCAN_INTERVAL_HOURS,
            id="trend_scan_job",
        )
        logger.info(
            f"Trend scanner scheduled (every {settings.TREND_SCAN_INTERVAL_HOURS}h)"
        )
    else:
        logger.warning(
            "Trend scanner disabled — set V03_PERPLEXITY_API_KEY and "
            "V03_ANTHROPIC_API_KEY in .env to enable"
        )

    scheduler.start()
    logger.info(f"Scheduler started (RSI every {settings.SCAN_INTERVAL_HOURS}h)")

    yield

    # Shutdown
    scheduler.shutdown()
    logger.info("Scheduler stopped")


app = FastAPI(
    title="RSI Divergence Screener",
    description="v03 종목추천 — 트렌드 발굴 + RSI 다이버전스 기반 종목 스크리너",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "v03-screener"}
