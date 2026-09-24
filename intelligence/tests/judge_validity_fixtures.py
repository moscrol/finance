"""Offline v2 receipts with actual request/response bindings for integration tests."""

from datetime import datetime, timedelta, timezone
import json
import math
import statistics

from intelligence.eval.judge_validity import (
    bind_answers,
    canonical_hash,
    judge_messages,
    new_manifest,
    seal_manifest,
    stamp_answer,
    text_hash,
)

NOW = datetime(2026, 9, 14, 0, 0, tzinfo=timezone.utc)
DIMENSIONS = ("directness", "coverage", "relevance", "truth_boundary", "usefulness")


def judge_spec():
    return {
        "requested_model": "grok-4",
        "allowed_reported_models": ["grok-4"],
        "model_family_version": "explicit-v1",
        "endpoint_id": "fixture-judge",
        "transport": "http",
        "rubric_version": "fixture-v1",
        "rubric_text": "Score the answer using five dimensions.",
        "temperature": 0.1,
        "thinking": None,
        "max_tokens": 1000,
        "answer_char_limit": 16000,
        "truncation_version": "prefix-v1",
        "retry_prompt": "Only JSON.\n\n",
        "selection_rule": "first_valid",
        "max_attempts": 2,
    }


def writer_provenance(answer, *, model="gpt-5.6-sol", question=None):
    return {
        "schema_version": 1,
        "receipt_id": "receipt-" + text_hash(answer)[:12],
        "receipt_verified": True,
        "question_sha256": canonical_hash({"text": question["text"], "as_of": question["as_of"]}) if question else None,
        "answer_sha256": text_hash(answer),
        "raw_output_sha256": text_hash(answer + "\n"),
        "delivery_state": "delivered",
        "scope": "all_successful_ask_calls",
        "records": [{
            "call_id": "writer-call-" + text_hash(answer)[:12],
            "attempt_id": "writer-attempt-" + text_hash(answer)[:12],
            "phase": "writer",
            "status": "success",
            "identity_state": "reported",
            "requested_model": model,
            "reported_model": model,
            "endpoint_id": "fixture-writer",
            "transport": "http",
            "request_sha256": canonical_hash([{"role": "user", "content": answer}]),
            "result_sha256": text_hash(answer),
        }],
    }


def verdict(manifest, question, answer, *, score=3, suffix="initial", phase="judge"):
    spec = manifest["run_manifest"]["judge_spec"]
    scores = dict.fromkeys(DIMENSIONS, score)
    content = json.dumps(scores, ensure_ascii=False)
    attempt_id = answer["answer_id"] + "-" + suffix
    request_hash = canonical_hash(judge_messages(question, answer["answer"], spec))
    return {
        "scored": True,
        "scores": scores,
        "total": sum(scores.values()),
        "rubric_version": spec["rubric_version"],
        "batch_id": manifest["batch_id"],
        "judge_spec_sha256": manifest["run_manifest"]["judge_spec_sha256"],
        "judge_input_sha256": answer["judge_input_sha256"],
        "selected_attempt_id": attempt_id,
        "raw_content_sha256": text_hash(content),
        "raw_content": content,
        "request_sha256": request_hash,
        "attempt_records": [{
            "call_id": attempt_id + "-call",
            "attempt_id": attempt_id,
            "phase": phase,
            "status": "success",
            "requested_model": spec["requested_model"],
            "reported_model": spec["requested_model"],
            "identity_state": "reported",
            "endpoint_id": spec["endpoint_id"],
            "transport": spec["transport"],
            "request_sha256": request_hash,
            "result_sha256": text_hash(content),
            "started_at": (NOW + timedelta(seconds=10)).isoformat(),
            "completed_at": (NOW + timedelta(seconds=11)).isoformat(),
        }],
    }


def noise_floor(calibration):
    sd = math.sqrt(statistics.fmean(statistics.variance(b["totals"]) for b in calibration))
    return {
        "measured": True,
        "sigma": 2.0,
        "sd_judging": round(sd, 4),
        "sd_delta_single_question": round(sd * math.sqrt(2), 4),
        "batch_id": calibration[0]["batch_id"],
        "judge_spec_sha256": calibration[0]["judge_spec_sha256"],
        "calibration_sha256": canonical_hash(calibration),
    }


def valid_batch(*, zero_variance=False, sealed=True):
    questions = [{"case_id": f"q{i}", "text": f"Question {i}", "as_of": "2026-09-01"} for i in range(2)]
    manifest = new_manifest(questions, ["kb-rag"], judge_spec(), now=NOW)
    answers = []
    for question in questions:
        for arm in ("baseline", "kb-rag"):
            body = f"Answer for {question['case_id']} / {arm}"
            answers.append(stamp_answer(manifest, {
                "case_id": question["case_id"], "arm": arm, "ok": True,
                "answer": body, "writer_provenance": writer_provenance(body, question=question),
            }))
    manifest = bind_answers(manifest, answers)
    calibration = []
    for answer in answers:
        question = next(q for q in questions if q["case_id"] == answer["case_id"])
        answer["judge"] = verdict(manifest, question, answer)
        if answer["arm"] == "baseline":
            repeat = verdict(manifest, question, answer, score=3 if zero_variance else 2,
                             suffix="repeat", phase="calibration")
            calibration.append({
                "case_id": answer["case_id"], "answer_id": answer["answer_id"],
                "answer_sha256": answer["answer_sha256"],
                "judge_input_sha256": answer["judge_input_sha256"],
                "batch_id": manifest["batch_id"],
                "judge_spec_sha256": manifest["run_manifest"]["judge_spec_sha256"],
                "totals": [answer["judge"]["total"], repeat["total"]],
                "repeats": [repeat],
            })
    if sealed:
        manifest = seal_manifest(manifest, now=NOW + timedelta(seconds=30))
    return answers, calibration, manifest, noise_floor(calibration)
