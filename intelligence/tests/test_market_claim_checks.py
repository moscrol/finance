"""Finite D10 failures, not an oracle for arbitrary market prose or live quality."""
from dataclasses import replace
import json

import pytest

from intelligence.services import episode_semantic_verifier as verifier
from intelligence.services.agent_research import AgentEvidence, evidence_content_hash
from intelligence.services.agent_runtime import EpisodeEvent, OutputEvidenceBinding, public_agent_evidence
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.research_contract import RequiredOutput, ResearchDeadline
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural

SAFE = "07-22 涨停47家、跌停8家（E1）。"
ROWS = (
    ("2026-07-22", "26531.66", "-10.27", 47, 8),
    ("2026-07-21", "29569.03", "9.44", 121, 21),
    ("2026-07-20", "27019.21", "1.78", 53, 212),
    ("2026-07-17", "26547.43", "10.46", 33, 193),
    ("2026-07-16", "24033.87", "-6.52", 42, 34),
)


def _case(draft, *, rows=ROWS, extra_outputs=()):
    frame, initial = _structural(draft)
    frame = replace(frame, question_type="dated_market_review",
                    raw_question="2026-07-16 到 07-22 成交额和涨停家数的变化说明什么？")
    outputs = tuple(RequiredOutput(oid, oid, ("finance_query",), True) for oid in (
        "change_summary", "direct_assessment", "supporting_evidence", "risk_signals",
    )) + extra_outputs
    contract = replace(initial.contract, question=frame.raw_question,
                       question_type=frame.question_type, task_frame_hash=frame.task_frame_hash,
                       required_outputs=outputs, allowed_capabilities=("finance_query",))
    evidence = []
    for day, amount, change, up, down in rows:
        row = AgentEvidence(
            tool="finance_query", title=f"市场日频总览（{day}）",
            detail=f"交易日={day}；市场成交额亿={amount}；成交额环比%={change}；涨停家数={up}；跌停家数={down}",
            source="本地结构化数据 · 市场日频总览", source_date=day,
            evidence_tier="L4_structured", independent_key=f"duckdb:market_daily:{day}",
        )
        evidence.append(replace(row, content_hash=evidence_content_hash(row)))
    payload = {
        "ok": True, "tool": "finance_query", "task_frame_hash": frame.task_frame_hash,
        "query_basis": {"dataset": "market_daily", "group_by": [],
                        "metrics": ["total_amount", "amount_change_pct", "limit_up", "limit_down"]},
        "evidence_hashes": [row.content_hash for row in evidence],
        "evidence": [public_agent_evidence(row) for row in evidence],
    }
    outcome = replace(initial.outcome, task_frame_hash=frame.task_frame_hash, evidence=tuple(evidence),
                      bindings=tuple(OutputEvidenceBinding(
                          o.output_id, tuple(e.content_hash for e in evidence) if o.grounding_mode == "evidence" else (),
                          basis=o.grounding_mode,
                      ) for o in outputs),
                      events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
                              EpisodeEvent(2, "tool_result", payload)))
    return frame, verify_episode_outcome(contract, outcome)


def _findings(verified):
    return verifier.market_claim_repair_feedback(verified)


def _result(frame, verified):
    return verifier.SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    monkeypatch.setenv("FINANCE_NUMERIC_CONDITION_MARK", "1")

    def denied(*_args, **_kwargs):
        pytest.fail("market regression attempted network IO")
    for name in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection"):
        monkeypatch.setattr(name, denied)


@pytest.mark.parametrize("claim", [
    "07-17 全市场成交额较前一交易日缩量。",
    "2026-07-20全市场成交额环比缩量（E3）。",
    "07-22全市场成交额环比放量（E1）。",
    "07-16全市场成交额环比放量（E5）。",
])
def test_dated_turnover_direction_has_recomputable_feedback(claim):
    _, verified = _case(SAFE + "\n" + claim)
    feedback = tuple(json.loads(row) for row in _findings(verified))
    assert any(row["reasons"] == ["market_amount_direction"] for row in feedback)
    assert claim in {row["sentence"] for row in feedback}
    assert any("成交额环比" in row["repair_instruction"] for row in feedback)


