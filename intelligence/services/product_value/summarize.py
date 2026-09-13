"""summarize：把 MeasurementReceipt 与试点级事件汇成 PilotSummary（pilot-summary/v1）。

三条状态各自独立、互不代签（总合同 §6）：

- ``engineering_status``：管线能不能算——夹具也能让它 ``engineering_complete``；
- ``field_status``：有没有真人读数——只看 provenance 为 observed / imported 的输入，
  ``observed`` 只表示「有真实读数」，不表示效果成立；
- ``commercial_status``：有没有经凭据核验的真实付款。

synthetic 输入永远进不了真人分母。它们单独汇成 ``synthetic_check``，字段上明写
``counts_toward_field=false``，用来验收工程逻辑（同一套判据代码跑一遍），不用来
宣布效果。

判据 ``unknown`` 分三种：``sample``（样本不足，继续收集）、``gap``（漏审、缺到期清单、
缺复用观察，属于数据缺口，需要补记录而不是等时间）与 ``consent``（缺同意，要补授权，
补不到就永远不能进效果判据）。后两者同属缺口家族，``field_status`` 靠它区分
``collecting`` 与 ``inconclusive``。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from statistics import median
from typing import Any

from intelligence.services.product_value import contracts as C
from intelligence.services.product_value.events import (
    event_time,
    parse_date_or_ts,
    parse_ts,
    prepare_events,
)
from intelligence.services.product_value.hashing import content_id, hash_ids
from intelligence.services.product_value.protocol import (
    case_index,
    criteria,
    exclusion_rule_versions,
    protocol_hash,
    validate_protocol,
)

UNKNOWN_SAMPLE = "sample"
UNKNOWN_GAP = "gap"
UNKNOWN_CONSENT = "consent"
UNKNOWN_UNSTARTED = "unstarted"

# 缺口家族：不是「再等等就有样本」，而是缺记录 / 缺授权，要补数据才能判。
_GAP_KINDS: frozenset[str] = frozenset({UNKNOWN_GAP, UNKNOWN_CONSENT})

# 这些判据的真实读数决定 field_status；成本与续费另有归属。
_EFFECT_CRITERIA: tuple[str, ...] = ("completion_quality", "time_saving", "proactive_reuse", "recheck")


def _now_iso(now: datetime | None) -> str:
    stamp = now if now is not None else datetime.now().astimezone()
    if stamp.tzinfo is None:
        stamp = stamp.astimezone()
    return stamp.isoformat(timespec="seconds")


def _metric(
    metric_id: str,
    value: float | int | None,
    unit: str,
    *,
    numerator_ids: Iterable[str] = (),
    denominator_ids: Iterable[str] = (),
    exclusions: Iterable[Mapping[str, Any]] = (),
    unknown: Iterable[Mapping[str, Any]] = (),
    coverage: Mapping[str, Any] | None = None,
    detail: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "metric_id": metric_id,
        "value": value,
        "unit": unit,
        "numerator_ids": sorted(str(item) for item in numerator_ids),
        "denominator_ids": sorted(str(item) for item in denominator_ids),
        "exclusions": sorted((dict(item) for item in exclusions), key=lambda item: (str(item.get("reason")), str(item.get("id")))),
        "unknown": sorted((dict(item) for item in unknown), key=lambda item: (str(item.get("reason")), str(item.get("id")))),
        "coverage": dict(coverage or {}),
        "detail": dict(detail or {}),
    }


def _criterion(
    criterion_id: str,
    verdict: str,
    reason: str,
    *,
    metric_ids: Iterable[str],
    threshold: Mapping[str, Any] | None = None,
    unknown_kind: str | None = None,
) -> dict[str, Any]:
    return {
        "criterion_id": criterion_id,
        "verdict": verdict,
        "reason": reason,
        "metric_ids": sorted(metric_ids),
        "threshold": dict(threshold or {}),
        "unknown_kind": unknown_kind,
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _resolve_as_of(value: Any, proto: Mapping[str, Any]) -> datetime:
    parsed = parse_date_or_ts(value) if value is not None else None
    if parsed is None:
        parsed = parse_date_or_ts(str(proto["cohort_window"]["end"]))
    if parsed is None:
        raise ValueError("as_of must be an ISO date/datetime, or protocol.cohort_window.end must be one")
    # 纯日期按当天结束算，否则「截止日当天完成」会被排除。
    if isinstance(value, str) and len(value.strip()) == 10 or value is None:
        parsed = parsed + timedelta(days=1) - timedelta(seconds=1)
    return parsed


def _observation_window_end(activated_at: datetime, weeks: int) -> datetime:
    """激活周之后第 ``weeks`` 个自然周的结束时刻（ISO 周一起算）。

    spec §4 的主动复用是「另一周本人启动核心任务」，所以观察单位是自然周而不是 N 天：
    激活当周不算，要等后面 ``weeks`` 个整周走完，这个人才算「进入完整观察周」。
    参与者自带 ``observation_window.end`` 时以声明为准，这里只补没有声明的人。
    """
    monday = (activated_at - timedelta(days=activated_at.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday + timedelta(days=7 * (max(weeks, 1) + 1)) - timedelta(seconds=1)


def _is_synthetic_event(event: Mapping[str, Any]) -> bool:
    return str(event.get("provenance", {}).get("kind")) == C.PROVENANCE_SYNTHETIC


def _receipt_task_is_measured(task: Mapping[str, Any]) -> bool:
    """收据里的任务条目是否含实际费用测量事实（PV4/PV6）：尝试或耗时至少观测到一样。

    只有分配、什么都没观测到的任务（attempts=[]、timing 缺证据）不能凭「收据里有它」就算
    费用已覆盖；终态（含放弃）证明的是任务状态，不证明费用已被测量（spec §3/§4：未观察到
    调用不作零费用依据）。原流程「无 run 但有人工计时」的合法通路不受影响：耗时本身就是
    测量事实；「明确无模型费用」由收据自己的 cost_items / unknown_cost_components 表达。
    """
    if task.get("attempts"):
        return True
    timing = task.get("timing") or {}
    return bool(timing) and timing.get("reason") is None


# 辅助流水线固有的模型调用：writer + review。tool / retry / 人工类组件按用量发生，
# 没发生不是缺口证据；但模型费用缺账不能靠其它类别的费用蒙混（评审 PV9）。
_ASSISTED_MODEL_COMPONENTS = frozenset({"writer_model", "review_model"})


def _assisted_task_uncovered_components(task: Mapping[str, Any], receipt: Mapping[str, Any], applicable: set[str]) -> list[str]:
    """辅助任务仍缺费用事实的固有模型组件（按协议适用集过滤）。

    覆盖保留「任务 × 执行实例 × 组件」：一笔费用只证明它自己那个组件、那一次执行——
    第一次执行的完整模型账不为第二次作证（PV11）；失败执行仍要 writer 账（失败不代表
    模型没调用；review 未发生则不要求——PV12）；无 run 时退到任务级费用事实（PV9）。
    关联认 attempt_id / run_id（有执行实例时）或 task_id（无 run 时）三种挂法；
    有执行实例时只挂 task_id 的账无法归属到具体执行，不作数（fail closed）。
    联合身份规则与测量层共用 `contracts.cost_item_covers_attempt`（round-8 补遗）。
    """
    items = [i for i in (receipt.get("cost_items") or ()) if i.get("selected")]
    attempts = task.get("attempts") or ()
    if not attempts:
        task_id = str(task.get("task_id") or "")
        covered = {str(i.get("component")) for i in items if str(i.get("task_id") or "") == task_id}
        return sorted(applicable & _ASSISTED_MODEL_COMPONENTS - covered)
    uncovered: set[str] = set()
    for attempt in attempts:
        required = applicable & (_ASSISTED_MODEL_COMPONENTS if not attempt.get("failed") else frozenset({"writer_model"}))
        if not required:
            continue
        covered = {
            str(i.get("component"))
            for i in items
            if C.cost_item_covers_attempt(i, attempt_id=str(attempt.get("attempt_id") or ""), run_id=str(attempt.get("run_id") or ""))
        }
        uncovered |= required - covered
    return sorted(uncovered)


def _is_synthetic_receipt(receipt: Mapping[str, Any]) -> bool:
    return bool((receipt.get("provenance") or {}).get("synthetic"))


# --------------------------------------------------------------------------
# 输入整理
# --------------------------------------------------------------------------


def _dedupe_receipts(
    receipts: Iterable[Any],
    p_hash: str,
    *,
    errors: list[dict[str, str]],
    limitations: set[str],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for index, receipt in enumerate(receipts):
        if not isinstance(receipt, Mapping):
            errors.append({"code": "receipt_not_mapping", "detail": f"index:{index}"})
            continue
        if receipt.get("schema_version") != C.RECEIPT_SCHEMA:
            errors.append({"code": "receipt_schema_mismatch", "detail": str(receipt.get("receipt_id") or index)})
            continue
        if receipt.get("protocol_hash") != p_hash:
            errors.append({"code": "receipt_protocol_hash_mismatch", "detail": str(receipt.get("receipt_id") or index)})
            continue
        receipt_id = str(receipt.get("receipt_id") or f"<index:{index}>")
        by_id.setdefault(receipt_id, dict(receipt))
    by_pair: dict[str, list[dict[str, Any]]] = {}
    for receipt in by_id.values():
        by_pair.setdefault(str(receipt.get("case_pair_id")), []).append(receipt)
    chosen: list[dict[str, Any]] = []
    for pair, members in sorted(by_pair.items()):
        if len(members) > 1:
            limitations.add(f"multiple_receipts_for_pair:{pair}")
            members.sort(key=lambda r: (len(r.get("input_event_ids") or ()), str(r.get("input_hash"))))
        chosen.append(members[-1])
    return chosen


def _task_universe(
    receipts: Sequence[Mapping[str, Any]],
    assignments: Sequence[Mapping[str, Any]],
    cases: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}
    for assignment in assignments:
        task_id = assignment.get("task_id")
        if not task_id:
            continue
        payload = assignment.get("payload") or {}
        case_id = str(assignment.get("case_id"))
        tasks[str(task_id)] = {
            "task_id": str(task_id),
            "condition": str(payload.get("condition") or assignment.get("assistance_condition")),
            "participant_id": assignment.get("participant_id"),
            "case_id": case_id,
            "category": cases.get(case_id, {}).get("category"),
            "deadline": payload.get("deadline"),
            "terminal_state": "unmeasured",
            "timed_out": None,
            "quality": None,
            "receipt_id": None,
        }
    for receipt in receipts:
        for condition, task in (receipt.get("tasks") or {}).items():
            task_id = str(task.get("task_id"))
            row = tasks.setdefault(
                task_id,
                {
                    "task_id": task_id,
                    "condition": condition,
                    "participant_id": task.get("participant_id"),
                    "case_id": task.get("case_id"),
                    "category": receipt.get("category"),
                    "deadline": task.get("deadline"),
                    "terminal_state": "unmeasured",
                    "timed_out": None,
                    "quality": None,
                    "receipt_id": None,
                },
            )
            row.update(
                {
                    "terminal_state": task.get("terminal_state") or C.TERMINAL_OPEN,
                    "timed_out": bool(task.get("timed_out")),
                    "quality": task.get("quality"),
                    "receipt_id": receipt.get("receipt_id"),
                    "category": row.get("category") or receipt.get("category"),
                }
            )
    return tasks


# --------------------------------------------------------------------------
# 指标块
# --------------------------------------------------------------------------


def _compute_block(
    receipts: Sequence[dict[str, Any]],
    assignments: Sequence[dict[str, Any]],
    events: Sequence[dict[str, Any]],
    *,
    proto: Mapping[str, Any],
    crit: Mapping[str, Mapping[str, Any]],
    as_of: datetime,
    due_rechecks: Sequence[Mapping[str, Any]] | None,
    rule_versions: Mapping[str, str],
    cases: Mapping[str, Mapping[str, Any]],
    due_unavailable_reason: str = "due_list_unavailable",
) -> dict[str, Any]:
    metrics: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    tasks = _task_universe(receipts, assignments, cases)
    usable = [r for r in receipts if r.get("status") != C.RECEIPT_INVALID]
    invalid_receipts = sorted(str(r.get("receipt_id")) for r in receipts if r.get("status") == C.RECEIPT_INVALID)
    # 缺同意的配对：measure 已标 incomplete，但只排除 invalid 不够——没有授权的样本
    # 不能支撑效果判据（spec §3「缺同意时判据为 unknown」）。
    consent_gap_pairs = sorted(
        {
            str(r.get("case_pair_id"))
            for r in usable
            if any(str(lim).startswith("consent_unknown:") for lim in (r.get("limitations") or ()))
        }
    )

    # ---- 完成率：分母是全部已分配任务，含失败 / 放弃 / 未测 ----
    rates: dict[str, float | None] = {}
    for condition in (C.CONDITION_ORIGINAL, C.CONDITION_ASSISTED):
        denominator = sorted(t for t, row in tasks.items() if row["condition"] == condition)
        numerator = [t for t in denominator if tasks[t]["terminal_state"] == C.TERMINAL_COMPLETED]
        unmeasured = [{"id": t, "reason": "unmeasured"} for t in denominator if tasks[t]["terminal_state"] == "unmeasured"]
        rates[condition] = _ratio(len(numerator), len(denominator))
        metrics.append(
            _metric(f"{condition}_completion_rate", rates[condition], "ratio", numerator_ids=numerator, denominator_ids=denominator, unknown=unmeasured)
        )

    all_tasks = sorted(tasks)
    incomplete: list[str] = []
    for task_id in all_tasks:
        row = tasks[task_id]
        deadline = parse_ts(row.get("deadline"))
        overdue_open = row["terminal_state"] in {C.TERMINAL_OPEN, "unmeasured"} and deadline is not None and deadline < as_of
        if row["terminal_state"] != C.TERMINAL_COMPLETED or row.get("timed_out") or overdue_open:
            incomplete.append(task_id)
    metrics.append(_metric("timeout_or_incomplete_rate", _ratio(len(incomplete), len(all_tasks)), "ratio", numerator_ids=incomplete, denominator_ids=all_tasks))

    # ---- 严重错误与配对质量 ----
    assisted_tasks = sorted(t for t, row in tasks.items() if row["condition"] == C.CONDITION_ASSISTED)
    reviewed_assisted = [t for t in assisted_tasks if (tasks[t]["quality"] or {}).get("status") == "reviewed"]
    unreviewed_assisted = [{"id": t, "reason": "no_independent_review"} for t in assisted_tasks if t not in reviewed_assisted]
    severe = sum(int(tasks[t]["quality"]["severe_error_count"]) for t in reviewed_assisted)
    metrics.append(
        _metric(
            "severe_error_count_assisted",
            severe if reviewed_assisted else None,
            "count",
            numerator_ids=reviewed_assisted,
            denominator_ids=assisted_tasks,
            unknown=unreviewed_assisted,
        )
    )
    pairs_reviewed = [r for r in usable if (r.get("quality") or {}).get("assisted_not_lower") is not None]
    not_lower = [str(r["case_pair_id"]) for r in pairs_reviewed if r["quality"]["assisted_not_lower"]]
    pairs_unreviewed = [
        {
            "id": str(r["case_pair_id"]),
            "reason": "consent_unknown" if str(r["case_pair_id"]) in consent_gap_pairs else "review_missing",
        }
        for r in usable
        if (r.get("quality") or {}).get("assisted_not_lower") is None
    ]
    unblinded = [str(r["case_pair_id"]) for r in pairs_reviewed if "unblinded_review" in (r.get("limitations") or ())]
    metrics.append(
        _metric(
            "pair_quality_not_lower_count",
            len(not_lower) if pairs_reviewed else None,
            "count",
            numerator_ids=not_lower,
            denominator_ids=[str(r["case_pair_id"]) for r in pairs_reviewed],
            unknown=pairs_unreviewed,
            detail={"unblinded_pairs": sorted(unblinded)},
        )
    )
    cq = crit["completion_quality"]
    original_tasks = [t for t, row in tasks.items() if row["condition"] == C.CONDITION_ORIGINAL]
    if not assisted_tasks or not original_tasks:
        results.append(_criterion("completion_quality", C.VERDICT_UNKNOWN, "no_assigned_tasks", metric_ids=["assisted_completion_rate", "severe_error_count_assisted", "pair_quality_not_lower_count"], unknown_kind=UNKNOWN_SAMPLE))
    elif consent_gap_pairs:
        results.append(_criterion("completion_quality", C.VERDICT_UNKNOWN, "consent_unknown", metric_ids=["severe_error_count_assisted", "pair_quality_not_lower_count"], unknown_kind=UNKNOWN_CONSENT))
    elif unreviewed_assisted or pairs_unreviewed:
        results.append(_criterion("completion_quality", C.VERDICT_UNKNOWN, "review_missing", metric_ids=["severe_error_count_assisted", "pair_quality_not_lower_count"], unknown_kind=UNKNOWN_GAP))
    else:
        reasons: list[str] = []
        if (rates[C.CONDITION_ASSISTED] or 0.0) < (rates[C.CONDITION_ORIGINAL] or 0.0):
            reasons.append("assisted_completion_below_original")
        if severe > int(cq.get("severe_error_max", 0)):
            reasons.append("severe_errors_present")
        if len(not_lower) != len(pairs_reviewed):
            reasons.append("assisted_quality_lower_in_some_pairs")
        if unblinded:
            reasons.append("unblinded_review_bias_listed")
        verdict = C.VERDICT_FAIL if any(r != "unblinded_review_bias_listed" for r in reasons) else C.VERDICT_PASS
        results.append(
            _criterion(
                "completion_quality",
                verdict,
                ";".join(reasons) or "assisted_not_worse_and_no_severe_errors",
                metric_ids=["assisted_completion_rate", "original_completion_rate", "severe_error_count_assisted", "pair_quality_not_lower_count"],
                threshold={"severe_error_max": int(cq.get("severe_error_max", 0))},
            )
        )

    # ---- 省时 ----
    ts_receipts = [r for r in usable if (r.get("timing") or {}).get("time_saving_ratio") is not None]
    zero_pairs = [str(r["case_pair_id"]) for r in usable if (r.get("timing") or {}).get("time_saving_reason") == "original_time_zero"]
    ratios = sorted(float(r["timing"]["time_saving_ratio"]) for r in ts_receipts)
    participants: set[str] = set()
    categories: set[str] = set()
    for receipt in ts_receipts:
        participants |= {str(p) for p in receipt.get("participants") or ()}
        if receipt.get("category"):
            categories.add(str(receipt["category"]))
    med = round(float(median(ratios)), 4) if ratios else None
    considered = len(ts_receipts) + len(zero_pairs)
    metrics.append(
        _metric(
            "time_saving_median",
            med,
            "ratio",
            numerator_ids=[str(r["case_pair_id"]) for r in ts_receipts],
            denominator_ids=[str(r["case_pair_id"]) for r in ts_receipts] + zero_pairs,
            exclusions=[{"id": pid, "reason": "original_time_zero", "rule_version": rule_versions.get("original_time_zero", "")} for pid in zero_pairs],
            unknown=[{"id": pid, "reason": "consent_unknown"} for pid in consent_gap_pairs],
            coverage={
                "participants": len(participants),
                "complete_pairs": len(ts_receipts),
                "categories": sorted(categories),
                "excluded_zero_original_share": _ratio(len(zero_pairs), considered),
            },
            detail={"ratios": ratios},
        )
    )
    tsc = crit["time_saving"]
    missing: list[str] = []
    if consent_gap_pairs:
        missing.append("consent_unknown")
    if len(participants) < int(tsc.get("min_participants", 3)):
        missing.append("participants_below_min")
    if len(ts_receipts) < int(tsc.get("min_complete_pairs", 6)):
        missing.append("complete_pairs_below_min")
    if bool(tsc.get("require_both_categories", True)) and set(str(c) for c in proto["task_categories"]) - categories:
        missing.append("category_missing")
    threshold = {"min_participants": tsc.get("min_participants"), "min_complete_pairs": tsc.get("min_complete_pairs"), "median_saving_min": tsc.get("median_saving_min")}
    if missing:
        kind = UNKNOWN_CONSENT if "consent_unknown" in missing else UNKNOWN_SAMPLE
        results.append(_criterion("time_saving", C.VERDICT_UNKNOWN, ";".join(missing), metric_ids=["time_saving_median"], threshold=threshold, unknown_kind=kind))
    else:
        verdict = C.VERDICT_PASS if (med or 0.0) >= float(tsc.get("median_saving_min", 0.2)) else C.VERDICT_FAIL
        results.append(_criterion("time_saving", verdict, "median_vs_threshold", metric_ids=["time_saving_median"], threshold=threshold))

    # ---- 主动复用 ----
    # 分母是「激活后进入完整观察周」的人（spec §4），不是「有复用事件」的人：只从
    # reuse_observed 建行再当分母，没复用的人整体消失，比率必然偏高（评审 PV3）。
    started_at: dict[str, datetime] = {}
    activation: dict[str, datetime] = {}
    for event in events:
        if event.get("event_type") != "task_started" or event.get("source_channel") != C.SOURCE_SERVER:
            continue
        stamp = event_time(event)
        if event.get("task_id"):
            key = str(event["task_id"])
            if key not in started_at or stamp < started_at[key]:
                started_at[key] = stamp
        actor = str(event.get("participant_id") or "")
        if actor and (actor not in activation or stamp < activation[actor]):
            activation[actor] = stamp
    prc = crit["proactive_reuse"]
    quiet = timedelta(hours=float(prc.get("manual_reminder_quiet_hours", 72)))
    observation_weeks = int(prc.get("observation_weeks", 1))
    reuse_rows: dict[str, dict[str, Any]] = {}
    declared_window_end: dict[str, datetime] = {}
    completed_window_end: dict[str, datetime] = {}
    later_window_open: set[str] = set()
    window_unknown: list[str] = []
    reminder_counts = {"system": 0, "manual": 0, "unknown": 0}
    for event in events:
        if event.get("event_type") != "reuse_observed" or event.get("source_channel") != C.SOURCE_SERVER:
            continue
        participant = str(event.get("participant_id") or "")
        if not participant:
            continue
        payload = event["payload"]
        # 复用记录自带的激活时刻同样是激活证据（没有单独 task_started 时用它）。
        declared_activation = parse_ts(payload.get("activation_at"))
        if declared_activation is not None and (participant not in activation or declared_activation < activation[participant]):
            activation[participant] = declared_activation
        window = payload.get("observation_window") or {}
        window_end = parse_ts(window.get("end"))
        if window_end is None:
            window_unknown.append(participant)
            continue
        if participant not in declared_window_end or window_end > declared_window_end[participant]:
            declared_window_end[participant] = window_end
        if window_end > as_of:
            # PV5：后续观察窗还没结束，另列缺测——不影响该人已在完整窗里取得的队列资格。
            later_window_open.add(participant)
            continue
        if participant not in completed_window_end or window_end > completed_window_end[participant]:
            completed_window_end[participant] = window_end
        first_start = started_at.get(str(payload.get("first_task_id"))) or parse_ts(payload.get("activation_at"))
        new_start = started_at.get(str(payload.get("new_task_id"))) or parse_ts(payload.get("new_task_started_at"))
        reasons: list[str] = []
        if new_start is None:
            reasons.append("new_task_start_unknown")
        if payload.get("initiator") != "participant":
            reasons.append("initiator_not_participant")
        if first_start is not None and new_start is not None and first_start.isocalendar()[:2] == new_start.isocalendar()[:2]:
            reasons.append("same_week")
        for reminder in payload.get("reminder_refs") or ():
            kind = str(reminder.get("kind"))
            reminder_counts[kind] = reminder_counts.get(kind, 0) + 1
            at = parse_ts(reminder.get("at"))
            if kind == "unknown":
                reasons.append("reminder_source_unknown")
            elif kind == "manual" and new_start is not None and at is not None and timedelta(0) <= new_start - at <= quiet:
                reasons.append("manual_reminder_within_quiet_hours")
        row = reuse_rows.setdefault(participant, {"proactive": False, "reasons": []})
        if not reasons:
            row["proactive"] = True
        else:
            row["reasons"] = sorted(set(row["reasons"]) | set(reasons))
    reuse_denominator: list[str] = []
    window_incomplete: list[str] = []
    activation_unknown: list[str] = sorted(set(window_unknown))
    for participant in sorted(set(activation) | set(reuse_rows)):
        activated_at = activation.get(participant)
        # PV5/PV7：分母资格 = 任一完整观察窗（窗末 ≤ as_of）或「可信激活时刻 + 冻结协议观察周」
        # 推导出的成熟窗——独立于复用观测是否存在（spec §4 分母为「激活后进入完整观察周者」）。
        # 后续未结束窗只增缺测标签，不撤销已成熟资格（§3 失败 / 放弃 / 退出不能为了改善读数删除）。
        window_end = completed_window_end.get(participant)
        if window_end is None and activated_at is not None:
            derived = _observation_window_end(activated_at, observation_weeks)
            if participant not in declared_window_end or derived <= as_of:
                window_end = derived
        if activated_at is None or (window_end is None and participant not in declared_window_end):
            if participant not in activation_unknown:
                activation_unknown.append(participant)
        elif window_end is not None and window_end <= as_of:
            reuse_denominator.append(participant)
        else:
            window_incomplete.append(participant)
    reuse_numerator = [p for p in reuse_denominator if reuse_rows.get(p, {}).get("proactive")]
    # 分母里没有复用观察记录的人：留在分母（比率不能被抬高），同时逐条列为缺测。
    observation_missing = [p for p in reuse_denominator if p not in reuse_rows]
    reuse_unknown = (
        [{"id": p, "reason": "observation_window_incomplete"} for p in sorted(set(window_incomplete))]
        + [{"id": p, "reason": "later_observation_window_incomplete"} for p in sorted(later_window_open & set(reuse_denominator))]
        + [{"id": p, "reason": "activation_unknown"} for p in sorted(set(activation_unknown))]
        + [{"id": p, "reason": "reuse_observation_missing"} for p in observation_missing]
    )
    metrics.append(
        _metric(
            "proactive_reuse_rate",
            _ratio(len(reuse_numerator), len(reuse_denominator)),
            "ratio",
            numerator_ids=reuse_numerator,
            denominator_ids=reuse_denominator,
            unknown=reuse_unknown,
            detail={
                "system_reminder_count": reminder_counts.get("system", 0),
                "manual_reminder_count": reminder_counts.get("manual", 0),
                "unknown_reminder_count": reminder_counts.get("unknown", 0),
                "observation_weeks": observation_weeks,
                "not_proactive_reasons": {
                    p: (reuse_rows[p]["reasons"] if p in reuse_rows else ["reuse_observation_missing"])
                    for p in reuse_denominator
                    if not reuse_rows.get(p, {}).get("proactive")
                },
            },
        )
    )
    if observation_missing:
        results.append(_criterion("proactive_reuse", C.VERDICT_UNKNOWN, "reuse_observation_missing", metric_ids=["proactive_reuse_rate"], threshold={"min_participants": prc.get("min_participants"), "min_rate": prc.get("min_rate")}, unknown_kind=UNKNOWN_GAP))
    elif len(reuse_denominator) < int(prc.get("min_participants", 3)):
        results.append(_criterion("proactive_reuse", C.VERDICT_UNKNOWN, "participants_below_min", metric_ids=["proactive_reuse_rate"], threshold={"min_participants": prc.get("min_participants"), "min_rate": prc.get("min_rate")}, unknown_kind=UNKNOWN_SAMPLE))
    else:
        rate = _ratio(len(reuse_numerator), len(reuse_denominator)) or 0.0
        results.append(_criterion("proactive_reuse", C.VERDICT_PASS if rate >= float(prc.get("min_rate", 0.5)) else C.VERDICT_FAIL, "rate_vs_threshold", metric_ids=["proactive_reuse_rate"], threshold={"min_participants": prc.get("min_participants"), "min_rate": prc.get("min_rate")}))

    # ---- 回检 ----
    if due_rechecks is None:
        metrics.append(_metric("recheck_completion_rate", None, "ratio", unknown=[{"id": "*", "reason": due_unavailable_reason}]))
        results.append(_criterion("recheck", C.VERDICT_UNKNOWN, due_unavailable_reason, metric_ids=["recheck_completion_rate"], unknown_kind=UNKNOWN_GAP if due_unavailable_reason == "due_list_unavailable" else UNKNOWN_SAMPLE))
    else:
        due_ids: list[str] = []
        not_due: list[str] = []
        inaccessible: list[str] = []
        for item in due_rechecks:
            ref = item.get("object_ref") if isinstance(item, Mapping) else None
            object_id = str((ref or {}).get("id") or item.get("id") or "") if isinstance(item, Mapping) else ""
            if not object_id:
                continue
            due_at = parse_date_or_ts(item.get("due_at"))
            if due_at is None or due_at > as_of:
                not_due.append(object_id)
            elif not item.get("accessible", True):
                inaccessible.append(object_id)
            else:
                due_ids.append(object_id)
        completed_ids: set[str] = set()
        auto_ids: set[str] = set()
        viewed_ids: set[str] = set()
        for event in events:
            if event.get("event_type") not in {"recheck_viewed", "recheck_completed"} or event_time(event) > as_of:
                continue
            object_id = str((event["payload"].get("object_ref") or {}).get("id") or "")
            if event["event_type"] == "recheck_viewed":
                viewed_ids.add(object_id)
            elif event.get("source_channel") == C.SOURCE_SERVER:
                if event["payload"].get("initiator") == "system":
                    auto_ids.add(object_id)
                else:
                    completed_ids.add(object_id)
        numerator = [oid for oid in due_ids if oid in completed_ids]
        metrics.append(
            _metric(
                "recheck_completion_rate",
                _ratio(len(numerator), len(due_ids)),
                "ratio",
                numerator_ids=numerator,
                denominator_ids=due_ids,
                detail={
                    "not_yet_due": sorted(set(not_due)),
                    "inaccessible": sorted(set(inaccessible)),
                    "viewed_only": sorted(oid for oid in due_ids if oid in viewed_ids and oid not in completed_ids),
                    "auto_recheck_not_counted": sorted(oid for oid in due_ids if oid in auto_ids and oid not in completed_ids),
                },
            )
        )
        if due_ids:
            results.append(_criterion("recheck", C.VERDICT_OBSERVED_ONLY, "ratio_displayed_no_threshold", metric_ids=["recheck_completion_rate"]))
        else:
            results.append(_criterion("recheck", C.VERDICT_UNKNOWN, "no_due_objects", metric_ids=["recheck_completion_rate"], unknown_kind=UNKNOWN_SAMPLE))

    # ---- 付款与续费（也给成本块提供收入）----
    payments: dict[str, list[dict[str, Any]]] = {}
    refunded_refs: set[str] = set()
    refund_count = 0
    for event in events:
        if event.get("event_type") != "payment_recorded" or event.get("source_channel") != C.SOURCE_MANUAL:
            continue
        payload = event["payload"]
        if payload.get("status") == "refunded":
            refunded_refs.add(str(payload.get("refunds_payment_ref")))
            refund_count += 1
            continue
        if not payload.get("verified_by"):
            continue
        period = payload.get("service_period") or {}
        start, end = parse_date_or_ts(period.get("start")), parse_date_or_ts(period.get("end"))
        if start is None or end is None:
            continue
        payments.setdefault(str(event.get("participant_id") or ""), []).append(
            {"payment_ref": str(payload.get("payment_ref")), "amount": payload.get("amount"), "currency": str(payload.get("currency")), "start": start, "end": end}
        )
    revenue: dict[str, Decimal] = {}
    first_payers: list[str] = []
    in_window: list[str] = []
    renewed: list[str] = []
    window_days = int(crit["renewal"].get("renewal_window_days", 14))
    for participant, rows in sorted(payments.items()):
        paid = sorted((r for r in rows if r["payment_ref"] not in refunded_refs), key=lambda r: (r["start"], r["payment_ref"]))
        if not paid:
            continue
        for row in paid:
            revenue[row["currency"]] = revenue.get(row["currency"], Decimal("0")) + Decimal(str(row["amount"]))
        first_payers.append(participant)
        first = paid[0]
        if first["end"] + timedelta(days=window_days) <= as_of:
            in_window.append(participant)
            if any(r["start"] >= first["end"] for r in paid[1:]):
                renewed.append(participant)
    metrics.append(
        _metric(
            "renewal_rate",
            _ratio(len(renewed), len(in_window)),
            "ratio",
            numerator_ids=renewed,
            denominator_ids=in_window,
            detail={"first_payers": sorted(first_payers), "not_yet_in_window": sorted(set(first_payers) - set(in_window)), "refund_count": refund_count},
        )
    )
    if not first_payers:
        results.append(_criterion("renewal", C.VERDICT_UNKNOWN, "no_verified_first_payment", metric_ids=["renewal_rate"], unknown_kind=UNKNOWN_UNSTARTED))
    elif not in_window:
        results.append(_criterion("renewal", C.VERDICT_UNKNOWN, "renewal_window_not_reached", metric_ids=["renewal_rate"], unknown_kind=UNKNOWN_SAMPLE))
    else:
        results.append(_criterion("renewal", C.VERDICT_OBSERVED_ONLY, "ratio_displayed", metric_ids=["renewal_rate"]))

    # ---- 成本：全部任务 / 重试 / 帮助，已知 / 估算 / 未知并列 ----
    known: dict[str, Decimal] = {}
    estimated: dict[str, Decimal] = {}
    unknown_components: list[dict[str, Any]] = []
    manual_minutes = Decimal("0")
    for receipt in receipts:
        for currency, amount in (receipt.get("known_cost_by_currency") or {}).items():
            known[str(currency)] = known.get(str(currency), Decimal("0")) + Decimal(str(amount))
        for currency, amount in (receipt.get("estimated_cost_by_currency") or {}).items():
            estimated[str(currency)] = estimated.get(str(currency), Decimal("0")) + Decimal(str(amount))
        for component in receipt.get("unknown_cost_components") or ():
            unknown_components.append({**dict(component), "receipt_id": receipt.get("receipt_id")})
        manual_minutes += Decimal(str((receipt.get("manual_minutes") or {}).get("rescue") or 0))
    pilot_cost_events = [
        e for e in events if e.get("event_type") == "cost_recorded" and not e.get("task_id") and not e.get("case_pair_id")
    ]
    for event in pilot_cost_events:
        item = event["payload"]["cost_item"]
        certainty = item.get("certainty")
        if certainty == C.CERTAINTY_KNOWN:
            known[str(item.get("currency"))] = known.get(str(item.get("currency")), Decimal("0")) + Decimal(str(item.get("amount")))
        elif certainty == C.CERTAINTY_ESTIMATED:
            estimated[str(item.get("currency"))] = estimated.get(str(item.get("currency")), Decimal("0")) + Decimal(str(item.get("amount")))
        else:
            unknown_components.append({"component": item.get("component"), "cost_id": item.get("cost_id"), "run_id": None, "attempt_id": None, "quantity": item.get("quantity"), "unit": item.get("unit"), "reason": "amount_unknown", "receipt_id": None})
    # 完整性不能只看收据主动列出的 unknown：那只覆盖「已经在算的那几笔」。缺口有两种，
    # 都是「没观察到 ≠ 花了 0 元」（spec §3、§4，评审 PV2）——
    #   1) 已分配却没有任何测量收据的任务，它的费用无从谈起；
    #   2) 合同要求覆盖、但整份试点一条账都没有的费用类别。
    not_applicable = sorted({str(x) for x in (crit["cost"].get("not_applicable_components") or ())})
    applicable_components = set(C.COST_COMPONENTS) - set(not_applicable)
    if receipts or pilot_cost_events or tasks:
        # PV4：任务条目出现在收据里 ≠ 费用已覆盖。逐任务核验测量事实（终态 / 尝试 / 耗时至少观测到一样）；
        # 只有分配的空壳收据盖不住缺口。「没有收据」与「收据在但没测」分开列——补的动作不同：
        # 前者补测量流程，后者该张收据对应的任务根本没有可入账的观察。
        task_coverage: dict[str, str] = {}
        task_cost_blocked: dict[str, tuple[str, list[str]]] = {}
        for receipt in receipts:
            for condition_key, task in (receipt.get("tasks") or {}).items():
                task_id = task.get("task_id")
                if not task_id:
                    continue
                tid = str(task_id)
                if _receipt_task_is_measured(task):
                    task_coverage[tid] = "measured"
                    # PV8/PV9/PV10：人工计时只覆盖时间，不覆盖辅助服务费用；「有 run」也只证明
                    # run 存在，不证明每个固有组件都有账。协议适用的固有模型组件（writer/review）
                    # 必须逐个有挂到该任务（task_id / run_id / attempt_id）的费用事实——一笔工具费
                    # 或只有 writer 的账都不能替缺失的组件作证，其它任务的类别覆盖也不能代签。
                    # 原流程任务按设计不用模型，计时即覆盖（PV4 合法通路保留）；补齐即解除阻断。
                    condition = str(task.get("condition") or condition_key or "")
                    if condition == C.CONDITION_ASSISTED:
                        uncovered = _assisted_task_uncovered_components(task, receipt, applicable_components)
                        if uncovered:
                            # 有 run 缺组件账 = 补齐费用录入；无 run 无费用事实 = 先补测量/用量证据。
                            reason = "assisted_task_model_cost_unbilled" if task.get("attempts") else "assisted_task_without_usage_or_cost_evidence"
                            task_cost_blocked.setdefault(tid, (reason, uncovered))
                        else:
                            task_cost_blocked.pop(tid, None)
                    else:
                        task_cost_blocked.pop(tid, None)
                else:
                    task_coverage.setdefault(tid, "shell")
        for task_id in sorted(tasks):
            coverage = task_coverage.get(task_id)
            if coverage == "measured" and task_id not in task_cost_blocked:
                continue
            if coverage is None:
                reason = "no_measurement_receipt_for_assigned_task"
            elif coverage == "shell":
                reason = "measurement_receipt_without_task_evidence"
            else:
                reason = task_cost_blocked[task_id][0]
            unknown_components.append(
                {
                    "component": "unmeasured_task",
                    "cost_id": f"unmeasured_task:{task_id}",
                    "run_id": None,
                    "attempt_id": None,
                    "quantity": None,
                    "unit": None,
                    "reason": reason,
                    "receipt_id": None,
                    # 缺哪些组件写进条目——补账动作直接可读（仅阻断类原因有）。
                    "uncovered_components": task_cost_blocked[task_id][1] if task_id in task_cost_blocked else None,
                }
            )
        observed_components = {
            str(item.get("component"))
            for receipt in receipts
            for item in (receipt.get("cost_items") or ())
            if item.get("selected")
        }
        observed_components |= {str(e["payload"]["cost_item"].get("component")) for e in pilot_cost_events}
        accounted = observed_components | {str(c.get("component")) for c in unknown_components} | set(not_applicable)
        for component in sorted(C.COST_COMPONENTS - accounted):
            unknown_components.append(
                {
                    "component": component,
                    "cost_id": f"cost_category:{component}",
                    "run_id": None,
                    "attempt_id": None,
                    "quantity": None,
                    "unit": None,
                    "reason": "cost_category_unobserved",
                    "receipt_id": None,
                }
            )
    if not receipts and not pilot_cost_events:
        full_cost_status = "unknown"
        full_cost_reason = "no_cost_evidence"
    elif unknown_components:
        full_cost_status = "unknown"
        full_cost_reason = "unknown_components_present"
    elif estimated:
        full_cost_status = "estimated"
        full_cost_reason = "estimated_components_present"
    else:
        full_cost_status = "known"
        full_cost_reason = None
    revenue_out = {currency: float(amount) for currency, amount in sorted(revenue.items())}
    gross_margin: float | None = None
    gross_margin_reason: str | None
    if full_cost_status != "known":
        gross_margin_reason = f"cost_{full_cost_status}"
    elif not revenue_out:
        gross_margin_reason = "no_verified_revenue"
    elif len(revenue_out) != 1 or set(revenue_out) != set(known):
        gross_margin_reason = "currency_mismatch_no_fx"
    else:
        currency = next(iter(revenue_out))
        rev = revenue[currency]
        gross_margin = float(round((rev - known[currency]) / rev, 4)) if rev else None
        gross_margin_reason = None if rev else "zero_revenue"
    metrics.append(
        _metric(
            "cost_full_status",
            None,
            "status",
            denominator_ids=[str(r.get("receipt_id")) for r in receipts],
            unknown=[
                {
                    "id": str(c.get("cost_id") or c.get("attempt_id") or c.get("component")),
                    "reason": str(c.get("reason")),
                    # PV13：缺哪个组件必须穿过公开投影层——06 从公开结果直接知道补哪笔账。
                    **({"uncovered_components": list(c["uncovered_components"])} if c.get("uncovered_components") else {}),
                }
                for c in unknown_components
            ],
            detail={
                "known_cost_by_currency": {k: float(v) for k, v in sorted(known.items())},
                "estimated_cost_by_currency": {k: float(v) for k, v in sorted(estimated.items())},
                "unknown_component_count": len(unknown_components),
                "not_applicable_components": not_applicable,
                "manual_rescue_minutes": float(manual_minutes),
                "full_cost_status": full_cost_status,
                "full_cost_reason": full_cost_reason,
                "revenue_by_currency": revenue_out,
                "gross_margin": gross_margin,
                "gross_margin_reason": gross_margin_reason,
                "invalid_receipts_included": invalid_receipts,
            },
        )
    )
    results.append(_criterion("cost", C.VERDICT_OBSERVED_ONLY if (receipts or pilot_cost_events) else C.VERDICT_UNKNOWN, full_cost_reason or "full_cost_known", metric_ids=["cost_full_status"], unknown_kind=None if (receipts or pilot_cost_events) else UNKNOWN_SAMPLE))

    verdicts = {r["criterion_id"]: r["verdict"] for r in results}
    if verdicts.get("completion_quality") == C.VERDICT_FAIL:
        recommendation = "pause_recruitment"
    elif all(verdicts.get(k) == C.VERDICT_PASS for k in ("completion_quality", "time_saving", "proactive_reuse")):
        recommendation = "continue_validation"
    else:
        recommendation = "keep_observing"

    return {
        "metrics": metrics,
        "criteria_results": results,
        "recommendation": recommendation,
        "task_count": len(tasks),
        "receipt_count": len(receipts),
        "invalid_receipts": invalid_receipts,
        "has_verified_payment": bool(first_payers),
    }


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------


def summarize(
    receipts: Iterable[Any],
    assignments: Iterable[Any],
    protocol: Mapping[str, Any],
    *,
    cohort_events: Iterable[Any] = (),
    due_rechecks: Sequence[Mapping[str, Any]] | None = None,
    as_of: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """汇总为 PilotSummary。

    - ``receipts``：``measure_pair`` 产出的收据；
    - ``assignments``：全部 ``assignment_created`` 事件（含没产生收据的分配，它们要进分母）；
    - ``cohort_events``：参与者 / 试点级事件（reuse_observed、recheck_*、consent_changed、
      payment_recorded、试点级 cost_recorded）；
    - ``due_rechecks``：06 从 01 取到的到期判断清单 ``[{object_ref, due_at, accessible}]``；
      为 None 时回检指标 ``unknown(due_list_unavailable)``；
    - ``as_of``：市场日 / 截止时点（ISO 日期或时间），缺省用协议 ``cohort_window.end``。
    """
    proto = validate_protocol(protocol)
    p_hash = protocol_hash(proto)
    crit = criteria(proto)
    rule_versions = exclusion_rule_versions(proto)
    cases = case_index(proto)
    as_of_dt = _resolve_as_of(as_of, proto)

    errors: list[dict[str, str]] = []
    limitations: set[str] = set()
    all_receipts = _dedupe_receipts(receipts, p_hash, errors=errors, limitations=limitations)

    prepared = prepare_events(list(assignments) + list(cohort_events), protocol=proto)
    accepted = prepared.accepted
    assignment_events = [e for e in accepted if e["event_type"] == "assignment_created"]
    other_events = [e for e in accepted if e["event_type"] != "assignment_created"]

    real_receipts = [r for r in all_receipts if not _is_synthetic_receipt(r)]
    synthetic_receipts = [r for r in all_receipts if _is_synthetic_receipt(r)]
    real_assignments = [e for e in assignment_events if not _is_synthetic_event(e)]
    synthetic_assignments = [e for e in assignment_events if _is_synthetic_event(e)]
    real_events = [e for e in other_events if not _is_synthetic_event(e)]
    synthetic_events = [e for e in other_events if _is_synthetic_event(e)]

    block_kwargs = {"proto": proto, "crit": crit, "as_of": as_of_dt, "due_rechecks": due_rechecks, "rule_versions": rule_versions, "cases": cases}
    real_inputs = bool(real_receipts or real_assignments or real_events)
    if real_inputs:
        real_block = _compute_block(real_receipts, real_assignments, real_events, **block_kwargs)
    else:
        # 没有任何真人输入时，到期清单上「0 完成」不是一个真人读数，而是根本没测；
        # 不让它显示成 0.0。
        real_block = _compute_block(real_receipts, real_assignments, real_events, **{**block_kwargs, "due_rechecks": None}, due_unavailable_reason="no_real_inputs")
    synthetic_block: dict[str, Any] | None = None
    if synthetic_receipts or synthetic_assignments or synthetic_events:
        computed = _compute_block(synthetic_receipts, synthetic_assignments, synthetic_events, **block_kwargs)
        synthetic_block = {
            "synthetic": True,
            "counts_toward_field": False,
            "metrics": computed["metrics"],
            "criteria_results": computed["criteria_results"],
            "recommendation": computed["recommendation"],
            "receipt_count": computed["receipt_count"],
            "task_count": computed["task_count"],
        }
        limitations.add("synthetic_inputs_present")

    owners = sorted({str(r.get("owner_user_id")) for r in all_receipts if r.get("owner_user_id")} | {str(e["owner_user_id"]) for e in accepted})
    owner = owners[0] if len(owners) == 1 else None
    if len(owners) > 1:
        limitations.add("multiple_owners")
    if errors:
        limitations.add("receipt_errors")
    if real_block["invalid_receipts"]:
        limitations.add(f"invalid_receipts:{len(real_block['invalid_receipts'])}")
    if due_rechecks is None:
        limitations.add("due_list_unavailable")

    if errors:
        engineering_status = C.ENGINEERING_INPUT_ERROR
    elif not all_receipts and not accepted:
        engineering_status = C.ENGINEERING_NO_INPUT
    else:
        engineering_status = C.ENGINEERING_COMPLETE

    effect = [r for r in real_block["criteria_results"] if r["criterion_id"] in _EFFECT_CRITERIA]
    if not real_inputs:
        field_status = C.FIELD_PENDING
        limitations.add("real_participants_absent")
    elif any(r["verdict"] in {C.VERDICT_PASS, C.VERDICT_FAIL, C.VERDICT_OBSERVED_ONLY} for r in effect):
        field_status = C.FIELD_OBSERVED
    elif any(r.get("unknown_kind") in _GAP_KINDS for r in effect):
        field_status = C.FIELD_INCONCLUSIVE
    else:
        field_status = C.FIELD_COLLECTING
    commercial_status = C.COMMERCIAL_OBSERVED if real_block["has_verified_payment"] else C.COMMERCIAL_UNSTARTED

    source_versions = {"code_shas": set(), "protocol_versions": set(), "artifact_hashes": set()}
    for receipt in all_receipts:
        for key in source_versions:
            source_versions[key] |= {str(v) for v in (receipt.get("source_versions") or {}).get(key, ())}
    for event in accepted:
        source_versions["code_shas"].add(str(event["source_version"].get("code_sha")))
        source_versions["protocol_versions"].add(str(event["source_version"].get("protocol_version")))

    summary: dict[str, Any] = {
        "schema_version": C.SUMMARY_SCHEMA,
        "summary_id": None,
        "owner_user_id": owner,
        "pilot_id": proto["pilot_id"],
        "generated_at": _now_iso(now),
        "as_of": as_of_dt.isoformat(),
        "protocol_version": proto["protocol_version"],
        "protocol_hash": p_hash,
        "cohort_window": dict(proto["cohort_window"]),
        "source_receipt_ids": sorted(str(r.get("receipt_id")) for r in all_receipts),
        "source_event_hash": hash_ids([f"{e['event_id']}:{prepared.content_hashes.get(e['event_id'], '')}" for e in accepted]),
        "source_versions": {key: sorted(values) for key, values in source_versions.items()},
        "metrics": real_block["metrics"],
        "criteria_results": real_block["criteria_results"],
        "recommendation": real_block["recommendation"],
        "engineering_status": engineering_status,
        "field_status": field_status,
        "commercial_status": commercial_status,
        "limitations": sorted(limitations),
        "input_errors": sorted(errors, key=lambda item: (item["code"], item["detail"])),
        "provenance": {
            "real_receipts": len(real_receipts),
            "synthetic_receipts": len(synthetic_receipts),
            "real_events": len(real_assignments) + len(real_events),
            "synthetic_events": len(synthetic_assignments) + len(synthetic_events),
            "synthetic": bool(synthetic_block),
        },
        "synthetic_check": synthetic_block,
        "event_accounting": prepared.accounting(),
    }
    summary["summary_id"] = content_id("ps", summary, drop_keys=frozenset({"generated_at", "summary_id", "event_accounting"}))
    return summary


__all__ = ["UNKNOWN_CONSENT", "UNKNOWN_GAP", "UNKNOWN_SAMPLE", "UNKNOWN_UNSTARTED", "summarize"]
