"""store 单测：SQLite CRUD + 幂等 + JSONL 审计 + 模拟续查记录。"""

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


def test_sim_failure_exists(tmp_qa):
    """防重：simulations 表已有 ERROR/FAILED 终态 → 不重复模拟；PENDING 仍可续查。"""
    s = Store(QaPaths(tmp_qa).DB)
    assert s.sim_failure_exists("h1") is False
    s.save_simulation({"id": "sim123", "alpha_id": "h1", "status": "PENDING"})
    assert s.sim_failure_exists("h1") is False  # PENDING 是续查对象，不防重
    s.save_simulation({"id": "sim123", "alpha_id": "h1", "status": "ERROR"})
    assert s.sim_failure_exists("h1") is True
    s.save_simulation({"id": "sim124", "alpha_id": "h2", "status": "FAILED"})
    assert s.sim_failure_exists("h2") is True
    s.save_simulation({"id": "sim125", "alpha_id": "h3", "status": "COMPLETE"})
    assert s.sim_failure_exists("h3") is False  # 终态成功由 alphas 表防重


def test_save_simulation(tmp_qa):
    s = Store(QaPaths(tmp_qa).DB)
    s.save_simulation({"id": "s1", "alpha_id": "a1", "status": "COMPLETED"})
    sims = s.list_simulations("a1")
    assert len(sims) == 1
    assert sims[0]["status"] == "COMPLETED"


def test_save_simulation_pending_then_final_same_row(tmp_qa):
    """同一条模拟 PENDING → 终态：同 id 覆盖，started_at 保留首次发起时间。"""
    from datetime import datetime

    s = Store(QaPaths(tmp_qa).DB)
    s.save_simulation(
        {
            "id": "sim123",
            "alpha_id": "h1",
            "status": "PENDING",
            "request": {"regular": "rank(close)"},
        }
    )
    first_started = s.list_simulations("h1")[0]["started_at"]
    s.save_simulation(
        {
            "id": "sim123",
            "alpha_id": "h1",
            "status": "COMPLETE",
            "result": {"alpha": "A1"},
            "finished_at": datetime.now().isoformat(),
        }
    )
    rows = s.list_simulations("h1")
    assert len(rows) == 1
    assert rows[0]["status"] == "COMPLETE"
    assert rows[0]["result"].get("alpha") == "A1"
    assert rows[0]["started_at"] == first_started  # 不覆盖首次发起时间


def test_find_pending_sim_id_and_delete(tmp_qa):
    """续查查询：PENDING/TIMEOUT 记录返回 id 供 poll 续查；删除后不再命中。"""
    s = Store(QaPaths(tmp_qa).DB)
    assert s.find_pending_sim_id("h1") is None
    s.save_simulation({"id": "sim123", "alpha_id": "h1", "status": "PENDING"})
    assert s.find_pending_sim_id("h1") == "sim123"
    # 终态不再续查
    s.save_simulation({"id": "sim123", "alpha_id": "h1", "status": "COMPLETE"})
    assert s.find_pending_sim_id("h1") is None
    # 超时仍可续查
    s.save_simulation({"id": "sim456", "alpha_id": "h1", "status": "TIMEOUT"})
    assert s.find_pending_sim_id("h1") == "sim456"
    s.delete_simulation("sim456")
    assert s.find_pending_sim_id("h1") is None
    # 任意非空 id 的 PENDING 都返回（若平台已清理，run 层 404 后删除重提，自愈）
    s.save_simulation({"id": "sim_old", "alpha_id": "h2", "status": "PENDING"})
    assert s.find_pending_sim_id("h2") == "sim_old"
    assert s.find_pending_sim_id("h3") is None


def test_lessons_and_failures(tmp_qa):
    s = Store(QaPaths(tmp_qa).DB)
    s.save_lesson({"id": "l1", "trigger": "LOW_SHARPE", "lesson": "x"})
    s.save_failure({"id": "f1", "expression_hash": "h1", "failure_reason": "syntax"})
    rows = s._conn.execute("SELECT * FROM failures").fetchall()
    assert len(rows) == 1


