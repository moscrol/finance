#!/usr/bin/env python3
"""Run one market question through an incrementally assembled Episode.

The ladder is an ablation harness, not a quality benchmark.  Every stage keeps
the same routing, task frame, contract outputs, registry and verifiers; the one
business variable is the *capability surface* handed to the Episode.  When a
stage breaks, the component admitted at that stage is the suspect.

Stage floors are not assigned by taste.  ``ResearchTaskContract.__post_init__``
requires the evidence plan's mandatory capabilities to be a subset of
``allowed_capabilities`` and raises otherwise, so a stage below a case's floor
cannot even *construct* its contract.  Running it would record a designed
failure instead of an observed seam defect.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.runtime.turn_control_core import TurnControlCore
from intelligence.services.agent_research import (
    AgentEvidence,
    evidence_content_hash,
)
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_semantic_verifier import SemanticEpisodeOutcome
from intelligence.services.episode_tools import build_episode_registry
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    ResearchContractError,
    release_root_budget,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolRunResult,
)
from scripts.smoke_workbench_self_use import _atomic_write_json

_VALID_TIERS = frozenset({"quick", "standard", "deep"})


@dataclass(frozen=True)
class Stage:
    """One rung: the capability surface exposed to the Episode."""

    stage_id: str
    name: str
    capabilities: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.stage_id.strip() or not self.name.strip():
            raise ValueError("stage requires a non-empty id and name")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError(f"stage {self.stage_id} repeats a capability")


STAGES: tuple[Stage, ...] = (
    Stage("S0", "planning", ()),
    Stage("S1", "market-data", ("market_data",)),
    Stage("S2", "mainline-context", ("market_data", "mainline_context")),
    Stage(
        "S3",
        "causal-evidence",
        ("market_data", "mainline_context", "news_search", "evidence_search"),
    ),
)

_STAGE_BY_ID = {stage.stage_id: stage for stage in STAGES}
_STAGE_ORDER = {stage.stage_id: index for index, stage in enumerate(STAGES)}


def resolve_stage(stage_id: str) -> Stage:
    stage = _STAGE_BY_ID.get(str(stage_id).strip())
    if stage is None:
        raise ValueError(f"unknown stage: {stage_id}")
    return stage


@dataclass(frozen=True)
class SeamLadderCase:
    """One frozen market question plus the lowest stage that can run it."""

    case_id: str
    question: str
    as_of: str
    tier: str
    timeout: float
    expected_stage_floor: str
    conversation_context: tuple[dict[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.question.strip():
            raise ValueError("ladder cases require a non-empty id and question")
        if self.tier not in _VALID_TIERS:
            raise ValueError(f"case {self.case_id} has an unknown tier: {self.tier}")
        if self.timeout <= 0:
            raise ValueError(f"case {self.case_id} needs a positive timeout")
        floor = resolve_stage(self.expected_stage_floor)
        # S0 builds no runtime and calls no tool, so it can never satisfy a
        # research contract; a case floored there would never run at all.
        if not floor.capabilities:
            raise ValueError(
                f"case {self.case_id} cannot floor at {floor.stage_id}: "
                "that stage exposes no capability"
            )


def load_cases(path: str | Path) -> tuple[SeamLadderCase, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("ladder fixture must contain a non-empty cases list")
    cases: list[SeamLadderCase] = []
    seen: set[str] = set()
    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise ValueError("each ladder case must be an object")
        case_id = str(raw.get("id") or "").strip()
        if case_id and case_id in seen:
            raise ValueError(f"duplicate ladder case id: {case_id}")
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
        as_of = str(raw.get("as_of") or "").strip()
        if not as_of:
            raise ValueError(f"case {case_id or '<unnamed>'} requires an as_of date")
        case = SeamLadderCase(
            case_id=case_id,
            question=str(raw.get("question") or "").strip(),
            as_of=as_of,
            tier=str(raw.get("tier") or "standard").strip(),
            timeout=float(raw.get("timeout") or 0.0),
            expected_stage_floor=str(raw.get("expected_stage_floor") or "").strip(),
            conversation_context=tuple(conversation_context),
        )
        seen.add(case.case_id)
        cases.append(case)
    return tuple(cases)


def cases_for_stage(
    cases: tuple[SeamLadderCase, ...],
    stage_id: str,
) -> tuple[SeamLadderCase, ...]:
    """Return the cases whose declared floor is at or below ``stage_id``.

    Higher stages re-run every case already reached, which is what catches a
    newly admitted capability breaking an already-closed loop.
    """

    ceiling = _STAGE_ORDER[resolve_stage(stage_id).stage_id]
    return tuple(
        case
        for case in cases
        if _STAGE_ORDER[case.expected_stage_floor] <= ceiling
    )


def _stage_episode_id(case_id: str, stage_id: str) -> str:
    """Single source of truth for one stage's episode id.

    Registration (``build_episode_context``) and release have to agree
    character for character; when they drift, the release degrades to a silent
    no-op and the next run of the same rung dies on "root budget already
    exists" -- a harness artifact that reads like a runtime defect.
    """

    return f"seam-ladder:{case_id}:{stage_id}"


def narrow_context_to_stage(
    source: object,
    stage: Stage,
) -> tuple[object | None, tuple[str, ...], str, str]:
    """Narrow one production context to a rung's capability surface.

    Returns ``(context, enabled, rejection, detail)``; ``context`` is ``None``
    when this rung cannot legally run the case.

    Why the intersection is taken against the *contract* rather than against
    the stage list alone: ``build_episode_context`` re-appends the evidence
    plan's mandatory capabilities to whatever the caller passed in, so handing
    it a narrow ``capabilities`` tuple does not produce a narrow contract.  The
    only honest way to shrink a rung is to derive the full production contract
    first and then replace its ``allowed_capabilities``.

    ``ResearchTaskContract.__post_init__`` rejects a contract whose evidence
    plan demands a capability the rung does not authorize.  That rejection is
    reported here instead of being allowed to raise, because a stage below a
    case's floor is a *designed* impossibility rather than an observed defect.
    """

    contract = source.contract
    stage_set = set(stage.capabilities)
    enabled = tuple(
        capability
        for capability in contract.allowed_capabilities
        if capability in stage_set
    )
    mandatory = tuple(contract.evidence_plan.mandatory_capabilities)
    unauthorized = tuple(item for item in mandatory if item not in set(enabled))
    if unauthorized:
        return (
            None,
            enabled,
            "mandatory_capability_unauthorized",
            (
                "evidence plan requires "
                + ",".join(unauthorized)
                + f"; stage {stage.stage_id} exposes "
                + (",".join(enabled) or "nothing")
            ),
        )
    if not enabled:
        return (
            None,
            enabled,
            "no_capability_in_common",
            (
                f"stage {stage.stage_id} shares no capability with the "
                "contract's authorization"
            ),
        )
    try:
        stage_contract = replace(contract, allowed_capabilities=enabled)
    except ResearchContractError as exc:
        # Defence in depth: the invariant is the authority on legality, so a
        # rung it rejects must be reported, never silently weakened.
        return (
            None,
            enabled,
            "mandatory_capability_unauthorized",
            str(exc),
        )
    return replace(source, contract=stage_contract), enabled, "", ""


def resolve_control(case: SeamLadderCase):
    """Run production routing for one case.

    ``TurnControlCore`` takes an injected ``llm_complete``; the ladder passes a
    stub so routing stays offline and deterministic.  Routing is a *fixed*
    variable here, so it is resolved once and reused across every rung.
    """

    core = TurnControlCore()
    previous_control = None
    previous_turn_id: str | None = None
    transcript: list[str] = []
    for index, item in enumerate(case.conversation_context, start=1):
        if item["role"] == "user":
            previous_turn_id = f"seam-ladder:{case.case_id}:context:{index}"
            previous_control = core.control(
                item["content"],
                context="\n".join(transcript),
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
                llm_complete=_STUB_LLM_COMPLETE,
            )
        transcript.append(f"{item['role']}: {item['content']}")
    return core.control(
        case.question,
        context="\n".join(transcript),
        previous_frame=(
            previous_control.task_frame if previous_control is not None else None
        ),
        previous_intent=(
            previous_control.turn_intent if previous_control is not None else None
        ),
        previous_turn_id=previous_turn_id,
        llm_complete=_STUB_LLM_COMPLETE,
    )


def _STUB_LLM_COMPLETE(*_args: object, **_kwargs: object):  # noqa: N802
    """Routing must not call a model; return the "no LLM opinion" shape."""

    return (None, None, "seam-ladder-offline")


@dataclass(frozen=True)
class StageDerivation:
    """What one rung actually got, or why it got nothing."""

    stage: Stage
    case: SeamLadderCase
    enabled_capabilities: tuple[str, ...] = ()
    context: object | None = None
    registry: ResearchToolRegistry | None = None
    rejection: str = ""
    rejection_detail: str = ""


@contextmanager
def stage_derivation(
    case: SeamLadderCase,
    control: object,
    stage_id: str,
) -> Iterator[StageDerivation]:
    """Derive one rung's contract and registry, then release its budget.

    Each rung builds its *own* production context.  ``ResearchDeadline`` is an
    absolute monotonic instant and the root budget is a live-registered ledger,
    so sharing one context across rungs would let an early stage's tool calls
    drain a later one -- a failure at S3 could then come from spent budget
    rather than from the component S3 admitted.

    The capability surface is narrowed on the *contract*, not only on the tool
    schema: filtering schemas alone would leave the contract authorizing more
    than the rung exposes, which is an unreal privilege path rather than a
    smaller assembly.
    """

    stage = resolve_stage(stage_id)
    if not stage.capabilities:
        # S0 constructs no runtime and calls no tool, so it can never satisfy a
        # research contract.  Freezing routing is the whole point of this rung.
        yield StageDerivation(
            stage=stage,
            case=case,
            rejection="planning_only",
            rejection_detail="planning stage exposes no capability",
        )
        return
    if not control.contract_required:
        yield StageDerivation(
            stage=stage,
            case=case,
            rejection="no_contract_required",
            rejection_detail="routing resolved this turn without a contract",
        )
        return

    episode_id = _stage_episode_id(case.case_id, stage.stage_id)
    source = build_episode_context(
        control.task_frame,
        task_id=episode_id,
        capabilities=control.capabilities,
        tier=case.tier,
        timeout=case.timeout,
        today=case.as_of,
        latest_data_date=case.as_of,
        conversation_context="\n".join(
            f"{item['role']}: {item['content']}"
            for item in case.conversation_context
        ),
    )
    try:
        stage_context, enabled, rejection, detail = narrow_context_to_stage(
            source,
            stage,
        )
        if stage_context is None:
            yield StageDerivation(
                stage=stage,
                case=case,
                enabled_capabilities=enabled,
                rejection=rejection,
                rejection_detail=detail,
            )
            return
        full_registry = build_episode_registry(control.task_frame, stage_context)
        yield StageDerivation(
            stage=stage,
            case=case,
            enabled_capabilities=enabled,
            context=stage_context,
            registry=ResearchToolRegistry(
                full_registry.authorized_specs(enabled)
            ),
        )
    finally:
        # Own the release: the registry is a WeakValueDictionary, so an episode
        # that ends by raising keeps its ledger reachable through the traceback
        # and the next run of this rung fails against a dead registration.
        release_root_budget(episode_id)


# --- offline execution ------------------------------------------------------
#
# Offline mode fixes only the *outermost* inputs: the model and the tools' data
# source.  Everything the ladder claims to test stays production -- the Episode
# loop, ``ResearchToolRegistry.execute`` (authorization, argument validation,
# cutoff filtering, evidence hashing), the structural verifier and the adapter.

OFFLINE_PROVIDER = "scripted"
_FIXTURE_QUERY = "以固定收盘日为准的盘面结构"


def fixture_tool_runner(tool_name: str, as_of: str):
    """Return a deterministic local data source for one tool.

    Only the tool's outbound call is replaced.  ``registry.execute`` remains the
    production one, so a stage that exposes an unauthorized tool, sends invalid
    arguments or binds an unknown hash still fails exactly as it would live.
    """

    def run(value: object, _context: object) -> ToolRunResult:
        query = (
            value
            if isinstance(value, str)
            else str((value or {}).get("query", ""))  # type: ignore[union-attr]
        ) or _FIXTURE_QUERY
        item = AgentEvidence(
            tool=tool_name,
            title=f"{tool_name} 固定观察",
            detail=f"{query} 的封闭样本：上涨家数抬升，成交维持活跃。",
            source="seam-ladder 固定样本",
            source_date=as_of,
            evidence_tier="L4_structured",
        )
        item = replace(item, content_hash=evidence_content_hash(item))
        return ToolRunResult(
            evidence=(item,),
            observation=f"{tool_name} 原始观察",
            trace=ProviderTrace(
                provider="seam-ladder:fixture",
                capability=tool_name,
                status="ok",
                source_trade_date=as_of,
                result_count=1,
            ),
        )

    return run


def stage_registry_with_fixture_runners(
    registry: ResearchToolRegistry,
    as_of: str,
) -> ResearchToolRegistry:
    """Swap each authorized tool's data source, keeping its spec and schema."""

    return ResearchToolRegistry(
        tuple(
            replace(spec, runner=fixture_tool_runner(spec.name, as_of))
            for spec in registry.authorized_specs()
        )
    )


