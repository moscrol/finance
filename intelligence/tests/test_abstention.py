"""弃权率是一等读数（能力放大 spec §3.2 · P1）。

守的失败形状（2026-08-27 四臂 38 题）：组件臂未见题 10/10 全弃权，rubric 均分 11.1，
读数上看不出「它什么都没说」。这里钉三件事：弃权认得出来、原因不编造、
弃权率与均分并列而**不改任何分数字段**。
"""

from __future__ import annotations

import copy

from intelligence.eval.abstention import (
    ABSTAIN_REASONS,
    abstain_rate,
    classify_episode,
    classify_probe_receipt,
    classify_text,
)
from scripts.run_quality_ablation import (
    RUBRIC_DIMENSIONS,
    abstain_rates_by_arm,
    abstention_of,
    aggregate_components,
)

# 2026-08-27 四臂产物里逐字出现过的三种正文。
COMPONENT_REFUSAL = "该问题超出本组件臂已登记的确定性处理器，结论未知。"
C2_HONEST_REFUSAL = "2026-02-17 fact_market_daily 为 0 行；该日没有可用交易数据，不能给出涨停家数。"
COMPONENT_ANSWER = (
    "截至 2026-07-23 收盘，市场是‘指数小涨、个股普涨，但明显缩量’的反弹：上证 3876.78 点、涨 +0.25%；"
    "上涨 4260 家，涨停 116 家、跌停 2 家。全市场成交 21949.97 亿元，较前日 -17.27%，量能状态为“缩量观望”。"
    "阶段标签是“反弹阶段第 3 天”。因此基准判断是反弹仍在、宽度较好，但量能不足；"
    "若随后成交继续收缩或涨停扩散明显回落，应下调持续性判断。"
)


def test_组件臂的弃权句认出来_原因判不出就是other():
    verdict = classify_text(COMPONENT_REFUSAL)
    assert verdict.abstained is True
    assert verdict.reason == "other"
    assert any(s.startswith("marker:结论未知") for s in verdict.signals)


def test_诚实拒答也是弃权_原因是证据缺口():
    verdict = classify_text(C2_HONEST_REFUSAL)
    assert verdict.abstained is True
    assert verdict.reason == "evidence_gap"


def test_真研判不是弃权():
    assert classify_text(COMPONENT_ANSWER).abstained is False


def test_首句拒答再指路_是诚实拒答_不看总长():
    # react D8（783 字）原形：首句「没有涨停家数，因为它不是交易日」，后面讲最近可用交易日。
    text = "**2026-05-01 没有涨停家数，因为它不是交易日（劳动节休市）。**\n\n查询结果：market_daily 在 2026-05-01 无任何记录……" + COMPONENT_ANSWER * 2
    verdict = classify_text(text)
    assert verdict.abstained is True
    assert verdict.reason == "evidence_gap"
    assert "lead_sentence" in verdict.signals


def test_首句给了研判_中段的缺口说明不算弃权():
    # 8792 D5（431 字）原形：首句「属于弱轮动分支，不是主线」，第二段「检索均未返回结果，无法给出经核验的层级」。
    text = (
        "**基准判断（条件化）**：2026-06-11 当日，A股可控核聚变题材属于**弱轮动分支，不是主线**。"
        + COMPONENT_ANSWER
        + "\n**产业链环节**：本轮知识库与新闻通道检索均未返回结果，无法给出经核验的层级与个股映射，此为缺口。"
    )
    verdict = classify_text(text)
    assert verdict.abstained is False
    assert any(s == "ignored_marker:无法给出" for s in verdict.signals)


def test_短快答没有标记_是回答不是弃权():
    # 8792 C4（62 字）与组件臂 A8（51 字）原形。
    assert classify_text("fact_sector_daily 2026-07-21 MLCC 成交额 amount=611.26（表内原值，未换算）。").abstained is False
    assert classify_text("2026-07-23 市场处于“反弹阶段”第 3 天。阶段标签只描述状态，不等于保证下一天继续上涨。").abstained is False


