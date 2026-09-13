"""机会去重与分母（规格 §5）。

单位 ``original_object_check_opportunity``：按 ``(owner, 原对象, 检查类别, 机会窗口)`` 去重。多源 / 修订 /
重复扫描落到同一 key，不增加样本。不同到期 / 不同使用日是不同机会，但 ``sample_refs`` 保留原对象身份，
让读者看得出它们是同一对象上的聚类，不是独立市场实验。

恒等式（每一行都成立）：``eligible = evaluated + unknown``、``evaluated = issue + context``；``excluded`` 单列。
首版只报计数，``rate`` 恒为 null。
"""

from __future__ import annotations

from collections import Counter

from intelligence.services.research_diagnostics.contracts import (
    ACTOR_GROUPS,
    Denominator,
    DiagnosticFinding,
    Exclusion,
    Gap,
    KINDS,
    content_hash,
)
from intelligence.services.research_diagnostics.rules import Opportunity

_PRECEDENCE = {"issue": 0, "context": 1, "unknown": 2, "excluded": 3}


def dedup(opps: list[Opportunity]) -> list[Opportunity]:
    """同 key 合并：分类取最有信息量的那份（issue > context > unknown > excluded），证据取并集。"""
    merged: dict[str, Opportunity] = {}
    for opp in sorted(opps, key=lambda o: (o.opportunity_key, _PRECEDENCE[o.classification], o.observed)):
        cur = merged.get(opp.opportunity_key)
        if cur is None:
            merged[opp.opportunity_key] = opp
            continue
        cur.evidence_refs = tuple(sorted({*cur.evidence_refs, *opp.evidence_refs}))
        cur.maintenance_item_ids = tuple(sorted({*cur.maintenance_item_ids, *opp.maintenance_item_ids}))
        seen_gaps = {g.to_dict()["reason"] + "|" + str(g.to_dict()["ref"]) for g in cur.gaps}
        extra = tuple(g for g in opp.gaps if (g.reason + "|" + str(g.ref)) not in seen_gaps)
        cur.gaps = (*cur.gaps, *extra)
        if cur.non_attributable is None and opp.non_attributable is not None:
            cur.non_attributable = opp.non_attributable
    return [merged[k] for k in sorted(merged)]


def finding_of(opp: Opportunity) -> DiagnosticFinding:
    body = {
        "key": opp.opportunity_key,
        "classification": opp.classification,
        "rule": [opp.rule.rule_id, opp.rule.rule_version] if opp.rule else None,
        "observed": opp.observed,
        "expected": opp.expected,
        "evidence": list(opp.evidence_refs),
        "gaps": [g.to_dict() for g in opp.gaps],
    }
    return DiagnosticFinding(
        id="df-" + content_hash(body)[:16],
        kind=opp.kind,
        classification=opp.classification,
        actor_group=opp.actor_group,
        object_refs=opp.object_refs,
        evidence_refs=opp.evidence_refs,
        maintenance_item_ids=opp.maintenance_item_ids,
        rule_id=opp.rule.rule_id if opp.rule else None,
        rule_version=opp.rule.rule_version if opp.rule else None,
        observed=opp.observed,
        expected=opp.expected,
        occurred_at=opp.occurred_at,
        knowledge_cutoff=opp.knowledge_cutoff,
        pit_grade=opp.pit_grade,
        gaps=opp.gaps,
        limitation=opp.limitation,
        opportunity_key=opp.opportunity_key,
    )


def exclusion_of(opp: Opportunity) -> Exclusion:
    return Exclusion(
        kind=opp.kind,
        actor_group=opp.actor_group,
        object_identity=opp.record.object_ref.identity,
        reason=opp.excluded_reason or "excluded",
        opportunity_key=opp.opportunity_key,
        detail=opp.observed or None,
    )


def build_denominators(findings: list[DiagnosticFinding], exclusions: list[Exclusion]) -> list[Denominator]:
    rows: list[Denominator] = []
    for kind in KINDS:
        for group in ACTOR_GROUPS:
            fs = [f for f in findings if f.kind == kind and f.actor_group == group]
            es = [e for e in exclusions if e.kind == kind and e.actor_group == group]
            if not fs and not es:
                continue
            issue = sum(1 for f in fs if f.classification == "issue")
            context = sum(1 for f in fs if f.classification == "context")
            unknown = sum(1 for f in fs if f.classification == "unknown")
            samples = sorted({r.identity for f in fs for r in f.object_refs[:1]} | {e.object_identity for e in es})
            rows.append(
                Denominator(
                    kind=kind,
                    actor_group=group,
                    eligible=issue + context + unknown,
                    evaluated=issue + context,
                    issue=issue,
                    context=context,
                    unknown=unknown,
                    excluded=len(es),
                    sample_refs=tuple(samples[:5]),
                    exclusion_reasons=dict(Counter(e.reason for e in es)),
                )
            )
    return rows


def check_identities(rows: list[Denominator]) -> list[Gap]:
    """恒等式自检：不成立就是实现 bug，报成 gap 让它可见而不是静默。"""
    out: list[Gap] = []
    for d in rows:
        if d.eligible != d.evaluated + d.unknown or d.evaluated != d.issue + d.context:
            out.append(Gap("denominator_identity_broken", f"{d.kind}|{d.actor_group}", retryable=False))
    return out
