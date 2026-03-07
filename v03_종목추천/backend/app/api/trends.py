"""
Trend API endpoints — 트렌드 발굴 파이프라인 API.
"""

from datetime import datetime

from fastapi import APIRouter, Query

from app.core.trend_scanner import (
    get_last_trend_scan,
    is_trend_scanning,
    run_trend_scan,
)
from app.models.schemas import TrendScanResult, TrendScanStatus

router = APIRouter(prefix="/trends", tags=["trends"])


@router.get("", response_model=TrendScanResult | None)
async def get_trend_results(
    theme: str | None = Query(None, description="Filter by theme name"),
):
    """캐시된 트렌드 스캔 결과 조회."""
    result = get_last_trend_scan()
    if result is None:
        return None

    if theme:
        filtered_rankings = [
            r for r in result.final_rankings
            if theme.lower() in r.theme.lower()
        ]
        return TrendScanResult(
            scanned_at=result.scanned_at,
            themes=[t for t in result.themes if theme.lower() in t.theme.lower()],
            discovered_count=result.discovered_count,
            validated_count=result.validated_count,
            final_rankings=filtered_rankings,
            scan_duration_sec=result.scan_duration_sec,
        )

    return result


@router.post("/scan", response_model=TrendScanResult)
async def trigger_trend_scan():
    """트렌드 발굴 파이프라인 즉시 실행. (Step 1~5 전체)"""
    if is_trend_scanning():
        last = get_last_trend_scan()
        if last:
            return last
        return TrendScanResult(
            scanned_at=datetime.now(),
            themes=[],
            discovered_count=0,
            validated_count=0,
            final_rankings=[],
            scan_duration_sec=0.0,
        )

    result = run_trend_scan()
    return result


@router.get("/status", response_model=TrendScanStatus)
async def get_trend_status():
    """트렌드 스캔 상태 확인."""
    last = get_last_trend_scan()
    return TrendScanStatus(
        last_scan=last.scanned_at if last else None,
        is_scanning=is_trend_scanning(),
    )