def _arguments_for_schema(schema: object) -> dict[str, object]:
    """Build arguments that satisfy one tool's own parameter schema.

    This is not a detail.  ``market_data`` declares ``query_scope="episode"``
    and therefore an *empty* closed schema: one turn-scoped snapshot whose
    evidence surface cannot be changed by rewording a query.  Sending it a
    ``query`` is rejected as ``invalid_arguments``, which then cascades into
    "output binding must contain evidence or a gap" and reads like a binding
    defect.  Query-scoped tools (``news_search``, ``evidence_search``) do
    require one.
    """

    properties = (
        schema.get("properties") if isinstance(schema, Mapping) else None
    )
    if isinstance(properties, Mapping) and "query" in properties:
        return {"query": _FIXTURE_QUERY}
    return {}


class ScriptedEpisodeModel:
    """Drive the real Episode loop: one authorized tool batch, then FINAL_JSON.

    Deliberately *not* a pre-built ``AgentOutcome``: the point of the offline
    rung is to cross the real seams (tool schema, authorization, arguments,
    evidence hashing, binding validation), which a canned outcome would skip.
    """

    def __init__(self, contract: object) -> None:
        self._contract = contract
        self._asked_for_tools = False
        self.offered_schemas: list[tuple[str, ...]] = []

    def complete(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        timeout: float,
    ):
        del timeout
        offered = tuple(
            str(function.get("name") or "")
            for definition in tools
            if isinstance(definition, Mapping)
            and isinstance(function := definition.get("function"), Mapping)
        )
        self.offered_schemas.append(offered)
        if not self._asked_for_tools and offered:
            self._asked_for_tools = True
            calls = tuple(
                ModelToolCall(
                    call_id=f"seam-ladder-{index}",
                    name=str(function["name"]),
                    arguments=_arguments_for_schema(function.get("parameters")),
                )
                for index, definition in enumerate(tools)
                if isinstance(definition, Mapping)
                and isinstance(function := definition.get("function"), Mapping)
                and function.get("name")
            )
            if calls:
                return ModelTurn("", calls, OFFLINE_PROVIDER, "")
        return ModelTurn(
            _final_json(self._contract, _observed_hashes(messages)),
            (),
            OFFLINE_PROVIDER,
            "",
        )


