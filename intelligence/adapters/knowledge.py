from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from intelligence.paths import default_paths


# relations 是每天重建的大 JSON（entity_exposures 18.6MB / evidence_index
# 18.7MB / concept_graph 6.8MB）。load_relation 原本每次调用都全量重解析，
# 单次问答里 entity_exposures 会被解析十几次——纯冗余，且直接吃掉 turn 预算。
#
# 缓存键含 mtime_ns 与 size：KB 重建后自动失效，不会读到陈旧图谱。
# 备选方案：lru_cache（无法感知重建，会读陈旧数据）；进程启动时一次性加载
# （同样陈旧，且拖慢冷启动）。故选带 stat 校验的显式缓存。
_RELATION_CACHE: dict[str, tuple[int, int, dict[str, Any]]] = {}
_RELATION_CACHE_LOCK = threading.Lock()


def clear_relation_cache() -> None:
    """清空 relations 缓存（测试与 KB 重建后的显式失效用）。"""
    with _RELATION_CACHE_LOCK:
        _RELATION_CACHE.clear()


# 概念打分的三档语义：
#   10  概念名精确匹配（名字出现在问题里，或与切词完全相等）
#    5  概念名包含查询词
#    2  查询词出现在「概念 payload 被截断到 2000 字符的 JSON dump」里
#
# 第三档不是语义关联，是截断产生的伪影：查"固态电池"会带出 MOF材料/全球锂矿/
# 化工，查"半导体设备"会带出 C4化工/CVD金刚石/GPU。实测 4 个主线题材里它占
# 命中的 80%–90%，这些噪声会随证据块一起进 LLM 上下文，既挤占预算又干扰判断。
#
# 语义召回由向量层（BM25 + BGE-m3 + RRF）负责且效果良好；结构化层的职责是
# 精确锚定，不是模糊召回。故只保留概念名级别的命中。
_PAYLOAD_DUMP_SCORE = 2
_MIN_CONCEPT_SCORE = 5


RELATION_FILES = {
    "aliases": "aliases.json",
    "benchmark_maps": "benchmark_maps.json",
    "concept_graph": "concept_graph.json",
    "entity_exposures": "entity_exposures.json",
    "evidence_index": "evidence_index.json",
    "invalidation_links": "invalidation_links.json",
    "pattern_library": "pattern_library.json",
    "report_contexts": "report_contexts.json",
    "theme_signals": "theme_signals.json",
}

_GENERIC_SEARCH_TERMS = {
    "a股",
    "公司",
    "相关",
    "题材",
    "产业链",
    "上游",
    "下游",
    "分层",
    "证据",
    "缺口",
    "反证",
    "事实",
    "推测",
    "待验证",
    "触发条件",
    "核验动作",
    "深研",
    "给出",
    "定义",
    "明确",
    "区分",
    "核心",
    "受益",
    "弱关联",
}


_EVIDENCE_STATUSES = {"active", "superseded", "invalidated"}


def evidence_status(item: dict[str, Any]) -> str:
    """证据条目的生命周期状态；缺失或非法值一律视为 active。"""
    status = str(item.get("status") or "").strip().lower()
    return status if status in _EVIDENCE_STATUSES else "active"


def _evidence_key(item: dict[str, Any]) -> str:
    """证据条目的稳定复合键，与知识库仓 invalidation_overlay.evidence_key 同构。"""
    return "|".join(
        (
            str(item.get("target") or ""),
            str(item.get("concept") or ""),
            str(item.get("source_date") or ""),
            str(item.get("source") or ""),
            str(item.get("evidence") or "")[:80],
        )
    )


