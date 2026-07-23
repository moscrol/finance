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
from intelligence.services.evidence_capabilities import EvidencePlan
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
    assert "外部因果" in system_prompt
    assert "任意触发阈值" in system_prompt
    assert "从第1句检查到最后一句" in system_prompt
    assert "一次返回全部不合格句号" in system_prompt


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
    assert result.status == "completed"
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


def test_rejudge_rejects_an_unsupported_claim_missed_by_first_scan() -> None:
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
        assert missed_claim in texts
        return {
            "passed": False,
            "rejected_sentence_indexes": [2],
            "issues": ["复核发现仍含无据外部因果"],
        }

    result = SemanticEpisodeVerifier(judge_fn=strict_judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert calls == 2
    assert result.status == "partial"
    assert result.judge_status == "rejected"
    assert missed_claim not in result.public_answer


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


def test_late_rejudge_pass_is_unavailable_and_cannot_complete() -> None:
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
    assert result.status == "partial"
    assert result.judge_status == "unavailable"
    assert any("deadline" in issue for issue in result.issues)


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
