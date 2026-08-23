"""Activation receipts: requested ≠ injected, and injected ≠ the model used it.

``injected=true`` only means the guidance string was written into the payload
field that will be sent to the model. Budget truncation or context overflow
can still drop it from the window. The receipt never claims the model followed
the guidance.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from typing import Literal

ActivationKind = Literal["perspective", "reading_baseline"]
ActivationStatus = Literal["inactive", "injected", "degraded"]

FORBIDDEN_BRAND_MARKERS = ("sptfei", "spt-")


@dataclass(frozen=True)
class ActivationRecord:
    kind: ActivationKind
    requested: str
    resolved: tuple[str, ...]
    display_names: tuple[str, ...]
    renderer: str
    prompt_hash: str
    injected: bool
    status: ActivationStatus
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "requested": self.requested,
            "resolved": list(self.resolved),
            "display_names": list(self.display_names),
            "renderer": self.renderer,
            "prompt_hash": self.prompt_hash,
            "injected": self.injected,
            "status": self.status,
            "reason": self.reason,
        }


def field_digest(field_bytes: str) -> str:
    return sha256(field_bytes.encode("utf-8")).hexdigest()


def seal_prompt_hash(record: ActivationRecord, field_bytes: str) -> ActivationRecord:
    """Hash the bytes ``episode_protocol`` just wrote into the payload field.

    Callers must pass the assigned Python string, not a pre-wrap fragment.
    ``activate_*`` leaves ``prompt_hash`` empty on purpose.
    """

    if record.status != "injected":
        return replace(record, prompt_hash="")
    if field_bytes == "":
        raise ValueError("injected record sealed with empty field")
    return replace(record, prompt_hash=field_digest(field_bytes))


def requested_perspective(
    mode: str,
    perspective_ids: tuple[str, ...] | list[str],
) -> str:
    ids = tuple(str(item) for item in perspective_ids)
    if mode == "neutral" or not ids:
        return "neutral"
    return f"{mode}:{','.join(ids)}"


def mode_from_requested(requested: str) -> str:
    if requested.startswith("compare:"):
        return "compare"
    if requested.startswith("single:"):
        return "single"
    return "neutral"


def activate_reading_baseline(
    guidance: str,
    rule_ids: tuple[str, ...],
    *,
    enabled: bool,
    pending_ids: tuple[str, ...] = (),
    wired: bool = True,
) -> ActivationRecord:
    """Pure baseline receipt. Does not import ``reading_baseline``."""

    pending = frozenset(pending_ids)
    live_ids = tuple(rule_id for rule_id in rule_ids if rule_id not in pending)
    if not wired:
        return ActivationRecord(
            kind="reading_baseline",
            requested="not_wired",
            resolved=(),
            display_names=(),
            renderer="activate_reading_baseline",
            prompt_hash="",
            injected=False,
            status="inactive",
            reason="not_wired",
        )
    if not enabled:
        return ActivationRecord(
            kind="reading_baseline",
            requested="off",
            resolved=(),
            display_names=(),
            renderer="activate_reading_baseline",
            prompt_hash="",
            injected=False,
            status="inactive",
            reason="switch_off",
        )
    text = str(guidance or "")
    if not text:
        return ActivationRecord(
            kind="reading_baseline",
            requested="on",
            resolved=(),
            display_names=(),
            renderer="activate_reading_baseline",
            prompt_hash="",
            injected=False,
            status="degraded",
            reason="no_rules",
        )
    return ActivationRecord(
        kind="reading_baseline",
        requested="on",
        resolved=live_ids,
        display_names=(),
        renderer="activate_reading_baseline",
        prompt_hash="",
        injected=True,
        status="injected",
        reason="",
    )


def collect_run_activations(
    *,
    perspective: ActivationRecord | None,
    perspective_field: str,
    baseline: ActivationRecord | None = None,
    baseline_field: str = "",
) -> tuple[ActivationRecord, ActivationRecord]:
    """Seal both slots. Absence of a perspective record is inferred from the field."""

    if perspective is None:
        if perspective_field:
            perspective = ActivationRecord(
                kind="perspective",
                requested="unknown",
                resolved=(),
                display_names=(),
                renderer="collect_run_activations",
                prompt_hash="",
                injected=True,
                status="injected",
                reason="",
            )
        else:
            perspective = ActivationRecord(
                kind="perspective",
                requested="neutral",
                resolved=(),
                display_names=(),
                renderer="collect_run_activations",
                prompt_hash="",
                injected=False,
                status="inactive",
                reason="not_requested",
            )
    sealed_perspective = seal_prompt_hash(perspective, perspective_field)
    if baseline is None:
        baseline = activate_reading_baseline("", (), enabled=False, wired=False)
    sealed_baseline = seal_prompt_hash(baseline, baseline_field)
    return sealed_perspective, sealed_baseline


def visible_text_leaks_brand(text: str, record: ActivationRecord) -> bool:
    """True when a non-injected record's user-visible text still carries a shop name."""

    if record.status == "injected":
        return False
    blob = str(text or "").lower()
    for name in record.display_names:
        if name and name.lower() in blob:
            return True
    return any(marker in blob for marker in FORBIDDEN_BRAND_MARKERS)
