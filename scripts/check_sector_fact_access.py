"""Inventory production SQL access to sector fact tables."""

from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import sys
import tokenize
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

PUBLIC_VIEWS = ("fact_sector_daily", "fact_sector_stock_daily")
# 物理代际表：只允许 sector_universe.py（唯一读写/迁移方）与 sector_schema.sql
# （DDL-only）提及。任何其他文件引用它们都意味着绕过了公开读口的代际隔离。
PHYSICAL_TABLES = (
    "fact_sector_daily_generation",
    "fact_sector_stock_daily_generation",
)
AUTHORIZED_PHYSICAL_PATHS = (
    "market_feature_store/sector_universe.py",
    "market_feature_store/sector_schema.sql",
)
WRITE_MODES = ("insert", "update", "delete", "create", "drop", "alter", "replace")

TARGET_TABLES = (*PHYSICAL_TABLES, *PUBLIC_VIEWS)
# 前缀用于动态拼表名的保守候选检测。两组表名共享 "fact_sector_" 前缀。
TARGET_PREFIX = PUBLIC_VIEWS[0][:-5]
_IDENTIFIER_BOUNDARY = r"[\w$]"
_EXCLUDED_DIR_NAMES = {
    ".cache",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "artifacts",
    "build",
    "cache",
    "caches",
    "dist",
    "node_modules",
    "runtime",
    "tests",
    "tmp",
    "venv",
}


class InventoryScanError(RuntimeError):
    """Fail-closed inventory error exposing only a safe relative path."""

    def __init__(self, path: str, *, error_code: str = "python_syntax_error") -> None:
        self.path = path
        self.error_code = error_code
        message = (
            "unable to parse production Python file"
            if error_code == "python_syntax_error"
            else "unable to map dynamic sector table reference"
        )
        super().__init__(f"{message}: {path}")


@dataclass(frozen=True, slots=True)
class AccessRecord:
    """One occurrence with 1-based Unicode source coordinates.

    For a conservative dynamic-table candidate, ``column`` points to the first
    character of the suspicious target-table literal prefix.
    """

    path: str
    line: int
    column: int
    table: str
    mode: str
    occurrence: int = 1


def _identifier_pattern(value: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!{_IDENTIFIER_BOUNDARY}){re.escape(value)}(?!{_IDENTIFIER_BOUNDARY})", re.IGNORECASE)


def _blank_sql_comments(text: str) -> str:
    """把 SQL 注释内容替换成空格，保留换行，因此行列坐标不变。

    注释里的表名不是访问。``.sql`` 文件整体走原文定位（``_physical_locations``），
    而分类走 ``_lex_sql``——后者正确忽略注释，前者不忽略，于是注释里的提及会以
    mode=unknown 留下记录。schema.sql 里两句"物理存储是 xxx_generation，这里的
    公开表名是只读视图"就因此被判成越权访问。
    """
    out = list(text)
    i = 0
    length = len(text)
    while i < length:
        if text.startswith("--", i):
            while i < length and text[i] != "\n":
                out[i] = " "
                i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            stop = length if end == -1 else end + 2
            while i < stop:
                if text[i] != "\n":
                    out[i] = " "
                i += 1
        elif text[i] in "'\"":
            quote = text[i]
            i += 1
            while i < length and text[i] != quote:
                i += 1
            i += 1
        else:
            i += 1
    return "".join(out)


COMMENT_MODE = "comment"


def _comment_only_positions(source: str) -> frozenset[tuple[str, int, int]]:
    """只出现在注释里的表名位置 (table, line, column)。

    清单要完整记录每一处文本提及（见
    test_inventory_keeps_quoted_and_commented_references_unknown），但注释不是
    访问：schema.sql 里两句"物理存储是 xxx_generation，这里的公开表名是只读视图"
    原先被静态守卫判成越权访问。用注释置空前后的定位差集把两者分开。
    """
    raw = _physical_locations(source, starting_line=1, starting_column=0)
    blanked = _physical_locations(
        _blank_sql_comments(source), starting_line=1, starting_column=0
    )
    positions: set[tuple[str, int, int]] = set()
    for table, found in raw.items():
        survivors = set(blanked.get(table, ()))
        for line, column in found:
            if (line, column) not in survivors:
                positions.add((table, line, column))
    return frozenset(positions)


