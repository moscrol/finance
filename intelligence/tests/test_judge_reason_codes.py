"""判官理由码（2026-09-21）：把「拒绝」拆成可路由的枚举，动词与缺陷类别一一对应。

背景：39 条实测拒句里判官理由异质——事实超出证据、因果/角色越权、「凭什么排第 1」
但同句数字判官亲口说有证据、暴露「调用工具」等内部过程表述。旧规则（引了 E 且被拒
→ 删，1d9e717d2）会把移远通信公司矩阵 8 行里判官背书的 7 行连行情数字一起删。
这里钉四件事：

1. 合同：``reason_codes`` 是判官报告唯一可选键；缺码 / 未知码 / 畸形字段只影响路由，
   不作废报告；多出别的未知键仍作废（严格性不松）。
2. 路由：fact_beyond_evidence 删；unsupported_ranking 改写「优先级」格；
   internal_process_leak 改写措辞；causal_or_role_overreach / 无码 / 改写落空 → 槽位规则。
3. 账本与稿一致：记 rewritten 的句子原文不在公开稿、改写文在；``rewritten_to`` 非空。
4. 契约缝：排序题送判载荷带 ``ranking_contract``，非排序题不带该键。
"""

from __future__ import annotations

from intelligence.services import answer_model
from intelligence.services.episode_semantic_verifier import (
    _JUDGE_REPORT_TOOLS,
    VERDICT_DELETED,
    VERDICT_DEMOTED,
    VERDICT_REASON_JUDGE,
    VERDICT_REASON_STOCK_CODE,
    VERDICT_REWRITTEN,
    VERDICT_STAGE_JUDGE,
    SemanticEpisodeVerifier,
    _numbered_sentences,
)
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.task_frame import TaskFrame
from intelligence.tests.test_episode_semantic_verifier import _structural

MATRIX_HEADER = "| 公司 | 优先级 | 需求暴露 | 收入/利润传导 | 兑现时间 | 已定价程度 | 关键分歧 |"
MATRIX_SEPARATOR = "|---|---|---|---|---|---|---|"
MATRIX_ROW = "| 移远通信 | 1 | 模组出货增长（E1） | 收入增长（E1） | 2026Q4 | 中等 | 竞争 |"


def _verify(structural, frame, judge):
    return SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )


def _coded_judge(
    rejected: tuple[int, ...],
    issues: tuple[str, ...],
    reason_codes: object,
):
    """首判按给定拒句 + 理由码回；复判一律放过（改写/删完的稿不再追加账目）。"""

    calls: list[dict[str, object]] = []

    def run(request):
        calls.append(request)
        if len(calls) > 1:
            return {"passed": True, "rejected_sentence_indexes": [], "issues": []}
        payload: dict[str, object] = {
            "passed": False,
            "rejected_sentence_indexes": list(rejected),
            "issues": list(issues),
        }
        if reason_codes is not None:
            payload["reason_codes"] = reason_codes
        return payload

    run.calls = calls  # type: ignore[attr-defined]
    return run


def _judge_verdicts(result) -> dict[int, dict[str, object]]:
    return {
        int(v["sentence_index"]): v
        for v in result.sentence_verdicts
        if v["stage"] == VERDICT_STAGE_JUDGE
    }


# ————————————————————————————————————————————— 1. 合同


def test_tool_schema_exposes_optional_reason_codes_and_stays_closed() -> None:
    parameters = _JUDGE_REPORT_TOOLS[0]["function"]["parameters"]
    assert parameters["additionalProperties"] is False
    assert parameters["required"] == ["passed", "rejected_sentence_indexes", "issues"]
    codes = parameters["properties"]["reason_codes"]["items"]
    assert codes["additionalProperties"] is False
    assert codes["required"] == ["sentence_index", "code"]
    assert set(codes["properties"]["code"]["enum"]) == set(answer_model.JUDGE_REASON_CODES)


