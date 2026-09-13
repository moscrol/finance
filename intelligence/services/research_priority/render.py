"""02 · 投影：把 ``research-priority/v1`` 报告渲染成不丢理由的用户视图与 Markdown。

视图只做标签翻译与字段挑选，不重排、不重算、不新增判断。每条任务都带
``click_payload``（task_id、source_refs、conversation_id、原 scope），供 06 点击时精确携带
（spec §6：不用自然语言标题猜目标）。
"""

from __future__ import annotations

from typing import Any

from . import contracts as c

EFFECT_LABELS = {
    c.EFFECT_ABANDON: "复核放弃/降级条件",
    c.EFFECT_REVIEW_CHANGED: "复核变化的依赖证据",
    c.EFFECT_VERIFY_DUE: "核查到期条件",
    c.EFFECT_FILL_GAP: "补证据缺口",
    c.EFFECT_EXPLORE: "探索",
}
AVAILABILITY_LABELS = {
    c.AVAIL_ACTIONABLE: "今天可做",
    c.AVAIL_WAITING_RELEASE: "等资料发布",
    c.AVAIL_MISSING_PERMISSION: "缺权限",
    c.AVAIL_MISSING_DATA: "缺数据",
    c.AVAIL_UNSUPPORTED: "系统不支持",
}
REASON_LABELS = {
    c.DEFER_MAX_ITEMS: "超出本次条数上限",
    c.DEFER_PER_OBJECT: "同一判断已有一项入选",
    c.DEFER_OVER_BUDGET: "超出剩余时间预算",
    c.DEFER_EFFORT_UNKNOWN: "耗时未知，不占有限预算",
    c.DEFER_USER_SNOOZED: "用户已选择稍后处理",
    c.AVAIL_WAITING_RELEASE: "等资料发布",
    c.AVAIL_MISSING_PERMISSION: "缺权限",
    c.AVAIL_MISSING_DATA: "缺数据",
    c.AVAIL_UNSUPPORTED: "系统不支持",
    c.BLOCK_NOT_YET_DUE: "条件尚未到期",
    c.BLOCK_FUTURE_RECORD: "记录晚于评估时刻，资料尚不可知",
}
CONDITION_LABELS = {True: "已触发", False: "未触发", c.CONDITION_UNKNOWN: "未知", None: "无确定性条件"}


def render_view(report: dict[str, Any]) -> dict[str, Any]:
    if report.get("schema_version") != c.SCHEMA_REPORT:
        raise c.ContractError("unknown_schema", f"report schema_version={report.get('schema_version')!r}")
    totals = report["totals"]
    return {
        "schema_version": c.SCHEMA_VIEW,
        "report_id": report["id"],
        "owner_user_id": report["owner_user_id"],
        "generated_at": report.get("generated_at"),
        "evaluation_at": report["evaluation_at"],
        "as_of": report.get("as_of"),
        "knowledge_cutoff": report.get("knowledge_cutoff"),
        "policy_version": report["policy_version"],
        "input_digest": report["input_digest"],
        "budget": dict(report["budget"]),
        "summary": {
            "候选": totals["candidate_count"],
            "入选": totals["selected_count"],
            "推迟": totals["deferred_count"],
            "等待区": totals["blocked_count"],
            "耗时未知": totals["unknown_effort_count"],
            "已知总耗时秒": totals["known_seconds"],
            "未入选的关键项": len(report["critical_not_selected_ids"]),
            "预算": "未给预算" if report["budget"]["minutes"] is None else f"{report['budget']['minutes']:g} 分钟",
        },
        "selected": [_selected_row(row) for row in report["selected"]],
        "deferred": [_deferred_row(row) for row in report["deferred"]],
        "blocked": [_blocked_row(row) for row in report["blocked"]],
        "critical_not_selected_ids": list(report["critical_not_selected_ids"]),
        "gaps": list(report["gaps"]),
        "limitations": list(report["limitations"]),
        "synthetic": bool(report.get("synthetic")),
        "hindsight": bool(report.get("hindsight")),
    }


