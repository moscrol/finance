from __future__ import annotations

from dataclasses import replace
import json
import time

import pytest

from intelligence.services import answer_model, llm_refine
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    ModelToolCall,
    ModelTurn,
    OutputEvidenceBinding,
)
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
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
    contract = ResearchTaskContract(
        task_id="semantic-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
        ),
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
        bindings=(
            OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),
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
    policy = request["claim_policy"]
    assert policy["observed_facts_require_direct_evidence"] is True
    assert policy["labelled_analytical_inference_allowed"] is True
    assert policy["requested_conditional_estimate_allowed"] is True
    assert policy["unsupported_external_cause_rejected"] is True
    assert policy["unsupported_historical_probability_rejected"] is True
    assert policy["unsupported_supporting_statistics_rejected"] is True
    assert policy["unsupported_numeric_trigger_rejected"] is True
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
    assert request["output_bindings"][0]["basis"] == "user_premise"
    assert request["output_bindings"][0]["evidence_ids"] == []


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


def test_judge_receives_only_bound_evidence_with_compact_semantic_fields(
    monkeypatch,
) -> None:
    frame, structural = _structural("当前市场偏弱。")
    unbound = AgentEvidence(
        tool="web_search",
        title="不应发送给裁判的未绑定标题",
        detail="UNBOUND_EVIDENCE_SENTINEL",
        source="https://example.invalid/unbound",
        content_hash="unbound-hash",
    )
    bound = replace(
        structural.outcome.evidence[0],
        supports=("量价判断",),
        contradicts=("趋势反转",),
        independent_key="market-snapshot",
    )
    expanded = replace(
        structural.outcome,
        evidence=(bound, unbound),
    )
    structural = verify_episode_outcome(structural.contract, expanded)
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
            "evidence_ids": ["E1"],
            "gap": "",
        }
    ]
    assert request["evidence_registry"] == [
        {
            "evidence_id": "E1",
            "tool": "market_data",
            "detail": "市场成交额与结构观察",
            "source_date": "2026-07-22",
            "evidence_tier": "",
            "supports": ["量价判断"],
            "contradicts": ["趋势反转"],
            "independent_key": "market-snapshot",
        }
    ]
    serialized = json.dumps(request, ensure_ascii=False)
    assert "UNBOUND_EVIDENCE_SENTINEL" not in serialized
    assert "unbound-hash" not in serialized
    assert "HASH_PRIVATE_SENTINEL" not in serialized
    assert '"title"' not in serialized
    assert '"source"' not in serialized
    assert '"freshness"' not in serialized


