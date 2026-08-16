"""门槛过滤 + 同字段集去重（组合视角 P3）。

门槛对齐平台提交检查；批次内同字段集候选只模拟最简者（省模拟配额）。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from qa.config import Thresholds
from qa.validate import expression_fields, measure_complexity


@dataclass(frozen=True)
class ScreeningVerdict:
    verdict: str  # PASS / MARGINAL / FAIL / FAIL_INFRA
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

    failed = [c["name"] for c in checks if c.get("result") == "FAIL"]
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
            verdict="FAIL",
            failed_checks=["SHARPE"],
            reason=f"Sharpe {sharpe:.2f} < {t.sharpe_d1}",
        )
    if fitness < t.fitness_d1:
        return ScreeningVerdict(
            verdict="FAIL",
            failed_checks=["FITNESS"],
            reason=f"Fitness {fitness:.2f} < {t.fitness_d1}",
        )
    if not (t.turnover_min <= turnover <= t.turnover_max):
        return ScreeningVerdict(
            verdict="FAIL",
            failed_checks=["TURNOVER"],
            reason=f"Turnover {turnover:.2f} 超出 [{t.turnover_min}, {t.turnover_max}]",
        )

    if checks:
        return ScreeningVerdict(verdict="PASS", reason="平台检查全部通过")

    margin = t.margin_marginal
    if sharpe < t.sharpe_d1 * (1 + margin) or fitness < t.fitness_d1 * (1 + margin):
        return ScreeningVerdict(verdict="MARGINAL", reason="指标距门槛余量 <10%")

    return ScreeningVerdict(verdict="PASS", reason="全部门槛通过")


def dedupe_by_fields(
    exprs: list[str], operators: set[str]
) -> tuple[list[int], list[tuple[int, str]]]:
    """同字段集候选去重：每组同字段集只保留算子数最少者。

    同字段集 ≈ 同信号簇（如 rank(ts_mean(close,5)) vs rank(ts_mean(close,20))），
    结果高度相关，全部模拟浪费配额。返回 (保留索引, [(跳过索引, 原因)])，保持输入顺序。
    """
    clusters: dict[frozenset[str], tuple[int, int]] = {}  # 字段集 → (索引, 算子数)
    keep: list[int] = []
    skipped: list[tuple[int, str]] = []
    for i, expr in enumerate(exprs):
        key = frozenset(expression_fields(expr, operators))
        complexity = measure_complexity(expr, operators)[0]
        if key not in clusters:
            clusters[key] = (i, complexity)
            keep.append(i)
            continue
        champion_idx, champion_complexity = clusters[key]
        if complexity < champion_complexity:
            keep.remove(champion_idx)
            keep.append(i)
            skipped.append((champion_idx, "同字段集簇去重（保留算子更少者）"))
            clusters[key] = (i, complexity)
        else:
            skipped.append((i, "同字段集簇去重（保留算子更少者）"))
    return keep, skipped