@pytest.mark.parametrize("claim", [
    "07-17全市场较前一交易日放量。",
    "07-20全市场成交额环比小幅放量（E3）。",
    "07-22全市场缩量回落（E1）。",
    "07-17全市场量比仍低于20日均额，按该基准属于缩量。",
    "07-17全市场成交额较前周缩量。",
    "07-17芯片板块缩量。",
    "07-17某个股缩量。",
    "若07-17全市场缩量，则需观察。",
    "07-17全市场不是缩量，而是放量。",
    "07-17全市场是否缩量仍待核对？",
    "07-17全市场缩量这个说法不成立。",
    "07-17全市场成交额增加，涨停家数减少。",
    "07-17全市场成交股数缩量，但成交额放大。",
    "07-17全市场缩量恐慌。",  # unspecified comparator is not a proved contradiction
    "07-17全市场成交额环比增加，芯片缩量。",
    "07-17全市场成交额环比增加，涨停家数缩量。",
    "07-17全市场成交额环比增加而芯片缩量。",
    "07-17芯片放量，但全市场成交额环比缩量。",
    "07-17并未说全市场成交额环比缩量。",
])
def test_direction_counterexamples_are_not_rejected(claim):
    _, verified = _case(claim)
    assert _findings(verified) == ()


@pytest.mark.parametrize("claim", [
    "指数反弹靠少数权重拉动，小票还在踩踏。",
    "两日跌停很多，属于情绪宣泄式出清，而非温和调整。",
    "07-21全面反弹才是出清得到验证的证据。",
    "07-17~07-20是一次明确的风险释放。",
    "整体呈现放量普跌→缩量恐慌→修复反弹，说明经历了一次风险释放。",
    "涨停集中说明资金集中回流硬件主线。",
    "涨停集中说明资金不是普涨回补，而是集中回流硬件主线。",
    "跌停减少不等于风险出清，但全面反弹才是出清得到验证的证据。",
    "缺少权重贡献数据，但指数反弹靠少数权重拉动。",
    "放量重挫，是最典型的恐慌宣泄日。",
    "修复质量对主线存续的依赖度高。",
])
@pytest.mark.parametrize("mode", ["off", "llm"])
def test_totals_do_not_prove_mechanisms_and_deletion_is_not_completion(monkeypatch, claim, mode):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    frame, verified = _case(SAFE + "\n" + claim)
    result = _result(frame, verified)
    assert SAFE in result.public_answer
    assert claim not in result.public_answer
    assert result.status == "partial"
    assert "direct_assessment" in result.repair_output_ids
    assert "direct_assessment" in result.verified.missing_outputs
    assert result.delivery_repair_notes
    assert any("market_evidence_scope" in row["reasons"] for row in result.sentence_verdicts)
    assert any(claim in row for row in verifier.semantic_repair_feedback(result))
    assert verified.outcome.draft == SAFE + "\n" + claim


@pytest.mark.parametrize("claim", [
    "不能确认风险已经出清。",
    "放量下跌、跌停减少不能据此确认风险已经出清。",
    "指数反弹可能由权重股拉动，仍需贡献分解验证。",
    "权重股拉动只是待验证假设，不是已证实事实。",
    "是否风险出清需要继续观察。",
    "总量数据不足以证明资金集中回流硬件主线。",
    "假设资金集中回流硬件主线，后续需核对资金流向。",
    "量价与广度共同改善，可描述为修复，不能确认风险出清。",
    "若跌停家数重新抬升，视为恐慌二次启动。",
    "07-22指数微涨与下跌家数背离未做权重贡献拆分。",
    "成交额反映交易规模，不构成对资金来源、买卖动机的判断。",
    "风险已经出清吗？",
    "这里说的风险释放仅是假设，尚未验证。",
    "指数不是由权重股拉动。",
    "评论员说“风险已经出清”，本轮尚未核实。",
    "旧稿称“指数反弹靠少数权重拉动”，这里仅列待核观点。",
])
def test_hypotheses_boundaries_and_useful_analysis_survive(claim):
    frame, verified = _case(SAFE + "\n" + claim)
    assert _findings(verified) == ()
    assert claim in _result(frame, verified).public_answer


