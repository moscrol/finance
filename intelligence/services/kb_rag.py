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
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from intelligence.services import rag_worker
from intelligence.services.kb_index_hygiene import fetch_k, sanitize_hits
from intelligence.services.kb_slot_rerank import allocate_topk_slots
from intelligence.services.kb_window_reexcerpt import reexcerpt_hits

# rag_index.py lives at <KB repo root>/scripts/rag_index.py; the KB repo root is
# the parent of the wiki root (KnowledgeAdapter.resolved_wiki_root.parent).
RAG_SCRIPT_REL = Path("scripts") / "rag_index.py"
DEFAULT_RAG_TIMEOUT = 90
DEFAULT_RAG_K = 6
DEFAULT_RAG_MODE = "hybrid"
HYBRID_MIN_REMAINING_SECONDS = 15.0
REMAINING_BUDGET_FALLBACK = "remaining_budget"
DEFAULT_EXCERPT_CHARS = 200
DEFAULT_LLM_EVIDENCE_CHARS = 1200
DEFAULT_LLM_EVIDENCE_TOTAL_CHARS = 4800
EVIDENCE_BUDGET_EXHAUSTED = "（本条仅保留引用定位）"

# 退出码本身不可操作。检索器把真正的原因写在 stderr，丢掉它等于让每次排查都从
# 零开始——实测有一批「退出码 1」事后完全无法归因，因为原因没被保留。
# 这里只放行已知可操作的模式：不外泄任意 stderr（可能带查询原文、路径、traceback）。
_STDERR_REASON_MAX_CHARS = 220
# 只匹配「异常类型名: 」开头，且类型名必须是合法标识符——避免把任意 stderr
# 首行当成异常放行。
_WORKER_EXC_RE = re.compile(r"^(?P<exc>[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Timeout|Interrupt)):\s")
_RAG_REMEDIES: tuple[tuple[str, str], ...] = (
    # 索引新鲜度守卫
    (
        "working-tree changes",
        "知识库有未提交改动导致索引与源不一致；提交后 post-commit hook 会自动重建"
        "（单跑 rag update 不够，守卫要求源已提交）",
    ),
    ("indexed source changed in git", "索引落后于已提交内容；在知识库仓跑 rag update"),
    ("built from dirty source", "索引是在脏工作区上建的；提交后重建"),
    ("age=", "索引超龄；在知识库仓跑 rag update"),
    # 网络/HF Hub：模型已缓存时这类失败纯属无谓，靠 HF_HUB_OFFLINE=1 消除
    ("429", "HuggingFace Hub 限流；本进程已默认 HF_HUB_OFFLINE=1，若被显式关掉请改回"),
    ("Too Many Requests", "HuggingFace Hub 限流；确认 HF_HUB_OFFLINE 未被设成 0"),
    ("RateLimit", "上游限流；确认 HF_HUB_OFFLINE 未被设成 0"),
    ("huggingface.co", "访问 HuggingFace Hub 失败；模型已缓存时设 HF_HUB_OFFLINE=1 可完全绕开"),
    ("ConnectionError", "网络不可达；模型已缓存时设 HF_HUB_OFFLINE=1 可完全绕开"),
    ("Max retries exceeded", "网络重试耗尽；模型已缓存时设 HF_HUB_OFFLINE=1 可完全绕开"),
)


def _stderr_reason(stderr: str | None) -> str:
    """命中已知可操作模式时返回「原因 + 补救动作」，否则空串（不外泄任意 stderr）。"""
    text = re.sub(r"\s+", " ", str(stderr or "")).strip()
    if not text:
        return ""
    for marker, remedy in _RAG_REMEDIES:
        if marker in text:
            return f"检索器失败（{marker}）｜补救：{remedy}"[:_STDERR_REASON_MAX_CHARS]
    return ""


def _stderr_diagnostic(stderr: str | None) -> str:
    """只给遥测用的异常类型名；**不进 res.warning**（那条会渲染给用户看）。

    常驻 worker（``scripts/rag_query_worker.py``）在 ``main()`` 抛异常时上报
    ``returncode=1`` + ``stderr="ExcType: message"``。类型名不含查询原文、路径或
    traceback，是「退出码 1」和可定位根因之间的唯一线索——2026-08-01 那 8 次
    知识库检索失败之所以事后完全无法归因，就是因为连类型都没留下。

    message 仍然不外泄；用户可见文案由 :func:`_stderr_reason` 的白名单决定。
    """
    text = re.sub(r"\s+", " ", str(stderr or "")).strip()
    if not text:
        return ""
    exc = _WORKER_EXC_RE.match(text)
    return f"exc={exc.group('exc')}" if exc else ""


REQUIRED_QUERY_OPTIONS = ("--json", "--k", "--mode")
OPTIONAL_QUERY_OPTIONS = (
    "--evidence-chars",
    "--evidence-layer",
    "--fact-hardness",
    "--source-type",
)

CITATION_PREFIX = "W"
_STDERR_REASON_MAX_CHARS = 400
# 索引新鲜度守卫的 fail-closed 文案 -> 可执行的补救动作。守卫本身是对的（索引与
# 源不一致时拒绝把召回当证据），问题在于工作台原先只把它显示成"退出码 3"。
_RAG_REMEDIES: tuple[tuple[str, str], ...] = (
    (
        "working-tree changes",
        "知识库有未提交改动导致索引与源不一致；提交后 post-commit hook 会自动重建"
        "（单跑 rag update 不够，守卫要求源已提交）",
    ),
    ("indexed source changed in git", "索引落后于已提交内容；在知识库仓跑 rag update"),
    ("built from dirty source", "索引是在脏工作区上建的；提交后重建"),
    ("age=", "索引超龄；在知识库仓跑 rag update"),
)