def _normalise_sql(text: str) -> tuple[str, list[int]]:
    normalised: list[str] = []
    source_indexes: list[int] = []
    in_whitespace = False
    for index, character in enumerate(text):
        if character.isspace():
            if normalised and not in_whitespace:
                normalised.append(" ")
                source_indexes.append(index)
            in_whitespace = True
            continue
        normalised.append(
            chr(ord(character) + 32) if "A" <= character <= "Z" else character
        )
        source_indexes.append(index)
        in_whitespace = False
    return "".join(normalised), source_indexes


def _lex_sql(sql: str) -> tuple[list[tuple[int, str]], str]:
    contexts: list[tuple[int, str]] = [(0, "code")] * len(sql)
    masked = list(sql)
    statement = 0
    state = "code"
    index = 0
    while index < len(sql):
        character = sql[index]
        previous_state = state
        if state == "code":
            if sql.startswith("--", index):
                state = "line_comment"
            elif sql.startswith("/*", index):
                state = "block_comment"
            elif character == "'":
                state = "single_quote"
        contexts[index] = (statement, state)
        if state != "code":
            masked[index] = "\n" if character == "\n" else " "

        if (
            state == "single_quote"
            and previous_state == "single_quote"
            and character == "'"
        ):
            if index + 1 < len(sql) and sql[index + 1] == "'":
                contexts[index + 1] = (statement, state)
                masked[index + 1] = " "
                index += 2
                continue
            state = "code"
        elif state == "line_comment" and character == "\n":
            state = "code"
        elif state == "block_comment" and sql.startswith("*/", index):
            if index + 1 < len(sql):
                contexts[index + 1] = (statement, state)
                masked[index + 1] = " "
            state = "code"
            index += 2
            continue
        elif state == "code" and character == ";":
            statement += 1
        index += 1
    return contexts, "".join(masked)


def _reference_modes(sql: str) -> list[tuple[str, str, int]]:
    lowered_sql = sql.lower()
    if not any(_identifier_pattern(table).search(lowered_sql) for table in TARGET_TABLES):
        return []
    lexical_contexts, masked_sql = _lex_sql(sql)
    normalised, normalised_source_indexes = _normalise_sql(masked_sql)
    references: list[tuple[str, str, int]] = []
    for table in TARGET_TABLES:
        qualified_table = rf"(?:[a-z_][\w$]*\.)?{re.escape(table)}(?!{_IDENTIFIER_BOUNDARY})"
        classifiers = (
            (
                "write",
                re.compile(
                    rf"\b(?:insert\s+into|update|delete\s+from|merge\s+into)\s+{qualified_table}\b"
                ),
            ),
            (
                "ddl",
                re.compile(
                    rf"\b(?:create\s+table(?:\s+if\s+not\s+exists)?|alter\s+table|"
                    rf"drop\s+table(?:\s+if\s+exists)?)\s+{qualified_table}\b|"
                    rf"\bcreate\s+(?:unique\s+)?index(?:\s+if\s+not\s+exists)?\s+\S+\s+on\s+{qualified_table}\b"
                ),
            ),
            ("read", re.compile(rf"\b(?:from|join)\s+{qualified_table}\b")),
        )
        classified_spans = [
            (
                mode,
                (
                    normalised_source_indexes[match.start()],
                    normalised_source_indexes[match.end() - 1] + 1,
                ),
            )
            for mode, pattern in classifiers
            for match in pattern.finditer(normalised)
        ]
        table_references: list[tuple[str, str, int, int, str]] = []
        for match in _identifier_pattern(table).finditer(sql):
            source_index = match.start()
            statement, lexical_context = lexical_contexts[source_index]
            mode = "unknown"
            if lexical_context == "code":
                mode = next(
                    (
                        candidate
                        for candidate, (start, end) in classified_spans
                        if start <= source_index < end
                    ),
                    "unknown",
                )
            table_references.append(
                (table, mode, source_index, statement, lexical_context)
            )
        for statement in {item[3] for item in table_references}:
            known_modes = {
                mode
                for _, mode, _, item_statement, lexical_context in table_references
                if item_statement == statement
                and lexical_context == "code"
                and mode != "unknown"
            }
            if len(known_modes) != 1:
                continue
            inherited_mode = next(iter(known_modes))
            table_references = [
                (
                    name,
                    inherited_mode
                    if mode == "unknown"
                    and item_statement == statement
                    and lexical_context == "code"
                    else mode,
                    source_index,
                    item_statement,
                    lexical_context,
                )
                for name, mode, source_index, item_statement, lexical_context in table_references
            ]
        references.extend(
            (name, mode, source_index)
            for name, mode, source_index, _, _ in table_references
        )
    return references