@pytest.mark.parametrize("payload_patch", [
    {"ok": False}, {"task_frame_hash": "other-task"}, {"tool": "memory_lookup"},
    {"query_basis": None}, {"query_basis": {"dataset": "market_daily", "group_by": ["trade_date"]}},
    {"evidence": []}, {"evidence_hashes": []}, {"evidence": [None, {"content_hash": []}]},
], ids=["failed", "foreign-task", "wrong-tool", "no-basis", "aggregate", "no-rows", "no-hashes", "bad-rows"])
def test_untrusted_tool_metadata_never_becomes_a_market_measurement(payload_patch):
    _, verified = _case("07-17全市场成交额环比缩量。")
    event = verified.outcome.events[-1]
    verified = replace(verified, outcome=replace(verified.outcome, events=(
        *verified.outcome.events[:-1], replace(event, payload={**event.payload, **payload_patch}),
    )))
    assert _findings(verified) == ()


def test_explicit_citation_cannot_borrow_a_different_days_value():
    _, verified = _case("07-17全市场成交额环比缩量（E1）。")
    assert _findings(verified) == ()


def test_optional_or_gap_binding_is_not_comparison_authority():
    _, verified = _case("07-17全市场成交额环比缩量。")
    optional = OutputEvidenceBinding("prime_quote", tuple(e.content_hash for e in verified.outcome.evidence))
    verified = replace(verified, outcome=replace(verified.outcome, bindings=(
        *(replace(b, evidence_hashes=(), gap="缺少输入") for b in verified.outcome.bindings), optional,
    )))
    assert _findings(verified) == ()


def test_cross_slot_values_cannot_prove_a_sentence_contradiction():
    _, verified = _case("07-17全市场成交额环比缩量。")
    keep = verified.outcome.evidence[0].content_hash  # risk binds only 07-22
    verified = replace(verified, outcome=replace(verified.outcome, bindings=tuple(
        replace(b, evidence_hashes=(keep,)) if b.output_id == "risk_signals" else b
        for b in verified.outcome.bindings)))
    assert _findings(verified) == ()


def test_other_slots_mechanism_evidence_prevents_an_absence_verdict():
    _, verified = _case("指数反弹靠少数权重拉动。")
    extra = AgentEvidence("web_fetch", "报告", "指数贡献待语义核对", "报告", content_hash="contribution")
    verified = replace(verified, outcome=replace(verified.outcome,
        evidence=(*verified.outcome.evidence, extra), bindings=tuple(
            replace(b, evidence_hashes=(*b.evidence_hashes, extra.content_hash))
            if b.output_id == "supporting_evidence" else b for b in verified.outcome.bindings)))
    assert _findings(verified) == ()  # cannot infer sentence→slot from vocabulary


@pytest.mark.parametrize("raw_change", ["NaN", "Infinity", "缺", "0"])
def test_missing_nonfinite_or_flat_changes_do_not_prove_a_direction(raw_change):
    _, verified = _case("07-17全市场成交额环比缩量。", rows=(("2026-07-17", "26547.43", raw_change, 33, 193),))
    assert _findings(verified) == ()


def test_conflicting_same_day_values_are_not_last_write_wins():
    _, verified = _case("07-17全市场成交额环比缩量。", rows=(*ROWS, ("2026-07-17", "26547.43", "-10.46", 33, 193)))
    assert _findings(verified) == ()


def test_same_fake_hash_in_event_and_card_is_not_authority():
    _, verified = _case("07-17全市场成交额环比缩量。", rows=(ROWS[3],))
    row = replace(verified.outcome.evidence[0], content_hash="fake")
    event = verified.outcome.events[-1]
    verified = replace(verified, outcome=replace(verified.outcome, evidence=(row,),
        bindings=tuple(replace(b, evidence_hashes=("fake",)) for b in verified.outcome.bindings),
        events=(*verified.outcome.events[:-1], replace(event, payload={**event.payload,
            "evidence_hashes": ["fake"], "evidence": [public_agent_evidence(row)]}))))
    assert _findings(verified) == ()


def test_evidence_threshold_needs_revision_not_just_a_doubt_suffix():
    condition = "若缩量延续1-2天则下调修复判断（待核：1-2天没有出处）。"
    frame, verified = _case(SAFE + "\n**风险信号与观察条件**：\n" + condition)
    result = _result(frame, verified)
    assert condition not in result.public_answer
    assert result.status == "partial"
    assert "risk_signals" in result.repair_output_ids
    assert "risk_signals" in result.verified.missing_outputs
    assert SAFE in result.public_answer


