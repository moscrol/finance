"""The copy guard, exercised against a real episode instead of our own wording.

Every other test in this area builds its evidence by hand, and a hand-built
fixture inherits the vocabulary of the checker it is testing: they all named the
ratio column 含金量, which is the word the question used. A live kimi-k3 run on
2026-09-22 named the same column 现金流/净利润, wrote 比值 in prose, and miscopied
its own product (0.7474 recorded, 0.7473 published). Every check stayed silent.

The fixtures here are that run's artifacts, byte for byte: the sandbox record and
the withheld draft. Nothing in them may be reworded to suit the checker - that is
the whole point of keeping them.
"""

import json
from pathlib import Path

import pytest

from intelligence.services.agent_research import AgentEvidence, StructuredObservation
from intelligence.services.derived_calculation import DerivedCalculation, derived_evidence
from intelligence.services.research_delivery_checks import (
    _claim_periods,
    _ratio_products,
    calculation_copy_findings,
    remove_findings,
)

LIVE = Path(__file__).parent / "fixtures" / "live_calculation_20260922"
RECORDED_2025_ANNUAL = 0.7474
PUBLISHED_2025_ANNUAL = "0.7473"


def _record():
    return json.loads((LIVE / "calc-5f4c2f1af63598f6.json").read_text(encoding="utf-8"))


def _draft():
    return (LIVE / "draft.txt").read_text(encoding="utf-8")


def _inputs(record):
    """The financial_data evidence the sandbox recorded as its own input."""
    return tuple(
        AgentEvidence(
            tool="financial_data",
            title="财报",
            detail="财报输入",
            source="F10",
            source_date=item.get("as_of") or "",
            content_hash=item["hash"],
            observations=tuple(
                StructuredObservation(
                    o["subject"], o.get("as_of") or "", o["metric"], o["value"]
                )
                for o in item.get("observations", ())
            ),
        )
        for item in record.get("inputs", ())
    )


def _evidence(record=None):
    record = record or _record()
    calc = DerivedCalculation(
        calc_id=record["calc_id"],
        purpose=record["purpose"],
        script=record.get("script", ""),
        input_evidence_hashes=tuple(record["input_evidence_hashes"]),
        input_refs=tuple(record["input_refs"]),
        as_of=record.get("as_of"),
        result=record["result"],
        enforcement=record.get("enforcement", ""),
        exit_code=record.get("exit_code"),
        duration_ms=record.get("duration_ms", 0),
        stdout_tail="",
        stderr_tail="",
        inputs=tuple(record.get("inputs", ())),
    )
    inputs = _inputs(record)
    return (*inputs, derived_evidence(calc)), inputs


def test_live_column_binds_by_arithmetic_not_by_its_name():
    """现金流/净利润 is in no keyword list, yet it IS the ratio column."""
    evidence, _ = _evidence()
    products = _ratio_products(evidence)
    assert products, "the live ratio column was not bound at all"
    assert products["2025-12-31"] == {RECORDED_2025_ANNUAL}
    assert products["2026-06-30"] == {1.588}


def test_a_dating_parenthesis_does_not_end_the_period_scope():
    """'2025年报（截止 …，披露 …）' states one period and then dates it."""
    line = "- 2025年报（截止 2025-12-31，披露 2026-04-17）：615.22 / 823.2，比值 0.7473"
    assert [m.group() for m in _claim_periods(line)] == ["2025年报"]


def test_live_draft_miscopy_is_caught_and_only_that_number_is_pulled():
    evidence, _ = _evidence()
    draft = _draft()
    findings = calculation_copy_findings(draft, evidence, calculation_required=True)
    assert [f.code for f in findings] == ["calculation_value_mismatch"]
    assert draft[findings[0].start:findings[0].end] == PUBLISHED_2025_ANNUAL
    kept = remove_findings(draft, findings)
    assert PUBLISHED_2025_ANNUAL not in kept
    # The independently sourced facts on the same line survive, and no guessed
    # number is written in place of the withdrawn one.
    for retained in ("615.22", "823.2", "2192.48", "2909.57", "1.588"):
        assert retained in kept
    assert str(RECORDED_2025_ANNUAL) not in kept


def test_the_same_draft_with_the_recorded_value_is_clean():
    """Control: the guard must not fire on the number the sandbox produced."""
    evidence, _ = _evidence()
    corrected = _draft().replace(PUBLISHED_2025_ANNUAL, str(RECORDED_2025_ANNUAL))
    assert calculation_copy_findings(corrected, evidence, calculation_required=True) == ()


def test_rounded_and_unrelated_numbers_in_the_live_draft_are_not_touched():
    """约 0.75 is 0.7474 shown to two places; 615.22 is a different quantity."""
    evidence, _ = _evidence()
    draft = _draft().replace(PUBLISHED_2025_ANNUAL, str(RECORDED_2025_ANNUAL))
    for line in draft.splitlines():
        assert calculation_copy_findings(line, evidence, calculation_required=True) == ()


def test_without_the_calculation_record_nothing_is_certified():
    """Inputs alone prove no product: the guard abstains rather than guesses."""
    _, inputs = _evidence()
    assert calculation_copy_findings(_draft(), inputs, calculation_required=True) == ()


@pytest.mark.parametrize("kept_rows", [1, 2])
def test_one_coincidental_row_cannot_promote_a_column(kept_rows):
    """A column qualifies on repeated agreement, not on a single lucky cell."""
    record = _record()
    table = record["result"]["tables"][0]
    columns = table["columns"]
    ratio_at = columns.index("现金流/净利润")
    # Keep the ratio column readable on `kept_rows` rows; corrupt the rest so
    # only repeated agreement can bind it.
    for index, row in enumerate(table["rows"]):
        if index >= kept_rows:
            row[ratio_at] = row[ratio_at] + 0.5
    products = _ratio_products(_evidence(record)[0])
    assert bool(products) is (kept_rows >= 2)