def test_report_with_reason_codes_parses_and_unrelated_extra_key_still_invalid() -> None:
    base = {"passed": False, "rejected_sentence_indexes": [2], "issues": ["第2句无证据。"]}

    report = SemanticEpisodeVerifier._parse_report(
        {**base, "reason_codes": [{"sentence_index": 2, "code": "fact_beyond_evidence"}]},
        2,
    )
    assert report is not None
    assert report.reason_codes == ((2, "fact_beyond_evidence"),)
    assert report.reason_code_by_index == {2: "fact_beyond_evidence"}
    assert report.to_dict()["reason_codes"] == [{"sentence_index": 2, "code": "fact_beyond_evidence"}]

    # 旧判官：不带该键，报告照旧有效，序列化形状与改动前逐字节相同。
    legacy = SemanticEpisodeVerifier._parse_report(dict(base), 2)
    assert legacy is not None and legacy.reason_codes == ()
    assert "reason_codes" not in legacy.to_dict()

    # 别的未知键仍作废整份报告——严格性不因新增可选键而放松。
    assert SemanticEpisodeVerifier._parse_report({**base, "confidence": 0.9}, 2) is None


def test_reason_codes_are_filtered_to_rejected_indexes_and_known_codes() -> None:
    codes = answer_model.parse_judge_reason_codes(
        [
            {"sentence_index": 2, "code": "fact_beyond_evidence"},
            {"sentence_index": 2, "code": "unsupported_ranking"},  # 同句第二条：不认
            {"sentence_index": 5, "code": "fact_beyond_evidence"},  # 不在拒句集合
            {"sentence_index": 3, "code": "made_up"},  # 未知码
            {"sentence_index": True, "code": "fact_beyond_evidence"},  # bool 不是句号
            "fact_beyond_evidence",  # 非对象条目
        ],
        allowed_indexes=(2, 3),
    )
    assert codes == ((2, "fact_beyond_evidence"),)
    assert answer_model.parse_judge_reason_codes("fact_beyond_evidence", allowed_indexes=(2,)) == ()
    assert answer_model.parse_judge_reason_codes(None, allowed_indexes=(2,)) == ()


# ————————————————————————————————————————————— 2. 路由 + 3. 账本与稿一致


def test_fact_beyond_evidence_code_deletes_cited_sentence() -> None:
    frame, structural = _structural("市场下跌（E1）。据E1显示成交额放大。")
    judge = _coded_judge(
        (2,),
        ("第2句「成交额放大」证据里没有。",),
        [{"sentence_index": 2, "code": "fact_beyond_evidence"}],
    )

    result = _verify(structural, frame, judge)

    assert "据E1显示成交额放大" not in result.public_answer
    assert "市场下跌（E1）" in result.public_answer
    verdict = _judge_verdicts(result)[2]
    assert verdict["decision"] == VERDICT_DELETED
    assert verdict["judge_reason_code"] == "fact_beyond_evidence"
    assert verdict["reasons"] == [VERDICT_REASON_JUDGE]
    assert verdict["rewritten_to"] == ""


def test_causal_overreach_code_in_required_slot_demotes_like_before() -> None:
    frame, structural = _structural("市场下跌（E1）。国标征求意见是上游订单的前置条件（E1）。")
    judge = _coded_judge(
        (2,),
        ("第2句把征求意见升级成订单前置条件，证据没有这层因果。",),
        [{"sentence_index": 2, "code": "causal_or_role_overreach"}],
    )

    result = _verify(structural, frame, judge)

    assert "国标征求意见是上游订单的前置条件" in result.public_answer
    verdict = _judge_verdicts(result)[2]
    assert verdict["decision"] == VERDICT_DEMOTED
    assert verdict["judge_reason_code"] == "causal_or_role_overreach"
    assert result.judge_status == "repaired"


def test_unknown_or_malformed_reason_codes_fall_back_to_slot_rule() -> None:
    frame, structural = _structural("市场下跌（E1）。据E1显示成交额放大。")
    for raw in (
        [{"sentence_index": 2, "code": "made_up"}],
        "fact_beyond_evidence",
        {"sentence_index": 2, "code": "fact_beyond_evidence"},
    ):
        result = _verify(
            structural,
            frame,
            _coded_judge((2,), ("第2句无证据。",), raw),
        )
        assert result.judge_status == "repaired", raw
        assert "据E1显示成交额放大" in result.public_answer, raw
        verdict = _judge_verdicts(result)[2]
        assert verdict["decision"] == VERDICT_DEMOTED, raw
        assert verdict["judge_reason_code"] == "", raw


