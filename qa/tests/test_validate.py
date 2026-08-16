"""validate 预检层单测：语法 lint / 字段白名单 / 哈希去重 / 复杂度度量。"""

from __future__ import annotations

from qa.validate import (
    check_fields,
    check_syntax,
    expression_fields,
    expression_hash,
    measure_complexity,
    validate_expression,
    validate_settings,
)

OPERATORS = {
    "rank",
    "ts_rank",
    "ts_mean",
    "ts_delta",
    "group_rank",
    "vec_avg",
    "is_nan",
}
FIELDS = {
    "close",
    "open",
    "volume",
    "earnings_est",
    "cashflow_flag",
    "assets",
    "nws_x",
    "subindustry",
    "top500",
    "sym",
}
# v1.4.1：字段类型检查（VECTOR/GROUP/UNIVERSE/SYMBOL）
FIELD_TYPES = {
    "close": "MATRIX",
    "nws_x": "VECTOR",
    "subindustry": "GROUP",
    "top500": "UNIVERSE",
    "sym": "SYMBOL",
}


def test_expression_hash_stable():
    assert expression_hash("rank(close)") == expression_hash("rank(close)")
    assert expression_hash("rank(close)") != expression_hash("rank(open)")


def test_expression_fields_extracts_fields_only():
    assert expression_fields("rank(ts_delta(close, 5))", OPERATORS) == {"close"}
    assert expression_fields("group_rank(rank(close), subindustry)", OPERATORS) == {
        "close",
        "subindustry",
    }
    assert expression_fields("hump(volume, hump=0.02)", OPERATORS) == {"volume"}


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


def test_vector_field_rejected_in_scalar_context():
    errs = check_fields("rank(nws_x)", FIELDS, FIELD_TYPES)
    assert any("VECTOR" in e for e in errs)


def test_vector_field_ok_inside_vec_operator():
    assert check_fields("vec_avg(nws_x)", FIELDS, FIELD_TYPES) == []


def test_group_field_ok_inside_group_operator():
    assert (
        check_fields("group_rank(rank(close), subindustry)", FIELDS, FIELD_TYPES) == []
    )


def test_group_field_rejected_in_scalar_context():
    errs = check_fields("rank(subindustry)", FIELDS, FIELD_TYPES)
    assert any("GROUP" in e for e in errs)


def test_universe_and_symbol_fields_rejected():
    errs = check_fields("rank(top500)", FIELDS, FIELD_TYPES)
    assert any("UNIVERSE" in e for e in errs)
    errs = check_fields("rank(sym)", FIELDS, FIELD_TYPES)
    assert any("SYMBOL" in e for e in errs)


def test_field_types_optional_backward_compatible():
    assert check_fields("rank(nws_x)", FIELDS) == []  # 不传类型映射 → 只查存在性


def test_validate_settings_ok_empty_and_full():
    assert validate_settings({}) == []
    assert (
        validate_settings({"decay": 12, "neutralization": "SECTOR", "truncation": 0.05})
        == []
    )


def test_validate_settings_bad_decay():
    assert any("decay" in e for e in validate_settings({"decay": -1}))
    assert any("decay" in e for e in validate_settings({"decay": 3.5}))
    assert any("decay" in e for e in validate_settings({"decay": "10"}))


def test_validate_settings_bad_truncation():
    assert any("truncation" in e for e in validate_settings({"truncation": 1.5}))
    assert any("truncation" in e for e in validate_settings({"truncation": -0.1}))


def test_validate_settings_bad_neutralization():
    assert any(
        "neutralization" in e for e in validate_settings({"neutralization": "XYZ"})
    )


def test_validate_settings_unknown_key():
    assert any("未知" in e for e in validate_settings({"hump": 0.02}))
