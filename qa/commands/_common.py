"""命令间共享的私有工具：经验沉淀 / 待提交暂存 / cookie 读取 / 交互确认 / 账号阶段缓存。

各命令（run/submit/status/login/report/reset/update-knowledge）共用同一份逻辑，
避免同款模板在多个命令文件里重复。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from qa import knowledge
from qa.paths import QaPaths
from qa.stage import StageInfo, read_cookie
from qa.store import Store

# 失败→修复建议映射（来源 document/reference/pitfalls.md「常见失败与修复」表）
_FAILURE_FIX_SUGGESTIONS = {
    "LOW_SHARPE": "延长 lookback / 换基本面字段 / 黄金组合",
    "HIGH_TURNOVER": "增大 decay（技术 10-30）或 ts_rank 平滑",
    "LOW_SUB_UNIVERSE_SHARPE": "去规模乘子；流动部分分开 decay",
    "CONCENTRATED_WEIGHT": "降 truncation；检查覆盖（ts_backfill）",
    "LOW_FITNESS": "通常由高换手导致——先降 turnover",
}


def _failure_fix_suggestion(failure_reason: str) -> str:
    """从失败原因文本中匹配已知失败名，返回其修复建议（多个用'；'连接）。

    大小写不敏感整词匹配（'SHARPE' 不会误中 'LOW_SHARPE' 内部）；
    无匹配返回空串（未知失败名不加建议，保持条目格式稳定）。
    """
    hits = [
        fix
        for name, fix in _FAILURE_FIX_SUGGESTIONS.items()
        if re.search(rf"\b{name}\b", failure_reason, re.IGNORECASE)
    ]
    return "；".join(hits)


def _require_cookie(paths: QaPaths, prefix: str) -> str | None:
    """读取会话 cookie；文件缺失时打印错误并返回 None（命令据此早退 return 1）。"""
    try:
        return read_cookie(paths.COOKIE)
    except FileNotFoundError as e:
        print(f"[{prefix}] 错误: {e}")
        return None


def _load_pending(
    paths: QaPaths, prefix: str = "pending"
) -> list[dict[str, Any]] | None:
    """统一读取待提交暂存 secrets/pending_submits.json。

    文件不存在 → None（调用方打印各自的空态文案，保留现有输出）；
    JSON 损坏或非数组 → 打印一行损坏提示并返回 None（不静默当空，
    避免达标 alpha 暂存丢失却不被发现）。
    """
    p = paths.PENDING_SUBMITS
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        print(
            f"[{prefix}] 待提交暂存文件损坏：pending_submits.json 无法解析"
            "（请修复或删除该文件，qa run 会重新写入）"
        )
        return None
    if not isinstance(data, list):
        print(
            f"[{prefix}] 待提交暂存格式异常：pending_submits.json 应为 JSON 数组"
            "（请修复或删除该文件，qa run 会重新写入）"
        )
        return None
    return [e for e in data if isinstance(e, dict)]


def _append_pending(
    paths: QaPaths, entry: dict[str, Any], prefix: str = "pending"
) -> None:
    """把达标 alpha 追加到待提交暂存 secrets/pending_submits.json（幂等）。

    跨会话接力：run 的 PASS 候选写入后，新会话 agent 启动时主动提示用户提交。
    文件损坏时 _load_pending 已打印提示，这里从空列表重建（自愈）。
    """
    p = paths.PENDING_SUBMITS
    data: list[dict] = []
    loaded = _load_pending(paths, prefix)
    if loaded is not None:
        data = loaded
    if any(e.get("id") == entry.get("id") for e in data if isinstance(e, dict)):
        return
    data.append(entry)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _remove_pending(paths: QaPaths, entry_id: str, prefix: str = "pending") -> None:
    """按 id 从待提交暂存删除条目（幂等：文件缺失/解析失败/条目不存在静默返回）。

    qa submit 平台接受提交后调用，避免下次启动误报"有 N 个待提交"。
    """
    p = paths.PENDING_SUBMITS
    loaded = _load_pending(paths, prefix)
    if loaded is None:
        return
    data = [e for e in loaded if e.get("id") != entry_id]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _confirm_or_yes(prompt: str, yes: bool, prefix: str) -> bool | None:
    """交互确认统一封装（reset/submit 共用）。

    返回 True=已确认、False=用户取消（调用方打印"已取消"）、
    None=非交互 EOF（已打印 --yes 指引，调用方应返回 1）。
    """
    if yes:
        return True
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except EOFError:
        print(f"[{prefix}] 非交互环境请使用 --yes（确认后由 agent 执行）。")
        return None


def _save_account_info(paths: QaPaths, stage: StageInfo) -> None:
    """登录成功后写账户阶段摘要到 secrets/account_info.json。

    只存阶段摘要（level/资格/区域/语言/时间），不含密码与分数明细；
    status 在 cookie 失效时读作离线阶段缓存。
    """
    info = {
        "level": stage.level,
        "is_consultant": stage.is_consultant,
        "regions": list(stage.regions),
        "languages": list(stage.expression_languages),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    paths.ACCOUNT_INFO.parent.mkdir(parents=True, exist_ok=True)
    paths.ACCOUNT_INFO.write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _sediment_lesson(
    paths: QaPaths, store: Store, entry: dict[str, Any], title: str, body: str
) -> None:
    """经验沉淀：SQLite lessons + experience/playbook.md（幂等，按 entry id 去重）。"""
    store.save_lesson(entry)
    knowledge.append_experience(paths, "lesson", entry.get("id", ""), title, body)


def _sediment_failure(
    paths: QaPaths, store: Store, entry: dict[str, Any], title: str, body: str
) -> None:
    """证伪沉淀：SQLite failures + experience/failures.md（幂等，按 entry id 去重）。

    阶段 5 增强：按 failure_reason 中的失败名查知识库映射表，给出一句修复建议
    追加到 failures.md 条目（无映射失败名不加建议）。
    """
    suggestion = _failure_fix_suggestion(entry.get("failure_reason", ""))
    if suggestion:
        body = f"{body}\n- 修复建议: {suggestion}"
    store.save_failure(entry)
    knowledge.append_experience(paths, "failure", entry.get("id", ""), title, body)
