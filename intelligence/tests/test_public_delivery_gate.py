"""最终交付门的离线回归：重放 2026-09-22 那次「见正文」空交付。

现场（``run_20260922_191550_067475``，``comparison_analog``）：模型在自由文本里
写完了 1500+ 字的完整答案，却把结构化 ``finish`` 的 ``draft`` 填成一句指针
``见正文：……``。运行时按 ``draft`` 交付，用户只收到 154 字，``report.modules``
为 0，而 77 条证据全绑定、结构核验与语义判官都 ``passed``，``report.status``
仍写着 ``partial``——没有任何一道门能拦。

本文件不调模型、不做 IO：夹具就是那份 154 字真实正文（逐字取自该 run 的
``answer.md``）与同一轮模型自由文本里的真正文。
"""

from __future__ import annotations

import json

from intelligence.runtime.continuous_turn_adapter import ContinuousTurnResult
from intelligence.runtime.conversation_orchestrator import TurnOrchestrator
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.public_delivery_gate import (
    VERDICT_EMPTY,
    VERDICT_INCOMPLETE,
    VERDICT_OK,
    contract_output_descriptions,
    review_public_delivery,
)
from intelligence.services.research_contract import TurnIntent
from intelligence.services.run_store import RunStore
from intelligence.services.task_frame import TaskFrame
from intelligence.services.turn_controller import TurnDecision
from intelligence.tests.test_conversation_orchestrator import _prepare_turn


# 逐字取自 run_20260922_191550_067475 的 answer.md（154 字，用户实际收到的全部）。
PRODUCTION_POINTER_ANSWER = (
    "见正文：反弹第1天+主线抱团环境下，量价双红口径下半导体（设备/存储）与AI算力"
    "（CPO/算力租赁）最有机会；情绪指纹匹配的三段历史相似窗口一段续强、两段先回调，"
    "属小样本描述而非预测。个股级类比与板块历史条件比较均为缺口。\n\n"
    "已有历史观察，但尚未完成声明条件全集的历史比较；单案例和相似列表不能作为规律验证。"
)

REQUIRED_OUTPUTS = ("direct_assessment", "counterpoint", "evidence_boundary")

# 与 episode_factory._OUTPUT_DESCRIPTIONS 同源：真实契约落进 private_artifact 的那份。
CONTRACT = {
    "required_outputs": [
        {
            "output_id": "direct_assessment",
            "description": "直接回答用户问题并说明判断强度",
            "required": True,
        },
        {
            "output_id": "counterpoint",
            "description": "提供主要反证或竞争性解释",
            "required": True,
        },
        {
            "output_id": "evidence_boundary",
            "description": "说明证据覆盖范围、数据日期与缺口",
            "required": True,
        },
    ]
}

# 同一轮模型自由文本里真正写出来的正文（节选自 events.jsonl 的 model_turn）。
# 它才是本该交付的东西，交付门必须原样放行。
PRODUCTION_REAL_BODY = (
    "**直接判断（截至 2026-09-18，A股）**\n\n"
    "盘面状态：全市场成交 20764.84 亿元、环比放量 13.92%，上涨 4234 家、涨停 79 家、"
    "跌停 0 家，上证 3911.87 点（+0.94%），市场处于「反弹阶段第 1 天」、量能状态为"
    "主线抱团，行业集中于电子（31.2%）、通信、机械设备 [E3][E4][E5]。\n\n"
    "**最有机会的方向：半导体与 AI 算力**，判断强度为「量价确认过半、方向占优但非"
    "无条件」：半导体当日 +3.97%、边际量 +43.87%，半导体设备 +4.40%/边际量 +45.13%，"
    "存储芯片 +3.35%/边际量 +35.13%，三者均为「真正双红/增量启动」口径 [E19]。\n\n"
    "**反证与竞争性解释**：强势股状态已达「沸点」（平均涨幅 9.70%）[E8]，历史上沸点后"
    "常见兑现/分化；半导体设备等当日边际量 45% 级别的放量也可解读为短期情绪透支而非"
    "增量行情起点。\n\n"
    "**证据边界**：数据截至 2026-09-18（今日为 09-22，无更新盘面）；历史类比仅 3 个"
    "样本、属描述性小样本而非概率；本轮个股级走势类比不可用（gap，见 E2）。"
)