def test_a_threshold_in_another_slots_observation_cannot_authorize_risk():
    from intelligence.services.agent_research import StructuredObservation
    frame, verified = _case(SAFE + "\n**风险信号与观察条件**：\n若缩量延续30天则改判。")
    extra = AgentEvidence("market_data", "别槽材料", "观测值=30天", "市场", content_hash="other-slot",
                          observations=(StructuredObservation("other", "2026-07-22", "window", 30),))
    verified = replace(verified, outcome=replace(verified.outcome, evidence=(*verified.outcome.evidence, extra),
        bindings=tuple(replace(b, evidence_hashes=(*b.evidence_hashes, extra.content_hash))
                       if b.output_id == "supporting_evidence" else b for b in verified.outcome.bindings)))
    result = _result(frame, verified)
    assert "30天" not in result.public_answer
    assert "risk_signals" in result.repair_output_ids


@pytest.mark.parametrize("window", ["30天", "20日"], ids=["scalar-count", "formula-lookback"])
def test_totals_scalar_or_formula_constant_cannot_authorize_a_monitoring_duration(window):
    from intelligence.services.agent_research import StructuredObservation
    frame, verified = _case(SAFE + "\n**风险信号与观察条件**：\n若缩量持续" + window + "则改判。")
    row = replace(verified.outcome.evidence[0],
                  detail=verified.outcome.evidence[0].detail + "；量比定义=相对20日均额的百分数",
                  observations=(StructuredObservation("全市场", "2026-07-22", "limit_up", 30),))
    row = replace(row, content_hash=evidence_content_hash(row))
    old_hash = verified.outcome.evidence[0].content_hash
    evidence = (row, *verified.outcome.evidence[1:])
    event = verified.outcome.events[-1]
    verified = replace(verified, outcome=replace(verified.outcome, evidence=evidence,
        bindings=tuple(replace(b, evidence_hashes=tuple(row.content_hash if h == old_hash else h
                                                       for h in b.evidence_hashes)) for b in verified.outcome.bindings),
        events=(*verified.outcome.events[:-1], replace(event, payload={**event.payload,
            "evidence_hashes": [e.content_hash for e in evidence],
            "evidence": [public_agent_evidence(e) for e in evidence]}))))
    result = _result(frame, verified)
    assert "risk_signals" in result.repair_output_ids
    assert "若缩量持续" not in result.public_answer


def test_optional_forward_slot_cannot_authorize_an_evidence_risk_threshold():
    optional = RequiredOutput("scenario_paths", "情景", (), False, "model_reasoning")
    frame, verified = _case(SAFE + "\n**风险信号与观察条件**：\n若缩量延续1-2天则改判。",
                            extra_outputs=(optional,))
    result = _result(frame, verified)
    assert "1-2天" not in result.public_answer
    assert "risk_signals" in result.repair_output_ids


def test_risk_heading_does_not_turn_field_definitions_into_mechanical_deletions():
    claim = "量比是相对20日均额的百分数。"
    frame, verified = _case(SAFE + "\n**风险信号与观察条件**：\n" + claim)
    result = _result(frame, verified)
    assert "量比是相对20日均额的百分数" in result.public_answer
    assert not result.repair_output_ids


def test_short_cited_dates_keep_original_ordinals_when_risk_pool_is_narrowed():
    claim = "若07-17的涨停家数重新回升则观察修复（E4）。"
    _, verified = _case(SAFE + "\n**风险信号与观察条件**：\n" + claim)
    digest = verified.outcome.evidence[3].content_hash
    verified = replace(verified, outcome=replace(verified.outcome, bindings=tuple(
        replace(b, evidence_hashes=(digest,)) if b.output_id == "risk_signals" else b
        for b in verified.outcome.bindings)))
    assert _findings(verified) == ()


def test_explicitly_conditional_phase_path_is_not_a_historical_assertion():
    _, verified = _case("假设全市场放量→缩量→再放量，则需逐日观察。")
    assert _findings(verified) == ()


def test_a_sector_phase_path_does_not_inherit_market_measurements():
    _, verified = _case("芯片放量→缩量→反弹。")
    assert _findings(verified) == ()


@pytest.mark.parametrize("claim", [
    "不能把若缩量持续30天则改判当成已验证规则。",
    "若缩量持续30天则改判只是待验证假设。",
    "旧稿称“若缩量持续30天则改判”，这里不认可。",
    "若缩量持续30天则改判吗？",
])
def test_risk_window_report_denial_or_question_is_not_a_new_condition(claim):
    _, verified = _case(SAFE + "\n**风险信号与观察条件**：\n" + claim)
    assert _findings(verified) == ()


