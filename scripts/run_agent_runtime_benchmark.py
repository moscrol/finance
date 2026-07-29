#!/usr/bin/env python3
"""Run frozen finance cases through explicit AgentRuntime backends."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.eval.capability_monotonicity import directness_score
from intelligence.eval.runtime_backend_benchmark import (
    RuntimeArmResult,
    RuntimeClaim,
    RuntimeDiagnostics,
    RuntimeSource,
    summarize_runtime_benchmark,
)
from intelligence.services import llm_refine
from intelligence.services.agent_runtime import AgentModelClient, ModelTurn
from intelligence.services.agent_runtime_factory import resolve_runtime_backend
from intelligence.services.continuous_turn_adapter import ContinuousTurnAdapter
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_finalizer import EpisodeFinalizer
from intelligence.services.episode_semantic_verifier import SemanticEpisodeOutcome
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
)
from intelligence.services.episode_tools import (
    SealedFixturePolicy,
    build_episode_registry,
    is_deterministic_fast_path,
    latest_market_date,
    run_deterministic_fast_path,
)
from intelligence.services.glm_agent_runtime import GLMAgentRuntime
from intelligence.services.glm_agent_runtime import GLMModelClient
from intelligence.services.llm_refine import LLMProvider
from intelligence.services.llm_settings import SessionLLMSettings
from intelligence.services.research_contract import (
    InMemoryRootBudgetLedger,
    ResearchDeadline,
    ResearchPolicy,
)
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


@dataclass(frozen=True)
class HeadlessBenchmarkBudgetProfile:
    """Benchmark-only budget injection; production tier defaults stay untouched."""

    profile_id: str
    total_seconds: float
    max_tool_calls: int
    synthesis_reserve_seconds: float
    gateway_floor_ratio: float
    minimum_tool_calls_to_exercise: int = 0

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError("headless budget profile id must be non-empty")
        if self.total_seconds <= 0 or self.max_tool_calls <= 0:
            raise ValueError("headless budget profile requires positive limits")
        if not 0 <= self.synthesis_reserve_seconds < self.total_seconds:
            raise ValueError("headless synthesis reserve must fit inside total time")
        if not 0.0 <= self.gateway_floor_ratio <= 1.0:
            raise ValueError("headless gateway floor ratio must be between 0 and 1")
        if not 0 <= self.minimum_tool_calls_to_exercise <= self.max_tool_calls:
            raise ValueError("headless profile exercise threshold is invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "total_seconds": self.total_seconds,
            "max_tool_calls": self.max_tool_calls,
            "synthesis_reserve_seconds": self.synthesis_reserve_seconds,
            "gateway_floor_ratio": self.gateway_floor_ratio,
            "minimum_tool_calls_to_exercise": (
                self.minimum_tool_calls_to_exercise
            ),
        }


HEADLESS_BUDGET_PROFILES = {
    "a_control": HeadlessBenchmarkBudgetProfile(
        "a_control", 90.0, 6, 30.0, 0.65
    ),
    "b_floor_ablation": HeadlessBenchmarkBudgetProfile(
        "b_floor_ablation", 90.0, 6, 30.0, 0.0
    ),
    "c_long_capped": HeadlessBenchmarkBudgetProfile(
        "c_long_capped", 180.0, 6, 30.0, 0.0
    ),
    "d_long_expanded": HeadlessBenchmarkBudgetProfile(
        "d_long_expanded", 180.0, 12, 30.0, 0.0, 7
    ),
}

_SEALED_CEILING_CASE_IDS = (
    "rebound-duration",
    "ruihuatai-valuation",
    "weekly-market-cause",
    "current-mainline",
    "unfamiliar-methodology",
)


@dataclass(frozen=True)
class SealedCeilingFixture:
    pointer_path: Path
    component_root: Path
    manifest_sha256: str
    input_sha256: str
    as_of: str
    question_file_sha256: str
    instruction_root: Path
    instruction_manifest_sha256: str
    finance_db: Path
    finance_db_sha256: str
    wiki_root: Path
    wiki_manifest_sha256: str
    hybrid_index_root: Path
    hybrid_manifest_sha256: str
    hybrid_code_root: Path
    hybrid_python: Path

    def provenance(self) -> dict[str, object]:
        return {
            "pointer_sha256": _sha256_file(self.pointer_path),
            "manifest_sha256": self.manifest_sha256,
            "input_sha256": self.input_sha256,
            "as_of": self.as_of,
            "question_file_sha256": self.question_file_sha256,
            "instruction_manifest_sha256": self.instruction_manifest_sha256,
            "finance_db_sha256": self.finance_db_sha256,
            "wiki_manifest_sha256": self.wiki_manifest_sha256,
            "hybrid_manifest_sha256": self.hybrid_manifest_sha256,
            "no_live_root": True,
        }


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_regular_json(path: Path, *, label: str) -> dict[str, object]:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"{label} must be a regular non-symlink file")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _self_hash(value: dict[str, object], field: str) -> str:
    payload = dict(value)
    payload.pop(field, None)
    return _artifact_hash(payload)


def _fixture_path(root: Path, relative: object, *, label: str) -> Path:
    text = str(relative or "").strip()
    candidate = Path(text)
    if not text or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"invalid sealed fixture {label} path")
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"sealed fixture {label} escapes component root")
    return resolved


def _audit_sealed_fixture_files(
    root: Path,
    expected: object,
) -> None:
    if not isinstance(expected, list):
        raise ValueError("sealed fixture file manifest is invalid")
    actual_entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("sealed fixture contains a symlink")
        if stat.S_ISDIR(metadata.st_mode):
            if stat.S_IMODE(metadata.st_mode) != 0o555:
                raise ValueError("sealed fixture directory is writable")
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("sealed fixture contains unsupported filesystem entry")
        relative = path.relative_to(root).as_posix()
        if relative == "fixture.manifest.json":
            continue
        actual_entries.append(
            {
                "path": relative,
                "mode": stat.S_IMODE(metadata.st_mode),
                "bytes": metadata.st_size,
                "sha256": _sha256_file(path),
            }
        )
    if actual_entries != expected:
        raise ValueError("sealed fixture file manifest mismatch")


def _component_mapping(
    components: object,
    name: str,
) -> dict[str, object]:
    value = components.get(name) if isinstance(components, dict) else None
    if not isinstance(value, dict):
        raise ValueError(f"sealed fixture component {name} is invalid")
    return value


def _load_sealed_fixture(
    pointer_path: Path,
    *,
    question_file: Path,
) -> SealedCeilingFixture:
    raw_pointer_path = pointer_path.expanduser().absolute()
    pointer = _read_regular_json(raw_pointer_path, label="fixture pointer")
    if pointer.get("pointer_sha256") != _self_hash(pointer, "pointer_sha256"):
        raise ValueError("sealed fixture pointer self hash mismatch")
    relative_component = str(pointer.get("relative_component") or "").strip()
    if Path(relative_component).name != relative_component:
        raise ValueError("sealed fixture pointer component is invalid")
    component_path = raw_pointer_path.parent / relative_component
    component_metadata = component_path.lstat()
    if stat.S_ISLNK(component_metadata.st_mode):
        raise ValueError("sealed fixture component root must not be a symlink")
    component_root = component_path.resolve()
    if not component_root.is_dir() or component_root.parent != raw_pointer_path.parent.resolve():
        raise ValueError("sealed fixture component root is unavailable")
    root_metadata = component_root.lstat()
    if stat.S_ISLNK(root_metadata.st_mode) or stat.S_IMODE(root_metadata.st_mode) != 0o555:
        raise ValueError("sealed fixture component root must be immutable")
    manifest_path = component_root / "fixture.manifest.json"
    manifest = _read_regular_json(manifest_path, label="fixture manifest")
    if manifest.get("status") != "sealed":
        raise ValueError("ceiling fixture is not sealed")
    manifest_sha256 = str(manifest.get("manifest_sha256") or "")
    if manifest_sha256 != _self_hash(manifest, "manifest_sha256"):
        raise ValueError("sealed fixture manifest self hash mismatch")
    if pointer.get("manifest_sha256") != manifest_sha256:
        raise ValueError("sealed fixture pointer manifest hash mismatch")
    _audit_sealed_fixture_files(component_root, manifest.get("files"))

    fixture_input = manifest.get("input")
    if not isinstance(fixture_input, dict):
        raise ValueError("sealed fixture input is invalid")
    input_sha256 = str(manifest.get("input_sha256") or "")
    if input_sha256 != _artifact_hash(fixture_input):
        raise ValueError("sealed fixture input hash mismatch")
    question_hash = str(fixture_input.get("question_file_sha256") or "")
    if question_hash != _sha256_file(question_file.expanduser().resolve()):
        raise ValueError("sealed fixture question file hash mismatch")
    components = manifest.get("components")
    instruction = _component_mapping(components, "instruction")
    finance = _component_mapping(components, "finance")
    wiki = _component_mapping(components, "wiki")
    hybrid = _component_mapping(components, "hybrid")
    instruction_component = _fixture_path(
        component_root,
        instruction.get("component_root"),
        label="instruction",
    )
    instruction_root = instruction_component / "instruction"
    finance_db = _fixture_path(
        component_root,
        finance.get("target"),
        label="finance",
    )
    wiki_root = _fixture_path(component_root, wiki.get("root"), label="wiki")
    hybrid_index = _fixture_path(
        component_root,
        hybrid.get("index_root"),
        label="hybrid index",
    )
    hybrid_code = _fixture_path(
        component_root,
        hybrid.get("code_runtime"),
        label="hybrid code",
    )
    required_directories = (instruction_root, wiki_root, hybrid_index, hybrid_code)
    if any(not item.is_dir() for item in required_directories) or not finance_db.is_file():
        raise ValueError("sealed fixture component path is unavailable")
    finance_sha256 = str(finance.get("sha256") or "")
    if finance_sha256 != _sha256_file(finance_db):
        raise ValueError("sealed fixture finance hash mismatch")
    hybrid_python = Path(str(hybrid.get("python_executable") or "")).expanduser()
    if not hybrid_python.exists():
        raise ValueError("sealed fixture Hybrid Python is unavailable")
    return SealedCeilingFixture(
        pointer_path=raw_pointer_path.resolve(),
        component_root=component_root,
        manifest_sha256=manifest_sha256,
        input_sha256=input_sha256,
        as_of=str(fixture_input.get("as_of") or ""),
        question_file_sha256=question_hash,
        instruction_root=instruction_root,
        instruction_manifest_sha256=str(instruction.get("manifest_sha256") or ""),
        finance_db=finance_db,
        finance_db_sha256=finance_sha256,
        wiki_root=wiki_root,
        wiki_manifest_sha256=str(wiki.get("manifest_sha256") or ""),
        hybrid_index_root=hybrid_index,
        hybrid_manifest_sha256=str(hybrid.get("manifest_sha256") or ""),
        hybrid_code_root=hybrid_code,
        hybrid_python=hybrid_python.resolve(),
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
    backend: str,
    latest_data_date: str,
    headless_budget_profile: HeadlessBenchmarkBudgetProfile | None = None,
):
    if not control.contract_required:
        return None
    if headless_budget_profile is not None and backend != "codex_headless":
        raise ValueError("headless budget profiles require codex_headless")
    if backend == "continuous_glm":
        synthesis_reserve = GLMAgentRuntime.synthesis_reserve_for_task(
            tier=case.tier,
            question_type=control.task_frame.question_type,
        )
    else:
        # SDK and headless runtimes research and draft in one continuous
        # episode.  They need only the backend-neutral semantic-verifier
        # reserve; GLM's separate internal-finalizer reserve would be charged
        # a second time and collapse a standard research ledger to 30 seconds.
        policy_reserve = ResearchPolicy.for_tier(case.tier).synthesis_reserve
        synthesis_reserve = min(
            ResearchPolicy.for_tier(case.tier).total_seconds * 0.4,
            max(policy_reserve, 30.0),
        )
    context = build_episode_context(
        control.task_frame,
        task_id=f"runtime-benchmark:{case.case_id}",
        capabilities=control.capabilities,
        tier=case.tier,
        timeout=case.timeout,
        synthesis_reserve=synthesis_reserve,
        today=case.as_of,
        latest_data_date=latest_data_date,
    )
    if headless_budget_profile is None:
        return context
    profile = headless_budget_profile
    policy = ResearchPolicy(
        context.policy.tier,
        profile.max_tool_calls,
        profile.total_seconds,
        profile.synthesis_reserve_seconds,
    )
    return replace(
        context,
        deadline=ResearchDeadline.from_timeout(
            profile.total_seconds,
            synthesis_reserve=profile.synthesis_reserve_seconds,
        ),
        policy=policy,
        root_budget=InMemoryRootBudgetLedger(
            episode_id=context.contract.task_id,
            initial_calls=profile.max_tool_calls,
            hard_calls_cap=profile.max_tool_calls,
            initial_seconds=(
                profile.total_seconds - profile.synthesis_reserve_seconds
            ),
            hard_seconds_cap=profile.total_seconds,
        ),
    )


def _build_runtime(
    backend: str,
    case: RuntimeBenchmarkCase,
    context: object,
    *,
    runtime_providers: tuple[LLMProvider, ...] = (),
    headless_budget_profile: HeadlessBenchmarkBudgetProfile | None = None,
    sealed_fixture: SealedCeilingFixture | None = None,
) -> tuple[object, str]:
    del context
    providers = runtime_providers or llm_refine.detect_providers()
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
            (item for item in providers if item.name == "openai"),
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
            model=(
                "gpt-5.6-sol"
                if sealed_fixture is not None
                else os.environ.get("CODEX_HEADLESS_MODEL")
            ),
            reasoning_effort=(
                "medium"
                if sealed_fixture is not None
                else ("high" if case.tier == "deep" else "medium")
            ),
            finalization_floor_ratio=(
                headless_budget_profile.gateway_floor_ratio
                if headless_budget_profile is not None
                else 0.65
            ),
            sealed_fixture=sealed_fixture is not None,
            instruction_root=(
                sealed_fixture.instruction_root
                if sealed_fixture is not None
                else None
            ),
            transport=("subprocess" if sealed_fixture is not None else None),
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


class _SemanticVerifierCapture:
    """Observe the product verifier result without making gate decisions."""

    def __init__(self, delegate: object) -> None:
        self._delegate = delegate
        self.latest: SemanticEpisodeOutcome | None = None

    @property
    def provider_attempts(self) -> int:
        return int(getattr(self._delegate, "provider_attempts", 0) or 0)

    def verify(self, **kwargs: object) -> SemanticEpisodeOutcome:
        verify = getattr(self._delegate, "verify", None)
        if not callable(verify):
            raise TypeError("semantic verifier must provide verify(...)")
        result = verify(**kwargs)
        if not isinstance(result, SemanticEpisodeOutcome):
            raise TypeError("semantic verifier must return SemanticEpisodeOutcome")
        self.latest = result
        return result


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
    fixture_policy: SealedFixturePolicy | None = None,
):
    return build_episode_registry(
        frame,
        context,
        finance_root=finance_root,
        knowledge_wiki=knowledge_wiki,
        fixture_policy=fixture_policy,
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


def _runtime_sources(
    outcome: object,
    *,
    excluded_output_ids: tuple[str, ...],
) -> tuple[RuntimeSource, ...]:
    excluded = set(excluded_output_ids)
    bound_hashes = {
        content_hash
        for binding in outcome.bindings
        if not binding.gap and binding.output_id not in excluded
        for content_hash in binding.evidence_hashes
    }
    selected = sorted(
        (
            item
            for item in outcome.evidence
            if item.content_hash in bound_hashes
        ),
        key=lambda item: (
            item.content_hash,
            item.tool,
            item.source_date or "",
        ),
    )
    return tuple(
        RuntimeSource(
            source_id=f"E{index}",
            tool=item.tool,
            content_hash=item.content_hash,
            source_date=item.source_date or "",
        )
        for index, item in enumerate(selected, start=1)
    )


def _runtime_claims(
    published_answer: str,
    *,
    sources: tuple[RuntimeSource, ...],
    evidence: object,
) -> tuple[RuntimeClaim, ...]:
    evidence_by_hash = {
        str(getattr(item, "content_hash", "") or ""): item
        for item in evidence
        if str(getattr(item, "content_hash", "") or "")
    } if isinstance(evidence, (tuple, list)) else {}
    source_tokens: dict[str, frozenset[str]] = {}
    for source in sources:
        item = evidence_by_hash.get(source.content_hash)
        if item is None:
            continue
        searchable = " ".join(
            str(getattr(item, field, "") or "")
            for field in ("title", "detail", "source")
        )
        source_tokens[source.source_id] = frozenset(
            _material_numeric_tokens(searchable)
        )
    claims: list[RuntimeClaim] = []
    for match in re.finditer(r"[^。！？!?；;\n]+(?:[。！？!?；;]+|(?=\n)|$)", published_answer):
        start, end = match.span()
        while start < end and published_answer[start].isspace():
            start += 1
        while end > start and published_answer[end - 1].isspace():
            end -= 1
        if start >= end:
            continue
        text = published_answer[start:end]
        numeric_tokens = _material_numeric_tokens(text)
        claim_source_ids = tuple(
            source.source_id
            for source in sources
            if numeric_tokens
            and set(numeric_tokens).issubset(
                source_tokens.get(source.source_id, frozenset())
            )
        )
        claims.append(
            RuntimeClaim(
                claim_id=f"C{len(claims) + 1}",
                start=start,
                end=end,
                text=text,
                material_numeric=bool(numeric_tokens),
                source_ids=claim_source_ids,
            )
        )
    return tuple(claims)


_MATERIAL_NUMERIC_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}"
    r"|[-+]?\d+(?:[.,]\d+)*(?:%|倍|亿|万|点|日|天|年|月)?"
    r")"
)


def _material_numeric_tokens(text: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            match.group(0).replace(",", "").replace("/", "-").lstrip("+")
            for match in _MATERIAL_NUMERIC_TOKEN_RE.finditer(str(text or ""))
        )
    )


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
    runtime_providers: tuple[LLMProvider, ...] = (),
    headless_budget_profile: HeadlessBenchmarkBudgetProfile | None = None,
    sealed_fixture: SealedCeilingFixture | None = None,
    fixture_policy: SealedFixturePolicy | None = None,
) -> RuntimeArmResult:
    started = time.monotonic()
    model = "unavailable"
    execution_case = (
        replace(case, timeout=headless_budget_profile.total_seconds)
        if headless_budget_profile is not None
        else case
    )
    try:
        context = _fresh_context(
            execution_case,
            control,
            backend=backend,
            latest_data_date=latest_data_date,
            headless_budget_profile=headless_budget_profile,
        )
        if context is None:
            raise RuntimeError("research_contract_missing")
        runtime, model = _build_runtime(
            backend,
            execution_case,
            context,
            runtime_providers=runtime_providers,
            headless_budget_profile=headless_budget_profile,
            sealed_fixture=sealed_fixture,
        )
        registry = _build_registry(
            control.task_frame,
            context,
            finance_root=finance_root,
            knowledge_wiki=knowledge_wiki,
            fixture_policy=fixture_policy,
        )
        semantic_providers = runtime_providers
        runtime_semantic_providers = getattr(
            runtime,
            "semantic_providers",
            None,
        )
        if not semantic_providers and callable(runtime_semantic_providers):
            semantic_providers = tuple(runtime_semantic_providers())
        semantic_delegate = _build_semantic_verifier(
            execution_case,
            context,
            providers=semantic_providers,
        )
        semantic_verifier = _SemanticVerifierCapture(semantic_delegate)
        adapter = ContinuousTurnAdapter(
            runtime=runtime,
            semantic_verifier=semantic_verifier,
            runtime_name=backend,
            mode="on",
            context_factory=lambda *_args, **_kwargs: context,
            registry_factory=lambda *_args, **_kwargs: registry,
            task_id_factory=lambda: context.contract.task_id,
            timeout=execution_case.timeout,
            verification_reserve=context.deadline.synthesis_reserve,
            tier=execution_case.tier,
            today=execution_case.as_of,
            latest_data_date=latest_data_date,
        )
        with llm_refine.call_ledger_scope() as ledger:
            turn_result = adapter.handle(
                frame=control.task_frame,
                control=control,
            )
            ledger_calls = _ledger_call_count(ledger)
        semantic = semantic_verifier.latest
        if semantic is None:
            raise RuntimeError("production adapter did not reach semantic verification")
        final_verified = semantic.verified
        final_outcome = final_verified.outcome
        if final_outcome.stop_reason in _INFRASTRUCTURE_STOP_REASONS:
            raise RuntimeBenchmarkInfrastructureError(
                case_id=case.case_id,
                backend=backend,
                reason=final_outcome.stop_reason,
            )
        input_tokens, output_tokens = _runtime_tokens(final_outcome.events)
        semantic_attempts = semantic_verifier.provider_attempts
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
        published_answer = turn_result.answer
        sources = _runtime_sources(
            final_outcome,
            excluded_output_ids=semantic.gap_output_ids,
        )
        claims = _runtime_claims(
            published_answer,
            sources=sources,
            evidence=final_outcome.evidence,
        )
        return RuntimeArmResult(
            case_id=case.case_id,
            backend=backend,
            model=model,
            answer=published_answer,
            candidate_answer=final_outcome.draft,
            published_answer=published_answer,
            claims=claims,
            sources=sources,
            status=turn_result.status,
            structural_status=final_verified.verified_status,
            semantic_status=semantic.judge_status,
            task_alignment_score=_task_alignment_score(
                control.task_frame,
                published_answer,
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
                execution_case.timeout,
                context.policy.total_seconds,
            ),
            citations=turn_result.citations,
            data_cutoff=turn_result.as_of,
            diagnostics=diagnostics,
        )
    except RuntimeBenchmarkInfrastructureError:
        raise
    except Exception as exc:
        return _arm_failure(
            case=execution_case,
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
    runtime_providers: tuple[LLMProvider, ...] = (),
    headless_budget_profile: HeadlessBenchmarkBudgetProfile | None = None,
    sealed_fixture: SealedCeilingFixture | None = None,
    fixture_policy: SealedFixturePolicy | None = None,
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
                runtime_providers=runtime_providers,
                headless_budget_profile=headless_budget_profile,
                sealed_fixture=sealed_fixture,
                fixture_policy=fixture_policy,
            )
            for backend in backends
        )
    else:
        arms = _run_non_research_arms(case, control, backends)
    record_case = (
        replace(case, timeout=headless_budget_profile.total_seconds)
        if headless_budget_profile is not None
        else case
    )
    record = _planned_case(record_case, control, None)
    record["execution_status"] = "completed"
    record["arms"] = [arm.to_dict() for arm in arms]
    return record, arms


def _sealed_tool_surface_manifest(
    frozen: list[tuple[RuntimeBenchmarkCase, object, object | None]],
    *,
    finance_root: Path,
    knowledge_wiki: Path,
    latest_data_date: str,
    profile: HeadlessBenchmarkBudgetProfile,
    fixture_policy: SealedFixturePolicy,
) -> dict[str, object]:
    cases: list[dict[str, object]] = []
    for case, control, dry_context in frozen:
        context = dry_context
        if context is None:
            context = _fresh_context(
                case,
                control,
                backend="codex_headless",
                latest_data_date=latest_data_date,
                headless_budget_profile=profile,
            )
        if context is None:
            names: tuple[str, ...] = ()
        else:
            registry = _build_registry(
                control.task_frame,
                context,
                finance_root=finance_root,
                knowledge_wiki=knowledge_wiki,
                fixture_policy=fixture_policy,
            )
            names = tuple(
                spec.name
                for spec in registry.authorized_specs(
                    context.contract.allowed_capabilities
                )
            )
        cases.append({"case_id": case.case_id, "authorized_tools": list(names)})
    payload: dict[str, object] = {"schema_version": 1, "cases": cases}
    payload["tool_surface_sha256"] = _artifact_hash(payload)
    return payload


def _bind_blind_projection_hashes(records: list[dict[str, object]]) -> None:
    for case_index, record in enumerate(records):
        arms = record.get("arms")
        if not isinstance(arms, list):
            continue
        for arm_index, arm in enumerate(arms):
            if not isinstance(arm, dict):
                raise ValueError("runtime arm projection must be an object")
            projection = {
                "published_answer": arm.get("published_answer"),
                "claims": arm.get("claims"),
                "sources": arm.get("sources"),
            }
            arm["blind_projection"] = projection
            arm["blind_projection_sha256"] = _artifact_hash(projection)
            arm["blind_projection_json_pointer"] = (
                f"/cases/{case_index}/arms/{arm_index}/blind_projection"
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the frozen finance benchmark across AgentRuntime backends"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backend", action="append", required=True)
    parser.add_argument(
        "--headless-budget-profile",
        choices=tuple(HEADLESS_BUDGET_PROFILES),
        help="Apply one preregistered benchmark-only Codex headless budget",
    )
    parser.add_argument(
        "--case",
        action="append",
        help="Run only the named frozen case; repeat to select multiple cases",
    )
    parser.add_argument("--questions-file", type=Path, required=True)
    parser.add_argument("--finance-root", type=Path)
    parser.add_argument("--knowledge-wiki", type=Path)
    parser.add_argument(
        "--ceiling-fixture-receipt",
        type=Path,
        help="Hash-bound sealed physical fixture pointer for the five-case profile-D control",
    )
    parser.add_argument(
        "--keychain-user",
        help="Load the runtime provider from macOS Keychain without exporting a key",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        source_revision, source_dirty = _source_provenance()
        cases = _load_cases(args.questions_file)
        sealed_fixture = (
            _load_sealed_fixture(
                args.ceiling_fixture_receipt,
                question_file=args.questions_file,
            )
            if args.ceiling_fixture_receipt is not None
            else None
        )
        backends = tuple(
            resolve_runtime_backend(value).name for value in args.backend
        )
        if len(set(backends)) != len(backends):
            raise ValueError("backend names must be unique")
        headless_budget_profile = (
            HEADLESS_BUDGET_PROFILES[args.headless_budget_profile]
            if args.headless_budget_profile
            else None
        )
        if (
            headless_budget_profile is not None
            and backends != ("codex_headless",)
        ):
            raise ValueError(
                "headless budget profiles require only the codex_headless backend"
            )
        if args.case:
            selected_ids = tuple(dict.fromkeys(str(item) for item in args.case))
            known_ids = {case.case_id for case in cases}
            unknown_ids = tuple(
                case_id for case_id in selected_ids if case_id not in known_ids
            )
            if unknown_ids:
                raise ValueError(
                    "unknown benchmark case selection: " + ",".join(unknown_ids)
                )
            selected_set = set(selected_ids)
            cases = tuple(
                case for case in cases if case.case_id in selected_set
            )
        fixture_policy: SealedFixturePolicy | None = None
        if sealed_fixture is not None:
            if source_dirty:
                raise ValueError("sealed fixture benchmark requires a clean source tree")
            if backends != ("codex_headless",):
                raise ValueError("sealed fixture benchmark requires codex_headless only")
            if args.headless_budget_profile != "d_long_expanded":
                raise ValueError("sealed fixture benchmark requires profile d_long_expanded")
            if tuple(case.case_id for case in cases) != _SEALED_CEILING_CASE_IDS:
                raise ValueError("sealed fixture benchmark requires exactly the frozen five cases")
            if any(case.as_of != sealed_fixture.as_of for case in cases):
                raise ValueError("sealed fixture case cutoff mismatch")
            if args.finance_root is not None or args.knowledge_wiki is not None:
                raise ValueError("sealed fixture benchmark forbids live data root arguments")
            finance_root = sealed_fixture.component_root
            knowledge_wiki = sealed_fixture.wiki_root
            fixture_policy = SealedFixturePolicy(
                market_db_path=sealed_fixture.finance_db,
                knowledge_index_dir=sealed_fixture.hybrid_index_root,
                knowledge_code_root=sealed_fixture.hybrid_code_root,
                knowledge_python=sealed_fixture.hybrid_python,
            )
        else:
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
        runtime_providers: tuple[LLMProvider, ...] = ()
        if not args.dry_run:
            if finance_root is None or knowledge_wiki is None:
                raise ValueError(
                    "live benchmark requires --finance-root and --knowledge-wiki"
                )
            if not finance_root.is_dir() or not knowledge_wiki.is_dir():
                raise ValueError("benchmark data roots must be existing directories")
            market_data_date = (
                latest_market_date(
                    finance_root,
                    market_db_path=sealed_fixture.finance_db,
                )
                if sealed_fixture is not None
                else latest_market_date(finance_root)
            )
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
                runtime_providers = (saved_provider,)
        frozen = [
            (case, *_freeze_case(case, dry_run=args.dry_run)) for case in cases
        ]
        sealed_tool_surface = (
            _sealed_tool_surface_manifest(
                frozen,
                finance_root=finance_root,
                knowledge_wiki=knowledge_wiki,
                latest_data_date=sealed_fixture.as_of,
                profile=headless_budget_profile,
                fixture_policy=fixture_policy,
            )
            if sealed_fixture is not None
            and headless_budget_profile is not None
            and fixture_policy is not None
            else None
        )
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
                        runtime_providers=runtime_providers,
                        headless_budget_profile=headless_budget_profile,
                        sealed_fixture=sealed_fixture,
                        fixture_policy=fixture_policy,
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

    if not args.dry_run:
        _bind_blind_projection_hashes(records)

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
            "keychain" if runtime_providers else "environment"
        ),
        "headless_budget_profile": (
            headless_budget_profile.to_dict()
            if headless_budget_profile is not None
            else None
        ),
        "budget_ablation_validity": (
            "not_executed"
            if args.dry_run and headless_budget_profile is not None
            else None
        ),
        "cases": records,
    }
    if sealed_fixture is not None:
        from intelligence.services.codex_headless_runtime import (
            sealed_environment_policy_payload,
        )

        artifact["ceiling_fixture"] = {
            **sealed_fixture.provenance(),
            "tool_surface": sealed_tool_surface,
            "environment_policy_sha256": _artifact_hash(
                sealed_environment_policy_payload()
            ),
            "transport": "subprocess_mailbox",
            "model": "gpt-5.6-sol",
            "reasoning_effort": "medium",
        }
    if not args.dry_run and headless_budget_profile is not None:
        observed_calls = max(
            (arm.tool_calls for arm in arm_results),
            default=0,
        )
        required_calls = headless_budget_profile.minimum_tool_calls_to_exercise
        artifact["budget_ablation_validity"] = (
            "invalid_not_physically_exercised"
            if required_calls and observed_calls < required_calls
            else "exercised"
        )
        artifact["budget_ablation_observation"] = {
            "max_observed_tool_calls": observed_calls,
            "minimum_tool_calls_to_exercise": required_calls,
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
