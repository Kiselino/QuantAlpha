"""QuantAlpha CLI：argparse 分发入口（命令实现在 qa/commands/ 子包）。

生成由对话层 agent 完成（agent 读 knowledge/ 后写候选到 data/candidates/）。
本项目只执行：读入候选 → 预检 → 模拟 → 筛选 → 报告 →（确认后）提交。
合规：提交/清除必须等待用户显式确认（--yes 仅限用户对话中确认后由 agent 代执行）。

命令统一签名：commands.<module>.main(paths, cfg, args) -> int（v1.6 结构拆分）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qa.commands import (
    login,
    report_cmd,
    reset,
    run,
    status,
    submit,
    suggest,
    update_knowledge,
)
from qa.config import AppConfig
from qa.paths import QaPaths


def main(argv: list[str] | None = None) -> int:
    paths = QaPaths(Path.cwd())
    cfg = AppConfig()
    parser = argparse.ArgumentParser(prog="qa", description="QuantAlpha CLI")
    sub = parser.add_subparsers(dest="command")

    p_status = sub.add_parser("status", help="启动首查（阶段检测）")
    p_status.set_defaults(func=lambda a: status.main(paths, cfg, a))

    p_login = sub.add_parser(
        "login", help="账号密码登录，写入会话 cookie（替代浏览器复制 cURL）"
    )
    p_login.add_argument("--username", type=str, default=None, help="BRAIN 账号邮箱")
    p_login.add_argument(
        "--password", type=str, default=None, help="BRAIN 账号密码（也可交互输入）"
    )
    p_login.set_defaults(func=lambda a: login.main(paths, cfg, a))

    p_run = sub.add_parser("run", help="完整闭环（读入候选→预检→模拟→筛选→报告）")
    p_run.add_argument(
        "--candidates-file",
        type=str,
        default=None,
        help="候选 JSON 文件路径（默认读当日 data/candidates/YYYY-MM-DD.json）",
    )
    p_run.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="并发模拟数（默认 3；顾问阶段实测平台限流后可调大）",
    )
    p_run.set_defaults(func=lambda a: run.main(paths, cfg, a))

    p_report = sub.add_parser("report", help="查看候选清单/每日汇总/待提交清单")
    report_view = p_report.add_mutually_exclusive_group()
    report_view.add_argument("--daily", action="store_true", help="显示每日汇总")
    report_view.add_argument(
        "--pending",
        action="store_true",
        help="显示待提交暂存清单（含指标 + 相关门排序值；提交仍逐个人工确认）",
    )
    p_report.set_defaults(func=lambda a: report_cmd.main(paths, cfg, a))

    p_knowledge = sub.add_parser(
        "update-knowledge",
        help="按账户抓取字段知识 → 写本地 experience/fields/（首次运行必做，数据不上传）",
    )
    p_knowledge.add_argument(
        "--regions",
        type=str,
        default=None,
        help="区域列表（逗号分隔，默认按账户阶段：用户=USA，顾问=12 区域）",
    )
    p_knowledge.add_argument(
        "--force",
        action="store_true",
        help="强制重新抓取（默认 24 小时内已生成则跳过）",
    )
    p_knowledge.set_defaults(func=lambda a: update_knowledge.main(paths, cfg, a))

    p_suggest = sub.add_parser(
        "suggest", help="随机建议一个研究方向（本地知识库数据集+字段+主题）"
    )
    p_suggest.set_defaults(func=lambda a: suggest.main(paths, cfg, a))

    p_submit = sub.add_parser(
        "submit", help="人工确认后提交 alpha（提交前展示检查 + 回查 ACTIVE）"
    )
    p_submit.add_argument("alpha_id", type=str, help="本地 alpha id（alphas 表主键）")
    p_submit.add_argument(
        "--yes",
        action="store_true",
        help="跳过交互确认（仅限用户在对话中已显式确认后，由 agent 代提交）",
    )
    p_submit.set_defaults(func=lambda a: submit.main(paths, cfg, a))

    p_reset = sub.add_parser(
        "reset", help="清除积累的经验，回到初始状态（保留登录凭证与知识库）"
    )
    p_reset.add_argument(
        "--yes",
        action="store_true",
        help="跳过交互确认（仅限用户在对话中已显式确认后，由 agent 执行）",
    )
    p_reset.set_defaults(func=lambda a: reset.main(paths, cfg, a))

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
