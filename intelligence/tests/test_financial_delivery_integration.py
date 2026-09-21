"""R6 + delivery guards at public/recovery seams; offline, not live acceptance."""
from dataclasses import replace

import pytest

from intelligence.runtime import continuous_turn_adapter as adapter_module
from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
from intelligence.services import llm_refine
from intelligence.services.agent_runtime import OutputEvidenceBinding
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeOutcome, SemanticEpisodeVerifier, recheck_material_public_delivery,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchDeadline, ResearchPolicy, ResearchRunContext
from intelligence.tests.test_boundary_partial_delivery import _delivery
from intelligence.tests.test_continuous_turn_adapter import _control
from intelligence.tests.test_episode_semantic_verifier import _judge
from intelligence.tests.test_financial_r6_regressions import SAFE, _financial
from intelligence.tests.test_research_delivery_checks import _financial_evidence

BAD = "二季度单季经营现金流=18−33.68=−15.66亿元。"
GOOD = "二季度单季经营现金流=18−33.68=−15.68亿元。"
ABSENCE = "窗口内无新公告即无新增官方信息差。"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*_args, **_kwargs):
        pytest.fail("delivery integration attempted network IO")
    for name in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection"):
        monkeypatch.setattr(name, denied)
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)


def _metric_only(draft):
    frame, verified = _financial(draft)
    contract = replace(verified.contract, required_outputs=verified.contract.required_outputs[1:])
    outcome = replace(verified.outcome, bindings=(
        OutputEvidenceBinding("metric_evidence", tuple(e.content_hash for e in verified.outcome.evidence)),
    ))
    return frame, verify_episode_outcome(contract, outcome)


def _ratio_delivery(draft, *, product_value=1.588, product_unit=""):
    frame, verified = _metric_only(draft)
    source, calc = _financial_evidence()
    source = replace(source, observations=tuple(
        replace(obs, subject=frame.subject) for obs in source.observations
    ))
    calc = replace(calc, observations=(replace(
        calc.observations[0], metric=f"现金流比率.含金量{product_unit}[2026中报]", value=product_value,
    ),))
    contract = replace(verified.contract, required_outputs=tuple(
        replace(required, evidence_types=(*required.evidence_types, "derived_calculation"))
        for required in verified.contract.required_outputs
    ))
    outcome = replace(verified.outcome, evidence=(source, calc), bindings=(
        OutputEvidenceBinding("metric_evidence", (source.content_hash, calc.content_hash)),
    ))
    return frame, verify_episode_outcome(contract, outcome)


@pytest.mark.parametrize("mode", ["off", "llm"])
@pytest.mark.parametrize("header,cell", [
    ("含金量(bp)", "1.588"),
    ("含金量(BP)", "1.588倍"),
    ("含金量（基点）", "1.588"),
    ("含金量(百分点)", "1.588"),
    ("含金量", "1.588bp"),
])
def test_ratio_unit_gap_reaches_real_exit_and_corrected_draft_clears_it(monkeypatch, mode, header, cell):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    table = f"|报告期|OCF累计|归母净利累计|{header}|\n|---|---|---|---|\n|2026中报|706.91|445.17|{cell}|"
    draft = SAFE + "[E1]。\n" + table
    frame, verified = _ratio_delivery(draft)
    assert verified.verified_status == "completed"
    verifier = SemanticEpisodeVerifier(judge_fn=_judge(True))
    result = verifier.verify(frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5))
    assert "|2026中报|706.91|445.17| 待核对 |" in result.public_answer
    assert SAFE in result.public_answer and "[E1]" in result.public_answer
    assert result.status == "partial"
    assert result.gap_output_ids == result.repair_output_ids == ("metric_evidence",)
    assert result.verified.outcome == verified.outcome
    assert result.delivery_retained_evidence_hashes == (verified.outcome.evidence[0].content_hash,)
    assert any("calculation_value_unverified" in issue for issue in result.issues)
    assert recheck_material_public_delivery(result) == result
    corrected_draft = SAFE + "[E1]。\n|报告期|含金量(%)|\n|---|---|\n|2026中报|158.8|"
    clean = verify_episode_outcome(verified.contract, replace(verified.outcome, draft=corrected_draft))
    corrected = verifier.verify(frame=frame, structurally_verified=clean, deadline=ResearchDeadline.from_timeout(5))
    assert corrected.status == "completed" and "158.8" in corrected.public_answer
    assert corrected.gap_output_ids == corrected.repair_output_ids == ()


