#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

KB = Path("/Users/lbq/Desktop/c c/知识库")
WIKI = KB / "wiki"


def next_log_id() -> int:
    text = (WIKI / "log.md").read_text(encoding="utf-8")
    ids = [int(x) for x in re.findall(r"^### #(\d+) \|", text, re.M)]
    return max(ids) + 1


def append_log(log_id: int, source: str, date: str, key: str) -> None:
    path = WIKI / "log.md"
    text = path.read_text(encoding="utf-8")
    if f"[[{source}]]" in text:
        return
    entry = f"""
### #{log_id:03d} | 2026-05-29 | ingest | {source} PDF ingest

- **trigger**: user-requested PDF ingest standard workflow
- **source**: [[{source}]]（逻辑红宝书，{date}）
- **created**: [[{source}]] (source note), `raw/{source}.md`
- **updated**: [[index.md]] (revision/count)
- **key**: {key}
"""
    path.write_text(text.rstrip() + "\n" + entry, encoding="utf-8")


def update_index() -> dict[str, int]:
    path = WIKI / "index.md"
    text = path.read_text(encoding="utf-8")
    sources = len(list((WIKI / "sources").glob("*.md")))
    concepts = len(list((WIKI / "concepts").glob("*.md")))
    entities = len(list((WIKI / "entities").glob("*.md")))
    synthesis = len(list((WIKI / "synthesis").glob("*.md")))
    total = sources + concepts + entities + synthesis
    rev = re.search(r"^revision:\s*(\d+)\s*$", text, re.M)
    if rev:
        text = re.sub(r"^revision:\s*\d+\s*$", f"revision: {int(rev.group(1)) + 1}", text, count=1, flags=re.M)
    text = re.sub(
        r"\*\*\d+ 页 \| \d+ 个来源 \| \d+ 个概念 \| \d+ 个实体 \| \d+ 个综合分析\*\*",
        f"**{total} 页 | {sources} 个来源 | {concepts} 个概念 | {entities} 个实体 | {synthesis} 个综合分析**",
        text,
        count=1,
    )
    text = re.sub(r"## Sources（\d+个）", f"## Sources（{sources}个）", text, count=1)
    path.write_text(text, encoding="utf-8")
    return {"sources": sources, "concepts": concepts, "entities": entities, "synthesis": synthesis, "total": total}


def update_source_note_log(log_id: int, source: str) -> None:
    path = WIKI / "sources" / f"{source}.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'^log:\s*\[.*?\]\s*$', f'log: ["#{log_id:03d} PDF ingest source-only observation"]', text, count=1, flags=re.M)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--key", default="")
    parser.add_argument("--key-file", type=Path, default=None)
    parser.add_argument("--log-id", type=int, default=0)
    args = parser.parse_args()
    key = args.key_file.read_text(encoding="utf-8").strip() if args.key_file else args.key
    if not key:
        raise SystemExit("--key or --key-file is required")
    log_id = args.log_id or next_log_id()
    append_log(log_id, args.source, args.date, key)
    update_source_note_log(log_id, args.source)
    counts = update_index()
    print({"log_id": f"#{log_id:03d}", "counts": counts})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
