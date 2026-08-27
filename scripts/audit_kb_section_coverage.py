#!/usr/bin/env python3
"""知识库 wiki 节标题分布审计（R3 §B2 / V10）。

扫 ``--wiki-root`` 下的 wiki markdown，量 ``STRUCTURAL_SECTIONS`` 黑名单对真实
节名的覆盖，并列出启发式判为结构节、但不在黑名单里的变体（盲区）。

不引入知识库仓包。``--wiki-root`` 必填，不写死本机路径。解析约定对齐
``KnowledgeAdapter.resolved_wiki_root``：传入的是含 ``entities/`` / ``concepts/``
的 wiki 根；若传入仓根且其下有 ``wiki/entities``，则收口到 ``wiki/``。

禁扫
----
任何名为 ``.rag_index`` 的目录（含 181MB ``chunks.jsonl``），以及任何
``chunks.jsonl`` 文件。``relations/`` 是 JSON 不是 wiki 页。``raw/`` 是 ingest
原文，不是 kb_search 换窗所读的实体/概念/来源页——默认跳过，见验证文档诚实边界。

结构类启发式（冻结；改它必须改夹具单测）
----------------------------------------
对 ``##`` 二级节标题（与黑名单同级；``#`` 页名、``###`` 日期条目不计）做判定。
``is_structural_heading(title)`` 为真，当且仅当下列之一成立：

1. 规范化后与 ``STRUCTURAL_SECTIONS`` 任一成员全等（大小写不敏感、空白折叠）；
2. 标题含子串（大小写不敏感）：``相关实体`` / ``相关概念`` / ``相关公司`` /
   ``相关标的`` / ``原始资料`` / ``资料链接`` / ``资料来源`` / ``manifest trace`` /
   ``source 分类`` / ``使用口径`` / ``仅更新图谱`` / ``观察列表`` / ``关键公司`` /
   ``关键标的`` / ``当前实体暴露`` / ``所属上位概念`` / ``所属主干`` / ``概念关系``；
3. 规范化后等于 ``来源``，或以 ``source `` / ``raw /`` 开头。

正文节（``一句话`` / ``核心逻辑`` / ``最新市场逻辑`` / ``边际变化`` / ``产业链``
等）不得命中以上规则。

覆盖率
------
``blacklist_heuristic_coverage`` = 黑名单 6 名里被启发式判为结构节的比例。
健全启发式下必须是 1.0。启发式恒 False → 该读数归零（变异钉）。

盲区
----
启发式为真、且不在黑名单、且出现页数 ≥ ``--min-blind-pages``（默认 20）的节名。

用法::

    .venv-workbench/bin/python scripts/audit_kb_section_coverage.py \\
        --wiki-root /path/to/knowledge-base-private/wiki --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.services.kb_window_reexcerpt import (  # noqa: E402
    STRUCTURAL_SECTIONS,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_SKIP_DIR_NAMES = frozenset(
    {
        ".rag_index",
        ".git",
        ".obsidian",
        "__pycache__",
        "node_modules",
        "relations",
        "raw",
    }
)
_STRUCTURAL_TOKENS = (
    "相关实体",
    "相关概念",
    "相关公司",
    "相关标的",
    "原始资料",
    "资料链接",
    "资料来源",
    "manifest trace",
    "source 分类",
    "使用口径",
    "仅更新图谱",
    "观察列表",
    "关键公司",
    "关键标的",
    "当前实体暴露",
    "所属上位概念",
    "所属主干",
    "概念关系",
)
_DEFAULT_MIN_BLIND_PAGES = 20


def normalize_heading(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip()).casefold()


def is_structural_heading(title: str) -> bool:
    """结构节启发式。规则写在模块 docstring；夹具单测冻结正反例。"""

    raw = (title or "").strip()
    if not raw:
        return False
    if raw in STRUCTURAL_SECTIONS:
        return True
    folded = normalize_heading(raw)
    if folded in {normalize_heading(item) for item in STRUCTURAL_SECTIONS}:
        return True
    if any(token.casefold() in folded for token in _STRUCTURAL_TOKENS):
        return True
    if folded == "来源" or folded.startswith("source ") or folded.startswith("raw /"):
        return True
    return False


def heading_from_text(title: str, detail: str = "") -> str:
    """从 evidence 的 title / detail 抽出用于正文头判定的节名。"""

    heading = (title or "").strip()
    if heading:
        return heading
    text = (detail or "").lstrip()
    if not text:
        return ""
    first = text.splitlines()[0].strip()
    match = _HEADING_RE.match(first)
    if match:
        return match.group(2).strip()
    return first


def is_body_header(title: str, detail: str = "") -> bool:
    """正文头 = 抽出的节名不是结构节。结构节或空标题 → False。"""

    heading = heading_from_text(title, detail)
    if not heading:
        return False
    return not is_structural_heading(heading)


def in_blacklist(title: str) -> bool:
    folded = normalize_heading(title)
    return title in STRUCTURAL_SECTIONS or folded in {
        normalize_heading(item) for item in STRUCTURAL_SECTIONS
    }


def resolve_wiki_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if (root / "entities").is_dir() or (root / "concepts").is_dir():
        return root
    nested = root / "wiki"
    if (nested / "entities").is_dir() or (nested / "concepts").is_dir():
        return nested
    return root


def iter_wiki_markdown(wiki_root: Path) -> list[Path]:
    """只收 wiki 页 markdown。``.rag_index`` / ``chunks.jsonl`` / ``raw`` 一律跳过。"""

    pages: list[Path] = []
    root = wiki_root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        try:
            relative = current.relative_to(root)
        except ValueError:
            dirnames[:] = []
            continue
        if any(part in _SKIP_DIR_NAMES for part in relative.parts):
            dirnames[:] = []
            continue
        dirnames[:] = [name for name in dirnames if name not in _SKIP_DIR_NAMES]
        for name in filenames:
            if name == "chunks.jsonl":
                continue
            if name.endswith(".md"):
                pages.append(current / name)
    return sorted(pages)


def extract_h2_titles(text: str) -> list[str]:
    titles: list[str] = []
    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match is None or len(match.group(1)) != 2:
            continue
        title = match.group(2).strip()
        if title:
            titles.append(title)
    return titles


def audit_wiki(
    wiki_root: Path,
    *,
    min_blind_pages: int = _DEFAULT_MIN_BLIND_PAGES,
) -> dict[str, Any]:
    root = resolve_wiki_root(wiki_root)
    pages_by_heading: dict[str, set[str]] = defaultdict(set)
    scanned = 0
    unread = 0
    for page in iter_wiki_markdown(root):
        try:
            text = page.read_text(encoding="utf-8")
        except OSError:
            unread += 1
            continue
        scanned += 1
        rel = page.relative_to(root).as_posix()
        for title in extract_h2_titles(text):
            pages_by_heading[title].add(rel)

    ranking: list[dict[str, Any]] = []
    for title, pages in pages_by_heading.items():
        ranking.append(
            {
                "title": title,
                "page_count": len(pages),
                "structural_candidate": is_structural_heading(title),
                "in_blacklist": in_blacklist(title),
            }
        )
    ranking.sort(key=lambda row: (-int(row["page_count"]), str(row["title"])))

    covered = [name for name in STRUCTURAL_SECTIONS if is_structural_heading(name)]
    present = [
        name
        for name in STRUCTURAL_SECTIONS
        if name in pages_by_heading
        or any(normalize_heading(seen) == normalize_heading(name) for seen in pages_by_heading)
    ]
    blind_spots = [
        {
            "title": row["title"],
            "page_count": row["page_count"],
            "reason": "heuristic structural, not in STRUCTURAL_SECTIONS",
        }
        for row in ranking
        if row["structural_candidate"]
        and not row["in_blacklist"]
        and int(row["page_count"]) >= min_blind_pages
    ]
    candidates = [
        row for row in ranking if row["structural_candidate"]
    ]
    return {
        "wiki_root": str(root),
        "pages_scanned": scanned,
        "pages_unread": unread,
        "heading_types": len(ranking),
        "min_blind_pages": min_blind_pages,
        "blacklist": sorted(STRUCTURAL_SECTIONS),
        "blacklist_heuristic_coverage": (
            len(covered) / len(STRUCTURAL_SECTIONS) if STRUCTURAL_SECTIONS else 0.0
        ),
        "blacklist_corpus_coverage": (
            len(present) / len(STRUCTURAL_SECTIONS) if STRUCTURAL_SECTIONS else 0.0
        ),
        "blacklist_present": present,
        "blacklist_missing_from_corpus": [
            name for name in sorted(STRUCTURAL_SECTIONS) if name not in present
        ],
        "heading_rank": ranking,
        "structural_candidates": candidates,
        "blind_spots": blind_spots,
    }


def render_table(report: dict[str, Any], *, rank_limit: int = 40) -> str:
    lines = [
        f"wiki_root: {report['wiki_root']}",
        f"pages_scanned: {report['pages_scanned']}  unread: {report['pages_unread']}",
        f"heading_types: {report['heading_types']}",
        (
            "STRUCTURAL_SECTIONS 启发式覆盖率: "
            f"{report['blacklist_heuristic_coverage']:.3f}  "
            f"语料出现率: {report['blacklist_corpus_coverage']:.3f}"
        ),
        "黑名单在语料中: " + "、".join(report["blacklist_present"] or ["（无）"]),
        "黑名单语料未出现: "
        + "、".join(report["blacklist_missing_from_corpus"] or ["（无）"]),
        "",
        "节标题出现页数排行",
        "| 节标题 | 页数 | 结构候选 | 在黑名单 |",
        "|---|---:|---|---|",
    ]
    for row in report["heading_rank"][:rank_limit]:
        lines.append(
            f"| {row['title']} | {row['page_count']} | "
            f"{'是' if row['structural_candidate'] else '否'} | "
            f"{'是' if row['in_blacklist'] else '否'} |"
        )
    lines.extend(
        [
            "",
            f"盲区（结构候选且不在黑名单，页数≥{report['min_blind_pages']}）",
            "| 节标题 | 页数 |",
            "|---|---:|",
        ]
    )
    if report["blind_spots"]:
        for row in report["blind_spots"]:
            lines.append(f"| {row['title']} | {row['page_count']} |")
    else:
        lines.append("| （无） | 0 |")
    return "\n".join(lines) + "\n"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--wiki-root",
        type=Path,
        required=True,
        help="知识库 wiki 根（含 entities/concepts）；不写死路径",
    )
    parser.add_argument(
        "--min-blind-pages",
        type=int,
        default=_DEFAULT_MIN_BLIND_PAGES,
        help="盲区页数门槛，默认 20",
    )
    parser.add_argument("--json", action="store_true", help="stdout 打 JSON")
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--md-out", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = audit_wiki(args.wiki_root, min_blind_pages=args.min_blind_pages)
    table = render_table(report)
    if args.json_out:
        args.json_out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.md_out:
        args.md_out.write_text(table, encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
