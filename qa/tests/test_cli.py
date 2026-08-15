"""cli 单测：命令分发 + status/run 端到端（mock 阶段检测与模拟）。"""

from __future__ import annotations

import json

import pytest

from qa import cli


def _seed_knowledge(paths) -> None:
    """写最小本地知识库（fields.json + top_fields.json + meta.json）。"""
    paths.KNOWLEDGE_FIELDS_DIR.mkdir(parents=True, exist_ok=True)
    fields = [
        {"id": "close", "description": "close", "dataset": "pv1",
         "type": "MATRIX", "coverage": 1.0, "userCount": 100},
        {"id": "volume", "description": "volume", "dataset": "pv1",
         "type": "MATRIX", "coverage": 1.0, "userCount": 50},
        {"id": "subindustry", "description": "subindustry", "dataset": "grp",
         "type": "GROUP", "coverage": 1.0, "userCount": 200},
        {"id": "nws_x", "description": "news vector", "dataset": "news12",
         "type": "VECTOR", "coverage": 1.0, "userCount": 30},
        {"id": "top500", "description": "universe member", "dataset": "univ1",
         "type": "UNIVERSE", "coverage": 1.0, "userCount": 999},
    ]
    paths.KNOWLEDGE_FIELDS_JSON.write_text(
        json.dumps(fields, ensure_ascii=False), encoding="utf-8"
    )
    paths.KNOWLEDGE_TOP_FIELDS_JSON.write_text(
        json.dumps(fields, ensure_ascii=False), encoding="utf-8"
    )
    paths.KNOWLEDGE_META_JSON.write_text(
        json.dumps({"field_count": len(fields), "dataset_count": 4,
                    "regions": ["USA"], "generated_at": "2026-08-15T00:00:00+00:00"}),
        encoding="utf-8",
    )


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
    # 本地知识库（v1.4：字段白名单改读 experience/）
    _seed_knowledge(paths)

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

    # 每日汇总已写入（按当天日期命名）
    from datetime import datetime

    daily = paths.REPORTS_DIR / "daily" / f"{datetime.now().strftime('%Y-%m-%d')}.md"
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


def test_cmd_run_missing_knowledge_errors(tmp_qa, monkeypatch, capsys):
    """v1.4：未生成本地知识库时 qa run 拒绝执行并提示 update-knowledge。"""
    from qa.candidates import Candidate, write_candidates
    from qa.paths import QaPaths
    import qa.cli as cli_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    write_candidates(cand_path, [Candidate(description="x", expression="rank(close)")])
    monkeypatch.setattr(cli_mod, "get_stage", lambda p: None)

    rc = cli_mod.cmd_run(paths, cli_mod.AppConfig(), str(cand_path), idea=None)
    out = capsys.readouterr().out

    assert rc == 1
    assert "update-knowledge" in out


def test_cmd_run_rejects_vector_field_via_type_check(tmp_qa, monkeypatch, capsys):
    """v1.4.1：VECTOR 字段未用 vec_* 转换 → 预检拦截（省无效模拟配额）。"""
    from qa.candidates import Candidate, write_candidates
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    import qa.cli as cli_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    write_candidates(
        cand_path,
        [
            Candidate(description="合法标量", hypothesis="h",
                      expression="rank(close)", dataset_ids=["pv1"]),
            Candidate(description="VECTOR 误用", hypothesis="h",
                      expression="rank(nws_x)", dataset_ids=["news12"]),
        ],
    )
    monkeypatch.setattr(
        cli_mod, "get_stage",
        lambda p: StageInfo(level="TEST", is_consultant=False),
    )
    monkeypatch.setattr(
        cli_mod.BrainClient, "simulate", lambda self, c, s: f"sim_{c[:8]}"
    )
    monkeypatch.setattr(
        cli_mod.BrainClient, "poll_simulation",
        lambda self, sid, max_wait=600.0: cli_mod.SimulationResult(
            sim_id=sid, status="COMPLETED", alpha_id="a1", checks=[],
            metrics={"sharpe": 1.5, "fitness": 1.1, "turnover": 0.2},
        ),
    )

    rc = cli_mod.cmd_run(paths, cli_mod.AppConfig(), str(cand_path), idea=None)
    out = capsys.readouterr().out

    assert rc == 0
    assert "VECTOR" in out          # 类型检查拦截提示
    assert "待模拟" in out and out.count("待模拟") == 1  # 只模拟合法候选
    assert "PASS" in out


