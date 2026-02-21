import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.core.scanner import run_scan

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def scheduled_scan():
    """Scheduled scan job — runs every SCAN_INTERVAL_HOURS."""
    logger.info("Scheduled scan triggered")
    try:
        result = run_scan()
        logger.info(f"Scheduled scan done: {result.signals_found} signals found")
    except Exception as e:
        logger.error(f"Scheduled scan failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting v03 RSI Divergence Screener")
    scheduler.add_job(
        scheduled_scan,
        "interval",
        hours=settings.SCAN_INTERVAL_HOURS,
        id="scan_job",
    )
    scheduler.start()
    logger.info(f"Scheduler started (every {settings.SCAN_INTERVAL_HOURS}h)")

    yield

    # Shutdown
    scheduler.shutdown()
    logger.info("Scheduler stopped")


app = FastAPI(
    title="RSI Divergence Screener",
    description="v03 종목추천 — RSI 다이버전스 기반 종목 스크리너",
    version="0.1.0",
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
