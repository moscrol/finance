"""R6 first-submission failures, reduced without changing the sealed answers.

Source: 8792-financial-live-r6-20260918/{quality-review.json,cases/*/public-message.json}.
Offline behavioral checks, not a new live acceptance or an oracle for causality.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from intelligence.services import llm_refine
from intelligence.services.agent_research import AgentEvidence, StructuredObservation
from intelligence.services.agent_runtime import EpisodeEvent, OutputEvidenceBinding
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.research_contract import RequiredOutput, ResearchDeadline
from intelligence.services.track_contract import (
    ingest_next_watch, missing_contract_elements, parse_next_watch_items,
)
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural

SAFE = "应收账款明细尚未取得，回款变化原因仍待核实。"
HEAD = "无上期基线，本期建立基线。复核期限：2026-10-22。\n"
WATCH = (
    "指标/事件——公司披露的2026三季报中的经营活动现金流量净额及存货、应收类科目；"
    "时间节点——在2026-10-22复查日核对其是否已披露；可证伪触发条件——"
    "若回款恶化，则削弱判断；若回款改善，则重新评估。"
)
TAIL = "单季口径为推算值，非官方披露。不构成买卖建议，本次研究不登记为长期跟踪、不写入投资观点。"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*_args, **_kwargs):
        pytest.fail("R6 regression attempted network IO")
    for name in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection"):
        monkeypatch.setattr(name, denied)
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)


@pytest.mark.parametrize("separator", ["", "\n", "\n\n"])
@pytest.mark.parametrize("footer", [TAIL, "以上为跟踪分析，不构成买卖建议。"])
def test_unbulleted_watch_does_not_absorb_a_disclaimer(tmp_path, separator, footer):
    answer = HEAD + "**下期关注（一条）**：" + WATCH + separator + footer
    assert missing_contract_elements(answer) == ()
    items = parse_next_watch_items(answer, as_of="2026-09-18")
    assert len(items) == 1 and items[0].due == "2026-10-22"
    assert footer not in items[0].claim
    path = tmp_path / "checkpoints.jsonl"
    assert ingest_next_watch(path, answer, query="跟踪旭创，不要登记长期跟踪") == []
    assert not path.exists()
    rows = ingest_next_watch(path, answer, query="跟踪旭创，请登记长期跟踪", session_id="r6-repair")
    assert len(rows) == 1 and rows[0]["session_id"] == "r6-repair"


@pytest.mark.parametrize("suffix", [
    "指标=存货；时间节点=2026-10-22。",
    "2. 指标=存货；时间节点=2026-10-22。",
    "单季口径为推算值，非官方披露；指标=存货；时间节点=2026-10-22。",
])
def test_footer_does_not_excuse_a_real_incomplete_watch(suffix):
    answer = HEAD + "下期关注清单：" + WATCH + "\n" + suffix
    assert missing_contract_elements(answer) == ("next_watch",)


@pytest.mark.parametrize("condition", [
    "检验条件：三季报净现比是否回到0.6以上、存货周转是否回落。",
    "三季报净现比是否回到0.6以上？",
    "三季报净现比能否恢复至0.6？",
    "三季报净现比能不能达到60%？",
    "三季报净现比可否回升到六成？",
    "净现比回到0.6以上才上调判断。",
    "| 净现比 | 是否回到0.6以上 |",
])
@pytest.mark.parametrize("mode", ["off", "llm"])
def test_threshold_question_is_not_a_numeric_gate_escape(monkeypatch, condition, mode):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    frame, verified = _structural(SAFE + "\n" + condition, detail=SAFE)
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    assert SAFE in result.public_answer
    assert condition not in result.public_answer
    assert any("novel_numeric_condition" in row["reasons"] for row in result.sentence_verdicts)


@pytest.mark.parametrize("text", [
    "三季报净现比是否改善？", "于2026-10-22复查净现比。", "2026年中报净现比为0.132。",
])
def test_qualitative_questions_and_raw_facts_are_retained(monkeypatch, text):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    frame, verified = _structural(SAFE + text, detail=SAFE)
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    assert text in result.public_answer


def _financial(draft, *, question="请比较中际旭创的利润与回款，注明可比口径。"):
    frame, initial = _structural(draft)
    frame = replace(frame, raw_question=question, user_goal=question, question_type="financial_analysis",
                    subject="300308", subject_kind="company")
    evidence = []
    # Finite obtained values used by R6. No new retrieval, no inference from titles.
    for period, ocf, profit, inventory in (
        ("2026-06-30", 18.0, 136.51, 198.26),
        ("2026-03-31", 33.68, 57.35, 156.72),
        ("2025-12-31", 108.96, 107.97, 126.81),
        ("2025-06-30", 32.18, 39.95, 91.68),
        ("2025-03-31", 21.64, 15.83, 78.19),
    ):
        evidence.append(AgentEvidence(
            "financial_data", f"300308 {period}", f"{period}累计经营现金流{ocf}亿元，归母净利{profit}亿元，存货{inventory}亿元。",
            "结构化财报", source_date="2026-08-22", content_hash=f"financial-{period}",
            observations=tuple(StructuredObservation("300308.SZ", period, metric, value) for metric, value in (
                ("ocf_cum_yi", ocf), ("net_profit_cum_yi", profit), ("inventory_yi", inventory),
            )),
        ))
    contract = replace(
        initial.contract, question=question, question_type=frame.question_type, subject=frame.subject,
        task_frame_hash=frame.task_frame_hash,
        required_outputs=(RequiredOutput("financial_assessment", "判断", ("financial_data",), True),
                          RequiredOutput("metric_evidence", "财务依据", ("financial_data", "web_fetch", "l3_lookup"), True)),
    )
    outcome = replace(initial.outcome, task_frame_hash=frame.task_frame_hash, evidence=tuple(evidence),
                      events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
                      bindings=tuple(OutputEvidenceBinding(o.output_id, tuple(e.content_hash for e in evidence))
                                     for o in contract.required_outputs))
    return frame, verify_episode_outcome(contract, outcome)


@pytest.mark.parametrize("claim", [
    "2026中报累计经营现金流18亿元，一季报为33.68亿元，二季度单季经营现金流为净流出约15.66亿元。",
    "二季度单季经营现金流=18−33.68=−15.66亿元。",
    "2026中报净现比0.133。",
    "2026中报含金量为0.133。",
    "2026中报含金量为0.132bp。",
    "2026中报含金量为0.132基点。",
    "2026中报含金量为0.132个百分点。",
    "2026中报含金量(bp)为0.132倍。",
    "2026中报净现比为0.132，同累计长度对照2025全年净现比1.009。",
    "2026中报OCF/净利从2025年报的1.009降至0.132。",
    "存货半年内增加约41.5亿元（156.72→198.26亿元）。",
    "若三季报累计经营现金流对归母净利的覆盖率较中报的0.132明显回升，则改变判断。",
    "2026中报累计经营现金流18亿元，一季报33.68亿元（二季度单季经营现金流为净流出约15.66亿元），OCF/净利从2025年报的1.009降至0.132。",
    "2026中报累计净现比0.133。",
    "2026中报和2025全年不能直接比较，但净现比从2025全年1.009降至2026中报0.132，说明回款恶化。",
])
@pytest.mark.parametrize("mode", ["off", "llm"])
def test_financial_contradiction_is_removed_even_when_judge_passes(monkeypatch, claim, mode):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    frame, verified = _financial(SAFE + "\n" + claim)
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    assert SAFE in result.public_answer
    assert claim not in result.public_answer
    assert any("financial_claim_mismatch" in row["reasons"] for row in result.sentence_verdicts)
    assert result.status == "partial"
    assert "metric_evidence" in result.gap_output_ids
    assert "metric_evidence" in result.repair_output_ids
    # Existing marker-loss gaps (e.g. the entire assessment was in this one
    # sentence) must not be erased merely because this gate adds a metric gap.
    assert set(result.verified.missing_outputs) <= set(result.repair_output_ids)


@pytest.mark.parametrize("claim", [
    "2026中报累计经营现金流18亿元，一季报为33.68亿元，二季度单季经营现金流为净流出约15.68亿元。",
    "二季度单季经营现金流=18−33.68=−15.68亿元。",
    "二季度单季经营现金流约-15.7亿元。",
    "2026中报净现比0.132。",
    "2026中报含金量为0.132。",
    "2026中报含金量为0.132倍。",
    "2026中报含金量为13.2%。",
    "2026中报含金量同比增长13.2%。",
    "2026中报和2025全年累计长度不同，不能直接比较净现比改善与否。",
    "2026中报净现比0.132，2025全年1.009；仅分别列示，不据此判断恶化。",
    "存货三个月内增加约41.5亿元（156.72→198.26亿元）。",
    "存货半年内增加71.45亿元（126.81→198.26亿元）。",
    "2026中报净现比13.2%。",
    "2026中报净现比同比增长13.2%。",
    "2026中报净现比0.132，2025全年仅作历史参考，2025中报净现比0.806，同比走弱。",
    "2026中报累计净现比0.132，2026一季报0.587，仅分别列示，不能直接比较。",
    "例如：二季度单季经营现金流=18−33.68=−15.66亿元是错误写法。",
    "2026半年度报告显示，存货三个月内增加41.54亿元（156.72→198.26亿元）。",
    "2026中报净现比0.132，一季报净现比0.587。",
    "2026中报存货在半年报披露前三个月从156.72→198.26亿元。",
])
def test_correct_arithmetic_and_explicit_noncomparison_are_retained(monkeypatch, claim):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    frame, verified = _financial(SAFE + "\n" + claim)
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    assert claim in result.public_answer


@pytest.mark.parametrize("claim", [
    "2026中报净现比0.132，同比2025中报0.806走弱。",
    "2026中报比2025中报回款走弱，但不能把2025全年当同累计长度比较。",
    "2026中报存货增长快于收入只是待验证假设，目前无法归因。",
])
def test_no_rejection_for_comparable_ratios_or_explicit_uncertainty(monkeypatch, claim):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    frame, verified = _financial(SAFE + "\n" + claim)
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    assert claim in result.public_answer


def test_structured_rows_cannot_fulfil_explicit_document_request():
    question = "选用一份你确实检索到、带明确发布日期的公告或定期报告，分析利润与回款。"
    _, verified = _financial(SAFE, question=question)
    assert verified.verified_status == "partial"
    assert verified.missing_outputs == ("metric_evidence",)
    assert verified.outcome.draft == SAFE
    assert "文档" in verified.completion.outputs[1].gap


@pytest.mark.parametrize("mode", ["off", "llm"])
def test_missing_document_stays_partial_without_losing_safe_prose_or_review_date(monkeypatch, mode):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    claim = "本次实际取得并引用的报告为中际旭创2026年半年度报告。"
    review = "请于2026-10-22复查现金回款。"
    frame, verified = _financial(
        SAFE + "\n" + claim + "\n" + review,
        question="选用一份你确实检索到、带明确发布日期的公告或定期报告，分析利润与回款。",
    )
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "partial"
    assert claim not in result.public_answer
    assert SAFE in result.public_answer and review in result.public_answer
    assert result.verified.missing_outputs == ("metric_evidence",)


def test_financial_repair_debt_is_local_and_not_sticky_after_correction(monkeypatch):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    verifier = SemanticEpisodeVerifier(judge_fn=_judge(True))
    frame, verified = _financial(SAFE + "\n2026中报净现比0.133。")
    first = verifier.verify(frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5))
    assert first.gap_output_ids == ("metric_evidence",)
    assert first.verified.completion.outputs[0].status == "fulfilled"
    corrected = verify_episode_outcome(verified.contract, replace(verified.outcome, draft=SAFE + "\n2026中报净现比0.132。"))
    second = verifier.verify(frame=frame, structurally_verified=corrected, deadline=ResearchDeadline.from_timeout(5))
    assert second.status == "completed"
    assert second.gap_output_ids == second.repair_output_ids == ()
    assert "净现比0.132" in second.public_answer


def _document(**kwargs):
    return replace(AgentEvidence(
        "web_fetch", "中际旭创（300308）2026年半年度报告", "中际旭创（300308）2026年半年度报告正文：经营活动现金流净额18亿元。",
        "https://www.cninfo.com.cn/report", source_date="2026-08-22", content_hash="report-doc",
        document_type="periodic_report", publisher_kind="official_disclosure",
    ), **kwargs)


@pytest.mark.parametrize("overrides,accepted", [
    ({}, True),
    ({"tool": "web_search"}, False),
    ({"tool": "financial_data"}, False),
    ({"document_type": "webpage"}, False),
    ({"source_date": None}, False),
    ({"source_date": "not-a-date"}, False),
    ({"detail": " "}, False),
    ({"source": "file:///report.pdf"}, False),
    ({"title": "其他公司2026年半年度报告", "detail": "其他公司报告正文"}, False),
])
def test_report_delivery_requires_subject_body_date_and_document_type(overrides, accepted):
    from intelligence.services.financial_report_contract import report_document_binding_gaps
    doc = _document(**overrides)
    gaps = report_document_binding_gaps(
        "选用一份你确实检索到、带明确发布日期的公告或定期报告。", (doc,), (doc.content_hash,), subject="300308",
    )
    assert bool(gaps) != accepted
    assert report_document_binding_gaps(
        "不用获取公告原文，只比较已有财务数据。", (), (), subject="300308",
    ) == ()
    assert report_document_binding_gaps(
        "请取得公告原文。", (doc,), (), subject="300308",
    )


@pytest.mark.parametrize("overrides,claim,rejected", [
    ({}, "本次实际取得并引用的报告为中际旭创2026年半年度报告。", False),
    ({"title": "其他公司报告", "detail": "其他公司报告正文"}, "本次实际取得并引用的报告为中际旭创2026年半年度报告。", True),
    ({"tool": "financial_data"}, "本次实际取得并引用的报告为中际旭创2026年半年度报告。", True),
    ({"tool": "financial_data"}, "未能取得报告文档，目前只有结构化代理数据。", False),
])
def test_document_claim_does_not_borrow_an_unrelated_company(monkeypatch, overrides, claim, rejected):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    frame, verified = _financial(SAFE + "\n" + claim)
    doc = _document(**overrides)
    outcome = replace(verified.outcome, evidence=(*verified.outcome.evidence, doc), bindings=tuple(
        replace(binding, evidence_hashes=(*binding.evidence_hashes, doc.content_hash))
        for binding in verified.outcome.bindings
    ))
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verify_episode_outcome(verified.contract, outcome),
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert SAFE in result.public_answer
    assert (claim not in result.public_answer) == rejected


@pytest.mark.parametrize("metric,value,rejected", [
    ("净现比.净现比[2026中报]", 0.132, False),
    ("净现比.净现比[2026中报]", 0.133, True),
    ("2025年报汇总.净现比[2026中报]", 0.132, False),
    ("净现比.净现比%[2026中报]", 13.2, False),
    ("净现比.营收[2026中报]", 417.78, False),
    ("净现比.净现比同比增长[2026中报]", 13.2, False),
    ("现金流.含金量(bp)[2026中报]", 0.132, True),
    ("现金流.净现比(BP)[2026中报]", 0.132, True),
    ("现金流.OCF/净利润（基点）[2026中报]", 0.132, True),
    ("现金流.含金量(百分点)[2026中报]", 0.132, True),
    ("现金流.含金量(倍)[2026中报]", 0.132, False),
    ("现金流.含金量增长(bp)[2026中报]", 9.999, False),
    ("现金流.含金量环比变化(基点)[2026中报]", 9.999, False),
    ("现金流.含金量[2024中报]", 9.999, False),
    ("净现比.净现比[2026中报]", float("nan"), True),
])
def test_result_ratio_is_recomputed_only_from_its_own_inputs(metric, value, rejected):
    from intelligence.services.financial_claim_checks import calculation_ratio_gaps
    _, verified = _financial(SAFE)
    inputs = verified.outcome.evidence
    calc = AgentEvidence(
        "derived_calculation", "净现比计算", "计算结果", "sandbox:0000000000000001", content_hash="calc",
        derived_from=tuple(item.content_hash for item in inputs),
        observations=(StructuredObservation("计算任务", "2025-04-21", metric, value),),
    )
    evidence = (*inputs, calc)
    assert bool(calculation_ratio_gaps(evidence, ("calc",), subject="300308")) == rejected
    assert calculation_ratio_gaps(evidence, (), subject="300308") == ()
    assert calculation_ratio_gaps((*inputs, replace(calc, derived_from=())), ("calc",), subject="300308") == ()
    peer = replace(inputs[0], content_hash="peer", observations=tuple(
        replace(obs, subject="000001.SZ") for obs in inputs[0].observations
    ))
    mixed = replace(calc, derived_from=(*calc.derived_from, "peer"))
    assert calculation_ratio_gaps((*inputs, peer, mixed), ("calc",), subject="300308") == ()


@pytest.mark.parametrize("ratio_name", ["含金量", "净现比", "OCF/净利润"])
def test_wrong_product_reopens_metric_slot_not_the_whole_research(ratio_name):
    _, verified = _financial(SAFE)
    inputs = verified.outcome.evidence
    calc = AgentEvidence(
        "derived_calculation", "净现比计算", "计算结果", "sandbox:0000000000000001", content_hash="calc",
        derived_from=tuple(item.content_hash for item in inputs),
        observations=(StructuredObservation("计算任务", "2025-04-21", f"{ratio_name}[2026中报]", 0.133),),
    )
    contract = replace(verified.contract, required_outputs=tuple(
        replace(required, evidence_types=(*required.evidence_types, "derived_calculation"))
        for required in verified.contract.required_outputs
    ))
    outcome = replace(verified.outcome, evidence=(*inputs, calc), bindings=tuple(
        replace(binding, evidence_hashes=(*binding.evidence_hashes, "calc"))
        for binding in verified.outcome.bindings
    ))
    checked = verify_episode_outcome(contract, outcome)
    assert checked.missing_outputs == ("metric_evidence",)
    assert checked.completion.outputs[0].status == "fulfilled"
    assert "复算不一致" in checked.completion.outputs[1].gap
    assert checked.outcome.draft == SAFE
    assert calc in checked.outcome.evidence


@pytest.mark.parametrize("ratio_name", ["含金量", "净现比", "OCF/净利润"])
@pytest.mark.parametrize("value,rejected", [(9.999, True), (1.588, False)])
def test_ratio_alias_recomputation_uses_the_same_bound_input_chain(ratio_name, value, rejected):
    from intelligence.services.financial_claim_checks import calculation_ratio_gaps
    from intelligence.tests.test_research_delivery_checks import _financial_evidence

    source, calc = _financial_evidence()
    calc = replace(calc, observations=(replace(
        calc.observations[0], metric=f"现金流比率.{ratio_name}[2026中报]", value=value,
    ),))
    evidence = (source, calc)
    assert bool(calculation_ratio_gaps(evidence, (calc.content_hash,), subject="600519.SH")) == rejected
    assert calculation_ratio_gaps(evidence, (), subject="600519.SH") == ()
    assert calculation_ratio_gaps(evidence, (calc.content_hash,), subject="000858.SZ") == ()


def test_conflicting_financial_inputs_are_not_cherry_picked():
    from intelligence.services.financial_claim_checks import financial_claim_mismatches
    _, verified = _financial(SAFE)
    evidence = verified.outcome.evidence
    conflicting = replace(evidence[0], content_hash="conflict", observations=(
        StructuredObservation("300308.SZ", "2026-06-30", "ocf_cum_yi", 19.0),
    ))
    rows = [{"index": 1, "text": "2026中报净现比0.133。"}]
    assert financial_claim_mismatches(rows, evidence, (), subject="300308") == ()
    assert financial_claim_mismatches(rows, (*evidence, conflicting), tuple(
        e.content_hash for e in (*evidence, conflicting)
    ), subject="300308") == ()