@pytest.mark.parametrize("question,window", [
    ("请以30天为观察窗口。", "30天"),
    ("请以3个交易日为观察窗口。", "3个交易日"),
    ("请以3交易日为观察窗口。", "3交易日"),
    ("请以3交易日为观察窗口。", "3个交易日"),
    ("请以1至2天为观察窗口。", "1-2天"),
    ("请以1～2个交易日为观察窗口。", "1至2个交易日"),
], ids=["days", "trading-days", "trading-days-no-counter", "trading-counter-variant", "range", "trading-range"])
def test_user_supplied_window_is_not_certified_or_rejected_by_this_finite_gate(question, window):
    _, verified = _case("**风险信号与观察条件**：\n若缩量持续" + window + "则改判。")
    verified = replace(verified, contract=replace(verified.contract, question=question))
    assert _findings(verified) == ()


@pytest.mark.parametrize("question,window", [
    ("30家涨停说明什么？", "30天"),
    ("相对20日均额的量比说明什么？", "30天"),
    ("相对20日均额的量比说明什么？", "20日"),
    ("2026-07-20说明什么？", "20日"),
    ("2026年7月20日说明什么？", "20日"),
    ("请按3个交易日观察。", "3天"),
    ("请按3天观察。", "3个交易日"),
    ("请看前30天的历史。", "3天"),
], ids=["counts", "different-window", "formula", "date", "chinese-date", "trading-to-calendar", "calendar-to-trading", "substring"])
def test_user_numbers_or_different_time_units_do_not_supply_the_risk_window(question, window):
    _, verified = _case("**风险观察**：\n若缩量持续" + window + "则改判。")
    verified = replace(verified, contract=replace(verified.contract, question=question))
    assert any("market_risk_threshold" in row for row in _findings(verified))


def test_no_named_required_slot_means_no_arbitrary_fallback_repair_target():
    _, verified = _case("指数反弹靠少数权重拉动。\n07-17全市场成交额环比缩量。")
    verified = replace(verified, contract=replace(verified.contract, required_outputs=tuple(
        o for o in verified.contract.required_outputs if o.output_id == "supporting_evidence")))
    assert _findings(verified) == ()


def test_reported_quote_does_not_shield_a_new_assertion_outside_it():
    _, verified = _case("旧稿称“风险已经出清”，但指数反弹靠少数权重拉动。")
    assert len(_findings(verified)) == 1


def test_final_delivery_feedback_keeps_specific_repair_instructions():
    frame, verified = _case(SAFE)
    result = verifier.recheck_material_public_delivery(_result(frame, verified),
                                                       projected=SAFE + "\n风险已经出清。")
    feedback = [json.loads(row) for row in verifier.semantic_repair_feedback(result)]
    assert any(row.get("stage") == "delivery" and row["sentence"] == "风险已经出清。"
               and "总量" not in row["sentence"] and row.get("repair_instruction") for row in feedback)


def test_different_market_fields_are_not_certified_as_total_only_support():
    _, verified = _case("风险已经出清。")
    event = verified.outcome.events[-1]
    payload = {**event.payload, "query_basis": {**event.payload["query_basis"],
                                               "metrics": ["market_stage_confidence"]}}
    verified = replace(verified, outcome=replace(verified.outcome,
        events=(*verified.outcome.events[:-1], replace(event, payload=payload))))
    assert _findings(verified) == ()


def test_model_reasoning_risk_slot_is_not_silently_changed_to_evidence():
    frame, verified = _case(SAFE + "\n**风险观察**：\n若缩量延续1-2天则改判，这是暂定的主观监测窗，用来观察修复持续性，尚不确定。")
    contract = replace(verified.contract, required_outputs=tuple(
        replace(o, grounding_mode="model_reasoning") if o.output_id == "risk_signals" else o
        for o in verified.contract.required_outputs))
    outcome = replace(verified.outcome, bindings=tuple(
        replace(b, evidence_hashes=(), basis="model_reasoning") if b.output_id == "risk_signals" else b
        for b in verified.outcome.bindings))
    verified = verify_episode_outcome(contract, outcome)
    assert _findings(verified) == ()
    assert "1-2天" in _result(frame, verified).public_answer


