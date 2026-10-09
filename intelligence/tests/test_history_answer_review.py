"""Review receipts are complete, source-bound and distinct from a truth certificate."""
from copy import deepcopy
import json

import pytest

from intelligence.history_context_cli import history_payload
from intelligence.services import history_answer_review as review
from intelligence.tests.test_river_history_consumption import _make_db


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    db = tmp_path_factory.mktemp("history-review") / "synthetic.duckdb"
    _make_db(db)
    return history_payload(db, as_of="2025-04-10", review_readouts=True)


def request_for(source, draft="当前窗涨家数均值2492家。\n涨家数方向为一方近零。"):
    return review.build_history_review("截至2025-04-10，比较历史窗口。", draft, [source])


def report_for(request):
    supported = [{"claim_id": row["claim_id"], "supported": True, "reason": "同窗具名读数支持此句。",
                  "support_kind": "bound_material", "anchor_indexes": [1]} for row in request["claims"]]
    return {"request_id": request["request_id"], "passed": True, "rejected_sentence_indexes": [], "issues": [],
            "material_claim_checks": supported,
            "material_output_checks": [{"output_id": "history_answer", "answered": True,
                                        "answer_sentence_indexes": [1], "reason": "给出历史比较读数。"}]}


def test_typed_readouts_keep_identity_kind_units_and_missingness(source):
    request = request_for(source)
    rows = request["readouts"]
    missing = next(row for row in rows if row["kind"] == "observation_coverage" and row["value"].get("feature") == "登记判断数")
    assert missing["value"]["read_status"] == "not_requested"
    assert missing["value"]["non_null_days"] == 0
    direction = next(row for row in rows if row["kind"] == "signatures" and row["value"].get("window_ref") == "river.1" and row["value"]["feature"] == "涨家数")
    assert direction["value"]["direction_relation"] == "一方近零"
    assert direction["value"]["source_unit"] == "家"
    assert direction["value"]["window_dates"] == ["2025-01-22", "2025-02-18"]
    assert request["evidence_grade"] == "INFERRED"
    assert "观测" in request["reading_semantics"]["non_null_days"]
    assert request["reading_semantics"]["direction_relation"]["near_zero_closed_interval"] == [-0.3, 0.3]
    assert review.review_messages(request)[0]["role"] == "system"
    assert "response_schema" in json.loads(review.review_messages(request)[1]["content"])


def test_readout_mapping_order_is_not_part_of_semantic_identity(source):
    packet = deepcopy(source)
    for item in packet["readouts"]:
        item["payload"] = dict(reversed(list(item["payload"].items())))
    assert request_for(packet)["request_id"] == request_for(source)["request_id"]


def test_input_objects_are_not_mutated_or_borrowed(source):
    copy = deepcopy(source)
    before = deepcopy(copy)
    request = request_for(copy)
    assert copy == before
    copy["readouts"][0]["payload"]["windows"]["d10.1"][0] = "1900-01-01"
    assert "1900-01-01" not in json.dumps(request)


def test_complete_receipt_is_explicitly_a_review_not_fact_promotion(source):
    request = request_for(source)
    result = review.validate_history_review(request, report_for(request))
    assert result["status"] == "reviewed"
    assert result["semantic_review_not_fact_promotion"]
    assert len(result["claim_checks"]) == len(request["claims"])
    assert result["claim_checks"][0]["material_anchors"][0] == request["readouts"][0]


@pytest.mark.parametrize("mutation", ["stale", "missing", "duplicate", "wrong_id", "wrong_index", "bool_index", "bool_pass", "non_object", "unknown_field", "bad_kind", "blank_reason", "no_outputs", "empty_support"])
def test_invalid_receipts_cannot_pass(source, mutation):
    request = request_for(source)
    payload = report_for(request)
    if mutation == "stale":
        payload["request_id"] = "old-draft"
    elif mutation == "missing":
        payload["material_claim_checks"].pop()
    elif mutation == "duplicate":
        payload["material_claim_checks"][1] = deepcopy(payload["material_claim_checks"][0])
    elif mutation == "wrong_id":
        payload["material_claim_checks"][0]["claim_id"] = "invented"
    elif mutation == "wrong_index":
        payload["material_claim_checks"][0]["anchor_indexes"] = [len(request["readouts"]) + 1]
    elif mutation == "bool_index":
        payload["material_claim_checks"][0]["anchor_indexes"] = [True]
    elif mutation == "bool_pass":
        payload["passed"] = 1
    elif mutation == "non_object":
        payload = []
    elif mutation == "unknown_field":
        payload["new_answer"] = "silently replace the draft"
    elif mutation == "bad_kind":
        payload["material_claim_checks"][0]["support_kind"] = "approved"
    elif mutation == "blank_reason":
        payload["material_claim_checks"][0]["reason"] = " "
    elif mutation == "no_outputs":
        payload["material_output_checks"] = []
    else:
        payload["material_claim_checks"][0]["anchor_indexes"] = []
    assert review.validate_history_review(request, payload)["status"] == "unavailable"


def test_per_statement_rejection_overrides_global_pass(source):
    request = request_for(source, "涨家数动能相反。")
    payload = report_for(request)
    payload["material_claim_checks"][0].update(supported=False, support_kind="contradicted", reason="具名方向是一方近零，不是反向。")
    result = review.validate_history_review(request, payload)
    assert result["status"] == "revision_required"
    assert result["rejected_sentence_indexes"] == [1]
    assert "一方近零" in " ".join(result["issues"])


def test_all_nonfactual_cannot_masquerade_as_a_complete_history_answer(source):
    request = request_for(source)
    payload = report_for(request)
    for check in payload["material_claim_checks"]:
        check.update(support_kind="nonfactual", anchor_indexes=[])
    assert review.validate_history_review(request, payload)["status"] == "unavailable"


