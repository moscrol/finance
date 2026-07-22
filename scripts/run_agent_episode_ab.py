#!/usr/bin/env python3
"""Run an isolated bare/current/continuous-episode comparison artifact."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import sys
import time
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.services import llm_refine
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_tools import (
    build_episode_registry,
    is_deterministic_fast_path,
    latest_market_date,
    run_deterministic_fast_path,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.glm_agent_runtime import GLMAgentRuntime
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
                model=(
                    model_override
                    or str(raw.get("model") or "glm-5.2").strip()
                ),
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
                raw.get("answer")
                or raw.get("current_answer")
                or nested.get("answer")
            )
            if case_id and isinstance(answer, str) and answer.strip():
                result: dict[str, object] = {"answer": answer.strip()}
                for key in (
                    "latency",
                    "llm_calls",
                    "tool_calls",
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
        raise ValueError(
            "current results missing case answers: " + ",".join(missing)
        )
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


def _build_registry(frame, context):
    return build_episode_registry(frame, context)


def _run_fast_path(frame, timeout: float):
    return run_deterministic_fast_path(frame, timeout=timeout)


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

        def fresh_context():
            if not control.contract_required:
                return None
            return build_episode_context(
                control.task_frame,
                task_id=f"ab:{case.case_id}",
                capabilities=control.capabilities,
                tier=args.tier,
                timeout=case.timeout,
                synthesis_reserve=(
                    GLMAgentRuntime.synthesis_reserve_for_task(
                        tier=args.tier,
                        question_type=control.task_frame.question_type,
                    )
                ),
                today=case.as_of,
                latest_data_date=(None if args.dry_run else latest_market_date()),
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
        context = fresh_context()
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
                "tool_calls": 0,
            }
        elif control.terminal_kind != "research" or context is None:
            record["episode"] = {
                "execution_kind": "not_applicable",
                "status": "partial",
                "answer": "",
                "gaps": ["case is not a research episode"],
                "llm_calls": 0,
                "tool_calls": 0,
            }
        elif is_deterministic_fast_path(control.task_frame):
            record["episode"] = _run_fast_path(
                control.task_frame,
                case.timeout,
            )
        else:
            started = time.monotonic()
            try:
                registry = _build_registry(control.task_frame, context)
                outcome = _build_runtime(case.model).run(
                    task_frame=control.task_frame,
                    context=context,
                    registry=registry,
                )
                verified = verify_episode_outcome(context.contract, outcome)
                episode_payload = verified.to_dict()
                episode_payload["execution_kind"] = "continuous_episode"
                episode_payload["answer"] = outcome.draft
                episode_payload["evidence_hashes"] = [
                    item.content_hash for item in outcome.evidence
                ]
                episode_payload["traces"] = [
                    item.to_dict() for item in outcome.traces
                ]
                episode_payload["gaps"] = list(outcome.gaps)
                episode_payload["stop_reason"] = outcome.stop_reason
                episode_payload["llm_calls"] = outcome.usage.llm_calls
                episode_payload["tool_calls"] = outcome.usage.tool_calls
                episode_payload["invalid_actions"] = (
                    outcome.usage.invalid_actions
                )
                episode_payload["latency"] = round(
                    time.monotonic() - started,
                    4,
                )
                record["episode"] = episode_payload
            except Exception as exc:  # sidecar records failure; never mutates 8792
                record["episode"] = {
                    "execution_kind": "continuous_episode",
                    "verified_status": "failed",
                    "answer": "",
                    "issues": [f"{type(exc).__name__}: {str(exc)[:240]}"],
                    "latency": round(time.monotonic() - started, 4),
                    "llm_calls": 0,
                    "tool_calls": 0,
                }
        records.append(record)

    artifact = {
        "schema_version": 1,
        "mode": "dry_run" if args.dry_run else "live",
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