def _is_excluded(relative_path: Path) -> bool:
    parts = relative_path.parts
    return (
        any(part in _EXCLUDED_DIR_NAMES or "venv" in part.lower() for part in parts[:-1])
        or parts[:2] == ("scripts", "archive")
        or relative_path.name.startswith("test_")
        # selftest 是测试夹具：为自测构造临时库时直接写代际行是合法的（公开表名
        # 已是只读视图，夹具没有别的写法）。计划要求排除测试。
        or relative_path.name.endswith("selftest.py")
        # 守卫自身的常量定义不是访问。不排除会让它永远报告自己违规。
        or relative_path.as_posix() == "scripts/check_sector_fact_access.py"
    )


def _physical_locations(
    source_segment: str,
    *,
    starting_line: int,
    starting_column: int,
) -> dict[str, list[tuple[int, int]]]:
    locations: dict[str, list[tuple[int, int]]] = {table: [] for table in TARGET_TABLES}
    for table in TARGET_TABLES:
        for match in _identifier_pattern(table).finditer(source_segment):
            prefix = source_segment[: match.start()]
            line_offset = prefix.count("\n")
            if line_offset:
                column = match.start() - prefix.rfind("\n")
            else:
                column = starting_column + match.start() + 1
            locations[table].append((starting_line + line_offset, column))
    return locations


def _unicode_column(source_line: str, utf8_byte_column: int) -> int:
    return len(source_line.encode("utf-8")[:utf8_byte_column].decode("utf-8"))


def _string_tokens_for_node(
    node: ast.AST,
    *,
    source_lines: list[str],
    tokens: tuple[tokenize.TokenInfo, ...],
) -> tuple[tokenize.TokenInfo, ...]:
    literal_token_types = {tokenize.STRING}
    if hasattr(tokenize, "FSTRING_MIDDLE"):
        literal_token_types.add(tokenize.FSTRING_MIDDLE)
    start = (
        node.lineno,
        _unicode_column(source_lines[node.lineno - 1], node.col_offset),
    )
    end = (
        node.end_lineno,
        _unicode_column(source_lines[node.end_lineno - 1], node.end_col_offset),
    )
    return tuple(
        item
        for item in tokens
        if item.type in literal_token_types and start <= item.start and item.end <= end
    )


def _physical_locations_from_tokens(
    tokens: tuple[tokenize.TokenInfo, ...],
) -> dict[str, list[tuple[int, int]]]:
    locations: dict[str, list[tuple[int, int]]] = {table: [] for table in TARGET_TABLES}
    for item in tokens:
        for table in TARGET_TABLES:
            for match in _identifier_pattern(table).finditer(item.string):
                prefix = item.string[: match.start()]
                line_offset = prefix.count("\n")
                column = (
                    match.start() - prefix.rfind("\n")
                    if line_offset
                    else item.start[1] + match.start() + 1
                )
                locations[table].append((item.start[0] + line_offset, column))
    return locations


def _prefix_locations_from_tokens(
    tokens: tuple[tokenize.TokenInfo, ...],
) -> tuple[tuple[int, int], ...]:
    locations: list[tuple[int, int]] = []
    pattern = _identifier_pattern(TARGET_PREFIX)
    for item in tokens:
        for match in pattern.finditer(item.string):
            prefix = item.string[: match.start()]
            line_offset = prefix.count("\n")
            column = (
                match.start() - prefix.rfind("\n")
                if line_offset
                else item.start[1] + match.start() + 1
            )
            locations.append((item.start[0] + line_offset, column))
    return tuple(locations)


