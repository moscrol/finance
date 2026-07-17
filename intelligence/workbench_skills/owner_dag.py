from __future__ import annotations

import time
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass

from intelligence.services import answer_model
from intelligence.services.ask import AskResult
from intelligence.services.research_contract import (
    ResearchDeadline,
    StageArtifact,
    StageStatus,
)


@dataclass(frozen=True)
class OwnerDAGResult:
    result: AskResult | None
    artifacts: tuple[StageArtifact, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class StageExecution:
    status: StageStatus
    payload: dict[str, object]
    evidence_atom_ids: tuple[str, ...] = ()
    result: AskResult | None = None
    degrade_reason: str | None = None


@dataclass(frozen=True)
class StageAdapter:
    producer: str
    input_hash: str
    artifact_type: str
    required_output: bool
    timeout_seconds: float
    on_failure: str
    execute: Callable[
        [AskResult | None, tuple[StageArtifact, ...]],
        StageExecution,
    ]


def execute_owner_dag(
    *,
    cache_key: str,
    stages: Sequence[str],
    retrieve: Callable[[], AskResult],
    cache: MutableMapping[str, object],
    deadline: ResearchDeadline | None,
    stage_adapters: Mapping[str, StageAdapter] | None = None,
) -> OwnerDAGResult:
    artifacts: list[StageArtifact] = []
    result = _cached_result(cache_key, cache)
    warnings: list[str] = []

    for stage in stages:
        adapter = (stage_adapters or {}).get(stage)
        if deadline is not None and deadline.expired:
            warning = f"{stage} 未在统一研究截止时间内完成"
            warnings.append(warning)
            artifacts.append(
                StageArtifact(
                    stage=stage,
                    status="timeout",
                    elapsed_ms=0,
                    producer=adapter.producer if adapter is not None else "",
                    input_hash=adapter.input_hash if adapter is not None else "",
                    artifact_type=adapter.artifact_type if adapter is not None else "",
                    required_output=(
                        adapter.required_output if adapter is not None else False
                    ),
                    timeout_seconds=(
                        adapter.timeout_seconds if adapter is not None else 0.0
                    ),
                    on_failure=(
                        adapter.on_failure if adapter is not None else ""
                    ),
                    degrade_reason=warning,
                )
            )
            continue

        started = time.monotonic()
        if adapter is not None:
            adapter_cache_key = (
                f"stage:{adapter.producer}:{adapter.input_hash}"
            )
            cached_execution = cache.get(adapter_cache_key)
            if isinstance(cached_execution, StageExecution):
                execution = cached_execution
            else:
                configured_timeout = max(0.0, adapter.timeout_seconds)
                stage_timeout = (
                    deadline.stage_timeout(configured_timeout)
                    if deadline is not None
                    else configured_timeout
                )
                if stage_timeout <= 0:
                    warning = f"{stage} 执行前已耗尽阶段时限"
                    warnings.append(warning)
                    artifacts.append(
                        _timeout_artifact(
                            stage,
                            adapter,
                            started,
                            warning,
                        )
                    )
                    continue
                try:
                    execution = adapter.execute(
                        result,
                        tuple(artifacts),
                    )
                except Exception as exc:  # noqa: BLE001
                    warning = f"{stage} 执行失败（{type(exc).__name__}）"
                    warnings.append(warning)
                    artifacts.append(
                        StageArtifact(
                            stage=stage,
                            status="failed",
                            elapsed_ms=_elapsed_ms(started),
                            producer=adapter.producer,
                            input_hash=adapter.input_hash,
                            artifact_type=adapter.artifact_type,
                            required_output=adapter.required_output,
                            timeout_seconds=adapter.timeout_seconds,
                            on_failure=adapter.on_failure,
                            degrade_reason=warning,
                        )
                    )
                    continue
                cache[adapter_cache_key] = execution
                if (time.monotonic() - started) > stage_timeout:
                    warning = (
                        f"{stage} 超过阶段时限 "
                        f"{stage_timeout:g} 秒；结果已完整收束并保留"
                    )
                    warnings.append(warning)
                    if execution.result is not None:
                        result = execution.result
                    if execution.degrade_reason:
                        warnings.append(execution.degrade_reason)
                    artifacts.append(
                        StageArtifact(
                            stage=stage,
                            status="timeout",
                            elapsed_ms=_elapsed_ms(started),
                            producer=adapter.producer,
                            input_hash=adapter.input_hash,
                            artifact_type=adapter.artifact_type,
                            required_output=adapter.required_output,
                            timeout_seconds=adapter.timeout_seconds,
                            on_failure=adapter.on_failure,
                            evidence_atom_ids=execution.evidence_atom_ids,
                            payload={
                                **execution.payload,
                                "termination_mode": "joined_overrun",
                                "background_work_remaining": False,
                            },
                            degrade_reason=warning,
                        )
                    )
                    continue
            if execution.result is not None:
                result = execution.result
            if execution.degrade_reason:
                warnings.append(execution.degrade_reason)
            artifacts.append(
                StageArtifact(
                    stage=stage,
                    status=execution.status,
                    elapsed_ms=_elapsed_ms(started),
                    producer=adapter.producer,
                    input_hash=adapter.input_hash,
                    artifact_type=adapter.artifact_type,
                    required_output=adapter.required_output,
                    timeout_seconds=adapter.timeout_seconds,
                    on_failure=adapter.on_failure,
                    evidence_atom_ids=execution.evidence_atom_ids,
                    payload=execution.payload,
                    degrade_reason=execution.degrade_reason,
                )
            )
            continue

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


def _timeout_artifact(
    stage: str,
    adapter: StageAdapter,
    started: float,
    warning: str,
) -> StageArtifact:
    return StageArtifact(
        stage=stage,
        status="timeout",
        elapsed_ms=_elapsed_ms(started),
        producer=adapter.producer,
        input_hash=adapter.input_hash,
        artifact_type=adapter.artifact_type,
        required_output=adapter.required_output,
        timeout_seconds=adapter.timeout_seconds,
        on_failure=adapter.on_failure,
        payload={
            "termination_mode": "joined",
            "background_work_remaining": False,
        },
        degrade_reason=warning,
    )
