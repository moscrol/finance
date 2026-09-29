"""#46: 历史 stock_name NUL 回归闸及单事务迁移的隔离演练。"""
from __future__ import annotations

import duckdb
import pytest

from market_feature_store.db import DB_PATH

NUL_COUNT_SQL = (
    "SELECT count(*) FROM fact_stock_daily "
    "WHERE stock_name LIKE '%' || chr(0) || '%'"
)
UPDATE_SQL = (
    "UPDATE fact_stock_daily "
    "SET stock_name = replace(stock_name, chr(0), '') "
    "WHERE stock_name LIKE '%' || chr(0) || '%'"
)


def _nul_count(con: duckdb.DuckDBPyConnection) -> int:
    return con.execute(NUL_COUNT_SQL).fetchone()[0]


def _names_by_code(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    return dict(con.execute(
        "SELECT stock_ts_code, count(DISTINCT stock_name) "
        "FROM fact_stock_daily GROUP BY stock_ts_code ORDER BY stock_ts_code"
    ).fetchall())


def _fixture_db(path):
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code VARCHAR, "
        "stock_name VARCHAR, source VARCHAR, close DOUBLE)"
    )
    con.executemany(
        "INSERT INTO fact_stock_daily VALUES (?, ?, ?, ?, ?)",
        [
            ("2026-09-03", "002193.SZ", "TCL科技\x00", "mootdx", 1.0),
            ("2026-09-04", "002193.SZ", "TCL科技", "eastmoney", 2.0),
            ("2026-09-03", "002305.SZ", "柳 工\x00\x00", "mootdx", 3.0),
            ("2026-09-04", "002305.SZ", "柳 工", "eastmoney", 4.0),
            # 真实改名应保持两名，不要求全库一码一名。
            ("2026-09-03", "000100.SZ", "旧名", "mootdx", 5.0),
            ("2026-09-04", "000100.SZ", "新名", "eastmoney", 6.0),
            ("2026-09-05", "000100.SZ", None, "test", 7.0),
        ],
    )
    return con


def _rows(con):
    return con.execute("SELECT * FROM fact_stock_daily ORDER BY stock_ts_code, trade_date").fetchall()


def test_single_transaction_only_removes_nul_and_is_idempotent(tmp_path):
    con = _fixture_db(tmp_path / "rehearsal.duckdb")
    try:
        before = _rows(con)
        before_names = _names_by_code(con)
        assert _nul_count(con) == 2
        assert before_names == {"000100.SZ": 2, "002193.SZ": 2, "002305.SZ": 2}
        con.execute("BEGIN")
        con.execute(UPDATE_SQL)
        assert _nul_count(con) == 0  # 提交前回读值
        con.execute("COMMIT")
        after = _rows(con)
        assert len(before) == len(after)
        for old, new in zip(before, after):
            assert new[2] == (old[2].replace("\x00", "") if old[2] is not None else None)
            assert new[:2] == old[:2] and new[3:] == old[3:]
        assert _names_by_code(con) == {"000100.SZ": 2, "002193.SZ": 1, "002305.SZ": 1}
        assert "柳 工" in {row[2] for row in after}  # 不抹真名里的空格
        con.execute("BEGIN")
        con.execute(UPDATE_SQL)
        con.execute("COMMIT")
        assert _rows(con) == after
    finally:
        con.close()


def test_failed_transaction_rolls_back_everything(tmp_path):
    con = _fixture_db(tmp_path / "rollback.duckdb")
    try:
        before = _rows(con)
        con.execute("BEGIN")
        try:
            con.execute(UPDATE_SQL)
            assert _nul_count(con) == 0
            raise RuntimeError("模拟验收失败，拒绝提交")
        except RuntimeError:
            con.execute("ROLLBACK")
        assert _rows(con) == before
        assert _nul_count(con) == 2
    finally:
        con.close()


def test_real_fact_stock_daily_stock_name_contains_no_nul():
    """没有真库才 skip；有库而缺表、被锁或存在 NUL 都必须红。只读。"""
    if not DB_PATH.is_file():
        pytest.skip(f"真库不存在：{DB_PATH}")
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        count = _nul_count(con)
    finally:
        con.close()
    assert count == 0, (
        f"{DB_PATH}: fact_stock_daily.stock_name 仍有 {count} 行包含 NUL；"
        "#46 迁移未验收。不得跳过或改小阈值。"
    )
