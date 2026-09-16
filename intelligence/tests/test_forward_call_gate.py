"""出口硬门：「明天哪个方向」的答案不得是领涨 / 方向判断（2026-09-07，D9 读数）。

依据：max 形状 D 组批跑，D9「2026-07-22 盘后，明天开盘哪个方向会先起来」被答成
「7月23日开盘最可能先动的是电力—风电链，次选贵金属」，判官放行；08-27 产品臂同题 0.5。
产品红线（终局 spec §2）：「第二天的方向」一律翻译成观察剧本，不预测涨跌。

门开在 ``admit_finish``（09-02 spec：出口唯一硬层），词表住 ``compliance_gate``。三件事要钉：
① 问句侧判据只认「明天 + 方向 / 走势」两组都命中——「长电科技怎么看」不归它管；
② 答案侧按子句扫，条件句免检——观察剧本自己的升级 / 降级条件不能被拦；
③ 拒收是可修正的回灌（SUBSTANCE），第二稿改成剧本形状就过；且 harness 的
   ``admit_finish`` 与 Episode loop 走的是同一条门。
"""

from __future__ import annotations

from datetime import date
import json

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services import compliance_gate as cg
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.episode_protocol import (
    REJECTION_KINDS,
    EpisodeFinishRejection,
    RejectionKind,
    forward_direction_call_hits,
    validate_episode_finish,
)
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.research_contract import (
    InformationCutoff,
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.task_frame import TaskFrame
from intelligence.tests.test_agent_episode import (  # noqa: E402  复用脚本模型与行情夹具
    ScriptedModel,
    _market_registry,
    _successful_runner,
)

D9_QUESTION = "2026-07-22 盘后，明天开盘哪个方向会先起来"
D9_DRAFT = (
    "**基准判断：7月23日开盘最可能先动的是“电力—风电”链，风格偏短线连板与低位补涨；"
    "次选贵金属/有色。**\n依据是：7月22日成交额26531.66亿元、环比缩量10.27%；电力当日有7家涨停。"
)
SCRIPT_DRAFT = (
    "明天要看的变量：① 电力板块涨停家数是否维持在 5 家以上，若成交额环比放大 10% 以上视为升级；"
    "② 若明天开盘半导体高开且封板数回到 3 家以上，算作修复信号；"
    "③ 贵金属连续加速后出现放量滞涨则降级。以上是观察项，不是投资建议。"
)


# ---------------------------------------------------------------------------
# ① 问句侧
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        D9_QUESTION,
        "你觉得A股明天会怎么走",
        "明天买什么板块好",
        "下个交易日哪个题材先动",
    ],
)
def test_next_day_direction_questions_are_recognised(question: str) -> None:
    assert cg.is_next_day_direction_question(question)


@pytest.mark.parametrize(
    "question",
    [
        "2026-07-22 收盘了，今天盘面整体是个什么情况",
        "长电科技怎么看",
        "明天有什么重要会议",
        "华工科技这只票现在什么情况",
        "如果明天放量，题材会怎么演化",  # 情景问法，不是挑方向；宁可漏不可滥
    ],
)
def test_other_questions_are_left_alone(question: str) -> None:
    assert not cg.is_next_day_direction_question(question)


# ---------------------------------------------------------------------------
# ② 答案侧
# ---------------------------------------------------------------------------


def test_d9_lead_sentence_is_a_forward_call() -> None:
    hits = cg.forward_call_hits(D9_DRAFT)
    assert hits and hits[0].code == cg.E_FORWARD_CALL
    assert "最可能先动" in hits[0].term
    assert hits[0].hint.startswith("不判断明天哪个方向")


@pytest.mark.parametrize(
    "sentence",
    ["预计明天将反弹", "首选方向是电力", "领涨的板块是半导体", "明天大盘会上涨", "次日大概率高开"],
)
def test_forward_call_shapes_are_caught(sentence: str) -> None:
    assert cg.forward_call_hits(sentence)


@pytest.mark.parametrize(
    "sentence",
    [
        SCRIPT_DRAFT,
        "电力今天涨停 7 家，梯队完整",
        "若明天开盘半导体高开，视为升级信号",
        "预期明天流动性会改善",  # 不是价格方向
        "明天要观察贵金属是否放量滞涨",
        # 下面两句**去掉条件词就是判断**——条件句免检这一层是靠它们钉住的。
        "若明天大盘会上涨，则把电力视为升级",
        "如果次日大概率高开，降级处理",
    ],
)
def test_observation_language_and_conditions_pass(sentence: str) -> None:
    assert cg.forward_call_hits(sentence) == []


def test_conditional_exemption_is_load_bearing() -> None:
    """同一句去掉条件词就命中：证明免检层真在工作，不是句子本来就不命中。"""

    assert cg.forward_call_hits("明天大盘会上涨，则把电力视为升级")
    assert cg.forward_call_hits("若明天大盘会上涨，则把电力视为升级") == []


def test_scan_can_opt_into_the_forward_call_code_but_script_codes_do_not_include_it() -> None:
    assert cg.E_FORWARD_CALL not in cg.OBSERVATION_SCRIPT_CODES
    assert [h.code for h in cg.scan(D9_DRAFT, codes=(cg.E_FORWARD_CALL,))] == [cg.E_FORWARD_CALL]
    assert cg.scan(D9_DRAFT) == []  # 旧词表不认领涨判断——这正是 D9 漏掉的原因


