"""Scripted SDK run through the existing adapter/repair budget, no network/model.

Not a natural model success: confirms local delivery failures reopen the same
turn and can't reappear through rollback when repair doesn't fix them.
"""

from dataclasses import replace
import json
from uuid import uuid4

import pytest

from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
from intelligence.runtime.openai_agents_runtime import (
    AgentsSdkResult,
    OpenAIAgentsRuntime,
)
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import InMemoryRootBudgetLedger
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.tests.test_continuous_turn_adapter import _control, _frame
from intelligence.tests.test_research_delivery_checks import TABLE, _financial_evidence


@pytest.mark.parametrize("mode", ["off", "llm"])
@pytest.mark.parametrize("repair_result", ["unchanged", "corrected", "timeout"])
@pytest.mark.parametrize("window", ["reserved", "exhausted", "root_expired"])
@pytest.mark.parametrize("case", [
    "disclosure", "disclosure_comma", "disclosure_residue", "disclosure_dash",
    "calculation", "calculation_prose", "calculation_ranking", "calculation_periods", "calculation_unlocated",
])
def test_same_turn_repairs_without_extra_fetch_or_restoring_false_inference(
    monkeypatch, mode, repair_result, window, case
):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    reserve = window != "exhausted"
    can_repair = window == "reserved"
    clock = {"now": 0.0}
    monkeypatch.setattr(
        "intelligence.services.research_contract.time.monotonic", lambda: clock["now"]
    )
    monkeypatch.setattr(
        "intelligence.runtime.openai_agents_runtime.monotonic", lambda: 0.0
    )
    frame = _frame()
    control = _control(frame)
    context = build_episode_context(
        frame,
        task_id=f"delivery-repair-{uuid4().hex}",
        capabilities=control.capabilities,
        timeout=30,
    )
    budget = InMemoryRootBudgetLedger(
        episode_id=context.contract.task_id,
        initial_calls=1,
        hard_calls_cap=1,
        initial_seconds=1,
        hard_seconds_cap=3 if reserve else 1,
    )
    context = replace(context, root_budget=budget)
    fetched = []
    evidence = AgentEvidence(
        tool="market_data",
        title="已取得的独立事实",
        detail="已核实中报收入，公告窗口覆盖仍不完整。",
        source="fixture",
        source_date="2026-09-17",
        content_hash="repair-input",
    )

    inputs = (evidence,) if case.startswith("disclosure") else (evidence, *_financial_evidence())

    def fetch(query, _context):
        fetched.append(query)
        return (
            list(inputs),
            evidence.detail,
            ProviderTrace("l3_lookup", "l3_lookup", "partial", result_count=1),
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="fixture",
                cost="local",
                freshness="current",
                runner=fetch,
            ),
        )
    )
    requests = []
    repair_inputs = []
    bad = "已核实中报收入。[E1]。窗口内无新公告即无新增官方信息差。仍需补全窗口查询。"
    good = "已核实中报收入。[E1]。公告来源仅部分返回，不能据此断言公司没有公告。"
    if case == "disclosure_comma":
        bad = "已核实中报收入[E1]，但查询返回空白，因此公司没有公告。"
    elif case == "disclosure_residue":
        bad = "已核实中报收入[E1]，查询返回空白，因此没有新公告，即公司无新增公告。"
    elif case == "disclosure_dash":
        bad = "已核实中报收入[E1]——查询返回空白因此公司没有公告。"
    elif case == "calculation":
        bad = "已核实中报收入。[E1]。\n" + TABLE
        good = bad.replace("1.587", "1.588")
    elif case == "calculation_prose":
        bad = "已核实中报收入[E1]，2026中报含金量为1.587，2025中报含金量为0.289。"
        good = bad.replace("1.587", "1.588")
    elif case == "calculation_ranking":
        bad = "已核实中报收入[E1]，2026中报含金量3年新高，实际为1.587，2025中报含金量为0.289。"
        good = bad.replace("1.587", "1.588")
    elif case == "calculation_periods":
        bad = "已核实中报收入[E1]，含金量对照：2026中报 2025中报分别为1.587与0.289。"
        good = bad.replace("1.587", "1.588")

    if case == "calculation_unlocated":
        bad = "已核实中报收入[E1]，2026中报含金量3年最高，为1.587，2025中报含金量为0.289。"
        good = "已核实中报收入[E1]，2026中报含金量为1.588，2025中报含金量为0.289。"

    def run(request):
        requests.append(request)
        if len(requests) == 1:
            request.tools[0].invoke("fixture")
            budget.consume_seconds(seconds=budget.remaining_seconds)
            clock["now"] = 121.0 if window == "root_expired" else 31.0
        else:
            assert request.tools == ()  # no extra lookup / tool grant
            repair_input = json.loads(request.input)
            assert repair_input["kind"] == "REPAIR_GOAL"
            assert repair_input["episode_id"] == context.contract.task_id
            assert repair_input["evidence"][0]["content_hash"] == evidence.content_hash
            assert repair_input["remaining_calls"] == 0
            repair_inputs.append(repair_input)
            if repair_result == "timeout":
                raise TimeoutError("scripted repair failure")
        return AgentsSdkResult(
            json.dumps(
                {
                    "status": "completed",
                    "draft": good
                    if len(requests) > 1 and repair_result == "corrected"
                    else bad,
                    "gaps": [],
                    "bindings": [
                        {
                            "output_id": "direct_assessment",
                            "evidence_hashes": [evidence.content_hash],
                            "gap": "",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            1,
        )

    result = ContinuousTurnAdapter(
        runtime=OpenAIAgentsRuntime(
            runner=run, backend="sdk_gpt", model_name="scripted-test"
        ),
        runtime_name="sdk_gpt",
        mode="on",
        timeout=120,
        context_factory=lambda *a, **kw: context,
        registry_factory=lambda *a, **kw: registry,
        semantic_verifier=SemanticEpisodeVerifier(
            judge_fn=lambda request: {
                "passed": True,
                "rejected_sentence_indexes": [],
                "issues": [],
            }
        ),
    ).handle(frame=frame, control=control)
    assert len(fetched) == 1
    assert len(requests) == (2 if can_repair else 1), result.private_artifact.get(
        "error"
    )
    if can_repair:
        assert len(repair_inputs) == 1
        expected_note = (
            "查询失败或空白不能推出没有公告"
            if case.startswith("disclosure")
            else "按报告期及比率列重新对账"
        )
        assert any(
            expected_note in note for note in repair_inputs[0]["unsupported_claims"]
        )
    assert budget.hard_calls_cap == 1 and budget.hard_seconds_cap == (
        3 if reserve else 1
    )
    assert budget.allocated_calls == 1
    assert budget.allocated_seconds <= budget.hard_seconds_cap
    assert "窗口内无新公告即" not in result.answer
    assert "因此公司没有公告" not in result.answer
    assert "因此没有新公告" not in result.answer
    assert "即公司无新增公告" not in result.answer
    if case == "calculation_unlocated" and not (can_repair and repair_result == "corrected") and window != "root_expired":
        assert "〔比率对应关系待核对〕" in result.answer
        assert "不能视为已核算结论" in result.answer
        assert "1.587" in result.answer  # retained as explicitly unverified, not replaced by a guess
    else:
        assert "1.587" not in result.answer
    if window == "root_expired":
        # The root expires BEFORE any semantic verification. No trusted answer
        # exists yet; do not silently authenticate the unverified first draft.
        assert result.status == "degraded" and "核验未完成" in result.answer
        assert result.private_artifact["repair_attempts"] == 0
        assert result.private_artifact["outcome"]["evidence"]
        return
    assert result.private_artifact["runtime_handle"]["state"] == "closed"
    assert "已核实中报收入" in result.answer
    assert "[E1]" in result.answer
    assert {c["title"] for c in result.citations} == {evidence.title}
    if case.startswith("calculation"):
        if case == "calculation":
            assert "706.91" in result.answer and "445.17" in result.answer
        assert "0.289" in result.answer
        if case in {"calculation_ranking", "calculation_periods"}:
            assert "2026中报" in result.answer and "2025中报" in result.answer
        if case == "calculation_ranking":
            assert "3年新高" in result.answer
        assert (
            "1.588" if can_repair and repair_result == "corrected" else "待核对"
        ) in result.answer
    assert result.status == (
        "completed" if can_repair and repair_result == "corrected" else "partial"
    )
    assert result.private_artifact["repair_attempts"] == int(can_repair)
    # The preserved draft stays private on failed repair; it cannot be replayed
    # directly to the user. No provider diagnostics belong in the public text.
    assert "scripted repair failure" not in result.answer


@pytest.mark.parametrize("separator", ["。", "，", "但", "——", " "])
def test_adapter_rechecks_nonmaterial_final_projection(monkeypatch, separator):
    from intelligence.runtime import continuous_turn_adapter as adapter
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeOutcome
    from intelligence.services.episode_session import CallbackEpisodeSession
    from intelligence.services.agent_runtime import (
        AgentOutcome,
        AgentUsage,
        EpisodeEvent,
        OutputEvidenceBinding,
    )

    frame = _frame()
    control = _control(frame)
    context = build_episode_context(
        frame,
        task_id=f"delivery-projection-{uuid4().hex}",
        capabilities=control.capabilities,
        timeout=30,
    )
    source = AgentEvidence(
        tool="market_data",
        title="可信事实",
        detail="已核实中报收入。",
        source="fixture",
        content_hash="projection-input",
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="已核实中报收入。[E1]。",
        evidence=(source,),
        traces=(ProviderTrace("l3_lookup", "l3_lookup", "partial"),),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=(
            OutputEvidenceBinding("direct_assessment", (source.content_hash,), ""),
        ),
        usage=AgentUsage(),
    )

    class Runtime:
        def start(self, frame, **kwargs):
            return CallbackEpisodeSession(
                episode_id=context.contract.task_id,
                outcome=outcome,
                resume_callback=lambda previous, goal: pytest.fail(
                    "no repair expected before final projection"
                ),
            )

    class Verifier:
        def verify(self, *, structurally_verified, **kwargs):
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer=outcome.draft,
                judge_status="passed",
            )

    # Adversarial seam injection, not a natural calendar/model behavior.
    monkeypatch.setattr(
        adapter,
        "_with_calendar_disclosure",
        lambda text, frame: text.rstrip("。") + separator + "窗口内无新公告即无新增官方信息差。",
    )
    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        runtime_name="sdk_gpt",
        mode="on",
        context_factory=lambda *args, **kwargs: context,
        registry_factory=lambda *args, **kwargs: ResearchToolRegistry(()),
        semantic_verifier=Verifier(),
    ).handle(frame=frame, control=control)
    assert result.status == "partial", result.private_artifact
    assert "窗口内无新公告即" not in result.answer
    assert "已核实中报收入" in result.answer and result.citations