@pytest.mark.parametrize("mode", ["off", "llm"])
@pytest.mark.parametrize("product_value,product_unit,gap_note", [
    (9.999, "", "复算不一致"),
    (1.588, "(bp)", "差值单位"),
])
def test_ratio_product_gap_survives_the_real_financial_exit(monkeypatch, mode, product_value, product_unit, gap_note):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    draft = SAFE + "[E1]。\n|报告期|含金量|\n|---|---|\n|2026中报|1.588|"
    frame, verified = _ratio_delivery(draft, product_value=product_value, product_unit=product_unit)
    assert verified.missing_outputs == ("metric_evidence",)
    assert gap_note in verified.completion.outputs[0].gap
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial" and result.repair_output_ids == ("metric_evidence",)
    assert result.verified.outcome == verified.outcome
    assert verified.outcome.draft == draft


@pytest.mark.parametrize("mode", ["off", "llm"])
@pytest.mark.parametrize("claim,rejected", [
    ("含金量(bp)：2026中报1.588。", True),
    ("含金量（基点）：2026中报1.588。", True),
    ("含金量(百分点)：2026中报1.588。", True),
    ("含金量(bp)：2026中报1.588倍。", True),
    ("含金量：2026中报1.588。", False),
    ("含金量：2026中报9.999。", True),
    ("含金量(倍)：2026中报1.588。", False),
    ("含金量(%)：2026中报158.8。", False),
    ("含金量同比增长(bp)：2026中报9.999。", False),
    ("含金量环比变化(基点)：2026中报9.999。", False),
    ("利差以bp计。含金量：2026中报1.588。", False),
    ("含金量：2024中报9.999。", False),
])
def test_ratio_prefix_unit_reaches_real_exit_without_widening_scope(monkeypatch, mode, claim, rejected):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    draft = SAFE + "[E1]。\n" + claim
    frame, verified = _ratio_delivery(draft)
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    assert (claim not in result.public_answer) == rejected
    assert result.status == ("partial" if rejected else "completed")
    expected_ids = ("metric_evidence",) if rejected else ()
    assert result.gap_output_ids == result.repair_output_ids == expected_ids
    assert SAFE in result.public_answer and "[E1]" in result.public_answer
    assert result.verified.outcome == verified.outcome
    assert verified.outcome.draft == draft


@pytest.mark.parametrize("bad", [BAD, "2026中报净现比0.133。", "本次实际取得并引用的报告为中际旭创2026年半年度报告。"])
@pytest.mark.parametrize("prior_status", ["completed", "partial", "degraded"])
def test_changed_public_projection_rechecks_financial_claims_without_upgrading(bad, prior_status):
    _, verified = _metric_only(SAFE + "[E1]。")
    initial = SemanticEpisodeOutcome(
        verified=verified, status=prior_status, public_answer=verified.outcome.draft, judge_status="passed",
    )
    checked = recheck_material_public_delivery(initial, projected=initial.public_answer + "\n" + bad)
    assert bad not in checked.public_answer
    assert SAFE in checked.public_answer and "[E1]" in checked.public_answer
    assert checked.status == ("partial" if prior_status == "completed" else prior_status)
    assert checked.gap_output_ids == checked.repair_output_ids == ("metric_evidence",)
    assert checked.verified.missing_outputs == ("metric_evidence",)
    assert checked.verified.outcome == initial.verified.outcome  # archive never rewritten
    assert checked.delivery_retained_evidence_hashes == (verified.outcome.evidence[0].content_hash,)
    assert any("financial_claim_mismatch" in row["reasons"] for row in checked.sentence_verdicts)
    assert recheck_material_public_delivery(checked) == checked
    assert recheck_material_public_delivery(checked, projected=SAFE).delivery_retained_evidence_hashes == ()


