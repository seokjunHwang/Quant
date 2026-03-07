"""
Pool Updater — dynamic_pool.json 관리.
트렌드 발굴로 검증된 종목을 동적 풀로 저장하고 기존 스캐너와 연동.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from app.models.schemas import ValidatedStock

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
DYNAMIC_POOL_PATH = DATA_DIR / "dynamic_pool.json"


def save_dynamic_pool(stocks: list[ValidatedStock]) -> None:
    """검증된 종목을 dynamic_pool.json으로 저장."""
    pool_data = {
        "updated_at": datetime.now().isoformat(),
        "market": "US",
        "source": "trend_discovery",
        "stocks": [
            {
                "ticker": s.ticker,
                "name": s.name,
                "category": s.theme,
                "pool_type": "dynamic",
                "theme_rank": s.theme_rank,
                "stock_rank": s.stock_rank,
                "discovery_score": s.discovery_score,
                "market_cap": s.market_cap,
                "warning_count": s.warning_count,
            }
            for s in stocks
        ],
    }

    with open(DYNAMIC_POOL_PATH, "w", encoding="utf-8") as f:
        json.dump(pool_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Dynamic pool saved: {len(stocks)} stocks → {DYNAMIC_POOL_PATH}")


def load_dynamic_pool() -> list[dict]:
    """dynamic_pool.json에서 종목 로드. 기존 scanner.load_stock_pool() 형식과 호환."""
    if not DYNAMIC_POOL_PATH.exists():
        logger.info("No dynamic pool file found")
        return []

    try:
        with open(DYNAMIC_POOL_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        stocks = []
        for s in data.get("stocks", []):
            stocks.append({
                "ticker": s["ticker"],
                "name": s["name"],
                "market": "US",
                "category": s.get("category", ""),
                "pool_type": "dynamic",
            })

        logger.info(f"Dynamic pool loaded: {len(stocks)} stocks")
        return stocks

    except Exception as e:
        logger.error(f"Failed to load dynamic pool: {e}")
        return []
