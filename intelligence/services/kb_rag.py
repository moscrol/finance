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


@dataclass
class WikiHit:
    page_id: str
    file_path: str  # relative to KB repo root, e.g. "wiki/synthesis/foo.md"
    title: str
    score: float
    excerpt: str
    evidence_layer: str = ""
    fact_hardness: str = ""
    source_type: str = ""
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
    evidence_layer: str | None = None,
    fact_hardness: str | None = None,
    source_type: str | None = None,
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
    index_dir = _resolve_index_dir(root)
    res.index_dir = str(index_dir)
    if not index_dir.exists():
        res.warning = (
            f"wiki-rag 未接入：向量索引不存在 {index_dir}"
            "（先在知识库仓跑 scripts/rag_index.py build 或 fetch_rag_index.py）"
        )
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
    filter_note = f" filters={','.join(filters)}" if filters else ""
    res.command = f"rag_index.py query <q> --k {k} --mode {mode}{filter_note} --json"
    res.citation_source = f"knowledge-base · rag_index.py query --mode {mode}{filter_note}（hybrid 向量召回 wiki 候选页）"
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(root))
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
                evidence_layer=str(item.get("evidence_layer") or ""),
                fact_hardness=str(item.get("fact_hardness") or ""),
                source_type=str(item.get("source_type") or ""),
                via_neighbor=bool(item.get("via_neighbor")),
            )
        )
    res.hits = hits
    res.ok = bool(hits)
    if not hits:
        res.warning = "wiki-rag 无命中"
    return res
