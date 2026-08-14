"""候选读入（agent 生成的候选 JSON → 项目数据结构）。

生成由对话层 agent 完成：agent 读 knowledge/ 后写 `data/candidates/YYYY-MM-DD.json`，
本项目只读入并执行后续流程（预检/模拟/筛选/报告）。项目内不调用 LLM API。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Candidate:
    description: str = ""
    hypothesis: str = ""
    expression: str = ""
    dataset_ids: list[str] = field(default_factory=list)


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
        cands.append(
            Candidate(
                description=str(it.get("description", "")),
                hypothesis=str(it.get("hypothesis", "")),
                expression=expr,
                dataset_ids=[str(x) for x in it.get("dataset_ids", [])],
            )
        )
    return cands


def write_candidates(path: Path, candidates: list[Candidate]) -> None:
    """把候选列表写入 JSON 文件（供 agent 调用落盘）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {
            "description": c.description,
            "hypothesis": c.hypothesis,
            "expression": c.expression,
            "dataset_ids": list(c.dataset_ids),
        }
        for c in candidates
    ]
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
