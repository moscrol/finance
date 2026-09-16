"""个股技术位本地计算：均线 / UP 线 / 回踩口径 / PIT 截断。

这套口径原先散在三个飞书 skill 里（watchlist-ma、top-gainers-feishu、up-line），
清单存飞书表、指标靠逐只 iFinD 问答，谁也没测过。搬到本地后必须钉住：

* **PIT**：传了 `as_of` 就只能看见那天及以前的行情。上一个教训（D6 拿库尾数据
  答历史问题）就栽在这里，新能力从第一天就得守住。
* **不足期不给数**：样本不满周期宁可给 None，不能拿 3 天均价冒充 MA26。
* **回踩口径**：两条判定都是严格不等式，边界（价==均线）不算命中。
"""

from __future__ import annotations

import math

import duckdb
import pytest

from market_feature_store import query as q
from market_feature_store.db import init_db


@pytest.fixture
def db(monkeypatch):
    con = duckdb.connect()
    init_db(con)

    class _Keep:
        """query 层每次调用都会 close()，内存库一关就没了——这里把 close 吞掉。"""

        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def close(self):
            pass

    monkeypatch.setattr(q, "connect", lambda read_only=False: _Keep(con))
    return con


def _seed(con, code, name, closes, start="2026-01-01"):
    """按交易日顺序写入收盘价序列（用自然日，计算只关心先后）。"""
    base = duckdb.connect().execute(f"SELECT DATE '{start}'").fetchone()[0]
    for i, close in enumerate(closes):
        con.execute(
            "INSERT INTO fact_stock_daily (trade_date, stock_ts_code, stock_name, close, "
            "pre_close, pct_chg, amount, source, updated_at) VALUES (?,?,?,?,?,?,?,?, now())",
            [base.replace(day=1) + __import__("datetime").timedelta(days=i),
             code, name, close, close, 0.0, 1.0, "test"],
        )


def test_ma_and_up_match_hand_computation(db):
    closes = [10.0 + i for i in range(26)]  # 10..35
    _seed(db, "600001.SH", "甲", closes)
    row = q.stock_technicals(["甲"])["rows"][0]

    assert row["ma5"] == pytest.approx(sum(closes[-5:]) / 5)
    assert row["ma26"] == pytest.approx(sum(closes) / 26)
    mean = sum(closes) / 26
    std = math.sqrt(sum((c - mean) ** 2 for c in closes) / 26)  # 总体标准差
    assert row["std26"] == pytest.approx(round(std, 2), abs=0.01)
    assert row["up_value"] == pytest.approx(round(mean + 0.764 * std, 2), abs=0.02)
    assert row["close"] == 35.0


def test_as_of_truncates_to_that_day(db):
    """传 as_of 就只能看见那天及以前——错一天，均线和 UP 线全是另一套数。"""
    _seed(db, "600001.SH", "甲", [10.0] * 26 + [99.0] * 5)
    latest = q.stock_technicals(["甲"])["rows"][0]
    early = q.stock_technicals(["甲"], as_of="2026-01-26")["rows"][0]

    assert latest["trade_date"] == "2026-01-31"
    assert latest["close"] == 99.0
    assert early["trade_date"] == "2026-01-26"
    assert early["close"] == 10.0
    assert early["ma26"] == pytest.approx(10.0)
    assert latest["ma26"] != pytest.approx(early["ma26"])


def test_short_history_yields_none_not_a_fake_average(db):
    """只有 3 天数据时 MA5/MA26 必须是 None，不能拿 3 天均价充数。"""
    _seed(db, "600002.SH", "乙", [10.0, 11.0, 12.0])
    row = q.stock_technicals(["乙"])["rows"][0]

    assert row["close"] == 12.0
    assert row["ma5"] is None
    assert row["ma26"] is None
    assert row["std26"] is None
    assert row["up_value"] is None
    assert row["up_deviation_pct"] is None
    assert row["above_up"] is None


def test_pullback_flags_follow_the_original_skill_semantics(db):
    # 上涨趋势中的回调：MA20 抬不上来、价格跌破 MA10 但仍在 MA20 上方 → 中期回踩
    _seed(db, "600003.SH", "丙", [10.0] * 16 + [20.0] * 10 + [18.0])
    row = q.stock_technicals(["丙"])["rows"][0]

    assert row["ma20"] < row["close"] < row["ma10"], (row["ma20"], row["close"], row["ma10"])
    assert row["pullback_ma10_ma20"] is True
    assert row["above_ma20_pct"] == pytest.approx(
        round((row["close"] - row["ma20"]) / row["ma20"] * 100, 2), abs=0.01
    )


def test_flat_price_is_not_a_pullback(db):
    """价与均线完全相等时不算回踩——严格不等式，不许放宽成 <=。"""
    _seed(db, "600004.SH", "丁", [10.0] * 30)
    row = q.stock_technicals(["丁"])["rows"][0]

    assert row["close"] == row["ma10"] == row["ma20"]
    assert row["pullback_ma10_ma20"] is False
    assert row["pullback_ma5_ma10"] is False


def test_above_up_flag(db):
    _seed(db, "600005.SH", "戊", [10.0] * 25 + [50.0])
    row = q.stock_technicals(["戊"])["rows"][0]
    assert row["close"] > row["up_value"]
    assert row["above_up"] is True


def test_terms_accept_name_full_code_and_bare_digits(db):
    _seed(db, "601127.SH", "赛力斯", [10.0] * 26)
    res = q.stock_technicals(["赛力斯", "601127.SH", "601127"])

    assert len(res["rows"]) == 3
    assert {r["stock_ts_code"] for r in res["rows"]} == {"601127.SH"}
    assert [r["term"] for r in res["rows"]] == ["赛力斯", "601127.SH", "601127"]
    assert res["missing"] == []


def test_unknown_term_reported_once(db):
    _seed(db, "600001.SH", "甲", [10.0] * 26)
    res = q.stock_technicals(["甲", "查无此股"])

    assert [r["term"] for r in res["rows"]] == ["甲"]
    assert res["missing"] == ["查无此股"]  # 恰好一次，不是两次


def test_empty_input_short_circuits(db):
    assert q.stock_technicals([])["rows"] == []
    assert q.stock_technicals(["", "  "])["rows"] == []


def test_bad_window_rejected(db):
    with pytest.raises(ValueError):
        q.stock_technicals(["甲"], windows=(1,))
    with pytest.raises(ValueError):
        q.stock_technicals(["甲"], windows=(9999,))


def test_screen_filters_to_matched_only(db):
    _seed(db, "600003.SH", "丙", [10.0] * 16 + [20.0] * 10 + [18.0])
    _seed(db, "600004.SH", "丁", [10.0] * 30)

    res = q.screen_stock_technicals(["丙", "丁"], screen="pullback")
    assert len(res["rows"]) == 2
    assert [r["stock_name"] for r in res["matched"]] == ["丙"]

    plain = q.screen_stock_technicals(["丙", "丁"])
    assert "matched" not in plain and len(plain["rows"]) == 2


def test_unknown_screen_rejected(db):
    with pytest.raises(ValueError):
        q.screen_stock_technicals(["甲"], screen="随便编一个")


def test_custom_window_is_honoured_and_26_always_present(db):
    _seed(db, "600001.SH", "甲", [float(i) for i in range(1, 61)])
    row = q.stock_technicals(["甲"], windows=(60,))["rows"][0]

    assert row["ma60"] == pytest.approx(sum(range(1, 61)) / 60)
    assert row["ma26"] is not None  # UP 线要用，无论调用方要不要都得算
