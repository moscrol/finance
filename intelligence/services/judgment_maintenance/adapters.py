"""旧对象 → 合同的纯适配（spec 01 §2 / §7 第 4 步）。

输入是**已由旧读取器加载好的 dict**（``checkpoints.load_checkpoints`` / ``judgments.load_judgments`` /
``scenario_trees.load`` + ``current_state``）；本模块不开文件、不推断生产根、不写任何台账。

它只做三件事：

1. 复用旧身份造 ``ObjectRef``（无原生版本用 ``content_sha256:`` + 原不可变行哈希；无 id 用可验证旧行 ref 代位）；
2. 从**可验证的结构化字段**造候选绑定（foresight 判断行的 ``evidence[{ref,hash}]``、情景树 ``realized_path``
   的 ``evidence_refs`` 与子节点确定性条件）；checkpoint 行本身没有证据引用，只能给 gap；
3. 把存量记录缺的东西（id / 时间 / 证据 / 只有散文条件）如实列成 gap，不补、不猜。

候选绑定仍要由用户在产品里明确确认（06 存 created_at 为真实确认时刻）；这里返回的是可供确认的草稿。
"""

from __future__ import annotations

from typing import Any, Mapping

from intelligence.services import checkpoints as checkpoints_svc
from intelligence.services import scenario_trees as st
from intelligence.services.judgment_maintenance.contracts import (
    BINDING_SCHEMA_VERSION,
    DependencyBinding,
    EvidenceVersion,
    Gap,
    ObjectRef,
    parse_binding,
    parse_object_ref,
    sha256_hex,
)

CONTENT_HASH_PREFIX = "content_sha256:"


def record_content_hash(record: Mapping[str, Any]) -> str:
    """原不可变记录的内容哈希（键排序的 canonical JSON）。"""
    return CONTENT_HASH_PREFIX + sha256_hex(dict(record))


def _scope(record: Mapping[str, Any], extra: Mapping[str, str] | None) -> dict[str, str]:
    scope: dict[str, str] = {k: v for k, v in (extra or {}).items() if isinstance(v, str) and v}
    if record.get("session_id"):
        scope.setdefault("session_id", str(record["session_id"]))
    return scope


def object_ref_from_checkpoint(record: Mapping[str, Any], *, owner_user_id: str, scope: Mapping[str, str] | None = None) -> ObjectRef:
    content = record_content_hash(record)
    rid = str(record.get("id")).strip() if record.get("id") else None
    ref = f"checkpoints.jsonl:{rid}" if rid else f"checkpoints.jsonl:{content}"
    sc = _scope(record, scope)
    sc.setdefault("object_type", checkpoints_svc.object_type_of(dict(record)))
    return parse_object_ref(
        {"kind": "checkpoint", "id": rid, "namespace": "checkpoints", "version_or_hash": content, "ref": ref, "scope": sc},
        owner_user_id=owner_user_id,
        where="checkpoint",
    )


def object_ref_from_judgment(record: Mapping[str, Any], *, owner_user_id: str, scope: Mapping[str, str] | None = None) -> ObjectRef:
    content = record_content_hash(record)
    rid = str(record.get("id")).strip() if record.get("id") else None
    ref = f"judgments.jsonl:{rid}" if rid else f"judgments.jsonl:{content}"
    sc = _scope(record, scope)
    if record.get("record_type"):
        sc.setdefault("record_type", str(record["record_type"]))
    return parse_object_ref(
        {"kind": "judgment", "id": rid, "namespace": "judgments", "version_or_hash": content, "ref": ref, "scope": sc},
        owner_user_id=owner_user_id,
        where="judgment",
    )


def object_ref_from_scenario_tree(state: Mapping[str, Any], *, owner_user_id: str, scope: Mapping[str, str] | None = None) -> ObjectRef:
    """树的身份用树本体（去掉随逐日解析变化的 realized_path / status）算内容哈希。"""
    body = {k: v for k, v in state.items() if k not in ("realized_path", "status")}
    content = record_content_hash(body)
    tid = str(state.get("id")).strip() if state.get("id") else None
    ref = f"scenario_trees.jsonl:{tid}" if tid else f"scenario_trees.jsonl:{content}"
    sc = _scope(state, scope)
    return parse_object_ref(
        {"kind": "scenario_tree", "id": tid, "namespace": "scenario_trees", "version_or_hash": content, "ref": ref, "scope": sc},
        owner_user_id=owner_user_id,
        where="scenario_tree",
    )


