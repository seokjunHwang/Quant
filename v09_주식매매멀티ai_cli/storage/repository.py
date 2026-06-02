"""트랜스크립트 영속화 — SQLite 인덱스 + JSON 파일.

JSON 파일이 진실의 원본 (full transcript), SQLite 는 검색용 인덱스.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class Repository:
    base_dir: Path
    db_path: Path

    @classmethod
    def from_config(cls, config: dict) -> "Repository":
        storage_cfg = config.get("storage", {})
        base = Path(storage_cfg.get("path", "storage/runs.db")).parent
        runs = base / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        repo = cls(base_dir=runs, db_path=Path(storage_cfg.get("path", "storage/runs.db")))
        repo._init_db()
        return repo

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id        TEXT PRIMARY KEY,
                    ticker        TEXT NOT NULL,
                    asset_class   TEXT NOT NULL,
                    started_at    TEXT NOT NULL,
                    ended_at      TEXT,
                    stop_reason   TEXT,
                    total_cost_usd REAL,
                    total_tokens  INTEGER,
                    json_path     TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_ticker ON runs(ticker)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at)")

    @staticmethod
    def new_run_id() -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{ts}_{uuid.uuid4().hex[:8]}"

    def save(self, transcript: dict) -> Path:
        run_id = transcript["run_id"]
        json_path = self.base_dir / f"{run_id}.json"
        json_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO runs
                   (run_id, ticker, asset_class, started_at, ended_at,
                    stop_reason, total_cost_usd, total_tokens, json_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    transcript["agenda"]["ticker"],
                    transcript["agenda"]["asset_class"],
                    transcript["started_at"],
                    transcript.get("ended_at"),
                    (transcript.get("final_report") or {}).get("stop_reason"),
                    transcript.get("total_cost_usd", 0.0),
                    transcript.get("total_tokens", 0),
                    str(json_path),
                ),
            )
        log.info("saved transcript run_id=%s path=%s", run_id, json_path)
        return json_path

    def list_runs(self, *, ticker: str | None = None, since: str | None = None) -> list[dict]:
        q = "SELECT run_id, ticker, started_at, stop_reason, total_cost_usd FROM runs WHERE 1=1"
        params: list = []
        if ticker:
            q += " AND ticker = ?"
            params.append(ticker)
        if since:
            q += " AND started_at >= ?"
            params.append(since)
        q += " ORDER BY started_at DESC"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(q, params)]

    def load(self, run_id: str) -> dict:
        path = self.base_dir / f"{run_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))