_UNRESOLVED = object()


@dataclass(frozen=True, slots=True)
class _StaticValue:
    value: str | int
    positions: tuple[tuple[int, int] | None, ...] = ()


_DYNAMIC_HOLE = "\0"


def _constant_source_positions(
    node: ast.Constant,
    *,
    source_lines: list[str],
) -> tuple[tuple[int, int] | None, ...]:
    starting_column = _unicode_column(source_lines[node.lineno - 1], node.col_offset)
    ending_column = _unicode_column(
        source_lines[node.end_lineno - 1], node.end_col_offset
    )
    if node.lineno == node.end_lineno:
        segment = source_lines[node.lineno - 1][starting_column:ending_column]
    else:
        segment = "".join(
            (
                source_lines[line - 1][starting_column:]
                if line == node.lineno
                else source_lines[line - 1][:ending_column]
                if line == node.end_lineno
                else source_lines[line - 1]
            )
            for line in range(node.lineno, node.end_lineno + 1)
        )
    matches = tuple(re.finditer(re.escape(node.value), segment))
    if len(matches) != 1:
        return (None,) * len(node.value)
    segment_offset = matches[0].start()
    starting_column += 1
    positions: list[tuple[int, int]] = []
    for offset in range(len(node.value)):
        prefix = segment[: segment_offset + offset]
        line_offset = prefix.count("\n")
        column = (
            segment_offset + offset - prefix.rfind("\n")
            if line_offset
            else starting_column + segment_offset + offset
        )
        positions.append((node.lineno + line_offset, column))
    return tuple(positions)


def _render_static_format(
    template: _StaticValue,
    args: list[_StaticValue],
    kwargs: dict[str, _StaticValue],
):
    from string import Formatter

    parts: list[str] = []
    positions: list[tuple[int, int] | None] = []
    cursor = 0
    automatic_index = 0
    try:
        fields = tuple(Formatter().parse(str(template.value)))
        for literal, field, format_spec, conversion in fields:
            for character in literal:
                width = 2 if character in "{}" else 1
                if str(template.value)[cursor : cursor + width] != character * width:
                    return _UNRESOLVED
                parts.append(character)
                positions.append(template.positions[cursor])
                cursor += width
            if field is None:
                continue
            if (
                format_spec
                or not re.fullmatch(r"(?:|\d+|[A-Za-z_][A-Za-z0-9_]*)", field)
                or conversion not in {None, "s", "r", "a"}
            ):
                return _UNRESOLVED
            token = "{" + field + (f"!{conversion}" if conversion else "") + "}"
            if str(template.value)[cursor : cursor + len(token)] != token:
                return _UNRESOLVED
            cursor += len(token)
            if not field:
                argument = args[automatic_index] if automatic_index < len(args) else None
                automatic_index += 1
            elif field.isdigit():
                index = int(field)
                argument = args[index] if index < len(args) else None
            else:
                argument = kwargs.get(field)
            if argument is None:
                return _UNRESOLVED
            converter = {"s": str, "r": repr, "a": ascii}.get(conversion, str)
            rendered = converter(argument.value)
            parts.append(rendered)
            if isinstance(argument.value, str) and conversion in {None, "s"}:
                positions.extend(argument.positions)
            else:
                positions.extend((None,) * len(rendered))
        if cursor != len(str(template.value)):
            return _UNRESOLVED
        expected = str(template.value).format(
            *(argument.value for argument in args),
            **{key: argument.value for key, argument in kwargs.items()},
        )
    except (IndexError, KeyError, TypeError, ValueError):
        return _UNRESOLVED
    value = "".join(parts)
    if value != expected or len(value) != len(positions):
        return _UNRESOLVED
    return _StaticValue(value, tuple(positions))


