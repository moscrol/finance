"""02 · 排序与预算：确定性分组、去重合并、贪心预算与可对账报告。

对外只有 ``prioritize(candidates, policy, budget, evaluation_at)``。全程无模型、无 IO、
不读系统时钟：``evaluation_at`` 由调用方注入并冻结进 ``input_digest``，历史重放显式给
历史时刻即可（P13）。

三条不变量（测试反向证伪）：
* 每个去重后的候选恰好出现在 selected / deferred / blocked 之一，且重复来源保存在
  ``merged_source_refs`` 里，不静默消失（P06 / P10 / P12）。
* 耗时未知不计为 0：有限预算下入 deferred(effort_unknown)（P05）。
* 只有 ``condition_result=true`` 且效果为 abandon_or_downgrade 的任务进第 1 组；
  hash 变化最多第 2 组（P02）。
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from . import contracts as c


def prioritize(
    candidates: Any,
    policy: Any = None,
    budget: Any = None,
    evaluation_at: Any = None,
    *,
    owner_user_id: str | None = None,
) -> dict[str, Any]:
    """按 spec §5 规则生成 ``research-priority/v1`` 报告。

    ``candidates`` 可以是任务列表，也可以是 ``adapt_candidates`` 的返回对象（取其 ``tasks``
    与 ``owner_user_id``）。空输入必须显式给 ``owner_user_id`` 才能出「结构完整的零项报告」。
    """
    eval_at = c.parse_evaluation_at(evaluation_at)
    pol = c.Policy.from_value(policy)
    bud = c.Budget.from_value(budget)

    tasks_raw, owner = _unpack(candidates, owner_user_id)
    validated = [c.validate_task(t, owner_user_id=owner, index=i) for i, t in enumerate(tasks_raw)]
    # 可知性先行（spec §5.1）：逐候选先判「记录晚于 evaluation_at」，未来记录与当前记录分开合并。
    # 合并键已含观测窗口，两侧本就不可能同键；这里再把顺序显式写死，防止后来放宽键时
    # 又出现「未来记录把当天的关键条件一起吞进 blocked」。
    knowable = [t for t in validated if not _is_future_record(t, eval_at)]
    future = [t for t in validated if _is_future_record(t, eval_at)]
    unique_knowable, merged_knowable = _merge(knowable)
    unique_future, merged_future = _merge(future)
    unique = unique_knowable + unique_future
    merged_count = merged_knowable + merged_future
    unique.sort(key=lambda t: t["id"])

    input_digest = c.sha256_hex(
        c.canonical_json(
            {
                "owner_user_id": owner,
                "policy": pol.to_dict(),
                "budget": {"minutes": bud.minutes},
                "evaluation_at": c.iso_utc(eval_at),
                "candidates": unique,
            }
        )
    )

    actionable: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for task in unique:
        entry = _block_entry(task, eval_at)
        if entry is not None:
            blocked.append(entry)
        else:
            actionable.append(task)

    ranked = sorted(actionable, key=lambda t: _sort_key(t, eval_at))
    selected, deferred = _select(ranked, pol, bud)
    selected_ids = {row["task"]["id"] for row in selected}
    critical_not_selected = [
        t["id"] for t in ranked if _group_of(t) == c.GROUP_ABANDON and t["id"] not in selected_ids
    ]

    as_of_values = sorted({t["as_of"] for t in unique if t["as_of"]})
    cutoffs = sorted({t["knowledge_cutoff"] for t in unique if t["knowledge_cutoff"]}, key=_cutoff_sort)
    report_gaps = _report_gaps(unique, blocked)
    known_seconds = sum(row["estimated_seconds"] for row in selected if row["estimated_seconds"] is not None)
    return {
        "schema_version": c.SCHEMA_REPORT,
        "id": "rp_" + c.sha256_hex(f"{owner}|{input_digest}")[:16],
        "owner_user_id": owner,
        # generated_at 是展示元数据，由调用方在渲染/落盘时填，不进 id / input_digest。
        "generated_at": None,
        "evaluation_at": c.iso_utc(eval_at),
        "as_of": as_of_values[-1] if as_of_values else None,
        "knowledge_cutoff": cutoffs[-1] if cutoffs else None,
        "policy_version": pol.policy_version,
        "input_digest": input_digest,
        "budget": {"minutes": bud.minutes, "max_items": pol.max_items, "max_per_object": pol.max_per_object},
        "selected": selected,
        "deferred": deferred,
        "blocked": blocked,
        "critical_not_selected_ids": critical_not_selected,
        "totals": {
            "candidate_count": len(unique),
            "input_count": len(validated),
            "merged_count": merged_count,
            "selected_count": len(selected),
            "deferred_count": len(deferred),
            "blocked_count": len(blocked),
            "known_seconds": known_seconds,
            "unknown_effort_count": sum(1 for t in unique if t["effort"]["seconds"] is None),
        },
        "gaps": report_gaps,
        "limitations": _limitations(bud, hindsight=any(t["hindsight"] for t in unique)),
        "synthetic": any(t.get("synthetic") for t in unique),
        # 09-06 终局 §4.1 / §4.5：hindsight 是强制可见的限制，只供人工复核，不进校准与方法统计。
        "hindsight": any(t["hindsight"] for t in unique),
    }


# ---------------------------------------------------------------------------
# 输入拆包与合并
# ---------------------------------------------------------------------------


def _unpack(candidates: Any, owner_user_id: str | None) -> tuple[list[Any], str]:
    if isinstance(candidates, dict) and "tasks" in candidates:
        if candidates.get("schema_version") not in (None, c.SCHEMA_CANDIDATES):
            raise c.ContractError("unknown_schema", f"candidates schema_version={candidates.get('schema_version')!r}")
        tasks = list(candidates.get("tasks") or [])
        embedded = candidates.get("owner_user_id")
        if owner_user_id is not None and embedded is not None and embedded != owner_user_id:
            raise c.ContractError("owner_mismatch", "candidates.owner_user_id 与调用方 owner 不一致")
        owner = owner_user_id or embedded
    elif isinstance(candidates, (list, tuple)):
        tasks = list(candidates)
        owner = owner_user_id
        if owner is None and tasks:
            first = tasks[0].get("owner_user_id") if isinstance(tasks[0], dict) else None
            owner = first if isinstance(first, str) and first.strip() else None
    elif candidates is None:
        tasks, owner = [], owner_user_id
    else:
        raise c.ContractError("invalid_task", "candidates 必须是列表或 adapt_candidates 的返回对象")
    if not isinstance(owner, str) or not owner.strip():
        raise c.ContractError("owner_missing", "无法确定 owner_user_id（空输入需显式传入）")
    return tasks, owner


def _merge(tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """按合并键归并；同键任务合成一个，受影响对象取并集，来源全部保留。返回 (唯一任务, 被合并条数)。"""
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for task in tasks:
        groups.setdefault(c.identity_key(task), []).append(task)
    unique: list[dict[str, Any]] = []
    merged_count = 0
    for key, members in groups.items():
        members = sorted(members, key=lambda t: (t["id"], c.canonical_json(t)))
        unique.append(_merge_members(key, members))
        merged_count += len(members) - 1
    return unique, merged_count


def _merge_members(key: tuple[Any, ...], members: list[dict[str, Any]]) -> dict[str, Any]:
    head = members[0]
    merged: dict[str, Any] = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in head.items()}
    merged["id"] = c.task_id_for(key)
    if len(members) == 1:
        merged["source_task_ids"] = sorted(set(head["source_task_ids"]) | {head["id"]})
        return merged

    def _dedup_refs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for ref in rows:
            seen.setdefault(c.ref_identity(ref), ref)
        return [seen[k] for k in sorted(seen)]

    merged["object_refs"] = _dedup_refs([r for m in members for r in m["object_refs"]])
    merged["effect_evidence_refs"] = _dedup_refs([r for m in members for r in m["effect_evidence_refs"]])
    merged["merged_source_refs"] = _dedup_refs([r for m in members for r in m["merged_source_refs"]])
    merged["source_task_ids"] = sorted({tid for m in members for tid in (m["source_task_ids"] + [m["id"]])})
    merged["maintenance_item_ids"] = sorted({mid for m in members for mid in m["maintenance_item_ids"]})
    merged["legacy_unbound"] = not merged["object_refs"]
    merged["scope"] = {
        "conversation_id": head["scope"]["conversation_id"],
        "entity_refs": sorted({e for m in members for e in m["scope"]["entity_refs"]}),
    }

    results = {c.canonical_json(m["condition_result"]) for m in members}
    if len(results) > 1:
        merged["condition_result"] = c.CONDITION_UNKNOWN
        merged.setdefault("gaps", []).append(
            {"reason": "condition_result_conflict", "ref": None, "checked_at": None, "retryable": None}
        )
    dues = [m["due_at"] for m in members if m["due_at"]]
    merged["due_at"] = min(dues, key=lambda v: c.parse_instant(v, field="due_at")) if dues else None
    avail = [m["available_at"] for m in members if m["available_at"]]
    merged["available_at"] = max(avail, key=lambda v: c.parse_instant(v, field="available_at")) if avail else None
    known = [m["effort"] for m in members if m["effort"]["seconds"] is not None]
    # 合成任务只核查一次证据；取已知估时的最大值，宁可高估不把预算撑爆。
    merged["effort"] = max(known, key=lambda e: e["seconds"]) if known else {"seconds": None, "kind": "unknown", "source_ref": None}
    # pit_grade 取最弱者（PIT_GRADES 按 strict → unverifiable 递弱排列）。
    merged["pit_grade"] = max((m["pit_grade"] for m in members), key=c.PIT_GRADES.index)
    merged["human_review_required"] = any(m["human_review_required"] for m in members)
    seen_gaps: dict[str, dict[str, Any]] = {}
    for m in members:
        for gap in m["gaps"]:
            seen_gaps.setdefault(c.canonical_json(gap), gap)
    for gap in merged.get("gaps", []):
        seen_gaps.setdefault(c.canonical_json(gap), gap)
    merged["gaps"] = [seen_gaps[k] for k in sorted(seen_gaps)]
    statuses = [m["management_status"] for m in members if m["management_status"]]
    # 任一来源仍 open/claimed 就不算「用户已推迟」；全部 snoozed 才 snoozed。
    merged["management_status"] = (
        "snoozed" if statuses and all(s == "snoozed" for s in statuses) else (sorted(set(statuses))[0] if statuses else None)
    )
    merged["synthetic"] = any(m.get("synthetic") for m in members)
    merged["hindsight"] = any(m["hindsight"] for m in members)  # 键已隔离，成员同值；显式写出以防漂
    # as_of / knowledge_cutoff 已进合并键（c.observation_window），成员必然同窗口，沿用 head 的值即可。
    # 不再对不同市场日取最大：那条路径会把当天可知的记录抬成未来记录，整组一起判 future_record。
    assert {c.observation_window(m) for m in members} == {c.observation_window(head)}
    # 合成任务的问句 / 结束条件要覆盖全部受影响对象与维护项，不能只剩首条来源那句；
    # 纯重复读取（同一来源出现多次）不算合成，不改写文字。
    distinct_sources = len(merged["merged_source_refs"])
    if distinct_sources > 1:
        labels = "、".join(sorted({c.object_label(r) for r in merged["object_refs"]})) or "未绑定判断"
        merged["question"] = f"{head['question']}（同一证据同时影响 {distinct_sources} 条来源：{labels}）"
    other_items = [mid for mid in merged["maintenance_item_ids"] if mid not in head["maintenance_item_ids"]]
    if other_items:
        merged["completion_condition"] = f"{head['completion_condition']}；同样对维护项 {', '.join(other_items)} 记录复核动作"
    return merged


# ---------------------------------------------------------------------------
# 可执行性与分组
# ---------------------------------------------------------------------------


def _is_future_record(task: dict[str, Any], eval_at: datetime) -> bool:
    """记录的观测窗口是否晚于评估时刻（P09 / P13）。合并前后共用同一判据。"""
    cutoff = c.parse_instant(task["knowledge_cutoff"], field="knowledge_cutoff")
    as_of = c.parse_market_date(task["as_of"], field="as_of")
    return (cutoff is not None and cutoff > eval_at) or (as_of is not None and as_of > eval_at.date())


def _block_entry(task: dict[str, Any], eval_at: datetime) -> dict[str, Any] | None:
    """返回 blocked 条目或 None（可排序）。时间状态只按 evaluation_at 判定（P13）。"""
    if _is_future_record(task, eval_at):
        later = max([v for v in (task["knowledge_cutoff"], task["as_of"]) if v], key=lambda v: c.parse_instant(v, field="x"))
        return _blocked(
            task,
            c.BLOCK_FUTURE_RECORD,
            f"记录的 knowledge_cutoff / as_of 晚于评估时刻 {c.iso_utc(eval_at)}：资料尚不可知，不进入评分；到该时刻后重算",
            later,
        )
    availability = task["availability"]
    available_at = c.parse_instant(task["available_at"], field="available_at")
    if availability == c.AVAIL_WAITING_RELEASE:
        if available_at is not None and available_at <= eval_at:
            availability = c.AVAIL_ACTIONABLE
        else:
            return _blocked(
                task,
                c.AVAIL_WAITING_RELEASE,
                task["availability_reason"] or f"资料发布后可核查（available_at={task['available_at'] or '未知'}）",
                task["available_at"],
            )
    if availability != c.AVAIL_ACTIONABLE:
        return _blocked(
            task,
            availability,
            task["availability_reason"] or {
                c.AVAIL_MISSING_PERMISSION: "取得该引用的读取权限后可核查",
                c.AVAIL_MISSING_DATA: "补齐缺失数据后可核查",
                c.AVAIL_UNSUPPORTED: "当前系统不支持该操作，需人工处理",
            }.get(availability, "解除条件未知"),
            task["available_at"],
        )
    due = c.parse_instant(task["due_at"], field="due_at")
    if task["effect_kind"] == c.EFFECT_VERIFY_DUE and due is not None and due > eval_at:
        return _blocked(task, c.BLOCK_NOT_YET_DUE, f"到期时刻 {task['due_at']} 之后可核查（按 evaluation_at 判定）", task["due_at"])
    return None


def _blocked(task: dict[str, Any], reason: str, release_condition: str, available_at: Any) -> dict[str, Any]:
    return {"task": task, "reason": reason, "release_condition": release_condition, "available_at": available_at}


def _group_of(task: dict[str, Any]) -> int:
    if task["legacy_unbound"] or not task["object_refs"]:
        return c.GROUP_EXPLORE
    kind = task["effect_kind"]
    if kind == c.EFFECT_ABANDON and task["condition_result"] is True:
        return c.GROUP_ABANDON
    if kind == c.EFFECT_REVIEW_CHANGED:
        return c.GROUP_REVIEW_CHANGED
    if kind == c.EFFECT_VERIFY_DUE:
        return c.GROUP_VERIFY_DUE
    if kind == c.EFFECT_FILL_GAP:
        return c.GROUP_FILL_GAP
    return c.GROUP_EXPLORE


def _affected_objects(task: dict[str, Any]) -> int:
    return len({c.object_identity(task["owner_user_id"], r) for r in task["object_refs"]})


def _sort_key(task: dict[str, Any], eval_at: datetime) -> tuple[Any, ...]:
    due = c.parse_instant(task["due_at"], field="due_at")
    seconds = task["effort"]["seconds"]
    return (
        _group_of(task),
        0 if due is not None else 1,
        due.timestamp() if due is not None else 0.0,
        -_affected_objects(task),
        0 if seconds is not None else 1,
        seconds if seconds is not None else 0.0,
        task["id"],
    )


# ---------------------------------------------------------------------------
# 选取（贪心，不声称最优）与解释
# ---------------------------------------------------------------------------


def _select(
    ranked: list[dict[str, Any]], pol: c.Policy, bud: c.Budget
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    remaining = bud.seconds
    per_object: Counter = Counter()
    for task in ranked:
        seconds = task["effort"]["seconds"]
        objects = {c.object_identity(task["owner_user_id"], r) for r in task["object_refs"]}
        if task["management_status"] == "snoozed":
            deferred.append(_deferred(task, c.DEFER_USER_SNOOZED, "用户已选择稍后处理；到期由 01 恢复为 open"))
            continue
        if len(selected) >= pol.max_items:
            deferred.append(_deferred(task, c.DEFER_MAX_ITEMS, f"已达 max_items={pol.max_items}"))
            continue
        capped = sorted(o for o in objects if per_object[o] >= pol.max_per_object)
        if capped:
            deferred.append(
                _deferred(task, c.DEFER_PER_OBJECT, f"对象 {capped[0][1]}:{capped[0][2]} 已有 {pol.max_per_object} 项入选")
            )
            continue
        if remaining is not None:
            if seconds is None:
                deferred.append(_deferred(task, c.DEFER_EFFORT_UNKNOWN, "耗时未知，不计为 0 也不自动占用有限预算；可先估时或单独执行"))
                continue
            if remaining <= 0 or seconds > remaining:
                deferred.append(
                    _deferred(task, c.DEFER_OVER_BUDGET, f"需 {seconds:g} 秒，剩余预算 {max(remaining, 0):g} 秒")
                )
                continue
            remaining -= seconds
        selected.append(
            {
                "task": task,
                "rank": len(selected) + 1,
                "group": _group_of(task),
                "reasons": _reasons(task, remaining, bud),
                "estimated_seconds": seconds,
            }
        )
        for obj in objects:
            per_object[obj] += 1
    return selected, deferred


def _deferred(task: dict[str, Any], reason: str, detail: str) -> dict[str, Any]:
    return {"task": task, "reason": reason, "detail": detail, "group": _group_of(task)}


def _evidence_label(ref: dict[str, Any]) -> str:
    """证据引用的可读标签；frozen_llm 散文按 09-06 终局 §4.2 带标记（可读不可重算，不进任何度量）。"""
    text = c.object_label(ref) + (f"@{ref['version_or_hash'][:12]}" if ref.get("version_or_hash") else "")
    if ref.get("namespace") == "frozen_llm":
        text += "［frozen_llm 散文：可读不可重算］"
    return text


def _reasons(task: dict[str, Any], remaining: float | None, bud: c.Budget) -> list[str]:
    """解释只由输入事实与规则生成：为什么排这里、依赖哪条判断、缺什么、做什么、何时停。"""
    group = _group_of(task)
    lines = [f"第 {group} 组：{c.GROUP_LABELS[group]}"]
    if task["object_refs"]:
        labels = sorted({c.object_label(r) for r in task["object_refs"]})
        lines.append(f"依赖判断：{'、'.join(labels)}（受影响对象 {_affected_objects(task)} 个）")
    else:
        lines.append("未绑定任何已登记判断（legacy_unbound），本项不维护原判断")
    if task["effect_evidence_refs"]:
        refs = sorted({_evidence_label(r) for r in task["effect_evidence_refs"]})
        lines.append(f"触发/核查证据：{'、'.join(refs)}")
    if task["hindsight"]:
        lines.append("来源为 hindsight 回放（历史 as_of 配更晚 cutoff）：只供人工复核，不进校准或方法统计")
    if task["condition_result"] is True:
        lines.append("条件判定：true（已观测触发；按条件角色区分升级/降级/放弃/复核，不一律放弃）")
    elif task["condition_result"] == c.CONDITION_UNKNOWN:
        lines.append("条件判定：unknown（未观测到判定值，不视为触发）")
    if task["gaps"]:
        lines.append("还缺：" + "；".join(sorted({g["reason"] + (f"（{g['ref']}）" if g.get("ref") else "") for g in task["gaps"]})))
    lines.append(f"需要做：{task['question']}")
    lines.append(
        f"结束条件：{task['completion_condition']}" + ("（语义题，需人工签核，模型不得自行签完成）" if task["human_review_required"] else "")
    )
    if len(task["merged_source_refs"]) > 1:
        lines.append(f"合并自 {len(task['merged_source_refs'])} 条来源（同一证据服务多个判断，只核查一次）")
    due = task["due_at"] or "无期限"
    seconds = task["effort"]["seconds"]
    effort_text = "未知" if seconds is None else f"{seconds:g} 秒（{task['effort']['kind']}）"
    lines.append(f"同组排序依据：到期 {due}；受影响对象 {_affected_objects(task)} 个；耗时 {effort_text}")
    if bud.seconds is not None and remaining is not None:
        lines.append(f"预算：选入后剩余 {remaining:g} 秒")
    return lines


# ---------------------------------------------------------------------------
# 报告级缺口与限制
# ---------------------------------------------------------------------------


def _report_gaps(unique: list[dict[str, Any]], blocked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    unknown_effort = [t["id"] for t in unique if t["effort"]["seconds"] is None]
    if unknown_effort:
        gaps.append({"reason": "effort_unknown", "task_ids": unknown_effort, "retryable": True})
    no_cutoff = [t["id"] for t in unique if not t["knowledge_cutoff"]]
    if no_cutoff:
        gaps.append({"reason": "knowledge_cutoff_missing", "task_ids": no_cutoff, "retryable": True})
    future = [row["task"]["id"] for row in blocked if row["reason"] == c.BLOCK_FUTURE_RECORD]
    if future:
        gaps.append({"reason": "future_record_excluded", "task_ids": future, "retryable": True})
    unbound = [t["id"] for t in unique if t["legacy_unbound"]]
    if unbound:
        gaps.append({"reason": "legacy_unbound", "task_ids": unbound, "retryable": False})
    hindsight = [t["id"] for t in unique if t["hindsight"]]
    if hindsight:
        gaps.append({"reason": "hindsight_source", "task_ids": hindsight, "retryable": False})
    return gaps


def _limitations(bud: c.Budget, *, hindsight: bool = False) -> list[str]:
    lines = [
        "输出是确定性规则下的研究优先级，不是预期收益、信息价值或任何概率；不构成任何个股买卖建议。",
        "组号是优先序不是评分；同组顺序只由到期、受影响对象数、已知耗时与 id 决定。",
        "耗时未知的任务不按 0 计；未给预算时不推算完成时间。",
        "时间状态只按注入的 evaluation_at 判定，市场 as_of 与资料 knowledge_cutoff 另管数据可知性。",
    ]
    if bud.seconds is not None:
        lines.append("预算选择为按优先序的贪心扫描，不声称是最优分配。")
    if hindsight:
        lines.append("含 hindsight 回放来源：整份报告只供人工复核，不得作为当前优先级、不进校准或方法有效性统计。")
    return lines


def _cutoff_sort(value: str) -> float:
    instant = c.parse_instant(value, field="knowledge_cutoff")
    return instant.timestamp() if instant else 0.0
