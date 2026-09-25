"""controller 挂掉时的检索地板不能漏掉本产品的核心问法。

线上实测 ``run_20260731_175959_316535``（canary，2026-07-31 18:00）：

    turn_controller 的 LLM 调用失败
      → question_type 停在默认的 general_finance_qa
      → task_frame_requires_retrieval 落到关键词分支
      → 关键词表里**没有「A股」**（有「大盘」）→ False
      → _enforce_task_frame_route 的地板不生效
      → 兜底成 chat 车道，needs_retrieval=False
      → 用户拿到「说实话，我没办法准确预测A股明天的具体走势」

整条研究链（检索 / 门禁 / 修复轮 / judge）**一次都没跑**。这个洞只在 controller
失败时暴露，所以 13 次正常 run 全都没看到。

两道修复各修各的，不互相替代：

1. **结构性**：``required_outputs`` 里出现**超出通用默认**的产出物 ⇒ 需要检索。
   判据一直在手边——同一个 frame 的 ``required_outputs`` 是
   ``("scenario_tree",)``，一个要求产出情景树的问题不可能不需要证据。
   ch28 明确把「逐个补关键词」列为打地鼠反模式。
   （第一版按「非空」判是错的：``("direct_answer","evidence_boundary")``
   每个 frame 都有，会把「给我讲个笑话」也拖进研究车道。）
2. **补洞**：关键词表加上 A股/港股/美股。关键词分支还要服务 required_outputs
   为空的场景，洞该补还是要补。
"""
from __future__ import annotations

import pytest

from intelligence.services.task_frame import (
    TaskFrame,
    _is_financial_task,
    task_frame_requires_retrieval,
)


def _frame(
    question: str,
    *,
    required_outputs: tuple[str, ...] = (),
    question_type: str = "general_finance_qa",
    evidence_policy: str = "general_finance_evidence",
) -> TaskFrame:
    return TaskFrame(
        raw_question=question,
        question_type=question_type,
        evidence_policy=evidence_policy,
        required_outputs=required_outputs,
        user_goal="目标",
        subject=None,
        subject_kind="market",
        market_scope="a_share",
        timeframe="next_session",
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        confidence=0.5,
    )


class TestStructuralFloor:
    """required_outputs 出现算子专属产出物就必须检索——换个措辞也漏不掉。"""

    def test_the_exact_shape_that_leaked_to_chat(self) -> None:
        """线上那次的原样：controller 挂了、类型是默认值、但 frame 点名了产出物。"""
        frame = _frame(
            "你觉得a股明天会怎么走", required_outputs=("scenario_tree",)
        )

        assert task_frame_requires_retrieval(frame) is True

    @pytest.mark.parametrize(
        "question",
        [
            "你觉得明天会怎么走",  # 一个金融关键词都没有
            "接下来会怎样",
            "然后呢",  # 追问，主体在上下文里
        ],
    )
    def test_required_outputs_beat_a_keywordless_question(
        self, question: str
    ) -> None:
        """这正是关键词表永远追不上的那一类：主体不在这句话里。"""
        assert (
            task_frame_requires_retrieval(
                _frame(question, required_outputs=("scenario_tree",))
            )
            is True
        )

    def test_empty_required_outputs_still_falls_back_to_keywords(self) -> None:
        """没点名产出物时保持原行为，不把所有闲聊都拖进检索。"""
        assert (
            task_frame_requires_retrieval(_frame("今天天气如何")) is False
        )

    def test_generic_defaults_are_not_a_research_signal(self) -> None:
        """("direct_answer","evidence_boundary") 每个 frame 都有，不算信号。

        第一版按「required_outputs 非空」判，把「给我讲个笑话」也拖进了研究
        车道——既有测试 test_retrieval_floor_keeps_plain_chat_without_signals
        抓住了它。这一对是 general_knowledge / general_finance_qa 以及所有
        未映射类型的兜底值。
        """
        frame = _frame(
            "给我讲个笑话",
            required_outputs=("direct_answer", "evidence_boundary"),
        )

        assert task_frame_requires_retrieval(frame) is False

    def test_model_reasoning_policy_still_skips_retrieval(self) -> None:
        """结构性地板不能越过 evidence_policy 的明确豁免。"""
        frame = _frame(
            "帮我推一下这个逻辑",
            required_outputs=("scenario_tree",),
            evidence_policy="model_reasoning",
        )

        assert task_frame_requires_retrieval(frame) is False


class TestKeywordHole:
    """关键词分支要服务 required_outputs 为空的场景，洞该补还是要补。"""

    @pytest.mark.parametrize(
        "question",
        [
            "你觉得a股明天会怎么走",
            "A股明天怎么走",
            "a 股会不会反弹",
            "港股怎么看",
            "今晚美股会怎么走",
        ],
    )
    def test_market_names_are_recognized(self, question: str) -> None:
        assert _is_financial_task("general_finance_qa", question) is True

    def test_the_keyword_that_used_to_work_still_works(self) -> None:
        """「大盘」原先就在表里——补洞不能把已有的碰坏。"""
        assert _is_financial_task("general_finance_qa", "明天大盘怎么走") is True

    def test_genuinely_unrelated_questions_stay_out(self) -> None:
        """补洞不能把关键词表放宽成「什么都算金融」。"""
        assert _is_financial_task("general_finance_qa", "今天天气如何") is False
        assert _is_financial_task("general_finance_qa", "帮我写个排序") is False