def _safe_static_value(
    node: ast.AST,
    *,
    source_lines: list[str],
):
    def evaluate(current: ast.AST):
        if isinstance(current, ast.Constant) and type(current.value) in {str, int}:
            positions = (
                _constant_source_positions(
                    current,
                    source_lines=source_lines,
                )
                if isinstance(current.value, str)
                else ()
            )
            return _StaticValue(current.value, positions)
        if isinstance(current, ast.BinOp) and isinstance(current.op, ast.Add):
            left, right = evaluate(current.left), evaluate(current.right)
            if all(
                isinstance(value, _StaticValue) and isinstance(value.value, str)
                for value in (left, right)
            ):
                return _StaticValue(
                    left.value + right.value,
                    left.positions + right.positions,
                )
            return _UNRESOLVED
        if isinstance(current, ast.JoinedStr):
            parts: list[str] = []
            positions: list[tuple[int, int] | None] = []
            for item in current.values:
                target = item.value if isinstance(item, ast.FormattedValue) else item
                value = evaluate(target)
                if not isinstance(value, _StaticValue):
                    return _UNRESOLVED
                conversion = item.conversion if isinstance(item, ast.FormattedValue) else -1
                converter = {ord("s"): str, ord("r"): repr, ord("a"): ascii}.get(
                    conversion
                )
                if (
                    isinstance(item, ast.FormattedValue)
                    and (conversion != -1 and converter is None or item.format_spec is not None)
                ):
                    return _UNRESOLVED
                rendered = converter(value.value) if converter else str(value.value)
                parts.append(rendered)
                positions.extend(
                    value.positions
                    if isinstance(value.value, str) and conversion in {-1, ord("s")}
                    else (None,) * len(rendered)
                )
            return _StaticValue("".join(parts), tuple(positions))
        if (
            isinstance(current, ast.Call)
            and isinstance(current.func, ast.Attribute)
            and current.func.attr == "format"
        ):
            template = evaluate(current.func.value)
            args = [evaluate(arg) for arg in current.args]
            if (
                not isinstance(template, _StaticValue)
                or not isinstance(template.value, str)
                or not all(isinstance(value, _StaticValue) for value in args)
            ):
                return _UNRESOLVED
            kwargs: dict[str, _StaticValue] = {}
            for keyword in current.keywords:
                value = evaluate(keyword.value)
                if keyword.arg is None or not isinstance(value, _StaticValue):
                    return _UNRESOLVED
                kwargs[keyword.arg] = value
            return _render_static_format(template, args, kwargs)
        return _UNRESOLVED

    return evaluate(node)


def _is_composite_string_expression(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.BinOp)
        and isinstance(node.op, (ast.Add, ast.Mod))
        or isinstance(node, ast.JoinedStr)
        or (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "format"
        )
    )


def _target_tables_in_static_sql(
    sql: str,
) -> tuple[tuple[str, int, int], ...]:
    occurrences = (
        (table, match.start(), match.end())
        for table in TARGET_TABLES
        for match in _identifier_pattern(table).finditer(sql)
    )
    return tuple(sorted(occurrences, key=lambda occurrence: occurrence[1:]))


