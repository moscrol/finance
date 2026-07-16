#!/usr/bin/env python3
"""列出知识库里还没做 DeepDive 的 concept 和个股（entity_type=上市公司）。

判定「已有 DeepDive」（任一命中即算已做）：
- 页面正文/frontmatter 出现 DeepDive/Deep Dive/深挖；
- wiki/sources 里存在标题含该页面名、且命中深挖类命名的源文件
  （DeepDive/深挖/IMA canonical/研究报告/深度研究/信息池/题材地图）；
- 个股：entity 页含 IMA 逻辑卡标记（「IMA 最新逻辑跟踪」/「最新逻辑卡」/「IMA stock logic」）。

增量模式：--state <json>。首跑写入全量清单快照；之后再跑只输出上次快照后
新增的缺口（新建页面 or 从「已有」变回「缺口」不会发生，只看新增页面），
并把快照滚动更新。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DD_RE = re.compile(r"deep[\s_-]?dive|深挖", re.IGNORECASE)
IMA_STOCK_RE = re.compile(r"IMA 最新逻辑跟踪|最新逻辑卡|IMA stock logic")
DD_SOURCE_RE = re.compile(
    r"deep[\s_-]?dive|深挖|IMA canonical|研究报告|深度研究|信息池|题材地图", re.IGNORECASE
)


def _covered_by_sources(sources_dir: Path) -> list[str]:
    return [p.stem for p in sources_dir.glob("*.md") if DD_SOURCE_RE.search(p.stem)]


FM_FIELD = re.compile(r"^([a-z_]+):\s*(.*)$")


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    fields: dict[str, str] = {}
    for line in text[3:end].splitlines():
        match = FM_FIELD.match(line.strip())
        if match:
            fields[match.group(1)] = match.group(2)
    return fields


def _hierarchy(graph_path: Path) -> tuple[set[str], set[str]]:
    parents: set[str] = set()
    children: set[str] = set()
    if graph_path.exists():
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        hier = ("is_subconcept_of", "子领域", "细分", "belongs_to", "题材雷达子方向", "子方向", "子工艺")
        for rel in graph.get("relations", []):
            rel_type = str(rel.get("type") or "")
            if rel_type in hier or rel_type.startswith("上位"):
                children.add(str(rel.get("from") or ""))
                parents.add(str(rel.get("to") or ""))
    return parents, children


def _scan(
    dir_path: Path,
    require_listed: bool,
    main_filter: tuple[set[str], set[str]] | None = None,
    dd_source_titles: list[str] | None = None,
) -> list[dict[str, str]]:
    rows = []
    for page in sorted(dir_path.glob("*.md")):
        text = page.read_text(encoding="utf-8", errors="replace")
        fm = _frontmatter(text)
        if require_listed and "上市公司" not in fm.get("entity_type", ""):
            continue
        if DD_RE.search(text):
            continue
        if require_listed and IMA_STOCK_RE.search(text):
            continue
        if dd_source_titles and any(page.stem in title for title in dd_source_titles):
            continue
        if main_filter is not None:
            parents, children = main_filter
            name = page.stem
            n_tickers = len(re.findall(r"\d{6}", fm.get("tickers", "")))
            is_main = name in parents or (name not in children and n_tickers >= 3)
            if not is_main:
                continue
        rows.append(
            {
                "name": page.stem,
                "tickers": fm.get("tickers", ""),
                "updated": fm.get("updated", ""),
                "revision": fm.get("revision", ""),
            }
        )
    rows.sort(key=lambda r: (r["updated"], r["revision"]), reverse=True)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wiki", default="/Users/a77/knowledge-base-private/wiki")
    ap.add_argument("--out-dir", default="/tmp/deepdive_gaps")
    ap.add_argument("--state", default=None, help="增量模式状态文件；不传则每次全量")
    ap.add_argument(
        "--concept-scope",
        choices=["main", "all"],
        default="main",
        help="main=只列主概念（concept_graph 层级边里的父节点，或非子节点且 tickers>=3）；all=全部",
    )
    args = ap.parse_args()

    wiki = Path(args.wiki)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    main_filter = None
    if args.concept_scope == "main":
        main_filter = _hierarchy(wiki / "relations" / "concept_graph.json")
    dd_source_titles = _covered_by_sources(wiki / "sources")
    concepts = _scan(
        wiki / "concepts",
        require_listed=False,
        main_filter=main_filter,
        dd_source_titles=dd_source_titles,
    )
    stocks = _scan(wiki / "entities", require_listed=True, dd_source_titles=dd_source_titles)

    prev: dict[str, list[str]] = {"concepts": [], "stocks": []}
    if args.state and Path(args.state).exists():
        prev = json.loads(Path(args.state).read_text(encoding="utf-8"))

    for label, rows in (("concepts", concepts), ("stocks", stocks)):
        seen = set(prev.get(label) or [])
        emit = [r for r in rows if r["name"] not in seen] if seen else rows
        mode = "增量" if seen else "全量"
        out = out_dir / f"deepdive-gap-{label}.md"
        lines = [
            f"# 待补 DeepDive：{label}（{mode}，共 {len(emit)} 条 / 缺口总数 {len(rows)}）",
            "",
            "| 名称 | tickers | updated | revision |",
            "|---|---|---|---|",
        ]
        lines += [
            f"| {r['name']} | {r['tickers'] or '-'} | {r['updated'] or '-'} | {r['revision'] or '-'} |"
            for r in emit
        ]
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{label}: {mode} {len(emit)} 条 -> {out}")

    if args.state:
        Path(args.state).write_text(
            json.dumps(
                {
                    "concepts": [r["name"] for r in concepts],
                    "stocks": [r["name"] for r in stocks],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