def test_cmd_run_auto_sediments_lessons_and_failures(tmp_qa, monkeypatch, capsys):
    """v1.4：run 后 PASS→lessons、FAIL→failures 自动写入 SQLite + experience/。"""
    from qa.candidates import Candidate, write_candidates
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.brain_client import SimulationResult
    from qa.store import Store
    import qa.cli as cli_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    write_candidates(
        cand_path,
        [
            Candidate(description="有效动量", hypothesis="动量延续",
                      expression="rank(ts_delta(close, 5))", dataset_ids=["pv1"]),
            Candidate(description="低夏普失败", hypothesis="弱信号",
                      expression="rank(close)", dataset_ids=["pv1"]),
        ],
    )
    monkeypatch.setattr(
        cli_mod, "get_stage", lambda p: StageInfo(level="TEST", is_consultant=False)
    )

    def fake_poll(self, sim_id, max_wait=600.0):
        sharpe = 1.5 if "ts_" in sim_id else 0.8
        return SimulationResult(
            sim_id=sim_id, status="COMPLETED", alpha_id="a1",
            checks=[{"name": "SHARPE", "result": "PASS" if sharpe > 1.0 else "FAIL",
                     "value": sharpe}],
            metrics={"sharpe": sharpe, "fitness": 1.1, "turnover": 0.2},
        )

    monkeypatch.setattr(cli_mod.BrainClient, "poll_simulation", fake_poll)
    monkeypatch.setattr(cli_mod.BrainClient, "simulate", lambda self, c, s: f"sim_{c[:8]}")

    rc = cli_mod.cmd_run(paths, cli_mod.AppConfig(), str(cand_path), idea=None)
    assert rc == 0

    store = Store(paths.DB)
    lessons = store._conn.execute("SELECT * FROM lessons").fetchall()
    failures = store._conn.execute("SELECT * FROM failures").fetchall()
    assert len(lessons) == 1
    assert len(failures) == 1
    assert "有效动量" in paths.PLAYBOOK.read_text(encoding="utf-8")
    assert "低夏普失败" in paths.FAILURES.read_text(encoding="utf-8")


def test_cmd_update_knowledge_end_to_end(tmp_qa, monkeypatch, capsys):
    """v1.4：qa update-knowledge 按账户区域抓字段 → 写 experience/（mock API）。"""
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    import qa.cli as cli_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    monkeypatch.setattr(
        cli_mod, "get_stage",
        lambda p: StageInfo(level="BRONZE", is_consultant=False, regions=["USA"]),
    )

    def fake_get_json(self, path, params=None):
        if path == "/data-sets":
            return {"results": [{"id": "pv1"}], "count": 1}
        if path == "/data-fields":
            return {"results": [{"id": "close", "description": "c",
                                 "type": "MATRIX", "coverage": 1.0, "userCount": 10}],
                    "count": 1}
        raise AssertionError(path)

    monkeypatch.setattr(cli_mod.BrainClient, "get_json", fake_get_json)

    rc = cli_mod.cmd_update_knowledge(paths, regions_arg=None, pace=0.0)
    out = capsys.readouterr().out

    assert rc == 0
    assert "完成" in out and "1 字段" in out
    assert paths.KNOWLEDGE_FIELDS_JSON.exists()
    assert "close" in paths.KNOWLEDGE_FIELDS_JSON.read_text(encoding="utf-8")
    assert paths.PLAYBOOK.exists()  # 模板随构建创建


def test_cmd_suggest_requires_and_uses_knowledge(tmp_qa, monkeypatch, capsys):
    """v1.4：qa suggest 无知识库报错；有知识库输出随机研究方向。"""
    from qa.paths import QaPaths
    import qa.cli as cli_mod

    paths = QaPaths(tmp_qa)
    assert cli_mod.cmd_suggest(paths) == 1

    _seed_knowledge(paths)
    rc = cli_mod.cmd_suggest(paths)
    out = capsys.readouterr().out
    assert rc == 0
    assert "建议研究方向" in out
    assert any(f in out for f in ("close", "volume", "subindustry"))


