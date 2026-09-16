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
    timeframe: str = "next_session",
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
        timeframe=timeframe,
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


class TestExplicitDateFloor:
    """带完整日历日期的金融题不可能靠模型记忆回答——第三道结构性地板。

    线上实测 ``run_20260827_184531_798332``（P0 D6 复跑，2026-08-27）：

        「2026-07-22 高标股的晋级情况如何，有没有出现空档」
          → controller LLM 回话但解析失败（unparsable_response）
          → question_type 停在默认 general_finance_qa
          → required_outputs 恰好是通用默认对 → 空差集，结构性地板不触发
          → 关键词分支：「高标股/晋级/空档」全不在表里 → False
          → 地板不生效 → chat 车道零检索 →「我答不了，去看开盘啦」

    这正是本文件开头引用的 ch28「打地鼠」预言的又一轮：8-13 补过
    涨停/连板，这次输的是高标股/晋级/空档。补的不再是词，是结构化信号：
    ``timeframe`` / 题面里的完整日期（``has_explicit_date`` 的 docstring
    自己就说它是最强时效信号）。训练语料里不会有 2026-07-22 的连板梯队。
    """

    def test_the_d6_shape_that_leaked_to_chat(self) -> None:
        """线上那次的原样：黑话题面 + understand_query 已抽出的 timeframe。"""
        frame = _frame(
            "2026-07-22 高标股的晋级情况如何，有没有出现空档",
            required_outputs=("direct_answer", "evidence_boundary"),
            timeframe="2026-07-22",
        )

        assert task_frame_requires_retrieval(frame) is True

    def test_date_in_the_question_alone_is_enough(self) -> None:
        """timeframe 抽取失败时，题面里的完整日期兜底。"""
        frame = _frame("2026年7月22日高标股晋级怎么样")

        assert task_frame_requires_retrieval(frame) is True

    def test_month_granularity_is_not_an_explicit_date(self) -> None:
        """判据是完整年月日，不是「出现 20xx」——月份粒度保持原行为。"""
        frame = _frame("2026年7月 高标股晋级情况如何", timeframe="2026-07")

        assert task_frame_requires_retrieval(frame) is False

    def test_model_reasoning_policy_still_beats_explicit_date(self) -> None:
        """日期地板与结构性地板一样，不越过 evidence_policy 的明确豁免。"""
        frame = _frame(
            "帮我推一下 2026-07-22 那个逻辑",
            evidence_policy="model_reasoning",
            timeframe="2026-07-22",
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
