"""板块维度一致化 (sector_alias): 映射规划 / 应用 / 解析 / 查询不混排 / staging 应用。

全部用例只连 :memory: 或 tmp_path, 不触碰生产库。
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from market_feature_store import db as _db
from market_feature_store import query, sector_alias
from market_feature_store.sector_universe import SectorUniverseStore

DIM_SECTOR_DDL = (
    "create table dim_sector(sector_ts_code text primary key, sector_name text not null, "
    "sw_l1 text, is_active boolean, first_seen_date date, last_seen_date date, "
    "source text, updated_at timestamp)"
)

# (code, name, is_active): 覆盖唯一匹配 / 多对一 / 无匹配 / 现行码同名歧义 / 退役码同名多个现行码
DIM_ROWS = [
    ("885362.TI", "云计算", False),
    ("990044.FP", "云计算", True),
    ("885100.TI", "小金属", False),
    ("885101.TI", "小金属", False),
    ("990168.FP", "小金属", True),
    ("885999.TI", "孤儿板块", False),
    ("990143.FP", "国防军工", True),
    ("990144.FP", "国防军工", True),
    ("885200.TI", "双现", False),
    ("990200.FP", "双现", True),
    ("990201.FP", "双现", True),
]


def _seed_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(DIM_SECTOR_DDL)
    SectorUniverseStore.ensure_schema(con)
    con.executemany(
        "insert into dim_sector values (?, ?, ?, ?, NULL, NULL, 'test', now())",
        [(code, name, "x", active) for code, name, active in DIM_ROWS],
    )
    con.executemany(
        """
        insert into fact_sector_daily_generation
            (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, pct_chg)
        values (?, 'legacy', ?, ?, ?)
        """,
        [
            ("2025-06-02", "885362.TI", "云计算", 1.0),
            ("2026-03-02", "885362.TI", "云计算", 1.1),
            ("2026-03-02", "990044.FP", "云计算", 2.2),
            ("2026-09-01", "990044.FP", "云计算", 3.3),
            ("2026-09-01", "990143.FP", "国防军工", 0.2),
            ("2026-09-01", "990144.FP", "国防军工", 0.5),
            # 历史上叫过别的名字的码
            ("2026-01-05", "990168.FP", "小金属概念", 0.9),
        ],
    )
    con.executemany(
        """
        insert into fact_sector_stock_daily_generation
            (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
             stock_ts_code, stock_name, price, pct_chg, amount)
        values (?, 'legacy', ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            # 并存日: 同名板块两套供应商, 成分不同
            ("2026-03-02", "885362.TI", "云计算", "000001.SZ", "TI股A", 10.0, 1.0, 5.0),
            ("2026-03-02", "885362.TI", "云计算", "000002.SZ", "TI股B", 10.0, 1.0, 4.0),
            ("2026-03-02", "990044.FP", "云计算", "300001.SZ", "FP股A", 20.0, 2.0, 9.0),
            ("2026-03-02", "990044.FP", "云计算", "000001.SZ", "TI股A", 10.0, 1.0, 5.0),
            # 只有退役码有数据的早期日
            ("2025-06-02", "885362.TI", "云计算", "000003.SZ", "早期股", 8.0, 0.5, 3.0),
            # 真歧义: 两个现行码同名, 同一只股各挂一份
            ("2026-09-01", "990143.FP", "国防军工", "600001.SH", "军工股", 30.0, 3.0, 12.0),
            ("2026-09-01", "990144.FP", "国防军工", "600001.SH", "军工股", 30.0, 3.0, 11.0),
        ],
    )


@pytest.fixture
def con():
    con = duckdb.connect(":memory:")
    _seed_schema(con)
    try:
        yield con
    finally:
        con.close()


@pytest.fixture
def file_db(tmp_path, monkeypatch) -> Path:
    """tmp 文件库 + 把 query.connect 指过去 (query 每次调用都 connect/close)。"""
    path = tmp_path / "mfs.duckdb"
    con = duckdb.connect(str(path))
    try:
        _seed_schema(con)
    finally:
        con.close()
    monkeypatch.setattr(
        query, "connect", lambda read_only=False: duckdb.connect(str(path), read_only=read_only)
    )
    return path


