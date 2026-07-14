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
from dataclasses import dataclass, field

from intelligence.adapters.knowledge import KnowledgeAdapter

MAX_ANCHOR_CONCEPTS = 4
MIN_NAME_LEN = 2
_GENERIC_CONCEPT_SEEDS = {
    "业务",
    "产品",
    "产业",
    "产业链",
    "公司",
    "相关",
    "市场",
    "技术",
    "数据",
    "概念",
    "中心",
    "系统",
    "行业",
    "设备",
    "题材",
}

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


@dataclass
class _EntityRecord:
    name: str
    codes: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)


def _load_entity_records(knowledge: KnowledgeAdapter) -> list[_EntityRecord]:
    relation = knowledge.load_relation("entity_exposures")
    if not relation["found"]:
        return []
    entities = relation["data"].get("entities", {})
    if not isinstance(entities, dict):
        return []
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
                codes=[str(c) for c in codes] if isinstance(codes, list) else [],
                concepts=concept_names,
            )
        )
    return records


def resolve_entity_anchor(query: str, knowledge: KnowledgeAdapter) -> EntityAnchor | None:
    """确定性实体解析：代码精确匹配优先，其次实体名最长子串匹配；未命中返回 None。"""
    text = str(query or "")
    if not text.strip():
        return None
    records = _load_entity_records(knowledge)
    if not records:
        return None

    code_match = _CODE_RE.search(text)
    if code_match:
        raw = code_match.group(1)
        for rec in records:
            if any(str(code).startswith(raw) for code in rec.codes):
                return _build_anchor(rec, matched_by="code", query=text)

    named = [rec for rec in records if len(rec.name) >= MIN_NAME_LEN and rec.name in text]
    if named:
        named.sort(key=lambda rec: len(rec.name), reverse=True)
        return _build_anchor(named[0], matched_by="name", query=text)
    return None


def _normalize_concept_text(value: str) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").casefold())


def _is_specific_concept_seed(value: str) -> bool:
    if value in _GENERIC_CONCEPT_SEEDS:
        return False
    minimum_length = 3 if value.isascii() else 2
    return len(value) >= minimum_length


def _rank_concepts_for_query(concepts: list[str], query: str) -> list[str]:
    normalized_query = _normalize_concept_text(query)
    if not normalized_query:
        return concepts
    normalized_concepts = [
        _normalize_concept_text(concept) for concept in concepts
    ]
    seeds = sorted(
        (
            (normalized_query.find(normalized), index, normalized)
            for index, normalized in enumerate(normalized_concepts)
            if _is_specific_concept_seed(normalized)
            and normalized in normalized_query
        ),
        key=lambda item: (item[0], item[1]),
    )
    if not seeds:
        return concepts

    ranked_indices: list[int] = []
    seen: set[int] = set()
    for _, _, seed in seeds:
        for index, normalized in enumerate(normalized_concepts):
            if index in seen or not normalized:
                continue
            same_family = seed in normalized or (
                _is_specific_concept_seed(normalized) and normalized in seed
            )
            if same_family:
                seen.add(index)
                ranked_indices.append(index)
    ranked_indices.extend(
        index for index in range(len(concepts)) if index not in seen
    )
    return [concepts[index] for index in ranked_indices]


def _build_anchor(
    rec: _EntityRecord,
    matched_by: str,
    *,
    query: str,
) -> EntityAnchor:
    warnings: list[str] = []
    if not rec.concepts:
        warnings.append(f"实体 {rec.name} 在 entity_exposures 无概念暴露登记，锚定退化为实体名本身")
    ranked_concepts = _rank_concepts_for_query(rec.concepts, query)
    return EntityAnchor(
        entity=rec.name,
        ticker=rec.codes[0] if rec.codes else "",
        concepts=tuple(ranked_concepts[:MAX_ANCHOR_CONCEPTS]),
        matched_by=matched_by,
        warnings=tuple(warnings),
    )