# ---------------------------------------------------------------------------
# ③ admit_finish：拒收可修正、同门
# ---------------------------------------------------------------------------


def _frame(question: str) -> TaskFrame:
    return TaskFrame(
        raw_question=question,
        user_goal="形成对次日开盘强势方向的条件化判断，并说明证据边界",
        question_type="general_finance_qa",
        subject="A股市场",
        subject_kind="market",
        market_scope="A股",
        timeframe="2026-07-22",
        required_outputs=("direct_answer",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="general_finance_evidence",
        confidence=0.9,
    )


def _context(question: str) -> ResearchRunContext:
    frame = _frame(question)
    policy = ResearchPolicy.for_tier("max")
    return ResearchRunContext(
        contract=ResearchTaskContract(
            task_id=f"forward-gate-{abs(hash(question)) % 10**8}",
            question=question,
            subject=frame.subject,
            subject_kind=frame.subject_kind,
            question_type=frame.question_type,
            required_outputs=(RequiredOutput("direct_answer", "直接回答", ("market_data",), True),),
            allowed_capabilities=("market_data",),
            research_tier="max",
            freshness="current",
            timeframe=frame.timeframe,
            evidence_plan=EvidencePlan(),
            task_frame_hash=frame.task_frame_hash,
        ),
        deadline=ResearchDeadline.from_timeout(policy.total_seconds, synthesis_reserve=policy.synthesis_reserve),
        policy=policy,
        trace_parent_id="forward-gate",
        today="2026-07-22",
        latest_data_date="2026-07-22",
        information_cutoff=InformationCutoff(date(2026, 7, 22), "requested"),
    )


def _finish(draft: str, hashes: tuple[str, ...] = ("evidence-1",)) -> str:
    return json.dumps(
        {
            "status": "completed",
            "draft": draft,
            "gaps": [],
            "bindings": [{"output_id": "direct_answer", "evidence_hashes": list(hashes), "gap": ""}],
        },
        ensure_ascii=False,
    )


def _evidence():
    evidence, _obs, _trace = _successful_runner("总览", None)  # type: ignore[arg-type]
    return tuple(evidence)


def test_validate_finish_rejects_a_forward_call_for_a_next_day_question() -> None:
    with pytest.raises(EpisodeFinishRejection) as excinfo:
        validate_episode_finish(_finish(D9_DRAFT), context=_context(D9_QUESTION), evidence=_evidence())
    assert excinfo.value.code == "forward_direction_call"
    assert excinfo.value.kind is RejectionKind.SUBSTANCE
    assert REJECTION_KINDS["forward_direction_call"] is RejectionKind.SUBSTANCE
    message = str(excinfo.value)
    for must in ("观察剧本", "升级条件", "不是投资建议", "最可能先动"):
        assert must in message


def test_validate_finish_accepts_the_same_draft_for_a_non_forward_question() -> None:
    """门只对「问明天方向」的题开：同一段话答别的题不归它管。"""

    finish = validate_episode_finish(
        _finish(D9_DRAFT), context=_context("2026-07-22 收盘了，今天盘面整体是个什么情况"), evidence=_evidence()
    )
    assert finish.status == "completed"


def test_validate_finish_accepts_an_observation_script_for_the_next_day_question() -> None:
    finish = validate_episode_finish(_finish(SCRIPT_DRAFT), context=_context(D9_QUESTION), evidence=_evidence())
    assert finish.status == "completed"
    assert forward_direction_call_hits(SCRIPT_DRAFT, question=D9_QUESTION) == ()


def test_harness_admit_finish_walks_through_the_same_gate() -> None:
    admission = FinanceResearchHarness().admit_finish(
        _finish(D9_DRAFT), context=_context(D9_QUESTION), evidence=_evidence(), registry=_market_registry(_successful_runner)
    )
    assert not admission.accepted
    assert admission.rejection["rejection_code"] == "forward_direction_call"
    assert admission.response is not None and admission.response.reinject


def test_episode_reinjects_the_rewrite_hint_and_accepts_the_second_script_shaped_draft() -> None:
    """有牙的一对：第一稿领涨判断被拒并回灌改写提示，第二稿剧本形状通过；事件里留下病因。"""

    model = ScriptedModel(
        [
            ModelTurn("", (ModelToolCall("c1", "market_data", {"query": "总览"}),), "scripted", ""),
            ModelTurn(_finish(D9_DRAFT), (), "scripted", ""),
            ModelTurn(_finish(SCRIPT_DRAFT), (), "scripted", ""),
        ]
    )
    outcome = ContinuousAgentEpisode(model).run(
        task_frame=_frame(D9_QUESTION), context=_context(D9_QUESTION), registry=_market_registry(_successful_runner)
    )
    assert outcome.status == "completed", outcome.stop_reason
    assert outcome.draft.startswith("明天要看的变量")
    invalid = [e for e in outcome.events if e.kind == "invalid_action"]
    assert len(invalid) == 1 and invalid[0].payload["code"] == "forward_direction_call"
    assert invalid[0].payload["kind"] == "substance"
    # 第三次模型调用前，模型看到了改写提示。
    reinjected = str(model.calls[2]["messages"][-1])
    assert "观察剧本" in reinjected and "最可能先动" in reinjected
