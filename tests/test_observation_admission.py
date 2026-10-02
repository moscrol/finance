"""Synthetic control receipts are not proof of a model's hidden computation."""

from copy import deepcopy
import json
import socket

import pytest

from scripts.review_probes.observation_admission import (
    ControlAdmissionError,
    DisabledThinkingGuard,
    OffCapability,
    audit_off_response,
    check_off_request,
    decode_combined_content,
)
from scripts.review_probes.quantity_role_contract import (
    ContractError,
    check_review,
    prepare_review,
)
from scripts.review_probes.quantity_role_observer import QuantityRoleObserver

MODEL = "synthetic-off-model"
ENDPOINT = "a" * 64


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("network forbidden")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)


def capability(**changes):
    args = dict(
        model=MODEL,
        endpoint_fingerprint=ENDPOINT,
        supports_disabled=True,
        source_ref="synthetic-reviewed-capability",
    )
    args.update(changes)
    return OffCapability(**args)


def wire(model=MODEL):
    return {
        "model": model,
        "thinking": {"type": "disabled"},
        "messages": [{"role": "user", "content": "synthetic"}],
    }


def response():
    return {
        "model": MODEL,
        "thinking": {"type": "disabled"},
        "choices": [{"message": {"content": "{}", "reasoning_content": ""}}],
        "usage": {"completion_tokens_details": {"reasoning_tokens": 0}},
    }


def check(value, cap=None):
    return check_off_request(
        value,
        expected_model=value["model"],
        endpoint_fingerprint=ENDPOINT,
        capability=cap,
    )


@pytest.mark.parametrize("model", ["glm-5.3", "GLM-5.3-FLASH", "vendor/glm-5.3"])
def test_known_forced_thinking_cannot_be_overridden(model):
    with pytest.raises(ControlAdmissionError, match="known_forced_thinking"):
        check(wire(model), capability(model=model))


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "unknown",
        "unsupported",
        "foreign_model",
        "foreign_endpoint",
        "no_source",
        "string_bool",
    ],
)
def test_capability_is_explicit_scoped_and_not_inferred(kind):
    cap = {
        "missing": None,
        "unknown": capability(supports_disabled=None),
        "unsupported": capability(supports_disabled=False),
        "foreign_model": capability(model="another"),
        "foreign_endpoint": capability(endpoint_fingerprint="b" * 64),
        "no_source": capability(source_ref=""),
        "string_bool": capability(supports_disabled="true"),
    }[kind]
    with pytest.raises(ControlAdmissionError):
        check(wire(), cap)


@pytest.mark.parametrize(
    "mutation",
    ["enabled", "omitted", "low", "none_effort", "alternate", "nested", "stream"],
)
def test_final_wire_not_environment_or_low_is_checked(mutation):
    value = wire()
    if mutation == "enabled":
        value["thinking"]["type"] = "enabled"
    elif mutation == "omitted":
        value.pop("thinking")
    elif mutation == "low":
        value["reasoning_effort"] = "low"
    elif mutation == "none_effort":
        value["reasoning_effort"] = "none"
    elif mutation == "alternate":
        value["enable_thinking"] = True
    elif mutation == "nested":
        value["extra_body"] = {"thinking": {"type": "enabled"}}
    else:
        value["stream"] = True
    with pytest.raises(ControlAdmissionError):
        check(value, capability())


def test_positive_declaration_is_only_eligibility_not_verification():
    result = check(wire(), capability())
    assert result["status"] == "eligible_for_observation"
    assert (
        not result["effective_disabled_verified"] and not result["release_authorized"]
    )


@pytest.mark.parametrize(
    "kind", ["text", "tokens", "alternate_tokens", "alternate_message"]
)
def test_response_reasoning_overrides_disabled_echo(kind):
    value = response()
    if kind == "text":
        value["choices"][0]["message"]["reasoning_content"] = "PRIVATE_REASONING"
    elif kind == "tokens":
        value["usage"]["completion_tokens_details"]["reasoning_tokens"] = 5
    elif kind == "alternate_tokens":
        value["usage"]["output_tokens_details"] = {"reasoning_tokens": 3}
    else:
        value["choices"][0]["message"]["reasoning"] = ["PRIVATE_REASONING"]
    result = audit_off_response(value, expected_model=MODEL)
    assert result["status"] == "contradicted"
    assert not result["effective_disabled_verified"] and "PRIVATE_REASONING" not in str(
        result
    )


@pytest.mark.parametrize(
    "kind",
    [
        "echo",
        "tokens",
        "text",
        "string_tokens",
        "bool_tokens",
        "negative_tokens",
        "model",
        "choices",
    ],
)
def test_absence_or_malformed_metadata_does_not_prove_thinking_off(kind):
    value = response()
    if kind == "echo":
        value.pop("thinking")
    elif kind == "tokens":
        value.pop("usage")
    elif kind == "text":
        value["choices"][0]["message"].pop("reasoning_content")
    elif kind == "string_tokens":
        value["usage"]["completion_tokens_details"]["reasoning_tokens"] = "0"
    elif kind == "bool_tokens":
        value["usage"]["completion_tokens_details"]["reasoning_tokens"] = False
    elif kind == "negative_tokens":
        value["usage"]["completion_tokens_details"]["reasoning_tokens"] = -1
    elif kind == "model":
        value["model"] = "different-model"
    else:
        value["choices"] = []
    result = audit_off_response(value, expected_model=MODEL)
    assert result["status"] != "reported_consistent"
    assert not result["effective_disabled_verified"]


