"""Fixed local failure checks: never erase the entire independently useful answer."""

from dataclasses import replace
import json

import pytest

from intelligence.services.agent_research import AgentEvidence, StructuredObservation
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.research_delivery_checks import (
    calculation_copy_findings,
    disclosure_absence_findings,
    remove_findings,
)
from intelligence.tests.test_episode_semantic_verifier import _structural


TRACE = ProviderTrace(
    provider="agent:l3_lookup",
    capability="l3_lookup",
    status="request_error",
    detail="private-path secret-token",
)


def _financial_evidence():
    source = AgentEvidence(
        tool="financial_data",
        title="财报",
        detail="财报输入",
        source="F10",
        content_hash="input-hash",
        observations=(
            StructuredObservation("600519.SH", "2026-06-30", "ocf_cum_yi", 706.91),
            StructuredObservation(
                "600519.SH", "2026-06-30", "net_profit_cum_yi", 445.17
            ),
        ),
    )
    calc = AgentEvidence(
        tool="derived_calculation",
        title="计算",
        detail="含金量",
        source="sandbox:0123456789abcdef",
        content_hash="calc-hash",
        derived_from=(source.content_hash,),
        observations=(
            StructuredObservation(
                "现金流", "2025-04-30", "现金流比率.含金量[2026中报]", 1.588
            ),
            StructuredObservation(
                "现金流", "2025-04-30", "现金流比率.含金量[2025中报]", 0.289
            ),
            # Same token in an unrelated metric must not green-light the typo.
            StructuredObservation(
                "现金流", "2025-04-30", "现金流比率.无关指标[2026中报]", 1.587
            ),
        ),
    )
    return source, calc


@pytest.mark.parametrize(
    "claim",
    [
        "窗口内无新公告即无新增官方信息差。",
        "若返回空白则可坐实窗口内无公告。",
        "接口失败，因此公司没有公告。",
        "检索无结果，所以尚未兑现。",
        "无法完整查询，但窗口内无新公告即无新增官方信息差。",
    ],
)
def test_search_failure_cannot_prove_absence(claim):
    draft = "中报原文披露了收入。[E1]。" + claim + "利润数据仍可核对。"
    findings = disclosure_absence_findings(draft, (TRACE,))
    assert findings
    kept = remove_findings(draft, findings)
    assert claim not in kept
    assert "中报原文披露了收入" in kept and "利润数据仍可核对" in kept


@pytest.mark.parametrize(
    "claim",
    [
        "不能据此断言公司没有公告或尚未兑现。",
        "查询失败不代表没有公告。",
        "若公司确实无新公告，则研究重点转向已披露信息。",
        "本轮未查到公告，不能证明没有公告。",
        "公告原文说明：截至该日没有新增订单。[E1]",
        "官方公告称，公司尚未兑现某项安排。[E1]",
        "查询到公司原文明确说明，截至该日没有公告应披露而未披露事项。[E1]",
        "查询为空，但不能证明公司没有公告。",
        "‘查询空白即可证明没有公告’是错误推断，不成立。",
        "窗口内存在两份已核实公告，但查询并不完整。",
    ],
)
def test_honest_gaps_hypotheses_and_independent_facts_survive(claim):
    assert disclosure_absence_findings(claim, (TRACE,)) == ()


def test_successful_lookup_is_not_universe_completeness_certificate():
    assert disclosure_absence_findings(
        "查询返回空白，所以公司没有公告。", (replace(TRACE, status="success"),)
    )


TABLE = "| 报告期 | 披露日 | OCF累计 | 归母净利累计 | 含金量 |\n|---|---|---|---|---|\n| 2026中报 | 2026-08-15 | 706.91 | 445.17 | 1.587 |\n| 2025中报 | 2025-08-13 | 131.19 | 454.03 | 0.289 |\n"


def test_copy_guard_binds_period_and_column_not_a_bag_of_numbers():
    findings = calculation_copy_findings(TABLE, _financial_evidence())
    assert len(findings) == 1
    kept = remove_findings(TABLE, findings)
    assert "2026中报 | 2026-08-15 | 706.91 | 445.17 | 待核对 |" in kept
    assert "2025中报 |" in kept and "1.587" not in kept


@pytest.mark.parametrize(
    "draft",
    [
        "2026中报含金量为1.587。",
        "**2026中报**含金量为**1.587**。",
        "比率只应与上年同期对照：2026中报1.587 vs 2025中报0.289。",
    ],
)
def test_ratio_typo_in_prose_is_not_left_behind(draft):
    assert calculation_copy_findings(draft, _financial_evidence())


@pytest.mark.parametrize(
    "draft",
    [
        TABLE.replace("1.587", "1.588"),
        TABLE.replace("1.587", "1.59"),
        "2026中报含金量为158.8%。",
        "2026中报收入为1.587亿元。",
        "2026中报含金量缺少可核验计算。",
        "含金量同比增速：2026中报449.8% vs 2025中报28.9%。",
    ],
)
def test_correct_rounding_percent_and_unrelated_numbers_not_rejected(draft):
    assert calculation_copy_findings(draft, _financial_evidence()) == ()


