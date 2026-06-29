from __future__ import annotations

from typing import Any


QUEUE_DO_IMA = "today_do_ima"
QUEUE_FIND_OFFICIAL = "today_find_official_evidence"
QUEUE_WAIT_MARKET = "today_wait_market_validation"
QUEUE_DOWNGRADE = "today_downgrade_or_watch"

ACTION_LABELS = {
    QUEUE_DO_IMA: "今日该做 IMA",
    QUEUE_FIND_OFFICIAL: "今日该找公告/调研/订单",
    QUEUE_WAIT_MARKET: "今日等盘面验证",
    QUEUE_DOWNGRADE: "今日降级/观察",
}

BLOCKING_GAPS = {
    "placeholder_market_theme",
    "missing_concept",
    "missing_entity_exposure",
    "missing_evidence",
    "missing_source_trace",
}

WEAK_STAGES = {"高位分歧", "衰退观察", "证伪退出"}
RESEARCHABLE_STAGES = {"新出现", "旧逻辑唤醒", "升温验证", "加速定价"}


def build_research_queue(decision: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    queue: dict[str, Any] = {
        QUEUE_DO_IMA: [],
        QUEUE_FIND_OFFICIAL: [],
        QUEUE_WAIT_MARKET: [],
        QUEUE_DOWNGRADE: [],
        "skipped": {
            "data_gap_or_unconfirmed": [],
            "no_clear_action": [],
        },
    }
    for row in _iter_rows(decision):
        bucket, reason = _classify_row(row)
        item = _queue_item(row, bucket, reason)
        if bucket in ACTION_LABELS:
            queue[bucket].append(item)
        elif bucket == "data_gap_or_unconfirmed":
            queue["skipped"]["data_gap_or_unconfirmed"].append(item)
        else:
            queue["skipped"]["no_clear_action"].append(item)

    for key in (QUEUE_DO_IMA, QUEUE_FIND_OFFICIAL, QUEUE_WAIT_MARKET, QUEUE_DOWNGRADE):
        queue[key].sort(key=lambda item: float(item.get("优先级") or 0), reverse=True)
    queue["summary"] = {
        QUEUE_DO_IMA: len(queue[QUEUE_DO_IMA]),
        QUEUE_FIND_OFFICIAL: len(queue[QUEUE_FIND_OFFICIAL]),
        QUEUE_WAIT_MARKET: len(queue[QUEUE_WAIT_MARKET]),
        QUEUE_DOWNGRADE: len(queue[QUEUE_DOWNGRADE]),
        "total": sum(len(queue[key]) for key in (QUEUE_DO_IMA, QUEUE_FIND_OFFICIAL, QUEUE_WAIT_MARKET, QUEUE_DOWNGRADE)),
        "skipped": sum(len(items) for items in queue["skipped"].values()),
    }
    return queue


def _iter_rows(decision: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket in ("old_logic_wakeup", "new_logic_candidate", "data_gap", "noise_or_unconfirmed"):
        rows.extend(row for row in decision.get(bucket, []) if isinstance(row, dict))
    return rows


def _classify_row(row: dict[str, Any]) -> tuple[str, str]:
    gaps = set(row.get("data_gaps") or [])
    if gaps & BLOCKING_GAPS or row.get("classification") in {"data_gap", "noise_or_unconfirmed"}:
        return "data_gap_or_unconfirmed", "仍有概念、公司、证据、来源或占位缺口，先留在回补/待确认区。"

    stage = _stage(row)
    layers = set(_judgment(row).get("已有证据层") or [])
    missing = set(_judgment(row).get("缺失证据层") or [])
    status = str(_judgment(row).get("证据状态") or "-")
    has_l1 = "L1 叙事线索" in layers
    has_l2 = bool({"L2 基线", "L2 官方基线"} & layers)
    has_l3_candidate = "L3 候选硬事实" in layers
    has_l3_official = "L3 官方验证" in layers
    has_l4 = "L4 盘面验证" in layers

    if stage in WEAK_STAGES:
        return QUEUE_DOWNGRADE, f"生命周期转弱为{stage}，先降级观察，等待新事实或盘面重新扩散。"

    if has_l2 and (has_l3_candidate or has_l3_official) and ("L4 盘面验证" in missing or not has_l4):
        return QUEUE_WAIT_MARKET, "已有 L2/L3，但缺 L4 盘面验证，先等市场重新定价或扩散。"

    if has_l1 and (not has_l2 or "L2 基线" in missing or "L2 官方基线" in missing or "L3 官方验证" in missing):
        return QUEUE_FIND_OFFICIAL, "已有 L1 旧逻辑材料，下一步补 L2 基线或 L3 官方验证，不重复做同一题材 IMA。"

    if ("L3 官方验证" in missing or not has_l3_official) and (has_l2 or has_l3_candidate or status in {"能力栈候选", "重点验证"}):
        return QUEUE_FIND_OFFICIAL, "已有 L2 或 L3 候选，但缺 L3 官方验证，优先找公告、调研、订单、客户验证。"

    if stage in RESEARCHABLE_STAGES and not has_l1 and not has_l2:
        return QUEUE_DO_IMA, "盘面触发但缺 L1/L2 叙事或基线材料，优先做 IMA/题材地图补边界。"

    if status == "已有事实验证" and has_l4:
        return QUEUE_WAIT_MARKET, "事实验证已较完整，今天重点观察盘面持续性和扩散。"

    return "no_clear_action", "证据和生命周期暂未触发明确研究动作，保留人工复核。"


def _queue_item(row: dict[str, Any], bucket: str, reason: str) -> dict[str, Any]:
    judgment = _judgment(row)
    lifecycle = row.get("logic_lifecycle") or row.get("生命周期") or {}
    return {
        "目标": row.get("query") or row.get("matched_theme") or "-",
        "动作": ACTION_LABELS.get(bucket, "暂不进入研究任务"),
        "理由": reason,
        "优先级": row.get("priority_score"),
        "生命周期阶段": lifecycle.get("生命周期阶段") or "-",
        "阶段变化": lifecycle.get("阶段变化") or "-",
        "证据状态": judgment.get("证据状态") or "-",
        "已有证据层": list(judgment.get("已有证据层") or []),
        "缺失证据层": list(judgment.get("缺失证据层") or []),
        "数据缺口": list(row.get("data_gaps") or []),
        "强势股": list(row.get("strong_stocks") or [])[:5],
        "建议动作": _suggest_action(bucket, judgment, lifecycle),
    }


def _suggest_action(bucket: str, judgment: dict[str, Any], lifecycle: dict[str, Any]) -> str:
    if bucket == QUEUE_DO_IMA:
        return "补 IMA/题材地图，目标是补清题材边界、产业链位置、核心公司和 L1/L2 材料。"
    if bucket == QUEUE_FIND_OFFICIAL:
        return "查公告、互动易、调研纪要、订单/合同、客户验证，把候选事实升级为 L3 官方验证。"
    if bucket == QUEUE_WAIT_MARKET:
        return "不急着补材料，观察强势股扩散、成交边际和后续是否继续进候选。"
    if bucket == QUEUE_DOWNGRADE:
        return "降级观察；除非新增 L3 事实或盘面重新扩散，否则减少研究投入。"
    if judgment.get("建议动作"):
        return str(judgment["建议动作"])
    if lifecycle.get("下一步"):
        return str(lifecycle["下一步"])
    return "人工复核。"


def _judgment(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("research_judgment") or {}


def _stage(row: dict[str, Any]) -> str:
    lifecycle = row.get("logic_lifecycle") or row.get("生命周期") or {}
    return str(lifecycle.get("生命周期阶段") or "-")
