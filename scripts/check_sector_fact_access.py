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
    if not any(table in lowered_sql for table in TARGET_TABLES):
        return []
    lexical_contexts, masked_sql = _lex_sql(sql)
    normalised, normalised_source_indexes = _normalise_sql(masked_sql)
    references: list[tuple[str, str, int]] = []
    for table in TARGET_TABLES:
        qualified_table = rf"(?:[a-z_][\w$]*\.)?{table}"
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
        for match in re.finditer(rf"\b{re.escape(table)}\b", sql, re.IGNORECASE):
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
        for match in re.finditer(rf"\b{re.escape(table)}\b", source_segment, re.IGNORECASE):
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
            for match in re.finditer(
                rf"\b{re.escape(table)}\b", item.string, re.IGNORECASE
            ):
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
    pattern = re.compile(
        rf"{re.escape(TARGET_PREFIX)}(?![A-Za-z0-9_])",
        re.IGNORECASE,
    )
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


def _static_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_string(node.left)
        right = _static_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _dynamic_candidate_nodes(
    tree: ast.AST,
) -> tuple[tuple[ast.AST, tuple[str, ...]], ...]:
    candidates: list[tuple[ast.AST, tuple[str, ...]]] = []
    covered_constants: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp):
            continue
        value = _static_string(node)
        if value is None or TARGET_PREFIX not in value.lower():
            continue
        tables = tuple(table for table in TARGET_TABLES if table in value.lower())
        candidates.append((node, tables or TARGET_TABLES))
        covered_constants.update(
            id(child) for child in ast.walk(node) if isinstance(child, ast.Constant)
        )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in covered_constants
            and TARGET_PREFIX in node.value.lower()
            and not any(table in node.value.lower() for table in TARGET_TABLES)
        ):
            candidates.append((node, TARGET_TABLES))
    return tuple(candidates)


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
                dynamic_candidates = _dynamic_candidate_nodes(tree)
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
                    and any(table in node.value.lower() for table in TARGET_TABLES)
                )
            else:
                dynamic_candidates = ()
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
                for table, mode, source_index in _reference_modes(sql):
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
                        )
                    )
            for node, candidate_tables in dynamic_candidates:
                string_tokens = _string_tokens_for_node(
                    node,
                    source_lines=source_lines,
                    tokens=python_tokens,
                )
                for line, column in _prefix_locations_from_tokens(string_tokens):
                    records.extend(
                        AccessRecord(
                            path=relative_path.as_posix(),
                            line=line,
                            column=column,
                            table=table,
                            mode="unknown",
                        )
                        for table in candidate_tables
                    )
    unique_records = dict.fromkeys(records)
    return tuple(
        sorted(
            unique_records,
            key=lambda row: (row.path, row.line, row.column, row.table, row.mode),
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