# ---------------------------------------------------------------------------
# 规划 / 应用
# ---------------------------------------------------------------------------


def test_plan_writes_only_unique_same_name_matches(con):
    plan = sector_alias.plan_provider_migration(con)

    mapping = {r.alias: r.sector_ts_code for r in plan.rows}
    # 云计算 一对一; 小金属 两个退役码指向同一现行码 (多对一是合法的别名形态)
    assert mapping == {
        "885362.TI": "990044.FP",
        "885100.TI": "990168.FP",
        "885101.TI": "990168.FP",
    }
    assert plan.unmapped == [("885999.TI", "孤儿板块")]
    assert plan.ambiguous == [("885200.TI", "双现", ["990200.FP", "990201.FP"])]
    # 现行码之间同名 (国防军工) 不是迁移问题, 不进任何一栏
    assert all("国防军工" not in r.sector_name for r in plan.rows)

    row = mapping and next(r for r in plan.rows if r.alias == "885362.TI")
    assert row.confidence == sector_alias.PROVIDER_MIGRATION_CONFIDENCE
    # note 带事实表真实起止日, 让人一眼看到断在哪
    assert "885362.TI(2025-06-02→2026-03-02)" in row.note
    assert "990044.FP(2026-03-02→2026-09-01)" in row.note


def test_apply_is_idempotent_and_view_resolves_canonical(con):
    plan = sector_alias.plan_provider_migration(con)
    assert sector_alias.apply_alias_rows(con, plan.rows) == 3
    assert sector_alias.apply_alias_rows(con, plan.rows) == 3
    assert con.execute("select count(*) from config_sector_alias").fetchone()[0] == 3

    rows = dict(
        con.execute(
            "select sector_ts_code, canonical_sector_ts_code from dim_sector_canonical"
        ).fetchall()
    )
    assert rows["885362.TI"] == "990044.FP"
    assert rows["885101.TI"] == "990168.FP"
    assert rows["885999.TI"] == "885999.TI"  # 无映射 → 自己就是 canonical
    assert rows["990044.FP"] == "990044.FP"
    # 一码一行: 视图不因 alias 表 fan out
    assert con.execute("select count(*) from dim_sector_canonical").fetchone()[0] == len(DIM_ROWS)

    provider = dict(con.execute("select sector_ts_code, provider from dim_sector_canonical").fetchall())
    assert provider["885362.TI"] == "TI" and provider["990044.FP"] == "FP"

    span = con.execute(
        "select fact_first_trade_date, fact_last_trade_date from dim_sector_canonical "
        "where sector_ts_code = '885362.TI'"
    ).fetchone()
    assert [str(d) for d in span] == ["2025-06-02", "2026-03-02"]


def test_view_picks_highest_confidence_when_alias_has_two_targets(con):
    con.execute(
        "insert into config_sector_alias values ('885362.TI', '990044.FP', '云计算', 0.9, 'a', now())"
    )
    con.execute(
        "insert into config_sector_alias values ('885362.TI', '990200.FP', '云计算', 0.3, 'b', now())"
    )
    rows = con.execute(
        "select canonical_sector_ts_code from dim_sector_canonical where sector_ts_code = '885362.TI'"
    ).fetchall()
    assert rows == [("990044.FP",)]


def test_apply_provider_migration_writes_receipt(con):
    result = sector_alias.apply_provider_migration(con, plan_name="direct")
    assert result["written"] == 3 and result["config_sector_alias"] == 3
    kind, plan, ok = con.execute(
        "select kind, plan, ok from ops_sync_run where run_id = ?", [result["run_id"]]
    ).fetchone()
    assert (kind, plan, ok) == ("sector-alias", "direct", True)


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------


@pytest.fixture
def resolved_con(con):
    sector_alias.apply_alias_rows(con, sector_alias.plan_provider_migration(con).rows)
    return con


def test_resolve_by_name_puts_current_code_first_then_retired(resolved_con):
    res = sector_alias.resolve_sector_codes(resolved_con, "云计算")
    assert res.matched_by == "name"
    assert res.codes == ["990044.FP", "885362.TI"]
    assert res.canonical == "990044.FP"
    assert res.ambiguous is False


