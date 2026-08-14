"""候选清单报告 + 每日达标汇总文档。"""

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
    """把通过候选追加到 reports/daily/YYYY-MM-DD.md。返回文件路径。"""
    d = date or datetime.now().strftime("%Y-%m-%d")
    daily_dir = reports_dir / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    path = daily_dir / f"{d}.md"
    header = f"# 每日达标汇总 {d}\n\n" if not path.exists() else ""
    passed = [c for c in candidates if c.get("verdict") == "PASS"]
    lines = [header]
    if not passed:
        lines.append("（今日无通过候选）\n")
    for c in passed:
        lines.append(
            f"- {c.get('description', '')} | `{c.get('expression', '')}` "
            f"| Sharpe={c.get('sharpe'):} | Fitness={c.get('fitness'):} "
            f"| TO={c.get('turnover'):}"
        )
    lines.append("")
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path