def _descriptions() -> dict[str, str]:
    return contract_output_descriptions(CONTRACT)


def test_production_pointer_answer_is_not_delivered_as_a_normal_answer() -> None:
    """真实坏答案必须被判为「正文没随本轮送达」，而不是一次普通的 partial 交付。"""

    receipt = review_public_delivery(
        PRODUCTION_POINTER_ANSWER,
        required_outputs=REQUIRED_OUTPUTS,
        descriptions=_descriptions(),
    )

    assert receipt.verdict == VERDICT_EMPTY
    assert receipt.answer_status == "missing"
    assert receipt.dangling_pointers == ("见正文",)
    assert set(receipt.missing_outputs) == {"direct_assessment", "evidence_boundary"}
    # 悬空指引本身不得留在公开正文里（它指的东西用户看不到），但指引后面的结论
    # 必须原样保留——不得把正文里唯一的实质内容一起抹掉。
    assert not receipt.text.startswith("见正文")
    assert "半导体（设备/存储）与AI算力" in receipt.text
    assert "直接回答用户问题并说明判断强度" in receipt.text
    assert "说明证据覆盖范围、数据日期与缺口" in receipt.text


def test_real_model_body_passes_unchanged() -> None:
    """同一轮真正写出来的正文必须原样放行：门是拦空壳的，不是拦长答案的。"""

    receipt = review_public_delivery(
        PRODUCTION_REAL_BODY,
        required_outputs=REQUIRED_OUTPUTS,
        descriptions=_descriptions(),
    )

    assert receipt.verdict == VERDICT_OK
    assert receipt.answer_status is None
    assert receipt.text == PRODUCTION_REAL_BODY


def test_missing_markers_alone_never_degrades_a_substantial_answer() -> None:
    """钥匙 2 单独命中不许降级——否则「措辞不同但内容完整」会被误伤。

    这段是自然段落写法：没有「直接判断 / 反证 / 证据边界」任何一个标记词，
    marker 覆盖率必然报 absent，但正文体量充足且没有悬空指引。08-01 验收 C5 的
    失分形状（24 条证据全绑定，只因少一个标记词整篇被换成缺口模板）不得复发。
    """

    natural = (
        "半导体设备与存储芯片是本轮最值得跟的方向。9 月 18 日半导体设备上涨 4.40%，"
        "成交较前一日放大 45.13%，存储芯片上涨 3.35%、放量 35.13%，两者在 9 月 15 日至"
        "9 月 18 日之间已经连续三个交易日量价同向，不是单日脉冲。\n\n"
        "换个角度看也有不利的一面。强势股平均涨幅已经到 9.70%，历史上这个位置常出现"
        "兑现和分化；45% 级别的单日放量同样可以读成情绪透支，而不是增量资金进场。"
        "这两种读法目前都没有被盘面证伪。\n\n"
        "能说到哪一步也要讲清楚：行情口径只到 9 月 18 日，9 月 19 日之后的盘面本轮"
        "没有取到；历史相似窗口只有 3 段，样本太小，只能当描述用，不能当概率用；"
        "个股层面的走势对照这次没有跑出来。"
    )

    receipt = review_public_delivery(
        natural,
        required_outputs=REQUIRED_OUTPUTS,
        descriptions=_descriptions(),
    )

    assert receipt.missing_outputs  # 钥匙 2 确实命中了
    assert receipt.verdict == VERDICT_OK
    assert receipt.text == natural


