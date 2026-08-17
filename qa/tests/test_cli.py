"""cli 单测：命令分发 + status/run 端到端（mock 阶段检测与模拟）。"""

from __future__ import annotations

import json

import pytest

from qa import cli


def _dump_cands(path, cands) -> None:
    """测试辅助：把候选列表写成候选 JSON 文件（生产侧无写入 API）。"""
    from qa.candidates import Candidate

    path.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {
            "description": c.description,
            "hypothesis": c.hypothesis,
            "expression": c.expression,
            "dataset_ids": list(c.dataset_ids),
            "settings": c.settings,
            "language": c.language,
        }
        for c in cands
        if isinstance(c, Candidate)
    ]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _seed_knowledge(paths) -> None:
    """写最小本地知识库（fields.json + top_fields.json + meta.json）。"""
    paths.KNOWLEDGE_FIELDS_DIR.mkdir(parents=True, exist_ok=True)
    fields = [
        {
            "id": "close",
            "description": "close",
            "dataset": "pv1",
            "type": "MATRIX",
            "coverage": 1.0,
            "userCount": 100,
        },
        {
            "id": "volume",
            "description": "volume",
            "dataset": "pv1",
            "type": "MATRIX",
            "coverage": 1.0,
            "userCount": 50,
        },
        {
            "id": "subindustry",
            "description": "subindustry",
            "dataset": "grp",
            "type": "GROUP",
            "coverage": 1.0,
            "userCount": 200,
        },
        {
            "id": "nws_x",
            "description": "news vector",
            "dataset": "news12",
            "type": "VECTOR",
            "coverage": 1.0,
            "userCount": 30,
        },
        {
            "id": "top500",
            "description": "universe member",
            "dataset": "univ1",
            "type": "UNIVERSE",
            "coverage": 1.0,
            "userCount": 999,
        },
    ]
    paths.KNOWLEDGE_FIELDS_JSON.write_text(
        json.dumps(fields, ensure_ascii=False), encoding="utf-8"
    )
    paths.KNOWLEDGE_TOP_FIELDS_JSON.write_text(
        json.dumps(fields, ensure_ascii=False), encoding="utf-8"
    )
    paths.KNOWLEDGE_META_JSON.write_text(
        json.dumps(
            {
                "field_count": len(fields),
                "dataset_count": 4,
                "regions": ["USA"],
                "generated_at": "2026-08-15T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )


def test_main_unknown_command():
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["frobnicate"])
    assert excinfo.value.code == 2


def test_settings_merge_candidate_overrides():
    from qa.commands import run as run_mod

    cfg = run_mod.AppConfig()
    base = run_mod._settings(cfg)
    assert base["decay"] == 0
    merged = run_mod._settings(
        cfg, {"decay": 12, "neutralization": "SECTOR", "truncation": 0.05}
    )
    assert merged["decay"] == 12
    assert merged["neutralization"] == "SECTOR"
    assert abs(float(merged["truncation"]) - 0.05) < 1e-9
    assert merged["region"] == "USA"  # 未覆盖的键保持全局默认
    # 未知键被忽略（值域校验由 validate 负责）
    assert run_mod._settings(cfg, {"hump": 1}) == base


def test_append_pending_idempotent(tmp_qa):
    from qa.commands import _common as common_mod
    from qa.paths import QaPaths

    paths = QaPaths(tmp_qa)
    common_mod._append_pending(paths, {"id": "h1", "description": "d1"})
    common_mod._append_pending(
        paths, {"id": "h1", "description": "d1"}
    )  # 幂等：同 id 不重复
    common_mod._append_pending(paths, {"id": "h2", "description": "d2"})
    data = json.loads(paths.PENDING_SUBMITS.read_text(encoding="utf-8"))
    assert [e["id"] for e in data] == ["h1", "h2"]


def test_run_settings_pending_corr_ranking(tmp_qa, monkeypatch, capsys):
    """候选级 settings 合并 + PASS 后相关门排序 + pending 暂存写入。"""
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.brain_client import RateLimits, SimulationResult
    from qa.validate import expression_hash
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
        cand_path,
        [
            Candidate(
                description="技术动量",
                hypothesis="h",
                expression="rank(ts_delta(close, 5))",
                dataset_ids=["pv1"],
                settings={"decay": 12},
            ),
            Candidate(
                description="量能",
                hypothesis="h",
                expression="rank(ts_mean(volume, 5))",
                dataset_ids=["pv1"],
            ),
        ],
    )
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    cfg = run_mod.AppConfig()

    from qa.stage import StageInfo

    monkeypatch.setattr(
        run_mod, "get_stage", lambda p: StageInfo(level="TEST", is_consultant=False)
    )

    captured_settings = []

    def fake_simulate(self, code, settings):
        captured_settings.append(settings)
        return f"sim_{expression_hash(code)}"

    def fake_poll(self, sim_id, max_wait=600.0):
        if sim_id == f"sim_{expression_hash('rank(ts_mean(volume, 5))')}":
            return SimulationResult(
                sim_id=sim_id,
                status="COMPLETED",
                alpha_id="a2",
                checks=[{"name": "SHARPE", "result": "PASS", "value": 1.6}],
                metrics={"sharpe": 1.6, "fitness": 1.2, "turnover": 0.2},
            )
        return SimulationResult(
            sim_id=sim_id,
            status="COMPLETED",
            alpha_id="a1",
            checks=[{"name": "SHARPE", "result": "PASS", "value": 1.5}],
            metrics={"sharpe": 1.5, "fitness": 1.2, "turnover": 0.2},
        )

    monkeypatch.setattr(run_mod.BrainClient, "simulate", fake_simulate)
    monkeypatch.setattr(
        run_mod.BrainClient,
        "rate_limits",
        lambda self: RateLimits(remaining_minute=30, limit_minute=30),
    )
    monkeypatch.setattr(run_mod.BrainClient, "poll_simulation", fake_poll)
    monkeypatch.setattr(
        run_mod.BrainClient,
        "correlations_self",
        lambda self, aid: {"a1": 0.6, "a2": 0.1}[aid],
    )

    rc = run_mod.cmd_run(paths, cfg, candidates_file=str(cand_path))
    out = capsys.readouterr().out

    assert rc == 0
    # 候选级 settings 合并：第一个 decay=12，第二个全局默认 0
    assert [s["decay"] for s in captured_settings] == [12, 0]
    # 相关门排序：corr 低的"量能"(0.1) 排在"技术动量"(0.6) 前
    assert out.index("量能") < out.index("技术动量")
    # 阶段 6：run 报告展示相关门排序值（标注提交前需复查，防误读）
    assert "相关门: 0.10（提交前需复查）" in out
    assert "相关门: 0.60（提交前需复查）" in out
    # PASS 候选已暂存待提交（含指标与相关门排序值，供 report --pending 展示）
    pending = json.loads(paths.PENDING_SUBMITS.read_text(encoding="utf-8"))
    assert {e["id"] for e in pending} == {
        expression_hash("rank(ts_delta(close, 5))"),
        expression_hash("rank(ts_mean(volume, 5))"),
    }
    pending_by_id = {e["id"]: e for e in pending}
    assert pending_by_id[expression_hash("rank(ts_mean(volume, 5))")]["corr"] == 0.1
    assert pending_by_id[expression_hash("rank(ts_delta(close, 5))")]["corr"] == 0.6
    assert "待提交" in out


def test_run_dedupe_same_field_set(tmp_qa, monkeypatch, capsys):
    """同字段集候选去重：只模拟最简者（省配额）。"""
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.brain_client import RateLimits, SimulationResult
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
        cand_path,
        [
            Candidate(
                description="动量5",
                hypothesis="h",
                expression="rank(ts_mean(close, 5))",
                dataset_ids=["pv1"],
            ),
            Candidate(
                description="动量20",
                hypothesis="h",
                expression="rank(ts_mean(close, 20))",
                dataset_ids=["pv1"],
            ),
            Candidate(
                description="量能",
                hypothesis="h",
                expression="rank(ts_mean(volume, 5))",
                dataset_ids=["pv1"],
            ),
        ],
    )
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    cfg = run_mod.AppConfig()

    from qa.stage import StageInfo

    monkeypatch.setattr(
        run_mod, "get_stage", lambda p: StageInfo(level="TEST", is_consultant=False)
    )
    simulated: list[str] = []

    def fake_simulate(self, code, settings):
        simulated.append(code)
        return f"sim_{len(simulated)}"

    def fake_poll(self, sim_id, max_wait=600.0):
        return SimulationResult(
            sim_id=sim_id,
            status="COMPLETED",
            alpha_id="a1",
            checks=[{"name": "SHARPE", "result": "PASS", "value": 1.5}],
            metrics={"sharpe": 1.5, "fitness": 1.2, "turnover": 0.2},
        )

    monkeypatch.setattr(run_mod.BrainClient, "simulate", fake_simulate)
    monkeypatch.setattr(
        run_mod.BrainClient,
        "rate_limits",
        lambda self: RateLimits(remaining_minute=30, limit_minute=30),
    )
    monkeypatch.setattr(run_mod.BrainClient, "poll_simulation", fake_poll)
    monkeypatch.setattr(run_mod.BrainClient, "correlations_self", lambda self, aid: 0.1)

    rc = run_mod.cmd_run(paths, cfg, candidates_file=str(cand_path))
    out = capsys.readouterr().out

    assert rc == 0
    assert len(simulated) == 2  # {close} 簇只模拟 1 个 + {volume} 1 个
    assert "同字段集" in out
    assert "rank(ts_mean(close, 20))" not in simulated  # 更复杂的被去重


