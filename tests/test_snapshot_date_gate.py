"""东财快照日期闸（工单 #32）：快照实际日期 ≠ 所传 trade_date 时一行都不许写。

事故形状（2026-07-20 / 08-06）：事后补历史日时调了只有「最新」语义的快照，把次日截面贴了历史日期，
整天 5500 行逐股与次日相同。模块 docstring 早就写了「非交易日调用会把上一交易日写到所传日期」，
但代码不拦——警告写在文档里等于没写。现在用每行自带的 ``f297``（行情交易日期）对账。
"""
from __future__ import annotations

import pytest

from market_feature_store.sync import sync_eastmoney_stock_snapshot as em


def _row(code="600000", f297=20260720, **over) -> dict:
    row = {"f12": code, "f14": "某股", "f2": 10.0, "f3": 1.5, "f18": 9.85, "f6": 1.2e8, "f8": 3.4, "f297": f297}
    row.update(over)
    return row


def _run(monkeypatch: pytest.MonkeyPatch, rows: list[dict], trade_date: str, **kw):
    """桩掉连库与请求，解析与闸门原样跑；返回 (截到的写入表, 返回的 stats)。"""
    captured: dict[str, object] = {}

    class _Con:
        def execute(self, *a, **k):
            return self

        def fetchone(self):
            return (0, 0, None, None)

        def register(self, name, df):
            captured[name] = df

        def unregister(self, *a, **k):
            return None

        def close(self):
            return None

    monkeypatch.setattr(em, "init_db", lambda *a, **k: None)
    monkeypatch.setattr(em, "connect", lambda *a, **k: _Con())
    monkeypatch.setattr(em, "ensure_stock_daily_columns", lambda con: None)
    monkeypatch.setattr(em, "fetch_snapshot", lambda **k: rows)
    stats = em.sync_fact_stock_daily_snapshot(trade_date=trade_date, **kw)
    return captured.get("_buf_df"), stats


class TestSnapshotTradeDate:
    def test_reads_majority_date_from_f297(self):
        rows = [_row(f297=20260721)] * 8 + [_row(code="600001", f297=20260601)] * 2  # 停牌股停在旧日期是正常的
        assert em.snapshot_trade_date(rows) == "2026-07-21"

    def test_unrecognizable_when_f297_missing_or_split(self):
        assert em.snapshot_trade_date([_row(f297=None), _row(f297="-")]) is None
        assert em.snapshot_trade_date([]) is None
        # 两个日期各占一半，谁都不到多数线 → 认不出，不猜
        rows = [_row(f297=20260720)] * 5 + [_row(f297=20260721)] * 5
        assert em.snapshot_trade_date(rows) is None

    def test_f297_is_requested(self):
        assert "f297" in em.EM_FIELDS


class TestGate:
    def test_misdated_snapshot_is_refused_and_writes_nothing(self, monkeypatch):
        """07-20 事故复现：拿 07-21 的快照写 07-20 → 抛，且没有任何行进到写入表。"""
        with pytest.raises(em.SnapshotMisdated, match="2026-07-21"):
            _run(monkeypatch, [_row(f297=20260721)], trade_date="2026-07-20")

    def test_unrecognizable_date_is_refused(self, monkeypatch):
        """认不出日期也拒写——不给「没有 f297」的响应发通行证。"""
        with pytest.raises(em.SnapshotMisdated, match="认不出"):
            _run(monkeypatch, [_row(f297=None)], trade_date="2026-07-20")

    def test_same_day_snapshot_writes_normally(self, monkeypatch):
        df, stats = _run(monkeypatch, [_row(f297=20260720)], trade_date="2026-07-20")
        assert df is not None and len(df) == 1
        assert stats["source"] == "eastmoney:snapshot" and stats["snapshot_trade_date"] == "2026-07-20"

    def test_explicit_override_writes_with_misdated_source(self, monkeypatch):
        """显式放行才写，且 source 带 -misdated——事后能从库里认出这批不是当天采的。"""
        df, stats = _run(monkeypatch, [_row(f297=20260721)], trade_date="2026-07-20", allow_misdated=True)
        assert df is not None and len(df) == 1
        assert df.iloc[0]["source"] == "eastmoney:snapshot-misdated"
        assert stats["source"] == "eastmoney:snapshot-misdated" and stats["snapshot_trade_date"] == "2026-07-21"