def test_short_but_honest_answers_are_not_blocked() -> None:
    """短而诚实的答案不得被判死——两条常数都是这么拍红的。

    两份文本逐字取自现有测试夹具（``test_conversation_orchestrator`` 与
    ``test_workbench_research_project``）。第一版的「体量下限」与「绝对下限 24
    字」分别把它们判成了 incomplete / empty。这条把那两次拍红固定下来：
    谁想把长度重新升级成钥匙，先得让这条红。
    """

    quick_fact = "2026Q2 单季营收 375.75 亿元（计算编号 0123456789abcdef）。"
    terse_research = "**第1轮判断：光模块主线延续。**\n证据见公告。"

    quick = review_public_delivery(
        quick_fact,
        required_outputs=("direct_assessment",),
    )
    terse = review_public_delivery(
        terse_research,
        required_outputs=("direct_assessment", "evidence_boundary"),
    )

    assert quick.missing_outputs and terse.missing_outputs  # marker 确实没命中
    assert quick.verdict == VERDICT_OK
    assert terse.verdict == VERDICT_OK
    assert quick.text == quick_fact
    assert terse.text == terse_research


def test_pointer_only_body_has_no_deliverable() -> None:
    """正文只剩一句指引：实质字符不足，直接判空。"""

    receipt = review_public_delivery(
        "见正文。",
        required_outputs=REQUIRED_OUTPUTS,
        descriptions=_descriptions(),
    )

    assert receipt.verdict == VERDICT_EMPTY
    assert receipt.answer_status == "missing"
    assert "no_substantive_body" in receipt.reasons


def test_runtime_gap_template_is_exempt_without_output_contract() -> None:
    """无输出契约的自由问答仍可诚实交付缺口模板。"""

    template = "关于A股，现有证据不足，暂不能给出可靠结论。"
    receipt = review_public_delivery(template)

    assert receipt.verdict == VERDICT_OK
    assert receipt.reasons == ("gap_template_exempt",)
    assert receipt.text == template


def test_gap_template_cannot_satisfy_required_outputs() -> None:
    """有明确必答项时，「证据不足」不能把全缺答案伪装成 ok。"""

    template = (
        "关于A股，现有证据不足，暂不能给出可靠结论。"
        "仍需核验：直接回答用户问题并说明判断强度、提供主要反证或竞争性解释。"
    )
    receipt = review_public_delivery(
        template,
        required_outputs=REQUIRED_OUTPUTS,
        descriptions=_descriptions(),
    )

    assert receipt.verdict != VERDICT_OK
    assert "gap_template_exempt" not in receipt.reasons
    assert receipt.missing_outputs


def test_boundary_only_body_is_incomplete() -> None:
    """判断槽无词表可检、正文只剩边界与免责：既有观测信号升级成可执行判定。

    ``evaluate_marker_coverage`` 早就会为这种形状打出
    ``uncheckable_judgment_empty`` 并把 ``observation_only`` 置 False——信号一直
    在，只是没人接。正文刻意写到体量下限以上，好把这条规则与体量规则分开钉。
    """

    boundary_only = (
        "数据截至 2026-09-18，9 月 19 日之后的盘面本轮未取得。"
        "证据覆盖范围仅限当日结构化行情，不含盘中分时与资金流向。"
        "历史类比的证据缺口未补齐，相似窗口只跑出 3 段。"
        "本轮没有独立证据可以交叉验证板块层面的历史条件比较。"
        "数据日期与问句日之间相差 4 个自然日，跨周末的口径差异未做校正。"
        "单一样本的相似度不等同于后续走势的可重复性。"
        "本回答不构成投资建议。"
    )

    receipt = review_public_delivery(
        boundary_only,
        required_outputs=("direct_answer", "evidence_boundary"),
        descriptions={"direct_answer": "直接回答用户问题"},
    )

    assert receipt.verdict == VERDICT_INCOMPLETE
    assert receipt.answer_status == "partial"
    assert "judgment_slot_empty" in receipt.reasons


