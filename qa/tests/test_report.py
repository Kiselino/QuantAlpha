from __future__ import annotations

from qa.report import format_candidates, write_daily_summary

CANDIDATES = [
    {
        "id": "c1",
        "description": "价格动量",
        "expression": "rank(ts_delta(close, 5))",
        "verdict": "PASS",
        "sharpe": 1.5,
        "fitness": 1.2,
        "turnover": 0.2,
    },
    {
        "id": "c2",
        "description": "量价背离",
        "expression": "rank(ts_mean(volume, 5))",
        "verdict": "FAIL",
        "reason": "Sharpe 0.80 < 1.25",
        "sharpe": 0.8,
        "fitness": 0.9,
        "turnover": 0.3,
    },
]


def test_format_candidates_contains_fields():
    text = format_candidates(CANDIDATES)
    assert "价格动量" in text
    assert "rank(ts_delta(close, 5))" in text
    assert "PASS" in text
    assert "Sharpe 0.80" in text


def test_write_daily_summary(tmp_qa):
    from qa.paths import QaPaths

    p = write_daily_summary(CANDIDATES, QaPaths(tmp_qa).REPORTS_DIR, date="2026-08-14")
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "2026-08-14" in content
    assert "价格动量" in content
