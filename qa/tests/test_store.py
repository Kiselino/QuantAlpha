"""store 单测：SQLite CRUD + 幂等 + JSONL 审计。"""

from __future__ import annotations

from qa.paths import QaPaths
from qa.store import Store


def test_save_and_list_alpha(tmp_qa):
    s = Store(QaPaths(tmp_qa).DB)
    alpha = {
        "id": "a1",
        "expression": "rank(close)",
        "description": "test",
        "hypothesis": "h",
        "dataset_ids": ["pv1"],
        "ast_hash": "abc123",
        "status": "DRAFT",
        "grade": None,
    }
    s.save_alpha(alpha)
    rows = s.list_alphas()
    assert len(rows) == 1
    assert rows[0]["expression"] == "rank(close)"


def test_alpha_hash_exists(tmp_qa):
    s = Store(QaPaths(tmp_qa).DB)
    s.save_alpha({"id": "a1", "expression": "x", "ast_hash": "h1", "status": "DRAFT"})
    assert s.alpha_hash_exists("h1") is True
    assert s.alpha_hash_exists("nope") is False


def test_save_simulation(tmp_qa):
    s = Store(QaPaths(tmp_qa).DB)
    s.save_simulation({"id": "s1", "alpha_id": "a1", "status": "COMPLETED"})
    sims = s.list_simulations("a1")
    assert len(sims) == 1
    assert sims[0]["status"] == "COMPLETED"


def test_lessons_and_failures(tmp_qa):
    s = Store(QaPaths(tmp_qa).DB)
    s.save_lesson({"id": "l1", "trigger": "LOW_SHARPE", "lesson": "x"})
    s.save_failure({"id": "f1", "expression_hash": "h1", "failure_reason": "syntax"})
    assert len(s.list_failures()) == 1


def test_audit_jsonl(tmp_qa):
    s = Store(QaPaths(tmp_qa).DB)
    s.append_audit("sim", {"id": "s1"})
    log = QaPaths(tmp_qa).AUDIT_DIR / "audit.jsonl"
    assert log.exists()
    assert "sim" in log.read_text(encoding="utf-8")