def legacy_gaps(record: Mapping[str, Any], object_ref: ObjectRef, *, checked_at: str) -> list[Gap]:
    """存量记录缺什么就报什么：无 id、无登记时刻、无证据引用。"""
    gaps: list[Gap] = []
    if not record.get("id"):
        gaps.append(Gap("object_id_missing", object_ref.ref, checked_at, False, "存量行没有 id，只能用内容哈希定位；不能声称完整历史复现"))
    if not (record.get("ts") or record.get("recorded_at")):
        gaps.append(Gap("time_metadata_missing", object_ref.ref, checked_at, False, "存量行没有登记时刻，原判断的知识截止不可判"))
    return gaps


def _binding_dict(
    *,
    binding_id: str,
    owner_user_id: str,
    object_ref: ObjectRef,
    refs: list[str],
    hashes: dict[str, str | None],
    baseline_cutoff: str,
    created_at: str,
    origin: str,
    conditions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": BINDING_SCHEMA_VERSION,
        "binding_id": binding_id,
        "binding_version": 1,
        "owner_user_id": owner_user_id,
        "object_ref": object_ref.to_dict(),
        "baseline_evidence_refs": refs,
        "baseline_source_hashes": hashes,
        "baseline_cutoff": baseline_cutoff,
        "created_at": created_at,
        "binding_origin": origin,
        "conditions": conditions,
    }


def candidate_binding_from_judgment(
    record: Mapping[str, Any],
    *,
    owner_user_id: str,
    binding_id: str,
    created_at: str,
    baseline_cutoff: str,
    scope: Mapping[str, str] | None = None,
) -> tuple[DependencyBinding | None, list[Gap]]:
    """foresight 判断行的 ``evidence: [{ref, hash}]`` 是可核实的结构化输出 → 候选绑定；纯 memo 行只有 gap。

    ``invalidation`` 是自然语言，**不**转成条件——列一条 gap 说明为什么它不能被机器判定。
    """
    object_ref = object_ref_from_judgment(record, owner_user_id=owner_user_id, scope=scope)
    gaps = legacy_gaps(record, object_ref, checked_at=baseline_cutoff)
    refs: list[str] = []
    hashes: dict[str, str | None] = {}
    for entry in record.get("evidence") or []:
        if not isinstance(entry, Mapping):
            continue
        ref = str(entry.get("ref") or "").strip()
        if not ref or ref in hashes:
            continue
        raw_hash = entry.get("hash") or entry.get("source_hash")
        refs.append(ref)
        hashes[ref] = str(raw_hash).strip() if raw_hash else None
    invalidation = record.get("invalidation")
    if isinstance(invalidation, str) and invalidation.strip():
        gaps.append(Gap("condition_not_deterministic", object_ref.ref, baseline_cutoff, False, "invalidation 是自然语言证伪条件，不能被编译为确定性条件；只能人工复核"))
    if not refs:
        gaps.append(Gap("dependency_unbound", object_ref.ref, baseline_cutoff, True, "原记录没有可验证的证据引用；需用户今天明确绑定后才能维护"))
        return None, gaps
    if any(h is None for h in hashes.values()):
        gaps.append(Gap("dependency_unbound", object_ref.ref, baseline_cutoff, True, "部分证据引用没有哈希：这些依赖只能从现在起跟踪，说不出「变了没有」"))
    binding = parse_binding(
        _binding_dict(
            binding_id=binding_id,
            owner_user_id=owner_user_id,
            object_ref=object_ref,
            refs=refs,
            hashes=hashes,
            baseline_cutoff=baseline_cutoff,
            created_at=created_at,
            origin="verified_structured_output",
            conditions=[],
        ),
        owner_user_id=owner_user_id,
        where="candidate_binding",
    )
    return binding, gaps