def test_resolve_by_retired_or_current_code_gives_same_line(resolved_con):
    by_old = sector_alias.resolve_sector_codes(resolved_con, "885362.TI")
    by_new = sector_alias.resolve_sector_codes(resolved_con, "990044.FP")
    assert by_old.matched_by == by_new.matched_by == "code"
    assert by_old.codes == by_new.codes == ["990044.FP", "885362.TI"]


def test_resolve_many_to_one_lists_all_retired_codes(resolved_con):
    res = sector_alias.resolve_sector_codes(resolved_con, "小金属")
    assert res.codes == ["990168.FP", "885100.TI", "885101.TI"]
    assert res.ambiguous is False


def test_resolve_flags_true_ambiguity_instead_of_merging(resolved_con):
    res = sector_alias.resolve_sector_codes(resolved_con, "国防军工")
    assert res.ambiguous is True
    assert res.codes == ["990143.FP", "990144.FP"]
    both = sector_alias.resolve_sector_codes(resolved_con, "双现")
    assert both.ambiguous is True
    # 两条线都在, 退役码在各自 canonical 之后
    assert both.codes == ["990200.FP", "990201.FP", "885200.TI"]


def test_resolve_falls_back_to_historical_name(resolved_con):
    res = sector_alias.resolve_sector_codes(resolved_con, "小金属概念")
    assert res.matched_by == "historical_name"
    assert res.canonical == "990168.FP"


def test_resolve_unknown_and_blank(resolved_con):
    assert sector_alias.resolve_sector_codes(resolved_con, "不存在的板块").matched_by == "none"
    assert sector_alias.resolve_sector_codes(resolved_con, "   ").matched_by == "none"


def test_resolve_manual_alias_from_config_table(resolved_con):
    resolved_con.execute(
        "insert into config_sector_alias values ('AI', '990044.FP', '云计算', 0.5, '人工别名', now())"
    )
    res = sector_alias.resolve_sector_codes(resolved_con, "AI")
    assert res.matched_by == "alias"
    assert res.canonical == "990044.FP"


def test_resolve_unavailable_when_view_missing(con):
    con.execute("drop view dim_sector_canonical")
    res = sector_alias.resolve_sector_codes(con, "云计算")
    assert res.matched_by == "unavailable"
    assert res.codes == []


def test_pick_code_falls_back_by_date(resolved_con):
    codes = sector_alias.resolve_sector_codes(resolved_con, "云计算").codes
    pick = sector_alias.pick_code_with_rows
    # 早期只有退役码有数据 → 落到退役码, 而不是答无数据
    assert pick(resolved_con, "fact_sector_daily", "2025-06-02", codes) == "885362.TI"
    # 并存日 → 现行码优先
    assert pick(resolved_con, "fact_sector_daily", "2026-03-02", codes) == "990044.FP"
    assert pick(resolved_con, "fact_sector_daily", "2026-09-01", codes) == "990044.FP"
    assert pick(resolved_con, "fact_sector_daily", "2024-01-01", codes) is None
    assert pick(resolved_con, "fact_sector_daily", "2026-09-01", []) is None


# ---------------------------------------------------------------------------
# 查询面: 不再按名字混排
# ---------------------------------------------------------------------------


def _apply_to_file(path: Path) -> None:
    con = duckdb.connect(str(path))
    try:
        sector_alias.apply_alias_rows(con, sector_alias.plan_provider_migration(con).rows)
    finally:
        con.close()


def test_sector_stocks_uses_one_provider_on_overlap_day(file_db):
    _apply_to_file(file_db)
    res = query.sector_stocks("云计算", trade_date="2026-03-02", top=50)
    names = sorted(s["stock_name"] for s in res["stocks"])
    # 旧行为会返回 TI股A/TI股B/FP股A/TI股A 四行混排; 现在只有现行码那一套
    assert names == ["FP股A", "TI股A"]
    assert res["resolution"]["resolved_sector_ts_code"] == "990044.FP"
    assert res["resolution"]["matched_by"] == "name"
    assert res["resolution"]["ambiguous"] is False


def test_sector_stocks_falls_back_to_retired_code_for_early_date(file_db):
    _apply_to_file(file_db)
    res = query.sector_stocks("云计算", trade_date="2025-06-02")
    assert [s["stock_name"] for s in res["stocks"]] == ["早期股"]
    assert res["resolution"]["resolved_sector_ts_code"] == "885362.TI"