def test_mid_text_pointer_with_full_coverage_is_not_blocked() -> None:
    """长答案中段出现「详见正文」但必需输出齐备：单把钥匙不拦。"""

    body = PRODUCTION_REAL_BODY + "\n\n更细的分板块拆解详见正文附表。"

    receipt = review_public_delivery(
        body,
        required_outputs=REQUIRED_OUTPUTS,
        descriptions=_descriptions(),
    )

    assert receipt.dangling_pointers  # 形态钥匙命中
    assert not receipt.missing_outputs  # 覆盖钥匙没命中
    assert receipt.verdict == VERDICT_OK


def test_no_required_outputs_still_catches_an_empty_body() -> None:
    """契约没声明必需输出时，绝对下限仍然生效。"""

    receipt = review_public_delivery("见正文", required_outputs=())

    assert receipt.verdict == VERDICT_EMPTY
    assert receipt.required_output_count == 0


def _frame(query: str) -> TaskFrame:
    return TaskFrame(
        raw_question=query,
        user_goal="判断当前最有机会的方向",
        question_type="comparison_analog",
        subject="A股",
        subject_kind="market",
        market_scope="A股",
        timeframe="当前",
        required_outputs=REQUIRED_OUTPUTS,
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="market_structure_evidence",
        confidence=0.9,
    )


def test_continuous_turn_report_records_the_gate_and_drops_answer_status(
    tmp_path,
) -> None:
    """端到端重放：同样的 154 字交付，报告不得再写成一次干净的 partial。

    这一条钉的是接线位置——门必须在 ``complete_report`` 之前、且看到的是用户
    真正读到的那段正文（视角头 / 复核意见 / 删句闸之后）。
    """

    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "现在最有机会的方向是什么，历史上有没有相似阶段"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )
    frame = _frame(query)
    intent = TurnIntent(
        primary_subject=frame.subject,
        secondary_topics=(),
        question_type=frame.question_type,
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
        timeframe=frame.timeframe,
        required_outputs=frame.required_outputs,
        task_frame_hash=frame.task_frame_hash,
    )

    def controller(_query: str, **_kwargs: object) -> TurnDecision:
        return TurnDecision(
            lane="research",
            needs_retrieval=True,
            needs_memory=False,
            needs_template=True,
            question_type=frame.question_type,
            capabilities=("market_data",),
            task_frame=frame,
            turn_intent=intent,
        )

    class Adapter:
        def handle(self, *, frame: TaskFrame, control):  # noqa: ARG002
            return ContinuousTurnResult(
                handled=True,
                status="partial",
                answer=PRODUCTION_POINTER_ANSWER,
                as_of="2026-09-18",
                citations=(),
                warnings=(),
                private_artifact={
                    "contract": CONTRACT,
                    "events": [
                        {
                            "kind": "task",
                            "payload": {"task_frame_hash": frame.task_frame_hash},
                        }
                    ],
                    "semantic_verifier": {"judge_status": "passed", "issues": []},
                },
                events=(),
            )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy dependency must not run")

    orchestrator = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=forbidden,
        route_skills_fn=forbidden,
        lane_answer_fn=forbidden,
        turn_controller_fn=controller,
        continuous_turn_adapter=Adapter(),
    )
    orchestrator.run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    gate = report["public_delivery_gate"]
    assert gate["verdict"] == VERDICT_EMPTY
    assert set(gate["missing_outputs"]) == {"direct_assessment", "evidence_boundary"}
    # 既有观测字段仍在，且仍是观测——判定权归交付门。
    assert report["answer_marker_coverage"]["observation_only"] is True
    assert report["answer_status"] == "missing"
    assert report["status"] == "missing"
    assert "public_delivery_gate:empty" in report["warnings"]

    answer = (run_store.run_dir(run_id) / "answer.md").read_text(encoding="utf-8")
    assert not answer.startswith("见正文")
    assert "【交付自检】" in answer
