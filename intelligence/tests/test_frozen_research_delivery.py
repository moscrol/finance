"""Replay frozen public failures with the real sandbox/renderer, no new providers.

The authored corrected script is NOT a model answer. Input perturbation below
proves this script consumes the changed input; it doesn't prove arbitrary
model-authored code does. Decimal reference is independent of fincalc math.
"""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, ROUND_HALF_EVEN
import json
from pathlib import Path

import pytest

from intelligence.services import derived_calculation as dc
from intelligence.services import derived_calculation_artifacts as art
from intelligence.services.agent_research import AgentEvidence, StructuredObservation
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.research_delivery_checks import (
    calculation_copy_findings,
    remove_findings,
)
from intelligence.tests.test_episode_semantic_verifier import _structural


FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/research_delivery_20260918.json").read_text()
)
SCRIPT = """sub = '600519.SH'
cash = series(sub, 'ocf_cum_yi')
profit = series(sub, 'net_profit_cum_yi')
ratios = ratio_series(cash, profit, digits=3)
notices = {o['as_of']: o['evidence_as_of'] for o in observations(subject=sub, metric='ocf_cum_yi')}
rows = [[r['as_of'], notices[r['as_of']], r['numerator'], r['denominator'], r['ratio']] for r in ratios]
emit_result(tables=[table('现金流比率', ['报告期', '披露日', 'OCF累计', '归母净利累计', '含金量'], rows)],
            formulas=['含金量 = 累计经营现金流净额 / 累计归母净利润'])
"""


def _inputs(snapshot=None):
    return tuple(
        AgentEvidence(
            tool=item["tool"],
            title=item["title"],
            detail="frozen structured inputs",
            source=item["source"],
            source_date=item["as_of"],
            content_hash=item["hash"],
            evidence_tier=item["tier"],
            observations=tuple(
                StructuredObservation(**o) for o in item["observations"]
            ),
        )
        for item in (
            snapshot if snapshot is not None else FIXTURE["calculation"]["inputs"]
        )
    )


def _run(inputs=None):
    calc = dc.run_derived_calculation(
        script=SCRIPT,
        purpose="累计经营现金流 / 归母净利润",
        evidence=_inputs() if inputs is None else inputs,
    )
    assert isinstance(calc, dc.DerivedCalculation)
    return calc


def _decimal_reference(inputs):
    values = {
        (o.as_of, o.metric): Decimal(str(o.value))
        for e in inputs
        for o in e.observations
    }
    return {
        period: (v / values[period, "net_profit_cum_yi"]).quantize(
            Decimal("0.001"), rounding=ROUND_HALF_EVEN
        )
        for (period, metric), v in values.items()
        if metric == "ocf_cum_yi"
    }


def test_original_script_no_longer_claims_renderable_success():
    result = dc.run_derived_calculation(
        script=FIXTURE["calculation"]["script"],
        purpose=FIXTURE["calculation"]["purpose"],
        evidence=_inputs(),
    )
    assert (
        isinstance(result, dc.CalculationError)
        and result.code == dc.ERROR_INVALID_RESULT
    )
    assert art.normalize_result(FIXTURE["calculation"]["result"]).tables == ()
    assert "1.587" in FIXTURE["financial_answer"]  # old failure is unchanged


def test_authored_corrected_script_matches_independent_math_and_rendered_cells():
    calc = _run()
    reference = _decimal_reference(_inputs())
    rows = calc.view.tables[0].rows
    assert len(rows) == 6
    assert {r[0]: Decimal(str(r[4])) for r in rows} == reference
    assert reference["2026-06-30"] == Decimal("1.588")
    assert rows[-1][1] == "2026-08-15"
    files = {f.renderer: f.content for f in art.artifact_files(calc.to_dict())}
    assert "2026-06-30,2026-08-15,706.91,445.17,1.588" in files["table"]
    assert (
        "<td>2026-06-30</td><td>2026-08-15</td><td>706.91</td><td>445.17</td><td>1.588</td>"
        in files["html"]
    )
    # The *old* answer remains rejected even against a correctly shaped result.
    evidence = (*_inputs(), dc.derived_evidence(calc))
    findings = calculation_copy_findings(FIXTURE["financial_answer"], evidence)
    assert len(findings) == 2  # one cell and the same-period comparison clause
    assert "1.587" not in remove_findings(FIXTURE["financial_answer"], findings)


def test_input_perturbation_changes_result_not_only_hash_or_purpose():
    snapshots = deepcopy(FIXTURE["calculation"]["inputs"])
    for item in snapshots:
        for obs in item["observations"]:
            if obs["metric"] == "ocf_cum_yi" and obs["as_of"] == "2026-06-30":
                obs["value"] = 800.0
                item["hash"] = "perturbed-input-for-test"
    inputs = _inputs(snapshots)
    rows = _run(inputs).view.tables[0].rows
    reference = _decimal_reference(inputs)
    assert {r[0]: Decimal(str(r[4])) for r in rows} == reference
    assert rows[-1][2] == 800.0 and rows[-1][4] != 1.588


@pytest.mark.parametrize("mode", ["off", "llm"])
def test_frozen_disclosure_answer_through_real_verifier_exit(monkeypatch, mode):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    frame, structural = _structural(
        FIXTURE["disclosure_answer"],
        traces=(
            ProviderTrace(
                provider="l3_lookup",
                capability="l3_lookup",
                status="request_error",
                detail="private-error",
            ),
        ),
    )
    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: {
            "passed": True,
            "rejected_sentence_indexes": [],
            "issues": [],
        }
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(10),
    )
    assert "窗口内无新公告即无新增官方信息差" not in result.public_answer
    assert "若返回空白则可坐实" not in result.public_answer
    assert "加权平均ROE 16.75%" in result.public_answer
    assert "本次未能核实到窗口内的新公告" in result.public_answer
    assert result.status == "partial" and "private-error" not in result.public_answer


@pytest.mark.parametrize("mode", ["off", "llm"])
def test_old_empty_product_cannot_support_claimed_calculator_ratios(monkeypatch, mode):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    frame, structural = _structural(FIXTURE["financial_answer"])
    structural = replace(
        structural,
        outcome=replace(
            structural.outcome, evidence=(*structural.outcome.evidence, *_inputs())
        ),
    )
    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: {
            "passed": True,
            "rejected_sentence_indexes": [],
            "issues": [],
        }
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(10),
    )
    assert "1.587" not in result.public_answer
    assert "706.91" in result.public_answer and "445.17" in result.public_answer
    assert result.status == "partial"
    assert "缺少可核对的计算结果" in result.public_answer
