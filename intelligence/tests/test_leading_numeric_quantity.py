"""句首小数和区间不能被列表序号剥离器截断。"""

from pathlib import Path

import pytest

from intelligence.services.episode_semantic_verifier import _LEADING_LIST_LABEL_RE
from intelligence.tests.test_numeric_note_false_positives import _dated, _flagged
from scripts import date_mask_ab


def test_leading_decimal_preserves_evidence_identity() -> None:
    row = "股票代码=300308.SZ；交易日=2026-09-15；收盘价=10.37；支撑位=3.85；估值区间=20-30倍"
    _, supported = _dated("10.37 元是关键支撑，若跌破（E1）则止损。", detail=row)
    assert _flagged(supported) == []
    _, unsupported = _dated("10.37 元是关键支撑，若跌破（E1）则止损。")
    assert _flagged(unsupported) == ["10.37"]


@pytest.mark.parametrize("text,stripped", [
    ("1. 若跌破", "若跌破"),
    ("1.若跌破", "若跌破"),
    ("3、若跌破", "若跌破"),
    ("2) 若跌破", "若跌破"),
    ("- 1. 若跌破", "若跌破"),
    ("十、若跌破", "若跌破"),
    ("1- 若跌破", "若跌破"),
    ("10.37 元", "10.37 元"),
    ("20-30 倍", "20-30 倍"),
    ("- 3.85 元", "- 3.85 元"),
])
def test_ordinals_are_stripped_but_decimals_and_ranges_are_preserved(text, stripped):
    assert _LEADING_LIST_LABEL_RE.sub("", text) == stripped


def test_mask_audit_reports_current_list_fix_without_claiming_date_fix(tmp_path: Path):
    run = tmp_path / "run_1"
    run.mkdir()
    (run / "answer.md").write_text(
        "10-31日公告后股价回落。若跌破10.25元则止损；当日换手率11.30%。\n"
        "1. 若跌破 812 元则止损。\n10.37 元是关键支撑，若跌破则止损。\n",
        encoding="utf-8",
    )
    report = date_mask_ab.scan(tmp_path)
    assert report["runs_scanned"] == 1
    assert [(row["kind"], row["token"], row["cond"]) for row in report["rows"]] == [
        ("list_label", "10.37", True),
    ]
    assert report["released_in_condition_sentences"] == 1
    assert report["by_kind"] == {"date": 0, "list_label": 1}
    assert date_mask_ab.main(["--runs-dir", str(tmp_path)]) == 0
    assert date_mask_ab.main(["--runs-dir", str(tmp_path / "missing")]) == 2
