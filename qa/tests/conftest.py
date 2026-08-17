from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 让 `qa` 包可直接导入（未安装时）
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def tmp_qa(tmp_path: Path) -> Path:
    """构造带标准子目录的临时仓库根。"""
    (tmp_path / "secrets").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "audit").mkdir(parents=True, exist_ok=True)
    (tmp_path / "reports" / "daily").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def mock_brain(monkeypatch):
    """qa run 测试脚手架：mock BrainClient 常用方法 + 收集 simulate/poll 调用。

    默认 simulate 记录 code 并返回 sim_{n}；poll 返回 COMPLETED 固定指标
    （sharpe=1.5/fitness=1.1/turnover=0.2，本地门槛 PASS）；rate_limits 返回
    30/30（分钟头，每日配额不查询）；correlations_self 返回 0.1。
    测试可按需覆写 mock.rate_limit / mock.metrics / mock.corr 等字段。
    """
    from qa.brain_client import RateLimits, SimulationResult
    from qa.commands import run as run_mod

    class _MockBrain:
        def __init__(self):
            self.simulated: list[str] = []
            self.polled: list[str] = []
            self.rate_limit = RateLimits(remaining_minute=30, limit_minute=30)
            self.corr = 0.1
            self.metrics: dict[str, float | None] = {
                "sharpe": 1.5,
                "fitness": 1.1,
                "turnover": 0.2,
            }
            self.checks: list[dict] = []

        def simulate(self, code, settings):
            self.simulated.append(code)
            return f"sim_{len(self.simulated)}"

        def poll_simulation(self, sim_id, max_wait=600.0):
            self.polled.append(sim_id)
            return SimulationResult(
                sim_id=sim_id,
                status="COMPLETED",
                alpha_id="a1",
                checks=self.checks,
                metrics=self.metrics,
            )

        def rate_limits(self):
            return self.rate_limit

        def correlations_self(self, alpha_id):
            return self.corr

    mock = _MockBrain()
    monkeypatch.setattr(run_mod.BrainClient, "simulate", mock.simulate)
    monkeypatch.setattr(run_mod.BrainClient, "poll_simulation", mock.poll_simulation)
    monkeypatch.setattr(run_mod.BrainClient, "rate_limits", mock.rate_limits)
    monkeypatch.setattr(
        run_mod.BrainClient, "correlations_self", mock.correlations_self
    )
    return mock
