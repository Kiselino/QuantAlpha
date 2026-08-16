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


# ---- v1.6 阶段 3：language 字段校验（fail-closed）----


def test_validate_expression_language_default_fastexpr():
    assert validate_expression("rank(close)", OPERATORS, FIELDS).ok is True


def test_validate_expression_rejects_python():
    r = validate_expression("rank(close)", OPERATORS, FIELDS, language="PYTHON")
    assert r.ok is False
    assert any("暂不支持本地预检" in e for e in r.errors)
    assert any("FASTEXPR" in e for e in r.errors)


def test_validate_expression_rejects_ml():
    r = validate_expression("rank(close)", OPERATORS, FIELDS, language="ML")
    assert r.ok is False
    assert any("暂不支持本地预检" in e for e in r.errors)


# ---- v1.6 阶段 3：算子白名单补全（67 全集，含官方确认的 14 个新算子）----

NEW_OPERATOR_EXAMPLES = [
    "signed_power(close, 0.5)",
    "reverse(close)",
    "densify(subindustry)",
    "kth_element(close, 20, 1)",
    "ts_step(1)",
    "days_from_last_change(close)",
    "ts_count_nans(close, 5)",
    "ts_covariance(close, open, 5)",
    "ts_product(close, 5)",
    "ts_regression(close, ts_step(1), 60)",
    "last_diff_value(close, 63)",
    "vector_neut(open, close)",
    "trade_when(volume >= ts_mean(volume, 5), rank(-returns), -1)",
    'bucket(rank(close), range="0,1,0.1")',
]


def test_operator_whitelist_full_set():
    from qa.commands.run import _load_operators

    assert len(_load_operators()) == 67


def test_new_operators_parseable_by_whitelist():
    from qa.commands.run import _load_operators

    ops = _load_operators()
    for expr in NEW_OPERATOR_EXAMPLES:
        errs = check_syntax(expr, ops)
        assert errs == [], f"{expr}: {errs}"


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
