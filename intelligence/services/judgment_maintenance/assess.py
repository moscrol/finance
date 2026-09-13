"""差分与条件判定：``assess()``（spec 01 §3–§4）。纯函数，不读文件 / 库 / 网络。

时钟纪律（§4）：

1. 先按知识截止过滤版本（``recorded_at`` ≤ C；没有 recorded_at 的按 ``valid_from`` 放置并降档），
   再在剩下的版本里选 ``as_of`` 那天有效的那一个。
2. 前态固定为绑定的基线 ref / hash；``created_at`` 之前不生成维护样本。
3. 后知的更正只产生当前项，不改历史截止下的回放——所以同一条依赖会沿知识日走出一条项链：
   早先的项标 ``superseded``，最新的项带 ``supersedes_item_id`` 指回去。
4. C > as_of 标 ``hindsight``，pit 永远不是 strict。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from intelligence.services.judgment_maintenance import conditions as cond_mod
from intelligence.services.judgment_maintenance.contracts import (
    ITEM_ID_PREFIX,
    REPORT_ID_PREFIX,
    SCHEMA_VERSION,
    BindingCondition,
    DependencyBinding,
    EvidenceVersion,
    Gap,
    MaintenanceContractError,
    MaintenanceItem,
    MaintenancePolicy,
    MaintenanceReport,
    canonical_json,
    day_of,
    parse_binding,
    parse_evidence_version,
    parse_observation,
    parse_policy,
    sha256_hex,
    short_hash,
    stamp_grade,
    validate_date,
    validate_owner,
    validate_stamp,
    weakest_pit,
)

# 状态种类 → (change_type, reason_code, epistemic_state, action)
_KIND_TO_ITEM: dict[str, tuple[str, str, str, str]] = {
    "content_changed": ("content_changed", "hash_changed", "requires_review", "review_evidence"),
    "source_corrected": ("source_corrected", "explicit_supersession", "requires_review", "review_evidence"),
    "expired": ("source_expired", "validity_ended", "unknown", "restore_evidence"),
    "unresolved": ("dependency_missing", "ref_unresolved", "unknown", "restore_evidence"),
    "unchanged": ("unchanged", "no_change", "observed", "none"),
}
# 条件触发后的建议动作按 condition_role 分流：升级 / 降级 / 放弃都要重新判断，复核只看证据。
_ROLE_TO_ACTION = {"upgrade": "rejudge", "downgrade": "rejudge", "abandon": "rejudge", "review": "review_evidence"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _as_list(value: Any, where: str) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    raise MaintenanceContractError("invalid_type", where, "需要列表")


# --------------------------------------------------------------------------- #
# 版本放置与替代链
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class _Placed:
    version: EvidenceVersion
    known_day: str  # 系统何时知道（recorded_at 的日期）；没有就退到 valid_from
    knowledge_grade: str  # strict：recorded_at 是带时区的完整时刻；trade_date_only：只知道哪一天


def _place(versions: list[EvidenceVersion], *, checked_at: str) -> tuple[dict[str, list[_Placed]], list[Gap]]:
    by_ref: dict[str, list[_Placed]] = {}
    gaps: list[Gap] = []
    for v in versions:
        if v.recorded_at:
            # 档位按 recorded_at 的实际精度算：纯日期 / 无时区的时刻只到 trade_date_only（spec 01 §4）。
            placed = _Placed(v, day_of(v.recorded_at) or "", stamp_grade(v.recorded_at))
        elif v.valid_from:
            placed = _Placed(v, v.valid_from, "trade_date_only")
        else:
            gaps.append(
                Gap(
                    reason="time_metadata_missing",
                    ref=v.ref,
                    checked_at=checked_at,
                    retryable=True,
                    detail="版本既无 recorded_at 也无 valid_from，放不到时间轴上，不参与判定",
                )
            )
            continue
        by_ref.setdefault(v.ref, []).append(placed)
    return by_ref, gaps


def _chain_refs(root_ref: str, by_supersedes: dict[str, set[str]], *, checked_at: str, binding_id: str) -> tuple[list[str], list[Gap]]:
    """从基线 ref 沿 ``supersedes_ref`` 反向链接（谁替代了它）走出整条替代链；成环记 gap 并停。"""
    refs = [root_ref]
    seen = {root_ref}
    gaps: list[Gap] = []
    queue = [root_ref]
    while queue:
        current = queue.pop(0)
        for nxt in sorted(by_supersedes.get(current, set())):
            if nxt in seen:
                gaps.append(
                    Gap(
                        reason="supersession_cycle",
                        ref=nxt,
                        checked_at=checked_at,
                        retryable=False,
                        detail=f"{nxt} 在替代链中再次出现，链在此截断",
                        binding_id=binding_id,
                    )
                )
                continue
            seen.add(nxt)
            refs.append(nxt)
            queue.append(nxt)
    return refs, gaps


@dataclass(frozen=True)
class _State:
    kind: str  # unchanged | content_changed | source_corrected | expired | unresolved
    current: _Placed | None
    ambiguous: bool = False

    def signature(self) -> tuple[Any, ...]:
        if self.current is None:
            return (self.kind, None, None)
        return (self.kind, self.current.version.ref, self.current.version.source_hash)


def _sort_key(p: _Placed) -> tuple[str, str, str]:
    # 先看 as_of 那天谁在生效（valid_from 最晚），再看谁更晚被记录（后知更正压前），最后哈希序兜底确定性。
    return (p.version.valid_from or p.known_day, p.version.recorded_at or "", p.version.source_hash or "")


def _state_at(root_ref: str, baseline_hash: str | None, chain_refs: list[str], by_ref: dict[str, list[_Placed]], *, as_of: str, day: str) -> _State:
    placed = [p for r in chain_refs for p in by_ref.get(r, []) if p.known_day <= day]
    if not placed:
        return _State("unresolved", None)
    # 显式更正一旦在 as_of 生效，被替代的那个 ref 就永久退场：后继自己再失效也不能把它复活成有效依据，
    # 否则「来源已被撤回」会表现成「没有需要维护的问题」（spec 01 §4：更正链断裂为 gap，不默认回退祖先）。
    # 只认已经生效的更正——后继若在 as_of 之后才成立，当天仍该看旧版本。
    retired_refs = {
        p.version.supersedes_ref
        for p in placed
        if p.version.supersedes_ref and (p.version.valid_from or p.known_day) <= as_of
    }
    live: list[_Placed] = []
    ended: list[_Placed] = []
    for p in placed:
        v = p.version
        if v.expired_at and (day_of(v.expired_at) or "") <= day:
            ended.append(p)
            continue
        effective_from = v.valid_from or p.known_day
        if effective_from > as_of:
            continue  # as_of 那天还不成立
        if v.valid_to and v.valid_to < as_of:
            ended.append(p)
            continue
        if v.ref in retired_refs:
            ended.append(p)  # 已被显式更正：留在 ended 里只为让「整条链都没了」时还能指出最后一版是什么
            continue
        live.append(p)
    if not live:
        if ended:
            return _State("expired", max(ended, key=_sort_key))
        return _State("unresolved", None)
    current = max(live, key=_sort_key)
    ambiguous = any(
        p is not current and _sort_key(p)[:2] == _sort_key(current)[:2] and p.version.source_hash != current.version.source_hash
        for p in live
    )
    if current.version.ref == root_ref:
        kind = "unchanged" if current.version.source_hash == baseline_hash else "content_changed"
    else:
        kind = "source_corrected"
    return _State(kind, current, ambiguous)


def _baseline(ref: str, baseline_hash: str | None, by_ref: dict[str, list[_Placed]], *, baseline_cutoff: str) -> tuple[EvidenceVersion, _Placed | None]:
    """基线版本：优先基线截止前、与基线哈希一致的那条；找不到就用占位（哈希已知、来源时间未知）。"""
    candidates = [p for p in by_ref.get(ref, []) if baseline_hash is not None and p.version.source_hash == baseline_hash]
    within = [p for p in candidates if p.known_day <= baseline_cutoff]
    pool = within or candidates
    if pool:
        chosen = min(pool, key=lambda p: (p.known_day, p.version.recorded_at or "", p.version.source_hash or ""))
        return chosen.version, chosen
    return EvidenceVersion(ref=ref, source_hash=baseline_hash, derivation="unknown"), None


# --------------------------------------------------------------------------- #
# 项构造
# --------------------------------------------------------------------------- #
def _item_id(dedup_key: str) -> str:
    return ITEM_ID_PREFIX + short_hash(dedup_key)


def _dedup_key(
    *,
    owner: str,
    binding: DependencyBinding,
    dependency_ref: str | None,
    before_hash: str | None,
    after_ref: str | None,
    after_hash: str | None,
    change_type: str,
    reason_code: str,
    condition_ref: str | None = None,
    expression_digest: str | None = None,
    window: str | None = None,
) -> str:
    return canonical_json(
        {
            "owner_user_id": owner,
            "object": list(binding.object_ref.identity()),
            "binding_id": binding.binding_id,
            "binding_version": binding.binding_version,
            "dependency_ref": dependency_ref,
            "before_hash": before_hash,
            "after_ref": after_ref,
            "after_hash": after_hash,
            "change_type": change_type,
            "reason_code": reason_code,
            "condition_ref": condition_ref,
            "expression_digest": expression_digest,
            "window": window,
        }
    )


def _dependency_items(
    binding: DependencyBinding,
    ref: str,
    by_ref: dict[str, list[_Placed]],
    by_supersedes: dict[str, set[str]],
    place_gaps: list[Gap],
    *,
    owner: str,
    as_of: str,
    cutoff: str,
    hindsight: bool,
    policy: MaintenancePolicy,
) -> tuple[list[MaintenanceItem], str, list[Gap], bool]:
    """一条依赖 → (项链, 该依赖的 pit, 报告级 gap, 是否 unchanged)。"""
    baseline_hash = binding.baseline_source_hashes[ref]
    chain, chain_gaps = _chain_refs(ref, by_supersedes, checked_at=cutoff, binding_id=binding.binding_id)
    ref_time_gaps = [g for g in place_gaps if g.ref == ref]
    before, before_placed = _baseline(ref, baseline_hash, by_ref, baseline_cutoff=binding.baseline_cutoff)
    common_gaps: list[Gap] = list(chain_gaps) + ref_time_gaps
    # 只有「源里认得这个 ref、却没见过基线哈希」才算基线版本未知；ref 完全没版本由 ref_unresolved 说明。
    if baseline_hash is not None and before_placed is None and by_ref.get(ref):
        common_gaps.append(
            Gap(
                reason="baseline_version_unknown",
                ref=ref,
                checked_at=cutoff,
                retryable=False,
                detail="绑定时的基线哈希未出现在冻结版本集合中：只能比对哈希，说不出基线版本何时被记录",
                binding_id=binding.binding_id,
            )
        )

    def build(day: str, state: _State, *, status: str, supersedes: str | None, override: tuple[str, str, str, str] | None = None) -> MaintenanceItem:
        change_type, reason_code, epistemic, action = override or _KIND_TO_ITEM[state.kind]
        current: tuple[EvidenceVersion, ...] = (state.current.version,) if state.current else ()
        after_ref = state.current.version.ref if state.current else None
        after_hash = state.current.version.source_hash if state.current else None
        gaps: list[Gap] = list(common_gaps)
        if reason_code == "dependency_unbound":
            gaps.append(Gap("dependency_unbound", ref, cutoff, True, "绑定时明知没有基线哈希：从现在起只能跟踪当前版本，说不出「变了没有」", binding.binding_id))
        elif reason_code == "ref_unresolved":
            gaps.append(Gap("ref_unresolved", ref, cutoff, True, f"截止 {day} 未见该引用（及其替代链）任何在 {as_of} 生效的版本", binding.binding_id))
        elif state.kind == "expired":
            gaps.append(Gap("validity_ended", ref, cutoff, True, f"最后已知版本在 {as_of} 已失效或已被撤回，且无替代版本", binding.binding_id))
        if state.ambiguous:
            gaps.append(Gap("ambiguous_version_order", ref, cutoff, True, "同一 valid_from / recorded_at 下有多个不同哈希的版本，按哈希序取最后一个", binding.binding_id))
        if reason_code in ("dependency_unbound", "ref_unresolved", "time_metadata_missing"):
            pit = "unverifiable"
        else:
            grades = ["trade_date_only" if hindsight else "strict", before_placed.knowledge_grade if before_placed else "trade_date_only"]
            if state.current:
                grades.append(state.current.knowledge_grade)
            pit = weakest_pit(grades)
        key = _dedup_key(
            owner=owner,
            binding=binding,
            dependency_ref=ref,
            before_hash=baseline_hash,
            after_ref=after_ref,
            after_hash=after_hash,
            change_type=change_type,
            reason_code=reason_code,
        )
        item_version = short_hash(
            {
                "before": [before.to_dict()],
                "current": [v.to_dict() for v in current],
                "binding_id": binding.binding_id,
                "binding_version": binding.binding_version,
                "change_type": change_type,
                "reason_code": reason_code,
            }
        )
        return MaintenanceItem(
            id=_item_id(key),
            item_version=item_version,
            owner_user_id=owner,
            object_ref=binding.object_ref,
            before=(before,),
            current=current,
            change_type=change_type,
            reason_code=reason_code,
            epistemic_state=epistemic,
            condition_result=None,
            as_of=as_of,
            knowledge_cutoff=cutoff,
            pit_grade=pit,
            gaps=tuple(gaps),
            action=action,
            status=status,
            dedup_key=key,
            binding_id=binding.binding_id,
            binding_version=binding.binding_version,
            dependency_ref=ref,
            supersedes_item_id=supersedes,
            first_known_day=day,
        )

    if baseline_hash is None:
        state = _state_at(ref, None, chain, by_ref, as_of=as_of, day=cutoff)
        item = build(cutoff, state, status="open", supersedes=None, override=("dependency_missing", "dependency_unbound", "unknown", "restore_evidence"))
        return [item], "unverifiable", chain_gaps + ref_time_gaps, False

    start = binding.created_day
    # 知识轴上的转折日：绑定生效日、每个版本被记录的日子、每次撤回生效的日子、报告截止日。
    days = {start, cutoff}
    for r in chain:
        for p in by_ref.get(r, []):
            if start < p.known_day <= cutoff:
                days.add(p.known_day)
            expired_day = day_of(p.version.expired_at)
            if expired_day and start < expired_day <= cutoff:
                days.add(expired_day)
    timeline: list[tuple[str, _State]] = []
    for day in sorted(days):
        state = _state_at(ref, baseline_hash, chain, by_ref, as_of=as_of, day=day)
        if not timeline or state.signature() != timeline[-1][1].signature():
            timeline.append((day, state))
    # 有版本却全都放不到时间轴上：原因是「时间元数据缺失」而不是「引用没解析到」。
    unresolved_override = ("dependency_missing", "time_metadata_missing", "unknown", "restore_evidence") if ref_time_gaps else None
    items: list[MaintenanceItem] = []
    previous_id: str | None = None
    for index, (day, state) in enumerate(timeline):
        is_last = index == len(timeline) - 1
        if state.kind == "unchanged":
            if is_last and policy.emit_unchanged:
                items.append(build(day, state, status="open", supersedes=previous_id))
            continue
        override = unresolved_override if state.kind == "unresolved" else None
        item = build(day, state, status="open" if is_last else "superseded", supersedes=previous_id, override=override)
        items.append(item)
        previous_id = item.id
    final_day, final_state = timeline[-1]
    if final_state.kind == "unresolved":
        dep_pit = "unverifiable"
    else:
        grades = ["trade_date_only" if hindsight else "strict", before_placed.knowledge_grade if before_placed else "trade_date_only"]
        if final_state.current:
            grades.append(final_state.current.knowledge_grade)
        dep_pit = weakest_pit(grades)
    return items, dep_pit, chain_gaps + ref_time_gaps, final_state.kind == "unchanged"


def _condition_item(
    binding: DependencyBinding,
    cond: BindingCondition,
    preds: tuple[Any, ...],
    index: cond_mod.ObservationIndex,
    *,
    owner: str,
    as_of: str,
    cutoff: str,
    hindsight: bool,
) -> MaintenanceItem:
    evaluation = cond_mod.evaluate_condition(preds, cond, index, as_of=as_of, knowledge_cutoff=cutoff, hindsight=hindsight, binding_id=binding.binding_id)
    reason = {"true": "condition_true", "false": "condition_false", "unknown": "condition_unknown"}[evaluation.result]
    epistemic = "observed" if evaluation.result in ("true", "false") else "unknown"
    action = _ROLE_TO_ACTION[cond.role] if evaluation.result == "true" else "none"
    expression_digest = short_hash(cond.expression)
    key = _dedup_key(
        owner=owner,
        binding=binding,
        dependency_ref=None,
        before_hash=None,
        after_ref=None,
        after_hash=None,
        change_type="condition_evaluated",
        reason_code=reason,
        condition_ref=cond.condition_id,
        expression_digest=expression_digest,
        window=as_of,
    )
    item_version = short_hash(
        {
            "expression": cond.expression,
            "entity_id": cond.entity_id,
            "role": cond.role,
            "binding_id": binding.binding_id,
            "binding_version": binding.binding_version,
            "evaluation": evaluation.to_dict(),
        }
    )
    return MaintenanceItem(
        id=_item_id(key),
        item_version=item_version,
        owner_user_id=owner,
        object_ref=binding.object_ref,
        before=(),
        current=(),
        change_type="condition_evaluated",
        reason_code=reason,
        epistemic_state=epistemic,
        condition_result=evaluation.result,
        as_of=as_of,
        knowledge_cutoff=cutoff,
        pit_grade=evaluation.pit_grade,
        gaps=evaluation.gaps,
        action=action,
        status="open",
        dedup_key=key,
        binding_id=binding.binding_id,
        binding_version=binding.binding_version,
        condition_ref=cond.condition_id,
        condition_role=cond.role,
        condition_evaluation=evaluation.to_dict(),
        first_known_day=cutoff,
    )


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def _dedupe_sorted(values: list[Any]) -> list[Any]:
    seen: set[tuple[Any, ...]] = set()
    out: list[Any] = []
    for v in sorted(values, key=lambda x: canonical_json(x.to_dict())):
        key = v.dedupe_key()
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


def _gap_key(g: Gap) -> tuple[Any, ...]:
    return (g.reason, g.ref or "", g.binding_id or "", g.condition_ref or "", g.checked_at, g.retryable, g.detail)


def _item_sort_key(it: MaintenanceItem) -> tuple[Any, ...]:
    return (it.object_ref.identity(), it.binding_id, it.binding_version, it.dependency_ref or "", it.condition_ref or "", it.knowledge_cutoff, it.id)


def assess(
    *,
    owner_user_id: str,
    as_of: str,
    knowledge_cutoff: str,
    bindings: Any,
    evidence_versions: Any,
    condition_observations: Any,
    policy: Any,
    generated_at: str | None = None,
) -> MaintenanceReport:
    """沿已绑定证据检查变化，产出可重复计算的维护报告。

    同输入（不论顺序、重复）同 ``id`` / ``input_digest`` / 各项 ``id``；``generated_at`` 只是展示元数据。
    任何未知版本 / 枚举 / 字段、跨 owner 输入、不可编译条件都抛 ``MaintenanceContractError``。
    """
    owner = validate_owner(owner_user_id, "owner_user_id")
    as_of_day = validate_date(as_of, "as_of")
    cutoff = validate_date(knowledge_cutoff, "knowledge_cutoff")
    if cutoff < as_of_day:
        raise MaintenanceContractError("knowledge_cutoff_before_as_of", "knowledge_cutoff", "知识截止早于市场日：那天的事还不可能知道")
    pol = parse_policy(policy)

    parsed: dict[tuple[str, int], DependencyBinding] = {}
    for i, raw in enumerate(_as_list(bindings, "bindings")):
        b = parse_binding(raw, owner_user_id=owner, where=f"bindings[{i}]")
        if b.object_ref.namespace not in pol.allowed_object_namespaces:
            raise MaintenanceContractError("namespace_not_allowed", f"bindings[{i}].object_ref.namespace", f"{b.object_ref.namespace!r} 不在策略允许的对象命名空间内")
        key = (b.binding_id, b.binding_version)
        if key in parsed:
            if canonical_json(parsed[key].to_dict()) != canonical_json(b.to_dict()):
                raise MaintenanceContractError("duplicate_binding", f"bindings[{i}]", f"同一 binding_id/version {key} 出现两份不同内容")
            continue
        parsed[key] = b
    ordered = sorted(parsed.values(), key=lambda b: (b.object_ref.identity(), b.binding_id, b.binding_version))
    compiled: dict[tuple[str, int, str], tuple[Any, ...]] = {}
    for b in ordered:
        for j, c in enumerate(b.conditions):
            compiled[(b.binding_id, b.binding_version, c.condition_id)] = cond_mod.compile_binding_condition(c, where=f"bindings[{b.binding_id}@{b.binding_version}].conditions[{j}]")

    versions = _dedupe_sorted([parse_evidence_version(v, owner_user_id=owner, where=f"evidence_versions[{i}]") for i, v in enumerate(_as_list(evidence_versions, "evidence_versions"))])
    observations = _dedupe_sorted([parse_observation(o, owner_user_id=owner, where=f"condition_observations[{i}]") for i, o in enumerate(_as_list(condition_observations, "condition_observations"))])

    input_digest = sha256_hex(
        {
            "schema_version": SCHEMA_VERSION,
            "owner_user_id": owner,
            "as_of": as_of_day,
            "knowledge_cutoff": cutoff,
            "bindings": [b.to_dict() for b in ordered],
            "evidence_versions": [v.to_dict() for v in versions],
            "condition_observations": [o.to_dict() for o in observations],
            "policy": pol.to_dict(),
        }
    )
    hindsight = cutoff > as_of_day
    by_ref, place_gaps = _place(versions, checked_at=cutoff)
    by_supersedes: dict[str, set[str]] = {}
    for v in versions:
        if v.supersedes_ref:
            by_supersedes.setdefault(v.supersedes_ref, set()).add(v.ref)
    obs_index = cond_mod.index_observations(observations)

    items: list[MaintenanceItem] = []
    report_gaps: list[Gap] = list(place_gaps)
    pits: list[str] = []
    objects_seen: set[tuple[str, ...]] = set()
    objects_bound: set[tuple[str, ...]] = set()
    objects_unverifiable: set[tuple[str, ...]] = set()
    dependencies_checked = 0
    for b in ordered:
        ident = b.object_ref.identity()
        objects_seen.add(ident)
        if b.created_day > as_of_day:
            report_gaps.append(
                Gap(
                    reason="binding_not_yet_effective",
                    ref=b.object_ref.ref,
                    checked_at=cutoff,
                    retryable=False,
                    detail=f"绑定建立于 {b.created_day}，晚于市场日 {as_of_day}：created_at 之前不生成维护样本",
                    binding_id=b.binding_id,
                )
            )
            continue
        objects_bound.add(ident)
        for ref in b.baseline_evidence_refs:
            dependencies_checked += 1
            dep_items, dep_pit, dep_gaps, _unchanged = _dependency_items(
                b, ref, by_ref, by_supersedes, place_gaps, owner=owner, as_of=as_of_day, cutoff=cutoff, hindsight=hindsight, policy=pol
            )
            items.extend(dep_items)
            pits.append(dep_pit)
            report_gaps.extend(dep_gaps)
            if any(it.status != "superseded" and it.epistemic_state == "unknown" for it in dep_items):
                objects_unverifiable.add(ident)
        if pol.evaluate_conditions:
            for c in b.conditions:
                item = _condition_item(b, c, compiled[(b.binding_id, b.binding_version, c.condition_id)], obs_index, owner=owner, as_of=as_of_day, cutoff=cutoff, hindsight=hindsight)
                items.append(item)
                pits.append(item.pit_grade)
                if item.epistemic_state == "unknown":
                    objects_unverifiable.add(ident)

    unique_items: dict[str, MaintenanceItem] = {}
    for it in sorted(items, key=_item_sort_key):
        unique_items.setdefault(it.id, it)
    final_items = tuple(unique_items.values())
    gap_pool: dict[tuple[Any, ...], Gap] = {}
    for g in report_gaps + [g for it in final_items for g in it.gaps]:
        gap_pool.setdefault(_gap_key(g), g)
    final_gaps = tuple(gap_pool[k] for k in sorted(gap_pool))
    counts = {
        "objects_seen": len(objects_seen),
        "objects_bound": len(objects_bound),
        "objects_unverifiable": len(objects_unverifiable),
        "dependencies_checked": dependencies_checked,
        "items_open": sum(1 for it in final_items if it.is_open),
    }
    report_id = REPORT_ID_PREFIX + short_hash({"schema_version": SCHEMA_VERSION, "owner_user_id": owner, "as_of": as_of_day, "knowledge_cutoff": cutoff, "input_digest": input_digest})
    stamp = validate_stamp(generated_at, "generated_at") if generated_at is not None else _now_iso()
    return MaintenanceReport(
        id=report_id,
        owner_user_id=owner,
        as_of=as_of_day,
        knowledge_cutoff=cutoff,
        input_digest=input_digest,
        generated_at=stamp,
        pit_grade=weakest_pit(pits),
        hindsight=hindsight,
        gaps=final_gaps,
        items=final_items,
        counts=counts,
    )


__all__ = ["assess"]
