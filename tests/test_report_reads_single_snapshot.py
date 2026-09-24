"""体检/报告类读取必须绑定单快照。

与 ``test_hithink_sector_preview.py`` 里的换池预览同一缺陷类：自动提交下**每条 SELECT
各取一次快照**，于是一份由多条 SELECT 拼出来的报告，可以由「从未同时成立」的数字组成。
这类报告比直接报错危险——它看上去完全正常。

这里用真实第二连接提交，不用 mock：mock 只能证明"我以为的并发"，证不了引擎的实际可见性。
"""
from __future__ import annotations

import duckdb
import pytest

from market_feature_store import query as query_mod
from market_feature_store.reports.daily_review import collect_daily_review
from market_feature_store.sector_universe import SectorUniverseStore

DAY = "2026-09-02"
PREV = "2026-09-01"


@pytest.fixture
def db_path(tmp_path):
    """落盘而非 :memory:——两条连接要共享同一个库才谈得上并发可见性。"""
    path = tmp_path / "health.duckdb"
    with duckdb.connect(str(path)) as c:
        c.execute(
            """
            CREATE TABLE dim_sector (
                sector_ts_code TEXT, sector_name TEXT, sw_l1 TEXT);
            CREATE TABLE fact_sector_daily (
                trade_date DATE, sector_ts_code TEXT, diff_ratio DOUBLE, sw_l1 TEXT);
            CREATE TABLE fact_sector_stock_daily (
                trade_date DATE, sector_ts_code TEXT, stock_ts_code TEXT, sw_l1 TEXT);
            CREATE TABLE fact_market_daily (trade_date DATE, total_amount DOUBLE);
            CREATE TABLE fact_stock_daily (
                trade_date DATE, stock_ts_code TEXT, close DOUBLE);

            INSERT INTO dim_sector VALUES
                ('885001.TI', '甲板块', '电子'), ('885002.TI', '乙板块', NULL);
            INSERT INTO fact_sector_daily VALUES
                ('2026-09-02', '885001.TI', 12.5, '电子');
            INSERT INTO fact_sector_stock_daily VALUES
                ('2026-09-02', '885001.TI', '600001.SH', '电子');
            INSERT INTO fact_market_daily VALUES ('2026-09-02', 9000.0);
            INSERT INTO fact_stock_daily VALUES
                ('2026-09-02', '600001.SH', 10.0);
            """
        )
    return path


class Passthrough:
    """转发给真连接，但 close() 空转。

    health() 在 finally 里 con.close()——直接把夹具连接交给它，第二次调用就
    Connection already closed。那是**脚手架**坏了，不是被测行为坏了；不隔开的话
    会把它误读成实现 bug。连接的生命周期统一交给夹具的 with 管。
    """

    def __init__(self, con):
        self._con = con

    def execute(self, sql, *args):
        return self._con.execute(sql, *args)

    def close(self):
        pass


def _health_on(monkeypatch, con):
    """把 health() 的连接换成夹具连接；它自己 connect()，不接受外部连接。"""
    monkeypatch.setattr(query_mod, "connect", lambda *a, **k: con)
    return query_mod.health()


def test_health_uses_one_snapshot_when_writer_commits_between_reads(db_path, monkeypatch):
    """写者在 dim_sector 读完之后提交；体检报告不得拼「旧维表 + 新事实表」。"""
    with duckdb.connect(str(db_path)) as reader, duckdb.connect(str(db_path)) as writer:
        before = _health_on(monkeypatch, Passthrough(reader))

        class ConcurrentCommit(Passthrough):
            """转发给真连接，并在指定读取之后让第二连接真提交一次。"""

            fired = False

            def execute(self, sql, *args):
                cursor = self._con.execute(sql, *args)
                if "FROM dim_sector" in sql and not self.fired:
                    self.fired = True
                    writer.execute("BEGIN TRANSACTION")
                    writer.execute(
                        "INSERT INTO fact_stock_daily VALUES ('2026-09-02','600002.SH',20.0)"
                    )
                    writer.execute(
                        "INSERT INTO fact_sector_stock_daily VALUES "
                        "('2026-09-02','885002.TI','600002.SH','机械')"
                    )
                    writer.execute("COMMIT")
                return cursor

        racing = ConcurrentCommit(reader)
        during = _health_on(monkeypatch, racing)
        after = _health_on(monkeypatch, Passthrough(reader))

        assert racing.fired, "并发提交没触发，这条用例就什么都没证明"
        # 核心判据：跨快照拼接会让 during 既不等于 before 也不等于 after。
        assert during == before
        # 写者确实落了盘——否则上一条断言可能只是因为没人写过。
        assert after["fact_stock_daily"]["rows"] == 2
        assert after["fact_sector_stock_daily"]["sectors"] == 2
        assert after != before


def test_health_report_is_internally_consistent_under_concurrent_writer(db_path, monkeypatch):
    """coverage_latest 拿自己早先的 dim_sector_total 和最后一次读的 covered 相比。

    这是**自指**的拼接点：同一份报告内部两个数字来自不同时刻，比值就会失真。
    """
    with duckdb.connect(str(db_path)) as reader, duckdb.connect(str(db_path)) as writer:

        class CommitAfterDimSector(Passthrough):
            fired = False

            def execute(self, sql, *args):
                cursor = self._con.execute(sql, *args)
                if "FROM dim_sector" in sql and not self.fired:
                    self.fired = True
                    # 只给维表加 1 个、给事实表加 2 个板块：让 covered 能超过**陈旧的**
                    # dim_sector 总数。不拉开这个差，断言 2<=2 会靠巧合变绿——不能鉴别的
                    # 断言等于没有断言。
                    writer.execute(
                        "INSERT INTO dim_sector VALUES ('885003.TI','丙板块','化工')"
                    )
                    writer.execute(
                        "INSERT INTO fact_sector_stock_daily VALUES "
                        "('2026-09-02','885003.TI','600003.SH','化工'),"
                        "('2026-09-02','885004.TI','600004.SH','医药')"
                    )
                return cursor

        racing = CommitAfterDimSector(reader)
        report = _health_on(monkeypatch, racing)
        assert racing.fired
        cov = report["coverage_latest"]
        # 有成分股的板块数不可能超过维表总数——超了就说明两个数字来自不同快照。
        assert cov["sectors_with_stocks"] <= cov["dim_sector_total"]
        assert cov["dim_sector_total"] == report["dim_sector"]["total"]


