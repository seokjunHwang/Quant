from fastapi import APIRouter, BackgroundTasks, Query

from app.core.scanner import get_last_scan, is_scanning, run_scan
from app.models.schemas import ScanResult, ScanStatus

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


@router.post("/trigger", response_model=ScanResult)
async def trigger_scan(
    background_tasks: BackgroundTasks,
    market: str | None = Query(None, description="US or KR"),
):
    """Trigger a new scan immediately."""
    if is_scanning():
        last = get_last_scan()
        if last:
            return last
        return ScanResult(
            scanned_at=__import__("datetime").datetime.now(),
            total_stocks=0,
            signals_found=0,
            scan_duration_sec=0.0,
            signals=[],
        )

    result = run_scan(market)
    return result


@router.get("/status", response_model=ScanStatus)
async def get_scan_status():
    """Get current scan status."""
    last = get_last_scan()
    return ScanStatus(
        last_scan=last.scanned_at if last else None,
        next_scan=None,
        is_scanning=is_scanning(),
    )
