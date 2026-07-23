#!/usr/bin/env python3
"""Run an isolated bare/current/continuous-episode comparison artifact."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.services import llm_refine
from intelligence.eval.capability_monotonicity import directness_score
from intelligence.services.agent_runtime import AgentModelClient, ModelTurn
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_tools import (
    build_episode_registry,
    is_deterministic_fast_path,
    run_deterministic_fast_path,
)
from intelligence.services.episode_finalizer import EpisodeFinalizer
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.glm_agent_runtime import GLMAgentRuntime, GLMModelClient
from intelligence.services.turn_control_core import TurnControlCore
from scripts.smoke_workbench_self_use import _atomic_write_json


@dataclass(frozen=True)
class ABQuestion:
    case_id: str
    question: str
    model: str
    timeout: float
    as_of: str
    conversation_context: tuple[dict[str, str], ...] = ()


def _load_questions(path: Path, *, model_override: str | None) -> list[ABQuestion]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("questions file must contain a cases list")
    result: list[ABQuestion] = []
    seen: set[str] = set()
    for raw in payload["cases"]:
        if not isinstance(raw, dict):
            raise ValueError("each question case must be an object")
        case_id = str(raw.get("case_id") or raw.get("id") or "").strip()
        question = str(raw.get("question") or "").strip()
        if not case_id or not question:
            raise ValueError("each question case requires id and question")
        if case_id in seen:
            raise ValueError(f"duplicate question case id: {case_id}")
        seen.add(case_id)
        raw_context = raw.get("conversation_context") or ()
        if not isinstance(raw_context, (list, tuple)):
            raise ValueError("conversation_context must be a list")
        context: list[dict[str, str]] = []
        for item in raw_context:
            if not isinstance(item, dict):
                raise ValueError("conversation_context items must be objects")
            context.append(
                {
                    "role": str(item.get("role") or "user"),
                    "content": str(item.get("content") or ""),
                }
            )
        timeout = float(raw.get("timeout") or 90.0)
        if timeout <= 0:
            raise ValueError("question timeout must be positive")
        result.append(
            ABQuestion(
                case_id=case_id,
                question=question,
                model=(model_override or str(raw.get("model") or "glm-5.2").strip()),
                timeout=timeout,
                as_of=str(raw.get("as_of") or date.today().isoformat()),
                conversation_context=tuple(context),
            )
        )
    if not result:
        raise ValueError("questions file contains no cases")
    return result


def _load_current_results(
    path: Path | None,
    cases: list[ABQuestion],
) -> dict[str, dict[str, object]]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    results: dict[str, dict[str, object]] = {}
    if isinstance(payload, dict) and isinstance(payload.get("cases"), list):
        for raw in payload["cases"]:
            if not isinstance(raw, dict):
                continue
            case_id = str(raw.get("case_id") or raw.get("id") or "").strip()
            nested = raw.get("current") if isinstance(raw.get("current"), dict) else {}
            answer = (
                raw.get("answer") or raw.get("current_answer") or nested.get("answer")
            )
            if case_id and isinstance(answer, str) and answer.strip():
                result: dict[str, object] = {"answer": answer.strip()}
                for key in (
                    "latency",
                    "llm_calls",
                    "tool_calls",
                    "structural_status",
                    "semantic_status",
                    "provider_attempts",
                    "duplicate_queries",
                    "runtime_mode",
                    "runtime_revision",
                    "task_alignment_score",
                    "terminal_outcome",
                    "failure_stage",
                    "fallback_reason",
                ):
                    value = raw.get(key, nested.get(key))
                    if value is not None and not isinstance(value, (dict, list)):
                        result[key] = value
                results[case_id] = result
    elif isinstance(payload, dict):
        results = {
            str(key): {"answer": value.strip()}
            for key, value in payload.items()
            if isinstance(value, str) and value.strip()
        }
    else:
        raise ValueError("current results must be an object or cases document")
    missing = [case.case_id for case in cases if case.case_id not in results]
    if missing:
        raise ValueError("current results missing case answers: " + ",".join(missing))
    return results


def _context_text(case: ABQuestion) -> str:
    return "\n".join(
        f"{item['role']}: {item['content']}"
        for item in case.conversation_context
        if item["content"].strip()
    )


def _provider_name(provider: object | None) -> str:
    name = getattr(provider, "name", "")
    return name.strip() if isinstance(name, str) else ""


def _run_bare_arm(case: ABQuestion) -> dict[str, object]:
    started = time.monotonic()
    message, provider, reason = llm_refine.chat_with_tools(
        messages=[
            {
                "role": "system",
                "content": (
                    "直接回答用户问题。你没有外部工具或数据库；可用通用金融知识"
                    "推理，但涉及当前数据时必须明确知识边界，不得声称已检索。"
                ),
            },
            *case.conversation_context,
            {"role": "user", "content": case.question},
        ],
        tools=[],
        model_override=case.model,
        timeout=case.timeout,
        temperature=0.0,
        tool_choice="none",
        disable_thinking=True,
    )
    raw_content = message.get("content") if isinstance(message, dict) else None
    content = raw_content if isinstance(raw_content, str) else None
    return {
        "answer": content or "",
        "provider": _provider_name(provider),
        "reason": str(reason or ""),
        "latency": round(time.monotonic() - started, 4),
        "llm_calls": 1 if provider is not None else 0,
        "tool_calls": 0,
    }


def _build_runtime(model: str):
    return GLMAgentRuntime(model)


class _AttemptCountingClient:
    """Count every physical provider attempt made behind one model seam."""

    def __init__(self, delegate: AgentModelClient) -> None:
        self._delegate = delegate
        self.provider_attempts = 0

    def complete(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        timeout: float,
    ) -> ModelTurn:
        turn = self._delegate.complete(
            messages=messages,
            tools=tools,
            timeout=timeout,
        )
        self.provider_attempts += turn.provider_attempts
        return turn


class _SemanticVerifierRun:
    """Expose semantic verification together with its physical call usage."""

    def __init__(self, model: str) -> None:
        client = _AttemptCountingClient(GLMModelClient(model))
        self._client = client
        self._verifier = SemanticEpisodeVerifier(
            primary_judge=client,
            finalizer=EpisodeFinalizer(client),
        )

    @property
    def provider_attempts(self) -> int:
        return self._client.provider_attempts

    def verify(self, **kwargs):
        return self._verifier.verify(**kwargs)


def _build_semantic_verifier(model: str):
    """Build the same structural-then-semantic boundary as production."""

    return _SemanticVerifierRun(model)


def _build_registry(frame, context):
    return build_episode_registry(frame, context)


def _run_fast_path(frame, timeout: float):
    return run_deterministic_fast_path(frame, timeout=timeout)


def _runtime_identity() -> tuple[str, str]:
    configured_mode = (
        str(os.environ.get("ASK_CONTINUOUS_RUNTIME") or "").strip().lower()
    )
    mode = configured_mode if configured_mode in {"off", "canary", "on"} else "sidecar"
    repo_root = str(Path(__file__).resolve().parents[1])
    try:
        revision_result = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        dirty_result = subprocess.run(
            ["git", "-C", repo_root, "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        revision = revision_result.stdout.strip()
        if dirty_result.stdout.strip():
            revision = f"{revision}-dirty"
    except (OSError, subprocess.SubprocessError):
        revision = "unversioned"
    return mode, revision


def _normalized_structural_status(value: object) -> str:
    status = str(value or "").strip().lower()
    return status if status in {"completed", "partial", "failed"} else "partial"


def _duplicate_query_count(events: object) -> int:
    if not isinstance(events, (list, tuple)):
        return 0
    return sum(
        1
        for event in events
        if getattr(event, "kind", "") == "tool_error"
        and getattr(event, "payload", {}).get("error") == "duplicate_query"
    )


def _task_alignment_score(frame, answer: object) -> float:
    """Deterministic direct-answer score; the Episode never grades itself."""

    text = str(answer or "").strip()
    if not text:
        return 0.0
    subject = str(getattr(frame, "subject", "") or "").strip()
    return directness_score(
        str(getattr(frame, "raw_question", "") or ""),
        text,
        direct_targets=((subject,) if subject else ()),
    )


def _ledger_call_count(ledger: object | None) -> int:
    if ledger is None or not callable(getattr(ledger, "summary", None)):
        return 0
    value = ledger.summary().get("call_count", 0)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _episode_acceptance_fields(
    *,
    structural_status: object,
    semantic_status: str,
    provider_attempts: object,
    tool_calls: object,
    task_alignment_score: object,
    duplicate_queries: object = 0,
) -> dict[str, object]:
    mode, revision = _runtime_identity()

    def non_negative_int(value: object) -> int:
        return (
            value
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0
            else 0
        )

    alignment = (
        float(task_alignment_score)
        if isinstance(task_alignment_score, (int, float))
        and not isinstance(task_alignment_score, bool)
        and math.isfinite(float(task_alignment_score))
        and 0.0 <= float(task_alignment_score) <= 1.0
        else 0.0
    )
    return {
        "structural_status": _normalized_structural_status(structural_status),
        "semantic_status": (
            semantic_status
            if semantic_status in {"passed", "repaired", "rejected", "unavailable"}
            else "unavailable"
        ),
        "provider_attempts": non_negative_int(provider_attempts),
        "tool_calls": non_negative_int(tool_calls),
        "duplicate_queries": non_negative_int(duplicate_queries),
        "runtime_mode": mode,
        "runtime_revision": revision,
        "task_alignment_score": round(alignment, 4),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run isolated bare/current/continuous-agent A/B artifacts"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--questions-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--current-results", type=Path)
    parser.add_argument("--model")
    parser.add_argument(
        "--tier",
        choices=("quick", "standard", "deep"),
        default="standard",
    )
    return parser


def _base_case_payload(case: ABQuestion, control, context) -> dict[str, Any]:
    return {
        "id": case.case_id,
        "question": case.question,
        "task_frame_hash": control.task_frame.task_frame_hash,
        "control": {
            "execution_route": control.execution_route,
            "terminal_kind": control.terminal_kind,
            "needs_retrieval": control.needs_retrieval,
            "capabilities": list(control.capabilities),
            "clarification_questions": list(control.clarification_questions),
        },
        "task_frame": control.task_frame.to_dict(),
        "contract": context.contract.to_dict() if context is not None else None,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cases = _load_questions(args.questions_file, model_override=args.model)
        current_results = _load_current_results(args.current_results, cases)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"agent episode A/B failed: {exc}", file=sys.stderr)
        return 2

    records: list[dict[str, Any]] = []
    core = TurnControlCore()
    for case in cases:
        control = core.control(
            case.question,
            context=_context_text(case),
            llm_complete=(
                (lambda *_args, **_kwargs: (None, None, "dry_run"))
                if args.dry_run
                else None
            ),
        )

        def fresh_context(
            *,
            timeout: float | None = None,
            latest_data_date: str | None = None,
        ):
            if not control.contract_required:
                return None
            return build_episode_context(
                control.task_frame,
                task_id=f"ab:{case.case_id}",
                capabilities=control.capabilities,
                tier=args.tier,
                timeout=(case.timeout if timeout is None else timeout),
                synthesis_reserve=(
                    GLMAgentRuntime.synthesis_reserve_for_task(
                        tier=args.tier,
                        question_type=control.task_frame.question_type,
                    )
                ),
                today=case.as_of,
                latest_data_date=latest_data_date,
            )

        if args.dry_run:
            context = fresh_context()
            record = _base_case_payload(case, control, context)
            if case.case_id in current_results:
                record["current"] = {
                    **current_results[case.case_id],
                    "source": str(args.current_results),
                }
            record["execution_status"] = "planned"
            records.append(record)
            continue

        bare = _run_bare_arm(case)
        episode_started = time.monotonic()
        episode_deadline = episode_started + case.timeout
        deterministic = is_deterministic_fast_path(control.task_frame)
        context = (
            None
            if deterministic or control.terminal_kind != "research"
            else fresh_context(
                timeout=max(0.0, episode_deadline - time.monotonic()),
            )
        )
        record = _base_case_payload(case, control, context)
        if case.case_id in current_results:
            record["current"] = {
                **current_results[case.case_id],
                "source": str(args.current_results),
            }
        record["bare"] = bare
        if control.terminal_kind == "clarification":
            record["episode"] = {
                "execution_kind": "clarification",
                "status": "clarification",
                "answer": "\n".join(control.clarification_questions),
                "llm_calls": 0,
                **_episode_acceptance_fields(
                    structural_status="partial",
                    semantic_status="unavailable",
                    provider_attempts=0,
                    tool_calls=0,
                    task_alignment_score=1.0,
                ),
            }
        elif control.terminal_kind != "research" or (
            context is None and not deterministic
        ):
            record["episode"] = {
                "execution_kind": "not_applicable",
                "status": "partial",
                "answer": "",
                "gaps": ["case is not a research episode"],
                "llm_calls": 0,
                **_episode_acceptance_fields(
                    structural_status="partial",
                    semantic_status="unavailable",
                    provider_attempts=0,
                    tool_calls=0,
                    task_alignment_score=0.0,
                ),
            }
        elif deterministic:
            remaining = max(0.0, episode_deadline - time.monotonic())
            if remaining <= 0.001:
                fast_path = {
                    "execution_kind": "deterministic_fast_path",
                    "status": "failed",
                    "answer": "",
                    "gaps": ["episode root deadline exhausted before fast path"],
                    "llm_calls": 0,
                    "tool_calls": 0,
                }
            else:
                fast_path = dict(
                    _run_fast_path(
                        control.task_frame,
                        remaining,
                    )
                )
            fast_path.update(
                _episode_acceptance_fields(
                    structural_status=fast_path.get("status"),
                    # A completed deterministic result is verified by its
                    # typed calculator contract, not by an LLM judge. This is
                    # still a semantic pass, while preserving the zero-LLM
                    # invariant.
                    semantic_status=(
                        "passed"
                        if fast_path.get("status") == "completed"
                        and str(fast_path.get("answer") or "").strip()
                        else "unavailable"
                    ),
                    provider_attempts=fast_path.get(
                        "provider_attempts",
                        fast_path.get("llm_calls"),
                    ),
                    tool_calls=fast_path.get("tool_calls"),
                    task_alignment_score=_task_alignment_score(
                        control.task_frame,
                        fast_path.get("answer"),
                    ),
                )
            )
            fast_path["semantic_verification_mode"] = "deterministic_contract"
            fast_path["latency"] = round(time.monotonic() - episode_started, 4)
            record["episode"] = fast_path
        else:
            outcome = None
            verified = None
            semantic_verifier = None
            episode_llm_ledger = None
            episode_ledger_before = 0
            semantic_attempts = 0
            try:
                with llm_refine.call_ledger_scope() as episode_llm_ledger:
                    episode_ledger_before = _ledger_call_count(episode_llm_ledger)
                    registry = _build_registry(control.task_frame, context)
                    outcome = _build_runtime(case.model).run(
                        task_frame=control.task_frame,
                        context=context,
                        registry=registry,
                    )
                    verified = verify_episode_outcome(context.contract, outcome)
                    semantic_verifier = _build_semantic_verifier(case.model)
                    semantic_ledger_before = _ledger_call_count(episode_llm_ledger)
                    semantic = semantic_verifier.verify(
                        frame=control.task_frame,
                        structurally_verified=verified,
                        deadline=context.deadline,
                    )
                    semantic_ledger_delta = max(
                        0,
                        _ledger_call_count(episode_llm_ledger) - semantic_ledger_before,
                    )
                    semantic_attempts = max(
                        semantic_ledger_delta,
                        semantic_verifier.provider_attempts,
                    )
                episode_payload = verified.to_dict()
                episode_payload["execution_kind"] = "continuous_episode"
                episode_payload["answer"] = semantic.public_answer
                episode_payload["semantic_verifier"] = semantic.to_dict()
                final_outcome = semantic.verified.outcome
                episode_payload["evidence_hashes"] = [
                    item.content_hash for item in final_outcome.evidence
                ]
                episode_payload["traces"] = [
                    item.to_dict() for item in final_outcome.traces
                ]
                episode_payload["gaps"] = list(final_outcome.gaps)
                episode_payload["stop_reason"] = final_outcome.stop_reason
                episode_payload["llm_calls"] = final_outcome.usage.llm_calls
                episode_payload["invalid_actions"] = final_outcome.usage.invalid_actions
                episode_payload.update(
                    _episode_acceptance_fields(
                        structural_status=verified.verified_status,
                        semantic_status=semantic.judge_status,
                        provider_attempts=(
                            final_outcome.usage.llm_calls + semantic_attempts
                        ),
                        tool_calls=final_outcome.usage.tool_calls,
                        task_alignment_score=_task_alignment_score(
                            control.task_frame,
                            semantic.public_answer,
                        ),
                        duplicate_queries=_duplicate_query_count(final_outcome.events),
                    )
                )
                episode_payload["latency"] = round(
                    time.monotonic() - episode_started,
                    4,
                )
                record["episode"] = episode_payload
            except Exception as exc:  # sidecar records failure; never mutates 8792
                record["episode"] = {
                    "execution_kind": "continuous_episode",
                    "verified_status": "failed",
                    "answer": "",
                    "issues": [f"{type(exc).__name__}: {str(exc)[:240]}"],
                    "latency": round(time.monotonic() - episode_started, 4),
                    "llm_calls": (
                        outcome.usage.llm_calls if outcome is not None else 0
                    ),
                    **_episode_acceptance_fields(
                        structural_status=(
                            verified.verified_status
                            if verified is not None
                            else "failed"
                        ),
                        semantic_status="unavailable",
                        provider_attempts=(
                            max(
                                (outcome.usage.llm_calls if outcome is not None else 0)
                                + (
                                    semantic_verifier.provider_attempts
                                    if semantic_verifier is not None
                                    else 0
                                ),
                                max(
                                    0,
                                    _ledger_call_count(episode_llm_ledger)
                                    - episode_ledger_before,
                                ),
                            )
                        ),
                        tool_calls=(
                            outcome.usage.tool_calls if outcome is not None else 0
                        ),
                        task_alignment_score=0.0,
                        duplicate_queries=(
                            _duplicate_query_count(outcome.events)
                            if outcome is not None
                            else 0
                        ),
                    ),
                }
        records.append(record)

    runtime_mode, runtime_revision = _runtime_identity()
    artifact = {
        "schema_version": 1,
        "mode": "dry_run" if args.dry_run else "live",
        "runtime_mode": runtime_mode,
        "runtime_revision": runtime_revision,
        "runtime_switched": False,
        "canonical_runtime_port": 8792,
        "canonical_runtime_touched": False,
        "generated_at": date.today().isoformat(),
        "cases": records,
    }
    _atomic_write_json(args.output, artifact)
    print(f"agent episode A/B artifact written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
