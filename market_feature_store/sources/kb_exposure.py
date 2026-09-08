"""知识库暴露度读侧适配器——把 ``wiki/relations/entity_exposures.json`` 变成「这只股对这个题材正不正宗」。

为什么要它：主线题材里成交额大、涨得凶的股，可能只是沾边炒作。判「正宗」需要一份
**与当日行情无关**的先验，知识库那份（iFinD 年报/主营画像 L2 + 研报线索 L1/L3）正好是。

数据形状（2026-09-07 实测）：4608 个实体 / 4510 个 6 位代码 / 24021 条 concept 边；
strength = related 14572 / core 6012 / peripheral 3065；evidence_layer = L2 13840（年报主营画像）、
L1_L3_candidate 5202、graph_only 2138、L1 1360、L2_candidate 1227、L3 218。

两个刻意的设计：

1. **只白名单硬证据层**（L1/L2/L3）。graph_only 与各种 ``*_candidate`` 是「研报说的、还没坐实」，
   算软证据。层名不认识时按软处理——认不出来就往低了判，不给未知层发正宗证书。
2. **``as_of`` 逐边过滤**。每条边自带 ``updated``，回测历史日时必须只用那天之前已经存在的边，
   否则是拿今天的知识去挑昨天的股（前视偏差）。缺 ``updated`` 的边在 as_of 模式下直接丢弃。

红线：知识库大 JSON 不许 ``cat``。本模块一次性 ``json.load`` 到内存并按 mtime 缓存，
调用方拿到的是精简子集（code → 边列表），不把原文塞进任何上下文。
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

HARD_LAYERS = frozenset({"L1", "L2", "L3"})
#: strength → (硬证据分, 软证据分)。core=主营直接对应；related=沾边；peripheral=图谱弱关联。
STRENGTH_SCORE = {
    "core": (1.0, 0.6),
    "core_related": (0.4, 0.2),
    "related": (0.4, 0.2),
    "peripheral": (0.0, 0.0),
    "watch": (0.0, 0.0),
}

_CACHE: dict[str, tuple[float, object]] = {}


class KbExposureUnavailable(RuntimeError):
    """知识库 relations 不可读。正宗度是本产品的定义要件，读不到就停，不静默降级成纯人气。"""


def kb_relations_dir() -> Path:
    """知识库 wiki/relations 目录。路径解析复用 ``intelligence.paths``，不另建第二套探测。

    懒导入：``intelligence`` 反过来 import ``market_feature_store``（adapters/market.py），
    模块级 import 会成环；函数内 import 只在运行时解析，两边都已就位。
    """
    # 函数内 import 是刻意的（避免包环，见 docstring），不是漏提到模块顶
    from intelligence.paths import resolve_knowledge_wiki

    return Path(resolve_knowledge_wiki()) / "relations"


def _load(name: str, relations_dir: Path | None = None):
    d = relations_dir or kb_relations_dir()
    path = d / name
    if not path.is_file():
        raise KbExposureUnavailable(f"知识库 relations 缺 {path}")
    key = str(path)
    mtime = path.stat().st_mtime
    hit = _CACHE.get(key)
    if hit and hit[0] == mtime:
        return hit[1]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _CACHE[key] = (mtime, data)
    return data


def concept_aliases(relations_dir: Path | None = None) -> dict[str, str]:
    """别名 → 规范概念名。板块名与 KB concept 名同粒度但写法不一（「散热」/「液冷温控」）。"""
    raw = _load("aliases.json", relations_dir)
    return dict(raw.get("aliases") or {})


def normalize_concept(name: str, aliases: dict[str, str]) -> str:
    if not name:
        return ""
    seen = set()
    cur = name.strip()
    # 别名表里存在链式指向（A→B、B→C），跟到不动点为止；自环/环路靠 seen 兜住。
    while cur in aliases and cur not in seen:
        seen.add(cur)
        cur = aliases[cur]
    return cur


#: 板块名常见的装饰后缀。fupanhui 的板块名带「概念/板块」而 KB concept 不带（「PCB概念」vs「PCB」）。
_DECOR_SUFFIX = ("概念", "板块", "指数", "产业")


def concept_candidates(name: str, aliases: dict[str, str]) -> set[str]:
    """一个板块/题材名 → 可能对应的 KB concept 名集合（原名、别名归一、剥装饰后缀后再归一）。

    只做这两类机械变换，**不手写映射表**：手写表会变成第二份事实源，且没人知道它什么时候漂了。
    覆盖率就当读数报出来（2026-09-07 实测：全库板块 297/512，当日主线 30/44 命中）。
    """
    out: set[str] = set()
    base = (name or "").strip()
    if not base:
        return out
    forms = {base}
    for suffix in _DECOR_SUFFIX:
        if base.endswith(suffix) and len(base) > len(suffix):
            forms.add(base[: -len(suffix)])
    for form in forms:
        out.add(form)
        out.add(normalize_concept(form, aliases))
    return {x for x in out if x}


def code6(ts_code: str) -> str:
    """``300308.SZ`` → ``300308``。知识库存 6 位裸代码，行情库存 ts_code。"""
    return str(ts_code).split(".")[0]


def exposure_index(*, relations_dir: Path | None = None, as_of: date | str | None = None) -> dict[str, list[dict]]:
    """code6 → 边列表 ``[{concept, strength, evidence_layer, confidence, updated, entity}]``。

    ``as_of`` 给定时只保留 ``updated <= as_of`` 的边（缺 updated 的丢弃），供历史回测使用。
    """
    data = _load("entity_exposures.json", relations_dir)
    aliases = concept_aliases(relations_dir)
    cutoff = None
    if as_of is not None:
        cutoff = as_of.isoformat() if isinstance(as_of, date) else str(as_of)[:10]
    index: dict[str, list[dict]] = {}
    for entity_name, entity in (data.get("entities") or {}).items():
        codes = [code6(c) for c in (entity.get("codes") or []) if str(c).strip()]
        codes = [c for c in codes if c.isdigit() and len(c) == 6]
        if not codes:
            continue
        edges = []
        for concept, meta in (entity.get("concepts") or {}).items():
            if not isinstance(meta, dict):
                continue
            updated = meta.get("updated")
            if cutoff is not None and (not updated or str(updated)[:10] > cutoff):
                continue
            edges.append({
                "concept": normalize_concept(concept, aliases),
                "raw_concept": concept,
                "strength": meta.get("strength"),
                "evidence_layer": meta.get("evidence_layer"),
                "confidence": meta.get("confidence"),
                "updated": updated,
                "entity": entity_name,
            })
        if not edges:
            continue
        for code in codes:
            index.setdefault(code, []).extend(edges)
    return index


def score_edge(edge: dict) -> float:
    hard, soft = STRENGTH_SCORE.get(edge.get("strength") or "", (0.0, 0.0))
    return hard if (edge.get("evidence_layer") in HARD_LAYERS) else soft


def best_exposure(edges: list[dict], concepts: set[str]) -> tuple[float, dict | None]:
    """在 ``concepts``（已归一的板块/题材名集合）里挑分最高的一条边。无命中返回 (0.0, None)。"""
    best_score, best = 0.0, None
    for edge in edges or ():
        if edge["concept"] not in concepts:
            continue
        s = score_edge(edge)
        if s > best_score or best is None:
            best_score, best = s, edge
    return (best_score, best) if best is not None else (0.0, None)
