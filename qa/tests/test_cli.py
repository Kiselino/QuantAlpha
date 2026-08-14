"""cli 单测：命令分发 + status/run 端到端（mock 阶段检测与模拟）。"""

from __future__ import annotations

import pytest

from qa import cli


def test_main_unknown_command():
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["frobnicate"])
    assert excinfo.value.code == 2


def test_main_status_missing_cookie(tmp_qa, monkeypatch, capsys):
    import qa.cli as cli_mod

    monkeypatch.setattr(
        cli_mod,
        "QaPaths",
        lambda *a, **k: __import__("qa.paths", fromlist=["QaPaths"]).QaPaths(tmp_qa),
    )
    rc = cli.main(["status"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "cookie" in out.lower()


def test_cmd_run_end_to_end(tmp_qa, monkeypatch, capsys):
    """qa run 端到端：读候选→预检→模拟(mock)→筛选→报告。"""
    from qa.candidates import Candidate, write_candidates
    from qa.paths import QaPaths
    from qa.brain_client import SimulationResult
    from qa.screener import apply_thresholds
    import qa.cli as cli_mod

    paths = QaPaths(tmp_qa)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    write_candidates(
        cand_path,
        [
            Candidate(
                description="价格动量",
                hypothesis="近期涨幅延续",
                expression="rank(ts_delta(close, 5))",
                dataset_ids=["pv1"],
            ),
            Candidate(
                description="幻觉字段",
                hypothesis="x",
                expression="rank(foobar123)",
                dataset_ids=["pv1"],
            ),
        ],
    )
    # 写 cookie（阶段检测 mock 需要）
    paths.COOKIE.write_text("t=abc", encoding="utf-8")

    cfg = cli_mod.AppConfig()

    # mock stage 检测（不真调 API）
    from qa.stage import StageInfo

    monkeypatch.setattr(
        cli_mod, "get_stage", lambda p: StageInfo(level="TEST", is_consultant=False)
    )

    # mock BrainClient：模拟→轮询返回固定结果
    def fake_poll(self, sim_id, max_wait=600.0):
        return SimulationResult(
            sim_id=sim_id,
            status="COMPLETED",
            alpha_id="a1",
            checks=[{"name": "SHARPE", "result": "PASS", "limit": 1.25, "value": 1.5}],
            metrics={"sharpe": 1.5, "fitness": 1.2, "turnover": 0.2, "returns": 0.05},
        )

    monkeypatch.setattr(cli_mod.BrainClient, "poll_simulation", fake_poll)
    monkeypatch.setattr(cli_mod.BrainClient, "simulate", lambda self, c, s: f"sim_{c[:8]}")

    rc = cli_mod.cmd_run(paths, cfg, candidates_file=str(cand_path), idea=None)
    out = capsys.readouterr().out

    assert rc == 0
    assert "读入 2 个候选" in out
    assert "预检未过" in out          # 幻觉字段被拦截
    assert "PASS" in out              # 合法候选通过
    assert "完成" in out

    # 每日汇总已写入
    daily = paths.REPORTS_DIR / "daily" / "2026-08-14.md"
    assert daily.exists()


def test_cmd_submit_end_to_end(tmp_qa, monkeypatch, capsys):
    """qa submit 端到端：展示检查 → 交互确认 → 提交 → 回查 ACTIVE。"""
    from qa.candidates import Candidate, write_candidates
    from qa.paths import QaPaths
    from qa.store import Store
    from qa.validate import expression_hash
    import qa.cli as cli_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    store = Store(paths.DB)

    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    expr = "group_rank(ts_rank(close, 60), subindustry)"
    write_candidates(
        cand_path,
        [Candidate(description="动量测试", hypothesis="h", expression=expr, dataset_ids=["pv1"])],
    )
    h = expression_hash(expr)
    store.save_alpha(
        {"id": h, "expression": expr, "description": "动量测试",
         "hypothesis": "h", "dataset_ids": ["pv1"], "ast_hash": h,
         "metrics": {"sharpe": 1.68, "fitness": 1.05, "turnover": 0.046},
         "status": "COMPLETE"}
    )
    store.save_simulation(
        {"id": f"sim_{h}", "alpha_id": h,
         "result": {"regular": expr, "alpha": "PLATFORM_A1"},
         "status": "COMPLETE",
         "checks": [{"name": "LOW_SHARPE", "result": "PASS", "value": 1.68}]}
    )

    monkeypatch.setattr(cli_mod, "get_stage", lambda p: None)  # 不触发阶段检测
    monkeypatch.setattr(cli_mod.BrainClient, "correlations_self", lambda self, aid: 0.12)
    monkeypatch.setattr(cli_mod.BrainClient, "submit", lambda self, aid: {"status": "SUBMITTED"})
    monkeypatch.setattr(cli_mod.BrainClient, "get_alpha", lambda self, aid: {"status": "ACTIVE"})

    rc = cli_mod._cmd_submit(paths, h, yes=True)
    out = capsys.readouterr().out

    assert rc == 0
    assert "平台检查" in out
    assert "相关门" in out
    assert "ACTIVE" in out

    subs = store._conn.execute("SELECT * FROM submissions").fetchall()
    assert len(subs) == 1
    assert subs[0]["confirmed_active"] == 1
    updated = store.list_alphas()
    assert updated[0]["status"] == "SUBMITTED"


def test_cmd_reset_clears_experience_keeps_credentials(tmp_qa, monkeypatch, capsys):
    """qa reset：清除经验数据，保留 cookie/账号/知识库。"""
    from qa.paths import QaPaths
    from qa.store import Store
    import qa.cli as cli_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.parent.mkdir(parents=True, exist_ok=True)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    paths.CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    (paths.CANDIDATES_DIR / "x.json").write_text("[]", encoding="utf-8")
    (paths.REPORTS_DIR / "daily").mkdir(parents=True, exist_ok=True)
    (paths.REPORTS_DIR / "daily" / "2026-08-14.md").write_text("# x", encoding="utf-8")
    pending = paths.COOKIE.parent / "pending_submits.json"
    pending.write_text('{"pending": []}', encoding="utf-8")
    s = Store(paths.DB)
    s.save_alpha({"id": "a1", "expression": "rank(close)", "ast_hash": "h1",
                  "status": "COMPLETE"})
    s.save_lesson({"id": "l1", "trigger": "x", "lesson": "y"})

    rc = cli_mod._cmd_reset(paths, yes=True)
    out = capsys.readouterr().out

    assert rc == 0
    assert not paths.DB.exists()          # qa.db 已删
    assert not paths.CANDIDATES_DIR.exists() or not list(paths.CANDIDATES_DIR.glob("*"))
    assert not list((paths.REPORTS_DIR / "daily").glob("*"))
    assert not pending.exists()           # 待提交暂存已删
    assert paths.COOKIE.exists()          # cookie 保留
    assert "保留" in out
