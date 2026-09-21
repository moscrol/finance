"""Offline protocol/consumer tests; scripted receipts are not financial gold answers."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from intelligence.services.agent_runtime import EpisodeEvent, ModelToolCall, ModelTurn
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
    _judge_report_tools,
    _judge_system_prompt,
    _numbered_sentences,
    recheck_research_requirement_delivery,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.research_requirement_review import (
    reconcile_requirement_checks,
    requirement_review_rows,
)
from intelligence.tests.test_episode_semantic_verifier import _structural

FIXTURES = Path(__file__).parent / "fixtures/research_requests_0921"
QUESTION = "请研究测试主题。\n要求：\n1. 给出当前判断。\n2. 列出反方解释。"
DRAFT = "当前判断：景气改善尚需观察。[E1]\n反方解释：也可能是短期轮动。[E1]"


def _case(question=QUESTION, draft=DRAFT):
    frame, verified = _structural(draft)
    material = understand_query(question).task_frame.material_contract
    frame = replace(frame, raw_question=question, material_contract=material)
    contract = replace(
        verified.contract,
        question=question,
        task_frame_hash=frame.task_frame_hash,
        material_contract=material,
    )
    outcome = replace(
        verified.outcome,
        task_frame_hash=frame.task_frame_hash,
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
    )
    return frame, verify_episode_outcome(contract, outcome)


def _request(question=QUESTION):
    frame, verified = _case(question)
    return SemanticEpisodeVerifier()._judge_request(
        frame, verified, _numbered_sentences(verified.outcome.draft)
    )


def _report(request, *, partial=None):
    rows = []
    for row in request["requirement_review"]:
        parts = []
        for part in row["parts"]:
            failed = partial == (row["question_id"], part["part_index"])
            parts.append(
                {
                    "part_index": part["part_index"],
                    "status": "partial" if failed else "fulfilled",
                    "answer_sentence_indexes": [request["sentences"][0]["index"]],
                    "reason": "离线固定回执，仅验证消费者协议。",
                    "missing_aspects": ["尚未逐项给出第三种解释。"] if failed else [],
                }
            )
        rows.append({"question_id": row["question_id"], "parts": parts})
    return {
        "passed": True,
        "rejected_sentence_indexes": [],
        "issues": [],
        "requirement_checks": rows,
    }


def _parse(payload, request):
    return SemanticEpisodeVerifier._parse_report(
        payload,
        len(request["sentences"]),
        requirement_review=request["requirement_review"],
        sentences=request["sentences"],
    )


def _verify(*, question=QUESTION, judge=None, draft=DRAFT):
    frame, verified = _case(question, draft)
    result = SemanticEpisodeVerifier(judge_fn=judge or _report).verify(
        frame=frame,
        structurally_verified=verified,
        deadline=ResearchDeadline.from_timeout(15),
    )
    return frame, verified, result


@pytest.mark.parametrize("name", ["q1", "q2", "q3"])
def test_frozen_checklist_review_uses_original_question_ids_and_all_bullets(name):
    question = (FIXTURES / f"{name}.txt").read_text()
    frame, verified = _case(question)
    rows = requirement_review_rows(verified.contract)
    assert [row["question_id"] for row in rows] == [
        q.question_id for q in frame.material_contract.questions
    ]
    assert len(rows) == 7
    for row in rows:
        assert "\n".join(part["text"] for part in row["parts"]).replace(
            "\n", ""
        ) == row["text"].replace("\n- ", "")
    if name == "q2":
        assert len(rows[1]["parts"]) == 7
        assert len(rows[4]["parts"]) == 4
        assert "2家" in rows[4]["parts"][1]["text"]
    if name == "q3":
        assert "至少3个" in rows[1]["parts"][0]["text"]
        assert len(rows[2]["parts"]) == 4
        assert "第三种解释" in rows[2]["parts"][3]["text"]


@pytest.mark.parametrize("scope", ["full", "local_only", "material_only"])
def test_read_scope_is_unchanged_and_material_only_keeps_its_existing_review(scope):
    _, verified = _case()
    if scope == "material_only":
        # Only the row builder is tested here; a real material-only contract has its own output slots.
        from types import SimpleNamespace

        contract = SimpleNamespace(
            question=QUESTION,
            material_contract=replace(
                verified.contract.material_contract, data_scope=scope
            ),
        )
    else:
        contract = replace(
            verified.contract,
            material_contract=replace(
                verified.contract.material_contract, data_scope=scope
            ),
            allowed_capabilities=("finance_query",),
            required_outputs=tuple(
                replace(item, evidence_types=("finance_query",))
                for item in verified.contract.required_outputs
            ),
        )
    assert bool(requirement_review_rows(contract)) == (scope != "material_only")
    assert contract.material_contract.data_scope == scope


def test_ordinary_or_quoted_lists_do_not_opt_into_checklist_gate():
    for question in (
        "当前市场怎么看？",
        "> 请研究测试主题。\n> 要求：\n> 1. 判断。\n> 2. 反方。",
    ):
        _, verified = _case(question)
        assert requirement_review_rows(verified.contract) == []


def test_schema_prompt_and_injected_seams_receive_required_receipts():
    from intelligence.services.episode_semantic_verifier import _call_flexible

    request = _request()
    schema = _judge_report_tools(request)[0]["function"]["parameters"]
    assert "requirement_checks" in schema["required"]
    assert schema["properties"]["requirement_checks"]["minItems"] == 2
    prompt = _judge_system_prompt(request)
    assert "逐信号" in prompt and "同一集合" in prompt and "分母" in prompt
    assert (
        _call_flexible(lambda requirement_review: requirement_review, request, 1)
        == request["requirement_review"]
    )
    assert (
        _call_flexible(lambda **kwargs: kwargs["requirement_review"], request, 1)
        == request["requirement_review"]
    )
    assert (
        "requirement_checks"
        not in _judge_report_tools({})[0]["function"]["parameters"]["required"]
    )


@pytest.mark.parametrize(
    "fault",
    [
        "missing_receipt",
        "missing_question",
        "duplicate_question",
        "unknown_question",
        "missing_part",
        "duplicate_part",
        "unknown_part",
        "bool_part",
        "missing_witness",
        "unknown_witness",
        "bool_witness",
        "duplicate_witness",
        "empty_reason",
        "false_completion",
        "blank_gap",
        "unknown_field",
        "wrong_status",
    ],
)
def test_invalid_or_incomplete_receipts_fail_closed(fault):
    question = (FIXTURES / "q3.txt").read_text()
    request = _request(question)
    payload = _report(request)
    rows = payload["requirement_checks"]
    part = rows[2]["parts"][0]
    if fault == "missing_receipt":
        payload.pop("requirement_checks")
    elif fault == "missing_question":
        rows.pop()
    elif fault == "duplicate_question":
        rows[-1] = deepcopy(rows[0])
    elif fault == "unknown_question":
        rows[0]["question_id"] = "q999"
    elif fault == "missing_part":
        rows[2]["parts"].pop()
    elif fault == "duplicate_part":
        rows[2]["parts"][-1] = deepcopy(part)
    elif fault == "unknown_part":
        part["part_index"] = 99
    elif fault == "bool_part":
        part["part_index"] = True
    elif fault == "missing_witness":
        part["answer_sentence_indexes"] = []
    elif fault == "unknown_witness":
        part["answer_sentence_indexes"] = [999]
    elif fault == "bool_witness":
        part["answer_sentence_indexes"] = [True]
    elif fault == "duplicate_witness":
        part["answer_sentence_indexes"] = [1, 1]
    elif fault == "empty_reason":
        part["reason"] = " "
    elif fault == "false_completion":
        part["missing_aspects"] = ["缺少B分支"]
    elif fault == "blank_gap":
        part.update(status="partial", missing_aspects=[" "])
    elif fault == "unknown_field":
        part["approved"] = True
    elif fault == "wrong_status":
        part["status"] = "complete"
    assert _parse(payload, request) is None


@pytest.mark.parametrize("passed", [True, False])
def test_omission_receipt_is_independent_of_top_level_fact_verdict(passed):
    request = _request()
    payload = _report(request, partial=("q2", 1))
    payload["passed"] = passed
    report = _parse(payload, request)
    if not passed:
        assert (
            report is None
        )  # A fact rejection without a location cannot be laundered by an omission.
    else:
        assert report is not None and report.passed
        assert report.rejected_sentence_indexes == ()
        assert report.requirement_checks[1]["parts"][0]["status"] == "partial"


def test_rejected_sentence_cannot_certify_completion():
    request = _request()
    payload = _report(request)
    payload.update(passed=False, rejected_sentence_indexes=[1], issues=["事实不支持"])
    report = _parse(payload, request)
    assert not report.passed
    assert report.requirement_checks[0]["parts"][0]["status"] == "partial"


def test_fact_issues_still_reject_omitted_indexes_and_revoke_their_receipts():
    request = _request()
    payload = _report(request)
    payload.update(
        passed=False, rejected_sentence_indexes=[2], issues=["第1句与第2句事实不支持"]
    )
    report = _parse(payload, request)
    assert report.rejected_sentence_indexes == (1, 2)
    assert report.requirement_checks[0]["parts"][0]["status"] == "partial"


def test_later_fact_gate_revokes_a_witness_even_when_prose_is_kept():
    from intelligence.services.episode_semantic_verifier import _JudgeCall

    request = _request()
    report = _parse(_report(request), request)
    _, _, result = _verify()
    finalized = SemanticEpisodeVerifier()._finalize_outcome(
        result,
        _JudgeCall(
            replace(report, passed=False, rejected_sentence_indexes=(1,)), False, False
        ),
    )
    checked = recheck_research_requirement_delivery(finalized)
    assert checked.status == "partial"
    assert checked.requirement_checks[0]["parts"][0]["status"] == "partial"


@pytest.mark.parametrize("wire", ["dict", "json", "tool"])
def test_receipts_survive_provider_wires(wire):
    request = _request()
    payload = _report(request)
    if wire == "tool":
        report = SemanticEpisodeVerifier._parse_tool_report(
            ModelTurn(
                "", (ModelToolCall("check", "submit_grounding_report", payload),)
            ),
            len(request["sentences"]),
            requirement_review=request["requirement_review"],
            sentences=request["sentences"],
        )
    else:
        report = _parse(json.dumps(payload) if wire == "json" else payload, request)
    assert report and report.requirement_checks
    assert report.to_dict()["requirement_checks"][0]["parts"][0][
        "answer_sentences"
    ] == [request["sentences"][0]]


def test_missing_branch_preserves_prose_and_downgrades_completion_without_retrieval():
    question = (FIXTURES / "q3.txt").read_text()
    calls = []

    def judge(request):
        calls.append(request)
        return _report(request, partial=("q3", 4))

    _, structural, result = _verify(question=question, judge=judge)
    assert len(calls) == 1
    assert result.status == "partial"
    assert result.verified.completion.task_coverage == "partial"
    assert (
        result.verified.completion.factual_grounding
        == structural.completion.factual_grounding
    )
    assert result.verified.missing_outputs == ("requirement_q3",)
    assert "当前判断" in result.public_answer
    assert "尚未逐项完成" in result.public_answer
    assert result.verified.outcome.evidence == structural.outcome.evidence
    assert result.to_dict()["requirement_checks"][2]["parts"][3]["missing_aspects"]


def test_complete_receipts_do_not_override_existing_runtime_partial():
    _, _, result = _verify()
    assert result.status == "completed"
    partial = replace(
        result,
        status="partial",
        verified=replace(result.verified, verified_status="partial"),
    )
    assert recheck_research_requirement_delivery(partial).status == "partial"


def test_public_deletion_revokes_completion_and_never_resurrects_old_receipt():
    _, _, result = _verify()
    assert result.status == "completed"
    witness = result.requirement_checks[0]["parts"][0]["answer_sentences"][0]["text"]
    changed = recheck_research_requirement_delivery(
        result, projected=result.public_answer.replace(witness, "")
    )
    assert changed.status == "partial"
    assert changed.verified.completion.task_coverage == "partial"
    assert "requirement_q1" in changed.repair_output_ids
    restored = recheck_research_requirement_delivery(
        changed, projected=result.public_answer
    )
    assert restored.status == "partial"
    assert restored.requirement_checks[0]["parts"][0]["status"] == "partial"


def test_substring_of_changed_sentence_is_not_the_original_witness():
    _, _, result = _verify()
    witness = result.requirement_checks[0]["parts"][0]["answer_sentences"][0]["text"]
    changed = recheck_research_requirement_delivery(
        result, projected=result.public_answer.replace(witness, "并非" + witness)
    )
    assert changed.status == "partial"
    assert "requirement_q1" in changed.verified.missing_outputs


def test_off_mode_does_not_call_judge_or_claim_semantic_checklist_completion(
    monkeypatch,
):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")

    def forbidden(_request):
        raise AssertionError("judge must stay off")

    _, _, result = _verify(judge=forbidden)
    assert result.status == "partial"
    assert result.judge_mode == "deterministic"
    assert result.requirement_checks == ()
    assert (
        result.verified.missing_outputs == ()
    )  # Unknown review is not a repair warrant.
    assert "未完成原要求的逐项核验" in result.public_answer


def test_legacy_pass_without_receipts_is_not_completion():
    _, _, result = _verify(
        judge=lambda _: {"passed": True, "rejected_sentence_indexes": [], "issues": []}
    )
    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert result.verified.completion.task_coverage == "partial"


def test_real_repair_consumer_receives_original_gap_but_no_new_permission():
    from intelligence.runtime.continuous_turn_adapter import _rejected_claim_notes
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.repair_coordinator import (
        classify_repair_need,
        build_repair_goal,
        ProgressSnapshot,
    )
    from intelligence.services.research_harness import FinanceResearchHarness

    frame, structural, result = _verify(
        judge=lambda request: _report(request, partial=("q2", 1))
    )
    context = build_episode_context(
        frame,
        task_id="requirements-test",
        tier="quick",
        today="2026-09-21",
        latest_data_date="2026-09-18",
    )
    context = replace(context, contract=structural.contract)
    notes = _rejected_claim_notes(result, context)
    assert any("第三种解释" in note and "原要求 q2" in note for note in notes)
    need = classify_repair_need(
        result.verified.outcome,
        result.verified,
        rejected_claims=(),
        semantic_gap_outputs=(),
    )
    assert (
        need.shape.contract_rewrite
        and not need.shape.input_only_rewrite
        and not need.needs_tools
    )
    goal = build_repair_goal(
        episode_id="requirements",
        missing_outputs=need.missing_outputs,
        missing_capabilities=(),
        rejected_claims=(),
        attempted_actions=(),
        previous_progress=ProgressSnapshot((), (), (), (), (), (), ()),
        remaining_calls=0,
        remaining_seconds=10,
        cycle=1,
        rejected_claim_notes=notes,
    )
    payload = json.loads(
        FinanceResearchHarness().repair_goal_message(goal, tools_open=False)
    )
    assert "不要作为 bindings" in payload["expression_elements_note"]
    assert "数值阈值" in payload["requirement_repair_rule"]
    assert payload["remaining_calls"] == 0 and not payload["reopen_tools"]


@pytest.mark.parametrize("repaired_complete", [True, False])
def test_adapter_reenters_once_and_rejudges_without_expanding_tool_budget(
    repaired_complete,
):
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.research_contract import InMemoryRootBudgetLedger
    from intelligence.tests.test_continuous_turn_adapter import (
        _control,
        _resumable_runtime,
    )

    frame, verified = _case()
    initial = verified.outcome
    repaired = replace(
        initial,
        draft=DRAFT + "\n补写反方：轮动解释仍需核验。[E1]",
        events=(*initial.events, EpisodeEvent(2, "model_turn", {})),
    )
    context = build_episode_context(
        frame,
        task_id=verified.contract.task_id,
        timeout=90,
        today="2026-09-21",
        latest_data_date="2026-09-18",
    )
    ledger = InMemoryRootBudgetLedger(
        episode_id=verified.contract.task_id,
        initial_calls=1,
        hard_calls_cap=8,
        initial_seconds=10,
        hard_seconds_cap=90,
    )
    context = replace(context, contract=verified.contract, root_budget=ledger)
    calls = []
    goals = []

    def judge(request):
        calls.append(request)
        return _report(
            request,
            partial=None if len(calls) == 2 and repaired_complete else ("q2", 1),
        )

    result = ContinuousTurnAdapter(
        runtime=_resumable_runtime(initial, repaired, goals),
        semantic_verifier=SemanticEpisodeVerifier(judge_fn=judge),
        runtime_name="continuous_glm",
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
        repair_seconds_cap=10,
    ).handle(frame=frame, control=_control(frame))
    assert result.status == ("completed" if repaired_complete else "partial")
    assert len(goals) == 1 and len(calls) == 2
    assert goals[0].missing_answer_elements == ("requirement_q2",)
    assert goals[0].remaining_calls == 0 and not goals[0].reopen_tools
    assert goals[0].remaining_seconds <= 10
    assert any("第三种解释" in note for note in goals[0].rejected_claim_notes)
    assert ledger.allocated_calls == 1
    assert calls[0]["requirement_review"] == calls[1]["requirement_review"]
    assert "补写反方" in result.answer
    artifact = result.private_artifact
    assert artifact["repair_cycles"] == 1
    assert artifact["semantic_verifier"]["verified"]["completion"]["task_coverage"] == (
        "fulfilled" if repaired_complete else "partial"
    )
    assert not artifact["semantic_verifier_stale"]


def test_adapter_final_projection_revokes_receipt_and_preserves_publication_notice(
    monkeypatch,
):
    import intelligence.runtime.continuous_turn_adapter as adapter_module
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.research_harness import (
        FinanceResearchHarness,
        PublicationAssessment,
    )
    from intelligence.tests.test_continuous_turn_adapter import _control

    frame, verified, semantic = _verify()
    context = build_episode_context(
        frame, task_id=verified.contract.task_id, timeout=60
    )
    context = replace(context, contract=verified.contract)
    witness = semantic.requirement_checks[0]["parts"][0]["answer_sentences"][0]["text"]
    original = adapter_module._with_calendar_disclosure
    monkeypatch.setattr(
        adapter_module,
        "_with_calendar_disclosure",
        lambda text, task: original(text.replace(witness, ""), task),
    )

    class Runtime:
        def run(self, *_args, **_kwargs):
            return verified.outcome

    class Semantic:
        def verify(self, **_kwargs):
            return semantic

    class Harness(FinanceResearchHarness):
        def assess_publication(self, **_kwargs):
            return PublicationAssessment(
                required_public_notices=("另有公开缺口说明。",)
            )

    result = adapter_module.ContinuousTurnAdapter(
        runtime=Runtime(),
        semantic_verifier=Semantic(),
        runtime_name="continuous_glm",
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
        harness=Harness(),
    ).handle(frame=frame, control=_control(frame))
    assert result.status == "partial"
    assert witness not in result.answer
    assert "另有公开缺口说明。" in result.answer
    assert (
        result.private_artifact["semantic_verifier"]["verified"]["completion"][
            "task_coverage"
        ]
        == "partial"
    )
    assert (
        result.private_artifact["semantic_verifier"]["requirement_checks"][0]["parts"][
            0
        ]["status"]
        == "partial"
    )


@pytest.mark.parametrize(
    "obstacle", ["no_evidence", "no_time", "used_delivery", "cycle_cap"]
)
def test_requirement_gap_does_not_bypass_repair_admission(obstacle):
    from intelligence.runtime.repair_budget import admit_repair
    from intelligence.services.repair_coordinator import (
        classify_repair_need,
        RepairWarrant,
        ProgressSnapshot,
    )
    from intelligence.services.research_contract import InMemoryRootBudgetLedger

    _, _, result = _verify(judge=lambda request: _report(request, partial=("q2", 1)))
    need = classify_repair_need(
        result.verified.outcome,
        result.verified,
        rejected_claims=(),
        semantic_gap_outputs=(),
    )
    ledger = InMemoryRootBudgetLedger(
        episode_id="requirements",
        initial_calls=1,
        hard_calls_cap=8,
        initial_seconds=10,
        hard_seconds_cap=90,
    )
    admission = admit_repair(
        need,
        RepairWarrant(cycle_allowed=obstacle != "cycle_cap", progressed=False),
        episode_id="requirements",
        previous_progress=ProgressSnapshot((), (), (), (), (), (), ()),
        remaining_calls=7,
        remaining_seconds=0 if obstacle == "no_time" else 30,
        cycle=1,
        root_budget=ledger,
        tools_open=True,
        allow_delivery_repair=obstacle != "used_delivery",
        evidence_count=0 if obstacle == "no_evidence" else 1,
    )
    assert admission is None
    assert ledger.allocated_calls == 1 and ledger.allocated_seconds == 10


def test_unrequested_receipts_cannot_be_smuggled_into_plain_reports():
    assert SemanticEpisodeVerifier._parse_report(_report(_request()), 2) is None
    assert (
        reconcile_requirement_checks(
            {"requirement_checks": []}, _request()["requirement_review"], []
        )
        is None
    )
