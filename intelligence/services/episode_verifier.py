"""Deterministic output-to-evidence verification for continuous episodes.

The verifier proves structural grounding only: a declared output is bound to
evidence that was actually collected by an authorized evidence type. Semantic
claim support remains the responsibility of the shared grounding judge before
public presentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from intelligence.services.agent_runtime import AgentOutcome
from intelligence.services.episode_output_substance import (
    required_output_evidence_floor,
    required_outputs_without_substance,
)
from intelligence.services.generic_research_owner import CompletionReport
from intelligence.services.research_contract import (
    OutputStatus,
    ResearchTaskContract,
)


VerifiedStatus = Literal["completed", "partial", "clarification", "failed"]


@dataclass(frozen=True)
class VerifiedEpisodeOutcome:
    outcome: AgentOutcome
    completion: CompletionReport
    verified_status: VerifiedStatus
    issues: tuple[str, ...] = ()
    # Keep the immutable contract alongside the structural result.  The
    # semantic gate needs the exact required-output identities when a repair
    # is parsed and re-verified; reconstructing a weaker contract from prose
    # would make that second verification unsound.
    contract: ResearchTaskContract | None = None
    missing_outputs: tuple[str, ...] = ()
    mandatory_missing_capabilities: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "verified_status": self.verified_status,
            "issues": list(self.issues),
            "completion": self.completion.to_dict(),
            "outcome": self.outcome.to_dict(),
            "missing_outputs": list(self.missing_outputs),
            "mandatory_missing_capabilities": list(
                self.mandatory_missing_capabilities
            ),
        }


def verify_episode_outcome(
    contract: ResearchTaskContract,
    outcome: AgentOutcome,
) -> VerifiedEpisodeOutcome:
    """Derive structural completion from bindings, not model confidence."""

    if (
        not contract.task_frame_hash
        or outcome.task_frame_hash != contract.task_frame_hash
    ):
        raise ValueError("contract/outcome task frame hash mismatch")

    issues: list[str] = []
    evidence_by_hash = {}
    duplicate_hashes: set[str] = set()
    for item in outcome.evidence:
        content_hash = item.content_hash.strip()
        if not content_hash:
            issues.append(f"evidence from {item.tool} has empty content hash")
            continue
        if content_hash in evidence_by_hash:
            duplicate_hashes.add(content_hash)
            issues.append(f"duplicate evidence hash: {content_hash}")
            continue
        evidence_by_hash[content_hash] = item

    required_by_id = {
        required.output_id: required for required in contract.required_outputs
    }
    bindings = {binding.output_id: binding for binding in outcome.bindings}
    unknown_outputs = sorted(set(bindings) - set(required_by_id))
    for output_id in unknown_outputs:
        issues.append(f"unknown output binding: {output_id}")

    statuses: list[OutputStatus] = []
    bound_tools: set[str] = set()
    for required in contract.required_outputs:
        binding = bindings.get(required.output_id)
        if binding is None:
            gap = f"仍缺少：{required.description}"
            statuses.append(
                OutputStatus(
                    required.output_id,
                    "missing" if required.required else "gap",
                    (),
                    gap,
                )
            )
            if required.required:
                issues.append(f"missing required output: {required.output_id}")
            continue

        basis_mismatch = binding.basis != required.grounding_mode
        if basis_mismatch:
            issues.append(
                f"grounding basis mismatch for {required.output_id}: "
                f"expected {required.grounding_mode}, got {binding.basis}"
            )

        if binding.gap:
            statuses.append(
                OutputStatus(
                    required.output_id,
                    "missing" if required.required else "gap",
                    (),
                    binding.gap,
                )
            )
            if required.required:
                issues.append(f"required output reports gap: {required.output_id}")
            continue

        unknown_hashes = tuple(
            content_hash
            for content_hash in binding.evidence_hashes
            if content_hash not in evidence_by_hash
        )
        collided_hashes = tuple(
            content_hash
            for content_hash in binding.evidence_hashes
            if content_hash in duplicate_hashes
        )
        if unknown_hashes:
            issues.append(
                f"unknown evidence hash for {required.output_id}: "
                + ",".join(unknown_hashes)
            )
        if collided_hashes:
            issues.append(
                f"ambiguous evidence hash for {required.output_id}: "
                + ",".join(collided_hashes)
            )
        evidence_items = tuple(
            evidence_by_hash[content_hash]
            for content_hash in binding.evidence_hashes
            if content_hash in evidence_by_hash and content_hash not in duplicate_hashes
        )
        wrong_types = tuple(
            item.tool
            for item in evidence_items
            if required.evidence_types and item.tool not in required.evidence_types
        )
        if wrong_types:
            issues.append(
                f"unsupported evidence type for {required.output_id}: "
                + ",".join(wrong_types)
            )

        evidence_floor = required_output_evidence_floor(required.output_id)
        missing_floor = tuple(
            tool
            for tool in evidence_floor
            if not any(item.tool == tool for item in evidence_items)
        )
        if missing_floor:
            issues.append(
                f"missing required evidence type for {required.output_id}: "
                + ",".join(missing_floor)
            )

        valid = bool(
            (
                required.grounding_mode != "evidence"
                or bool(binding.evidence_hashes)
            )
            and not unknown_hashes
            and not collided_hashes
            and not wrong_types
            and not missing_floor
            and not basis_mismatch
            and len(evidence_items) == len(binding.evidence_hashes)
        )
        if valid:
            bound_tools.update(item.tool for item in evidence_items)
            statuses.append(
                OutputStatus(
                    required.output_id,
                    "fulfilled",
                    binding.evidence_hashes,
                )
            )
        else:
            gap = f"{required.description}未绑定可验证证据"
            statuses.append(
                OutputStatus(
                    required.output_id,
                    "missing" if required.required else "gap",
                    (),
                    gap,
                )
            )

    mandatory_missing = tuple(
        capability
        for capability in contract.evidence_plan.mandatory_capabilities
        if capability not in bound_tools
    )
    if mandatory_missing:
        issues.append(
            "missing mandatory capability evidence: " + ",".join(mandatory_missing)
        )

    missing_substance = required_outputs_without_substance(contract, outcome.draft)
    if missing_substance:
        missing_set = set(missing_substance)
        statuses = [
            OutputStatus(
                status.output_id,
                "missing",
                (),
                f"{required_by_id[status.output_id].description}缺少实质内容",
            )
            if status.output_id in missing_set
            else status
            for status in statuses
        ]
        issues.extend(
            f"required output lacks substantive answer: {output_id}"
            for output_id in missing_substance
        )

    required_statuses = tuple(
        status
        for required, status in zip(contract.required_outputs, statuses)
        if required.required
    )
    missing_outputs = tuple(
        status.output_id
        for required, status in zip(contract.required_outputs, statuses)
        if required.required and status.status != "fulfilled"
    )
    all_required_fulfilled = all(
        status.status == "fulfilled" for status in required_statuses
    )
    structurally_complete = bool(
        all_required_fulfilled
        and not mandatory_missing
        and not unknown_outputs
        and outcome.draft.strip()
    )

    if outcome.status in {"clarification", "failed"}:
        verified_status = outcome.status
    elif structurally_complete and outcome.status == "completed":
        verified_status = "completed"
    else:
        # Verification may preserve or downgrade the runtime status, never
        # upgrade it. A structurally complete partial can still enter the
        # semantic gate and release useful prose as a first-class partial.
        verified_status = "partial"

    completion = CompletionReport(
        status="completed" if verified_status == "completed" else "partial",
        outputs=tuple(statuses),
        factual_grounding=("fulfilled" if all_required_fulfilled else "partial"),
        causal_adequacy="unknown",
        task_coverage=("fulfilled" if all_required_fulfilled else "partial"),
        business_status=("complete" if verified_status == "completed" else "partial"),
    )
    return VerifiedEpisodeOutcome(
        outcome=outcome,
        completion=completion,
        verified_status=verified_status,
        issues=tuple(dict.fromkeys(issues)),
        contract=contract,
        missing_outputs=missing_outputs,
        mandatory_missing_capabilities=mandatory_missing,
    )


__all__ = [
    "VerifiedEpisodeOutcome",
    "VerifiedStatus",
    "verify_episode_outcome",
]
