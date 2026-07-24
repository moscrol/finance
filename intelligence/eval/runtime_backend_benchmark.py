"""Provider-neutral result contract for multi-runtime finance benchmarks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
import re
from statistics import median
from typing import Any


_RUN_STATUSES = frozenset(
    {"completed", "partial", "degraded", "failed", "clarification"}
)
_STRUCTURAL_STATUSES = frozenset({"completed", "partial", "failed"})
_SEMANTIC_STATUSES = frozenset(
    {"passed", "repaired", "rejected", "unavailable"}
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _non_negative_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _optional_non_negative_int(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    return _non_negative_int(value, field_name)


def _finite_non_negative(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite non-negative number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field_name} must be a finite non-negative number")
    return number


@dataclass(frozen=True)
class RuntimeArmResult:
    case_id: str
    backend: str
    model: str
    answer: str
    status: str
    structural_status: str
    semantic_status: str
    task_alignment_score: float
    latency_seconds: float
    provider_attempts: int
    llm_calls: int
    tool_calls: int
    duplicate_queries: int
    input_tokens: int | None
    output_tokens: int | None
    protocol_issues: tuple[str, ...]
    artifact_sha256: str
    citations: tuple[dict[str, str], ...] = ()
    data_cutoff: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("case_id", "backend", "model"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
            object.__setattr__(self, field_name, value.strip())
        if not isinstance(self.answer, str):
            raise ValueError("answer must be a string")
        if self.status not in _RUN_STATUSES:
            raise ValueError("unsupported status")
        if self.structural_status not in _STRUCTURAL_STATUSES:
            raise ValueError("unsupported structural_status")
        if self.semantic_status not in _SEMANTIC_STATUSES:
            raise ValueError("unsupported semantic_status")
        alignment = _finite_non_negative(
            self.task_alignment_score,
            "task_alignment_score",
        )
        if alignment > 1.0:
            raise ValueError("task_alignment_score must be between 0 and 1")
        object.__setattr__(self, "task_alignment_score", alignment)
        object.__setattr__(
            self,
            "latency_seconds",
            _finite_non_negative(self.latency_seconds, "latency_seconds"),
        )
        for field_name in (
            "provider_attempts",
            "llm_calls",
            "tool_calls",
            "duplicate_queries",
        ):
            object.__setattr__(
                self,
                field_name,
                _non_negative_int(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "input_tokens",
            _optional_non_negative_int(self.input_tokens, "input_tokens"),
        )
        object.__setattr__(
            self,
            "output_tokens",
            _optional_non_negative_int(self.output_tokens, "output_tokens"),
        )
        issues = tuple(dict.fromkeys(str(item).strip() for item in self.protocol_issues))
        if any(not item for item in issues):
            raise ValueError("protocol_issues must contain non-empty strings")
        object.__setattr__(self, "protocol_issues", issues)
        if not isinstance(self.artifact_sha256, str) or not _SHA256_RE.fullmatch(
            self.artifact_sha256
        ):
            raise ValueError("artifact_sha256 must be a lowercase SHA-256 hex digest")
        citations: list[dict[str, str]] = []
        for citation in self.citations:
            if not isinstance(citation, Mapping):
                raise ValueError("citations must contain mappings")
            normalized = {
                key: str(citation.get(key) or "").strip()
                for key in ("title", "source", "date")
            }
            if not normalized["title"] or not normalized["source"]:
                raise ValueError("citations require title and source")
            citations.append(normalized)
        object.__setattr__(self, "citations", tuple(citations))
        if self.data_cutoff is not None:
            cutoff = str(self.data_cutoff).strip()
            object.__setattr__(self, "data_cutoff", cutoff or None)

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "backend": self.backend,
            "model": self.model,
            "answer": self.answer,
            "status": self.status,
            "structural_status": self.structural_status,
            "semantic_status": self.semantic_status,
            "task_alignment_score": self.task_alignment_score,
            "latency_seconds": self.latency_seconds,
            "provider_attempts": self.provider_attempts,
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "duplicate_queries": self.duplicate_queries,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "protocol_issues": list(self.protocol_issues),
            "artifact_sha256": self.artifact_sha256,
            "citations": [dict(item) for item in self.citations],
            "data_cutoff": self.data_cutoff,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> RuntimeArmResult:
        raw_issues = value.get("protocol_issues")
        if not isinstance(raw_issues, (list, tuple)):
            raise ValueError("protocol_issues must be a sequence")
        raw_citations = value.get("citations", ())
        if not isinstance(raw_citations, (list, tuple)):
            raise ValueError("citations must be a sequence")
        answer = value.get("answer")
        if not isinstance(answer, str):
            raise ValueError("answer must be a string")
        return cls(
            case_id=str(value.get("case_id") or ""),
            backend=str(value.get("backend") or ""),
            model=str(value.get("model") or ""),
            answer=answer,
            status=str(value.get("status") or ""),
            structural_status=str(value.get("structural_status") or ""),
            semantic_status=str(value.get("semantic_status") or ""),
            task_alignment_score=value.get("task_alignment_score"),
            latency_seconds=value.get("latency_seconds"),
            provider_attempts=value.get("provider_attempts"),
            llm_calls=value.get("llm_calls"),
            tool_calls=value.get("tool_calls"),
            duplicate_queries=value.get("duplicate_queries"),
            input_tokens=value.get("input_tokens"),
            output_tokens=value.get("output_tokens"),
            protocol_issues=tuple(raw_issues),
            artifact_sha256=str(value.get("artifact_sha256") or ""),
            citations=tuple(raw_citations),
            data_cutoff=(
                str(value.get("data_cutoff"))
                if value.get("data_cutoff") is not None
                else None
            ),
        )


def _derived_protocol_issues(result: RuntimeArmResult) -> tuple[str, ...]:
    issues = list(result.protocol_issues)
    if result.status == "completed" and result.structural_status != "completed":
        issues.append("completed_without_structural_completion")
    if result.status == "completed" and result.semantic_status not in {
        "passed",
        "repaired",
    }:
        issues.append("completed_without_semantic_acceptance")
    if result.structural_status == "completed" and result.semantic_status in {
        "rejected",
        "unavailable",
    }:
        issues.append("semantic_regression")
    return tuple(dict.fromkeys(issues))


def summarize_runtime_benchmark(
    *,
    case_ids: Sequence[str],
    results: Sequence[RuntimeArmResult],
    expected_backends: Sequence[str],
) -> dict[str, object]:
    """Validate arm coverage and build comparable per-backend metrics."""

    cases = tuple(str(item).strip() for item in case_ids)
    backends = tuple(str(item).strip() for item in expected_backends)
    if not cases or any(not item for item in cases) or len(set(cases)) != len(cases):
        raise ValueError("case_ids must be unique non-empty strings")
    if (
        not backends
        or any(not item for item in backends)
        or len(set(backends)) != len(backends)
    ):
        raise ValueError("expected_backends must be unique non-empty strings")

    by_key: dict[tuple[str, str], RuntimeArmResult] = {}
    for result in results:
        key = (result.case_id, result.backend)
        if key in by_key:
            raise ValueError(
                f"duplicate runtime arm result: {result.case_id}/{result.backend}"
            )
        by_key[key] = result

    expected = {(case_id, backend) for case_id in cases for backend in backends}
    missing = sorted(expected - set(by_key))
    if missing:
        rendered = ",".join(f"{case}/{backend}" for case, backend in missing)
        raise ValueError(f"missing backend results: {rendered}")
    unexpected = sorted(set(by_key) - expected)
    if unexpected:
        rendered = ",".join(f"{case}/{backend}" for case, backend in unexpected)
        raise ValueError(f"unexpected backend results: {rendered}")

    protocol_failure_count = 0
    backend_metrics: dict[str, object] = {}
    for backend in backends:
        arm_results = tuple(by_key[(case_id, backend)] for case_id in cases)
        effective_issues = tuple(
            issue
            for result in arm_results
            for issue in _derived_protocol_issues(result)
        )
        protocol_failure_count += sum(
            bool(_derived_protocol_issues(result)) for result in arm_results
        )
        input_values = tuple(
            item.input_tokens for item in arm_results if item.input_tokens is not None
        )
        output_values = tuple(
            item.output_tokens for item in arm_results if item.output_tokens is not None
        )
        backend_metrics[backend] = {
            "case_count": len(arm_results),
            "median_latency_seconds": median(
                item.latency_seconds for item in arm_results
            ),
            "provider_attempts": sum(item.provider_attempts for item in arm_results),
            "llm_calls": sum(item.llm_calls for item in arm_results),
            "tool_calls": sum(item.tool_calls for item in arm_results),
            "duplicate_queries": sum(
                item.duplicate_queries for item in arm_results
            ),
            "input_tokens": sum(input_values) if input_values else None,
            "output_tokens": sum(output_values) if output_values else None,
            "protocol_issue_count": len(effective_issues),
        }

    return {
        "schema_version": 1,
        "gate": "runtime_backend_benchmark",
        "passed": protocol_failure_count == 0,
        "case_count": len(cases),
        "arm_count": len(by_key),
        "expected_backends": list(backends),
        "protocol_failure_count": protocol_failure_count,
        "backends": backend_metrics,
        "results": [
            by_key[(case_id, backend)].to_dict()
            for case_id in cases
            for backend in backends
        ],
    }


__all__ = ["RuntimeArmResult", "summarize_runtime_benchmark"]
