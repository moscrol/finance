"""Opt-in experiment controls; no HTTP implementation or production installation.

A capability record is a caller-reviewed declaration, not an authenticated
capability discovery service. Unknown or mismatched declarations block. Known
GLM-5.3 off incompatibility (llm_refine's documented constraint) cannot be
superseded by such a declaration. This gate only supports thinking=disabled;
it never substitutes enabled/low, switches models, retries or grants budget.

Even consistent provider self-reports cannot prove hidden computation was off.
Identity admission, physical HTTP accounting and semantic acceptance remain
separate obligations. A transport must send the immutable bytes exactly once.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import threading
from collections.abc import Callable

from intelligence.eval.model_admission import normalize_model
from scripts.review_probes.quantity_role_contract import ContractError, _canonical


class ControlAdmissionError(ValueError):
    """A stable reason code, never a provider exception or reasoning transcript."""


@dataclass(frozen=True)
class OffCapability:
    model: str
    endpoint_fingerprint: str
    supports_disabled: bool | None
    source_ref: str


def _flags() -> dict:
    return {
        "diagnostic_only": True,
        "effective_disabled_verified": False,
        "model_identity_verified": False,
        "release_authorized": False,
    }


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ControlAdmissionError(code)


def _model(value: object) -> str:
    _require(isinstance(value, str) and bool(value.strip()), "model_missing")
    return normalize_model(value)


def check_off_request(
    wire: dict,
    *,
    expected_model: str,
    endpoint_fingerprint: str,
    capability: OffCapability | None = None,
) -> dict:
    """Check the FINAL wire, not environment variables or model defaults."""
    _require(isinstance(wire, dict), "request_shape")
    model = _model(wire.get("model"))
    _require(model == _model(expected_model), "requested_model_mismatch")
    _require(wire.get("thinking") == {"type": "disabled"}, "disabled_not_requested")
    # Negative knowledge, not a positive model allowlist. Namespace-qualified
    # forms of these same named models must not bypass the known constraint.
    _require(
        model.rsplit("/", 1)[-1] not in {"glm-5.3", "glm-5.3-flash"},
        "known_forced_thinking",
    )
    _require(
        not any(
            k in wire
            for k in (
                "reasoning_effort",
                "reasoning",
                "enable_thinking",
                "extra_body",
                "chat_template_kwargs",
            )
        ),
        "conflicting_or_unsupported_controls",
    )
    _require(wire.get("stream", False) is False, "stream_not_supported")
    _require(
        isinstance(endpoint_fingerprint, str)
        and len(endpoint_fingerprint) == 64
        and all(c in "0123456789abcdef" for c in endpoint_fingerprint),
        "endpoint_scope_invalid",
    )
    _require(isinstance(capability, OffCapability), "capability_unknown")
    _require(
        _model(capability.model) == model
        and capability.endpoint_fingerprint == endpoint_fingerprint,
        "capability_scope_mismatch",
    )
    _require(capability.supports_disabled is True, "capability_not_supported")
    _require(
        isinstance(capability.source_ref, str) and bool(capability.source_ref.strip()),
        "capability_source_missing",
    )
    return {
        **_flags(),
        "status": "eligible_for_observation",
        "capability_ref": capability.source_ref,
    }


def audit_off_response(response: object, *, expected_model: str) -> dict:
    """Read only control metadata; never retain reasoning text in diagnostics.

    Positive eligibility is deliberately narrow: exact reported model, explicit
    disabled echo, explicitly empty reasoning_content and explicit zero counters.
    Missing telemetry is unverifiable, not evidence of disabled computation.
    """
    result = {
        **_flags(),
        "status": "unverifiable",
        "reason": "response_shape",
        "reasoning_chars": None,
        "reasoning_tokens": None,
    }
    if not isinstance(response, dict):
        return result
    served = response.get("model")
    if not isinstance(served, str) or not served.strip():
        return {**result, "reason": "served_model_missing"}
    if normalize_model(served) != _model(expected_model):
        return {**result, "status": "model_mismatch", "reason": "served_model_mismatch"}
    choices = response.get("choices")
    if (
        not isinstance(choices, list)
        or len(choices) != 1
        or not isinstance(choices[0], dict)
    ):
        return result
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return result
    text = message.get("reasoning_content")
    result["reasoning_chars"] = len(text) if isinstance(text, str) else None
    counters = []
    malformed = False
    usage = response.get("usage")
    if isinstance(usage, dict):
        for key in ("completion_tokens_details", "output_tokens_details"):
            details = usage.get(key)
            if isinstance(details, dict) and "reasoning_tokens" in details:
                count = details["reasoning_tokens"]
                if type(count) is not int or count < 0:
                    malformed = True
                else:
                    counters.append(count)
    result["reasoning_tokens"] = max(counters) if counters else None
    alternative = message.get("reasoning")
    if (
        (isinstance(text, str) and bool(text))
        or any(n > 0 for n in counters)
        or bool(alternative)
    ):
        return {
            **result,
            "status": "contradicted",
            "reason": "reported_reasoning_present",
        }
    if (
        malformed
        or not counters
        or not isinstance(text, str)
        or response.get("thinking") != {"type": "disabled"}
    ):
        return {**result, "reason": "control_evidence_missing_or_invalid"}
    return {**result, "status": "reported_consistent", "reason": "self_report_only"}


class DisabledThinkingGuard:
    """Serialized, permanently latched stop after any failed control check.

    This is not a model authorization token or a physical HTTP budget. The
    caller-owned transport must enforce those and must not rewrite the bytes.
    """

    def __init__(
        self,
        transport: Callable,
        *,
        model: str,
        endpoint_fingerprint: str,
        capability: OffCapability | None,
        max_dispatches: int,
    ):
        if (
            not callable(transport)
            or type(max_dispatches) is not int
            or max_dispatches <= 0
        ):
            raise ValueError("explicit transport and positive dispatch cap required")
        self._transport = transport
        self._model = _model(model)
        self._endpoint = endpoint_fingerprint
        self._capability = deepcopy(capability)
        self._cap = max_dispatches
        self._used = 0
        self._stopped = False
        self._active = False
        self._records: list[dict] = []
        self._lock = threading.RLock()

    @property
    def records(self) -> tuple[dict, ...]:
        with self._lock:
            return tuple(deepcopy(self._records))

    def __call__(self, wire: dict, *, timeout: float) -> dict:
        with self._lock:
            record = {
                **_flags(),
                "dispatch_index": len(self._records) + 1,
                "status": "pending",
                "transport_calls": 0,
            }
            self._records.append(record)
            owns_dispatch = False
            try:
                _require(not self._stopped, "session_stopped")
                _require(not self._active, "reentrant_dispatch")
                _require(self._used < self._cap, "dispatch_cap")
                _require(
                    type(timeout) in {int, float}
                    and math.isfinite(timeout)
                    and timeout > 0,
                    "timeout_invalid",
                )
                self._used += 1
                self._active = True
                owns_dispatch = True
                snapshot = deepcopy(wire)
                body = _canonical(snapshot).encode("utf-8")
                record["preflight"] = check_off_request(
                    snapshot,
                    expected_model=self._model,
                    endpoint_fingerprint=self._endpoint,
                    capability=self._capability,
                )
                record["request_sha256"] = hashlib.sha256(body).hexdigest()
                record["transport_calls"] = 1
                try:
                    response = self._transport(body, timeout=timeout)
                except Exception as exc:
                    record["transport_error_type"] = type(exc).__name__
                    raise ControlAdmissionError("transport_failed") from None
                _require(not self._stopped, "session_stopped")
                _require(
                    _canonical(wire).encode("utf-8") == body,
                    "request_changed_during_transport",
                )
                response = deepcopy(response)
                record["response_sha256"] = hashlib.sha256(
                    _canonical(response).encode("utf-8")
                ).hexdigest()
                audit = audit_off_response(response, expected_model=self._model)
                record["response_audit"] = audit
                _require(
                    audit["status"] == "reported_consistent",
                    "response_controls_" + audit["status"],
                )
                record["status"] = "reported_consistent"
                return response
            except Exception as exc:
                self._stopped = True
                record["status"] = "blocked"
                code = (
                    str(exc)
                    if isinstance(exc, ControlAdmissionError)
                    else "invalid_control_input"
                )
                record["reason"] = code
                raise ControlAdmissionError(code) from None
            finally:
                if owns_dispatch:
                    self._active = False


def decode_combined_content(content: str) -> dict:
    """One bare JSON object or the native parser's exact single-fence grammar.

    No substring scraping, duplicate-key choice, core/nonce/ID repair, or role
    validation here. R22 binding and core validation must still run afterwards.
    """
    from intelligence.services.episode_semantic_verifier import _STRICT_JSON_FENCE_RE

    if not isinstance(content, str):
        raise ContractError("combined content must be text")

    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ContractError("duplicate JSON key")
            value[key] = item
        return value

    def nonfinite(value):
        raise ContractError("nonfinite JSON value")

    text = content.strip()
    fenced = _STRICT_JSON_FENCE_RE.fullmatch(text)
    if fenced is not None:
        text = fenced.group("body")
    try:
        decoded = json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (ValueError, TypeError) as exc:
        raise ContractError("invalid combined JSON container") from exc
    if not isinstance(decoded, dict):
        raise ContractError("combined content must be one object")
    _canonical(decoded)
    return decoded
