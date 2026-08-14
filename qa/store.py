from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS alphas (
    id TEXT PRIMARY KEY,
    expression TEXT NOT NULL,
    description TEXT,
    hypothesis TEXT,
    dataset_ids TEXT,
    ast_hash TEXT UNIQUE,
    metrics_json TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    grade TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS simulations (
    id TEXT PRIMARY KEY,
    alpha_id TEXT,
    request_json TEXT,
    result_json TEXT,
    checks_json TEXT,
    status TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    audit_path TEXT
);
CREATE TABLE IF NOT EXISTS submissions (
    id TEXT PRIMARY KEY,
    alpha_id TEXT,
    submitted_at TEXT,
    user_confirmed INTEGER DEFAULT 0,
    platform_response TEXT,
    current_status TEXT,
    confirmed_active INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS daily_returns (
    alpha_id TEXT,
    date TEXT,
    pnl REAL,
    PRIMARY KEY (alpha_id, date)
);
CREATE TABLE IF NOT EXISTS lessons (
    id TEXT PRIMARY KEY,
    trigger TEXT,
    hypothesis TEXT,
    verdict TEXT,
    lesson TEXT,
    raw_ref TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS failures (
    id TEXT PRIMARY KEY,
    expression_hash TEXT,
    failure_reason TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sim_alpha ON simulations(alpha_id);
CREATE INDEX IF NOT EXISTS idx_lessons_trigger ON lessons(trigger);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    """SQLite 持久化 + JSONL 审计。所有写操作幂等（INSERT OR REPLACE）。"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_path = self.db_path.parent / "audit" / "audit.jsonl"
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ---- alphas ----
    def save_alpha(self, alpha: dict) -> int:
        self._conn.execute(
            "INSERT OR REPLACE INTO alphas "
            "(id, expression, description, hypothesis, dataset_ids, ast_hash, metrics_json, status, grade, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                alpha.get("id"),
                alpha["expression"],
                alpha.get("description"),
                alpha.get("hypothesis"),
                json.dumps(alpha.get("dataset_ids", [])),
                alpha.get("ast_hash"),
                json.dumps(alpha.get("metrics", {})),
                alpha.get("status", "DRAFT"),
                alpha.get("grade"),
                alpha.get("created_at", _now()),
            ),
        )
        self._conn.commit()
        return self._conn.total_changes

    def alpha_hash_exists(self, expr_hash: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM alphas WHERE ast_hash = ?", (expr_hash,)
        ).fetchone()
        return row is not None

    def list_alphas(self, status: str | None = None) -> list[dict]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM alphas WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM alphas ORDER BY created_at DESC"
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["dataset_ids"] = json.loads(d.get("dataset_ids") or "[]")
            d["metrics"] = json.loads(d.get("metrics_json") or "{}")
            out.append(d)
        return out

    # ---- simulations ----
    def save_simulation(self, sim: dict) -> int:
        self._conn.execute(
            "INSERT OR REPLACE INTO simulations "
            "(id, alpha_id, request_json, result_json, checks_json, status, started_at, finished_at, audit_path) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                sim.get("id"),
                sim.get("alpha_id"),
                json.dumps(sim.get("request", {})),
                json.dumps(sim.get("result", {})),
                json.dumps(sim.get("checks", [])),
                sim.get("status", "PENDING"),
                sim.get("started_at"),
                sim.get("finished_at"),
                sim.get("audit_path"),
            ),
        )
        self._conn.commit()
        return self._conn.total_changes

    def list_simulations(self, alpha_id: str | None = None) -> list[dict]:
        if alpha_id:
            rows = self._conn.execute(
                "SELECT * FROM simulations WHERE alpha_id = ? ORDER BY started_at DESC",
                (alpha_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM simulations ORDER BY started_at DESC"
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["request"] = json.loads(d.get("request_json") or "{}")
            d["result"] = json.loads(d.get("result_json") or "{}")
            d["checks"] = json.loads(d.get("checks_json") or "[]")
            out.append(d)
        return out

    # ---- lessons / failures ----
    def save_lesson(self, lesson: dict) -> int:
        self._conn.execute(
            "INSERT OR REPLACE INTO lessons "
            "(id, trigger, hypothesis, verdict, lesson, raw_ref, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                lesson.get("id"),
                lesson.get("trigger"),
                lesson.get("hypothesis"),
                lesson.get("verdict"),
                lesson.get("lesson"),
                lesson.get("raw_ref"),
                lesson.get("created_at", _now()),
            ),
        )
        self._conn.commit()
        return self._conn.total_changes

    def save_failure(self, failure: dict) -> int:
        self._conn.execute(
            "INSERT OR REPLACE INTO failures "
            "(id, expression_hash, failure_reason, created_at) VALUES (?,?,?,?)",
            (
                failure.get("id"),
                failure.get("expression_hash"),
                failure.get("failure_reason"),
                failure.get("created_at", _now()),
            ),
        )
        self._conn.commit()
        return self._conn.total_changes

    def list_failures(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM failures ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- audit ----
    def append_audit(self, kind: str, payload: dict) -> None:
        with open(self.audit_path, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {"ts": _now(), "kind": kind, **payload}, ensure_ascii=False
                )
                + "\n"
            )