def _observed_hashes(messages: list[dict[str, object]]) -> tuple[str, ...]:
    """Collect evidence hashes the episode actually put in front of the model.

    Read back from the tool messages rather than from the fixture, so a hash the
    loop never surfaced can never be bound.
    """

    hashes: list[str] = []
    for message in messages:
        if message.get("role") != "tool":
            continue
        try:
            payload = json.loads(str(message.get("content") or ""))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, Mapping):
            continue
        for value in payload.get("evidence_hashes") or ():
            if isinstance(value, str) and value and value not in hashes:
                hashes.append(value)
    return tuple(hashes)


def _final_json(contract: object, hashes: tuple[str, ...]) -> str:
    """Render one FINAL_JSON that respects each slot's own grounding mode.

    ``validate_episode_finish`` compares every binding's ``basis`` against its
    required output's ``grounding_mode`` and raises on a mismatch, so a uniform
    ``evidence`` basis would fail the ``model_reasoning`` slots that
    ``market_cause`` carries (``causal_chain``, ``cause_attribution``).
    """

    payload = {
        "status": "completed",
        "draft": (
            "基准判断：短周期修复延续，但驱动力偏弱。\n"
            "支撑条件在于成交与上涨家数同步维持；一旦两者同时回落，"
            "该基准判断失效。\n"
            "以上结论仅覆盖最新一个交易日的盘面结构，不含盘后消息。"
        ),
        "gaps": [],
        "bindings": [
            {
                "output_id": item.output_id,
                "evidence_hashes": (
                    list(hashes) if item.grounding_mode == "evidence" else []
                ),
                "basis": item.grounding_mode,
                "gap": "",
            }
            for item in contract.required_outputs
            if item.required
        ],
    }
    body = json.dumps(payload, ensure_ascii=False)
    return f"```json\n{body}\n```"


