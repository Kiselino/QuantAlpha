"""screener 单测：门槛判定（PASS/MARGINAL/FAIL/FAIL_INFRA）+ 同字段集去重 + 排序。"""

from __future__ import annotations

import pytest

from qa.config import Thresholds
from qa.screener import (
    ScreeningVerdict,
    apply_thresholds,
    dedupe_by_fields,
)


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
    """平台 checks 缺失时本地 margin 判定（兜底）。"""
    t = Thresholds()
    metrics = {"sharpe": 1.3, "fitness": 1.1, "turnover": 0.2}
    v = apply_thresholds(metrics, [], t)
    # 1.3 vs 1.25 → 余量 4% < 10% → MARGINAL
    assert v.verdict == "MARGINAL"


def test_platform_checks_pass_overrides_marginal():
    """平台 checks 全部 PASS 时不降级为 MARGINAL（P1：平台为权威）。"""
    t = Thresholds()
    metrics = {"sharpe": 1.3, "fitness": 1.02, "turnover": 0.2}
    checks = [
        {"name": "LOW_SHARPE", "result": "PASS", "limit": 1.25, "value": 1.3},
        {"name": "LOW_FITNESS", "result": "PASS", "limit": 1.0, "value": 1.02},
    ]
    v = apply_thresholds(metrics, checks, t)
    assert v.verdict == "PASS"


def test_fail_infra_when_no_metrics():
    v = apply_thresholds({}, [], Thresholds())
    assert v.verdict == "FAIL_INFRA"


OPS = {"rank", "ts_mean", "ts_delta", "group_rank"}


def test_dedupe_same_field_set_keeps_simplest():
    exprs = ["rank(ts_mean(close, 5))", "rank(ts_mean(close, 20))", "rank(volume)"]
    keep, skipped = dedupe_by_fields(exprs, OPS)
    assert keep == [0, 2]  # 同字段集 {close} → 保留第一个（更简单）；volume 独立保留
    assert len(skipped) == 1
    assert skipped[0][0] == 1
    assert "同字段集" in skipped[0][1]


def test_dedupe_distinct_field_sets_all_kept():
    exprs = ["rank(ts_mean(close, 5))", "rank(ts_mean(volume, 5))"]
    keep, skipped = dedupe_by_fields(exprs, OPS)
    assert keep == [0, 1]
    assert skipped == []


def test_dedupe_keeps_simplest_within_cluster():
    exprs = ["rank(ts_delta(close, 5))", "rank(ts_mean(ts_mean(close, 5), 5))"]
    keep, skipped = dedupe_by_fields(exprs, OPS)
    assert keep == [0]  # 两个都用 {close}，保留算子更少的
    assert skipped[0][0] == 1
