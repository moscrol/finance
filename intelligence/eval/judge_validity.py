"""Pure qualification of versioned judging receipts; no environment or model IO.

Response model names are declarations from the serving endpoint, not an
authentication of model weights. Missing evidence never inherits today's config.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import re
import statistics
from uuid import uuid4

from intelligence.call_identity import IDENTITY_REPORTED, IDENTITY_UNREPORTED


SCHEMA_VERSION = 2
MODEL_FAMILY_VERSION = "explicit-v1"
_DIMENSIONS = ("directness", "coverage", "relevance", "truth_boundary", "usefulness")
_SPEC_FIELDS = {
    "requested_model", "allowed_reported_models", "model_family_version",
    "endpoint_id", "transport", "rubric_version", "rubric_text", "temperature",
    "thinking", "max_tokens", "answer_char_limit", "truncation_version",
    "retry_prompt", "selection_rule", "max_attempts",
}


def canonical_hash(value: object) -> str:
    """Hash JSON values without whitespace, nonfinite numbers, or key-order drift."""
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
    return text_hash(payload)


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def model_family(label: object) -> str:
    if not isinstance(label, str):
        return "unknown"
    name = label.rsplit("/", 1)[-1].strip().lower()
    for family in ("gpt", "grok", "glm", "claude", "gemini", "deepseek", "qwen", "moonshot", "kimi", "mistral", "llama"):
        if re.match(rf"^{family}(?:$|[-_.\d])", name):
            return "moonshot" if family == "kimi" else family
    if re.match(r"^o[134](?:$|[-_.])", name):
        return "gpt"
    return "unknown"


def _instant(value: object = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    result = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if not isinstance(result, datetime) or result.tzinfo is None:
        raise ValueError("an aware timestamp is required")
    return result.astimezone(timezone.utc)


def _number(value: object, *, positive: bool = False) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and (value > 0 if positive else value >= 0))


def _stored_instant(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("a stored ISO timestamp is required")
    return _instant(value)


def _digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _question_dict(question: object) -> dict:
    if isinstance(question, Mapping):
        return dict(question)
    raise ValueError("questions must be JSON objects")


def judge_messages(question: Mapping, answer: str, spec: Mapping, *, retry: bool = False) -> list[dict]:
    """The one frozen prompt construction used for dispatch and request verification."""
    limit = spec["answer_char_limit"]
    body = answer[:limit]
    header = "（以下答案已按预算截断，只保留开头部分）\n" if len(answer) > limit else ""
    prompt = f"问题：{question['text']}\n\n{header}答案：\n{body}"
    if retry:
        prompt = spec["retry_prompt"] + prompt
    return [{"role": "system", "content": spec["rubric_text"]},
            {"role": "user", "content": prompt}]


def judge_input_hash(question: Mapping, answer: str, spec: Mapping) -> str:
    return canonical_hash({"question": dict(question),
                           "answer": answer[:spec["answer_char_limit"]],
                           "truncated": len(answer) > spec["answer_char_limit"],
                           "truncation_version": spec["truncation_version"]})


def new_manifest(questions: Sequence[Mapping], component_ids: Sequence[str], judge_spec: Mapping, *,
                 source_run_sha256: str | None = None, parent_batch_id: str | None = None,
                 calibration_repeats: int = 1, batch_max_seconds: int = 3600,
                 now: datetime | None = None, independence: str = "require") -> dict:
    started = _instant(now)
    if (not isinstance(calibration_repeats, int) or isinstance(calibration_repeats, bool)
            or calibration_repeats < 0 or not _number(batch_max_seconds, positive=True)):
        raise ValueError("invalid calibration repeats or batch duration")
    batch_id = uuid4().hex
    run = {
        "batch_id": batch_id,
        "source_run_sha256": source_run_sha256,
        "parent_batch_id": parent_batch_id,
        "questions": [_question_dict(q) for q in questions],
        "arms": ["baseline", *component_ids],
        "judge_spec": deepcopy(dict(judge_spec)),
        "judge_spec_sha256": canonical_hash(judge_spec),
        "started_at": started.isoformat(),
        "expires_at": (started + timedelta(seconds=batch_max_seconds)).isoformat(),
        "independence": independence,
        "calibration_plan": {"selection": "all_baselines", "include_initial": True,
                             "repeats": calibration_repeats, "sigma": 2.0},
        "denominator": "all_registered_question_arms",
    }
    return {"schema_version": SCHEMA_VERSION, "batch_id": batch_id, "state": "open",
            "run_manifest": run, "run_manifest_sha256": canonical_hash(run),
            "answer_manifest": None, "answer_manifest_sha256": None, "sealed_at": None}


def stamp_answer(manifest: Mapping, answer: Mapping) -> dict:
    run = manifest["run_manifest"]
    question = next(q for q in run["questions"] if q["case_id"] == answer["case_id"])
    if answer["arm"] not in run["arms"] or not isinstance(answer.get("answer"), str):
        raise ValueError("answer must belong to a registered arm and contain text")
    result = deepcopy(dict(answer))
    result["answer_sha256"] = text_hash(answer["answer"])
    result["answer_id"] = canonical_hash({
        "source_run_sha256": run["source_run_sha256"] or manifest["run_manifest_sha256"],
        "case_id": answer["case_id"], "arm": answer["arm"],
        "answer_sha256": result["answer_sha256"],
    })
    result["judge_input_sha256"] = judge_input_hash(question, answer["answer"], run["judge_spec"])
    return result


def _answer_binding(manifest: Mapping, answer: Mapping) -> dict:
    stamped = stamp_answer(manifest, answer)
    return {key: stamped[key] for key in ("case_id", "arm", "answer_id", "answer_sha256", "judge_input_sha256")} | {
        "writer_provenance_sha256": canonical_hash(answer.get("writer_provenance"))}


def bind_answers(manifest: Mapping, answers: Sequence[Mapping]) -> dict:
    if manifest.get("state") != "open" or manifest.get("answer_manifest") is not None:
        raise ValueError("answers are already bound or the batch is not open")
    result = deepcopy(dict(manifest))
    bindings = [_answer_binding(manifest, answer) for answer in answers]
    planned_scores = manifest["run_manifest"]["calibration_plan"]["repeats"] + 1
    bound = {
        "run_manifest_sha256": manifest["run_manifest_sha256"], "answers": bindings,
        "calibration": [{key: row[key] for key in ("case_id", "answer_id", "answer_sha256", "judge_input_sha256")} | {
            "planned_scores": planned_scores} for row in bindings if row["arm"] == "baseline"],
    }
    result["answer_manifest"] = bound
    result["answer_manifest_sha256"] = canonical_hash(bound)
    return result


def seal_manifest(manifest: Mapping, *, now: datetime | None = None) -> dict:
    if manifest.get("state") != "open" or manifest.get("answer_manifest") is None:
        raise ValueError("only an open, answer-bound batch can be sealed")
    result = deepcopy(dict(manifest))
    result["sealed_at"] = _instant(now).isoformat()
    result["state"] = "sealed"
    return result


class _Validation:
    def __init__(self):
        self.reasons: set[str] = set()
        self.invalid_ids: set[str] = set()
        self.judge_models: set[str] = set()
        self.attempt_ids: set[str] = set()
        self.call_ids: set[str] = set()

    def reject(self, reason: str, answer_id: object = None):
        self.reasons.add(reason)
        if isinstance(answer_id, str):
            self.invalid_ids.add(answer_id)

    def result(self) -> dict:
        return {"valid": not self.reasons, "reason_codes": sorted(self.reasons),
                "invalid_answer_ids": sorted(self.invalid_ids)}


def _validate_spec(spec: Mapping, gate: _Validation):
    if not _SPEC_FIELDS.issubset(spec):
        gate.reject("judge_spec_incomplete")
        return
    allowed = spec["allowed_reported_models"]
    if (not isinstance(allowed, list) or not allowed
            or any(not isinstance(model, str) or not model for model in allowed)):
        gate.reject("judge_spec_incomplete")
    if (spec["model_family_version"] != MODEL_FAMILY_VERSION
            or spec["truncation_version"] != "prefix-v1"
            or spec["selection_rule"] != "first_valid"
            or not isinstance(spec["rubric_text"], str) or not spec["rubric_text"]
            or not isinstance(spec["retry_prompt"], str)
            or not isinstance(spec["rubric_version"], str) or not spec["rubric_version"]
            or not isinstance(spec["endpoint_id"], str) or not spec["endpoint_id"]
            or spec["transport"] not in ("http", "cli")
            or not (spec["transport"] == "cli" and spec["temperature"] is None
                    or _number(spec["temperature"]))
            or not (spec["transport"] == "cli" and spec["max_tokens"] is None
                    or type(spec["max_tokens"]) is int and spec["max_tokens"] > 0)
            or type(spec["answer_char_limit"]) is not int or spec["answer_char_limit"] <= 0
            or type(spec["max_attempts"]) is not int or spec["max_attempts"] <= 0):
        gate.reject("judge_spec_incomplete")
    if model_family(spec["requested_model"]) == "unknown":
        gate.reject("judge_identity_unknown")


def _writer_families(answer: Mapping, question: Mapping, gate: _Validation) -> set[str]:
    answer_id = answer.get("answer_id")
    provenance = answer.get("writer_provenance")
    if not isinstance(provenance, Mapping):
        gate.reject("writer_identity_unknown", answer_id)
        return set()
    if (provenance.get("answer_sha256") != text_hash(answer["answer"])
            or not _digest(provenance.get("raw_output_sha256"))
            or provenance.get("schema_version") != 1
            or provenance.get("receipt_verified") is not True
            or not isinstance(provenance.get("receipt_id"), str) or not provenance["receipt_id"]
            or provenance.get("question_sha256") != canonical_hash({
                "text": question["text"], "as_of": question["as_of"]})):
        gate.reject("writer_provenance_mismatch", answer_id)
    if (answer.get("ok") is not True or not answer["answer"].strip()
            or provenance.get("delivery_state") != "delivered"):
        gate.reject("product_undelivered", answer_id)
    if provenance.get("scope") != "all_successful_ask_calls":
        gate.reject("writer_identity_unknown", answer_id)
    records = provenance.get("records")
    if not isinstance(records, list):
        gate.reject("writer_identity_unknown", answer_id)
        return set()
    families = set()
    ids = set()
    for record in records:
        if not isinstance(record, Mapping):
            gate.reject("writer_provenance_mismatch", answer_id)
            continue
        if record.get("status") != "success":
            continue
        if (record.get("phase") != "writer"
                or not _digest(record.get("request_sha256"))
                or not _digest(record.get("result_sha256"))):
            gate.reject("writer_provenance_mismatch", answer_id)
        attempt_id = record.get("attempt_id")
        if not isinstance(attempt_id, str) or not attempt_id or attempt_id in ids:
            gate.reject("writer_provenance_mismatch", answer_id)
        ids.add(attempt_id)
        family = model_family(record.get("reported_model"))
        if (record.get("identity_state") != IDENTITY_REPORTED or family == "unknown"
                or record.get("identity_conflict") or not record.get("call_id")):
            gate.reject("writer_identity_unknown", answer_id)
        else:
            families.add(family)
    if not families:
        gate.reject("writer_identity_unknown", answer_id)
    return families


def _raw_scores(content: object, dimensions: Sequence[str]) -> dict | None:
    if not isinstance(content, str):
        return None
    # Use the same JSON-envelope extraction as the scoring adapter without a
    # dependency from this pure module back into services.
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
    braces = fence or re.search(r"\{.*\}", content, re.DOTALL)
    payload = fence.group(1) if fence else braces.group(0) if braces else content
    try:
        parsed = json.loads(payload)
        if not isinstance(parsed, Mapping):
            return None
        if any(type(parsed.get(d)) is not int for d in dimensions):
            return None
        return {dimension: parsed[dimension] for dimension in dimensions}
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def _validate_verdict(verdict: object, answer: Mapping, question: Mapping, manifest: Mapping,
                      writer_families: set[str], gate: _Validation, *, phase: str) -> float | None:
    answer_id = answer["answer_id"]
    if not isinstance(verdict, Mapping):
        gate.reject("judging_incomplete", answer_id)
        return None
    run = manifest["run_manifest"]
    spec = run["judge_spec"]
    scored = verdict.get("scored") is True
    if not scored:
        gate.reject("judging_incomplete" if phase == "judge" else "calibration_incomplete", answer_id)
    if scored and (verdict.get("batch_id") != manifest["batch_id"]
                   or verdict.get("judge_spec_sha256") != run["judge_spec_sha256"]
                   or verdict.get("judge_input_sha256") != answer["judge_input_sha256"]
                   or verdict.get("rubric_version") != spec["rubric_version"]):
        gate.reject("judging_binding_mismatch", answer_id)
    records = verdict.get("attempt_records", [])
    if not isinstance(records, list):
        gate.reject("judge_attempt_missing", answer_id)
        return None
    if len(records) > spec["max_attempts"]:
        gate.reject("judge_attempt_budget_exceeded", answer_id)
    expected_requests = {canonical_hash(judge_messages(question, answer["answer"], spec, retry=retry))
                         for retry in (False, True)}
    selected = []
    local_call_ids = set()
    started, expires = _stored_instant(run["started_at"]), _stored_instant(run["expires_at"])
    sealed = _stored_instant(manifest["sealed_at"]) if manifest.get("sealed_at") else expires
    for record in records:
        if not isinstance(record, Mapping):
            gate.reject("judge_attempt_missing", answer_id)
            continue
        attempt_id = record.get("attempt_id")
        if not isinstance(attempt_id, str) or not attempt_id or attempt_id in gate.attempt_ids:
            gate.reject("judge_attempt_duplicate", answer_id)
        gate.attempt_ids.add(attempt_id)
        call_id = record.get("call_id")
        if not isinstance(call_id, str) or not call_id:
            gate.reject("judge_attempt_invalid", answer_id)
        else:
            if call_id in gate.call_ids:
                gate.reject("judge_call_duplicate", answer_id)
            local_call_ids.add(call_id)
        if attempt_id == verdict.get("selected_attempt_id"):
            selected.append(record)
        if (record.get("identity_state") not in (IDENTITY_REPORTED, IDENTITY_UNREPORTED)
                or record.get("status") not in ("success", "failed")):
            gate.reject("judge_attempt_invalid", answer_id)
        try:
            begin, end = _stored_instant(record["started_at"]), _stored_instant(record["completed_at"])
            if not started <= begin <= end <= min(expires, sealed):
                gate.reject("batch_window_violation", answer_id)
        except (KeyError, TypeError, ValueError):
            gate.reject("batch_window_violation", answer_id)
        if record.get("request_sha256") not in expected_requests:
            gate.reject("judge_request_mismatch", answer_id)
        if (record.get("phase") != phase or record.get("endpoint_id") != spec["endpoint_id"]
                or record.get("transport") != spec["transport"]
                or record.get("requested_model") != spec["requested_model"] or not record.get("call_id")):
            gate.reject("judge_spec_mismatch", answer_id)
        if record.get("status") != "success":
            continue
        reported = record.get("reported_model")
        family = model_family(reported)
        if record.get("identity_state") != IDENTITY_REPORTED or family == "unknown":
            gate.reject("judge_identity_unknown", answer_id)
        else:
            gate.judge_models.add(reported)
        if record.get("identity_conflict") or reported not in spec["allowed_reported_models"]:
            gate.reject("judge_identity_mismatch", answer_id)
        if family in writer_families:
            gate.reject("judge_not_independent", answer_id)
    gate.call_ids.update(local_call_ids)
    if not scored:
        return None
    if len(selected) != 1 or selected[0].get("status") != "success":
        gate.reject("judge_attempt_missing", answer_id)
    elif (selected[0].get("result_sha256") != verdict.get("raw_content_sha256")
          or not _digest(verdict.get("raw_content_sha256"))
          or selected[0].get("request_sha256") != verdict.get("request_sha256")):
        gate.reject("judge_result_mismatch", answer_id)
    scores = verdict.get("scores")
    dimensions = spec.get("dimensions", _DIMENSIONS)
    content = verdict.get("raw_content")
    if (not isinstance(content, str) or text_hash(content) != verdict.get("raw_content_sha256")
            or _raw_scores(content, dimensions) != scores):
        gate.reject("judge_result_mismatch", answer_id)
    if (not isinstance(scores, Mapping) or set(scores) != set(dimensions)
            or any(not _number(value) or value > 4 for value in scores.values())
            or not _number(verdict.get("total"))
            or verdict["total"] != sum(scores.values())):
        gate.reject("judge_score_invalid", answer_id)
        return None
    return float(verdict["total"])


def _validate_batch(answers: object, calibration: object, manifest: object,
                    now: object, noise_floor: object, gate: _Validation):
    if not isinstance(manifest, Mapping) or manifest.get("schema_version") != SCHEMA_VERSION:
        gate.reject("unsupported_schema")
        return
    run, bound = manifest.get("run_manifest"), manifest.get("answer_manifest")
    if not isinstance(run, Mapping) or not isinstance(bound, Mapping):
        gate.reject("manifest_incomplete")
        return
    if (canonical_hash(run) != manifest.get("run_manifest_sha256")
            or canonical_hash(bound) != manifest.get("answer_manifest_sha256")
            or bound.get("run_manifest_sha256") != manifest.get("run_manifest_sha256")
            or run.get("batch_id") != manifest.get("batch_id")
            or canonical_hash(run.get("judge_spec")) != run.get("judge_spec_sha256")):
        gate.reject("manifest_hash_mismatch")
    spec = run["judge_spec"]
    _validate_spec(spec, gate)
    if "judge_spec_incomplete" in gate.reasons:
        return
    state = manifest.get("state")
    started, expires = _stored_instant(run["started_at"]), _stored_instant(run["expires_at"])
    if started >= expires:
        gate.reject("batch_window_violation")
    if state == "open":
        current = _instant(now)
        if current < started:
            gate.reject("batch_window_violation")
        if current >= expires:
            gate.reject("batch_expired")
    elif state == "sealed":
        if not manifest.get("sealed_at") or not started <= _stored_instant(manifest["sealed_at"]) <= expires:
            gate.reject("batch_window_violation")
    else:
        gate.reject("batch_invalid")
    if run.get("independence") != "require":
        gate.reject("judge_not_independent")
    questions = run["questions"]
    question_map = {q["case_id"]: q for q in questions}
    arms = run["arms"]
    if (not questions or len(question_map) != len(questions) or not arms
            or len(set(arms)) != len(arms) or arms[0] != "baseline"
            or run.get("denominator") != "all_registered_question_arms"):
        gate.reject("manifest_denominator_mismatch")
    expected = {(case_id, arm) for case_id in question_map for arm in arms}
    if not isinstance(answers, list) or not isinstance(calibration, list):
        gate.reject("invalid_input")
        return
    actual = [(answer["case_id"], answer["arm"]) for answer in answers]
    frozen = [(answer["case_id"], answer["arm"]) for answer in bound["answers"]]
    if (len(actual) != len(expected) or set(actual) != expected
            or len(frozen) != len(expected) or set(frozen) != expected):
        gate.reject("manifest_denominator_mismatch")
    bindings = {(row["case_id"], row["arm"]): row for row in bound["answers"]}
    originals = {}
    families = {}
    for answer in answers:
        key = (answer["case_id"], answer["arm"])
        if key not in expected:
            gate.reject("answer_binding_mismatch", answer.get("answer_id"))
            continue
        binding = _answer_binding(manifest, answer)
        if (bindings.get(key) != binding
                or any(answer.get(field) != binding[field] for field in ("answer_id", "answer_sha256", "judge_input_sha256"))):
            gate.reject("answer_binding_mismatch", answer.get("answer_id"))
        answer_id = answer.get("answer_id", binding["answer_id"])
        if answer_id in originals:
            gate.reject("answer_binding_mismatch", answer_id)
        originals[answer_id] = answer
        families[answer_id] = _writer_families(answer, question_map[answer["case_id"]], gate)
        _validate_verdict(answer.get("judge"), answer, question_map[answer["case_id"]], manifest,
                          families[answer_id], gate, phase="judge")

    plan = run["calibration_plan"]
    if (plan.get("selection") != "all_baselines" or plan.get("include_initial") is not True
            or not isinstance(plan.get("repeats"), int) or isinstance(plan.get("repeats"), bool)
            or plan["repeats"] < 1 or not _number(plan.get("sigma"), positive=True)):
        gate.reject("calibration_incomplete")
    samples = bound["calibration"]
    baseline_ids = {a["answer_id"] for a in bound["answers"] if a["arm"] == "baseline"}
    sample_map = {row["answer_id"]: row for row in samples}
    if len(samples) != len(baseline_ids) or set(sample_map) != baseline_ids:
        gate.reject("calibration_binding_mismatch")
    if len({row["judge_input_sha256"] for row in samples}) < 2:
        gate.reject("calibration_incomplete")
    # Different questions with the same answer text do not supply two texts.
    if len({originals[key]["answer"][:spec["answer_char_limit"]] for key in baseline_ids if key in originals}) < 2:
        gate.reject("calibration_incomplete")
    actual_samples = [block["answer_id"] for block in calibration]
    if len(actual_samples) != len(baseline_ids) or set(actual_samples) != baseline_ids:
        gate.reject("calibration_incomplete")
    variances = []
    for block in calibration:
        answer_id = block["answer_id"]
        if answer_id not in sample_map or answer_id not in originals:
            gate.reject("calibration_binding_mismatch", answer_id)
            continue
        sample, answer = sample_map[answer_id], originals[answer_id]
        if (any(block.get(key) != sample[key] for key in ("case_id", "answer_id", "answer_sha256", "judge_input_sha256"))
                or block.get("batch_id") != manifest["batch_id"]
                or block.get("judge_spec_sha256") != run["judge_spec_sha256"]):
            gate.reject("calibration_binding_mismatch", answer_id)
        repeats = block.get("repeats")
        if (not isinstance(repeats, list) or len(repeats) != plan["repeats"]
                or sample["planned_scores"] != plan["repeats"] + 1):
            gate.reject("calibration_incomplete", answer_id)
            continue
        initial = answer.get("judge", {})
        totals = [float(initial["total"])] if initial.get("scored") is True and _number(initial.get("total")) else []
        for repeat in repeats:
            total = _validate_verdict(repeat, answer, question_map[answer["case_id"]], manifest,
                                      families[answer_id], gate, phase="calibration")
            if total is not None:
                totals.append(total)
        if len(totals) != sample["planned_scores"] or len(totals) < 2:
            gate.reject("calibration_incomplete", answer_id)
        elif block.get("totals") != totals:
            gate.reject("calibration_binding_mismatch", answer_id)
        else:
            variances.append(statistics.variance(totals))
    if len(gate.judge_models) > 1:
        gate.reject("judge_identity_mismatch")
    if not isinstance(noise_floor, Mapping) or noise_floor.get("measured") is not True:
        gate.reject("noise_floor_missing")
        return
    if (noise_floor.get("batch_id") != manifest["batch_id"]
            or noise_floor.get("judge_spec_sha256") != run["judge_spec_sha256"]
            or noise_floor.get("calibration_sha256") != canonical_hash(calibration)):
        gate.reject("calibration_stale")
    if (not _number(noise_floor.get("sigma"), positive=True)
            or not _number(noise_floor.get("sd_judging"))
            or not _number(noise_floor.get("sd_delta_single_question"))):
        gate.reject("noise_floor_invalid")
    elif noise_floor["sigma"] != plan.get("sigma"):
        gate.reject("noise_floor_mismatch")
    elif len(variances) != len(samples) or not variances:
        gate.reject("calibration_incomplete")
    else:
        sd = math.sqrt(statistics.fmean(variances))
        if (not math.isclose(noise_floor["sd_judging"], round(sd, 4), abs_tol=0.00005)
                or not math.isclose(noise_floor["sd_delta_single_question"], round(sd * math.sqrt(2), 4), abs_tol=0.00005)):
            gate.reject("noise_floor_mismatch")


def validate_judging_batch(answers: object, calibration: object, manifest: object, *,
                           now: datetime | None = None, noise_floor: object = None) -> dict:
    """Return qualification and stable reasons, including for unreadable old receipts."""
    gate = _Validation()
    try:
        _validate_batch(answers, calibration, manifest, now, noise_floor, gate)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
        gate.reject("invalid_input")
    return gate.result()