def _stderr_reason(stderr: str | None) -> str:
    """只在 stderr 命中已知的可操作模式时返回原因 + 补救动作，否则返回空串。

    **不泄露任意 stderr**：那可能带查询原文、路径或 traceback，且对用户没有
    操作价值（见 test_unrelated_retriever_error_does_not_fall_back——不外泄是
    有意的设计）。这里只放行索引新鲜度守卫那几条：它们既是最高频的失败原因，
    又能直接对应一个明确动作。工作台原先把它们统一显示成"退出码 3"，等于把
    唯一可操作的信息藏了起来。
    """
    text = re.sub(r"\s+", " ", str(stderr or "")).strip()
    if not text:
        return ""
    for marker, remedy in _RAG_REMEDIES:
        if marker in text:
            return f"索引不可用作证据（{marker}）｜补救：{remedy}"[
                :_STDERR_REASON_MAX_CHARS
            ]
    return ""


_LEGACY_QUERY_OPTIONS: dict[str, frozenset[str]] = {}
# CLI 拒收时可以安全丢弃并重试的查询选项。丢掉它们只降低精度（过滤失效、
# 证据文本预算变短），不会让召回结果变错；因此宁可退化也不要返回空集。
_DROPPABLE_QUERY_OPTIONS: tuple[str, ...] = (
    "--evidence-chars",
    "--evidence-layer",
    "--fact-hardness",
    "--source-type",
    "--stale-policy",
)
# 索引过期时的策略。CLI 默认是 fail（退出码 3、零结果），那是**代码仓**的假设：
# 提交之间工作区是干净的。知识库是**内容仓**，用户每天 ingest 概念和实体，
# 工作区常态就是脏的——实测 wiki/sources 与 wiki/synthesis 有 26 个未提交文件时，
# 每一次检索都硬失败，且同一根因在 degrades 里重复计 4 次，占全部降级事件的 46%。
# 代价不对称：索引晚两天 vs 完全没有检索，显然前者好得多。降级本身仍会经
# stderr 的 WARNING 进 degrades，可观测性不丢。
_STALE_POLICY = os.environ.get("KB_RAG_STALE_POLICY", "warn").strip().lower()
_DENSE_UNAVAILABLE_UNTIL: dict[str, float] = {}
_RESULT_CACHE: OrderedDict[tuple[object, ...], tuple[float, WikiRagResult]] = (
    OrderedDict()
)
_RESULT_CACHE_LOCK = Lock()
_RESULT_CACHE_MAX_ENTRIES = 128
_RESULT_CACHE_TTL_SECONDS = 300.0
_RESULT_CACHE_EMPTY_TTL_SECONDS = 30.0
_DENSE_FAILURE_TTL_SECONDS = 600.0

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
    llm_evidence: str = ""
    display_excerpt: str = ""
    best_chunk_id: str = ""
    evidence_chunk_ids: tuple[str, ...] = ()
    evidence_query_terms: tuple[str, ...] = ()
    evidence_char_budget: int = 0
    section: str = ""
    content_hash: str = ""
    index_built_at: str = ""
    index_source_revision: str = ""
    index_freshness: str = ""
    evidence_layer: str = ""
    fact_hardness: str = ""
    source_type: str = ""
    via_neighbor: bool = False
    source_date: str = ""
    reexcerpted: bool = False


# 检索方式 → 人类可读的“用了什么召回”说明（教学 / 可观测用）。
_MODE_RECALL_DESC = {
    "hybrid": "BM25 关键词 + 稠密向量(BGE-m3) + RRF 融合",
    "rerank": "BM25 + 稠密向量 + rerank 二次重排",
    "dense": "稠密向量(BGE-m3)",
    "bm25": "BM25 关键词",
}

_DENSE_MODES = frozenset({"hybrid", "dense", "rerank"})


def select_mode_for_remaining(
    requested: str,
    remaining_seconds: float,
) -> tuple[str, str | None]:
    """Map remaining wall-clock seconds to a retrieval mode. No I/O."""
    requested_mode = str(requested or "")
    if (
        requested_mode in _DENSE_MODES
        and float(remaining_seconds) < HYBRID_MIN_REMAINING_SECONDS
    ):
        return "bm25", REMAINING_BUDGET_FALLBACK
    return requested_mode, None


_DENSE_DEPENDENCY_FAILURES = (
    "flagembedding",
    "bgem3flagmodel",
    "no module named 'sentence_transformers'",
    'no module named "sentence_transformers"',
    "no module named 'torch'",
    'no module named "torch"',
)


