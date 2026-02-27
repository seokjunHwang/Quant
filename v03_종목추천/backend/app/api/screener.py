import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Query

from app.core.scanner import get_last_scan, is_scanning, run_scan
from app.models.schemas import ScanResult, ScanStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scan", tags=["screener"])


@router.get("", response_model=ScanResult | None)
async def get_scan_results(
    market: str | None = Query(None, description="US or KR"),
    category: str | None = Query(None, description="Category filter"),
    signal_type: str | None = Query(None, description="bullish or bearish"),
):
    """Get cached latest scan results with optional filtering."""
    result = get_last_scan()
    if result is None:
        return None

    signals = result.signals

    if market:
        signals = [s for s in signals if s.market == market]
    if category:
        signals = [s for s in signals if s.category == category]
    if signal_type:
        if signal_type == "bullish":
            signals = [s for s in signals if "bullish" in s.signal_type]
        elif signal_type == "bearish":
            signals = [s for s in signals if "bearish" in s.signal_type]

    return ScanResult(
        scanned_at=result.scanned_at,
        total_stocks=result.total_stocks,
        signals_found=len(signals),
        scan_duration_sec=result.scan_duration_sec,
        signals=signals,
    )


_VALID_SCAN_INTERVALS = {"15m", "1h", "4h", "1d", "1w"}


@router.post("/trigger", response_model=ScanResult)
async def trigger_scan(
    background_tasks: BackgroundTasks,
    market: str | None = Query(None, description="US or KR"),
    interval: str = Query("4h", description="Candle interval: 15m, 1h, 4h, 1d, 1w"),
    rsi_period: int | None = Query(None, ge=2, le=50),
    lb_left: int | None = Query(None, ge=1, le=20),
    lb_right: int | None = Query(None, ge=1, le=20),
    range_lower: int | None = Query(None, ge=1, le=50),
    range_upper: int | None = Query(None, ge=10, le=200),
):
    """Trigger a new scan immediately with optional RSI divergence parameters."""
    if interval not in _VALID_SCAN_INTERVALS:
        interval = "4h"

    if is_scanning():
        last = get_last_scan()
        if last:
            return last
        return ScanResult(
            scanned_at=datetime.now(),
            total_stocks=0,
            signals_found=0,
            scan_duration_sec=0.0,
            signals=[],
        )

    try:
        result = run_scan(
            market,
            interval=interval,
            rsi_period=rsi_period,
            lb_left=lb_left,
            lb_right=lb_right,
            range_lower=range_lower,
            range_upper=range_upper,
        )
        return result
    except Exception as e:
        logger.exception(f"Scan failed: {e}")
        return ScanResult(
            scanned_at=datetime.now(),
            total_stocks=0,
            signals_found=0,
            scan_duration_sec=0.0,
            signals=[],
        )


@router.get("/status", response_model=ScanStatus)
async def get_scan_status():
    """Get current scan status."""
    last = get_last_scan()
    return ScanStatus(
        last_scan=last.scanned_at if last else None,
        next_scan=None,
        is_scanning=is_scanning(),
    )
