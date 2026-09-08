"""东财快照：请求了的字段必须被接住（换手率 f8 曾经采回来又被丢掉）。

2026-09-06 查出来的事故形状：``EM_FIELDS`` 一直请求 ``f8=换手率%``、数据也一直回来，
但解析处硬绑 ``None``，注释理由是「与 mootdx 行口径一致」。代价是**能采到的
23.7 万行也一起丢了**，而且丢得没有痕迹——只有把请求字段表和解析代码对着看才发现得了。
审计侧看到的是「``fact_stock_daily.turnover`` 全库非空 0 行」，看起来像采不到。

所以这里钉两层：
1. **行为**：给一行带 f8 的假响应，turnover 必须落盘；
2. **门禁**：``EM_FIELDS`` 里声明的每个字段，模块里都必须有对应的 ``it.get("fN")``。
   只钉 turnover 挡不住下一次——换个字段还会同样丢。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from market_feature_store.sync import sync_eastmoney_stock_snapshot as em


def _row(**over) -> dict:
    # f297 = 行情自身的交易日期; 与 _run_capture 传的 trade_date 一致, 才过得了日期闸 (见 test_snapshot_date_gate)
    row = {"f12": "600000", "f13": 1, "f14": "浦发银行", "f2": 10.0,
           "f3": 1.5, "f18": 9.85, "f6": 1.2e8, "f8": 3.42, "f297": 20260902}
    row.update(over)
    return row


class TestRequestedFieldsAreConsumed:
    def test_every_requested_field_is_read_somewhere(self) -> None:
        """请求了就必须接。请求字段表与解析代码对不上，就是在白花请求、白丢数据。"""
        src = Path(em.__file__).read_text(encoding="utf-8")
        requested = [f.strip() for f in em.EM_FIELDS.split(",") if f.strip()]
        assert requested, "EM_FIELDS 不应为空"
        unread = [f for f in requested if f'it.get("{f}")' not in src]
        assert unread == [], (
            f"这些字段请求了却没人读：{unread}。"
            "要么接住它、要么从 EM_FIELDS 里去掉——不许请求了扔掉，"
            "那会让审计侧看成「上游采不到」。"
        )

    def test_turnover_field_is_declared(self) -> None:
        assert "f8" in em.EM_FIELDS


def _run_capture(monkeypatch: pytest.MonkeyPatch, rows: list[dict]):
    """跑一次 sync，把真正要写进库的那张 DataFrame 截下来。

    只桩掉「连库」与「发请求」两件事，**解析与装行的代码原样跑**——桩到解析层
    就等于自己跟自己对答案，测不出「f8 被丢掉」这种事。
    """
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
    monkeypatch.setattr(em, "fetch_snapshot", lambda **k: rows)
    em.sync_fact_stock_daily_snapshot(trade_date="2026-09-02")
    return captured.get("_buf_df")


class TestTurnoverLands:
    def test_f8_becomes_turnover(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """端到端：假响应里的 f8=3.42 必须出现在写入行的 turnover 列。"""
        df = _run_capture(monkeypatch, [_row()])
        assert df is not None and len(df) == 1
        assert df.iloc[0]["turnover"] == pytest.approx(3.42)
        assert df.iloc[0]["stock_ts_code"] == "600000.SH"

    def test_missing_f8_stays_null_not_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """来源没给就是 NULL——不许拿 0 顶替。0% 换手率是有含义的读数（停牌当天）。"""
        df = _run_capture(monkeypatch, [_row(f8=None), _row(f12="600001", f8="-")])
        assert df is not None and len(df) == 2
        assert df["turnover"].isna().all()

    def test_zero_turnover_is_preserved(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """真的 0 换手率要存成 0，不能被「假值当空值」的写法吞掉。"""
        df = _run_capture(monkeypatch, [_row(f8=0)])
        assert df is not None
        assert df.iloc[0]["turnover"] == pytest.approx(0.0)

    def test_old_hardcoded_none_does_not_come_back(self) -> None:
        src = Path(em.__file__).read_text(encoding="utf-8")
        assert not re.search(r"None,\s*#\s*turnover", src), "旧的硬绑 None 不该再回来"
