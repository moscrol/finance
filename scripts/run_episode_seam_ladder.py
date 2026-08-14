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
import os
from pathlib import Path
import subprocess
import sys
import time

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.runtime import agent_episode, episode_tool_batch
from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.runtime.turn_control_core import TurnControlCore
from intelligence.services.agent_research import (
    AgentEvidence,
    evidence_content_hash,
)
from intelligence.runtime.episode_finalizer import EpisodeFinalizer
from intelligence.runtime.glm_agent_runtime import GLMModelClient
from intelligence.paths import default_paths
from intelligence.services import kb_rag, llm_refine
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.episode_factory import build_episode_context
from intelligence.services import episode_semantic_verifier
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeOutcome,
    SemanticEpisodeVerifier,
)
from intelligence.services.episode_tools import (
    build_episode_registry,
    latest_market_date,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    ResearchContractError,
    release_root_budget,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolRunResult,
)
from intelligence.services.run_store import build_trace_step
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
    # Budget must be allocated the way production allocates it, or the ladder
    # measures a budget nobody ships.  `intelligence/api/app.py:366` hands the
    # adapter `GLMAgentRuntime.synthesis_reserve_for_task`, which the adapter
    # turns into a `synthesis_reserve` kwarg for the context factory
    # (`continuous_turn_adapter.py:420`).  This ladder pre-builds its context in
    # order to narrow the capability surface, and its context factory therefore
    # swallows that kwarg — so the allocation has to happen here instead.
    #
    # Omitting it does not merely change a number, it silently disables a fix:
    # the tier default is 20.0s (`research_contract.py:393`), exactly equal to
    # `MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS`, so `_opening_planning_timeout` has
    # nothing above the floor to lend the opening turn and becomes dead code.
    # Production allocates 60s (75s for market_cause / market_watch), which is
    # what makes the borrow real.
    source = build_episode_context(
        control.task_frame,
        task_id=episode_id,
        capabilities=control.capabilities,
        tier=case.tier,
        timeout=case.timeout,
        today=case.as_of,
        latest_data_date=case.as_of,
        synthesis_reserve=GLMAgentRuntime.synthesis_reserve_for_task(
            tier=case.tier,
            question_type=control.task_frame.question_type,
        ),
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


_TRACE_FAILED_EVENT_KINDS = frozenset(
    {"model_error", "tool_error", "invalid_action"}
)
_TRACE_SUMMARY_MAX_CHARS = 2000


def episode_trace_steps(
    events: object,
    *,
    case_id: str,
    stage_id: str,
) -> list[dict[str, object]]:
    """Project one episode's event ledger onto the production trace schema.

    为什么要有这个：``agent-run-triage`` 那类分诊工具的输入门闩是「有中间
    step/span」，只给最终答案会被判 ``INSUFFICIENT_TRACE``。生产每次跑都写
    ``trace.jsonl``（``run_store``），而这个试验台此前只在收据里留一串**事件
    名字**——名字能告诉你哪一步、不能告诉你为什么。2026-08-10 那次误诊
    （把修复轮的失败读成首轮超时）就卡在这里。

    与 ``run_store.append_step`` 共用 ``build_trace_step`` 这一个 schema 定义，
    不另起格式；否则分诊工具只认生产那份，试验台产出照样没人能读。

    时间的取法：每条事件自带发生时刻（``payload["at"]``），**下一条事件的时刻
    就是这一步的结束时刻**。相邻差值即耗时，不需要给每步单独开 span。
    """

    if not isinstance(events, (list, tuple)):
        return []
    ordered = [item for item in events if isinstance(item, Mapping)]
    steps: list[dict[str, object]] = []
    for index, event in enumerate(ordered):
        payload = dict(event.get("payload") or {})
        started_at = str(payload.pop("at", "") or "") or None
        # 每条事件都带同一个 task_frame_hash，逐条重复没有信息量。
        payload.pop("task_frame_hash", None)
        finished_at: str | None = None
        if index + 1 < len(ordered):
            next_payload = ordered[index + 1].get("payload") or {}
            finished_at = str(next_payload.get("at") or "") or None
        kind = str(event.get("kind") or "")
        summary = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if len(summary) > _TRACE_SUMMARY_MAX_CHARS:
            # ``model_turn`` 的 payload 含整段消息正文，不截断会把 trace 撑爆。
            # 截断长度写进串里，免得下游把「被截了」读成「模型只说了这些」。
            summary = (
                summary[:_TRACE_SUMMARY_MAX_CHARS]
                + f"…[truncated from {len(summary)} chars]"
            )
        sequence = event.get("sequence")
        ordinal = sequence if isinstance(sequence, int) else index + 1
        steps.append(
            build_trace_step(
                step_id=f"{stage_id}:{case_id}:{ordinal:03d}",
                name=kind,
                status=(
                    "failed" if kind in _TRACE_FAILED_EVENT_KINDS else "completed"
                ),
                output_summary=summary,
                started_at=started_at,
                finished_at=finished_at,
            )
        )
    return steps


def write_trace_sidecar(artifact: Mapping[str, object], output: Path) -> Path | None:
    """把各 record 的 trace_steps 移出到 ``<收据>.trace.jsonl``。

    移出而不是复制：收据是给人读的汇总，trace 是给分诊工具读的流水。把逐步
    payload 留在收据里会让它从 15KB 涨到几百 KB，而那正是当初决定「只存事件
    名字」的原因——这次是把内容换个地方存，不是塞回原处。
    """

    steps: list[dict[str, object]] = []
    for stage in artifact.get("stages") or ():
        if not isinstance(stage, Mapping):
            continue
        for record in stage.get("results") or ():
            if not isinstance(record, dict):
                continue
            steps.extend(record.pop("trace_steps", None) or [])
    if not steps:
        return None
    path = Path(output).with_suffix(".trace.jsonl")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        "".join(json.dumps(step, ensure_ascii=False) + "\n" for step in steps),
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


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
            # Absolute deadline, not just the relative `timeout`.  Without it
            # `_effective_timeout` returns `self._timeout` unchanged on every
            # hop (`continuous_turn_adapter.py:176`), so each phase restarts
            # its own clock and total wall time inflates — exactly the failure
            # the control-plane invariant "绝对截止而非相对超时" names.
            # Production derives it from the run's own budget the same way
            # (`app.py:958`: `time.monotonic() + self.timeout_sec`).
            #
            # Deliberately NOT mirrored from production, so the omission reads
            # as a decision rather than a third oversight:
            #   · `is_cancelled` — the adapter already defaults to
            #     `lambda: False` (:159) and a batch script has no canceller,
            #     so passing one would be wiring theatre, not fidelity.
            #   · `progress_sink` — no UI to publish progress to here.
            deadline_expires_at=time.monotonic() + case.timeout,
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
        # ``semantic_status`` on its own is not auditable.  ``unavailable`` is
        # returned from six sites in ``episode_semantic_verifier`` (missing
        # contract, frame/contract hash mismatch, a structural partial that may
        # not be released, empty public draft, judge deadline exhausted,
        # transient judge failure) and is *also* what ``continuous_turn_adapter``
        # records when the verifier never produced an outcome at all.  Seven
        # distinct defects wearing one word.  Every fact that separates them was
        # already in the artifact and only this receipt dropped it, which forced
        # the 2026-08-09 live run to be diagnosed by reading source.
        semantic = artifact.get("semantic_verifier") or {}
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
                # Absent block means the verifier never ran, which is a
                # different failure from any verdict it could have returned.
                "semantic_verifier_ran": bool(semantic),
                "semantic_issues": list(semantic.get("issues") or ()),
                # Length, not text: the draft is private and can be long, and
                # what decides the "empty public draft" branch is whether it
                # parses into numbered sentences.  0 means the model produced
                # nothing; >0 with that issue means the model produced text the
                # sentence parser rejected.  Two different bugs, one symptom.
                #
                # 「0 = 模型什么都没产出」这句在 2026-08-10 之前是**假的**：这里取的是
                # 最终 outcome，而修复轮失败会用空草稿把上一轮的顶掉，于是走过
                # ``finalization -> finish`` 的 run 照样报 0（判 30 那两次就是）。
                # ``agent_episode._stopped_outcome`` 已改成结转上一轮的草稿与绑定，
                # 这句话才重新成立。要看修复轮拿什么去冒险，读 ``repair_calls``。
                "draft_chars": len(str(outcome.get("draft") or "")),
                # The only place a stopped episode's provider error survives:
                # ``_stopped_outcome`` passes ``gap=turn.error``.
                "gaps": list(outcome.get("gaps") or ()),
                # Run trajectory.  ``_EpisodeLedger`` already records every
                # step, and ``model_error`` events carry the *raw* provider
                # reason (``agent_episode.py:540/611/1066/1676``) rather than a
                # classified label.  It reaches the artifact via
                # ``outcome["events"]`` and this receipt was simply dropping it.
                #
                # Kinds only, not payloads: a ``model_turn`` payload contains
                # the full message content, which would bloat the receipt and
                # bury the signal.  The shape of the run plus the raw errors is
                # what diagnosis actually needs.
                "trajectory": [
                    str(event.get("kind") or "")
                    for event in outcome.get("events") or ()
                    if isinstance(event, Mapping)
                ],
                "model_errors": [
                    str((event.get("payload") or {}).get("reason") or "")
                    for event in outcome.get("events") or ()
                    if isinstance(event, Mapping)
                    and event.get("kind") == "model_error"
                ],
                # Which tool failed and why.  The book's rule for tool failures
                # is to check the tool's *description* — its boundary conditions
                # — before suspecting the model or the budget, because most
                # wrong-tool failures come from the model not knowing what a
                # tool *cannot* do.  That rule is unusable while the receipt
                # records only that some tool errored.
                "tool_errors": [
                    {
                        "tool": str((event.get("payload") or {}).get("tool") or ""),
                        "error": str(
                            (event.get("payload") or {}).get("error") or ""
                        )[:200],
                    }
                    for event in outcome.get("events") or ()
                    if isinstance(event, Mapping)
                    and event.get("kind") == "tool_error"
                ],
                # 修复轮的时钟账，与 judge_calls 里的 timeout_asked 同一用途。
                # ``timeout_asked`` 远小于 ``timeout_configured`` 说明修复轮进场时
                # 时钟已经被前面耗光，此时给它加预算是没用的（judge 那次就是这么
                # 误诊的）；两者接近才轮到怀疑 provider 本身慢。
                # ``previous_draft_chars`` 是这一轮拿去冒险的东西——它 >0 而最终
                # ``draft_chars`` 也 >0，才说明结转生效了。
                # 逐步流水，落盘时会被 write_trace_sidecar 移出到
                # <收据>.trace.jsonl，收据本身不留它。
                "trace_steps": episode_trace_steps(
                    outcome.get("events"),
                    case_id=case.case_id,
                    stage_id=derived.stage.stage_id,
                ),
                "repair_calls": [
                    {
                        key: (event.get("payload") or {}).get(key)
                        for key in (
                            "cycle",
                            "granted_seconds",
                            "timeout_asked",
                            "timeout_configured",
                            "research_tools_open",
                            "previous_draft_chars",
                        )
                    }
                    for event in outcome.get("events") or ()
                    if isinstance(event, Mapping)
                    and event.get("kind") == "repair_reentry"
                ],
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


# --- live mode ---------------------------------------------------------------
#
# Live spends real provider budget against a real market snapshot, so it is
# opt-in and never a merge gate: the production relay's P95 is tens of seconds
# and one episode makes several model calls.  Its job is to re-validate the
# production path, not to grade answers.

# 家目录下的运行时目录（与 agent-review / test-receipts 同一约定），故用
# Path.home() 而非仓根推导——它刻意在仓树之外，收据不该被 git 管。
# 此前写死 Path("/Users/a77/.finance-runtime/seam-ladder")。
LIVE_RECEIPT_ROOT = Path.home() / ".finance-runtime" / "seam-ladder"
# Two rungs, not the whole matrix: S1 proves the narrowest real assembly closes
# and S3 proves the full causal surface does.  The rungs in between are already
# covered offline, where they cost nothing.
LIVE_STAGE_CASES: tuple[tuple[str, str], ...] = (
    ("S1", "next-session-index"),
    ("S3", "weekly-market-cause"),
)


def validate_live_output_path(path: Path | None) -> Path:
    """Keep live receipts outside Git.

    A receipt carries run-specific provider identity, timings and answers.  It
    is evidence about one environment at one moment, not source, so committing
    it would make the repository's history depend on whoever happened to run it.
    """

    if path is None:
        raise ValueError(
            "live mode requires --output under " + str(LIVE_RECEIPT_ROOT)
        )
    resolved = Path(path).expanduser()
    try:
        resolved.relative_to(LIVE_RECEIPT_ROOT)
    except ValueError as exc:
        raise ValueError(
            f"live receipt must live under {LIVE_RECEIPT_ROOT}; got {resolved}"
        ) from exc
    return resolved


@dataclass(frozen=True)
class LivePreflight:
    """Whether the environment can produce live evidence, and why not."""

    ready: bool
    failures: tuple[str, ...]
    continuous_mode: str
    provider: str
    model: str
    latest_data_date: str
    required_as_of: str

    def to_dict(self) -> dict[str, object]:
        # Only provider *identity* is recorded.  Keys and endpoints are secrets
        # and are never part of a receipt.
        return {
            "ready": self.ready,
            "failures": list(self.failures),
            "continuous_mode": self.continuous_mode,
            "provider": self.provider,
            "model": self.model,
            "latest_data_date": self.latest_data_date,
            "required_as_of": self.required_as_of,
        }


def live_preflight(
    cases: tuple[SeamLadderCase, ...],
    *,
    providers: tuple[object, ...],
    latest_data_date: str | None,
    environ: Mapping[str, str] | None = None,
) -> LivePreflight:
    """Check the three inputs live evidence depends on, before spending budget.

    Each check exists because failing it would produce a receipt that *looks*
    like a seam result: a declined episode (continuous mode off), a zero-attempt
    run (no provider), or an answer grounded in a snapshot older than the
    question's own ``as_of``.
    """

    env = os.environ if environ is None else environ
    failures: list[str] = []
    mode = str(env.get("ASK_CONTINUOUS_RUNTIME") or "").strip().lower()
    if mode != "on":
        # Anything but "on" makes the adapter decline the turn, which would be
        # recorded as an empty rung rather than as a configuration fact.
        failures.append(
            f"continuous_mode must be 'on' to run an episode; got "
            f"'{mode or 'unset'}'"
        )
    provider_name = ""
    model_name = ""
    if not providers:
        failures.append("provider_chain is empty: no LLM provider resolved")
    else:
        # Read identity off the resolved chain, never off an environment
        # variable: the relay can rewrite which model actually serves a call.
        provider_name = str(getattr(providers[0], "name", "") or "")
        model_name = str(getattr(providers[0], "model", "") or "")
    required_as_of = max((case.as_of for case in cases), default="")
    snapshot = str(latest_data_date or "")
    if not snapshot:
        failures.append("market_data_freshness: no market snapshot date available")
    elif snapshot < required_as_of:
        failures.append(
            f"market_data_freshness: snapshot {snapshot} predates fixture "
            f"as_of {required_as_of}"
        )
    return LivePreflight(
        ready=not failures,
        failures=tuple(failures),
        continuous_mode=mode,
        provider=provider_name,
        model=model_name,
        latest_data_date=snapshot,
        required_as_of=required_as_of,
    )


class _RecordingJudgeClient:
    """Keep what the semantic verifier throws away about its judge call.

    ``_stable_semantic_judge_error`` classifies a judge failure from the
    exception's **type name alone** and discards the message, so a receipt can
    say "semantic judge transient provider error" without ever naming what
    happened.  Diagnosing it has meant reading source and guessing.

    Wrapping the injected client is the honest seam.  The verifier has two
    judge paths and only one is live here: the independent
    ``llm_refine.judge_provider()`` path is skipped whenever ``LLM_JUDGE_*`` is
    unset (``episode_semantic_verifier.py:1107``), which is our case, so the
    judge actually arrives at ``primary.complete(...)`` at :1244 — this object.
    An earlier version of this instrumentation patched ``llm_refine.complete``
    and recorded nothing at all, because that is the path we never take.

    Two shapes of failure reach us: a raised exception, and a returned
    ``ModelTurn`` carrying a non-empty ``error``.  Only the first becomes the
    classified label, so both are recorded.

    Deliberately not callable and exposing ``complete``: the verifier branches
    on ``callable(primary) and not hasattr(primary, "complete")`` (:1213), so
    the wrapper must keep the same shape or it would silently change the path
    under test.
    """

    def __init__(
        self,
        inner: object,
        records: list[dict[str, object]],
    ) -> None:
        self._inner = inner
        self._records = records

    def complete(self, **kwargs: object) -> object:
        started = time.monotonic()
        try:
            turn = self._inner.complete(**kwargs)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001 — recorded, then re-raised
            self._records.append(
                {
                    "seconds": round(time.monotonic() - started, 2),
                    "outcome": "exception",
                    "detail": f"{type(exc).__name__}: {exc}"[:300],
                }
            )
            raise
        error = str(getattr(turn, "error", "") or "")
        self._records.append(
            {
                "seconds": round(time.monotonic() - started, 2),
                "outcome": "turn_error" if error else "ok",
                "detail": error[:300],
                "provider_attempts": getattr(turn, "provider_attempts", None),
                "timeout_asked": kwargs.get("timeout"),
            }
        )
        return turn


def run_live_stage_case(
    case: SeamLadderCase,
    control: object,
    stage_id: str,
    *,
    providers: tuple[object, ...],
) -> dict[str, object]:
    """Run one rung against the resolved production provider and tools."""

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
        registry = derived.registry
        record["tool_schema_names"] = list(registry.names())
        client = GLMModelClient(providers=providers)
        finalizer = EpisodeFinalizer(client)
        judge_calls: list[dict[str, object]] = []
        judge_client = _RecordingJudgeClient(client, judge_calls)
        adapter = ContinuousTurnAdapter(
            runtime=GLMAgentRuntime(
                client=client,
                finalizer=finalizer,
            ),
            # Wire the judge exactly as `intelligence/api/app.py` does.  Built
            # with no seam at all, the verifier has nothing to call: the judge
            # loop exhausts its attempts and falls through to "semantic judge
            # unavailable" (`episode_semantic_verifier.py:1196`) on every rung,
            # every time.  That is what the 2026-08-09 live runs recorded, and
            # it made the third completion criterion in the design spec
            # (semantic verifier `passed` or `repaired`) unreachable by
            # construction rather than by any property of the seam under test.
            # The receipt already labels this path `production_llm_judge`; the
            # label was true of the intent and false of the wiring.
            semantic_verifier=SemanticEpisodeVerifier(
                primary_judge=judge_client,
                finalizer=finalizer,
            ),
            mode="on",
            context_factory=lambda _frame, **_kwargs: derived.context,
            registry_factory=lambda _frame, _context: registry,
            tier=case.tier,
            timeout=case.timeout,
            today=case.as_of,
            latest_data_date=case.as_of,
            # Absolute deadline, not just the relative `timeout`.  Without it
            # `_effective_timeout` returns `self._timeout` unchanged on every
            # hop (`continuous_turn_adapter.py:176`), so each phase restarts
            # its own clock and total wall time inflates — exactly the failure
            # the control-plane invariant "绝对截止而非相对超时" names.
            # Production derives it from the run's own budget the same way
            # (`app.py:958`: `time.monotonic() + self.timeout_sec`).
            #
            # Deliberately NOT mirrored from production, so the omission reads
            # as a decision rather than a third oversight:
            #   · `is_cancelled` — the adapter already defaults to
            #     `lambda: False` (:159) and a batch script has no canceller,
            #     so passing one would be wiring theatre, not fidelity.
            #   · `progress_sink` — no UI to publish progress to here.
            deadline_expires_at=time.monotonic() + case.timeout,
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
        record["judge_calls"] = list(judge_calls)
        artifact = result.private_artifact or {}
        metrics = artifact.get("metrics") or {}
        structural = artifact.get("structural_verifier") or {}
        outcome = artifact.get("outcome") or {}
        # ``semantic_status`` on its own is not auditable.  ``unavailable`` is
        # returned from six sites in ``episode_semantic_verifier`` (missing
        # contract, frame/contract hash mismatch, a structural partial that may
        # not be released, empty public draft, judge deadline exhausted,
        # transient judge failure) and is *also* what ``continuous_turn_adapter``
        # records when the verifier never produced an outcome at all.  Seven
        # distinct defects wearing one word.  Every fact that separates them was
        # already in the artifact and only this receipt dropped it, which forced
        # the 2026-08-09 live run to be diagnosed by reading source.
        semantic = artifact.get("semantic_verifier") or {}
        record.update(
            {
                "handled": result.handled,
                "status": result.status,
                "execution_kind": artifact.get("execution_kind", ""),
                "answer": result.answer,
                "structural_status": metrics.get("structural_status", ""),
                "semantic_status": metrics.get("semantic_status", ""),
                "tool_calls": metrics.get("tool_calls", 0),
                "provider_attempts": metrics.get("provider_attempts", 0),
                "duplicate_queries": metrics.get("duplicate_queries", 0),
                "evidence_hashes": [
                    str(item.get("content_hash") or "")
                    for item in outcome.get("evidence") or ()
                    if isinstance(item, Mapping) and item.get("content_hash")
                ],
                "missing_outputs": list(structural.get("missing_outputs") or ()),
                "structural_issues": list(structural.get("issues") or ()),
                # Absent block means the verifier never ran, which is a
                # different failure from any verdict it could have returned.
                "semantic_verifier_ran": bool(semantic),
                "semantic_issues": list(semantic.get("issues") or ()),
                # Length, not text: the draft is private and can be long, and
                # what decides the "empty public draft" branch is whether it
                # parses into numbered sentences.  0 means the model produced
                # nothing; >0 with that issue means the model produced text the
                # sentence parser rejected.  Two different bugs, one symptom.
                #
                # 「0 = 模型什么都没产出」这句在 2026-08-10 之前是**假的**：这里取的是
                # 最终 outcome，而修复轮失败会用空草稿把上一轮的顶掉，于是走过
                # ``finalization -> finish`` 的 run 照样报 0（判 30 那两次就是）。
                # ``agent_episode._stopped_outcome`` 已改成结转上一轮的草稿与绑定，
                # 这句话才重新成立。要看修复轮拿什么去冒险，读 ``repair_calls``。
                "draft_chars": len(str(outcome.get("draft") or "")),
                # The only place a stopped episode's provider error survives:
                # ``_stopped_outcome`` passes ``gap=turn.error``.
                "gaps": list(outcome.get("gaps") or ()),
                # Run trajectory.  ``_EpisodeLedger`` already records every
                # step, and ``model_error`` events carry the *raw* provider
                # reason (``agent_episode.py:540/611/1066/1676``) rather than a
                # classified label.  It reaches the artifact via
                # ``outcome["events"]`` and this receipt was simply dropping it.
                #
                # Kinds only, not payloads: a ``model_turn`` payload contains
                # the full message content, which would bloat the receipt and
                # bury the signal.  The shape of the run plus the raw errors is
                # what diagnosis actually needs.
                "trajectory": [
                    str(event.get("kind") or "")
                    for event in outcome.get("events") or ()
                    if isinstance(event, Mapping)
                ],
                "model_errors": [
                    str((event.get("payload") or {}).get("reason") or "")
                    for event in outcome.get("events") or ()
                    if isinstance(event, Mapping)
                    and event.get("kind") == "model_error"
                ],
                # Which tool failed and why.  The book's rule for tool failures
                # is to check the tool's *description* — its boundary conditions
                # — before suspecting the model or the budget, because most
                # wrong-tool failures come from the model not knowing what a
                # tool *cannot* do.  That rule is unusable while the receipt
                # records only that some tool errored.
                "tool_errors": [
                    {
                        "tool": str((event.get("payload") or {}).get("tool") or ""),
                        "error": str(
                            (event.get("payload") or {}).get("error") or ""
                        )[:200],
                    }
                    for event in outcome.get("events") or ()
                    if isinstance(event, Mapping)
                    and event.get("kind") == "tool_error"
                ],
                # 修复轮的时钟账，与上面的 judge_calls.timeout_asked 同一用途。
                # ``timeout_asked`` 远小于 ``timeout_configured``：修复轮进场时时钟
                # 已被前面耗光，此时给它加预算没用（judge 那次正是这么误诊的）；
                # 两者接近才轮到怀疑 provider 本身慢。
                # ``previous_draft_chars`` 是这一轮拿去冒险的东西：它 >0 时最终
                # ``draft_chars`` 也应 >0，否则说明结转又被谁清掉了。
                # 逐步流水，落盘时会被 write_trace_sidecar 移出到
                # <收据>.trace.jsonl，收据本身不留它。
                "trace_steps": episode_trace_steps(
                    outcome.get("events"),
                    case_id=case.case_id,
                    stage_id=derived.stage.stage_id,
                ),
                "repair_calls": [
                    {
                        key: (event.get("payload") or {}).get(key)
                        for key in (
                            "cycle",
                            "granted_seconds",
                            "timeout_asked",
                            "timeout_configured",
                            "research_tools_open",
                            "previous_draft_chars",
                        )
                    }
                    for event in outcome.get("events") or ()
                    if isinstance(event, Mapping)
                    and event.get("kind") == "repair_reentry"
                ],
                "satisfiability_precheck": artifact.get(
                    "satisfiability_precheck",
                    {},
                ),
                "stop_reason": outcome.get("stop_reason", ""),
                "llm_provider": result.llm_provider or "",
            }
        )
        return record


def _provider_honors_max_tokens(providers: tuple[object, ...]) -> str:
    """One cheap call: does this provider apply the output cap we send?

    Returns ``"yes"`` / ``"no"`` / ``"unknown"`` rather than a bool, because
    "we could not find out" and "it ignores the cap" are different facts and
    collapsing them is the same defect this receipt keeps running into.
    """

    if not providers:
        return "unknown"
    try:
        # Deliberately the production synthesis path, not a hand-rolled
        # request: what matters is whether the cap survives *the call shape we
        # actually ship*, headers and all.
        content, _finish = llm_refine._post_chat_synthesis(  # noqa: SLF001
            providers[0],  # type: ignore[arg-type]
            [{"role": "user", "content": "请用三百字介绍A股的涨跌停制度。"}],
            60.0,
            0.0,
            10,
            1_000_000,  # never trip the char guard; we are measuring tokens
        )
    except Exception:  # noqa: BLE001 — a probe failure is not a run failure
        return "unknown"
    if not content:
        return "unknown"
    # 10 tokens cannot render a sentence; comfortably past it means the cap
    # was dropped somewhere between us and the model.
    return "no" if len(content) > 120 else "yes"


def run_live_ladder(
    questions: Path,
    *,
    providers: tuple[object, ...],
    preflight: LivePreflight,
) -> dict[str, object]:
    """Build the live receipt; fabricate no stage result when preflight failed."""

    cases = {case.case_id: case for case in load_cases(questions)}
    stages: list[dict[str, object]] = []
    if preflight.ready:
        for stage_id, case_id in LIVE_STAGE_CASES:
            case = cases[case_id]
            stages.append(
                {
                    "stage_id": stage_id,
                    "stage_name": resolve_stage(stage_id).name,
                    "stage_capabilities": list(
                        resolve_stage(stage_id).capabilities
                    ),
                    "results": [
                        run_live_stage_case(
                            case,
                            resolve_control(case),
                            stage_id,
                            providers=providers,
                        )
                    ],
                }
            )
    return {
        "schema_version": 1,
        "artifact_kind": "episode_seam_ladder",
        "mode": "live",
        "source_revision": _source_revision(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture": {
            "path": str(questions),
            "sha256": _fixture_digest(questions),
            "as_of": sorted({case.as_of for case in cases.values()}),
        },
        "runtime": {
            "backend": "continuous_glm",
            "continuous_mode": preflight.continuous_mode,
            "provider": preflight.provider,
            "model": preflight.model,
            "semantic_verifier": "production_llm_judge",
            # Whether the provider actually honours the output cap we send.
            # 2026-08-09: this relay does not — `max_tokens=10` returned 416
            # tokens with `finish_reason=stop`, i.e. the limit was never
            # applied.  `llm_refine` sends `max_tokens` on every synthesis call
            # (default 3000) and the budget arithmetic downstream assumes that
            # bound holds, so a receipt that omits this records timings drawn
            # from a belief the provider does not share.  Recorded rather than
            # gated: an unhonoured cap makes the run *less* comparable, not
            # invalid.
            "provider_honors_max_tokens": _provider_honors_max_tokens(providers),
            # Which experiment arm produced this receipt.  The time-budget
            # signal ships default-off, so two receipts from the same revision
            # can legitimately differ; recording the arm is what keeps that
            # from looking like run-to-run noise.
            "budget_status": (
                "on" if agent_episode.budget_status_enabled() else "off"
            ),
            # The two ceilings that actually bind, recorded as *effective*
            # values rather than as the constants' defaults.  Both cap a
            # `stage_timeout`/`synthesis_timeout` call, so raising the episode
            # tier does not widen them — a receipt that omits them cannot be
            # compared against one from a calibration run.
            "tool_batch_timeout": episode_tool_batch.tool_batch_timeout_seconds(),
            "judge_window": (
                episode_semantic_verifier.semantic_judge_window_seconds()
            ),
        },
        "preflight": preflight.to_dict(),
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
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Opt in to the current production provider. Spends real budget, "
            "writes its receipt outside Git, and is never a merge gate."
        ),
    )
    return parser


def _print_ladder(artifact: dict[str, object]) -> None:
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


def _prewarm_retrieval() -> None:
    """预热 RAG worker，否则 live 阶梯量的是启动成本不是检索成本。

    生产 8792 在 ``lifespan`` 里 prewarm 一次（``api/app.py:1860``），之后 worker
    一直热着。这个脚本是独立进程，不预热就会每次现加载 BGE-m3 与 214MB 稠密索引。

    2026-08-10 用 ``scripts/probe_tool.py`` 实测的三种状态，差 5 倍：

    | 条件 | kb_search | evidence_search |
    |---|---|---|
    | 无 worker（subprocess 每次现起） | 19s | 56-64s |
    | worker 开但未预热 | 30s（超时返空） | — |
    | **预热 + worker（= 生产）** | **2.6-3.6s** | **16-17s** |

    影响的是结论本身：未预热时 ``evidence_search`` 必然撞 30s 工具批次上限，
    于是阶梯把它记成 ``tool_timeout``——那是**试验台产物，不是生产缺陷**。
    生产状态下 16-17s 在上限之内。此前几轮据此判断「evidence_search 是慢工具、
    要并行化」，全部建立在这个测量条件错误之上。

    失败不阻断：预热不了就照跑，只是读数会偏慢——但要让它在日志里看得见。
    """

    if not kb_rag.rag_worker.enabled():
        print(
            "preflight: RAG_WORKER_ENABLED 未开启（生产是 1）；"
            "检索读数将包含每次现加载成本，不代表生产"
        )
        return
    started = time.monotonic()
    try:
        kb_rag.prewarm(default_paths().knowledge_wiki, timeout=120.0)
    except Exception as exc:  # noqa: BLE001 - 预热失败要看得见，但不阻断
        print(f"preflight: RAG 预热失败（{type(exc).__name__}: {exc}）")
        return
    print(f"preflight: RAG worker 已预热（{time.monotonic() - started:.1f}s）")


def main(argv: tuple[str, ...] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.live:
        artifact = run_offline_ladder(args.questions)
        if args.output is not None:
            trace_path = write_trace_sidecar(artifact, Path(args.output))
            _atomic_write_json(args.output, artifact)
            if trace_path is not None:
                print(f"trace written to {trace_path}")
        _print_ladder(artifact)
        return 0

    # Live mode resolves its identity from the production seams, never from an
    # environment variable: the relay can rewrite which model serves a call.
    output = validate_live_output_path(args.output)
    _prewarm_retrieval()
    providers = llm_refine.detect_providers()
    preflight = live_preflight(
        load_cases(args.questions),
        providers=providers,
        latest_data_date=latest_market_date(),
    )
    artifact = run_live_ladder(
        args.questions,
        providers=providers,
        preflight=preflight,
    )
    # 先移出 trace 再写收据：顺序反了收据里就会留一份逐步 payload 副本。
    trace_path = write_trace_sidecar(artifact, Path(output))
    _atomic_write_json(output, artifact)
    if trace_path is not None:
        print(f"trace written to {trace_path}")
    if not preflight.ready:
        for failure in preflight.failures:
            print(f"preflight: {failure}")
        print(f"preflight blocked; receipt written to {output}")
        return 2
    _print_ladder(artifact)
    print(f"live receipt written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
