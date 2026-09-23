"""Versioned recovery authority, separate from the model-facing configure summary.

A saved declaration is NOT a grant. Recovery compares it with authority supplied
by the owning entry point before synthesizing anything. It does not deserialize
runners, bind user identity, allocate budgets or restore a complete run context.
The registry digest covers declarations, not executable code/closures. Who the
episode belongs to is a separate question, answered by ``episode_entry_identity``
(same-owner check) and ``episode_store.writer`` (single-writer ownership); a
future driver still needs effect/cost reconciliation on top of both.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
import math

from intelligence.services.agent_runtime import _json_copy, _json_freeze
from intelligence.services.research_contract import (
    InformationCutoff, RESEARCH_TIERS, ResearchPolicy, ResearchRunContext, ResearchTaskContract,
)
from intelligence.services.research_tool_registry import ResearchToolRegistry

_VERSION = 1
_KIND = "episode_authorization"
_FIELDS = frozenset({
    "schema_version", "kind", "episode_id", "contract", "policy",
    "information_cutoff", "trace_parent_id", "registry", "registry_sha256",
})
_TOOL_FIELDS = frozenset({
    "name", "capability", "description", "contract", "cost", "freshness",
    "query_scope", "parameters", "produces", "min_window_seconds", "replay", "io_effect",
})
_SCOPE_RANK = {"full": 0, "local_only": 1, "material_only": 2}


def _json(value: object) -> str:
    return json.dumps(_json_copy(value, path="authorization"), ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(registry: Mapping[str, object]) -> str:
    return hashlib.sha256(_json(registry).encode("utf-8")).hexdigest()


def _object(value: object, fields: frozenset[str], name: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"authorization {name} fields are incomplete or unknown")
    return value


def _seconds(value: object) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def _contract_payload(contract: ResearchTaskContract) -> dict[str, object]:
    # Unlike the legacy domain serializer, omission must not erase a prior scope.
    return {**contract.to_dict(), "material_contract": (
        contract.material_contract.to_dict() if contract.material_contract is not None else None
    )}


def _parse_contract(raw: object, *, episode_id: str) -> ResearchTaskContract:
    if not isinstance(raw, dict):
        raise ValueError("authorization contract must be an object")
    payload = dict(raw)
    if "material_contract" in payload and payload["material_contract"] is None:
        del payload["material_contract"]
    try:
        contract = ResearchTaskContract.from_dict(payload)
    except (TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("authorization contract has invalid field types") from exc
    # Reuse the domain validator, then reject its backwards-compatible defaults,
    # coercions and dropped fields. Don't build a second financial contract schema.
    if _json(raw) != _json(_contract_payload(contract)):
        raise ValueError("authorization contract is incomplete or noncanonical")
    if contract.task_id != episode_id or contract.contract_version != "1":
        raise ValueError("authorization contract identity/version mismatch")
    if any(not cap.strip() or cap != cap.strip() for cap in contract.allowed_capabilities):
        raise ValueError("authorization capabilities require canonical identities")
    if len(set(contract.allowed_capabilities)) != len(contract.allowed_capabilities):
        raise ValueError("authorization capabilities contain duplicates")
    return contract


def _validate_registry(raw: object, contract: ResearchTaskContract) -> Mapping[str, object]:
    registry = _object(raw, frozenset({"read_scope", "tools"}), "registry")
    scope = registry["read_scope"]
    if not isinstance(scope, str) or scope not in _SCOPE_RANK:
        raise ValueError("authorization registry scope is invalid")
    material = contract.material_contract
    if material is not None and material.data_scope in _SCOPE_RANK:
        if _SCOPE_RANK[scope] < _SCOPE_RANK[material.data_scope]:
            raise ValueError("authorization registry relaxes the material contract")
    tools = registry["tools"]
    if not isinstance(tools, list):
        raise ValueError("authorization registry tools must be a list")
    names = []
    for value in tools:
        tool = _object(value, _TOOL_FIELDS, "tool")
        for key in ("name", "capability", "description", "contract", "cost", "freshness"):
            if not isinstance(tool[key], str):
                raise ValueError(f"authorization tool {key} must be a string")
        name = tool["name"]
        if not name.strip() or name != name.strip() or tool["capability"] not in contract.allowed_capabilities:
            raise ValueError("authorization tool name/capability is invalid")
        if tool["query_scope"] not in ("query", "episode") or tool["replay"] not in ("safe", "never"):
            raise ValueError("authorization tool query/replay declaration is invalid")
        if tool["io_effect"] not in ("local_read", "external_or_mixed", "unknown"):
            raise ValueError("authorization tool IO declaration is invalid")
        if scope == "material_only" or (scope == "local_only" and tool["io_effect"] != "local_read"):
            raise ValueError("authorization tool violates the registry IO ceiling")
        if not isinstance(tool["parameters"], dict):
            raise ValueError("authorization tool parameters must be an object")
        produces = tool["produces"]
        if (not isinstance(produces, list) or any(not isinstance(p, str) or not p for p in produces)
                or produces != sorted(set(produces))):
            raise ValueError("authorization tool produces must be canonical strings")
        if tool["min_window_seconds"] is not None and not _seconds(tool["min_window_seconds"]):
            raise ValueError("authorization tool window must be finite nonnegative seconds")
        names.append(name)
    if names != sorted(set(names)):
        raise ValueError("authorization tool names must be unique and sorted")
    return registry


@dataclass(frozen=True)
class EpisodeAuthorizationSnapshot:
    episode_id: str
    contract: ResearchTaskContract
    policy: ResearchPolicy
    information_cutoff: InformationCutoff
    trace_parent_id: str
    registry: Mapping[str, object]
    registry_sha256: str

    def to_dict(self) -> dict[str, object]:
        return _json_copy({
            "schema_version": _VERSION, "kind": _KIND, "episode_id": self.episode_id,
            "contract": _contract_payload(self.contract), "policy": asdict(self.policy),
            "information_cutoff": self.information_cutoff.to_dict(),
            "trace_parent_id": self.trace_parent_id,
            "registry": self.registry, "registry_sha256": self.registry_sha256,
        }, path="authorization")

    @classmethod
    def from_dict(cls, payload: object, *, episode_id: str) -> EpisodeAuthorizationSnapshot:
        raw = _object(_json_copy(payload, path="authorization"), _FIELDS, "snapshot")
        if type(raw["schema_version"]) is not int or raw["schema_version"] != _VERSION or raw["kind"] != _KIND:
            raise ValueError("unsupported authorization snapshot version/kind")
        if not isinstance(episode_id, str) or not episode_id.strip() or episode_id != episode_id.strip() or raw["episode_id"] != episode_id:
            raise ValueError("authorization episode identity mismatch")
        contract = _parse_contract(raw["contract"], episode_id=episode_id)
        policy_raw = _object(raw["policy"], frozenset({"tier", "max_steps", "total_seconds", "synthesis_reserve"}), "policy")
        if not isinstance(policy_raw["tier"], str) or policy_raw["tier"] not in RESEARCH_TIERS:
            raise ValueError("authorization policy tier is invalid")
        if type(policy_raw["max_steps"]) is not int or policy_raw["max_steps"] < 0:
            raise ValueError("authorization policy steps must be a nonnegative integer")
        if not all(_seconds(policy_raw[key]) for key in ("total_seconds", "synthesis_reserve")):
            raise ValueError("authorization policy seconds must be finite and nonnegative")
        # A current deep policy can accompany a standard original contract; mode
        # promotion deliberately keeps those separate. Never recalculate for_tier.
        policy = ResearchPolicy(**policy_raw)
        cutoff_raw = _object(raw["information_cutoff"], frozenset({"as_of_date", "source"}), "cutoff")
        if not isinstance(cutoff_raw["as_of_date"], str) or not isinstance(cutoff_raw["source"], str):
            raise ValueError("authorization cutoff date/source must be strings")
        cutoff = InformationCutoff(date.fromisoformat(cutoff_raw["as_of_date"]), cutoff_raw["source"])
        if _json(cutoff_raw) != _json(cutoff.to_dict()):
            raise ValueError("authorization cutoff is noncanonical")
        if not isinstance(raw["trace_parent_id"], str):
            raise ValueError("authorization trace parent must be a string")
        registry = _validate_registry(raw["registry"], contract)
        if raw["registry_sha256"] != _digest(registry):
            raise ValueError("authorization registry declaration digest mismatch")
        return cls(episode_id, contract, policy, cutoff, raw["trace_parent_id"],
                   _json_freeze(registry, path="authorization.registry"), raw["registry_sha256"])


def capture_authorization_snapshot(context: ResearchRunContext, registry: ResearchToolRegistry) -> dict[str, object]:
    """Capture the effective, episode-bound registry without serializing runners."""
    effective = registry.for_context(context)
    manifest = {
        "read_scope": effective.read_scope,
        "tools": [{
            "name": spec.name, "capability": spec.capability, "description": spec.description,
            "contract": spec.contract, "cost": spec.cost, "freshness": spec.freshness,
            "query_scope": spec.query_scope, "parameters": spec.parameters,
            "produces": sorted(spec.produces), "min_window_seconds": spec.min_window_seconds,
            "replay": spec.replay, "io_effect": spec.io_effect,
        } for spec in effective.authorized_specs(context.contract.allowed_capabilities)],
    }
    value = EpisodeAuthorizationSnapshot(
        context.contract.task_id, context.contract, context.policy, context.information_cutoff,
        context.trace_parent_id, manifest, _digest(manifest),
    ).to_dict()
    # Encoding/validation failure is required-persistence failure at the caller.
    return EpisodeAuthorizationSnapshot.from_dict(value, episode_id=context.contract.task_id).to_dict()


def validate_current_authorization(
    payload: object, *, context: ResearchRunContext, registry: ResearchToolRegistry,
) -> None:
    """Exact match only. No merging, migration, fresh budget, IO or callable trust."""
    saved = EpisodeAuthorizationSnapshot.from_dict(payload, episode_id=context.contract.task_id)
    current = capture_authorization_snapshot(context, registry)
    if _json(saved.to_dict()) != _json(current):
        raise ValueError("current authorization does not match the captured contract/policy/registry")
    if saved.contract.material_contract is not None and saved.contract.material_contract.needs_clarification:
        raise ValueError("authorization material boundary remains unresolved")