@pytest.mark.parametrize("mode", ["off", "llm"])
def test_both_guards_keep_local_debt_bound_citations_and_corrected_draft_clears_it(monkeypatch, mode):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    frame, verified = _metric_only(SAFE + "[E1]。\n" + BAD + "\n" + ABSENCE)
    verified = replace(verified, outcome=replace(verified.outcome, traces=(ProviderTrace("l3_lookup", "l3_lookup", "partial"),)))
    verifier = SemanticEpisodeVerifier(judge_fn=_judge(True))
    result = verifier.verify(frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5))
    assert BAD not in result.public_answer and ABSENCE not in result.public_answer
    assert SAFE in result.public_answer and result.status == "partial"
    assert result.gap_output_ids == result.repair_output_ids == ("metric_evidence",)
    assert result.delivery_retained_evidence_hashes == (verified.outcome.evidence[0].content_hash,)
    assert any("差值" in note or "期间" in note for note in result.delivery_repair_notes)
    assert any("查询失败" in note for note in result.delivery_repair_notes)
    clean = verify_episode_outcome(verified.contract, replace(verified.outcome, draft=SAFE + "[E1]。\n" + GOOD))
    corrected = verifier.verify(frame=frame, structurally_verified=clean, deadline=ResearchDeadline.from_timeout(5))
    assert corrected.status == "completed" and corrected.gap_output_ids == ()
    assert corrected.delivery_repair_notes == () and GOOD in corrected.public_answer


@pytest.mark.parametrize("bad", [BAD, ABSENCE])
def test_exception_recovery_checks_after_calendar_and_keeps_citations(monkeypatch, bad):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    original = adapter_module._with_calendar_disclosure
    # Deliberate post-check injection, not a claim about natural calendar output.
    monkeypatch.setattr(adapter_module, "_with_calendar_disclosure", lambda text, frame: original(text, frame) + "\n" + bad)
    frame, verified = _metric_only(SAFE + "[E1]。\n" + BAD)
    verified = replace(verified, outcome=replace(verified.outcome, traces=(ProviderTrace("l3_lookup", "l3_lookup", "partial"),)))
    semantic = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    context = ResearchRunContext(
        contract=verified.contract, deadline=ResearchDeadline.from_timeout(60),
        policy=ResearchPolicy("standard", 3, 60, 20), trace_parent_id=verified.contract.task_id,
    )
    result = ContinuousTurnAdapter(
        runtime=object(), semantic_verifier=SemanticEpisodeVerifier(judge_fn=_judge(True)),
    )._recover_verified_delivery(frame, context, semantic, {})
    assert result is not None and result.status == "partial"
    assert BAD not in result.answer and ABSENCE not in result.answer
    assert SAFE in result.answer and "[E1]" in result.answer and result.citations
    assert result.private_artifact["semantic_verifier"]["gap_output_ids"] == ["metric_evidence"]


@pytest.mark.parametrize("mode", ["off", "llm"])
def test_adapter_final_financial_projection_is_guarded_and_cited(monkeypatch, mode):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    frame, verified = _metric_only(SAFE + "[E1]。\n" + GOOD)
    context = ResearchRunContext(
        contract=verified.contract, deadline=ResearchDeadline.from_timeout(60),
        policy=ResearchPolicy("standard", 3, 60, 20), trace_parent_id=verified.contract.task_id,
    )
    class Runtime:
        def run(self, **kwargs):
            return verified.outcome
    monkeypatch.setattr(adapter_module, "_with_calendar_disclosure", lambda text, frame: text + "\n" + BAD)
    result = ContinuousTurnAdapter(
        runtime=Runtime(), mode="on", context_factory=lambda *a, **k: context,
        registry_factory=lambda *a, **k: "registry",
        semantic_verifier=SemanticEpisodeVerifier(judge_fn=_judge(True)),
    ).handle(frame=frame, control=_control(frame))
    assert result.status == "partial" and BAD not in result.answer
    assert GOOD in result.answer and SAFE in result.answer and result.citations
    assert result.private_artifact["repair_attempts"] == 0  # final seam grants no extra loop


