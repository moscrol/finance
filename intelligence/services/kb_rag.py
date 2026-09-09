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

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections import OrderedDict
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from intelligence.services import rag_worker
from intelligence.services.kb_index_hygiene import fetch_k, sanitize_hits
from intelligence.services.kb_slot_rerank import allocate_topk_slots
from intelligence.services.kb_window_reexcerpt import (
    STRUCTURAL_SECTIONS,
    reexcerpt_hits,
    resolve_wiki_page,
    split_sections,
)
from intelligence.services.tool_result_budget import MAX_EVIDENCE_DETAIL_CHARS

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

# ---------------------------------------------------------------------------
# 深读（能力升级任务包 02）：找到页以后继续读到能解题。
#
# 为什么放在这一层而不是新工具：Engine A 的工具参数面由注册表钉死（kb_search 只收
# ``query``），知识库侧 ``rag/agent.py::get_page`` 没接进金融侧，常驻 worker 协议只跑
# ``query``。V9a（``kb_window_reexcerpt``）已经在这一层按 ``file_path`` 直接读源页做
# 重摘录，所以「读整节、表头随切片、列章节目录」就地做：不加工具、不改知识库侧、
# 不碰注册表。
#
# 为什么按 ``MAX_EVIDENCE_DETAIL_CHARS`` 切段：模型看到的是 ``tool_result_budget``
# 投影后的副本，每条证据 ``detail`` 超过它就被截，且对模型声明「被截掉的原文没有工具
# 可以取回」。命中块加相邻块 1200 字送达，模型只见前 240 字——这就是「找到了却没读到
# 答案」的第一损失点。段落级证据把整节装进模型真能看见的形状里：不是加大上下文，
# 是把已经取回却看不见的字变成看得见，并且每段可独立引用（E 号）。
# ---------------------------------------------------------------------------
DEEP_READ_ITEM_CHARS = MAX_EVIDENCE_DETAIL_CHARS
DEEP_READ_PER_HIT_CHARS = 1200
DEEP_READ_TOTAL_CHARS = 3000
DEEP_READ_TOTAL_ENV = "KB_DEEP_READ_TOTAL_CHARS"
# 只深读排前的几页：bm25 的第 4–6 名常是词面撞上的无关页（实测「沃格光电 2024 盈利」
# 拉出湖北能源 / 冀中能源），给它们读整节只会稀释上下文。
DEEP_READ_MAX_PAGES = 3
DEEP_READ_MAX_OUTLINE = 8
# ``KB_STALE_RECOVERY=0`` 关闭过期命中重读原页（对照实验用；缺省开）。
STALE_RECOVERY_ENV = "KB_STALE_RECOVERY"
# 过期命中当轮重读原页后的新鲜度状态：索引是旧版（排序可能偏），正文取自当前页面并
# 核对过问句词——它既不是 fresh（索引没变）也不是 stale（正文不是旧的）。
FRESHNESS_RECOVERED = "recovered"
_ACCEPTED_FRESHNESS = frozenset({"fresh", FRESHNESS_RECOVERED})

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
    # 深读（02）：命中所在整节按 ``DEEP_READ_ITEM_CHARS`` 切成的段；表格切片各自带表头。
    # ``deep_read_blocks`` 是 (节面包屑, 段落) 对——命中节之外还可能多读一节「问句词更多」的
    # 所缺章节；``deep_read_paragraphs`` 是纯文本视图，与 blocks 同序。
    deep_read_section: str = ""
    deep_read_sections: tuple[str, ...] = ()
    deep_read_blocks: tuple[tuple[str, str], ...] = ()
    deep_read_paragraphs: tuple[str, ...] = ()
    deep_read_truncated: bool = False
    deep_read_omitted_chars: int = 0
    # 同页其余章节的面包屑（不含结构小节），给模型「缺什么再读哪节」用。
    page_outline: tuple[str, ...] = ()
    # 深读那一节正文里出现的最晚日期（ISO），空 = 节内没有日期。
    section_latest_date: str = ""
    # 过期命中当轮重读原页恢复（见 ``recover_stale_hits``）。
    recovered_from_source: bool = False


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
    # 深读（02）。None = 本条遥测未跑深读（历史 run 报不可判，不报 0）。
    deep_read_pages: int | None = None
    deep_read_paragraphs: int | None = None
    deep_read_chars: int | None = None
    # 过期命中当轮重读原页：恢复数 / 重读后找不到原段落而丢弃数。
    stale_recovered: int | None = None
    stale_unrecoverable: int | None = None
    # 问句的材料口径：current / history / concept / method / general。
    material_scope: str = ""

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
        if self.deep_read_pages is not None:
            parts.append(
                f"深读={self.deep_read_pages}页/{self.deep_read_paragraphs or 0}段"
                f"/{self.deep_read_chars or 0}字"
            )
        if self.stale_recovered:
            parts.append(f"过期命中重读恢复={self.stale_recovered}")
        if self.stale_unrecoverable:
            parts.append(f"过期命中未恢复丢弃={self.stale_unrecoverable}")
        if self.material_scope:
            parts.append(f"材料口径={self.material_scope}")
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
            hit.index_freshness not in _ACCEPTED_FRESHNESS for hit in result.hits
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


