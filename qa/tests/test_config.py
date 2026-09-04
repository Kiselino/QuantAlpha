"""config/paths 单测：默认阈值、模拟默认值、私有路径布局。"""

from __future__ import annotations

from pathlib import Path

from qa.config import AppConfig, SimulationDefaults, Thresholds
from qa.paths import QaPaths


def test_paths_under_root(tmp_qa: Path):
    p = QaPaths(tmp_qa)
    assert p.COOKIE == tmp_qa / "secrets" / "worldquant_cookies.txt"
    assert p.DB == tmp_qa / "data" / "qa.db"
    assert p.AUDIT_DIR == tmp_qa / "data" / "audit"
    assert p.REPORTS_DIR == tmp_qa / "reports"
    assert p.CANDIDATES_DIR == tmp_qa / "data" / "candidates"


def test_thresholds_defaults():
    t = Thresholds()
    assert t.sharpe_d1 == 1.25
    assert t.fitness_d1 == 1.0
    assert t.turnover_max == 0.70


def test_simulation_defaults():
    d = SimulationDefaults()
    assert d.region == "USA"
    assert d.universe == "TOP3000"
    assert d.delay == 1
    assert d.neutralization == "INDUSTRY"


def test_app_config_defaults():
    c = AppConfig()
    assert c.concurrency == 3
