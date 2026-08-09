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
from dataclasses import dataclass
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
