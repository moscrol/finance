"""gap 答案的中间档：缺 X → 仍可判 Y → 验证窗口 Z。

背景：原版 `_gap_answer` 只说「证据不足 + 仍需核验 X」，把「一格没核验」和
「全军覆没」呈现成同一句话（knevo 对照：从不输出裸的「不知道」；08-01 验收
C 组诚实度失分同源）。升级后追加两段**纯结构性事实**：已 fulfilled 槽位及其
绑定证据数（Y）、证据最新来源日期（Z）。

红线由测试钉住：Y/Z 一个字都不来自 draft——gap 答案出现的场合正是 draft
被拒的场合，捞正文等于绕过语义门禁。
"""
from __future__ import annotations

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
    _latest_evidence_date,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchTaskContract,
)
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
        required_outputs=("direct_assessment", "invalidation_conditions"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def _verified(draft: str = "市场偏弱，观察缩量。"):
    """一格 fulfilled（绑 2 条证据）+ 一格空 binding → partial。"""
    frame = _frame()
    evidence = (
        AgentEvidence(
            tool="market_data",
            title="A股市场快照",
            detail="成交额 21949 亿",
            source="行情快照",
            source_date="2026-08-11",
            content_hash="hash-a",
        ),
        AgentEvidence(
            tool="market_data",
            title="涨停结构",
            detail="涨停 116 家",
            source="行情快照",
            source_date="2026-08-12",
            content_hash="hash-b",
        ),
    )
    contract = ResearchTaskContract(
        task_id="gap-middle-tier-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
            RequiredOutput(
                "invalidation_conditions", "失效条件", ("market_data",), True
            ),
        ),
        allowed_capabilities=("market_data",),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="partial",
        draft=draft,
        evidence=evidence,
        traces=(),
        gaps=("失效条件证据不足",),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
        ),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("hash-a", "hash-b")),
            OutputEvidenceBinding(
                "invalidation_conditions", (), gap="证据不足"
            ),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    return frame, verify_episode_outcome(contract, outcome)


class TestGapAnswerMiddleTier:
    def test_names_missing_kept_and_window(self):
        frame, verified = _verified()
        answer = SemanticEpisodeVerifier._gap_answer(frame, verified)

        assert "现有证据不足" in answer
        assert "仍需核验：失效条件" in answer
        assert "本轮已核验" in answer
        assert "直接判断（2 条证据）" in answer
        assert "证据数据截至 2026-08-12" in answer

    def test_labels_take_only_the_first_clause_of_long_descriptions(self):
        """#293 起描述带面向模型的长指令；gap 标签只取首个分句，
        不把指令文本打到用户可见正文（08-12 A 组第二轮实测形状）。"""
        from dataclasses import replace

        frame, verified = _verified()
        contract = verified.contract
        assert contract is not None
        long_desc = replace(
            contract,
            required_outputs=tuple(
                replace(
                    item,
                    description=(
                        "列出与结论直接相关的支持证据；证据中的关键数值须"
                        "原样写进正文，不得只作定性概括"
                    ),
                )
                if item.output_id == "invalidation_conditions"
                else item
                for item in contract.required_outputs
            ),
        )
        answer = SemanticEpisodeVerifier._gap_answer(
            frame, replace(verified, contract=long_desc)
        )
        assert "仍需核验：列出与结论直接相关的支持证据。" in answer
        assert "不得只作定性概括" not in answer

    def test_kept_section_never_quotes_the_draft(self):
        """红线：Y 段只用契约描述与计数，draft 原文一个字不进 gap 答案。"""
        frame, verified = _verified(draft="市场偏弱，观察缩量。")
        answer = SemanticEpisodeVerifier._gap_answer(frame, verified)
        assert "市场偏弱" not in answer
        assert "观察缩量" not in answer

    def test_unbound_evidence_is_reported_as_count_only(self):
        """LLM 超时打断（有证据、零绑定）时报条数——区分「没查到」和
        「查到了没来得及核验」（08-12 A5：25 条证据、repair_model_unavailable）。"""
        from dataclasses import replace

        frame, verified = _verified()
        no_bindings = replace(
            verified,
            outcome=replace(verified.outcome, bindings=()),
        )
        answer = SemanticEpisodeVerifier._gap_answer(frame, no_bindings)
        assert "已取得 2 条证据" in answer
        assert "未完成核验绑定" in answer
        assert "本轮已核验" not in answer

    def test_judge_unavailable_does_not_claim_unbound_or_empty_evidence(self):
        """§5.3 B2：判官挂了证据却在，禁语不得进 gap_body。"""

        from dataclasses import replace

        frame, verified = _verified()
        no_bindings = replace(
            verified,
            outcome=replace(verified.outcome, bindings=()),
        )
        answer = SemanticEpisodeVerifier._gap_answer(
            frame,
            no_bindings,
            judge_unavailable=True,
        )
        assert "复核服务不可用" in answer
        assert "现有证据不足" not in answer
        assert "未完成核验绑定" not in answer
        assert "已取得 2 条证据" in answer
        assert "复核服务超时" not in answer

    def test_no_contract_keeps_the_bare_sentence(self):
        from dataclasses import replace

        frame, verified = _verified()
        answer = SemanticEpisodeVerifier._gap_answer(
            frame, replace(verified, contract=None)
        )
        assert answer == "关于“当前市场怎么看？”，现有证据不足，暂不能可靠回答。"


def _verified_invalid_repair(*, draft: str = "", keep_fulfilled: bool = False):
    from dataclasses import replace

    frame, verified = _verified(draft=draft or "占位")
    assert verified.contract is not None
    outcome = replace(
        verified.outcome,
        stop_reason="invalid_repair_finish",
        draft=draft,
        bindings=verified.outcome.bindings if keep_fulfilled else (),
    )
    return frame, verify_episode_outcome(verified.contract, outcome)


class TestInvalidRepairFinishIsNotEvidenceGap:
    def test_opening_is_verification_incomplete(self):
        frame, verified = _verified_invalid_repair(draft="")
        answer = SemanticEpisodeVerifier._gap_answer(frame, verified)
        assert "本轮核验未完成" in answer
        assert "现有证据不足" not in answer
        assert "【结构缺口】" not in answer
        assert "这次还核验不了：直接判断。" in answer
        assert "这次还核验不了：失效条件。" in answer
        assert "已取得 2 条证据" in answer

    def test_fulfilled_draft_sentence_is_kept(self):
        frame, verified = _verified_invalid_repair(
            draft="液冷服务器当日跌 1.11%。",
            keep_fulfilled=True,
        )
        answer = SemanticEpisodeVerifier._gap_answer(frame, verified)
        assert "液冷服务器当日跌 1.11%。" in answer
        assert "这次还核验不了：失效条件。" in answer
        assert "现有证据不足" not in answer
        assert "【结构缺口】" not in answer


class TestLatestEvidenceDate:
    def test_picks_the_max_iso_date(self):
        _frame_, verified = _verified()
        assert _latest_evidence_date(verified.outcome.evidence) == "2026-08-12"

    def test_ignores_non_iso_source_dates(self):
        evidence = (
            AgentEvidence(
                tool="web_search",
                title="t",
                detail="d",
                source="s",
                source_date="上周·某媒体",
            ),
        )
        assert _latest_evidence_date(evidence) == ""
