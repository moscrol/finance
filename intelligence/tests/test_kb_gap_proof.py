"""V2：缺口声明取证义务。零 KB 查证不得写成断言性「库无/暂无」。

口径与 V7 钉 ``test_shape_i_called_uses_provider_not_capability`` 一致：
本轮是否调过 KB 看 ``provider=agent:kb_search|agent:evidence_search``，
不按 capability 分组（成功路 capability 是 ``agent_loop``）。
"""

from __future__ import annotations

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_answer_hygiene import (
    find_unverified_kb_gap_claims,
    kb_gap_claim_kind,
    rewrite_unverified_kb_gap_claims,
    traces_include_kb_query,
)
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchTaskContract,
)
from intelligence.services.task_frame import TaskFrame
from intelligence.tests.test_episode_semantic_verifier import _judge

_ANNOUNCEMENT_GAP = "板块在发酵，但缺公告级证据，无法确认订单落地。"
_ABSENT_GAP = "知识库无该题材公告级证据，产业链角色无法落格。"
_ABSENT_TEMP = "知识库暂无该题材公告级证据。"


def _kb_trace(*, provider: str, capability: str, result_count: int = 0) -> ProviderTrace:
    return ProviderTrace(
        provider=provider,
        capability=capability,
        status="success",
        result_count=result_count,
    )


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="减肥药这波从月初发酵到现在怎么看",
        user_goal="判断发酵",
        question_type="theme_analysis",
        subject="减肥药",
        subject_kind="theme",
        market_scope="A股",
        timeframe="当前",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="theme_multi_layer_evidence",
        confidence=0.9,
    )


def _verify(draft: str, traces: tuple[ProviderTrace, ...]):
    frame = _frame()
    evidence = AgentEvidence(
        tool="market_data",
        title="盘面快照",
        detail="板块涨跌与成交",
        source="行情快照",
        source_date="2026-08-19",
        content_hash="HASH_V2_GAP_PROOF",
    )
    contract = ResearchTaskContract(
        task_id="v2-gap-proof",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
        ),
        allowed_capabilities=("market_data", "kb_search", "evidence_search"),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft=draft,
        evidence=(evidence,),
        traces=traces,
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=(OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    structural = verify_episode_outcome(contract, outcome)
    return SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )


def test_zero_kb_call_is_unverified_kind() -> None:
    assert kb_gap_claim_kind(()) == "未查证"
    assert traces_include_kb_query(()) is False


def test_zero_kb_call_qualifies_announcement_gap() -> None:
    """合成：零 kb 调用 + 缺口声明 → 文案带「未查证」限定。"""

    rewritten = rewrite_unverified_kb_gap_claims(_ANNOUNCEMENT_GAP, ())
    assert "未查证" in rewritten
    assert find_unverified_kb_gap_claims(rewritten, ()) == ()


def test_zero_kb_call_must_not_keep_assertive_absent() -> None:
    """零查证时公开稿不得写成断言性「库无/暂无」。"""

    rewritten = rewrite_unverified_kb_gap_claims(_ABSENT_GAP, ())
    assert "未查证" in rewritten
    assertive = find_unverified_kb_gap_claims(rewritten, ())
    assert assertive == ()
    # 改写后不再以「知识库无/暂无」作断言动词
    assert "知识库无" not in rewritten
    assert "知识库暂无" not in rewritten


def test_kb_called_miss_allows_absent() -> None:
    """有查证未命中 → 允许「库无」。成功路 capability 是 agent_loop。"""

    traces = (_kb_trace(provider="agent:kb_search", capability="agent_loop"),)
    assert kb_gap_claim_kind(traces) == "库无"
    assert traces_include_kb_query(traces) is True
    rewritten = rewrite_unverified_kb_gap_claims(_ABSENT_TEMP, traces)
    assert rewritten == _ABSENT_TEMP
    assert "未查证" not in rewritten


def test_called_uses_provider_not_capability() -> None:
    """按 capability 分组会漏计：provider 才是工具真名。"""

    traces = (_kb_trace(provider="agent:evidence_search", capability="agent_loop"),)
    assert traces_include_kb_query(traces) is True
    assert kb_gap_claim_kind(traces) == "库无"


def test_capability_name_without_kb_provider_is_unverified() -> None:
    """capability=kb_search 但 provider 不是 agent:kb_search → 仍算未查证。"""

    traces = (_kb_trace(provider="eastmoney", capability="kb_search"),)
    assert traces_include_kb_query(traces) is False
    assert kb_gap_claim_kind(traces) == "未查证"
    rewritten = rewrite_unverified_kb_gap_claims(_ANNOUNCEMENT_GAP, traces)
    assert "未查证" in rewritten


def test_public_answer_zero_kb_has_unverified_qualifier() -> None:
    result = _verify(_ANNOUNCEMENT_GAP, ())
    assert "未查证" in result.public_answer
    assert find_unverified_kb_gap_claims(result.public_answer, ()) == ()


def test_public_answer_kb_miss_keeps_absent() -> None:
    traces = (_kb_trace(provider="agent:kb_search", capability="agent_loop"),)
    result = _verify(_ABSENT_TEMP, traces)
    assert "知识库暂无" in result.public_answer
    assert "未查证" not in result.public_answer
