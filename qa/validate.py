"""表达式预检（本地，无需交易数据）。

只做：语法 lint、字段白名单、哈希去重、复杂度度量。
不做：任何性能/回测计算（P1 —— 测试只在平台）。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

# 标识符：小写字母/数字/下划线（FASTEXPR 字段与算子命名）
_IDENT = re.compile(r"[a-z][a-z0-9_]*")
# 常量：数字 / 字符串
_CONST = re.compile(r"(-?\d+(?:\.\d+)?|'[^']*'|\"[^\"]*\")")


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    expr_hash: str = ""
    operator_count: int = 0
    nesting_depth: int = 0


def expression_hash(expr: str) -> str:
    """规范化后的 SHA-256 指纹（用于去重）。"""
    norm = re.sub(r"\s+", "", expr)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def _tokenize(expr: str) -> list[str]:
    """极简分词：标识符/常量/括号/逗号/运算符。"""
    tokens: list[str] = []
    i = 0
    n = len(expr)
    while i < n:
        c = expr[i]
        if c.isspace():
            i += 1
            continue
        if c in "(),+-*/<>=!;":
            tokens.append(c)
            i += 1
            continue
        m = _IDENT.match(expr, i)
        if m:
            tokens.append(m.group(0))
            i = m.end()
            continue
        m = _CONST.match(expr, i)
        if m:
            tokens.append("CONST")
            i = m.end()
            continue
        # 未知字符
        tokens.append(c)
        i += 1
    return tokens


def check_syntax(expr: str, operators: set[str]) -> list[str]:
    """语法 lint：括号配对、未知算子、标识符类型。"""
    errors: list[str] = []
    tokens = _tokenize(expr)
    depth = 0
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "(":
            depth += 1
            # 前一个 token 必须是已知算子（函数调用）
            if i == 0:
                errors.append("表达式以 '(' 开头，缺少算子")
            elif tokens[i - 1] not in operators:
                errors.append(f"未知算子: {tokens[i - 1]}")
        elif tok == ")":
            depth -= 1
            if depth < 0:
                errors.append("括号不配对：多余的 ')'")
        i += 1
    if depth != 0:
        errors.append("括号不配对：缺少 ')'")
    if not tokens:
        errors.append("表达式为空")
    return errors


def _enclosing_operator(tokens: list[str], i: int) -> str | None:
    """字段 token 位置 i → 最近包裹它的算子名（无则 None）。

    从后往前扫描括号配对：遇到的第一个未闭合 "(" 即包裹当前 token 的调用。
    """
    depth = 0
    for j in range(i, -1, -1):
        if tokens[j] == ")":
            depth += 1
        elif tokens[j] == "(":
            if depth == 0:
                return tokens[j - 1] if j > 0 else None
            depth -= 1
    return None


def check_fields(
    expr: str,
    fields: set[str],
    field_types: dict[str, str] | None = None,
) -> list[str]:
    """字段白名单：表达式中的标识符必须是字段（算子调用除外）。

    识别规则：标识符后紧跟 '(' 视为算子调用（算子校验由 check_syntax 负责）；
    其余标识符必须是已知字段。
    field_types（v1.4.1）：按平台字段类型拦截非法用法——
    VECTOR 必须位于 vec_* 算子内；GROUP 仅用于 group_* 的 group_by；
    UNIVERSE/SYMBOL 不可用于任何表达式。
    """
    errors: list[str] = []
    tokens = _tokenize(expr)
    for i, tok in enumerate(tokens):
        if not (_IDENT.match(tok) and not _CONST.match(tok)):
            continue
        # 后跟 '(' → 算子调用，跳过（算子存在性由 check_syntax 校验）
        if i + 1 < len(tokens) and tokens[i + 1] == "(":
            continue
        # 命名参数（如 hump(x, hump=0.02)）：标识符后跟 '=' 且再后非 '='（区别于 == 比较）
        if (
            i + 1 < len(tokens)
            and tokens[i + 1] == "="
            and (i + 2 >= len(tokens) or tokens[i + 2] != "=")
        ):
            continue
        if tok not in fields and tok not in {"nan", "inf"}:
            errors.append(f"未知字段: {tok}")
            continue
        ftype = field_types.get(tok) if field_types else None
        if ftype == "UNIVERSE":
            errors.append(f"UNIVERSE 类型字段不可用于表达式: {tok}")
        elif ftype == "SYMBOL":
            errors.append(f"SYMBOL 类型字段不可用于表达式: {tok}")
        elif ftype == "VECTOR":
            op = _enclosing_operator(tokens, i)
            if not op or not op.startswith("vec_"):
                errors.append(f"VECTOR 类型字段需 vec_* 算子转换: {tok}")
        elif ftype == "GROUP":
            op = _enclosing_operator(tokens, i)
            if not op or not op.startswith("group_"):
                errors.append(
                    f"GROUP 类型字段仅用于 group_* 算子的 group_by 参数: {tok}"
                )
    return errors


def measure_complexity(expr: str, operators: set[str]) -> tuple[int, int]:
    """返回 (算子调用数, 最大嵌套深度)。复杂度控制：算子数 ≤ 30、深度 ≤ 8。"""
    tokens = _tokenize(expr)
    count = 0
    max_depth = 0
    depth = 0
    for i, tok in enumerate(tokens):
        if tok == "(" and i > 0 and tokens[i - 1] in operators:
            count += 1
            depth += 1
            max_depth = max(max_depth, depth)
        elif tok == ")":
            depth = max(0, depth - 1)
    return count, max_depth


def validate_expression(
    expr: str,
    operators: set[str],
    fields: set[str],
    field_types: dict[str, str] | None = None,
) -> ValidationResult:
    """综合预检：语法 + 字段（含类型）+ 复杂度。"""
    errors = check_syntax(expr, operators)
    errors += check_fields(expr, fields, field_types)
    op_count, depth = measure_complexity(expr, operators)
    if op_count > 30:
        errors.append(f"表达式过复杂：{op_count} 个算子（上限 30）")
    if depth > 8:
        errors.append(f"嵌套过深：{depth} 层（上限 8）")
    return ValidationResult(
        ok=not errors,
        errors=errors,
        expr_hash=expression_hash(expr),
        operator_count=op_count,
        nesting_depth=depth,
    )
