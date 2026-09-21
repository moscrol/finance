"""Read-only Episode projection of the existing daily snapshot contract."""
from __future__ import annotations

from dataclasses import replace
from datetime import date
import json
import math
from pathlib import Path

from intelligence.services.agent_research import AgentEvidence, StructuredObservation, evidence_content_hash
from intelligence.services.market_snapshot_contract import load_market_snapshot_as_of
from intelligence.services.provider_observability import ProviderTrace

_MARKET_FIELDS = (
    ("stage", "快照阶段标签", ""),
    ("total_amount", "全市场成交额", "亿元"),
    ("amount_ratio", "快照成交量比", ""),
    ("advancers", "上涨家数", "家"),
    ("decliners", "下跌家数", "家"),
    ("limit_up", "涨停家数", "家"),
    ("limit_down", "跌停家数", "家"),
)


def read_snapshot_evidence(root: Path | None, *, as_of: date):
    if root is None:
        return [], "封存夹具未配置本地行情日快照目录；未读取默认目录。", ProviderTrace(
            provider="local_market_snapshot", capability="local_market_snapshot",
            status="empty", detail="sealed_snapshot_root_unconfigured", result_count=0,
        )
    loaded = load_market_snapshot_as_of(root, as_of)
    doc = loaded["doc"]
    scope = (
        "读取范围：仅本地行情日快照；未取得某源或某字段不代表整个本地没有该日数据。"
        "快照和结构化复盘表是独立来源，日期不同仍分别使用；不补零，比较先核对口径。"
    )
    if not loaded["found"]:
        return [], scope + f" 截止 {as_of.isoformat()} 未取得可用本地日快照。", ProviderTrace(
            provider="local_market_snapshot", capability="local_market_snapshot",
            status="empty", detail="no_valid_snapshot_at_or_before_cutoff", result_count=0,
        )
    day = doc["trade_date"]
    source = f"本地行情日快照 · {doc.get('source') or '来源未标明'} · {day}"
    evidence: list[AgentEvidence] = []
    notes = [scope, f"快照实际数据日期 {day}；质量 {doc.get('quality') or 'unknown'}；新鲜度 {doc.get('freshness') or 'unknown'}。"]
    if loaded["warnings"]:
        notes.append("快照校验存在缺项或跳过的文件；本次仅引用已返回字段，不证明覆盖完整。")
    if doc.get("source_errors"):
        notes.append("快照记录了采集源错误；本次只读已保存结果，未补采或联网。")
    akshare = "akshare" in str(doc.get("schema_version", "")).lower()
    if akshare:
        notes.append("AkShare 快照阶段按涨跌家数差分类，不等同于复盘周期阶段；题材行按涨停池所属行业聚合，不是全市场题材或主线全集。")

    def add(title: str, detail: str, field: str, observations=()):
        item = AgentEvidence(
            tool="local_market_snapshot", title=title, detail=f"数据日期 {day}；{detail}",
            source=source, internal_locator=f"{loaded['path']}#{field}",
            source_date=day, evidence_tier="L4_structured",
            freshness=str(doc.get("freshness") or "unknown"),
            observations=tuple(observations),
        )
        evidence.append(replace(item, content_hash=evidence_content_hash(item)))

    market = doc["market"]
    for field, label, unit in _MARKET_FIELDS:
        value = market.get(field)
        numeric = isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)
        if value is None or (field != "stage" and not numeric):
            notes.append(f"快照 {label}缺失。")
            continue
        qualifier = "（涨跌家数差口径）" if field == "stage" and akshare else ""
        obs = (StructuredObservation("market", day, f"snapshot_{field}", float(value)),) if numeric else ()
        add(f"{day} {label}", f"{label} {value}{unit}{qualifier}", f"market.{field}", obs)
    capacity = market.get("capacity_top3")
    if capacity:
        add(f"{day} 快照容量前三", json.dumps(capacity, ensure_ascii=False), "market.capacity_top3")
    else:
        notes.append("快照容量前三未提供，不能推为不存在容量板块。")
    themes = [(index, row) for index, row in enumerate(doc["themes"]) if isinstance(row, dict)]
    shown = 0
    for index, row in themes[:12]:
        name = row.get("concept")
        if not isinstance(name, str) or not name:
            continue
        values = {key: row[key] for key in ("priority_score", "trigger_types", "limit_up_count", "new_high_count", "strong_stock_count") if key in row}
        triggers = row.get("trigger_types")
        caliber = "涨停池行业分布" if isinstance(triggers, list) and "akshare_limit_up_pool" in triggers else "快照题材候选"
        observations = tuple(
            StructuredObservation(name, day, f"snapshot_{key}", float(value))
            for key, value in values.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        )
        add(f"{day} {caliber} {name}", f"{caliber} {name}：{json.dumps(values, ensure_ascii=False)}（null 为缺失，不是零）", f"themes.{index}", observations)
        shown += 1
    notes.append(f"本文件共 {len(themes)} 条对象型题材/行业候选，本次展示 {shown} 条；保持文件顺序，不另作全市场排名。")
    observation = "\n".join([*notes, *(item.detail for item in evidence)])
    return evidence, observation, ProviderTrace(
        provider="local_market_snapshot", capability="local_market_snapshot",
        status="success" if evidence else "empty", detail="dated_local_json_snapshot",
        source_trade_date=day, result_count=len(evidence),
    )
