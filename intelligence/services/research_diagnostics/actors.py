"""actor_group 分组：``user_original / agent_generated / user_after_agent / unknown_origin``。

规格 §3：按**作者与曝光收据**分组。看后采纳 / 修改都保留原 agent 引用；**文本相似不证明看过**，
这里根本不看正文。未知来源不算独立用户能力——所以缺作者字段时落 ``unknown_origin``，
不默认成用户。

判定表（``ActorInfo`` → group）：

| author | agent_refs 或曝光收据 | group |
|---|---|---|
| agent / system | 任意 | agent_generated |
| user | 有（记录自带 agent 引用，或有早于记录时刻的曝光收据） | user_after_agent |
| user | 无 | user_original |
| unknown | 任意 | unknown_origin |

曝光收据（``ProcessReceipt.kind == "exposure"``）要指向本对象或本对象保留的 agent 引用，且
发生时刻不晚于记录时刻；晚于记录时刻的曝光不能倒过来证明「写之前看过」。
"""

from __future__ import annotations

from intelligence.services.research_diagnostics.clock import known_by
from intelligence.services.research_diagnostics.contracts import ProcessReceipt, ProcessRecord


def exposure_refs_for(record: ProcessRecord, receipts: list[ProcessReceipt]) -> tuple[str, ...]:
    """早于（或同日于）记录时刻、且指向本对象或其 agent 引用的曝光收据 id。"""
    targets = {record.object_ref.identity, *record.actor.agent_refs}
    if record.object_ref.id:
        targets.add(record.object_ref.id)
    if record.object_ref.ref:
        targets.add(record.object_ref.ref)
    out: list[str] = []
    for r in receipts:
        if r.kind != "exposure":
            continue
        target = str(r.payload.get("target_ref") or "")
        same_object = r.object_ref is not None and r.object_ref.identity == record.object_ref.identity
        if target not in targets and not same_object:
            continue
        if known_by(r.occurred_at, record.recorded_at.value) is False:
            continue
        out.append(r.receipt_id)
    return tuple(sorted(out))


def actor_group_of(record: ProcessRecord, receipts: list[ProcessReceipt]) -> tuple[str, tuple[str, ...]]:
    """返回 ``(actor_group, 依据 refs)``。依据 refs 进 finding.evidence_refs，让分组可追溯。"""
    author = record.actor.author
    evidence = list(record.actor.evidence)
    if author in ("agent", "system"):
        return "agent_generated", tuple(evidence)
    if author == "unknown":
        return "unknown_origin", tuple(evidence)
    exposures = tuple(sorted({*record.actor.exposure_refs, *exposure_refs_for(record, receipts)}))
    if record.actor.agent_refs or exposures:
        return "user_after_agent", tuple(evidence) + tuple(record.actor.agent_refs) + exposures
    return "user_original", tuple(evidence)
