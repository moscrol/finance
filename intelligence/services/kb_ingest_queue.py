from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any

from intelligence.summary import now_iso


TASK_CONCEPT = "concept_ingest"
TASK_DISCLOSURE = "disclosure"
TASK_ENTITY_DELTA = "entity_delta"
TASK_SOURCE_TRACE = "source_trace"

TASK_TYPE_LABELS = {
    TASK_CONCEPT: "概念入库",
    TASK_DISCLOSURE: "官方证据归档",
    TASK_ENTITY_DELTA: "公司边际变化",
    TASK_SOURCE_TRACE: "来源回溯",
}

DATA_GAP_TASKS = {
    "missing_concept": TASK_CONCEPT,
    "missing_entity_exposure": TASK_ENTITY_DELTA,
    "missing_evidence": TASK_DISCLOSURE,
    "missing_source_trace": TASK_SOURCE_TRACE,
}

GLOSSARY = {
    "RAG": "检索增强生成（Retrieval-Augmented Generation）：先从知识库找证据，再让模型生成回答。",
    "BM25": "一种关键词相关性排序算法，适合精确词命中；常和向量检索组成混合检索。",
    "rerank": "二次排序：先粗召回一批材料，再用更精细模型重排，提升证据相关性。",
    "IMA": "题材/产业链深度拆解材料；这里指补清题材边界、核心公司、证据层级的研究动作。",
    "MOC": "收盘集合竞价（Market-on-Close）；如果用于成交或盘口语境，必须写出中文释义。",
}

_PINYIN = {
    "先": "xian",
    "进": "jin",
    "封": "feng",
    "装": "zhuang",
    "光": "guang",
    "刻": "ke",
    "胶": "jiao",
    "存": "cun",
    "储": "chu",
    "芯": "xin",
    "片": "pian",
    "电": "dian",
    "子": "zi",
    "化": "hua",
    "学": "xue",
    "品": "pin",
    "液": "ye",
    "冷": "leng",
    "服": "fu",
    "务": "wu",
    "器": "qi",
    "金": "jin",
    "属": "shu",
    "铜": "tong",
}


def build_kb_ingest_queue(
    research_queue: dict[str, Any],
    *,
    market_date: str,
    source_artifact: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    created = created_at or now_iso()
    tasks: list[dict[str, Any]] = []
    tasks.extend(_tasks_from_items(research_queue.get("today_do_ima") or [], TASK_CONCEPT, "research_queue.today_do_ima"))
    tasks.extend(
        _tasks_from_items(
            research_queue.get("today_find_official_evidence") or [],
            TASK_DISCLOSURE,
            "research_queue.today_find_official_evidence",
        )
    )
    tasks.extend(_tasks_from_data_gaps((research_queue.get("skipped") or {}).get("data_gap_or_unconfirmed") or []))

    counters: Counter[tuple[str, str]] = Counter()
    for task in tasks:
        slug = _slugify(str(task["theme"]))
        key = (str(task["task_type"]), slug)
        counters[key] += 1
        task["task_id"] = f"{market_date}-{task['task_type']}-{slug}-{counters[key]:03d}"
        task["market_date"] = market_date
        task["source_repo"] = "finance-workspace-private"
        task["source_artifact"] = source_artifact
        task["created_at"] = created

    by_task_type = Counter(str(task["task_type"]) for task in tasks)
    return {
        "schema_version": "1.0",
        "source_repo": "finance-workspace-private",
        "source_artifact": source_artifact,
        "market_date": market_date,
        "created_at": created,
        "tasks": tasks,
        "summary": {
            "total_tasks": len(tasks),
            "by_task_type": dict(sorted(by_task_type.items())),
        },
        "glossary": GLOSSARY,
        "notes": [
            "本队列只表达金融 repo 发现的知识库缺口；知识库 repo 接收后仍需人工复核。",
            "所有任务默认 requires_human_review=true、auto_apply=false，不允许自动写入 wiki/relations。",
        ],
    }


def _tasks_from_items(items: list[dict[str, Any]], task_type: str, origin: str) -> list[dict[str, Any]]:
    return [_task_from_item(item, task_type, origin, item.get("理由") or item.get("建议动作") or "") for item in items]


def _tasks_from_data_gaps(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for item in items:
        gaps = list(item.get("数据缺口") or item.get("data_gaps") or [])
        mapped_types = []
        for gap in gaps:
            task_type = DATA_GAP_TASKS.get(str(gap))
            if task_type and task_type not in mapped_types:
                mapped_types.append(task_type)
        for task_type in mapped_types:
            reason = f"数据缺口触发：{', '.join(gaps)}。{item.get('理由') or ''}".strip()
            tasks.append(_task_from_item(item, task_type, "research_queue.skipped.data_gap_or_unconfirmed", reason, gaps=gaps))
    return tasks


def _task_from_item(
    item: dict[str, Any],
    task_type: str,
    origin: str,
    reason: str,
    *,
    gaps: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "task_id": "",
        "task_type": task_type,
        "task_type_label": TASK_TYPE_LABELS[task_type],
        "theme": str(item.get("目标") or item.get("theme") or "-"),
        "priority": item.get("优先级"),
        "reason": reason or "-",
        "evidence_gap": list(item.get("缺失证据层") or []),
        "data_gaps": list(gaps or item.get("数据缺口") or item.get("data_gaps") or []),
        "strong_stocks": list(item.get("强势股") or []),
        "suggested_action": item.get("建议动作") or "-",
        "origin": origin,
        "requires_human_review": True,
        "auto_apply": False,
        "status": "pending",
    }


def _slugify(text: str) -> str:
    pieces: list[str] = []
    ascii_buf: list[str] = []
    for char in text.lower():
        if char in _PINYIN:
            if ascii_buf:
                pieces.append("".join(ascii_buf))
                ascii_buf = []
            pieces.append(_PINYIN[char])
        elif char.isascii() and char.isalnum():
            ascii_buf.append(char)
        elif ascii_buf:
            pieces.append("".join(ascii_buf))
            ascii_buf = []
    if ascii_buf:
        pieces.append("".join(ascii_buf))
    slug = "-".join(piece for piece in pieces if piece)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if slug:
        return slug[:80]
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