# ---------------------------------------------------------------------------
# 深读实现（02）。全部纯函数 + 本地文件读取，不调模型、不外呼；页不可读 / 节定位
# 失败一律 fail-open（沿 V5 / V9a），命中本身不受影响。
# ---------------------------------------------------------------------------
_FRONTMATTER_STRIP_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
_DEEP_DATE_RE = re.compile(r"(?<!\d)(20\d{2})[-/.年]\s?(\d{1,2})[-/.月]\s?(\d{1,2})")
_DEEP_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_DEEP_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")
_DEEP_TABLE_CELL_WS_RE = re.compile(r"\s*\|\s*")
_DEEP_SENTENCE_RE = re.compile(r"[^。；！？!?;]+[。；！？!?;]?")
_DEEP_LOCATOR_RE = re.compile(r"(?:命中块|相邻块)\s+\S+::\d+:\s*")
# 字母 / 数字 token：800G、1.6T、HBM、DDR5、2024、Q1、98.5%、688776 都要能当定位词。
_DEEP_ALNUM_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-+%/]*")
_DEEP_CJK_RE = re.compile(r"[一-鿿]{2,}")
_DEEP_YEAR_RE = re.compile(r"(\d)年")
# 问句里的功能词：不当检索/定位词用，也不算命中；同时是汉字串的切分点——
# 「光模块的单价大概是多少」要切成「光模块」「单价」，而不是滑出「块的」「是多」这种碎片。
_DEEP_STOP_TERMS = frozenset(
    {
        "公司", "哪些", "哪几", "哪家", "哪个", "怎么", "怎么样", "怎样", "如何", "什么", "是什么",
        "为什么", "最新", "目前", "现在", "情况", "一下", "是否", "可以", "能否", "能不能",
        "会不会", "还有", "有没有", "有没", "没有", "以及", "关于", "请问", "帮我", "看看",
        "分析", "解释", "介绍", "深挖", "一家", "几家", "几个", "受益", "影响", "多少", "多大",
        "方面", "这个", "那个", "我们", "他们", "它们", "还是", "大概", "大约", "最近", "谁是",
        "主要", "核心", "相关", "重要", "属于", "包括", "分别", "各自", "到底", "究竟",
    }
)
_DEEP_PARTICLES = frozenset("的了吗呢啊吧呀嘛之与及或把被对这那哪和有在是让给向从到")
_DEEP_SPLIT_RE = re.compile(
    "|".join(
        re.escape(term)
        for term in sorted(_DEEP_STOP_TERMS | _DEEP_PARTICLES, key=len, reverse=True)
    )
)
_SCOPE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("history", re.compile(r"历史|回顾|回看|复盘|当年|曾经|过去|以前|回溯|(?:19|20)\d{2}\s*年(?!报)")),
    ("current", re.compile(r"最新|目前|现在|当前|近期|最近|今日|今天|本周|这周|本月|今年|现状|进展")),
    ("method", re.compile(r"方法|框架|口径|怎么看|如何判断|怎么判断|指标体系|逻辑链|方法论|怎么算|如何计算")),
    ("concept", re.compile(r"是什么|什么是|定义|原理|机制|概念|区别|区分|指的是")),
)