def candidate_binding_from_checkpoint(
    record: Mapping[str, Any],
    *,
    owner_user_id: str,
    baseline_cutoff: str,
    scope: Mapping[str, str] | None = None,
) -> tuple[None, list[Gap]]:
    """checkpoint 行只有 claim / due / metric，没有证据引用：不能自动绑定，只给 gap。

    ``metric`` 是回检规格不是依赖；它的取数走 checkpoint_resolvers，本包不调用（§4 第 3 条）。
    """
    object_ref = object_ref_from_checkpoint(record, owner_user_id=owner_user_id, scope=scope)
    gaps = legacy_gaps(record, object_ref, checked_at=baseline_cutoff)
    detail = "checkpoint 行不含证据引用；需用户明确绑定"
    if record.get("metric"):
        detail += f"（metric.type={record['metric'].get('type') if isinstance(record.get('metric'), Mapping) else '?'} 只引用旧 verdict，不在本包取数）"
    gaps.append(Gap("dependency_unbound", object_ref.ref, baseline_cutoff, True, detail))
    return None, gaps


def verdict_evidence_versions(checkpoint_id: str, verdicts: list[Mapping[str, Any]]) -> list[EvidenceVersion]:
    """把某个 checkpoint 已有的回检打分转成可绑定的冻结版本（只引用旧 verdict，不重算）。"""
    out: list[EvidenceVersion] = []
    for v in verdicts:
        if str(v.get("id")) != checkpoint_id or not v.get("checked_at"):
            continue
        checked_at = str(v["checked_at"])
        out.append(
            EvidenceVersion(
                ref=f"verdicts.jsonl:{checkpoint_id}@{checked_at}",
                source_hash=record_content_hash(v),
                valid_from=checked_at[:10],
                recorded_at=checked_at,
                derivation="deterministic",
                namespace="verdicts",
            )
        )
    return out


def candidate_binding_from_scenario_tree(
    state: Mapping[str, Any],
    *,
    owner_user_id: str,
    binding_id: str,
    created_at: str,
    baseline_cutoff: str,
    include_conditions: bool = True,
    scope: Mapping[str, str] | None = None,
) -> tuple[DependencyBinding | None, list[Gap]]:
    """情景树：``realized_path`` 的 evidence_refs 作依赖（树只存 ref 不存 hash → 全部 null），
    当前节点的子条件作 role=review 的确定性条件（角色不猜升降级，只标复核）。"""
    object_ref = object_ref_from_scenario_tree(state, owner_user_id=owner_user_id, scope=scope)
    gaps = legacy_gaps(state, object_ref, checked_at=baseline_cutoff)
    refs: list[str] = []
    path = list(state.get("realized_path") or [])
    for step in path:
        for ref in (step.get("evidence_refs") or []) if isinstance(step, Mapping) else []:
            r = str(ref).strip()
            if r and r not in refs:
                refs.append(r)
    conditions: list[dict[str, Any]] = []
    if include_conditions and path:
        last_node = str(path[-1].get("node_id")) if isinstance(path[-1], Mapping) else None
        entity = str((state.get("entity_ids") or [""])[0])
        for node in state.get("nodes") or []:
            if not isinstance(node, Mapping) or str(node.get("parent")) != last_node:
                continue
            condition = node.get("condition")
            if condition is None or condition == st.OTHERWISE or isinstance(condition, str):
                continue
            conditions.append(
                {
                    "condition_id": f"{state.get('id')}:{node.get('node_id')}",
                    "role": "review",
                    "expression": condition,
                    "entity_id": entity,
                    "label_version": None,
                }
            )
    if not refs:
        gaps.append(Gap("dependency_unbound", object_ref.ref, baseline_cutoff, True, "树尚未走过带证据引用的步骤；没有可绑定的依赖"))
        return None, gaps
    gaps.append(Gap("dependency_unbound", object_ref.ref, baseline_cutoff, True, "树只保存 evidence_refs 不保存哈希：这些依赖只能从现在起跟踪"))
    binding = parse_binding(
        _binding_dict(
            binding_id=binding_id,
            owner_user_id=owner_user_id,
            object_ref=object_ref,
            refs=refs,
            hashes={r: None for r in refs},
            baseline_cutoff=baseline_cutoff,
            created_at=created_at,
            origin="verified_structured_output",
            conditions=conditions,
        ),
        owner_user_id=owner_user_id,
        where="candidate_binding",
    )
    return binding, gaps


__all__ = [
    "CONTENT_HASH_PREFIX",
    "candidate_binding_from_checkpoint",
    "candidate_binding_from_judgment",
    "candidate_binding_from_scenario_tree",
    "legacy_gaps",
    "object_ref_from_checkpoint",
    "object_ref_from_judgment",
    "object_ref_from_scenario_tree",
    "record_content_hash",
    "verdict_evidence_versions",
]