def test_signal_fields_filters_unusable_types():
    """v1.4.1：suggest 排除 UNIVERSE/SYMBOL/VECTOR 字段（不可用于标量表达式）。"""
    from qa import cli as cli_mod
    from qa.paths import QaPaths
    import tempfile
    from pathlib import Path

    paths = QaPaths(Path(tempfile.mkdtemp()))
    _seed_knowledge(paths)
    from qa import knowledge

    top = knowledge.load_top_fields(paths)
    signal = cli_mod._signal_fields(top)
    ids = {f["id"] for f in signal}
    assert "close" in ids
    assert "top500" not in ids    # UNIVERSE 排除
    assert "nws_x" not in ids     # VECTOR 排除
    assert "subindustry" in ids   # GROUP 保留（group_by 可用）


def test_cmd_run_respects_minute_rate_limit(tmp_qa, monkeypatch, capsys):
    """v1.4.1：分钟限流剩余不足时批间等待，不硬撞 429。"""
    from qa.candidates import Candidate, write_candidates
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.brain_client import RateLimits
    import qa.cli as cli_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    write_candidates(
        cand_path,
        [Candidate(description=f"c{i}", hypothesis="h",
                   expression="rank(close)", dataset_ids=["pv1"]) for i in range(4)],
    )
    monkeypatch.setattr(
        cli_mod, "get_stage",
        lambda p: StageInfo(level="TEST", is_consultant=False),
    )
    monkeypatch.setattr(
        cli_mod.BrainClient, "simulate", lambda self, c, s: f"sim_{c[:8]}"
    )
    monkeypatch.setattr(
        cli_mod.BrainClient, "poll_simulation",
        lambda self, sid, max_wait=600.0: cli_mod.SimulationResult(
            sim_id=sid, status="COMPLETED", alpha_id="a1", checks=[],
            metrics={"sharpe": 1.5, "fitness": 1.1, "turnover": 0.2},
        ),
    )
    monkeypatch.setattr(
        cli_mod.BrainClient, "rate_limits",
        lambda self: RateLimits(remaining_minute=1, limit_minute=30),
    )
    sleeps: list[float] = []
    monkeypatch.setattr(cli_mod.time, "sleep", lambda s: sleeps.append(s))

    rc = cli_mod.cmd_run(paths, cli_mod.AppConfig(), str(cand_path), idea=None)
    out = capsys.readouterr().out

    assert rc == 0
    assert sleeps, "剩余 1 时应等待限流窗口重置"
    assert "限流" in out


def test_cmd_status_prompts_knowledge_generation(tmp_qa, monkeypatch, capsys):
    """v1.4：status 展示知识库状态，缺失时提示 update-knowledge。"""
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    import qa.cli as cli_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    monkeypatch.setattr(
        cli_mod, "get_stage",
        lambda p: StageInfo(level="BRONZE", is_consultant=False),
    )
    assert cli_mod.cmd_status(paths) == 0
    out = capsys.readouterr().out
    assert "update-knowledge" in out

    _seed_knowledge(paths)
    assert cli_mod.cmd_status(paths) == 0
    out = capsys.readouterr().out
    assert "字段" in out and "生成于" in out


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
    # 本地知识库：fields 保留、playbook/failures 恢复模板
    _seed_knowledge(paths)
    from qa import knowledge

    knowledge.append_experience(paths, "lesson", "h9", "某经验", "内容")
    knowledge.append_experience(paths, "failure", "h9", "某证伪", "内容")

    rc = cli_mod._cmd_reset(paths, yes=True)
    out = capsys.readouterr().out

    assert rc == 0
    assert not paths.DB.exists()          # qa.db 已删
    assert not paths.CANDIDATES_DIR.exists() or not list(paths.CANDIDATES_DIR.glob("*"))
    assert not list((paths.REPORTS_DIR / "daily").glob("*"))
    assert not pending.exists()           # 待提交暂存已删
    assert paths.COOKIE.exists()          # cookie 保留
    assert "某经验" not in paths.PLAYBOOK.read_text(encoding="utf-8")  # playbook 恢复模板
    assert "某证伪" not in paths.FAILURES.read_text(encoding="utf-8")
    assert paths.KNOWLEDGE_FIELDS_JSON.exists()  # 账户字段知识保留
    assert "保留" in out
