"""出口 guard for relation questions.

Concept/entity co-occurrence is not a graph edge.  A relation answer may only
claim a direction when the graph row contains an explicit chain stage/role;
otherwise the presenter must say the edge is missing.
"""
from __future__ import annotations

from typing import Iterable, Mapping


def relation_edge_supported(query: str, exposure_rows: Iterable[Mapping[str, object]]) -> bool:
    text = str(query or "")
    directional_terms = tuple(
        term for term in ("上游", "中游", "下游", "客户", "供应", "环节") if term in text
    )
    rows = list(exposure_rows)
    if not rows:
        return False
    for row in rows:
        role = " ".join(
            str(row.get(field) or "")
            for field in ("chain_stage", "role", "relationship", "relation", "position")
        )
        if not role.strip():
            continue
        if directional_terms:
            if any(term in role for term in directional_terms):
                return bool(row.get("company") or row.get("entity"))
        elif row.get("company") and row.get("concept"):
            return True
    return False


def relation_gap_text(query: str) -> str:
    direction = next(
        (term for term in ("上游", "中游", "下游", "客户", "供应关系") if term in str(query or "")),
        "关系",
    )
    return (
        f"图谱暂未提供可核验的“{direction}”关系边；已命中的概念/公司只能作为线索，"
        "不能据此拼接产业链关系。"
    )
