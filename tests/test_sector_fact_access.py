from __future__ import annotations

import json

import pytest

from scripts import check_sector_fact_access as access_inventory
from scripts.check_sector_fact_access import inventory_sector_fact_access


def test_inventory_sector_fact_access_classifies_literal_reads_and_writes(tmp_path) -> None:
    (tmp_path / "reader.py").write_text(
        'SQL = "select * from fact_sector_daily where trade_date = ?"\n',
        encoding="utf-8",
    )
    (tmp_path / "writer.py").write_text(
        'SQL = "insert into fact_sector_stock_daily values (?, ?, ?)"\n',
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.table, record.mode) for record in records] == [
        ("fact_sector_daily", "read"),
        ("fact_sector_stock_daily", "write"),
    ]


def test_inventory_includes_ddl_and_unknown_but_excludes_nonproduction_paths(tmp_path) -> None:
    (tmp_path / "schema.sql").write_text(
        "CREATE INDEX idx_sector_date ON fact_sector_daily(trade_date);\n",
        encoding="utf-8",
    )
    (tmp_path / "metadata.py").write_text(
        'TABLE = "fact_sector_stock_daily"\n',
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_ignored.py").write_text(
        'SQL = "delete from fact_sector_daily"\n',
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "archive").mkdir(parents=True)
    (tmp_path / "scripts" / "archive" / "ignored.sql").write_text(
        "drop table fact_sector_stock_daily;\n",
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.path, record.table, record.mode) for record in records] == [
        ("metadata.py", "fact_sector_stock_daily", "unknown"),
        ("schema.sql", "fact_sector_daily", "ddl"),
    ]


def test_inventory_classifies_qualified_reads_and_repeated_upsert_targets(tmp_path) -> None:
    (tmp_path / "qualified.sql").write_text(
        "select * from db.fact_sector_stock_daily;\n",
        encoding="utf-8",
    )
    (tmp_path / "upsert.py").write_text(
        'SQL = """insert into fact_sector_daily values (?)\n'
        "on conflict do update set amount =\n"
        'coalesce(fact_sector_daily.amount, excluded.amount)"""\n',
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.path, record.line, record.table, record.mode) for record in records] == [
        ("qualified.sql", 1, "fact_sector_stock_daily", "read"),
        ("upsert.py", 1, "fact_sector_daily", "write"),
        ("upsert.py", 3, "fact_sector_daily", "write"),
    ]


def test_inventory_reports_physical_lines_for_adjacent_string_literals(tmp_path) -> None:
    (tmp_path / "adjacent.py").write_text(
        "SQL = (\n"
        '    "select * "\n'
        '    "from fact_sector_daily "\n'
        '    "join "\n'
        '    "fact_sector_stock_daily on true"\n'
        ")\n",
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.table, record.line) for record in records] == [
        ("fact_sector_daily", 3),
        ("fact_sector_stock_daily", 5),
    ]


def test_inventory_preserves_repeated_occurrences_on_the_same_line(tmp_path) -> None:
    (tmp_path / "self_join.sql").write_text(
        "SELECT * FROM fact_sector_daily a JOIN fact_sector_daily b ON a.trade_date = b.trade_date;\n",
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.table, record.mode) for record in records] == [
        ("fact_sector_daily", "read"),
        ("fact_sector_daily", "read"),
    ]


def test_inventory_does_not_inherit_mode_across_sql_statements(tmp_path) -> None:
    (tmp_path / "statements.sql").write_text(
        "SELECT * FROM fact_sector_daily;\n"
        "SELECT 'fact_sector_daily';\n",
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.line, record.mode) for record in records] == [
        (1, "read"),
        (2, "unknown"),
    ]


def test_inventory_keeps_quoted_and_commented_references_unknown(tmp_path) -> None:
    (tmp_path / "comments.sql").write_text(
        "SELECT 'fact_sector_daily', * FROM fact_sector_daily;\n"
        "-- FROM fact_sector_daily\n"
        "/* JOIN fact_sector_stock_daily */\n",
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.line, record.table, record.mode) for record in records] == [
        (1, "fact_sector_daily", "unknown"),
        (1, "fact_sector_daily", "read"),
        (2, "fact_sector_daily", "unknown"),
        (3, "fact_sector_stock_daily", "unknown"),
    ]


