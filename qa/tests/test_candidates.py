"""candidates 单测：候选 JSON 读写往返 + 容错（跳过非法条目）。"""

from __future__ import annotations

import json

import pytest

from qa.candidates import Candidate, load_candidates, write_candidates
from qa.paths import QaPaths

SAMPLE = [
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


def test_write_and_load_roundtrip(tmp_qa):
    path = QaPaths(tmp_qa).CANDIDATES_DIR / "2026-08-14.json"
    cands = [Candidate(**s) for s in SAMPLE]
    write_candidates(path, cands)
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
        json.dumps([{"expression": "rank(close)"}, {"expression": ""}, "junk"]),
        encoding="utf-8",
    )
    loaded = load_candidates(path)
    assert len(loaded) == 1
    assert loaded[0].expression == "rank(close)"
