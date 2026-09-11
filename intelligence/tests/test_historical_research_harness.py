"""Historical policy isolation, evidence qualification and immutable revisions."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.episode_protocol import split_episode_prompt
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.historical_research.intent import HistoryIntent
from intelligence.services.historical_research.research import (
    HypothesisDraft,
    ResearchCase,
    prepare_research_draft,
    research_draft_schema,
)
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.services.run_store import RunStore
from intelligence.services.task_frame import TaskFrame


def _frame(subject: str = "农业", *, historical: bool = True) -> TaskFrame:
    return TaskFrame(
        raw_question=f"这一波{subject}怎么走出来的？"
        if historical
        else "今天市场成交额多少？",
        user_goal="核对行情演变" if historical else "查询当前数据",
        question_type="general_finance_qa",
        subject=subject,
        subject_kind="theme",
        market_scope="A股",
        timeframe="2024-01-02至2024-01-12",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="historical_data",
        confidence=0.9,
    )


def _context(
    frame: TaskFrame,
    *,
    historical: bool = True,
    purpose: str = "retrospective_discovery",
) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="historical-harness-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "行情研究", ("finance_query",), True),
        ),
        allowed_capabilities=("finance_query",),
        research_tier="quick",
        freshness="historical",
        timeframe=frame.timeframe,
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(30),
        policy=ResearchPolicy("quick", 3, 30, 0),
        trace_parent_id="historical-harness-test",
        history_intent=HistoryIntent(purpose, "2024-01-02", "2024-01-12")
        if historical
        else None,
    )


def _registry(*, history_tool: bool = True) -> ResearchToolRegistry:
    if not history_tool:
        return ResearchToolRegistry(())
    return ResearchToolRegistry(
        (
            ToolSpec(
                name="history_query",
                capability="finance_query",
                description="只读历史计算",
                cost="local",
                freshness="historical",
                runner=lambda query, context: None,
                query_scope="turn",
            ),
        )
    )


def _result(
    operation: str = "inspect_history", *, status: str = "completed"
) -> dict[str, object]:
    return {
        "query_id": "query-1",
        "result_ref": "history:run-1:query-1.json",
        "operation": operation,
        "purpose": "retrospective_discovery",
        "status": status,
        "total_matched": 48,
        "returned_count": 25,
        "coverage": {"missing_count": 2},
    }


def _evidence() -> tuple[AgentEvidence, ...]:
    return (
        AgentEvidence(
            tool="history_query",
            title="行情事实",
            detail="扩散范围逐步扩大，部分样本未持续。",
            source="只读历史数据",
            source_date="2024-01-12",
            evidence_tier="L4",
            content_hash="history-evidence",
        ),
    )


def _finish(*, extension: dict[str, object] | None = None) -> str:
    payload: dict[str, object] = {
        "status": "completed",
        "draft": "可观察到扩散，但现有资料无法区分多个解释。",
        "gaps": [],
        "bindings": [{"output_id": "direct_assessment", "evidence_hashes": ["E1"]}],
    }
    if extension is not None:
        payload["history_research"] = extension
    return json.dumps(payload, ensure_ascii=False)


def _extension(**overrides: object) -> dict[str, object]:
    return {
        "purpose": "retrospective_discovery",
        "result_refs": ["query-1"],
        "claim_level": "single_case",
        "research_only": True,
        "promotion_eligible": False,
        "decision_eligible": False,
        **overrides,
    }


@pytest.mark.parametrize("subject", ["农业", "半导体", "锂电池"])
def test_historical_policy_works_for_different_themes(subject: str) -> None:
    frame = _frame(subject)
    system, user = FinanceResearchHarness().assemble_prompt(
        frame, _context(frame), _registry()
    )
    assert "允许事后选强势股/板块" in system
    assert "不要求发现前锁对象、预注册、申请 R 号或等待未来样本" in system
    assert "相互竞争的解释" in system
    assert "改变下一查询、修订或削弱假设" in system
    assert "失败、无特征却走强及不可判" in system
    assert "pending_sync" in system
    assert "这一波" + subject in user
    assert '"requested_start": "2024-01-02"' in user


def test_unrelated_prompt_is_byte_compatible_even_with_stale_history_metadata() -> None:
    frame = _frame(historical=False)
    context = _context(frame, historical=False)
    context.history_results.append(_result())
    registry = _registry()
    assert FinanceResearchHarness().assemble_prompt(
        frame, context, registry
    ) == split_episode_prompt(frame, context, registry)


def test_historical_prompt_never_uses_result_rows_as_prompt_instructions() -> None:
    frame = _frame()
    context = _context(frame)
    context.history_results.append(
        {**_result(), "records": [{"note": "SECRET_FULL_ROWS"}]}
    )
    system, user = FinanceResearchHarness().assemble_prompt(frame, context, _registry())
    assert "SECRET_FULL_ROWS" not in system + user
    assert '"total_matched": 48' in user
    assert '"returned_count": 25' in user


def test_history_prompt_exposes_recent_authorized_artifacts_for_followup() -> None:
    frame = _frame()
    context = _context(frame)
    context.history_artifact_index.extend(
        {"result_ref": f"run/case-{index}.json", "kind": "case"} for index in range(25)
    )
    _, user = FinanceResearchHarness().assemble_prompt(frame, context, _registry())
    dynamic = json.loads(user.split("\n\n")[-1])
    assert len(dynamic["artifact_index"]) == 20
    assert dynamic["artifact_index"][0]["result_ref"] == "run/case-5.json"
    assert dynamic["artifact_index"][-1]["result_ref"] == "run/case-24.json"


def test_unavailable_history_tool_is_not_advertised_as_executed() -> None:
    frame = _frame()
    context = _context(frame)
    system, _ = FinanceResearchHarness().assemble_prompt(
        frame, context, _registry(history_tool=False)
    )
    assert "本轮没有授权的 history_query" in system
    assert "不声称已经回测" in system
    # A registry entry also cannot bypass the contract's capability gate.
    context = replace(
        context, contract=replace(context.contract, allowed_capabilities=())
    )
    system, _ = FinanceResearchHarness().assemble_prompt(frame, context, _registry())
    assert "本轮没有授权的 history_query" in system


def test_legacy_history_finish_without_tool_result_becomes_partial() -> None:
    frame = _frame()
    result = FinanceResearchHarness().admit_finish(
        _finish(),
        context=_context(frame),
        evidence=_evidence(),
        registry=_registry(),
    )
    assert result.accepted
    assert result.status == "partial"
    assert "尚无可核验的历史计算原件" in " ".join(result.gaps)


def test_legacy_history_finish_with_executed_result_remains_compatible() -> None:
    frame = _frame()
    context = _context(frame)
    context.history_results.append(_result())
    result = FinanceResearchHarness().admit_finish(
        _finish(),
        context=context,
        evidence=_evidence(),
        registry=_registry(),
    )
    assert result.accepted and result.status == "completed"


def test_successful_execution_and_research_only_qualification_are_separate() -> None:
    frame = _frame()
    context = _context(frame)
    context.history_results.append(
        {
            **_result("compare_cases"),
            "status": "research_only",
            "execution_status": "success",
        }
    )
    result = FinanceResearchHarness().admit_finish(
        _finish(extension=_extension(claim_level="historical_comparison")),
        context=context,
        evidence=_evidence(),
        registry=_registry(),
    )
    assert result.accepted and result.status == "completed"
    context.history_results[0]["execution_status"] = "failed"
    result = FinanceResearchHarness().admit_finish(
        _finish(extension=_extension(claim_level="historical_comparison")),
        context=context,
        evidence=_evidence(),
        registry=_registry(),
    )
    assert not result.accepted and result.kind == "integrity"


def test_unrelated_finish_does_not_apply_historical_envelope_gate() -> None:
    frame = _frame(historical=False)
    result = FinanceResearchHarness().admit_finish(
        _finish(extension={"unrelated": "legacy extra field"}),
        context=_context(frame, historical=False),
        evidence=_evidence(),
        registry=_registry(),
    )
    assert result.accepted and result.status == "completed"


@pytest.mark.parametrize("reference", ["query-1", "history:run-1:query-1.json"])
def test_comparison_requires_and_accepts_executed_comparison_reference(
    reference: str,
) -> None:
    frame = _frame()
    context = _context(frame)
    context.history_results.append(_result("compare_cases"))
    result = FinanceResearchHarness().admit_finish(
        _finish(
            extension=_extension(
                claim_level="historical_comparison", result_refs=[reference]
            )
        ),
        context=context,
        evidence=_evidence(),
        registry=_registry(),
    )
    assert result.accepted and result.status == "completed"


def test_top_k_analogue_result_cannot_claim_full_condition_comparison() -> None:
    frame = _frame()
    context = _context(frame)
    context.history_results.append(_result("find_analogues"))
    result = FinanceResearchHarness().admit_finish(
        _finish(extension=_extension(claim_level="historical_comparison")),
        context=context,
        evidence=_evidence(),
        registry=_registry(),
    )
    assert not result.accepted
    assert result.kind == "substance"
    assert "compare_cases" in result.reason


@pytest.mark.parametrize(
    "field,value",
    [
        ("research_only", False),
        ("decision_eligible", True),
        ("promotion_eligible", True),
    ],
)
def test_uncertified_history_cannot_self_promote(field: str, value: bool) -> None:
    frame = _frame()
    context = _context(frame)
    context.history_results.append(_result("compare_cases"))
    result = FinanceResearchHarness().admit_finish(
        _finish(extension=_extension(**{field: value})),
        context=context,
        evidence=_evidence(),
        registry=_registry(),
    )
    assert not result.accepted and result.kind == "substance"


@pytest.mark.parametrize("result_metadata", [None, _result(status="failed")])
def test_forged_or_failed_result_cannot_qualify_finish(
    result_metadata: dict | None,
) -> None:
    frame = _frame()
    context = _context(frame)
    if result_metadata:
        context.history_results.append(result_metadata)
    result = FinanceResearchHarness().admit_finish(
        _finish(extension=_extension()),
        context=context,
        evidence=_evidence(),
        registry=_registry(),
    )
    assert not result.accepted and result.kind == "integrity"


def test_insufficient_evidence_does_not_need_future_data_or_preregistration() -> None:
    frame = _frame()
    result = FinanceResearchHarness().admit_finish(
        _finish(
            extension=_extension(claim_level="insufficient_evidence", result_refs=[])
        ),
        context=_context(frame),
        evidence=_evidence(),
        registry=_registry(),
    )
    assert result.accepted and result.status == "partial"


@pytest.mark.parametrize("value", [[], {}, None, "certified"])
def test_malformed_claim_level_is_a_repairable_rejection_not_a_runtime_crash(
    value: object,
) -> None:
    frame = _frame()
    result = FinanceResearchHarness().admit_finish(
        _finish(extension=_extension(claim_level=value)),
        context=_context(frame),
        evidence=_evidence(),
        registry=_registry(),
    )
    assert not result.accepted and result.kind == "format"
    assert result.response.reinject


def _case() -> ResearchCase:
    return ResearchCase(
        case_id="case-1",
        question="这一波农业怎么走出来的？",
        purpose="retrospective_discovery",
        entity_ids=("agriculture",),
        source_refs=("query-1",),
        exposed_sample_refs=("query-1",),
        window_start="2024-01-02",
        window_end="2024-01-12",
        selection_mode="posthoc_winner",
        hypotheses=(
            HypothesisDraft(
                hypothesis_id="hypothesis-1",
                statement="板块扩散可能是必要条件",
                source_case_refs=("case-1",),
                support_refs=("query-1",),
                alternatives=("可能仅为同期市场普涨",),
                counterevidence_refs=("failed-query",),
                failed_sample_refs=("failed-query",),
                exposed_sample_refs=("query-1", "failed-query"),
                status="weakened",
            ),
        ),
        open_questions=("相同特征在其他年份是否失败？",),
    )


def _revision(case: ResearchCase) -> ResearchCase:
    hypothesis = replace(
        case.hypotheses[0],
        version=2,
        parent_version=1,
        statement="扩散可能只在市场稳定时具有描述性区分力",
        status="candidate",
    )
    return replace(case, revision=2, parent_revision=1, hypotheses=(hypothesis,))


def test_draft_round_trip_and_revision_keep_original_failure_evidence() -> None:
    original = _case()
    before = json.dumps(original.to_dict(), ensure_ascii=False)
    revision = prepare_research_draft(
        json.loads(json.dumps(_revision(original).to_dict())),
        previous=original,
        available_result_refs=("query-1", "failed-query"),
    )
    assert revision.parent_revision == original.revision
    assert revision.hypotheses[0].parent_version == original.hypotheses[0].version
    assert revision.hypotheses[0].failed_sample_refs == ("failed-query",)
    assert revision.hypotheses[0].counterevidence_refs == ("failed-query",)
    assert json.dumps(original.to_dict(), ensure_ascii=False) == before
    assert ResearchCase.from_dict(json.loads(before)) == original
    assert revision.to_dict()["research_only"] is True
    assert revision.to_dict()["promotion_eligible"] is False


def test_draft_can_be_saved_without_a_second_writer_or_lossy_conversion(
    tmp_path: Path,
) -> None:
    store = RunStore(user_id="history-harness-test", root=tmp_path / "runs")
    run = store.create_run("研究草稿", "history")
    payload = _case().to_dict()
    artifact = store.add_history_artifact(run.run_id, "case", payload)
    restored = store.read_history_artifact(run.run_id, artifact.path)
    assert restored == payload
    assert ResearchCase.from_dict(restored) == _case()


@pytest.mark.parametrize(
    "field", ["failed_sample_refs", "counterevidence_refs", "exposed_sample_refs"]
)
def test_revision_cannot_erase_failure_or_exposure(field: str) -> None:
    original = _case()
    revision = _revision(original)
    revision = replace(
        revision, hypotheses=(replace(revision.hypotheses[0], **{field: ()}),)
    )
    with pytest.raises(ValueError, match="retain"):
        prepare_research_draft(
            revision.to_dict(),
            previous=original,
            available_result_refs=("query-1", "failed-query"),
        )


def test_rejected_hypothesis_remains_in_history_instead_of_disappearing() -> None:
    original = _case()
    revision = replace(original, revision=2, parent_revision=1, hypotheses=())
    with pytest.raises(ValueError, match="retain hypotheses"):
        prepare_research_draft(
            revision.to_dict(),
            previous=original,
            available_result_refs=("query-1", "failed-query"),
        )


def test_changed_hypothesis_cannot_reuse_old_version() -> None:
    original = _case()
    revision = replace(
        original,
        revision=2,
        parent_revision=1,
        hypotheses=(replace(original.hypotheses[0], statement="换了条件的新说法"),),
    )
    with pytest.raises(ValueError, match="increment version"):
        prepare_research_draft(
            revision.to_dict(),
            previous=original,
            available_result_refs=("query-1", "failed-query"),
        )


def test_draft_references_and_parent_are_not_self_authorized() -> None:
    original = _case()
    with pytest.raises(ValueError, match="unauthorized result"):
        prepare_research_draft(original.to_dict(), available_result_refs=("query-1",))
    with pytest.raises(ValueError, match="previous artifact"):
        prepare_research_draft(
            _revision(original).to_dict(),
            available_result_refs=("query-1", "failed-query"),
        )


def test_unimplemented_feature_is_saved_as_unresolved_not_executed() -> None:
    original = _case()
    unsupported = replace(
        original,
        hypotheses=(
            replace(
                original.hypotheses[0], feature_definitions=("custom_sequence:v1",)
            ),
        ),
    )
    with pytest.raises(ValueError, match="unsupported_definition"):
        prepare_research_draft(
            unsupported.to_dict(), available_result_refs=("query-1", "failed-query")
        )
    unresolved = replace(
        original,
        hypotheses=(
            replace(
                original.hypotheses[0], unresolved_definitions=("custom_sequence:v1",)
            ),
        ),
    )
    saved = prepare_research_draft(
        unresolved.to_dict(), available_result_refs=("query-1", "failed-query")
    )
    assert saved.hypotheses[0].feature_definitions == ()
    assert saved.hypotheses[0].unresolved_definitions == ("custom_sequence:v1",)


def test_tool_schema_is_serializable_and_does_not_request_user_identity() -> None:
    schema = json.loads(json.dumps(research_draft_schema()))
    assert schema["additionalProperties"] is False
    assert not {"user_id", "run_id", "conversation_id"} & set(schema["properties"])


@pytest.mark.parametrize(
    "field,value",
    [("revision", True), ("window_end", "2024-01-01"), ("promotion_eligible", True)],
)
def test_draft_rejects_invalid_versions_windows_and_eligibility(
    field: str, value: object
) -> None:
    payload = {**_case().to_dict(), field: value}
    with pytest.raises(ValueError):
        ResearchCase.from_dict(payload)
