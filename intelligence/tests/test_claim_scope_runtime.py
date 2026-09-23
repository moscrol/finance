"""Runtime wiring tests; no provider or production data access."""

from dataclasses import asdict, replace
import hashlib
import json

import pytest

from intelligence.services import answer_claim_scope, ask, ask_synthesis
from intelligence.services.ask_claim_scope import review_ask_claim_scope
from intelligence.services.ask_types import AskOptions, AskResult, Citation, PreparedAnswer
from intelligence.services.claim_scope_context import build_context
from intelligence.services.claim_scope_review import review_runtime_claims
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeOutcome, SemanticEpisodeVerifier, review_public_claim_scope,
)
from intelligence.services.output_review import OutputReviewGate
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.test_boundary_partial_delivery import _delivery
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural
from scripts import check_answer_claims
from scripts.claim_scope_census import census

DATE = "数据截至 2026-09-18（最近一个已收盘交易日）。"
FLOW = "成交额放大至 114.90 亿元，显示资金当日集中流入封测方向。"
SCOPE = "长电科技当日涨幅 7.75%，跑赢其所有归属板块。"
UNIT = "未注明公告日期、币种单位。"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv("ASK_CLAIM_SCOPE_REVIEW", raising=False)
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    monkeypatch.setattr("intelligence.services.llm_refine.judge_provider", lambda: None)

    def denied(*_args, **_kwargs):
        raise AssertionError("claim-scope wiring must not connect")

    monkeypatch.setattr("socket.socket.connect", denied)
    monkeypatch.setattr("socket.create_connection", denied)


def episode():
    return {"outcome": {
        "events": [{"kind": "tool_request", "payload": {
            "name": "finance_query", "arguments": {
                "metrics": ["amount"], "filters": [{
                    "field": "sector_code", "value": ["A", "B", "C", "D", "E"],
                }],
            },
        }}],
        "evidence": [{"source_date": "2026-09-18", "detail": "成交额 114.90 亿元"}],
    }}


def result(answer=FLOW):
    return AskResult(
        query="请复盘长电科技（600584）最近一个交易日的表现。",
        trade_date="2026-09-18", matched_theme=None, candidate_tier=None,
        priority_score=None, synthesis=answer, review_gate=OutputReviewGate(),
        citations=[Citation("D1", "本地行情", "成交额 114.90 亿元")],
    )


@pytest.mark.parametrize("configured", [None, "off"])
def test_off_keeps_serialized_gates_and_answer_unchanged(monkeypatch, configured):
    if configured is not None:
        monkeypatch.setenv("ASK_CLAIM_SCOPE_REVIEW", configured)
    frame, structural = _structural(DATE)
    semantic = SemanticEpisodeOutcome(structural, "completed", DATE, "passed")
    before = json.dumps(semantic.to_dict(), ensure_ascii=False)
    assert review_public_claim_scope(semantic, question=frame.raw_question) is semantic
    assert json.dumps(semantic.to_dict(), ensure_ascii=False) == before
    assert "claim_scope" not in semantic.to_dict()
    draft = result()
    before = json.dumps(asdict(draft), ensure_ascii=False)
    assert review_ask_claim_scope(draft) is draft
    assert json.dumps(asdict(draft), ensure_ascii=False) == before
    assert "claim_scope" not in draft.review_gate.to_dict()
    assert review_runtime_claims(answer=DATE, question="", episode={}) is None


@pytest.mark.parametrize("value,key", [
    ("typo", "claim_scope_mode_invalid"), ("", "claim_scope_mode_invalid"),
    ("revise", "claim_scope_mode_unsupported"), ("block", "claim_scope_mode_unsupported"),
])
def test_unimplemented_or_invalid_mode_never_enables_review(monkeypatch, value, key):
    monkeypatch.setenv("ASK_CLAIM_SCOPE_REVIEW", value)
    assert review_runtime_claims(answer=FLOW, question="", episode={}) == {"mode": "off", key: value}


@pytest.mark.parametrize("answer,question,total,count", [
    (DATE + SCOPE + FLOW, "复盘长电科技", 20, 3),
    (UNIT, "营收 10 亿元，利润 2 亿元", None, 1),
])
def test_shared_mapping_matches_cli_field_for_field(monkeypatch, answer, question, total, count):
    monkeypatch.setenv("ASK_CLAIM_SCOPE_REVIEW", "advisory")
    assert check_answer_claims.build_context is build_context
    context, diagnostics = build_context({"question": question}, episode(), total)
    expected = answer_claim_scope.review_answer_claims(answer, context).to_dict()
    receipt = review_runtime_claims(answer=answer, question=question, episode=episode(), scope_total=total)
    assert {key: receipt[key] for key in expected} == expected
    assert receipt["context_diagnostics"] == diagnostics
    assert receipt["issue_count"] == count
    assert receipt["degraded"] == []


@pytest.mark.parametrize("rule,answer,question", [
    (answer_claim_scope._latest_trading_day_issue, DATE, "复盘长电科技"),
    (answer_claim_scope._unit_gap_issue, UNIT, "营收 10 亿元"),
])
def test_rule_removal_changes_runtime_verdict(monkeypatch, rule, answer, question):
    monkeypatch.setenv("ASK_CLAIM_SCOPE_REVIEW", "advisory")
    args = dict(answer=answer, question=question, episode=episode())
    assert review_runtime_claims(**args)["issue_count"] == 1
    with monkeypatch.context() as mutation:
        mutation.setattr(answer_claim_scope, "_RULE_CHECKS", tuple(
            check for check in answer_claim_scope._RULE_CHECKS if check is not rule
        ))
        assert review_runtime_claims(**args)["issue_count"] == 0
    assert review_runtime_claims(**args)["issue_count"] == 1


