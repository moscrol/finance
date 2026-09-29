"""Offline experiment component: omit H rows from an already-compact author view.

Not wired into Workbench. The experiment caller, not a keyword detector, must
explicitly certify that the task requests a standalone replacement answer, not
quotation, comparison or retraction of the prior answer. This is an input
ablation, not a semantic checker, permission change or canonical-record edit.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any


class ProjectionRefused(ValueError):
    """Fail before model submission when the expected author boundary is absent."""


@dataclass(frozen=True)
class ProjectionResult:
    author_view: dict[str, Any]
    omitted_refs: tuple[str, ...] = ()


def project_standalone_redraft(
    payload: dict[str, Any], *, standalone_redraft: bool = False,
) -> ProjectionResult:
    """Keep the OFF arm exact; the ON arm only removes well-formed H sources.

    Canonical contracts and conversation storage are not inputs to this
    mutator. Unknown/legacy views and duplicate catalogue copies are refused
    rather than guessed or searched/replaced as free text. M aliases, user
    quotations, source order and all other fields remain unchanged.
    """
    if type(standalone_redraft) is not bool:
        raise ProjectionRefused("explicit experiment intent must be boolean")
    if not standalone_redraft:
        return ProjectionResult(payload)
    if not isinstance(payload, dict):
        raise ProjectionRefused("author view must be an object")
    author = payload.get("material_grounding")
    contract = payload.get("research_contract")
    frame = payload.get("task_frame")
    if not all(isinstance(value, dict) for value in (author, contract, frame)):
        raise ProjectionRefused("compact author, contract and frame are required")
    material = frame.get("material_contract")
    finish_format = author.get("finish_format")
    if (not isinstance(material, dict)
            or author.get("data_scope") != "material_only"
            or contract.get("allowed_capabilities") != []
            or material.get("data_scope") != "material_only"
            or material.get("classification") in {"state_unavailable", "boundary_uncertain"}):
        raise ProjectionRefused("settled material-only zero-read task required")
    if not isinstance(finish_format, dict) or finish_format.get("format") != "material_claims_v1":
        raise ProjectionRefused("unsupported or legacy author format")
    if "material_grounding" in contract:
        raise ProjectionRefused("canonical catalogue was not compacted")
    history = frame.get("conversation_materials") or {}
    if not isinstance(history, dict) or history.get("assistant_statements"):
        raise ProjectionRefused("duplicate historical answer catalogue")
    sources = author.get("sources")
    if not isinstance(sources, list):
        raise ProjectionRefused("source catalogue must be a list")
    seen: set[str] = set()
    omitted: list[str] = []
    for row in sources:
        if not isinstance(row, dict):
            raise ProjectionRefused("invalid source row")
        ref, kind, text = row.get("ref"), row.get("kind"), row.get("text")
        if not isinstance(ref, str) or not re.fullmatch(r"[MH][1-9][0-9]*", ref) or ref in seen:
            raise ProjectionRefused("invalid or duplicate source alias")
        if not isinstance(text, str) or not text.strip():
            raise ProjectionRefused("source text missing")
        seen.add(ref)
        expected_kind = "user_material" if ref.startswith("M") else "historical_assistant_statement"
        if kind != expected_kind:
            raise ProjectionRefused("wrong-class source; do not conceal invalid input")
        if ref.startswith("H"):
            omitted.append(ref)
    view = deepcopy(payload)
    view["material_grounding"]["sources"] = [
        row for row in view["material_grounding"]["sources"] if row["ref"] not in omitted
    ]
    return ProjectionResult(view, tuple(omitted))
