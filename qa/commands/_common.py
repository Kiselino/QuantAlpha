"""run 与 submit 共享的经验沉淀 / 待提交暂存逻辑。"""

from __future__ import annotations

import json
import re
from typing import Any

from qa import knowledge
from qa.paths import QaPaths
from qa.store import Store

# 失败→修复建议映射（来源 knowledge/pitfalls.md「常见失败与修复」表）
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


def _append_pending(paths: QaPaths, entry: dict[str, Any]) -> None:
    """把达标 alpha 追加到待提交暂存 secrets/pending_submits.json（幂等）。

    跨会话接力：run 的 PASS 候选写入后，新会话 agent 启动时主动提示用户提交。
    """
    p = paths.PENDING_SUBMITS
    data: list[dict] = []
    if p.exists():
        try:
            loaded = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                data = loaded
        except ValueError:
            data = []
    if any(e.get("id") == entry.get("id") for e in data if isinstance(e, dict)):
        return
    data.append(entry)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _remove_pending(paths: QaPaths, entry_id: str) -> None:
    """按 id 从待提交暂存删除条目（幂等：文件缺失/解析失败/条目不存在静默返回）。

    qa submit 平台接受提交后调用，避免下次启动误报"有 N 个待提交"。
    """
    p = paths.PENDING_SUBMITS
    if not p.exists():
        return
    try:
        loaded = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return
    if not isinstance(loaded, list):
        return
    data = [e for e in loaded if not (isinstance(e, dict) and e.get("id") == entry_id)]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
