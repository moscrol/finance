from __future__ import annotations

import time
from collections.abc import Callable, MutableMapping, Sequence
from dataclasses import dataclass

from intelligence.services import answer_model
from intelligence.services.ask import AskResult
from intelligence.services.research_contract import (
    ResearchDeadline,
    StageArtifact,
)


@dataclass(frozen=True)
class OwnerDAGResult:
    result: AskResult | None
    artifacts: tuple[StageArtifact, ...]
    warnings: tuple[str, ...] = ()


def execute_owner_dag(
    *,
    cache_key: str,
    stages: Sequence[str],
    retrieve: Callable[[], AskResult],
    cache: MutableMapping[str, object],
    deadline: ResearchDeadline | None,
) -> OwnerDAGResult:
    artifacts: list[StageArtifact] = []
    result = _cached_result(cache_key, cache)
    warnings: list[str] = []

    for stage in stages:
        if deadline is not None and deadline.expired:
            warning = f"{stage} 未在统一研究截止时间内完成"
            warnings.append(warning)
            artifacts.append(
                StageArtifact(
                    stage=stage,
                    status="timeout",
                    elapsed_ms=0,
                    degrade_reason=warning,
                )
            )
            continue

        started = time.monotonic()
        if result is None:
            try:
                result = retrieve()
            except Exception as exc:  # noqa: BLE001
                warning = f"{stage} 检索失败（{type(exc).__name__}）"
                warnings.append(warning)
                artifacts.append(
                    StageArtifact(
                        stage=stage,
                        status="failed",
                        elapsed_ms=_elapsed_ms(started),
                        degrade_reason=warning,
                    )
                )
                break
            cache[cache_key] = result

        payload, citation_ids, evidence_atom_ids = _stage_payload(result, stage)
        status = "completed" if citation_ids else "partial"
        degrade_reason = None
        if status == "partial":
            degrade_reason = f"{stage} 未形成可追溯证据"
            warnings.append(degrade_reason)
        artifacts.append(
            StageArtifact(
                stage=stage,
                status=status,
                elapsed_ms=_elapsed_ms(started),
                evidence_atom_ids=evidence_atom_ids,
                payload=payload,
                degrade_reason=degrade_reason,
            )
        )

    return OwnerDAGResult(
        result=result,
        artifacts=tuple(artifacts),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _cached_result(
    cache_key: str,
    cache: MutableMapping[str, object],
) -> AskResult | None:
    cached = cache.get(cache_key)
    return cached if isinstance(cached, AskResult) else None


def _stage_payload(
    result: AskResult,
    stage: str,
) -> tuple[dict[str, object], tuple[str, ...], tuple[str, ...]]:
    citation_ids = tuple(
        dict.fromkeys(citation.tag for citation in result.citations if citation.tag)
    )
    claim_ids: tuple[str, ...] = ()
    evidence_atom_ids: tuple[str, ...] = ()
    if result.answer_spec is not None:
        claims = (
            *result.answer_spec.summary,
            *result.answer_spec.verified_facts,
            *result.answer_spec.counter_evidence,
            *result.answer_spec.gaps,
        )
        claim_ids = tuple(
            dict.fromkeys(claim.claim_id for claim in claims if claim.claim_id)
        )
        evidence_atom_ids = tuple(
            atom.atom_id
            for atom in answer_model.evidence_atoms_from_answer_spec(
                result.answer_spec
            )
        )
    payload = {
        "stage": stage,
        "source_mode": "shared_owner_bundle",
        "citation_count": len(citation_ids),
        "claim_count": len(claim_ids),
        "claim_ids": list(claim_ids),
        "evidence_atom_count": len(evidence_atom_ids),
        "trade_date": result.trade_date,
        "matched_theme": result.matched_theme,
    }
    return payload, citation_ids, evidence_atom_ids


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))