def _dynamic_target_candidates(
    node: ast.AST,
    *,
    source_lines: list[str],
) -> tuple[tuple[str, tuple[int, int] | None], ...]:
    def unresolved() -> _StaticValue:
        return _StaticValue(_DYNAMIC_HOLE, (None,))

    def collect(current: ast.AST) -> _StaticValue:
        if isinstance(current, ast.Constant) and isinstance(current.value, str):
            return _StaticValue(
                current.value,
                _constant_source_positions(current, source_lines=source_lines),
            )
        if isinstance(current, ast.BinOp) and isinstance(current.op, ast.Add):
            left, right = collect(current.left), collect(current.right)
            return _StaticValue(str(left.value) + str(right.value), left.positions + right.positions)
        if isinstance(current, ast.BinOp) and isinstance(current.op, ast.Mod):
            left = collect(current.left)
            marker = str(left.value).find("%")
            if marker >= 0:
                return _StaticValue(
                    str(left.value)[:marker] + _DYNAMIC_HOLE + str(left.value)[marker + 2 :],
                    left.positions[:marker] + (None,) + left.positions[marker + 2 :],
                )
            return _StaticValue(str(left.value) + _DYNAMIC_HOLE, left.positions + (None,))
        if isinstance(current, ast.JoinedStr):
            values = (
                collect(item.value) if isinstance(item, ast.FormattedValue) else collect(item)
                for item in current.values
            )
            parts = tuple(values)
            return _StaticValue(
                "".join(str(part.value) for part in parts),
                tuple(position for part in parts for position in part.positions),
            )
        if (
            isinstance(current, ast.Call)
            and isinstance(current.func, ast.Attribute)
            and current.func.attr == "format"
            and isinstance(current.func.value, ast.Constant)
            and isinstance(current.func.value.value, str)
        ):
            template = collect(current.func.value)
            from string import Formatter

            parts: list[_StaticValue] = []
            cursor = 0
            for literal, field, _, _ in Formatter().parse(str(template.value)):
                parts.append(_StaticValue(literal, template.positions[cursor : cursor + len(literal)]))
                cursor += len(literal)
                if field is not None:
                    cursor += len("{" + field + "}")
                    parts.append(unresolved())
            return _StaticValue(
                "".join(str(part.value) for part in parts),
                tuple(position for part in parts for position in part.positions),
            )
        return unresolved()

    value = collect(node)
    candidates: list[tuple[str, tuple[int, int] | None]] = []

    def is_one_literal(start: int, end: int) -> bool:
        positions = value.positions[start:end]
        return all(
            left is not None
            and right is not None
            and left[0] == right[0]
            and left[1] + 1 == right[1]
            for left, right in zip(positions, positions[1:])
        )

    text = str(value.value)
    for table in TARGET_TABLES:
        for start, character in enumerate(text):
            if character != "f":
                continue
            if start and re.fullmatch(_IDENTIFIER_BOUNDARY, text[start - 1]):
                continue
            literal_width = 0
            for end in range(start + 1, len(text) + 1):
                if text[end - 1] != _DYNAMIC_HOLE:
                    literal_width += 1
                if literal_width > len(table):
                    break
                if end < len(text) and re.fullmatch(_IDENTIFIER_BOUNDARY, text[end]):
                    continue
                pattern = re.escape(text[start:end]).replace(
                    _DYNAMIC_HOLE, rf"{_IDENTIFIER_BOUNDARY}*"
                )
                if re.fullmatch(pattern, table) and not is_one_literal(start, end):
                    candidates.append((table, value.positions[start]))
    unique = tuple(dict.fromkeys(candidates))
    return tuple(
        candidate
        for candidate in unique
        if candidate[1] is not None
        or not any(table == candidate[0] and location is not None for table, location in unique)
    )


def _dynamic_candidate_nodes(
    tree: ast.AST,
    *,
    source_lines: list[str],
) -> tuple[
    tuple[
        tuple[ast.AST, _StaticValue, tuple[tuple[str, int, int], ...]],
        ...,
    ],
    tuple[tuple[tuple[str, tuple[int, int] | None], ...], ...],
    frozenset[int],
]:
    composite_nodes = [node for node in ast.walk(tree) if _is_composite_string_expression(node)]
    nested_ids = {
        id(child)
        for node in composite_nodes
        for child in ast.walk(node)
        if child is not node and _is_composite_string_expression(child)
    }
    roots = (node for node in composite_nodes if id(node) not in nested_ids)

    static_candidates: list[
        tuple[ast.AST, _StaticValue, tuple[tuple[str, int, int], ...]]
    ] = []
    dynamic_candidates: list[tuple[tuple[str, tuple[int, int] | None], ...]] = []
    covered_constants: set[int] = set()
    for node in roots:
        value = _safe_static_value(
            node,
            source_lines=source_lines,
        )
        occurrences = (
            _target_tables_in_static_sql(value.value)
            if isinstance(value, _StaticValue) and isinstance(value.value, str)
            else ()
        )
        if occurrences and isinstance(value, _StaticValue):
            static_candidates.append((node, value, occurrences))
            covered_constants.update(
                id(child) for child in ast.walk(node) if isinstance(child, ast.Constant)
            )
        elif value is _UNRESOLVED:
            candidates = _dynamic_target_candidates(node, source_lines=source_lines)
            if candidates and all(location is not None for _, location in candidates):
                dynamic_candidates.append(candidates)
                covered_constants.update(
                    id(child) for child in ast.walk(node) if isinstance(child, ast.Constant)
                )
        else:
            covered_constants.update(
                id(child) for child in ast.walk(node) if isinstance(child, ast.Constant)
            )
    return (
        tuple(static_candidates),
        tuple(dynamic_candidates),
        frozenset(covered_constants),
    )