def test_sector_stocks_surfaces_true_ambiguity(file_db):
    _apply_to_file(file_db)
    res = query.sector_stocks("国防军工", trade_date="2026-09-01")
    assert res["resolution"]["ambiguous"] is True
    assert res["resolution"]["resolved_sector_ts_code"] == "990143.FP"
    assert res["resolution"]["codes"] == ["990143.FP", "990144.FP"]
    # 不再把两个同名板块的同一只股返回两遍
    assert len(res["stocks"]) == 1


def test_sector_stocks_keeps_legacy_filter_when_view_missing(file_db):
    con = duckdb.connect(str(file_db))
    try:
        con.execute("drop view dim_sector_canonical")
    finally:
        con.close()
    res = query.sector_stocks("云计算", trade_date="2026-03-02", top=50)
    # 视图不存在时退回旧行为 (按名或码直配), 不静默吞掉结果
    assert len(res["stocks"]) == 4
    assert res["resolution"]["matched_by"] == "unavailable"
    assert res["resolution"]["resolved_sector_ts_code"] is None


def test_stock_sectors_merges_provider_duplicates_but_keeps_true_ambiguity(file_db):
    _apply_to_file(file_db)
    res = query.stock_sectors("000001.SZ", trade_date="2026-03-02")
    # 并存日同一只股挂 云计算.TI 和 云计算.FP → 合成一行, 留现行码
    assert [s["sector_ts_code"] for s in res["sectors"]] == ["990044.FP"]
    assert res["alias_rows_merged"] == 1

    res2 = query.stock_sectors("600001.SH", trade_date="2026-09-01")
    # 国防军工 两个现行码 canonical 不同, 两行都保留
    assert sorted(s["sector_ts_code"] for s in res2["sectors"]) == ["990143.FP", "990144.FP"]
    assert res2["alias_rows_merged"] == 0


def test_top_sectors_collapses_provider_duplicates_and_keeps_true_ambiguity(file_db):
    _apply_to_file(file_db)
    # 并存日 云计算 有 .TI(1.1) 与 .FP(2.2) 两行 → 只留现行码那一行
    res = query.top_sectors(trade_date="2026-03-02", top=10, order_by="pct_chg")
    names = [s["sector_name"] for s in res["sectors"]]
    assert names.count("云计算") == 1
    row = next(s for s in res["sectors"] if s["sector_name"] == "云计算")
    assert row["sector_ts_code"] == "990044.FP" and row["pct_chg"] == 2.2
    assert res["alias_rows_merged"] == 1

    # 国防军工 两个 .FP 是两个板块, 两行都在; 名次按值重排 (0.5 排在 0.2 前)
    res2 = query.top_sectors(trade_date="2026-09-01", top=10, order_by="pct_chg")
    codes = [s["sector_ts_code"] for s in res2["sectors"]]
    assert codes[:3] == ["990044.FP", "990144.FP", "990143.FP"]
    assert res2["alias_rows_merged"] == 0


def test_ask_blocks_stock_rank_uses_one_sector_code_as_denominator(file_db):
    """国防军工 两个码各挂同一只股: 按名字分区分母会是 2, 解析到码后是 1。"""
    from intelligence.services import ask_blocks

    _apply_to_file(file_db)
    con = duckdb.connect(str(file_db), read_only=True)
    try:
        lines = ask_blocks._format_stock_rank_lines(con, "2026-09-01", "600001.SH", ["国防军工"])
        assert lines == ["国防军工成交排名1/1、涨幅排名1/1、涨跌幅3.0%、成交12.0亿"]
        # 并存日: 云计算 现行码有 2 只成分 (FP股A/TI股A), 退役码的 TI股B 不进分母
        lines = ask_blocks._format_stock_rank_lines(con, "2026-03-02", "000001.SZ", ["云计算"])
        assert lines == ["云计算成交排名2/2、涨幅排名2/2、涨跌幅1.0%、成交5.0亿"]
        # 板块状态行同样落到现行码 (.FP 的 2.2), 不再 limit 1 随机
        state = ask_blocks._format_sector_state_lines(con, "2026-03-02", ["云计算"])
        assert state and state[0].startswith("云计算2.2%")
    finally:
        con.close()


