"""A cited measurement definition is not a bag of new market quantities."""
from dataclasses import replace

import pytest

from intelligence.services import finance_query
from intelligence.services.agent_research import evidence_content_hash
from intelligence.services.agent_runtime import EpisodeEvent, public_agent_evidence
from intelligence.services.episode_semantic_verifier import (
    _mask_market_ratio_definition, _novel_numeric_condition_tokens, _numbered_sentences,
)
from intelligence.services.research_contract import RequiredOutput
from intelligence.tests.test_episode_semantic_verifier import _structural

DRAFT = "量比88.1%（低于100%，即成交额低于20日均额水平），观察后续变化。"
DETAIL = "交易日=2026-07-22；量比%=88.1；市场成交额亿=26531.66"
# Frozen tool-side definition from the aee first run, not arbitrary source prose.
DEFINITION = "volume_ratio=total_amount/amount_ma20×100 是相对20日均额的百分数，不是倍数。"


def _case(draft=DRAFT, *, detail=DETAIL, basis_override=None, payload_override=None):
    _, verified = _structural(draft, detail=detail, required_outputs=(
        RequiredOutput("direct_assessment", "直接判断", ("finance_query",), True),
        RequiredOutput("risk_signals", "风险与观察条件", ("finance_query",), True),
    ))
    evidence = replace(verified.outcome.evidence[0], tool="finance_query",
                       independent_key="duckdb:market_daily:2026-07-22")
    evidence = replace(evidence, content_hash=evidence_content_hash(evidence))
    basis = {
        "dataset": "market_daily", "metrics": ["volume_ratio"], "group_by": [],
        "interpretation_note": "原始行口径：" + DEFINITION,
        **(basis_override or {}),
    }
    payload = {
        "ok": True, "tool": "finance_query", "query_basis": basis,
        "evidence_hashes": [evidence.content_hash],
        "evidence": [public_agent_evidence(evidence)],
        "task_frame_hash": verified.outcome.task_frame_hash,
        **(payload_override or {}),
    }
    event = EpisodeEvent(2, "tool_result", payload)
    return replace(verified, outcome=replace(verified.outcome, evidence=(evidence,),
                   bindings=tuple(replace(b, evidence_hashes=(evidence.content_hash,))
                                  for b in verified.outcome.bindings),
                   events=(*verified.outcome.events, event)))


def _missing(verified):
    result = _novel_numeric_condition_tokens(_numbered_sentences(verified.outcome.draft), verified)
    return [token.replace(" ", "") for values in result.values() for token in values]


@pytest.mark.parametrize("draft", [
    DRAFT,
    "量比 88.1%（低于 100%，即成交额低于 20 日均额水平）（E1）。",
    "量比88.1%（低于100%，即成交额低于20日均额水平），若延续30天则改判。",
], ids=["plain", "cited", "future"])
def test_known_ratio_definition_is_not_a_new_observation(draft):
    assert _missing(_case(draft)) == (["30天"] if "30天" in draft else [])


@pytest.mark.parametrize("override", [
    {"dataset": "stock_daily"}, {"metrics": ["total_amount"]},
    {"group_by": ["trade_date"]}, {"interpretation_note": "附近有20日和100%"},
    {"interpretation_note": DEFINITION.replace("20日", "10日")},
    {"metrics": None}, {"metrics": "volume_ratio"},
    {"metrics": ["volume_ratio", None]}, {"group_by": None},
    {"interpretation_note": [DEFINITION]}, {"interpretation_note": {"note": DEFINITION}},
    {"interpretation_note": None},
], ids=["dataset", "unrequested-field", "aggregation", "arbitrary-prose", "other-definition",
        "null-metrics", "string-metrics", "mixed-metrics", "null-grouping",
        "list-note", "object-note", "null-note"])
def test_other_query_metadata_cannot_authorize_formula_constants(override):
    assert _missing(_case(basis_override=override)) == ["100%", "20日"]


@pytest.mark.parametrize("override", [
    {"ok": False}, {"tool": "memory_lookup"}, {"evidence_hashes": ["other"]},
    {"evidence": [{"content_hash": "other"}]},
    {"evidence": None}, {"evidence_hashes": None},
    {"query_basis": None}, {"evidence": "not-rows"}, {"evidence_hashes": "not-hashes"},
    {"evidence": [None, "not-a-row", {"content_hash": []}]},
    {"evidence_hashes": [None, ["not-a-hash"]]},
], ids=["failed-tool", "other-tool", "other-ledger", "other-row", "null-evidence", "null-hashes",
        "null-basis", "string-evidence", "string-hashes", "malformed-rows", "malformed-hashes"])
