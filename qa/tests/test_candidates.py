"""candidates 单测：候选 JSON 读入 + 容错（跳过非法条目）。"""

from __future__ import annotations

import json
from typing import TypedDict

import pytest

from qa.candidates import Candidate, load_candidates
from qa.paths import QaPaths


class SampleCand(TypedDict):
    description: str
    hypothesis: str
    expression: str
    dataset_ids: list[str]


SAMPLE: list[SampleCand] = [
    {
        "description": "价格动量",
        "hypothesis": "近期涨幅延续",
        "expression": "rank(ts_delta(close, 5))",
        "dataset_ids": ["pv1"],
    },
    {
        "description": "量价背离",
        "hypothesis": "缩量上涨不可持续",
        "expression": "rank(ts_mean(volume, 5))",
        "dataset_ids": ["pv1"],
    },
]


def _write_cands(path, cands: list[SampleCand]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cands, ensure_ascii=False), encoding="utf-8")


def test_load_candidates_from_json(tmp_qa):
    path = QaPaths(tmp_qa).CANDIDATES_DIR / "2026-08-14.json"
    _write_cands(path, SAMPLE)
    loaded = load_candidates(path)
    assert len(loaded) == 2
    assert loaded[0].expression == "rank(ts_delta(close, 5))"
    assert loaded[1].dataset_ids == ["pv1"]


def test_load_missing_raises(tmp_qa):
    path = QaPaths(tmp_qa).CANDIDATES_DIR / "nope.json"
    with pytest.raises(FileNotFoundError):
        load_candidates(path)


def test_load_drops_invalid_entries(tmp_qa):
    path = QaPaths(tmp_qa).CANDIDATES_DIR / "2026-08-14.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([{"expression": ""}, "junk"]),
        encoding="utf-8",
    )
    loaded = load_candidates(path)
    assert len(loaded) == 0


def test_load_drops_missing_hypothesis(tmp_qa):
    """阶段 3 学习机制：无设计逻辑（hypothesis 为空）的候选跳过。"""
    path = QaPaths(tmp_qa).CANDIDATES_DIR / "2026-08-14.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {"description": "无假设", "expression": "rank(close)"},
                {
                    "description": "有假设",
                    "hypothesis": "h",
                    "expression": "rank(volume)",
                },
            ]
        ),
        encoding="utf-8",
    )
    loaded = load_candidates(path)
    assert len(loaded) == 1
    assert loaded[0].expression == "rank(volume)"


def test_load_defaults_language_to_fastexpr(tmp_qa):
    path = QaPaths(tmp_qa).CANDIDATES_DIR / "2026-08-14.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {"hypothesis": "h", "expression": "rank(close)"},
                {"hypothesis": "h", "expression": "rank(volume)", "language": "PYTHON"},
            ]
        ),
        encoding="utf-8",
    )
    loaded = load_candidates(path)
    assert loaded[0].language == "FASTEXPR"
    assert loaded[1].language == "PYTHON"


def test_load_keeps_candidate_settings(tmp_qa):
    path = QaPaths(tmp_qa).CANDIDATES_DIR / "2026-08-14.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {
                    "hypothesis": "h",
                    "expression": "rank(ts_delta(close, 5))",
                    "settings": {"decay": 12, "neutralization": "SECTOR"},
                },
                {"hypothesis": "h", "expression": "rank(close)", "settings": "junk"},
            ]
        ),
        encoding="utf-8",
    )
    loaded = load_candidates(path)
    assert len(loaded) == 2
    assert loaded[0].settings == {"decay": 12, "neutralization": "SECTOR"}
    assert loaded[1].settings == {}
