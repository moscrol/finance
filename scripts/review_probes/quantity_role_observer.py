"""Explicit opt-in observer for SemanticEpisodeVerifier's injected judge seam.

Not installed in production. The caller supplies a target selector and a
transport returning JSON-compatible native core or R22 combined envelopes.
Exactly one transport invocation is allowed per admitted native dispatch; this
is NOT an HTTP retry budget or authorization to spend model tokens. A live
transport must enforce its own physical ledger, identity admission and deadline.

Only the core verdict returns to the real verifier. Role data stays in separate
caller-owned diagnostics, never alters numeric marking, and has no release
rights. Use a fresh observer per experiment; no reset/replenish operation exists.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
import math
import threading

from scripts.review_probes.quantity_role_contract import (
    ContractError,
    _canonical,
    check_native_report,
    check_review,
    prepare_review,
)


def _copy(value):
    # Detach data retained by selectors, transports and record readers.
    return deepcopy(value)


class QuantityRoleObserver:
    """One-instance serialized experimental callback, never a service singleton."""

    def __init__(
        self, transport: Callable, target_selector: Callable, *, max_dispatches: int
    ):
        if type(max_dispatches) is not int or max_dispatches <= 0:
            raise ValueError("explicit positive dispatch cap required")
        if not callable(transport) or not callable(target_selector):
            raise ValueError("explicit transport and target selector required")
        self._transport = transport
        self._selector = target_selector
        self._cap = max_dispatches
        self._used = 0
        self._records: list[dict] = []
        self._lock = threading.RLock()

    @property
    def records(self) -> tuple[dict, ...]:
        with self._lock:
            return tuple(_copy(self._records))

    def __call__(self, request: dict, timeout: float) -> object:
        with self._lock:
            record = {
                "dispatch_index": len(self._records) + 1,
                "review_id": None,
                "sidecar_status": "pending",
                "transport_calls": 0,
                "diagnostic_only": True,
                "release_authorized": False,
                "model_identity_verified": False,
            }
            # A failed latest dispatch must supersede earlier valid annotations.
            self._records.append(record)
            try:
                if (
                    type(timeout) not in {float, int}
                    or not math.isfinite(timeout)
                    or timeout <= 0
                ):
                    raise ValueError("invalid native timeout")
                if self._used >= self._cap:
                    raise RuntimeError("observer dispatch budget exhausted")
                self._used += 1
                snapshot = _copy(request)
                _canonical(snapshot)
                record["native_request"] = _copy(snapshot)
                spans = self._selector(_copy(snapshot))
                if not isinstance(spans, list):
                    raise ContractError(
                        "selector must return explicit occurrence spans"
                    )
                bundle = prepare_review(snapshot, spans) if spans else None
                wire = _copy(bundle if bundle is not None else snapshot)
                record["bundle"] = _copy(bundle)
                if bundle is not None:
                    record["review_id"] = bundle["review_id"]
                expected_wire = _canonical(wire)
                record["transport_calls"] = 1
                response = self._transport(wire, timeout=timeout)
                if _canonical(wire) != expected_wire:
                    raise ContractError("transport mutated the dispatched input")
                if _canonical(request) != _canonical(snapshot):
                    raise ContractError("native request changed during dispatch")
                response = _copy(response)
                if bundle is not None and isinstance(response, str):
                    from scripts.review_probes.observation_admission import (
                        decode_combined_content,
                    )

                    record["response_text"] = response
                    response = decode_combined_content(response)
                _canonical(response)
                record["response"] = _copy(response)
                if bundle is None:
                    from intelligence.services.episode_semantic_verifier import (
                        SemanticEpisodeVerifier,
                    )

                    report = SemanticEpisodeVerifier._parse_report(
                        response,
                        len(snapshot["sentences"]),
                        material_claims=snapshot.get("material_claims"),
                        material_outputs=snapshot.get("material_outputs"),
                    )
                    if report is None:
                        raise ContractError("invalid unextended native core")
                    record["native_report"] = report.to_dict()
                    record["sidecar_status"] = "not_requested"
                    return _copy(response)
                # Header/context/nonce/core failures reject the WHOLE dispatch.
                # A core from a different request must never be salvaged.
                record["native_report"] = check_native_report(
                    bundle,
                    response,
                    current_request=request,
                )
                try:
                    record["diagnostic"] = check_review(
                        bundle, response, current_request=request
                    )
                except ContractError:
                    # Only sidecar content failed; its binding header and core
                    # were already checked. Keep the real core rejection intact.
                    record["sidecar_status"] = "invalid_roles"
                else:
                    record["sidecar_status"] = "bound"
                # Return the ORIGINAL validated core, not a normalized/reconciled
                # copy that the native material parser would reconcile twice.
                return _copy(response["grounding_report"])
            except Exception as exc:
                record["sidecar_status"] = "failed"
                record["error_type"] = type(exc).__name__
                # No exception message: arbitrary transports may expose secrets.
                raise

    def delivery_view(self, current_request: dict, *, review_id: str | None) -> dict:
        """Only latest dispatch; edits invalidate, no older-good fallback/remap."""
        with self._lock:
            base = {
                "diagnostic_only": True,
                "release_authorized": False,
                "model_identity_verified": False,
            }
            if not self._records:
                return {**base, "status": "not_observed"}
            latest = self._records[-1]
            if review_id != latest["review_id"]:
                return {**base, "status": "foreign_or_superseded"}
            if latest["sidecar_status"] != "bound":
                return {**base, "status": latest["sidecar_status"]}
            try:
                diagnostic = check_review(
                    latest["bundle"],
                    latest["response"],
                    current_request=current_request,
                )
            except ContractError:
                return {**base, "status": "stale"}
            return {**diagnostic, "status": "current_binding"}