@pytest.mark.parametrize("header,cell", [
    ("含金量(bp)", "1.588"),
    ("含金量(BP)", "1.588"),
    ("含金量（基点）", "1.588"),
    ("含金量(百分点)", "1.588"),
    ("含金量(bp)", "1.588倍"),
    ("含金量(%)", "158.8bp"),
    ("含金量", "1.588bp"),
    ("含金量", "1.588基点"),
    ("含金量", "1.588个百分点"),
])
def test_ratio_delta_units_are_unverified_at_either_table_location(header, cell):
    draft = f"| 报告期 | OCF累计 | 含金量占位 |\n|---|---|---|\n|2026中报|706.91|{cell}|"
    draft = draft.replace("含金量占位", header)
    findings = calculation_copy_findings(draft, _financial_evidence())
    assert len(findings) == 1 and findings[0].code == "calculation_value_unverified"
    kept = remove_findings(draft, findings)
    assert f"| 报告期 | OCF累计 | {header} |" in kept
    assert "|2026中报|706.91| 待核对 |" in kept


@pytest.mark.parametrize("claim", [
    "2026中报含金量为1.588bp。",
    "2026中报含金量为1.588基点。",
    "2026中报含金量为1.588百分点。",
    "2026中报含金量为1.588个百分点。",
    "2026中报含金量(bp)为1.588倍。",
])
def test_explicit_ratio_prose_does_not_drop_a_delta_unit(claim):
    findings = calculation_copy_findings(claim, _financial_evidence())
    assert len(findings) == 1 and findings[0].code == "calculation_value_unverified"


@pytest.mark.parametrize("draft", [
    "含金量(%)：2026中报158.8，含金量(倍)：2025中报0.289。",
    "含金量(倍)：2026中报1.588，含金量(%)：2025中报28.9。",
    "含金量：2026中报1.588，2025中报0.289。",
    "含金量(%)：2026中报158.8，2025中报28.9。",
    "含金量(bp)需要另行核验。含金量：2026中报1.588。",
])
def test_ratio_prefix_unit_belongs_to_its_label_not_another_period_or_sentence(draft):
    assert calculation_copy_findings(draft, _financial_evidence()) == ()


@pytest.mark.parametrize("unit", ["bp", "BP", "基点", "百分点"])
@pytest.mark.parametrize("with_valid_product", [False, True])
def test_delta_unit_product_cannot_certify_a_level(unit, with_valid_product):
    source, calc = _financial_evidence()
    invalid = replace(calc, content_hash="delta-calc", observations=(replace(
        calc.observations[0], metric=f"现金流比率.含金量({unit})[2026中报]",
    ),))
    evidence = (source, invalid, calc) if with_valid_product else (source, invalid)
    findings = calculation_copy_findings("2026中报含金量为1.588。", evidence)
    assert len(findings) == 1 and findings[0].code == "calculation_value_unverified"


@pytest.mark.parametrize("header,cell", [
    ("含金量", "1.588"),
    ("含金量(倍)", "1.588"),
    ("含金量", "1.588倍"),
    ("含金量(%)", "158.8"),
    ("含金量", "158.8%"),
    ("含金量同比增长(bp)", "9.999"),
    ("含金量增长(bp)", "9.999"),
    ("含金量环比变化(基点)", "9.999"),
    ("收入(亿元)", "9.999"),
])
def test_ratio_units_preserve_absolute_values_and_excluded_column_roles(header, cell):
    draft = f"|报告期|{header}|\n|---|---|\n|2026中报|{cell}|"
    assert calculation_copy_findings(draft, _financial_evidence()) == ()


@pytest.mark.parametrize("mode", ["off", "llm"])
@pytest.mark.parametrize(
    "status", ["request_error", "partial", "empty", "not_attempted"]
)
def test_success_exit_also_checks_absence_and_preserves_neighbors(
    monkeypatch, mode, status
):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    draft = "已取得中报原文，收入数据可核。[E1]。窗口内无新公告即无新增官方信息差。仍需补全窗口查询。"
    frame, structural = _structural(draft, traces=(replace(TRACE, status=status),))
    verifier = SemanticEpisodeVerifier(
        judge_fn=lambda request: {
            "passed": True,
            "rejected_sentence_indexes": [],
            "issues": [],
        }
    )
    result = verifier.verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(10),
    )
    assert "窗口内无新公告即" not in result.public_answer
    assert (
        "已取得中报原文" in result.public_answer
        and "收入数据可核" in result.public_answer
    )
    assert "不能据此断言公司没有公告" in result.public_answer
    assert result.status == "partial"
    assert any("disclosure_absence_inference" in issue for issue in result.issues)
    assert (
        "private-path" not in result.public_answer
        and "secret-token" not in result.public_answer
    )
    assert result.verified.outcome.evidence == structural.outcome.evidence
    assert result.gap_output_ids  # existing repair loop, no new budget or fetch


