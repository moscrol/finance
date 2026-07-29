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

TARGET_TABLES = ("fact_sector_daily", "fact_sector_stock_daily")
TARGET_PREFIX = TARGET_TABLES[0][:-5]
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.inventory_only:
        parser.error("only --inventory-only mode is available before the allowlist gate")
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
    payload = {
        "schema_version": 1,
        "records": [asdict(record) for record in records],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"records": len(records)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
