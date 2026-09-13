"""``diagnose``：纯函数入口（规格 §3）。

顺序：验 owner / 版本 → 按本次 cutoff 过滤输入 → 五类检查 → 去重 → 分母 → 不确定性 → 选一题 → 稳定 id。

``generated_at`` 只是展示元数据：同输入两次调用 id / 内容逐字节相同，只有它不同。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from intelligence.services.research_diagnostics.clock import day_of, parse_day, weakest_pit
from intelligence.services.research_diagnostics.contracts import (
    DiagnosticFinding,
    DiagnosticPolicy,
    DiagnosticReport,
    DiagnosticsInputError,
    Exclusion,
    ExerciseCase,
    Gap,
    InputSummary,
    MaintenanceItemView,
    NonAttributable,
    ProcessReceipt,
    ProcessRecord,
    UncertaintyFlag,
    VerdictRecord,
    content_hash,
    parse_exercise_pack,
    parse_maintenance_reports,
    require_owner,
)
from intelligence.services.research_diagnostics.denominators import (
    build_denominators,
    check_identities,
    dedup,
    exclusion_of,
    finding_of,
)
from intelligence.services.research_diagnostics.exercise import select_exercise
from intelligence.services.research_diagnostics.rules import CheckContext, run_all


def _coerce(items: Iterable[Any], cls: type, *, owner_user_id: str, where: str, id_attr: str) -> tuple[list[Any], int]:
    """dict / dataclass → 已验 owner 的对象列表；同 id 重复（重复扫描、多源）只留第一份，返回丢弃数。"""
    out: list[Any] = []
    seen: set[str] = set()
    dropped = 0
    for i, raw in enumerate(items or ()):
        obj = raw if isinstance(raw, cls) else cls.from_dict(raw)
        require_owner(owner_user_id, obj.owner_user_id, where=f"{where}[{i}]")
        key = str(getattr(obj, id_attr))
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        out.append(obj)
    return out, dropped


def _dedup_items(items: Iterable[MaintenanceItemView]) -> tuple[list[MaintenanceItemView], int]:
    out: list[MaintenanceItemView] = []
    seen: set[tuple[str, str]] = set()
    dropped = 0
    for item in items:
        key = (item.report_id, item.item_id)
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        out.append(item)
    return out, dropped


def _coerce_cases(cases: Any) -> list[ExerciseCase]:
    if cases is None:
        return []
    if isinstance(cases, Mapping):
        return list(parse_exercise_pack(cases))
    out: list[ExerciseCase] = []
    for c in cases:
        out.append(c if isinstance(c, ExerciseCase) else ExerciseCase.from_dict(c))
    return out


def _after_cutoff(when: str | None, cutoff: str) -> bool:
    day = parse_day(when)
    return day is not None and day > cutoff


def _uncertainty(
    *,
    findings: list[DiagnosticFinding],
    denominators,
    gaps: list[Gap],
    min_sample: int,
    records: list[ProcessRecord],
) -> list[UncertaintyFlag]:
    flags: list[UncertaintyFlag] = []
    small = sorted({f"{d.kind}|{d.actor_group}" for d in denominators if 0 < d.eligible < min_sample})
    if small:
        flags.append(UncertaintyFlag("small_sample", f"以下分母 eligible < {min_sample}：{small}"))
    if records:
        flags.append(UncertaintyFlag("selection_bias", "输入来自主动登记的对象，不代表用户全部研究任务"))
    cov_reasons = sorted({g.reason for g in gaps} | {g.reason for f in findings for g in f.gaps})
    cov_hits = [r for r in cov_reasons if r in ("coverage_unknown", "filtered_after_cutoff", "evidence_validity_unknown", "no_maintenance_reports")]
    if cov_hits:
        flags.append(UncertaintyFlag("source_coverage", f"来源覆盖不完整：{cov_hits}"))
    if any(f.actor_group == "unknown_origin" for f in findings):
        flags.append(UncertaintyFlag("actor_coverage", "存在来源不明的对象，未知来源不算独立用户能力"))
    by_object: dict[str, int] = {}
    for f in findings:
        for r in f.object_refs[:1]:
            by_object[r.identity] = by_object.get(r.identity, 0) + 1
    clustered = sorted(k for k, n in by_object.items() if n > 1)
    same_day: dict[str, int] = {}
    for f in findings:
        d = day_of(f.occurred_at)
        if d:
            same_day[d] = same_day.get(d, 0) + 1
    if clustered or any(n > 1 for n in same_day.values()):
        flags.append(
            UncertaintyFlag(
                "correlated_observations",
                f"同一对象多机会 {len(clustered)} 个；同日多机会 {sum(1 for n in same_day.values() if n > 1)} 天；不是独立样本",
            )
        )
    return flags


def diagnose(
    *,
    owner_user_id: str,
    start: str,
    end: str,
    knowledge_cutoff: str,
    records: Sequence[ProcessRecord | Mapping[str, Any]],
    verdicts: Sequence[VerdictRecord | Mapping[str, Any]] = (),
    maintenance_reports: Sequence[Mapping[str, Any]] = (),
    process_receipts: Sequence[ProcessReceipt | Mapping[str, Any]] = (),
    exercise_cases: Any = None,
    policy: DiagnosticPolicy | Mapping[str, Any],
    generated_at: str | None = None,
) -> DiagnosticReport:
    """诊断一个 owner 在 ``[start, end]`` 内、站在 ``knowledge_cutoff`` 回看的流程问题。

    所有输入既接 dataclass 也接同形 dict（夹具直接喂）。任何一项 owner 不一致 → ``OwnerMismatch``。
    """
    owner = str(owner_user_id or "").strip()
    if not owner:
        raise DiagnosticsInputError("owner_user_id 不能为空")
    s, e, c = parse_day(start), parse_day(end), parse_day(knowledge_cutoff)
    if s is None or e is None or c is None:
        raise DiagnosticsInputError("start / end / knowledge_cutoff 必须是 YYYY-MM-DD")
    if s > e:
        raise DiagnosticsInputError("start 不能晚于 end")
    if c < e:
        raise DiagnosticsInputError("knowledge_cutoff 不能早于 end：站在区间结束前回看不是诊断，是预测")
    pol = policy if isinstance(policy, DiagnosticPolicy) else DiagnosticPolicy.from_dict(policy)

    recs, d1 = _coerce(records, ProcessRecord, owner_user_id=owner, where="records", id_attr="record_id")
    vds, d2 = _coerce(verdicts, VerdictRecord, owner_user_id=owner, where="verdicts", id_attr="verdict_id")
    rcts, d3 = _coerce(process_receipts, ProcessReceipt, owner_user_id=owner, where="process_receipts", id_attr="receipt_id")
    items, d4 = _dedup_items(parse_maintenance_reports(maintenance_reports, owner_user_id=owner))
    duplicates_dropped = d1 + d2 + d3 + d4
    cases = _coerce_cases(exercise_cases)

    gaps: list[Gap] = []
    # 按本次 cutoff 过滤：记录时间晚于 cutoff 的东西站在 cutoff 那天还不存在。
    kept_recs = [r for r in recs if not _after_cutoff(r.recorded_at.value, c)]
    kept_vds = [v for v in vds if not _after_cutoff(v.checked_at, c)]
    kept_rcts = [r for r in rcts if not _after_cutoff(r.recorded_at or r.occurred_at, c)]
    kept_items = [i for i in items if not (i.knowledge_cutoff and i.knowledge_cutoff > c)]
    filtered = (len(recs) - len(kept_recs)) + (len(vds) - len(kept_vds)) + (len(rcts) - len(kept_rcts)) + (len(items) - len(kept_items))
    if filtered:
        gaps.append(Gap("filtered_after_cutoff", None, detail=f"{filtered} 条输入记录时间晚于 knowledge_cutoff={c}，未参与"))
    if not kept_recs:
        gaps.append(Gap("no_records", None, detail="没有可诊断的原对象记录"))
    if not kept_items:
        gaps.append(Gap("no_maintenance_reports", None, detail="没有 01 维护报告，过期证据沿用只能 unknown"))

    ctx = CheckContext(
        owner_user_id=owner,
        start=s,
        end=e,
        knowledge_cutoff=c,
        records=kept_recs,
        verdicts=kept_vds,
        receipts=kept_rcts,
        maintenance_items=kept_items,
        policy=pol,
    )
    opps = dedup(run_all(ctx))
    findings = [finding_of(o) for o in opps if o.classification != "excluded"]
    exclusions: list[Exclusion] = [exclusion_of(o) for o in opps if o.classification == "excluded"]
    non_attr: list[NonAttributable] = sorted(
        (o.non_attributable for o in opps if o.non_attributable is not None),
        key=lambda n: (n.kind, n.object_identity, n.reason),
    )
    findings.sort(key=lambda f: (f.kind, f.opportunity_key, f.id))
    exclusions.sort(key=lambda x: (x.kind, x.opportunity_key))
    denominators = build_denominators(findings, exclusions)
    gaps.extend(check_identities(denominators))

    exercise, ex_gaps = select_exercise(owner_user_id=owner, findings=findings, cases=cases, receipts=kept_rcts)
    gaps.extend(ex_gaps)
    uncertainty = _uncertainty(findings=findings, denominators=denominators, gaps=gaps, min_sample=pol.min_sample, records=kept_recs)

    pit = weakest_pit([r.pit_grade for r in kept_recs] + [i.pit_grade for i in kept_items]) if kept_recs else "unverifiable"
    provenance = "synthetic" if any(
        x.provenance == "synthetic" for x in (*kept_recs, *kept_vds, *kept_rcts)
    ) or any(cs.provenance == "synthetic" for cs in cases) else "observed"
    input_digest = content_hash(
        {
            "owner": owner,
            "start": s,
            "end": e,
            "cutoff": c,
            "records": sorted((r.to_dict() for r in recs), key=lambda d: d["record_id"]),
            "verdicts": sorted((v.to_dict() for v in vds), key=lambda d: d["verdict_id"]),
            "receipts": sorted((r.to_dict() for r in rcts), key=lambda d: d["receipt_id"]),
            "maintenance": sorted((i.to_dict() for i in items), key=lambda d: (d["report_id"], d["item_id"])),
            "cases": sorted((cs.to_dict() for cs in cases), key=lambda d: d["case_id"]),
            "policy": pol.to_dict(),
        }
    )
    summary = InputSummary(
        records=len(recs),
        verdicts=len(vds),
        receipts=len(rcts),
        maintenance_items=len(items),
        exercise_cases=len(cases),
        filtered_after_cutoff=filtered,
        out_of_range=ctx.out_of_range,
        duplicates_dropped=duplicates_dropped,
    )
    draft = DiagnosticReport(
        id="",
        owner_user_id=owner,
        start=s,
        end=e,
        knowledge_cutoff=c,
        input_digest=input_digest,
        generated_at=None,
        pit_grade=pit,
        gaps=tuple(gaps),
        findings=tuple(findings),
        denominators=tuple(denominators),
        exclusions=tuple(exclusions),
        uncertainty=tuple(uncertainty),
        non_attributable=tuple(non_attr),
        exercise=exercise,
        input_summary=summary,
        provenance=provenance,
        policy_id=pol.policy_id,
    )
    report_id = "rd-" + content_hash(draft.content_dict())[:16]
    stamp = generated_at if generated_at is not None else datetime.now(timezone.utc).isoformat(timespec="seconds")
    return DiagnosticReport(**{**draft.__dict__, "id": report_id, "generated_at": stamp})
