"""Historical evidence must survive the actual episode finish/verification seam."""

from dataclasses import replace
from datetime import date

import duckdb
import pytest

from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.historical_research.episode import (
    HistorySession,
    history_tool_specs,
)
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.run_store import RunStore


@pytest.mark.parametrize("has_history_result", [False, True])
@pytest.mark.parametrize("repair", [False, True])
def test_history_finish_gap_survives_semantic_completion_and_publication(
    tmp_path, has_history_result, repair
):
    """M3: ordinary finance evidence filled slots but no history query ran."""
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.runtime.turn_control_core import TurnControlResult
    from intelligence.services.agent_research import AgentEvidence

    frame, context, registry = _history_episode(tmp_path)
    evidence = (
        AgentEvidence(
            tool="finance_query",
            title="农业同期行情",
            detail="农业样本共同上涨，但现有资料无法区分独立催化与同期行情共振。",
            source="本地行情",
            source_date="2026-08-04",
            content_hash="local-finance-evidence",
        ),
    )
    if has_history_result:
        query_result = registry.execute(
            "history_query",
            {
                "operation": "compute_history",
                "start": "2026-08-03",
                "end": "2026-08-04",
                "entity_codes": ["A.FP"],
                "features": ["return_pct"],
            },
            context=context,
            step_id="query",
        )
        evidence = query_result.evidence
    draft = (
        "农业样本存在共同上涨的现象。竞争性解释是同期行情共振，尚不能认定独立催化。"
        "证据边界是缺少可靠新闻与独立多样本比较；这只是历史探索，尚非认证规律。"
    )
    admission = FinanceResearchHarness().admit_finish(
        {
            "status": "completed",
            "draft": draft,
            "gaps": [],
            "bindings": [
                {
                    "output_id": output.output_id,
                    "evidence_hashes": ["E1"],
                    "basis": output.grounding_mode,
                    "gap": "",
                }
                for output in context.contract.required_outputs
            ],
        },
        context=context,
        evidence=evidence,
        registry=registry,
    )
    assert admission.accepted, admission.reason
    assert admission.status == ("completed" if has_history_result else "partial")
    assert bool(context.history_results) is has_history_result
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status=admission.status,
        draft=admission.draft,
        evidence=evidence,
        traces=(),
        gaps=admission.gaps,
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=admission.bindings,
        usage=AgentUsage(llm_calls=0, tool_calls=0),
    )

    class Runtime:
        def run(self, **_kwargs):
            return outcome

    judge_calls = []

    def judge(request):
        judge_calls.append(request)
        reject = repair and len(judge_calls) == 1
        return {
            "passed": not reject,
            "rejected_sentence_indexes": [2] if reject else [],
            "issues": ["因果证据不足"] if reject else [],
        }

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: registry,
        semantic_verifier=SemanticEpisodeVerifier(judge_fn=judge),
    ).handle(
        frame=frame,
        control=TurnControlResult(
            task_frame=frame,
            execution_route=frame.question_type,
            terminal_kind="research",
            needs_retrieval=True,
            capabilities=("finance_query",),
            contract_required=True,
        ),
    )
    assert result.status == ("completed" if has_history_result else "partial")
    notice = "尚无可核验的历史计算原件，未完成历史样本检验。"
    assert (notice in result.answer) is not has_history_result
    assert (notice in result.open_gaps) is not has_history_result
    assert "农业样本存在共同上涨的现象" in result.answer
    assert result.citations
    assert result.private_artifact["semantic_verifier"]["judge_status"] == (
        "repaired" if repair else "passed"
    )


def _history_episode(tmp_path):
    question = "这一波农业是怎么走出来的？"
    path = tmp_path / "history.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE fact_sector_daily (trade_date DATE, sector_ts_code TEXT, "
            "sector_name TEXT, pct_chg DOUBLE, amount DOUBLE, diff_ratio DOUBLE)"
        )
        con.execute(
            "INSERT INTO fact_sector_daily VALUES "
            "('2026-08-03', 'A.FP', '农业', 1, 100, 15), "
            "('2026-08-04', 'A.FP', '农业', 2, 130, 30)"
        )
        con.execute(
            "CREATE TABLE fact_market_daily "
            "(trade_date DATE, sh_index_pct_chg DOUBLE)"
        )
        con.execute(
            "INSERT INTO fact_market_daily VALUES "
            "('2026-08-03', 0), ('2026-08-04', 0)"
        )
    store = RunStore("history-test", root=tmp_path / "runs")
    run = store.create_run(question, "ask", session_id="history-conversation")
    session = HistorySession(store, run.run_id, "history-conversation")
    frame = understand_query(question).task_frame
    context = build_episode_context(
        frame,
        task_id=run.run_id,
        capabilities=("finance_query",),
        information_cutoff=InformationCutoff(date(2026, 9, 7), "requested"),
    )
    registry = ResearchToolRegistry(
        tuple(history_tool_specs(frame, context, path, session))
    )
    return frame, context, registry