def test_consistent_self_report_is_not_hidden_compute_or_identity_proof():
    result = audit_off_response(response(), expected_model=MODEL)
    assert result["status"] == "reported_consistent"
    assert (
        not result["effective_disabled_verified"]
        and not result["model_identity_verified"]
    )
    assert not result["release_authorized"]


def make_guard(transport, *, cap=2, cap_evidence=True, model=MODEL):
    return DisabledThinkingGuard(
        transport,
        model=model,
        endpoint_fingerprint=ENDPOINT,
        capability=capability(model=model) if cap_evidence else None,
        max_dispatches=cap,
    )


def test_known_bad_configuration_never_reaches_transport_and_latches():
    calls = []
    guard = make_guard(lambda body, timeout: calls.append(1), model="glm-5.3")
    with pytest.raises(ControlAdmissionError):
        guard(wire("glm-5.3"), timeout=5)
    with pytest.raises(ControlAdmissionError, match="session_stopped"):
        guard(wire(), timeout=5)
    assert not calls and all(r["transport_calls"] == 0 for r in guard.records)


@pytest.mark.parametrize(
    "failure", ["reasoning", "unverifiable", "exception", "model_mismatch"]
)
def test_first_bad_return_blocks_all_later_cases_without_retry(failure):
    calls = []

    def transport(body, *, timeout):
        calls.append(1)
        if failure == "exception":
            raise RuntimeError("PRIVATE_KEY_MUST_NOT_LEAK")
        value = response()
        if failure == "reasoning":
            value["choices"][0]["message"]["reasoning_content"] = "PRIVATE_REASONING"
        elif failure == "unverifiable":
            value.pop("usage")
        else:
            value["model"] = "wrong-model"
        return value

    guard = make_guard(transport)
    with pytest.raises(ControlAdmissionError):
        guard(wire(), timeout=3)
    with pytest.raises(ControlAdmissionError, match="session_stopped"):
        guard(wire(), timeout=3)
    assert len(calls) == 1
    assert "PRIVATE_" not in str(guard.records)
    assert guard.records[-1]["transport_calls"] == 0


def test_wire_is_immutable_bytes_timeout_exact_and_budget_finite():
    calls = []

    def transport(body, *, timeout):
        assert isinstance(body, bytes)
        calls.append((json.loads(body), timeout))
        return response()

    guard = make_guard(transport, cap=1)
    request = wire()
    before = deepcopy(request)
    result = guard(request, timeout=4.25)
    assert result == response() and request == before and calls == [(request, 4.25)]
    snapshot = guard.records
    snapshot[0]["status"] = "changed"
    assert guard.records[0]["status"] == "reported_consistent"
    with pytest.raises(ControlAdmissionError, match="dispatch_cap"):
        guard(request, timeout=4.25)
    assert len(calls) == 1


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_invalid_cap_is_not_unlimited(value):
    with pytest.raises(ValueError):
        make_guard(lambda *args: None, cap=value)


@pytest.mark.parametrize("value", [0, True, float("inf")])
def test_invalid_timeout_never_dispatches(value):
    calls = []
    guard = make_guard(lambda *args, **kwargs: calls.append(1))
    with pytest.raises(ControlAdmissionError):
        guard(wire(), timeout=value)
    assert not calls


def bundle():
    request = {
        "question": "test",
        "required_outputs": [],
        "answer_grounding_mode": "evidence",
        "output_bindings": [],
        "sentences": [{"index": 1, "text": "连续三日。"}],
        "evidence_registry": [],
    }
    return prepare_review(request, [{"sentence_index": 1, "start": 2, "end": 4}])


def combined(value):
    return {
        "schema": "quantity_role_response_v1",
        "review_id": value["review_id"],
        "grounding_report": {
            "passed": False,
            "rejected_sentence_indexes": [1],
            "issues": ["synthetic rejection"],
        },
        "quantity_roles": [
            {
                "target_id": "q1",
                "role": "unknown",
                "evidence_ids": [],
                "historical_source_dates": [],
                "historical_cardinality": None,
                "reason": "synthetic",
            }
        ],
    }


@pytest.mark.parametrize("fenced", [False, True])
def test_one_native_compatible_json_container_leaves_fields_unchanged(fenced):
    b = bundle()
    value = combined(b)
    text = json.dumps(value)
    if fenced:
        text = "```json\n" + text + "\n```"
    decoded = decode_combined_content(text)
    assert (
        decoded == value
        and check_review(b, decoded, current_request=b["native_request"])[
            "native_report"
        ]["passed"]
        is False
    )


