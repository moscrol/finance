"""Inventory production SQL access to sector fact tables."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

TARGET_TABLES = ("fact_sector_daily", "fact_sector_stock_daily")
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


@dataclass(frozen=True, slots=True)
class AccessRecord:
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
        normalised.append(character.lower())
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
                    continue
                literals = (
                    (
                        node.value,
                        node.lineno,
                        node.col_offset,
                        ast.get_source_segment(source, node) or node.value,
                    )
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and any(table in node.value.lower() for table in TARGET_TABLES)
                )
            else:
                literals = ((source, 1, 0, source),)
            for sql, starting_line, starting_column, source_segment in literals:
                physical_locations = _physical_locations(
                    source_segment,
                    starting_line=starting_line,
                    starting_column=starting_column,
                )
                for table, mode, source_index in _reference_modes(sql):
                    if physical_locations[table]:
                        line, column = physical_locations[table].pop(0)
                    else:
                        prefix = sql[:source_index]
                        line = starting_line + prefix.count("\n")
                        column = source_index - prefix.rfind("\n")
                    records.append(
                        AccessRecord(
                            path=relative_path.as_posix(),
                            line=line,
                            column=column,
                            table=table,
                            mode=mode,
                        )
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
    records = inventory_sector_fact_access(args.root)
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
