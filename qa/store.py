"""SQLite 持久化 + JSONL 审计。

表：alphas（候选/已提交 alpha 全生命周期）、simulations（每次模拟请求/结果）、
    submissions（提交记录与 ACTIVE 回查）、lessons（脱敏经验教训）、failures（证伪库）。
写操作幂等：alphas 等用 INSERT OR REPLACE；simulations 用 ON CONFLICT DO UPDATE
（保留 started_at，支持 PENDING → 终态多次更新）。支持中断后重跑跳过已完成项。
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def _jload(value: str | None, default: Any) -> Any:
    """JSON 字段防御解析：缺失/损坏返回默认值。"""
    if not value:
        return default
    try:
        return json.loads(value)
    except ValueError:
        return default


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

    # ---- alphas ----
    def save_alpha(self, alpha: dict[str, Any]) -> None:
        """保存/更新 alpha 记录（幂等，按 id 覆盖）。"""
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

    def alpha_hash_exists(self, expr_hash: str) -> bool:
        """按表达式哈希查重（预检阶段用，防止重复模拟消耗配额）。"""
        row = self._conn.execute(
            "SELECT 1 FROM alphas WHERE ast_hash = ?", (expr_hash,)
        ).fetchone()
        return row is not None

    def sim_failure_exists(self, expr_hash: str) -> bool:
        """按表达式哈希查 simulations 表已有 ERROR/FAILED 终态。

        平台语义拒绝的表达式（参数拒绝/平台 ERROR/FAILED）不重复模拟：
        ERROR/FAILED 记录即"已试过且失败"，重跑时跳过并报告原因；
        PENDING/TIMEOUT 不走此路径（中断恢复需续查），COMPLETE 已进 alphas 表。
        """
        row = self._conn.execute(
            "SELECT 1 FROM simulations WHERE alpha_id = ? "
            "AND status IN ('ERROR', 'FAILED') LIMIT 1",
            (expr_hash,),
        ).fetchone()
        return row is not None

    def list_alphas(self, status: str | None = None) -> list[dict[str, Any]]:
        """列出 alpha 记录（可按状态过滤；创建时间倒序）。"""
        if status:
            rows = self._conn.execute(
                "SELECT * FROM alphas WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM alphas ORDER BY created_at DESC"
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["dataset_ids"] = _jload(d.get("dataset_ids"), [])
            d["metrics"] = _jload(d.get("metrics_json"), {})
            out.append(d)
        return out

    # ---- simulations ----
    def save_simulation(self, sim: dict[str, Any]) -> None:
        """保存/更新一次模拟记录（幂等，按 id 覆盖）。

        id 为平台 sim_id（v1.6 中断恢复）；旧记录 id=sim_{expr_hash} 保留兼容
        （无平台 sim_id，不会被续查命中，重跑会重新模拟）。
        同一条模拟从 PENDING → 终态（COMPLETE/ERROR/TIMEOUT）多次调用：
        ON CONFLICT DO UPDATE 不覆盖 started_at，保留首次写入的发起时间。
        """
        self._conn.execute(
            "INSERT INTO simulations "
            "(id, alpha_id, request_json, result_json, checks_json, status, started_at, finished_at, audit_path) "
            "VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "alpha_id=excluded.alpha_id, request_json=excluded.request_json, "
            "result_json=excluded.result_json, checks_json=excluded.checks_json, "
            "status=excluded.status, finished_at=excluded.finished_at, "
            "audit_path=excluded.audit_path",
            (
                sim.get("id"),
                sim.get("alpha_id"),
                json.dumps(sim.get("request", {})),
                json.dumps(sim.get("result", {})),
                json.dumps(sim.get("checks", [])),
                sim.get("status", "PENDING"),
                sim.get("started_at", _now()),
                sim.get("finished_at"),
                sim.get("audit_path"),
            ),
        )
        self._conn.commit()

    def find_pending_sim_id(self, expr_hash: str) -> str | None:
        """查可续查的模拟记录（PENDING/TIMEOUT），返回平台 sim_id（simulations.id）。

        v1.6 中断恢复：重跑时先查此方法，有平台 sim_id → 不重新 simulate，
        直接 poll 续查；无记录/无 sim_id → 重新模拟。
        """
        row = self._conn.execute(
            "SELECT id FROM simulations WHERE alpha_id = ? "
            "AND status IN ('PENDING', 'TIMEOUT') AND id != '' "
            "ORDER BY started_at DESC LIMIT 1",
            (expr_hash,),
        ).fetchone()
        return row["id"] if row else None

    def delete_simulation(self, sim_id: str) -> None:
        """删除一条模拟记录（续查 404 平台已清理的过期 PENDING，回退重新模拟）。"""
        self._conn.execute("DELETE FROM simulations WHERE id = ?", (sim_id,))
        self._conn.commit()

    def list_simulations(self, alpha_id: str | None = None) -> list[dict[str, Any]]:
        """列出模拟记录（可按 alpha_id 过滤；开始时间倒序）。"""
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
            d["request"] = _jload(d.get("request_json"), {})
            d["result"] = _jload(d.get("result_json"), {})
            d["checks"] = _jload(d.get("checks_json"), [])
            out.append(d)
        return out

    # ---- submissions ----
    def save_submission(self, sub: dict[str, Any]) -> None:
        """保存一条提交记录（幂等，按 id 覆盖；供 ACTIVE 回查）。"""
        self._conn.execute(
            "INSERT OR REPLACE INTO submissions "
            "(id, alpha_id, submitted_at, user_confirmed, platform_response, current_status, confirmed_active) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                sub.get("id"),
                sub.get("alpha_id"),
                sub.get("submitted_at", _now()),
                1 if sub.get("user_confirmed") else 0,
                json.dumps(sub.get("platform_response", {}), ensure_ascii=False),
                sub.get("current_status"),
                1 if sub.get("confirmed_active") else 0,
            ),
        )
        self._conn.commit()

    # ---- lessons / failures ----
    def save_lesson(self, lesson: dict[str, Any]) -> None:
        """保存一条经验教训（幂等，脱敏后写入 playbook 的数据源）。"""
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

    def save_failure(self, failure: dict[str, Any]) -> None:
        """保存一条证伪记录（幂等；记录已证伪路径，避免重复走死路）。"""
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

    def failure_stats(
        self, limit: int = 20, category: str | None = None
    ) -> list[dict[str, Any]]:
        """按失败名归因统计（failures 表），供 qa report「失败归因」小节。

        category 按 failures.id 前缀区分失败类别（阶段 6 归因分离——修复路径不同：
        模拟失败→优化表达式，提交被拒→避开饱和簇）：
          "sim" → 模拟类（id 非 corr_/sub_ 前缀：预检未过/模拟未过）；
          "sub" → 提交类（id 为 corr_/sub_ 前缀：相关门被拒/提交被拒/提交失败）；
          None → 全部（不按类别过滤）。

        单条 failure_reason 可含多个失败名（如平台检查列表
        ['LOW_SHARPE','HIGH_TURNOVER'] 或 ';' 连接），逐名展开计数；
        提取不到拉丁字母标识符的按原样计数（如"提交失败: 404"）。
        返回 [{reason, count}] 按 count 降序（同数按名字典序），limit 截断。
        """
        rows = self._conn.execute("SELECT id, failure_reason FROM failures").fetchall()
        counter: Counter[str] = Counter()
        for r in rows:
            rid = r["id"] or ""
            if category == "sim" and (
                rid.startswith("corr_") or rid.startswith("sub_")
            ):
                continue
            if category == "sub" and not (
                rid.startswith("corr_") or rid.startswith("sub_")
            ):
                continue
            reason = (r["failure_reason"] or "").strip()
            if not reason:
                continue
            names = [
                m.group(0).upper()
                for m in re.finditer(r"[A-Za-z][A-Za-z_0-9]*", reason)
            ]
            counter.update(names if names else [reason])
        stats = [
            {"reason": name, "count": n}
            for name, n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
        ]
        if limit:
            stats = stats[:limit]
        return stats

    # ---- audit ----
    def append_audit(self, kind: str, payload: dict[str, Any]) -> str:
        """追加一行 JSONL 审计日志（不可变；模拟/提交等关键动作全记录）。

        返回该行的 UTC 时间戳，供 simulations.audit_path 关联定位。
        """
        ts = _now()
        with open(self.audit_path, "a", encoding="utf-8") as f:
            f.write(
                json.dumps({"ts": ts, "kind": kind, **payload}, ensure_ascii=False)
                + "\n"
            )
        return ts