@pytest.mark.parametrize(
    "kind", ["prefix", "suffix", "two", "array", "duplicate", "nan"]
)
def test_framing_is_not_json_scraping_or_silent_field_selection(kind):
    text = json.dumps(combined(bundle()))
    value = {
        "prefix": "explanation\n" + text,
        "suffix": text + "\nexplanation",
        "two": text + "\n" + text,
        "array": "[" + text + "]",
        "duplicate": '{"review_id":"a","review_id":"b"}',
        "nan": '{"value":NaN}',
    }[kind]
    with pytest.raises(ContractError):
        decode_combined_content(value)


def test_fence_removal_does_not_repair_wrong_binding():
    b = bundle()
    value = combined(b)
    value["review_id"] += "a5"
    parsed = decode_combined_content("```json\n" + json.dumps(value) + "\n```")
    assert len(parsed["review_id"]) == 66
    with pytest.raises(ContractError):
        check_review(b, parsed, current_request=b["native_request"])


def test_real_native_callback_composes_control_guard_and_bound_parser():
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier

    b = bundle()
    count = []

    def transport(body, *, timeout):
        payload = json.loads(body)
        current = json.loads(payload["messages"][0]["content"])
        value = response()
        value["choices"][0]["message"]["content"] = (
            "```json\n" + json.dumps(combined(current)) + "\n```"
        )
        count.append(1)
        return value

    guard = make_guard(transport, cap=1)

    def observer_transport(current, *, timeout):
        request = wire()
        request["messages"][0]["content"] = json.dumps(current)
        return guard(request, timeout=timeout)["choices"][0]["message"]["content"]

    observer = QuantityRoleObserver(
        observer_transport,
        lambda req: [{"sentence_index": 1, "start": 2, "end": 4}],
        max_dispatches=1,
    )
    result = SemanticEpisodeVerifier._invoke_injected(
        observer, b["native_request"], 5, True
    )
    assert result.report and result.report.rejected_sentence_indexes == (1,)
    assert len(count) == 1 and observer.records[0]["sidecar_status"] == "bound"
    assert guard.records[0]["status"] == "reported_consistent"


def test_native_entry_does_not_send_known_forced_model():
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier

    b = bundle()
    calls = []
    guard = make_guard(lambda *args, **kwargs: calls.append(1), model="glm-5.3")

    def transport(current, *, timeout):
        return guard(wire("glm-5.3"), timeout=timeout)

    observer = QuantityRoleObserver(
        transport,
        lambda req: [{"sentence_index": 1, "start": 2, "end": 4}],
        max_dispatches=1,
    )
    result = SemanticEpisodeVerifier._invoke_injected(
        observer, b["native_request"], 5, True
    )
    assert result.unavailable and result.report is None and not calls
    assert observer.records[0]["sidecar_status"] == "failed"
    assert guard.records[0]["transport_calls"] == 0


def test_native_entry_still_refuses_fenced_foreign_id():
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier

    b = bundle()

    def transport(current, *, timeout):
        value = combined(current)
        value["review_id"] += "a5"
        return "```json\n" + json.dumps(value) + "\n```"

    observer = QuantityRoleObserver(
        transport,
        lambda req: [{"sentence_index": 1, "start": 2, "end": 4}],
        max_dispatches=1,
    )
    result = SemanticEpisodeVerifier._invoke_injected(
        observer, b["native_request"], 5, True
    )
    assert result.unavailable and result.report is None
    record = observer.records[0]
    assert record["sidecar_status"] == "failed" and record["response_text"].startswith(
        "```"
    )
    assert len(record["response"]["review_id"]) == 66


def test_reentrant_dispatch_cannot_start_next_case_before_first_audit():
    calls = []

    def transport(body, *, timeout):
        calls.append(1)
        with pytest.raises(ControlAdmissionError, match="reentrant_dispatch"):
            guard(wire(), timeout=timeout)
        return response()

    guard = make_guard(transport)
    with pytest.raises(ControlAdmissionError, match="session_stopped"):
        guard(wire(), timeout=2)
    assert len(calls) == 1 and all(r["status"] == "blocked" for r in guard.records)


def test_native_request_mutation_cannot_be_reported_consistent():
    request = wire()

    def transport(body, *, timeout):
        request["messages"][0]["content"] = "edited while in flight"
        return response()

    guard = make_guard(transport)
    with pytest.raises(ControlAdmissionError, match="request_changed_during_transport"):
        guard(request, timeout=2)


def test_concurrent_cases_wait_for_first_audit_and_then_stop():
    from concurrent.futures import ThreadPoolExecutor
    import threading

    barrier = threading.Barrier(2)
    calls = []

    def transport(body, *, timeout):
        calls.append(1)
        value = response()
        value["usage"]["completion_tokens_details"]["reasoning_tokens"] = 1
        return value

    guard = make_guard(transport)

    def task():
        barrier.wait(timeout=5)
        try:
            guard(wire(), timeout=2)
        except ControlAdmissionError as exc:
            return str(exc)
        raise AssertionError("contradiction was accepted")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: task(), range(2)))
    assert sorted(results) == ["response_controls_contradicted", "session_stopped"]
    assert len(calls) == 1