def test_run_respects_platform_daily_remaining(tmp_qa, monkeypatch, capsys):
    """平台每日配额头存在时，run 预算取平台剩余（v1.6：纯平台头，无本地预算）。

    断言走入口首查 remaining=1 分支：todo 截断为 1 个，模拟只发起 1 次
    （非批间截断——批间截断场景由 test_run_stops_when_platform_daily_exhausted 覆盖）。
    """
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.brain_client import RateLimits
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
        cand_path,
        [
            Candidate(
                description="动量",
                hypothesis="h",
                expression="rank(close)",
                dataset_ids=["pv1"],
            ),
            Candidate(
                description="量能",
                hypothesis="h",
                expression="rank(volume)",
                dataset_ids=["pv1"],
            ),
        ],
    )
    monkeypatch.setattr(
        run_mod, "get_stage", lambda p: StageInfo(level="TEST", is_consultant=False)
    )
    simulated: list[str] = []

    def fake_simulate(self, code, settings):
        simulated.append(code)
        return f"sim_{len(simulated)}"

    def fake_poll(self, sim_id, max_wait=600.0):
        return run_mod.SimulationResult(
            sim_id=sim_id,
            status="COMPLETED",
            alpha_id="a1",
            checks=[],
            metrics={"sharpe": 1.5, "fitness": 1.1, "turnover": 0.2},
        )

    monkeypatch.setattr(run_mod.BrainClient, "simulate", fake_simulate)
    monkeypatch.setattr(run_mod.BrainClient, "poll_simulation", fake_poll)
    monkeypatch.setattr(
        run_mod.BrainClient,
        "rate_limits",
        lambda self: RateLimits(
            remaining_minute=30, limit_minute=30, daily_remaining=1, daily_limit=2000
        ),
    )

    rc = run_mod.cmd_run(paths, run_mod.AppConfig(), str(cand_path))
    out = capsys.readouterr().out
    assert rc == 0
    assert len(simulated) == 1  # 平台只剩 1 次
    assert "平台每日" in out


def test_run_stops_when_platform_daily_exhausted(tmp_qa, monkeypatch, capsys):
    """主线程 rate_limits 读到的平台每日配额耗尽时，run 提前停止不再开新批。"""
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.brain_client import RateLimits
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
        cand_path,
        [
            Candidate(
                description="a",
                hypothesis="h",
                expression="rank(close)",
                dataset_ids=["pv1"],
            ),
            Candidate(
                description="b",
                hypothesis="h",
                expression="rank(volume)",
                dataset_ids=["pv1"],
            ),
            Candidate(
                description="c",
                hypothesis="h",
                expression="group_rank(rank(close), subindustry)",
                dataset_ids=["pv1"],
            ),
            Candidate(
                description="d",
                hypothesis="h",
                expression="vec_avg(nws_x)",
                dataset_ids=["pv1"],
            ),
        ],
    )
    monkeypatch.setattr(
        run_mod, "get_stage", lambda p: StageInfo(level="TEST", is_consultant=False)
    )
    # 入口首查正常；批间截断统一主线程读 rate_limits（v1.6 修并发竞态）——
    # 第二批前平台每日配额已耗尽（daily_remaining=0）
    rl_calls = {"n": 0}

    def fake_rate_limits(self):
        rl_calls["n"] += 1
        if rl_calls["n"] == 1:
            return RateLimits(remaining_minute=30, limit_minute=30)
        return RateLimits(remaining_minute=30, limit_minute=30, daily_remaining=0)

    monkeypatch.setattr(run_mod.BrainClient, "rate_limits", fake_rate_limits)
    simulated: list[str] = []

    def fake_simulate(self, code, settings):
        simulated.append(code)
        return f"sim_{len(simulated)}"

    def fake_poll(self, sim_id, max_wait=600.0):
        return run_mod.SimulationResult(
            sim_id=sim_id,
            status="COMPLETED",
            alpha_id="a1",
            checks=[],
            metrics={"sharpe": 1.5, "fitness": 1.1, "turnover": 0.2},
        )

    monkeypatch.setattr(run_mod.BrainClient, "simulate", fake_simulate)
    monkeypatch.setattr(run_mod.BrainClient, "poll_simulation", fake_poll)
    monkeypatch.setattr(run_mod.BrainClient, "correlations_self", lambda self, aid: 0.1)

    rc = run_mod.cmd_run(paths, run_mod.AppConfig(), str(cand_path))
    out = capsys.readouterr().out
    assert rc == 0
    assert len(simulated) == 3  # 第一批 3 个跑完，第二批被每日配额截断
    assert "每日模拟配额" in out


# ---- 阶段 4 模拟环节：纯平台头配额 / --concurrency / 中断恢复 ----


def test_run_platform_daily_missing_not_blocked(
    tmp_qa, monkeypatch, capsys, mock_brain
):
    """平台每日配额头缺失（None）时不拦截：照跑全部候选，靠平台错误码兜底。"""
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
        cand_path,
        [
            Candidate(
                description="动量",
                hypothesis="h",
                expression="rank(close)",
                dataset_ids=["pv1"],
            ),
            Candidate(
                description="量能",
                hypothesis="h",
                expression="rank(volume)",
                dataset_ids=["pv1"],
            ),
        ],
    )
    monkeypatch.setattr(
        run_mod, "get_stage", lambda p: StageInfo(level="TEST", is_consultant=False)
    )

    rc = run_mod.cmd_run(paths, run_mod.AppConfig(), str(cand_path))
    out = capsys.readouterr().out
    assert rc == 0
    assert len(mock_brain.simulated) == 2  # 无平台头照跑全部，不误拦截
    assert "配额" not in out  # 不出现截断/耗尽提示


def test_run_concurrency_priority(tmp_qa, monkeypatch, capsys):
    """并发优先级：显式 --concurrency > stage.max_concurrency > cfg 默认。"""
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.brain_client import RateLimits
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
        cand_path,
        [
            Candidate(
                description=f"c{i}",
                hypothesis="h",
                expression=expr,
                dataset_ids=["pv1"],
            )
            for i, expr in enumerate(
                [
                    "rank(close)",
                    "rank(volume)",
                    "group_rank(rank(close), subindustry)",
                    "vec_avg(nws_x)",
                    "group_rank(rank(volume), subindustry)",
                ]
            )
        ],
    )
    monkeypatch.setattr(
        run_mod,
        "get_stage",
        lambda p: StageInfo(level="TEST", is_consultant=False, max_concurrency=2),
    )
    monkeypatch.setattr(
        run_mod.BrainClient, "simulate", lambda self, c, s: f"sim_{c[:8]}"
    )
    monkeypatch.setattr(
        run_mod.BrainClient,
        "rate_limits",
        lambda self: RateLimits(remaining_minute=30, limit_minute=30),
    )
    monkeypatch.setattr(
        run_mod.BrainClient,
        "poll_simulation",
        lambda self, sid, max_wait=600.0: run_mod.SimulationResult(
            sim_id=sid,
            status="COMPLETED",
            alpha_id="a1",
            checks=[],
            metrics={"sharpe": 1.5, "fitness": 1.1, "turnover": 0.2},
        ),
    )
    monkeypatch.setattr(run_mod.BrainClient, "correlations_self", lambda self, aid: 0.1)

    # 显式参数优先：stage=2 被覆盖为 5
    rc = run_mod.cmd_run(paths, run_mod.AppConfig(), str(cand_path), concurrency=5)
    assert rc == 0
    assert "并发 5" in capsys.readouterr().out

    # 无显式参数：stage.max_concurrency 生效
    paths.DB.unlink()
    rc = run_mod.cmd_run(paths, run_mod.AppConfig(), str(cand_path))
    assert rc == 0
    assert "并发 2" in capsys.readouterr().out

    # stage.max_concurrency 为 0：回落 cfg 默认 3
    paths.DB.unlink()
    monkeypatch.setattr(
        run_mod,
        "get_stage",
        lambda p: StageInfo(level="TEST", is_consultant=False, max_concurrency=0),
    )
    rc = run_mod.cmd_run(paths, run_mod.AppConfig(), str(cand_path))
    assert rc == 0
    assert "并发 3" in capsys.readouterr().out