def test_判官不可用的扣稿话术_原因是judge_blocked():
    # 8792 D2（63 字）原形。
    verdict = classify_text("本次未完成独立复核（复核服务不可用）。本轮已取得 13 条证据，暂不对外引用；可直接重试。证据数据截至 2026-07-22。")
    assert verdict.abstained is True
    assert verdict.reason == "judge_blocked"


def test_空答案与过短答案都是弃权():
    assert classify_text("").abstained is True
    assert classify_text("").reason == "other"
    assert classify_text("无法回答。").reason == "other"
    assert classify_text("无。").reason == "other"


def test_原因只能落在spec枚举里():
    for text in (COMPONENT_REFUSAL, C2_HONEST_REFUSAL, "证据不足，不下结论。", "研究截止时间已到。", ""):
        verdict = classify_text(text)
        assert verdict.abstained
        assert verdict.reason in ABSTAIN_REASONS


def _episode(*, status: str, stop_reason: str, draft: str, rejection: str = "none", evidence: int = 3) -> dict:
    return {
        "outcome": {
            "status": status,
            "stop_reason": stop_reason,
            "draft": draft,
            "evidence": [{"evidence_id": f"E{i}"} for i in range(evidence)],
        },
        "events": [
            {"kind": "task", "payload": {}},
            {
                "kind": "finish",
                "payload": {"status": status, "stop_reason": stop_reason, "rejection_code": rejection},
            },
        ],
    }


def test_episode正常终局且正文有研判_不是弃权():
    ep = _episode(status="completed", stop_reason="model_finish", draft=COMPONENT_ANSWER)
    assert classify_episode(ep).abstained is False


def test_episode截止耗尽且正文空_是deadline_exhausted():
    ep = _episode(status="partial", stop_reason="deadline_exhausted", draft="")
    verdict = classify_episode(ep)
    assert verdict.abstained is True
    assert verdict.reason == "deadline_exhausted"


def test_episode修复轮停但正文有研判_读者拿到了答案_不算弃权():
    ep = _episode(status="partial", stop_reason="repair_model_stop", draft=COMPONENT_ANSWER)
    verdict = classify_episode(ep)
    assert verdict.abstained is False
    assert "partial_with_assessment" in verdict.signals


def test_episode终局被驳回为无出处_是unsupported():
    ep = _episode(status="failed", stop_reason="invalid_model_finish", draft="", rejection="unsupported_claims")
    assert classify_episode(ep).reason == "unsupported"


def test_episode零证据且正文空_是evidence_gap():
    ep = _episode(status="failed", stop_reason="model_unavailable", draft="", evidence=0)
    assert classify_episode(ep).reason == "evidence_gap"


def test_判官扣稿是弃权_哪怕正文写得再好():
    ep = _episode(status="completed", stop_reason="model_finish", draft=COMPONENT_ANSWER)
    verdict = classify_episode(ep, gate_receipt={"judge_status": "blocked"})
    assert verdict.abstained is True
    assert verdict.reason == "judge_blocked"


def test_探针收据的terminal_phase是弃权信号_旧收据存成repr也认():
    receipt = {
        "answer_stream": "{'draft_seen': True, 'terminal_phase': 'evidence_gap_fallback'}",
        "gate_receipt": {"judge_status": "unavailable"},
    }
    verdict = classify_probe_receipt(receipt, answer="查不到该标的的可用数据。")
    assert verdict.abstained is True
    assert verdict.reason == "evidence_gap"
    assert classify_probe_receipt(receipt, answer=COMPONENT_ANSWER).abstained is False


