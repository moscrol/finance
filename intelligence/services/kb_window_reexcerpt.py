"""KB 消费侧重摘录（V9a / 方案 A1）。

命中后按 ``WikiHit.file_path`` 读本地 wiki 页，按标题切节（规则抄知识库仓
``chunking._split_sections``，不引入 KB 包），跳过结构小节黑名单，把零信息窗
换成正文段。

认不出结构 → fail-open 保持现状（沿 V5）。
重摘录后整页仍无正文 → 丢弃该 hit（指针页），靠既有 ``fetch_k`` 过采样补位。
禁止用路径行充正文。不在请求路径扫 ``chunks.jsonl``。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")

STRUCTURAL_SECTIONS = frozenset(
    {
        "原始资料链接",
        "相关实体",
        "相关概念",
        "Raw / Manifest Trace",
        "Source 分类",
        "使用口径",
    }
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_LOCATOR_RE = re.compile(r"(?:命中块|相邻块)\s+.+?::\d+:\s*")
_WIKILINK_RE = re.compile(r"\[\[[^\]]+\]\]")
_SOURCE_ITEM_RE = re.compile(r"\d+\.\s+\*\*[^*]+?\*\*.{0,240}?https?://\S+")
_PATH_RE = re.compile(r"(?:raw/|wiki/)[\w./\u4e00-\u9fff\-]+\.\w+")
_POINTER_MARKERS = ("source note", "用于追踪", "本 source note")
_PREFERRED_CRUMBS = ("一句话", "最新市场逻辑", "核心逻辑", "公司简介", "预期差")


@dataclass(frozen=True)
class ReexcerptStats:
    pointer_dropped: int = 0
    reexcerpted: int = 0


def _strip_frontmatter(raw: str) -> str:
    match = _FM_RE.match(raw)
    return raw[match.end() :] if match else raw


def split_sections(body: str) -> list[tuple[str, str]]:
    """按标题切成 ``(breadcrumb, section_text)``，规则与 KB ``_split_sections`` 同形。"""

    lines = body.splitlines()
    sections: list[tuple[str, str]] = []
    crumb: list[tuple[int, str]] = []
    buf: list[str] = []
    cur_crumb = "正文"

    def crumb_str() -> str:
        return " > ".join(title for _, title in crumb) or "正文"

    def flush() -> None:
        nonlocal buf
        text = "\n".join(buf).strip()
        if text:
            sections.append((cur_crumb, text))
        buf = []

    for line in lines:
        heading = _HEADING_RE.match(line)
        if heading:
            flush()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            while crumb and crumb[-1][0] >= level:
                crumb.pop()
            crumb.append((level, title))
            cur_crumb = crumb_str()
        else:
            buf.append(line)
    flush()
    return sections


def _crumb_parts(crumb: str) -> list[str]:
    return [part.strip() for part in str(crumb or "").split(">") if part.strip()]


def _is_blacklisted(crumb: str, blacklist: frozenset[str]) -> bool:
    return any(part in blacklist for part in _crumb_parts(crumb))


def _bare_window(text: str) -> str:
    return _LOCATOR_RE.sub("", text or "").lstrip()


def _looks_like_source_list(text: str) -> bool:
    bare = _bare_window(text)
    if "cnfin.com" in bare[:400]:
        return True
    return _SOURCE_ITEM_RE.search(bare[:400]) is not None


def _looks_like_wikilink_pile(text: str) -> bool:
    bare = _bare_window(text)
    if "[[" not in bare:
        return False
    residual = _WIKILINK_RE.sub("", bare)
    residual = re.sub(r"[·•|,/\s\-：:]+", "", residual)
    return len(residual) < 12


def _looks_like_path_line(text: str) -> bool:
    bare = _bare_window(text).strip()
    if not _PATH_RE.search(bare):
        return False
    residual = _PATH_RE.sub("", bare)
    residual = re.sub(r"[`*\-\s]+", "", residual)
    return len(residual) < 24


def _text_is_structural(text: str) -> bool:
    return (
        _looks_like_source_list(text)
        or _looks_like_wikilink_pile(text)
        or _looks_like_path_line(text)
    )


def _is_pointer_text(text: str) -> bool:
    lowered = (text or "").casefold()
    return any(marker.casefold() in lowered for marker in _POINTER_MARKERS)


def _current_text(hit: object) -> str:
    return str(
        getattr(hit, "llm_evidence", "")
        or getattr(hit, "display_excerpt", "")
        or getattr(hit, "excerpt", "")
        or ""
    )


def _should_replace(
    hit: object,
    sections: Sequence[tuple[str, str]],
    blacklist: frozenset[str],
) -> bool:
    """只换零信息窗。黑名单清空时结构节不再被跳过，#1 保持清单（变异②）。"""

    section = str(getattr(hit, "section", "") or "")
    if _is_blacklisted(section, blacklist):
        return True
    page_has_blacklisted = any(_is_blacklisted(crumb, blacklist) for crumb, _ in sections)
    return _text_is_structural(_current_text(hit)) and page_has_blacklisted


