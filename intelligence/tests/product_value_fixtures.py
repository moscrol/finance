"""05 轨夹具生成器：确定性地生成四类反例场景 + 一组参与者级信号，全部标 ``synthetic``。

夹具从生成器生成、不手抄（同本仓 ``unread-fields-baseline.json`` 的纪律）：
``test_product_value_cli.py`` 会断言磁盘上的 JSONL 与生成器输出逐字节一致，改场景
必须重跑 ``python -m intelligence.tests.product_value_fixtures`` 再提交。

单元测试也直接 import 这里的 ``scenario_*`` 在内存里造事件，并可用 ``provenance``
参数把它们标成 ``imported`` 来验真人分母逻辑——那只发生在测试进程里，落盘的夹具
永远是 synthetic。
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from intelligence.services.product_value.contracts import (
    EVENT_SCHEMA,
    PROTOCOL_SCHEMA,
    PROVENANCE_SYNTHETIC,
    SOURCE_FRONTEND,
    SOURCE_MANUAL,
    SOURCE_SERVER,
)
from intelligence.services.product_value.protocol import freeze_protocol

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "research_evolution" / "05"
OWNER = "u_synthetic"
PILOT = "pilot-synthetic-01"
CODE_SHA = "5fb13a8c"
PROTOCOL_VERSION = "pilot-synthetic-v1"
TZ = "+08:00"
NULLABLE = ("participant_id", "task_id", "case_id", "case_version", "case_pair_id", "assistance_condition")

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def ts(day: str, hms: str) -> str:
    return f"2026-{day}T{hms}{TZ}"


def build_protocol() -> dict[str, Any]:
    protocol = {
        "schema_version": PROTOCOL_SCHEMA,
        "protocol_version": PROTOCOL_VERSION,
        "pilot_id": PILOT,
        "frozen_at": ts("09-14", "08:00:00"),
        "task_categories": ["fact_check", "judgment_recheck"],
        "cases": [
            {"case_id": "case-fc-01", "case_version": "1", "category": "fact_check", "title": "核对某公司三季度订单口径", "deliverable": "核对单 + 出处列表", "source_scale": "3 份公告", "cutoff": "2026-09-12"},
            {"case_id": "case-fc-02", "case_version": "1", "category": "fact_check", "title": "核对某板块成交额口径", "deliverable": "核对单 + 出处列表", "source_scale": "3 份公告", "cutoff": "2026-09-12"},
            {"case_id": "case-fc-03", "case_version": "1", "category": "fact_check", "title": "核对某产品价格数据", "deliverable": "核对单 + 出处列表", "source_scale": "2 份数据表", "cutoff": "2026-09-12"},
            {"case_id": "case-fc-04", "case_version": "1", "category": "fact_check", "title": "核对某产能数据", "deliverable": "核对单 + 出处列表", "source_scale": "2 份数据表", "cutoff": "2026-09-12"},
            {"case_id": "case-jr-01", "case_version": "1", "category": "judgment_recheck", "title": "回检一条旧板块判断", "deliverable": "变化单 + 维持/修订结论", "source_scale": "1 条判断 + 5 条新证据", "cutoff": "2026-09-12"},
            {"case_id": "case-jr-02", "case_version": "1", "category": "judgment_recheck", "title": "回检一条旧题材判断", "deliverable": "变化单 + 维持/修订结论", "source_scale": "1 条判断 + 5 条新证据", "cutoff": "2026-09-12"},
        ],
        "case_pairs": [
            {"case_pair_id": "pair-01", "category": "fact_check", "case_ids": ["case-fc-01", "case-fc-02"]},
            {"case_pair_id": "pair-02", "category": "judgment_recheck", "case_ids": ["case-jr-01", "case-jr-02"]},
            {"case_pair_id": "pair-03", "category": "fact_check", "case_ids": ["case-fc-03", "case-fc-04"]},
        ],
        "rubric": {
            "rubric_version": "rubric-v1",
            "dimensions": ["fact_sourcing", "calculation", "assumption_gaps", "task_completion"],
            "max_per_dimension": 2,
            "severe_error_rule": "关键事实或计算错误计一次严重错误",
        },
        "allowed_pause_reasons": ["pre_registered_break", "scheduled_meeting"],
        "criteria": {
            "time_saving": {"min_participants": 3, "min_complete_pairs": 6, "require_both_categories": True, "median_saving_min": 0.2},
            "proactive_reuse": {"min_participants": 3, "min_rate": 0.5, "manual_reminder_quiet_hours": 72},
            "renewal": {"renewal_window_days": 14},
        },
        "exclusion_rules": [
            {"rule_id": "original_time_zero", "rule_version": "1", "description": "原流程耗时为 0 的配对不进省时中位数，比例单列"},
            {"rule_id": "consent_withdrawn", "rule_version": "1", "description": "撤回研究/日志同意后的事件不进有效测量，退出计数保留"},
            {"rule_id": "consent_scope", "rule_version": "1", "description": "未同意盲审的评审不进质量读数"},
            {"rule_id": "conflicting_event_id", "rule_version": "1", "description": "同 ID 不同内容的事件整体不进计算"},
        ],
        "cohort_window": {"start": "2026-09-14", "end": "2026-10-11"},
    }
    return freeze_protocol(protocol)


def ev(
    event_type: str,
    *,
    event_id: str,
    at: str,
    channel: str,
    participant: str | None = None,
    task: str | None = None,
    case: str | None = None,
    case_version: str | None = None,
    pair: str | None = None,
    condition: str | None = None,
    run_ids: Sequence[str] = (),
    object_refs: Sequence[Mapping[str, Any]] = (),
    payload: Mapping[str, Any] | None = None,
    provenance: str = PROVENANCE_SYNTHETIC,
    recorded_at: str | None = None,
    protocol_hash: str | None = None,
    supersedes: str | None = None,
) -> dict[str, Any]:
    """按合同填满全部顶层字段；null 的可空字段自动补 gaps 理由。"""
    body = dict(payload or {})
    body.setdefault("initiator", "participant" if channel == SOURCE_FRONTEND else "system" if channel == SOURCE_SERVER else "importer")
    body.setdefault("assistance_source", "none" if condition == "original" else "workbench" if condition == "assisted" else "none")
    if channel == SOURCE_MANUAL:
        body.setdefault("importer_id", "imp-01")
        body.setdefault("evidence_ref", f"evidence:{event_id}")
        body.setdefault("evidence_hash", "sha256:" + ("e" * 64))
    if event_type == "assignment_created":
        body.setdefault("protocol_hash", protocol_hash or "")
    event: dict[str, Any] = {
        "schema_version": EVENT_SCHEMA,
        "event_id": event_id,
        "event_type": event_type,
        "owner_user_id": OWNER,
        "pilot_id": PILOT,
        "participant_id": participant,
        "task_id": task,
        "case_id": case,
        "case_version": case_version,
        "case_pair_id": pair,
        "run_ids": list(run_ids),
        "object_refs": [dict(ref) for ref in object_refs],
        "assistance_condition": condition,
        "event_at": at,
        "recorded_at": recorded_at or at,
        "source_version": {"code_sha": CODE_SHA, "protocol_version": PROTOCOL_VERSION, "artifact_hash": None},
        "provenance": {"kind": provenance, "source_ref": f"fixture:{event_id}", "source_hash": None},
        "source_channel": channel,
        "payload": body,
    }
    if supersedes:
        event["supersedes_event_id"] = supersedes
    gaps = [{"field": name, "reason": "not_applicable"} for name in NULLABLE if event[name] is None]
    if gaps:
        event["gaps"] = gaps
    return event


def artifact_ref(artifact_id: str, run_id: str, digest: str) -> dict[str, Any]:
    return {"kind": "artifact", "id": artifact_id, "namespace": "workbench.runs", "version_or_hash": f"sha256:{digest}", "scope": {"run_id": run_id, "owner_user_id": OWNER}}


def cost_item(cost_id: str, component: str, *, run_id: str | None, attempt_id: str | None, scope: str | None, quantity: float | None, unit: str | None, amount: float | None, currency: str | None, certainty: str, evidence_ref: str | None, rate_version: str | None, span_id: str | None = None) -> dict[str, Any]:
    return {
        "cost_id": cost_id,
        "component": component,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "span_id": span_id,
        "coverage_scope": scope,
        "quantity": quantity,
        "unit": unit,
        "amount": amount,
        "currency": currency,
        "certainty": certainty,
        "evidence_ref": evidence_ref,
        "rate_version": rate_version,
        "allocation_rule": None,
    }


def _consent(event_id: str, participant: str, at: str, scopes: Sequence[str], provenance: str) -> dict[str, Any]:
    return ev("consent_changed", event_id=event_id, at=at, channel=SOURCE_MANUAL, participant=participant, provenance=provenance, payload={"consent_version": "consent-v1", "scopes": list(scopes), "effective_at": at, "action": "grant", "terms_hash": "sha256:" + "f" * 64})


def _assignment(event_id: str, *, participant: str, task: str, case: str, pair: str, condition: str, assigned_at: str, deadline: str, p_hash: str, provenance: str) -> dict[str, Any]:
    return ev(
        "assignment_created",
        event_id=event_id,
        at=assigned_at,
        channel=SOURCE_MANUAL,
        participant=participant,
        task=task,
        case=case,
        case_version="1",
        pair=pair,
        condition=condition,
        provenance=provenance,
        protocol_hash=p_hash,
        payload={"assigned_at": assigned_at, "condition": condition, "case_pair_id": pair, "completion_condition": "交付核对单并列出处；盲审前不得改稿", "deadline": deadline},
    )


def _interval(event_id: str, *, at: str, channel: str, participant: str, task: str, case: str, pair: str, condition: str, interval_id: str, start: str, end: str, activity: str, clock: str, pause_reason: str | None = None, provenance: str) -> dict[str, Any]:
    return ev(
        "time_interval",
        event_id=event_id,
        at=at,
        channel=channel,
        participant=participant,
        task=task,
        case=case,
        case_version="1",
        pair=pair,
        condition=condition,
        provenance=provenance,
        payload={"interval_id": interval_id, "start": start, "end": end, "activity": activity, "clock_source": clock, "pause_reason": pause_reason, "visibility": "visible" if channel == SOURCE_FRONTEND else "n/a"},
    )


def _review(event_id: str, *, at: str, participant: str, task: str, case: str, pair: str, condition: str, dims: Sequence[int], severe: int, provenance: str, blinded: bool = True, artifact_refs: Sequence[str] = ()) -> dict[str, Any]:
    names = ["fact_sourcing", "calculation", "assumption_gaps", "task_completion"]
    return ev(
        "quality_reviewed",
        event_id=event_id,
        at=at,
        channel=SOURCE_MANUAL,
        participant=participant,
        task=task,
        case=case,
        case_version="1",
        pair=pair,
        condition=condition,
        provenance=provenance,
        payload={"rubric_version": "rubric-v1", "reviewer_id": "rev-01", "blinded": blinded, "artifact_refs": list(artifact_refs), "dimensions": dict(zip(names, dims)), "severe_error_count": severe},
    )


def _run_event(event_type: str, event_id: str, *, at: str, participant: str, task: str, case: str, pair: str, run_id: str, attempt_id: str, status: str, error_ref: str | None, provenance: str) -> dict[str, Any]:
    return ev(event_type, event_id=event_id, at=at, channel=SOURCE_SERVER, participant=participant, task=task, case=case, case_version="1", pair=pair, condition="assisted", run_ids=[run_id], provenance=provenance, payload={"run_id": run_id, "attempt_id": attempt_id, "status": status, "error_ref": error_ref})


def _terminal(event_type: str, event_id: str, *, at: str, channel: str, participant: str, task: str, case: str, pair: str, condition: str, refs: Sequence[Mapping[str, Any]] = (), evidence: Sequence[str] = (), reason: str, run_ids: Sequence[str] = (), provenance: str) -> dict[str, Any]:
    return ev(event_type, event_id=event_id, at=at, channel=channel, participant=participant, task=task, case=case, case_version="1", pair=pair, condition=condition, run_ids=run_ids, object_refs=refs, provenance=provenance, payload={"task_id": task, "completion_evidence_refs": list(evidence), "terminal_reason": reason})


def _cost(event_id: str, *, at: str, channel: str, participant: str | None, task: str | None, case: str | None, pair: str | None, condition: str | None, item: Mapping[str, Any], provenance: str) -> dict[str, Any]:
    run_ids = [item["run_id"]] if item.get("run_id") else []
    return ev("cost_recorded", event_id=event_id, at=at, channel=channel, participant=participant, task=task, case=case, case_version="1" if task else None, pair=pair, condition=condition, run_ids=run_ids, provenance=provenance, payload={"cost_item": dict(item)})


# --------------------------------------------------------------------------
# 场景
# --------------------------------------------------------------------------


def scenario_complete_pair(p_hash: str, *, provenance: str = PROVENANCE_SYNTHETIC) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """完整配对：原流程 45 分钟（扣 5 分钟预登记暂停），辅助 20 分钟；质量 7 → 8；费用全已知。"""
    p, pair = "p01", "pair-01"
    o, a = "t-cp-o", "t-cp-a"
    co, ca = "case-fc-01", "case-fc-02"
    run = "r-cp-1"
    events = [
        _consent("e-cp-consent", p, ts("09-14", "09:00:00"), ["research", "logging", "blind_review"], provenance),
        _assignment("e-cp-assign-o", participant=p, task=o, case=co, pair=pair, condition="original", assigned_at=ts("09-14", "10:00:00"), deadline=ts("09-16", "18:00:00"), p_hash=p_hash, provenance=provenance),
        _assignment("e-cp-assign-a", participant=p, task=a, case=ca, pair=pair, condition="assisted", assigned_at=ts("09-14", "10:00:00"), deadline=ts("09-16", "18:00:00"), p_hash=p_hash, provenance=provenance),
        _interval("e-cp-o-int1", at=ts("09-15", "11:00:00"), channel=SOURCE_MANUAL, participant=p, task=o, case=co, pair=pair, condition="original", interval_id="i-cp-o-1", start=ts("09-15", "10:00:00"), end=ts("09-15", "10:40:00"), activity="user_active", clock="manual_actual", provenance=provenance),
        _interval("e-cp-o-int2", at=ts("09-15", "11:00:00"), channel=SOURCE_MANUAL, participant=p, task=o, case=co, pair=pair, condition="original", interval_id="i-cp-o-2", start=ts("09-15", "10:20:00"), end=ts("09-15", "10:25:00"), activity="pause", clock="manual_actual", pause_reason="pre_registered_break", provenance=provenance),
        _interval("e-cp-o-int3", at=ts("09-15", "11:00:00"), channel=SOURCE_MANUAL, participant=p, task=o, case=co, pair=pair, condition="original", interval_id="i-cp-o-3", start=ts("09-15", "10:40:00"), end=ts("09-15", "10:50:00"), activity="external_lookup", clock="manual_actual", provenance=provenance),
        _terminal("task_completed", "e-cp-o-done", at=ts("09-15", "10:50:00"), channel=SOURCE_MANUAL, participant=p, task=o, case=co, pair=pair, condition="original", evidence=["doc:orig-deliverable-01"], reason="delivered", provenance=provenance),
        _review("e-cp-o-review", at=ts("09-16", "09:00:00"), participant=p, task=o, case=co, pair=pair, condition="original", dims=[2, 2, 1, 2], severe=0, artifact_refs=["doc:orig-deliverable-01"], provenance=provenance),
        ev("task_started", event_id="e-cp-a-start-f", at=ts("09-15", "14:00:00"), channel=SOURCE_FRONTEND, participant=p, task=a, case=ca, case_version="1", pair=pair, condition="assisted", provenance=provenance, payload={"task_id": a, "policy_version": "policy-v1", "view_id": "view-task", "client_at": ts("09-15", "14:00:00")}),
        ev("task_started", event_id="e-cp-a-start-s", at=ts("09-15", "14:00:02"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, case_version="1", pair=pair, condition="assisted", provenance=provenance, payload={"task_id": a, "policy_version": "policy-v1", "view_id": "view-task", "client_at": ts("09-15", "14:00:00")}),
        _interval("e-cp-a-int1", at=ts("09-15", "14:05:00"), channel=SOURCE_FRONTEND, participant=p, task=a, case=ca, pair=pair, condition="assisted", interval_id="i-cp-a-1", start=ts("09-15", "14:00:00"), end=ts("09-15", "14:05:00"), activity="user_active", clock="client", provenance=provenance),
        _run_event("run_started", "e-cp-a-run-start", at=ts("09-15", "14:05:00"), participant=p, task=a, case=ca, pair=pair, run_id=run, attempt_id="a-cp-1", status="running", error_ref=None, provenance=provenance),
        _interval("e-cp-a-int2", at=ts("09-15", "14:12:00"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, pair=pair, condition="assisted", interval_id="i-cp-a-2", start=ts("09-15", "14:05:00"), end=ts("09-15", "14:12:00"), activity="model_wait", clock="run", provenance=provenance),
        _run_event("run_finished", "e-cp-a-run-finish", at=ts("09-15", "14:12:00"), participant=p, task=a, case=ca, pair=pair, run_id=run, attempt_id="a-cp-1", status="completed", error_ref=None, provenance=provenance),
        _interval("e-cp-a-int3", at=ts("09-15", "14:20:00"), channel=SOURCE_FRONTEND, participant=p, task=a, case=ca, pair=pair, condition="assisted", interval_id="i-cp-a-3", start=ts("09-15", "14:12:00"), end=ts("09-15", "14:20:00"), activity="user_active", clock="client", provenance=provenance),
        _terminal("task_completed", "e-cp-a-done", at=ts("09-15", "14:20:00"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, pair=pair, condition="assisted", refs=[artifact_ref("art-cp-1", run, HASH_A)], evidence=["artifact:art-cp-1"], reason="delivered", run_ids=[run], provenance=provenance),
        _review("e-cp-a-review", at=ts("09-16", "09:10:00"), participant=p, task=a, case=ca, pair=pair, condition="assisted", dims=[2, 2, 2, 2], severe=0, artifact_refs=["artifact:art-cp-1"], provenance=provenance),
        _cost("e-cp-a-cost-w", at=ts("09-15", "14:12:30"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, pair=pair, condition="assisted", item=cost_item("c-cp-w", "writer_model", run_id=run, attempt_id="a-cp-1", scope="run", quantity=12000, unit="tokens", amount=0.36, currency="CNY", certainty="known", evidence_ref=f"usage:{run}", rate_version="rate-2026-09"), provenance=provenance),
        _cost("e-cp-a-cost-r", at=ts("09-15", "14:12:31"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, pair=pair, condition="assisted", item=cost_item("c-cp-r", "review_model", run_id=run, attempt_id="a-cp-1", scope="run", quantity=2000, unit="tokens", amount=0.10, currency="CNY", certainty="known", evidence_ref=f"usage:{run}", rate_version="rate-2026-09"), provenance=provenance),
        # span 级重复：已被 run 级覆盖，不得再加。
        _cost("e-cp-a-cost-span", at=ts("09-15", "14:12:32"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, pair=pair, condition="assisted", item=cost_item("c-cp-span", "writer_model", run_id=run, attempt_id="a-cp-1", scope="span", span_id="s-cp-1", quantity=5000, unit="tokens", amount=0.15, currency="CNY", certainty="known", evidence_ref=f"usage:{run}", rate_version="rate-2026-09"), provenance=provenance),
    ]
    evidence = {"runs": [{"owner_user_id": OWNER, "run_id": run, "status": "completed", "error": None, "degrades": [], "artifacts": {"art-cp-1": HASH_A}, "created_at": ts("09-15", "14:05:00"), "finished_at": ts("09-15", "14:12:00")}]}
    return events, evidence


def scenario_failed_retry(p_hash: str, *, provenance: str = PROVENANCE_SYNTHETIC) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """失败重试：第一次 run 失败（无报告）仍计尝试与已知费用；第二次完成但降级、费用缺费率。"""
    p, pair = "p02", "pair-02"
    o, a = "t-fr-o", "t-fr-a"
    co, ca = "case-jr-01", "case-jr-02"
    r1, r2 = "r-fr-1", "r-fr-2"
    events = [
        _consent("e-fr-consent", p, ts("09-14", "09:00:00"), ["research", "logging", "blind_review"], provenance),
        _assignment("e-fr-assign-o", participant=p, task=o, case=co, pair=pair, condition="original", assigned_at=ts("09-14", "10:00:00"), deadline=ts("09-17", "18:00:00"), p_hash=p_hash, provenance=provenance),
        _assignment("e-fr-assign-a", participant=p, task=a, case=ca, pair=pair, condition="assisted", assigned_at=ts("09-14", "10:00:00"), deadline=ts("09-17", "18:00:00"), p_hash=p_hash, provenance=provenance),
        _interval("e-fr-o-int1", at=ts("09-16", "10:00:00"), channel=SOURCE_MANUAL, participant=p, task=o, case=co, pair=pair, condition="original", interval_id="i-fr-o-1", start=ts("09-16", "09:00:00"), end=ts("09-16", "09:30:00"), activity="user_active", clock="manual_actual", provenance=provenance),
        _terminal("task_completed", "e-fr-o-done", at=ts("09-16", "09:30:00"), channel=SOURCE_MANUAL, participant=p, task=o, case=co, pair=pair, condition="original", evidence=["doc:orig-deliverable-02"], reason="delivered", provenance=provenance),
        _review("e-fr-o-review", at=ts("09-17", "09:00:00"), participant=p, task=o, case=co, pair=pair, condition="original", dims=[2, 1, 1, 2], severe=0, artifact_refs=["doc:orig-deliverable-02"], provenance=provenance),
        ev("task_started", event_id="e-fr-a-start-s", at=ts("09-16", "15:00:00"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, case_version="1", pair=pair, condition="assisted", provenance=provenance, payload={"task_id": a, "policy_version": "policy-v1", "view_id": "view-task", "client_at": ts("09-16", "15:00:00")}),
        _run_event("run_started", "e-fr-a-run1-start", at=ts("09-16", "15:00:00"), participant=p, task=a, case=ca, pair=pair, run_id=r1, attempt_id="a-fr-1", status="running", error_ref=None, provenance=provenance),
        _interval("e-fr-a-int1", at=ts("09-16", "15:03:00"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, pair=pair, condition="assisted", interval_id="i-fr-a-1", start=ts("09-16", "15:00:00"), end=ts("09-16", "15:03:00"), activity="model_wait", clock="run", provenance=provenance),
        _run_event("run_finished", "e-fr-a-run1-finish", at=ts("09-16", "15:03:00"), participant=p, task=a, case=ca, pair=pair, run_id=r1, attempt_id="a-fr-1", status="failed", error_ref="err:timeout", provenance=provenance),
        _cost("e-fr-a-cost1", at=ts("09-16", "15:03:10"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, pair=pair, condition="assisted", item=cost_item("c-fr-1", "writer_model", run_id=r1, attempt_id="a-fr-1", scope="run", quantity=4000, unit="tokens", amount=0.12, currency="CNY", certainty="known", evidence_ref=f"usage:{r1}", rate_version="rate-2026-09"), provenance=provenance),
        _run_event("run_started", "e-fr-a-run2-start", at=ts("09-16", "15:04:00"), participant=p, task=a, case=ca, pair=pair, run_id=r2, attempt_id="a-fr-2", status="running", error_ref=None, provenance=provenance),
        _interval("e-fr-a-int2", at=ts("09-16", "15:10:00"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, pair=pair, condition="assisted", interval_id="i-fr-a-2", start=ts("09-16", "15:04:00"), end=ts("09-16", "15:10:00"), activity="model_wait", clock="run", provenance=provenance),
        _run_event("run_finished", "e-fr-a-run2-finish", at=ts("09-16", "15:10:00"), participant=p, task=a, case=ca, pair=pair, run_id=r2, attempt_id="a-fr-2", status="completed", error_ref=None, provenance=provenance),
        _cost("e-fr-a-cost2", at=ts("09-16", "15:10:10"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, pair=pair, condition="assisted", item=cost_item("c-fr-2", "writer_model", run_id=r2, attempt_id="a-fr-2", scope="run", quantity=9000, unit="tokens", amount=None, currency=None, certainty="unknown", evidence_ref=f"usage:{r2}", rate_version=None), provenance=provenance),
        _interval("e-fr-a-int3", at=ts("09-16", "15:18:00"), channel=SOURCE_FRONTEND, participant=p, task=a, case=ca, pair=pair, condition="assisted", interval_id="i-fr-a-3", start=ts("09-16", "15:10:00"), end=ts("09-16", "15:18:00"), activity="user_active", clock="client", provenance=provenance),
        _terminal("task_completed", "e-fr-a-done", at=ts("09-16", "15:18:00"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, pair=pair, condition="assisted", refs=[artifact_ref("art-fr-2", r2, HASH_B)], evidence=["artifact:art-fr-2"], reason="delivered_after_retry", run_ids=[r2], provenance=provenance),
        _review("e-fr-a-review", at=ts("09-17", "09:10:00"), participant=p, task=a, case=ca, pair=pair, condition="assisted", dims=[2, 2, 1, 2], severe=0, artifact_refs=["artifact:art-fr-2"], provenance=provenance),
    ]
    evidence = {
        "runs": [
            {"owner_user_id": OWNER, "run_id": r1, "status": "failed", "error": "timeout", "degrades": [], "artifacts": {}, "created_at": ts("09-16", "15:00:00"), "finished_at": ts("09-16", "15:03:00")},
            {"owner_user_id": OWNER, "run_id": r2, "status": "completed", "error": None, "degrades": ["llm_unavailable_template_answer"], "artifacts": {"art-fr-2": HASH_B}, "created_at": ts("09-16", "15:04:00"), "finished_at": ts("09-16", "15:10:00")},
        ]
    }
    return events, evidence


def scenario_cost_gaps(p_hash: str, *, provenance: str = PROVENANCE_SYNTHETIC) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """费用缺口：总 tokens 缺费率、自审缺用量、失败重试无账、人工救援未计费、混币种；未同意盲审 → 质量未知。"""
    p, pair = "p03", "pair-03"
    o, a = "t-cg-o", "t-cg-a"
    co, ca = "case-fc-03", "case-fc-04"
    r1, r2 = "r-cg-1", "r-cg-2"
    events = [
        _consent("e-cg-consent", p, ts("09-14", "09:00:00"), ["research", "logging"], provenance),
        _assignment("e-cg-assign-o", participant=p, task=o, case=co, pair=pair, condition="original", assigned_at=ts("09-14", "10:00:00"), deadline=ts("09-18", "18:00:00"), p_hash=p_hash, provenance=provenance),
        _assignment("e-cg-assign-a", participant=p, task=a, case=ca, pair=pair, condition="assisted", assigned_at=ts("09-14", "10:00:00"), deadline=ts("09-18", "18:00:00"), p_hash=p_hash, provenance=provenance),
        _interval("e-cg-o-int1", at=ts("09-17", "10:00:00"), channel=SOURCE_MANUAL, participant=p, task=o, case=co, pair=pair, condition="original", interval_id="i-cg-o-1", start=ts("09-17", "09:00:00"), end=ts("09-17", "09:35:00"), activity="user_active", clock="manual_estimate", provenance=provenance),
        _terminal("task_completed", "e-cg-o-done", at=ts("09-17", "09:35:00"), channel=SOURCE_MANUAL, participant=p, task=o, case=co, pair=pair, condition="original", evidence=["doc:orig-deliverable-03"], reason="delivered", provenance=provenance),
        ev("task_started", event_id="e-cg-a-start-s", at=ts("09-17", "14:00:00"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, case_version="1", pair=pair, condition="assisted", provenance=provenance, payload={"task_id": a, "policy_version": "policy-v1", "view_id": "view-task", "client_at": ts("09-17", "14:00:00")}),
        _run_event("run_started", "e-cg-a-run1-start", at=ts("09-17", "14:00:00"), participant=p, task=a, case=ca, pair=pair, run_id=r1, attempt_id="a-cg-1", status="running", error_ref=None, provenance=provenance),
        _run_event("run_finished", "e-cg-a-run1-finish", at=ts("09-17", "14:04:00"), participant=p, task=a, case=ca, pair=pair, run_id=r1, attempt_id="a-cg-1", status="failed", error_ref="err:tool_unavailable", provenance=provenance),
        _run_event("run_started", "e-cg-a-run2-start", at=ts("09-17", "14:05:00"), participant=p, task=a, case=ca, pair=pair, run_id=r2, attempt_id="a-cg-2", status="running", error_ref=None, provenance=provenance),
        _interval("e-cg-a-int1", at=ts("09-17", "14:12:00"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, pair=pair, condition="assisted", interval_id="i-cg-a-1", start=ts("09-17", "14:00:00"), end=ts("09-17", "14:12:00"), activity="model_wait", clock="run", provenance=provenance),
        _run_event("run_finished", "e-cg-a-run2-finish", at=ts("09-17", "14:12:00"), participant=p, task=a, case=ca, pair=pair, run_id=r2, attempt_id="a-cg-2", status="completed", error_ref=None, provenance=provenance),
        _cost("e-cg-a-cost-w", at=ts("09-17", "14:12:10"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, pair=pair, condition="assisted", item=cost_item("c-cg-w", "writer_model", run_id=r2, attempt_id="a-cg-2", scope="run", quantity=20000, unit="tokens", amount=None, currency=None, certainty="unknown", evidence_ref=f"usage:{r2}", rate_version=None), provenance=provenance),
        _cost("e-cg-a-cost-r", at=ts("09-17", "14:12:11"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, pair=pair, condition="assisted", item=cost_item("c-cg-r", "review_model", run_id=r2, attempt_id="a-cg-2", scope="run", quantity=None, unit=None, amount=0.05, currency="USD", certainty="known", evidence_ref="bill:review-2026-09", rate_version="rate-2026-09"), provenance=provenance),
        _cost("e-cg-a-cost-t", at=ts("09-17", "14:12:12"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, pair=pair, condition="assisted", item=cost_item("c-cg-t", "tool", run_id=r2, attempt_id="a-cg-2", scope="run", quantity=3, unit="calls", amount=0.30, currency="CNY", certainty="known", evidence_ref="bill:tool-2026-09", rate_version="rate-2026-09"), provenance=provenance),
        ev("manual_assistance", event_id="e-cg-a-help", at=ts("09-17", "14:22:00"), channel=SOURCE_MANUAL, participant=p, task=a, case=ca, case_version="1", pair=pair, condition="assisted", provenance=provenance, payload={"helper_id": "helper-01", "task_id": a, "start": ts("09-17", "14:12:00"), "end": ts("09-17", "14:22:00"), "help_kind": "fix_query", "estimate": False}),
        _terminal("task_completed", "e-cg-a-done", at=ts("09-17", "14:25:00"), channel=SOURCE_SERVER, participant=p, task=a, case=ca, pair=pair, condition="assisted", refs=[artifact_ref("art-cg-2", r2, HASH_C)], evidence=["artifact:art-cg-2"], reason="delivered_with_help", run_ids=[r2], provenance=provenance),
        # 参与者没同意盲审：这条评审必须被排除，质量保持未知。
        _review("e-cg-a-review", at=ts("09-18", "09:00:00"), participant=p, task=a, case=ca, pair=pair, condition="assisted", dims=[2, 2, 2, 2], severe=0, artifact_refs=["artifact:art-cg-2"], provenance=provenance),
    ]
    evidence = {
        "runs": [
            {"owner_user_id": OWNER, "run_id": r1, "status": "failed", "error": "tool unavailable", "degrades": [], "artifacts": {}, "created_at": ts("09-17", "14:00:00"), "finished_at": ts("09-17", "14:04:00")},
            {"owner_user_id": OWNER, "run_id": r2, "status": "completed", "error": None, "degrades": [], "artifacts": {"art-cg-2": HASH_C}, "created_at": ts("09-17", "14:05:00"), "finished_at": ts("09-17", "14:12:00")},
        ]
    }
    return events, evidence


def scenario_empty_cohort(p_hash: str, *, provenance: str = PROVENANCE_SYNTHETIC) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """空真人队列：只有一条同意记录，没有分配、没有任务；所有真人分母为 0。"""
    return [_consent("e-ec-consent", "p00", ts("09-14", "09:00:00"), ["research", "logging"], provenance)], {"runs": []}


def scenario_cohort_signals(p_hash: str, *, provenance: str = PROVENANCE_SYNTHETIC) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    """参与者级信号：主动复用（1 主动 / 1 人工催促 / 1 来源未知）、回检（1 完成 / 1 仅查看 / 1 自动）、付款与退款、试点级托管费。"""
    events = [
        _consent("e-cs-consent-04", "p04", ts("09-14", "09:00:00"), ["research", "logging"], provenance),
        _consent("e-cs-consent-05", "p05", ts("09-14", "09:00:00"), ["research", "logging"], provenance),
        _consent("e-cs-consent-06", "p06", ts("09-14", "09:00:00"), ["research", "logging"], provenance),
        ev("task_started", event_id="e-cs-04-new-start", at=ts("09-23", "10:00:00"), channel=SOURCE_SERVER, participant="p04", task="t-cs-04b", provenance=provenance, payload={"task_id": "t-cs-04b", "policy_version": "policy-v1", "view_id": "view-task", "client_at": ts("09-23", "10:00:00"), "initiator": "participant"}),
        ev("reuse_observed", event_id="e-cs-reuse-04", at=ts("09-28", "23:00:00"), channel=SOURCE_SERVER, participant="p04", provenance=provenance, payload={"first_task_id": "t-cs-04a", "new_task_id": "t-cs-04b", "activation_at": ts("09-15", "10:00:00"), "reminder_refs": [{"kind": "system", "at": ts("09-22", "09:00:00"), "ref": "reminder:sys-1"}], "observation_window": {"start": ts("09-15", "00:00:00"), "end": ts("09-28", "23:59:59")}, "initiator": "participant"}),
        ev("reuse_observed", event_id="e-cs-reuse-05", at=ts("09-28", "23:00:00"), channel=SOURCE_SERVER, participant="p05", provenance=provenance, payload={"first_task_id": "t-cs-05a", "new_task_id": "t-cs-05b", "activation_at": ts("09-15", "10:00:00"), "new_task_started_at": ts("09-23", "10:00:00"), "reminder_refs": [{"kind": "manual", "at": ts("09-23", "08:00:00"), "ref": "reminder:wechat-1"}], "observation_window": {"start": ts("09-15", "00:00:00"), "end": ts("09-28", "23:59:59")}, "initiator": "participant"}),
        ev("reuse_observed", event_id="e-cs-reuse-06", at=ts("09-28", "23:00:00"), channel=SOURCE_SERVER, participant="p06", provenance=provenance, payload={"first_task_id": "t-cs-06a", "new_task_id": "t-cs-06b", "activation_at": ts("09-15", "10:00:00"), "new_task_started_at": ts("09-24", "10:00:00"), "reminder_refs": [{"kind": "unknown", "at": ts("09-23", "08:00:00"), "ref": "reminder:?"}], "observation_window": {"start": ts("09-15", "00:00:00"), "end": ts("09-28", "23:59:59")}, "initiator": "participant"}),
        ev("recheck_viewed", event_id="e-cs-recheck-view-01", at=ts("09-21", "10:00:00"), channel=SOURCE_FRONTEND, participant="p04", provenance=provenance, payload={"object_ref": {"kind": "judgment", "id": "j-01", "namespace": "foresight.judgments", "version_or_hash": "v3", "scope": {}}, "verdict_ref": None, "action_id": "act-view-1", "evidence_refs": []}),
        ev("recheck_completed", event_id="e-cs-recheck-done-02", at=ts("09-22", "10:00:00"), channel=SOURCE_SERVER, participant="p04", provenance=provenance, payload={"object_ref": {"kind": "judgment", "id": "j-02", "namespace": "foresight.judgments", "version_or_hash": "v2", "scope": {}}, "verdict_ref": "verdict:j-02:v2", "action_id": "act-confirm-2", "evidence_refs": ["evidence:river:2026-09-21"], "initiator": "participant"}),
        ev("recheck_completed", event_id="e-cs-recheck-auto-01", at=ts("09-23", "02:00:00"), channel=SOURCE_SERVER, participant="p04", provenance=provenance, payload={"object_ref": {"kind": "judgment", "id": "j-01", "namespace": "foresight.judgments", "version_or_hash": "v3", "scope": {}}, "verdict_ref": "verdict:j-01:auto", "action_id": "act-auto-1", "evidence_refs": [], "initiator": "system"}),
        ev("payment_recorded", event_id="e-cs-pay-04", at=ts("09-15", "09:00:00"), channel=SOURCE_MANUAL, participant="p04", provenance=provenance, payload={"payment_ref": "pay-04-1", "amount": 199, "currency": "CNY", "service_period": {"start": "2026-09-15", "end": "2026-10-14"}, "status": "paid", "verified_by": "bank-statement-2026-09"}),
        ev("payment_recorded", event_id="e-cs-pay-05", at=ts("09-15", "09:00:00"), channel=SOURCE_MANUAL, participant="p05", provenance=provenance, payload={"payment_ref": "pay-05-1", "amount": 199, "currency": "CNY", "service_period": {"start": "2026-09-15", "end": "2026-10-14"}, "status": "paid", "verified_by": "bank-statement-2026-09"}),
        ev("payment_recorded", event_id="e-cs-refund-05", at=ts("09-20", "09:00:00"), channel=SOURCE_MANUAL, participant="p05", provenance=provenance, payload={"payment_ref": "pay-05-refund", "amount": 199, "currency": "CNY", "service_period": {"start": "2026-09-15", "end": "2026-10-14"}, "status": "refunded", "verified_by": "bank-statement-2026-09", "refunds_payment_ref": "pay-05-1"}),
        _cost("e-cs-cost-hosting", at=ts("09-30", "09:00:00"), channel=SOURCE_MANUAL, participant=None, task=None, case=None, pair=None, condition=None, item=cost_item("c-hosting-09", "hosting", run_id=None, attempt_id=None, scope="pilot", quantity=1, unit="month", amount=50, currency="CNY", certainty="known", evidence_ref="invoice:hosting-2026-09", rate_version=None), provenance=provenance),
    ]
    due_rechecks = [
        {"object_ref": {"kind": "judgment", "id": "j-01", "namespace": "foresight.judgments", "version_or_hash": "v3"}, "due_at": "2026-09-20", "accessible": True},
        {"object_ref": {"kind": "judgment", "id": "j-02", "namespace": "foresight.judgments", "version_or_hash": "v2"}, "due_at": "2026-09-21", "accessible": True},
        {"object_ref": {"kind": "judgment", "id": "j-03", "namespace": "foresight.judgments", "version_or_hash": "v1"}, "due_at": "2026-10-20", "accessible": True},
        {"object_ref": {"kind": "judgment", "id": "j-04", "namespace": "foresight.judgments", "version_or_hash": "v1"}, "due_at": "2026-09-22", "accessible": False},
    ]
    return events, {"runs": []}, due_rechecks


SCENARIOS = ("complete_pair", "failed_retry", "cost_gaps", "empty_cohort", "cohort_signals")


def build_scenario(name: str, p_hash: str, *, provenance: str = PROVENANCE_SYNTHETIC) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]] | None]:
    if name == "complete_pair":
        events, evidence = scenario_complete_pair(p_hash, provenance=provenance)
        return events, evidence, None
    if name == "failed_retry":
        events, evidence = scenario_failed_retry(p_hash, provenance=provenance)
        return events, evidence, None
    if name == "cost_gaps":
        events, evidence = scenario_cost_gaps(p_hash, provenance=provenance)
        return events, evidence, None
    if name == "empty_cohort":
        events, evidence = scenario_empty_cohort(p_hash, provenance=provenance)
        return events, evidence, None
    if name == "cohort_signals":
        return scenario_cohort_signals(p_hash, provenance=provenance)
    raise KeyError(name)


def render_files(protocol: Mapping[str, Any]) -> dict[str, str]:
    """场景名/文件名 → 文件内容（字符串），供落盘与漂移比对共用。"""
    p_hash = str(protocol["protocol_hash"])
    files: dict[str, str] = {"protocol.yaml": yaml.safe_dump(dict(protocol), allow_unicode=True, sort_keys=False)}
    for name in SCENARIOS:
        events, evidence, due = build_scenario(name, p_hash)
        files[f"{name}/events.jsonl"] = "".join(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n" for e in events)
        files[f"{name}/evidence.json"] = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if due is not None:
            files[f"{name}/due_rechecks.json"] = json.dumps({"due_rechecks": due}, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    # all/：三对配对 + 参与者级信号合在一起，给 summarize 走完整路径。
    combined: list[dict[str, Any]] = []
    for name in ("complete_pair", "failed_retry", "cost_gaps", "cohort_signals"):
        combined.extend(build_scenario(name, p_hash)[0])
    evidence_all = {"runs": []}
    for name in ("complete_pair", "failed_retry", "cost_gaps"):
        evidence_all["runs"].extend(build_scenario(name, p_hash)[1]["runs"])
    files["all/events.jsonl"] = "".join(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n" for e in combined)
    files["all/evidence.json"] = json.dumps(evidence_all, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    files["all/due_rechecks.json"] = files["cohort_signals/due_rechecks.json"]
    return files


def write_all(out_dir: Path = FIXTURE_DIR) -> list[Path]:
    protocol = build_protocol()
    written: list[Path] = []
    for relative, content in render_files(protocol).items():
        path = out_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def load_fixture_protocol() -> dict[str, Any]:
    return deepcopy(build_protocol())


def main() -> int:
    for path in write_all():
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