def test_metadata_must_belong_to_the_actual_bound_tool_row(override):
    assert _missing(_case(payload_override=override)) == ["100%", "20日"]


def test_no_event_definition_does_not_reinterpret_legacy_evidence():
    verified = _case()
    verified = replace(verified, outcome=replace(verified.outcome, events=verified.outcome.events[:1]))
    assert _missing(verified) == ["100%", "20日"]


def test_a_different_output_binding_cannot_lend_the_definition():
    verified = _case()
    first, risk = verified.outcome.bindings
    verified = replace(verified, outcome=replace(verified.outcome,
                       bindings=(first, replace(risk, evidence_hashes=(), gap="风险依据缺失"))))
    assert _missing(verified) == ["100%", "20日"]


def test_wrong_explicit_citation_does_not_borrow_the_bound_market_definition():
    assert _missing(_case(DRAFT.replace("。", "（E2）。"))) == ["100%", "20日"]


@pytest.mark.parametrize("draft,expected", [
    ("量比88.1%低于常态，未来20日涨幅超过100%则减仓（E1）。", ["20日", "100%"]),
    ("量比88.1%，若涨停覆盖100%个股且延续20日则改判（E1）。", ["100%", "20日"]),
    (DRAFT.replace("低于", "高于"), ["100%", "20日"]),
    (DRAFT.replace("88.1", "75.5"), ["75.5%", "100%", "20日"]),
    (DRAFT.replace("即成交额低于", "即涨幅低于"), ["100%", "20日"]),
    (DRAFT.replace("100%", "110%"), ["110%", "20日"]),
], ids=["future-return", "other-metric", "reversed-relation", "invented-value", "wrong-meaning", "new-threshold"])
def test_formula_constants_do_not_license_market_facts_or_new_thresholds(draft, expected):
    assert _missing(_case(draft)) == expected


def test_explicit_citation_to_other_bound_row_cannot_borrow_the_definition():
    verified = _case(DRAFT.replace("。", "（E2）。"))
    other = replace(verified.outcome.evidence[0], content_hash="OTHER", detail="交易日=2026-07-22；涨停家数=47")
    verified = replace(verified, outcome=replace(verified.outcome,
        evidence=(*verified.outcome.evidence, other),
        bindings=tuple(replace(b, evidence_hashes=(*b.evidence_hashes, "OTHER")) for b in verified.outcome.bindings)))
    assert _missing(verified) == ["100%", "20日"]


def test_definition_cannot_authorize_a_value_absent_from_the_market_row():
    verified = _case()
    row = replace(verified.outcome.evidence[0], detail="交易日=2026-07-22；量比%=缺")
    verified = replace(verified, outcome=replace(verified.outcome, evidence=(row,)))
    assert _missing(verified) == ["88.1%", "100%", "20日"]


@pytest.mark.parametrize("value,relation", [(100, "等于"), (123.4, "高于"), (88.1, "低于")])
def test_comparison_is_calculated_from_the_observed_ratio(value, relation):
    draft = DRAFT.replace("88.1", str(value)).replace("低于", relation)
    verified = _case(draft, detail=DETAIL.replace("88.1", str(value)))
    assert _missing(verified) == []


@pytest.mark.parametrize("field,value", [
    ("tool", "memory_lookup"), ("independent_key", "duckdb:stock_daily:2026-07-22"),
    ("independent_key", None), ("detail", None),
    ("detail", "量比%=NaN"), ("detail", "量比%=88.1倍"),
    ("content_hash", None), ("content_hash", []),
], ids=["other-tool", "other-dataset", "null-key", "null-detail", "nan", "wrong-unit",
        "null-hash", "nonhashable-hash"])
def test_invalid_actual_row_does_not_grant_definition_authority(field, value):
    verified = _case()
    row = replace(verified.outcome.evidence[0], **{field: value})
    verified = replace(verified, outcome=replace(verified.outcome, evidence=(row,)))
    assert _mask_market_ratio_definition(DRAFT, verified) == DRAFT


