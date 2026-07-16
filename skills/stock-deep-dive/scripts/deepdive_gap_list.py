#!/usr/bin/env python3
"""列出知识库里还没做 DeepDive 的 concept 和个股（entity_type=上市公司）。

判定「已有 DeepDive」：
- concept：frontmatter sources/log 或正文引用了 *DeepDive*/*Deep Dive*/*深挖* 源。
- 个股：entity 页出现 DeepDive/深挖 引用。

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


def _scan(dir_path: Path, require_listed: bool) -> list[dict[str, str]]:
    rows = []
    for page in sorted(dir_path.glob("*.md")):
        text = page.read_text(encoding="utf-8", errors="replace")
        fm = _frontmatter(text)
        if require_listed and "上市公司" not in fm.get("entity_type", ""):
            continue
        if DD_RE.search(text):
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
    args = ap.parse_args()

    wiki = Path(args.wiki)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    concepts = _scan(wiki / "concepts", require_listed=False)
    stocks = _scan(wiki / "entities", require_listed=True)

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
