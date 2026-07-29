from __future__ import annotations

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