def test_required_bindings_use_intersection_not_union():
    verified = _case()
    other = replace(verified.outcome.evidence[0], content_hash="OTHER",
                    detail="交易日=2026-07-22；涨停家数=47")
    first, risk = verified.outcome.bindings
    verified = replace(verified, outcome=replace(verified.outcome,
        evidence=(*verified.outcome.evidence, other),
        bindings=(first, replace(risk, evidence_hashes=("OTHER",)))))
    assert _mask_market_ratio_definition(DRAFT, verified) == DRAFT


def test_a_non_tool_event_does_not_grant_definition_authority():
    verified = _case()
    old_event = verified.outcome.events[-1]
    events = (*verified.outcome.events[:-1], replace(old_event, kind="model_turn"))
    verified = replace(verified, outcome=replace(verified.outcome, events=events))
    assert _mask_market_ratio_definition(DRAFT, verified) == DRAFT


def test_projection_keeps_every_other_assertion_and_never_changes_the_public_draft():
    suffix = "未来30天涨幅超过110%，是增量资金入场、权重股拉动和风险出清的证据。"
    draft = DRAFT[:-1] + "；" + suffix
    verified = _case(draft)
    projected = _mask_market_ratio_definition(draft, verified)
    assert projected == "量比88.1%（相对均额的定义比较），观察后续变化；" + suffix
    assert verified.outcome.draft == draft
    assert _missing(verified) == ["30天", "110%"]


@pytest.mark.parametrize("field,value", [
    ("tool", "memory_lookup"), ("title", "旧市场快照"),
    ("detail", DETAIL.replace("88.1", "77.7")), ("source", "其他来源"),
    ("source_date", "2026-07-21"), ("independent_key", "duckdb:stock_daily:2026-07-22"),
], ids=["tool", "title", "value", "source", "date", "dataset"])
def test_event_row_content_must_match_not_just_its_hash_label(field, value):
    verified = _case()
    event = verified.outcome.events[-1]
    payload = dict(event.payload)
    payload["evidence"] = [{**dict(event.payload["evidence"][0]), field: value}]
    verified = replace(verified, outcome=replace(verified.outcome,
        events=(*verified.outcome.events[:-1], replace(event, payload=payload))))
    assert _mask_market_ratio_definition(DRAFT, verified) == DRAFT


@pytest.mark.parametrize("digest", ["", "forged-hash"])
def test_consistent_but_invalid_hash_labels_cannot_authorize_the_definition(digest):
    verified = _case()
    row = replace(verified.outcome.evidence[0], content_hash=digest)
    event = verified.outcome.events[-1]
    payload = {**dict(event.payload), "evidence": [public_agent_evidence(row)],
               "evidence_hashes": [digest]}
    verified = replace(verified, outcome=replace(verified.outcome, evidence=(row,),
        bindings=tuple(replace(b, evidence_hashes=(digest,), gap="缺少内容身份" if not digest else "")
                       for b in verified.outcome.bindings),
        events=(*verified.outcome.events[:-1], replace(event, payload=payload))))
    assert _mask_market_ratio_definition(DRAFT, verified) == DRAFT


@pytest.mark.parametrize("stamp", [None, "other-task"])
def test_unattributed_or_foreign_task_event_cannot_lend_the_definition(stamp):
    verified = _case(payload_override={"task_frame_hash": stamp})
    assert _mask_market_ratio_definition(DRAFT, verified) == DRAFT


def test_optional_evidence_output_cannot_lend_the_definition():
    verified = _case()
    contract = replace(verified.contract, required_outputs=tuple(
        replace(spec, required=False) for spec in verified.contract.required_outputs))
    assert _mask_market_ratio_definition(DRAFT, replace(verified, contract=contract)) == DRAFT


def test_missing_required_binding_cannot_lend_the_definition():
    verified = _case()
    verified = replace(verified, outcome=replace(verified.outcome, bindings=verified.outcome.bindings[:1]))
    assert _mask_market_ratio_definition(DRAFT, verified) == DRAFT


def test_definition_text_is_owned_by_the_dataset_registry():
    spec = finance_query.FinanceQuerySpec("market_daily", ("volume_ratio",), ("trade_date",))
    assert DEFINITION in finance_query.interpretation_note(spec)
