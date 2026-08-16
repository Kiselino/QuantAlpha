"""候选读入（agent 生成的候选 JSON → 项目数据结构）。

生成由对话层 agent 完成：agent 读 knowledge/ 后写 `data/candidates/YYYY-MM-DD.json`，
本项目只读入并执行后续流程（预检/模拟/筛选/报告）。项目内不调用 LLM API。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Candidate:
    description: str = ""
    hypothesis: str = ""
    expression: str = ""
    dataset_ids: list[str] = field(default_factory=list)
    # 可选的模拟参数覆盖（decay/neutralization/truncation；未给则用全局默认）
    settings: dict[str, Any] = field(default_factory=dict)
    # 候选表达式语言（默认 FASTEXPR；PYTHON/ML 由 validate fail-closed 拒绝）
    language: str = "FASTEXPR"


def load_candidates(path: Path) -> list[Candidate]:
    """读取候选 JSON 文件（容错：跳过非法条目）。"""
    if not path.exists():
        raise FileNotFoundError(f"候选文件不存在: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    cands: list[Candidate] = []
    for it in data:
        if not isinstance(it, dict):
            continue
        expr = str(it.get("expression", "")).strip()
        if not expr:
            continue
        hypothesis = str(it.get("hypothesis", "")).strip()
        if not hypothesis:
            # 设计逻辑是学习机制核心（阶段 3）：缺失的候选不进入模拟，防机械生成
            print(f"[candidates] 跳过无设计逻辑（hypothesis 为空）的候选: {expr}")
            continue
        raw_settings = it.get("settings")
        cands.append(
            Candidate(
                description=str(it.get("description", "")),
                hypothesis=hypothesis,
                expression=expr,
                dataset_ids=[str(x) for x in it.get("dataset_ids", [])],
                settings=raw_settings if isinstance(raw_settings, dict) else {},
                language=str(it.get("language", "FASTEXPR")),
            )
        )
    return cands