@pytest.mark.parametrize("payload,total", [({"outcome": {}}, 20), ({"outcome": {}}, None),
                                             ({"outcome": {"events": [None, {"kind": "tool_request", "payload": None}]}}, 20)])
def test_missing_or_malformed_mapping_is_not_clean(monkeypatch, payload, total):
    monkeypatch.setenv("ASK_CLAIM_SCOPE_REVIEW", "advisory")
    receipt = review_runtime_claims(answer=SCOPE, question="", episode=payload, scope_total=total)
    assert receipt["degraded"]
    assert receipt["clean"] is False
    assert any(check["name"] == "口径越界·判据降级" for check in receipt["checks"])
    assert all(check["advisory_only"] for check in receipt["checks"])


def test_verifier_advisory_preserves_public_and_terminal_fields(monkeypatch):
    frame, structural = _structural("当前需求仍待确认 E1。")
    def verify():
        return SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
            frame=frame, structurally_verified=structural, deadline=ResearchDeadline.from_timeout(30),
        )
    baseline = verify()
    monkeypatch.setenv("ASK_CLAIM_SCOPE_REVIEW", "advisory")
    reviewed = verify()
    assert reviewed.claim_scope is not None
    assert replace(reviewed, claim_scope=None) == baseline


@pytest.mark.parametrize("repair", ["none", "raises", "recheck_raises", "good"])
def test_adapter_reviews_final_delivery_including_recovery(monkeypatch, repair):
    baseline, old_goals, _ = _delivery(repair=repair)
    monkeypatch.setenv("ASK_CLAIM_SCOPE_REVIEW", "advisory")
    reviewed, goals, _ = _delivery(repair=repair)
    assert (reviewed.answer, reviewed.status, reviewed.warnings) == (baseline.answer, baseline.status, baseline.warnings)
    assert len(goals) == len(old_goals)
    receipt = reviewed.private_artifact["semantic_verifier"]["claim_scope"]
    assert receipt["answer_sha256"] == hashlib.sha256(reviewed.answer.encode()).hexdigest()
    assert receipt["mode"] == "advisory"
    if repair in {"raises", "recheck_raises"}:
        assert reviewed.private_artifact["delivery_recovery"]["source"] == "last_verified_public_answer"


def test_ask_early_return_is_reviewed_without_revising(monkeypatch):
    monkeypatch.setenv("ASK_CLAIM_SCOPE_REVIEW", "advisory")
    draft = result()
    before = (draft.synthesis, list(draft.warnings), draft.review_gate.warn_count)
    monkeypatch.setattr(ask, "_answer_query_impl", lambda _options: draft)
    actual = ask.answer_query(AskOptions(query=draft.query))
    assert (actual.synthesis, actual.warnings, actual.review_gate.warn_count) == before
    assert actual.review_gate.claim_scope["rules_hit"] == [answer_claim_scope.RULE_FUND_FLOW]
    assert actual.review_gate.claim_scope["degraded"] == ["engine_b_tool_requests_unavailable"]
    count = len(actual.review_gate.checks)
    assert len(review_ask_claim_scope(actual).review_gate.checks) == count


def test_deferred_synthesis_replaces_old_advisory_receipt(monkeypatch):
    monkeypatch.setenv("ASK_CLAIM_SCOPE_REVIEW", "advisory")
    draft = review_ask_claim_scope(result())
    assert draft.review_gate.claim_scope["issue_count"] == 1
    def synthesize(prepared):
        prepared.result.synthesis = "成交活跃度提升，不据此判断资金方向。"
        return prepared.result
    monkeypatch.setattr(ask_synthesis, "_synthesize_prepared_answer", synthesize)
    actual = ask_synthesis.synthesize_prepared_answer(PreparedAnswer(AskOptions(query=draft.query), draft))
    assert actual.review_gate.claim_scope["issue_count"] == 0
    assert not any(check.name == "口径越界·无资金流证据推断资金方向" for check in actual.review_gate.checks)


def test_workbench_b_persists_review_of_delivered_text(monkeypatch, tmp_path):
    from intelligence.tests.test_conversation_orchestrator import (
        test_research_compose_revises_on_warn_and_keeps_review_as_appendix as exercise,
    )

    monkeypatch.setenv("ASK_CLAIM_SCOPE_REVIEW", "advisory")
    exercise(tmp_path, monkeypatch)
    paths = list((tmp_path / "runs").rglob("claim-scope-review.json"))
    assert len(paths) == 1
    receipt = json.loads(paths[0].read_text())
    answer = paths[0].with_name("answer.md").read_text()
    assert receipt["answer_sha256"] == hashlib.sha256(answer.encode()).hexdigest()
    assert receipt["mode"] == "advisory"
    assert "口径越界" not in answer


def test_census_counts_explicit_artifacts_and_missing_receipts(tmp_path):
    payloads = [
        {"semantic_verifier": None},
        {"mode": "off", "claim_scope_mode_invalid": ""},
        {"mode": "advisory", "issue_count": 2, "degraded": [], "rules_hit": ["date", "date"]},
        {"semantic_verifier": {"claim_scope": {"mode": "advisory", "issue_count": 0,
                                                 "degraded": ["scope"], "rules_hit": []}}},
    ]
    paths = []
    for index, payload in enumerate(payloads):
        path = tmp_path / f"{index}.json"
        path.write_text(json.dumps(payload))
        paths.append(path)
    actual = census(paths)
    assert actual["artifact_count"] == 4
    assert actual["advisory_count"] == 2
    assert actual["hit_count"] == actual["degraded_count"] == actual["invalid_or_unsupported_count"] == 1
    assert actual["presence_rate"] == actual["hit_rate_among_advisory"] == 0.5
    assert actual["rules_hit_counts"] == {"date": 1}