def test_unsupported_ranking_code_marks_priority_cell_as_judgment() -> None:
    draft = "\n".join(["市场广度改善（E1）。", MATRIX_HEADER, MATRIX_SEPARATOR, MATRIX_ROW])
    frame, structural = _structural(draft)
    judge = _coded_judge(
        (4,),
        ("第4句的优先级1没有证据或透明排序规则支持；其中数字本身有E1支持，不是拒绝原因。",),
        [{"sentence_index": 4, "code": "unsupported_ranking"}],
    )

    result = _verify(structural, frame, judge)

    marked_row = MATRIX_ROW.replace("| 1 |", "| 1（研判） |")
    assert marked_row in result.public_answer
    assert MATRIX_ROW not in result.public_answer
    # 判官背书的行情数字一个不少。
    assert "模组出货增长（E1）" in result.public_answer
    verdict = _judge_verdicts(result)[4]
    assert verdict["decision"] == VERDICT_REWRITTEN
    assert verdict["judge_reason_code"] == "unsupported_ranking"
    assert verdict["rewritten_to"] == marked_row
    assert result.judge_status == "repaired"
    # 复判看到的是改写后的稿。
    second_sentences = judge.calls[1]["sentences"]  # type: ignore[attr-defined]
    assert any(item["text"] == marked_row for item in second_sentences)
    assert result.guided_retrieval.skip_reason == "rewrite_pending"


def test_unsupported_ranking_code_without_matrix_row_falls_back_to_slot_rule() -> None:
    frame, structural = _structural("市场下跌（E1）。据E1显示成交额放大。")
    judge = _coded_judge(
        (2,),
        ("第2句排序无依据。",),
        [{"sentence_index": 2, "code": "unsupported_ranking"}],
    )

    result = _verify(structural, frame, judge)

    assert "据E1显示成交额放大" in result.public_answer
    verdict = _judge_verdicts(result)[2]
    assert verdict["decision"] == VERDICT_DEMOTED
    assert verdict["judge_reason_code"] == "unsupported_ranking"
    assert verdict["rewritten_to"] == ""


def test_internal_process_leak_code_scrubs_wording_and_keeps_facts() -> None:
    frame, structural = _structural("市场下跌（E1）。本轮调用工具查询了成交额，据E1放大。")
    judge = _coded_judge(
        (2,),
        ("第2句暴露「调用工具」等内部过程表述。",),
        [{"sentence_index": 2, "code": "internal_process_leak"}],
    )

    result = _verify(structural, frame, judge)

    assert "本轮检索查询了成交额，据E1放大。" in result.public_answer
    assert "调用工具" not in result.public_answer
    verdict = _judge_verdicts(result)[2]
    assert verdict["decision"] == VERDICT_REWRITTEN
    assert verdict["rewritten_to"] == "本轮检索查询了成交额，据E1放大。"
    assert verdict["judge_reason_code"] == "internal_process_leak"


def test_internal_process_leak_code_with_residue_falls_back_to_slot_rule() -> None:
    frame, structural = _structural("市场下跌（E1）。调用工具后 provider 返回成交额放大（E1）。")
    judge = _coded_judge(
        (2,),
        ("第2句暴露内部过程表述。",),
        [{"sentence_index": 2, "code": "internal_process_leak"}],
    )

    result = _verify(structural, frame, judge)

    verdict = _judge_verdicts(result)[2]
    assert verdict["decision"] == VERDICT_DEMOTED
    assert verdict["rewritten_to"] == ""


def test_unknown_stock_code_makes_judge_rejection_mechanical() -> None:
    frame, structural = _structural("市场下跌（E1）。相关个股包括白银有色（601212）与湖南白银（002716）。")
    judge = _coded_judge((2,), ("第2句的股票代码证据里没有。",), None)

    result = _verify(structural, frame, judge)

    assert "601212" not in result.public_answer
    verdict = _judge_verdicts(result)[2]
    assert verdict["decision"] == VERDICT_DELETED
    assert VERDICT_REASON_STOCK_CODE in verdict["reasons"]