def _dense_dependency_failure(stderr: str) -> bool:
    normalized = str(stderr or "").casefold()
    return any(marker in normalized for marker in _DENSE_DEPENDENCY_FAILURES)


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
    requested_mode: str = ""
    effective_mode: str = ""
    fallback_reason: str = ""
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
    index_built_at: str = ""
    index_source_revision: str = ""
    index_freshness: str = ""
    warning: str = ""
    display_excerpt_chars: int = 0
    llm_evidence_chars: int = 0
    llm_evidence_total_chars: int = 0
    query_protocol: str = "current"
    unsupported_options: tuple[str, ...] = ()
    cache_hit: bool = False
    cache_age_ms: int | None = None
    index_fingerprint: str = ""
    # 本次查询是否顺带加载了 BGE-m3 与稠密索引（常驻 worker 的冷启动）。
    # 实测冷 60.1s / 热 4-6s，差 10 倍以上，所以冷查询的耗时不能当成后续查询的
    # 成本样本——下游预算据此决定要不要采纳这次观测。
    model_loaded: bool = False
    # V9a：指针页丢弃数。None = 本条遥测未跑重摘录（历史 run 报不可判，不报 0）。
    pointer_dropped: int | None = None
    # V9b：结构邻页代表块排后数。None = 未跑槽位重排（历史 run 报不可判，不报 0）。
    structural_neighbor_demoted: int | None = None

    def summary_line(self) -> str:
        """一行可观测摘要，供回答 / 日志展示。"""
        kind_cn = {"structured": "结构版索引", "full": "全文版索引", "custom": "自定义索引"}.get(
            self.index_kind, self.index_kind or "?"
        )
        effective = self.effective_mode or self.mode or "?"
        recall = self.recall_desc or effective
        parts = [f"检索方式={effective}（{recall}）", f"索引={kind_cn}", f"k={self.k}"]
        if self.requested_mode and self.requested_mode != effective:
            parts.append(f"请求方式={self.requested_mode}")
        if self.fallback_reason:
            parts.append(f"降级原因={self.fallback_reason}")
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
        if self.cache_hit:
            parts.append(f"缓存命中={self.cache_age_ms or 0}ms")
        if self.degraded:
            parts.append("⚠检索降级")
        if self.index_freshness:
            parts.append(f"新鲜度={self.index_freshness}")
        if self.index_built_at:
            parts.append(f"构建={self.index_built_at}")
        if self.llm_evidence_chars:
            parts.append(
                f"LLM证据预算={self.llm_evidence_chars}字/条，总{self.llm_evidence_total_chars}字"
            )
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


@dataclass(frozen=True)
class RagCliProbe:
    available: bool
    query_protocol_compatible: bool
    supported_options: tuple[str, ...] = ()
    missing_required_options: tuple[str, ...] = ()
    missing_optional_options: tuple[str, ...] = ()
    warning: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "query_protocol_compatible": self.query_protocol_compatible,
            "supported_options": list(self.supported_options),
            "missing_required_options": list(self.missing_required_options),
            "missing_optional_options": list(self.missing_optional_options),
            "warning": self.warning,
        }


def kb_root(kb_wiki: str | Path) -> Path:
    """KB repo root = parent of the wiki root (mirrors theme_modules._kb_root)."""
    return Path(kb_wiki).expanduser().resolve().parent


def _resolve_index_dir(root: Path) -> Path:
    env = os.environ.get("VECTOR_INDEX_DIR") or os.environ.get("RAG_INDEX_DIR")
    if env:
        return Path(env).expanduser()
    return root / ".rag_index"


def _index_fingerprint(index_dir: Path) -> str:
    parts: list[str] = []
    for name in ("meta.json", "chunks.jsonl", "bm25.pkl.gz", "dense.npy"):
        path = index_dir / name
        try:
            stat = path.stat()
        except OSError:
            continue
        parts.append(f"{name}:{stat.st_size}:{stat.st_mtime_ns}")
    return "|".join(parts) or f"{index_dir}:missing"


def _cache_get(
    key: tuple[object, ...],
    *,
    require_fresh: bool,
) -> WikiRagResult | None:
    now = time.monotonic()
    with _RESULT_CACHE_LOCK:
        cached = _RESULT_CACHE.get(key)
        if cached is None:
            return None
        stored_at, result = cached
        ttl = (
            _RESULT_CACHE_TTL_SECONDS
            if result.ok
            else _RESULT_CACHE_EMPTY_TTL_SECONDS
        )
        if now - stored_at > ttl:
            _RESULT_CACHE.pop(key, None)
            return None
        if require_fresh and any(
            hit.index_freshness != "fresh" for hit in result.hits
        ):
            _RESULT_CACHE.pop(key, None)
            return None
        _RESULT_CACHE.move_to_end(key)
        cloned = deepcopy(result)
    cloned.telemetry.cache_hit = True
    cloned.telemetry.cache_age_ms = int((now - stored_at) * 1000)
    cloned.telemetry.latency_ms = 0
    return cloned


def _cache_put(
    key: tuple[object, ...],
    result: WikiRagResult,
) -> WikiRagResult:
    if result.telemetry.status not in {"ok", "empty"}:
        return result
    with _RESULT_CACHE_LOCK:
        _RESULT_CACHE[key] = (time.monotonic(), deepcopy(result))
        _RESULT_CACHE.move_to_end(key)
        while len(_RESULT_CACHE) > _RESULT_CACHE_MAX_ENTRIES:
            _RESULT_CACHE.popitem(last=False)
    return result


def clear_result_cache() -> None:
    with _RESULT_CACHE_LOCK:
        _RESULT_CACHE.clear()
    _DENSE_UNAVAILABLE_UNTIL.clear()


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


def prewarm(
    kb_wiki: str | Path | None,
    *,
    timeout: float = 90,
) -> dict[str, object]:
    """Load the production hybrid retriever before serving user requests."""
    if not rag_worker.enabled():
        return rag_worker.status()
    if not kb_wiki:
        raise ValueError("knowledge wiki is required for RAG prewarm")
    root = kb_root(kb_wiki)
    script = root / RAG_SCRIPT_REL
    index_dir = _resolve_index_dir(root)
    if not script.is_file():
        raise FileNotFoundError(script)
    if not index_dir.is_dir():
        raise FileNotFoundError(index_dir)
    # 预热必须和普通查询用同一个 stale 口径（见 `_run_rag_cli` 里同名分支）。
    # 漏掉它不是「少一个参数」而是换了一套失败语义：KB 侧 CLI 的默认是
    # `fail`，而 `_STALE_POLICY` 默认 `warn`——索引一旦过期，普通查询照常降级
    # 返回结果，预热却硬失败，于是整个服务报 not_ready。同一个索引状态，两条
    # 路给出「可用」和「完全不可用」两个答案，且更严的那条是没人显式选过的。
    prewarm_argv = [
        "query",
        "Workbench RAG 预热",
        "--k",
        "1",
        "--mode",
        DEFAULT_RAG_MODE,
    ]
    if _STALE_POLICY:
        prewarm_argv.extend(["--stale-policy", _STALE_POLICY])
    prewarm_argv.append("--json")
    rag_worker.prewarm(
        python=_resolve_rag_python(root),
        kb_root=root,
        index_dir=index_dir,
        argv=prewarm_argv,
        timeout=timeout,
    )
    return rag_worker.status()


