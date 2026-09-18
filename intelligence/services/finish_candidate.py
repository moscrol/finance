"""Same-task prose retention, independent of finish/completion admission.

No model calls, no inferred bindings, no permissive substring JSON recovery.
Only a complete envelope (optionally preceded by prose on separate lines) can
supply a candidate. Public delivery still runs the normal safety and QC gates.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
import json
import re

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import OutputEvidenceBinding
from intelligence.services.episode_protocol import (
    _unique_json_keys, cited_evidence_ordinals, evidence_ordinal_table,
    validate_finish_bindings,
)
from intelligence.services.historical_research.research import assess_history_finish
from intelligence.services.material_delivery import append_material_supplement
from intelligence.services.research_annotations import (
    CANDIDATE_REVIEW_NOTICE as CANDIDATE_REVIEW_NOTICE,
    append_research_supplement,
)
from intelligence.services.research_contract import ResearchRunContext, ResearchTaskContract
from intelligence.services.research_public_prose import has_public_analysis, sanitize_public_analysis


@dataclass(frozen=True)
class FinishCandidate:
    task_frame_hash: str
    draft: str
    bindings: tuple[OutputEvidenceBinding, ...]
    evidence: tuple[AgentEvidence, ...]
    review_pending: bool = True


def _candidate_object(content: object) -> tuple[str, dict[str, object]] | None:
    if isinstance(content, Mapping):
        return "", dict(content)
    if not isinstance(content, str):
        return None
    raw = content.strip()
    # Whole fenced object only; never harvest arbitrary JSON from code blocks.
    fence = re.fullmatch(r"```(?:json)?\s*\n(.*)\n```", raw, re.S | re.I)
    if fence:
        raw = fence.group(1).strip()
    decoder = json.JSONDecoder(object_pairs_hook=_unique_json_keys)
    found = []
    # The only mixed form is prose followed by ONE complete terminal envelope
    # at a line boundary. No brace slicing, partial decoding or trailing text.
    for start in re.finditer(r"(?m)^[ \t]*(?=\{)", raw):
        offset = start.end()
        try:
            value, end = decoder.raw_decode(raw, offset)
        except (ValueError, RecursionError):
            continue
        if isinstance(value, dict) and {"status", "draft", "gaps", "bindings"} <= value.keys():
            found.append((offset, end, value))
    if len(found) != 1:
        return None
    start, end, value = found[0]
    prefix = raw[:start].strip()
    if raw[end:].strip() or any(token in prefix for token in ("{", "}", "```", "tool_calls", "FINAL_JSON", "system_prompt")):
        return None
    return prefix, value


def retain_finish_candidate(
    content: object, *, context: ResearchRunContext, evidence: tuple[AgentEvidence, ...],
) -> FinishCandidate | None:
    """Return analysis only after a separate, complete identity validation.

    A FORMAT error earlier in admission cannot conceal an INTEGRITY error.
    Research completeness is deliberately not claimed by this value.
    """
    if not context.contract.task_frame_hash:
        return None
    parsed = _candidate_object(content)
    if parsed is None:
        return None
    prefix, value = parsed
    if set(value) - {"status", "draft", "gaps", "bindings", "history_research", "task_id", "task_frame_hash"}:
        return None
    if not isinstance(value.get("draft"), str):
        return None
    try:
        bindings = validate_finish_bindings(value, context=context, evidence=evidence)
        history = value.get("history_research")
        if isinstance(history, Mapping):
            # Qualification complaints must not mask an unknown result_ref.
            # This validation-only copy cannot change the retained claim or
            # the original admission; it reaches the history identity check.
            identity_value = {**value, "history_research": {
                **history, "research_only": True,
                "promotion_eligible": False, "decision_eligible": False,
            }}
            assess_history_finish(identity_value, context=context)
        assess_history_finish(value, context=context)
    except ValueError as exc:
        # History checks identity before ordinary quality. Binding format
        # errors are NOT automatically deemed safe just because they are format.
        if not str(getattr(exc, "code", "")).startswith("history_") or getattr(getattr(exc, "kind", None), "value", "") != "substance":
            return None
    body = append_research_supplement(
        sanitize_public_analysis(prefix, evidence),
        sanitize_public_analysis(value["draft"], evidence),
    )
    if not has_public_analysis(body):
        return None
    return FinishCandidate(context.contract.task_frame_hash, body, bindings, evidence)


def merge_finish_candidates(
    candidates: tuple[FinishCandidate, ...], *, task_frame_hash: str,
    evidence: tuple[AgentEvidence, ...], draft: str,
    bindings: tuple[OutputEvidenceBinding, ...], contract: ResearchTaskContract | None = None,
) -> tuple[str, tuple[OutputEvidenceBinding, ...], int]:
    """Append without overwriting, rebinding ordinals or certifying coverage.

    Unreconcilable candidates stay in the private trajectory, not in this
    answer. The accepted/current binding owns conflicts, never the old draft.
    The count is the number of included drafts still pending admission review,
    including exact copies; previously admitted prose alone does not add doubt.
    """
    hashes = [item.content_hash for item in evidence if item.content_hash]
    if len(hashes) != len(set(hashes)) or (contract and contract.task_frame_hash != task_frame_hash):
        return draft, bindings, 0
    by_hash = {item.content_hash: item for item in evidence if item.content_hash}
    by_id = {eid: digest for digest, eid in evidence_ordinal_table(evidence).items()}
    body = ""
    retained = 0
    included = False
    merged = {item.output_id: item for item in bindings}
    if len(merged) != len(bindings):
        return draft, bindings, 0
    for candidate in candidates:
        if candidate.task_frame_hash != task_frame_hash or not candidate.draft.strip():
            continue
        old_hashes = [item.content_hash for item in candidate.evidence if item.content_hash]
        if len(old_hashes) != len(set(old_hashes)) or len({item.output_id for item in candidate.bindings}) != len(candidate.bindings):
            continue
        if any(
            item.content_hash not in by_hash or replace(
                by_hash[item.content_hash], reexcerpted=item.reexcerpted,
                pointer_dropped=item.pointer_dropped,
                structural_neighbor_demoted=item.structural_neighbor_demoted, deep_read=item.deep_read,
            ) != item
            for item in candidate.evidence if item.content_hash
        ):
            continue
        old_ids = {eid: digest for digest, eid in evidence_ordinal_table(candidate.evidence).items()}
        if any(old_ids.get(eid) != by_id.get(eid) for eid in cited_evidence_ordinals(candidate.draft)):
            continue
        # Exact inclusion prevents duplicate prose, not review/binding loss.
        # Copying a rejected draft into a later finish is not a completion pass.
        included = True
        retained += int(candidate.review_pending)
        if candidate.draft not in body:
            body = append_material_supplement(contract, body, candidate.draft) if contract else append_research_supplement(body, candidate.draft)
        for prior in candidate.bindings:
            current = merged.get(prior.output_id)
            if current is None:
                merged[prior.output_id] = prior
            elif current.basis == prior.basis and not current.gap and not prior.gap:
                merged[prior.output_id] = replace(current, evidence_hashes=tuple(dict.fromkeys((*current.evidence_hashes, *prior.evidence_hashes))))
    if not included:
        return draft, bindings, 0
    if draft and body in draft:
        body = draft  # exact aggregate containment, never fuzzy sentence editing
    elif draft not in body:
        body = append_material_supplement(contract, body, draft) if contract else append_research_supplement(body, draft)
    return body, tuple(merged.values()), retained