def test_cli_run_concurrency_arg(tmp_qa, monkeypatch):
    """cli 分发：--concurrency 透传给 run 命令（默认 None 走优先级链）。"""
    import qa.cli as cli_mod

    captured = {}

    def fake_main(paths, cfg, args):
        captured["concurrency"] = args.concurrency
        captured["candidates_file"] = args.candidates_file
        return 0

    monkeypatch.setattr(cli_mod.run, "main", fake_main)
    assert (
        cli_mod.main(["run", "--candidates-file", "x.json", "--concurrency", "5"]) == 0
    )
    assert captured["concurrency"] == 5
    assert captured["candidates_file"] == "x.json"

    assert cli_mod.main(["run"]) == 0
    assert captured["concurrency"] is None  # 默认 None → 走 stage/cfg 优先级


def test_run_resumes_pending_simulation(tmp_qa, monkeypatch, capsys):
    """中断恢复：存在 PENDING 平台 sim_id → 不重新 simulate，直接 poll 续查。"""
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.brain_client import RateLimits
    from qa.store import Store
    from qa.validate import expression_hash
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    expr = "rank(close)"
    h = expression_hash(expr)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
        cand_path,
        [
            Candidate(
                description="动量",
                hypothesis="h",
                expression=expr,
                dataset_ids=["pv1"],
            )
        ],
    )
    # 预置上次运行中断留下的 PENDING 记录（id=平台 sim_id）
    store = Store(paths.DB)
    store.save_simulation(
        {
            "id": "plat_sim_1",
            "alpha_id": h,
            "status": "PENDING",
            "request": {"regular": expr},
        }
    )
    monkeypatch.setattr(
        run_mod, "get_stage", lambda p: StageInfo(level="TEST", is_consultant=False)
    )

    def fake_simulate(self, code, settings):
        raise AssertionError("续查路径不应重新 simulate")

    polled: list[str] = []

    def fake_poll(self, sim_id, max_wait=600.0):
        polled.append(sim_id)
        return run_mod.SimulationResult(
            sim_id=sim_id,
            status="COMPLETED",
            alpha_id="a1",
            checks=[],
            metrics={"sharpe": 1.5, "fitness": 1.1, "turnover": 0.2},
        )

    monkeypatch.setattr(run_mod.BrainClient, "simulate", fake_simulate)
    monkeypatch.setattr(run_mod.BrainClient, "poll_simulation", fake_poll)
    monkeypatch.setattr(
        run_mod.BrainClient,
        "rate_limits",
        lambda self: RateLimits(remaining_minute=30, limit_minute=30),
    )
    monkeypatch.setattr(run_mod.BrainClient, "correlations_self", lambda self, aid: 0.1)

    rc = run_mod.cmd_run(paths, run_mod.AppConfig(), str(cand_path))
    out = capsys.readouterr().out
    assert rc == 0
    assert polled == ["plat_sim_1"]  # 直接续查平台 sim_id
    assert "PASS" in out
    # 同一条记录被更新为终态（仍以平台 sim_id 为主键）
    sims = store.list_simulations(h)
    assert len(sims) == 1
    assert sims[0]["id"] == "plat_sim_1"
    assert sims[0]["status"] == "COMPLETED"


def test_run_resume_fallback_on_404(tmp_qa, monkeypatch, capsys):
    """续查 404（平台已清理）→ 删旧记录回退重新 simulate。"""
    import requests as _requests

    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.brain_client import RateLimits
    from qa.store import Store
    from qa.validate import expression_hash
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    expr = "rank(close)"
    h = expression_hash(expr)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
        cand_path,
        [
            Candidate(
                description="动量",
                hypothesis="h",
                expression=expr,
                dataset_ids=["pv1"],
            )
        ],
    )
    store = Store(paths.DB)
    store.save_simulation(
        {
            "id": "stale_sim",
            "alpha_id": h,
            "status": "PENDING",
            "request": {"regular": expr},
        }
    )
    monkeypatch.setattr(
        run_mod, "get_stage", lambda p: StageInfo(level="TEST", is_consultant=False)
    )

    def fake_simulate(self, code, settings):
        return "fresh_sim_1"

    def fake_poll(self, sim_id, max_wait=600.0):
        if sim_id == "stale_sim":
            resp = _requests.Response()
            resp.status_code = 404
            raise _requests.exceptions.HTTPError(response=resp)
        return run_mod.SimulationResult(
            sim_id=sim_id,
            status="COMPLETED",
            alpha_id="a1",
            checks=[],
            metrics={"sharpe": 1.5, "fitness": 1.1, "turnover": 0.2},
        )

    monkeypatch.setattr(run_mod.BrainClient, "simulate", fake_simulate)
    monkeypatch.setattr(run_mod.BrainClient, "poll_simulation", fake_poll)
    monkeypatch.setattr(
        run_mod.BrainClient,
        "rate_limits",
        lambda self: RateLimits(remaining_minute=30, limit_minute=30),
    )
    monkeypatch.setattr(run_mod.BrainClient, "correlations_self", lambda self, aid: 0.1)

    rc = run_mod.cmd_run(paths, run_mod.AppConfig(), str(cand_path))
    out = capsys.readouterr().out
    assert rc == 0
    assert "PASS" in out
    # 旧记录已删除，新记录以 fresh_sim_1 为主键且为终态
    sims = store.list_simulations(h)
    assert len(sims) == 1
    assert sims[0]["id"] == "fresh_sim_1"
    assert sims[0]["status"] == "COMPLETED"
    assert store.find_pending_sim_id(h) is None


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
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.brain_client import RateLimits, SimulationResult
    from qa.screener import apply_thresholds
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
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

    cfg = run_mod.AppConfig()

    # mock stage 检测（不真调 API）
    from qa.stage import StageInfo

    monkeypatch.setattr(
        run_mod, "get_stage", lambda p: StageInfo(level="TEST", is_consultant=False)
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

    monkeypatch.setattr(run_mod.BrainClient, "poll_simulation", fake_poll)
    monkeypatch.setattr(
        run_mod.BrainClient, "simulate", lambda self, c, s: f"sim_{c[:8]}"
    )
    monkeypatch.setattr(
        run_mod.BrainClient,
        "rate_limits",
        lambda self: RateLimits(remaining_minute=30, limit_minute=30),
    )

    rc = run_mod.cmd_run(paths, cfg, candidates_file=str(cand_path))
    out = capsys.readouterr().out

    assert rc == 0
    assert "读入 2 个候选" in out
    assert "预检未过" in out  # 幻觉字段被拦截
    assert "PASS" in out  # 合法候选通过
    assert "完成" in out

    # 每日汇总已写入（按当天日期命名）
    from datetime import datetime

    daily = paths.REPORTS_DIR / "daily" / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    assert daily.exists()


def test_cmd_submit_end_to_end(tmp_qa, monkeypatch, capsys):
    """qa submit 端到端：展示检查 → 交互确认 → 提交 → 回查 ACTIVE。"""
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.store import Store
    from qa.validate import expression_hash
    from qa.commands import _common as common_mod
    from qa.commands import submit as submit_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    store = Store(paths.DB)

    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    expr = "group_rank(ts_rank(close, 60), subindustry)"
    _dump_cands(
        cand_path,
        [
            Candidate(
                description="动量测试",
                hypothesis="h",
                expression=expr,
                dataset_ids=["pv1"],
            )
        ],
    )
    h = expression_hash(expr)
    store.save_alpha(
        {
            "id": h,
            "expression": expr,
            "description": "动量测试",
            "hypothesis": "h",
            "dataset_ids": ["pv1"],
            "ast_hash": h,
            "metrics": {"sharpe": 1.68, "fitness": 1.05, "turnover": 0.046},
            "status": "COMPLETE",
        }
    )
    store.save_simulation(
        {
            "id": f"sim_{h}",
            "alpha_id": h,
            "result": {"regular": expr, "alpha": "PLATFORM_A1"},
            "status": "COMPLETE",
            "checks": [{"name": "LOW_SHARPE", "result": "PASS", "value": 1.68}],
        }
    )
    # 预置待提交暂存，模拟 qa run 跨会话接力后的状态
    common_mod._append_pending(paths, {"id": h, "description": "动量测试"})
    assert json.loads(paths.PENDING_SUBMITS.read_text(encoding="utf-8")) == [
        {"id": h, "description": "动量测试"}
    ]

    monkeypatch.setattr(
        submit_mod.BrainClient, "correlations_self", lambda self, aid: 0.12
    )
    monkeypatch.setattr(
        submit_mod.BrainClient, "submit", lambda self, aid: {"status": "SUBMITTED"}
    )
    monkeypatch.setattr(
        submit_mod.BrainClient, "get_alpha", lambda self, aid: {"status": "ACTIVE"}
    )

    rc = submit_mod._cmd_submit(paths, h, yes=True)
    out = capsys.readouterr().out

    assert rc == 0
    assert "平台检查" in out
    assert "相关门" in out
    assert "ACTIVE" in out
    assert "设计逻辑" in out  # 确认输出展示设计逻辑（机械确认 → 知情确认）

    # 提交成功后待提交暂存中的条目已被删除（保留空列表文件）
    pending = json.loads(paths.PENDING_SUBMITS.read_text(encoding="utf-8"))
    assert pending == []
    assert paths.PENDING_SUBMITS.exists()

    subs = store._conn.execute("SELECT * FROM submissions").fetchall()
    assert len(subs) == 1
    assert subs[0]["confirmed_active"] == 1
    updated = store.list_alphas()
    assert updated[0]["status"] == "SUBMITTED"


def test_cmd_run_missing_knowledge_errors(tmp_qa, monkeypatch, capsys):
    """v1.4：未生成本地知识库时 qa run 拒绝执行并提示 update-knowledge。"""
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
        cand_path,
        [Candidate(description="x", hypothesis="h", expression="rank(close)")],
    )
    monkeypatch.setattr(run_mod, "get_stage", lambda p: None)

    rc = run_mod.cmd_run(paths, run_mod.AppConfig(), str(cand_path))
    out = capsys.readouterr().out

    assert rc == 1
    assert "update-knowledge" in out