def probe_rag_cli(
    kb_wiki: str | Path | None,
    *,
    timeout: int = 5,
) -> RagCliProbe:
    if not kb_wiki:
        return RagCliProbe(
            available=False,
            query_protocol_compatible=False,
            warning="未配置知识库 wiki 路径",
        )
    root = kb_root(kb_wiki)
    script = root / RAG_SCRIPT_REL
    if not script.is_file():
        return RagCliProbe(
            available=False,
            query_protocol_compatible=False,
            warning="RAG CLI 脚本不存在",
        )
    try:
        proc = subprocess.run(
            [_resolve_rag_python(root), str(script), "query", "--help"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(root),
        )
    except subprocess.TimeoutExpired:
        return RagCliProbe(
            available=False,
            query_protocol_compatible=False,
            warning="RAG CLI 能力探测超时",
        )
    except Exception:
        return RagCliProbe(
            available=False,
            query_protocol_compatible=False,
            warning="RAG CLI 能力探测失败",
        )
    if proc.returncode != 0:
        return RagCliProbe(
            available=False,
            query_protocol_compatible=False,
            warning=f"RAG CLI 能力探测退出码 {proc.returncode}",
        )
    help_text = f"{proc.stdout}\n{proc.stderr}"
    known_options = (*REQUIRED_QUERY_OPTIONS, *OPTIONAL_QUERY_OPTIONS)
    supported = tuple(option for option in known_options if option in help_text)
    missing_required = tuple(
        option for option in REQUIRED_QUERY_OPTIONS if option not in supported
    )
    missing_optional = tuple(
        option for option in OPTIONAL_QUERY_OPTIONS if option not in supported
    )
    warning = ""
    if missing_required:
        warning = "RAG CLI 缺少必要 query 参数"
    elif missing_optional:
        warning = "RAG CLI 使用 legacy query 协议"
    return RagCliProbe(
        available=True,
        query_protocol_compatible=not missing_required,
        supported_options=supported,
        missing_required_options=missing_required,
        missing_optional_options=missing_optional,
        warning=warning,
    )


def _without_option(cmd: list[str], option: str) -> list[str]:
    updated = list(cmd)
    if option not in updated:
        return updated
    index = updated.index(option)
    del updated[index : index + 2]
    return updated


def _unsupported_option(stderr: str, option: str) -> bool:
    compact = re.sub(r"\s+", " ", stderr or "").strip()
    return "unrecognized arguments:" in compact and option in compact


def _compact_text(value: object, max_chars: int | None = None) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if max_chars is not None:
        return text[:max_chars]
    return text


def _matched_excerpt(item: dict, max_chars: int) -> str:
    text = item.get("display_excerpt") or item.get("snippet") or item.get("evidence_text") or ""
    return _compact_text(text, max_chars)


def _matched_llm_evidence(item: dict, max_chars: int) -> str:
    text = item.get("llm_evidence_text") or item.get("evidence_text") or item.get("snippet") or ""
    return _compact_text(text, max_chars)


def _tuple_of_strings(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item) for item in value if str(item))
    return ()


def evidence_budget_for_query(
    query: str,
    *,
    mode: str = DEFAULT_RAG_MODE,
    index_kind: str = "",
) -> tuple[int, int]:
    q = str(query or "")
    high_precision_terms = (
        "订单", "合同", "中标", "收入", "营收", "兑现", "公告", "互动",
        "认证", "量产", "出货", "客户", "金额", "生效", "条件", "L3", "l3",
    )
    broad_terms = ("深挖", "原文", "全文", "详细", "为什么", "如何", "证据")
    quick_terms = ("快速", "速查", "概览", "简单")
    per_hit = DEFAULT_LLM_EVIDENCE_CHARS
    high_precision = any(term in q for term in high_precision_terms)
    broad = any(term in q for term in broad_terms)
    quick = any(term in q for term in quick_terms)
    if high_precision:
        per_hit = 1600
    elif broad or str(mode).lower() == "rerank" or index_kind == "full":
        per_hit = 1400
    elif quick:
        per_hit = 800
    total = max(DEFAULT_LLM_EVIDENCE_TOTAL_CHARS, per_hit * 4)
    return per_hit, min(total, 8000)


def apply_total_llm_budget(hits: list[WikiHit], total_chars: int) -> None:
    remaining = max(total_chars, 0)
    for hit in hits:
        text = hit.llm_evidence or hit.excerpt
        if remaining <= 0:
            hit.llm_evidence = EVIDENCE_BUDGET_EXHAUSTED
            continue
        if len(text) > remaining:
            hit.llm_evidence = text[: max(0, remaining - 1)].rstrip() + "…"
            remaining = 0
        else:
            hit.llm_evidence = text
            remaining -= len(text)


