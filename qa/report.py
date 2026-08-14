"""候选清单报告 + 每日达标汇总文档。

- format_candidates：把筛选结果渲染为 markdown 候选清单（指标/通过项/说明/建议排序）。
- write_daily_summary：把 PASS 候选追加到 reports/daily/YYYY-MM-DD.md（累计趋势）。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def format_candidates(candidates: list[dict]) -> str:
    """生成候选清单 markdown（指标/通过项/逻辑解释/建议排序）。"""
    lines = ["## 候选清单", ""]
    if not candidates:
        lines.append("（无候选）")
        return "\n".join(lines)
    for i, c in enumerate(candidates, 1):
        lines.append(f"### {i}. {c.get('description', '未命名')}  `[{c.get('verdict', '?')}]`")
        lines.append(f"- 表达式: `{c.get('expression', '')}`")
        lines.append(
            f"- 指标: Sharpe={c.get('sharpe', '—'):}  "
            f"Fitness={c.get('fitness', '—'):}  Turnover={c.get('turnover', '—'):}"
        )
        if c.get("reason"):
            lines.append(f"- 说明: {c['reason']}")
        lines.append("")
    return "\n".join(lines)


def write_daily_summary(
    candidates: list[dict], reports_dir: Path, date: str | None = None
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
