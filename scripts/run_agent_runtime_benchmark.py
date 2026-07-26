#!/usr/bin/env python3
"""Run frozen finance cases through explicit AgentRuntime backends."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.eval.capability_monotonicity import directness_score
from intelligence.eval.runtime_backend_benchmark import (
    RuntimeArmResult,
    RuntimeDiagnostics,
    summarize_runtime_benchmark,
)
from intelligence.services import llm_refine
from intelligence.services.agent_runtime import AgentModelClient, ModelTurn
from intelligence.services.agent_runtime_factory import resolve_runtime_backend
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_finalizer import EpisodeFinalizer
from intelligence.services.episode_semantic_verifier import SemanticEpisodeOutcome
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
)
from intelligence.services.episode_tools import (
    build_episode_registry,
    is_deterministic_fast_path,
    latest_market_date,
    run_deterministic_fast_path,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.glm_agent_runtime import GLMAgentRuntime
from intelligence.services.glm_agent_runtime import GLMModelClient
from intelligence.services.llm_refine import LLMProvider
from intelligence.services.llm_settings import SessionLLMSettings
from intelligence.services.turn_control_core import TurnControlCore
from scripts.smoke_workbench_self_use import _atomic_write_json


@dataclass(frozen=True)
class RuntimeBenchmarkCase:
    case_id: str
    question: str
    as_of: str
    tier: str
    timeout: float
    required_outputs: tuple[str, ...]
    conversation_context: tuple[dict[str, str], ...] = ()


class RuntimeBenchmarkInfrastructureError(RuntimeError):
    def __init__(self, *, case_id: str, backend: str, reason: str) -> None:
        super().__init__(reason)
        self.case_id = case_id
        self.backend = backend
        self.reason = reason


_INFRASTRUCTURE_STOP_REASONS = frozenset(
    {
        "sdk_auth_unavailable",
        "sdk_rate_limited",
        "sdk_upstream_unavailable",
        "sdk_transport_unavailable",
    }
)


def _source_provenance() -> tuple[str, bool]:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5.0,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
                timeout=5.0,
            ).stdout.strip()
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("benchmark source provenance unavailable") from exc
    if not revision:
        raise ValueError("benchmark source revision unavailable")
    return revision, dirty


def _load_cases(path: Path) -> tuple[RuntimeBenchmarkCase, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("questions file must contain a non-empty cases list")
    cases: list[RuntimeBenchmarkCase] = []
    seen: set[str] = set()
    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise ValueError("each benchmark case must be an object")
        case_id = str(raw.get("id") or raw.get("case_id") or "").strip()
        question = str(raw.get("question") or "").strip()
        if not case_id or not question or case_id in seen:
            raise ValueError("benchmark cases require unique ids and questions")
        seen.add(case_id)
        raw_outputs = raw.get("required_outputs")
        if not isinstance(raw_outputs, list) or not all(
            isinstance(item, str) and item.strip() for item in raw_outputs
        ):
            raise ValueError(f"case {case_id} requires acceptance outputs")
        raw_context = raw.get("conversation_context") or []
        if not isinstance(raw_context, list):
            raise ValueError("conversation_context must be a list")
        conversation_context: list[dict[str, str]] = []
        for item in raw_context:
            if not isinstance(item, dict):
                raise ValueError("conversation context items must be objects")
            role = str(item.get("role") or "").strip()
            content = str(item.get("content") or "").strip()
            if role not in {"user", "assistant"} or not content:
                raise ValueError("conversation context items must be non-empty")
            conversation_context.append({"role": role, "content": content})
        timeout = float(raw.get("timeout") or 180.0)
        tier = str(raw.get("tier") or "standard").strip()
        if timeout <= 0 or tier not in {"quick", "standard", "deep"}:
            raise ValueError(f"case {case_id} has invalid budget")
        cases.append(
            RuntimeBenchmarkCase(
                case_id=case_id,
                question=question,
                as_of=str(raw.get("as_of") or date.today().isoformat()),
                tier=tier,
                timeout=timeout,
                required_outputs=tuple(item.strip() for item in raw_outputs),
                conversation_context=tuple(conversation_context),
            )
        )
    return tuple(cases)


def _context_text(case: RuntimeBenchmarkCase) -> str:
    return "\n".join(
        f"{item['role']}: {item['content']}" for item in case.conversation_context
    )


def _freeze_case(
    case: RuntimeBenchmarkCase,
    *,
    dry_run: bool,
) -> tuple[object, object | None]:
    core = TurnControlCore()
    llm_complete = (
        (lambda *_args, **_kwargs: (None, None, "dry_run"))
        if dry_run
        else None
    )
    previous_control = None
    prior_transcript: list[str] = []
    previous_turn_id: str | None = None
    for index, item in enumerate(case.conversation_context, start=1):
        if item["role"] == "user":
            previous_turn_id = (
                f"runtime-benchmark:{case.case_id}:context:{index}"
            )
            previous_control = core.control(
                item["content"],
                context="\n".join(prior_transcript),
                previous_frame=(
                    previous_control.task_frame
                    if previous_control is not None
                    else None
                ),
                previous_intent=(
                    previous_control.turn_intent
                    if previous_control is not None
                    else None
                ),
                previous_turn_id=previous_turn_id,
                llm_complete=llm_complete,
            )
        prior_transcript.append(f"{item['role']}: {item['content']}")
    control = core.control(
        case.question,
        context=_context_text(case),
        previous_frame=(
            previous_control.task_frame if previous_control is not None else None
        ),
        previous_intent=(
            previous_control.turn_intent if previous_control is not None else None
        ),
        previous_turn_id=previous_turn_id,
        llm_complete=llm_complete,
    )
    context = None
    if dry_run and control.contract_required:
        context = build_episode_context(
            control.task_frame,
            task_id=f"runtime-benchmark:{case.case_id}",
            capabilities=control.capabilities,
            tier=case.tier,
            timeout=case.timeout,
            synthesis_reserve=GLMAgentRuntime.synthesis_reserve_for_task(
                tier=case.tier,
                question_type=control.task_frame.question_type,
            ),
            today=case.as_of,
            latest_data_date=case.as_of,
        )
    return control, context


def _planned_case(
    case: RuntimeBenchmarkCase,
    control: object,
    context: object | None,
) -> dict[str, object]:
    frame = control.task_frame
    contract = getattr(context, "contract", None)
    frame_outputs = set(frame.required_outputs)
    return {
        "id": case.case_id,
        "question": case.question,
        "as_of": case.as_of,
        "tier": case.tier,
        "timeout": case.timeout,
        "conversation_context": list(case.conversation_context),
        "acceptance_outputs": list(case.required_outputs),
        "acceptance_contract_gaps": [
            output_id
            for output_id in case.required_outputs
            if output_id not in frame_outputs
        ],
        "task_frame_hash": frame.task_frame_hash,
        "task_frame": frame.to_dict(),
        "control": {
            "execution_route": control.execution_route,
            "terminal_kind": control.terminal_kind,
            "capabilities": list(control.capabilities),
        },
        "contract": contract.to_dict() if contract is not None else None,
        "execution_status": "planned",
    }


def _fresh_context(
    case: RuntimeBenchmarkCase,
    control: object,
    *,
    latest_data_date: str,
):
    if not control.contract_required:
        return None
    return build_episode_context(
        control.task_frame,
        task_id=f"runtime-benchmark:{case.case_id}",
        capabilities=control.capabilities,
        tier=case.tier,
        timeout=case.timeout,
        synthesis_reserve=GLMAgentRuntime.synthesis_reserve_for_task(
            tier=case.tier,
            question_type=control.task_frame.question_type,
        ),
        today=case.as_of,
        latest_data_date=latest_data_date,
    )


def _build_runtime(
    backend: str,
    case: RuntimeBenchmarkCase,
    context: object,
    *,
    sdk_gpt_providers: tuple[LLMProvider, ...] = (),
) -> tuple[object, str]:
    del context
    providers = llm_refine.detect_providers()
    if backend == "continuous_glm":
        client = GLMModelClient(providers=providers)
        finalizer = EpisodeFinalizer(client)
        return (
            GLMAgentRuntime(client=client, finalizer=finalizer),
            providers[0].model if providers else "glm-unavailable",
        )
    if backend == "sdk_glm":
        if not providers:
            raise RuntimeError("sdk_glm provider unavailable")
        from intelligence.services.openai_agents_runtime import (
            OpenAIAgentsRuntime,
            build_glm_sdk_model_factory,
        )

        provider = providers[0]
        return (
            OpenAIAgentsRuntime(
                backend="sdk_glm",
                model_name=provider.model,
                model_factory=build_glm_sdk_model_factory(
                    api_key=provider.api_key,
                    base_url=provider.base_url,
                    model=provider.model,
                    timeout=case.timeout,
                ),
            ),
            provider.model,
        )
    if backend == "sdk_gpt":
        from intelligence.services.openai_agents_runtime import (
            OpenAIAgentsRuntime,
            build_gpt_sdk_model,
            build_gpt_sdk_model_factory,
        )

        provider = next(
            (item for item in sdk_gpt_providers if item.name == "openai"),
            None,
        )
        if provider is not None:
            return (
                OpenAIAgentsRuntime(
                    backend="sdk_gpt",
                    model_name=provider.model,
                    model_factory=build_gpt_sdk_model_factory(
                        api_key=provider.api_key,
                        base_url=provider.base_url,
                        model=provider.model,
                        timeout=case.timeout,
                    ),
                ),
                provider.model,
            )
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("openai_api_key_missing")
        model = str(os.environ.get("OPENAI_AGENT_MODEL") or "gpt-5.6-sol")
        return (
            OpenAIAgentsRuntime(
                backend="sdk_gpt",
                model_name=model,
                model=build_gpt_sdk_model(model),
            ),
            model,
        )
    if backend == "codex_headless":
        from intelligence.services.codex_headless_runtime import (
            CodexHeadlessRuntime,
        )

        runtime = CodexHeadlessRuntime(
            model=os.environ.get("CODEX_HEADLESS_MODEL")
        )
        return runtime, runtime.model_name
    raise RuntimeError(f"unsupported benchmark backend: {backend}")


class _AttemptCountingClient:
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
    def __init__(self, *, providers: tuple[LLMProvider, ...] = ()) -> None:
        client = _AttemptCountingClient(
            GLMModelClient(providers=providers or llm_refine.detect_providers())
        )
        self._client = client
        self._verifier = SemanticEpisodeVerifier(
            primary_judge=client,
            finalizer=EpisodeFinalizer(client),
        )

    @property
    def provider_attempts(self) -> int:
        return self._client.provider_attempts

    def verify(self, **kwargs: object) -> SemanticEpisodeOutcome:
        return self._verifier.verify(**kwargs)


def _build_semantic_verifier(
    _case: RuntimeBenchmarkCase,
    _context: object,
    *,
    providers: tuple[LLMProvider, ...] = (),
) -> _SemanticVerifierRun:
    return _SemanticVerifierRun(providers=providers)


def _build_registry(
    frame: object,
    context: object,
    *,
    finance_root: Path,
    knowledge_wiki: Path,
):
    return build_episode_registry(
        frame,
        context,
        finance_root=finance_root,
        knowledge_wiki=knowledge_wiki,
    )


def _task_alignment_score(frame: object, answer: str) -> float:
    text = str(answer or "").strip()
    if not text:
        return 0.0
    subject = str(getattr(frame, "subject", "") or "").strip()
    return directness_score(
        str(getattr(frame, "raw_question", "") or ""),
        text,
        direct_targets=((subject,) if subject else ()),
    )


def _duplicate_query_count(events: object) -> int:
    if not isinstance(events, (tuple, list)):
        return 0
    return sum(
        1
        for event in events
        if getattr(event, "kind", "") == "tool_error"
        and getattr(event, "payload", {}).get("error") == "duplicate_query"
    )


def _runtime_tokens(events: object) -> tuple[int | None, int | None]:
    if not isinstance(events, (tuple, list)):
        return None, None
    for event in reversed(events):
        if getattr(event, "kind", "") != "runtime_result":
            continue
        payload = getattr(event, "payload", {})
        input_tokens = payload.get("input_tokens")
        output_tokens = payload.get("output_tokens")
        return (
            input_tokens if isinstance(input_tokens, int) else None,
            output_tokens if isinstance(output_tokens, int) else None,
        )
    return None, None


def _bound_public_citations(
    outcome: object,
) -> tuple[tuple[dict[str, str], ...], str | None]:
    bindings = getattr(outcome, "bindings", ())
    bound_hashes = {
        content_hash
        for binding in bindings
        for content_hash in getattr(binding, "evidence_hashes", ())
    }
    citations: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    cutoffs: list[str] = []
    for item in getattr(outcome, "evidence", ()):
        if getattr(item, "content_hash", "") not in bound_hashes:
            continue
        title = " ".join(str(getattr(item, "title", "") or "").split())
        source = " ".join(str(getattr(item, "source", "") or "").split())
        source_date = str(getattr(item, "source_date", "") or "").strip()
        key = (title, source, source_date)
        if not title or not source or key in seen:
            continue
        seen.add(key)
        citations.append(
            {"title": title, "source": source, "date": source_date}
        )
        try:
            cutoffs.append(date.fromisoformat(source_date).isoformat())
        except ValueError:
            pass
    return tuple(citations), (max(cutoffs) if cutoffs else None)


def _artifact_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ledger_call_count(ledger: object | None) -> int:
    if ledger is None or not callable(getattr(ledger, "summary", None)):
        return 0
    value = ledger.summary().get("call_count", 0)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _arm_failure(
    *,
    case: RuntimeBenchmarkCase,
    backend: str,
    model: str,
    started: float,
    issue: str,
) -> RuntimeArmResult:
    payload = {"case_id": case.case_id, "backend": backend, "issue": issue}
    return RuntimeArmResult(
        case_id=case.case_id,
        backend=backend,
        model=model,
        answer="",
        status="failed",
        structural_status="failed",
        semantic_status="unavailable",
        task_alignment_score=0.0,
        latency_seconds=max(0.0, time.monotonic() - started),
        provider_attempts=0,
        llm_calls=0,
        tool_calls=0,
        duplicate_queries=0,
        input_tokens=None,
        output_tokens=None,
        protocol_issues=(issue,),
        artifact_sha256=_artifact_hash(payload),
        stop_reason="runner_exception",
        effective_timeout_seconds=case.timeout,
    )


def _run_research_arm(
    case: RuntimeBenchmarkCase,
    control: object,
    backend: str,
    *,
    finance_root: Path,
    knowledge_wiki: Path,
    latest_data_date: str,
    sdk_gpt_providers: tuple[LLMProvider, ...] = (),
) -> RuntimeArmResult:
    started = time.monotonic()
    model = "unavailable"
    outcome = None
    try:
        context = _fresh_context(
            case,
            control,
            latest_data_date=latest_data_date,
        )
        if context is None:
            raise RuntimeError("research_contract_missing")
        runtime, model = _build_runtime(
            backend,
            case,
            context,
            sdk_gpt_providers=sdk_gpt_providers,
        )
        registry = _build_registry(
            control.task_frame,
            context,
            finance_root=finance_root,
            knowledge_wiki=knowledge_wiki,
        )
        with llm_refine.call_ledger_scope() as ledger:
            outcome = runtime.run(
                task_frame=control.task_frame,
                context=context,
                registry=registry,
            )
            if outcome.stop_reason in _INFRASTRUCTURE_STOP_REASONS:
                raise RuntimeBenchmarkInfrastructureError(
                    case_id=case.case_id,
                    backend=backend,
                    reason=outcome.stop_reason,
                )
            verified = verify_episode_outcome(context.contract, outcome)
            semantic_providers = (
                sdk_gpt_providers if backend == "sdk_gpt" else ()
            )
            runtime_semantic_providers = getattr(
                runtime,
                "semantic_providers",
                None,
            )
            if not semantic_providers and callable(runtime_semantic_providers):
                semantic_providers = tuple(runtime_semantic_providers())
            semantic_verifier = _build_semantic_verifier(
                case,
                context,
                providers=semantic_providers,
            )
            semantic = semantic_verifier.verify(
                frame=control.task_frame,
                structurally_verified=verified,
                deadline=context.deadline,
            )
            ledger_calls = _ledger_call_count(ledger)
        final_verified = semantic.verified
        final_outcome = final_verified.outcome
        citations, data_cutoff = _bound_public_citations(final_outcome)
        input_tokens, output_tokens = _runtime_tokens(final_outcome.events)
        semantic_attempts = int(
            getattr(semantic_verifier, "provider_attempts", 0) or 0
        )
        provider_attempts = max(
            final_outcome.usage.llm_calls + semantic_attempts,
            ledger_calls,
        )
        issues: list[str] = []
        if final_outcome.usage.invalid_actions:
            issues.append(
                f"runtime_invalid_actions:{final_outcome.usage.invalid_actions}"
            )
        if (
            final_outcome.status == "completed"
            and final_verified.verified_status != "completed"
        ):
            issues.extend(final_verified.issues)
        root_budget = getattr(context, "root_budget", None)
        root_budget_snapshot = (
            root_budget.to_dict()
            if root_budget is not None and callable(getattr(root_budget, "to_dict", None))
            else None
        )
        diagnostics = RuntimeDiagnostics.from_runtime_state(
            events=tuple(event.to_dict() for event in final_outcome.events),
            provider_traces=tuple(trace.to_dict() for trace in final_outcome.traces),
            missing_outputs=final_verified.missing_outputs,
            mandatory_missing_capabilities=(
                final_verified.mandatory_missing_capabilities
            ),
            gaps=final_outcome.gaps,
            bindings=tuple(binding.to_dict() for binding in final_outcome.bindings),
            root_budget=root_budget_snapshot,
        )
        return RuntimeArmResult(
            case_id=case.case_id,
            backend=backend,
            model=model,
            answer=semantic.public_answer,
            status=semantic.status,
            structural_status=final_verified.verified_status,
            semantic_status=semantic.judge_status,
            task_alignment_score=_task_alignment_score(
                control.task_frame,
                semantic.public_answer,
            ),
            latency_seconds=max(0.0, time.monotonic() - started),
            provider_attempts=provider_attempts,
            llm_calls=final_outcome.usage.llm_calls,
            tool_calls=final_outcome.usage.tool_calls,
            duplicate_queries=_duplicate_query_count(final_outcome.events),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            protocol_issues=tuple(issues),
            artifact_sha256=_artifact_hash(final_outcome.to_dict()),
            stop_reason=final_outcome.stop_reason,
            effective_timeout_seconds=min(
                case.timeout,
                context.policy.total_seconds,
            ),
            citations=citations,
            data_cutoff=data_cutoff,
            diagnostics=diagnostics,
        )
    except RuntimeBenchmarkInfrastructureError:
        raise
    except Exception as exc:
        return _arm_failure(
            case=case,
            backend=backend,
            model=model,
            started=started,
            issue=f"{type(exc).__name__}:{str(exc)[:160]}",
        )


def _run_non_research_arms(
    case: RuntimeBenchmarkCase,
    control: object,
    backends: tuple[str, ...],
) -> tuple[RuntimeArmResult, ...]:
    started = time.monotonic()
    if is_deterministic_fast_path(control.task_frame):
        raw = dict(
            run_deterministic_fast_path(
                control.task_frame,
                timeout=case.timeout,
            )
        )
        answer = str(raw.get("answer") or "")
        status = str(raw.get("status") or "failed")
        structural = status if status in {"completed", "partial", "failed"} else "failed"
        semantic = "passed" if status == "completed" and answer else "unavailable"
        payload_hash = _artifact_hash(raw)
        source_trade_date = next(
            (
                str(trace.get("source_trade_date") or "").strip()
                for trace in raw.get("traces", [])
                if isinstance(trace, dict) and trace.get("source_trade_date")
            ),
            "",
        )
        citations = (
            (
                {
                    "title": "指数日线结构化行情",
                    "source": "tencent_kline",
                    "date": source_trade_date,
                },
            )
            if source_trade_date
            else ()
        )
        return tuple(
            RuntimeArmResult(
                case_id=case.case_id,
                backend=backend,
                model="deterministic_fast_path",
                answer=answer,
                status=status,
                structural_status=structural,
                semantic_status=semantic,
                task_alignment_score=_task_alignment_score(
                    control.task_frame,
                    answer,
                ),
                latency_seconds=max(0.0, time.monotonic() - started),
                provider_attempts=0,
                llm_calls=0,
                tool_calls=int(raw.get("tool_calls") or 0),
                duplicate_queries=0,
                input_tokens=None,
                output_tokens=None,
                protocol_issues=(),
                artifact_sha256=payload_hash,
                stop_reason=str(
                    raw.get("stop_reason")
                    or raw.get("execution_kind")
                    or "deterministic_fast_path"
                ),
                effective_timeout_seconds=min(case.timeout, 15.0),
                citations=citations,
                data_cutoff=source_trade_date or None,
            )
            for backend in backends
        )
    answer = "\n".join(control.clarification_questions)
    payload_hash = _artifact_hash(
        {"task_frame_hash": control.task_frame.task_frame_hash, "answer": answer}
    )
    return tuple(
        RuntimeArmResult(
            case_id=case.case_id,
            backend=backend,
            model="turn_control",
            answer=answer,
            status="clarification",
            structural_status="partial",
            semantic_status="unavailable",
            task_alignment_score=_task_alignment_score(control.task_frame, answer),
            latency_seconds=max(0.0, time.monotonic() - started),
            provider_attempts=0,
            llm_calls=0,
            tool_calls=0,
            duplicate_queries=0,
            input_tokens=None,
            output_tokens=None,
            protocol_issues=(),
            artifact_sha256=payload_hash,
            stop_reason="clarification",
            effective_timeout_seconds=0.0,
        )
        for backend in backends
    )


def _run_runtime_arm(
    case: RuntimeBenchmarkCase,
    control: object,
    backends: tuple[str, ...],
    *,
    finance_root: Path,
    knowledge_wiki: Path,
    latest_data_date: str,
    sdk_gpt_providers: tuple[LLMProvider, ...] = (),
) -> tuple[dict[str, object], tuple[RuntimeArmResult, ...]]:
    if control.terminal_kind == "research" and not is_deterministic_fast_path(
        control.task_frame
    ):
        arms = tuple(
            _run_research_arm(
                case,
                control,
                backend,
                finance_root=finance_root,
                knowledge_wiki=knowledge_wiki,
                latest_data_date=latest_data_date,
                sdk_gpt_providers=sdk_gpt_providers,
            )
            for backend in backends
        )
    else:
        arms = _run_non_research_arms(case, control, backends)
    record = _planned_case(case, control, None)
    record["execution_status"] = "completed"
    record["arms"] = [arm.to_dict() for arm in arms]
    return record, arms


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the frozen finance benchmark across AgentRuntime backends"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backend", action="append", required=True)
    parser.add_argument("--questions-file", type=Path, required=True)
    parser.add_argument("--finance-root", type=Path)
    parser.add_argument("--knowledge-wiki", type=Path)
    parser.add_argument(
        "--keychain-user",
        help="Load the sdk_gpt provider from macOS Keychain without exporting a key",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        source_revision, source_dirty = _source_provenance()
        cases = _load_cases(args.questions_file)
        backends = tuple(
            resolve_runtime_backend(value).name for value in args.backend
        )
        if len(set(backends)) != len(backends):
            raise ValueError("backend names must be unique")
        finance_root = (
            args.finance_root.expanduser().resolve()
            if args.finance_root is not None
            else None
        )
        knowledge_wiki = (
            args.knowledge_wiki.expanduser().resolve()
            if args.knowledge_wiki is not None
            else None
        )
        market_data_date = None
        sdk_gpt_providers: tuple[LLMProvider, ...] = ()
        if not args.dry_run:
            if finance_root is None or knowledge_wiki is None:
                raise ValueError(
                    "live benchmark requires --finance-root and --knowledge-wiki"
                )
            if not finance_root.is_dir() or not knowledge_wiki.is_dir():
                raise ValueError("benchmark data roots must be existing directories")
            market_data_date = latest_market_date(finance_root)
            if market_data_date is None:
                raise ValueError("finance root has no readable market data date")
            latest_required_date = max(
                date.fromisoformat(case.as_of) for case in cases
            ).isoformat()
            if market_data_date < latest_required_date:
                raise ValueError(
                    "finance root market data is stale: "
                    f"{market_data_date} < {latest_required_date}"
                )
            if args.keychain_user:
                saved_provider = SessionLLMSettings().byok_provider(
                    args.keychain_user
                )
                if saved_provider is None:
                    raise ValueError("saved Keychain provider unavailable")
                sdk_gpt_providers = (saved_provider,)
        frozen = [
            (case, *_freeze_case(case, dry_run=args.dry_run)) for case in cases
        ]
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"runtime benchmark failed: {exc}", file=sys.stderr)
        return 2

    return_code = 0
    infrastructure_failure: dict[str, str] | None = None
    if not args.dry_run:
        try:
            executed = []
            for index, (case, control, _context) in enumerate(frozen, start=1):
                print(
                    f"runtime benchmark [{index}/{len(frozen)}] {case.case_id}",
                    flush=True,
                )
                executed.append(
                    _run_runtime_arm(
                        case,
                        control,
                        backends,
                        finance_root=finance_root,
                        knowledge_wiki=knowledge_wiki,
                        latest_data_date=market_data_date,
                        sdk_gpt_providers=sdk_gpt_providers,
                    )
                )
            records = [record for record, _arms in executed]
            arm_results = tuple(
                arm for _record, arms in executed for arm in arms
            )
            summary = summarize_runtime_benchmark(
                case_ids=tuple(case.case_id for case in cases),
                results=arm_results,
                expected_backends=backends,
            )
        except RuntimeBenchmarkInfrastructureError as exc:
            records = [record for record, _arms in executed]
            arm_results = tuple(
                arm for _record, arms in executed for arm in arms
            )
            infrastructure_failure = {
                "case_id": exc.case_id,
                "backend": exc.backend,
                "reason": exc.reason,
            }
            summary = {
                "gate": "runtime_backend_benchmark",
                "passed": False,
                "infrastructure_failure": infrastructure_failure,
                "completed_case_count": len(records),
                "completed_arm_count": len(arm_results),
            }
            return_code = 3
        except Exception as exc:
            print(f"runtime benchmark failed: {exc}", file=sys.stderr)
            return 2
    else:
        records = [
            _planned_case(case, control, context)
            for case, control, context in frozen
        ]
        summary = None

    artifact: dict[str, Any] = {
        "schema_version": 1,
        "mode": "dry_run" if args.dry_run else "live",
        "generated_at": date.today().isoformat(),
        "source_revision": source_revision,
        "source_dirty": source_dirty,
        "expected_backends": list(backends),
        "case_count": len(cases),
        "runtime_switched": False,
        "canonical_runtime_port": 8792,
        "canonical_runtime_touched": False,
        "finance_root": str(finance_root) if finance_root is not None else None,
        "knowledge_wiki": (
            str(knowledge_wiki) if knowledge_wiki is not None else None
        ),
        "market_data_date": market_data_date,
        "credential_source": (
            "keychain" if sdk_gpt_providers else "environment"
        ),
        "cases": records,
    }
    if summary is not None:
        artifact["summary"] = summary
    if infrastructure_failure is not None:
        artifact["infrastructure_failure"] = infrastructure_failure
    _atomic_write_json(args.output, artifact)
    print(f"runtime benchmark artifact written: {args.output}")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