def _hit_evidence_limit(item: dict, base_chars: int) -> int:
    limit = max(base_chars, 200)
    if bool(item.get("via_neighbor")):
        limit = max(400, limit // 2)
    evidence_layer = str(item.get("evidence_layer") or "").upper()
    source_type = str(item.get("source_type") or "").lower()
    if evidence_layer.startswith("L3") or source_type in {
        "official",
        "announcement",
        "official_disclosure",
    }:
        limit = min(max(limit, int(base_chars * 1.25)), 2000)
    return limit


def retrieve(
    query: str,
    kb_wiki: str | Path | None,
    k: int = DEFAULT_RAG_K,
    mode: str = DEFAULT_RAG_MODE,
    timeout: int = DEFAULT_RAG_TIMEOUT,
    excerpt_chars: int = DEFAULT_EXCERPT_CHARS,
    llm_evidence_chars: int | None = None,
    llm_evidence_total_chars: int | None = None,
    budget_query: str | None = None,
    evidence_layer: str | None = None,
    fact_hardness: str | None = None,
    source_type: str | None = None,
    index_dir: str | Path | None = None,
    code_root: str | Path | None = None,
    python_executable: str | Path | None = None,
    worker_enabled: bool | None = None,
    require_fresh: bool = True,
    cache_scope: str | None = None,
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
    requested_mode = str(mode)
    tel.requested_mode = requested_mode
    planned_mode, budget_reason = select_mode_for_remaining(
        requested_mode, float(timeout)
    )
    tel.effective_mode = planned_mode
    tel.mode = planned_mode
    tel.recall_desc = _MODE_RECALL_DESC.get(planned_mode, "")
    if budget_reason:
        tel.fallback_reason = budget_reason
        tel.degraded = True
    requested_k = int(k)
    tel.k = requested_k
    query_k = fetch_k(requested_k)
    tel.display_excerpt_chars = int(excerpt_chars)
    if not kb_wiki:
        res.warning = "wiki-rag 需要知识库 wiki 路径 (--kb-wiki / KNOWLEDGE_WIKI)"
        tel.status = "skipped"
        tel.warning = res.warning
        return res
    wiki_root = Path(kb_wiki).expanduser().resolve()
    root = kb_root(wiki_root)
    runtime_root = (
        Path(code_root).expanduser().resolve()
        if code_root is not None
        else root
    )
    script = runtime_root / RAG_SCRIPT_REL
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
    tel.index_fingerprint = _index_fingerprint(chosen)
    if llm_evidence_chars is None or llm_evidence_total_chars is None:
        dynamic_chars, dynamic_total = evidence_budget_for_query(
            budget_query or query,
            mode=str(mode),
            index_kind=tel.index_kind,
        )
        if llm_evidence_chars is None:
            llm_evidence_chars = dynamic_chars
        if llm_evidence_total_chars is None:
            llm_evidence_total_chars = dynamic_total
    tel.llm_evidence_chars = int(llm_evidence_chars)
    tel.llm_evidence_total_chars = int(llm_evidence_total_chars)
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

    rag_python = (
        str(Path(python_executable).expanduser())
        if python_executable is not None
        else _resolve_rag_python(runtime_root)
    )
    generation_evidence_chars = min(
        max(int(llm_evidence_chars), int(llm_evidence_chars * 1.25)),
        2000,
    )
    cache_key = (
        cache_scope,
        str(root),
        str(script),
        str(chosen),
        tel.index_fingerprint,
        query,
        requested_k,
        requested_mode,
        int(excerpt_chars),
        int(llm_evidence_chars),
        int(llm_evidence_total_chars),
        budget_query or "",
        evidence_layer or "",
        fact_hardness or "",
        source_type or "",
        bool(require_fresh),
    )
    if cache_scope:
        cached = _cache_get(cache_key, require_fresh=require_fresh)
        if cached is not None:
            return cached
    legacy_options = _LEGACY_QUERY_OPTIONS.get(str(script), frozenset())
    effective_mode = planned_mode
    dense_disabled_until = _DENSE_UNAVAILABLE_UNTIL.get(str(script), 0.0)
    if (
        effective_mode in _DENSE_MODES
        and dense_disabled_until
        and dense_disabled_until > time.monotonic()
    ):
        effective_mode = "bm25"
        tel.mode = "bm25"
        tel.effective_mode = "bm25"
        tel.recall_desc = _MODE_RECALL_DESC["bm25"]
        if tel.fallback_reason != REMAINING_BUDGET_FALLBACK:
            tel.fallback_reason = "dense_dependency_cached_unavailable"
        tel.degraded = True
    cmd = [
        rag_python,
        str(script),
        "query",
        str(query),
        "--k",
        str(query_k),
        "--mode",
        effective_mode,
    ]
    if "--evidence-chars" not in legacy_options:
        cmd.extend(["--evidence-chars", str(generation_evidence_chars)])
    if _STALE_POLICY and "--stale-policy" not in legacy_options:
        cmd.extend(["--stale-policy", _STALE_POLICY])
    cmd.append("--json")
    # 已知被 CLI 拒收的过滤选项不再下发：否则每轮都要先失败一次才降级，
    # 白烧一次查询预算。tel.filters 仍记录请求过什么，便于对账"要过滤但没过滤"。
    filters = []
    for option, value in (
        ("--evidence-layer", evidence_layer),
        ("--fact-hardness", fact_hardness),
        ("--source-type", source_type),
    ):
        if not value:
            continue
        key = option.lstrip("-").replace("-", "_")
        tel.filters[key] = value
        if option in legacy_options:
            continue
        cmd.extend([option, value])
        filters.append(f"{key}={value}")
    filter_note = f" filters={','.join(filters)}" if filters else ""
    evidence_chars_note = (
        f" --evidence-chars {generation_evidence_chars}"
        if "--evidence-chars" in cmd
        else ""
    )
    res.command = (
        f"rag_index.py query <q> --k {query_k} --mode {effective_mode}"
        f"{evidence_chars_note}{filter_note} --json"
    )
    res.citation_source = (
        "knowledge-base · rag_index.py query "
        f"--mode {effective_mode}{filter_note}（匹配 chunk 证据）"
    )
    env = dict(os.environ)
    env["RAG_INDEX_DIR"] = str(chosen)
    env["KB_VAULT"] = str(wiki_root)
    # 检索器每次查询都会向 HuggingFace Hub 发**未认证**请求校验 bge-m3 的 30 个
    # 文件，即便本地已缓存。未认证请求有速率限制，连跑一批查询就会被限流、
    # 整条检索以退出码 1 挂掉（实测：离线 19s / 联网 21s，联网校验零收益）。
    # 索引能建起来就意味着模型已缓存，所以默认离线；留 setdefault 以便冷启动的
    # 机器用 HF_HUB_OFFLINE=0 显式打开首次下载。
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    # 静音进度条：模型加载会往 stderr 打 391 个分片的 tqdm 进度条，而 rc=0 且
    # stderr 非空会被记成一条「wiki-rag 检索器返回告警」——**每次检索都触发**。
    # 那条告警没有任何信息量，却会挤进 degrades 列表，把真告警淹掉。
    # 实测加这三个后 stderr 完全干净，于是 stderr 非空重新变回一个有意义的信号。
    env.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    env.setdefault("TRANSFORMERS_VERBOSITY", "error")
    env.setdefault("TQDM_DISABLE", "1")
    fallback_warnings: list[str] = []
    if legacy_options:
        tel.query_protocol = "legacy"
        tel.unsupported_options = tuple(sorted(legacy_options))
        tel.fallback_reason = "legacy_cli_missing_evidence_chars"
        tel.degraded = True
        fallback_warnings.append(
            "wiki-rag CLI 不支持 --evidence-chars，已使用 legacy query 协议"
        )
    _t0 = time.monotonic()
    if worker_enabled is None:
        worker_enabled = os.environ.get("RAG_WORKER_ENABLED", "0").strip().lower() not in {
            "0",
            "false",
            "off",
            "no",
        }
    try:
        if worker_enabled and not filters:
            proc = rag_worker.query(
                python=rag_python,
                kb_root=runtime_root,
                index_dir=chosen,
                argv=cmd[2:],
                timeout=float(timeout),
            )
            tel.query_protocol = "persistent_worker"
            tel.model_loaded = int(getattr(proc, "model_load_count", 0) or 0) > 0
        else:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(runtime_root),
                env=env,
            )
            # 每次都是新进程，必然重新加载模型与索引。
            tel.model_loaded = True
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        fallback_warnings.append(
            f"wiki-rag 常驻 worker 不可用（{type(exc).__name__}），已回退 CLI"
        )
        tel.degraded = True
        tel.fallback_reason = "persistent_worker_unavailable"
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=max(0.001, float(timeout) - (time.monotonic() - _t0)),
                cwd=str(runtime_root),
                env=env,
            )
        except subprocess.TimeoutExpired:
            res.warning = "wiki-rag worker 降级 CLI 后仍超时"
            tel.latency_ms = int((time.monotonic() - _t0) * 1000)
            tel.status = "timeout"
            tel.warning = res.warning
            return res
    except rag_worker.WorkerRequestAbandoned:
        # 热 worker 第一次超窗：请求放弃、进程保留，下一次查询不用等模型重载。
        res.warning = f"wiki-rag 常驻 worker 超时(>{timeout}s)，请求已放弃、worker 保留"
        tel.latency_ms = int((time.monotonic() - _t0) * 1000)
        tel.status = "timeout"
        tel.warning = res.warning
        return res
    except TimeoutError:
        res.warning = f"wiki-rag 常驻 worker 超时(>{timeout}s)，进程已终止"
        tel.latency_ms = int((time.monotonic() - _t0) * 1000)
        tel.status = "timeout"
        tel.warning = res.warning
        return res
    except subprocess.TimeoutExpired:
        res.warning = f"wiki-rag 超时(>{timeout}s)，已跳过"
        tel.latency_ms = int((time.monotonic() - _t0) * 1000)
        tel.status = "timeout"
        tel.warning = res.warning
        return res
    except Exception:  # pragma: no cover - defensive
        res.warning = "wiki-rag 调用失败"
        tel.status = "error"
        tel.warning = res.warning
        return res

    # CLI 不支持的选项一律走同一条降级路径：丢掉该选项后重试一次。
    #
    # 原先只硬编码了 --evidence-chars。实测知识库的 rag_index.py query 只支持
    # --model/--include-raw/--k/--mode/--reranker/--json/--evidence-chars/
    # --stale-policy，并不支持工作台一直在下发的三个过滤参数，于是每一次分层
    # 证据检索都以 "unrecognized arguments" rc=2 收场、返回空集，表面上只留一句
    # "检索器返回告警"。改 KB 的 CLI 属跨仓改动（未获授权），所以在工作台侧
    # 泛化这条既有降级路径：分层过滤退化为未过滤召回并如实记账，而不是什么都拿不到。
    unsupported = tuple(
        option
        for option in _DROPPABLE_QUERY_OPTIONS
        if option in cmd and _unsupported_option(proc.stderr, option)
    )
    if proc.returncode != 0 and unsupported:
        remaining = float(timeout) - (time.monotonic() - _t0)
        listed = "/".join(unsupported)
        if remaining < 1:
            tel.latency_ms = int((time.monotonic() - _t0) * 1000)
            res.warning = (
                f"wiki-rag CLI 不支持 {listed}，剩余预算不足，未执行 legacy query 回退"
            )
            tel.status = "error"
            tel.warning = res.warning
            return res
        for option in unsupported:
            cmd = _without_option(cmd, option)
        _LEGACY_QUERY_OPTIONS[str(script)] = frozenset(unsupported)
        tel.query_protocol = "legacy"
        tel.unsupported_options = unsupported
        tel.fallback_reason = "legacy_cli_missing_" + "_".join(
            option.lstrip("-").replace("-", "_") for option in unsupported
        )
        tel.degraded = True
        fallback_warnings.append(
            f"wiki-rag CLI 不支持 {listed}，已丢弃该选项后重试；"
            "分层过滤未生效，本轮召回为未过滤结果"
        )
        res.command = (
            f"rag_index.py query <q> --k {query_k} --mode {mode}{filter_note} --json"
        )
        try:
            if worker_enabled and not filters:
                proc = rag_worker.query(
                    python=rag_python,
                    kb_root=runtime_root,
                    index_dir=chosen,
                    argv=cmd[2:],
                    timeout=remaining,
                )
                tel.query_protocol = "persistent_worker_legacy"
            else:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=remaining,
                    cwd=str(runtime_root),
                    env=env,
                )
        except (subprocess.TimeoutExpired, TimeoutError):
            tel.latency_ms = int((time.monotonic() - _t0) * 1000)
            res.warning = "wiki-rag legacy query 回退超时"
            tel.status = "timeout"
            tel.warning = res.warning
            return res
        except Exception:  # pragma: no cover - defensive
            tel.latency_ms = int((time.monotonic() - _t0) * 1000)
            res.warning = "wiki-rag legacy query 回退调用失败"
            tel.status = "error"
            tel.warning = res.warning
            return res
        fallback_warnings.append(
            "wiki-rag CLI 不支持 --evidence-chars，已使用 legacy query 协议"
        )

    if (
        proc.returncode != 0
        and effective_mode in _DENSE_MODES
        and _dense_dependency_failure(proc.stderr)
    ):
        _DENSE_UNAVAILABLE_UNTIL[str(script)] = (
            _t0 + _DENSE_FAILURE_TTL_SECONDS
        )
        if tel.fallback_reason != REMAINING_BUDGET_FALLBACK:
            tel.fallback_reason = "dense_dependency_missing"
        remaining = float(timeout) - (time.monotonic() - _t0)
        if remaining < 1:
            tel.latency_ms = int((time.monotonic() - _t0) * 1000)
            res.warning = "wiki-rag dense 依赖不可用，剩余预算不足，未执行 BM25 回退"
            tel.status = "error"
            tel.warning = res.warning
            return res

        fallback_cmd = list(cmd)
        fallback_cmd[fallback_cmd.index("--mode") + 1] = "bm25"
        tel.mode = "bm25"
        tel.effective_mode = "bm25"
        tel.recall_desc = _MODE_RECALL_DESC["bm25"]
        tel.degraded = True
        res.command = (
            f"rag_index.py query <q> --k {query_k} --mode bm25"
            f"{evidence_chars_note if '--evidence-chars' in fallback_cmd else ''}"
            f"{filter_note} --json"
        )
        res.citation_source = (
            f"knowledge-base · rag_index.py query --mode bm25{filter_note}"
            "（匹配 chunk 证据；dense 不可用时回退）"
        )
        try:
            proc = subprocess.run(
                fallback_cmd,
                capture_output=True,
                text=True,
                timeout=remaining,
                cwd=str(runtime_root),
                env=env,
            )
        except subprocess.TimeoutExpired:
            tel.latency_ms = int((time.monotonic() - _t0) * 1000)
            res.warning = "wiki-rag dense 依赖不可用，BM25 回退超时"
            tel.status = "timeout"
            tel.warning = res.warning
            return res
        except Exception:  # pragma: no cover - defensive
            tel.latency_ms = int((time.monotonic() - _t0) * 1000)
            res.warning = "wiki-rag dense 依赖不可用，BM25 回退调用失败"
            tel.status = "error"
            tel.warning = res.warning
            return res
        fallback_warnings.append("wiki-rag dense 依赖不可用，已回退 BM25")

    tel.latency_ms = int((time.monotonic() - _t0) * 1000)
    if proc.returncode != 0:
        reason = _stderr_reason(proc.stderr)
        if tel.fallback_reason == "dense_dependency_missing":
            res.warning = f"wiki-rag dense 依赖不可用，BM25 回退退出码 {proc.returncode}"
        elif tel.query_protocol == "legacy":
            res.warning = f"wiki-rag legacy query 回退退出码 {proc.returncode}"
        else:
            res.warning = f"wiki-rag 检索失败（退出码 {proc.returncode}）"
        # 退出码本身不可操作。检索器把真正的原因写在 stderr——索引过期时那里
        # 明确写着是哪一类不新鲜、该跑什么命令。丢掉它等于让每次排查都从零开始。
        # （reason 已在上面的 if 链之前算过，main 侧那次重复调用去掉。）
        if reason:
            res.warning = f"{res.warning}：{reason}"
        tel.status = "error"
        # 遥测比用户文案多带一个异常类型：归因要它，用户不需要看。
        diagnostic = _stderr_diagnostic(proc.stderr)
        tel.warning = f"{res.warning}｜{diagnostic}" if diagnostic else res.warning
        return res
    warnings = [warning for warning in (res.warning, *fallback_warnings) if warning]
    if re.sub(r"\s+", " ", (proc.stderr or "")).strip():
        # rc=0 但有 stderr：保留原来的笼统措辞（不外泄任意 stderr），只在命中
        # 已知可操作模式时补一句补救动作。
        actionable = _stderr_reason(proc.stderr)
        warnings.append(
            f"wiki-rag 检索器返回告警：{actionable}"
            if actionable
            else "wiki-rag 检索器返回告警"
        )

    try:
        raw = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        res.warning = "wiki-rag 输出非 JSON"
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
        evidence_limit = _hit_evidence_limit(item, int(llm_evidence_chars))
        llm_evidence = _matched_llm_evidence(item, evidence_limit)
        chunk_id = str(item.get("best_chunk_id") or "")
        content_hash = str(item.get("content_hash") or "")
        revision = str(item.get("index_source_revision") or "")
        freshness = str(item.get("index_freshness") or "")
        if not rel or not excerpt or not llm_evidence or not chunk_id or not content_hash or not revision or not freshness:
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
                llm_evidence=llm_evidence,
                display_excerpt=excerpt,
                best_chunk_id=chunk_id,
                evidence_chunk_ids=_tuple_of_strings(item.get("evidence_chunk_ids")),
                evidence_query_terms=_tuple_of_strings(item.get("evidence_query_terms")),
                evidence_char_budget=min(
                    int(item.get("evidence_char_budget") or evidence_limit),
                    evidence_limit,
                ),
                section=str(item.get("section") or ""),
                content_hash=content_hash,
                index_built_at=str(item.get("index_built_at") or ""),
                index_source_revision=revision,
                index_freshness=freshness,
                evidence_layer=str(item.get("evidence_layer") or ""),
                fact_hardness=str(item.get("fact_hardness") or ""),
                source_type=str(item.get("source_type") or ""),
                via_neighbor=bool(item.get("via_neighbor")),
                source_date=str(item.get("source_date") or item.get("date") or ""),
            )
        )
    if rejected_hits:
        warnings.append(f"wiki-rag 丢弃 {rejected_hits} 条缺少 chunk/hash/快照绑定或快照不一致的命中")
    non_fresh_hits = [hit for hit in hits if hit.index_freshness != "fresh"]
    if require_fresh:
        # formal 契约：过期/未知命中一律丢弃，绝不进入 res.hits / LLM 证据。
        if non_fresh_hits:
            tel.degraded = True
            states = ",".join(sorted({hit.index_freshness for hit in non_fresh_hits}))
            # 光说「丢了几条、契约要求 fresh」只解释了机制，没告诉人怎么办。
            # 内容仓每天 ingest，工作区脏是常态，这条会高频出现——它必须自带动作，
            # 否则用户看到的就是「又没有证据」，而实际上证据就在那里、差一次提交。
            remedy = (
                "在知识库仓提交改动后 post-commit 会自动重建索引，届时这些证据即可进入"
                if states == "stale"
                else "先在知识库仓跑 rag update 重建索引"
            )
            warnings.append(
                f"wiki-rag 丢弃 {len(non_fresh_hits)} 条非 fresh 命中（新鲜度={states}）；"
                f"formal 证据要求 fresh，过期/未知命中不进入证据｜可恢复：{remedy}"
            )
        hits = [hit for hit in hits if hit.index_freshness == "fresh"]
    else:
        # 显式探索(降级)模式：保留 stale/unknown，但标记 degraded 并告警。
        if non_fresh_hits:
            tel.degraded = True
            states = ",".join(sorted({hit.index_freshness for hit in hits}))
            warnings.append(f"wiki-rag 索引新鲜度={states}，探索模式保留降级证据")
    hits, reexcerpt = reexcerpt_hits(hits, wiki_root=wiki_root)
    tel.pointer_dropped = reexcerpt.pointer_dropped
    hits, slot_stats = allocate_topk_slots(hits)
    tel.structural_neighbor_demoted = slot_stats.demoted
    hits = sanitize_hits(hits, k=requested_k)
    res.warning = "；".join(dict.fromkeys(warning for warning in warnings if warning))
    res.hits = hits
    apply_total_llm_budget(res.hits, int(llm_evidence_total_chars))
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
    return _cache_put(cache_key, res) if cache_scope else res

