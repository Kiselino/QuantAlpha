"""qa reset 命令：清除积累的经验，回到初始状态（保留登录凭证与知识库）。"""

from __future__ import annotations

from qa import knowledge
from qa.config import AppConfig
from qa.paths import QaPaths


def _cmd_reset(paths: QaPaths, yes: bool = False) -> int:
    """清除积累的经验，回到项目初始状态（合规：保留登录凭证与静态知识库）。

    清除：qa.db、audit/、candidates/、reports/daily/、pending_submits.json、
    playbook/failures 的沉淀段落（恢复模板）。
    保留：secrets/ 下 cookie 与 account_info（登录凭证）、knowledge/ 静态知识库。
    """
    targets = {
        "qa.db（模拟/提交/经验全部记录）": paths.DB,
        "审计日志 data/audit/": paths.AUDIT_DIR,
        "候选文件 data/candidates/": paths.CANDIDATES_DIR,
        "每日汇总 reports/daily/": paths.REPORTS_DIR / "daily",
    }
    pending = paths.PENDING_SUBMITS
    if pending.exists():
        targets["待提交暂存 pending_submits.json"] = pending

    print("[reset] 将清除以下经验积累（回到初始状态）：")
    for label, p in targets.items():
        print(f"  - {label} ({p})")
    if pending.exists():
        print("  ⚠️ 待提交暂存含未提交 alpha，清除后需重新模拟生成")
    print(
        "[reset] 同时恢复：experience/playbook.md、failures.md 为模板（本地经验沉淀）"
    )
    print(
        "[reset] 保留：secrets/ 登录凭证、knowledge/ 公开知识库、"
        "experience/fields/ 账户字段知识、qa/ 代码"
    )

    if yes:
        confirmed = True
    else:
        try:
            confirmed = input("确认清除？(y/N): ").strip().lower() in ("y", "yes")
        except EOFError:
            print("[reset] 非交互环境请使用 --yes（确认后由 agent 执行）。")
            return 1
    if not confirmed:
        print("[reset] 已取消。")
        return 0

    for label, p in targets.items():
        if p.is_dir():
            for f in p.glob("*"):
                f.unlink(missing_ok=True)
            print(f"  ✓ 已清空 {label}")
        elif p.exists():
            p.unlink()
            print(f"  ✓ 已删除 {label}")
    knowledge.restore_experience_templates(paths)
    print("  ✓ experience/playbook.md、failures.md 已恢复模板")
    print("[reset] 完成。项目已回到初始状态，可重新开始生成/模拟。")
    return 0


def main(paths: QaPaths, cfg: AppConfig, args) -> int:
    """命令入口：qa reset（argparse 分发）。"""
    return _cmd_reset(paths, args.yes)
