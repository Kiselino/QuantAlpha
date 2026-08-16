"""qa report 命令：查看候选清单/每日汇总/待提交清单。

命名避让 qa/report.py（报告格式化模块），故子包文件名为 report_cmd.py。
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

from qa.config import AppConfig
from qa.paths import QaPaths
from qa.report import format_failure_attribution, format_pending
from qa.store import Store


def _report_pending(paths: QaPaths) -> int:
    """展示待提交暂存清单（qa report --pending）。

    展示每个条目的 local_id/description/hypothesis/指标/相关门排序值；
    提交仍逐个人工确认（qa submit <local_id>），不做批量自动提交（合规红线）。
    """
    p = paths.PENDING_SUBMITS
    if not p.exists():
        print("[report] 暂存为空：无待提交 alpha（先 qa run 模拟并产生 PASS 候选）")
        return 0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        print("[report] 暂存为空：pending_submits.json 解析失败")
        return 0
    entries = [e for e in data if isinstance(e, dict)] if isinstance(data, list) else []
    if not entries:
        print("[report] 暂存为空：无待提交 alpha")
        return 0
    print(format_pending(entries))
    return 0


def _cmd_report(paths: QaPaths, args) -> int:
    daily_dir = paths.REPORTS_DIR / "daily"
    rc = 0
    if getattr(args, "pending", False):
        rc = _report_pending(paths)
    elif not daily_dir.exists():
        print("[report] 尚无每日汇总。先运行 qa run。")
        return 0
    else:
        files = sorted(glob.glob(str(daily_dir / "*.md")), reverse=True)
        if not files:
            print("[report] 尚无每日汇总。先运行 qa run。")
            return 0
        if args.daily:
            for f in files[:1]:
                print(Path(f).read_text(encoding="utf-8"))
        else:
            print("近期每日汇总:")
            for f in files[:7]:
                print(f"  {Path(f).name}")
    # 阶段 6：归因分离——模拟失败归因 与 提交被拒归因 分两节展示（无记录的小节不显示）
    store = Store(paths.DB)
    for stats, category in (
        (store.failure_stats(category="sim"), "sim"),
        (store.failure_stats(category="sub"), "sub"),
    ):
        section = format_failure_attribution(stats, category=category)
        if section:
            print()
            print(section)
    return rc


def main(paths: QaPaths, cfg: AppConfig, args) -> int:
    """命令入口：qa report（argparse 分发）。"""
    return _cmd_report(paths, args)
