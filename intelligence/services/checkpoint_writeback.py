"""回检闭环写回：checkpoint 裁决 miss → 关联证据标 invalidated（方案 5 步骤 3）。

原理：``verdicts.jsonl`` 里 ``miss`` 是一条**已核对落空**的判断（比启发式证伪回链
把握更高），但此前只影响校准统计，不影响后续 ask 的证据池——旧证据继续进 prompt。
本模块把 miss 裁决写回知识库仓的证伪回链派生层 ``relations/invalidation_links.json``
（overlay，不改 evidence_index 账本本体，与知识库仓 invalidation_overlay 的架构决策
一致）：hard 链 → 读侧（KnowledgeAdapter.get_evidence）视为 invalidated，默认过滤。

匹配边界（防过度连接误杀）：
- 只匹配 checkpoint 显式登记的 ``stocks``（target 全等）；``themes`` 存在时还要求
  concept 命中其一；两者都没有则不写回（无法定位关联证据）；
- 只匹配 ``source_date`` 早于等于 checkpoint 登记日的证据（后来的新证据不背锅）；
- 幂等：同一 checkpoint 已写过的 link（negation.source 相同）跳过。

写回失败只告警不阻断回检落盘（写回是增强，不是闸门）。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from intelligence.adapters.knowledge import KnowledgeAdapter, _evidence_key, evidence_status

OVERLAY_SCHEMA = "invalidation_links/v1"


def _checkpoint_source(checkpoint_id: str) -> str:
    return f"checkpoint:{checkpoint_id}"


def _match_evidence(
    items: list[Any],
    *,
    stocks: list[str],
    themes: list[str],
    cutoff_date: str,
) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("target") or "") not in stocks:
            continue
        if themes and str(item.get("concept") or "") not in themes:
            continue
        source_date = str(item.get("source_date") or "")
        if not source_date or source_date > cutoff_date:
            continue
        if evidence_status(item) == "invalidated":
            continue
        matched.append(item)
    return matched


def writeback_miss_verdict(
    checkpoint: dict[str, Any],
    verdict: dict[str, Any],
    *,
    wiki_root: str | Path | None = None,
) -> dict[str, Any]:
    """把一条 miss 裁决写回 overlay；返回 ``{written, matched, skipped_reason}``。"""
    result: dict[str, Any] = {"written": 0, "matched": 0, "skipped_reason": None}
    if str(verdict.get("verdict") or "") != "miss":
        result["skipped_reason"] = "verdict 非 miss"
        return result
    checkpoint_id = str(checkpoint.get("id") or "")
    stocks = [str(s) for s in (checkpoint.get("stocks") or []) if str(s).strip()]
    themes = [str(t) for t in (checkpoint.get("themes") or []) if str(t).strip()]
    if not stocks:
        result["skipped_reason"] = "checkpoint 未登记 stocks，无法定位关联证据"
        return result
    cutoff_date = str(checkpoint.get("ts") or "")[:10]
    if not cutoff_date:
        result["skipped_reason"] = "checkpoint 无登记时间"
        return result

    adapter = KnowledgeAdapter(wiki_root=wiki_root)
    relation = adapter.load_relation("evidence_index")
    if not relation["found"]:
        result["skipped_reason"] = "evidence_index 不可用"
        return result
    items = relation["data"].get("items", [])
    if not isinstance(items, list):
        result["skipped_reason"] = "evidence_index.items 非列表"
        return result

    matched = _match_evidence(items, stocks=stocks, themes=themes, cutoff_date=cutoff_date)
    result["matched"] = len(matched)
    if not matched:
        return result

    overlay_path = adapter.relation_path("invalidation_links")
    if overlay_path.exists():
        overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    else:
        overlay = {"schema": OVERLAY_SCHEMA, "links": []}
    links = overlay.setdefault("links", [])
    negation_source = _checkpoint_source(checkpoint_id)
    if any(
        (link.get("negation") or {}).get("source") == negation_source
        for link in links
        if isinstance(link, dict)
    ):
        result["skipped_reason"] = "该 checkpoint 已写回过（幂等跳过）"
        return result

    reason = str(verdict.get("reason") or "").strip() or str(checkpoint.get("claim") or "")
    checked_at = str(verdict.get("checked_at") or "")[:10]
    for target in stocks:
        target_items = [item for item in matched if item.get("target") == target]
        if not target_items:
            continue
        concepts = sorted({str(item.get("concept") or "") for item in target_items})
        for concept in concepts:
            concept_items = [
                item for item in target_items if str(item.get("concept") or "") == concept
            ]
            links.append(
                {
                    "target": target,
                    "concept": concept,
                    "strength": "hard",
                    "negation": {
                        "source_date": checked_at,
                        "source": negation_source,
                        "hits": ["checkpoint_miss"],
                        "evidence": reason,
                    },
                    "invalidates": [
                        {
                            "key": _evidence_key(item),
                            "source_date": item.get("source_date"),
                            "source": item.get("source"),
                            "predicate": None,
                            "confidence": item.get("confidence"),
                            "evidence": item.get("evidence"),
                        }
                        for item in concept_items
                    ],
                }
            )
            result["written"] += len(concept_items)
    overlay["generated"] = datetime.now().isoformat(timespec="seconds")
    tmp = overlay_path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(overlay, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(overlay_path)
    return result