def test_cmd_run_rejects_vector_field_via_type_check(
    tmp_qa, monkeypatch, capsys, mock_brain
):
    """v1.4.1：VECTOR 字段未用 vec_* 转换 → 预检拦截（省无效模拟配额）。"""
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
        cand_path,
        [
            Candidate(
                description="合法标量",
                hypothesis="h",
                expression="rank(close)",
                dataset_ids=["pv1"],
            ),
            Candidate(
                description="VECTOR 误用",
                hypothesis="h",
                expression="rank(nws_x)",
                dataset_ids=["news12"],
            ),
        ],
    )
    monkeypatch.setattr(
        run_mod,
        "get_stage",
        lambda p: StageInfo(level="TEST", is_consultant=False),
    )

    rc = run_mod.cmd_run(paths, run_mod.AppConfig(), str(cand_path))
    out = capsys.readouterr().out

    assert rc == 0
    assert "VECTOR" in out  # 类型检查拦截提示
    assert mock_brain.simulated == ["rank(close)"]  # 只模拟合法候选
    assert "PASS" in out


def test_cmd_run_rejects_non_fastexpr_language(tmp_qa, monkeypatch, capsys, mock_brain):
    """v1.6：非 FASTEXPR（PYTHON/ML）候选预检 fail-closed 拒绝，不进入模拟。"""
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
        cand_path,
        [
            Candidate(
                description="FASTEXPR 合法",
                hypothesis="h",
                expression="rank(close)",
                dataset_ids=["pv1"],
            ),
            Candidate(
                description="PYTHON 占位",
                hypothesis="h",
                expression="rank(close)",
                dataset_ids=["pv1"],
                language="PYTHON",
            ),
        ],
    )
    monkeypatch.setattr(
        run_mod,
        "get_stage",
        lambda p: StageInfo(level="TEST", is_consultant=False),
    )

    rc = run_mod.cmd_run(paths, run_mod.AppConfig(), str(cand_path))
    out = capsys.readouterr().out

    assert rc == 0
    assert "暂不支持本地预检" in out
    assert mock_brain.simulated == ["rank(close)"]  # 只模拟 FASTEXPR 候选
    assert "PASS" in out


def test_cmd_run_auto_sediments_lessons_and_failures(tmp_qa, monkeypatch, capsys):
    """v1.4：run 后 PASS→lessons、FAIL→failures 自动写入 SQLite + experience/。"""
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.brain_client import SimulationResult
    from qa.store import Store
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
        cand_path,
        [
            Candidate(
                description="有效动量",
                hypothesis="动量延续",
                expression="rank(ts_delta(close, 5))",
                dataset_ids=["pv1"],
            ),
            Candidate(
                description="低夏普失败",
                hypothesis="弱信号",
                expression="rank(volume)",
                dataset_ids=["pv1"],
            ),
        ],
    )
    monkeypatch.setattr(
        run_mod, "get_stage", lambda p: StageInfo(level="TEST", is_consultant=False)
    )

    def fake_poll(self, sim_id, max_wait=600.0):
        sharpe = 1.5 if "ts_" in sim_id else 0.8
        return SimulationResult(
            sim_id=sim_id,
            status="COMPLETED",
            alpha_id="a1",
            checks=[
                {
                    "name": "SHARPE",
                    "result": "PASS" if sharpe > 1.0 else "FAIL",
                    "value": sharpe,
                }
            ],
            metrics={"sharpe": sharpe, "fitness": 1.1, "turnover": 0.2},
        )

    monkeypatch.setattr(run_mod.BrainClient, "poll_simulation", fake_poll)
    monkeypatch.setattr(
        run_mod.BrainClient, "simulate", lambda self, c, s: f"sim_{c[:8]}"
    )
    monkeypatch.setattr(run_mod.BrainClient, "correlations_self", lambda self, aid: 0.1)

    rc = run_mod.cmd_run(paths, run_mod.AppConfig(), str(cand_path))
    assert rc == 0

    store = Store(paths.DB)
    lessons = store._conn.execute("SELECT * FROM lessons").fetchall()
    failures = store._conn.execute("SELECT * FROM failures").fetchall()
    assert len(lessons) == 1
    assert len(failures) == 1
    assert "有效动量" in paths.PLAYBOOK.read_text(encoding="utf-8")
    assert "低夏普失败" in paths.FAILURES.read_text(encoding="utf-8")


def test_cmd_run_skips_sim_failure_on_rerun(tmp_qa, monkeypatch, capsys):
    """防重接线：simulations 表已有 ERROR 记录（平台拒绝过）→ 重跑跳过不重复模拟。"""
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.store import Store
    from qa.validate import expression_hash
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    expr = "rank(close)"
    h = expression_hash(expr)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
        cand_path,
        [
            Candidate(
                description="动量", hypothesis="h", expression=expr, dataset_ids=["pv1"]
            )
        ],
    )
    # 预置上次运行失败留下的 ERROR 记录（id=sim_{hash} 占位）
    store = Store(paths.DB)
    store.save_simulation(
        {"id": f"sim_{h}", "alpha_id": h, "status": "ERROR", "result": {"error": "400"}}
    )
    monkeypatch.setattr(
        run_mod, "get_stage", lambda p: StageInfo(level="TEST", is_consultant=False)
    )
    simulated: list[str] = []

    def fake_simulate(self, code, settings):
        simulated.append(code)
        return "never"

    monkeypatch.setattr(run_mod.BrainClient, "simulate", fake_simulate)

    rc = run_mod.cmd_run(paths, run_mod.AppConfig(), str(cand_path))
    out = capsys.readouterr().out

    assert rc == 0
    assert simulated == []  # 平台拒绝过的表达式不重复模拟
    assert "不重复模拟" in out  # 跳过原因对用户透明