@pytest.mark.parametrize("evidence_tool", ["history_query", "read_history_result"])
def test_real_history_evidence_reaches_structural_and_numeric_semantic_verification(
    tmp_path, evidence_tool
):
    # Reproduces the natural-question failure: finance_query authorization was
    # present, yet the real producer name made every bound output unsupported.
    frame, context, registry = _history_episode(tmp_path)
    result = registry.execute(
        "history_query",
        {
            "operation": "compute_history",
            "start": "2026-08-03",
            "end": "2026-08-04",
            "entity_codes": ["A.FP"],
            "features": ["return_pct"],
        },
        context=context,
        step_id="query",
    )
    if evidence_tool == "read_history_result":
        result = registry.execute(
            evidence_tool,
            {"result_ref": result.telemetry["result_ref"]},
            context=context,
            step_id="read",
        )
    assert result.trace.status == "success"
    assert {item.tool for item in result.evidence} == {evidence_tool}
    draft = (
        "农业样本的区间涨幅为3.02%。竞争性解释是同期行情共振，尚不能认定独立催化。"
        "证据边界是缺少可靠新闻与独立多样本比较；这只是历史探索，尚非认证规律。"
    )
    admission = FinanceResearchHarness().admit_finish(
        {
            "status": "completed",
            "draft": draft,
            "gaps": [],
            "bindings": [
                {
                    "output_id": output.output_id,
                    "evidence_hashes": [
                        f"E{index}" for index in range(1, len(result.evidence) + 1)
                    ],
                    "basis": output.grounding_mode,
                    "gap": "",
                }
                for output in context.contract.required_outputs
            ],
        },
        context=context,
        evidence=result.evidence,
        registry=registry,
    )
    assert admission.accepted, admission.reason
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status=admission.status,
        draft=admission.draft,
        evidence=result.evidence,
        traces=(result.trace,),
        gaps=admission.gaps,
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=admission.bindings,
        usage=AgentUsage(llm_calls=0, tool_calls=1),
    )
    structural = verify_episode_outcome(context.contract, outcome)
    assert structural.verified_status == "completed", structural.issues
    assert not structural.missing_outputs
    assert all(item.status == "fulfilled" for item in structural.completion.outputs)

    judge_requests = []

    def judge(request):
        judge_requests.append(request)
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    semantic = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert len(judge_requests) == 1
    assert semantic.status == "completed"
    assert semantic.judge_status == "passed"
    assert "3.02%" in semantic.public_answer
    assert evidence_tool in str(judge_requests[0])


@pytest.mark.parametrize(
    "question",
    [
        "这一波农业是怎么走出来的？",
        "复盘这一波半导体是怎么走出来的？",
        "这一波农业是怎么走出来的？你认为后市会怎么走？",
    ],
)
def test_history_prompt_does_not_require_a_future_scenario_tree(question):
    frame = understand_query(question).task_frame
    context = build_episode_context(frame, task_id=f"history-prompt:{question}")
    assert context.history_intent is not None
    system, user = FinanceResearchHarness().assemble_prompt(
        frame, context, ResearchToolRegistry(())
    )
    assert "【情景树表达契约】" not in system + user
    if "后市" in question:
        # Explicitly asking about the future still has a legitimate optional
        # reasoning slot, without forcing the retrospective into that shape.
        forward = next(
            output
            for output in context.contract.required_outputs
            if output.output_id == "scenario_paths"
        )
        assert not forward.required
        assert forward.grounding_mode == "model_reasoning"
        assert not forward.evidence_types


def test_nonhistorical_forecast_preserves_the_scenario_contract():
    frame = understand_query("明天市场会怎么走？").task_frame
    context = build_episode_context(frame, task_id="forecast-prompt")
    assert context.history_intent is None
    system, user = FinanceResearchHarness().assemble_prompt(
        frame, context, ResearchToolRegistry(())
    )
    assert "【情景树表达契约】" in system + user
    assert all(
        "history_query" not in output.evidence_types
        and "read_history_result" not in output.evidence_types
        for output in context.contract.required_outputs
    )


def test_history_does_not_widen_specialized_output_evidence_contracts():
    frame = replace(
        understand_query("这一波农业是怎么走出来的？").task_frame,
        required_outputs=(
            "direct_assessment",
            "prime_quote",
            "prime_news",
            "prior_recall",
            "financial_business_anchor",
        ),
    )
    context = build_episode_context(
        frame,
        task_id="history-narrow-slots",
        capabilities=(
            "finance_query",
            "market_data",
            "news_search",
            "memory_lookup",
            "financial_data",
        ),
    )
    types = {
        output.output_id: output.evidence_types
        for output in context.contract.required_outputs
    }
    assert types["prime_quote"] == ("market_data",)
    assert types["prime_news"] == ("news_search",)
    assert types["prior_recall"] == ("memory_lookup",)
    assert types["financial_business_anchor"] == ("financial_data",)
    assert {"history_query", "read_history_result"} <= set(types["direct_assessment"])
    assert not {"history_query", "read_history_result"} & set(
        context.contract.allowed_capabilities
    )
