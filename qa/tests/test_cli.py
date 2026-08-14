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