@dataclass
class DeepReadStats:
    pages: int = 0
    paragraphs: int = 0
    chars: int = 0
    skipped_pages: int = 0  # 页不可读 / 无节 / 定位失败（fail-open，命中照常送达）


@dataclass
class StaleRecoveryStats:
    recovered: int = 0
    unrecoverable: int = 0


def deep_read_total_chars() -> int:
    """整次检索的深读总字数预算；``KB_DEEP_READ_TOTAL_CHARS=0`` 关闭深读。"""
    raw = str(os.environ.get(DEEP_READ_TOTAL_ENV) or "").strip()
    if not raw:
        return DEEP_READ_TOTAL_CHARS
    try:
        return max(0, int(raw))
    except ValueError:
        return DEEP_READ_TOTAL_CHARS


def stale_recovery_enabled() -> bool:
    raw = str(os.environ.get(STALE_RECOVERY_ENV) or "").strip().lower()
    return raw not in {"0", "off", "false", "no"}


def material_scope_for_query(query: str) -> str:
    """问句的材料口径：``current`` / ``history`` / ``concept`` / ``method`` / ``general``。

    只做标签，不改召回：概念与方法题老资料照常可用；当前事实题要看节内最新日期。
    时间限定词（history / current）优先于题型词。
    """

    text = str(query or "")
    for name, pattern in _SCOPE_RULES:
        if pattern.search(text):
            return name
    return "general"


def deep_read_query_terms(query: str) -> tuple[str, ...]:
    """从问句抽定位/命中词：字母数字 token、按功能词切开后的汉字短串（≤4 字整取）及其二元组。

    长词排前（定位时整词命中比二元组更有判断力）。零依赖、确定性，与知识库侧
    ``_query_terms`` 同型（汉字 bigram + 保留代码），不引入分词器。先切功能词再取二元组，
    是为了不产生跨词碎片：「光模块的单价」→「光模块」「单价」，而不是「块的」。
    """

    terms: dict[str, None] = {}
    text = _DEEP_YEAR_RE.sub(r"\1 ", str(query or ""))
    for token in _DEEP_ALNUM_RE.findall(text):
        if len(token) >= 2 and not token.isdigit() or len(token) >= 4:
            terms.setdefault(token.lower(), None)
    cleaned = _DEEP_SPLIT_RE.sub(" ", text)
    for run in _DEEP_CJK_RE.findall(cleaned):
        if run in _DEEP_STOP_TERMS:
            continue
        if len(run) <= 4:
            terms.setdefault(run, None)
        if len(run) >= 3:
            for index in range(len(run) - 1):
                bigram = run[index : index + 2]
                if bigram not in _DEEP_STOP_TERMS:
                    terms.setdefault(bigram, None)
    return tuple(sorted(terms, key=lambda term: (-len(term), term)))


def _strip_frontmatter_text(raw: str) -> str:
    match = _FRONTMATTER_STRIP_RE.match(raw)
    return raw[match.end() :] if match else raw


def _is_structural_crumb(crumb: str) -> bool:
    return any(part.strip() in STRUCTURAL_SECTIONS for part in str(crumb or "").split(">"))


def _crumb_tail(crumb: str) -> str:
    parts = [part.strip() for part in str(crumb or "").split(">") if part.strip()]
    return parts[-1] if parts else ""


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _bare_window_text(hit: object) -> str:
    text = str(
        getattr(hit, "llm_evidence", "")
        or getattr(hit, "display_excerpt", "")
        or getattr(hit, "excerpt", "")
        or ""
    )
    return _DEEP_LOCATOR_RE.sub("", text).strip()