def test_inventory_excludes_nested_runtime_directories(tmp_path) -> None:
    (tmp_path / "reader.py").write_text(
        'SQL = "select * from fact_sector_daily"\n',
        encoding="utf-8",
    )
    (tmp_path / "generated" / "runtime" / "nested").mkdir(parents=True)
    (tmp_path / "generated" / "runtime" / "nested" / "ignored.py").write_text(
        'SQL = "delete from fact_sector_stock_daily"\n',
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.path, record.table) for record in records] == [
        ("reader.py", "fact_sector_daily"),
    ]


def test_inventory_ignores_python_comments_between_adjacent_strings(tmp_path) -> None:
    (tmp_path / "commented_adjacent.py").write_text(
        "SQL = (\n"
        '    "select * "\n'
        "    # fact_sector_daily label only\n"
        '    "from fact_sector_daily"\n'
        ")\n",
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.table, record.line) for record in records] == [
        ("fact_sector_daily", 4),
    ]


def test_inventory_column_is_one_based_unicode_for_python_strings(tmp_path) -> None:
    (tmp_path / "unicode_string.py").write_text(
        '前缀 = "值"; SQL = "中文 FROM fact_sector_daily"\n',
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.table, record.line, record.column) for record in records] == [
        ("fact_sector_daily", 1, 26),
    ]


def test_inventory_maps_only_static_fstring_segments_to_unicode_columns(tmp_path) -> None:
    (tmp_path / "unicode_fstring.py").write_text(
        '前缀 = "值"; SQL = f"中文 {fact_sector_daily} FROM fact_sector_stock_daily"\n',
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.table, record.line, record.column) for record in records] == [
        ("fact_sector_stock_daily", 1, 47),
    ]


def test_inventory_fails_closed_on_production_python_syntax_errors(
    tmp_path, capsys
) -> None:
    canary = "SECRET_SOURCE_CANARY"
    (tmp_path / "broken.py").write_text(
        'SQL = "select * from fact_sector_daily"\n'
        f"{canary} = (\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError) as caught:
        inventory_sector_fact_access(tmp_path)

    assert type(caught.value).__name__ == "InventoryScanError"
    assert str(caught.value) == "unable to parse production Python file: broken.py"
    assert canary not in str(caught.value)

    output = tmp_path / "inventory.json"
    output.write_text("stale inventory", encoding="utf-8")
    exit_code = access_inventory.main(
        ["--root", str(tmp_path), "--inventory-only", "--output", str(output)]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert canary not in captured.err
    assert json.loads(captured.err) == {
        "error_code": "python_syntax_error",
        "path": "broken.py",
    }
    assert not output.exists()


def test_inventory_records_conservative_dynamic_table_candidates(tmp_path) -> None:
    (tmp_path / "concat.py").write_text(
        'SQL = "fact_sector_" + "daily"\n',
        encoding="utf-8",
    )
    (tmp_path / "format.py").write_text(
        'SQL = "SELECT * FROM fact_sector_{}".format(kind)\n',
        encoding="utf-8",
    )
    (tmp_path / "fstring.py").write_text(
        'SQL = f"SELECT * FROM fact_sector_{kind}"\n',
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [
        (record.path, record.line, record.column, record.table, record.mode)
        for record in records
    ] == [
        ("concat.py", 1, 8, "fact_sector_daily", "unknown"),
        ("format.py", 1, 22, "fact_sector_daily", "unknown"),
        ("format.py", 1, 22, "fact_sector_stock_daily", "unknown"),
        ("fstring.py", 1, 23, "fact_sector_daily", "unknown"),
        ("fstring.py", 1, 23, "fact_sector_stock_daily", "unknown"),
    ]


def test_inventory_exact_target_columns_ignore_preceding_escape_width(tmp_path) -> None:
    (tmp_path / "escaped_prefix.py").write_text(
        'HEX = "\\x20SELECT * FROM fact_sector_daily"\n'
        'OCT = "\\040SELECT * FROM fact_sector_stock_daily"\n'
        'UNI = "\\u0020SELECT * FROM fact_sector_daily"\n',
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.line, record.column, record.table, record.mode) for record in records] == [
        (1, 26, "fact_sector_daily", "read"),
        (2, 26, "fact_sector_stock_daily", "read"),
        (3, 28, "fact_sector_daily", "read"),
    ]


def test_inventory_marks_escaped_or_split_targets_as_unknown_candidates(tmp_path) -> None:
    (tmp_path / "derived_targets.py").write_text(
        'ESCAPED = "SELECT * FROM fact_sector_\\x64aily"\n'
        'SPLIT = "SELECT * FROM fact_sector_" "daily"\n',
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.line, record.column, record.table, record.mode) for record in records] == [
        (1, 26, "fact_sector_daily", "unknown"),
        (2, 24, "fact_sector_daily", "unknown"),
    ]


def test_inventory_sql_normalisation_preserves_unicode_source_indexes(tmp_path) -> None:
    (tmp_path / "unicode.sql").write_text(
        "İ SELECT * FROM fact_sector_daily",
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.line, record.column, record.table, record.mode) for record in records] == [
        (1, 17, "fact_sector_daily", "read"),
    ]