def test_cmd_run_sediments_fail_infra_for_platform_error(tmp_qa, monkeypatch, capsys):
    """FAIL_INFRA 沉淀：平台返回 ERROR 状态（无指标）→ 写 failures（模拟 FAIL→failures 约定）。"""
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.brain_client import RateLimits
    from qa.store import Store
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
        cand_path,
        [
            Candidate(
                description="平台 ERROR",
                hypothesis="h",
                expression="rank(close)",
                dataset_ids=["pv1"],
            )
        ],
    )
    monkeypatch.setattr(
        run_mod, "get_stage", lambda p: StageInfo(level="TEST", is_consultant=False)
    )
    monkeypatch.setattr(
        run_mod.BrainClient, "simulate", lambda self, c, s: "plat_err_sim"
    )
    monkeypatch.setattr(
        run_mod.BrainClient,
        "poll_simulation",
        lambda self, sid, max_wait=600.0: run_mod.SimulationResult(
            sim_id=sid, status="ERROR", alpha_id=None, checks=[], metrics={}
        ),
    )
    monkeypatch.setattr(
        run_mod.BrainClient,
        "rate_limits",
        lambda self: RateLimits(remaining_minute=30, limit_minute=30),
    )
    monkeypatch.setattr(run_mod.BrainClient, "correlations_self", lambda self, aid: 0.1)

    rc = run_mod.cmd_run(paths, run_mod.AppConfig(), str(cand_path))
    out = capsys.readouterr().out

    assert rc == 0
    assert "FAIL_INFRA" in out
    store = Store(paths.DB)
    failures = store._conn.execute("SELECT * FROM failures").fetchall()
    assert len(failures) == 1
    assert "模拟基础设施失败" in failures[0]["failure_reason"]
    assert "平台 ERROR" in paths.FAILURES.read_text(encoding="utf-8")


def test_cmd_submit_verify_failure_keeps_pending_removed(tmp_qa, monkeypatch, capsys):
    """提交已受理但回查失败：不沉淀"提交失败"假记录，照常删 pending，提示核实。"""
    from qa.paths import QaPaths
    from qa.store import Store
    from qa.validate import expression_hash
    from qa.commands import _common as common_mod
    from qa.commands import submit as submit_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    store = Store(paths.DB)
    expr = "rank(close)"
    h = expression_hash(expr)
    store.save_alpha({"id": h, "expression": expr, "ast_hash": h, "status": "COMPLETE"})
    store.save_simulation(
        {
            "id": f"sim_{h}",
            "alpha_id": h,
            "result": {"alpha": "PLATFORM_A1"},
            "status": "COMPLETE",
        }
    )
    common_mod._append_pending(paths, {"id": h, "description": "动量"})

    monkeypatch.setattr(
        submit_mod.BrainClient, "correlations_self", lambda self, aid: 0.12
    )
    monkeypatch.setattr(
        submit_mod.BrainClient, "submit", lambda self, aid: {"status": "SUBMITTED"}
    )
    # 回查网络异常：平台已受理，但状态未知
    monkeypatch.setattr(
        submit_mod,
        "_wait_for_active",
        lambda client, aid: (_ for _ in ()).throw(RuntimeError("网络中断")),
    )

    rc = submit_mod._cmd_submit(paths, h, yes=True)
    out = capsys.readouterr().out

    assert rc == 1
    assert "提交已受理，回查失败" in out
    assert "请到平台核实" in out
    # 平台已受理 → pending 照常删除（防止重试重复提交）
    pending = json.loads(paths.PENDING_SUBMITS.read_text(encoding="utf-8"))
    assert pending == []
    # 不沉淀"提交失败"假记录：submissions 表有记录且非 confirmed_active，failures 无 sub_ 前缀
    subs = store._conn.execute("SELECT * FROM submissions").fetchall()
    assert len(subs) == 1
    assert subs[0]["current_status"] == "UNKNOWN"
    failures = store._conn.execute("SELECT * FROM failures").fetchall()
    assert [f["id"] for f in failures] == []

    """24h 内已生成的知识库默认跳过抓取；--force 强制刷新。"""
    from datetime import datetime, timedelta, timezone

    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.commands import update_knowledge as uk_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    monkeypatch.setattr(
        uk_mod,
        "get_stage",
        lambda p: StageInfo(level="BRONZE", is_consultant=False, regions=["USA"]),
    )
    _seed_knowledge(paths)
    now = datetime.now(timezone.utc)
    paths.KNOWLEDGE_META_JSON.write_text(
        json.dumps(
            {
                "field_count": 5,
                "dataset_count": 2,
                "regions": ["USA"],
                "generated_at": now.isoformat(),
            }
        ),
        encoding="utf-8",
    )

    called = []
    monkeypatch.setattr(
        uk_mod.knowledge,
        "build_local_knowledge",
        lambda *a, **k: called.append(True) or {"field_count": 0, "dataset_count": 0},
    )

    rc = uk_mod.cmd_update_knowledge(paths, None)
    out = capsys.readouterr().out
    assert rc == 0
    assert not called
    assert "跳过抓取" in out

    rc = uk_mod.cmd_update_knowledge(paths, None, force=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert called


def test_cmd_update_knowledge_end_to_end(tmp_qa, monkeypatch, capsys):
    """v1.4：qa update-knowledge 按账户区域抓字段 → 写 experience/（mock API）。"""
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.commands import update_knowledge as uk_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    monkeypatch.setattr(
        uk_mod,
        "get_stage",
        lambda p: StageInfo(level="BRONZE", is_consultant=False, regions=["USA"]),
    )

    def fake_get_json(self, path, params=None):
        if path == "/data-sets":
            return {"results": [{"id": "pv1"}], "count": 1}
        if path == "/data-fields":
            return {
                "results": [
                    {
                        "id": "close",
                        "description": "c",
                        "type": "MATRIX",
                        "coverage": 1.0,
                        "userCount": 10,
                    }
                ],
                "count": 1,
            }
        raise AssertionError(path)

    monkeypatch.setattr(uk_mod.BrainClient, "get_json", fake_get_json)

    rc = uk_mod.cmd_update_knowledge(paths, regions_arg=None, pace=0.0)
    out = capsys.readouterr().out

    assert rc == 0
    assert "完成" in out and "1 字段" in out
    assert paths.KNOWLEDGE_FIELDS_JSON.exists()
    assert "close" in paths.KNOWLEDGE_FIELDS_JSON.read_text(encoding="utf-8")
    assert paths.PLAYBOOK.exists()  # 模板随构建创建


def test_cmd_suggest_requires_and_uses_knowledge(tmp_qa, monkeypatch, capsys):
    """v1.4：qa suggest 无知识库报错；有知识库输出随机研究方向。"""
    from qa.paths import QaPaths
    from qa.commands import suggest as suggest_mod

    paths = QaPaths(tmp_qa)
    assert suggest_mod.cmd_suggest(paths) == 1

    _seed_knowledge(paths)
    rc = suggest_mod.cmd_suggest(paths)
    out = capsys.readouterr().out
    assert rc == 0
    assert "建议研究方向" in out
    assert any(f in out for f in ("close", "volume", "subindustry"))


def test_signal_fields_filters_unusable_types(tmp_qa, monkeypatch):
    """v1.4.1：suggest 排除 UNIVERSE/SYMBOL/VECTOR 字段（不可用于标量表达式）。"""
    from qa.commands import suggest as suggest_mod
    from qa.paths import QaPaths

    paths = QaPaths(tmp_qa)
    _seed_knowledge(paths)
    from qa import knowledge

    top = knowledge.load_top_fields(paths)
    signal = suggest_mod._signal_fields(top)
    ids = {f["id"] for f in signal}
    assert "close" in ids
    assert "top500" not in ids  # UNIVERSE 排除
    assert "nws_x" not in ids  # VECTOR 排除
    assert "subindustry" in ids  # GROUP 保留（group_by 可用）


def test_cmd_run_respects_minute_rate_limit(tmp_qa, monkeypatch, capsys):
    """v1.4.1：分钟限流剩余不足时批间等待，不硬撞 429。"""
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.brain_client import RateLimits
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
        cand_path,
        [
            Candidate(
                description=f"c{i}",
                hypothesis="h",
                expression=expr,
                dataset_ids=["pv1"],
            )
            for i, expr in enumerate(
                [
                    "rank(close)",
                    "rank(volume)",
                    "group_rank(rank(close), subindustry)",
                    "vec_avg(nws_x)",
                ]
            )
        ],
    )
    monkeypatch.setattr(
        run_mod,
        "get_stage",
        lambda p: StageInfo(level="TEST", is_consultant=False),
    )
    monkeypatch.setattr(
        run_mod.BrainClient, "simulate", lambda self, c, s: f"sim_{c[:8]}"
    )
    monkeypatch.setattr(
        run_mod.BrainClient,
        "poll_simulation",
        lambda self, sid, max_wait=600.0: run_mod.SimulationResult(
            sim_id=sid,
            status="COMPLETED",
            alpha_id="a1",
            checks=[],
            metrics={"sharpe": 1.5, "fitness": 1.1, "turnover": 0.2},
        ),
    )
    monkeypatch.setattr(
        run_mod.BrainClient,
        "rate_limits",
        lambda self: RateLimits(remaining_minute=1, limit_minute=30),
    )
    monkeypatch.setattr(run_mod.BrainClient, "correlations_self", lambda self, aid: 0.1)
    sleeps: list[float] = []
    monkeypatch.setattr(run_mod.time, "sleep", lambda s: sleeps.append(s))

    rc = run_mod.cmd_run(paths, run_mod.AppConfig(), str(cand_path))
    out = capsys.readouterr().out

    assert rc == 0
    assert sleeps, "剩余 1 时应等待限流窗口重置"
    assert "限流" in out


