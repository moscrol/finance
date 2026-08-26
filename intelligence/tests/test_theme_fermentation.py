"""theme_fermentation：发酵摘要纯函数——逐交易日委托盘面袋口径回看窗口。

Spec: docs/superpowers/specs/2026-08-26-watchlist-digest-pack-design.md §3.3 P1
台账: R-20260827-01（P1a 发酵摘要：委托口径 + 快照合同）

口径纪律（机械核查在本文件）：双红/涨停热度判定不得在本模块重写——
逐日委托 market_watch_pack._query_dual_red / _query_limit_heat；
本模块自有 SQL 只许碰交易日历（fact_market_daily）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb
import pytest

from intelligence.services import theme_fermentation as tf

TRADE_WORD_RE = re.compile(r"买入|卖出|加仓|减仓|现在做多|现在做空")


def _db(tmp_path: Path) -> Path:
    """五个交易日的窗口夹具：电力设备三天双红（其中两天连红收尾）、两天在热度榜。"""

    path = tmp_path / "market.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        """
        create table fact_market_daily(
          trade_date date,
          market_stage varchar,
          stage_day integer,
          total_amount double,
          amount_vs_yesterday_pct double,
          volume_state varchar,
          limit_up integer,
          limit_down integer,
          sh_index_pct_chg double
        )
        """
    )
    con.execute(
        "insert into fact_market_daily values "
        "('2026-08-18', '反弹阶段', 1, 20000, 0, '缩量', 50, 1, 0.1),"
        "('2026-08-19', '反弹阶段', 2, 21000, 5, '放量', 60, 0, 0.5),"
        "('2026-08-20', '反弹阶段', 3, 20500, -2, '缩量', 55, 0, 0.2),"
        "('2026-08-21', '反弹阶段', 4, 22000, 7, '放量', 70, 0, 0.8),"
        "('2026-08-22', '反弹阶段', 5, 23000, 4, '放量', 75, 0, 0.6)"
    )
    con.execute(
        """
        create table fact_sector_daily(
          trade_date date,
          sector_name varchar,
          pct_chg double,
          diff_ratio double,
          amount double
        )
        """
    )
    # 电力设备：08-19 / 08-21 / 08-22 满足严格双红；08-18 边际量不达标、08-20 无行。
    con.execute(
        "insert into fact_sector_daily values "
        "('2026-08-18', '电力设备', 1.0, 5.0, 600),"
        "('2026-08-19', '电力设备', 3.2, 12.0, 610),"
        "('2026-08-21', '电力设备', 2.5, 15.0, 700),"
        "('2026-08-22', '电力设备', 3.0, 13.0, 650),"
        "('2026-08-22', '固态电池', 2.2, 11.0, 520)"
    )
    con.execute(
        """
        create table fact_theme_limit_heat_daily(
          trade_date date,
          sector_name varchar,
          limit_up_count integer,
          market_share double
        )
        """
    )
    con.execute(
        "insert into fact_theme_limit_heat_daily values "
        "('2026-08-20', '电力设备', 15, 0.1),"
        "('2026-08-22', '电力设备', 25, 0.2),"
        "('2026-08-22', '储能', 30, 0.3)"
    )
    con.close()
    return path


def test_summary_counts_streak_and_peak(tmp_path: Path) -> None:
    db = _db(tmp_path)
    out = tf.trace_sectors_fermentation(
        (("电力设备板块", "电力设备"),),
        market_db_path=db,
        standing_date="2026-08-22",
        window=5,
    )
    assert len(out) == 1
    s = out[0]
    assert s.subject == "电力设备板块"
    assert s.sector_name == "电力设备"
    assert s.window_days == 5
    assert s.window_start == "2026-08-18"
    assert s.dual_red_days == 3
    assert s.first_dual_red == "2026-08-19"
    assert s.latest_dual_red == "2026-08-22"
    # 08-21 + 08-22 连续两个交易日双红收尾。
    assert s.dual_red_streak == 2
    assert s.heat_days == 2
    assert s.peak_limit_up == 25
    assert s.peak_limit_up_date == "2026-08-22"
    assert len(s.daily) == 5


def test_zero_hit_subject_gets_zero_summary_not_crash(tmp_path: Path) -> None:
    db = _db(tmp_path)
    out = tf.trace_sectors_fermentation(
        (("锂矿", "锂矿"),),
        market_db_path=db,
        standing_date="2026-08-22",
        window=5,
    )
    assert len(out) == 1
    s = out[0]
    assert s.dual_red_days == 0
    assert s.heat_days == 0
    assert s.first_dual_red is None
    assert s.peak_limit_up is None
    assert s.dual_red_streak == 0


def test_window_clips_to_available_calendar(tmp_path: Path) -> None:
    db = _db(tmp_path)
    out = tf.trace_sectors_fermentation(
        (("电力设备", "电力设备"),),
        market_db_path=db,
        standing_date="2026-08-22",
        window=30,
    )
    assert out[0].window_days == 5  # 日历只有 5 个交易日，不虚报窗口。


def test_no_calendar_or_no_db_returns_empty(tmp_path: Path) -> None:
    db = _db(tmp_path)
    assert (
        tf.trace_sectors_fermentation(
            (("电力设备", "电力设备"),),
            market_db_path=db,
            standing_date="2020-01-01",
            window=5,
        )
        == ()
    )
    assert (
        tf.trace_sectors_fermentation(
            (("电力设备", "电力设备"),),
            market_db_path=tmp_path / "missing.duckdb",
            standing_date="2026-08-22",
            window=5,
        )
        == ()
    )
    assert (
        tf.trace_sectors_fermentation(
            (),
            market_db_path=db,
            standing_date="2026-08-22",
        )
        == ()
    )


def test_batch_queries_bags_once_per_day_not_per_subject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path)
    calls = {"dual": 0, "heat": 0}
    real_dual = tf._query_dual_red
    real_heat = tf._query_limit_heat

    def counting_dual(con, standing):
        calls["dual"] += 1
        return real_dual(con, standing)

    def counting_heat(con, standing):
        calls["heat"] += 1
        return real_heat(con, standing)

    monkeypatch.setattr(tf, "_query_dual_red", counting_dual)
    monkeypatch.setattr(tf, "_query_limit_heat", counting_heat)
    out = tf.trace_sectors_fermentation(
        (("电力设备", "电力设备"), ("固态电池", "固态电池")),
        market_db_path=db,
        standing_date="2026-08-22",
        window=5,
    )
    assert len(out) == 2
    # 逐日各查一次袋，主体数不放大查询数。
    assert calls == {"dual": 5, "heat": 5}


def test_text_numbers_all_in_snapshot_dict_and_no_trade_words(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    s = tf.trace_sectors_fermentation(
        (("电力设备板块", "电力设备"),),
        market_db_path=db,
        standing_date="2026-08-22",
        window=5,
    )[0]
    text = s.text()
    blob = json.dumps(s.to_dict(), ensure_ascii=False)
    for number in re.findall(r"\d+(?:\.\d+)?", text.replace("-", "")):
        assert number in blob.replace("-", ""), f"摘要数字 {number} 不在快照 dict"
    assert not TRADE_WORD_RE.search(text)
    assert "在袋" in text and "在榜" in text  # 榜有截断，措辞必须是袋内口径。


def test_module_contains_no_second_caliber_sql() -> None:
    """口径棘轮：双红/热度判定只能在 market_watch_pack；本模块只许碰日历表。"""

    source = Path(tf.__file__).read_text(encoding="utf-8")
    for banned in (
        "fact_sector_daily",
        "fact_theme_limit_heat_daily",
        "DOUBLE_RED",
        "diff_ratio",
        "duckdb.connect",
    ):
        assert banned not in source, f"theme_fermentation 出现第二份口径痕迹: {banned}"
    assert "fact_market_daily" in source  # 日历查询留在本模块，防止误搬进袋模块。
