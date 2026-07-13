"""Knowledge-base hybrid 向量检索 as an `ask` 召回源 (W source).

`intelligence.ask` already recalls graph/evidence (G/R) by deterministic keyword
scoring over the committed ``wiki/relations/*.json``. That只命中已入图谱的关系；
this module adds a *semantic* recall path that closes the loop between finance
review and the knowledge base: it fans the query out to the knowledge-base repo's
    hybrid vector retriever (``scripts/rag_index.py query --json`` — BGE-m3 dense +
    BM25 + RRF) to select candidate chunks and uses the returned matched chunk text
    as numbered ``[W#]`` evidence. Chunk identity and index revision stay attached
    so ranking and citation use the same snapshot.

Following the existing cross-repo wiring (``theme_modules`` replay/scan/migrate),
the retriever lives in the *knowledge-base* repo and is invoked by subprocess with
timeout + return-code check + graceful degrade. If the KB repo / RAG CLI / a built
index is unavailable (or the subprocess fails / times out / returns no hits), the
W source is skipped silently — 存在才接 —— without touching the S/G/R sources.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# rag_index.py lives at <KB repo root>/scripts/rag_index.py; the KB repo root is
# the parent of the wiki root (KnowledgeAdapter.resolved_wiki_root.parent).
RAG_SCRIPT_REL = Path("scripts") / "rag_index.py"
DEFAULT_RAG_TIMEOUT = 90
DEFAULT_RAG_K = 6
DEFAULT_RAG_MODE = "hybrid"
DEFAULT_EXCERPT_CHARS = 200

CITATION_PREFIX = "W"

# ---- 两种命名查询模式：结构版（默认）/ 全文版 -----------------------------
# 模式只切「索引目录 + 检索方式」，不改其余行为。默认 structured 与历史逐字节一致。
KB_MODE_STRUCTURED = "structured"
KB_MODE_FULL = "full"
FULL_INDEX_DIRNAME = ".rag_index_full"

# name / 别名（含中文）→ 规范模式名。
_KB_MODE_ALIASES = {
    KB_MODE_STRUCTURED: KB_MODE_STRUCTURED,
    "fast": KB_MODE_STRUCTURED,
    "\u7ed3\u6784": KB_MODE_STRUCTURED,
    "\u7ed3\u6784\u7248": KB_MODE_STRUCTURED,
    "\u901f\u67e5": KB_MODE_STRUCTURED,
    KB_MODE_FULL: KB_MODE_FULL,
    "deep": KB_MODE_FULL,
    "\u5168\u6587": KB_MODE_FULL,
    "\u5168\u6587\u7248": KB_MODE_FULL,
    "\u6df1\u5ea6": KB_MODE_FULL,
}

# 规范模式名 →（索引目录覆盖, 检索方式）。索引目录为 None 表示用默认 .rag_index。
_KB_MODE_PROFILE = {
    KB_MODE_STRUCTURED: (None, "hybrid"),
    KB_MODE_FULL: (FULL_INDEX_DIRNAME, "rerank"),
}

# 自然语言触发词：命中全文词→全文版；命中结构词→结构版（结构词显式优先）。
FULL_MODE_TRIGGERS = ("\u6df1\u6316", "\u770b\u539f\u6587", "\u539f\u6587", "\u6743\u5a01", "\u5b8c\u6574\u7248", "\u6df1\u5ea6", "\u5168\u6587")
STRUCTURED_MODE_TRIGGERS = ("\u5feb\u901f", "\u901f\u67e5", "\u7ed3\u6784\u7248", "\u7ed3\u6784")


def normalize_kb_mode(name: str | None) -> str | None:
    """把 name / 别名（含中文）解析成规范模式名；无法识别返回 None。"""
    if not name:
        return None
    return _KB_MODE_ALIASES.get(str(name).strip().lower())


def kb_mode_profile(name: str | None) -> tuple[str | None, str]:
    """规范模式名 →（索引目录覆盖, 检索方式）。未知 / None 回退结构版。"""
    canonical = normalize_kb_mode(name) or KB_MODE_STRUCTURED
    return _KB_MODE_PROFILE[canonical]


def detect_kb_mode(query: str | None) -> str | None:
    """从问句里识别模式触发词。

    命中全文触发词（深挖/看原文/原文/权威/完整版/深度/全文）→ ``full``；
    命中结构触发词（快速/速查/结构版/结构）→ ``structured``（显式快速优先）；
    都没命中 → None（由调用方默认结构版）。
    """
    q = str(query or "")
    if any(t in q for t in STRUCTURED_MODE_TRIGGERS):
        return KB_MODE_STRUCTURED
    if any(t in q for t in FULL_MODE_TRIGGERS):
        return KB_MODE_FULL
    return None


@dataclass
class WikiHit:
    page_id: str
    file_path: str  # relative to KB repo root, e.g. "wiki/synthesis/foo.md"
    title: str
    score: float
    excerpt: str
    best_chunk_id: str = ""
    section: str = ""
    content_hash: str = ""
    index_built_at: str = ""
    index_source_revision: str = ""
    index_freshness: str = ""
    evidence_layer: str = ""
    fact_hardness: str = ""
    source_type: str = ""
    via_neighbor: bool = False


# 检索方式 → 人类可读的“用了什么召回”说明（教学 / 可观测用）。
_MODE_RECALL_DESC = {
    "hybrid": "BM25 关键词 + 稠密向量(BGE-m3) + RRF 融合",
    "rerank": "BM25 + 稠密向量 + rerank 二次重排",
    "dense": "稠密向量(BGE-m3)",
    "bm25": "BM25 关键词",
}


def _index_kind(index_dir: Path | str) -> str:
    """索引类型：结构版 .rag_index / 全文版 .rag_index_full / 其他(自定义覆盖)。"""
    name = Path(index_dir).name
    if name == FULL_INDEX_DIRNAME:
        return "full"
    if name == ".rag_index":
        return "structured"
    return "custom"


@dataclass
class RetrievalTelemetry:
    """检索遥测：把“检索计划 → 实际召回源 → 召回质量”结构化记录下来。

    RAG 系统单看最终回答无法判断检索好坏；把每次召回的方式/索引/命中质量显式
    留痕，是做离线评估(recall@k、nDCG)、A/B 调参和排障的前提。此结构可迁移到
    任何检索 / 搜索 / 推荐系统的可观测层。
    """

    # 检索计划
    mode: str = ""  # 检索方式：hybrid / rerank / ...
    recall_desc: str = ""  # mode 的人话说明（用了 BM25 / 向量 / rerank 哪些）
    index_kind: str = ""  # 索引类型：structured(.rag_index) / full(.rag_index_full) / custom
    index_dir: str = ""  # 实际使用的索引目录
    requested_index_dir: str = ""  # 调用方请求的索引目录（与 index_dir 不同即发生降级）
    degraded: bool = False  # 是否发生索引降级（如全文索引缺失回退结构版）
    k: int = 0  # 请求的候选数
    filters: dict[str, str] = field(default_factory=dict)  # 层级 / 硬度 / 来源过滤
    # 召回结果与质量
    status: str = "pending"  # ok / empty / skipped / error / timeout
    hit_count: int = 0
    neighbor_hits: int = 0  # via_neighbor（图谱邻居扩展）命中数
    score_max: float | None = None
    score_min: float | None = None
    score_mean: float | None = None
    latency_ms: int | None = None  # 检索子进程耗时（毫秒）
    # None=旧 adapter/fake 未上报；0.0=已上报且真实零预算。
    timeout_seconds: float | None = None
    index_built_at: str = ""
    index_source_revision: str = ""
    index_freshness: str = ""
    dense_initializations: int = 0
    warning: str = ""

    def summary_line(self) -> str:
        """一行可观测摘要，供回答 / 日志展示。"""
        kind_cn = {"structured": "结构版索引", "full": "全文版索引", "custom": "自定义索引"}.get(
            self.index_kind, self.index_kind or "?"
        )
        recall = self.recall_desc or self.mode or "?"
        parts = [f"检索方式={self.mode or '?'}（{recall}）", f"索引={kind_cn}", f"k={self.k}"]
        if self.filters:
            parts.append("过滤=" + ",".join(f"{k}={v}" for k, v in self.filters.items()))
        parts.append(f"命中={self.hit_count}")
        if self.neighbor_hits:
            parts.append(f"其中邻居扩展={self.neighbor_hits}")
        if self.score_max is not None:
            parts.append(
                f"分数[max/mean/min]={self.score_max:.4f}/{self.score_mean:.4f}/{self.score_min:.4f}"
            )
        if self.latency_ms is not None:
            parts.append(f"耗时={self.latency_ms}ms")
        if self.degraded:
            parts.append("⚠索引降级")
        if self.index_freshness:
            parts.append(f"新鲜度={self.index_freshness}")
        if self.index_built_at:
            parts.append(f"构建={self.index_built_at}")
        parts.append(f"状态={self.status}")
        return " | ".join(parts)


@dataclass
class WikiRagResult:
    ok: bool = False
    command: str = ""
    citation_source: str = ""
    index_dir: str = ""
    hits: list[WikiHit] = field(default_factory=list)
    warning: str = ""
    telemetry: RetrievalTelemetry = field(default_factory=RetrievalTelemetry)


def kb_root(kb_wiki: str | Path) -> Path:
    """KB repo root = parent of the wiki root (mirrors theme_modules._kb_root)."""
    return Path(kb_wiki).expanduser().resolve().parent


def _resolve_index_dir(root: Path) -> Path:
    env = os.environ.get("VECTOR_INDEX_DIR") or os.environ.get("RAG_INDEX_DIR")
    if env:
        return Path(env).expanduser()
    return root / ".rag_index"


def _resolve_rag_python(root: Path) -> str:
    """Prefer the KB repo's RAG venv, while allowing explicit overrides."""
    env = os.environ.get("KB_RAG_PYTHON") or os.environ.get("RAG_PYTHON")
    if env:
        return str(Path(env).expanduser())
    for rel in (Path(".rag_venv") / "bin" / "python", Path(".venv") / "bin" / "python"):
        candidate = root / rel
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _matched_excerpt(item: dict, max_chars: int) -> str:
    text = str(item.get("evidence_text") or item.get("snippet") or "")
    return re.sub(r"\s+", " ", text).strip()[:max_chars]


