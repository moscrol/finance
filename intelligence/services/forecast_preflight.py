from __future__ import annotations

from typing import Any


STATUS_READY = "ready"
STATUS_NEEDS_DEEPDIVE = "needs_deepdive"
STATUS_MISSING_DAILY_AGENT = "missing_daily_agent"

BLOCKING_BUCKETS = {
    "today_do_ima": "先补 IMA / DeepDive / 题材地图",
    "today_find_official_evidence": "先补公告 / 调研 / 订单 / 客户验证",
}


def build_forecast_preflight(
    report_or_queue: dict[str, Any],
    *,
    source_artifact: str | None = None,
    allow_draft: bool = True,
) -> dict[str, Any]:
    """Build the readiness gate for a market forecast / daily review.

    The input can be a full daily-agent report containing ``research_queue`` or
    the queue itself. The gate does not redo lifecycle analysis; it reuses the
    daily-agent research queue as the contract for what must be checked before a
    formal forecast is generated.
    """
    queue = _extract_queue(report_or_queue)
    if not queue:
        result = {
            "status": STATUS_MISSING_DAILY_AGENT,
            "can_generate_formal": False,
            "can_generate_draft": bool(allow_draft),
            "source_artifact": source_artifact or "-",
            "blocking_items": [],
            "next_steps": [
                "先生成或同步 daily-agent，再运行生命周期 / research_queue 查漏。",
                "若必须先写，只能生成带缺口标记的草稿，不能伪装成正式复盘。",
            ],
            "human_summary": "未读取到 daily-agent 研究队列；正式复盘前置查漏无法完成。",
        }
        result["prompt_block"] = render_preflight_prompt(result)
        return result

    blocking_items = _blocking_items(queue)
    if blocking_items:
        result = {
            "status": STATUS_NEEDS_DEEPDIVE,
            "can_generate_formal": False,
            "can_generate_draft": bool(allow_draft),
            "source_artifact": source_artifact or "-",
            "blocking_items": blocking_items,
            "next_steps": [
                "先让用户补 DeepDive / IMA / 题材地图或 L3 官方证据。",
                "ingest 完成并重跑 daily-agent 后，再生成正式复盘。",
                "如用户要求先看草稿，必须把 blocking_items 写成显式证据缺口。",
            ],
            "human_summary": f"正式复盘生成前需要先补 {len(blocking_items)} 个研究缺口。",
        }
        result["prompt_block"] = render_preflight_prompt(result)
        return result

    result = {
        "status": STATUS_READY,
        "can_generate_formal": True,
        "can_generate_draft": True,
        "source_artifact": source_artifact or "-",
        "blocking_items": [],
        "next_steps": ["可以生成正式复盘；仍需在输出中保留四源合议和盘后验证表。"],
        "human_summary": "daily-agent 查漏门禁通过，可以生成正式复盘。",
    }
    result["prompt_block"] = render_preflight_prompt(result)
    return result


def render_preflight_prompt(result: dict[str, Any]) -> str:
    lines = [
        "## 复盘前置查漏门（forecast_preflight）",
        f"- 状态：{result.get('status') or '-'}",
        f"- 来源：{result.get('source_artifact') or '-'}",
        f"- 可生成正式复盘：{'是' if result.get('can_generate_formal') else '否'}",
        f"- 可生成缺口草稿：{'是' if result.get('can_generate_draft') else '否'}",
        f"- 摘要：{result.get('human_summary') or '-'}",
    ]
    blocking = result.get("blocking_items") or []
    if blocking:
        lines.append("- 需要先补的 DeepDive / 证据缺口：")
        for item in blocking:
            stocks = "、".join(item.get("strong_stocks") or []) or "-"
            missing = "、".join(item.get("missing_layers") or []) or "-"
            lines.append(
                f"  - {item.get('theme') or '-'}｜{item.get('required_action') or '-'}"
                f"｜生命周期={item.get('lifecycle_stage') or '-'}｜缺={missing}｜强势股={stocks}"
            )
    steps = result.get("next_steps") or []
    if steps:
        lines.append("- 下一步：")
        lines.extend(f"  - {step}" for step in steps)
    return "\n".join(lines)


def _extract_queue(report_or_queue: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(report_or_queue, dict):
        return None
    maybe_queue = report_or_queue.get("research_queue")
    if isinstance(maybe_queue, dict):
        return maybe_queue
    if any(key in report_or_queue for key in BLOCKING_BUCKETS):
        return report_or_queue
    return None


def _blocking_items(queue: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for bucket, required_action in BLOCKING_BUCKETS.items():
        for raw in queue.get(bucket) or []:
            if not isinstance(raw, dict):
                continue
            items.append(
                {
                    "theme": str(raw.get("目标") or raw.get("theme") or "-"),
                    "bucket": bucket,
                    "action": str(raw.get("动作") or "-"),
                    "reason": str(raw.get("理由") or "-"),
                    "priority": raw.get("优先级"),
                    "lifecycle_stage": str(raw.get("生命周期阶段") or "-"),
                    "evidence_status": str(raw.get("证据状态") or "-"),
                    "missing_layers": [str(item) for item in (raw.get("缺失证据层") or [])],
                    "strong_stocks": [str(item) for item in (raw.get("强势股") or [])],
                    "required_action": required_action,
                }
            )
    items.sort(key=lambda item: float(item.get("priority") or 0), reverse=True)
    return items
