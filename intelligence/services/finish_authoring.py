"""Choose and compile one author body; evidence admission stays in the protocol.

Material semantics and owned result authority remain with their existing owners.
This module owns only the author envelope, mechanical body compilation and its
detached immutable products. It performs no IO and certifies no free prose.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from intelligence.services.material_answer_authoring import (
    MaterialAuthoringError, compile_material_author_finish, material_author_schema,
)
from intelligence.services.material_grounding import (
    claim_finish_format, render_material_claims, split_claim_sentences,
)
from intelligence.services.owned_results import (
    OwnedResultError, _catalogue_from_context, _context_owner, render_owned_parts,
)

if TYPE_CHECKING:
    from intelligence.services.prior_evidence import PriorTurnEvidence
    from intelligence.services.research_contract import ResearchRunContext, ResearchTaskContract


ORDINARY_AUTHOR_FORMAT = "ordinary_answer_parts_v1"
_FINISH_STATUSES = frozenset({"completed", "partial"})
_ORDINARY_RULE = (
    "按 wire_template 提交一个终局 JSON，status、draft、answer_parts、gaps、bindings 为原有字段。"
    "默认 draft 为空，answer_parts 按最终正文顺序填写自由文字字符串或只有 result_ref 的对象；"
    "程序把块以空行连接，result_ref 必须来自本轮已实际交付的 owned_results.parts。"
    "没有可用目录时只写自由文字；是否选 ref、选择多少个及排列顺序由你决定，不要求至少一个。"
    "ref 对象不添加 text、value、truth、单位或 receipt，自由文字不自动获得来源认证。"
    "兼容旧 draft 或 render_from_claims 时，answer_parts 须省略或为 null；"
    "使用 answer_parts 时 draft 必须为空且不能 render_from_claims，始终只有一个正文生成者。"
    "status、gaps 与 bindings 继续按本轮原合同填写；格式和编译本身不授予 completed、证据或权限。"
    "不提交 format 或 owned_answer 字段，篇幅、Markdown 和数字绑定规则适用于编译后的最终正文。"
)


class FinishAuthoringError(ValueError):
    """An existing protocol reason raised before evidence admission."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class _FrozenList(tuple):
    """Keep list identity so a copy cannot turn an invalid tuple into a list."""


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return _FrozenList(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, _FrozenList):
        return [_thaw(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_thaw(item) for item in value)
    return value


@dataclass(frozen=True)
class FinishAuthorContract:
    json_schema: Mapping[str, object]
    model_payload: Mapping[str, object] | None

    def schema_payload(self) -> dict[str, object]:
        """Return a disposable provider-facing copy, never an authority cache."""
        return cast(dict[str, object], _thaw(self.json_schema))

    def prompt_payload(self) -> dict[str, object] | None:
        return cast(dict[str, object] | None, _thaw(self.model_payload))


@dataclass(frozen=True)
class CompiledFinishAuthoring:
    envelope: Mapping[str, object]
    claim_origins: Mapping[str, tuple[int, ...]]
    owned_answer: Mapping[str, object] | None

    def envelope_payload(self) -> dict[str, object]:
        """Restore author container types for the unchanged admission checks."""
        return cast(dict[str, object], _thaw(self.envelope))

    def owned_answer_payload(self) -> dict[str, object] | None:
        return cast(dict[str, object] | None, _thaw(self.owned_answer))


def _legacy_finish_schema(
    contract: ResearchTaskContract | None = None, *, prior_evidence: PriorTurnEvidence | None = None,
) -> dict[str, object]:
    """The byte-stable context-free adapter, including the material exception."""
    author_schema = material_author_schema(contract, prior_evidence=prior_evidence)
    if author_schema is not None:
        return author_schema
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {
                "type": "string",
                "enum": ["completed", "partial"],
            },
            "draft": {"type": "string"},
            "answer_parts": {
                "type": "array",
                "items": {"anyOf": [
                    {"type": "string"},
                    {"type": "object", "additionalProperties": False,
                     "properties": {"result_ref": {"type": "string"}}, "required": ["result_ref"]},
                ]},
            },
            "render_from_claims": {"type": "boolean"},
            "gaps": {
                "type": "array",
                "items": {"type": "string"},
            },
            "bindings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "output_id": {"type": "string"},
                        "evidence_hashes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Episode ordinals E1..En from the observation, "
                                "or an exact collected content_hash"
                            ),
                        },
                        "basis": {
                            "type": "string",
                            "enum": [
                                "evidence",
                                "user_premise",
                                "model_reasoning",
                            ],
                        },
                        "gap": {"type": "string"},
                        "claims": {
                            "type": "array",
                            "items": {
                                "type": "object", "additionalProperties": False,
                                "properties": {
                                    "text": {"type": "string"},
                                    "kind": {"type": "string", "enum": ["material_fact", "reasoning", "premise_declaration", "historical_assistant_statement"]},
                                    "material_anchors": {"type": "array", "items": {
                                        "type": "object", "additionalProperties": False,
                                        "properties": {"material_id": {"type": "string"}, "quote": {"type": "string"}},
                                        "required": ["material_id", "quote"],
                                    }},
                                    "old_answer_coordinate": {"type": "string"},
                                    "historical_quote": {"type": "string"},
                                    "basis": {"type": "string"},
                                },
                                "required": ["text", "kind"],
                            },
                        },
                    },
                    "required": [
                        "output_id",
                        "evidence_hashes",
                        "basis",
                        "gap",
                    ],
                },
            },
        },
        "required": ["status", "draft", "gaps", "bindings"],
    }


