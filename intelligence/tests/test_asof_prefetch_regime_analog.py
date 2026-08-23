from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from intelligence.services.asof_prefetch import collect_prefetch_items
from intelligence.services.market_regime_analogs import parse_regime_intent
from intelligence.tests.test_market_regime_analogs import LoaderAndBlockTests, _day

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None

_FROZEN_ANALOG = (
    "用spt和风远的结合视角，说一下目前的行情和之前的哪一段历史行情比较相似，个股怎么对标。"
)


def _make_market_db(path: Path, n: int = 200) -> None:
    """复用 D10 既有夹具，避免第二份建表 SQL 漂移；_make_db 不使用 self。"""
    LoaderAndBlockTests._make_db(None, path, n=n, hot_ranges=[(40, 60), (180, 200)])


def _blob(items) -> str:
    return "\n".join(f"{item.title}\n{item.detail}" for item in items)


def test_frozen_question_is_regime_analog() -> None:
    assert parse_regime_intent(_FROZEN_ANALOG)


def test_missing_db_still_emits_historical_analog_gap(tmp_path: Path) -> None:
    items = collect_prefetch_items(
        question=_FROZEN_ANALOG,
        question_type="general_finance_qa",
        subject="",
        as_of=date(2026, 8, 21),
        market_db_path=tmp_path / "missing.duckdb",
    )
    assert items
    blob = _blob(items)
    assert "historical_analogs" in blob
    assert "gap" in blob.lower()


def test_frozen_question_also_marks_stock_analog_gap(tmp_path: Path) -> None:
    """题面含「个股怎么对标」：D11 未接 Engine A，必须留 gap，不得静默无证据。"""
    items = collect_prefetch_items(
        question=_FROZEN_ANALOG,
        question_type="general_finance_qa",
        subject="",
        as_of=date(2026, 8, 21),
        market_db_path=tmp_path / "missing.duckdb",
    )
    blob = _blob(items)
    assert "D11" in blob


@pytest.mark.skipif(duckdb is None, reason="duckdb 不可用")
def test_regime_question_with_data_emits_real_d10_block(tmp_path: Path) -> None:
    """有数据时必须真的出 D10 块——否则「永远返回 gap」的实现也能全绿。"""
    db = tmp_path / "m.duckdb"
    _make_market_db(db)
    items = collect_prefetch_items(
        question=_FROZEN_ANALOG,
        question_type="general_finance_qa",
        subject="",
        as_of=date.fromisoformat(_day(120)),
        market_db_path=db,
    )
    blob = _blob(items)
    assert "[D10]" in blob
    assert "历史相似窗口" in blob
    assert "后续5日" in blob


@pytest.mark.skipif(duckdb is None, reason="duckdb 不可用")
def test_d10_prefetch_honours_as_of(tmp_path: Path) -> None:
    """两个不同 as_of 必须给出不同的块；相同即说明 as_of 被忽略。"""
    db = tmp_path / "m.duckdb"
    _make_market_db(db)

    def _run(cut: str) -> str:
        return _blob(
            collect_prefetch_items(
                question=_FROZEN_ANALOG,
                question_type="general_finance_qa",
                subject="",
                as_of=date.fromisoformat(cut),
                market_db_path=db,
            )
        )

    early = _run(_day(120))
    late = _run(_day(199))
    assert "[D10]" in early and "[D10]" in late
    assert early != late


def test_non_analog_question_does_not_grow_d10(tmp_path: Path) -> None:
    items = collect_prefetch_items(
        question="宁德时代今天收盘多少",
        question_type="quick_fact",
        subject="宁德时代",
        as_of=date(2026, 8, 21),
        market_db_path=tmp_path / "missing.duckdb",
    )
    blob = _blob(items)
    assert "D10" not in blob
    assert "historical_analogs" not in blob