class OfflineSemanticVerifier:
    """Deterministic stand-in that only proves the semantic seam is invoked.

    It derives its answer solely from the structural output and never judges
    grounding, so it must not be read as evidence that the production LLM judge
    works.  Live mode uses ``SemanticEpisodeVerifier`` for that.
    """

    def verify(
        self,
        *,
        frame: object,
        structurally_verified: object,
        deadline: object,
    ):
        del frame, deadline
        return SemanticEpisodeOutcome(
            verified=structurally_verified,
            status=(
                "completed"
                if structurally_verified.verified_status == "completed"
                else "partial"
            ),
            public_answer=structurally_verified.outcome.draft,
            judge_status="passed",
        )


def _classify_failure(exc: BaseException) -> tuple[str, str]:
    """Attribute a runner exception to the component that owns it."""

    if isinstance(exc, ResearchContractError) or isinstance(exc, ValueError):
        return "contract_or_verifier", f"{type(exc).__name__}: {exc}"
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return "provider_or_budget", f"{type(exc).__name__}: {exc}"
    return "tool_or_data", f"{type(exc).__name__}: {exc}"


def run_offline_stage_case(
    case: SeamLadderCase,
    control: object,
    stage_id: str,
) -> dict[str, object]:
    """Run one rung/case through the real Episode loop with fixed inputs."""

    with stage_derivation(case, control, stage_id) as derived:
        record: dict[str, object] = {
            "stage_id": derived.stage.stage_id,
            "stage_name": derived.stage.name,
            "case_id": case.case_id,
            "enabled_capabilities": list(derived.enabled_capabilities),
            "tool_schema_names": [],
            "rejection": derived.rejection,
            "rejection_detail": derived.rejection_detail,
            "failure_class": "",
            "failure_detail": "",
        }
        if derived.context is None:
            return record
        contract = derived.context.contract
        record["task_frame_hash"] = contract.task_frame_hash
        record["question_type"] = contract.question_type
        registry = stage_registry_with_fixture_runners(
            derived.registry,
            case.as_of,
        )
        record["tool_schema_names"] = list(registry.names())
        model = ScriptedEpisodeModel(contract)
        adapter = ContinuousTurnAdapter(
            runtime=GLMAgentRuntime(client=model),
            semantic_verifier=OfflineSemanticVerifier(),
            # Explicit: never let an ambient ASK_CONTINUOUS_RUNTIME decide
            # whether this rung ran the episode or silently declined.
            mode="on",
            context_factory=lambda _frame, **_kwargs: derived.context,
            registry_factory=lambda _frame, _context: registry,
            tier=case.tier,
            timeout=case.timeout,
            today=case.as_of,
            latest_data_date=case.as_of,
        )
        started = time.monotonic()
        try:
            result = adapter.handle(frame=control.task_frame, control=control)
        except Exception as exc:  # noqa: BLE001 — classified, never swallowed
            failure_class, detail = _classify_failure(exc)
            record["failure_class"] = failure_class
            record["failure_detail"] = detail
            record["latency_seconds"] = round(time.monotonic() - started, 3)
            return record
        record["latency_seconds"] = round(time.monotonic() - started, 3)
        artifact = result.private_artifact or {}
        metrics = artifact.get("metrics") or {}
        structural = artifact.get("structural_verifier") or {}
        outcome = artifact.get("outcome") or {}
        record.update(
            {
                "handled": result.handled,
                "status": result.status,
                "execution_kind": artifact.get("execution_kind", ""),
                "answer": result.answer,
                "structural_status": metrics.get("structural_status", ""),
                "semantic_status": metrics.get("semantic_status", ""),
                "tool_calls": metrics.get("tool_calls", 0),
                "llm_calls": len(model.offered_schemas),
                "provider_attempts": metrics.get("provider_attempts", 0),
                "duplicate_queries": metrics.get("duplicate_queries", 0),
                "evidence_hashes": [
                    str(item.get("content_hash") or "")
                    for item in outcome.get("evidence") or ()
                    if isinstance(item, Mapping) and item.get("content_hash")
                ],
                "missing_outputs": list(structural.get("missing_outputs") or ()),
                "structural_issues": list(structural.get("issues") or ()),
                "satisfiability_precheck": artifact.get(
                    "satisfiability_precheck",
                    {},
                ),
                "offered_schemas": [
                    list(item) for item in model.offered_schemas
                ],
                "stop_reason": outcome.get("stop_reason", ""),
            }
        )
        unauthorized = sorted(
            {
                name
                for offered in model.offered_schemas
                for name in offered
                if registry.resolve(name).capability
                not in set(derived.enabled_capabilities)
            }
        )
        if unauthorized:
            # A tool outside the rung reached the model: the ablation's only
            # variable leaked, so the whole rung's reading is void.
            record["failure_class"] = "contract_or_verifier"
            record["failure_detail"] = (
                "unauthorized capability offered: " + ",".join(unauthorized)
            )
        return record


