"""The qualification gate must reject incompatible observations, not repair them."""

from copy import deepcopy
from datetime import timedelta

import pytest

from intelligence.eval.judge_validity import (
    _Validation,
    _validate_spec,
    bind_answers,
    canonical_hash,
    model_family,
    validate_judging_batch,
)
from intelligence.tests.judge_validity_fixtures import NOW, judge_spec, valid_batch


def check(batch, *, now=NOW):
    answers, calibration, manifest, floor = batch
    return validate_judging_batch(answers, calibration, manifest, now=now, noise_floor=floor)


def test_complete_batch_and_true_zero_variance_are_valid():
    assert check(valid_batch())["valid"]
    assert check(valid_batch(zero_variance=True))["valid"]


def test_sealed_history_does_not_expire_when_read_later():
    assert check(valid_batch(), now=NOW + timedelta(days=400))["valid"]
    assert "batch_expired" in check(valid_batch(sealed=False), now=NOW + timedelta(days=1))["reason_codes"]


@pytest.mark.parametrize("value", [None, {}, {"schema_version": 1}, {"schema_version": 900}, "bad", []])
def test_unknown_and_malformed_manifests_fail_closed(value):
    assert not validate_judging_batch([], [], value, now=NOW)["valid"]


@pytest.mark.parametrize("mutation", ["delete", "duplicate", "arm", "answer"])
def test_denominator_and_full_answers_cannot_be_rewritten(mutation):
    batch = valid_batch()
    answers = batch[0]
    if mutation == "delete":
        answers.pop()
    elif mutation == "duplicate":
        answers.append(deepcopy(answers[0]))
    elif mutation == "arm":
        answers[0]["arm"] = "other"
    else:
        answers[0]["answer"] += " changed"
    assert not check(batch)["valid"]


@pytest.mark.parametrize("field,value", [("rubric_text", "different"), ("temperature", 0.9), ("answer_char_limit", 2)])
def test_spec_changes_are_rejected_even_when_version_label_is_unchanged(field, value):
    batch = valid_batch()
    batch[2]["run_manifest"]["judge_spec"][field] = value
    assert "manifest_hash_mismatch" in check(batch)["reason_codes"]


def test_question_cutoff_is_part_of_the_frozen_input():
    batch = valid_batch()
    batch[2]["run_manifest"]["questions"][0]["as_of"] = "2026-09-14"
    assert not check(batch)["valid"]


@pytest.mark.parametrize("model,reason", [("gpt-5.6-sol", "judge_identity_mismatch"), (None, "judge_identity_unknown"), ("stranger-1", "judge_identity_unknown")])
def test_response_identity_is_required_and_must_match_the_frozen_spec(model, reason):
    batch = valid_batch()
    batch[0][0]["judge"]["attempt_records"][0]["reported_model"] = model
    assert reason in check(batch)["reason_codes"]


def test_unknown_success_before_json_retry_cannot_be_erased():
    batch = valid_batch()
    verdict = batch[0][0]["judge"]
    unknown = deepcopy(verdict["attempt_records"][0])
    unknown.update(attempt_id="unparseable-first", reported_model=None, identity_state="unreported")
    verdict["attempt_records"].insert(0, unknown)
    assert "judge_identity_unknown" in check(batch)["reason_codes"]


@pytest.mark.parametrize("mutation", ["missing", "content", "request", "late", "duplicate"])
def test_selected_attempt_must_bind_actual_body_input_and_collection_window(mutation):
    batch = valid_batch()
    verdict = batch[0][0]["judge"]
    attempt = verdict["attempt_records"][0]
    if mutation == "missing":
        verdict["selected_attempt_id"] = "absent"
    elif mutation == "content":
        attempt["result_sha256"] = "wrong"
    elif mutation == "request":
        attempt["request_sha256"] = "wrong"
    elif mutation == "late":
        attempt["completed_at"] = (NOW + timedelta(hours=2)).isoformat()
    else:
        verdict["attempt_records"].append(deepcopy(attempt))
    assert not check(batch)["valid"]


def test_historical_writer_and_all_successful_contributors_control_independence():
    batch = valid_batch()
    answer = batch[0][0]
    record = answer["writer_provenance"]["records"][0]
    record["reported_model"] = "grok-4"
    frozen = batch[2]["answer_manifest"]["answers"][0]
    frozen["writer_provenance_sha256"] = canonical_hash(answer["writer_provenance"])
    batch[2]["answer_manifest_sha256"] = canonical_hash(batch[2]["answer_manifest"])
    assert "judge_not_independent" in check(batch)["reason_codes"]


@pytest.mark.parametrize("mutation", ["batch", "text", "repeat", "totals", "floor_binding", "extra"])
def test_calibration_cannot_reuse_a_different_batch_or_pick_successful_samples(mutation):
    batch = valid_batch()
    block = batch[1][0]
    if mutation == "batch":
        block["batch_id"] = "old-batch"
    elif mutation == "text":
        block["answer_id"] = batch[0][1]["answer_id"]
    elif mutation == "repeat":
        block["repeats"] = []
    elif mutation == "totals":
        block["totals"] = [20, 20]
    elif mutation == "floor_binding":
        batch[3]["calibration_sha256"] = "old-calibration"
    else:
        batch[1].append(deepcopy(block))
    assert not check(batch)["valid"]


@pytest.mark.parametrize("field", ["sigma", "sd_judging", "sd_delta_single_question"])
@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), -1, "0"])
def test_noise_must_be_present_finite_and_recomputed(field, value):
    batch = valid_batch()
    batch[3][field] = value
    assert not check(batch)["valid"]


