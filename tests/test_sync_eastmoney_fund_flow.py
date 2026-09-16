from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from market_feature_store import db
from market_feature_store.sync import sync_eastmoney_fund_flow as ff


def _connect(path: Path):
    def connect(read_only: bool = False):
        return duckdb.connect(str(path), read_only=read_only)

    return connect


def _init(path: Path):
    def init_db(con=None):
        own = con is None
        con = con or duckdb.connect(str(path))
        try:
            con.execute(db.SCHEMA_PATH.read_text(encoding="utf-8"))
        finally:
            if own:
                con.close()

    return init_db


def _seed(con, trade_date: str) -> None:
    con.executemany(
        """
        INSERT INTO fact_sector_stock_daily_generation
            (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
             stock_ts_code, stock_name, amount, fund_flow_1d, source)
        VALUES (?, 'legacy', ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            # local:stitch 且缺资金流 → 应被填
            (trade_date, "990001.FP", "AI硬件", "300308.SZ", "中际旭创", 220.6, None, "local:stitch"),
            (trade_date, "990001.FP", "AI硬件", "300502.SZ", "新易盛", 150.0, None, "local:stitch"),
            # 同股在第二个板块 → 两行都要填
            (trade_date, "990002.FP", "CPO", "300308.SZ", "中际旭创", 220.6, None, "local:stitch"),
            # 供应商行已有值 → 绝不覆盖
            (trade_date, "990002.FP", "CPO", "600519.SH", "贵州茅台", 26.34, -1.81, "fupanhui"),
        ],
    )


@pytest.fixture()
def patched(tmp_path, monkeypatch):
    db_path = tmp_path / "m.duckdb"
    init_db = _init(db_path)
    connect = _connect(db_path)
    init_db()
    from market_feature_store.sync import sync_theme_capital_from_baskets as baskets

    monkeypatch.setattr(ff, "connect", connect)
    monkeypatch.setattr(ff, "init_db", init_db)
    monkeypatch.setattr(baskets, "connect", connect)
    monkeypatch.setattr(baskets, "init_db", init_db)
    return connect


def test_secid_mapping():
    assert ff._secid("600519.SH") == "1.600519"
    assert ff._secid("300308.SZ") == "0.300308"
    assert ff._secid("833171.BJ") == "0.833171"


def test_rolling_5d_needs_full_window():
    series = {f"2026-09-0{i}": float(i) for i in range(1, 6)}  # 09-01..09-05
    assert ff._rolling_5d(series, "2026-09-05") == 15.0
    assert ff._rolling_5d(series, "2026-09-04") is None  # 只有4日<=date
    assert ff._rolling_5d(series, "2026-09-06") is None  # 当日无值不算


def test_history_fills_stitch_rows_and_aggregates(patched, monkeypatch):
    connect = patched
    con = connect()
    try:
        _seed(con, "2026-09-10")
    finally:
        con.close()

    fake_series = {
        "300308.SZ": {d: -1326000000.0 if d == "2026-09-10" else 1e8
                      for d in ["2026-09-04", "2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10"]},
        "300502.SZ": {"2026-09-10": 250000000.0},  # 不足5日 → f5 None
    }
    monkeypatch.setattr(ff, "fetch_flow_history", lambda ts, **k: fake_series[ts])

    s = ff.sync_history(["2026-09-10"], concurrency=1)
    assert s["fetched"] == 2 and s["failed"] == 0
    day = s["days"][0]
    assert day["filled_rows"] == 3  # 中际旭创两行 + 新易盛一行

    con = connect(read_only=True)
    try:
        rows = con.execute(
            """
            SELECT stock_ts_code, sector_ts_code, fund_flow_1d, fund_flow_5d, source
            FROM fact_sector_stock_daily_generation
            WHERE trade_date = '2026-09-10' ORDER BY stock_ts_code, sector_ts_code
            """
        ).fetchall()
        by = {(r[0], r[1]): r for r in rows}
        assert by[("300308.SZ", "990001.FP")][2] == pytest.approx(-13.26)
        assert by[("300308.SZ", "990002.FP")][2] == pytest.approx(-13.26)
        # 5日 = 4*1e8 + (-13.26e8) = -9.26e8 → -9.26亿
        assert by[("300308.SZ", "990001.FP")][3] == pytest.approx(-9.26)
        assert by[("300502.SZ", "990001.FP")][2] == pytest.approx(2.5)
        assert by[("300502.SZ", "990001.FP")][3] is None
        # 供应商行未被触碰
        assert by[("600519.SH", "990002.FP")][2] == pytest.approx(-1.81)

        panels = con.execute(
            """
            SELECT theme_code, total_fund, total_amount, stock_count,
                   member_count, fund_coverage, fund_caliber, source
            FROM fact_theme_flow_daily WHERE trade_date = '2026-09-10'
            ORDER BY theme_code
            """
        ).fetchall()
        p = {r[0]: r for r in panels}
        # AI硬件: 两只都是 local:stitch 且都有值 → -13.26 + 2.5
        assert p["990001.FP"][1] == pytest.approx(-10.76)
        assert p["990001.FP"][3] == 2 and p["990001.FP"][4] == 2
        assert p["990001.FP"][5] == pytest.approx(1.0)
        # CPO 篮子里茅台是 fupanhui 行(不同口径) → 绝不能加进来;
        # 只算中际旭创一只, 且覆盖率如实报 1/2——旧实现这里是 -15.07(混加)。
        assert p["990002.FP"][1] == pytest.approx(-13.26)
        assert p["990002.FP"][3] == 1 and p["990002.FP"][4] == 2
        assert p["990002.FP"][5] == pytest.approx(0.5)
        assert p["990002.FP"][6] == "em-main-net"
        assert p["990002.FP"][7] == "local:sector-basket:em-main-net"
    finally:
        con.close()


def test_history_resume_skips_filled(patched, monkeypatch):
    connect = patched
    con = connect()
    try:
        _seed(con, "2026-09-09")
    finally:
        con.close()
    calls: list[str] = []

    def fake_fetch(ts, **k):
        calls.append(ts)
        # 给足 5 天: 1 日与 5 日都能算出 → 该行才算「已完成」
        return {f"2026-09-{d:02d}": 1e8 for d in (3, 4, 7, 8, 9)}

    monkeypatch.setattr(ff, "fetch_flow_history", fake_fetch)
    ff.sync_history(["2026-09-09"], concurrency=1)
    assert sorted(set(calls)) == ["300308.SZ", "300502.SZ"]

    calls.clear()
    s = ff.sync_history(["2026-09-09"], concurrency=1)
    assert calls == []  # 已填的不再拉
    assert s["codes"] == 0


def test_snapshot_rejects_non_today(patched):
    with pytest.raises(ValueError):
        ff.sync_snapshot("2000-01-01")


def test_empty_basket_is_not_written(patched, monkeypatch):
    """全空篮子不得写出面板行——旧实现会写 total_fund=NULL 的空壳骗过闸门。"""
    connect = patched
    con = connect()
    try:
        con.executemany(
            """
            INSERT INTO fact_sector_stock_daily_generation
                (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
                 stock_ts_code, stock_name, amount, fund_flow_1d, source)
            VALUES (?, 'legacy', ?, ?, ?, ?, ?, ?, 'local:stitch')
            """,
            [
                ("2026-09-10", "990003.FP", "空篮子", "000001.SZ", "平安银行", 10.0, None),
                ("2026-09-10", "990004.FP", "有值篮子", "300308.SZ", "中际旭创", 30.0, None),
            ],
        )
    finally:
        con.close()
    monkeypatch.setattr(
        ff, "fetch_flow_history",
        lambda ts, **k: {"2026-09-10": 1e8} if ts == "300308.SZ" else {},
    )
    ff.sync_history(["2026-09-10"], concurrency=1)

    con = connect(read_only=True)
    try:
        codes = [r[0] for r in con.execute(
            "SELECT theme_code FROM fact_theme_flow_daily WHERE trade_date='2026-09-10'"
        ).fetchall()]
        assert "990004.FP" in codes          # 有资金 → 写
        assert "990003.FP" not in codes      # 全空 → 不写
        assert con.execute(
            "SELECT count(*) FROM fact_theme_flow_daily WHERE total_fund IS NULL"
        ).fetchone()[0] == 0                 # 任何情况下都不落 NULL 资金行
    finally:
        con.close()


def test_mixed_caliber_refuses_to_guess(patched):
    """同日出现两种口径且未指定时必须报错, 而不是相加出一个看着合理的数。"""
    from market_feature_store.sync import sync_theme_capital_from_baskets as baskets

    connect = patched
    con = connect()
    try:
        _seed(con, "2026-09-02")
        con.execute(
            "UPDATE fact_sector_stock_daily_generation SET fund_flow_1d = 3.0 "
            "WHERE trade_date='2026-09-02' AND stock_ts_code='300308.SZ'"
        )
        with pytest.raises(ValueError, match="多种口径"):
            baskets.sync_from_sector_baskets("2026-09-02", con=con)
        # 显式指定则各算各的
        r = baskets.sync_from_sector_baskets("2026-09-02", con=con, member_source="fupanhui")
        assert r["caliber"] == "fupanhui-native"
        assert r["panels"] == 1  # 只有茅台所在的 CPO 篮子
    finally:
        con.close()


def test_replay_from_archive_without_network(patched, monkeypatch, tmp_path):
    """次日走正常入口必须能重放归档, 而不是又去求那个不可靠的历史接口。"""
    connect = patched
    con = connect()
    try:
        _seed(con, "2026-09-11")
    finally:
        con.close()

    # 条数下限由 test_empty_upstream_response_is_never_replayed 专测；
    # 这里只验重放路径，用小样本并显式放宽阈值，避免造 3000 条噪声。
    monkeypatch.setattr(ff, "MIN_RECORDS", 1)
    # 两列都给全: 归档能完整覆盖当日缺口 → 不应再触碰历史接口。
    # (若归档缺 5 日值, auto 会按设计接着走历史回补, 另见 test_auto_falls_through_for_5d_gap)
    raw = {"300308": (3119764480.0, 10202306736.0), "300502": (2.5e8, 8.0e8)}
    ff.capture_raw_snapshot("2026-09-11", raw=raw, out_dir=tmp_path, inferred=True)
    monkeypatch.setattr(ff, "RAW_DIR", tmp_path)

    def _no_net(*_a, **_k):
        raise AssertionError("有归档时不得联网")

    monkeypatch.setattr(ff, "fetch_flow_snapshot", _no_net)
    monkeypatch.setattr(ff, "fetch_flow_history", _no_net)

    # 2026-09-11 早已不是「今天」, 旧实现在这里直接走网络回补
    s = ff.sync("2026-09-11", mode="auto")
    assert s["mode"] == "snapshot" and s["replayed_from_raw"] is True
    assert s["filled_rows"] == 3 and s["panels"] == 2
    con = connect(read_only=True)
    try:
        assert con.execute(
            "SELECT fund_flow_1d FROM fact_sector_stock_daily_generation "
            "WHERE trade_date='2026-09-11' AND stock_ts_code='300308.SZ' LIMIT 1"
        ).fetchone()[0] == pytest.approx(31.1976)
    finally:
        con.close()


def test_archive_metadata_is_validated(tmp_path):
    """归属日/单位/口径任一对不上就拒绝重放——整份快照安错日子是安静的错。"""
    ff.capture_raw_snapshot("2026-09-11", raw={"000001": (1.0, 2.0)}, out_dir=tmp_path)
    path = tmp_path / "2026-09-11.json"
    doc = json.loads(path.read_text())

    doc["trade_date"] = "2026-09-10"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="归属日"):
        ff.load_raw_snapshot("2026-09-11", out_dir=tmp_path)

    doc["trade_date"] = "2026-09-11"
    doc["unit"] = "yi"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="单位"):
        ff.load_raw_snapshot("2026-09-11", out_dir=tmp_path)

    doc["unit"] = "yuan"
    doc["caliber"] = "fupanhui-native"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="口径"):
        ff.load_raw_snapshot("2026-09-11", out_dir=tmp_path)


def test_panels_rebuild_after_aggregation_failure(patched, monkeypatch):
    """资金写成功、汇总炸了之后, 重跑必须能把面板补出来（旧 if filled 会永久跳过）。"""
    connect = patched
    con = connect()
    try:
        _seed(con, "2026-09-10")
    finally:
        con.close()
    monkeypatch.setattr(
        ff, "fetch_flow_history",
        lambda ts, **k: {f"2026-09-{d:02d}": 1e8 for d in (4, 7, 8, 9, 10)},
    )

    boom = {"n": 0}

    def _explode(*_a, **_k):
        boom["n"] += 1
        raise RuntimeError("汇总步骤炸了")

    monkeypatch.setattr(ff, "sync_from_sector_baskets", _explode)
    with pytest.raises(RuntimeError):
        ff.sync_history(["2026-09-10"], concurrency=1)
    assert boom["n"] == 1

    con = connect(read_only=True)
    try:
        assert con.execute(
            "SELECT count(fund_flow_1d) FROM fact_sector_stock_daily_generation "
            "WHERE trade_date='2026-09-10'"
        ).fetchone()[0] == 4          # 资金已落库
        assert con.execute(
            "SELECT count(*) FROM fact_theme_flow_daily WHERE trade_date='2026-09-10'"
        ).fetchone()[0] == 0          # 面板还没有
    finally:
        con.close()

    # 重跑: 已无待填资金, 但面板必须能从已存成分独立重建
    from market_feature_store.sync import sync_theme_capital_from_baskets as baskets

    monkeypatch.setattr(ff, "sync_from_sector_baskets", baskets.sync_from_sector_baskets)
    s = ff.sync_history(["2026-09-10"], concurrency=1)
    day = s["days"][0]
    assert day["filled_rows"] == 0 and day["panels"] == 2


def test_stale_panel_is_revoked(patched, monkeypatch):
    """成分变全空后, 上一轮的有效面板必须被撤销, 不能继续被查到。"""
    from market_feature_store.sync import sync_theme_capital_from_baskets as baskets

    connect = patched
    con = connect()
    try:
        # 成分视图只放行已 published 的快照，注册一份真快照，顺带验成分版本落库
        con.execute(
            """
            INSERT INTO ops_sector_universe_snapshot_daily
            VALUES ('2026-09-10','snapA','local:test',1,1,'published',now())
            """
        )
        con.execute(
            """
            INSERT INTO fact_sector_stock_daily_generation
                (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
                 stock_ts_code, stock_name, amount, fund_flow_1d, source)
            VALUES ('2026-09-10','snapA','990009.FP','会消失的题材','000001.SZ','A',
                    10.0, 3.0, 'local:stitch')
            """
        )
        r1 = baskets.sync_from_sector_baskets("2026-09-10", con=con,
                                              member_source="local:stitch")
        assert r1["panels"] == 1
        assert con.execute(
            "SELECT total_fund, universe_snapshot_id FROM fact_theme_flow_daily "
            "WHERE theme_code='990009.FP'"
        ).fetchone() == (3.0, "snapA")

        # 成分资金变空 → 该篮子不再产出面板
        con.execute(
            "UPDATE fact_sector_stock_daily_generation SET fund_flow_1d = NULL "
            "WHERE trade_date='2026-09-10'"
        )
        r2 = baskets.sync_from_sector_baskets("2026-09-10", con=con,
                                              member_source="local:stitch")
        assert r2["panels"] == 0
        assert r2["stale_removed"] == 1
        assert con.execute(
            "SELECT count(*) FROM fact_theme_flow_daily WHERE theme_code='990009.FP'"
        ).fetchone()[0] == 0, "旧面板仍可被查到——失效行没有撤销"
    finally:
        con.close()


def test_stale_panel_revoked_through_sync_entrypoint(patched, monkeypatch):
    """撤销必须在**正常入口**生效: 上一版 _rebuild_panels 遇当日无资金提前返回, 旧面板留存。"""
    connect = patched
    con = connect()
    try:
        con.execute(
            "INSERT INTO ops_sector_universe_snapshot_daily "
            "VALUES ('2026-09-10','snapA','local:test',1,1,'published',now())"
        )
        con.execute(
            """
            INSERT INTO fact_sector_stock_daily_generation
                (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
                 stock_ts_code, stock_name, amount, fund_flow_1d, source)
            VALUES ('2026-09-10','snapA','990009.FP','会消失的题材','000001.SZ','A',
                    10.0, 3.0, 'local:stitch')
            """
        )
    finally:
        con.close()
    monkeypatch.setattr(ff, "fetch_flow_history", lambda ts, **k: {})

    ff.sync_history(["2026-09-10"], concurrency=1)   # 建面板
    con = connect()
    try:
        assert con.execute(
            "SELECT total_fund FROM fact_theme_flow_daily WHERE theme_code='990009.FP'"
        ).fetchone()[0] == 3.0
        con.execute(
            "UPDATE fact_sector_stock_daily_generation SET fund_flow_1d = NULL "
            "WHERE trade_date='2026-09-10'"
        )
    finally:
        con.close()

    s = ff.sync_history(["2026-09-10"], concurrency=1)   # 成分变空后经正常入口重跑
    day = s["days"][0]
    assert day["coverage"] == "0/1" and day["panels"] == 0
    assert day["stale_removed"] == 1
    con = connect(read_only=True)
    try:
        assert con.execute(
            "SELECT count(*) FROM fact_theme_flow_daily WHERE theme_code='990009.FP'"
        ).fetchone()[0] == 0, "经 sync 入口重跑后旧面板仍在"
    finally:
        con.close()


def test_intraday_archive_is_not_frozen_as_final(tmp_path, monkeypatch):
    """09:05 采的盘中值不能被固定成终值: 收盘后重跑必须重新采集。"""
    import datetime as _dt

    big = {f"{i:06d}": (1e8, None) for i in range(ff.MIN_RECORDS + 10)}
    real_dt = ff.datetime

    class _At0905(real_dt):
        @classmethod
        def now(cls, tz=None):
            return real_dt(2026, 9, 11, 9, 5, tzinfo=ff._SHANGHAI).astimezone(tz)

    monkeypatch.setattr(ff, "datetime", _At0905)
    ff.capture_raw_snapshot("2026-09-11", raw=big, out_dir=tmp_path)
    monkeypatch.setattr(ff, "datetime", real_dt)

    doc = json.loads((tmp_path / "2026-09-11.json").read_text())
    assert doc["status"] == "provisional"
    assert ff.load_raw_snapshot("2026-09-11", out_dir=tmp_path) is None, "盘中快照被当成终值重放"
    assert _dt is not None


def test_empty_upstream_response_is_never_replayed(tmp_path):
    """上游返回空: 存证可以, 但绝不能当作「已有留底」填成全市场零。"""
    ff.capture_raw_snapshot("2026-09-11", raw={}, out_dir=tmp_path)
    doc = json.loads((tmp_path / "2026-09-11.json").read_text())
    assert doc["status"] == "rejected" and doc["record_count"] == 0
    assert ff.load_raw_snapshot("2026-09-11", out_dir=tmp_path) is None


def test_aggregator_inside_outer_transaction(patched):
    """声明由外层管事务时不得自行 BEGIN——嵌套 BEGIN 会把外层事务打成 aborted。"""
    from market_feature_store.sync import sync_theme_capital_from_baskets as baskets

    connect = patched
    con = connect()
    try:
        con.execute(
            """
            INSERT INTO fact_sector_stock_daily_generation
                (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
                 stock_ts_code, stock_name, amount, fund_flow_1d, source)
            VALUES ('2026-09-10','legacy','990010.FP','外层事务','000001.SZ','A',
                    10.0, 7.0, 'local:stitch')
            """
        )
        con.execute("BEGIN TRANSACTION")
        r = baskets.sync_from_sector_baskets(
            "2026-09-10", con=con, member_source="local:stitch",
            manage_transaction=False,
        )
        assert r["panels"] == 1
        con.execute("COMMIT")          # 外层事务仍健康
        assert con.execute(
            "SELECT total_fund FROM fact_theme_flow_daily WHERE theme_code='990010.FP'"
        ).fetchone()[0] == 7.0
    finally:
        con.close()


def _at(monkeypatch, y, mo, d, h, mi):
    real_dt = ff.datetime

    class _Frozen(real_dt):
        @classmethod
        def now(cls, tz=None):
            return real_dt(y, mo, d, h, mi, tzinfo=ff._SHANGHAI).astimezone(tz)

    monkeypatch.setattr(ff, "datetime", _Frozen)
    return real_dt


def test_intraday_snapshot_is_never_written_to_db(patched, monkeypatch, tmp_path):
    """09:05 的盘中值不得入库: 否则 16:05 采到的终值再也盖不上（_fill_rows 只补 NULL）。"""
    connect = patched
    con = connect()
    try:
        _seed(con, "2026-09-11")
    finally:
        con.close()
    monkeypatch.setattr(ff, "RAW_DIR", tmp_path)
    monkeypatch.setattr(ff, "MIN_RECORDS", 1)

    monkeypatch.setattr(ff, "fetch_flow_snapshot", lambda: {"300308": (1e8, None)})
    real_dt = _at(monkeypatch, 2026, 9, 11, 9, 5)
    s = ff.sync_snapshot("2026-09-11")
    assert s["archive_status"] == "provisional" and s["written"] is False
    monkeypatch.setattr(ff, "datetime", real_dt)
    con = connect(read_only=True)
    try:
        assert con.execute(
            "SELECT fund_flow_1d FROM fact_sector_stock_daily_generation "
            "WHERE trade_date='2026-09-11' AND stock_ts_code='300308.SZ' LIMIT 1"
        ).fetchone()[0] is None, "盘中值已写库，收盘后将无法纠正"
    finally:
        con.close()

    # 16:05 重采终值 9 亿 → 归档 final → 正常写库
    monkeypatch.setattr(ff, "fetch_flow_snapshot", lambda: {"300308": (9e8, None)})
    real_dt = _at(monkeypatch, 2026, 9, 11, 16, 5)
    s2 = ff.sync_snapshot("2026-09-11")
    monkeypatch.setattr(ff, "datetime", real_dt)
    assert s2["archive_status"] == "final" and s2["written"] is True
    con = connect(read_only=True)
    try:
        assert con.execute(
            "SELECT fund_flow_1d FROM fact_sector_stock_daily_generation "
            "WHERE trade_date='2026-09-11' AND stock_ts_code='300308.SZ' LIMIT 1"
        ).fetchone()[0] == pytest.approx(9.0)
    finally:
        con.close()


def test_rejected_snapshot_produces_no_panels(patched, monkeypatch, tmp_path):
    """条数不足的快照不得写库、更不得据此生成面板。"""
    connect = patched
    con = connect()
    try:
        _seed(con, "2026-09-11")
    finally:
        con.close()
    monkeypatch.setattr(ff, "RAW_DIR", tmp_path)
    monkeypatch.setattr(ff, "fetch_flow_snapshot", lambda: {"300308": (1e8, None)})
    real_dt = _at(monkeypatch, 2026, 9, 11, 16, 5)
    s = ff.sync_snapshot("2026-09-11")
    monkeypatch.setattr(ff, "datetime", real_dt)
    assert s["archive_status"] == "rejected" and s["written"] is False
    assert s["panels"] == 0
    con = connect(read_only=True)
    try:
        assert con.execute(
            "SELECT count(*) FROM fact_theme_flow_daily WHERE trade_date='2026-09-11'"
        ).fetchone()[0] == 0
    finally:
        con.close()


def test_five_day_gap_is_refillable(patched, monkeypatch):
    """1日已有、5日为空的行必须仍在待补集里, 否则 5 日值永远补不上。"""
    connect = patched
    con = connect()
    try:
        _seed(con, "2026-09-10")
        con.execute(
            "UPDATE fact_sector_stock_daily_generation SET fund_flow_1d = 1.0, "
            "fund_flow_5d = NULL WHERE trade_date='2026-09-10'"
        )
        assert ff._pending_codes(con, "2026-09-10"), "1日已填、5日空的行被排除出待补集"
    finally:
        con.close()
    monkeypatch.setattr(
        ff, "fetch_flow_history",
        lambda ts, **k: {f"2026-09-{d:02d}": 1e8 for d in range(4, 11)},
    )
    s = ff.sync_history(["2026-09-10"], concurrency=1)
    assert s["codes"] > 0
    con = connect(read_only=True)
    try:
        row = con.execute(
            "SELECT fund_flow_1d, fund_flow_5d FROM fact_sector_stock_daily_generation "
            "WHERE trade_date='2026-09-10' AND fund_flow_5d IS NOT NULL LIMIT 1"
        ).fetchone()
        assert row is not None and row[0] == pytest.approx(1.0), "既有 1 日值被覆盖"
        assert row[1] is not None, "5 日值仍为空"
    finally:
        con.close()
    assert s["days"][0]["coverage_5d"].split("/")[0] != "0"


def test_daily_theme_flow_entry_revokes_stale(patched, monkeypatch):
    """日更面板入口: 自动探测返回 None 时也必须撤销本模块写过的旧面板。"""
    from market_feature_store.sync import sync_theme_capital_from_baskets as baskets

    connect = patched
    con = connect()
    try:
        con.execute(
            """
            INSERT INTO fact_sector_stock_daily_generation
                (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
                 stock_ts_code, stock_name, amount, fund_flow_1d, source)
            VALUES ('2026-09-10','legacy','990011.FP','日更题材','000001.SZ','A',
                    10.0, 5.0, 'local:stitch')
            """
        )
        r1 = baskets.sync_from_sector_baskets("2026-09-10", con=con)   # 不指定来源
        assert r1["panels"] == 1
        con.execute(
            "UPDATE fact_sector_stock_daily_generation SET fund_flow_1d = NULL "
            "WHERE trade_date='2026-09-10'"
        )
        r2 = baskets.sync_from_sector_baskets("2026-09-10", con=con)   # 探测不到口径
        assert r2["panels"] == 0 and r2["stale_removed"] == 1
        assert con.execute(
            "SELECT count(*) FROM fact_theme_flow_daily WHERE trade_date='2026-09-10'"
        ).fetchone()[0] == 0, "日更入口未撤销失效面板"
    finally:
        con.close()


def test_revoke_all_leaves_vendor_panels_alone(patched):
    """撤销只清本模块写的面板, 供应商原生面板不受影响。"""
    from market_feature_store.sync import sync_theme_capital_from_baskets as baskets

    connect = patched
    con = connect()
    try:
        con.execute(
            "INSERT INTO fact_theme_flow_daily (trade_date, theme_code, theme_name, "
            "total_fund, source) VALUES ('2026-09-10','T9','供应商面板',42.0,'fupanhui')"
        )
        r = baskets.sync_from_sector_baskets("2026-09-10", con=con)
        assert r["panels"] == 0
        assert con.execute(
            "SELECT total_fund FROM fact_theme_flow_daily WHERE theme_code='T9'"
        ).fetchone()[0] == 42.0, "误删了供应商原生面板"
    finally:
        con.close()


def test_auto_falls_through_for_5d_gap(patched, monkeypatch, tmp_path):
    """归档补不上的 5 日缺口, auto 必须接着走历史接口, 不能永远重放。"""
    connect = patched
    con = connect()
    try:
        _seed(con, "2026-09-11")
    finally:
        con.close()
    monkeypatch.setattr(ff, "RAW_DIR", tmp_path)
    monkeypatch.setattr(ff, "MIN_RECORDS", 1)
    # 归档只有 1 日值, 没有 5 日值
    ff.capture_raw_snapshot(
        "2026-09-11", raw={"300308": (1e8, None), "300502": (2e8, None)},
        out_dir=tmp_path, inferred=True,
    )
    hist_calls: list[str] = []

    def fake_hist(ts, **k):
        hist_calls.append(ts)
        return {f"2026-09-{d:02d}": 1e8 for d in (3, 4, 7, 8, 9, 10, 11)}

    monkeypatch.setattr(ff, "fetch_flow_history", fake_hist)
    monkeypatch.setattr(ff, "fetch_flow_snapshot",
                        lambda: pytest.fail("有归档不应联网取快照"))
    s = ff.sync("2026-09-11", mode="auto")
    assert s["mode"] == "auto:snapshot+history"
    assert hist_calls, "重放后仍缺 5 日值, 却没调用历史接口"
    con = connect(read_only=True)
    try:
        assert con.execute(
            "SELECT count(*) FROM fact_sector_stock_daily_generation "
            "WHERE trade_date='2026-09-11' AND source='local:stitch' "
            "AND fund_flow_5d IS NULL"
        ).fetchone()[0] == 0, "5 日缺口未被补上"
    finally:
        con.close()


def test_short_history_is_marked_not_retried_forever(patched, monkeypatch):
    """上市不满 5 天: 该日永远算不出 5 日值, 必须留痕退出待补集, 而非每轮重拉。"""
    connect = patched
    con = connect()
    try:
        _seed(con, "2026-09-10")
    finally:
        con.close()
    calls: list[str] = []

    def fake_hist(ts, **k):
        calls.append(ts)
        return {"2026-09-09": 1e8, "2026-09-10": 2e8}   # 上游全部可得历史就这两天

    monkeypatch.setattr(ff, "fetch_flow_history", fake_hist)
    s1 = ff.sync_history(["2026-09-10"], concurrency=1)
    assert s1["days"][0]["5d_gap_marked"] == 2
    con = connect(read_only=True)
    try:
        assert con.execute(
            "SELECT count(*) FROM ops_fund_flow_5d_gap WHERE trade_date='2026-09-10'"
        ).fetchone()[0] == 2
    finally:
        con.close()

    calls.clear()
    s2 = ff.sync_history(["2026-09-10"], concurrency=1)
    assert calls == [], "结构性不足的 5 日缺口仍在每轮重拉"
    assert s2["codes"] == 0


def test_empty_upstream_dict_is_not_success(patched, monkeypatch):
    """历史接口全返回 {} 时不得记成拉取成功——否则 rc=0、收据 ok=True。"""
    connect = patched
    con = connect()
    try:
        _seed(con, "2026-09-10")
    finally:
        con.close()
    monkeypatch.setattr(ff, "fetch_flow_history", lambda ts, **k: {})
    s = ff.sync_history(["2026-09-10"], concurrency=1)
    assert s["codes"] == 2 and s["fetched"] == 0 and s["empty"] == 2


def test_caliber_switch_removes_previous_panels(patched):
    """同日换口径重建: 旧口径的面板必须一并撤销, 不能两套口径共存。"""
    from market_feature_store.sync import sync_theme_capital_from_baskets as baskets

    connect = patched
    con = connect()
    try:
        con.executemany(
            """
            INSERT INTO fact_sector_stock_daily_generation
                (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
                 stock_ts_code, stock_name, amount, fund_flow_1d, source)
            VALUES (?,'legacy',?,?,?,?,?,?,?)
            """,
            [("2026-09-10", "990020.FP", "东财口径题材", "000001.SZ", "A", 10.0, 3.0,
              "local:stitch")],
        )
        r1 = baskets.sync_from_sector_baskets("2026-09-10", con=con,
                                              member_source="local:stitch")
        assert r1["panels"] == 1
        # 换成复盘会口径的成分（不同题材）
        con.execute(
            "UPDATE fact_sector_stock_daily_generation SET fund_flow_1d = NULL "
            "WHERE trade_date='2026-09-10' AND source='local:stitch'"
        )
        con.execute(
            """
            INSERT INTO fact_sector_stock_daily_generation
                (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
                 stock_ts_code, stock_name, amount, fund_flow_1d, source)
            VALUES ('2026-09-10','legacy','990021.FP','复盘会口径题材','600519.SH','B',
                    20.0, 4.0, 'fupanhui')
            """
        )
        r2 = baskets.sync_from_sector_baskets("2026-09-10", con=con,
                                              member_source="fupanhui")
        assert r2["panels"] == 1 and r2["stale_removed"] == 1
        rows = con.execute(
            "SELECT theme_code, source FROM fact_theme_flow_daily "
            "WHERE trade_date='2026-09-10' ORDER BY 1"
        ).fetchall()
        assert [r[0] for r in rows] == ["990021.FP"], f"旧口径面板仍在: {rows}"
    finally:
        con.close()
