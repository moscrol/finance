"""实体锚定（#6 修复）：图谱语义检索前先做确定性实体解析。

问题根因：问题原文（如「深信服现在 PE TTM 80 倍，贵不贵？」）直接进
``get_concept_matches`` / ``get_exposure_matches`` / wiki 向量检索，
「PE/估值/贵」这类通用词会把检索带偏到无关概念（实锤误锚：深信服→交换机/800G
光模块、中际旭创→AI PCB）。

修复思路（检索工程里叫 query anchoring / entity linking，先做实体链接再检索，
同样适用于任何 RAG 管线的 query 预处理层）：

1. **精确实体解析**（确定性，不用 LLM）：股票代码正则 + 实体名最长子串匹配，
   实体清单来自 wiki ``relations/entity_exposures.json``（知识库登记的公司实体）。
2. **命中实体 → 用实体自身的概念暴露定锚**：把「实体名 + 它已登记的概念」作为
   图谱/向量检索词，替代问题原文，检索空间被锚回实体真实产业链。
3. **未命中 → 原样退回语义检索**，行为逐字节不变。

替代方案对比：a) NER 模型（如 LAC/HanLP）——召回更广但引入模型依赖与误识别，
白名单实体清单已覆盖需求；b) LLM 抽实体——有幻觉风险且破坏确定性纪律；
c) 向量检索加权——治标不治本，通用词仍会稀释。精确匹配是这里的最优解。
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from intelligence.adapters.knowledge import KnowledgeAdapter

MAX_ANCHOR_CONCEPTS = 4
MIN_NAME_LEN = 2

_CODE_RE = re.compile(r"\b(\d{6})(?:\.(SH|SZ|BJ))?\b", re.I)


@dataclass(frozen=True)
class EntityAnchor:
    entity: str
    ticker: str = ""
    concepts: tuple[str, ...] = ()
    matched_by: str = "name"  # "name" | "code"
    warnings: tuple[str, ...] = ()

    @property
    def graph_query(self) -> str:
        """锚定后的图谱/向量检索词：实体名 + 实体自身概念暴露。"""
        return " ".join([self.entity, *self.concepts]).strip()

    def summary(self) -> str:
        concepts = "、".join(self.concepts) if self.concepts else "（该实体暂无概念暴露登记）"
        code = f"（{self.ticker}）" if self.ticker else ""
        return f"实体锚定：命中 {self.entity}{code}，图谱检索以其概念暴露定锚 → {concepts}"


@dataclass(frozen=True)
class _EntityRecord:
    name: str
    codes: tuple[str, ...] = field(default_factory=tuple)
    concepts: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class _EntityLexiconCacheEntry:
    fingerprint: tuple[int, int]
    records: tuple[_EntityRecord, ...]


_LEXICON_CACHE: dict[str, _EntityLexiconCacheEntry] = {}
_LEXICON_LOCK = threading.RLock()


def _load_entity_records(knowledge: KnowledgeAdapter) -> tuple[_EntityRecord, ...]:
    relation = knowledge.load_relation("entity_exposures")
    if not relation["found"]:
        return ()
    entities = relation["data"].get("entities", {})
    if not isinstance(entities, dict):
        return ()
    records: list[_EntityRecord] = []
    for name, row in entities.items():
        if not isinstance(name, str) or not isinstance(row, dict):
            continue
        codes = row.get("codes", [])
        concepts = row.get("concepts", {})
        concept_names = [str(c) for c in concepts] if isinstance(concepts, dict) else []
        for exposure in row.get("exposures", []) if isinstance(row.get("exposures"), list) else []:
            if isinstance(exposure, dict):
                c = str(exposure.get("concept") or exposure.get("theme") or "").strip()
                if c and c not in concept_names:
                    concept_names.append(c)
        records.append(
            _EntityRecord(
                name=name.strip(),
                codes=tuple(str(c) for c in codes) if isinstance(codes, list) else (),
                concepts=tuple(concept_names),
            )
        )
    return tuple(records)


def _relation_fingerprint(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def _cached_entity_records(knowledge: KnowledgeAdapter) -> tuple[_EntityRecord, ...]:
    path = knowledge.relation_path("entity_exposures").resolve()
    fingerprint = _relation_fingerprint(path)
    if fingerprint is None:
        return ()
    cache_key = str(path)
    with _LEXICON_LOCK:
        cached = _LEXICON_CACHE.get(cache_key)
        if cached is not None and cached.fingerprint == fingerprint:
            return cached.records
        records = _load_entity_records(knowledge)
        _LEXICON_CACHE[cache_key] = _EntityLexiconCacheEntry(
            fingerprint=fingerprint,
            records=records,
        )
        return records


def _clear_entity_lexicon_cache() -> None:
    """测试辅助：生产代码通过文件指纹自动刷新，无需主动清理。"""
    with _LEXICON_LOCK:
        _LEXICON_CACHE.clear()


def resolve_entity_anchor(query: str, knowledge: KnowledgeAdapter) -> EntityAnchor | None:
    """确定性实体解析：代码精确匹配优先，其次实体名最长子串匹配；未命中返回 None。"""
    text = str(query or "")
    if not text.strip():
        return None
    records = _cached_entity_records(knowledge)
    if not records:
        return None

    code_match = _CODE_RE.search(text)
    if code_match:
        raw = code_match.group(1)
        for rec in records:
            if any(str(code).startswith(raw) for code in rec.codes):
                return _build_anchor(rec, matched_by="code")

    named = [rec for rec in records if len(rec.name) >= MIN_NAME_LEN and rec.name in text]
    if named:
        named.sort(key=lambda rec: len(rec.name), reverse=True)
        return _build_anchor(named[0], matched_by="name")
    return None


def _build_anchor(rec: _EntityRecord, matched_by: str) -> EntityAnchor:
    warnings: list[str] = []
    if not rec.concepts:
        warnings.append(f"实体 {rec.name} 在 entity_exposures 无概念暴露登记，锚定退化为实体名本身")
    return EntityAnchor(
        entity=rec.name,
        ticker=rec.codes[0] if rec.codes else "",
        concepts=tuple(rec.concepts[:MAX_ANCHOR_CONCEPTS]),
        matched_by=matched_by,
        warnings=tuple(warnings),
    )