@dataclass(frozen=True)
class KnowledgeAdapter:
    wiki_root: str | Path | None = None

    @property
    def resolved_wiki_root(self) -> Path:
        return Path(self.wiki_root).expanduser() if self.wiki_root else default_paths().knowledge_wiki

    @property
    def relations_dir(self) -> Path:
        return self.resolved_wiki_root / "relations"

    def relation_path(self, name: str) -> Path:
        filename = RELATION_FILES.get(name, name)
        if not filename.endswith(".json"):
            filename = f"{filename}.json"
        return self.relations_dir / filename

    def load_relation(self, name: str) -> dict[str, Any]:
        path = self.relation_path(name)
        key = str(path)
        try:
            stat = path.stat()
        except OSError:
            return {"found": False, "name": name, "path": key, "data": {}, "warnings": ["relation file not found"], "errors": []}

        mtime_ns, size = stat.st_mtime_ns, stat.st_size
        with _RELATION_CACHE_LOCK:
            cached = _RELATION_CACHE.get(key)
        if cached is not None and cached[0] == mtime_ns and cached[1] == size:
            # 返回的是缓存中的同一个 dict。全部调用方都只读（.get / 迭代），
            # 唯一会改 relations 的 checkpoint_writeback 走独立的 json.loads
            # 且写完后 mtime 变化会让本缓存自然失效。
            return {"found": True, "name": name, "path": key, "data": cached[2], "warnings": [], "errors": []}

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"found": False, "name": name, "path": key, "data": {}, "warnings": [], "errors": [str(exc)]}
        if not isinstance(data, dict):
            return {"found": False, "name": name, "path": key, "data": {}, "warnings": ["relation root is not an object"], "errors": []}

        with _RELATION_CACHE_LOCK:
            _RELATION_CACHE[key] = (mtime_ns, size, data)
        return {"found": True, "name": name, "path": key, "data": data, "warnings": [], "errors": []}

    def get_entity_exposures(self, entity: str) -> dict[str, Any]:
        relation = self.load_relation("entity_exposures")
        if not relation["found"]:
            return {
                "found": False,
                "entity": entity,
                "data": None,
                "concepts": {},
                "exposures": [],
                "warnings": relation["warnings"],
                "errors": relation["errors"],
            }
        data = relation["data"]
        entities = data.get("entities", {})
        if not isinstance(entities, dict):
            return {
                "found": False,
                "entity": entity,
                "data": None,
                "concepts": {},
                "exposures": [],
                "warnings": ["entity_exposures.entities is not an object"],
                "errors": [],
            }
        item = entities.get(entity)
        if item is None:
            return {
                "found": False,
                "entity": entity,
                "data": None,
                "concepts": {},
                "exposures": [],
                "warnings": ["entity not found in entity_exposures"],
                "errors": [],
            }
        if not isinstance(item, dict):
            return {
                "found": False,
                "entity": entity,
                "data": None,
                "concepts": {},
                "exposures": [],
                "warnings": ["entity exposure entry is not an object"],
                "errors": [],
            }
        concepts = item.get("concepts", {})
        exposures = item.get("exposures", [])
        return {
            "found": True,
            "entity": entity,
            "data": item,
            "concepts": concepts if isinstance(concepts, dict) else {},
            "exposures": exposures if isinstance(exposures, list) else [],
            "warnings": [],
            "errors": [],
        }

    def get_evidence(
        self,
        target: str,
        concept: str | None = None,
        limit: int = 20,
        include_invalidated: bool = False,
    ) -> dict[str, Any]:
        """按 target/concept 检索证据条目（Temporal Facts 读策略）。

        条目可选 ``status`` 字段：``active``（默认）/ ``superseded``（已被新证据
        取代，保留但排序降后）/ ``invalidated``（已被证伪，默认不返回）。

        另叠加知识库仓的证伪回链派生层 ``relations/invalidation_links.json``：
        hard 链→视为 invalidated；soft 链→视为 superseded（保留但降后并附回链说明）。
        """
        relation = self.load_relation("evidence_index")
        if not relation["found"]:
            return {
                "found": False,
                "target": target,
                "concept": concept,
                "items": [],
                "warnings": relation["warnings"],
                "errors": relation["errors"],
            }
        data = relation["data"]
        items = data.get("items", [])
        if not isinstance(items, list):
            return {
                "found": False,
                "target": target,
                "concept": concept,
                "items": [],
                "warnings": ["evidence_index.items is not a list"],
                "errors": [],
            }
        overlay_idx = self._invalidation_overlay_index()
        target_items = []
        for item in items:
            if not isinstance(item, dict) or item.get("target") != target:
                continue
            status = evidence_status(item)
            if status == "active" and overlay_idx:
                link = overlay_idx.get(_evidence_key(item))
                if link is not None:
                    status = (
                        "invalidated"
                        if link.get("strength") == "hard"
                        else "superseded"
                    )
                    item = {
                        **item,
                        "status": status,
                        "status_note": link.get("note") or "",
                    }
            if status == "invalidated" and not include_invalidated:
                continue
            target_items.append(item)
        target_items.sort(
            key=lambda item: evidence_status(item) == "superseded"
        )
        if concept:
            exact_items = [
                item
                for item in target_items
                if self._normalize(item.get("concept")) == self._normalize(concept)
            ]
            target_items = exact_items or [
                item
                for item in target_items
                if self._evidence_matches_concept(item, concept)
            ]
        matched = target_items[:limit]
        return {
            "found": bool(matched),
            "target": target,
            "concept": concept,
            "items": matched,
            "warnings": [] if matched else ["evidence not found"],
            "errors": [],
        }

    def get_concept_matches(self, term: str, limit: int = 5) -> dict[str, Any]:
        relation = self.load_relation("concept_graph")
        if not relation["found"]:
            return {
                "found": False,
                "term": term,
                "items": [],
                "warnings": relation["warnings"],
                "errors": relation["errors"],
            }
        concepts = relation["data"].get("concepts", {})
        if not isinstance(concepts, dict):
            return {
                "found": False,
                "term": term,
                "items": [],
                "warnings": ["concept_graph.concepts is not an object"],
                "errors": [],
            }
        terms = self._search_terms(term)
        query_text = self._normalize(term)
        matched = []
        for name, payload in concepts.items():
            text = f"{name} {json.dumps(payload, ensure_ascii=False)[:2000]}"
            score = 0
            normalized_name = self._normalize(name)
            if normalized_name and normalized_name in query_text:
                score += 10
            for candidate in terms:
                if self._is_generic_search_term(candidate):
                    continue
                if self._normalize(candidate) == normalized_name:
                    score += 10
                elif self._contains(candidate, name):
                    score += 5
                elif self._is_precise_weak_search_term(
                    candidate
                ) and self._contains(candidate, text):
                    score += _PAYLOAD_DUMP_SCORE
            if score >= _MIN_CONCEPT_SCORE:
                matched.append({"concept": name, "score": score})
        items = sorted(matched, key=lambda row: (-int(row["score"]), row["concept"]))[:limit]
        return {
            "found": bool(items),
            "term": term,
            "items": items,
            "warnings": [] if items else ["concept not found"],
            "errors": [],
        }

    def get_exposure_matches(self, term: str, limit: int = 12) -> dict[str, Any]:
        relation = self.load_relation("entity_exposures")
        if not relation["found"]:
            return {
                "found": False,
                "term": term,
                "items": [],
                "warnings": relation["warnings"],
                "errors": relation["errors"],
            }
        terms = self._search_terms(term)
        query_text = self._normalize(term)
        matched = []
        for row in self._iter_exposure_rows(relation["data"]):
            score = 0
            concept_name = str(row.get("concept") or row.get("theme") or "")
            company = str(
                row.get("entity") or row.get("company") or row.get("name") or ""
            ).strip()
            text = self._exposure_text(row)
            normalized_concept = self._normalize(concept_name)
            normalized_company = self._normalize(company)
            if normalized_concept and normalized_concept in query_text:
                score += 10
            if normalized_company and normalized_company in query_text:
                score += 8
            for candidate in terms:
                if self._is_generic_search_term(candidate):
                    continue
                if self._normalize(candidate) == normalized_concept:
                    score += 10
                elif self._contains(candidate, concept_name):
                    score += 5
                elif self._is_precise_weak_search_term(
                    candidate
                ) and self._contains(
                    candidate, text
                ):
                    score += 1
            if score <= 0:
                continue
            if not company:
                continue
            matched.append(self._exposure_ref(row, score))
        merged: dict[str, dict[str, Any]] = {}
        for row in matched:
            key = row["company"]
            if key not in merged or int(row["score"]) > int(merged[key]["score"]):
                merged[key] = row
        items = sorted(merged.values(), key=lambda row: (-int(row["score"]), row["company"]))[:limit]
        return {
            "found": bool(items),
            "term": term,
            "items": items,
            "warnings": [] if items else ["entity exposures not found"],
            "errors": [],
        }

    def _invalidation_overlay_index(self) -> dict[str, dict[str, Any]]:
        """把证伪回链 overlay 摆平成 {evidence_key: {strength, note}}；hard 优先。"""
        relation = self.load_relation("invalidation_links")
        if not relation["found"]:
            return {}
        idx: dict[str, dict[str, Any]] = {}
        for link in relation["data"].get("links", []) or []:
            if not isinstance(link, dict):
                continue
            strength = str(link.get("strength") or "")
            negation = link.get("negation") or {}
            hits = "/".join(negation.get("hits") or [])
            kind = "证伪" if strength == "hard" else "待定性"
            note = (
                f"回链：{negation.get('source_date') or '?'} "
                f"{hits}（{kind}·待人工复核）"
            )
            for prior in link.get("invalidates") or []:
                if not isinstance(prior, dict):
                    continue
                key = prior.get("key")
                if not key:
                    continue
                current = idx.get(key)
                if current is None or (
                    current.get("strength") != "hard" and strength == "hard"
                ):
                    idx[key] = {"strength": strength, "note": note}
        return idx

    @staticmethod
    def _evidence_matches_concept(item: dict[str, Any], concept: str) -> bool:
        fields = [
            item.get("concept"),
            item.get("theme"),
            item.get("term"),
            item.get("evidence"),
            item.get("source"),
        ]
        return any(concept in str(value) for value in fields if value is not None)

    @staticmethod
    def _normalize(value: Any) -> str:
        return re.sub(r"\s+", "", str(value or "").lower())

    @classmethod
    def _contains(cls, term: str, text: str) -> bool:
        return bool(term and text and cls._normalize(term) in cls._normalize(text))

    @classmethod
    def _is_generic_search_term(cls, term: str) -> bool:
        return cls._normalize(term) in _GENERIC_SEARCH_TERMS

    @classmethod
    def _is_precise_weak_search_term(cls, term: str) -> bool:
        normalized = cls._normalize(term)
        return (
            2 <= len(normalized) <= 8
            and not any(
                generic in normalized
                for generic in _GENERIC_SEARCH_TERMS
                if len(generic) >= 2
            )
        )

    @staticmethod
    def _search_terms(term: str) -> list[str]:
        parts = re.split(
            r"[\s,，、/|;；：:()（）\[\]【】“”\"'《》]+",
            str(term or ""),
        )
        terms = [part.strip() for part in parts if len(part.strip()) >= 2]
        out = []
        for item in terms:
            if item and item not in out:
                out.append(item)
        return out

    @classmethod
    def _iter_exposure_rows(cls, data: dict[str, Any]):
        for row in data.get("items", []) or []:
            if isinstance(row, dict):
                yield row
        entities = data.get("entities", {})
        if not isinstance(entities, dict):
            return
        for entity_name, entity_row in entities.items():
            if not isinstance(entity_row, dict):
                continue
            codes = entity_row.get("codes", [])
            ticker = codes[0] if isinstance(codes, list) and codes else ""
            concepts = entity_row.get("concepts", {})
            if isinstance(concepts, dict):
                for concept_name, concept_row in concepts.items():
                    row = dict(concept_row) if isinstance(concept_row, dict) else {"summary": concept_row}
                    row["entity"] = entity_name
                    row["company"] = entity_name
                    row["concept"] = concept_name
                    row["ticker"] = row.get("ticker") or ticker
                    yield row
            exposures = entity_row.get("exposures", [])
            if isinstance(exposures, list):
                for exposure in exposures:
                    if isinstance(exposure, dict):
                        row = dict(exposure)
                        row["entity"] = row.get("entity") or entity_name
                        row["company"] = row.get("company") or entity_name
                        row["ticker"] = row.get("ticker") or ticker
                        yield row

    @staticmethod
    def _exposure_text(row: dict[str, Any]) -> str:
        values = []
        for key in ("entity", "company", "concept", "theme", "role", "summary", "evidence", "source", "source_name", "reason", "chain_layer"):
            values.append(row.get(key, ""))
        for key in ("concepts", "aliases", "tags"):
            value = row.get(key)
            values.extend(value if isinstance(value, list) else [value])
        return " ".join(str(value) for value in values if str(value).strip())

    @staticmethod
    def _exposure_ref(row: dict[str, Any], score: int) -> dict[str, Any]:
        return {
            "company": row.get("entity") or row.get("company") or row.get("name") or "",
            "ticker": row.get("ticker") or row.get("code") or row.get("stock_code") or "",
            "concept": row.get("concept") or row.get("theme") or "",
            "role": row.get("role") or row.get("summary") or row.get("chain_layer") or "",
            "strength": row.get("strength") or row.get("tier") or row.get("exposure_strength") or "",
            "confidence": row.get("confidence") or row.get("confidence_tier") or "",
            "evidence_layer": row.get("evidence_layer") or row.get("layer") or "",
            "source": row.get("source") or row.get("source_name") or "",
            "score": score,
        }