def _is_preferred(crumb: str, text: str) -> bool:
    if any(key in crumb for key in _PREFERRED_CRUMBS):
        return True
    head = text.lstrip()[:80]
    return "**一句话**" in head or head.startswith("一句话")


def _select_body(
    sections: Sequence[tuple[str, str]],
    blacklist: frozenset[str],
) -> str | None:
    candidates = [
        (crumb, text)
        for crumb, text in sections
        if text.strip() and not _is_blacklisted(crumb, blacklist)
    ]
    real = [(crumb, text) for crumb, text in candidates if not _is_pointer_text(text)]
    if not real:
        return None
    preferred = [text for crumb, text in real if _is_preferred(crumb, text)]
    chosen = preferred or [real[0][1]]
    return "\n\n".join(chosen[:2]).strip() or None


def resolve_wiki_page(wiki_root: Path, file_path: str) -> Path | None:
    posix = str(file_path or "").replace("\\", "/").lstrip("./")
    if not posix:
        return None
    candidates = (
        wiki_root.parent / posix,
        wiki_root / posix,
        wiki_root / posix.removeprefix("wiki/"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _assign(hit: T, **values: object) -> T:
    for key, value in values.items():
        setattr(hit, key, value)
    return hit


def reexcerpt_hits(
    hits: Sequence[T],
    *,
    wiki_root: str | Path | None = None,
) -> tuple[list[T], ReexcerptStats]:
    """按页重摘录；指针页丢弃。``wiki_root`` 缺失或页不可读 → fail-open。"""

    items = list(hits)
    if wiki_root is None:
        return items, ReexcerptStats()
    root = Path(wiki_root)
    kept: list[T] = []
    dropped = 0
    changed = 0
    blacklist = STRUCTURAL_SECTIONS
    for hit in items:
        page = resolve_wiki_page(root, str(getattr(hit, "file_path", "") or ""))
        if page is None:
            kept.append(_assign(hit, reexcerpted=False))
            continue
        try:
            raw = page.read_text(encoding="utf-8")
        except OSError:
            kept.append(_assign(hit, reexcerpted=False))
            continue
        sections = split_sections(_strip_frontmatter(raw))
        if not sections:
            kept.append(_assign(hit, reexcerpted=False))
            continue
        selected = _select_body(sections, blacklist)
        if selected is None:
            if any(_is_blacklisted(crumb, blacklist) for crumb, _ in sections):
                dropped += 1
                continue
            kept.append(_assign(hit, reexcerpted=False))
            continue
        if not _should_replace(hit, sections, blacklist):
            kept.append(_assign(hit, reexcerpted=False))
            continue
        kept.append(
            _assign(
                hit,
                excerpt=selected,
                display_excerpt=selected,
                llm_evidence=selected,
                reexcerpted=True,
            )
        )
        changed += 1
    return kept, ReexcerptStats(pointer_dropped=dropped, reexcerpted=changed)
