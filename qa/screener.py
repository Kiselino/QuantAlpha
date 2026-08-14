"""门槛过滤 + 相关性（组合视角 P3）。

门槛对齐平台提交检查；相关性用日收益（非累计 PnL，防误判）。
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from qa.config import Thresholds


@dataclass(frozen=True)
class ScreeningVerdict:
    verdict: str                       # PASS / MARGINAL / FAIL / FAIL_INFRA
    failed_checks: list[str] = field(default_factory=list)
    reason: str = ""


def apply_thresholds(
    metrics: Mapping[str, float | None], checks: list[dict[str, Any]], t: Thresholds
) -> ScreeningVerdict:
    """用平台 is.checks 结果 + 本地门槛判断。

    平台已给出各检查 PASS/FAIL（checks），直接采信（P1：平台为权威）；
    平台 checks 全部 PASS 时不再用本地 margin 降级为 MARGINAL。
    本地硬门槛兜底平台未覆盖维度；MARGINAL 仅当平台 checks 缺失时使用。
    """
    sharpe_raw = metrics.get("sharpe")
    if not metrics or sharpe_raw is None:
        return ScreeningVerdict(verdict="FAIL_INFRA", reason="缺少模拟指标")

    failed = [
        c["name"] for c in checks if c.get("result") == "FAIL"
    ]
    if failed:
        return ScreeningVerdict(
            verdict="FAIL", failed_checks=failed, reason=f"平台检查未过: {failed}"
        )

    # 本地硬门槛（平台 checks 未覆盖的维度）
    sharpe = float(sharpe_raw)
    fitness = float(metrics.get("fitness") or 0.0)
    turnover = float(metrics.get("turnover") or 0.0)
    if sharpe < t.sharpe_d1:
        return ScreeningVerdict(
            verdict="FAIL", failed_checks=["SHARPE"],
            reason=f"Sharpe {sharpe:.2f} < {t.sharpe_d1}",
        )
    if fitness < t.fitness_d1:
        return ScreeningVerdict(
            verdict="FAIL", failed_checks=["FITNESS"],
            reason=f"Fitness {fitness:.2f} < {t.fitness_d1}",
        )
    if not (t.turnover_min <= turnover <= t.turnover_max):
        return ScreeningVerdict(
            verdict="FAIL", failed_checks=["TURNOVER"],
            reason=f"Turnover {turnover:.2f} 超出 [{t.turnover_min}, {t.turnover_max}]",
        )

    if checks:
        return ScreeningVerdict(verdict="PASS", reason="平台检查全部通过")

    margin = t.margin_marginal
    if sharpe < t.sharpe_d1 * (1 + margin) or fitness < t.fitness_d1 * (1 + margin):
        return ScreeningVerdict(verdict="MARGINAL", reason="指标距门槛余量 <10%")

    return ScreeningVerdict(verdict="PASS", reason="全部门槛通过")


def compute_correlation(a: list[float], b: list[float]) -> float:
    """Pearson 相关系数（日收益序列）。长度不足返回 0。"""
    if len(a) < 3 or len(b) < 3 or len(a) != len(b):
        return 0.0
    ma, mb = statistics.mean(a), statistics.mean(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va == 0 or vb == 0:
        return 0.0
    return cov / (va ** 0.5 * vb ** 0.5)


def rank_candidates(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 score 降序排序（供提交建议排序）。"""
    return sorted(scored, key=lambda x: x.get("score", 0.0), reverse=True)