def inventory_sector_fact_access(root: Path) -> tuple[AccessRecord, ...]:
    """Return a deterministic inventory of production sector-fact SQL references."""
    root = Path(root).resolve()
    records: list[AccessRecord] = []
    for directory, dirnames, filenames in os.walk(root):
        relative_directory = Path(directory).relative_to(root)
        dirnames[:] = sorted(
            name
            for name in dirnames
            if not _is_excluded(relative_directory / name / "placeholder.py")
        )
        for filename in sorted(filenames):
            path = Path(directory) / filename
            relative_path = path.relative_to(root)
            if path.suffix not in {".py", ".sql"} or _is_excluded(relative_path):
                continue
            source = path.read_text(encoding="utf-8")
            sql_comment_positions: frozenset[tuple[str, int, int]] = frozenset()
            if path.suffix == ".py":
                try:
                    tree = ast.parse(source, filename=str(relative_path))
                except SyntaxError:
                    raise InventoryScanError(relative_path.as_posix()) from None
                source_lines = source.splitlines(keepends=True)
                python_tokens = tuple(tokenize.generate_tokens(io.StringIO(source).readline))
                static_candidates, dynamic_candidates, covered_constants = (
                    _dynamic_candidate_nodes(
                        tree,
                        source_lines=source_lines,
                    )
                )
                literals = (
                    (
                        node.value,
                        node.lineno,
                        node.col_offset,
                        _string_tokens_for_node(
                            node,
                            source_lines=source_lines,
                            tokens=python_tokens,
                        ),
                    )
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in covered_constants
                    and any(table in node.value.lower() for table in TARGET_TABLES)
                )
            else:
                static_candidates = ()
                dynamic_candidates = ()
                covered_constants = frozenset()
                literals = ((source, 1, 0, None),)
                # 注释里的表名要照旧记进清单（清单是完整的文本提及记录），但
                # 不能算访问。把注释置空后重新定位，两次结果的差集就是注释提及。
                sql_comment_positions = _comment_only_positions(source)
            for sql, starting_line, starting_column, string_tokens in literals:
                physical_locations = (
                    _physical_locations_from_tokens(string_tokens)
                    if string_tokens is not None
                    else _physical_locations(
                        sql,
                        starting_line=starting_line,
                        starting_column=starting_column,
                    )
                )
                prefix_locations = (
                    list(_prefix_locations_from_tokens(string_tokens))
                    if string_tokens is not None
                    else []
                )
                for occurrence, (table, mode, source_index) in enumerate(
                    _reference_modes(sql), start=1
                ):
                    if physical_locations[table]:
                        line, column = physical_locations[table].pop(0)
                    elif prefix_locations:
                        line, column = prefix_locations.pop(0)
                        mode = "unknown"
                    else:
                        raise InventoryScanError(
                            relative_path.as_posix(),
                            error_code="unmapped_dynamic_table",
                        ) from None
                    if (table, line, column) in sql_comment_positions:
                        mode = COMMENT_MODE
                    records.append(
                        AccessRecord(
                            path=relative_path.as_posix(),
                            line=line,
                            column=column,
                            table=table,
                            mode=mode,
                            occurrence=occurrence,
                        )
                    )
            for _, value, occurrences in static_candidates:
                reference_modes = {
                    (table, source_index): mode
                    for table, mode, source_index in _reference_modes(str(value.value))
                }
                for occurrence, (table, start, _) in enumerate(occurrences, start=1):
                    location = value.positions[start] if start < len(value.positions) else None
                    if location is None:
                        raise InventoryScanError(
                            relative_path.as_posix(),
                            error_code="unmapped_dynamic_table",
                        ) from None
                    line, column = location
                    records.append(
                        AccessRecord(
                            path=relative_path.as_posix(),
                            line=line,
                            column=column,
                            table=table,
                            mode=reference_modes.get((table, start), "unknown"),
                            occurrence=occurrence,
                        )
                    )
            for candidates in dynamic_candidates:
                for occurrence, (table, location) in enumerate(candidates, start=1):
                    if location is None:
                        raise InventoryScanError(
                            relative_path.as_posix(),
                            error_code="unmapped_dynamic_table",
                        ) from None
                    line, column = location
                    records.append(
                        AccessRecord(
                            path=relative_path.as_posix(),
                            line=line,
                            column=column,
                            table=table,
                            mode="unknown",
                            occurrence=occurrence,
                        )
                    )
    return tuple(
        sorted(
            records,
            key=lambda row: (
                row.path,
                row.line,
                row.column,
                row.table,
                row.mode,
                row.occurrence,
            ),
        )
    )