def test_stock_codes_present_in_evidence_keep_slot_rule() -> None:
    frame, structural = _structural(
        "市场下跌（E1）。相关个股包括白银有色（601212）与湖南白银（002716）。",
        detail="白银有色 601212、湖南白银 002716 领涨；成交额放大",
    )
    judge = _coded_judge((2,), ("第2句无证据。",), None)

    result = _verify(structural, frame, judge)

    assert "601212" in result.public_answer
    verdict = _judge_verdicts(result)[2]
    assert verdict["decision"] == VERDICT_DEMOTED
    assert VERDICT_REASON_STOCK_CODE not in verdict["reasons"]


# ————————————————————————————————————————————— 4. 契约缝


def _ranking_frame(frame: TaskFrame) -> TaskFrame:
    return TaskFrame(
        raw_question="英维克、申菱环境、高澜股份谁更值得优先研究？排个序",
        user_goal=frame.user_goal,
        question_type="theme_analysis",
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        market_scope=frame.market_scope,
        timeframe=frame.timeframe,
        required_outputs=frame.required_outputs,
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy=frame.evidence_policy,
        confidence=frame.confidence,
    )


def test_ranking_question_judge_request_carries_ranking_contract_block() -> None:
    frame, structural = _structural("\n".join([MATRIX_HEADER, MATRIX_SEPARATOR, MATRIX_ROW]))
    sentences = _numbered_sentences(structural.outcome.draft)
    verifier = SemanticEpisodeVerifier(judge_fn=lambda request: {"passed": True, "rejected_sentence_indexes": [], "issues": []})

    request = verifier._judge_request(_ranking_frame(frame), structural, sentences)

    block = request["ranking_contract"]
    assert block["priority_column"] == "优先级"
    assert block["priority_grounding"] == "model_reasoning"
    assert "不得仅因优先级数字无证据" in block["note"]


def test_non_ranking_question_judge_request_has_no_ranking_contract_key() -> None:
    frame, structural = _structural("市场下跌（E1）。")
    sentences = _numbered_sentences(structural.outcome.draft)
    verifier = SemanticEpisodeVerifier(judge_fn=lambda request: {"passed": True, "rejected_sentence_indexes": [], "issues": []})

    request = verifier._judge_request(frame, structural, sentences)

    assert "ranking_contract" not in request


# ————————————————————————————————————————————— 5. 与材料题判官（#770）的缝


def test_reason_codes_survive_material_claim_reconciliation() -> None:
    """材料题判官的 ``reconcile_claim_checks`` 只重建三个必填键；理由码必须原样带过。

    合并 #770 时发现的缝：材料题路径把 payload 换成 {passed, rejected, issues} 三键再送
    ``parse_grounding_judge_report``，``reason_codes`` 在那一步静默丢失，材料题的拒句
    永远走无码缺省。这里钉住：带码进、带码出；越界句号的码仍按最终拒句集合过滤。
    """

    from intelligence.tests.material_judge_helpers import material_judge_report

    request = {
        "material_claims": [
            {"claim_id": "c1", "sentence_index": 2, "kind": "material_fact",
             "material_anchors": [{"material_id": "m1", "quote": "输入"}]},
        ],
        "sentences": [{"index": 1}, {"index": 2}],
    }
    payload = material_judge_report(request, rejected=(2,), issues=("第2句超出材料。",))
    payload["reason_codes"] = [
        {"sentence_index": 2, "code": "fact_beyond_evidence"},
        {"sentence_index": 1, "code": "internal_process_leak"},  # 第 1 句没被拒：过滤掉
    ]

    report = SemanticEpisodeVerifier._parse_report(
        payload, 2, material_claims=request["material_claims"]
    )

    assert report is not None and not report.passed
    assert report.rejected_sentence_indexes == (2,)
    assert report.reason_codes == ((2, "fact_beyond_evidence"),)
    assert report.material_claim_checks and report.material_claim_checks[0]["claim_id"] == "c1"
    # 材料题必填键缺一不可；reason_codes 仍是唯一可选键，别的未知键仍作废。
    assert SemanticEpisodeVerifier._parse_report(
        {**payload, "confidence": 0.5}, 2, material_claims=request["material_claims"]
    ) is None
    payload.pop("material_claim_checks")
    assert SemanticEpisodeVerifier._parse_report(
        payload, 2, material_claims=request["material_claims"]
    ) is None
