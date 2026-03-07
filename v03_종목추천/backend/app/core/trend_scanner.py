"""
Trend Scanner — 전체 파이프라인 오케스트레이터.

Step 1: 테마 발굴 (Perplexity) → Step 2: 종목 발굴 (Claude)
→ Step 3: 검증 (yfinance + AI) → Step 4: RSI 스캔 (기존 엔진)
→ Step 5: 최종 스코어링
"""

import logging
import time
from datetime import datetime

from app.core.data_fetcher import fetch_batch
from app.core.final_scorer import calculate_final_scores
from app.core.pool_updater import save_dynamic_pool
from app.core.rsi_divergence import detect_divergences
from app.core.stock_discovery import discover_stocks
from app.core.stock_validator import validate_stocks
from app.core.trend_discovery import discover_themes
from app.models.schemas import (
    DivergenceSignal,
    TrendScanResult,
)

logger = logging.getLogger(__name__)

# In-memory cache
_last_trend_scan: TrendScanResult | None = None
_is_trend_scanning: bool = False


def run_trend_scan() -> TrendScanResult:
    """
    전체 트렌드 발굴 파이프라인 실행.

    Step 1: Perplexity → 핫 테마 5개
    Step 2: Claude → 테마당 종목 5~10개
    Step 3: yfinance + AI → 검증 (Fail 제거, 경고 플래그)
    Step 4: 기존 RSI 엔진 → 다이버전스 시그널
    Step 5: 합산 → 최종 랭킹
    """
    global _last_trend_scan, _is_trend_scanning
    _is_trend_scanning = True
    start = time.time()

    try:
        # ── Step 1: 테마 발굴 ──
        logger.info("=" * 60)
        logger.info("Step 1: Discovering trending themes...")
        themes = discover_themes()

        if not themes:
            logger.warning("No themes discovered. Aborting scan.")
            return _empty_result(start)

        # ── Step 2: 종목 발굴 ──
        logger.info("=" * 60)
        logger.info("Step 2: Discovering stocks per theme...")
        discovered = discover_stocks(themes)

        if not discovered:
            logger.warning("No stocks discovered. Aborting scan.")
            return _empty_result(start, themes=themes)

        # ── Step 3: 종목 검증 ──
        logger.info("=" * 60)
        logger.info("Step 3: Validating discovered stocks...")
        validated = validate_stocks(discovered)

        if not validated:
            logger.warning("No stocks passed validation.")
            return _empty_result(start, themes=themes)

        # 검증 통과 종목을 dynamic_pool.json으로 저장
        save_dynamic_pool(validated)

        # ── Step 4: RSI 스캔 ──
        logger.info("=" * 60)
        logger.info("Step 4: Running RSI divergence scan...")
        tickers = [s.ticker for s in validated]
        ticker_info = {s.ticker: s for s in validated}

        candles = fetch_batch(tickers)

        all_signals: list[DivergenceSignal] = []
        for ticker, df in candles.items():
            info = ticker_info.get(ticker)
            if not info:
                continue

            divergences = detect_divergences(df)
            current_price = float(df["close"].iloc[-1]) if not df.empty else 0.0

            for div in divergences:
                price_change = (
                    ((current_price - div.price) / div.price * 100)
                    if div.price > 0 else 0.0
                )

                signal = DivergenceSignal(
                    ticker=ticker,
                    name=info.name,
                    market="US",
                    category=info.theme,
                    signal_type=div.signal_type,
                    signal_label=div.signal_label,
                    detected_at=div.timestamp,
                    price_at_signal=div.price,
                    rsi_at_signal=round(div.rsi, 2),
                    current_price=current_price,
                    price_change_pct=round(price_change, 2),
                )
                all_signals.append(signal)

        logger.info(f"RSI scan found {len(all_signals)} signals from {len(candles)} tickers")

        # ── Step 5: 최종 스코어링 ──
        logger.info("=" * 60)
        logger.info("Step 5: Calculating final scores...")
        final_rankings = calculate_final_scores(validated, all_signals)

        duration = time.time() - start

        result = TrendScanResult(
            scanned_at=datetime.now(),
            themes=themes,
            discovered_count=len(discovered),
            validated_count=len(validated),
            final_rankings=final_rankings,
            scan_duration_sec=round(duration, 2),
        )

        _last_trend_scan = result

        logger.info("=" * 60)
        logger.info(
            f"Trend scan complete in {duration:.1f}s: "
            f"{len(themes)} themes → {len(discovered)} discovered → "
            f"{len(validated)} validated → {len(final_rankings)} ranked"
        )

        return result

    except Exception as e:
        logger.error(f"Trend scan failed: {e}", exc_info=True)
        return _empty_result(start)

    finally:
        _is_trend_scanning = False


def _empty_result(
    start: float,
    themes: list | None = None,
) -> TrendScanResult:
    """빈 결과 생성."""
    return TrendScanResult(
        scanned_at=datetime.now(),
        themes=themes or [],
        discovered_count=0,
        validated_count=0,
        final_rankings=[],
        scan_duration_sec=round(time.time() - start, 2),
    )


def get_last_trend_scan() -> TrendScanResult | None:
    return _last_trend_scan


def is_trend_scanning() -> bool:
    return _is_trend_scanning
