from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from intelligence.adapters.knowledge import KnowledgeAdapter


LAYER_ORDER = {
    "L0 图谱登记": 0,
    "L1 叙事线索": 1,
    "L2 基线": 2,
    "L2 官方基线": 3,
    "L3 候选硬事实": 4,
    "L3 官方验证": 5,
    "L4 盘面验证": 6,
}

OFFICIAL_L3_KEYWORDS = (
    "announcement",
    "official_interaction",
    "official_research",
    "investor_relation",
    "order",
    "contract",
    "customer_validation",
    "certification",
    "production",
    "shipment",
    "capacity",
    "中标",
    "订单",
    "合同",
    "客户验证",
    "认证",
    "量产",
    "出货",
    "公告",
    "调研",
    "互动易",
)

MARKET_KEYWORDS = (
    "market",
    "price",
    "limit",
    "turnover",
    "relative_strength",
    "盘面",
    "涨停",
    "成交",
    "相对强度",
)

BASELINE_SOURCE_HINTS = (
    "baseline",
    "ifind",
    "f10",
    "mootdx",
    "主营业务",
    "年报",
)

NARRATIVE_SOURCE_HINTS = (
    "deepdive",
    "deep_dive",
    "theme_radar",
    "themeradar",
    "深度研究",
    "市场逻辑精选",
    "脱水研报",
    "晨汇",
    "研报",
    "逻辑卡",
)


@dataclass(frozen=True)
class ResearchJudgeOptions:
    target: str
    kb_wiki: str | Path | None = None
    concept: str | None = None
    max_evidence: int = 8
    has_market_signal: bool = False


def judge_research_target(
    target: str,
    kb_wiki: str | Path | None = None,
    concept: str | None = None,
    max_evidence: int = 8,
    has_market_signal: bool = False,
) -> dict[str, Any]:
    return ResearchJudge(ResearchJudgeOptions(target, kb_wiki, concept, max_evidence, has_market_signal)).judge()


def judge_row(row: dict[str, Any], kb_wiki: str | Path | None = None, max_evidence: int = 8) -> dict[str, Any]:
    target = str(row.get("matched_theme") or row.get("query") or "").strip()
    if not target:
        return _empty_judgment("-", "未知", ["缺少可裁判的题材或公司名"])
    trigger_types = row.get("trigger_types") or []
    has_market_signal = bool(trigger_types) and "placeholder_market_theme" not in set(row.get("data_gaps") or [])
    return judge_research_target(
        target,
        kb_wiki=kb_wiki,
        max_evidence=max_evidence,
        has_market_signal=has_market_signal,
    )