def retrieve(
    query: str,
    kb_wiki: str | Path | None,
    k: int = DEFAULT_RAG_K,
    mode: str = DEFAULT_RAG_MODE,
    timeout: float = DEFAULT_RAG_TIMEOUT,
    excerpt_chars: int = DEFAULT_EXCERPT_CHARS,
    evidence_layer: str | None = None,
    fact_hardness: str | None = None,
    source_type: str | None = None,
    index_dir: str | Path | None = None,
    require_fresh: bool = True,
) -> WikiRagResult:
    """Run the KB hybrid retriever for ``query`` and return candidate wiki pages.

    Any unavailability (no wiki path / no rag_index.py / no built index / timeout /
    non-zero exit / unparsable JSON) sets ``warning`` and returns ``ok=False`` so
    the caller can skip the W source without breaking S/G/R.

    ``require_fresh`` (default True) is the *formal* fail-closed contract: 命中若非
    fresh（stale/unknown）一律在返回前丢弃，绝不进入 res.hits / LLM 证据；若过滤后没有
    fresh 命中则 ok=False，只留降级/不可用告警——RAG 失效可让整体回答降级，但过期/未知
    命中不得混进证据。显式探索模式 ``require_fresh=False`` 才保留 stale/unknown（标记
    degraded + 告警），且不得被称作 strict。
    """
    res = WikiRagResult()
    tel = res.telemetry
    tel.mode = str(mode)
    tel.recall_desc = _MODE_RECALL_DESC.get(str(mode), "")
    tel.k = int(k)
    tel.timeout_seconds = float(timeout)
    if timeout <= 0:
        res.warning = "wiki-rag 可用时间已耗尽，已跳过"
        tel.status = "timeout"
        tel.warning = res.warning
        return res
    if not kb_wiki:
        res.warning = "wiki-rag 需要知识库 wiki 路径 (--kb-wiki / KNOWLEDGE_WIKI)"
        tel.status = "skipped"
        tel.warning = res.warning
        return res
    root = kb_root(kb_wiki)
    script = root / RAG_SCRIPT_REL
    if not script.exists():
        res.warning = f"wiki-rag 未接入：找不到 {script}"
        tel.status = "skipped"
        tel.warning = res.warning
        return res
    # 选索引目录：默认走 _resolve_index_dir（RAG_INDEX_DIR env 或 .rag_index）；
    # 全文版经 index_dir 指向 .rag_index_full。若指定索引缺失则回退默认索引，
    # 避免 W 源在只装了结构版索引的机器上被静默丢弃。
    default_index = _resolve_index_dir(root)
    chosen = default_index
    requested: Path | None = None
    if index_dir is not None:
        cand = Path(index_dir).expanduser()
        if not cand.is_absolute():
            cand = root / cand
        requested = cand
        if cand.exists():
            chosen = cand
        elif default_index.exists():
            res.warning = f"wiki-rag 请求索引 {cand.name} 不存在，已回退默认索引 {default_index.name}"
            tel.degraded = True
        else:
            chosen = cand  # 都不存在 → 落到下方缺失索引告警
    res.index_dir = str(chosen)
    tel.index_dir = str(chosen)
    tel.index_kind = _index_kind(chosen)
    if requested is not None:
        tel.requested_index_dir = str(requested)
    if not chosen.exists():
        res.warning = (
            f"wiki-rag 未接入：向量索引不存在 {chosen}"
            "（先在知识库仓跑 scripts/rag_index.py build 或 fetch_rag_index.py）"
        )
        tel.status = "skipped"
        tel.warning = res.warning
        return res

    rag_python = _resolve_rag_python(root)
    cmd = [rag_python, str(script), "query", str(query), "--k", str(k), "--mode", str(mode), "--json"]
    filters = []
    if evidence_layer:
        cmd.extend(["--evidence-layer", evidence_layer])
        filters.append(f"evidence_layer={evidence_layer}")
    if fact_hardness:
        cmd.extend(["--fact-hardness", fact_hardness])
        filters.append(f"fact_hardness={fact_hardness}")
    if source_type:
        cmd.extend(["--source-type", source_type])
        filters.append(f"source_type={source_type}")
    if evidence_layer:
        tel.filters["evidence_layer"] = evidence_layer
    if fact_hardness:
        tel.filters["fact_hardness"] = fact_hardness
    if source_type:
        tel.filters["source_type"] = source_type
    filter_note = f" filters={','.join(filters)}" if filters else ""
    res.command = f"rag_index.py query <q> --k {k} --mode {mode}{filter_note} --json"
    res.citation_source = f"knowledge-base · rag_index.py query --mode {mode}{filter_note}（匹配 chunk 证据）"
    env = dict(os.environ)
    env["RAG_INDEX_DIR"] = str(chosen)
    if str(mode).casefold() in {"dense", "hybrid", "rerank"}:
        tel.dense_initializations = 1
    _t0 = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(root), env=env)
    except subprocess.TimeoutExpired:
        res.warning = f"wiki-rag 超时(>{timeout}s)，已跳过"
        tel.latency_ms = int((time.monotonic() - _t0) * 1000)
        tel.status = "timeout"
        tel.warning = res.warning
        return res
    except Exception as exc:  # pragma: no cover - defensive
        res.warning = f"wiki-rag 调用失败: {exc}"
        tel.status = "error"
        tel.warning = res.warning
        return res
    tel.latency_ms = int((time.monotonic() - _t0) * 1000)
    if proc.returncode != 0:
        res.warning = f"wiki-rag 退出码 {proc.returncode}: {(proc.stderr or '').strip()[:160]}"
        tel.status = "error"
        tel.warning = res.warning
        return res
    warnings = [res.warning] if res.warning else []
    stderr_warning = re.sub(r"\s+", " ", (proc.stderr or "")).strip()
    if stderr_warning:
        warnings.append(stderr_warning[:500])

    try:
        raw = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        res.warning = f"wiki-rag 输出非 JSON: {exc}"
        tel.status = "error"
        tel.warning = res.warning
        return res
    if not isinstance(raw, list):
        res.warning = "wiki-rag 输出格式异常（期望 PageHit 列表）"
        tel.status = "error"
        tel.warning = res.warning
        return res

    hits: list[WikiHit] = []
    rejected_hits = 0
    expected_revision = ""
    for item in raw:
        if not isinstance(item, dict):
            continue
        rel = str(item.get("file_path") or "")
        excerpt = _matched_excerpt(item, excerpt_chars)
        chunk_id = str(item.get("best_chunk_id") or "")
        content_hash = str(item.get("content_hash") or "")
        revision = str(item.get("index_source_revision") or "")
        freshness = str(item.get("index_freshness") or "")
        if not rel or not excerpt or not chunk_id or not content_hash or not revision or not freshness:
            rejected_hits += 1
            continue
        if freshness not in {"fresh", "stale", "unknown"}:
            rejected_hits += 1
            continue
        if expected_revision and revision != expected_revision:
            rejected_hits += 1
            continue
        expected_revision = expected_revision or revision
        hits.append(
            WikiHit(
                page_id=str(item.get("page_id") or ""),
                file_path=rel,
                title=str(item.get("title") or item.get("page_id") or "(无标题)"),
                score=float(item.get("score") or 0.0),
                excerpt=excerpt,
                best_chunk_id=chunk_id,
                section=str(item.get("section") or ""),
                content_hash=content_hash,
                index_built_at=str(item.get("index_built_at") or ""),
                index_source_revision=revision,
                index_freshness=freshness,
                evidence_layer=str(item.get("evidence_layer") or ""),
                fact_hardness=str(item.get("fact_hardness") or ""),
                source_type=str(item.get("source_type") or ""),
                via_neighbor=bool(item.get("via_neighbor")),
            )
        )
    if rejected_hits:
        warnings.append(f"wiki-rag 丢弃 {rejected_hits} 条缺少 chunk/hash/快照绑定或快照不一致的命中")
    if hits:
        # 在 strict freshness 过滤前留下索引快照状态；否则 stale /
        # unknown 命中被丢弃后，上层闭环会将缺失新鲜度误判为可继续。
        tel.index_built_at = hits[0].index_built_at
        tel.index_source_revision = hits[0].index_source_revision
        raw_freshness = {hit.index_freshness for hit in hits}
        # 混合批次若仍有 fresh 命中，strict 过滤后可以安全继续；
        # 只有 stale/unknown 时则必须把非 fresh 状态透传给闭环并停止。
        tel.index_freshness = (
            "fresh" if "fresh" in raw_freshness else hits[0].index_freshness
        )
    non_fresh_hits = [hit for hit in hits if hit.index_freshness != "fresh"]
    if require_fresh:
        # formal 契约：过期/未知命中一律丢弃，绝不进入 res.hits / LLM 证据。
        if non_fresh_hits:
            tel.degraded = True
            states = ",".join(sorted({hit.index_freshness for hit in non_fresh_hits}))
            warnings.append(
                f"wiki-rag 丢弃 {len(non_fresh_hits)} 条非 fresh 命中（新鲜度={states}）；"
                "formal 证据要求 fresh，过期/未知命中不进入证据"
            )
        hits = [hit for hit in hits if hit.index_freshness == "fresh"]
    else:
        # 显式探索(降级)模式：保留 stale/unknown，但标记 degraded 并告警。
        if non_fresh_hits:
            tel.degraded = True
            states = ",".join(sorted({hit.index_freshness for hit in hits}))
            warnings.append(f"wiki-rag 索引新鲜度={states}，探索模式保留降级证据")
    res.warning = "；".join(dict.fromkeys(warning for warning in warnings if warning))
    res.hits = hits
    res.ok = bool(hits)
    tel.hit_count = len(hits)
    tel.neighbor_hits = sum(1 for h in hits if h.via_neighbor)
    if hits:
        tel.index_built_at = hits[0].index_built_at
        tel.index_source_revision = hits[0].index_source_revision
        tel.index_freshness = hits[0].index_freshness
        scores = [h.score for h in hits]
        tel.score_max = max(scores)
        tel.score_min = min(scores)
        tel.score_mean = sum(scores) / len(scores)
        tel.status = "ok"
        tel.warning = res.warning  # 可能携带索引降级提示
    else:
        res.warning = "；".join(filter(None, [res.warning, "wiki-rag 无可用 chunk 命中"]))
        tel.status = "empty"
        tel.warning = res.warning
    return res
