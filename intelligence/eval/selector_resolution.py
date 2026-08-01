"""Controlled, deterministic resolution metrics for the exposure selector.

The live selector is intentionally non-deterministic because it uses an LLM.  This
module freezes one candidate pool, varies only the question intent, and then evaluates
the stored ordered company lists with pure metrics.  Evidence coverage is copied into
the receipt for diagnosis but never enters the selector prompt or its ordering.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services import exposure_selector, llm_refine


REPO = Path(__file__).resolve().parents[2]
CONTROLLED_INTENTS: dict[str, str] = {
    "beneficiary": "产业链里谁最受益，为什么",
    "expansion": "谁在扩产，扩产证据是什么",
    "margin_elasticity": "原材料降价时谁的利润弹性最大",
    "revenue_realization": "谁最可能率先形成收入兑现",
}
_POOL_LIMIT = 100_000
_RBO_PERSISTENCE = 0.9


class SelectorResolutionError(ValueError):
    """The controlled probe cannot produce a trustworthy artifact."""


@dataclass(frozen=True)
class SelectorSelection:
    question: str
    companies: tuple[str, ...]
    telemetry: Mapping[str, Any] = field(default_factory=dict)
    selected_coverage: tuple[int, ...] = ()
    pool_coverage: tuple[int, ...] = ()
    provider: str | None = None
    model: str | None = None


@dataclass(frozen=True)
class PairwiseResolution:
    left: str
    right: str
    jaccard: float
    top3_changed: int
    rank_overlap: float


@dataclass(frozen=True)
class SelectorResolutionReport:
    outcome: str
    pairs: tuple[PairwiseResolution, ...]
    unique_ordered_lists: int
    union_size: int
    reason: str
    telemetry_totals: Mapping[str, int] = field(default_factory=dict)
    evidence_coverage: Mapping[str, Mapping[str, float | None]] = field(
        default_factory=dict
    )


def _ordered_unique(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return tuple(result)


def _jaccard(left: Sequence[str], right: Sequence[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    return 1.0 if not union else len(left_set & right_set) / len(union)


def _top3_changed(left: Sequence[str], right: Sequence[str]) -> int:
    sentinel = object()
    return sum(
        (left[index] if index < len(left) else sentinel)
        != (right[index] if index < len(right) else sentinel)
        for index in range(3)
    )


def rank_biased_overlap(
    left: Sequence[str],
    right: Sequence[str],
    *,
    persistence: float = _RBO_PERSISTENCE,
) -> float:
    """Finite extrapolated rank-biased overlap (RBO).

    RBO discounts deeper ranks geometrically, so a top-of-list change matters more than
    a tail swap.  The extrapolated tail term keeps identical finite lists at exactly 1.
    """

    if not 0.0 < persistence < 1.0:
        raise ValueError("persistence must be between 0 and 1")
    depth = max(len(left), len(right))
    if depth == 0:
        return 1.0
    left_seen: set[str] = set()
    right_seen: set[str] = set()
    weighted = 0.0
    last_agreement = 0.0
    for index in range(depth):
        if index < len(left):
            left_seen.add(left[index])
        if index < len(right):
            right_seen.add(right[index])
        current_depth = index + 1
        last_agreement = len(left_seen & right_seen) / current_depth
        weighted += last_agreement * (persistence**index)
    score = (1.0 - persistence) * weighted + last_agreement * (
        persistence**depth
    )
    return min(1.0, max(0.0, score))


def _nonnegative_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _median(values: Sequence[int]) -> float | None:
    eligible = [
        value
        for value in values
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
    ]
    return float(statistics.median(eligible)) if eligible else None


def analyze_selector_results(
    selections: Mapping[str, SelectorSelection],
) -> SelectorResolutionReport:
    normalized = {
        name: _ordered_unique(selection.companies)
        for name, selection in selections.items()
    }
    names = sorted(normalized)
    pairs: list[PairwiseResolution] = []
    for left_index, left_name in enumerate(names):
        for right_name in names[left_index + 1 :]:
            left = normalized[left_name]
            right = normalized[right_name]
            pairs.append(
                PairwiseResolution(
                    left=left_name,
                    right=right_name,
                    jaccard=round(_jaccard(left, right), 6),
                    top3_changed=_top3_changed(left, right),
                    rank_overlap=round(rank_biased_overlap(left, right), 6),
                )
            )

    telemetry_totals = {
        field_name: sum(
            _nonnegative_int(selection.telemetry.get(field_name))
            for selection in selections.values()
        )
        for field_name in ("llm_selected", "backfilled", "hallucinated")
    }
    coverage = {
        name: {
            "selected_median": _median(selection.selected_coverage),
            "pool_median": _median(selection.pool_coverage),
        }
        for name, selection in selections.items()
    }
    unique_ordered_lists = len(set(normalized.values()))
    union_size = len({company for companies in normalized.values() for company in companies})
    fallback_intents = sorted(
        name
        for name, selection in selections.items()
        if selection.telemetry.get("mode") != "llm"
    )
    hallucinated_intents = sorted(
        name
        for name, selection in selections.items()
        if _nonnegative_int(selection.telemetry.get("hallucinated")) > 0
    )

    if len(selections) < 2:
        outcome = "unjudgeable"
        reason = "at least two intent results are required"
    elif fallback_intents:
        outcome = "unjudgeable"
        reason = "selector fallback in: " + ", ".join(fallback_intents)
    elif hallucinated_intents:
        outcome = "unjudgeable"
        reason = "hallucinated candidate names in: " + ", ".join(hallucinated_intents)
    elif unique_ordered_lists <= 1:
        outcome = "indistinguishable"
        reason = "all intents produced the same ordered company list"
    else:
        outcome = "discriminative"
        weak_rank_only = bool(pairs) and all(
            pair.jaccard >= 0.8 and pair.rank_overlap >= 0.8 for pair in pairs
        )
        reason = (
            "ordered lists differ, but changes are mostly rank-only"
            if weak_rank_only
            else "intent changes produced distinct set or rank selections"
        )

    return SelectorResolutionReport(
        outcome=outcome,
        pairs=tuple(pairs),
        unique_ordered_lists=unique_ordered_lists,
        union_size=union_size,
        reason=reason,
        telemetry_totals=telemetry_totals,
        evidence_coverage=coverage,
    )


def canonical_payload_hash(payload: Mapping[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "artifact_sha256"}
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path) -> str | None:
    try:
        with path.open("rb") as handle:
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            return digest.hexdigest()
    except OSError:
        return None


def _json_copy(value: object) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _provider_name(provider: object) -> str | None:
    if provider is None:
        return None
    name = getattr(provider, "name", None)
    return str(name).strip() if name else type(provider).__name__


def _provider_model(provider: object) -> str | None:
    model = getattr(provider, "model", None)
    return str(model).strip() if model else None


def _git_revision() -> str:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=REPO,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SelectorResolutionError("unable to resolve code revision") from exc
    return f"{revision}-dirty" if dirty else revision


def _requested_model(model: str | None) -> str:
    if model:
        return model
    configured = str(os.environ.get("ASK_EXPOSURE_SELECTOR_MODEL") or "").strip()
    if configured:
        return configured
    provider = llm_refine.detect_provider(None)
    resolved = _provider_model(provider)
    return resolved or "unconfigured"


def run_probe(
    *,
    concept: str,
    adapter: Any,
    complete: Callable[..., tuple[str | None, Any, str]],
    limit: int = 12,
    model: str | None = None,
    code_revision: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Run four intent selections against one frozen candidate pool."""

    concept = str(concept or "").strip()
    if not concept:
        raise SelectorResolutionError("concept is required")
    if limit <= 0:
        raise SelectorResolutionError("limit must be positive")
    pool_response = adapter.get_exposure_matches(concept, limit=_POOL_LIMIT)
    raw_items = pool_response.get("items") if isinstance(pool_response, dict) else None
    if not isinstance(raw_items, list) or not raw_items:
        raise SelectorResolutionError("candidate pool is empty")
    if pool_response.get("truncated"):
        raise SelectorResolutionError("candidate pool is still truncated")
    candidate_pool = _json_copy(raw_items)
    candidate_pool_sha256 = _sha256_json(candidate_pool)
    raw_coverage = pool_response.get("evidence_coverage") or {}
    coverage = _json_copy(raw_coverage) if isinstance(raw_coverage, dict) else {}
    by_company = coverage.get("by_company") if isinstance(coverage, dict) else {}
    if not isinstance(by_company, dict):
        by_company = {}
    pool_coverage = tuple(
        _nonnegative_int(by_company.get(str(row.get("company") or "")))
        for row in candidate_pool
    )
    requested_model = _requested_model(model)

    selections: dict[str, SelectorSelection] = {}
    result_payloads: dict[str, dict[str, Any]] = {}
    providers: set[str] = set()
    provider_models: set[str] = set()
    for intent_id, question in CONTROLLED_INTENTS.items():
        call_provider: str | None = None
        call_model: str | None = None

        def captured_complete(messages, **kwargs):
            nonlocal call_provider, call_model
            content, provider, reason = complete(messages, **kwargs)
            call_provider = _provider_name(provider)
            call_model = _provider_model(provider)
            if call_provider:
                providers.add(call_provider)
            if call_model:
                provider_models.add(call_model)
            return content, provider, reason

        selected = exposure_selector.select_exposures(
            question,
            candidate_pool,
            limit,
            complete=captured_complete,
            model_override=requested_model if requested_model != "unconfigured" else None,
        )
        companies = _ordered_unique(
            [str(row.get("company") or "") for row in selected.items]
        )
        selected_coverage = tuple(
            _nonnegative_int(by_company.get(company)) for company in companies
        )
        selection = SelectorSelection(
            question=question,
            companies=companies,
            telemetry=_json_copy(selected.telemetry),
            selected_coverage=selected_coverage,
            pool_coverage=pool_coverage,
            provider=call_provider,
            model=call_model,
        )
        selections[intent_id] = selection
        result_payloads[intent_id] = {
            "question": question,
            "companies": list(companies),
            "telemetry": _json_copy(selected.telemetry),
            "provider": call_provider,
            "model": call_model,
            "candidate_pool_sha256": candidate_pool_sha256,
            "evidence_coverage": {
                "selected_median": _median(selected_coverage),
                "pool_median": _median(pool_coverage),
            },
        }

    relation_hashes: dict[str, str] = {}
    relation_path = getattr(adapter, "relation_path", None)
    if callable(relation_path):
        for relation_name in ("entity_exposures", "evidence_index"):
            digest = _sha256_file(Path(relation_path(relation_name)))
            if digest:
                relation_hashes[relation_name] = digest

    report = analyze_selector_results(selections)
    artifact: dict[str, Any] = {
        "format_version": 1,
        "artifact_kind": "exposure_selector_resolution",
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "concept": concept,
        "limit": limit,
        "model": requested_model,
        "providers": sorted(providers),
        "provider_models": sorted(provider_models),
        "code_revision": code_revision or _git_revision(),
        "candidate_pool": {
            "sha256": candidate_pool_sha256,
            "count": len(candidate_pool),
            "items": candidate_pool,
            "relation_sha256": relation_hashes,
            "evidence_coverage": coverage,
        },
        "intents": _json_copy(CONTROLLED_INTENTS),
        "results": result_payloads,
        "report": asdict(report),
    }
    artifact["artifact_sha256"] = canonical_payload_hash(artifact)
    return artifact


def write_probe_artifact(payload: Mapping[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except FileExistsError as exc:
        raise SelectorResolutionError(f"output already exists: {output}") from exc


def _cmd_probe(args: argparse.Namespace) -> int:
    adapter = KnowledgeAdapter(wiki_root=args.kb_wiki)
    artifact = run_probe(
        concept=args.concept,
        adapter=adapter,
        complete=llm_refine.complete,
        limit=args.limit,
        model=args.model,
    )
    write_probe_artifact(artifact, args.output)
    report = artifact["report"]
    print(
        f"wrote {args.output} outcome={report['outcome']} "
        f"pool={artifact['candidate_pool']['count']} "
        f"hash={artifact['artifact_sha256']}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="selector-resolution",
        description="Measure whether exposure selection changes across controlled intents",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    probe = subparsers.add_parser("probe")
    probe.add_argument("--concept", required=True)
    probe.add_argument("--output", type=Path, required=True)
    probe.add_argument("--kb-wiki", type=Path)
    probe.add_argument("--limit", type=int, default=12)
    probe.add_argument("--model")
    probe.set_defaults(handler=_cmd_probe)
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except SelectorResolutionError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
