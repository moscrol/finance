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

import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.paths import default_market_db_path

MAX_ANCHOR_CONCEPTS = 4
MIN_NAME_LEN = 2
# 证券名单是第二本词典（DuckDB 全市场 ~7500 名），比 wiki 实体面大一个量级；
# 2 字简称（如「万科」）的常用词碰撞面太大，回退词典只收 3 字以上。
# 2 字名个股仍可经 wiki 登记（第一本词典）或 6 位代码锚定。
MIN_SECURITY_NAME_LEN = 3
# 第二本词典的显式开关：未设走 default_market_db_path()（生产），"0"/"off"
# 禁用，路径值覆盖。存在的理由是**测试密封**——生产库路径不靠 env 也能
# 解析出来（data_repo_root 回退），conftest 的 delenv 密封盖不住这条路；
# 没有开关，实体锚定测试在有真实库的机器上就变环境依赖（#310 同病）。
SECURITIES_DB_ENV = "ENTITY_ANCHOR_SECURITIES_DB"

_CODE_RE = re.compile(r"(?<!\d)(\d{6})(?:\.(SH|SZ|BJ))?(?!\d)", re.I)


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


def _load_security_records(db_path: Path) -> tuple[_EntityRecord, ...]:
    """从本地行情库读证券名单（第二本词典）。任何失败都退成空表。

    为什么需要它（2026-08-13 R13-A3）：wiki ``entity_exposures`` 只登记做过
    研究的公司；「立新能源怎么看」这类未登记个股锚定落空后，要么被主题词典
    误抢（已由左边界检查挡住），要么落进通用问答给不出个股深挖。全市场
    名单一直就在 ``fact_stock_daily`` 里，缺的只是接进锚定层。

    fail closed：库不存在/被写锁/表缺失时返回空表，行为退回 wiki 单词典，
    与 trading_calendar._known_trading_days 同一纪律。
    """

    try:
        import duckdb

        connection = duckdb.connect(str(db_path), read_only=True)
    except Exception:
        return ()
    try:
        rows = connection.execute(
            "select distinct stock_name, stock_ts_code from fact_stock_daily "
            "where stock_name is not null and stock_ts_code is not null"
        ).fetchall()
    except Exception:
        return ()
    finally:
        connection.close()
    by_name: dict[str, set[str]] = {}
    for name, code in rows:
        cleaned = str(name).strip()
        if len(cleaned) < MIN_SECURITY_NAME_LEN:
            continue
        by_name.setdefault(cleaned, set()).add(str(code))
    return tuple(
        _EntityRecord(name=name, codes=tuple(sorted(codes)))
        for name, codes in by_name.items()
    )


def _resolve_securities_db(explicit: str | Path | None) -> Path | None:
    if explicit is not None:
        return Path(explicit).expanduser()
    raw = os.environ.get(SECURITIES_DB_ENV, "").strip()
    if raw.lower() in {"0", "off", "disabled"}:
        return None
    if raw:
        return Path(raw).expanduser()
    return default_market_db_path()


_SECURITY_CACHE: dict[str, _EntityLexiconCacheEntry] = {}


def _cached_security_records(db_path: Path) -> tuple[_EntityRecord, ...]:
    fingerprint = _relation_fingerprint(db_path)
    if fingerprint is None:
        return ()
    cache_key = str(db_path.resolve())
    with _LEXICON_LOCK:
        cached = _SECURITY_CACHE.get(cache_key)
        if cached is not None and cached.fingerprint == fingerprint:
            return cached.records
        records = _load_security_records(db_path)
        _SECURITY_CACHE[cache_key] = _EntityLexiconCacheEntry(
            fingerprint=fingerprint,
            records=records,
        )
        return records


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
        _SECURITY_CACHE.clear()


def entity_concept_names(knowledge: KnowledgeAdapter) -> tuple[str, ...]:
    """返回实体暴露里登记过的概念名，供确定性主题词典复用。"""
    return tuple(
        sorted(
            {
                concept
                for record in _cached_entity_records(knowledge)
                for concept in record.concepts
                if len(concept.strip()) >= MIN_NAME_LEN
            },
            key=len,
            reverse=True,
        )
    )


def resolve_entity_anchor(
    query: str,
    knowledge: KnowledgeAdapter,
    *,
    securities_db_path: str | Path | None = None,
) -> EntityAnchor | None:
    """确定性实体解析：wiki 词典优先，证券名单回退；未命中返回 None。

    两本词典的分工：wiki ``entity_exposures`` 带概念暴露（锚定后能定向
    图谱检索），证券名单只有名字和代码（锚定后至少路由对、盘面工具查得到）。
    wiki 命中时永远优先——概念暴露是锚定的全部增值。
    """

    text = str(query or "")
    if not text.strip():
        return None
    records = _cached_entity_records(knowledge)
    security_db = _resolve_securities_db(securities_db_path)
    security_records = (
        _cached_security_records(security_db) if security_db is not None else ()
    )
    if not records and not security_records:
        return None

    code_match = _CODE_RE.search(text)
    if code_match:
        raw = code_match.group(1)
        for rec in records:
            if any(str(code).startswith(raw) for code in rec.codes):
                return _build_anchor(rec, matched_by="code")
        for rec in security_records:
            if any(str(code).startswith(raw) for code in rec.codes):
                return _build_anchor(rec, matched_by="code", source="security_master")

    named = [rec for rec in records if len(rec.name) >= MIN_NAME_LEN and rec.name in text]
    if named:
        named.sort(key=lambda rec: len(rec.name), reverse=True)
        return _build_anchor(named[0], matched_by="name")
    security_named = [rec for rec in security_records if rec.name in text]
    if security_named:
        security_named.sort(key=lambda rec: len(rec.name), reverse=True)
        return _build_anchor(
            security_named[0],
            matched_by="name",
            source="security_master",
        )
    return None


def _build_anchor(
    rec: _EntityRecord,
    matched_by: str,
    *,
    source: str = "knowledge",
) -> EntityAnchor:
    warnings: list[str] = []
    if source == "security_master":
        warnings.append(
            f"实体 {rec.name} 来自证券名单（未在知识库登记），无概念暴露，"
            "图谱检索退化为实体名本身"
        )
    elif not rec.concepts:
        warnings.append(f"实体 {rec.name} 在 entity_exposures 无概念暴露登记，锚定退化为实体名本身")
    return EntityAnchor(
        entity=rec.name,
        ticker=rec.codes[0] if rec.codes else "",
        concepts=tuple(rec.concepts[:MAX_ANCHOR_CONCEPTS]),
        matched_by=matched_by,
        warnings=tuple(warnings),
    )
