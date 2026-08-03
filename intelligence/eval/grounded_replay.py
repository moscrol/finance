"""Frozen-input replay for the Grounded Composer and semantic judge.

The replay intentionally skips retrieval and DecisionBrief generation. It reads
the exact artifacts persisted by a completed Workbench run, reconstructs the
production ``AnswerSpec``, and reuses the production registry/prompt builders.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, ContextManager

from intelligence.services import answer_model, llm_refine
from intelligence.services.keychain_credentials import (
    KeychainCredentialError,
    KeychainCredentialStore,
)
from intelligence.services.research_contract import EvidenceAtom, StageArtifact

SCHEMA_VERSION = "grounded-replay-1.0"
_COMPOSER_PREDICTION_SECONDS = (110, 180)


class ReplayInputError(ValueError):
    """The frozen input or an upstream replay artifact is not usable."""


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReplayInputError(f"{key} must be a non-empty string")
    return value.strip()


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ReplayInputError(f"{key} must be a string or null")
    return value


def _string_tuple(
    payload: dict[str, Any],
    key: str,
    *,
    required: bool = False,
) -> tuple[str, ...]:
    if key not in payload and not required:
        return ()
    value = payload.get(key)
    if not isinstance(value, list):
        raise ReplayInputError(f"{key} must be a list")
    if any(not isinstance(item, str) for item in value):
        raise ReplayInputError(f"{key} must contain only strings")
    return tuple(value)


def _object_tuple(payload: dict[str, Any], key: str) -> tuple[dict[str, Any], ...]:
    value = payload.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ReplayInputError(f"{key} must be a list of objects")
    return tuple(dict(item) for item in value)


def _claim_from_payload(payload: dict[str, Any]) -> answer_model.Claim:
    try:
        status = answer_model.ClaimStatus(_required_str(payload, "status"))
    except ValueError as exc:
        raise ReplayInputError("claim status is invalid") from exc
    confidence = payload.get("confidence")
    if confidence is not None and (
        isinstance(confidence, bool) or not isinstance(confidence, (int, float))
    ):
        raise ReplayInputError("claim confidence must be numeric or null")
    return answer_model.Claim(
        claim_id=_required_str(payload, "claim_id"),
        text=_required_str(payload, "text"),
        claim_type=_required_str(payload, "claim_type"),
        theme=_required_str(payload, "theme"),
        evidence_ids=_string_tuple(payload, "evidence_ids"),
        evidence_tier=str(payload.get("evidence_tier") or ""),
        freshness=_optional_str(payload, "freshness"),
        confidence=float(confidence) if confidence is not None else None,
        counter_evidence=_string_tuple(payload, "counter_evidence"),
        status=status,
        company=_optional_str(payload, "company"),
    )


def _theme_spec_from_payload(payload: dict[str, Any]) -> answer_model.ThemeResearchSpec:
    return answer_model.ThemeResearchSpec(
        theme=_required_str(payload, "theme"),
        pack_id=_required_str(payload, "pack_id"),
        definition=_required_str(payload, "definition"),
        chain_stages=_string_tuple(payload, "chain_stages", required=True),
        company_scope=_required_str(payload, "company_scope"),
        as_of=_optional_str(payload, "as_of"),
        evidence_requirements=_string_tuple(
            payload,
            "evidence_requirements",
            required=True,
        ),
        counter_evidence_requirements=_string_tuple(
            payload,
            "counter_evidence_requirements",
            required=True,
        ),
        trigger_conditions=_string_tuple(
            payload,
            "trigger_conditions",
            required=True,
        ),
        verification_actions=_string_tuple(
            payload,
            "verification_actions",
            required=True,
        ),
        focus_entities=_string_tuple(payload, "focus_entities", required=True),
        requested_sections=_string_tuple(
            payload,
            "requested_sections",
            required=True,
        ),
    )


def _company_from_payload(payload: dict[str, Any]) -> answer_model.CompanyAssessment:
    try:
        tier = answer_model.CompanyTier(_required_str(payload, "tier"))
    except ValueError as exc:
        raise ReplayInputError("company tier is invalid") from exc
    return answer_model.CompanyAssessment(
        company=_required_str(payload, "company"),
        ticker=str(payload.get("ticker") or ""),
        chain_stage=str(payload.get("chain_stage") or ""),
        directness=str(payload.get("directness") or ""),
        tier=tier,
        claims=tuple(
            _claim_from_payload(item) for item in _object_tuple(payload, "claims")
        ),
        evidence_gaps=_string_tuple(payload, "evidence_gaps"),
    )


def _source_from_payload(payload: dict[str, Any]) -> answer_model.EvidenceRef:
    return answer_model.EvidenceRef(
        evidence_id=_required_str(payload, "evidence_id"),
        source=_required_str(payload, "source"),
        detail=str(payload.get("detail") or ""),
        tier=str(payload.get("tier") or ""),
        source_date=_optional_str(payload, "source_date"),
        freshness=str(payload.get("freshness") or "unknown"),
        content_hash=str(payload.get("content_hash") or ""),
        source_revision=str(payload.get("source_revision") or ""),
    )


def _quality_from_payload(payload: object) -> answer_model.AnswerQualityReport:
    if not isinstance(payload, dict):
        raise ReplayInputError("quality must be an object")
    issues = _object_tuple(payload, "issues")
    return answer_model.AnswerQualityReport(
        issues=tuple(
            answer_model.QualityIssue(
                code=_required_str(issue, "code"),
                severity=_required_str(issue, "severity"),
                message=_required_str(issue, "message"),
            )
            for issue in issues
        )
    )


def answer_spec_from_payload(payload: object) -> answer_model.AnswerSpec:
    """Reconstruct the production dataclasses from ``AnswerSpec.to_dict``."""

    if not isinstance(payload, dict):
        raise ReplayInputError("answer_spec.json must contain an object")
    research_spec = payload.get("research_spec")
    if not isinstance(research_spec, dict):
        raise ReplayInputError("research_spec must be an object")

    stage_artifacts: list[StageArtifact] = []
    for item in _object_tuple(payload, "research_artifacts"):
        artifact = StageArtifact.from_dict(item)
        if artifact is None:
            raise ReplayInputError("research_artifacts contains an invalid record")
        stage_artifacts.append(artifact)

    evidence_atoms: list[EvidenceAtom] = []
    for item in _object_tuple(payload, "research_evidence_atoms"):
        atom = EvidenceAtom.from_dict(item)
        if atom is None:
            raise ReplayInputError("research_evidence_atoms contains an invalid record")
        evidence_atoms.append(atom)

    return answer_model.AnswerSpec(
        research_spec=_theme_spec_from_payload(research_spec),
        summary=tuple(
            _claim_from_payload(item) for item in _object_tuple(payload, "summary")
        ),
        verified_facts=tuple(
            _claim_from_payload(item)
            for item in _object_tuple(payload, "verified_facts")
        ),
        company_table=tuple(
            _company_from_payload(item)
            for item in _object_tuple(payload, "company_table")
        ),
        counter_evidence=tuple(
            _claim_from_payload(item)
            for item in _object_tuple(payload, "counter_evidence")
        ),
        gaps=tuple(
            _claim_from_payload(item) for item in _object_tuple(payload, "gaps")
        ),
        triggers=tuple(
            _claim_from_payload(item) for item in _object_tuple(payload, "triggers")
        ),
        candidate_facts=tuple(
            _claim_from_payload(item)
            for item in _object_tuple(payload, "candidate_facts")
        ),
        next_actions=_string_tuple(payload, "next_actions", required=True),
        sources=tuple(
            _source_from_payload(item) for item in _object_tuple(payload, "sources")
        ),
        system_notices=_string_tuple(payload, "system_notices", required=True),
        prompt_constraints=_string_tuple(
            payload,
            "prompt_constraints",
            required=True,
        ),
        presentation_kind=str(payload.get("presentation_kind") or "theme_research"),
        presentation_title=str(payload.get("presentation_title") or ""),
        presentation_profile=str(payload.get("presentation_profile") or "theme"),
        research_artifacts=tuple(stage_artifacts),
        research_evidence_atoms=tuple(evidence_atoms),
        quality=_quality_from_payload(payload.get("quality")),
    )


def _decision_brief_from_payload(payload: object) -> answer_model.DecisionBrief:
    if not isinstance(payload, dict):
        raise ReplayInputError("decision_brief.json must contain an object")
    return answer_model.DecisionBrief(
        direct_answer=_required_str(payload, "direct_answer"),
        core_tension=_required_str(payload, "core_tension"),
        supports=_string_tuple(payload, "supports", required=True),
        counterevidence=_string_tuple(payload, "counterevidence", required=True),
        unknowns=_string_tuple(payload, "unknowns", required=True),
        upgrade_conditions=_string_tuple(
            payload,
            "upgrade_conditions",
            required=True,
        ),
        downgrade_conditions=_string_tuple(
            payload,
            "downgrade_conditions",
            required=True,
        ),
        chain_mapping=_string_tuple(payload, "chain_mapping", required=True),
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReplayInputError(f"cannot read {path.name}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ReplayInputError(f"invalid JSON in {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReplayInputError(f"{path.name} must contain an object")
    return payload


def _file_sha256(path: Path) -> str:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ReplayInputError(f"cannot hash {path.name}: {exc}") from exc
    return sha256(content).hexdigest()


def _json_sha256(value: object) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(serialized).hexdigest()


def _git_revision() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


@dataclass(frozen=True)
class FrozenRun:
    run_dir: Path
    run_id: str
    question: str
    answer_spec: answer_model.AnswerSpec
    decision_brief: answer_model.DecisionBrief
    input_sha256: dict[str, str]


def load_frozen_run(run_dir: Path) -> FrozenRun:
    run_dir = run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        raise ReplayInputError("run-dir must be an existing directory")
    paths = {
        "run.json": run_dir / "run.json",
        "answer_spec.json": run_dir / "answer_spec.json",
        "decision_brief.json": run_dir / "decision_brief.json",
    }
    run_payload = _read_json_object(paths["run.json"])
    answer_payload = _read_json_object(paths["answer_spec.json"])
    brief_payload = _read_json_object(paths["decision_brief.json"])
    question = _required_str(run_payload, "question")
    run_id = str(run_payload.get("run_id") or run_dir.name)
    return FrozenRun(
        run_dir=run_dir,
        run_id=run_id,
        question=question,
        answer_spec=answer_spec_from_payload(answer_payload),
        decision_brief=_decision_brief_from_payload(brief_payload),
        input_sha256={name: _file_sha256(path) for name, path in paths.items()},
    )


@dataclass(frozen=True)
class ReplayArtifact:
    phase: str
    status: str
    run_id: str
    revision: str
    grant_seconds: float
    elapsed_ms: int
    elapsed_is_lower_bound: bool
    input_sha256: dict[str, str]
    prompt_sha256: str
    completion_tokens: int | None
    finish_reason: str | None
    provider: str | None
    model: str | None
    failure_reason: str | None
    output_text: str | None
    parsed_output: dict[str, object] | None
    deterministic_issues: tuple[dict[str, str], ...]
    prediction: dict[str, object]
    validation_status: str | None = None
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "phase": self.phase,
            "status": self.status,
            "run_id": self.run_id,
            "revision": self.revision,
            "grant_seconds": self.grant_seconds,
            "elapsed_ms": self.elapsed_ms,
            "elapsed_is_lower_bound": self.elapsed_is_lower_bound,
            "input_sha256": dict(self.input_sha256),
            "prompt_sha256": self.prompt_sha256,
            "completion_tokens": self.completion_tokens,
            "finish_reason": self.finish_reason,
            "provider": self.provider,
            "model": self.model,
            "failure_reason": self.failure_reason,
            "output_text": self.output_text,
            "parsed_output": self.parsed_output,
            "deterministic_issues": list(self.deterministic_issues),
            "prediction": dict(self.prediction),
            "validation_status": self.validation_status,
        }

    @classmethod
    def from_dict(cls, value: object) -> ReplayArtifact:
        if not isinstance(value, dict):
            raise ReplayInputError("replay artifact must be an object")
        input_hashes = value.get("input_sha256")
        issues = value.get("deterministic_issues")
        prediction = value.get("prediction")
        parsed = value.get("parsed_output")
        if not isinstance(input_hashes, dict) or not all(
            isinstance(key, str) and isinstance(item, str)
            for key, item in input_hashes.items()
        ):
            raise ReplayInputError("input_sha256 must be a string map")
        if not isinstance(issues, list) or any(
            not isinstance(item, dict) for item in issues
        ):
            raise ReplayInputError("deterministic_issues must be a list")
        if not isinstance(prediction, dict):
            raise ReplayInputError("prediction must be an object")
        if parsed is not None and not isinstance(parsed, dict):
            raise ReplayInputError("parsed_output must be an object or null")
        completion_tokens = value.get("completion_tokens")
        if completion_tokens is not None and (
            isinstance(completion_tokens, bool)
            or not isinstance(completion_tokens, int)
        ):
            raise ReplayInputError("completion_tokens must be an integer or null")
        return cls(
            schema_version=str(value.get("schema_version") or SCHEMA_VERSION),
            phase=_required_str(value, "phase"),
            status=_required_str(value, "status"),
            run_id=_required_str(value, "run_id"),
            revision=_required_str(value, "revision"),
            grant_seconds=float(value.get("grant_seconds")),
            elapsed_ms=int(value.get("elapsed_ms")),
            elapsed_is_lower_bound=bool(value.get("elapsed_is_lower_bound")),
            input_sha256=dict(input_hashes),
            prompt_sha256=str(value.get("prompt_sha256") or ""),
            completion_tokens=completion_tokens,
            finish_reason=_optional_str(value, "finish_reason"),
            provider=_optional_str(value, "provider"),
            model=_optional_str(value, "model"),
            failure_reason=_optional_str(value, "failure_reason"),
            output_text=_optional_str(value, "output_text"),
            parsed_output=dict(parsed) if isinstance(parsed, dict) else None,
            deterministic_issues=tuple(dict(item) for item in issues),
            prediction=dict(prediction),
            validation_status=_optional_str(value, "validation_status"),
        )


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))


def _is_timeout_reason(reason: str) -> bool:
    normalized = str(reason or "").casefold()
    return "截止时间" in normalized or "超时" in normalized or "timeout" in normalized


def _composer_prediction(status: str, elapsed_ms: int) -> dict[str, object]:
    seconds = elapsed_ms / 1000
    if status == "timeout":
        verdict = "greater_than_or_equal_to_grant"
    elif seconds < 40:
        verdict = "below_40_seconds"
    elif seconds < _COMPOSER_PREDICTION_SECONDS[0]:
        verdict = "below_preregistered_range"
    elif seconds <= _COMPOSER_PREDICTION_SECONDS[1]:
        verdict = "within_preregistered_range"
    else:
        verdict = "above_preregistered_range"
    return {
        "basis": {
            "brief_output_chars": 1098,
            "brief_elapsed_ms": 69740,
            "brief_max_tokens": 1200,
            "composer_max_tokens": 2400,
        },
        "range_seconds": list(_COMPOSER_PREDICTION_SECONDS),
        "verdict": verdict,
    }


def run_composer_replay(
    frozen: FrozenRun,
    *,
    grant_seconds: float,
    model_override: str | None = None,
) -> ReplayArtifact:
    registry = answer_model.grounded_claim_registry_block(
        frozen.answer_spec,
        query=frozen.question,
        max_chars=12_000,
    )
    messages = llm_refine.build_grounded_composer_messages(
        frozen.question,
        frozen.decision_brief.to_prompt_block(),
        registry,
        required_outputs=frozen.answer_spec.prompt_constraints,
    )
    started = time.monotonic()
    deadline = llm_refine.Deadline.from_timeout(grant_seconds)
    result, reason = llm_refine.synthesize_messages(
        messages,
        model_override=model_override,
        timeout=grant_seconds,
        deadline=deadline,
        temperature=0.2,
        max_tokens=2400,
        max_chars=16000,
    )
    elapsed_ms = _elapsed_ms(started)
    status = (
        "completed"
        if result is not None
        else ("timeout" if _is_timeout_reason(reason) else "failed")
    )
    return ReplayArtifact(
        phase="composer",
        status=status,
        run_id=frozen.run_id,
        revision=_git_revision(),
        grant_seconds=grant_seconds,
        elapsed_ms=elapsed_ms,
        elapsed_is_lower_bound=status == "timeout",
        input_sha256=frozen.input_sha256,
        prompt_sha256=_json_sha256(messages),
        completion_tokens=None,
        finish_reason=result.finish_reason if result is not None else None,
        provider=result.provider if result is not None else None,
        model=result.model if result is not None else model_override,
        failure_reason=reason or None,
        output_text=result.answer if result is not None else None,
        parsed_output=None,
        deterministic_issues=(),
        prediction=_composer_prediction(status, elapsed_ms),
        validation_status="not_run",
    )


def _blocked_judge_artifact(
    frozen: FrozenRun,
    composer: ReplayArtifact,
    *,
    status: str,
    reason: str,
    issues: tuple[dict[str, str], ...] = (),
) -> ReplayArtifact:
    hashes = dict(frozen.input_sha256)
    hashes["composer_artifact"] = _json_sha256(composer.to_dict())
    return ReplayArtifact(
        phase="judge",
        status=status,
        run_id=frozen.run_id,
        revision=_git_revision(),
        grant_seconds=0,
        elapsed_ms=0,
        elapsed_is_lower_bound=False,
        input_sha256=hashes,
        prompt_sha256="",
        completion_tokens=None,
        finish_reason=None,
        provider=None,
        model=None,
        failure_reason=reason,
        output_text=None,
        parsed_output=None,
        deterministic_issues=issues,
        prediction={},
        validation_status="blocked",
    )


def run_judge_replay(
    frozen: FrozenRun,
    *,
    composer_artifact: ReplayArtifact,
    grant_seconds: float,
    model_override: str | None = None,
) -> ReplayArtifact:
    if (
        composer_artifact.phase != "composer"
        or composer_artifact.status != "completed"
        or not composer_artifact.output_text
    ):
        return _blocked_judge_artifact(
            frozen,
            composer_artifact,
            status="blocked_by_composer",
            reason="composer did not produce a completed candidate",
        )

    candidate = answer_model.canonicalize_grounded_claim_ids(
        composer_artifact.output_text,
        frozen.answer_spec,
    )
    candidate = answer_model.rebind_entity_claim_ids(candidate, frozen.answer_spec)
    issues = answer_model.validate_grounded_composer_answer(
        candidate,
        frozen.answer_spec,
    )
    serialized_issues = tuple(issue.to_dict() for issue in issues)
    if any(issue.severity == "error" for issue in issues):
        repaired = answer_model.repair_grounded_composer_answer(
            candidate,
            frozen.answer_spec,
        )
        if repaired is None:
            return _blocked_judge_artifact(
                frozen,
                composer_artifact,
                status="blocked_by_validation",
                reason="deterministic repair failed",
                issues=serialized_issues,
            )
        candidate = repaired

    sentences, _unbound = answer_model.parse_grounded_sentences(candidate)
    if not sentences:
        return _blocked_judge_artifact(
            frozen,
            composer_artifact,
            status="blocked_by_validation",
            reason="candidate has no grounded sentences",
            issues=serialized_issues,
        )

    registry = answer_model.grounded_claim_registry_block(
        frozen.answer_spec,
        query=frozen.question,
        max_chars=12_000,
    )
    messages = llm_refine.build_grounding_judge_messages(
        frozen.question,
        candidate,
        registry,
    )
    started = time.monotonic()
    deadline = llm_refine.Deadline.from_timeout(grant_seconds)
    judge_override = llm_refine.judge_provider()
    context: ContextManager[None] = (
        llm_refine.provider_override(judge_override)
        if judge_override is not None
        else nullcontext()
    )
    with context:
        result, reason = llm_refine.synthesize_messages(
            messages,
            model_override=None if judge_override is not None else model_override,
            timeout=grant_seconds,
            deadline=deadline,
            temperature=0.0,
            max_tokens=1200,
            max_chars=8000,
        )
    elapsed_ms = _elapsed_ms(started)
    status = (
        "completed"
        if result is not None
        else ("timeout" if _is_timeout_reason(reason) else "failed")
    )
    parsed = (
        answer_model.parse_grounding_judge_report(
            result.answer,
            sentence_count=len(sentences),
        )
        if result is not None
        else None
    )
    hashes = dict(frozen.input_sha256)
    hashes["composer_artifact"] = _json_sha256(composer_artifact.to_dict())
    return ReplayArtifact(
        phase="judge",
        status=status,
        run_id=frozen.run_id,
        revision=_git_revision(),
        grant_seconds=grant_seconds,
        elapsed_ms=elapsed_ms,
        elapsed_is_lower_bound=status == "timeout",
        input_sha256=hashes,
        prompt_sha256=_json_sha256(messages),
        completion_tokens=None,
        finish_reason=result.finish_reason if result is not None else None,
        provider=result.provider if result is not None else None,
        model=result.model if result is not None else model_override,
        failure_reason=(
            reason
            or ("judge_output_invalid" if result is not None and parsed is None else None)
        ),
        output_text=result.answer if result is not None else None,
        parsed_output=parsed.to_dict() if parsed is not None else None,
        deterministic_issues=serialized_issues,
        prediction={},
        validation_status=(
            "valid" if parsed is not None else ("invalid" if result is not None else "not_run")
        ),
    )


def load_replay_artifact(path: Path) -> ReplayArtifact:
    return ReplayArtifact.from_dict(_read_json_object(path.expanduser().resolve()))


def write_replay_artifact(path: Path, artifact: ReplayArtifact) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(artifact.to_dict(), ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        handle.write(rendered)
        temporary = Path(handle.name)
    temporary.replace(path)


def _positive_seconds(raw: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return value


def _keychain_context(user_id: str | None) -> ContextManager[None]:
    if not user_id:
        return nullcontext()
    try:
        provider = KeychainCredentialStore().load(user_id)
    except KeychainCredentialError as exc:
        raise ReplayInputError("unable to load Keychain provider") from exc
    if provider is None:
        raise ReplayInputError("no Keychain provider configured for user")
    return llm_refine.provider_override(provider)


def _output_is_inside_run(out: Path, run_dir: Path) -> bool:
    try:
        out.expanduser().resolve().relative_to(run_dir.resolve())
    except ValueError:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="grounded-replay",
        description="Replay composer/judge from frozen Workbench artifacts",
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--phase", choices=("composer", "judge"), required=True)
    parser.add_argument("--grant-seconds", type=_positive_seconds, required=True)
    parser.add_argument("--composer-artifact", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--keychain-user")
    parser.add_argument("--model")
    args = parser.parse_args(argv)

    try:
        frozen = load_frozen_run(args.run_dir)
        if _output_is_inside_run(args.out, frozen.run_dir):
            raise ReplayInputError("--out must be outside the frozen run directory")
        if args.phase == "judge" and args.composer_artifact is None:
            parser.error("--composer-artifact is required for judge replay")
        with _keychain_context(args.keychain_user):
            if args.phase == "composer":
                artifact = run_composer_replay(
                    frozen,
                    grant_seconds=args.grant_seconds,
                    model_override=args.model,
                )
            else:
                artifact = run_judge_replay(
                    frozen,
                    composer_artifact=load_replay_artifact(
                        args.composer_artifact
                    ),
                    grant_seconds=args.grant_seconds,
                    model_override=args.model,
                )
        write_replay_artifact(args.out, artifact)
    except ReplayInputError as exc:
        print(f"grounded-replay: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "phase": artifact.phase,
                "status": artifact.status,
                "elapsed_ms": artifact.elapsed_ms,
                "artifact": str(args.out.expanduser().resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0 if artifact.status == "completed" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