def rag_runtime_ready() -> bool:
    """kb_search 的解释器**真的能执行吗**——不是「路径字符串存在吗」。

    判据对齐**消费方的失败条件**（subprocess 能否拉起解释器），不是对齐
    「文件系统里有没有这个名字」：悬空符号链接、目录、无执行位三种情况
    ``Path.exists()`` 的答案各不相同，对 subprocess 却是同一个结果。

    2026-08-12 [实测] ``knowledge-base-private/.rag_venv`` 是指向
    ``~/知识库/.rag_venv`` 的符号链接，而那个目录已不存在。kb_search 每次 7ms 抛
    FileNotFoundError（当场复现过），被脱敏成「研究过程中出现内部错误」，
    **而 health 一直报 vector_index: true**——它只判索引目录存不存在。

    ⚠ **断裂窗口 ≤6 天，不是「一个月」**：符号链接的创建日期（07-14）不是它
    断掉的日期。索引 2026-08-06 22:20 用 bge-m3 成功建成，且当天 kb_search 还
    返回过真 ``empty``，证明那时 venv 可用。历史上 14 次 ``无命中（error）``
    集中在 07-28/29，属**另一次故障**，别和这次连成一条因果链——
    初版注释就是这么连的，已更正。
    """

    import os
    import shutil

    candidate = str(os.environ.get("KB_RAG_PYTHON") or "").strip()
    if not candidate:
        return bool(shutil.which("python3"))
    path = Path(candidate).expanduser()
    return path.is_file() and os.access(path, os.X_OK)