def test_reverification_of_corrected_text_clears_only_current_market_debt():
    frame, verified = _case(SAFE + "\n07-17全市场成交额环比缩量。")
    service = verifier.SemanticEpisodeVerifier(judge_fn=_judge(True))
    first = service.verify(frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5))
    assert first.status == "partial" and first.repair_output_ids
    corrected = verify_episode_outcome(verified.contract, replace(
        verified.outcome, draft=SAFE + "\n07-17全市场放量，跌停增多只说明下跌压力扩大，不能确认风险出清。"))
    second = service.verify(frame=frame, structurally_verified=corrected, deadline=ResearchDeadline.from_timeout(5))
    assert not second.repair_output_ids
    assert not any("market_amount_direction" in row["reasons"] for row in second.sentence_verdicts)


def test_unknown_question_class_does_not_disable_bound_market_checks():
    claim = "指数反弹靠少数权重拉动。"
    frame, verified = _case(SAFE + "\n" + claim + "\n**风险信号与观察条件**：\n若缩量延续1-2天则改判。")
    frame = replace(frame, subject=None, subject_kind="unknown", question_type="general_finance_qa")
    contract = replace(verified.contract, subject=None, subject_kind="unknown", question_type="general_finance_qa",
                       task_frame_hash=frame.task_frame_hash)
    events = tuple(replace(e, payload={**e.payload, "task_frame_hash": frame.task_frame_hash})
                   for e in verified.outcome.events)
    verified = verify_episode_outcome(contract, replace(verified.outcome, events=events,
                                                        task_frame_hash=frame.task_frame_hash))
    result = _result(frame, verified)
    assert result.status == "partial"
    assert claim not in result.public_answer and "1-2天" not in result.public_answer
    assert {"direct_assessment", "risk_signals"} <= set(result.repair_output_ids)


def test_unlocated_phase_path_is_a_scope_gap_not_a_false_arithmetic_verdict():
    claim = "整体呈现放量普跌→缩量恐慌→修复反弹→冲高缩量回落。"
    frame, verified = _case(SAFE + "\n" + claim)
    feedback = [json.loads(row) for row in _findings(verified)]
    assert [row["reasons"] for row in feedback] == [["market_path_scope"]]
    result = _result(frame, verified)
    assert result.status == "partial" and "change_summary" in result.repair_output_ids
    assert claim not in result.public_answer and SAFE in result.public_answer
    assert "保留不代表已逐项核实" in result.public_answer


@pytest.mark.parametrize("citation", ["E4、E999", "E4、E1"])
def test_citations_do_not_authorize_unbound_or_ambiguous_date_context(citation):
    _, verified = _case(f"07-17全市场成交额环比缩量（{citation}）。")
    if "E999" in citation:
        assert _findings(verified) == ()
    else:
        assert len(_findings(verified)) == 1  # explicit date selects E4, not E1's shrinking value


def test_wrong_event_content_not_just_wrong_hash_is_rejected():
    _, verified = _case("07-17全市场成交额环比缩量。", rows=(ROWS[3],))
    event = verified.outcome.events[-1]
    payload = {**event.payload, "evidence": [{**event.payload["evidence"][0], "source_date": "2026-07-22"}]}
    verified = replace(verified, outcome=replace(verified.outcome,
        events=(*verified.outcome.events[:-1], replace(event, payload=payload))))
    assert _findings(verified) == ()


def test_a_neighboring_denial_does_not_authorize_a_new_fact():
    _, verified = _case("风险尚未出清。指数反弹靠少数权重拉动。")
    rows = [json.loads(row) for row in _findings(verified)]
    assert len(rows) == 1 and rows[0]["sentence"] == "指数反弹靠少数权重拉动。"


def test_declared_non_total_support_is_not_certified_by_this_finite_absence_check():
    _, verified = _case("指数反弹靠少数权重拉动。")
    extra = AgentEvidence("web_fetch", "分解报告", "待语义审查的指数贡献材料", "报告", content_hash="report")
    verified = replace(verified, outcome=replace(verified.outcome,
        evidence=(*verified.outcome.evidence, extra), bindings=tuple(
            replace(b, evidence_hashes=(*b.evidence_hashes, "report"))
            if b.output_id == "direct_assessment" else b for b in verified.outcome.bindings)))
    assert _findings(verified) == ()  # abstention, NOT a pass/certificate for the prose report


