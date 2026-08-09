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
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.runtime.turn_control_core import TurnControlCore
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_tools import build_episode_registry
from intelligence.services.research_contract import (
    ResearchContractError,
    release_root_budget,
)
from intelligence.services.research_tool_registry import ResearchToolRegistry

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
        stage_set = set(stage.capabilities)
        # Derive from the *production* contract rather than from the stage
        # tuple: ``build_episode_context`` adds capabilities of its own (the
        # evidence plan's mandatory ones), so the real authorization is the
        # ordered intersection of what production granted and what this rung
        # admits.
        enabled = tuple(
            capability
            for capability in source.contract.allowed_capabilities
            if capability in stage_set
        )
        mandatory = tuple(source.contract.evidence_plan.mandatory_capabilities)
        missing = tuple(item for item in mandatory if item not in set(enabled))
        if missing:
            # Not a defect to fix by weakening the contract: below its floor a
            # case is simply unrunnable, and recording that honestly is what
            # keeps a designed failure out of the results.
            yield StageDerivation(
                stage=stage,
                case=case,
                enabled_capabilities=enabled,
                rejection="mandatory_capability_unauthorized",
                rejection_detail=(
                    "evidence plan requires "
                    f"{', '.join(missing)} at {stage.stage_id}"
                ),
            )
            return
        try:
            stage_context = replace(
                source,
                contract=replace(
                    source.contract,
                    allowed_capabilities=enabled,
                ),
            )
        except ResearchContractError as exc:
            yield StageDerivation(
                stage=stage,
                case=case,
                enabled_capabilities=enabled,
                rejection="contract_or_verifier",
                rejection_detail=str(exc),
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
    return parser


def main(argv: tuple[str, ...] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cases = load_cases(args.questions)
    for stage in STAGES:
        selected = cases_for_stage(cases, stage.stage_id)
        print(
            f"{stage.stage_id} {stage.name}: "
            f"capabilities={stage.capabilities or '()'} "
            f"cases={[case.case_id for case in selected] or '[]'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
