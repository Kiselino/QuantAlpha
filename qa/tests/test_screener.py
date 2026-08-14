"""screener 单测：门槛判定（PASS/MARGINAL/FAIL/FAIL_INFRA）+ 相关性 + 排序。"""

from __future__ import annotations

import math

import pytest

from qa.config import Thresholds
from qa.screener import ScreeningVerdict, apply_thresholds, compute_correlation, rank_candidates


def test_pass_all():
    metrics = {"sharpe": 1.5, "fitness": 1.2, "turnover": 0.2, "returns": 0.05}
    checks = [
        {"name": "SHARPE", "result": "PASS", "limit": 1.25, "value": 1.5},
        {"name": "HIGH_TURNOVER", "result": "PASS", "limit": 0.7, "value": 0.2},
    ]
    v = apply_thresholds(metrics, checks, Thresholds())
    assert v.verdict == "PASS"


def test_fail_low_sharpe():
    metrics = {"sharpe": 0.8, "fitness": 0.9, "turnover": 0.2}
    checks = [
        {"name": "SHARPE", "result": "FAIL", "limit": 1.25, "value": 0.8},
    ]
    v = apply_thresholds(metrics, checks, Thresholds())
    assert v.verdict == "FAIL"
    assert "SHARPE" in v.failed_checks


def test_marginal_near_threshold():
    t = Thresholds()
    metrics = {"sharpe": 1.3, "fitness": 1.1, "turnover": 0.2}
    checks = [
        {"name": "SHARPE", "result": "PASS", "limit": 1.25, "value": 1.3},
    ]
    v = apply_thresholds(metrics, checks, t)
    # 1.3 vs 1.25 → 余量 4% < 10% → MARGINAL
    assert v.verdict == "MARGINAL"


def test_fail_infra_when_no_metrics():
    v = apply_thresholds({}, [], Thresholds())
    assert v.verdict == "FAIL_INFRA"


def test_compute_correlation_perfect():
    a = [1.0, 2.0, 3.0, 4.0]
    b = [2.0, 4.0, 6.0, 8.0]
    assert compute_correlation(a, b) == pytest.approx(1.0)


def test_compute_correlation_independent():
    a = [1.0, 2.0, 3.0, 4.0]
    b = [4.0, 3.0, 2.0, 1.0]
    assert compute_correlation(a, b) == pytest.approx(-1.0)


def test_rank_candidates():
    scored = [
        {"id": "a", "score": 1.0},
        {"id": "b", "score": 3.0},
        {"id": "c", "score": 2.0},
    ]
    ranked = rank_candidates(scored)
    assert [x["id"] for x in ranked] == ["b", "c", "a"]
