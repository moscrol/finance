"""切主覆盖对账工具：短历史新源必须被抓出来。"""
from __future__ import annotations

import duckdb
import pytest

from scripts.source_switch_coverage_diff import Side, main


@pytest.fixture
def db(tmp_path):
    """日历 5 天；旧源全覆盖，新源只有后 2 天（短历史），第 5 天只有新源。"""
    path = tmp_path / "mfs.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE TABLE fact_market_daily (trade_date DATE)")
        con.executemany(
            "INSERT INTO fact_market_daily VALUES (?)",
            [(f"2026-01-0{i}",) for i in range(1, 6)],
        )
        con.execute("CREATE TABLE old_src (trade_date DATE, v DOUBLE)")
        con.executemany(
            "INSERT INTO old_src VALUES (?, ?)",
            [("2026-01-01", 1.0), ("2026-01-02", 1.0), ("2026-01-03", 1.0), ("2026-01-04", 1.0)],
        )
        con.execute("CREATE TABLE new_src (trade_date DATE, v DOUBLE)")
        con.executemany(
            "INSERT INTO new_src VALUES (?, ?)",
            [("2026-01-04", 2.0), ("2026-01-05", 2.0)],
        )
    finally:
        con.close()
    return path


def test_short_history_source_fails_closed(db, capsys) -> None:
    code = main(["--db", str(db), "--old", "old_src", "--new", "new_src"])
    out = capsys.readouterr().out
    assert code == 1  # 裸切会掉日子 → 非 0
    assert "裸切丢失  3 天" in out
    assert "并集      按日回退后：5 天" in out  # 回退后比旧源单独的 4 天还多
    assert "按日回退" in out


def test_full_coverage_passes(db, capsys) -> None:
    # 新源覆盖日历全部 5 天 ⊇ 旧源的 4 天 → 裸切安全
    code = main(["--db", str(db), "--old", "old_src", "--new", "fact_market_daily"])
    assert code == 0
    out = capsys.readouterr().out
    assert "裸切丢失  0 天" in out
    assert "裸切新增  1 天" in out


def test_value_column_narrows_to_non_null(db, capsys) -> None:
    """行在、值全 NULL 的日子不算覆盖——行数审计抓不到的空壳。"""
    con = duckdb.connect(str(db))
    try:
        con.execute("UPDATE new_src SET v = NULL WHERE trade_date = DATE '2026-01-05'")
    finally:
        con.close()
    assert main(["--db", str(db), "--old", "old_src", "--new", "new_src"]) == 1
    assert "裸切新增  1 天" in capsys.readouterr().out
    code = main(["--db", str(db), "--old", "old_src:v", "--new", "new_src:v"])
    assert code == 1
    assert "裸切新增  0 天" in capsys.readouterr().out


def test_missing_table_is_argument_error(db) -> None:
    assert main(["--db", str(db), "--old", "nope", "--new", "new_src"]) == 2


def test_side_parse() -> None:
    assert Side.parse("t") == Side(table="t", value_column=None)
    assert Side.parse("t:c") == Side(table="t", value_column="c")
    with pytest.raises(ValueError):
        Side.parse(":c")
