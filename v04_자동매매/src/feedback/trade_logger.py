"""
Phase 2: 트레이드 기록 + 로직체인 성과 추적.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from src.utils.config import DATA_DIR

logger = logging.getLogger(__name__)

TRADES_DIR = DATA_DIR / "trades"


def log_trade(trade: dict) -> None:
    """트레이드 결과를 JSON 파일로 기록."""
    TRADES_DIR.mkdir(parents=True, exist_ok=True)

    trade["logged_at"] = datetime.now().isoformat()

    # Append to daily file
    today = datetime.now().strftime("%Y-%m-%d")
    file_path = TRADES_DIR / f"trades_{today}.json"

    existing = []
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            existing = json.load(f)

    existing.append(trade)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    logger.info(f"Trade logged: {trade.get('ticker', '?')} → {trade.get('result', '?')}")


def load_all_trades() -> list[dict]:
    """모든 트레이드 기록 로드."""
    TRADES_DIR.mkdir(parents=True, exist_ok=True)
    all_trades = []

    for f in sorted(TRADES_DIR.glob("trades_*.json")):
        with open(f, "r", encoding="utf-8") as fh:
            trades = json.load(fh)
            all_trades.extend(trades)

    return all_trades


def calc_chain_accuracy() -> dict[str, float]:
    """
    로직체인별 적중률 계산.

    Returns:
        {chain_id: accuracy_ratio}
    """
    trades = load_all_trades()

    chain_results: dict[str, dict] = {}  # {chain_id: {win: n, total: n}}

    for t in trades:
        chain_id = t.get("logic_chain_id")
        if not chain_id:
            continue

        if chain_id not in chain_results:
            chain_results[chain_id] = {"win": 0, "total": 0}

        chain_results[chain_id]["total"] += 1
        if t.get("result") == "profit":
            chain_results[chain_id]["win"] += 1

    return {
        cid: data["win"] / data["total"] if data["total"] > 0 else 0.0
        for cid, data in chain_results.items()
    }


def get_performance_summary() -> dict:
    """전체 트레이딩 성과 요약."""
    trades = load_all_trades()

    if not trades:
        return {"total_trades": 0}

    profits = [t for t in trades if t.get("result") == "profit"]
    losses = [t for t in trades if t.get("result") == "loss"]

    total_pnl = sum(t.get("pnl_percent", 0) for t in trades)
    avg_pnl = total_pnl / len(trades) if trades else 0

    return {
        "total_trades": len(trades),
        "wins": len(profits),
        "losses": len(losses),
        "win_rate": round(len(profits) / len(trades) * 100, 1) if trades else 0,
        "total_pnl_pct": round(total_pnl, 2),
        "avg_pnl_pct": round(avg_pnl, 2),
        "best_trade": max((t.get("pnl_percent", 0) for t in trades), default=0),
        "worst_trade": min((t.get("pnl_percent", 0) for t in trades), default=0),
    }
