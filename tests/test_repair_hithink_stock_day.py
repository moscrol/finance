"""同花顺 dump 修复 canonical 个股日行情（2026-09-11 事故修复）。

夹具自造小库 + 小 parquet，不碰真生产库、不读真 dump。
覆盖：五类处置（换源/除息校准/整行保留/停牌保留/IPO 发行价口径/新增票）、
fail-closed 断言、其他日期指纹、保留行逐字段不动。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import pytest

from market_feature_store.sync import repair_hithink_stock_day as rep
from market_feature_store.sync.repair_hithink_stock_day import RepairRefused

DAILY_DDL = """
CREATE TABLE fact_stock_daily (
    trade_date DATE,
    stock_ts_code VARCHAR,
    stock_name VARCHAR,
    close DOUBLE,
    pre_close DOUBLE,
    pct_chg DOUBLE,
    amount DOUBLE,
    turnover DOUBLE,
    source VARCHAR,
    updated_at TIMESTAMP,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    volume DOUBLE,
    PRIMARY KEY (trade_date, stock_ts_code)
)
"""
ADJ_DDL = """
CREATE TABLE fact_stock_adjustment_hithink (
    stock_ts_code VARCHAR,
    ex_date DATE,
    dividend_per_share DOUBLE,
    per_share_bonus DOUBLE,
    allotment_ratio DOUBLE,
    allotment_price DOUBLE,
    currency VARCHAR,
    source VARCHAR,
    updated_at TIMESTAMP,
    PRIMARY KEY (stock_ts_code, ex_date)
)
"""

TD = date(2026, 9, 11)
PREV = date(2026, 9, 10)


def _ms(d: date) -> int:
    """上海零点毫秒（与 dump 契约一致）。"""
    import datetime as dt

    return int(
        dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() * 1000
    ) - 8 * 3600 * 1000


def _write_parquet(path: Path, rows: list[tuple]) -> None:
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            """
            CREATE TABLE t (
                thscode VARCHAR, currency VARCHAR, interval VARCHAR, adjusted VARCHAR,
                date_ms BIGINT, open_price DOUBLE, high_price DOUBLE, low_price DOUBLE,
                close_price DOUBLE, volume DOUBLE, turnover DOUBLE
            )
            """
        )
        con.executemany("INSERT INTO t VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.execute(f"COPY t TO '{path}' (FORMAT PARQUET)")
    finally:
        con.close()


def _bar(code: str, d: date, o: float, h: float, lo: float, c: float,
         vol_shares: float, turnover_yuan: float) -> tuple:
    return (code, "CNY", "1d", "none", _ms(d), o, h, lo, c, vol_shares, turnover_yuan)


def _old_row(code: str, name: str, close: float, pre: float, pct: float,
             amount: float, rate: float, vol_lots: float,
             o: float, h: float, lo: float, d: date = TD) -> tuple:
    return (d, code, name, close, pre, pct, amount, rate,
            "eastmoney:snapshot", "2026-09-11 18:00:00", o, h, lo, vol_lots)


@pytest.fixture()
def world(tmp_path):
    """小世界：5 只共同行（含 1 除息 1 IPO 1 北交所保留 1 amount 边界）+
    1 停牌旧独有 + 1 dump 新增 + 1 其他日期。"""
    db_path = tmp_path / "mini.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute(DAILY_DDL)
    con.execute(ADJ_DDL)
    # 旧表 09-11 行
    old_rows = [
        # 普通行 000001: dump close 10.02, prev 10.00 → pct 0.2
        _old_row("000001.SZ", "平安银行", 10.02, 10.00, 0.2, 50.1234, 1.1, 5000.0,
                 9.99, 10.05, 9.98),
        # 除息行 600000: prev 裸收 20.00, 分红 0.50 → pre 19.50; close 19.70 → pct 1.03
        _old_row("600000.SH", "浦发银行", 19.70, 19.50, 1.03, 30.0, 0.9, 3000.0,
                 19.55, 19.8, 19.5),
        # IPO 行 688801: 发行价口径 pre 142.18 / pct 179.22, dump 无昨日 bar
        _old_row("688801.SH", "N测试-U", 397.0, 142.18, 179.22, 56.4795, 76.02,
                 136087.0, 410.0, 475.0, 386.99),
        # 北交所整行保留 920045: dump 侧 amount/volume 都不同
        _old_row("920045.BJ", "蘅东光", 583.2, 531.1, 9.81, 12.4085, 8.04, 22654.0,
                 515.5, 584.99, 515.5),
        # amount 边界行 600176: 旧 113.6007, dump 换算 113.6006
        _old_row("600176.SH", "中国巨石", 44.66, 43.46, 2.76, 113.6007, 6.6,
                 2621416.0, 42.3, 44.97, 41.5),
        # 停牌旧独有 688291: close=pre_close, amount NULL
        ("2026-09-11", "688291.SH", "停牌甲", 45.22, 45.22, 0.0, None, None,
         "eastmoney:snapshot", "2026-09-11 18:00:00", None, None, None, None),
        # 其他日期行（指纹哨兵）
        ("2026-09-10", "000001.SZ", "平安银行", 10.00, 9.98, 0.2, 48.0, 1.0,
         "eastmoney:snapshot", "2026-09-10 18:00:00", 9.9, 10.01, 9.89, 4800.0),
    ]
    con.executemany("INSERT INTO fact_stock_daily VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    old_rows)
    # 除息事件（纯现金）
    con.execute(
        "INSERT INTO fact_stock_adjustment_hithink VALUES (?,?,?,?,?,?,?,?,?)",
        ("600000.SH", TD, 0.5, 0.0, 0.0, 0.0, "CNY",
         "hithink:adjustment-factors", "2026-09-08 22:00:00"),
    )
    con.close()

    pq = tmp_path / "dump.parquet"
    bars = [
        # 普通行：09-10 + 09-11
        _bar("000001.SZ", PREV, 9.9, 10.01, 9.89, 10.00, 480000.0, 4_800_000_000.0),
        _bar("000001.SZ", TD, 9.99, 10.05, 9.98, 10.02, 500000.0, 5_012_340_000.0),
        # 除息行
        _bar("600000.SH", PREV, 19.9, 20.1, 19.8, 20.00, 100.0, 2_000.0),
        _bar("600000.SH", TD, 19.55, 19.8, 19.5, 19.70, 300000.0, 3_000_000_000.0),
        # IPO：只有当日
        _bar("688801.SH", TD, 410.0, 475.0, 386.99, 397.0, 13_608_674.0,
             5_647_951_616.16),
        # 北交所：close 一致，amount/volume 不同（应整行保留）
        _bar("920045.BJ", PREV, 520.0, 535.0, 518.0, 531.1, 100.0, 5_000.0),
        _bar("920045.BJ", TD, 515.5, 584.99, 515.5, 583.2, 2_225_367.0,
             1_218_226_818.3),
        # amount 边界：dump 元值换算 round4 = 113.6006
        _bar("600176.SH", PREV, 43.0, 43.5, 42.9, 43.46, 100.0, 4_000.0),
        _bar("600176.SH", TD, 42.3, 44.97, 41.5, 44.66, 262_141_600.0,
             11_360_064_999.58),
        # dump 新增票 302132：09-10 有 bar
        _bar("302132.SZ", PREV, 64.88, 65.48, 63.55, 64.35, 9_813_208.0,
             634_093_804.05),
        _bar("302132.SZ", TD, 64.01, 64.66, 62.82, 63.42, 9_447_135.0,
             598_632_440.33),
    ]
    _write_parquet(pq, bars)

    spec = rep.RepairSpec(
        trade_date=TD,
        keep_codes=("920045.BJ",),
        suspended_keep=("688291.SH",),
        issue_price_codes=("688801.SH",),
        new_code_names={"302132.SZ": "中航成飞"},
        exdiv_codes=("600000.SH",),
        amount_drift_ok={"600176.SH": 0.0001},
        expected={
            "dump_rows": 6,
            "old_rows": 6,
            "common_rows": 5,
            "written_rows": 5,   # 5 共同 − 1 保留 + 1 新增
            "final_rows": 7,     # 6 − 4 被替换 + 5 写入
        },
    )
    return {"db": db_path, "parquet": pq, "spec": spec}


def _rows(con, td=TD):
    return {
        r[0]: r
        for r in con.execute(
            "SELECT stock_ts_code, stock_name, close, pre_close, pct_chg, amount,"
            " turnover, source, open, high, low, volume"
            " FROM fact_stock_daily WHERE trade_date = ? ORDER BY 1", [td]
        ).fetchall()
    }


def test_happy_path(world, tmp_path):
    report = rep.run_repair(
        world["spec"], world["parquet"],
        db_path=world["db"],
        status_json=tmp_path / "status.json",
        report_path=tmp_path / "report.json",
    )
    con = duckdb.connect(str(world["db"]), read_only=True)
    try:
        rows = _rows(con)
    finally:
        con.close()

    assert set(rows) == {
        "000001.SZ", "600000.SH", "688801.SH", "920045.BJ",
        "600176.SH", "688291.SH", "302132.SZ",
    }
    # 普通行换源
    r = rows["000001.SZ"]
    assert r[2] == 10.02 and r[3] == 10.00 and r[4] == 0.2
    assert r[7] == rep.SOURCE_REBUILD
    assert r[1] == "平安银行" and r[6] == 1.1  # 名字/换手率保留
    assert r[5] == 50.1234  # 5012340000/1e8 round4
    assert r[11] == 5000.0  # 500000 股 /100
    # 除息行校准
    r = rows["600000.SH"]
    assert r[3] == 19.50 and r[4] == 1.03 and r[7] == rep.SOURCE_REBUILD
    # IPO 发行价口径保留，行情来自 dump
    r = rows["688801.SH"]
    assert r[3] == 142.18 and r[4] == 179.22 and r[2] == 397.0
    assert r[7] == rep.SOURCE_REBUILD
    # 北交所整行保留：source 不换、值不动
    r = rows["920045.BJ"]
    assert r[5] == 12.4085 and r[11] == 22654.0 and r[7] == "eastmoney:snapshot"
    # amount 边界行取 dump 值
    assert rows["600176.SH"][5] == 113.6006
    # 停牌旧独有保留
    r = rows["688291.SH"]
    assert r[7] == "eastmoney:snapshot" and r[5] is None
    # 新增票
    r = rows["302132.SZ"]
    assert r[1] == "中航成飞" and r[2] == 63.42 and r[3] == 64.35
    assert r[4] == -1.45 and r[6] is None and r[7] == rep.SOURCE_REBUILD

    # 其他日期未动 + 报告/状态落盘
    assert report["post"]["other_dates_unchanged"] is True
    assert report["post"]["final_rows"] == 7
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["ok"] is True and status["trade_date"] == "2026-09-11"
    disk_report = json.loads((tmp_path / "report.json").read_text())
    assert disk_report["evidence"]["field_diffs"]["amount"] == {
        "600176.SH": {"old": 113.6007, "new": 113.6006}
    }
    # 其他日期哨兵行原样
    con = duckdb.connect(str(world["db"]), read_only=True)
    try:
        prev = con.execute(
            "SELECT close, source FROM fact_stock_daily"
            " WHERE trade_date='2026-09-10' AND stock_ts_code='000001.SZ'"
        ).fetchone()
    finally:
        con.close()
    assert prev == (10.00, "eastmoney:snapshot")


def test_roster_drift_refused(world):
    """旧表多出一只白名单外的独有票 → 拒跑且未写入。"""
    con = duckdb.connect(str(world["db"]))
    con.execute(
        "INSERT INTO fact_stock_daily VALUES ('2026-09-11','999999.SH','幽灵',"
        "1.0,1.0,0.0,1.0,1.0,'eastmoney:snapshot','2026-09-11 18:00:00',"
        "1.0,1.0,1.0,1.0)"
    )
    con.close()
    spec = world["spec"]
    object.__setattr__(spec, "expected", {**spec.expected, "old_rows": 7})
    with pytest.raises(RepairRefused, match="旧独有名单"):
        rep.run_repair(spec, world["parquet"], db_path=world["db"])
    con = duckdb.connect(str(world["db"]), read_only=True)
    try:
        assert con.execute(
            "SELECT count(*) FROM fact_stock_daily WHERE trade_date='2026-09-11'"
        ).fetchone()[0] == 7  # 只有手工插的那行，修复未动
    finally:
        con.close()


def test_exdiv_recompute_mismatch_refused(world):
    """除息校准复现不了旧 pre_close → 拒跑。"""
    con = duckdb.connect(str(world["db"]))
    con.execute(
        "UPDATE fact_stock_daily SET pre_close=19.99, pct_chg=-1.45"
        " WHERE trade_date='2026-09-11' AND stock_ts_code='600000.SH'"
    )
    con.close()
    with pytest.raises(RepairRefused, match="pre_close"):
        rep.run_repair(world["spec"], world["parquet"], db_path=world["db"])


def test_amount_drift_beyond_whitelist_refused(world):
    """amount 漂移代码不在白名单 → 拒跑。"""
    spec = world["spec"]
    object.__setattr__(spec, "amount_drift_ok", {})
    with pytest.raises(RepairRefused, match="amount 漂移"):
        rep.run_repair(spec, world["parquet"], db_path=world["db"])


def test_expected_count_mismatch_refused(world):
    """期望计数与实数不符（日期用错/名单漂移）→ 拒跑。"""
    spec = world["spec"]
    object.__setattr__(
        spec, "expected", {**spec.expected, "dump_rows": 9999}
    )
    with pytest.raises(RepairRefused, match="dump_rows"):
        rep.run_repair(spec, world["parquet"], db_path=world["db"])


def test_non_cash_event_refused(world):
    """当日有送转/配股事件 → 校准公式不覆盖，拒跑。"""
    con = duckdb.connect(str(world["db"]))
    con.execute(
        "INSERT INTO fact_stock_adjustment_hithink VALUES"
        " ('000001.SZ','2026-09-11',0.0,0.5,0.0,0.0,'CNY','t','2026-09-08 22:00:00')"
    )
    con.close()
    with pytest.raises(RepairRefused, match="非纯现金"):
        rep.run_repair(world["spec"], world["parquet"], db_path=world["db"])


def test_verify_post_detects_other_date_tamper(world):
    """其他日期指纹变化 → verify_post 拒。"""
    con = duckdb.connect(str(world["db"]))
    before = rep.fingerprint(con)
    con.execute(
        "UPDATE fact_stock_daily SET close=999 WHERE trade_date='2026-09-10'"
    )
    after = rep.fingerprint(con)
    with pytest.raises(RepairRefused, match="其他日期被改动"):
        rep.verify_post(con, world["spec"], before, after, {})
    con.close()


def test_parquet_sha_pin(world):
    """spec 钉了哈希而文件不符 → 拒跑。"""
    spec = world["spec"]
    object.__setattr__(spec, "parquet_sha256", "0" * 64)
    with pytest.raises(RepairRefused, match="哈希"):
        rep.run_repair(spec, world["parquet"], db_path=world["db"])