@pytest.mark.parametrize("repair_case", ["correct", "ignored", "delete_only", "formatted_deletion", "no_budget"])
def test_market_gap_reenters_the_same_session_and_rechecks_without_new_tools(repair_case):
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.episode_session import CallbackEpisodeSession
    from intelligence.services.research_contract import InMemoryRootBudgetLedger
    from intelligence.tests.test_continuous_turn_adapter import _control

    claim = "指数反弹靠少数权重拉动。"
    frame, verified = _case(SAFE + "\n" + claim)
    control = _control(frame, capabilities=("finance_query",))
    context = build_episode_context(frame, task_id=verified.contract.task_id,
                                    capabilities=control.capabilities, timeout=120)
    context = replace(context, contract=verified.contract, root_budget=InMemoryRootBudgetLedger(
        episode_id=verified.contract.task_id, initial_calls=1, initial_seconds=30,
        hard_calls_cap=1 if repair_case == "no_budget" else 2,
        hard_seconds_cap=30 if repair_case == "no_budget" else 120,
    ))
    initial = verified.outcome
    goals = []
    corrected = SAFE + "\n指数与涨跌统计不同，权重贡献未核对，不能从总量确认风险出清。"

    class Runtime:
        def start(self, task_frame, *, context, registry):
            def resume(previous, goal):
                assert previous.draft == initial.draft
                assert goal.episode_id == verified.contract.task_id
                assert not goal.reopen_tools
                rows = [json.loads(row) for row in goal.unsupported_claims]
                assert any(row["sentence"] == claim and "market_evidence_scope" in row["reasons"] for row in rows)
                goals.append(goal)
                drafts = {"correct": corrected, "delete_only": SAFE,
                          "formatted_deletion": "**07-22 涨停47家、跌停8家（E1）。**"}
                draft = drafts.get(repair_case, previous.draft)
                return replace(previous, draft=draft,
                    stop_reason="model_finish", events=(*previous.events, EpisodeEvent(
                        len(previous.events) + 1, "model_turn", {"repair": True})))
            return CallbackEpisodeSession(episode_id=context.contract.task_id,
                                          outcome=initial, resume_callback=resume)

    result = ContinuousTurnAdapter(runtime=Runtime(),
        semantic_verifier=verifier.SemanticEpisodeVerifier(judge_fn=_judge(True)),
        runtime_name="continuous_glm", mode="on", context_factory=lambda *_a, **_k: context,
        registry_factory=lambda *_a, **_k: "registry").handle(frame=frame, control=control)
    assert len(goals) == int(repair_case != "no_budget")
    assert SAFE in result.answer.replace("**", "")
    assert claim not in result.answer
    assert result.private_artifact["outcome"]["usage"]["tool_calls"] == initial.usage.tool_calls
    if repair_case == "correct":
        assert corrected in result.answer
        assert not result.private_artifact["semantic_verifier"]["repair_output_ids"]
    else:
        assert result.status != "completed"
        assert "direct_assessment" in result.private_artifact["semantic_verifier"]["repair_output_ids"]


@pytest.mark.parametrize("claim", [
    "没有证据证明风险已经出清。",
    "指数反弹并没有靠权重股拉动。",
    "未见资金集中回流硬件主线。",
    "并无证据表明风险已经出清。",
    "07-17没有说全市场成交额环比缩量。",
], ids=["no-evidence", "no-weight", "not-observed", "no-basis", "denied-direction"])
def test_explicit_absence_or_denial_is_not_an_asserted_market_claim(claim):
    frame, verified = _case(SAFE + "\n" + claim)
    assert _findings(verified) == ()
    assert claim in _result(frame, verified).public_answer


@pytest.mark.parametrize("prefix", ["没有证据支持", "并无依据采用", "未见依据支持"])
def test_denied_risk_rule_is_not_a_new_monitoring_condition(prefix):
    _, verified = _case("**风险观察**：\n" + prefix + "若缩量持续30天则改判。")
    assert _findings(verified) == ()


@pytest.mark.parametrize("prefix", ["没有证据确认风险出清", "未见权重贡献", "并无资金流向数据"],
                         ids=["no-evidence", "not-observed", "no-flow"])
def test_absence_in_another_clause_does_not_excuse_a_new_mechanism(prefix):
    claim = prefix + "，但指数反弹靠少数权重拉动。"
    _, verified = _case(claim)
    assert any("market_evidence_scope" in row for row in _findings(verified))


def test_hypothesis_is_not_mechanism_evidence_but_is_not_deleted_as_a_fact():
    _, verified = _case("指数反弹可能由权重股拉动。")
    assert _findings(verified) == ()