def test_percent_units_period_labels_and_growth_are_not_conflated():
    source, calc = _financial_evidence()
    percent_calc = replace(
        calc,
        observations=(
            replace(
                calc.observations[0], metric="2025现金流.含金量%[2026中报]", value=158.8
            ),
            calc.observations[1],
        ),
    )
    assert (
        calculation_copy_findings(
            TABLE.replace("1.587", "1.588"), (source, percent_calc)
        )
        == ()
    )
    assert (
        calculation_copy_findings(
            TABLE.replace("含金量", "含金量同比增速"), (source, calc)
        )
        == ()
    )
    # Methodology examples with no disclosure lookup aren't this guard's domain.
    assert disclosure_absence_findings("查询返回空白，所以公司没有公告。", ()) == ()


def test_missing_and_conflicting_products_are_not_certified_by_numeric_presence():
    source, calc = _financial_evidence()
    assert all(
        f.code == "calculation_value_unverified"
        for f in calculation_copy_findings(
            TABLE,
            (source,),
            calculation_required=True,
        )
    )
    assert (
        len(calculation_copy_findings(TABLE, (source,), calculation_required=True)) == 2
    )
    conflicting = replace(
        calc,
        content_hash="other-calc",
        observations=(replace(calc.observations[0], value=1.6),),
    )
    result = calculation_copy_findings(
        TABLE.replace("1.587", "1.588"),
        (source, calc, conflicting),
        calculation_required=True,
    )
    assert len(result) == 1 and result[0].code == "calculation_value_unverified"
    # Explicitly outside this finite single-company contract.
    other_company = replace(
        source,
        content_hash="other-input",
        observations=(replace(source.observations[0], subject="000858.SZ"),),
    )
    assert calculation_copy_findings(TABLE, (source, calc, other_company)) == ()


@pytest.mark.parametrize("mode", ["off", "llm"])
def test_ratio_error_reaches_real_verifier_exit_without_losing_input_facts(
    monkeypatch, mode
):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    frame, structural = _structural("收入数据可核。[E1]。\n" + TABLE)
    structural = replace(
        structural,
        outcome=replace(
            structural.outcome,
            evidence=(*structural.outcome.evidence, *_financial_evidence()),
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
    assert "1.587" not in result.public_answer and "待核对" in result.public_answer
    assert "706.91" in result.public_answer and "445.17" in result.public_answer
    assert "2025中报" in result.public_answer and "0.289" in result.public_answer
    assert result.status == "partial" and result.gap_output_ids
    assert result.verified.outcome.evidence == structural.outcome.evidence
    # Idempotent final recheck must not duplicate gaps or restore the bad cell.
    from intelligence.services.episode_semantic_verifier import (
        recheck_material_public_delivery,
    )

    checked = recheck_material_public_delivery(result)
    assert checked == result


def test_retained_citations_do_not_resurrect_unbound_or_already_gapped_evidence(
    monkeypatch,
):
    from intelligence.services.episode_semantic_verifier import (
        SemanticEpisodeOutcome,
        recheck_material_public_delivery,
    )

    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    frame, structural = _structural(
        "可信事实。[E1]。无绑定内容。[E2]。查询空白因此没有公告。", traces=(TRACE,)
    )
    structural = replace(
        structural,
        outcome=replace(
            structural.outcome,
            evidence=(
                *structural.outcome.evidence,
                AgentEvidence(
                    tool="market_data",
                    title="未绑定",
                    detail="未绑定",
                    source="fixture",
                    content_hash="unbound",
                ),
            ),
        ),
    )
    initial = SemanticEpisodeOutcome(
        verified=structural,
        status="completed",
        public_answer=structural.outcome.draft,
        judge_status="passed",
    )
    checked = recheck_material_public_delivery(initial)
    assert checked.delivery_retained_evidence_hashes == (
        structural.outcome.evidence[0].content_hash,
    )
    assert "unbound" not in checked.delivery_retained_evidence_hashes
    # A prior judge gap must not acquire citations merely via this local check.
    prior_gap = recheck_material_public_delivery(
        replace(initial, gap_output_ids=("direct_assessment",))
    )
    assert prior_gap.delivery_retained_evidence_hashes == ()
    # Adapter sanitizer removes the retained citation: don't keep a stale card.
    projected = recheck_material_public_delivery(checked, projected="只剩覆盖缺口。")
    assert projected.delivery_retained_evidence_hashes == ()


def test_actual_failure_flag_reaches_model_and_audit_not_transport_ok():
    from intelligence.services import derived_calculation as dc
    from intelligence.services.research_harness import FinanceResearchHarness
    from intelligence.services.research_tool_registry import ToolObservation

    result = dc.to_tool_result(
        dc.CalculationError("invalid_result_contract", "summary_non_scalar")
    )
    observation = ToolObservation(
        tool="derived_calculation",
        query="calc",
        evidence=result.evidence,
        observation=result.observation,
        trace=result.trace,
        gaps=result.gaps,
        telemetry=dict(result.telemetry),
    )
    projection = FinanceResearchHarness().project_tool_result(
        observation, evidence_so_far=(), seen_prose=frozenset()
    )
    model = json.loads(projection.model_content)
    assert projection.audit_payload["ok"] is False and model["ok"] is False
    assert model["error"] == "invalid_result_contract" and model["gaps"]
    assert "telemetry" not in model and "telemetry" in projection.audit_payload