def finish_author_contract(context: ResearchRunContext) -> FinishAuthorContract:
    """Return one immutable author shape without granting any result refs."""
    contract, prior = context.contract, context.prior_evidence
    schema = _legacy_finish_schema(contract, prior_evidence=prior)
    if contract.material_contract is not None:
        payload = claim_finish_format(contract, prior_evidence=prior)
    else:
        properties = schema["properties"]
        properties["answer_parts"] = {"anyOf": [properties["answer_parts"], {"type": "null"}]}
        # The legacy branch excludes arrays, and claims require true while both
        # other branches exclude true. Each accepted wire has exactly one owner.
        schema["oneOf"] = [
            {"required": ["answer_parts"], "properties": {
                "draft": {"const": ""}, "answer_parts": {"type": "array"},
                "render_from_claims": {"const": False},
            }},
            {"properties": {
                "answer_parts": {"type": "null"}, "render_from_claims": {"const": False},
            }},
            {"required": ["render_from_claims"], "properties": {
                "draft": {"const": ""}, "answer_parts": {"type": "null"},
                "render_from_claims": {"const": True},
            }},
        ]
        payload = {
            "format": ORDINARY_AUTHOR_FORMAT,
            "wire_template": json.dumps({
                "status": "completed", "draft": "", "answer_parts": [], "gaps": [], "bindings": [],
            }, ensure_ascii=False),
            "rule": _ORDINARY_RULE,
        }
    return FinishAuthorContract(
        cast(Mapping[str, object], _freeze(schema)),
        cast(Mapping[str, object] | None, _freeze(payload)),
    )


def _normalize_natural_language_layout(value: str) -> str:
    """Decode the existing double-escaped newline literals in free prose."""
    return value.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")


def compile_finish_authoring(
    envelope: Mapping[str, object], *, context: ResearchRunContext,
) -> CompiledFinishAuthoring:
    """Compile one body in the old error order; the protocol still admits it."""
    if "owned_answer" in envelope:
        raise FinishAuthoringError("bad_claim_binding", "ownership receipt is program-owned")
    parts = envelope.get("answer_parts")
    if parts is not None and (envelope.get("format") is not None or envelope.get("render_from_claims")
                              or context.contract.material_contract is not None):
        raise FinishAuthoringError("bad_claim_binding", "answer_parts cannot mix with material authoring or claim rendering")
    try:
        decoded = compile_material_author_finish(
            envelope, context.contract, prior_evidence=context.prior_evidence,
        )
    except MaterialAuthoringError as exc:
        raise FinishAuthoringError(exc.code, str(exc)) from exc
    status = decoded.get("status")
    if status not in _FINISH_STATUSES:
        raise FinishAuthoringError("bad_status", "finish status must be completed or partial")
    draft = decoded.get("draft")
    if not isinstance(draft, str):
        raise FinishAuthoringError("draft_not_string", "finish draft must be a string")
    owned_answer = None
    if parts is not None:
        try:
            normalized_parts = [_normalize_natural_language_layout(p) if type(p) is str else p for p in parts] if isinstance(parts, list) else parts
            rendered = render_owned_parts(normalized_parts, _catalogue_from_context(context), legacy_draft=draft)
        except OwnedResultError as exc:
            raise FinishAuthoringError("bad_claim_binding", "owned result selection: " + exc.reason) from exc
        draft = rendered.draft
        if rendered.owned_blocks:
            owned_answer = {**rendered.receipt, "owner": _context_owner(context)}
    render_from_claims = decoded.get("render_from_claims", False)
    if not isinstance(render_from_claims, bool):
        raise FinishAuthoringError("bad_claim_binding", "render_from_claims must be a boolean")
    if render_from_claims:
        if draft:
            raise FinishAuthoringError("bad_claim_binding", "claim rendering cannot include a second draft")
        try:
            draft = render_material_claims(context.contract, decoded.get("bindings"))
        except ValueError as exc:
            raise FinishAuthoringError("bad_claim_binding", str(exc)) from exc
        decoded, claim_origins = split_claim_sentences(decoded)
    else:
        claim_origins = {}
        if parts is None:
            draft = _normalize_natural_language_layout(draft)
    return CompiledFinishAuthoring(
        cast(Mapping[str, object], _freeze({**decoded, "draft": draft})),
        cast(Mapping[str, tuple[int, ...]], _freeze(claim_origins)),
        cast(Mapping[str, object] | None, _freeze(owned_answer)),
    )
