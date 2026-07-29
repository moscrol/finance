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
    "tests",
    "tmp",
    "venv",
}


@dataclass(frozen=True, slots=True)
class AccessRecord:
    path: str
    line: int
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


def _reference_modes(sql: str) -> list[tuple[str, str, int]]:
    normalised, source_indexes = _normalise_sql(sql)
    references: list[tuple[str, str, int]] = []
    for table in TARGET_TABLES:
        table_pattern = re.compile(rf"\b{re.escape(table)}\b")
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
            (mode, match.span())
            for mode, pattern in classifiers
            for match in pattern.finditer(normalised)
        ]
        table_references: list[tuple[str, str, int]] = []
        for match in table_pattern.finditer(normalised):
            mode = next(
                (
                    candidate
                    for candidate, (start, end) in classified_spans
                    if start <= match.start() < end
                ),
                "unknown",
            )
            table_references.append((table, mode, source_indexes[match.start()]))
        known_modes = {mode for _, mode, _ in table_references if mode != "unknown"}
        if len(known_modes) == 1:
            inherited_mode = next(iter(known_modes))
            table_references = [
                (name, inherited_mode if mode == "unknown" else mode, source_index)
                for name, mode, source_index in table_references
            ]
        references.extend(table_references)
    return references


def _is_excluded(relative_path: Path) -> bool:
    parts = relative_path.parts
    return (
        any(part in _EXCLUDED_DIR_NAMES or "venv" in part.lower() for part in parts[:-1])
        or parts[:2] == ("scripts", "archive")
        or relative_path.name.startswith("test_")
    )


def inventory_sector_fact_access(root: Path) -> tuple[AccessRecord, ...]:
    """Return a deterministic inventory of production sector-fact SQL references."""
    root = Path(root).resolve()
    records: set[AccessRecord] = set()
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
                    (node.value, node.lineno)
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)
                )
            else:
                literals = ((source, 1),)
            for sql, starting_line in literals:
                for table, mode, source_index in _reference_modes(sql):
                    records.add(
                        AccessRecord(
                            path=relative_path.as_posix(),
                            line=starting_line + sql[:source_index].count("\n"),
                            table=table,
                            mode=mode,
                        )
                    )
    return tuple(sorted(records, key=lambda row: (row.path, row.line, row.table, row.mode)))


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