def test_fulfilled_partial_model_finish_still_reaches_semantic_judge(
    monkeypatch,
) -> None:
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
    assert result.status == "partial"
    assert result.judge_status == "passed"
    assert result.verified.completion.task_coverage == "fulfilled"
    assert result.verified.outcome.gaps == ("本轮资讯检索未命中",)


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
    assert "政策变化导致了下跌" not in result.public_answer


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
    assert "证据缺口" in result.public_answer
    assert "继续成立条件" in result.public_answer
    assert result.gap_output_ids == ("continuation_conditions",)
    assert result.to_dict()["gap_output_ids"] == ["continuation_conditions"]
    assert (
        "semantic repair removed required output: continuation_conditions"
        in result.issues
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
    assert "required output lacks substantive answer: scenario_range" in (
        structural.issues
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

    assert result.status == "partial"
    assert result.judge_status == "repaired"
    assert result.gap_output_ids == ("scenario_range",)
    assert "估值情景区间" in result.public_answer
    assert "| 情景 | 关键条件 | 隐含PB |" not in result.public_answer
    assert "| 保守" not in result.public_answer
    assert "| 中性" not in result.public_answer
    assert "| 乐观" not in result.public_answer


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
    assert "现有证据已完整覆盖判断边界" not in result.public_answer


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
    assert result.status == "partial"
    assert result.judge_status == "rejected"


def test_rejected_sentence_redaction_preserves_truth_state_and_rejudges() -> None:
    frame, structural = _structural(
        "市场下跌。政策变化导致了下跌。",
        gaps=("外围催化仍待核验",),
    )
    original = structural.outcome
    judge = _judge(False, rejected=(2,), issues=("因果证据不足",))
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
        texts = [str(item["text"]) for item in request["sentences"]]
        if calls == 1:
            return {
                "passed": False,
                "rejected_sentence_indexes": [3],
                "issues": [
                    "句2包含未绑定的CPO状态。",
                    "第3句包含未绑定的创新药涨幅。",
                ],
            }
        assert texts == ["市场广度已经改善。"]
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert calls == 2
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert result.public_answer == "市场广度已经改善。"


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
        assert rejected_sentence not in texts
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert calls == 2
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert rejected_sentence not in result.verified.outcome.draft


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
    expected = "## 当前判断\n\n\n- 市场下跌。\n\n## 证据边界\n\n仍需观察。"
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


def test_second_targeted_repair_handles_claim_missed_by_first_scan() -> None:
    missed_claim = "外资将持续流入，因此反弹将延续。"
    frame, structural = _structural(f"市场下跌。政策变化导致了下跌。{missed_claim}")
    calls = 0

    def strict_judge(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "passed": False,
                "rejected_sentence_indexes": [2],
                "issues": ["外部因果无据"],
            }
        texts = [str(item["text"]) for item in request["sentences"]]
        assert "政策变化导致了下跌。" not in texts
        if calls == 2:
            assert missed_claim in texts
            return {
                "passed": False,
                "rejected_sentence_indexes": [2],
                "issues": ["复核发现仍含无据外部因果"],
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
        "市场下跌。政策导致下跌。外资将持续流入。行业一定反转。"
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


def test_terminal_redaction_preserves_reviewed_remainder_when_marker_is_removed() -> (
    None
):
    frame, structural = _structural(
        "【当前判断】市场下跌。政策导致下跌。外资将持续流入。行业一定反转。"
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
    assert "【当前判断】市场下跌" not in result.public_answer
    assert "行业一定反转" in result.public_answer
    assert "证据缺口" in result.public_answer
    assert "直接判断" in result.public_answer
    assert result.gap_output_ids == ("direct_assessment",)


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
    assert "现有证据不足" in result.public_answer
    assert "直接判断" in result.public_answer
    assert result.gap_output_ids == ("direct_assessment",)


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
    assert "证据缺口：估值的" in result.public_answer
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
        deadline=ResearchDeadline.from_timeout(5),
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
        deadline=ResearchDeadline.from_timeout(5),
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
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert len(calls) == 2
    assert all(0.0 < timeout <= 5.0 for timeout in calls)


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


def test_primary_judge_default_attempt_is_bounded_to_twenty_five_seconds(
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
    assert model.calls[0]["timeout"] == pytest.approx(25.0)


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
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")
    calls = 0

    def reject_then_late_pass(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "passed": False,
                "rejected_sentence_indexes": [2],
                "issues": ["因果证据不足"],
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
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")

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
                            "issues": ["因果证据不足"],
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
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")

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
                            "issues": ["因果证据不足"],
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
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")

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
                            "issues": ["因果证据不足"],
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
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")

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
                            "issues": ["因果证据不足"],
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
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")

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
                            "issues": ["因果证据不足"],
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
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")
    calls = 0

    def reject_then_malformed(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "passed": False,
                "rejected_sentence_indexes": [2],
                "issues": ["因果证据不足"],
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
    frame, structural = _structural("市场下跌。政策变化导致了下跌。")
    calls = 0

    def reject_then_late_malformed(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "passed": False,
                "rejected_sentence_indexes": [2],
                "issues": ["因果证据不足"],
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
        "市场下跌。资金变化导致了下跌。政策变化导致了下跌。"
    )
    calls = 0

    def reject_then_late_reject(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "passed": False,
                "rejected_sentence_indexes": [3],
                "issues": ["政策因果证据不足"],
            }
        time.sleep(0.03)
        return {
            "passed": False,
            "rejected_sentence_indexes": [2],
            "issues": ["资金因果证据不足"],
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
    assert "资金变化导致了下跌。" not in result.public_answer


def test_late_final_rejudge_preserves_twice_judged_monotonic_redaction() -> None:
    frame, structural = _structural(
        "市场下跌。政策变化导致了下跌。资金变化导致了下跌。"
    )
    calls = 0

    def reject_twice_then_late_pass(_request):
        nonlocal calls
        calls += 1
        if calls <= 2:
            return {
                "passed": False,
                "rejected_sentence_indexes": [2],
                "issues": [f"第{calls}个因果句证据不足"],
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
        "市场下跌。政策变化导致了下跌。资金变化导致了下跌。"
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
                            "issues": [f"第{self.calls}个因果句证据不足"],
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
        "市场下跌。政策变化导致了下跌。资金变化导致了下跌。"
    )
    calls = 0

    def reject_twice_then_late_malformed(_request):
        nonlocal calls
        calls += 1
        if calls <= 2:
            return {
                "passed": False,
                "rejected_sentence_indexes": [2],
                "issues": [f"第{calls}个因果句证据不足"],
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
    assert result.status == "partial"
    assert result.judge_status == "rejected"
    assert "semantic repair unavailable" in result.issues


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
    assert result.status == "partial"
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
    assert result.status == "partial"
    assert poisoned not in result.public_answer
    assert "PRIVATE_GAP_SENTINEL" not in result.public_answer
    assert "直接判断" in result.public_answer


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
    assert partial.issues == (
        "missing mandatory capability evidence: news_search",
    )
    assert result.status == "partial"
    assert result.judge_status == "passed"
    assert "本周实际上涨约3%" in result.public_answer


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