def classify_violations(records: Sequence[AccessRecord]) -> tuple[dict[str, object], ...]:
    """两条不变量。任何一条被破，代际隔离就形同虚设。

    1. 物理代际表只能被 sector_universe.py（唯一读写/迁移方）与 sector_schema.sql
       （DDL-only）提及。别处提及意味着绕过了公开读口的代际过滤，可能把 legacy
       行或被取代代际当成当日事实。
    2. 公开视图只读。写入本来就会被 DuckDB 拒绝，静态拦住是为了不把失败留到运行时。

    刻意**不**实现"拒绝一切 mode=unknown"。实测 110 条 unknown 里绝大多数不是访问：
    表注册表字面量、当参数传递、告警文案里的 "fact_sector_daily has no rows"，以及
    动态拼接的保守候选（``fact_sector_{kind}`` 会同时产出四个候选，其中两个代际表
    名可能压根不会被拼出来）。按字面拒绝会把告警文案和保守候选判成违规。

    因此只对确定是访问的模式判违规：``read`` / ``ddl`` / 各写入模式。
    """
    violations: list[dict[str, object]] = []
    definite = frozenset(("read", "ddl", *WRITE_MODES))
    for record in records:
        if record.table in PHYSICAL_TABLES:
            if record.mode in definite and record.path not in AUTHORIZED_PHYSICAL_PATHS:
                violations.append(
                    {
                        "rule": "physical_table_outside_owner",
                        "path": record.path,
                        "line": record.line,
                        "table": record.table,
                        "mode": record.mode,
                    }
                )
            continue
        if record.mode in WRITE_MODES:
            violations.append(
                {
                    "rule": "write_to_public_view",
                    "path": record.path,
                    "line": record.line,
                    "table": record.table,
                    "mode": record.mode,
                }
            )
    return tuple(violations)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--inventory-only",
        action="store_true",
        help="只写清单，不因违规返回非零",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    args.output.unlink(missing_ok=True)
    try:
        records = inventory_sector_fact_access(args.root)
    except InventoryScanError as exc:
        print(
            json.dumps(
                {"error_code": exc.error_code, "path": exc.path},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    violations = classify_violations(records)
    baseline_path = args.output.parent / f"{args.output.stem}-baseline.json"
    baseline = None
    if baseline_path.is_file():
        try:
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            baseline = None
    payload = {
        "schema_version": 2,
        # candidate 是当前分类清单；baseline 保留改动前的那份，好让每个原始写入方
        # 都可见地被交代过去，而不是悄悄消失。
        "candidate": {
            "records": [asdict(record) for record in records],
            "violations": list(violations),
        },
        "baseline": baseline,
        "records": [asdict(record) for record in records],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"records": len(records), "violations": len(violations)}, sort_keys=True
        )
    )
    if violations and not args.inventory_only:
        for violation in violations:
            print(json.dumps(violation, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