def test_failure_stats_expands_multi_reason_and_sorts(tmp_qa):
    """阶段 5：失败归因按失败名展开计数，count 降序（同数按名字典序）。"""
    s = Store(QaPaths(tmp_qa).DB)
    s.save_failure(
        {
            "id": "f1",
            "expression_hash": "h1",
            "failure_reason": "模拟未过: 平台检查未过: ['LOW_SHARPE', 'HIGH_TURNOVER']",
        }
    )
    s.save_failure(
        {
            "id": "f2",
            "expression_hash": "h2",
            "failure_reason": "模拟未过: 平台检查未过: ['LOW_SHARPE']",
        }
    )
    s.save_failure(
        {
            "id": "f3",
            "expression_hash": "h3",
            "failure_reason": "模拟未过: Sharpe 0.80 < 1.25",
        }
    )
    stats = s.failure_stats()
    assert [st["reason"] for st in stats] == ["LOW_SHARPE", "HIGH_TURNOVER", "SHARPE"]
    assert stats[0]["count"] == 2
    assert stats[1]["count"] == 1


def test_failure_stats_limit_and_raw_fallback(tmp_qa):
    """limit 截断；无拉丁标识符的原因按原样计数。"""
    s = Store(QaPaths(tmp_qa).DB)
    for i in range(5):
        s.save_failure(
            {
                "id": f"f{i}",
                "expression_hash": f"h{i}",
                "failure_reason": f"模拟未过: 平台检查未过: ['LOW_SHARPE', 'F_{i}']",
            }
        )
    s.save_failure(
        {"id": "fx", "expression_hash": "hx", "failure_reason": "提交失败: 404"}
    )
    stats = s.failure_stats(limit=3)
    assert len(stats) == 3
    assert stats[0] == {"reason": "LOW_SHARPE", "count": 5}
    raw = [st for st in s.failure_stats() if st["reason"] == "提交失败: 404"]
    assert raw == [{"reason": "提交失败: 404", "count": 1}]


def test_failure_stats_category_split(tmp_qa):
    """阶段 6：模拟类（f_ 前缀）与提交类（corr_/sub_ 前缀）归因分开统计。"""
    s = Store(QaPaths(tmp_qa).DB)
    s.save_failure(
        {
            "id": "f_sim1",
            "expression_hash": "h1",
            "failure_reason": "模拟未过: 平台检查未过: ['LOW_SHARPE']",
        }
    )
    s.save_failure(
        {
            "id": "corr_h2",
            "expression_hash": "h2",
            "failure_reason": "提交前相关门未过: max_corr=0.80≥0.7（与现有组合饱和）",
        }
    )
    s.save_failure(
        {
            "id": "sub_h2",
            "expression_hash": "h2",
            "failure_reason": "提交检查未过: LOW_FITNESS",
        }
    )
    sim_stats = s.failure_stats(category="sim")
    assert [st["reason"] for st in sim_stats] == ["LOW_SHARPE"]
    sub_stats = s.failure_stats(category="sub")
    assert {st["reason"] for st in sub_stats} == {"MAX_CORR", "LOW_FITNESS"}
    # 默认不过滤：三条全计入
    assert {st["reason"] for st in s.failure_stats()} == {
        "LOW_SHARPE",
        "MAX_CORR",
        "LOW_FITNESS",
    }


def test_list_falls_back_on_corrupt_json_fields(tmp_qa):
    """DB 中损坏的 JSON 字段 → list_* 回落默认值，不抛 JSONDecodeError。"""
    s = Store(QaPaths(tmp_qa).DB)
    s.save_alpha(
        {"id": "a1", "expression": "rank(close)", "ast_hash": "h1", "status": "DRAFT"}
    )
    s._conn.execute("UPDATE alphas SET metrics_json = '{broken' WHERE id = 'a1'")
    s.save_simulation({"id": "sim1", "alpha_id": "h1", "status": "PENDING"})
    s._conn.execute("UPDATE simulations SET result_json = '{broken' WHERE id = 'sim1'")
    s._conn.commit()
    alpha = s.list_alphas()[0]
    assert alpha["metrics"] == {}  # 损坏回落默认值
    sim = s.list_simulations("h1")[0]
    assert sim["result"] == {}


def test_audit_jsonl(tmp_qa):
    s = Store(QaPaths(tmp_qa).DB)
    s.append_audit("sim", {"id": "s1"})
    log = QaPaths(tmp_qa).AUDIT_DIR / "audit.jsonl"
    assert log.exists()
    assert "sim" in log.read_text(encoding="utf-8")