def test_health_refuses_to_read_inside_callers_uncommitted_transaction(db_path, monkeypatch):
    """不允许体检读未提交行。拒绝有代价，代价写在这里而不是留给下个人撞。"""
    from market_feature_store.db import SnapshotUnavailableError

    with duckdb.connect(str(db_path)) as con:
        con.execute("BEGIN TRANSACTION")
        con.execute("INSERT INTO dim_sector VALUES ('885099.TI','未提交','未知')")
        with pytest.raises(SnapshotUnavailableError):
            _health_on(monkeypatch, Passthrough(con))
        con.execute("ROLLBACK")
        assert _health_on(monkeypatch, Passthrough(con))["dim_sector"]["total"] == 2


# --------------------------------------------------------------------------
# 当日复盘：这份是给人看的最终产物，拼接了就是一份自洽却从未同时成立的复盘。
# --------------------------------------------------------------------------


@pytest.fixture
def review_db(tmp_path):
    """用真 schema 建库，不手抄列。

    fact_sector_daily 是**视图**（底下是 _generation 表，且要有 published 表头才放行）。
    这里走视图里那条 legacy 旁路：无已发布表头时放行 snapshot_id='legacy' 的行——
    省掉整套发布机制，夹具才不会因为发布逻辑变动而连坐。
    """
    path = tmp_path / "review.duckdb"
    with duckdb.connect(str(path)) as c:
        SectorUniverseStore.ensure_schema(c)
        c.execute(
            "INSERT INTO fact_market_daily (trade_date, total_amount) "
            "VALUES ('2026-09-01', 8000), ('2026-09-02', 9000)"
        )
        c.execute(
            "INSERT INTO dim_sector (sector_ts_code, sector_name, sw_l1) "
            "VALUES ('885001.TI','甲板块','电子')"
        )
        c.execute(
            "INSERT INTO fact_sector_daily_generation (trade_date, sector_ts_code, "
            "sector_name, sw_l1, pct_chg, diff_ratio, amount, sector_universe_snapshot_id) "
            "VALUES ('2026-09-02','885001.TI','甲板块','电子',3.0,25.0,400,'legacy')"
        )
        c.execute(
            "INSERT INTO fact_sector_stock_daily_generation (trade_date, sector_ts_code, "
            "stock_ts_code, sw_l1, price, pct_chg, amount, sector_universe_snapshot_id) "
            "VALUES ('2026-09-02','885001.TI','600001.SH','电子',10.0,5.0,100,'legacy')"
        )
    return path


def _stable(report: dict) -> dict:
    """副本去掉生成时间。不去的话断言会因为**时钟**而红，不是因为缺陷。"""
    return {k: v for k, v in report.items() if k != "generated_at"}


def test_daily_review_uses_one_snapshot_when_writer_commits_between_reads(
    review_db, tmp_path
):
    """市场总量读完之后写者改了板块行；复盘不得拼「旧市场 + 新板块」。"""
    out, chart = tmp_path / "r.md", tmp_path / "c.png"
    with duckdb.connect(str(review_db)) as reader, duckdb.connect(str(review_db)) as writer:
        before = collect_daily_review(reader, DAY, out_path=out, chart_path=chart)

        class ConcurrentCommit(Passthrough):
            fired = False

            def execute(self, sql, *args):
                cursor = self._con.execute(sql, *args)
                if "FROM fact_market_daily" in sql and not self.fired:
                    self.fired = True
                    writer.execute("BEGIN TRANSACTION")
                    # 把甲板块从双红打下去：后续那几条板块读取就会看到另一个世界。
                    writer.execute(
                        "UPDATE fact_sector_daily_generation "
                        "SET diff_ratio = 2.0, pct_chg = -1.0 WHERE trade_date = ?",
                        [DAY],
                    )
                    writer.execute("COMMIT")
                return cursor

        racing = ConcurrentCommit(reader)
        during = collect_daily_review(racing, DAY, out_path=out, chart_path=chart)
        after = collect_daily_review(reader, DAY, out_path=out, chart_path=chart)

        assert racing.fired, "并发提交没触发，这条用例就什么都没证明"
        assert _stable(during) == _stable(before)
        # 写者确实落了盘——否则上一条可能只是因为没人写过。
        assert _stable(after) != _stable(before)


def test_daily_review_refuses_to_read_inside_callers_uncommitted_transaction(
    review_db, tmp_path
):
    """复盘会被当成证据存档，所以不允许它读未提交行。"""
    from market_feature_store.db import SnapshotUnavailableError

    out, chart = tmp_path / "r.md", tmp_path / "c.png"
    with duckdb.connect(str(review_db)) as con:
        con.execute("BEGIN TRANSACTION")
        con.execute(
            "UPDATE fact_sector_daily_generation SET pct_chg = 99.0 WHERE trade_date = ?",
            [DAY],
        )
        with pytest.raises(SnapshotUnavailableError):
            collect_daily_review(con, DAY, out_path=out, chart_path=chart)
        con.execute("ROLLBACK")
        assert collect_daily_review(con, DAY, out_path=out, chart_path=chart)
