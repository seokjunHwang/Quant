"""
Main Scanner Orchestrator.
Loads stock pool, fetches data, runs RSI divergence detection,
and returns sorted results.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

from app.core.data_fetcher import fetch_batch
from app.core.rsi_divergence import detect_divergences
from app.models.schemas import DivergenceSignal, ScanResult, StockPool

# Appropriate fetch days per interval for scanning
# (enough for RSI warmup + divergence detection without overloading yfinance)
_SCAN_DAYS: dict[str, int] = {
    "15m": 60,   # yfinance max for 15m
    "1h": 180,   # ~1400 candles
    "4h": 180,   # ~360 candles
    "1d": 365,   # ~250 candles
    "1w": 730,   # ~104 candles
}

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

# In-memory cache for latest scan result
_last_scan: ScanResult | None = None
_is_scanning: bool = False


def load_stock_pool(market: str | None = None) -> list[dict]:
    """Load stock pool from JSON files."""
    stocks = []

    files = []
    if market is None or market == "US":
        files.append(("US", DATA_DIR / "us_stocks.json"))
    if market is None or market == "KR":
        files.append(("KR", DATA_DIR / "kr_stocks.json"))

    for mkt, path in files:
        if not path.exists():
            logger.warning(f"Stock pool file not found: {path}")
            continue
        with open(path, "r", encoding="utf-8") as f:
            pool = StockPool(**json.load(f))
        for s in pool.stocks:
            stocks.append({
                "ticker": s.ticker,
                "name": s.name,
                "market": mkt,
                "category": s.category,
                "pool_type": s.pool_type,
            })

    return stocks


def run_scan(
    market: str | None = None,
    interval: str = "4h",
    rsi_period: int | None = None,
    lb_left: int | None = None,
    lb_right: int | None = None,
    range_lower: int | None = None,
    range_upper: int | None = None,
) -> ScanResult:
    """
    Execute full scan pipeline:
    1. Load stock pool
    2. Fetch candles in batch (any interval)
    3. Detect RSI divergences per ticker
    4. Sort by newest signal first
    5. Cache and return result
    """
    global _last_scan, _is_scanning
    _is_scanning = True
    start = time.time()

    try:
        # 1. Load stock pool
        pool = load_stock_pool(market)
        if not pool:
            return ScanResult(
                scanned_at=datetime.now(),
                total_stocks=0,
                signals_found=0,
                scan_duration_sec=0.0,
                signals=[],
            )

        tickers = [s["ticker"] for s in pool]
        ticker_info = {s["ticker"]: s for s in pool}

        days = _SCAN_DAYS.get(interval, 180)
        logger.info(f"Starting scan for {len(tickers)} tickers (market={market}, interval={interval}, days={days})")

        # 2. Fetch candles
        candles = fetch_batch(tickers, interval=interval, days=days)

        # 3. Detect divergences
        all_signals: list[DivergenceSignal] = []

        for ticker, df in candles.items():
            info = ticker_info.get(ticker, {})
            divergences = detect_divergences(
                df,
                rsi_period=rsi_period,
                lb_left=lb_left,
                lb_right=lb_right,
                range_lower=range_lower,
                range_upper=range_upper,
            )

            current_price = float(df["close"].iloc[-1]) if not df.empty else 0.0

            for div in divergences:
                price_change = (
                    ((current_price - div.price) / div.price * 100)
                    if div.price > 0 else 0.0
                )

                signal = DivergenceSignal(
                    ticker=ticker,
                    name=info.get("name", ticker),
                    market=info.get("market", ""),
                    category=info.get("category", ""),
                    signal_type=div.signal_type,
                    signal_label=div.signal_label,
                    detected_at=div.timestamp,
                    price_at_signal=div.price,
                    rsi_at_signal=round(div.rsi, 2),
                    current_price=current_price,
                    price_change_pct=round(price_change, 2),
                )
                all_signals.append(signal)

        # 4. Sort by newest first
        all_signals.sort(key=lambda s: s.detected_at, reverse=True)

        duration = time.time() - start

        result = ScanResult(
            scanned_at=datetime.now(),
            total_stocks=len(candles),
            signals_found=len(all_signals),
            scan_duration_sec=round(duration, 2),
            signals=all_signals,
        )

        _last_scan = result
        logger.info(
            f"Scan complete: {len(all_signals)} signals from "
            f"{len(candles)} tickers in {duration:.1f}s"
        )
        return result

    finally:
        _is_scanning = False


def get_last_scan() -> ScanResult | None:
    """Return cached last scan result."""
    return _last_scan


def is_scanning() -> bool:
    """Check if a scan is currently running."""
    return _is_scanning
