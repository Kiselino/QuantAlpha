from __future__ import annotations

from qa.validate import (
    check_fields,
    check_syntax,
    expression_hash,
    measure_complexity,
    validate_expression,
)

OPERATORS = {"rank", "ts_rank", "ts_mean", "ts_delta", "group_rank", "vec_avg", "is_nan"}
FIELDS = {"close", "open", "volume", "earnings_est", "cashflow_flag", "assets"}


def test_expression_hash_stable():
    assert expression_hash("rank(close)") == expression_hash("rank(close)")
    assert expression_hash("rank(close)") != expression_hash("rank(open)")


def test_check_syntax_valid():
    assert check_syntax("rank(close)", OPERATORS) == []


def test_check_syntax_unbalanced():
    errs = check_syntax("rank(close", OPERATORS)
    assert any("括号" in e for e in errs)


def test_check_syntax_unknown_operator():
    errs = check_syntax("notanop(close)", OPERATORS)
    assert any("未知算子" in e for e in errs)


def test_check_fields_unknown():
    errs = check_fields("rank(foobar123)", FIELDS)
    assert any("字段" in e for e in errs)


def test_check_fields_valid():
    assert check_fields("rank(close)", FIELDS) == []


def test_measure_complexity():
    cnt, depth = measure_complexity("ts_rank(ts_mean(close, 20), 5)", OPERATORS)
    assert cnt == 2
    assert depth == 2


def test_validate_expression_ok():
    r = validate_expression("rank(close)", OPERATORS, FIELDS)
    assert r.ok is True
    assert r.errors == []


def test_validate_expression_bad():
    r = validate_expression("notanop(close)", OPERATORS, FIELDS)
    assert r.ok is False
    assert len(r.errors) >= 1