def test_unscored_product_failure_stays_in_denominator():
    batch = valid_batch()
    batch[0][1]["judge"] = {"scored": False}
    assert "judging_incomplete" in check(batch)["reason_codes"]


@pytest.mark.parametrize("mutation", ["not_called", "missing_time", "unknown_status"])
def test_attempt_state_and_timestamps_must_describe_a_real_success(mutation):
    batch = valid_batch()
    attempt = batch[0][0]["judge"]["attempt_records"][0]
    if mutation == "not_called":
        attempt["identity_state"] = "not_called"
    elif mutation == "missing_time":
        attempt["started_at"] = None
    else:
        attempt["status"] = "unrecognized"
    assert not check(batch)["valid"]


@pytest.mark.parametrize("mutation", ["missing", "unreported", "unknown_family", "no_success", "scope", "output"])
def test_writer_provenance_must_be_historical_and_attributable(mutation):
    batch = valid_batch()
    answer = batch[0][0]
    provenance = answer["writer_provenance"]
    if mutation == "missing":
        answer.pop("writer_provenance")
    elif mutation == "unreported":
        provenance["records"][0]["reported_model"] = None
    elif mutation == "unknown_family":
        provenance["records"][0]["reported_model"] = "unfamiliar-2"
    elif mutation == "no_success":
        provenance["records"][0]["status"] = "failed"
    elif mutation == "scope":
        provenance["scope"] = "today_configuration"
    else:
        provenance["answer_sha256"] = "old-output"
    assert not check(batch)["valid"]


def test_correlated_exploration_never_qualifies():
    batch = valid_batch()
    batch[2]["run_manifest"]["independence"] = "allow-correlated"
    assert "judge_not_independent" in check(batch)["reason_codes"]


def test_plausible_noise_is_recomputed_from_the_raw_scores():
    batch = valid_batch()
    batch[3]["sd_judging"] = 0.01
    batch[3]["sd_delta_single_question"] = 0.0141
    assert "noise_floor_mismatch" in check(batch)["reason_codes"]


def test_already_bound_answers_cannot_be_rebound():
    answers, _, manifest, _ = valid_batch(sealed=False)
    with pytest.raises(ValueError, match="bound"):
        bind_answers(manifest, answers)


@pytest.mark.parametrize("label,family", [("judge/gpt-5.6-sol", "gpt"), ("grok-4", "grok"), ("GLM-5", "glm"), ("foo-v1", "unknown"), ("", "unknown"), (None, "unknown")])
def test_family_recognition_is_explicit(label, family):
    assert model_family(label) == family


def _refreeze_writer(batch, index=0):
    answer = batch[0][index]
    binding = batch[2]["answer_manifest"]["answers"][index]
    binding["writer_provenance_sha256"] = canonical_hash(answer["writer_provenance"])
    batch[2]["answer_manifest_sha256"] = canonical_hash(batch[2]["answer_manifest"])


@pytest.mark.parametrize("mutation", ["missing", "body", "scores"])
def test_scores_must_reproduce_the_selected_raw_json_response(mutation):
    batch = valid_batch()
    verdict = batch[0][1]["judge"]
    if mutation == "missing":
        verdict.pop("raw_content")
    elif mutation == "body":
        verdict["raw_content"] = "{}"
    else:
        verdict["scores"] = dict.fromkeys(verdict["scores"], 4)
        verdict["total"] = 20
    assert "judge_result_mismatch" in check(batch)["reason_codes"]


def test_one_logical_call_cannot_be_reused_for_two_answers():
    batch = valid_batch()
    batch[0][1]["judge"]["attempt_records"][0]["call_id"] = batch[0][0]["judge"]["attempt_records"][0]["call_id"]
    assert "judge_call_duplicate" in check(batch)["reason_codes"]


@pytest.mark.parametrize("mutation", ["unverified", "wrong_question", "no_receipt"])
def test_writer_receipt_requires_the_subprocess_verification(mutation):
    batch = valid_batch()
    provenance = batch[0][0]["writer_provenance"]
    if mutation == "unverified":
        provenance.pop("receipt_verified")
    elif mutation == "wrong_question":
        provenance["question_sha256"] = "0" * 64
    else:
        provenance.pop("receipt_id")
    _refreeze_writer(batch)
    assert "writer_provenance_mismatch" in check(batch)["reason_codes"]


@pytest.mark.parametrize("state", ["no_answer", "clarification", None])
def test_undelivered_answers_never_qualify_even_if_scored(state):
    batch = valid_batch()
    batch[0][0]["writer_provenance"]["delivery_state"] = state
    _refreeze_writer(batch)
    assert "product_undelivered" in check(batch)["reason_codes"]


def test_product_error_cannot_be_reclassified_by_a_valid_judge():
    batch = valid_batch()
    batch[0][0]["ok"] = False
    assert "product_undelivered" in check(batch)["reason_codes"]


def test_reading_an_open_batch_before_its_start_is_invalid():
    assert "batch_window_violation" in check(valid_batch(sealed=False), now=NOW - timedelta(seconds=1))["reason_codes"]


def test_noise_multiplier_is_frozen_before_scoring():
    batch = valid_batch()
    batch[3]["sigma"] = 0.01
    assert "noise_floor_mismatch" in check(batch)["reason_codes"]


@pytest.mark.parametrize("transport,limit,valid", [
    ("http", None, False), ("cli", None, True), ("http", True, False),
    ("http", 1000, True), ("http", 0.5, False),
])
def test_effective_token_cap_is_an_integer_or_explicit_cli_absence(transport, limit, valid):
    spec = judge_spec() | {"transport": transport, "max_tokens": limit}
    gate = _Validation()
    _validate_spec(spec, gate)
    assert gate.result()["valid"] is valid