class ResearchJudge:
    def __init__(self, options: ResearchJudgeOptions):
        self.options = options
        self.adapter = KnowledgeAdapter(options.kb_wiki)

    def judge(self) -> dict[str, Any]:
        target = self.options.target.strip()
        if not target:
            return _empty_judgment("-", "未知", ["缺少可裁判的题材或公司名"])

        entity = self.adapter.get_entity_exposures(target)
        target_type = "公司" if entity.get("found") else "题材"
        evidence_items = self._load_evidence(target)
        if self.options.has_market_signal:
            evidence_items.append(
                {
                    "target": target,
                    "concept": self.options.concept,
                    "evidence_layer": "L4",
                    "update_type": "market_signal",
                    "source_quality": "market_feature_store",
                    "source": "盘面候选",
                    "evidence": "daily agent 检测到盘面触发信号。",
                }
            )

        layers = _classify_layers(evidence_items)
        if target_type == "题材" and self._concept_registered(target):
            layers.add("L0 图谱登记")

        status = _status_from_layers(layers)
        missing = _missing_layers(layers, status)
        reasons = _blocking_reasons(layers, evidence_items)
        action = _next_action(status, layers, missing)
        evidence_summary = [_summarize_evidence(item) for item in evidence_items[: self.options.max_evidence]]

        return {
            "目标": target,
            "目标类型": target_type,
            "关联概念": self.options.concept or "-",
            "证据状态": status,
            "已有证据层": _sort_layers(layers),
            "缺失证据层": missing,
            "已有证据": evidence_summary,
            "建议动作": action,
            "不可升级原因": reasons,
        }

    def _load_evidence(self, target: str) -> list[dict[str, Any]]:
        direct = self.adapter.get_evidence(target, self.options.concept, limit=max(self.options.max_evidence * 3, 20))
        items = [item for item in direct.get("items", []) if isinstance(item, dict)]
        if not items:
            items = self._scan_evidence_by_concept(target)
        return items[: max(self.options.max_evidence * 3, self.options.max_evidence)]

    def _scan_evidence_by_concept(self, target: str) -> list[dict[str, Any]]:
        relation = self.adapter.load_relation("evidence_index")
        if not relation.get("found"):
            return []
        raw_items = relation.get("data", {}).get("items", [])
        if not isinstance(raw_items, list):
            return []
        matched: list[dict[str, Any]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            fields = [item.get("concept"), item.get("theme"), item.get("target"), item.get("evidence"), item.get("source")]
            if self.options.concept and not any(str(self.options.concept) in str(value) for value in fields if value is not None):
                continue
            if any(str(target) in str(value) for value in fields if value is not None):
                matched.append(item)
        return matched

    def _concept_registered(self, target: str) -> bool:
        return bool(self.adapter.get_concept_matches(target, limit=1).get("items"))


def _classify_layers(items: list[dict[str, Any]]) -> set[str]:
    layers: set[str] = set()
    for item in items:
        text = _item_text(item)
        raw_layer = str(item.get("evidence_layer") or item.get("layer") or "").strip().upper()
        update_type = str(item.get("update_type") or "").lower()
        source_quality = str(item.get("source_quality") or "").lower()

        if raw_layer == "L4" or any(keyword in text for keyword in MARKET_KEYWORDS):
            layers.add("L4 盘面验证")
            continue

        if _is_official_l3_item(item):
            layers.add("L3 官方验证")
            continue

        if "candidate" in raw_layer.lower() or raw_layer in {"L1_L3_CANDIDATE", "L3_CANDIDATE"} or "ima" in update_type:
            layers.add("L3 候选硬事实")
            continue

        if raw_layer == "L2" or "baseline" in update_type or "baseline" in source_quality:
            if "official" in source_quality or "annual_report" in update_type or "年报" in text:
                layers.add("L2 官方基线")
            else:
                layers.add("L2 基线")
            continue

        if raw_layer == "L1" or "narrative" in update_type or "briefing" in source_quality:
            layers.add("L1 叙事线索")
            continue

        if not raw_layer:
            if any(hint in text for hint in BASELINE_SOURCE_HINTS):
                layers.add("L2 基线")
            elif any(hint in text for hint in NARRATIVE_SOURCE_HINTS):
                layers.add("L1 叙事线索")

    return layers


def _is_official_l3_item(item: dict[str, Any]) -> bool:
    raw_layer = str(item.get("evidence_layer") or item.get("layer") or "").strip().upper()
    update_type = str(item.get("update_type") or "").lower()
    source_quality = str(item.get("source_quality") or "").lower()
    source = str(item.get("source") or "").lower()
    text = _item_text(item)
    if "candidate" in raw_layer.lower() or "ima" in update_type or "curated_research" in source_quality:
        return False
    if raw_layer in {"L3", "L3_OFFICIAL"}:
        return True
    official_context = (
        any(keyword in update_type for keyword in OFFICIAL_L3_KEYWORDS)
        or any(keyword in source_quality for keyword in OFFICIAL_L3_KEYWORDS)
        or any(keyword in source for keyword in OFFICIAL_L3_KEYWORDS)
        or "official_interaction" in update_type
        or "announcement" in update_type
    )
    hard_fact = any(keyword in text for keyword in OFFICIAL_L3_KEYWORDS)
    baseline_only = "baseline" in update_type or "annual_report" in update_type
    return bool(official_context and hard_fact and not baseline_only)


def _status_from_layers(layers: set[str]) -> str:
    has_l2 = bool({"L2 基线", "L2 官方基线"} & layers)
    has_l1 = "L1 叙事线索" in layers
    has_l3_official = "L3 官方验证" in layers
    has_l3_candidate = "L3 候选硬事实" in layers
    has_l4 = "L4 盘面验证" in layers
    if has_l2 and has_l3_official and has_l4:
        return "已有事实验证"
    if has_l2 and (has_l3_official or has_l3_candidate):
        return "重点验证"
    if has_l2:
        return "能力栈候选"
    if has_l1 and has_l4:
        return "旧逻辑待验证"
    if has_l4:
        return "盘面触发待解释"
    return "观察"


def _missing_layers(layers: set[str], status: str) -> list[str]:
    missing: list[str] = []
    if not ({"L2 基线", "L2 官方基线"} & layers):
        missing.append("L2 基线")
    if "L3 官方验证" not in layers:
        missing.append("L3 官方验证")
    if "L4 盘面验证" not in layers:
        missing.append("L4 盘面验证")
    if status == "观察" and "L1 叙事线索" not in layers and "L3 候选硬事实" not in layers:
        missing.insert(0, "L1 叙事线索")
    return missing


def _blocking_reasons(layers: set[str], items: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    if "L3 候选硬事实" in layers and "L3 官方验证" not in layers:
        reasons.append("已有 IMA/研报里的候选硬事实，但还缺公告、互动、调研纪要等官方 L3 验证。")
    if "L1 叙事线索" in layers and not ({"L2 基线", "L2 官方基线"} & layers):
        reasons.append("已有旧材料或研报叙事，但还缺年报/F10 等 L2 基线确认。")
    if {"L2 基线", "L2 官方基线"} & layers and "L3 官方验证" not in layers:
        reasons.append("年报/F10 只能证明公司能力栈存在，不能证明这条逻辑正在发生边际变化。")
    if "L4 盘面验证" not in layers:
        reasons.append("还缺盘面验证，不能判断市场是否已经重新定价。")
    if not items:
        reasons.append("结构化证据为空，需要先补来源或确认概念/公司名称。")
    return reasons


def _next_action(status: str, layers: set[str], missing: list[str]) -> str:
    if status == "已有事实验证":
        return "等盘面持续性验证：看相对强度、成交额边际、强势股扩散和回撤。"
    if status == "重点验证":
        if "L3 官方验证" in missing:
            return "优先找公告/互动/调研/订单/客户验证，把 IMA 候选硬事实升级成官方 L3。"
        return "已有官方事实，下一步等盘面验证，不急着继续补 IMA。"
    if status == "能力栈候选":
        return "先找公告、调研、订单、客户验证或产能/出货变化；年报基线之后不要直接升级。"
    if status == "旧逻辑待验证":
        return "先用旧材料补 L2 基线，再找公告/调研等 L3 事实；不用重复做同一题材 IMA。"
    if status == "盘面触发待解释":
        return "先回查旧逻辑和公司暴露，补 L2/L3 证据后再判断是不是有效唤醒。"
    if "L2 基线" in missing:
        return "先补年报/F10/公司页基线，确认公司和题材的真实暴露。"
    return "先补 IMA 或旧研报材料，确认这是不是可研究逻辑。"


def _summarize_evidence(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "层级": _sort_layers(_classify_layers([item]))[0] if _classify_layers([item]) else "未分层",
        "概念": str(item.get("concept") or item.get("theme") or "-"),
        "来源": str(item.get("source") or "-"),
        "来源质量": str(item.get("source_quality") or "-"),
        "摘要": str(item.get("evidence") or item.get("summary") or "-")[:220],
    }


def _sort_layers(layers: set[str]) -> list[str]:
    return sorted(layers, key=lambda layer: (LAYER_ORDER.get(layer, 99), layer))


def _item_text(item: dict[str, Any]) -> str:
    fields = [
        item.get("evidence_layer"),
        item.get("layer"),
        item.get("update_type"),
        item.get("source_quality"),
        item.get("source"),
        item.get("evidence"),
        item.get("summary"),
        item.get("concept"),
    ]
    return " ".join(str(value).lower() for value in fields if value is not None)


def _empty_judgment(target: str, target_type: str, reasons: list[str]) -> dict[str, Any]:
    return {
        "目标": target,
        "目标类型": target_type,
        "关联概念": "-",
        "证据状态": "观察",
        "已有证据层": [],
        "缺失证据层": ["L1 叙事线索", "L2 基线", "L3 官方验证", "L4 盘面验证"],
        "已有证据": [],
        "建议动作": "先补 IMA 或旧研报材料，确认这是不是可研究逻辑。",
        "不可升级原因": reasons,
    }