def section_latest_date(text: str) -> str:
    """节内出现的最晚日期（ISO）；没有合法日期返回空串。"""

    latest = ""
    for year, month, day in _DEEP_DATE_RE.findall(str(text or "")):
        try:
            month_i, day_i = int(month), int(day)
        except ValueError:
            continue
        if not (1 <= month_i <= 12 and 1 <= day_i <= 31):
            continue
        iso = f"{year}-{month_i:02d}-{day_i:02d}"
        if iso > latest:
            latest = iso
    return latest


def _term_score(text: str, terms: Sequence[str]) -> int:
    hay = str(text or "").casefold()
    return sum(len(term) for term in terms if term and term.casefold() in hay)


def locate_section(
    sections: Sequence[tuple[str, str]],
    *,
    crumb: str,
    window_text: str,
    terms: Sequence[str],
) -> int | None:
    """命中落在哪一节：面包屑全等 → 末级同名 → 窗口文本前缀落点 → 问句词最多的节。

    末级同名是为「别名与股票代码混用」留的：索引里的面包屑可能是
    ``688776_国光电气 > 反证与风险``，当前页改成 ``国光电气 > 反证与风险``，末级仍能对上。
    """

    if not sections:
        return None
    crumb = str(crumb or "").strip()
    if crumb:
        for index, (candidate, _text) in enumerate(sections):
            if candidate.strip() == crumb:
                return index
        tail = _crumb_tail(crumb)
        if tail:
            for index, (candidate, _text) in enumerate(sections):
                if _crumb_tail(candidate) == tail:
                    return index
    probe = _squash(_DEEP_LOCATOR_RE.sub("", str(window_text or "")))[:24]
    if len(probe) >= 8:
        for index, (_candidate, text) in enumerate(sections):
            if probe in _squash(text):
                return index
    if terms:
        best: int | None = None
        best_score = 0
        for index, (candidate, text) in enumerate(sections):
            if _is_structural_crumb(candidate):
                continue
            score = _term_score(f"{candidate}\n{text}", terms)
            if score > best_score:
                best, best_score = index, score
        return best
    return None


def _section_blocks(text: str) -> list[tuple[str, list[str]]]:
    """按空行切段；连续表格行归为一个 ``table`` 块，其余为 ``para`` 块。"""

    blocks: list[tuple[str, list[str]]] = []
    current: list[str] = []
    current_kind = ""

    def flush() -> None:
        nonlocal current, current_kind
        if current:
            blocks.append((current_kind, current))
        current, current_kind = [], ""

    for raw_line in str(text or "").splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            flush()
            continue
        kind = "table" if _DEEP_TABLE_ROW_RE.match(line) else "para"
        if current and kind != current_kind:
            flush()
        current.append(line)
        current_kind = kind
    flush()
    return blocks


def _table_slices(lines: Sequence[str], item_chars: int) -> list[str]:
    """表格按行分片，**每片都带表头（含分隔行）**，单位/列名不会留在相邻片里。"""

    rows = [_DEEP_TABLE_CELL_WS_RE.sub("|", line.strip()) for line in lines if line.strip()]
    if not rows:
        return []
    header = rows[0]
    separator = rows[1] if len(rows) > 1 and _DEEP_TABLE_SEP_RE.match(rows[1]) else ""
    body = rows[2:] if separator else rows[1:]
    head = f"{header}\n{separator}" if separator else header
    if len(head) > item_chars:
        head = head[: max(1, item_chars - 1)] + "…"
    if not body:
        return [head]
    room = max(8, item_chars - len(head) - 1)
    slices: list[str] = []
    current: list[str] = []
    size = len(head)
    for row in body:
        row_text = row if len(row) <= room else row[: max(1, room - 1)] + "…"
        if current and size + 1 + len(row_text) > item_chars:
            slices.append("\n".join([head, *current]))
            current, size = [], len(head)
        current.append(row_text)
        size += 1 + len(row_text)
    if current:
        slices.append("\n".join([head, *current]))
    return slices