def test_cmd_status_prompts_knowledge_generation(tmp_qa, monkeypatch, capsys):
    """v1.4：status 展示知识库状态，缺失时提示 update-knowledge。"""
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.commands import status as status_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    monkeypatch.setattr(
        status_mod,
        "get_stage",
        lambda p: StageInfo(level="BRONZE", is_consultant=False),
    )
    assert status_mod.cmd_status(paths) == 0
    out = capsys.readouterr().out
    assert "update-knowledge" in out

    _seed_knowledge(paths)
    assert status_mod.cmd_status(paths) == 0
    out = capsys.readouterr().out
    assert "字段" in out and "生成于" in out


def test_cmd_reset_clears_experience_keeps_credentials(tmp_qa, monkeypatch, capsys):
    """qa reset：清除经验数据，保留 cookie/账号/知识库。"""
    from qa.paths import QaPaths
    from qa.store import Store
    from qa.commands import reset as reset_mod

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
    s.save_alpha(
        {
            "id": "a1",
            "expression": "rank(close)",
            "ast_hash": "h1",
            "status": "COMPLETE",
        }
    )
    s.save_lesson({"id": "l1", "trigger": "x", "lesson": "y"})
    # 本地知识库：fields 保留、playbook/failures 恢复模板
    _seed_knowledge(paths)
    from qa import knowledge

    knowledge.append_experience(paths, "lesson", "h9", "某经验", "内容")
    knowledge.append_experience(paths, "failure", "h9", "某证伪", "内容")

    rc = reset_mod._cmd_reset(paths, yes=True)
    out = capsys.readouterr().out

    assert rc == 0
    assert not paths.DB.exists()  # qa.db 已删
    assert not paths.CANDIDATES_DIR.exists() or not list(paths.CANDIDATES_DIR.glob("*"))
    assert not list((paths.REPORTS_DIR / "daily").glob("*"))
    assert not pending.exists()  # 待提交暂存已删
    assert paths.COOKIE.exists()  # cookie 保留
    assert "某经验" not in paths.PLAYBOOK.read_text(
        encoding="utf-8"
    )  # playbook 恢复模板
    assert "某证伪" not in paths.FAILURES.read_text(encoding="utf-8")
    assert paths.KNOWLEDGE_FIELDS_JSON.exists()  # 账户字段知识保留
    assert "保留" in out


# ---- 阶段 1 登录改造：status 环境判定 / cookie 分支 / 401 中断 / account_info ----


def test_env_verdict_states(tmp_qa):
    """_env_verdict 四态：new_user / partial / reset / ready。"""
    from qa.paths import QaPaths
    from qa.commands import status as status_mod

    paths = QaPaths(tmp_qa)
    # 全缺 → new_user
    assert status_mod._env_verdict(status_mod._env_checks(paths)) == "new_user"
    # 知识库在但 cookie 缺 → partial
    _seed_knowledge(paths)
    assert status_mod._env_verdict(status_mod._env_checks(paths)) == "partial"
    # fields+cookie 在但 db 缺（qa reset 后）→ reset
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    assert status_mod._env_verdict(status_mod._env_checks(paths)) == "reset"
    # 全部就绪 → ready
    from qa.store import Store

    Store(paths.DB)
    assert status_mod._env_verdict(status_mod._env_checks(paths)) == "ready"


def test_cmd_status_new_user_guides_first_run(tmp_qa, monkeypatch, capsys):
    """status：meta 缺失 → 新用户引导 login → update-knowledge → run。"""
    from qa.paths import QaPaths
    from qa.commands import status as status_mod

    paths = QaPaths(tmp_qa)
    rc = status_mod.cmd_status(paths)
    out = capsys.readouterr().out
    assert rc == 1  # cookie 也缺失
    assert "首次运行" in out
    assert "update-knowledge" in out
    assert "cookie 不存在" in out
    assert "qa login" in out


def test_cmd_status_partial_verdict_prompts_login(tmp_qa, monkeypatch, capsys):
    """status：知识库已生成但无 cookie → partial，提示先登录。"""
    from qa.paths import QaPaths
    from qa.commands import status as status_mod

    paths = QaPaths(tmp_qa)
    _seed_knowledge(paths)
    rc = status_mod.cmd_status(paths)
    out = capsys.readouterr().out
    assert rc == 1
    assert "请先 qa login" in out


def test_cmd_status_reset_verdict_no_relogin_needed(tmp_qa, monkeypatch, capsys):
    """status：qa reset 后（fields+cookie 在、db 缺）→ 可重新开始，无需重拉知识库。"""
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.commands import status as status_mod

    paths = QaPaths(tmp_qa)
    _seed_knowledge(paths)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    monkeypatch.setattr(
        status_mod,
        "get_stage",
        lambda p: StageInfo(level="BRONZE", is_consultant=False),
    )
    rc = status_mod.cmd_status(paths)
    out = capsys.readouterr().out
    assert rc == 0
    assert "经验已清除" in out
    assert "无需重拉知识库" in out


def test_cmd_status_cookie_expired_reports_relogin(tmp_qa, monkeypatch, capsys):
    """status：cookie 存在但已过期（fetch_self 401）→ 明确提示重新认证。"""
    from qa.paths import QaPaths
    from qa.commands import status as status_mod

    paths = QaPaths(tmp_qa)
    _seed_knowledge(paths)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")

    def fake_get_stage(p):
        raise PermissionError("BRAIN 会话无效或已过期，请更新 cookie 文件。")

    monkeypatch.setattr(status_mod, "get_stage", fake_get_stage)
    rc = status_mod.cmd_status(paths)
    out = capsys.readouterr().out
    assert rc == 1
    assert "cookie 已过期" in out
    assert "qa login 重新认证" in out


