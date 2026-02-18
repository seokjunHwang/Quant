"""SQLite database helper for the strategy pipeline.

Stores indicator metadata, analysis results, strategies, and backtest results.
Separate from the main DynamoDB — pipeline uses local SQLite for fast iteration.
"""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "pipeline.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS indicators (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_file TEXT NOT NULL,
    converted_file TEXT,
    source_code_hash TEXT,
    pine_version TEXT,
    source_url TEXT,
    conversion_status TEXT DEFAULT 'pending',
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    converted_at DATETIME,
    verified_at DATETIME
);

CREATE TABLE IF NOT EXISTS analysis_results (
    indicator_id TEXT PRIMARY KEY REFERENCES indicators(id),
    roles TEXT,
    indicator_type TEXT,
    market_condition TEXT,
    timeframe_fit TEXT,
    recommended_partners TEXT,
    default_params TEXT,
    description TEXT,
    analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS strategies (
    id TEXT PRIMARY KEY,
    primary_indicator_id TEXT NOT NULL,
    primary_params TEXT,
    confirmation_ids TEXT,
    confirmation_params TEXT,
    filter_indicator_id TEXT,
    filter_params TEXT,
    exit_indicator_id TEXT,
    exit_params TEXT,
    template_type TEXT,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT REFERENCES strategies(id),
    asset TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    period_start DATE,
    period_end DATE,
    period_label TEXT,
    total_return_pct REAL,
    annual_return_pct REAL,
    benchmark_return_pct REAL,
    excess_return_pct REAL,
    max_drawdown_pct REAL,
    sharpe_ratio REAL,
    sortino_ratio REAL,
    calmar_ratio REAL,
    total_trades INTEGER,
    win_rate_pct REAL,
    profit_factor REAL,
    avg_trade_return_pct REAL,
    avg_holding_period_days REAL,
    composite_score REAL,
    tested_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fusion_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT REFERENCES strategies(id),
    step_number INTEGER,
    added_indicator_id TEXT,
    added_role TEXT,
    sharpe_ratio REAL,
    total_return_pct REAL,
    max_drawdown_pct REAL,
    sharpe_delta REAL,
    return_delta REAL,
    mdd_delta REAL,
    contribution_score REAL,
    tested_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


class PipelineDB:
    """Thin wrapper around SQLite for pipeline data."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = str(db_path or DB_PATH)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_schema(self):
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    # ── Indicator CRUD ──────────────────────────────────────

    def upsert_indicator(self, data: dict):
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO indicators (id, title, source_file, source_code_hash, conversion_status)
                   VALUES (:id, :title, :source_file, :source_code_hash, :conversion_status)
                   ON CONFLICT(id) DO UPDATE SET
                       source_code_hash = :source_code_hash,
                       conversion_status = CASE
                           WHEN excluded.source_code_hash != indicators.source_code_hash
                           THEN 'pending'
                           ELSE indicators.conversion_status
                       END
                """,
                data,
            )

    def update_indicator_status(self, indicator_id: str, status: str, **kwargs):
        sets = ["conversion_status = ?"]
        vals = [status]
        for k, v in kwargs.items():
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(indicator_id)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE indicators SET {', '.join(sets)} WHERE id = ?", vals
            )

    def get_indicator(self, indicator_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM indicators WHERE id = ?", (indicator_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_indicators_by_status(self, status: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM indicators WHERE conversion_status = ?", (status,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_indicators(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM indicators ORDER BY added_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Analysis CRUD ───────────────────────────────────────

    def upsert_analysis(self, data: dict):
        cols = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())
        updates = ", ".join(f"{k} = :{k}" for k in data.keys() if k != "indicator_id")
        with self._connect() as conn:
            conn.execute(
                f"""INSERT INTO analysis_results ({cols}) VALUES ({placeholders})
                    ON CONFLICT(indicator_id) DO UPDATE SET {updates}""",
                data,
            )

    def get_analysis(self, indicator_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM analysis_results WHERE indicator_id = ?",
                (indicator_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_analyzed_indicators(self) -> list[dict]:
        """Get all indicators with their analysis results."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT i.*, a.roles, a.indicator_type, a.market_condition,
                          a.timeframe_fit, a.recommended_partners, a.default_params,
                          a.description as analysis_description
                   FROM indicators i
                   JOIN analysis_results a ON i.id = a.indicator_id
                   WHERE i.conversion_status = 'verified'"""
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Strategy CRUD ───────────────────────────────────────

    def insert_strategy(self, data: dict):
        cols = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())
        with self._connect() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO strategies ({cols}) VALUES ({placeholders})",
                data,
            )

    def get_all_strategies(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM strategies").fetchall()
            return [dict(r) for r in rows]

    # ── Backtest CRUD ───────────────────────────────────────

    def insert_backtest_result(self, data: dict):
        cols = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO backtest_results ({cols}) VALUES ({placeholders})", data
            )

    def get_backtest_results(self, strategy_id: str | None = None) -> list[dict]:
        with self._connect() as conn:
            if strategy_id:
                rows = conn.execute(
                    "SELECT * FROM backtest_results WHERE strategy_id = ? ORDER BY composite_score DESC",
                    (strategy_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM backtest_results ORDER BY composite_score DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    def get_top_strategies(self, limit: int = 10) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT br.*, s.description, s.primary_indicator_id
                   FROM backtest_results br
                   JOIN strategies s ON br.strategy_id = s.id
                   ORDER BY br.composite_score DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Fusion Analysis CRUD ────────────────────────────────

    def insert_fusion_step(self, data: dict):
        cols = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO fusion_analysis ({cols}) VALUES ({placeholders})", data
            )

    def get_fusion_analysis(self, strategy_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM fusion_analysis WHERE strategy_id = ? ORDER BY step_number",
                (strategy_id,),
            ).fetchall()
            return [dict(r) for r in rows]