def test_inventory_safely_evaluates_maximal_static_string_expressions(tmp_path) -> None:
    (tmp_path / "concat.py").write_text(
        'SQL = "SELECT * FROM fact_" + "sector_daily"\n',
        encoding="utf-8",
    )
    (tmp_path / "format.py").write_text(
        'SQL = "SELECT * FROM fact_{}_daily".format("sector")\n',
        encoding="utf-8",
    )
    (tmp_path / "fstring.py").write_text(
        'SQL = f"SELECT * FROM fact_{\'sector\'}_daily"\n',
        encoding="utf-8",
    )
    (tmp_path / "nested.py").write_text(
        "SQL = (\n"
        '    ("SELECT * FROM " + "fact_")\n'
        '    + ("sector_" + "daily")\n'
        ")\n",
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [
        (record.path, record.line, record.column, record.table, record.mode)
        for record in records
    ] == [
        ("concat.py", 1, 22, "fact_sector_daily", "read"),
        ("format.py", 1, 22, "fact_sector_daily", "read"),
        ("fstring.py", 1, 23, "fact_sector_daily", "read"),
        ("nested.py", 2, 26, "fact_sector_daily", "read"),
    ]


def test_inventory_preserves_static_add_occurrences_and_source_locations(tmp_path) -> None:
    (tmp_path / "repeated.py").write_text(
        'SQL = "SELECT * FROM fact_" + "sector_daily a JOIN fact_sector_daily b"\n',
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [
        (record.line, record.column, record.table, record.mode) for record in records
    ] == [
        (1, 22, "fact_sector_daily", "read"),
        (1, 52, "fact_sector_daily", "read"),
    ]


def test_inventory_maps_static_add_to_the_contributing_target_fragment(tmp_path) -> None:
    (tmp_path / "unrelated_prefix.py").write_text(
        'SQL = "SELECT fact_x, * FROM " + "fact_" + "sector_daily"\n',
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [
        (record.line, record.column, record.table, record.mode) for record in records
    ] == [
        (1, 35, "fact_sector_daily", "read"),
    ]


def test_inventory_static_expression_boundaries_avoid_unrelated_tables(tmp_path) -> None:
    (tmp_path / "concat_other.py").write_text(
        'SQL = "SELECT * FROM fact_" + "sector_theme_daily"\n',
        encoding="utf-8",
    )
    (tmp_path / "format_other.py").write_text(
        'SQL = "SELECT * FROM fact_{}_daily".format("sector_theme")\n',
        encoding="utf-8",
    )
    (tmp_path / "fstring_other.py").write_text(
        'SQL = f"SELECT * FROM fact_{\'sector_theme\'}_daily"\n',
        encoding="utf-8",
    )
    (tmp_path / "unrelated.py").write_text(
        'SQL = f"unrelated_fact_sector_{kind}"\n',
        encoding="utf-8",
    )

    assert inventory_sector_fact_access(tmp_path) == ()


def test_inventory_preserves_nested_dynamic_sector_candidates(tmp_path) -> None:
    (tmp_path / "suffix.py").write_text(
        'SQL = ("SELECT * FROM fact_" + "sector_daily") + suffix\n',
        encoding="utf-8",
    )
    (tmp_path / "prefix.py").write_text(
        'SQL = prefix + ("fact_" + "sector_daily")\n',
        encoding="utf-8",
    )
    (tmp_path / "fstring.py").write_text(
        'SQL = "fact_" + f"sector_{kind}"\n',
        encoding="utf-8",
    )
    (tmp_path / "percent.py").write_text(
        'SQL = "fact_sector_%s" % kind\n',
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.path, record.column, record.table, record.mode) for record in records] == [
        ("fstring.py", 8, "fact_sector_daily", "unknown"),
        ("fstring.py", 8, "fact_sector_stock_daily", "unknown"),
        ("percent.py", 8, "fact_sector_daily", "unknown"),
        ("percent.py", 8, "fact_sector_stock_daily", "unknown"),
        ("prefix.py", 18, "fact_sector_daily", "unknown"),
        ("suffix.py", 23, "fact_sector_daily", "unknown"),
    ]


def test_inventory_matches_dynamic_holes_inside_sector_identifiers(tmp_path) -> None:
    (tmp_path / "fstring.py").write_text(
        'SQL = f"SELECT * FROM fact_sector_{kind}_daily"\n',
        encoding="utf-8",
    )
    (tmp_path / "format.py").write_text(
        'SQL = "SELECT * FROM fact_sector_{}_daily".format(kind)\n',
        encoding="utf-8",
    )
    (tmp_path / "concat.py").write_text(
        'SQL = "fact_" + f"sector_{kind}_daily"\n',
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.path, record.table, record.mode) for record in records] == [
        ("concat.py", "fact_sector_stock_daily", "unknown"),
        ("format.py", "fact_sector_stock_daily", "unknown"),
        ("fstring.py", "fact_sector_stock_daily", "unknown"),
    ]


def test_inventory_preserves_reused_static_format_occurrences(tmp_path) -> None:
    (tmp_path / "reused.py").write_text(
        'SQL = "SELECT * FROM {0} a JOIN {0} b".format("fact_sector_daily")\n',
        encoding="utf-8",
    )

    records = inventory_sector_fact_access(tmp_path)

    assert [(record.table, record.mode, record.occurrence) for record in records] == [
        ("fact_sector_daily", "read", 1),
        ("fact_sector_daily", "read", 2),
    ]
    assert (records[0].line, records[0].column) == (records[1].line, records[1].column)


def test_inventory_static_identifier_boundaries_include_unicode_and_dollar(tmp_path) -> None:
    (tmp_path / "static.py").write_text(
        'PREFIX = "中文fact_sector_daily"\n'
        'SUFFIX = "fact_sector_stock_daily中文"\n'
        'DOLLAR = "fact_sector_daily$archive"\n',
        encoding="utf-8",
    )

    assert inventory_sector_fact_access(tmp_path) == ()


def test_inventory_dynamic_identifier_boundaries_include_unicode_and_dollar(tmp_path) -> None:
    (tmp_path / "dynamic.py").write_text(
        'PREFIX = f"中文fact_sector_{kind}"\n'
        'SUFFIX = f"fact_sector_{kind}中文"\n'
        'DOLLAR = f"fact_sector_{kind}$archive"\n',
        encoding="utf-8",
    )

    assert inventory_sector_fact_access(tmp_path) == ()
