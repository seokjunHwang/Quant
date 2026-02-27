"""
Dynamic KRX stock name ↔ ticker lookup using pykrx.

Fetches ALL KOSPI + KOSDAQ stock names in batch and caches to a local JSON file.
Cache refreshes once per day (or on first startup).
"""

import json
import logging
import threading
import time
from datetime import date, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_PATH = Path(__file__).parent.parent / "data" / "krx_name_cache.json"
_CACHE_MAX_AGE_HOURS = 24

# In-memory lookup tables (populated from cache or pykrx)
_name_to_ticker: dict[str, str] = {}   # "삼성전자" → "005930.KS"
_num_to_ticker: dict[str, str] = {}    # "005930"   → "005930.KS"
_ticker_to_name: dict[str, str] = {}   # "005930.KS" → "삼성전자"
_loaded = False
_lock = threading.Lock()


def _build_from_pykrx() -> dict[str, str]:
    """Fetch all KRX stocks via pykrx and return {name: ticker_with_suffix}."""
    from pykrx.website.krx.market import wrap

    today = date.today().strftime("%Y%m%d")
    mapping: dict[str, str] = {}

    try:
        kospi = wrap.get_market_ticker_and_name(today, "KOSPI")
        for code, name in kospi.items():
            mapping[name] = f"{code}.KS"
    except Exception as e:
        logger.warning(f"Failed to fetch KOSPI list: {e}")

    try:
        kosdaq = wrap.get_market_ticker_and_name(today, "KOSDAQ")
        for code, name in kosdaq.items():
            mapping[name] = f"{code}.KQ"
    except Exception as e:
        logger.warning(f"Failed to fetch KOSDAQ list: {e}")

    return mapping


def _save_cache(mapping: dict[str, str]) -> None:
    """Save lookup mapping to disk cache."""
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now().isoformat(),
            "stocks": mapping,
        }
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=0)
        logger.info(f"KRX cache saved: {len(mapping)} stocks → {_CACHE_PATH}")
    except Exception as e:
        logger.warning(f"Failed to save KRX cache: {e}")


def _load_cache() -> dict[str, str] | None:
    """Load lookup mapping from disk cache if fresh enough."""
    if not _CACHE_PATH.exists():
        return None
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        updated = datetime.fromisoformat(data["updated_at"])
        age_hours = (datetime.now() - updated).total_seconds() / 3600
        if age_hours > _CACHE_MAX_AGE_HOURS:
            logger.info(f"KRX cache expired ({age_hours:.1f}h old)")
            return None
        stocks = data.get("stocks", {})
        logger.info(f"KRX cache loaded: {len(stocks)} stocks ({age_hours:.1f}h old)")
        return stocks
    except Exception as e:
        logger.warning(f"Failed to load KRX cache: {e}")
        return None


def _populate(mapping: dict[str, str]) -> None:
    """Populate in-memory lookup tables from mapping."""
    global _name_to_ticker, _num_to_ticker, _ticker_to_name, _loaded
    _name_to_ticker = dict(mapping)
    _num_to_ticker = {}
    _ticker_to_name = {}
    for name, ticker in mapping.items():
        num = ticker.split(".")[0]
        _num_to_ticker[num] = ticker
        _ticker_to_name[ticker] = name
    _loaded = True


def _ensure_loaded() -> None:
    """Load lookup tables (from cache or pykrx). Thread-safe, runs once."""
    global _loaded
    if _loaded:
        return

    with _lock:
        if _loaded:
            return

        # Try disk cache first
        cached = _load_cache()
        if cached:
            _populate(cached)
            return

        # Fetch from pykrx (slow but one-time)
        logger.info("Building KRX lookup from pykrx (first time or cache expired)...")
        start = time.time()
        mapping = _build_from_pykrx()
        elapsed = time.time() - start

        if mapping:
            _populate(mapping)
            _save_cache(mapping)
            logger.info(f"KRX lookup ready: {len(mapping)} stocks in {elapsed:.1f}s")
        else:
            logger.warning("pykrx returned empty data; KRX lookup unavailable")
            _loaded = True  # Don't retry forever


def resolve_korean_name(name: str) -> str | None:
    """
    Resolve a Korean stock name to a yfinance ticker.
    Returns None if not found.

    Examples:
        "삼성전자" → "005930.KS"
        "두산퓨얼셀" → "336260.KS"
        "리노공업" → "058470.KQ"
    """
    _ensure_loaded()

    # Exact match
    if name in _name_to_ticker:
        return _name_to_ticker[name]

    # Partial match (input is substring of stock name)
    matches = [(n, t) for n, t in _name_to_ticker.items() if name in n]
    if len(matches) == 1:
        return matches[0][1]
    if matches:
        # Prefer exact-length match, then shortest name
        matches.sort(key=lambda x: (len(x[0]) != len(name), len(x[0])))
        return matches[0][1]

    return None


def resolve_korean_number(num: str) -> str | None:
    """
    Resolve a 6-digit Korean stock number to a yfinance ticker.
    Returns None if not found (caller should try .KS/.KQ fallback).

    Examples:
        "005930" → "005930.KS"
        "058470" → "058470.KQ"
    """
    _ensure_loaded()
    return _num_to_ticker.get(num)


def get_name_by_ticker(yf_ticker: str) -> str | None:
    """
    Reverse lookup: yfinance ticker → Korean stock name.
    Returns None for non-Korean tickers.

    Examples:
        "005930.KS" → "삼성전자"
        "058470.KQ" → "리노공업"
        "AAPL"      → None
    """
    _ensure_loaded()
    return _ticker_to_name.get(yf_ticker)


def preload_async() -> None:
    """Kick off background loading so first request doesn't block."""
    thread = threading.Thread(target=_ensure_loaded, daemon=True)
    thread.start()
