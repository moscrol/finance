"""盘面数据是哪天，必须算出来告知模型，不能靠它自己注意到。

实测：提示词里只有一句「保留数据日期」时，模型把 2026-07-29 的收盘写成
「今天市场定性为底部横盘阶段的第1个交易日」，全文一个日期都没提——当天其实是
07-30，只有引用的 as_of 是诚实的。

这对每天要开的工作台是信任问题：盘后到夜间入库之间提问，最新可用数据就是上一
交易日，这件事必须说出口。日期关系是确定可算的，不该交给模型判断。
"""
from __future__ import annotations

import pytest

from intelligence.services import ask
from intelligence.services.ask import _market_data_date_line


# 「今天」一律注入固定日期，不读真实时钟。此前这两条用 `date.today()`（宿主时钟）
# 推「昨天」，而被测代码按 Asia/Shanghai 判断——CI 容器在 UTC，北京时间已跨到次日时
# 两边差一天，于是常年红。生产代码那边是刻意的、不能改（见 `_market_today` docstring）。
def test_stale_date_demands_an_explicit_disclosure() -> None:
    line = _market_data_date_line("2026-07-29", today="2026-07-30")

    assert "2026-07-29" in line
    assert "2026-07-30" in line
    assert "不是当日数据" in line
    assert "不得称其为今天" in line


def test_todays_date_is_marked_as_current() -> None:
    line = _market_data_date_line("2026-07-30", today="2026-07-30")

    assert "即今天" in line
    assert "不是当日数据" not in line


def test_default_today_comes_from_the_trading_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """注入口不得把默认路径的回归藏起来。

    不传 ``today`` 时必须仍走 `_market_today()`（Asia/Shanghai）。若有人改回
    `date.today()`，本条会**始终**失败，而不是只在 UTC 傍晚那个窗口里失败。
    """
    monkeypatch.setattr(ask, "_market_today", lambda: "2026-07-30")

    assert "今天是 2026-07-30" in _market_data_date_line("2026-07-29")
    assert "即今天" in _market_data_date_line("2026-07-30")


def test_missing_date_forbids_any_same_day_verdict() -> None:
    for value in (None, "", "   "):
        line = _market_data_date_line(value)
        assert "未确认" in line
        assert "不得给出任何当日定性" in line


def test_system_prompt_carries_the_hard_requirement() -> None:
    """口径写在系统提示词里，才对所有市场复盘答案生效。"""
    from intelligence.services.ask import _MARKET_REVIEW_SYSTEM_PROMPT

    assert "数据日期口径" in _MARKET_REVIEW_SYSTEM_PROMPT
    assert "第一句" in _MARKET_REVIEW_SYSTEM_PROMPT
