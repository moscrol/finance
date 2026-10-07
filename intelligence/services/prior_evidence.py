"""Bounded reuse of original local tool evidence, not old answers or run state.

This is a cross-turn input projection, not an episode restart/checkpoint. RunStore
owns integrity/ownership checks. Dates and fields are validated before admission;
old coverage, targets, verdicts and tool permissions are deliberately not copied.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from datetime import date
import json
import math
from typing import TYPE_CHECKING, Sequence

from intelligence.services.agent_research import (
    AgentEvidence, HistoricalEvidenceProvenance, StructuredObservation, evidence_content_hash,
)
from intelligence.services.material_permissions import LOCAL_READ_CAPABILITIES
from intelligence.services.query_understanding import query_time_scope
from intelligence.services.user_task import requests_previous_answer_review, requests_previous_evidence_only, top_level_message_text

if TYPE_CHECKING:
    from intelligence.services.conversation_store import Message
    from intelligence.services.run_store import RunStore
    from intelligence.services.task_frame import TaskFrame


@dataclass(frozen=True)
class PriorTurnEvidence:
    task_frame_hash: str
    source_run_id: str
    source_message_id: str
    artifact_sha256: str
    source_question: str
    source_cutoff: date
    entries: tuple[tuple[str, AgentEvidence], ...]
    excluded_ordinals: tuple[str, ...] = ()

    def admitted(self, *, task_frame_hash: str, cutoff: date) -> tuple[AgentEvidence, ...]:
        if self.task_frame_hash != task_frame_hash:
            raise ValueError("prior evidence belongs to a different task frame")
        bound = min(cutoff, self.source_cutoff)
        return tuple(item for _, item in self.entries
                     if date.fromisoformat(item.source_date) <= bound
                     and all(date.fromisoformat(o.as_of) <= bound for o in item.observations))

    def receipt(self) -> dict[str, object]:
        return {
            "source_run_id": self.source_run_id, "source_message_id": self.source_message_id,
            "artifact_sha256": self.artifact_sha256, "source_question": self.source_question,
            "source_cutoff": self.source_cutoff.isoformat(),
            "entries": [{"old_ref": ref, "content_hash": item.content_hash,
                         "source_date": item.source_date} for ref, item in self.entries],
            "excluded_ordinals": list(self.excluded_ordinals),
        }


def remap_evidence_bindings(
    snapshot: PriorTurnEvidence,
    evidence: tuple[AgentEvidence, ...],
) -> list[dict[str, str]]:
    """Build the private old-to-new citation map for a restored input block."""
    from intelligence.services.episode_protocol import evidence_ordinal_table

    ordinals = evidence_ordinal_table(evidence)
    return [
        {"old_ref": ref, "new_ref": ordinals[item.content_hash], "content_hash": item.content_hash}
        for ref, item in snapshot.entries
        if item.content_hash in ordinals
    ]


PRIOR_EVIDENCE_INPUT_SOURCE = "prior_tool_evidence"


def restored_prior_hashes(events: Sequence[object]) -> frozenset[str]:
    """Content hashes of the prior-turn atoms ``_seed_prior_evidence`` injected.

    Read back from the durable ``model_input`` event whose ``source`` is
    ``prior_tool_evidence`` (its content is the receipt built by
    :meth:`PriorTurnEvidence.receipt` plus the remapped bindings), so structural
    verifiers that only see an ``AgentOutcome`` can tell restored inputs from
    fresh reads without a second plumbing path. Malformed or absent blocks yield
    an empty set, which keeps every frozen-scope rule at its strict default.
    """
    hashes: set[str] = set()
    for event in events:
        if getattr(event, "kind", None) != "model_input":
            continue
        payload = getattr(event, "payload", None) or {}
        if payload.get("source") != PRIOR_EVIDENCE_INPUT_SOURCE:
            continue
        try:
            body = json.loads(str(payload.get("content") or ""))
        except ValueError:
            continue
        receipt = body.get("receipt") if isinstance(body, dict) else None
        if not isinstance(receipt, dict):
            continue
        for row in (*receipt.get("entries", ()), *receipt.get("bindings", ())):
            if isinstance(row, dict):
                digest = str(row.get("content_hash") or "").strip()
                if digest:
                    hashes.add(digest)
    return frozenset(hashes)


def _original_atom(raw: object) -> AgentEvidence:
    """Reconstruct the complete stored schema without coercing or dropping fields."""
    expected = {field.name for field in fields(AgentEvidence)}
    if not isinstance(raw, dict) or set(raw) not in (expected, expected - {"history_provenance"}):
        raise ValueError("incomplete or unknown prior evidence schema")
    # Explicit additive-schema compatibility, not a general missing-field escape.
    # Old ordinary atoms had no historical metadata; old history atoms cannot
    # acquire source identity merely by taking the None default.
    raw = {"history_provenance": None, **raw}
    values = dict(raw)
    history = raw["history_provenance"]
    if not isinstance(raw["tool"], str):
        raise ValueError("invalid evidence text field")
    if history is not None:
        if raw["tool"] not in {"history_query", "read_history_result"}:
            raise ValueError("historical provenance on non-historical evidence")
        values["history_provenance"] = HistoricalEvidenceProvenance.from_dict(history)
    elif raw["tool"] in {"history_query", "read_history_result"}:
        raise ValueError("missing historical provenance")
    sequences = {"supports", "contradicts", "derived_from", "observations"}
    nullable = {"source_date", "reexcerpted", "pointer_dropped", "structural_neighbor_demoted"}
    for key in set(raw) - sequences - nullable - {"deep_read", "history_provenance"}:
        if not isinstance(raw[key], str):
            raise ValueError("invalid evidence text field")
    for key in sequences - {"observations"}:
        if not isinstance(raw[key], list) or any(not isinstance(v, str) for v in raw[key]):
            raise ValueError("invalid evidence sequence")
        values[key] = tuple(raw[key])
    if type(raw["deep_read"]) is not bool or (
        raw["reexcerpted"] is not None and type(raw["reexcerpted"]) is not bool
    ):
        raise ValueError("invalid evidence boolean")
    for key in ("pointer_dropped", "structural_neighbor_demoted"):
        if raw[key] is not None and (type(raw[key]) is not int or raw[key] < 0):
            raise ValueError("invalid evidence counter")
    if raw["source_date"] is not None and not isinstance(raw["source_date"], str):
        raise ValueError("invalid evidence date")
    if not raw["content_hash"].strip() or raw["content_hash"] != raw["content_hash"].strip():
        raise ValueError("missing evidence identity")
    if not isinstance(raw["observations"], list):
        raise ValueError("invalid observations")
    observations = []
    for row in raw["observations"]:
        if (not isinstance(row, dict) or set(row) != {"subject", "as_of", "metric", "value"}
                or any(not isinstance(row[k], str) for k in ("subject", "as_of", "metric"))
                or type(row["value"]) not in (int, float) or not math.isfinite(row["value"])):
            raise ValueError("invalid structured observation")
        observations.append(StructuredObservation(**row))
    values["observations"] = tuple(observations)
    atom = AgentEvidence(**values)
    if json.loads(json.dumps(asdict(atom), allow_nan=False)) != raw:
        raise ValueError("lossy evidence reconstruction")
    if atom.history_provenance is not None and (
        atom.content_hash != evidence_content_hash(atom)
        or atom.internal_locator != atom.history_provenance.result_ref
        or atom.independent_key != atom.history_provenance.query_id
    ):
        raise ValueError("historical evidence identity mismatch")
    return atom


def load_previous_evidence(
    frame: TaskFrame, *, messages: Sequence[Message], store: RunStore,
    conversation_id: str, current_run_id: str, history_unavailable: bool = False,
) -> PriorTurnEvidence | None:
    """Select the latest original answer in the authorized window, never scan runs."""
    from intelligence.services.research_contract import _EXPLICIT_SWITCH_PATTERN
    from intelligence.services.task_frame import TaskFrame

    material = frame.material_contract
    if not (material and not material.needs_clarification
            and material.data_scope == "material_only" and material.continuation_requested
            and requests_previous_answer_review(frame.raw_question)
            and requests_previous_evidence_only(frame.raw_question)):
        return None
    visible, uncertain = top_level_message_text(frame.raw_question)
    if history_unavailable or uncertain or _EXPLICIT_SWITCH_PATTERN.search(visible):
        raise ValueError("prior evidence requires an intact history and unchanged date scope")
    if any(m.conversation_id != conversation_id for m in messages):
        raise ValueError("cross-conversation evidence request")
    old_answers = [m for m in messages if m.role == "assistant" and m.run_id != current_run_id]
    if not old_answers or old_answers[-1].status != "completed":
        raise ValueError("previous completed answer unavailable")
    answer = old_answers[-1]
    history = frame.conversation_materials
    if history is None or answer.message_id not in {s.source_message_id for s in history.assistant_statements}:
        raise ValueError("previous answer is outside the material chain")
    if not answer.run_id:
        raise ValueError("previous answer has no original run")
    users = [m for m in messages if m.role == "user" and m.run_id == answer.run_id and m.status == "completed"]
    if len(users) != 1:
        raise ValueError("previous source question unavailable or ambiguous")
    current_scope = query_time_scope(visible)
    source_visible, source_uncertain = top_level_message_text(users[0].content)
    if current_scope.labels:
        try:
            source_anchor = date.fromisoformat(users[0].created_at[:10])
        except (TypeError, ValueError):
            raise ValueError("prior evidence requires an intact history and unchanged date scope") from None
        source_scope = query_time_scope(source_visible, today=source_anchor)
        if source_uncertain or not current_scope.same_absolute_window(source_scope):
            raise ValueError("prior evidence requires an intact history and unchanged date scope")
    raw, digest = store.read_episode_artifact(answer.run_id, conversation_id=conversation_id)
    source_frame = TaskFrame.from_dict(raw.get("task_frame"))
    contract, outcome = raw.get("contract"), raw.get("outcome")
    if (raw.get("schema_version") != 1 or raw.get("execution_kind") != "continuous_episode"
            or source_frame is None or not isinstance(contract, dict) or not isinstance(outcome, dict)
            # Ordinary research may contain local originals even when its read
            # scope was broad. The per-atom allowlist below still excludes every
            # external/derived atom; old permissions are never restored.
            or (source_frame.material_contract is not None and (
                source_frame.material_contract.needs_clarification
                or source_frame.material_contract.authenticity != "real"
                or source_frame.material_contract.data_scope not in {"local_only", "full"}
            ))
            or contract.get("task_id") != f"{answer.run_id}:{answer.message_id}"
            or source_frame.raw_question != users[0].content
            or contract.get("task_frame_hash") != source_frame.task_frame_hash
            or outcome.get("task_frame_hash") != source_frame.task_frame_hash
            or outcome.get("status") not in {"completed", "partial"}):
        raise ValueError("original episode identity mismatch")
    source_context = raw.get("research_context")
    cutoff_object = source_context.get("information_cutoff") if isinstance(source_context, dict) else None
    cutoff_raw = cutoff_object.get("as_of_date") if isinstance(cutoff_object, dict) else None
    if not isinstance(cutoff_raw, str):
        raise ValueError("source cutoff unavailable")
    cutoff = date.fromisoformat(cutoff_raw)
    rows = outcome.get("evidence")
    if not isinstance(rows, list) or not rows or len(rows) > 128:
        raise ValueError("previous evidence missing or over input budget")
    entries, excluded, seen = [], [], set()
    for i, row in enumerate(rows, 1):
        atom = _original_atom(row)
        if atom.content_hash in seen:
            raise ValueError("duplicate prior evidence identity")
        seen.add(atom.content_hash)
        ref = f"E{i}"
        try:
            day = date.fromisoformat(atom.source_date or "")
        except ValueError:
            excluded.append(ref)
            continue
        if (atom.tool not in LOCAL_READ_CAPABILITIES or atom.io_effect != "local_read"
                or day > cutoff or atom.derived_from
                or any(date.fromisoformat(o.as_of) > cutoff for o in atom.observations)):
            excluded.append(ref)
            continue
        entries.append((ref, replace(atom, supports=(), contradicts=())))
    if not entries:
        raise ValueError("no admissible original local evidence")
    return PriorTurnEvidence(
        frame.task_frame_hash, answer.run_id, answer.message_id, digest,
        source_frame.raw_question, cutoff, tuple(entries), tuple(excluded),
    )
