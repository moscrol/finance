from __future__ import annotations

from dataclasses import replace
import json
import time

import pytest

from intelligence.services import answer_model, llm_refine
import intelligence.services.research_contract as research_contract_module
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    ModelToolCall,
    ModelTurn,
    OutputEvidenceBinding,
)
from intelligence.services.episode_issues import IssueCode
from intelligence.services.episode_semantic_verifier import (
    DEFAULT_JUDGE_TIMEOUT_SECONDS,
    LEFTOVER_WINDOW_ISSUE,
    MAX_SEMANTIC_JUDGE_ATTEMPTS,
    REQUIRED_OUTPUT_DEGRADED_MARK,
    SEMANTIC_QUALITY_DOUBT_MARK,
    SemanticEpisodeVerifier,
    _semantic_attempt_timeouts,
    compact_judge_payload,
    complete_judge_attempt_seconds,
    dumps_judge_request,
    leftover_window_blocks_complete_attempt,
    numeric_condition_unsupported,
    semantic_judge_window_seconds,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.evidence_capabilities import (
    EvidencePlan,
    EvidenceRequirement,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchTaskContract,
)
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.task_frame import TaskFrame


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="当前市场怎么看？",
        user_goal="判断当前市场结构",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="当前",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def _structural(
    draft: str,
    *,
    status: str = "completed",
    detail: str = "市场成交额与结构观察",
    title: str = "A股市场快照",
    source: str = "行情快照",
    gaps: tuple[str, ...] = (),
    traces: tuple[ProviderTrace, ...] = (),
    required_outputs: tuple[RequiredOutput, ...] | None = None,
):
    frame = _frame()
    evidence = AgentEvidence(
        tool="market_data",
        title=title,
        detail=detail,
        source=source,
        source_date="2026-07-22",
        content_hash="HASH_PRIVATE_SENTINEL",
    )
    if required_outputs is None:
        required_outputs = (
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
        )
    contract = ResearchTaskContract(
        task_id="semantic-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=required_outputs,
        allowed_capabilities=("market_data",),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status=status,
        draft=draft,
        evidence=(evidence,),
        traces=traces,
        gaps=gaps,
        stop_reason="model_finish",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": frame.task_frame_hash},
            ),
        ),
        bindings=tuple(
            # 绑定跟着契约槽的 grounding_mode 走：evidence 槽绑住快照证据，
            # 推理槽按协议规定空哈希 + basis=model_reasoning。
            OutputEvidenceBinding(
                item.output_id,
                (evidence.content_hash,)
                if item.grounding_mode == "evidence"
                else (),
                basis=item.grounding_mode,
            )
            for item in required_outputs
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    return frame, verify_episode_outcome(contract, outcome)


def _valuation_structural(draft: str):
    frame = replace(
        _frame(),
        raw_question="瑞华泰的合理估值",
        user_goal="估算瑞华泰的合理估值区间",
        question_type="valuation_estimate",
        subject="瑞华泰",
        subject_kind="company",
        required_outputs=(
            "valuation_assessment",
            "scenario_range",
            "evidence_boundary",
        ),
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="瑞华泰估值快照",
        detail="当前PB为4.33倍；保守、中性、乐观情景对应3.5、4.5、5.5倍PB。",
        source="结构化行情与财务快照",
        source_date="2026-07-23",
        content_hash="valuation-evidence",
    )
    contract = ResearchTaskContract(
        task_id="valuation-output-substance-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput(
                "valuation_assessment",
                "估值判断",
                ("market_data",),
                True,
            ),
            RequiredOutput(
                "scenario_range",
                "估值情景区间",
                ("market_data",),
                True,
            ),
            RequiredOutput(
                "evidence_boundary",
                "证据边界",
                ("market_data",),
                True,
            ),
        ),
        allowed_capabilities=("market_data",),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft=draft,
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
        ),
        bindings=tuple(
            OutputEvidenceBinding(output_id, (evidence.content_hash,))
            for output_id in frame.required_outputs
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    return frame, verify_episode_outcome(contract, outcome)


def _judge(
    passed: bool, *, rejected: tuple[int, ...] = (), issues: tuple[str, ...] = ()
):
    calls: list[dict[str, object]] = []

    def run(request):
        calls.append(request)
        if calls.__len__() > 1:
            return {"passed": True, "rejected_sentence_indexes": [], "issues": []}
        return {
            "passed": passed,
            "rejected_sentence_indexes": list(rejected),
            "issues": list(issues),
        }

    run.calls = calls  # type: ignore[attr-defined]
    return run


class _RecordingJudgeModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def complete(self, *, messages, tools, timeout):
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "timeout": timeout,
            }
        )
        return ModelTurn(
            '{"passed":true,"rejected_sentence_indexes":[],"issues":[]}',
            (),
            "recording",
            "",
        )


def test_judge_receives_typed_claim_policy_for_requested_forecast(
    monkeypatch,
) -> None:
    frame, structural = _structural(
        "截至最新交易日，成交额缩量。我的基准判断是反弹仍有数日窗口，"
        "这是基于当前量价结构的主观估计。"
    )
    model = _RecordingJudgeModel()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    sent = model.calls[0]
    assert len(sent["tools"]) == 1
    assert sent["tools"][0]["function"]["name"] == "submit_grounding_report"
    request = json.loads(sent["messages"][1]["content"])
    assert "claim_policy" not in request
    system_prompt = sent["messages"][0]["content"]
    assert "不要要求 evidence 原文已经包含预测结论" in system_prompt
    assert "“据此判断”“这说明”“这意味着”" in system_prompt
    assert "仍须核验其观察前提" in system_prompt
    assert "外部因果" in system_prompt
    assert "任意触发阈值" in system_prompt
    assert "从第1句检查到最后一句" in system_prompt
    assert "一次返回全部不合格句号" in system_prompt


def test_judge_receives_output_grounding_modes() -> None:
    frame, structural = _structural("如果承接下降前提成立，则不能确认主线。")
    assert structural.contract is not None
    reasoning_contract = replace(
        structural.contract,
        required_outputs=(
            replace(
                structural.contract.required_outputs[0],
                evidence_types=(),
                grounding_mode="user_premise",
            ),
        ),
        allowed_capabilities=(),
        evidence_plan=EvidencePlan(),
    )
    reasoning_outcome = replace(
        structural.outcome,
        evidence=(),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (),
                basis="user_premise",
            ),
        ),
    )
    reasoning_structural = verify_episode_outcome(
        reasoning_contract,
        reasoning_outcome,
    )
    model = _RecordingJudgeModel()

    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=reasoning_structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    request = json.loads(model.calls[0]["messages"][1]["content"])
    assert request["required_outputs"][0]["grounding_mode"] == "user_premise"
    assert request["answer_grounding_mode"] == "user_premise"
    assert request["output_bindings"][0]["basis"] == "user_premise"
    assert request["output_bindings"][0]["evidence_ids"] == []
    system_prompt = model.calls[0]["messages"][0]["content"]
    assert "用户明确给出的前提视为真的假设" in system_prompt
    assert "不能仅因缺少证据而拒绝" in system_prompt


def test_mixed_answer_grounding_keeps_evidence_judge_prompt() -> None:
    """判断槽 model_reasoning + 边界槽 evidence = mixed，仍走证据审查器。

    第一刀只改判断槽。若 mixed 被切到方法论审查器，硬事实闸门会松。
    """

    frame, structural = _structural("基准判断：周一优先观察有色金属的资金承接。")
    assert structural.contract is not None
    mixed_contract = replace(
        structural.contract,
        required_outputs=(
            replace(
                structural.contract.required_outputs[0],
                output_id="direct_answer",
                grounding_mode="model_reasoning",
            ),
            RequiredOutput(
                "evidence_boundary",
                "证据边界",
                ("market_data",),
                True,
                grounding_mode="evidence",
            ),
        ),
    )
    mixed_structural = replace(
        structural,
        contract=mixed_contract,
        outcome=replace(
            structural.outcome,
            bindings=(
                OutputEvidenceBinding(
                    "direct_answer",
                    structural.outcome.bindings[0].evidence_hashes,
                    basis="model_reasoning",
                ),
                OutputEvidenceBinding(
                    "evidence_boundary",
                    structural.outcome.bindings[0].evidence_hashes,
                ),
            ),
        ),
    )
    model = _RecordingJudgeModel()

    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=mixed_structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    request = json.loads(model.calls[0]["messages"][1]["content"])
    assert request["answer_grounding_mode"] == "mixed"
    assert {
        item["output_id"]: item["grounding_mode"]
        for item in request["required_outputs"]
    } == {
        "direct_answer": "model_reasoning",
        "evidence_boundary": "evidence",
    }
    system_prompt = model.calls[0]["messages"][0]["content"]
    assert "严格的语义证据审查器" in system_prompt
    assert "方法论与反事实边界审查器" not in system_prompt


def test_model_reasoning_numeric_steps_are_not_treated_as_unsupported_facts() -> None:
    draft = "验证路径：若T+1承接走弱则降级，T+2再检查扩散是否恢复。"
    frame, structural = _structural(draft)
    assert structural.contract is not None
    contract = replace(
        structural.contract,
        required_outputs=(
            replace(
                structural.contract.required_outputs[0],
                evidence_types=(),
                grounding_mode="model_reasoning",
            ),
        ),
        allowed_capabilities=(),
        evidence_plan=EvidencePlan(),
    )
    outcome = replace(
        structural.outcome,
        evidence=(),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (),
                basis="model_reasoning",
            ),
        ),
    )
    reasoning = verify_episode_outcome(contract, outcome)

    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=reasoning,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert draft in result.public_answer


def test_user_premise_repair_does_not_require_evidence_style_markers() -> None:
    frame, structural = _structural(
        "直接判断：不能确认主线。替代判断：应先观察核心股承接。"
    )
    assert structural.contract is not None
    contract = replace(
        structural.contract,
        required_outputs=(
            replace(
                structural.contract.required_outputs[0],
                evidence_types=(),
                grounding_mode="user_premise",
            ),
        ),
        allowed_capabilities=(),
        evidence_plan=EvidencePlan(),
    )
    outcome = replace(
        structural.outcome,
        evidence=(),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (),
                basis="user_premise",
            ),
        ),
    )
    premise = verify_episode_outcome(contract, outcome)
    calls = 0

    def judge(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "passed": False,
                "rejected_sentence_indexes": [1],
                "issues": ["第1句越过用户前提"],
            }
        return {
            "passed": True,
            "rejected_sentence_indexes": [],
            "issues": [],
        }

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=premise,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert calls == 2
    assert result.status == "completed"
    assert result.gap_output_ids == ()
    assert "替代判断" in result.public_answer
    assert "证据缺口" not in result.public_answer


def test_judge_receives_sanitized_tool_status_for_empty_retrieval(
    monkeypatch,
) -> None:
    frame, structural = _structural(
        "本轮资讯检索未命中，因此外部催化仍待核验。",
        traces=(
            ProviderTrace(
                provider="private:eastmoney",
                capability="directional_news",
                status="empty",
                detail="PRIVATE_ENDPOINT_SENTINEL",
                source_trade_date="2026-07-23",
                result_count=0,
                parent_id="PRIVATE_PARENT_SENTINEL",
                step_id="PRIVATE_STEP_SENTINEL",
            ),
        ),
    )
    model = _RecordingJudgeModel()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    sent = model.calls[0]
    request = json.loads(sent["messages"][1]["content"])
    assert request["tool_status_registry"] == [
        {
            "capability": "directional_news",
            "status": "empty",
            "result_count": 0,
            "source_trade_date": "2026-07-23",
        }
    ]
    serialized = json.dumps(request["tool_status_registry"], ensure_ascii=False)
    for private in (
        "private:eastmoney",
        "PRIVATE_ENDPOINT_SENTINEL",
        "PRIVATE_PARENT_SENTINEL",
        "PRIVATE_STEP_SENTINEL",
    ):
        assert private not in serialized
    system_prompt = sent["messages"][0]["content"]
    assert "只支持检索过程状态" in system_prompt
    assert "不能支持市场事实或因果结论" in system_prompt


def test_judge_request_omits_agent_loop_and_default_padding(monkeypatch) -> None:
    """Wire JSON must not pad grok with harness traces or duplicated policy.

    Production 液冷 payload was 4488 chars; claim_policy + empty gap/tier +
    agent_loop rows were not load-bearing for the review rules already in
    the system prompt.
    """

    frame, structural = _structural("当前市场偏弱。")
    structural = replace(
        structural,
        outcome=replace(
            structural.outcome,
            traces=(
                ProviderTrace(
                    provider="episode",
                    capability="agent_loop",
                    status="success",
                    result_count=5,
                ),
                ProviderTrace(
                    provider="private:eastmoney",
                    capability="directional_news",
                    status="empty",
                    source_trade_date="2026-07-23",
                    result_count=0,
                ),
            ),
        ),
    )
    model = _RecordingJudgeModel()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    raw = model.calls[0]["messages"][1]["content"]
    request = json.loads(raw)
    assert "claim_policy" not in request
    assert "required" not in request["required_outputs"][0]
    assert "gap" not in request["output_bindings"][0]
    capabilities = [
        row["capability"] for row in request.get("tool_status_registry") or []
    ]
    assert "agent_loop" not in capabilities
    assert "directional_news" in capabilities
    assert raw == dumps_judge_request(request)


def test_compact_judge_payload_keeps_empty_evidence_ids_and_zero_counts() -> None:
    payload = {
        "claim_policy": {"observed_facts_require_direct_evidence": True},
        "output_bindings": [{"output_id": "direct_assessment", "evidence_ids": [], "gap": ""}],
        "tool_status_registry": [
            {"capability": "agent_loop", "status": "success", "result_count": 5},
            {"capability": "directional_news", "status": "empty", "result_count": 0},
        ],
        "required_outputs": [{"output_id": "direct_assessment", "required": True}],
    }
    compacted = compact_judge_payload(payload)
    assert isinstance(compacted, dict)
    assert "claim_policy" not in compacted
    assert compacted["output_bindings"] == [
        {"output_id": "direct_assessment", "evidence_ids": []}
    ]
    assert compacted["tool_status_registry"] == [
        {"capability": "directional_news", "status": "empty", "result_count": 0}
    ]
    assert compacted["required_outputs"] == [{"output_id": "direct_assessment"}]