def _para_slices(lines: Sequence[str], item_chars: int) -> list[str]:
    """段落按句切、按行保留换行，凑满 ``item_chars``；超长单句硬切。"""

    units: list[tuple[str, str]] = []  # (joiner, piece)
    for line in lines:
        compact = re.sub(r"[ \t]+", " ", line.strip())
        if not compact:
            continue
        first = True
        for sentence in _DEEP_SENTENCE_RE.findall(compact):
            piece = sentence.strip()
            if not piece:
                continue
            joiner = "\n" if first else ""
            first = False
            while len(piece) > item_chars:
                units.append((joiner, piece[:item_chars]))
                piece = piece[item_chars:]
                joiner = ""
            if piece:
                units.append((joiner, piece))
    slices: list[str] = []
    current = ""
    for joiner, piece in units:
        candidate = f"{current}{joiner if current else ''}{piece}"
        if current and len(candidate) > item_chars:
            slices.append(current)
            current = piece
        else:
            current = candidate
    if current:
        slices.append(current)
    return slices


def section_slices(text: str, item_chars: int = DEEP_READ_ITEM_CHARS) -> list[str]:
    """把一节正文切成 ≤ ``item_chars`` 的段：表格片带表头，段落按句凑满。"""

    item_chars = max(int(item_chars), 16)
    slices: list[str] = []
    pending: list[str] = []  # 相邻的段落块合成一个流再切：一行标题 + 两行列表不该各占一条证据

    def flush_paragraphs() -> None:
        nonlocal pending
        if pending:
            slices.extend(_para_slices(pending, item_chars))
            pending = []

    for kind, lines in _section_blocks(text):
        if kind == "table":
            flush_paragraphs()
            slices.extend(_table_slices(lines, item_chars))
        else:
            pending.extend(lines)
    flush_paragraphs()
    return [item for item in slices if item.strip()]


def _select_slices(
    slices: Sequence[str],
    terms: Sequence[str],
    budget: int,
) -> tuple[list[str], int]:
    """预算内选段：全放得下就按原序全给；放不下先要命中问句词的段，再按原序补齐。

    返回 ``(按文档顺序的选段, 被省略的字数)``。省略数必须如实带出——「节没读完」
    与「节就这么多」对模型是两件事。
    """

    total = sum(len(item) for item in slices)
    if budget <= 0 or not slices:
        return [], total
    if total <= budget:
        return list(slices), 0
    chosen: set[int] = set()
    used = 0
    ranked = sorted(
        ((_term_score(item, terms), index) for index, item in enumerate(slices)),
        key=lambda pair: (-pair[0], pair[1]),
    )
    for score, index in ranked:
        if score <= 0:
            break
        if used + len(slices[index]) > budget:
            continue
        chosen.add(index)
        used += len(slices[index])
    for index, item in enumerate(slices):
        if index in chosen:
            continue
        if used + len(item) > budget:
            break
        chosen.add(index)
        used += len(item)
    selected = [slices[index] for index in sorted(chosen)]
    return selected, total - used


def _read_page_sections(wiki_root: Path, file_path: str) -> list[tuple[str, str]] | None:
    page = resolve_wiki_page(wiki_root, str(file_path or ""))
    if page is None:
        return None
    try:
        raw = page.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    sections = split_sections(_strip_frontmatter_text(raw))
    return sections or None


def _hit_terms(hit: object, base_terms: Sequence[str]) -> tuple[str, ...]:
    own = tuple(str(term) for term in (getattr(hit, "evidence_query_terms", ()) or ()) if str(term))
    return tuple(dict.fromkeys((*own, *base_terms)))


