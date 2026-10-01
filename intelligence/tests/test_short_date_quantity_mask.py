"""数值门禁：「MM.DD / MM-DD」短写后面紧跟数量单位时是数量，不是日期（2026-10-01）。

``_DATE_TOKEN_RE`` 在抽数前掩日期；它的无年份短写分支连带掩掉了 ``10.25元``、``12.15%``、
``11.30亿``、``10-15倍``——条件句里的阈值不受审：「若跌破 9.25 元则止损」挂待核，
「若跌破 10.25 元则止损」放行。A 股 10–13 元价位、两位小数的涨跌幅 / 换手率大量落在
这个形状里。修复：后面紧跟数量单位的按数量审；跟「日 / 月 / 年」或什么都不跟的照旧是日期。

证据侧抽数不掩日期（``_bound_evidence_quantities``），所以证据里真有的数修后照样对得上——
见 ``test_values_present_in_evidence_still_pass``。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from intelligence.services.episode_semantic_verifier import _DATE_TOKEN_RE
from intelligence.tests.test_numeric_note_false_positives import _dated, _flagged

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("draft", "token"),
    [
        # 对照组：本来就受审
        ("若跌破 9.25 元（E1）则止损。", "9.25"),
        # 修前被当成 10 月 25 日 / 12 月 15 日 / 11 月 30 日 / 10 月 15 日掩掉
        ("若跌破 10.25 元（E1）则止损。", "10.25"),
        ("若涨幅超过 12.15%（E1）才算突破。", "12.15%"),
        ("若换手率升到 11.30%（E1）则降级。", "11.30%"),
        ("若市盈率落到 10-15 倍（E1）则降级。", "10-15 倍"),
    ],
)
def test_short_date_shaped_thresholds_with_a_unit_are_audited(draft: str, token: str) -> None:
    _, verified = _dated(draft)
    assert _flagged(verified) == [token]


@pytest.mark.parametrize(
    "draft",
    [
        # 证据（ROW_0915）里有的数照样放行
        "若收盘价站上 864.01（E1）则趋势转强。",
        "若涨幅 -5.72%（E1）再现则止损。",
        # 跟「日」的短写仍是日期
        "若跌破 10-25 日低点（E1）则止损。",
    ],
)
def test_dates_and_evidence_values_are_not_newly_flagged(draft: str) -> None:
    _, verified = _dated(draft)
    assert _flagged(verified) == []


def test_values_present_in_evidence_still_pass() -> None:
    """证据行里的 10.25 / 12.15 / 11.30 没有单位：证据侧不掩日期，回答带单位复述照样对得上。"""

    row = "股票代码=600487.SH；交易日=2026-09-15；收盘价=10.25；涨跌幅=12.15；换手率=11.30；市场成交额亿=10.31"
    for draft in (
        "若跌破 10.25 元（E1）则止损。",
        "若涨幅再超过 12.15%（E1）则加仓。",
        "若换手率回到 11.30%（E1）则降级。",
        "若成交额回到 10.31亿元（E1）则确认。",
    ):
        _, verified = _dated(draft, detail=row)
        assert _flagged(verified) == [], draft


@pytest.mark.parametrize(
    ("text", "masked"),
    [
        ("10-31日公告", "日公告"),
        ("09-15开盘", "开盘"),
        ("2026.09.01", ""),
        ("10.25 日", " 日"),
        ("12/15收盘", "收盘"),
        ("10.25元", "10.25元"),
        ("12.15 %", "12.15 %"),
        ("11.30亿以上", "11.30亿以上"),
        ("10/15倍", "10/15倍"),
    ],
)
def test_date_token_mask_table(text: str, masked: str) -> None:
    assert _DATE_TOKEN_RE.sub("", text) == masked


def test_ab_script_lists_released_tokens(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("date_mask_ab", REPO / "scripts" / "date_mask_ab.py")
    assert spec and spec.loader
    ab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ab)

    run = tmp_path / "run_1"
    run.mkdir()
    (run / "answer.md").write_text(
        "10-31日公告后股价回落。若跌破10.25元则止损；当日换手率11.30%。\n"
        "1. 若跌破 812 元则止损。\n10.37 元是关键支撑，若跌破则止损。\n",
        encoding="utf-8",
    )
    report = ab.scan(tmp_path)
    assert report["runs_scanned"] == 1
    assert [(r["kind"], r["token"], r["cond"]) for r in report["rows"]] == [
        ("date", "10.25", True), ("date", "11.30", False), ("list_label", "10.37", True),
    ]
    assert report["released_in_condition_sentences"] == 2
    assert report["by_kind"] == {"date": 2, "list_label": 1}
    assert ab.main(["--runs-dir", str(tmp_path)]) == 0
    assert ab.main(["--runs-dir", str(tmp_path / "missing")]) == 2


# ---------------------------------------------------------------------------
# 句首列表序号：``.`` / ``-`` 后紧跟数字是小数或区间，不是序号（2026-10-01）
# ---------------------------------------------------------------------------

_ROW_WITH_1037 = "股票代码=300308.SZ；交易日=2026-09-15；收盘价=10.37；支撑位=3.85；估值区间=20-30倍"


def test_leading_decimal_is_not_eaten_as_a_list_label() -> None:
    """``10.37 元是关键支撑…``：修前被剥成 ``37 元``——证据里有 10.37 也挂「37」（误报），
    证据里没有时点名的也是错的数。"""

    _, verified = _dated("10.37 元是关键支撑，若跌破（E1）则止损。", detail=_ROW_WITH_1037)
    assert _flagged(verified) == []
    _, verified = _dated("10.37 元是关键支撑，若跌破（E1）则止损。")
    assert _flagged(verified) == ["10.37"]


@pytest.mark.parametrize(
    ("text", "stripped"),
    [
        ("1. 若跌破", "若跌破"),
        ("1.若跌破", "若跌破"),
        ("3、若跌破", "若跌破"),
        ("2) 若跌破", "若跌破"),
        ("- 1. 若跌破", "若跌破"),
        ("十、若跌破", "若跌破"),
        ("1- 若跌破", "若跌破"),
        # 小数 / 区间原样保留
        ("10.37 元", "10.37 元"),
        ("20-30 倍", "20-30 倍"),
        ("- 3.85 元", "- 3.85 元"),
    ],
)
def test_leading_list_label_table(text: str, stripped: str) -> None:
    from intelligence.services.episode_semantic_verifier import _LEADING_LIST_LABEL_RE

    assert _LEADING_LIST_LABEL_RE.sub("", text) == stripped
