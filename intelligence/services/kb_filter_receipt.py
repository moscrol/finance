"""KB query 回执的消费边界：不推断证据等级，不用请求参数冒充实际执行。

知识库拥有切块/过滤实现；这里只验跨仓协议及出参一致性，不另建 metadata 提取器。
版本 1 合同见知识库 scripts/rag_index.py::cmd_query / rag.evidence。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

FILTER_OPTIONS = {
    "--evidence-layer": "evidence_layer",
    "--fact-hardness": "fact_hardness",
    "--source-type": "source_type",
    "--as-of": "as_of",
}
FILTER_POLICY = "explicit_chunk_metadata; unknown_excluded; as_of=available_time"


def _date(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return ""
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return ""


def requested_filters(**values: str | None) -> dict[str, str]:
    out = {key: value for key, value in values.items() if value is not None and value != ""}
    if any(not isinstance(value, str) for value in out.values()):
        raise ValueError("证据过滤条件必须是字符串")
    if "as_of" in out and not _date(out["as_of"]):
        raise ValueError("as_of must be YYYY-MM-DD")
    return out


def _same_filters(actual: object, expected: dict[str, str]) -> bool:
    return (
        isinstance(actual, dict)
        and actual.keys() == expected.keys()
        and all(isinstance(actual[k], str) and actual[k].casefold() == v.casefold()
                for k, v in expected.items())
    )


def _matches(row: dict, filters: dict[str, str]) -> bool:
    review = row.get("review_required", "")
    if not isinstance(review, str) or review.casefold() not in ("", "true", "false"):
        return False  # 不能把畸形否决标记强转成字符串后当作「不是 true」。
    for key, value in filters.items():
        if key == "as_of":
            available = _date(row.get("available_time"))
            published = _date(row.get("publish_time"))
            if (not available or available > value
                    or (row.get("publish_time") and not published)
                    or (published and available < published)):
                return False
        elif not isinstance(row.get(key), str) or row[key].casefold() != value.casefold():
            return False
    if (filters.get("evidence_layer", "").casefold() == "l3"
            or filters.get("fact_hardness", "").casefold() == "hard_fact"):
        if (str(row.get("review_required")).casefold() == "true"
                or str(row.get("fact_hardness")).casefold() == "review_candidate"
                or "candidate" in str(row.get("evidence_layer")).casefold()):
            return False
    return True


@dataclass(frozen=True)
class QueryReceipt:
    hits: list
    received: bool = False
    applied_filters: dict[str, str] = field(default_factory=dict)
    filter_policy: str = ""
    metadata_version: int | None = None
    metadata_update_required: bool | None = None


def parse_receipt(payload: object, requested: dict[str, str]) -> QueryReceipt:
    """旧列表仅允许无过滤查询；有约束时必须持有自洽回执，含合法空结果。"""
    if isinstance(payload, list):
        if requested:
            raise ValueError("缺少证据过滤回执；旧列表不能证明约束已执行")
        return QueryReceipt(payload)
    if not isinstance(payload, dict) or not isinstance(payload.get("hits"), list):
        raise ValueError("检索回执格式异常（期望 hits 封套或旧列表）")
    rows = payload["hits"]
    version = payload.get("metadata_version")
    update = payload.get("metadata_update_required")
    if (payload.get("status") != ("success" if rows else "no_results")
            or payload.get("filter_policy") != FILTER_POLICY
            or type(version) is not int or version < 0
            or type(update) is not bool or update != (version != 1)
            or not _same_filters(payload.get("applied_filters"), requested)):
        raise ValueError("证据过滤回执与请求/版本合同不一致，拒绝交付证据")
    if requested:
        if (rows and version != 1) or any(
            not isinstance(row, dict)
            or not _same_filters(row.get("applied_filters"), requested)
            or row.get("content_validity") not in ("valid", "indexed_only")
            or not _matches(row, requested)
            for row in rows
        ):
            raise ValueError("证据过滤回执与命中元数据矛盾，拒绝交付证据")
    return QueryReceipt(
        rows, received=True, applied_filters=dict(payload["applied_filters"]),
        filter_policy=FILTER_POLICY, metadata_version=version, metadata_update_required=update,
    )
