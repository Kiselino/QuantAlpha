"""候选清单报告 + 待提交清单 + 每日达标汇总文档 + 失败归因小节。

- format_candidates：把筛选结果渲染为 markdown 候选清单（指标/通过项/说明/相关门排序）。
- format_pending：待提交暂存清单（qa report --pending，提交前全貌查看）。
- write_daily_summary：把 PASS 候选追加到 reports/daily/YYYY-MM-DD.md（累计趋势）。
- format_failure_attribution：失败归因小节（阶段 6 起分模拟/提交两类展示）。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def _format_corr(corr: float) -> str:
    """相关门排序值展示：标注"提交前需复查"防误读。

    排序值是 run 时的历史值，提交时以实时复查为准（相关门被拒即弃，
    不重试）；≥0.7 时额外提示提交时将被拒。
    """
    corr = float(corr)
    suffix = "，≥0.7 提交时将被拒" if corr >= 0.7 else ""
    return f"{corr:.2f}（提交前需复查{suffix}）"


def _metrics_line(metrics: dict[str, Any]) -> str:
    """指标行渲染（候选清单与待提交清单共用，格式保持一致）。"""
    return (
        f"- 指标: Sharpe={metrics.get('sharpe', '—'):}  "
        f"Fitness={metrics.get('fitness', '—'):}  Turnover={metrics.get('turnover', '—'):}"
    )


def format_candidates(candidates: list[dict[str, Any]]) -> str:
    """生成候选清单 markdown（指标/通过项/逻辑解释/相关门排序/建议排序）。"""
    lines = ["## 候选清单", ""]
    if not candidates:
        lines.append("（无候选）")
        return "\n".join(lines)
    for i, c in enumerate(candidates, 1):
        lines.append(
            f"### {i}. {c.get('description', '未命名')}  `[{c.get('verdict', '?')}]`"
        )
        lines.append(f"- 表达式: `{c.get('expression', '')}`")
        if c.get("hypothesis"):
            lines.append(f"- 设计逻辑: {c['hypothesis']}")
        lines.append(_metrics_line(c))
        if c.get("corr") is not None:
            lines.append(f"- 相关门: {_format_corr(c['corr'])}")
        if c.get("reason"):
            lines.append(f"- 说明: {c['reason']}")
        lines.append("")
    return "\n".join(lines)


def format_pending(entries: list[dict[str, Any]]) -> str:
    """待提交清单 markdown（qa report --pending，提交前全貌查看）。

    展示 local_id/description/hypothesis/指标/相关门排序值；
    提交仍逐个人工确认（qa submit <local_id>），本清单不替代确认环节。
    """
    lines = [f"## 待提交清单（{len(entries)} 条）", ""]
    for i, e in enumerate(entries, 1):
        lines.append(
            f"### {i}. {e.get('description', '未命名')}  `[{e.get('id', '?')}]`"
        )
        if e.get("hypothesis"):
            lines.append(f"- 设计逻辑: {e['hypothesis']}")
        metrics = e.get("metrics") or {}
        lines.append(_metrics_line(metrics))
        if e.get("corr") is not None:
            lines.append(f"- 相关门: {_format_corr(e['corr'])}")
        lines.append("")
    return "\n".join(lines)


def format_failure_attribution(
    stats: list[dict[str, Any]], category: str = "sim"
) -> str | None:
    """失败归因小节：`LOW_SHARPE ×12 / LOW_FITNESS ×8`（无数据返回 None，不显示）。

    stats 来自 store.failure_stats(category=...) 的 [{reason, count}] 列表。
    category: "sim" → 标题"失败归因（模拟类）"；"sub" → "提交被拒归因"
    （阶段 6：模拟失败→优化表达式，提交被拒→避开饱和簇，修复路径不同分开展示）。
    """
    if not stats:
        return None
    items = " / ".join(f"{s['reason']} ×{s['count']}" for s in stats)
    title = "提交被拒归因" if category == "sub" else "失败归因（模拟类）"
    return f"## {title}\n\n{items}"


def write_daily_summary(
    candidates: list[dict[str, Any]], reports_dir: Path, date: str | None = None
) -> Path:
    """把通过候选追加到 reports/daily/YYYY-MM-DD.md。返回文件路径。

    追加模式 + 去重：同日多次 run 时，"今日无通过候选"标记只写一次，
    同一表达式不重复记录。
    """
    d = date or datetime.now().strftime("%Y-%m-%d")
    daily_dir = reports_dir / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    path = daily_dir / f"{d}.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""

    text = f"# 每日达标汇总 {d}\n\n" if not existing else ""
    passed = [c for c in candidates if c.get("verdict") == "PASS"]
    if not passed:
        if "今日无通过候选" not in existing:
            text += "（今日无通过候选）\n\n"
    else:
        added = False
        for c in passed:
            expr = c.get("expression", "")
            if expr and f"`{expr}`" in existing:
                continue
            text += (
                f"- {c.get('description', '')} | `{expr}` "
                f"| Sharpe={c.get('sharpe'):} | Fitness={c.get('fitness'):} "
                f"| TO={c.get('turnover'):}\n"
            )
            added = True
        if added:
            text += "\n"
    if text:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
    return path