def test_factual_support_does_not_imply_answer_completeness(source):
    request = request_for(source)
    payload = report_for(request)
    payload["material_output_checks"][0].update(answered=False, answer_sentence_indexes=[], reason="只复述当前数据，未比较历史。")
    result = review.validate_history_review(request, payload)
    assert result["status"] == "revision_required"
    assert result["rejected_sentence_indexes"] == []


def test_duplicate_sentence_occurrences_have_distinct_coverage(source):
    request = request_for(source, "方向是一方近零。\n方向是一方近零。")
    assert len(request["claims"]) == 2
    assert request["claims"][0]["text"] == request["claims"][1]["text"]
    assert len({row["claim_id"] for row in request["claims"]}) == 2


def test_nonfactual_escape_requires_an_isolated_second_review(source):
    request = request_for(source, "## 历史比较\n研报有0条。\n当前均值2492家。")
    payload = report_for(request)
    payload["material_output_checks"][0]["answer_sentence_indexes"] = [3]
    for check in payload["material_claim_checks"][:2]:
        check.update(support_kind="nonfactual", anchor_indexes=[])
    first = review.validate_history_review(request, payload)
    assert first["status"] == "reviewed"
    audit = review.build_nonfactual_audit(request, first)
    assert audit is not None and audit["readouts"] == []
    assert "2492" not in json.dumps(audit, ensure_ascii=False)
    assert review.combine_history_reviews(first, audit, None)["status"] == "unavailable"
    checks = [{"claim_id": row["claim_id"], "supported": i == 0,
               "reason": "纯标题。" if i == 0 else "0条是指标值断言，不是非事实。",
               "support_kind": "nonfactual" if i == 0 else "unsupported", "anchor_indexes": []}
              for i, row in enumerate(audit["claims"])]
    second = review.validate_history_review(audit, {"request_id": audit["request_id"], "passed": False,
        "rejected_sentence_indexes": [2], "issues": [], "material_claim_checks": checks})
    combined = review.combine_history_reviews(first, audit, second)
    assert combined["status"] == "revision_required"
    assert combined["rejected_sentence_indexes"] == [2]


@pytest.mark.parametrize("mutation", ["text", "hash", "cutoff", "readout", "schema", "grade"])
def test_source_tampering_is_rejected(source, mutation):
    packet = deepcopy(source)
    if mutation == "readout":
        packet["readouts"][0]["payload"]["current_window"][0] = "1900-01-01"
    elif mutation == "hash":
        packet["readouts"][0]["source_sha256"] = "0" * 64
    elif mutation == "schema":
        packet["schema_version"] = "unknown"
    else:
        public = json.loads(packet["public_text"])
        if mutation == "text":
            public["blocks"][0]["detail"] += " forged"
        elif mutation == "cutoff":
            public["as_of"] = "2025-05-01"
        else:
            public["evidence_grade"] = "VERIFIED"
        packet["public_text"] = json.dumps(public, ensure_ascii=False)
    with pytest.raises(ValueError):
        request_for(packet)


def test_changed_request_cannot_reuse_a_good_report(source):
    request = request_for(source)
    report = report_for(request)
    request["claims"][0]["text"] = "偷换后的正文"
    assert review.validate_history_review(request, report)["status"] == "unavailable"


def test_input_budget_is_atomic_and_missing_source_never_calls_a_reviewer(source):
    with pytest.raises(ValueError):
        review.build_history_review("q", "x" * (review.MAX_DRAFT_CHARS + 1), [source])
    with pytest.raises(ValueError):
        review.build_history_review("q", "answer", [])
    with pytest.raises(ValueError):
        review.build_history_review("q", "a。" * (review.MAX_STATEMENTS + 1), [source])


def test_one_json_fence_is_only_framing_not_a_relaxed_receipt(source):
    request = request_for(source)
    text = json.dumps(report_for(request))
    assert review.validate_history_review(request, f"```json\n{text}\n```")["status"] == "reviewed"
    assert review.validate_history_review(request, f"prefix\n```json\n{text}\n```")["status"] == "unavailable"
    assert review.validate_history_review(request, f"```json\n{text}\n```\nsuffix")["status"] == "unavailable"


def test_duplicate_json_fields_cannot_hide_a_rejection(source):
    request = request_for(source)
    text = json.dumps(report_for(request)).replace('"passed": true', '"passed": false, "passed": true')
    assert review.validate_history_review(request, text)["status"] == "unavailable"


def test_bare_negative_without_any_basis_is_unavailable(source):
    request = request_for(source)
    payload = report_for(request)
    payload["passed"] = False
    assert review.validate_history_review(request, payload)["status"] == "unavailable"


@pytest.mark.parametrize("packet", [None, [], {}, {"schema_version": "finance-history-review-source/v1", "public_text": "[]"}])
def test_malformed_source_has_a_stable_admission_failure(packet):
    with pytest.raises(ValueError):
        review.build_history_review("q", "draft", [packet])


def test_available_source_cannot_lose_its_typed_readout(source):
    packet = deepcopy(source)
    packet["readouts"][0]["payload"] = None
    with pytest.raises(ValueError, match="typed readout missing"):
        request_for(packet)


def test_review_bridge_rejects_nonobject_and_over_budget_input():
    from pathlib import Path
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[2]
    for body in ("[]", "x" * (512 * 1024 + 1)):
        result = subprocess.run([sys.executable, "-m", "intelligence.history_answer_review_cli", "prepare"],
                                input=body, text=True, capture_output=True, cwd=root, timeout=20)
        assert result.returncode == 2
        assert json.loads(result.stdout) == {"error": "history_review_unavailable"}
        assert result.stderr == ""