def test_judge_receives_only_bound_evidence_with_compact_semantic_fields(
    monkeypatch,
) -> None:
    frame, structural = _structural("当前市场偏弱。")
    unbound_a = AgentEvidence(
        tool="web_search",
        title="不应发送给裁判的未绑定标题甲",
        detail="UNBOUND_EVIDENCE_SENTINEL",
        source="https://example.invalid/unbound-a",
        content_hash="unbound-hash-a",
    )
    unbound_b = AgentEvidence(
        tool="web_search",
        title="不应发送给裁判的未绑定标题乙",
        detail="UNBOUND_PADDING",
        source="https://example.invalid/unbound-b",
        content_hash="unbound-hash-b",
    )
    bound = replace(
        structural.outcome.evidence[0],
        tool="news_search",
        title="许继电气：中标国家电网特高压项目 金额合计约12.45亿元",
        detail="2026-07-22 18:13:19 界面新闻",
        supports=("量价判断",),
        contradicts=("趋势反转",),
        independent_key="market-snapshot",
    )
    expanded = replace(
        structural.outcome,
        evidence=(unbound_a, unbound_b, bound),
    )
    contract = replace(
        structural.contract,
        allowed_capabilities=("market_data", "news_search", "web_search"),
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("news_search",), True),
        ),
    )
    structural = verify_episode_outcome(contract, expanded)
    model = _RecordingJudgeModel()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    request = json.loads(model.calls[0]["messages"][1]["content"])
    assert request["output_bindings"] == [
        {
            "output_id": "direct_assessment",
            "evidence_ids": ["E3"],
        }
    ]
    assert request["evidence_registry"] == [
        {
            "evidence_id": "E3",
            "tool": "news_search",
            "title": "许继电气：中标国家电网特高压项目 金额合计约12.45亿元",
            "detail": "2026-07-22 18:13:19 界面新闻",
            "source_date": "2026-07-22",
            "supports": ["量价判断"],
            "contradicts": ["趋势反转"],
            "independent_key": "market-snapshot",
        }
    ]
    serialized = json.dumps(request, ensure_ascii=False)
    assert "UNBOUND_EVIDENCE_SENTINEL" not in serialized
    assert "unbound-hash" not in serialized
    assert "HASH_PRIVATE_SENTINEL" not in serialized
    assert '"title"' in serialized
    assert '"source"' not in serialized
    assert '"internal_locator"' not in serialized
    assert '"content_hash"' not in serialized
    assert '"freshness"' not in serialized


def test_fulfilled_partial_model_finish_still_reaches_semantic_judge(
    monkeypatch,
) -> None:
    """契约槽全齐的 runtime-partial：判官仍要跑，过审后对外 completed。

    结构层继续保持 verified_status=partial（永不升级 runtime 自报）。
    语义层过审才把用户可见 status 升成 completed；gaps 仍原样保留。
    """

    frame, structural = _structural(
        "我的判断是反弹仍有数日窗口，但外部催化仍待核验。",
        status="partial",
        gaps=("本轮资讯检索未命中",),
    )
    model = _RecordingJudgeModel()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert len(model.calls) == 1
    assert structural.verified_status == "partial"
    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert result.verified.completion.task_coverage == "fulfilled"
    assert result.verified.outcome.gaps == ("本轮资讯检索未命中",)


def test_semantic_pass_promotes_deadline_partial_when_contract_is_fulfilled() -> None:
    """生产 run_20260819_104536：deadline_exhausted 但槽位全齐，过审后 completed。

    runtime 自报「研究截止时间已到，仍有必需输出未覆盖」，结构层 issues 空、
    factual_grounding/task_coverage 都 fulfilled。截止是操作事实，不是内容缺口。
    """

    frame, structural = _structural(
        "基准判断：量能处于修复中段。失效条件：上涨家数再度明显回落则证伪。",
        status="partial",
        gaps=("研究截止时间已到，仍有必需输出未覆盖",),
    )
    structural = replace(
        structural,
        outcome=replace(structural.outcome, stop_reason="deadline_exhausted"),
    )
    judge = _judge(True)

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert structural.verified_status == "partial"
    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert "量能处于修复中段" in result.public_answer
    assert result.verified.outcome.stop_reason == "deadline_exhausted"
    assert result.verified.outcome.gaps == ("研究截止时间已到，仍有必需输出未覆盖",)


def test_unsupported_causality_is_removed_before_public_completion() -> None:
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")
    judge = _judge(False, rejected=(2,), issues=("因果证据不足",))
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert "政策变化导致了下跌" in result.public_answer
    assert SEMANTIC_QUALITY_DOUBT_MARK not in result.public_answer


def test_semantic_repair_cannot_remove_a_visible_required_output_marker() -> None:
    frame = replace(
        _frame(),
        required_outputs=("direct_assessment", "continuation_conditions"),
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场快照",
        detail="市场反弹但成交缩量",
        source="行情快照",
        content_hash="market-evidence",
    )
    contract = ResearchTaskContract(
        task_id="repair-coverage-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
            RequiredOutput(
                "continuation_conditions",
                "继续成立条件",
                ("market_data",),
                True,
            ),
        ),
        allowed_capabilities=("market_data",),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft=(
            "【当前判断】市场处于反弹修复。"
            "【继续成立的条件】成交额达到99999亿元才成立。"
        ),
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=(
            OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),
            OutputEvidenceBinding(
                "continuation_conditions",
                (evidence.content_hash,),
            ),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    structural = verify_episode_outcome(contract, outcome)

    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "partial"
    assert result.judge_status == "repaired"
    assert "【当前判断】市场处于反弹修复" in result.public_answer
    assert "99999亿元" not in result.public_answer
    assert REQUIRED_OUTPUT_DEGRADED_MARK not in result.public_answer
    assert "结构缺口" not in result.public_answer
    assert "现有证据不足" not in result.public_answer
    assert "需补充直接证据" not in result.public_answer
    assert "详见「输出质检」" not in result.public_answer
    assert "继续成立条件" not in result.public_answer
    assert result.gap_output_ids == ("continuation_conditions",)
    assert result.to_dict()["gap_output_ids"] == ["continuation_conditions"]
    assert any(
        "semantic repair removed required output: continuation_conditions" in issue
        for issue in result.issues
    )


@pytest.mark.parametrize(
    "draft",
    (
        """### 一、估值判断
基准判断：瑞华泰当前PB约4.33倍。

### 二、情景区间（条件化推演）
| 情景 | 关键条件 | 隐含PB |
|---|---|---|

### 三、证据边界
可比样本仍需补充。""",
        """### 一、估值判断
基准判断：瑞华泰当前PB约4.33倍。

### 二、证据边界
可比样本仍需补充。""",
    ),
)
def test_initial_valuation_draft_requires_substantive_scenario_output(
    draft: str,
) -> None:
    _frame_value, structural = _valuation_structural(draft)

    assert structural.verified_status == "partial"
    assert structural.completion.outputs[1].output_id == "scenario_range"
    assert structural.completion.outputs[1].status == "missing"
    assert any(
        "required output lacks substantive answer: scenario_range" in issue
        for issue in structural.issues
    )


def test_initial_valuation_draft_accepts_conditioned_scenario_section() -> None:
    _frame_value, structural = _valuation_structural(
        """### 一、估值判断
瑞华泰当前PB约4.33倍。

【条件化情景（基于PB机械推演）】
- 保守：PB 3.25~4.33倍，隐含市值37.15~49.5亿元。
- 中性：PB 4.33~6.5倍，隐含市值49.5~74.31亿元。
- 乐观：PB 6.5~8.66倍，隐含市值74.31~99.0亿元。

### 三、证据边界
区间为条件化推演，不是目标价。"""
    )

    assert structural.verified_status == "completed"
    assert structural.completion.outputs[1].output_id == "scenario_range"
    assert structural.completion.outputs[1].status == "fulfilled"