@pytest.mark.parametrize("prior_gap", [False, True])
def test_final_financial_recheck_never_revives_unbound_or_previously_gapped_cards(prior_gap):
    _, verified = _metric_only(SAFE + "[E1]。")
    verified = replace(verified, outcome=replace(verified.outcome, bindings=(
        replace(verified.outcome.bindings[0], evidence_hashes=(verified.outcome.evidence[0].content_hash,)),
    )))
    initial = SemanticEpisodeOutcome(
        verified=verified, status="partial" if prior_gap else "completed",
        public_answer=verified.outcome.draft, judge_status="passed",
        gap_output_ids=("metric_evidence",) if prior_gap else (),
    )
    checked = recheck_material_public_delivery(
        initial, projected=initial.public_answer + "\n尚未绑定的内容。[E2]。\n" + BAD,
    )
    assert BAD not in checked.public_answer
    assert checked.delivery_retained_evidence_hashes == (
        () if prior_gap else (verified.outcome.evidence[0].content_hash,)
    )


def test_final_financial_recheck_keeps_legal_prose_and_prior_repair_debt():
    _, verified = _metric_only(SAFE)
    initial = SemanticEpisodeOutcome(
        verified=verified, status="partial", public_answer=SAFE, judge_status="repaired",
        gap_output_ids=("metric_evidence",), repair_output_ids=("metric_evidence",),
    )
    checked = recheck_material_public_delivery(initial, projected=SAFE + "\n" + GOOD)
    assert GOOD in checked.public_answer and checked.status == "partial"
    assert checked.gap_output_ids == checked.repair_output_ids == ("metric_evidence",)
    assert not checked.sentence_verdicts  # only a new full verify may clear old debt


def test_delivery_verdicts_do_not_mask_preflight_ledger(monkeypatch):
    from intelligence.services import episode_semantic_verifier as module
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    frame, verified = _metric_only(SAFE + "[E1]。\n" + BAD)
    original = module.recheck_material_public_delivery
    def inject(outcome, *, projected=None):
        if outcome.gap_output_ids:
            projected = outcome.public_answer + "\n2026中报净现比0.133。"
        return original(outcome, projected=projected)
    monkeypatch.setattr(module, "recheck_material_public_delivery", inject)
    checked = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    stages = {row["stage"] for row in checked.sentence_verdicts if "financial_claim_mismatch" in row["reasons"]}
    assert "preflight" in stages and "delivery" in stages
    assert "0.133" not in checked.public_answer and BAD not in checked.public_answer


def test_true_exception_recovery_cannot_restore_postcheck_disclosure_inference(monkeypatch):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    # Existing real adapter exception path, with no new tool permission.
    original = adapter_module._with_calendar_disclosure
    monkeypatch.setattr(adapter_module, "_with_calendar_disclosure", lambda text, frame: original(text, frame) + "\n查询空白，因此公司没有公告。")
    # Add an actual trace to the scripted outcome; no external lookup.
    from intelligence.tests import test_boundary_partial_delivery as structural
    build = structural._structural
    monkeypatch.setattr(structural, "_structural", lambda *a, **k: build(*a, **k, traces=(ProviderTrace("l3_lookup", "l3_lookup", "partial"),)))
    result, goals, _ = _delivery(repair="recheck_raises")
    assert "delivery_recovery" in result.private_artifact and goals
    assert "查询空白，因此公司没有公告" not in result.answer
    assert result.status == "partial" and result.citations