def deep_read_hits(
    hits: Sequence[WikiHit],
    *,
    wiki_root: str | Path | None,
    query: str,
    per_hit_chars: int = DEEP_READ_PER_HIT_CHARS,
    total_chars: int | None = None,
    item_chars: int = DEEP_READ_ITEM_CHARS,
    max_pages: int = DEEP_READ_MAX_PAGES,
) -> DeepReadStats:
    """对最终送达的前 ``max_pages`` 条命中按序深读：读命中所在整节（必要时再读同页问句词
    更多的那一节）、切段、列同页其余章节、记节内最晚日期。

    预算两层：每页 ``per_hit_chars``、整次 ``total_chars``（默认读 env，0 关闭）。
    按命中顺序分配，但每页都能拿到至少一段（只要还有预算）——跨实体比较题不能让
    第一页把预算吃光（合同任务 2）。
    """

    stats = DeepReadStats()
    if wiki_root is None or not hits:
        return stats
    total = deep_read_total_chars() if total_chars is None else max(0, int(total_chars))
    if total <= 0:
        return stats
    root = Path(wiki_root)
    base_terms = deep_read_query_terms(query)
    remaining = total
    targets = list(hits)[: max(1, int(max_pages))]
    # 先按页数均分一个保底，再让排前的页拿剩余——第一页读得多，但不会独占。
    floor = max(item_chars, total // max(len(targets), 1))
    for position, hit in enumerate(targets):
        if remaining <= 0:
            break
        sections = _read_page_sections(root, str(getattr(hit, "file_path", "") or ""))
        if sections is None:
            stats.skipped_pages += 1
            continue
        terms = _hit_terms(hit, base_terms)
        index = locate_section(
            sections,
            crumb=str(getattr(hit, "section", "") or ""),
            window_text=_bare_window_text(hit),
            terms=terms,
        )
        hit.page_outline = tuple(
            crumb
            for offset, (crumb, _text) in enumerate(sections)
            if offset != index and not _is_structural_crumb(crumb)
        )[:DEEP_READ_MAX_OUTLINE]
        if index is None:
            stats.skipped_pages += 1
            continue
        later_pages = len(targets) - position - 1
        # 给后面每一页留一个保底段的位置；最后一页可用完剩余。
        budget = min(per_hit_chars, max(floor, remaining - later_pages * item_chars))
        budget = min(budget, remaining)
        # 读命中节；若同页另有一节问句词明显更多（「所缺章节」），剩余预算再读它。
        # 命中块只证明「这一页相关」，答案常在同页别的节——沃格光电的亏损数字在
        # 「高信度研究线索」，命中却落在「后续跟踪」表。
        crumb, text = sections[index]
        hit_score = _term_score(f"{crumb}\n{text}", terms)
        plan: list[int] = [index]
        best_other: int | None = None
        best_score = hit_score
        for offset, (other_crumb, other_text) in enumerate(sections):
            if offset == index or _is_structural_crumb(other_crumb):
                continue
            score = _term_score(f"{other_crumb}\n{other_text}", terms)
            if score > best_score:
                best_other, best_score = offset, score
        if best_other is not None:
            plan.append(best_other)
        blocks: list[tuple[str, str]] = []
        omitted_total = 0
        used = 0
        for step, offset in enumerate(plan):
            section_crumb, section_text = sections[offset]
            slices = section_slices(section_text, item_chars)
            if not slices:
                continue
            share = budget - used
            if step == 0 and len(plan) > 1:
                # 命中节与所缺章节分预算：所缺章节问句词更多，至少留给它一半。
                share = min(share, max(item_chars, budget // 2))
            selected, omitted = _select_slices(slices, terms, share)
            omitted_total += omitted
            if not selected:
                continue
            used += sum(len(item) for item in selected)
            blocks.extend((section_crumb, item) for item in selected)
        if not blocks:
            stats.skipped_pages += 1
            continue
        remaining -= used
        hit.deep_read_section = crumb
        hit.deep_read_sections = tuple(dict.fromkeys(section for section, _item in blocks))
        hit.deep_read_blocks = tuple(blocks)
        hit.deep_read_paragraphs = tuple(item for _section, item in blocks)
        hit.deep_read_truncated = omitted_total > 0
        hit.deep_read_omitted_chars = omitted_total
        hit.section_latest_date = section_latest_date(
            "\n".join(sections[offset][1] for offset in plan)
        )
        stats.pages += 1
        stats.paragraphs += len(blocks)
        stats.chars += used
    return stats


def _centered_window(text: str, terms: Sequence[str], max_chars: int) -> str:
    body = _compact_text(text)
    if max_chars <= 0 or len(body) <= max_chars:
        return body[: max(max_chars, 0)] if max_chars > 0 else ""
    lower = body.casefold()
    found = [
        (lower.find(term.casefold()), term)
        for term in terms
        if term and lower.find(term.casefold()) >= 0
    ]
    if found:
        radius = max(max_chars // 2, 1)
        center, _term = max(
            found,
            key=lambda candidate: sum(
                len(term) for position, term in found if abs(position - candidate[0]) <= radius
            ),
        )
        start = max(0, center - max_chars // 2)
    else:
        start = 0
    end = min(len(body), start + max_chars)
    start = max(0, end - max_chars)
    out = body[start:end].strip()
    if start > 0:
        out = "…" + out
    if end < len(body):
        out = out + "…"
    return out


def recover_stale_hits(
    hits: Sequence[WikiHit],
    *,
    wiki_root: str | Path | None,
    query: str,
    excerpt_chars: int = DEFAULT_EXCERPT_CHARS,
) -> StaleRecoveryStats:
    """过期 / 未知新鲜度的命中当轮重读原页：原节还在且含问句词 → 用当前正文替换并标
    ``recovered``；找不到原节或原节已不含问句词 → 保持原状（随后按合同丢弃）。

    这条把「索引比页面旧」从一票否决改成可核对的恢复：页面就在本地磁盘上，与其让
    模型等一次不知何时的 ``rag update``，不如现在读一遍并核对。不把所有 stale 直接当
    当前事实——只有核对通过的才放行，且新鲜度写成 ``recovered`` 不冒充 fresh。
    """

    stats = StaleRecoveryStats()
    if wiki_root is None:
        return stats
    root = Path(wiki_root)
    base_terms = deep_read_query_terms(query)
    for hit in hits:
        if hit.index_freshness not in {"stale", "unknown"}:
            continue
        sections = _read_page_sections(root, hit.file_path)
        if sections is None:
            stats.unrecoverable += 1
            continue
        terms = _hit_terms(hit, base_terms)
        index = locate_section(
            sections,
            crumb=hit.section,
            window_text=_bare_window_text(hit),
            terms=terms,
        )
        if index is None:
            stats.unrecoverable += 1
            continue
        crumb, text = sections[index]
        if terms and _term_score(text, terms) <= 0:
            stats.unrecoverable += 1
            continue
        limit = max(int(hit.evidence_char_budget or 0), len(hit.llm_evidence), DEFAULT_LLM_EVIDENCE_CHARS)
        window = _centered_window(text, terms, limit)
        if not window:
            stats.unrecoverable += 1
            continue
        hit.llm_evidence = window
        hit.excerpt = _compact_text(window, int(excerpt_chars))
        hit.display_excerpt = hit.excerpt
        hit.section = crumb
        hit.content_hash = hashlib.sha1(window.encode("utf-8")).hexdigest()  # noqa: S324 — 内容标识，非安全用途；与索引 40 位形状一致
        hit.index_freshness = FRESHNESS_RECOVERED
        hit.recovered_from_source = True
        stats.recovered += 1
    return stats


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
    # ⚠ 子句顺序是承重的，别按「宽的放前面」重排：``WorkerRequestAbandoned``
    # 继承 ``TimeoutError`` → ``OSError``，一旦排在 ``(RuntimeError, OSError,
    # json.JSONDecodeError)`` 之后就永远匹配不到（2026-09-03 实测：两个超时处置
    # 器都是死代码，超时被判成 `persistent_worker_unavailable` → 回退 CLI 用
    # `timeout − 已耗` 的残窗重载 4.3G 模型 → 必然二次超时；生产 kb_search 66%
    # 以 tool_timeout 收场、常驻 worker `queries_served=1` 里那 1 次就是被放弃的
    # 那次）。超时不是「worker 不可用」：进程还在，回退 CLI 是最贵的那条路。
    except rag_worker.WorkerRequestAbandoned:
        # 热 worker 第一次超窗：请求放弃、进程保留，下一次查询不用等模型重载。
        res.warning = f"wiki-rag 常驻 worker 超时(>{timeout}s)，请求已放弃、worker 保留"
        tel.latency_ms = int((time.monotonic() - _t0) * 1000)
        tel.status = "timeout"
        tel.warning = res.warning
        return res
    except TimeoutError:
        # 冷 worker 或连续第二次超时：``_on_query_timeout`` 已杀进程。此处同样
        # 不回退 CLI——残窗里重载模型必然再超时，白烧剩余预算。
        res.warning = f"wiki-rag 常驻 worker 超时(>{timeout}s)，进程已终止"
        tel.latency_ms = int((time.monotonic() - _t0) * 1000)
        tel.status = "timeout"
        tel.warning = res.warning
        return res
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        # 真正的「worker 不可用」：进程没了/协议错乱/响应不可解析。这些回退 CLI
        # 是对的——没有热进程可保，CLI 是唯一还能出结果的路。
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
    if require_fresh and stale_recovery_enabled():
        # 02：丢弃之前先当轮重读原页——页就在本地，核对得过的换成当前正文放行（recovered）。
        recovery = recover_stale_hits(
            hits,
            wiki_root=wiki_root,
            query=budget_query or query,
            excerpt_chars=int(excerpt_chars),
        )
        tel.stale_recovered = recovery.recovered
        tel.stale_unrecoverable = recovery.unrecoverable
        if recovery.recovered:
            warnings.append(
                f"wiki-rag {recovery.recovered} 条过期命中已当轮重读原页恢复"
                f"（新鲜度={FRESHNESS_RECOVERED}：索引是旧版，正文取自当前页面并核对过问句词）"
            )
    non_fresh_hits = [hit for hit in hits if hit.index_freshness not in _ACCEPTED_FRESHNESS]
    if require_fresh:
        # formal 契约：过期/未知且重读原页也救不回的命中一律丢弃，绝不进入 res.hits / LLM 证据。
        if non_fresh_hits:
            tel.degraded = True
            states = ",".join(sorted({hit.index_freshness for hit in non_fresh_hits}))
            # 光说「丢了几条、契约要求 fresh」只解释了机制，没告诉人怎么办。
            # 内容仓每天 ingest，工作区脏是常态，这条会高频出现——它必须自带动作，
            # 否则用户看到的就是「又没有证据」，而实际上证据就在那里、差一次提交。
            #
            # 但这句动作**不能去断言某个后台机制正在工作**。原文写的是「提交后
            # post-commit 会自动重建索引，届时这些证据即可进入」——2026-09-03 查出
            # 那个钩子从 08-22 起五次没跑完、09-01 起被残留锁卡死，这句话当时是假话，
            # 照做的人会一直等一个不会发生的重建。改成先给**当场能做、能自己验证**
            # 的手动动作，自动那条只作补充。
            remedy = (
                "在知识库仓跑 scripts/rag_index.py update 重建索引"
                "（提交后 post-commit 也会尝试自动重建，但以手动跑通为准）"
                if states == "stale"
                else "先在知识库仓跑 rag update 重建索引"
            )
            warnings.append(
                f"wiki-rag 丢弃 {len(non_fresh_hits)} 条非 fresh 命中（新鲜度={states}）："
                "已尝试当轮重读原页，但页不可读、原节已不在或原节已不含问句词，"
                f"不能当作当前事实使用；formal 证据要求 fresh｜可恢复：{remedy}"
            )
        hits = [hit for hit in hits if hit.index_freshness in _ACCEPTED_FRESHNESS]
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
    # 02：只对最终送达的 k 条深读（不对过采样的 4k 条读页），读的是命中所在整节。
    tel.material_scope = material_scope_for_query(budget_query or query)
    deep = deep_read_hits(res.hits, wiki_root=wiki_root, query=budget_query or query)
    tel.deep_read_pages = deep.pages
    tel.deep_read_paragraphs = deep.paragraphs
    tel.deep_read_chars = deep.chars
    if deep.skipped_pages:
        # 「没深读」与「深读了但页读不到 / 定位不到节」要分开可见：前者是预算为 0，后者是页的事。
        res.warning = "；".join(
            filter(None, [res.warning, f"深读跳过 {deep.skipped_pages} 页（页不可读或未定位到命中节）"])
        )
        tel.warning = res.warning
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