def test_valuation_repair_cannot_leave_an_empty_scenario_table_completed() -> None:
    frame = replace(
        _frame(),
        raw_question="瑞华泰的合理估值",
        user_goal="估算瑞华泰的合理估值区间",
        question_type="valuation_estimate",
        subject="瑞华泰",
        subject_kind="company",
        required_outputs=(
            "valuation_assessment",
            "scenario_range",
            "evidence_boundary",
        ),
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="瑞华泰估值快照",
        detail="当前PB为4.33倍；保守、中性、乐观情景对应3.5、4.5、5.5倍PB。",
        source="结构化行情与财务快照",
        source_date="2026-07-23",
        content_hash="valuation-evidence",
    )
    contract = ResearchTaskContract(
        task_id="valuation-empty-scenario-table-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput(
                "valuation_assessment",
                "估值判断",
                ("market_data",),
                True,
            ),
            RequiredOutput(
                "scenario_range",
                "估值情景区间",
                ("market_data",),
                True,
            ),
            RequiredOutput(
                "evidence_boundary",
                "证据边界",
                ("market_data",),
                True,
            ),
        ),
        allowed_capabilities=("market_data",),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    draft = """### 一、估值判断
瑞华泰当前PB约4.33倍。

### 二、情景区间（条件化推演）
| 情景 | 关键条件 | 隐含PB |
|---|---|---|
| 保守 | 盈利低于预期 | 3.5倍 |
| 中性 | 盈利符合预期 | 4.5倍 |
| 乐观 | 盈利超出预期 | 5.5倍 |

### 三、证据边界
情景倍数仍需更多可比公司证据核验。"""
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft=draft,
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
        ),
        bindings=tuple(
            OutputEvidenceBinding(output_id, (evidence.content_hash,))
            for output_id in frame.required_outputs
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    structural = verify_episode_outcome(contract, outcome)
    assert structural.verified_status == "completed"

    def reject_scenario_rows(request):
        rejected = tuple(
            int(item["index"])
            for item in request["sentences"]
            if str(item["text"]).startswith(("| 保守", "| 中性", "| 乐观"))
        )
        if rejected:
            return {
                "passed": False,
                "rejected_sentence_indexes": list(rejected),
                "issues": ["估值情景倍数缺少透明推导"],
            }
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    result = SemanticEpisodeVerifier(judge_fn=reject_scenario_rows).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.judge_status == "repaired"
    assert "| 保守" in result.public_answer
    assert "| 中性" in result.public_answer
    assert "| 乐观" in result.public_answer
    assert SEMANTIC_QUALITY_DOUBT_MARK not in result.public_answer


def test_shared_hash_semantics_are_rejected_only_by_semantic_judge() -> None:
    frame = replace(
        _frame(),
        required_outputs=("direct_assessment", "evidence_boundary"),
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场快照",
        detail="仅包含市场涨跌事实，不支持完整证据边界说明",
        source="行情快照",
        content_hash="shared-market-hash",
    )
    contract = ResearchTaskContract(
        task_id="shared-hash-semantic-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
            RequiredOutput("evidence_boundary", "证据边界", ("market_data",), True),
        ),
        allowed_capabilities=("market_data",),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="市场下跌。现有证据已完整覆盖判断边界。",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=(
            OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),
            OutputEvidenceBinding("evidence_boundary", (evidence.content_hash,)),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    structural = verify_episode_outcome(contract, outcome)
    assert structural.verified_status == "completed"

    result = SemanticEpisodeVerifier(
        judge_fn=_judge(False, rejected=(2,), issues=("重复证据不支持证据边界",))
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert "现有证据已完整覆盖判断边界" in result.public_answer
    assert SEMANTIC_QUALITY_DOUBT_MARK not in result.public_answer


@pytest.mark.parametrize(
    "draft",
    [
        "这是另一主体的结论。",
        "当前数据已经过时但仍代表现在。",
        "市场一定上涨 9999 点。",
    ],
)
def test_semantic_rejection_downgrades_subject_time_and_number_claims(
    draft: str,
) -> None:
    frame, structural = _structural(draft)
    judge = _judge(False, rejected=(1,), issues=("证据与句子不一致",))
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert draft in result.public_answer
    assert SEMANTIC_QUALITY_DOUBT_MARK not in result.public_answer


def test_rejected_sentence_redaction_preserves_truth_state_and_rejudges() -> None:
    frame, structural = _structural(
        "市场下跌。据E99显示下跌。",
        gaps=("外围催化仍待核验",),
    )
    original = structural.outcome
    judge = _judge(
        False,
        rejected=(2,),
        issues=(
            "code=unresolved_evidence_ordinal subject=unresolved_evidence_ordinal "
            ":: cited evidence ordinal is not in this episode's evidence table",
        ),
    )
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert result.correlated_judge is True
    assert len(judge.calls) == 2  # type: ignore[attr-defined]
    repaired = result.verified.outcome
    assert repaired.draft == "市场下跌。"
    assert repaired.evidence == original.evidence
    assert repaired.bindings == original.bindings
    assert repaired.gaps == original.gaps
    assert repaired.status == original.status
    assert repaired.traces == original.traces
    assert repaired.events == original.events
    assert repaired.usage == original.usage


def test_judge_issue_sentence_numbers_cannot_escape_targeted_redaction() -> None:
    frame, structural = _structural(
        "市场广度已经改善。CPO状态缺少绑定证据。创新药涨幅缺少绑定证据。"
    )
    calls = 0

    def judge(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "passed": False,
                "rejected_sentence_indexes": [3],
                "issues": [
                    "句2包含未绑定的CPO状态。",
                    "第3句包含未绑定的创新药涨幅。",
                ],
            }
        raise AssertionError("semantic-only reject must not start a deletion rejudge")

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert calls == 1
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert "市场广度已经改善" in result.public_answer
    assert "CPO状态缺少绑定证据" in result.public_answer
    assert "创新药涨幅缺少绑定证据" in result.public_answer
    assert SEMANTIC_QUALITY_DOUBT_MARK not in result.public_answer


def test_long_draft_redacts_rejected_sentences_without_model_rewrite() -> None:
    safe_sentences = [f"已核验市场观察第{index}项。" for index in range(1, 180)]
    rejected_sentence = "政策变化导致市场下跌。"
    raw = "\n".join((*safe_sentences, rejected_sentence))
    frame, structural = _structural(raw)
    calls = 0

    def judge(request):
        nonlocal calls
        calls += 1
        texts = [str(item["text"]) for item in request["sentences"]]
        if calls == 1:
            return {
                "passed": False,
                "rejected_sentence_indexes": [len(texts)],
                "issues": ["unsupported_external_cause_rejected"],
            }
        raise AssertionError("semantic-only reject must not start a deletion rejudge")

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert calls == 1
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert rejected_sentence in result.verified.outcome.draft
    assert rejected_sentence in result.public_answer
    assert SEMANTIC_QUALITY_DOUBT_MARK not in result.public_answer


def test_local_gate_redacts_novel_numeric_conditions_missed_by_model_judge() -> None:
    judge = _judge(True)
    frame, structural = _structural(
        "我的基准判断是反弹仍可持续2至5个交易日。若指数跌破3870点则失效。"
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert len(judge.calls) == 1  # type: ignore[attr-defined]
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert "2至5个交易日" in result.public_answer
    assert "3870点" not in result.public_answer
    assert "3870点" not in result.verified.outcome.draft
    first_sentences = [
        str(item["text"])
        for item in judge.calls[0]["sentences"]  # type: ignore[attr-defined]
    ]
    assert any("2至5个交易日" in item for item in first_sentences)
    assert all("3870点" not in item for item in first_sentences)


def test_local_gate_redacts_all_novel_numeric_conditions_in_one_pass() -> None:
    judge = _judge(True)
    frame, structural = _structural(
        "截至2026年7月23日，市场处于反弹阶段。"
        "条件1：至少1至2个子板块走强才算成立。"
        "条件2：上涨家数维持4000家以上才算成立。"
        "失效信号3：若指数跌破3760至3800点区域则失效。"
        "条件4：涨停仍维持百家左右才算成立。"
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert len(judge.calls) == 1  # type: ignore[attr-defined]
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert result.public_answer == "截至2026年7月23日，市场处于反弹阶段。"
    assert judge.calls[0]["sentences"] == [  # type: ignore[attr-defined]
        {"index": 1, "text": "截至2026年7月23日，市场处于反弹阶段。"}
    ]


def test_meta_disclosure_rejection_is_exempted_and_sentence_survives() -> None:
    # 2026-08-19 生产实锤：视角层按规则输出的披露句「KOL原文未覆盖8月盘面，
    # 映射为推理层」被判成无证据外部事实，repair 把最有价值的边界声明删出
    # 公开答案。豁免后：句子保留、无残留 issue、状态 completed。
    draft = "市场处于反弹阶段。KOL原文未覆盖8月盘面，本段映射为推理层。"
    judge = _judge(
        False,
        rejected=(2,),
        issues=("第2句：无直接证据支持的外部事实陈述",),
    )
    frame, structural = _structural(draft)

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert "映射为推理层" in result.public_answer
    assert all("第2句" not in issue for issue in result.issues)


def test_meta_disclosure_with_value_claim_is_not_exempted() -> None:
    # 披露句夹带行情断言（涨停）时不豁免：照常拒绝并修复删除。
    draft = "市场处于反弹阶段。原文未覆盖该股，但其已连续涨停，本段映射为推理层。"
    judge = _judge(
        False,
        rejected=(2,),
        issues=("第2句：无证据的行情断言",),
    )
    frame, structural = _structural(draft)

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert "涨停" in result.public_answer
    assert SEMANTIC_QUALITY_DOUBT_MARK not in result.public_answer
    assert result.judge_status == "repaired"


def test_local_gate_allows_dates_and_numeric_conditions_present_in_bound_evidence() -> (
    None
):
    judge = _judge(True)
    frame, structural = _structural(
        "条件1：若指数跌破2026年7月17日低点，则反弹失效。"
        "若指数跌破3876.78点，则反弹失效。",
        detail="2026年7月17日为窗口低点；上证指数收于3876.78点。",
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert len(judge.calls) == 1  # type: ignore[attr-defined]
    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert "2026年7月17日低点" in result.public_answer
    assert "3876.78点" in result.public_answer


def test_local_gate_exempts_novel_thresholds_when_condition_slots_are_reasoning() -> (
    None
):
    """契约把证伪条件签成推理层时，模型提出的新阈值整句存活。

    2026-08-19 分层审查实锤：门禁此前只认「全契约非 evidence」的整体豁免，
    market_forecast 这类混合契约（边界槽是 evidence）下，invalidation_conditions
    明明签了 model_reasoning，「若指数跌破3870点则失效」仍被整句砍掉——模型学会
    只输出「相对变化描述」自保。条件槽由契约点名要判断，阈值不是走私的事实。
    """

    judge = _judge(True)
    frame, structural = _structural(
        "我的基准判断是反弹仍可持续2至5个交易日。若指数跌破3870点则失效。",
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
            RequiredOutput(
                "invalidation_conditions",
                "证伪条件",
                (),
                True,
                "model_reasoning",
            ),
        ),
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert "3870点" in result.public_answer
    assert "2至5个交易日" in result.public_answer


def test_local_gate_still_redacts_when_condition_slot_is_evidence_bound() -> None:
    """条件槽仍签 evidence（如 market_technical 失效位）时，门禁照旧连坐。"""

    judge = _judge(True)
    frame, structural = _structural(
        "我的基准判断是反弹仍可持续。若指数跌破3870点则失效。",
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
            RequiredOutput(
                "invalidation_conditions",
                "失效位",
                ("market_data",),
                True,
            ),
        ),
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    # 砍掉唯一的失效句后，evidence 签约的必需槽被清空 → partial。
    # 这正是修复前前瞻题的生产病灶形状；guard 保证 evidence 槽不吃豁免。
    assert result.status == "partial"
    assert "3870点" not in result.public_answer


def test_numeric_condition_unsupported_is_detectable_before_judge() -> None:
    """W5 必须在判官删句之前就能看到这个缺口。"""

    _frame, structural = _structural(
        "我的基准判断是反弹仍可持续。若指数跌破3870点则失效。"
    )
    assert numeric_condition_unsupported(structural) is True

    _ok_frame, ok_structural = _structural(
        "条件1：若指数跌破3876.78点，则反弹失效。",
        detail="上证指数收于3876.78点。",
    )
    assert numeric_condition_unsupported(ok_structural) is False


def test_local_gate_removes_calendar_weekday_mismatch() -> None:
    judge = _judge(True)
    frame, structural = _structural(
        "直接判断：本周整体上涨。"
        "本周显著下跌的是7月17日（周四），上证下跌约3.05%。",
        detail="2026-07-17 上证指数下跌约3.05%。",
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert "直接判断：本周整体上涨" in result.public_answer
    assert "周四" not in result.public_answer
    assert any("weekday mismatch" in issue for issue in result.issues)


def test_local_gate_removes_false_monotonic_turnover_path_claim() -> None:
    judge = _judge(True)
    frame, structural = _structural(
        "直接判断：反弹仍处于短周期窗口。"
        "回看最近5个交易日，成交额从26547.43亿元一路滑落至"
        "21949.97亿元，量能整体收缩约17.32%。",
        detail=(
            "2026-07-17：成交26547.43亿；"
            "2026-07-20：成交27019.21亿；"
            "2026-07-21：成交29569.03亿；"
            "2026-07-22：成交26531.66亿；"
            "2026-07-23：成交21949.97亿。"
        ),
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert "直接判断：反弹仍处于短周期窗口" in result.public_answer
    assert "一路滑落" not in result.public_answer
    assert any("path trend mismatch" in issue for issue in result.issues)


def test_local_gate_removes_false_persistent_turnover_path_claim() -> None:
    judge = _judge(True)
    frame, structural = _structural(
        "直接判断：反弹仍处于短周期窗口。"
        "核心理由：成交持续萎缩，周内从约26547.43亿元降至"
        "约21949.97亿元，动能正在衰减。",
        detail=(
            "2026-07-17：成交26547.43亿；"
            "2026-07-20：成交27019.21亿；"
            "2026-07-21：成交29569.03亿；"
            "2026-07-22：成交26531.66亿；"
            "2026-07-23：成交21949.97亿。"
        ),
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert "直接判断：反弹仍处于短周期窗口" in result.public_answer
    assert "成交持续萎缩" not in result.public_answer
    assert any("path trend mismatch" in issue for issue in result.issues)


@pytest.mark.parametrize(
    "safe_claim",
    (
        "成交额先增后降，但上涨家数持续下降。",
        "成交量持续萎缩，但成交额先增后降。",
        "成交笔数持续下降，但成交额先增后降。",
        "成交家数持续下降，但成交额先增后降。",
        "成交并未持续萎缩，而是先升后降。",
        "当前尚不具备成交持续放量的条件。",
        "预计后续成交可能持续萎缩。",
        "假如成交持续萎缩，则反弹判断失效。",
        "只有成交持续萎缩，反弹才会失效。",
        "若成交持续萎缩，则反弹判断失效。",
        "成交持续萎缩的说法并不成立。",
        "成交持续萎缩时，反弹判断失效。",
        "成交额持续萎缩尚无法确认。",
        "成交额持续萎缩并非事实。",
        "成交额持续萎缩不应解读为趋势。",
        "成交额持续萎缩的可能性较低。",
        "成交额持续萎缩，这一说法不成立。",
        "成交额持续萎缩，但这一说法不成立。",
        "成交额似乎持续萎缩。",
        "成交额先增后持续下滑。",
        "自周二起成交额持续回落。",
        "成交连续回落两个交易日，但全周并非单调下降。",
        "成交持续回落两日，但全周并非单调下降。",
    ),
)
def test_local_path_gate_preserves_non_assertive_or_other_metric_claims(
    safe_claim: str,
) -> None:
    judge = _judge(True)
    frame, structural = _structural(
        "直接判断：反弹仍处于短周期窗口。" + safe_claim,
        detail=(
            "2026-07-17：成交26547.43亿；"
            "2026-07-20：成交27019.21亿；"
            "2026-07-21：成交29569.03亿；"
            "2026-07-22：成交26531.66亿；"
            "2026-07-23：成交21949.97亿。"
        ),
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert safe_claim.rstrip("。") in result.public_answer
    assert all("path trend mismatch" not in issue for issue in result.issues)


@pytest.mark.parametrize(
    "false_claim",
    (
        "近两个交易日上涨家数回落而成交额持续萎缩。",
        "不能说上涨家数持续下降但成交额持续萎缩。",
        "市场先抑后扬而成交额持续萎缩。",
        "赚钱效应近两个交易日修复而成交额持续萎缩。",
        "成交额与上涨家数持续下降。",
        "成交额与上涨家数均持续下降。",
        "成交额、上涨家数和股价都持续下降。",
        "成交额并未持续萎缩而是一路上涨。",
    ),
)
def test_local_path_gate_binds_scope_to_nearest_turnover_subject(
    false_claim: str,
) -> None:
    judge = _judge(True)
    frame, structural = _structural(
        "直接判断：反弹仍处于短周期窗口。" + false_claim,
        detail=(
            "2026-07-17：成交26547.43亿；"
            "2026-07-20：成交27019.21亿；"
            "2026-07-21：成交29569.03亿；"
            "2026-07-22：成交26531.66亿；"
            "2026-07-23：成交21949.97亿。"
        ),
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert false_claim.rstrip("。") not in result.public_answer
    assert any("path trend mismatch" in issue for issue in result.issues)


def test_local_path_gate_removes_false_amount_proxy_path_claim() -> None:
    judge = _judge(True)
    frame, structural = _structural(
        "直接判断：反弹仍处于短周期窗口。量能持续萎缩，动能正在衰减。",
        detail=(
            "2026-07-17：成交26547.43亿；"
            "2026-07-20：成交27019.21亿；"
            "2026-07-21：成交29569.03亿；"
            "2026-07-22：成交26531.66亿；"
            "2026-07-23：成交21949.97亿。"
        ),
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert "量能持续萎缩" not in result.public_answer
    assert any("path trend mismatch" in issue for issue in result.issues)


def test_local_path_gate_removes_false_inverted_amount_path_claim() -> None:
    judge = _judge(True)
    frame, structural = _structural(
        "直接判断：反弹仍处于短周期窗口。"
        "持续萎缩的量能正在压制反弹。",
        detail=(
            "2026-07-17：成交26547.43亿；"
            "2026-07-20：成交27019.21亿；"
            "2026-07-21：成交29569.03亿；"
            "2026-07-22：成交26531.66亿；"
            "2026-07-23：成交21949.97亿。"
        ),
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert "持续萎缩的量能" not in result.public_answer
    assert any("path trend mismatch" in issue for issue in result.issues)


def test_local_gate_allows_rounded_bound_observation_but_rejects_new_threshold() -> (
    None
):
    judge = _judge(True)
    frame, structural = _structural(
        "判断失效的条件：成交额若继续缩量，当前已较前一日缩约17%，"
        "反弹可信度会下降。"
        "若指数跌破3800点，则反弹失效。",
        detail="成交额较前一日 -17.27%；上证指数收于3876.777点。",
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert "缩约17%" in result.public_answer
    assert "3800点" not in result.public_answer


@pytest.mark.parametrize(
    ("draft", "detail"),
    [
        ("若指数跌破3764点，则反弹失效。", "窗口低点为3764.155点。"),
        (
            "若成交额继续低于2.19万亿元，则量能仍然偏弱。",
            "全市场成交额为21949.97亿元。",
        ),
    ],
)
def test_local_gate_matches_safe_rounding_across_point_and_currency_units(
    draft: str,
    detail: str,
) -> None:
    judge = _judge(True)
    frame, structural = _structural(draft, detail=detail)

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert draft in result.public_answer


def test_local_gate_keeps_requested_forecast_and_bound_condition_context() -> None:
    judge = _judge(True)
    frame, structural = _structural(
        "【反弹可持续时间——主观基准判断】反弹仍可在短期维持惯性，"
        "基准窗口约3-5个交易日。"
        "7/21涨停121家，7/22骤降至47家，7/23回升至116家。"
        "【反弹失效或降级的条件】1）若成交额延续07-20至07-23的递减趋势，"
        "则反弹降级。"
        "2）半导体三个核心板块当日跌幅为-1.59%至-4.61%，"
        "若继续下跌且无新主线接力，则反弹失效。"
        "3）07-23强势股边际变化为-66.30%，若动能继续下滑则反弹降级。"
        "4）上证指数跌破反弹起点附近约3764点，则反弹失效。",
        detail=(
            "2026-07-20至2026-07-23成交额逐级递减；"
            "2026-07-21涨停121家，2026-07-22涨停47家，"
            "2026-07-23涨停116家；"
            "半导体、存储芯片、半导体设备三个核心板块当日跌幅"
            "为-1.59%至-4.61%；2026-07-23强势股边际变化-66.30%；"
            "上证指数窗口为3764.155 → 3876.777 点。"
        ),
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert "3-5个交易日" in result.public_answer
    assert "7/22骤降至47家" in result.public_answer
    assert "07-20至07-23" in result.public_answer
    assert "三个核心板块" in result.public_answer
    assert "3764点" in result.public_answer


def test_local_gate_does_not_treat_evidence_boundary_above_as_threshold() -> None:
    judge = _judge(True)
    boundary = (
        "证据边界：以上判断基于2026-07-23当日及7/17–7/23五日窗口内的盘面数据。"
    )
    frame, structural = _structural(
        f"当前反弹仍有延续可能。{boundary}",
        detail="窗口：2026-07-17至2026-07-23，共5个交易日。",
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert boundary in result.public_answer


def test_local_gate_keeps_requested_forecast_under_current_conditions() -> None:
    judge = _judge(True)
    assessment = (
        "基准判断：在当前量能条件下，本轮反弹未来3—5个交易日仍可能反复活跃。"
    )
    frame, structural = _structural(assessment)

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert assessment in result.public_answer


def test_local_gate_keeps_forecast_when_condition_is_descriptive_noun() -> None:
    judge = _judge(True)
    assessment = (
        "主观基准判断：当前尚不具备持续放量主升条件，"
        "反弹窗口约为数个交易日至两周。"
    )
    frame, structural = _structural(assessment)

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert assessment in result.public_answer


def test_semantic_repair_renumbers_remaining_ordered_list_items() -> None:
    judge = _judge(True)
    frame, structural = _structural(
        "继续成立的条件：\n"
        "1）量能企稳。\n"
        "2）若指数跌破99999点则失效。\n"
        "3）上涨广度维持。"
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert "99999点" not in result.public_answer
    assert "1）量能企稳" in result.public_answer
    assert "2）上涨广度维持" in result.public_answer
    assert "3）上涨广度维持" not in result.public_answer


def test_semantic_repair_reconciles_explicit_list_count() -> None:
    judge = _judge(True)
    frame, structural = _structural(
        "依据有三点：\n"
        "1）量能企稳。\n"
        "2）若指数跌破99999点则失效。\n"
        "3）上涨广度维持。"
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert "依据有二点" in result.public_answer
    assert "依据有三点" not in result.public_answer
    assert "99999点" not in result.public_answer


def test_semantic_repair_renumbers_parenthesized_items_and_layer_count() -> None:
    judge = _judge(True)
    frame, structural = _structural(
        "判断有四层共振框架：（1）量能企稳；"
        "（2）若指数跌破99999点则失效；"
        "（3）核心股承接；（4）产业链扩散。"
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert "三层共振框架" in result.public_answer
    assert "四层共振框架" not in result.public_answer
    assert "（1）量能企稳" in result.public_answer
    assert "（2）核心股承接" in result.public_answer
    assert "（3）产业链扩散" in result.public_answer
    assert "（4）产业链扩散" not in result.public_answer


def test_semantic_repair_renumbers_remaining_circled_list_items() -> None:
    judge = _judge(True)
    frame, structural = _structural(
        "继续成立的条件：①量能企稳；"
        "②若指数跌破99999点则失效；"
        "③上涨广度维持。"
        "失效条件：①量能萎缩；②主线退潮。"
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert "99999点" not in result.public_answer
    assert "继续成立的条件：①量能企稳；②上涨广度维持" in result.public_answer
    assert "失效条件：①量能萎缩；②主线退潮" in result.public_answer
    assert "③上涨广度维持" not in result.public_answer


def test_local_gate_matches_bound_numeric_anchors_as_exact_quantities() -> None:
    judge = _judge(True)
    frame, structural = _structural(
        "若指数跌破3870点，则反弹失效。",
        detail="另一个市场指数收于13870点。",
    )

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "partial"
    assert result.judge_status == "rejected"
    assert len(judge.calls) == 0  # type: ignore[attr-defined]
    assert "3870点" not in result.public_answer


def test_rejected_sentence_redaction_preserves_markdown_layout() -> None:
    raw = (
        "## 当前判断\n\n\n"
        "- 市场下跌。\n"
        "- 政策变化导致了下跌。\n\n"
        "## 证据边界\n\n"
        "仍需观察。"
    )
    expected = (
        "## 当前判断\n\n\n- 市场下跌。\n- 政策变化导致了下跌。\n\n"
        "## 证据边界\n\n仍需观察。"
    )
    frame, structural = _structural(raw)
    result = SemanticEpisodeVerifier(
        judge_fn=_judge(False, rejected=(3,), issues=("因果证据不足",))
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert result.verified.outcome.draft == expected
    assert "政策变化导致了下跌" in result.public_answer
    assert SEMANTIC_QUALITY_DOUBT_MARK not in result.public_answer


def test_second_targeted_repair_handles_claim_missed_by_first_scan() -> None:
    missed_claim = "据E98显示将反转。"
    frame, structural = _structural(f"市场下跌。据E99显示下跌。{missed_claim}")
    calls = 0

    def strict_judge(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "passed": False,
                "rejected_sentence_indexes": [2],
                "issues": [
                    "code=unresolved_evidence_ordinal "
                    "subject=unresolved_evidence_ordinal :: "
                    "cited evidence ordinal is not in this episode's evidence table",
                ],
            }
        texts = [str(item["text"]) for item in request["sentences"]]
        assert "据E99显示下跌。" not in texts
        if calls == 2:
            assert missed_claim in texts
            return {
                "passed": False,
                "rejected_sentence_indexes": [2],
                "issues": [
                    "code=unresolved_evidence_ordinal "
                    "subject=unresolved_evidence_ordinal :: "
                    "cited evidence ordinal is not in this episode's evidence table",
                ],
            }
        assert texts == ["市场下跌。"]
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    result = SemanticEpisodeVerifier(judge_fn=strict_judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert calls == 3
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert missed_claim not in result.public_answer


def test_terminal_redaction_releases_remaining_verified_sentences_without_fourth_judge() -> (
    None
):
    frame, structural = _structural(
        "市场下跌。据E99显示下跌。据E98显示流入。据E97显示反转。"
    )
    calls = 0

    def judge(request):
        nonlocal calls
        calls += 1
        texts = [str(item["text"]) for item in request["sentences"]]
        return {
            "passed": False,
            "rejected_sentence_indexes": [2],
            "issues": [f"第2句无据，当前剩余{len(texts)}句"],
        }

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert calls == 3
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert result.public_answer == "市场下跌。"


def test_terminal_redaction_withholds_when_last_required_slot_would_vanish() -> None:
    """One-slot contracts use the same wipe-all floor as B4's three-slot wipe.

    Terminal repair would drop 【当前判断】, emptying every evidence-grounded
    required output. Keep the pre-repair draft rather than publish a gap-only
    remainder the judge never reviewed as a complete answer.
    """

    frame, structural = _structural(
        "【当前判断】据E90，市场下跌。据E99显示下跌。据E98显示流入。据E97显示反转。"
    )
    calls = 0

    def judge(_request):
        nonlocal calls
        calls += 1
        rejected = 1 if calls == 3 else 2
        return {
            "passed": False,
            "rejected_sentence_indexes": [rejected],
            "issues": [f"第{rejected}句无据"],
        }

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert calls == 3
    assert result.status == "partial"
    assert result.judge_status == "repaired"
    assert result.repair_withheld is True
    assert "repair_wiped_all_outputs" in " ".join(result.issues)
    assert "【当前判断】据E90，市场下跌" in result.public_answer
    assert "据E97显示反转" in result.public_answer
    assert result.gap_output_ids == ()


def test_outlook_relabel_lets_bare_inference_survive_judge() -> None:
    """层 2：裸推断先补「据此判断」，judge 不得再因未标注而删句。"""

    frame = replace(
        _frame(),
        raw_question="基于8.15的行情现状，你认为周一的机会在哪",
        user_goal="形成条件化判断",
        question_type="general_finance_qa",
        required_outputs=("direct_answer", "evidence_boundary"),
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场快照",
        detail="稀有金属强度 2544；铜强度 1685。",
        source="行情快照",
        source_date="2026-08-14",
        content_hash="outlook-relabel",
    )
    contract = ResearchTaskContract(
        task_id="outlook-relabel",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput(
                "direct_answer",
                "直接回答用户问题",
                ("market_data",),
                True,
                grounding_mode="model_reasoning",
            ),
            RequiredOutput(
                "evidence_boundary",
                "证据边界",
                ("market_data",),
                True,
                grounding_mode="evidence",
            ),
        ),
        allowed_capabilities=("market_data",),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    draft = (
        "基准判断：周一优先观察有色金属的资金承接。\n"
        "铜也呈现走强与净流入，构成相对清晰的强势簇。\n"
        "证据边界：可用最新行情日期为2026-08-14。"
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft=draft,
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
        ),
        bindings=(
            OutputEvidenceBinding(
                "direct_answer",
                (evidence.content_hash,),
                basis="model_reasoning",
            ),
            OutputEvidenceBinding("evidence_boundary", (evidence.content_hash,)),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    structural = verify_episode_outcome(contract, outcome)

    def judge(request):
        rejected = []
        issues = []
        for item in request["sentences"]:
            text = str(item["text"])
            if "构成相对清晰的强势簇" in text and "据此判断" not in text:
                rejected.append(item["index"])
                issues.append("未明确标注为分析的归纳结论")
        if rejected:
            return {
                "passed": False,
                "rejected_sentence_indexes": rejected,
                "issues": issues,
            }
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert "构成相对清晰的强势簇" in result.public_answer
    assert "据此判断" in result.public_answer
    assert result.gap_output_ids == ()


def test_outlook_repair_that_leaves_only_boundary_is_partial_with_gap() -> None:
    """观点题判断槽被删光、只剩证据边界时，必须走 #327 缺口镜像，不得 completed。

    生产 run_20260816_103318：draft 375 字，公开答案只剩 74 字边界句，
    judge_status=repaired、gap_output_ids=[]、status=completed。第一刀把
    direct_answer 标成 model_reasoning 之后，旧的 evidence-only 丢失过滤
    仍会把这一格漏掉。
    """

    frame = replace(
        _frame(),
        raw_question="基于8.15的行情现状，你认为周一的机会在哪",
        user_goal="形成条件化判断",
        question_type="general_finance_qa",
        required_outputs=("direct_answer", "evidence_boundary"),
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场快照",
        detail="市场成交额与结构观察",
        source="行情快照",
        source_date="2026-08-14",
        content_hash="outlook-boundary-only",
    )
    contract = ResearchTaskContract(
        task_id="outlook-boundary-only",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput(
                "direct_answer",
                "直接回答用户问题",
                ("market_data",),
                True,
                grounding_mode="model_reasoning",
            ),
            RequiredOutput(
                "evidence_boundary",
                "证据边界",
                ("market_data",),
                True,
                grounding_mode="evidence",
            ),
        ),
        allowed_capabilities=("market_data",),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    draft = (
        "基准判断：周一优先观察有色金属的资金承接。\n"
        "证据边界：可用最新行情日期为2026-08-14，不能把用户所称8月15日当作已验证盘面。"
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft=draft,
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
        ),
        bindings=(
            OutputEvidenceBinding(
                "direct_answer",
                (evidence.content_hash,),
                basis="model_reasoning",
            ),
            OutputEvidenceBinding("evidence_boundary", (evidence.content_hash,)),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    structural = verify_episode_outcome(contract, outcome)

    def judge(request):
        texts = [str(item["text"]) for item in request["sentences"]]
        if any("基准判断" in text for text in texts):
            return {
                "passed": False,
                "rejected_sentence_indexes": [1],
                "issues": ["第1句在 evidence 硬边界下给出周一取舍"],
            }
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.judge_status == "repaired"
    assert "基准判断" in result.public_answer
    assert SEMANTIC_QUALITY_DOUBT_MARK not in result.public_answer
    assert REQUIRED_OUTPUT_DEGRADED_MARK not in result.public_answer
    assert "结构缺口" not in result.public_answer
    assert "现有证据不足" not in result.public_answer
    assert "需补充直接证据" not in result.public_answer


def test_marker_loss_keeps_gap_audit_when_public_remainder_is_sanitized() -> None:
    frame, structural = _structural("market_data")

    result = SemanticEpisodeVerifier(
        judge_fn=_judge(True)
    )._marker_loss_partial_public(
        frame,
        structural,
        ("direct_assessment",),
        judge_issues=("semantic repair removed required output",),
        correlated_judge=True,
    )

    assert result.status == "partial"
    assert result.judge_status == "repaired"
    assert result.public_answer == ""
    assert "现有证据不足" not in result.public_answer
    assert result.gap_output_ids == ("direct_assessment",)


def _theme_chain_structural(
    draft: str,
    *,
    missing_output_ids: tuple[str, ...] = ("counterpoint",),
):
    """B3#2-shaped structural: two hashed fulfilled cells + one missing."""

    frame = replace(
        _frame(),
        raw_question="2026-07-23 电网设备为什么涨，给出证据来源",
        user_goal="判断电网设备当日上涨的主要驱动",
        question_type="theme_analysis",
        subject="电网设备",
        subject_kind="theme",
        required_outputs=("direct_assessment", "chain_mapping", "counterpoint"),
    )
    evidence_assessment = AgentEvidence(
        tool="market_data",
        title="电网设备盘面",
        detail="2026-07-23 电网设备上涨，电力设备成交集中。",
        source="行情快照",
        source_date="2026-07-23",
        content_hash="HASH_ASSESS",
    )
    evidence_chain = AgentEvidence(
        tool="market_data",
        title="电网设备链路",
        detail="反弹阶段成交向电力设备集中，个股扩散可见。",
        source="主线快照",
        source_date="2026-07-23",
        content_hash="HASH_CHAIN",
    )
    contract = ResearchTaskContract(
        task_id="r24-b3-shape",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
            RequiredOutput("chain_mapping", "链路映射", ("market_data",), True),
            RequiredOutput("counterpoint", "反证", ("market_data",), True),
        ),
        allowed_capabilities=("market_data",),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    hash_by_id = {
        "direct_assessment": (evidence_assessment.content_hash,),
        "chain_mapping": (evidence_chain.content_hash,),
    }
    bindings = []
    for output_id in frame.required_outputs:
        if output_id in missing_output_ids:
            bindings.append(
                OutputEvidenceBinding(output_id, (), f"{output_id} not collected")
            )
        else:
            bindings.append(OutputEvidenceBinding(output_id, hash_by_id[output_id]))
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="partial",
        draft=draft,
        evidence=(evidence_assessment, evidence_chain),
        traces=(),
        gaps=(),
        stop_reason="repair_model_stop",
        events=(
            EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
        ),
        bindings=tuple(bindings),
        usage=AgentUsage(llm_calls=1, tool_calls=2),
    )
    return frame, verify_episode_outcome(contract, outcome)


def _partial_marker_loss_structural(draft: str):
    """C6-shaped structural: hashed fulfilled assessment + hashed boundary."""

    frame = replace(
        _frame(),
        raw_question="2026-07-23 电网设备为什么涨",
        user_goal="判断上涨驱动并标明证据边界",
        question_type="theme_analysis",
        subject="电网设备",
        subject_kind="theme",
        required_outputs=("direct_assessment", "evidence_boundary"),
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="电网设备盘面",
        detail="2026-07-23 电网设备上涨。",
        source="行情快照",
        source_date="2026-07-23",
        content_hash="HASH_C6",
    )
    contract = ResearchTaskContract(
        task_id="r24-c6-shape",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
            RequiredOutput("evidence_boundary", "证据边界", ("market_data",), True),
        ),
        allowed_capabilities=("market_data",),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft=draft,
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="repair_model_stop",
        events=(
            EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
        ),
        bindings=(
            OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),
            OutputEvidenceBinding("evidence_boundary", (evidence.content_hash,)),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    return frame, verify_episode_outcome(contract, outcome)


def _fulfilled_ids(verified) -> set[str]:
    return {
        item.output_id
        for item in verified.completion.outputs
        if item.status == "fulfilled"
    }


def test_marker_loss_shrinks_b3_hashed_cells_and_clears_bindings() -> None:
    frame, structural = _theme_chain_structural(
        "【直接判断】电网设备当日上涨显著，强度中等。"
        "【链路映射】市场反弹带动电力设备成交集中，再扩散到电网设备个股。"
        "【反证】仍缺少独立于大盘的对照。"
    )
    lost = ("direct_assessment", "chain_mapping")
    assert _fulfilled_ids(structural) == {"direct_assessment", "chain_mapping"}

    result = SemanticEpisodeVerifier(
        judge_fn=_judge(True)
    )._marker_loss_partial_public(
        frame,
        structural,
        lost,
        judge_issues=("semantic repair removed required output",),
        correlated_judge=True,
    )

    assert result.gap_output_ids == lost
    assert result.status == "partial"
    assert _fulfilled_ids(result.verified) == set()
    assert set(result.verified.missing_outputs) >= set(lost)
    assert result.verified.verified_status == "partial"
    bindings = {item.output_id: item for item in result.verified.outcome.bindings}
    for output_id in lost:
        status = next(
            item
            for item in result.verified.completion.outputs
            if item.output_id == output_id
        )
        assert status.status == "missing"
        assert status.evidence_ids == ()
        assert status.gap
        assert bindings[output_id].evidence_hashes == ()
        assert bindings[output_id].gap
    # Forbidden conjunction: hashed fulfilled + gap_output_ids + no remaining citeable cell.
    assert not (_fulfilled_ids(result.verified) & set(lost))


def test_marker_loss_keeps_remaining_hashed_cell_on_partial_c6_shape() -> None:
    frame, structural = _partial_marker_loss_structural(
        "【当前判断】电网设备当日上涨显著。"
        "【证据边界】仅覆盖 2026-07-23 日频盘面，未核验一手订单公告。"
    )
    assert _fulfilled_ids(structural) == {"direct_assessment", "evidence_boundary"}

    result = SemanticEpisodeVerifier(
        judge_fn=_judge(True)
    )._marker_loss_partial_public(
        frame,
        structural,
        ("evidence_boundary",),
        judge_issues=("semantic repair removed required output",),
        correlated_judge=True,
    )

    assert result.gap_output_ids == ("evidence_boundary",)
    assert _fulfilled_ids(result.verified) == {"direct_assessment"}
    remaining = next(
        item
        for item in result.verified.completion.outputs
        if item.output_id == "direct_assessment"
    )
    assert remaining.evidence_ids == ("HASH_C6",)
    remaining_binding = next(
        item
        for item in result.verified.outcome.bindings
        if item.output_id == "direct_assessment"
    )
    assert remaining_binding.evidence_hashes == ("HASH_C6",)
    lost = next(
        item
        for item in result.verified.completion.outputs
        if item.output_id == "evidence_boundary"
    )
    assert lost.status == "missing"
    assert lost.evidence_ids == ()
    lost_binding = next(
        item
        for item in result.verified.outcome.bindings
        if item.output_id == "evidence_boundary"
    )
    assert lost_binding.evidence_hashes == ()
    assert lost_binding.gap


def test_marker_loss_ignores_output_ids_absent_from_contract() -> None:
    frame, structural = _structural("市场当前偏弱，成交额观察仍成立。")
    before = structural.completion.outputs

    result = SemanticEpisodeVerifier(
        judge_fn=_judge(True)
    )._marker_loss_partial_public(
        frame,
        structural,
        ("not_in_contract",),
        judge_issues=("semantic repair removed required output",),
        correlated_judge=True,
    )

    assert result.gap_output_ids == ("not_in_contract",)
    assert result.verified.completion.outputs == before
    assert _fulfilled_ids(result.verified) == {"direct_assessment"}


def test_valuation_marker_loss_gap_keeps_task_context() -> None:
    frame, structural = _structural("瑞华泰当前PB约4.33。")
    valuation_frame = replace(
        frame,
        raw_question="瑞华泰的合理估值",
        question_type="valuation_estimate",
        subject="瑞华泰",
        subject_kind="company",
    )

    result = SemanticEpisodeVerifier(
        judge_fn=_judge(True)
    )._marker_loss_partial_public(
        valuation_frame,
        structural,
        ("evidence_boundary",),
        judge_issues=("semantic repair removed required output",),
        correlated_judge=True,
    )

    assert result.status == "partial"
    assert REQUIRED_OUTPUT_DEGRADED_MARK not in result.public_answer
    assert "瑞华泰当前PB约4.33" in result.public_answer
    assert "证据缺口：" not in result.public_answer
    assert "现有证据不足" not in result.public_answer
    assert result.gap_output_ids == ("evidence_boundary",)


def test_injected_passing_judge_records_correlated_limit() -> None:
    frame, structural = _structural("市场当前偏弱。")
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert result.correlated_judge is True


def test_independent_judge_provider_records_uncorrelated(monkeypatch) -> None:
    frame, structural = _structural("市场当前偏弱。")
    provider = llm_refine.LLMProvider("judge", "secret", "https://judge.invalid", "j")
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: provider)
    monkeypatch.setattr(
        llm_refine,
        "complete",
        lambda *_args, **_kwargs: (
            '{"passed":true,"rejected_sentence_indexes":[],"issues":[]}',
            provider,
            "",
        ),
    )
    result = SemanticEpisodeVerifier().verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(60),
    )
    assert result.status == "completed"
    assert result.correlated_judge is False


def test_independent_judge_provider_takes_priority_over_injected_judge(
    monkeypatch,
) -> None:
    frame, structural = _structural("市场当前偏弱。")
    provider = llm_refine.LLMProvider("judge", "secret", "https://judge.invalid", "j")
    independent_calls: list[object] = []
    injected_calls: list[object] = []
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: provider)

    def independent(*_args, **_kwargs):
        independent_calls.append(object())
        return (
            '{"passed":true,"rejected_sentence_indexes":[],"issues":[]}',
            provider,
            "",
        )

    monkeypatch.setattr(llm_refine, "complete", independent)
    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: injected_calls.append(request)
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(60),
    )
    assert result.status == "completed"
    assert result.correlated_judge is False
    assert len(independent_calls) == 1
    assert injected_calls == []


def test_independent_judge_retries_one_transient_failure(
    monkeypatch,
) -> None:
    frame, structural = _structural("市场当前偏弱。")
    provider = llm_refine.LLMProvider("judge", "secret", "https://judge.invalid", "j")
    calls: list[float] = []
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: provider)

    def flaky(*_args, **kwargs):
        calls.append(float(kwargs["timeout"]))
        if len(calls) == 1:
            return None, provider, "LLM 调用失败（ReadTimeout）"
        return (
            '{"passed":true,"rejected_sentence_indexes":[],"issues":[]}',
            provider,
            "",
        )

    monkeypatch.setattr(llm_refine, "complete", flaky)
    result = SemanticEpisodeVerifier().verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(60),
    )

    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert len(calls) == 2
    assert all(0.0 < timeout <= 60.0 for timeout in calls)


def test_leftover_sliver_does_not_dispatch_independent_judge(monkeypatch) -> None:
    frame, structural = _structural("市场当前偏弱。")
    provider = llm_refine.LLMProvider(
        "judge", "secret", "https://judge.invalid", "j"
    )
    calls: list[float] = []

    def complete(*_args, **kwargs):
        calls.append(float(kwargs["timeout"]))
        return (
            '{"passed":true,"rejected_sentence_indexes":[],"issues":[]}',
            provider,
            "",
        )

    monkeypatch.setattr(llm_refine, "judge_provider", lambda: provider)
    monkeypatch.setattr(llm_refine, "complete", complete)

    result = SemanticEpisodeVerifier(judge_timeout=12.0).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(0.5),
    )
    payload = result.to_dict()

    assert calls == []
    assert leftover_window_blocks_complete_attempt(0.5, 12.0) is True
    assert leftover_window_blocks_complete_attempt(20.0, 12.0) is False
    assert leftover_window_blocks_complete_attempt(
        49.0, DEFAULT_JUDGE_TIMEOUT_SECONDS
    ) is True
    assert leftover_window_blocks_complete_attempt(
        50.0, DEFAULT_JUDGE_TIMEOUT_SECONDS
    ) is False
    assert result.judge_status == "unavailable"
    assert LEFTOVER_WINDOW_ISSUE in result.issues
    assert payload["degrade_class"] == "judge_unavailable"
    assert payload["judge_unavailable_count"] == 1
    assert payload["content_degraded_count"] == 0
    assert payload["pending_rejudge"] is True
    assert payload["timeout_asked"] == 0.0
    assert isinstance(payload.get("judge_request"), dict)


def test_unclassified_runtimeerror_holds_draft_without_evidence_lie(
    monkeypatch,
) -> None:
    """§5.3 B2：兜底 provider error 不得放稿，也不得说证据不足 / 未绑定。"""

    frame, structural = _structural("市场当前偏弱，科技延续强于医药。")
    provider = llm_refine.LLMProvider("judge", "secret", "https://judge.invalid", "j")
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: provider)

    def boom(*_args, **_kwargs):
        return None, provider, "RuntimeError"

    monkeypatch.setattr(llm_refine, "complete", boom)
    result = SemanticEpisodeVerifier().verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(60),
    )
    payload = result.to_dict()
    public = result.public_answer

    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert payload["pending_rejudge"] is True
    assert "semantic judge provider error" in result.issues
    assert "复核服务不可用" in public
    assert "现有证据不足" not in public
    assert "未完成核验绑定" not in public
    assert "科技延续强于医药" not in public


def test_judge_outage_is_partial_and_never_exposes_raw_draft() -> None:
    frame, structural = _structural(
        "RAW_PROVIDER_SENTINEL market_data HASH_PRIVATE_SENTINEL。"
    )

    def outage(_request):
        raise TimeoutError("RAW_PROVIDER_SENTINEL")

    result = SemanticEpisodeVerifier(judge_fn=outage).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert result.public_answer != structural.outcome.draft
    assert "RAW_PROVIDER_SENTINEL" not in result.public_answer
    assert "HASH_PRIVATE_SENTINEL" not in result.public_answer
    assert "market_data" not in result.public_answer


def test_independent_judge_outage_keeps_uncorrelated_audit_flag(monkeypatch) -> None:
    frame, structural = _structural("市场当前偏弱。")
    provider = llm_refine.LLMProvider(
        "judge", "secret", "https://judge.invalid", "j"
    )
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: provider)
    monkeypatch.setattr(
        llm_refine,
        "complete",
        lambda *_args, **_kwargs: (None, provider, "ReadTimeout"),
    )

    result = SemanticEpisodeVerifier().verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(60),
    )

    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert result.correlated_judge is False
    assert "本次未完成独立复核（复核服务超时）" in result.public_answer


def test_independent_judge_timeout_records_asked_triplet_and_exc_class(
    monkeypatch,
) -> None:
    """R-06：judge 失败必须留下 #84 同款三元组 + 压平前的原始异常类。

    ``llm_refine._failure_reason`` 会把 TimeoutError 压成 ``timeout``，
    ``_stable_semantic_judge_error`` 再把 TimeoutError 和 5xx/连接收成同一句
    transient。缺 ``exc_class`` 就分不开 H8/H9。
    """

    frame, structural = _structural("市场当前偏弱。")
    provider = llm_refine.LLMProvider(
        "judge", "secret", "https://judge.invalid", "j"
    )
    seen: dict[str, float] = {}

    def complete(*_args, **kwargs):
        seen["timeout"] = float(kwargs["timeout"])
        return None, provider, "LLM 调用失败（TimeoutError）"

    monkeypatch.setattr(llm_refine, "judge_provider", lambda: provider)
    monkeypatch.setattr(llm_refine, "complete", complete)

    result = SemanticEpisodeVerifier(judge_timeout=12.0).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(20.0),
    )
    payload = result.to_dict()

    assert result.judge_status == "unavailable"
    assert "semantic judge transient provider error" in result.issues
    assert payload["timeout_configured"] == 12.0
    assert payload["timeout_asked"] == pytest.approx(seen["timeout"])
    assert isinstance(payload["remaining_seconds_at_entry"], float)
    assert payload["timeout_asked"] <= payload["remaining_seconds_at_entry"] + 0.001
    assert payload["exc_class"] == "TimeoutError"
    assert payload.get("http_status") is None
    assert "TimeoutError" not in result.public_answer


def test_independent_judge_http_503_records_status_not_timeout_class(
    monkeypatch,
) -> None:
    frame, structural = _structural("市场当前偏弱。")
    provider = llm_refine.LLMProvider(
        "judge", "secret", "https://judge.invalid", "j"
    )

    def complete(*_args, **_kwargs):
        return None, provider, "LLM 调用 HTTP 503"

    monkeypatch.setattr(llm_refine, "judge_provider", lambda: provider)
    monkeypatch.setattr(llm_refine, "complete", complete)

    result = SemanticEpisodeVerifier(judge_timeout=12.0).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(20.0),
    )
    payload = result.to_dict()

    assert "semantic judge transient provider error" in result.issues
    assert payload["exc_class"] == "HTTPError"
    assert payload["http_status"] == 503
    assert payload["timeout_asked"] > 0.0


def test_primary_judge_connection_error_keeps_raw_class_and_hides_message(
    monkeypatch,
) -> None:
    frame, structural = _structural("市场当前偏弱。")

    class BoomJudge:
        def complete(self, *, messages, tools, timeout):
            del messages, tools, timeout
            raise ConnectionError("RAW_PROVIDER_SENTINEL")

    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    result = SemanticEpisodeVerifier(
        primary_judge=BoomJudge(),
        judge_timeout=12.0,
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(20.0),
    )
    payload = result.to_dict()
    dumped = json.dumps(payload, ensure_ascii=False)

    assert payload["exc_class"] == "ConnectionError"
    assert payload["timeout_configured"] == 12.0
    assert isinstance(payload["timeout_asked"], float)
    assert "RAW_PROVIDER_SENTINEL" not in dumped
    assert "RAW_PROVIDER_SENTINEL" not in result.public_answer


def test_primary_judge_retries_one_transient_failure_within_shared_deadline(
    monkeypatch,
) -> None:
    frame, structural = _structural("市场当前偏弱。")

    class FlakyJudge:
        def __init__(self) -> None:
            self.calls: list[float] = []

        def complete(self, *, messages, tools, timeout):
            del messages, tools
            self.calls.append(timeout)
            if len(self.calls) == 1:
                return ModelTurn(
                    "",
                    (),
                    "glm",
                    "LLM 调用失败（ReadTimeout）",
                )
            return ModelTurn(
                '{"passed":true,"rejected_sentence_indexes":[],"issues":[]}',
                (),
                "glm",
                "",
            )

    model = FlakyJudge()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert len(model.calls) == 2
    assert all(0.0 < timeout <= 5.0 for timeout in model.calls)


def test_primary_judge_default_attempt_reserves_retry_window(
    monkeypatch,
) -> None:
    frame, structural = _structural("市场当前偏弱。")
    model = _RecordingJudgeModel()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(60),
    )

    assert result.status == "completed"
    # Opening attempt is one complete try: min(cap, window). The 0.5 pre-split
    # was retired after the 08-20 grok tail (46.7s) could not fit in half of
    # the 50s floor. Retries share the leftover, they do not own a reserved
    # half-window.
    window = semantic_judge_window_seconds()
    # 绝对容差，不用 approx 的默认相对容差（2026-08-11 改）：
    # 这个 timeout 是从**活的 deadline** 现算的，`from_timeout(60)` 到判定发生之间
    # 真实流逝的时间会被减掉。50ms 对负载抖动足够宽，对真回归足够紧。
    assert model.calls[0]["timeout"] == pytest.approx(
        min(DEFAULT_JUDGE_TIMEOUT_SECONDS, window), abs=0.05
    )
    assert model.calls[0]["timeout"] <= window + 0.01


def test_primary_judge_shared_semantic_deadline_bounds_transient_attempts(
    monkeypatch,
) -> None:
    frame, structural = _structural("市场当前偏弱。")

    class RepeatedTransientJudge:
        def __init__(self) -> None:
            self.calls: list[float] = []

        def complete(self, *, messages, tools, timeout):
            del messages, tools
            self.calls.append(float(timeout))
            return ModelTurn("", (), "glm", "LLM 调用 HTTP 503")

    model = RepeatedTransientJudge()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(60),
    )

    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert len(model.calls) == 3
    # The invariant is "all attempts together stay inside the one shared
    # window", not any particular number of seconds — express it that way so
    # recalibrating the window does not read as a broken bound.
    #
    # 这里断言的是**报价**上限，不再是报价之和：窗口现在由 ``_run_judge`` 的
    # 余额账按真实耗时封顶（本例的假判官瞬时返回，一秒都没花）。真正的
    # 「合计不超窗」由 test_judge_attempts_never_exceed_the_shared_window_in_wall_clock
    # 用会走钟的假判官证明。报价之和曾是那条不变式的代理，静态划分取消后它不再等价。
    assert max(model.calls) <= complete_judge_attempt_seconds(
        DEFAULT_JUDGE_TIMEOUT_SECONDS
    ) + 0.01
    assert model.calls[0] >= model.calls[1]


def test_primary_judge_accepts_one_schema_valid_report_tool_call(
    monkeypatch,
) -> None:
    frame, structural = _structural("市场当前偏弱。")

    class StructuredJudge:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def complete(self, *, messages, tools, timeout):
            self.calls.append(
                {"messages": messages, "tools": tools, "timeout": timeout}
            )
            return ModelTurn(
                "",
                (
                    ModelToolCall(
                        "judge-report-1",
                        "submit_grounding_report",
                        {
                            "passed": True,
                            "rejected_sentence_indexes": [],
                            "issues": [],
                        },
                    ),
                ),
                "glm",
                "",
            )

    model = StructuredJudge()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert len(model.calls) == 1
    definitions = model.calls[0]["tools"]
    assert len(definitions) == 1
    assert definitions[0]["function"]["name"] == "submit_grounding_report"
    assert definitions[0]["function"]["parameters"]["additionalProperties"] is False


def test_primary_judge_rejects_unknown_report_tool_without_retry(
    monkeypatch,
) -> None:
    frame, structural = _structural("市场当前偏弱。")

    class WrongToolJudge:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            return ModelTurn(
                "",
                (ModelToolCall("wrong-1", "market_data", {"query": "x"}),),
                "glm",
                "",
            )

    model = WrongToolJudge()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert model.calls == 1
    assert "semantic judge returned an invalid tool call" in result.issues


def test_primary_judge_accepts_valid_report_tool_with_ignored_sibling_content(
    monkeypatch,
) -> None:
    frame, structural = _structural("市场当前偏弱。")
    report = ModelToolCall(
        "judge-report-1",
        "submit_grounding_report",
        {
            "passed": True,
            "rejected_sentence_indexes": [],
            "issues": [],
        },
    )

    class SiblingContentJudge:
        def complete(self, **_kwargs):
            return ModelTurn(
                "这段兼容性正文不会进入裁判结果或公共答案。",
                (report,),
                "glm",
                "",
            )

    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    result = SemanticEpisodeVerifier(primary_judge=SiblingContentJudge()).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert "兼容性正文" not in result.public_answer


def test_primary_judge_rejects_multiple_report_tool_calls(
    monkeypatch,
) -> None:
    frame, structural = _structural("市场当前偏弱。")
    report = ModelToolCall(
        "judge-report-1",
        "submit_grounding_report",
        {
            "passed": True,
            "rejected_sentence_indexes": [],
            "issues": [],
        },
    )

    class MultipleReportsJudge:
        def complete(self, **_kwargs):
            return ModelTurn("", (report, report), "glm", "")

    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    result = SemanticEpisodeVerifier(primary_judge=MultipleReportsJudge()).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert "semantic judge returned an invalid tool call" in result.issues


def test_primary_judge_does_not_retry_configuration_failure(monkeypatch) -> None:
    frame, structural = _structural("市场当前偏弱。")

    class MisconfiguredJudge:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            return ModelTurn("", (), "glm", "LLM 调用 HTTP 401")

    model = MisconfiguredJudge()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert model.calls == 1
    assert "semantic judge configuration error" in result.issues
    assert all("401" not in issue for issue in result.issues)


def test_late_judge_pass_is_unavailable_and_cannot_complete() -> None:
    frame, structural = _structural("市场当前偏弱。")

    def late_pass(_request):
        time.sleep(0.02)
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    result = SemanticEpisodeVerifier(judge_fn=late_pass).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(0.005),
    )
    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert any("deadline" in issue for issue in result.issues)


def test_late_rejudge_preserves_prior_judged_monotonic_redaction() -> None:
    frame, structural = _structural("市场下跌。据E99显示下跌。")
    calls = 0

    def reject_then_late_pass(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "passed": False,
                "rejected_sentence_indexes": [2],
                "issues": [
                    "code=unresolved_evidence_ordinal "
                    "subject=unresolved_evidence_ordinal :: "
                    "cited evidence ordinal is not in this episode's evidence table"
                ],
            }
        time.sleep(0.03)
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    result = SemanticEpisodeVerifier(judge_fn=reject_then_late_pass).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(0.02),
    )
    assert calls == 2
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert result.public_answer == "市场下跌。"
    assert any("deadline" in issue for issue in result.issues)


def test_transient_optional_rejudge_preserves_prior_monotonic_redaction(
    monkeypatch,
) -> None:
    frame, structural = _structural("市场下跌。据E99显示下跌。")

    class TransientRejudge:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return ModelTurn(
                    json.dumps(
                        {
                            "passed": False,
                            "rejected_sentence_indexes": [2],
                            "issues": [
                    "code=unresolved_evidence_ordinal "
                    "subject=unresolved_evidence_ordinal :: "
                    "cited evidence ordinal is not in this episode's evidence table"
                ],
                        },
                        ensure_ascii=False,
                    ),
                    (),
                    "glm",
                    "",
                )
            return ModelTurn("", (), "glm", "LLM 调用 HTTP 503")

    model = TransientRejudge()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert model.calls == 4
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert result.public_answer == "市场下跌。"
    assert "semantic judge transient provider error" in result.issues


@pytest.mark.parametrize(
    "errors",
    (
        ("rate limit exceeded", "LLM 调用 HTTP 503"),
        ("LLM 调用 HTTP 503", "temporarily unavailable"),
    ),
)
def test_mixed_optional_rejudge_failures_cannot_unlock_monotonic_release(
    monkeypatch,
    errors: tuple[str, str],
) -> None:
    frame, structural = _structural("市场下跌。据E99显示下跌。")

    class MixedOptionalRejudge:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return ModelTurn(
                    json.dumps(
                        {
                            "passed": False,
                            "rejected_sentence_indexes": [2],
                            "issues": [
                    "code=unresolved_evidence_ordinal "
                    "subject=unresolved_evidence_ordinal :: "
                    "cited evidence ordinal is not in this episode's evidence table"
                ],
                        },
                        ensure_ascii=False,
                    ),
                    (),
                    "glm",
                    "",
                )
            return ModelTurn("", (), "glm", errors[self.calls - 2])

    model = MixedOptionalRejudge()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert model.calls == 3
    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert result.public_answer != "市场下跌。"


def test_weak_optional_failure_then_retry_deadline_cannot_unlock_release(
    monkeypatch,
) -> None:
    frame, structural = _structural("市场下跌。据E99显示下跌。")

    class RetryWindowClosesAfterWeakFailure:
        def __init__(self) -> None:
            self.timeout_calls = 0

        def synthesis_timeout(self, _configured_limit: float) -> float:
            self.timeout_calls += 1
            return 0.0 if self.timeout_calls >= 5 else 1.0

        @property
        def expired(self) -> bool:
            return self.timeout_calls >= 5

    class WeakOptionalRejudge:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return ModelTurn(
                    json.dumps(
                        {
                            "passed": False,
                            "rejected_sentence_indexes": [2],
                            "issues": [
                    "code=unresolved_evidence_ordinal "
                    "subject=unresolved_evidence_ordinal :: "
                    "cited evidence ordinal is not in this episode's evidence table"
                ],
                        },
                        ensure_ascii=False,
                    ),
                    (),
                    "glm",
                    "",
                )
            return ModelTurn("", (), "glm", "rate limit exceeded")

    model = WeakOptionalRejudge()
    deadline = RetryWindowClosesAfterWeakFailure()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=deadline,  # type: ignore[arg-type]
    )

    assert model.calls == 2
    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert result.public_answer != "市场下跌。"
    assert any("deadline" in issue for issue in result.issues)


def test_release_grade_optional_failure_then_retry_deadline_allows_release(
    monkeypatch,
) -> None:
    frame, structural = _structural("市场下跌。据E99显示下跌。")

    class RetryWindowClosesAfterTypedFailure:
        def __init__(self) -> None:
            self.timeout_calls = 0

        def synthesis_timeout(self, _configured_limit: float) -> float:
            self.timeout_calls += 1
            return 0.0 if self.timeout_calls >= 5 else 1.0

        @property
        def expired(self) -> bool:
            return self.timeout_calls >= 5

    class TypedOptionalRejudge:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return ModelTurn(
                    json.dumps(
                        {
                            "passed": False,
                            "rejected_sentence_indexes": [2],
                            "issues": [
                    "code=unresolved_evidence_ordinal "
                    "subject=unresolved_evidence_ordinal :: "
                    "cited evidence ordinal is not in this episode's evidence table"
                ],
                        },
                        ensure_ascii=False,
                    ),
                    (),
                    "glm",
                    "",
                )
            return ModelTurn("", (), "glm", "LLM 调用 HTTP 503")

    model = TypedOptionalRejudge()
    deadline = RetryWindowClosesAfterTypedFailure()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=deadline,  # type: ignore[arg-type]
    )

    assert model.calls == 2
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert result.public_answer == "市场下跌。"
    assert any("deadline" in issue for issue in result.issues)


def test_initial_transient_judge_still_fails_closed(monkeypatch) -> None:
    frame, structural = _structural("市场下跌。")

    class TransientFirstJudge:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            return ModelTurn("", (), "glm", "LLM 调用 HTTP 503")

    model = TransientFirstJudge()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert model.calls == 3
    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert result.public_answer != "市场下跌。"


def test_initial_judge_can_recover_on_third_release_grade_attempt(
    monkeypatch,
) -> None:
    frame, structural = _structural("市场下跌。")

    class RecoveringJudge:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls <= 2:
                return ModelTurn("", (), "glm", "LLM 调用 HTTP 503")
            return ModelTurn(
                json.dumps(
                    {
                        "passed": True,
                        "rejected_sentence_indexes": [],
                        "issues": [],
                    },
                    ensure_ascii=False,
                ),
                (),
                "glm",
                "",
            )

    model = RecoveringJudge()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert model.calls == 3
    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert result.public_answer == "市场下跌。"


@pytest.mark.parametrize(
    "errors",
    (
        ("rate limit exceeded", "LLM 调用 HTTP 503"),
        ("LLM 调用 HTTP 503", "temporarily unavailable"),
    ),
)
def test_mixed_retryable_failures_cannot_unlock_third_judge_attempt(
    monkeypatch,
    errors: tuple[str, str],
) -> None:
    frame, structural = _structural("市场下跌。")

    class MixedFailureJudge:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls <= 2:
                return ModelTurn("", (), "glm", errors[self.calls - 1])
            return ModelTurn(
                json.dumps(
                    {
                        "passed": True,
                        "rejected_sentence_indexes": [],
                        "issues": [],
                    },
                    ensure_ascii=False,
                ),
                (),
                "glm",
                "",
            )

    model = MixedFailureJudge()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert model.calls == 2
    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert result.public_answer != "市场下跌。"


@pytest.mark.parametrize(
    ("error", "expected_calls"),
    (
        ("HTTP 400 invalid max_tokens, must be <= 500", 2),
        ("remote model not found", 2),
        ("invalid remote endpoint", 2),
        ("rate limit exceeded", 3),
        ("temporarily unavailable", 3),
        ("网络错误，请稍后重试", 3),
    ),
)
def test_optional_rejudge_unapproved_error_cannot_masquerade_as_release_grade(
    monkeypatch,
    error: str,
    expected_calls: int,
) -> None:
    frame, structural = _structural("市场下跌。据E99显示下跌。")

    class InvalidRejudge:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return ModelTurn(
                    json.dumps(
                        {
                            "passed": False,
                            "rejected_sentence_indexes": [2],
                            "issues": [
                    "code=unresolved_evidence_ordinal "
                    "subject=unresolved_evidence_ordinal :: "
                    "cited evidence ordinal is not in this episode's evidence table"
                ],
                        },
                        ensure_ascii=False,
                    ),
                    (),
                    "glm",
                    "",
                )
            return ModelTurn("", (), "glm", error)

    model = InvalidRejudge()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert model.calls == expected_calls
    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert result.public_answer != "市场下跌。"


def test_malformed_rejudge_cannot_release_prior_redaction() -> None:
    frame, structural = _structural("市场下跌。据E99显示下跌。")
    calls = 0

    def reject_then_malformed(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "passed": False,
                "rejected_sentence_indexes": [2],
                "issues": [
                    "code=unresolved_evidence_ordinal "
                    "subject=unresolved_evidence_ordinal :: "
                    "cited evidence ordinal is not in this episode's evidence table"
                ],
            }
        return None

    result = SemanticEpisodeVerifier(judge_fn=reject_then_malformed).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert calls == 2
    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert result.public_answer != "市场下跌。"


def test_late_malformed_rejudge_cannot_masquerade_as_deadline_recovery() -> None:
    frame, structural = _structural("市场下跌。据E99显示下跌。")
    calls = 0

    def reject_then_late_malformed(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "passed": False,
                "rejected_sentence_indexes": [2],
                "issues": [
                    "code=unresolved_evidence_ordinal "
                    "subject=unresolved_evidence_ordinal :: "
                    "cited evidence ordinal is not in this episode's evidence table"
                ],
            }
        time.sleep(0.03)
        return None

    result = SemanticEpisodeVerifier(
        judge_fn=reject_then_late_malformed
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(0.02),
    )

    assert calls == 2
    assert result.status == "partial"
    assert result.judge_status == "unavailable"


def test_late_rejudge_rejection_is_redacted_before_release() -> None:
    frame, structural = _structural(
        "市场下跌。据E98显示资金变化。据E99显示政策变化。"
    )
    calls = 0

    def reject_then_late_reject(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "passed": False,
                "rejected_sentence_indexes": [3],
                "issues": [
                    "code=unresolved_evidence_ordinal "
                    "subject=unresolved_evidence_ordinal :: "
                    "cited evidence ordinal is not in this episode's evidence table"
                ],
            }
        time.sleep(0.03)
        return {
            "passed": False,
            "rejected_sentence_indexes": [2],
            "issues": [
                "code=unresolved_evidence_ordinal "
                "subject=unresolved_evidence_ordinal :: "
                "cited evidence ordinal is not in this episode's evidence table"
            ],
        }

    result = SemanticEpisodeVerifier(judge_fn=reject_then_late_reject).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(0.02),
    )

    assert calls == 2
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert result.public_answer == "市场下跌。"
    assert "据E98显示资金变化。" not in result.public_answer


def test_late_final_rejudge_preserves_twice_judged_monotonic_redaction() -> None:
    frame, structural = _structural(
        "市场下跌。据E99显示下跌。据E98显示资金变化。"
    )
    calls = 0

    def reject_twice_then_late_pass(_request):
        nonlocal calls
        calls += 1
        if calls <= 2:
            return {
                "passed": False,
                "rejected_sentence_indexes": [2],
                "issues": [
                    "code=unresolved_evidence_ordinal "
                    "subject=unresolved_evidence_ordinal :: "
                    f"cited evidence ordinal is not in this episode's evidence table #{calls}"
                ],
            }
        time.sleep(0.03)
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    result = SemanticEpisodeVerifier(
        judge_fn=reject_twice_then_late_pass
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(0.02),
    )

    assert calls == 3
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert result.public_answer == "市场下跌。"
    assert any("deadline" in issue for issue in result.issues)


def test_transient_final_rejudge_preserves_twice_judged_monotonic_redaction(
    monkeypatch,
) -> None:
    frame, structural = _structural(
        "市场下跌。据E99显示下跌。据E98显示资金变化。"
    )

    class TransientFinalRejudge:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls <= 2:
                return ModelTurn(
                    json.dumps(
                        {
                            "passed": False,
                            "rejected_sentence_indexes": [2],
                            "issues": [
                                "code=unresolved_evidence_ordinal "
                                "subject=unresolved_evidence_ordinal :: "
                                "cited evidence ordinal is not in this episode's "
                                f"evidence table #{self.calls}"
                            ],
                        },
                        ensure_ascii=False,
                    ),
                    (),
                    "glm",
                    "",
                )
            return ModelTurn("", (), "glm", "LLM 调用 HTTP 503")

    model = TransientFinalRejudge()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert model.calls == 5
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert result.public_answer == "市场下跌。"
    assert "semantic judge transient provider error" in result.issues


def test_late_malformed_final_rejudge_remains_fail_closed() -> None:
    frame, structural = _structural(
        "市场下跌。据E99显示下跌。据E98显示资金变化。"
    )
    calls = 0

    def reject_twice_then_late_malformed(_request):
        nonlocal calls
        calls += 1
        if calls <= 2:
            return {
                "passed": False,
                "rejected_sentence_indexes": [2],
                "issues": [
                    "code=unresolved_evidence_ordinal "
                    "subject=unresolved_evidence_ordinal :: "
                    f"cited evidence ordinal is not in this episode's evidence table #{calls}"
                ],
            }
        time.sleep(0.03)
        return None

    result = SemanticEpisodeVerifier(
        judge_fn=reject_twice_then_late_malformed
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(0.02),
    )

    assert calls == 3
    assert result.status == "partial"
    assert result.judge_status == "unavailable"


@pytest.mark.parametrize(
    "wrapped",
    [
        'I think {"passed":true,"rejected_sentence_indexes":[],"issues":[]}',
        '{"passed":true,"rejected_sentence_indexes":[],"issues":[]} trailing',
    ],
)
def test_judge_rejects_json_with_surrounding_prose(wrapped: str) -> None:
    frame, structural = _structural("市场当前偏弱。")
    result = SemanticEpisodeVerifier(judge_fn=lambda _request: wrapped).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert result.judge_status == "unavailable"


def test_judge_accepts_one_strict_json_code_fence() -> None:
    frame, structural = _structural("市场当前偏弱。")
    result = SemanticEpisodeVerifier(
        judge_fn=lambda _request: (
            '```json\n{"passed":true,"rejected_sentence_indexes":[],"issues":[]}\n```'
        )
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert result.judge_status == "passed"


@pytest.mark.parametrize(
    "invalid",
    [
        {"passed": True, "rejected_sentence_indexes": []},
        {"passed": True, "rejected_sentence_indexes": [], "issues": "none"},
        answer_model.GroundingJudgeReport(False, (), ()),
        {
            "passed": True,
            "rejected_sentence_indexes": [],
            "issues": {object()},
        },
    ],
)
def test_invalid_judge_shape_fails_closed_without_raising(invalid: object) -> None:
    frame, structural = _structural("市场当前偏弱。")
    result = SemanticEpisodeVerifier(judge_fn=lambda _request: invalid).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert result.judge_status == "unavailable"


def test_clean_strict_json_report_is_accepted() -> None:
    frame, structural = _structural("市场当前偏弱。")
    result = SemanticEpisodeVerifier(
        judge_fn=lambda _request: (
            '{"passed":true,"rejected_sentence_indexes":[],"issues":[]}'
        )
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"


def test_empty_public_projection_preserves_passed_judge_status() -> None:
    frame, structural = _structural("provider=OpenAI。")
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert result.judge_status == "passed"
    assert "public projection empty" in result.issues


def test_redaction_that_empties_draft_fails_closed() -> None:
    frame, structural = _structural("政策变化导致了下跌。")
    judge = _judge(False, rejected=(1,), issues=("因果证据不足",))
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert "政策变化导致了下跌" in result.public_answer
    assert SEMANTIC_QUALITY_DOUBT_MARK not in result.public_answer
    assert "semantic repair unavailable" not in result.issues


def test_public_projection_filters_casefolded_private_tokens_everywhere() -> None:
    frame, structural = _structural(
        "市场当前偏弱。\nprovider=OpenAI。\nprovider_attempt=2。\n"
        "_provider_trace=Zhipu。\nendpoint=https://private。\n"
        "system_prompt=PRIVATE。\nhash=PRIVATE。\nMARKET_DATA。\n"
        "hash_private_sentinel。"
    )
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    for sentinel in (
        "provider=",
        "provider_attempt",
        "_provider_trace",
        "endpoint=",
        "system_prompt",
        "hash=",
        "market_data",
        "hash_private_sentinel",
    ):
        assert sentinel.casefold() not in result.public_answer.casefold()


def test_public_projection_drops_only_contaminated_sentence_in_single_line() -> (
    None
):
    frame, structural = _structural(
        "本周上证指数实际上涨2.99%。"
        "news_search未返回对齐资讯。"
        "7月17日单日下跌约3.05%。",
        detail="本周上证指数上涨2.99%；7月17日单日下跌3.05%。",
        traces=(
            ProviderTrace(
                provider="private:news",
                capability="news_search",
                status="empty",
                result_count=0,
            ),
        ),
    )

    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert "本周上证指数实际上涨2.99%" in result.public_answer
    assert "7月17日单日下跌约3.05%" in result.public_answer
    assert "news_search" not in result.public_answer


def test_public_projection_filters_empty_trace_capability_but_keeps_natural_status() -> (
    None
):
    frame, structural = _structural(
        "本轮资讯检索未命中，外部催化仍待核验。\ndirectional_news status=empty。",
        traces=(
            ProviderTrace(
                provider="private:news",
                capability="directional_news",
                status="empty",
                result_count=0,
            ),
        ),
    )

    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert "本轮资讯检索未命中" in result.public_answer
    assert "directional_news" not in result.public_answer


def test_public_sanitizer_keeps_provider_brand_in_financial_fact() -> None:
    frame, structural = _structural(
        "OpenAI资本开支上升，带动光模块需求；当前 drawdown（最大回撤）仍需观察。"
    )
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert "OpenAI资本开支上升" in result.public_answer
    assert "drawdown" in result.public_answer


def test_public_sanitizer_keeps_raw_material_and_valuation_model_facts() -> None:
    frame, structural = _structural(
        "Raw material prices rose 8%。\n估值 model=DCF，折现率9%。"
    )
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert "Raw material prices rose 8%" in result.public_answer
    assert "估值 model=DCF，折现率9%" in result.public_answer


def test_semantic_public_answer_does_not_duplicate_citation_ledger() -> None:
    frame, structural = _structural(
        "市场当前偏弱。",
        title="OpenAI公司公告",
        source="公开来源",
    )
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert result.public_answer == "市场当前偏弱。"
    assert "OpenAI公司公告" not in result.public_answer
    assert "依据：" not in result.public_answer


def test_structural_gap_filters_private_control_tokens_case_insensitively() -> None:
    frame, structural = _structural(
        "未核验草稿。",
        gaps=("system_prompt=PRIVATE OpenAI HASH_PRIVATE_SENTINEL MARKET_DATA",),
    )
    original = structural.outcome
    partial_outcome = AgentOutcome(
        task_frame_hash=original.task_frame_hash,
        status="partial",
        draft=original.draft,
        evidence=original.evidence,
        traces=original.traces,
        gaps=original.gaps,
        stop_reason=original.stop_reason,
        events=original.events,
        bindings=(),
        usage=original.usage,
    )
    assert structural.contract is not None
    partial = verify_episode_outcome(structural.contract, partial_outcome)
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=partial,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    for sentinel in ("system_prompt", "OpenAI", "hash_private", "market_data"):
        assert sentinel.casefold() not in result.public_answer.casefold()


def test_public_gap_never_projects_business_context_free_text() -> None:
    frame, structural = _structural(
        "未核验草稿。",
        gaps=("OpenAI资本开支证据仍缺",),
    )
    original = structural.outcome
    partial_outcome = AgentOutcome(
        task_frame_hash=original.task_frame_hash,
        status="partial",
        draft=original.draft,
        evidence=original.evidence,
        traces=original.traces,
        gaps=original.gaps,
        stop_reason=original.stop_reason,
        events=original.events,
        bindings=(),
        usage=original.usage,
    )
    assert structural.contract is not None
    partial = verify_episode_outcome(structural.contract, partial_outcome)
    result = SemanticEpisodeVerifier().verify(
        frame=frame,
        structurally_verified=partial,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert "OpenAI资本开支证据仍缺" not in result.public_answer
    assert "直接判断" in result.public_answer


def test_public_gap_never_includes_internal_semantic_repair_issues() -> None:
    frame, structural = _structural("政策变化导致了下跌。")
    result = SemanticEpisodeVerifier(
        judge_fn=_judge(False, rejected=(1,), issues=("因果证据不足",))
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert "政策变化导致了下跌" in result.public_answer
    assert "semantic" not in result.public_answer.casefold()
    assert "judge" not in result.public_answer.casefold()
    assert "repair unavailable" not in result.public_answer.casefold()


@pytest.mark.parametrize("judge_mode", ["rejected", "unavailable"])
def test_public_gap_never_projects_adversarial_outcome_gap(judge_mode: str) -> None:
    poisoned = "政策变化导致了下跌 PRIVATE_GAP_SENTINEL"
    frame, structural = _structural("市场下跌。", gaps=(poisoned,))
    if judge_mode == "rejected":
        judge_fn = _judge(False, rejected=(1,), issues=("证据不足",))
    else:

        def judge_fn(_request):
            return "invalid"

    result = SemanticEpisodeVerifier(judge_fn=judge_fn).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert poisoned not in result.public_answer
    assert "PRIVATE_GAP_SENTINEL" not in result.public_answer
    if judge_mode == "unavailable":
        assert result.status == "partial"
        assert "复核服务不可用" in result.public_answer
        assert "现有证据不足" not in result.public_answer
        assert "未完成核验绑定" not in result.public_answer
    else:
        assert "市场下跌" in result.public_answer


def test_public_gap_never_projects_adversarial_binding_gap() -> None:
    poisoned = "政策变化导致了下跌 PRIVATE_BINDING_SENTINEL"
    frame, structural = _structural("未核验草稿。")
    original = structural.outcome
    partial_outcome = AgentOutcome(
        task_frame_hash=original.task_frame_hash,
        status="partial",
        draft=original.draft,
        evidence=original.evidence,
        traces=original.traces,
        gaps=(poisoned,),
        stop_reason=original.stop_reason,
        events=original.events,
        bindings=(OutputEvidenceBinding("direct_assessment", (), poisoned),),
        usage=original.usage,
    )
    assert structural.contract is not None
    partial = verify_episode_outcome(structural.contract, partial_outcome)
    result = SemanticEpisodeVerifier().verify(
        frame=frame,
        structurally_verified=partial,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert "PRIVATE_BINDING_SENTINEL" not in result.public_answer
    assert "直接判断" in result.public_answer


def test_structural_partial_is_not_upgraded_or_judged() -> None:
    frame, structural = _structural("市场下跌。")
    # Remove the only required binding by verifying a partial outcome.
    partial_outcome = AgentOutcome(
        task_frame_hash=structural.outcome.task_frame_hash,
        status="partial",
        draft=structural.outcome.draft,
        evidence=structural.outcome.evidence,
        traces=structural.outcome.traces,
        gaps=structural.outcome.gaps,
        stop_reason=structural.outcome.stop_reason,
        events=structural.outcome.events,
        bindings=(),
        usage=structural.outcome.usage,
    )
    contract = structural.contract
    assert contract is not None
    partial = verify_episode_outcome(contract, partial_outcome)
    calls: list[object] = []
    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: calls.append(request)
    ).verify(
        frame=frame,
        structurally_verified=partial,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert not calls


def test_mixed_structural_partial_can_release_judged_fulfilled_draft() -> None:
    frame, structural = _structural(
        "直接判断：本周实际上涨约3%。证据缺口：单日下跌诱因无法确认。"
    )
    evidence = structural.outcome.evidence[0]
    contract = ResearchTaskContract(
        task_id="semantic-partial-release",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
            RequiredOutput("cause_attribution", "原因归因", ("web_search",), True),
        ),
        allowed_capabilities=("market_data", "web_search"),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    partial = verify_episode_outcome(
        contract,
        replace(
            structural.outcome,
            status="partial",
            gaps=("单日下跌诱因缺少时间对齐证据",),
            bindings=(
                OutputEvidenceBinding(
                    "direct_assessment",
                    (evidence.content_hash,),
                ),
                OutputEvidenceBinding(
                    "cause_attribution",
                    (),
                    "单日下跌诱因缺少时间对齐证据",
                ),
            ),
        ),
    )
    judge = _judge(True)

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=partial,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert partial.verified_status == "partial"
    assert result.status == "partial"
    assert result.judge_status == "passed"
    assert len(judge.calls) == 1  # type: ignore[attr-defined]
    assert "本周实际上涨约3%" in result.public_answer
    assert "单日下跌诱因无法确认" in result.public_answer


def test_missing_mandatory_news_can_release_judged_market_facts_as_partial() -> None:
    frame, structural = _structural(
        "直接判断：本周实际上涨约3%。证据缺口：单日诱因仍无法确认。"
    )
    contract = ResearchTaskContract(
        task_id="semantic-missing-cause-news",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type="market_cause",
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
        ),
        allowed_capabilities=("market_data", "news_search"),
        evidence_plan=EvidencePlan(
            profile="time_aligned_market_causal",
            requirements=(
                EvidenceRequirement(
                    "MARKET_DAILY",
                    "market_data",
                    True,
                    "current",
                    "市场窗口",
                ),
                EvidenceRequirement(
                    "CAUSE_NEWS",
                    "news_search",
                    True,
                    "current",
                    "时间对齐的原因证据",
                ),
            ),
        ),
        task_frame_hash=frame.task_frame_hash,
    )
    partial = verify_episode_outcome(contract, structural.outcome)
    judge = _judge(True)

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=partial,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert partial.verified_status == "partial"
    assert [item.code for item in partial.issue_items] == [
        IssueCode.MISSING_MANDATORY_CAPABILITY,
    ]
    assert "news_search" in partial.issue_items[0].subject
    assert result.status == "partial"
    assert result.judge_status == "passed"
    assert "本周实际上涨约3%" in result.public_answer


def test_wrong_type_prime_slot_releases_judged_rest_as_partial() -> None:
    """类型白名单缺口进放行名单：整格非法的 prime 槽只降级，不换缺口模板。

    run_20260819_130854 的第二种形态：模型给 prime_quote 只绑了
    finance_query 的日频总览。槽位判 missing，但其余槽位已凭真实证据履行、
    草稿仍应交给语义裁判以 partial 放行。
    """

    frame, structural = _structural("直接判断：市场结构中性偏强，量能维持在高位。")
    evidence = structural.outcome.evidence[0]
    overview = AgentEvidence(
        tool="finance_query",
        title="日频总览",
        detail="同日行情总览",
        source="本地库",
        source_date="2026-07-22",
        content_hash="finance-overview-1",
    )
    contract = ResearchTaskContract(
        task_id="semantic-wrong-type-release",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
            RequiredOutput("prime_quote", "最新行情要点", ("market_data",), True),
        ),
        allowed_capabilities=("market_data", "finance_query"),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    partial = verify_episode_outcome(
        contract,
        replace(
            structural.outcome,
            evidence=(evidence, overview),
            bindings=(
                OutputEvidenceBinding(
                    "direct_assessment",
                    (evidence.content_hash,),
                ),
                OutputEvidenceBinding("prime_quote", ("finance-overview-1",)),
            ),
        ),
    )
    assert partial.verified_status == "partial"
    assert [item.code for item in partial.issue_items] == [
        IssueCode.EVIDENCE_TYPE_UNSUPPORTED,
    ]
    assert partial.issue_items[0].subject == "prime_quote"
    assert "finance_query" in partial.issue_items[0].message
    judge = _judge(True)

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=partial,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "partial"
    assert result.judge_status == "passed"
    assert len(judge.calls) == 1  # type: ignore[attr-defined]
    assert "市场结构中性偏强" in result.public_answer
    assert "现有证据不足" not in result.public_answer


def test_stripped_mixed_prime_binding_completes_and_releases_draft() -> None:
    """SPT 端到端复现：prime 槽混绑合法行情 + 越界 finance_query。

    结构层剔掉越界哈希后槽位照常履行，整篇按 completed 走语义裁判并公开
    模型稿——这正是 run_20260819_130854 里被换成「现有证据不足」的那种答案。
    """

    frame, structural = _structural("直接判断：市场结构中性偏强，量能维持在高位。")
    evidence = structural.outcome.evidence[0]
    overview = AgentEvidence(
        tool="finance_query",
        title="日频总览",
        detail="同日行情总览",
        source="本地库",
        source_date="2026-07-22",
        content_hash="finance-overview-1",
    )
    contract = ResearchTaskContract(
        task_id="semantic-stripped-release",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
            RequiredOutput("prime_quote", "最新行情要点", ("market_data",), True),
        ),
        allowed_capabilities=("market_data", "finance_query"),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    verified = verify_episode_outcome(
        contract,
        replace(
            structural.outcome,
            evidence=(evidence, overview),
            bindings=(
                OutputEvidenceBinding(
                    "direct_assessment",
                    (evidence.content_hash,),
                ),
                OutputEvidenceBinding(
                    "prime_quote",
                    (evidence.content_hash, "finance-overview-1"),
                ),
            ),
        ),
    )
    assert verified.verified_status == "completed"
    assert [item.code for item in verified.issue_items] == [
        IssueCode.EVIDENCE_TYPE_STRIPPED,
    ]
    assert verified.issue_items[0].subject == "prime_quote"
    assert "finance_query" in verified.issue_items[0].message
    judge = _judge(True)

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=verified,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert "市场结构中性偏强" in result.public_answer
    assert "现有证据不足" not in result.public_answer


def test_financial_floor_issue_still_fails_closed_without_judge() -> None:
    """放宽只到类型白名单为止：财务锚地板（missing required evidence type）
    不在放行名单，「拿行情洗白估值锚」仍整篇 fail closed。"""

    frame, structural = _structural("当前PB为4.33倍，估值中性。")
    evidence = structural.outcome.evidence[0]
    contract = ResearchTaskContract(
        task_id="semantic-floor-fail-closed",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type="valuation_estimate",
        required_outputs=(
            RequiredOutput(
                "valuation_assessment",
                "估值判断",
                ("market_data",),
                True,
            ),
            RequiredOutput(
                "financial_business_anchor",
                "财务或业务硬数据锚点",
                ("financial_data",),
                True,
            ),
        ),
        allowed_capabilities=("market_data", "financial_data"),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    partial = verify_episode_outcome(
        contract,
        replace(
            structural.outcome,
            bindings=(
                OutputEvidenceBinding(
                    "valuation_assessment",
                    (evidence.content_hash,),
                ),
                OutputEvidenceBinding(
                    "financial_business_anchor",
                    (evidence.content_hash,),
                ),
            ),
        ),
    )
    assert partial.verified_status == "partial"
    assert any(
        item.code == IssueCode.FINANCIAL_ANCHOR_MISSING
        for item in partial.issue_items
    )
    calls: list[object] = []

    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: calls.append(request)
    ).verify(
        frame=frame,
        structurally_verified=partial,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert calls == []
    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert "现有证据不足" in result.public_answer


def test_missing_structural_contract_fails_closed_without_judge() -> None:
    frame, structural = _structural("市场当前偏弱。")
    calls: list[object] = []
    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: calls.append(request)
    ).verify(
        frame=frame,
        structurally_verified=replace(structural, contract=None),
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert calls == []
    assert "当前市场怎么看" in result.public_answer
    assert any("contract" in issue for issue in result.issues)


def test_missing_contract_never_promotes_structural_failed_status() -> None:
    frame, structural = _structural("不应公开的失败草稿。")
    assert structural.contract is not None
    failed = verify_episode_outcome(
        structural.contract,
        replace(structural.outcome, status="failed"),
    )
    assert failed.verified_status == "failed"
    calls: list[object] = []

    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: calls.append(request)
    ).verify(
        frame=frame,
        structurally_verified=replace(failed, contract=None),
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "failed"
    assert result.judge_status == "unavailable"
    assert calls == []
    assert result.public_answer == (
        "关于“当前市场怎么看？”，现有证据不足，暂不能可靠回答。"
    )
    assert any("contract" in issue for issue in result.issues)


def test_cross_turn_frame_hash_mismatch_never_reuses_a_share_outcome() -> None:
    _market_frame, structural = _structural("A股市场当前偏弱。")
    stock_frame = replace(
        _frame(),
        raw_question="瑞华泰怎么看？",
        user_goal="判断瑞华泰当前逻辑",
        subject="瑞华泰",
        subject_kind="company",
    )
    calls: list[object] = []
    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: calls.append(request)
    ).verify(
        frame=stock_frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert calls == []
    assert "瑞华泰怎么看" in result.public_answer
    assert "A股市场当前偏弱" not in result.public_answer
    assert any("hash mismatch" in issue for issue in result.issues)


def test_cross_frame_guard_never_promotes_structural_failed_status() -> None:
    _market_frame, structural = _structural("不应跨轮公开的 A 股失败草稿。")
    assert structural.contract is not None
    failed = verify_episode_outcome(
        structural.contract,
        replace(structural.outcome, status="failed"),
    )
    assert failed.verified_status == "failed"
    stock_frame = replace(
        _frame(),
        raw_question="瑞华泰怎么看？",
        user_goal="判断瑞华泰当前逻辑",
        subject="瑞华泰",
        subject_kind="company",
    )
    calls: list[object] = []

    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: calls.append(request)
    ).verify(
        frame=stock_frame,
        structurally_verified=failed,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "failed"
    assert result.judge_status == "unavailable"
    assert calls == []
    assert result.public_answer == (
        "关于“瑞华泰怎么看？”，现有证据不足，暂不能可靠回答。"
    )
    assert any("hash mismatch" in issue for issue in result.issues)


def test_contract_hash_mismatch_fails_closed_without_judge() -> None:
    frame, structural = _structural("市场当前偏弱。")
    assert structural.contract is not None
    mismatched = replace(
        structural,
        contract=replace(structural.contract, task_frame_hash="other-contract-hash"),
    )
    calls: list[object] = []
    result = SemanticEpisodeVerifier(
        judge_fn=lambda request: calls.append(request)
    ).verify(
        frame=frame,
        structurally_verified=mismatched,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert calls == []
    assert any("hash mismatch" in issue for issue in result.issues)


def test_passed_judge_records_clock_and_attempt_index() -> None:
    """R-13 顺路：passed 出口也要带时钟，不能只在 unavailable 上 attach。"""

    frame, structural = _structural("市场当前偏弱。")
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(20.0),
    )
    payload = result.to_dict()

    assert result.judge_status == "passed"
    assert isinstance(payload["timeout_asked"], float)
    assert payload["timeout_asked"] > 0.0
    assert payload["timeout_configured"] == DEFAULT_JUDGE_TIMEOUT_SECONDS
    assert isinstance(payload["remaining_seconds_at_entry"], float)
    assert payload["judge_attempt_index"] == 0


def test_repaired_judge_after_transient_retry_keeps_clock_and_attempt_index(
    monkeypatch,
) -> None:
    """活证形：repaired/passed 混过 transient 之后，三元组不能再是 None。"""

    frame, structural = _structural("市场当前偏弱。")

    class FlakyThenPass:
        def __init__(self) -> None:
            self.calls: list[float] = []

        def complete(self, *, messages, tools, timeout):
            del messages, tools
            self.calls.append(timeout)
            if len(self.calls) == 1:
                return ModelTurn(
                    "",
                    (),
                    "glm",
                    "LLM 调用失败（TimeoutError）",
                )
            return ModelTurn(
                '{"passed":true,"rejected_sentence_indexes":[],"issues":[]}',
                (),
                "glm",
                "",
            )

    model = FlakyThenPass()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    result = SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(20.0),
    )
    payload = result.to_dict()

    assert result.judge_status == "passed"
    assert len(model.calls) == 2
    assert payload["timeout_asked"] == pytest.approx(model.calls[1])
    assert payload["judge_attempt_index"] == 1
    assert payload["exc_class"] is None


def test_every_dispatched_judge_attempt_is_a_complete_attempt() -> None:
    """派发口径必须和守卫口径一致：查 50 就不能发半截。

    生产 ``run_20260820_105405_479375``：剩余 216s 过了守卫（当时阈值 25s），
    随后被派了个 12.5s 的尝试并 TimeoutError。08-20 压 prompt 后 grok 尾巴
    46.7s，完整尝试必须是整窗。
    """

    complete = complete_judge_attempt_seconds(DEFAULT_JUDGE_TIMEOUT_SECONDS)
    attempts = _semantic_attempt_timeouts(
        ResearchDeadline.from_timeout(216.0),
        configured_attempt_timeout=DEFAULT_JUDGE_TIMEOUT_SECONDS,
    )

    assert attempts, "充裕时钟下必须至少发一次"
    # 每一发都够一次完整尝试——不存在守卫会拦、却仍被派出去的窗口。
    for asked in attempts:
        assert not leftover_window_blocks_complete_attempt(
            asked, DEFAULT_JUDGE_TIMEOUT_SECONDS
        ), f"派发了守卫本会拦下的半截调用：{asked}s < {complete}s"
    assert len(attempts) <= MAX_SEMANTIC_JUDGE_ATTEMPTS


def test_judge_attempts_never_exceed_the_shared_window_in_wall_clock(
    monkeypatch,
) -> None:
    """真不变式：三发合计的**墙钟**不超总窗口，且不比旧划分更费。

    旧划分靠「报价之和 = 窗口」来保证这条；取消静态划分后，保证改由
    ``_run_judge`` 的余额账承担，所以必须用会走钟的假判官直接测墙钟。
    """

    frame, structural = _structural("市场当前偏弱。")
    window = semantic_judge_window_seconds()
    now = [1000.0]

    def monotonic() -> float:
        return now[0]

    monkeypatch.setattr(research_contract_module.time, "monotonic", monotonic)

    class BurnsItsWholeGrant:
        def __init__(self) -> None:
            self.calls: list[float] = []

        def complete(self, *, messages, tools, timeout):
            del messages, tools
            self.calls.append(float(timeout))
            now[0] += float(timeout)  # 每发都吃满自己的窗口
            return ModelTurn("", (), "glm", "LLM 调用 HTTP 503")

    model = BurnsItsWholeGrant()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    start = now[0]
    SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(600.0),
    )
    spent = now[0] - start

    assert model.calls, "至少要发一次"
    assert spent <= window + 0.01, f"判官烧了 {spent}s，超出共享窗口 {window}s"
    # 每一发都够一次完整尝试——不存在守卫会拦、却仍被派出去的半截调用。
    for asked in model.calls:
        assert not leftover_window_blocks_complete_attempt(
            asked, DEFAULT_JUDGE_TIMEOUT_SECONDS
        ), f"派发了守卫本会拦下的半截调用：{asked}s"


def test_tight_clock_keeps_a_retry_and_does_not_halve_it() -> None:
    """紧窗下重试报价仍与首发相等——修首窗时最容易顺手砍掉的就是它。

    余量按需支取：20s 窗给 (20, 20, 20)，不是 (10, 5, 5)。守卫按完整尝试
    （50s）拦发，所以 20s 剩余在生产路径会 skip；本测试只锁报价形状。
    """

    attempts = _semantic_attempt_timeouts(
        ResearchDeadline.from_timeout(20.0),
        configured_attempt_timeout=DEFAULT_JUDGE_TIMEOUT_SECONDS,
    )

    assert len(attempts) >= 2, "瞬态重试必须还在"
    assert attempts[1] == pytest.approx(attempts[0]), "重试不得只有首发的一半"