def _fixture_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_revision() -> str:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,
                text=True,
                timeout=5.0,
                check=False,
            ).stdout.strip()
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if not revision:
        return "unknown"
    return f"{revision}-dirty" if dirty else revision


def run_offline_ladder(questions: Path) -> dict[str, object]:
    """Run every rung and return one receipt for the whole ladder."""

    cases = load_cases(questions)
    controls = {case.case_id: resolve_control(case) for case in cases}
    stages: list[dict[str, object]] = []
    for stage in STAGES:
        selected = cases_for_stage(cases, stage.stage_id)
        stages.append(
            {
                "stage_id": stage.stage_id,
                "stage_name": stage.name,
                "stage_capabilities": list(stage.capabilities),
                "results": [
                    run_offline_stage_case(
                        case,
                        controls[case.case_id],
                        stage.stage_id,
                    )
                    for case in selected
                ],
            }
        )
    return {
        "schema_version": 1,
        "artifact_kind": "episode_seam_ladder",
        "mode": "offline",
        "source_revision": _source_revision(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture": {
            "path": str(questions),
            "sha256": _fixture_digest(questions),
            "as_of": sorted({case.as_of for case in cases}),
        },
        "runtime": {
            "backend": "continuous_glm",
            "continuous_mode": "on",
            # Offline provenance is scripted and must never be dressed up as a
            # production provider/model.
            "provider": OFFLINE_PROVIDER,
            "model": OFFLINE_PROVIDER,
            "semantic_verifier": "offline_deterministic",
        },
        "stages": stages,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--questions",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "intelligence"
            / "tests"
            / "fixtures"
            / "episode_seam_ladder_cases.json"
        ),
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: tuple[str, ...] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact = run_offline_ladder(args.questions)
    if args.output is not None:
        _atomic_write_json(args.output, artifact)
    for stage in artifact["stages"]:
        for record in stage["results"]:
            print(
                f"{record['stage_id']} {record['case_id']}: "
                f"status={record.get('status') or record.get('rejection')} "
                f"structural={record.get('structural_status', '-')} "
                f"semantic={record.get('semantic_status', '-')} "
                f"tools={record.get('tool_calls', 0)} "
                f"failure={record.get('failure_class') or '-'}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
