"""report 单测：候选清单 markdown 渲染 + 每日汇总写入 + 失败归因小节。"""

from __future__ import annotations

from qa.report import (
    format_candidates,
    format_failure_attribution,
    format_pending,
    write_daily_summary,
)

CANDIDATES = [
    {
        "id": "c1",
        "description": "价格动量",
        "hypothesis": "近期涨幅延续，短期动量可预测相对收益",
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


def test_format_candidates_shows_hypothesis():
    text = format_candidates(CANDIDATES)
    assert "设计逻辑" in text
    assert "近期涨幅延续" in text


def test_format_failure_attribution_with_data():
    """阶段 5：归因小节展示 `失败名 ×次数`，按传入顺序。"""
    text = format_failure_attribution(
        [
            {"reason": "LOW_SHARPE", "count": 12},
            {"reason": "LOW_FITNESS", "count": 8},
        ]
    )
    assert text is not None
    assert "失败归因" in text
    assert "LOW_SHARPE ×12" in text
    assert "LOW_FITNESS ×8" in text


def test_format_failure_attribution_empty_hidden():
    """无失败记录 → 返回 None，调用方不显示该小节。"""
    assert format_failure_attribution([]) is None


def test_format_candidates_shows_corr_with_recheck_note():
    """阶段 6：PASS 候选带 corr 时显示相关门栏（标注提交前需复查，防误读）。"""
    cands = [
        {
            "id": "c1",
            "description": "价格动量",
            "expression": "rank(ts_delta(close, 5))",
            "verdict": "PASS",
            "sharpe": 1.5,
            "fitness": 1.2,
            "turnover": 0.2,
            "corr": 0.42,
        }
    ]
    text = format_candidates(cands)
    assert "相关门: 0.42（提交前需复查）" in text


def test_format_candidates_warns_corr_above_gate():
    """corr ≥0.7 时额外标注提交时将被拒（排序值是历史值，非提交值）。"""
    cands = [
        {
            "id": "c1",
            "description": "饱和信号",
            "expression": "rank(close)",
            "verdict": "PASS",
            "sharpe": 1.5,
            "fitness": 1.2,
            "turnover": 0.2,
            "corr": 0.75,
        }
    ]
    text = format_candidates(cands)
    assert "相关门: 0.75（提交前需复查，≥0.7 提交时将被拒）" in text


def test_format_candidates_hides_corr_when_missing():
    """无 corr 值的候选不显示相关门栏（旧记录/查询失败场景）。"""
    text = format_candidates(CANDIDATES)  # CANDIDATES 无 corr 字段
    assert "相关门" not in text


def test_format_pending_shows_metrics_and_corr():
    """qa report --pending 展示 local_id/description/hypothesis/指标/相关门排序。"""
    entries = [
        {
            "id": "h1",
            "description": "价格动量",
            "hypothesis": "近期涨幅延续",
            "expression": "rank(ts_delta(close, 5))",
            "metrics": {"sharpe": 1.5, "fitness": 1.2, "turnover": 0.2},
            "corr": 0.42,
        }
    ]
    text = format_pending(entries)
    assert "待提交清单" in text
    assert "[h1]" in text
    assert "价格动量" in text
    assert "设计逻辑: 近期涨幅延续" in text
    assert "Sharpe=1.5" in text
    assert "相关门: 0.42（提交前需复查）" in text


def test_format_pending_tolerates_legacy_entries():
    """旧格式条目（无 hypothesis/metrics/corr）不报错，缺省字段不显示。"""
    entries = [{"id": "h1", "description": "旧条目"}]
    text = format_pending(entries)
    assert "旧条目" in text
    assert "相关门" not in text


def test_format_failure_attribution_sub_section():
    """阶段 6：提交类归因使用独立标题（模拟失败与提交被拒分开统计）。"""
    text = format_failure_attribution(
        [{"reason": "MAX_CORR", "count": 3}], category="sub"
    )
    assert text is not None
    assert "提交被拒归因" in text
    assert "MAX_CORR ×3" in text


def test_write_daily_summary(tmp_qa):
    from qa.paths import QaPaths

    p = write_daily_summary(CANDIDATES, QaPaths(tmp_qa).REPORTS_DIR, date="2026-08-14")
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "2026-08-14" in content
    assert "价格动量" in content


def test_write_daily_summary_dedup(tmp_qa):
    """同日多次 run：同一表达式与"无通过"标记均不重复追加。"""
    from qa.paths import QaPaths

    r = QaPaths(tmp_qa).REPORTS_DIR
    write_daily_summary(CANDIDATES, r, date="2026-08-14")
    write_daily_summary(CANDIDATES, r, date="2026-08-14")
    content = (r / "daily" / "2026-08-14.md").read_text(encoding="utf-8")
    assert content.count("价格动量") == 1

    write_daily_summary([], r, date="2026-08-15")
    write_daily_summary([], r, date="2026-08-15")
    content2 = (r / "daily" / "2026-08-15.md").read_text(encoding="utf-8")
    assert content2.count("今日无通过候选") == 1