def render_markdown(report: dict[str, Any]) -> str:
    view = render_view(report)
    lines = [
        f"# 下一步研究排序（{view['policy_version']}）",
        f"- 评估时刻 {view['evaluation_at']}；市场日 {view['as_of'] or '未记录'}；资料截止 {view['knowledge_cutoff'] or '未记录'}",
        f"- 预算：{view['summary']['预算']}；候选 {view['summary']['候选']}，入选 {view['summary']['入选']}，"
        f"推迟 {view['summary']['推迟']}，等待区 {view['summary']['等待区']}，耗时未知 {view['summary']['耗时未知']}",
    ]
    if view["synthetic"]:
        lines.append("- ⚠ 输入含 synthetic 夹具，仅作工程验收")
    if view["hindsight"]:
        lines.append("- ⚠ 含 hindsight 回放来源：只供人工复核，不是当前优先级")
    if view["critical_not_selected_ids"]:
        lines.append(f"- ⚠ 未入选的关键（第 1 组）任务：{', '.join(view['critical_not_selected_ids'])}")
    # 09-06 终局 §4.5 规矩 2：缺口与限制排在事实块之前——它们是判读的边界条件，不是脚注。
    lines.append("")
    lines.append("## 限制与缺口")
    for text in view["limitations"]:
        lines.append(f"- {text}")
    for gap in view["gaps"]:
        lines.append(f"- 缺口 {gap['reason']}：{len(gap.get('task_ids') or [])} 项")
    lines.append("")
    lines.append("## 入选")
    if not view["selected"]:
        lines.append("（无）")
    for row in view["selected"]:
        lines.append(f"{row['rank']}. **{row['标题']}**  ·  {row['组']}  ·  耗时 {row['耗时']}")
        for reason in row["为什么在前"]:
            lines.append(f"   - {reason}")
    lines.append("")
    lines.append("## 推迟")
    if not view["deferred"]:
        lines.append("（无）")
    for row in view["deferred"]:
        lines.append(f"- {row['标题']}  ·  {row['原因']}（{row['说明']}）  ·  {row['组']}")
    lines.append("")
    lines.append("## 等待区")
    if not view["blocked"]:
        lines.append("（无）")
    for row in view["blocked"]:
        lines.append(f"- {row['标题']}  ·  {row['原因']}  ·  解除条件：{row['解除条件']}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------


def _task_view(task: dict[str, Any]) -> dict[str, Any]:
    seconds = task["effort"]["seconds"]
    return {
        "task_id": task["id"],
        "标题": task["question"],
        "动作类型": EFFECT_LABELS.get(task["effect_kind"], task["effect_kind"]),
        "受影响对象": sorted({c.object_label(r) for r in task["object_refs"]}),
        "已绑定判断": not task["legacy_unbound"],
        "条件判定": CONDITION_LABELS.get(task["condition_result"], str(task["condition_result"])),
        "判别证据": task["discriminating_evidence"],
        "还缺什么": sorted({g["reason"] + (f"（{g['ref']}）" if g.get("ref") else "") for g in task["gaps"]}),
        "结束条件": task["completion_condition"],
        "需人工签核": task["human_review_required"],
        "耗时": "未知" if seconds is None else f"{seconds:g} 秒（{task['effort']['kind']}）",
        "可执行状态": AVAILABILITY_LABELS.get(task["availability"], task["availability"]),
        "到期": task.get("due_at"),
        "市场日": task.get("as_of"),
        "资料截止": task.get("knowledge_cutoff"),
        "pit_grade": task["pit_grade"],
        "hindsight": task["hindsight"],
        "来源": [c.object_label(r) for r in task["merged_source_refs"]],
        "维护项": list(task["maintenance_item_ids"]),
        "click_payload": {
            "task_id": task["id"],
            "source_refs": [dict(r) for r in task["merged_source_refs"]],
            "conversation_id": task["scope"]["conversation_id"],
            "scope": dict(task["scope"]),
            "object_refs": [dict(r) for r in task["object_refs"]],
        },
    }


def _selected_row(row: dict[str, Any]) -> dict[str, Any]:
    view = _task_view(row["task"])
    view.update(
        {
            "rank": row["rank"],
            "组": f"第 {row['group']} 组｜{c.GROUP_LABELS[row['group']]}",
            "为什么在前": list(row["reasons"]),
            "预计秒数": row["estimated_seconds"],
        }
    )
    return view


def _deferred_row(row: dict[str, Any]) -> dict[str, Any]:
    view = _task_view(row["task"])
    view.update(
        {
            "组": f"第 {row['group']} 组｜{c.GROUP_LABELS[row['group']]}",
            "原因": REASON_LABELS.get(row["reason"], row["reason"]),
            "原因码": row["reason"],
            "说明": row["detail"],
        }
    )
    return view


def _blocked_row(row: dict[str, Any]) -> dict[str, Any]:
    view = _task_view(row["task"])
    view.update(
        {
            "原因": REASON_LABELS.get(row["reason"], row["reason"]),
            "原因码": row["reason"],
            "解除条件": row["release_condition"],
            "可用时刻": row["available_at"],
        }
    )
    return view
