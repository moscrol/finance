"""Knowledge-base hybrid 向量检索 as an `ask` 召回源 (W source).

`intelligence.ask` already recalls graph/evidence (G/R) by deterministic keyword
scoring over the committed ``wiki/relations/*.json``. That只命中已入图谱的关系；
this module adds a *semantic* recall path that closes the loop between finance
review and the knowledge base: it fans the query out to the knowledge-base repo's
hybrid vector retriever (``scripts/rag_index.py query --json`` — BGE-m3 dense +
BM25 + RRF) to **select candidate wiki pages**, then reads those page bodies as
numbered ``[W#]`` evidence. Per the KB convention, embedding 只替换「找哪些页」，
不替换「读全文」: the RAG picks pages, we read their raw bodies for the excerpt.

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
    via_neighbor: bool = False


@dataclass
class WikiRagResult:
    ok: bool = False
    command: str = ""
    citation_source: str = ""
    index_dir: str = ""
    hits: list[WikiHit] = field(default_factory=list)
    warning: str = ""


def kb_root(kb_wiki: str | Path) -> Path:
    """KB repo root = parent of the wiki root (mirrors theme_modules._kb_root)."""
    return Path(kb_wiki).expanduser().resolve().parent


def _resolve_index_dir(root: Path) -> Path:
    """Mirror rag.config.index_dir(): RAG_INDEX_DIR env, else <kb_root>/.rag_index."""
    env = os.environ.get("RAG_INDEX_DIR")
    if env:
        return Path(env).expanduser()
    return root / ".rag_index"


def _read_excerpt(page_path: Path, fallback: str, max_chars: int) -> str:
    """Read a candidate page body for a clean excerpt (strip YAML frontmatter)."""
    try:
        text = page_path.read_text(encoding="utf-8")
    except Exception:
        return (fallback or "").strip()[:max_chars]
    # strip a leading Obsidian/YAML frontmatter block
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            nl = text.find("\n", end + 1)
            text = text[nl + 1:] if nl != -1 else ""
    body = re.sub(r"\s+", " ", text).strip()
    if not body:
        return (fallback or "").strip()[:max_chars]
    return body[:max_chars]


def retrieve(
    query: str,
    kb_wiki: str | Path | None,
    k: int = DEFAULT_RAG_K,
    mode: str = DEFAULT_RAG_MODE,
    timeout: int = DEFAULT_RAG_TIMEOUT,
    excerpt_chars: int = DEFAULT_EXCERPT_CHARS,
    index_dir: str | Path | None = None,
) -> WikiRagResult:
    """Run the KB hybrid retriever for ``query`` and return candidate wiki pages.

    Any unavailability (no wiki path / no rag_index.py / no built index / timeout /
    non-zero exit / unparsable JSON) sets ``warning`` and returns ``ok=False`` so
    the caller can skip the W source without breaking S/G/R.
    """
    res = WikiRagResult()
    if not kb_wiki:
        res.warning = "wiki-rag 需要知识库 wiki 路径 (--kb-wiki / KNOWLEDGE_WIKI)"
        return res
    root = kb_root(kb_wiki)
    script = root / RAG_SCRIPT_REL
    if not script.exists():
        res.warning = f"wiki-rag 未接入：找不到 {script}"
        return res
    # 选索引目录：默认走 _resolve_index_dir（RAG_INDEX_DIR env 或 .rag_index）；
    # 全文版经 index_dir 指向 .rag_index_full。若指定索引缺失则回退默认索引，
    # 避免 W 源在只装了结构版索引的机器上被静默丢弃。
    default_index = _resolve_index_dir(root)
    chosen = default_index
    if index_dir is not None:
        cand = Path(index_dir).expanduser()
        if not cand.is_absolute():
            cand = root / cand
        if cand.exists():
            chosen = cand
        elif default_index.exists():
            res.warning = f"wiki-rag 请求索引 {cand.name} 不存在，已回退默认索引 {default_index.name}"
        else:
            chosen = cand  # 都不存在 → 落到下方缺失索引告警
    res.index_dir = str(chosen)
    if not chosen.exists():
        res.warning = (
            f"wiki-rag 未接入：向量索引不存在 {chosen}"
            "（先在知识库仓跑 scripts/rag_index.py build 或 fetch_rag_index.py）"
        )
        return res

    cmd = [sys.executable, str(script), "query", str(query), "--k", str(k), "--mode", str(mode), "--json"]
    res.command = f"rag_index.py query <q> --k {k} --mode {mode} --json"
    res.citation_source = f"knowledge-base · rag_index.py query --mode {mode}（hybrid 向量召回 wiki 候选页）"
    # 把选定的索引目录显式传给子进程，确保 rag_index.py 用的是 chosen（含全文版/回退）。
    env = dict(os.environ)
    env["RAG_INDEX_DIR"] = str(chosen)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(root), env=env)
    except subprocess.TimeoutExpired:
        res.warning = f"wiki-rag 超时(>{timeout}s)，已跳过"
        return res
    except Exception as exc:  # pragma: no cover - defensive
        res.warning = f"wiki-rag 调用失败: {exc}"
        return res
    if proc.returncode != 0:
        res.warning = f"wiki-rag 退出码 {proc.returncode}: {(proc.stderr or '').strip()[:160]}"
        return res

    try:
        raw = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        res.warning = f"wiki-rag 输出非 JSON: {exc}"
        return res
    if not isinstance(raw, list):
        res.warning = "wiki-rag 输出格式异常（期望 PageHit 列表）"
        return res

    hits: list[WikiHit] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        rel = str(item.get("file_path") or "")
        excerpt = _read_excerpt(root / rel, str(item.get("snippet") or ""), excerpt_chars)
        hits.append(
            WikiHit(
                page_id=str(item.get("page_id") or ""),
                file_path=rel,
                title=str(item.get("title") or item.get("page_id") or "(无标题)"),
                score=float(item.get("score") or 0.0),
                excerpt=excerpt,
                via_neighbor=bool(item.get("via_neighbor")),
            )
        )
    res.hits = hits
    res.ok = bool(hits)
    if not hits:
        res.warning = "wiki-rag 无命中"
    return res
