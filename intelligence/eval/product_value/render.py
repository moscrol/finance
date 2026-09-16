"""收据与总结的 Markdown 投影。只读合同字段，不再算任何数。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_STATUS_LABEL = {
    "valid": "有效",
    "incomplete": "不完整",
    "invalid": "无效",
    "pending": "待真人参与",
    "collecting": "收集中",
    "observed": "已有真实读数",
    "inconclusive": "有读数但缺口未补",
    "unstarted": "未开始",
    "engineering_complete": "工程完成",
    "no_input": "无输入",
    "input_error": "输入错误",
    "pass": "达标",
    "fail": "不达标",
    "unknown": "未知",
    "observed_only": "只展示读数",
}


def _label(value: Any) -> str:
    return _STATUS_LABEL.get(str(value), str(value))


def _fmt(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))
    return str(value)


def _synthetic_banner(flag: bool) -> list[str]:
    if not flag:
        return []
    return [
        "> **SYNTHETIC** — 输入含仿真夹具，本文件只用于工程验收；真人效果 / 方法支持 / 付费状态不得由此得出。",
        "",
    ]


def render_receipt_markdown(receipt: Mapping[str, Any]) -> str:
    lines = [f"# 测量收据 `{receipt.get('receipt_id')}`", ""]
    lines += _synthetic_banner(bool((receipt.get("provenance") or {}).get("synthetic")))
    lines += [
        f"- 配对：`{receipt.get('case_pair_id')}`（{receipt.get('category')}）· owner `{receipt.get('owner_user_id')}` · 试点 `{receipt.get('pilot_id')}`",
        f"- 协议：`{receipt.get('protocol_version')}` @ `{str(receipt.get('protocol_hash'))[:16]}…`",
        f"- 状态：**{_label(receipt.get('status'))}**；输入事件 {len(receipt.get('input_event_ids') or ())} 条，input_hash `{str(receipt.get('input_hash'))[:16]}…`",
        f"- 生成时间：{receipt.get('generated_at')}（不进入内容摘要）",
        "",
    ]
    if receipt.get("invalid_reasons"):
        lines.append("## 无效原因")
        lines += [f"- `{item['code']}`：{item['detail']}" for item in receipt["invalid_reasons"]]
        lines.append("")
    if receipt.get("limitations"):
        lines.append("## 限制项")
        lines += [f"- `{item}`" for item in receipt["limitations"]]
        lines.append("")

    lines += ["## 任务", "", "| 条件 | 任务 | 参与者 | 终态 | 来源 | 超时 | 尝试(失败/降级) |", "|---|---|---|---|---|---|---|"]
    for condition, task in sorted((receipt.get("tasks") or {}).items()):
        lines.append(
            f"| {condition} | `{task.get('task_id')}` | `{task.get('participant_id')}` | {task.get('terminal_state')} | "
            f"{task.get('terminal_source')} | {task.get('timed_out')} | {task.get('attempt_count')}({task.get('failed_attempt_count')}/{task.get('degraded_attempt_count')}) |"
        )
    lines.append("")

    timing = receipt.get("timing") or {}
    lines += ["## 计时（分钟）", "", "| 条件 | 端到端 | 用户主动 | 等模型 | 人工救援 | 已扣暂停 | 确定性 | 仅客户端 |", "|---|---|---|---|---|---|---|---|"]
    for condition in ("original", "assisted"):
        block = timing.get(condition) or {}
        lines.append(
            f"| {condition} | {_fmt(block.get('end_to_end_minutes'))} | {_fmt(block.get('user_active_minutes'))} | {_fmt(block.get('model_wait_minutes'))} | "
            f"{_fmt(block.get('manual_rescue_minutes'))} | {_fmt(block.get('pause_deducted_minutes'))} | {block.get('certainty')} | {block.get('client_only')} |"
        )
    lines += ["", f"省时比例：**{_fmt(timing.get('time_saving_ratio'))}**（{timing.get('time_saving_reason') or 'ok'}）", ""]

    quality = receipt.get("quality") or {}
    lines += ["## 质量（独立盲审）", ""]
    for condition in ("original", "assisted"):
        block = quality.get(condition) or {}
        if block.get("status") == "reviewed":
            lines.append(f"- {condition}：总分 {block.get('total')}/{block.get('max_total')}，严重错误 {block.get('severe_error_count')}，盲审 {block.get('blinded')}，评审 `{block.get('reviewer_id')}`")
        else:
            lines.append(f"- {condition}：未知（{block.get('reason')}）")
    lines += [f"- 辅助不低于原流程：{_fmt(quality.get('assisted_not_lower'))}", ""]

    lines += ["## 费用", ""]
    lines.append(f"- 已知：{receipt.get('known_cost_by_currency')}")
    lines.append(f"- 估算：{receipt.get('estimated_cost_by_currency')}")
    unknown = receipt.get("unknown_cost_components") or []
    lines.append(f"- 未知组件 {len(unknown)} 项：" + "；".join(f"{item.get('component')}({item.get('reason')})" for item in unknown))
    lines.append(f"- 人工工时：{receipt.get('manual_minutes')}")
    lines += ["", "## 分子 / 分母 / 排除", ""]
    lines.append(f"- 分子：{receipt.get('numerator_ids')}")
    lines.append(f"- 分母：{receipt.get('denominator_ids')}")
    lines.append(f"- 排除：{receipt.get('exclusions')}")
    lines.append("")
    return "\n".join(lines)


def _render_block(block: Mapping[str, Any], title: str) -> list[str]:
    lines = [f"## {title}", "", "| 指标 | 值 | 分子 | 分母 | 未知 | 覆盖 |", "|---|---|---|---|---|---|"]
    for metric in block.get("metrics") or ():
        lines.append(
            f"| `{metric['metric_id']}` | {_fmt(metric.get('value'))} {metric.get('unit')} | {len(metric.get('numerator_ids') or ())} | "
            f"{len(metric.get('denominator_ids') or ())} | {len(metric.get('unknown') or ())} | {metric.get('coverage') or ''} |"
        )
    lines += ["", "| 判据 | 结论 | 原因 | 未知类型 |", "|---|---|---|---|"]
    for result in block.get("criteria_results") or ():
        lines.append(f"| `{result['criterion_id']}` | **{_label(result['verdict'])}** | {result['reason']} | {result.get('unknown_kind') or ''} |")
    lines += ["", f"建议：`{block.get('recommendation')}`（达标只建议继续验证，不证明效果成立）", ""]
    return lines


def render_summary_markdown(summary: Mapping[str, Any]) -> str:
    lines = [f"# 试点总结 `{summary.get('summary_id')}`", ""]
    lines += _synthetic_banner(bool((summary.get("provenance") or {}).get("synthetic")))
    lines += [
        f"- 试点 `{summary.get('pilot_id')}` · owner `{summary.get('owner_user_id')}` · 协议 `{summary.get('protocol_version')}` @ `{str(summary.get('protocol_hash'))[:16]}…`",
        f"- as_of：{summary.get('as_of')}；生成时间：{summary.get('generated_at')}",
        f"- 收据 {len(summary.get('source_receipt_ids') or ())} 份；provenance：{summary.get('provenance')}",
        "",
        "| 状态 | 值 |",
        "|---|---|",
        f"| 工程 | **{_label(summary.get('engineering_status'))}** |",
        f"| 真人效果 | **{_label(summary.get('field_status'))}** |",
        f"| 商业 | **{_label(summary.get('commercial_status'))}** |",
        "",
    ]
    if summary.get("limitations"):
        lines.append("限制项：" + "、".join(f"`{item}`" for item in summary["limitations"]))
        lines.append("")
    if summary.get("input_errors"):
        lines.append("输入错误：" + "；".join(f"`{item['code']}`:{item['detail']}" for item in summary["input_errors"]))
        lines.append("")
    lines += _render_block(summary, "真人读数（observed / imported）")
    synthetic = summary.get("synthetic_check")
    if synthetic:
        lines += _render_block(synthetic, "synthetic_check（仿真夹具，不计入真人效果）")
    return "\n".join(lines)


__all__ = ["render_receipt_markdown", "render_summary_markdown"]
