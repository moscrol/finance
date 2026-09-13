"""五类流程检查（规格 §4）。每个检查产出 ``Opportunity``：一个「原对象 × 检查类别 × 机会窗口」。

三条纪律写在这里而不是写在文档里：

1. **issue 必须引用当时在效的显式规则**（``policy.rule_for(kind, object_kind, at)``）。行为时刻没有规则
   在效 → unknown（``rule_not_in_effect``），不能拿今天的标准判过去。策略里根本没为该对象类型定义
   规则 → 这类对象不在本检查的分母里（excluded ``not_applicable`` / ``not_ex_ante``）。
2. **缺证不是反证**：缺截止、只有日期、链不完整、无覆盖声明 → unknown 并写 gap。UNKNOWN 不会变成 0、
   失败或已解除。
3. **问题存在与责任归属分开**：系统 / 数据限制列 ``non_attributable``；执行者不明归 ``unknown_origin``。
   其中**无责任系统故障**（系统失败窗口、回检责任在系统）连机会都不属于用户，按规格 §5 落 ``excluded``
   并列出原因，不进 ``eligible/evaluated``——否则会把故障算成已评估覆盖，夸大诊断分母。用户**确实做了**
   回检、只是结果 unverifiable 的，机会已被履行，仍按 context 计入已评估。

每个检查函数只读 ``CheckContext``，不做 IO，不调模型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from intelligence.services.research_diagnostics.actors import actor_group_of
from intelligence.services.research_diagnostics.clock import (
    add_days,
    day_of,
    instant_lt,
    known_by,
    parse_day,
    parse_instant,
    weakest_pit,
)
from intelligence.services.research_diagnostics.contracts import (
    DiagnosticPolicy,
    EvidenceVersionView,
    Gap,
    MaintenanceItemView,
    NonAttributable,
    ObjectRef,
    ProcessReceipt,
    ProcessRecord,
    Rule,
    VerdictRecord,
)

TERMINAL_VERDICTS = ("hit", "partial", "miss")
# 规则明确说「从哪天起算」才有效；这是所有检查共用的默认参数名。
DEFAULT_DISCLOSURE_FIELDS = ("recorded_at", "reason", "linked_refs")


@dataclass
class Opportunity:
    kind: str
    record: ProcessRecord
    opportunity_key: str
    classification: str  # issue | context | unknown | excluded
    actor_group: str
    observed: str
    expected: str
    occurred_at: str | None
    knowledge_cutoff: str | None
    pit_grade: str
    rule: Rule | None = None
    object_refs: tuple[ObjectRef, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    maintenance_item_ids: tuple[str, ...] = ()
    gaps: tuple[Gap, ...] = ()
    limitation: str = ""
    excluded_reason: str | None = None
    non_attributable: NonAttributable | None = None


@dataclass
class CheckContext:
    owner_user_id: str
    start: str
    end: str
    knowledge_cutoff: str
    records: list[ProcessRecord]
    verdicts: list[VerdictRecord]
    receipts: list[ProcessReceipt]
    maintenance_items: list[MaintenanceItemView]
    policy: DiagnosticPolicy
    receipts_by_object: dict[str, list[ProcessReceipt]] = field(default_factory=dict)
    verdicts_by_object: dict[str, list[VerdictRecord]] = field(default_factory=dict)
    records_by_object: dict[str, ProcessRecord] = field(default_factory=dict)
    out_of_range_keys: set[str] = field(default_factory=set)

    @property
    def out_of_range(self) -> int:
        return len(self.out_of_range_keys)

    def __post_init__(self) -> None:
        for r in self.receipts:
            if r.object_ref is not None:
                self.receipts_by_object.setdefault(r.object_ref.identity, []).append(r)
        for v in self.verdicts:
            self.verdicts_by_object.setdefault(v.object_ref.identity, []).append(v)
        for rec in self.records:
            # 同一原对象多行（多源 / 修订 / 重复扫描）：取 record_id 字典序最小的那行作代表，不重复计数。
            cur = self.records_by_object.get(rec.object_ref.identity)
            if cur is None or rec.record_id < cur.record_id:
                self.records_by_object[rec.object_ref.identity] = rec

    def receipts_for(self, identity: str, kind: str) -> list[ProcessReceipt]:
        return [r for r in self.receipts_by_object.get(identity, []) if r.kind == kind]

    def in_scope(self, when: str | None, fallback: str | None = None, *, tag: str = "") -> bool:
        """行为日在 [start, end] 内。两个时间都没有时**保留**（判不了位置就不能悄悄丢掉）。"""
        day = parse_day(when) or parse_day(fallback)
        if day is None:
            return True
        ok = self.start <= day <= self.end
        if not ok:
            self.out_of_range_keys.add(f"{tag}|{day}")
        return ok

    def key(self, kind: str, identity: str, window: str) -> str:
        return f"{self.owner_user_id}|{kind}|{identity}|{window}"


def _gap(reason: str, ref: str | None = None, *, retryable: bool = True, detail: str | None = None) -> Gap:
    return Gap(reason=reason, ref=ref, retryable=retryable, detail=detail)


def _base(
    ctx: CheckContext,
    kind: str,
    rec: ProcessRecord,
    window: str,
    *,
    occurred_at: str | None,
    at_cutoff: str | None,
    pit: str,
    extra_refs: tuple[ObjectRef, ...] = (),
) -> Opportunity:
    group, actor_refs = actor_group_of(rec, ctx.receipts)
    return Opportunity(
        kind=kind,
        record=rec,
        opportunity_key=ctx.key(kind, rec.object_ref.identity, window),
        classification="unknown",
        actor_group=group,
        observed="",
        expected="",
        occurred_at=occurred_at,
        knowledge_cutoff=at_cutoff,
        pit_grade=pit,
        object_refs=(rec.object_ref, *extra_refs),
        evidence_refs=tuple(sorted({*rec.source_refs, *actor_refs})),
    )


def _exclude(opp: Opportunity, reason: str, detail: str | None = None) -> Opportunity:
    opp.classification = "excluded"
    opp.excluded_reason = reason
    opp.observed = detail or reason
    return opp


def _unknown(opp: Opportunity, reason: str, detail: str | None = None, ref: str | None = None) -> Opportunity:
    opp.classification = "unknown"
    opp.gaps = (*opp.gaps, _gap(reason, ref, detail=detail))
    opp.observed = detail or reason
    opp.limitation = "缺证不是反证：补齐缺口后可重算，不得当作 0 或已解除"
    return opp


def _rule_gate(
    ctx: CheckContext,
    opp: Opportunity,
    kind: str,
    at: str | None,
    *,
    missing_is: str,
    time_unknown_is: str = "rule_time_unknown",
) -> Rule | None:
    """规则门：返回在效规则；否则把 opp 置成 excluded（策略没定义）或 unknown（当时不在效 / 时刻未知）。"""
    rule, gap = ctx.policy.rule_for(kind, opp.record.object_kind, at)
    if rule is not None:
        opp.rule = rule
        return rule
    if gap == "rule_not_defined":
        _exclude(opp, missing_is, f"策略未为 object_kind={opp.record.object_kind} 定义 {kind} 规则")
        return None
    if gap == "rule_time_unknown":
        _unknown(opp, time_unknown_is, "行为时刻未知，判不了当时哪条规则在效")
        return None
    _unknown(opp, gap or "rule_unknown", "行为时刻没有在效的显式规则，不能事后定标准")
    return None


def _has_backfill(ctx: CheckContext, rec: ProcessRecord) -> bool:
    return rec.is_backfill or bool(ctx.receipts_for(rec.object_ref.identity, "backfill"))


# --------------------------------------------------------------------------- #
# 1. 迟登
# --------------------------------------------------------------------------- #
def check_late_registration(ctx: CheckContext) -> list[Opportunity]:
    out: list[Opportunity] = []
    for rec in ctx.records_by_object.values():
        recorded = rec.recorded_at
        if not ctx.in_scope(recorded.value, rec.event_time.value, tag=f"late|{rec.object_ref.identity}"):
            continue
        opp = _base(
            ctx,
            "late_registration",
            rec,
            recorded.day or "unknown",
            occurred_at=recorded.value,
            at_cutoff=recorded.day,
            pit=weakest_pit([rec.pit_grade, "strict" if recorded.granularity == "datetime" else "trade_date_only"]),
        )
        opp.expected = "登记时刻不晚于预先声明的截止"
        if rec.derived_from:
            out.append(_exclude(opp, "derived_object", f"派生自 {rec.derived_from}，登记时刻以原对象为准"))
            continue
        rule = _rule_gate(
            ctx,
            opp,
            "late_registration",
            recorded.value or recorded.day,
            missing_is="not_ex_ante",
            time_unknown_is="recorded_at_unknown",
        )
        if opp.classification == "excluded":
            out.append(opp)
            continue
        if _has_backfill(ctx, rec):
            out.append(_exclude(opp, "historical_backfill", "显式声明的历史补录不判迟登"))
            continue
        if rec.hindsight:
            out.append(_exclude(opp, "hindsight_declared", "站在事后视角建立的对象不是事前对象"))
            continue
        if rule is None:
            out.append(opp)
            continue
        if rec.declared_deadline is None:
            out.append(_unknown(opp, "deadline_missing", "记录没有预先声明的截止", rec.object_ref.identity))
            continue
        if recorded.granularity == "unknown":
            out.append(_unknown(opp, "recorded_at_unknown", "没有登记时刻", rec.object_ref.identity))
            continue
        if recorded.granularity == "date":
            out.append(_unknown(opp, "recorded_at_date_only", "只有日期粒度，不判精确迟登", rec.object_ref.identity))
            continue
        late = instant_lt(rec.declared_deadline, recorded.value)
        if late is None:
            out.append(_unknown(opp, "deadline_unparseable", "截止或登记时刻不是带时区的时刻", rec.object_ref.identity))
            continue
        opp.observed = f"登记 {recorded.value}；截止 {rec.declared_deadline}"
        opp.classification = "issue" if late else "context"
        opp.limitation = "迟登只说明登记晚于截止，不说明判断内容对错"
        if rec.deadline_rule_ref:
            opp.evidence_refs = tuple(sorted({*opp.evidence_refs, rec.deadline_rule_ref}))
        out.append(opp)
    return out


# --------------------------------------------------------------------------- #
# 2. 条件修改
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class _Transition:
    from_version: str | None
    to_version: str
    at: str | None
    reason: str | None
    disclosed: bool | None
    linked_refs: tuple[str, ...]
    refs: tuple[str, ...]


def _transitions(ctx: CheckContext, rec: ProcessRecord) -> list[_Transition]:
    seen: dict[str, _Transition] = {}
    chain = list(rec.versions)
    for prev, cur in zip(chain, chain[1:]):
        key = f"{prev.version}->{cur.version}"
        seen[key] = _Transition(prev.version, cur.version, cur.recorded_at, cur.reason, cur.disclosed, cur.linked_refs, ())
    for r in ctx.receipts_for(rec.object_ref.identity, "revision"):
        p: dict[str, Any] = dict(r.payload)
        frm = str(p.get("from_version") or "") or None
        to = str(p.get("to_version"))
        key = f"{frm}->{to}"
        prior = seen.get(key)
        disclosed = p.get("disclosed")
        linked = tuple(str(x) for x in (p.get("linked_refs") or []) if str(x).strip())
        merged = _Transition(
            frm,
            to,
            r.occurred_at or (prior.at if prior else None),
            str(p.get("reason") or "") or (prior.reason if prior else None),
            disclosed if isinstance(disclosed, bool) else (prior.disclosed if prior else None),
            tuple(sorted({*linked, *(prior.linked_refs if prior else ())})),
            tuple(sorted({*(prior.refs if prior else ()), r.receipt_id})),
        )
        seen[key] = merged
    return [seen[k] for k in sorted(seen)]


def check_condition_revision(ctx: CheckContext) -> list[Opportunity]:
    out: list[Opportunity] = []
    for rec in ctx.records_by_object.values():
        transitions = _transitions(ctx, rec)
        if not transitions:
            continue  # 没改过 = 没有机会，不进任何桶
        for tr in transitions:
            if not ctx.in_scope(tr.at, rec.event_time.value, tag=f"revision|{rec.object_ref.identity}"):
                continue
            window = f"{tr.from_version or '?'}->{tr.to_version}"
            opp = _base(
                ctx,
                "condition_revision",
                rec,
                window,
                occurred_at=tr.at,
                at_cutoff=day_of(tr.at),
                pit=weakest_pit([rec.pit_grade, "strict" if parse_instant(tr.at) is not None else "trade_date_only"]),
            )
            opp.evidence_refs = tuple(sorted({*opp.evidence_refs, *tr.refs}))
            opp.expected = "修改带时间 / 理由 / 关联并按当时变更规则披露"
            if rec.derived_from:
                out.append(_exclude(opp, "derived_object", f"派生自 {rec.derived_from}"))
                continue
            rule = _rule_gate(ctx, opp, "condition_revision", tr.at, missing_is="not_applicable")
            if opp.classification == "excluded":
                out.append(opp)
                continue
            if _has_backfill(ctx, rec):
                out.append(_exclude(opp, "historical_backfill", "历史补录的修订不判"))
                continue
            if rule is None:
                out.append(opp)
                continue
            if tr.at is None:
                out.append(_unknown(opp, "revision_time_unknown", "修改没有时间", rec.object_ref.identity))
                continue
            if rec.version_chain_complete is not True:
                out.append(
                    _unknown(
                        opp,
                        "version_chain_incomplete",
                        "版本链不完整或未声明完整，不能证明未披露；仅文本变化不足以判「事后改口」",
                        rec.object_ref.identity,
                    )
                )
                continue
            required = tuple(rule.params.get("disclosure_required_fields") or DEFAULT_DISCLOSURE_FIELDS)
            present = {
                "recorded_at": tr.at is not None,
                "reason": bool(tr.reason),
                "linked_refs": bool(tr.linked_refs),
            }
            missing = [f for f in required if not present.get(f, False)]
            undisclosed = tr.disclosed is False or bool(missing)
            frozen = _frozen_at(rule, rec, tr.at)
            if frozen is None and rule.params.get("freeze_after"):
                out.append(_unknown(opp, "freeze_point_unknown", "冻结点所需的截止 / 市场日缺失", rec.object_ref.identity))
                continue
            always = bool(rule.params.get("require_disclosure_always", True))
            violates = undisclosed and (always or bool(frozen))
            opp.observed = (
                f"{tr.from_version or '?'}→{tr.to_version} @ {tr.at}；披露字段缺 {missing or '无'}；"
                f"disclosed={tr.disclosed}；冻结后={frozen}"
            )
            opp.classification = "issue" if violates else "context"
            opp.limitation = "修改不自动等于犯错；本条只判披露与冻结规则，不判改后判断对错"
            out.append(opp)
    return out


def _frozen_at(rule: Rule, rec: ProcessRecord, at: str) -> bool | None:
    mode = rule.params.get("freeze_after")
    if not mode:
        return False
    if mode == "deadline":
        if rec.declared_deadline is None:
            return None
        return instant_lt(rec.declared_deadline, at)
    if mode == "as_of":
        if rec.event_time.day is None or day_of(at) is None:
            return None
        return day_of(at) > rec.event_time.day  # type: ignore[operator]
    return None


# --------------------------------------------------------------------------- #
# 3. 过期证据沿用
# --------------------------------------------------------------------------- #
def _evidence_entries(items: list[MaintenanceItemView], ref: str) -> list[tuple[MaintenanceItemView, EvidenceVersionView, str]]:
    out: list[tuple[MaintenanceItemView, EvidenceVersionView, str]] = []
    for item in items:
        for v in item.before:
            if v.ref == ref or v.supersedes_ref == ref:
                out.append((item, v, "before"))
        for v in item.current:
            if v.ref == ref or v.supersedes_ref == ref:
                out.append((item, v, "current"))
    return out


def evidence_status_at(
    items: list[MaintenanceItemView], ref: str, used_hash: str | None, used_at: str
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """某证据版本在使用时刻的状态。

    返回 ``(status, item_ids, refs)``，status ∈
    ``invalid / valid / later_correction / changed_only / unknown_version / unknown_time / no_info``。
    只用**记录时间 ≤ 使用时刻**的失效 / 更正事实；晚于使用时刻的更正是 later_correction（后知，不追责）。

    判 ``invalid`` 要同时满足两件事，缺一不可：失效在使用时刻**已经生效**（``expired_at`` / ``valid_to``），
    且断言失效的那条记录在使用时刻**已经存在**（``recorded_at``）。只满足前者是事后补记的追溯失效
    （later_correction）；``recorded_at`` 缺失则证明不了当时可知，落 unknown_time。少了后一半，
    9 月 7 日补记的「9 月 3 日起失效」会反过来追责 9 月 4 日的引用。

    显式替代（``supersedes_ref``）同构：替代关系要在使用时刻**已生效**（``valid_from``，缺省退回记录日）
    且**已知**（``recorded_at``）才追责；已公告但未生效的替代不追责（D3）。同一条 ref 上时间缺口与
    后知更正并存时，缺口优先（D4）：后来的更正证明不了先前的失效当时是否已知，只能 unknown_time。
    """
    entries = _evidence_entries(items, ref)
    if not entries:
        return "no_info", (), ()
    item_ids = tuple(sorted({item.item_id for item, _, _ in entries}))
    refs: set[str] = set()
    invalid = later = time_unknown = False
    used_is_current = False
    hash_seen = False
    only_content_change = True
    use_day = day_of(used_at)
    for item, v, side in entries:
        if item.change_type not in ("content_changed", "unchanged"):
            only_content_change = False
        if v.ref == ref and (used_hash is None or v.source_hash == used_hash):
            if used_hash is not None:
                hash_seen = True
            if side == "current" and not v.expired_at and (v.valid_to is None or (use_day and use_day <= v.valid_to)):
                used_is_current = True
            ended_refs: set[str] = set()
            expires_after_use = False
            if v.expired_at:
                effective = known_by(v.expired_at, used_at)
                if effective is True:
                    ended_refs.add(f"{v.ref}@expired:{v.expired_at}")
                elif effective is False:
                    expires_after_use = True
                else:
                    time_unknown = True
            if v.valid_to and use_day and v.valid_to < use_day:
                ended_refs.add(f"{v.ref}@valid_to:{v.valid_to}")
            if ended_refs:
                # 已经生效还不够：断言失效的那条记录必须在使用时刻之前就存在，否则是后知补记。
                recorded = known_by(v.recorded_at, used_at)
                if recorded is True:
                    invalid = True
                    refs.update(ended_refs)
                elif recorded is False:
                    later = True
                else:
                    time_unknown = True
            elif expires_after_use:
                later = True
        if v.supersedes_ref == ref and (used_hash is None or v.source_hash != used_hash):
            # D3：追责要「使用时刻替代已生效」且「使用时刻替代已知」同时成立（与 expiry 分支双条件同构）。
            # 生效看 valid_from；缺 valid_from 退回「记录日即生效日」（与 01 缺省放置口径一致），由 recorded 一并判。
            # 已公告但未生效的替代不追责——当时引用的旧版仍在生效（规格 §4「当时已知失效版本」）。
            effective = known_by(v.valid_from, used_at) if v.valid_from else True
            if effective is False:
                pass  # 尚未生效的既定安排：既不 invalid 也不是后知更正
            elif effective is None:
                time_unknown = True
            else:
                kb = known_by(v.recorded_at, used_at)
                if kb is True:
                    invalid = True
                    refs.add(f"{v.ref}@supersedes:{v.recorded_at}")
                elif kb is False:
                    later = True
                else:
                    time_unknown = True
    if used_hash is not None and used_is_current and not invalid:
        return "valid", item_ids, tuple(sorted(refs))
    if invalid and (used_hash is None or hash_seen or any(v.supersedes_ref == ref for _, v, _ in entries)):
        if used_hash is None and any(v.ref == ref and v.source_hash for _, v, _ in entries):
            # 知道 ref 失效过，但不知道用户用的是哪一版：可能用的正是更正后的版本。
            return "unknown_version", item_ids, tuple(sorted(refs))
        return "invalid", item_ids, tuple(sorted(refs))
    # D4：时间缺口压过后知更正——后来的更正证明不了先前那条失效在使用时刻是否已知；
    # 补上缺失时间后 issue 与 context 都可能，与现状一致的结局不唯一时就只能 unknown（规格 §4 / §5）。
    if time_unknown:
        return "unknown_time", item_ids, tuple(sorted(refs))
    if later:
        return "later_correction", item_ids, tuple(sorted(refs))
    if used_hash is not None and not hash_seen:
        return "unknown_version", item_ids, tuple(sorted(refs))
    if only_content_change and any(item.reason_code == "hash_changed" for item, _, _ in entries):
        return "changed_only", item_ids, tuple(sorted(refs))
    return "valid", item_ids, tuple(sorted(refs))


def check_stale_evidence_reuse(ctx: CheckContext) -> list[Opportunity]:
    out: list[Opportunity] = []
    uses = sorted((r for r in ctx.receipts if r.kind == "evidence_use"), key=lambda r: r.receipt_id)
    for r in uses:
        if r.object_ref is None:
            continue
        rec = ctx.records_by_object.get(r.object_ref.identity)
        if rec is None:
            continue  # 用了证据但对不上任何原对象：不是本用户的机会（06 应先绑定对象）
        used_at = r.occurred_at
        if not ctx.in_scope(used_at, rec.event_time.value, tag=f"stale|{rec.object_ref.identity}"):
            continue
        ref = str(r.payload.get("evidence_ref"))
        used_hash = str(r.payload.get("version_or_hash") or "") or None
        window = f"{ref}|{day_of(used_at) or 'unknown'}"
        opp = _base(
            ctx,
            "stale_evidence_reuse",
            rec,
            window,
            occurred_at=used_at,
            at_cutoff=day_of(used_at),
            pit=weakest_pit([rec.pit_grade, "strict" if parse_instant(used_at) is not None else "trade_date_only"]),
        )
        opp.evidence_refs = tuple(sorted({*opp.evidence_refs, r.receipt_id}))
        opp.expected = "实际引用的证据版本在使用时刻仍有效"
        rule = _rule_gate(ctx, opp, "stale_evidence_reuse", used_at, missing_is="not_applicable")
        if opp.classification == "excluded":
            out.append(opp)
            continue
        if rule is None:
            out.append(opp)
            continue
        if used_at is None:
            out.append(_unknown(opp, "use_time_unknown", "引用收据没有使用时刻", r.receipt_id))
            continue
        status, item_ids, refs = evidence_status_at(ctx.maintenance_items, ref, used_hash, used_at)
        opp.maintenance_item_ids = item_ids
        opp.evidence_refs = tuple(sorted({*opp.evidence_refs, *refs}))
        pits = [i.pit_grade for i in ctx.maintenance_items if i.item_id in item_ids]
        opp.pit_grade = weakest_pit([opp.pit_grade, *pits])
        if status == "no_info":
            out.append(_unknown(opp, "evidence_validity_unknown", f"01 报告里没有 {ref} 的版本信息", ref))
        elif status == "changed_only":
            out.append(_unknown(opp, "change_not_invalidating", "只有 hash 变化，不构成失效；哈希变化不能判原判断被推翻", ref))
        elif status == "unknown_version":
            out.append(_unknown(opp, "used_version_unknown", "引用收据没带版本哈希或哈希对不上任何已知版本", ref))
        elif status == "unknown_time":
            out.append(_unknown(opp, "time_metadata_missing", "失效 / 更正事实缺记录时间，判不了当时是否可知", ref))
        elif status == "invalid":
            opp.classification = "issue"
            opp.observed = f"{used_at} 引用 {ref}@{used_hash or '?'}，该版本在此之前已失效 / 被更正"
            opp.limitation = "沿用过期证据是流程问题，不等于结论错误；后知更正不在此列"
            out.append(opp)
        elif status == "later_correction":
            opp.classification = "context"
            opp.observed = f"{ref} 的更正记录晚于使用时刻 {used_at}：后知更正，不追责"
            opp.limitation = "后知更正只作背景，不改旧判定"
            out.append(opp)
        else:
            opp.classification = "context"
            opp.observed = f"{used_at} 引用 {ref}@{used_hash or '?'}，当时有效"
            out.append(opp)
    return out


# --------------------------------------------------------------------------- #
# 4. 阶段不适用
# --------------------------------------------------------------------------- #
def check_stage_mismatch(ctx: CheckContext) -> list[Opportunity]:
    out: list[Opportunity] = []
    uses = sorted((r for r in ctx.receipts if r.kind == "stage_use"), key=lambda r: r.receipt_id)
    for r in uses:
        if r.object_ref is None:
            continue
        rec = ctx.records_by_object.get(r.object_ref.identity)
        if rec is None:
            continue
        used_at = r.occurred_at
        if not ctx.in_scope(used_at, rec.event_time.value, tag=f"stage|{rec.object_ref.identity}"):
            continue
        p = r.payload
        method_ref = str(p.get("method_ref"))
        method_version = str(p.get("method_version") or "") or None
        window = f"{method_ref}|{day_of(used_at) or 'unknown'}"
        opp = _base(
            ctx,
            "stage_mismatch",
            rec,
            window,
            occurred_at=used_at,
            at_cutoff=day_of(used_at),
            pit=weakest_pit([rec.pit_grade, "trade_date_only"]),
        )
        opp.evidence_refs = tuple(sorted({*opp.evidence_refs, r.receipt_id}))
        opp.expected = "使用的方法在当时确定性阶段标签下按当时适用表适用"
        rule = _rule_gate(ctx, opp, "stage_mismatch", used_at, missing_is="not_applicable")
        if opp.classification == "excluded":
            out.append(opp)
            continue
        if rule is None:
            out.append(opp)
            continue
        if used_at is None:
            out.append(_unknown(opp, "use_time_unknown", "使用收据没有时刻", r.receipt_id))
            continue
        table, gap = ctx.policy.table_for(method_ref, method_version, used_at)
        if table is None:
            out.append(_unknown(opp, gap or "applicability_table_missing", f"{method_ref} 当时没有在效适用表", method_ref))
            continue
        opp.evidence_refs = tuple(sorted({*opp.evidence_refs, f"{table.table_ref}@{table.version}"}))
        label = str(p.get("stage_label") or "") or None
        grade = str(p.get("stage_label_grade") or ("deterministic" if label else "gap"))
        label_cutoff = str(p.get("stage_label_cutoff") or "") or None
        if label is None or grade != "deterministic":
            out.append(_unknown(opp, "stage_label_unknown", f"当时阶段标签为 {grade}，不判", method_ref))
            continue
        if label_cutoff is None:
            out.append(_unknown(opp, "stage_label_cutoff_missing", "标签没有知识截止，判不了是不是当时的标签", method_ref))
            continue
        if known_by(label_cutoff, used_at) is False:
            out.append(_unknown(opp, "stage_label_hindsight", "标签截止晚于使用时刻：那是后来换的阶段，不判当时错", method_ref))
            continue
        applicable = label in table.applicable_stages
        opp.observed = f"{used_at} 在阶段「{label}」使用 {method_ref}@{method_version or '*'}；适用表 {table.table_ref}@{table.version} 允许 {list(table.applicable_stages)}"
        opp.classification = "context" if applicable else "issue"
        opp.limitation = "只比对当时适用表与当时标签；后来换阶段、后来改表都不追溯"
        out.append(opp)
    return out


# --------------------------------------------------------------------------- #
# 5. 到期未回检
# --------------------------------------------------------------------------- #
def _coverage_ok(ctx: CheckContext, due: str, window_end: str) -> tuple[bool, tuple[str, ...]]:
    refs: list[str] = []
    for r in ctx.receipts:
        if r.kind != "coverage" or str(r.payload.get("ledger")) != "verdicts":
            continue
        through = parse_day(str(r.payload.get("complete_through")))
        frm = parse_day(str(r.payload.get("complete_from") or "")) if r.payload.get("complete_from") else None
        if through is None or through < window_end:
            continue
        if frm is not None and frm > due:
            continue
        refs.append(r.receipt_id)
    return bool(refs), tuple(sorted(refs))


def _overlaps(r: ProcessReceipt, start: str, end: str) -> bool:
    ws = parse_day(str(r.payload.get("window_start") or r.occurred_at or ""))
    we = parse_day(str(r.payload.get("window_end") or r.payload.get("window_start") or r.occurred_at or ""))
    if ws is None or we is None:
        return False
    return ws <= end and we >= start


def check_overdue_unreviewed(ctx: CheckContext) -> list[Opportunity]:
    out: list[Opportunity] = []
    # 派生行（如剧本登记出的 checkpoint）才是回检队列里的那条；原对象自己不再算一次到期机会。
    has_derived = {r.derived_from for r in ctx.records if r.derived_from}
    for rec in ctx.records_by_object.values():
        due = parse_day(rec.due)
        if due is None or rec.object_ref.identity in has_derived:
            continue  # 没有到期日 = 没有回检机会；有派生行的以派生行为准
        if due < ctx.start:
            ctx.out_of_range_keys.add(f"overdue|{rec.object_ref.identity}|{due}")
            continue
        # due > end 的不丢：要作为「未到期」显式排除，让读者看见它们存在。
        opp = _base(
            ctx,
            "overdue_unreviewed",
            rec,
            due,
            occurred_at=due,
            at_cutoff=due,
            pit=weakest_pit([rec.pit_grade, "trade_date_only"]),
        )
        opp.expected = "到期后在回检窗口内有回检、延期或非用户原因说明"
        rule = _rule_gate(ctx, opp, "overdue_unreviewed", due, missing_is="not_applicable")
        if opp.classification == "excluded":
            out.append(opp)
            continue
        if due > ctx.end or due > ctx.knowledge_cutoff:
            out.append(_exclude(opp, "not_due_yet", f"到期 {due} 晚于区间末 / 知识截止"))
            continue
        window_days = int(rule.params.get("review_window_days", 0)) if rule else 0
        window_end = add_days(due, window_days)
        if window_end > ctx.end or window_end > ctx.knowledge_cutoff:
            out.append(_exclude(opp, "window_open", f"回检窗口到 {window_end}，区间内尚未结束"))
            continue
        if rule is None:
            out.append(opp)
            continue
        identity = rec.object_ref.identity
        in_window = [
            v
            for v in ctx.verdicts_by_object.get(identity, [])
            if (d := parse_day(v.checked_at)) is not None and due <= d <= window_end
        ]
        terminal = [v for v in in_window if v.verdict in TERMINAL_VERDICTS]
        unverifiable = [v for v in in_window if v.verdict == "unverifiable"]
        reviews = [
            r
            for r in ctx.receipts_for(identity, "review")
            if (d := parse_day(r.occurred_at)) is not None and due <= d <= window_end
        ]
        failures = [r for r in ctx.receipts if r.kind == "system_failure" and _overlaps(r, due, window_end)]
        opp.observed = f"到期 {due}，窗口至 {window_end}"
        if terminal:
            opp.classification = "context"
            opp.observed += f"；窗口内有终态回检 {sorted({v.verdict_id for v in terminal})}"
            opp.evidence_refs = tuple(sorted({*opp.evidence_refs, *(v.verdict_id for v in terminal)}))
            opp.limitation = "hit / partial / miss 不映射流程优劣；本条只看有没有回检"
            out.append(opp)
            continue
        if reviews:
            opp.classification = "context"
            acts = sorted({str(r.payload.get("action")) for r in reviews})
            opp.observed += f"；窗口内有回检动作 {acts}"
            opp.evidence_refs = tuple(sorted({*opp.evidence_refs, *(r.receipt_id for r in reviews)}))
            out.append(opp)
            continue
        if unverifiable:
            opp.classification = "context"
            opp.observed += "；窗口内回检为 unverifiable（数据未到 / 系统降级）"
            opp.evidence_refs = tuple(sorted({*opp.evidence_refs, *(v.verdict_id for v in unverifiable)}))
            opp.non_attributable = NonAttributable(
                kind=opp.kind,
                object_identity=identity,
                reason="data_or_system_limit",
                refs=tuple(sorted(v.verdict_id for v in unverifiable)),
                detail="；".join(sorted({v.degradation_reason or "unverifiable" for v in unverifiable})),
            )
            opp.limitation = "数据 / 系统限制不归用户；补数据后可重判"
            out.append(opp)
            continue
        if failures:
            # 无责任系统故障：用户根本没拿到这次机会，排除出可评估分母（规格 §5），但责任归属清单仍留名。
            opp.evidence_refs = tuple(sorted({*opp.evidence_refs, *(r.receipt_id for r in failures)}))
            opp.non_attributable = NonAttributable(
                kind=opp.kind,
                object_identity=identity,
                reason="system_failure_window",
                refs=tuple(sorted(r.receipt_id for r in failures)),
            )
            out.append(_exclude(opp, "system_failure_window", opp.observed + "；窗口与系统失败重叠"))
            continue
        covered, cov_refs = _coverage_ok(ctx, due, window_end)
        if not covered:
            out.append(_unknown(opp, "coverage_unknown", "回检台账没有覆盖该窗口的完整性声明，缺记录不等于没回检", identity))
            continue
        opp.evidence_refs = tuple(sorted({*opp.evidence_refs, *cov_refs}))
        if rec.review_responsibility == "system":
            # 回检责任本就不在用户身上：不是用户的机会，同样排除而不是计成已评估的 context。
            opp.non_attributable = NonAttributable(
                kind=opp.kind, object_identity=identity, reason="system_recheck_missing", refs=cov_refs
            )
            out.append(_exclude(opp, "system_recheck_missing", opp.observed + "；机检对象无回检记录，责任在系统"))
            continue
        if rec.review_responsibility != "user":
            out.append(_unknown(opp, "responsibility_unknown", "回检责任人不明", identity))
            continue
        opp.classification = "issue"
        opp.observed += "；台账覆盖完整，窗口内无回检 / 延期"
        opp.limitation = "到期未回检是流程问题，不涉及判断对错；未到期与窗口未结束的都已排除"
        out.append(opp)
    return out


ALL_CHECKS = (
    check_late_registration,
    check_condition_revision,
    check_stale_evidence_reuse,
    check_stage_mismatch,
    check_overdue_unreviewed,
)


def run_all(ctx: CheckContext) -> list[Opportunity]:
    out: list[Opportunity] = []
    for check in ALL_CHECKS:
        out.extend(check(ctx))
    return out