def test_cmd_status_shows_cached_stage_when_cookie_invalid(tmp_qa, monkeypatch, capsys):
    """cookie 失效时 status 展示 account_info.json 离线阶段缓存（标注来源）。"""
    from qa.paths import QaPaths
    from qa.commands import status as status_mod

    paths = QaPaths(tmp_qa)
    _seed_knowledge(paths)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    paths.ACCOUNT_INFO.write_text(
        json.dumps(
            {
                "level": "GOLD",
                "is_consultant": True,
                "updated_at": "2026-08-15T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    def fake_get_stage(p):
        raise PermissionError("BRAIN 会话无效或已过期，请更新 cookie 文件。")

    monkeypatch.setattr(status_mod, "get_stage", fake_get_stage)
    rc = status_mod.cmd_status(paths)
    out = capsys.readouterr().out
    assert rc == 1
    assert "离线缓存" in out
    assert "GOLD" in out


def test_cmd_status_stage_mismatch_warns_refresh(tmp_qa, monkeypatch, capsys):
    """status：meta 资格快照与当前资格不符（顾问 vs 用户）→ 建议 --force 刷新。"""
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.commands import status as status_mod

    paths = QaPaths(tmp_qa)
    _seed_knowledge(paths)
    meta = json.loads(paths.KNOWLEDGE_META_JSON.read_text(encoding="utf-8"))
    meta["stage"] = {"level": "BRONZE", "is_consultant": True}  # 顾问阶段生成的快照
    paths.KNOWLEDGE_META_JSON.write_text(json.dumps(meta), encoding="utf-8")
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    monkeypatch.setattr(
        status_mod,
        "get_stage",
        lambda p: StageInfo(level="SILVER", is_consultant=False),
    )
    rc = status_mod.cmd_status(paths)
    out = capsys.readouterr().out
    assert rc == 0
    assert "update-knowledge --force" in out
    assert "知识库一致性" in out


def test_cmd_status_level_mismatch_no_warning(tmp_qa, monkeypatch, capsys):
    """status：用户阶段内等级变化（BRONZE→SILVER）只是分数段位，不触发刷新提示。"""
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.commands import status as status_mod

    paths = QaPaths(tmp_qa)
    _seed_knowledge(paths)
    meta = json.loads(paths.KNOWLEDGE_META_JSON.read_text(encoding="utf-8"))
    meta["stage"] = {"level": "BRONZE", "is_consultant": False}
    paths.KNOWLEDGE_META_JSON.write_text(json.dumps(meta), encoding="utf-8")
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    monkeypatch.setattr(
        status_mod,
        "get_stage",
        lambda p: StageInfo(level="SILVER", is_consultant=False),
    )
    assert status_mod.cmd_status(paths) == 0
    out = capsys.readouterr().out
    assert "知识库一致性" not in out


def test_cmd_status_splits_level_and_consultant(tmp_qa, monkeypatch, capsys):
    """status：等级与资格分离展示（level 是分数段位，非顾问资格）。"""
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.commands import status as status_mod

    paths = QaPaths(tmp_qa)
    _seed_knowledge(paths)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    monkeypatch.setattr(
        status_mod, "get_stage", lambda p: StageInfo(level="GOLD", is_consultant=False)
    )
    assert status_mod.cmd_status(paths) == 0
    out = capsys.readouterr().out
    assert "等级: GOLD（分数段位，非顾问资格）" in out
    assert "资格: 用户" in out


def test_cmd_login_writes_account_info(tmp_qa, monkeypatch, capsys):
    """qa login 成功 → secrets/account_info.json 写入阶段摘要（不含密码/分数）。"""
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.commands import login as login_mod

    paths = QaPaths(tmp_qa)
    monkeypatch.setattr(login_mod.auth, "login", lambda email, pwd: "t=abc")
    monkeypatch.setattr(
        login_mod,
        "get_stage",
        lambda p: StageInfo(
            level="BRONZE",
            is_consultant=False,
            regions=["USA"],
            expression_languages=["FASTEXPR"],
        ),
    )
    rc = login_mod._cmd_login(paths, "user@example.com", "secret")
    out = capsys.readouterr().out
    assert rc == 0
    info = json.loads(paths.ACCOUNT_INFO.read_text(encoding="utf-8"))
    assert info["level"] == "BRONZE"
    assert info["is_consultant"] is False
    assert info["regions"] == ["USA"]
    assert "updated_at" in info
    assert "password" not in json.dumps(info)
    assert "等级" in out and "资格" in out


def test_cmd_run_interrupts_on_session_expired(tmp_qa, monkeypatch, capsys):
    """会话过期（401）时 run 中断：剩余候选不模拟，提示重登后重试。"""
    from qa.candidates import Candidate
    from qa.paths import QaPaths
    from qa.stage import StageInfo
    from qa.brain_client import RateLimits
    from qa.commands import run as run_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    _seed_knowledge(paths)
    cand_path = paths.CANDIDATES_DIR / "2026-08-14.json"
    _dump_cands(
        cand_path,
        [
            Candidate(
                description=f"c{i}",
                hypothesis="h",
                expression=expr,
                dataset_ids=["pv1"],
            )
            for i, expr in enumerate(
                [
                    "rank(close)",
                    "rank(volume)",
                    "group_rank(rank(close), subindustry)",
                    "vec_avg(nws_x)",
                ]
            )
        ],
    )
    monkeypatch.setattr(
        run_mod, "get_stage", lambda p: StageInfo(level="TEST", is_consultant=False)
    )

    def fake_simulate(self, code, settings):
        raise PermissionError("BRAIN 会话无效或已过期，请更新 cookie 文件。")

    monkeypatch.setattr(run_mod.BrainClient, "simulate", fake_simulate)
    monkeypatch.setattr(
        run_mod.BrainClient,
        "rate_limits",
        lambda self: RateLimits(remaining_minute=30, limit_minute=30),
    )
    monkeypatch.setattr(run_mod.time, "sleep", lambda s: None)

    rc = run_mod.cmd_run(paths, run_mod.AppConfig(), str(cand_path))
    out = capsys.readouterr().out
    assert rc == 0
    assert "会话已过期" in out
    assert "剩余 4 个候选未模拟" in out
    assert "qa login 后重试" in out


def test_cmd_submit_permission_error_reports_login(tmp_qa, monkeypatch, capsys):
    """submit 相关门查询时会话过期 → 明确提示 qa login（不再模糊报查询失败）。"""
    from qa.paths import QaPaths
    from qa.store import Store
    from qa.validate import expression_hash
    from qa.commands import submit as submit_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    store = Store(paths.DB)
    h = expression_hash("rank(close)")
    store.save_alpha(
        {"id": h, "expression": "rank(close)", "ast_hash": h, "status": "COMPLETE"}
    )
    store.save_simulation(
        {
            "id": f"sim_{h}",
            "alpha_id": h,
            "result": {"alpha": "PLATFORM_A1"},
            "status": "COMPLETE",
        }
    )

    def fake_corr(self, aid):
        raise PermissionError("BRAIN 会话无效或已过期，请更新 cookie 文件。")

    monkeypatch.setattr(submit_mod.BrainClient, "correlations_self", fake_corr)
    rc = submit_mod._cmd_submit(paths, h, yes=True)
    out = capsys.readouterr().out
    assert rc == 1
    assert "登录失效" in out
    assert "qa login" in out
    assert "相关门查询失败" not in out


def test_update_knowledge_permission_error_reports_login(tmp_qa, monkeypatch, capsys):
    """update-knowledge 阶段检测时会话过期 → 明确提示 qa login（不再模糊报阶段失败）。"""
    from qa.paths import QaPaths
    from qa.commands import update_knowledge as uk_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")

    def fake_get_stage(p):
        raise PermissionError("BRAIN 会话无效或已过期，请更新 cookie 文件。")

    monkeypatch.setattr(uk_mod, "get_stage", fake_get_stage)
    rc = uk_mod.cmd_update_knowledge(paths, None)
    out = capsys.readouterr().out
    assert rc == 1
    assert "登录失效" in out
    assert "qa login" in out


def test_cmd_report_shows_failure_attribution(tmp_qa, capsys):
    """阶段 5：qa report 无失败记录不显示归因；有失败记录显示归因小节。"""
    from qa.paths import QaPaths
    from qa.store import Store
    from qa.commands import report_cmd

    class Args:
        daily = False

    paths = QaPaths(tmp_qa)
    daily_dir = paths.REPORTS_DIR / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    (daily_dir / "2026-08-14.md").write_text(
        "# 每日达标汇总 2026-08-14\n", encoding="utf-8"
    )

    rc = report_cmd._cmd_report(paths, Args())
    assert rc == 0
    assert "失败归因" not in capsys.readouterr().out

    Store(paths.DB).save_failure(
        {
            "id": "f1",
            "expression_hash": "h1",
            "failure_reason": "模拟未过: 平台检查未过: ['LOW_SHARPE']",
        }
    )
    report_cmd._cmd_report(paths, Args())
    out = capsys.readouterr().out
    assert "失败归因" in out
    assert "LOW_SHARPE ×1" in out


def test_sediment_failure_appends_fix_suggestion(tmp_qa):
    """阶段 5：已知失败名 → failures.md 条目含修复建议；未知失败名照常写入不加建议。"""
    from qa.paths import QaPaths
    from qa.store import Store
    from qa.commands._common import _sediment_failure

    paths = QaPaths(tmp_qa)
    store = Store(paths.DB)
    _sediment_failure(
        paths,
        store,
        {
            "id": "f_known",
            "expression_hash": "h1",
            "failure_reason": "模拟未过: 平台检查未过: ['LOW_SHARPE', 'HIGH_TURNOVER']",
        },
        "低夏普失败",
        "- 触发: 模拟 FAIL（平台检查未过: ['LOW_SHARPE', 'HIGH_TURNOVER']）",
    )
    _sediment_failure(
        paths,
        store,
        {
            "id": "f_unknown",
            "expression_hash": "h2",
            "failure_reason": "提交失败: 404",
        },
        "提交失败",
        "- 触发: 提交失败（404）",
    )
    text = paths.FAILURES.read_text(encoding="utf-8")
    assert "延长 lookback / 换基本面字段 / 黄金组合" in text
    assert "增大 decay（技术 10-30）或 ts_rank 平滑" in text
    # 未知失败名：条目照常写入，body 后紧跟 id 标记（无修复建议行插入）
    assert "（404）\n\n<!-- f_unknown -->" in text


# ---- 阶段 6 成功提交：report --pending / 归因分离 / 回查提示语 / 被拒沉淀增强 ----


def test_cli_report_pending_arg(tmp_qa, monkeypatch):
    """cli 分发：--pending 透传给 report 命令，且与 --daily 互斥。"""
    import qa.cli as cli_mod

    captured = {}

    def fake_main(paths, cfg, args):
        captured["pending"] = args.pending
        captured["daily"] = args.daily
        return 0

    monkeypatch.setattr(cli_mod.report_cmd, "main", fake_main)
    assert cli_mod.main(["report", "--pending"]) == 0
    assert captured["pending"] is True
    assert captured["daily"] is False

    # 互斥：--pending 与 --daily 同传 → argparse 报错退出
    with pytest.raises(SystemExit):
        cli_mod.main(["report", "--pending", "--daily"])


def test_cmd_report_pending_empty(tmp_qa, capsys):
    """qa report --pending 无待提交 → 提示暂存为空。"""
    from qa.paths import QaPaths
    from qa.commands import report_cmd

    class Args:
        daily = False
        pending = True

    paths = QaPaths(tmp_qa)
    rc = report_cmd._cmd_report(paths, Args())
    out = capsys.readouterr().out
    assert rc == 0
    assert "暂存为空" in out


def test_cmd_report_pending_shows_entries_with_metrics_and_corr(tmp_qa, capsys):
    """qa report --pending 展示 pending 条目：description/hypothesis/指标/corr。"""
    from qa.paths import QaPaths
    from qa.commands import report_cmd

    class Args:
        daily = False
        pending = True

    paths = QaPaths(tmp_qa)
    paths.PENDING_SUBMITS.write_text(
        json.dumps(
            [
                {
                    "id": "h1",
                    "description": "价格动量",
                    "hypothesis": "近期涨幅延续",
                    "expression": "rank(ts_delta(close, 5))",
                    "metrics": {"sharpe": 1.5, "fitness": 1.2, "turnover": 0.2},
                    "corr": 0.42,
                }
            ]
        ),
        encoding="utf-8",
    )
    rc = report_cmd._cmd_report(paths, Args())
    out = capsys.readouterr().out
    assert rc == 0
    assert "待提交清单" in out
    assert "价格动量" in out
    assert "近期涨幅延续" in out
    assert "Sharpe=1.5" in out
    assert "相关门: 0.42（提交前需复查）" in out


def test_cmd_report_splits_failure_attribution_sections(tmp_qa, capsys):
    """阶段 6：report 归因分两节——模拟失败归因与提交被拒归因分开展示。"""
    from qa.paths import QaPaths
    from qa.store import Store
    from qa.commands import report_cmd

    class Args:
        daily = False
        pending = False

    paths = QaPaths(tmp_qa)
    daily_dir = paths.REPORTS_DIR / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    (daily_dir / "2026-08-14.md").write_text(
        "# 每日达标汇总 2026-08-14\n", encoding="utf-8"
    )
    store = Store(paths.DB)
    store.save_failure(
        {
            "id": "f_sim1",
            "expression_hash": "h1",
            "failure_reason": "模拟未过: 平台检查未过: ['LOW_SHARPE']",
        }
    )
    store.save_failure(
        {
            "id": "corr_h2",
            "expression_hash": "h2",
            "failure_reason": "提交前相关门未过: max_corr=0.80≥0.7",
        }
    )

    report_cmd._cmd_report(paths, Args())
    out = capsys.readouterr().out
    assert "失败归因（模拟类）" in out
    assert "LOW_SHARPE ×1" in out
    assert "提交被拒归因" in out
    assert "MAX_CORR ×1" in out


def test_cmd_submit_non_active_keeps_pending_removed_and_clear_prompt(
    tmp_qa, monkeypatch, capsys
):
    """提交被平台接受但回查非 ACTIVE：pending 照删，提示语说明正常延迟。"""
    from qa.paths import QaPaths
    from qa.store import Store
    from qa.validate import expression_hash
    from qa.commands import _common as common_mod
    from qa.commands import submit as submit_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    store = Store(paths.DB)
    expr = "rank(close)"
    h = expression_hash(expr)
    store.save_alpha({"id": h, "expression": expr, "ast_hash": h, "status": "COMPLETE"})
    store.save_simulation(
        {
            "id": f"sim_{h}",
            "alpha_id": h,
            "result": {"alpha": "PLATFORM_A1"},
            "status": "COMPLETE",
        }
    )
    common_mod._append_pending(paths, {"id": h, "description": "动量"})

    monkeypatch.setattr(
        submit_mod.BrainClient, "correlations_self", lambda self, aid: 0.12
    )
    monkeypatch.setattr(
        submit_mod.BrainClient, "submit", lambda self, aid: {"status": "SUBMITTED"}
    )
    # mock 回查（避免 _wait_for_active 真实轮询 120s）：平台已接受但状态未同步 ACTIVE
    monkeypatch.setattr(
        submit_mod, "_wait_for_active", lambda client, aid: {"status": "PENDING"}
    )

    rc = submit_mod._cmd_submit(paths, h, yes=True)
    out = capsys.readouterr().out
    assert rc == 1
    assert "平台已接受提交，状态未同步 ACTIVE 属正常延迟" in out
    assert "请到平台核实" in out
    # 平台已接受 → 从 pending 删除（使命完成，保留删除行为）
    pending = json.loads(paths.PENDING_SUBMITS.read_text(encoding="utf-8"))
    assert pending == []


def test_cmd_submit_corr_rejection_sediments_avoid_cluster_hint(
    tmp_qa, monkeypatch, capsys
):
    """相关门被拒（≥0.7）：不提交，沉淀消息含"生成时避开该信号簇"提示。"""
    from qa.paths import QaPaths
    from qa.store import Store
    from qa.validate import expression_hash
    from qa.commands import submit as submit_mod

    paths = QaPaths(tmp_qa)
    paths.COOKIE.write_text("t=abc", encoding="utf-8")
    store = Store(paths.DB)
    expr = "rank(close)"
    h = expression_hash(expr)
    store.save_alpha({"id": h, "expression": expr, "ast_hash": h, "status": "COMPLETE"})
    store.save_simulation(
        {
            "id": f"sim_{h}",
            "alpha_id": h,
            "result": {"alpha": "PLATFORM_A1"},
            "status": "COMPLETE",
        }
    )
    monkeypatch.setattr(
        submit_mod.BrainClient, "correlations_self", lambda self, aid: 0.85
    )
    submitted = []
    monkeypatch.setattr(
        submit_mod.BrainClient,
        "submit",
        lambda self, aid: submitted.append(aid) or {},
    )

    rc = submit_mod._cmd_submit(paths, h, yes=True)
    out = capsys.readouterr().out
    assert rc == 1
    assert "放弃提交" in out
    assert not submitted  # 相关门被拒不触发平台提交
    # 沉淀消息增强：包含"生成时避开该信号簇"提示
    failures_text = paths.FAILURES.read_text(encoding="utf-8")
    assert "生成时避开该信号簇" in failures_text
    assert "需换思路或降相关" in failures_text
