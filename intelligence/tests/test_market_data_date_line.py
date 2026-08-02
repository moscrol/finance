"""盘面数据是哪天，必须算出来告知模型，不能靠它自己注意到。

实测：提示词里只有一句「保留数据日期」时，模型把 2026-07-29 的收盘写成
「今天市场定性为底部横盘阶段的第1个交易日」，全文一个日期都没提——当天其实是
07-30，只有引用的 as_of 是诚实的。

这对每天要开的工作台是信任问题：盘后到夜间入库之间提问，最新可用数据就是上一
交易日，这件事必须说出口。日期关系是确定可算的，不该交给模型判断。
"""
from __future__ import annotations

from datetime import date, timedelta

from intelligence.services.ask import _market_data_date_line


def test_stale_date_demands_an_explicit_disclosure() -> None:
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    line = _market_data_date_line(yesterday)

    assert yesterday in line
    assert date.today().isoformat() in line
    assert "不是当日数据" in line
    assert "不得称其为今天" in line


def test_todays_date_is_marked_as_current() -> None:
    line = _market_data_date_line(date.today().isoformat())

    assert "即今天" in line
    assert "不是当日数据" not in line


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