def test_弃权率把该拒而拒和不该弃而弃分开念():
    verdicts = [
        classify_text(COMPONENT_REFUSAL),  # 不该弃
        classify_text(C2_HONEST_REFUSAL),  # 该拒
        classify_text(COMPONENT_ANSWER),
        classify_text(COMPONENT_ANSWER),
    ]
    rate = abstain_rate(verdicts, expect_refusal=[False, True, False, False])
    assert rate["n"] == 4 and rate["abstained"] == 2 and rate["abstain_rate"] == 0.5
    assert rate["n_answer_expected"] == 3
    assert rate["abstained_where_answer_expected"] == 1
    assert rate["abstain_rate_where_answer_expected"] == 0.3333
    assert rate["refusals_honored"] == 1
    assert rate["by_reason"] == {"other": 1, "evidence_gap": 1}


# ---- 接进消融壳 ----------------------------------------------------------


def _judged(total: int) -> dict[str, object]:
    base, rem = divmod(total, len(RUBRIC_DIMENSIONS))
    values = [base + (1 if i < rem else 0) for i in range(len(RUBRIC_DIMENSIONS))]
    return {"scored": True, "scores": dict(zip(RUBRIC_DIMENSIONS, values)), "total": total}


def _rec(arm: str, case_id: str, total: int, answer: str = COMPONENT_ANSWER, ok: bool = True) -> dict[str, object]:
    row: dict[str, object] = {"arm": arm, "case_id": case_id, "ok": ok, "answer": answer, "elapsed_sec": 5.0}
    row["judge"] = _judged(total) if ok else {"scored": False, "reason": "答案臂失败，未送评"}
    if not ok:
        row["error"] = "ask 超时（>420s）"
    return row


def test_旧收据没有弃权字段_按正文现算_新收据用记录里的():
    assert abstention_of(_rec("baseline", "q1", 15))["abstained"] is False
    assert abstention_of(_rec("kb-rag", "q1", 11, answer=COMPONENT_REFUSAL))["abstain_reason"] == "other"
    stamped = {**_rec("kb-rag", "q1", 11), "abstained": True, "abstain_reason": "judge_blocked"}
    assert abstention_of(stamped)["abstain_reason"] == "judge_blocked"


def test_ask超时没交卷_弃权率要数它_分数口径继续不送评():
    timed_out = _rec("kb-rag", "q1", 0, ok=False)
    verdict = abstention_of(timed_out)
    assert verdict == {"abstained": True, "abstain_reason": "deadline_exhausted", "abstain_detector": "arm_failure"}
    assert timed_out["judge"]["scored"] is False


def test_全弃权的关断臂_均分不难看_弃权率把它揪出来():
    answers = [_rec("baseline", f"q{i}", 15) for i in range(4)] + [
        _rec("kb-rag", f"q{i}", 11, answer=COMPONENT_REFUSAL) for i in range(4)
    ]
    aggregates = aggregate_components(answers, ["kb-rag"])
    ab = aggregates["kb-rag"]["abstention"]
    assert ab["baseline"]["abstain_rate"] == 0.0
    assert ab["ablated"]["abstain_rate"] == 1.0
    assert ab["ablated"]["by_reason"] == {"other": 4}
    # 分数字段一个都不许被弃权率改动：边际贡献仍是纯 rubric 分差。
    assert aggregates["kb-rag"]["marginal_contribution_total"] == 4.0
    by_arm = abstain_rates_by_arm(answers)
    assert by_arm["kb-rag"]["mean_total"] == 11.0 and by_arm["kb-rag"]["abstain_rate"] == 1.0
    assert by_arm["baseline"]["mean_total"] == 15.0 and by_arm["baseline"]["abstain_rate"] == 0.0


def test_加弃权率不改任何既有分数字段():
    answers = [_rec("baseline", f"q{i}", 14 + i) for i in range(3)] + [
        _rec("evidence-judge", f"q{i}", 12 + i) for i in range(3)
    ]
    before = copy.deepcopy(answers)
    aggregates = aggregate_components(answers, ["evidence-judge"])
    assert answers == before, "聚合不得写回记录"
    agg = aggregates["evidence-judge"]
    assert agg["marginal_contribution_total"] == 2.0
    assert agg["questions_usable"] == 3
    assert set(agg["abstention"]) == {"baseline", "ablated", "note"}