@pytest.mark.parametrize(
    "claim",
    [
        "放量重挫，是最典型的恐慌宣泄日。",
        "跌停激增呈现恐慌特征。",
    ],
    ids=["panic-release", "panic-feature"],
)
def test_panic_descriptors_are_not_certified_from_totals(claim):
    _, verified = _case(claim)
    rows = [json.loads(row) for row in _findings(verified)]
    assert len(rows) == 1
    assert rows[0]["reasons"] == ["market_evidence_scope"]
    assert rows[0]["sentence"] == claim


@pytest.mark.parametrize(
    "claim",
    [
        "修复质量对主线存续的依赖度高。",
        "后续取决于题材持续性。",
    ],
    ids=["forward-dependency", "reverse-dependency"],
)
def test_mainline_dependency_descriptors_are_not_certified_from_totals(claim):
    _, verified = _case(claim)
    rows = [json.loads(row) for row in _findings(verified)]
    assert len(rows) == 1
    assert rows[0]["reasons"] == ["market_evidence_scope"]
    assert rows[0]["sentence"] == claim


@pytest.mark.parametrize(
    "claim",
    [
        "主线存续不依赖增量资金。",
        "后续不取决于题材持续性。",
    ],
    ids=["not-dependent", "not-dependent-reverse"],
)
def test_explicit_dependency_denials_are_not_mechanism_claims(claim):
    _, verified = _case(claim)
    assert _findings(verified) == ()


def test_neighbor_clause_does_not_supply_date_for_contradiction():
    _, verified = _case("07-17芯片放量，但全市场成交额环比缩量。")
    assert _findings(verified) == ()


def test_contract_and_outcome_task_identities_must_match():
    _, verified = _case("07-17全市场成交额环比缩量。")
    verified = replace(verified, contract=replace(verified.contract, task_frame_hash="foreign"))
    assert _findings(verified) == ()


def test_aggregate_metadata_does_not_supply_raw_amount_changes():
    _, verified = _case("07-17全市场成交额环比缩量。")
    event = verified.outcome.events[-1]
    payload = {**event.payload, "query_basis": {**event.payload["query_basis"], "group_by": ["trade_date"]}}
    verified = replace(verified, outcome=replace(verified.outcome,
        events=(*verified.outcome.events[:-1], replace(event, payload=payload))))
    assert _findings(verified) == ()


def test_unverified_risk_evidence_is_not_a_verified_total_only_schema():
    _, verified = _case("**风险观察**：\n若缩量持续30天则改判。")
    verified = replace(verified, outcome=replace(verified.outcome, events=verified.outcome.events[:1]))
    assert _findings(verified) == ()


def test_explicit_market_citation_does_not_inherit_uncited_report_support():
    _, verified = _case("指数反弹靠少数权重拉动（E1）。")
    report = AgentEvidence("web_fetch", "分解", "另一个来源", "报告", content_hash="report")
    verified = replace(verified, outcome=replace(verified.outcome,
        evidence=(*verified.outcome.evidence, report), bindings=tuple(
            replace(b, evidence_hashes=(*b.evidence_hashes, report.content_hash))
            if b.output_id == "direct_assessment" else b for b in verified.outcome.bindings)))
    assert len(_findings(verified)) == 1


def test_duplicate_card_identity_cannot_supply_direction_measurements():
    _, verified = _case("07-17全市场成交额环比缩量。", rows=(ROWS[3], ROWS[3]))
    assert _findings(verified) == ()


def test_market_issue_release_policy_is_explicitly_blocking():
    from intelligence.services.episode_issues import IssueCode, ReleaseAction, release_action
    assert release_action(IssueCode.MARKET_CLAIM_UNSUPPORTED) == ReleaseAction.BLOCK


def test_final_projection_rechecks_new_bad_text_and_keeps_safe_neighbor():
    frame, verified = _case(SAFE)
    good = _result(frame, verified)
    bad = SAFE + "\n指数反弹靠少数权重拉动。"
    result = verifier.recheck_material_public_delivery(good, projected=bad)
    assert result.status == "partial"
    assert SAFE in result.public_answer
    assert "指数反弹靠少数权重拉动" not in result.public_answer
    assert "direct_assessment" in result.repair_output_ids
    again = verifier.recheck_material_public_delivery(result, projected=result.public_answer)
    assert again.public_answer == result.public_answer
    assert again.repair_output_ids == result.repair_output_ids