# ---------------------------------------------------------------------------
# staging 应用: 生产库正门
# ---------------------------------------------------------------------------


def test_staged_apply_swaps_atomically_and_cleans_staging(tmp_path):
    target = tmp_path / "prod.duckdb"
    con = duckdb.connect(str(target))
    try:
        _seed_schema(con)
        con.execute("drop view dim_sector_canonical")  # 模拟旧库: 视图尚未存在
    finally:
        con.close()

    result = sector_alias.apply_provider_migration_staged(target)

    assert result["swapped"] is True and result["reason"] == "ok"
    assert result["written"] == 3 and result["mapped"] == 3
    assert result["copy"]["method"] in {"clonefile", "copy"}
    assert not _db.staging_path(target).exists()
    assert not _db.wal_path(target).exists()

    con = duckdb.connect(str(target), read_only=True)
    try:
        assert con.execute("select count(*) from config_sector_alias").fetchone()[0] == 3
        assert con.execute(
            "select canonical_sector_ts_code from dim_sector_canonical where sector_ts_code='885362.TI'"
        ).fetchone() == ("990044.FP",)
        kind, plan, copy_method = con.execute(
            "select kind, plan, copy_method from ops_sync_run where run_id = ?", [result["run_id"]]
        ).fetchone()
        assert (kind, plan) == ("sector-alias", "staging-swap")
        assert copy_method == result["copy"]["method"]
    finally:
        con.close()


def test_staged_apply_refuses_when_target_missing(tmp_path):
    result = sector_alias.apply_provider_migration_staged(tmp_path / "nope.duckdb")
    assert result["swapped"] is False
    assert "不存在" in result["reason"]


def test_staged_apply_refuses_when_writer_active(tmp_path, monkeypatch):
    """开工闸: 有活跃写者就不克隆、不动生产库。

    同进程内 duckdb 不允许对同一文件以另一配置再开连接 (抛 ConnectionException 而非
    锁冲突), 真实场景是跨进程持锁——探针原语本身在 db 模块的测试里覆盖, 这里只验
    本函数对 DatabaseLockedError 的处理。
    """
    target = tmp_path / "prod.duckdb"
    con = duckdb.connect(str(target))
    try:
        _seed_schema(con)
    finally:
        con.close()

    def locked(_path):
        raise _db.DatabaseLockedError("模拟同步进程持写锁")

    monkeypatch.setattr(_db, "probe_no_active_writer", locked)
    result = sector_alias.apply_provider_migration_staged(target)
    assert result["swapped"] is False
    assert "活跃写者" in result["reason"]
    assert result.get("copy") is None  # 连克隆都没做
    assert not _db.staging_path(target).exists()


def test_staged_apply_refuses_when_third_party_modified_target(tmp_path, monkeypatch):
    """换名前守卫: 克隆基线之后生产库被别人改过, 换名会覆盖对方写入 → 拒绝。"""
    target = tmp_path / "prod.duckdb"
    con = duckdb.connect(str(target))
    try:
        _seed_schema(con)
    finally:
        con.close()

    real_init = _db.init_db

    def init_then_third_party_writes(staging_con):
        # 此刻克隆已完成、基线 stat 已取; 模拟第三方对**生产库**落一笔并关闭 (checkpoint 改 mtime/size)
        real_init(staging_con)
        third = duckdb.connect(str(target))
        try:
            third.execute(
                "insert into config_sector_alias values ('X', '990044.FP', '云计算', 0.1, 't', now())"
            )
        finally:
            third.close()

    monkeypatch.setattr(_db, "init_db", init_then_third_party_writes)
    result = sector_alias.apply_provider_migration_staged(target)
    assert result["swapped"] is False
    assert "第三方写者守卫" in result["reason"]
    # staging 留作取证; 生产库里只有第三方那 1 行, 我们的 3 行没有覆盖上去
    assert _db.staging_path(target).exists()
    con = duckdb.connect(str(target), read_only=True)
    try:
        assert con.execute("select count(*) from config_sector_alias").fetchone()[0] == 1
    finally:
        con.close()
