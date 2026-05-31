#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

DEFAULT_VAULT = Path("/Users/lbq/Desktop/c c/知识库/wiki")
DEFAULT_BACKFILL = DEFAULT_VAULT / "raw/entity-delta-backfill"


def safe_filename(value):
    return re.sub(r'[/:*?"<>|\n\r\t]+', "_", str(value)).strip()


def load_candidates(backfill_dir):
    files = sorted(backfill_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    idx = next(i for i, p in enumerate(files) if "华为芯片" in p.name)
    candidates = []
    for payload_path in files[idx + 1 : idx + 16]:
        data = json.loads(payload_path.read_text(encoding="utf-8"))
        source = data.get("source_name") or payload_path.stem.replace(".entity-delta", "")
        for update in data.get("updates", []):
            if not update.get("graph_only"):
                company = update.get("company")
                if company:
                    candidates.append((company, source))
    return candidates


def remove_source_section(text, source):
    pattern = re.compile(
        r"^### \d{4}-\d{2}-\d{2}｜" + re.escape(source) + r"\n.*?(?=^### \d{4}-\d{2}-\d{2}｜|^## |\Z)",
        re.M | re.S,
    )
    return pattern.sub("", text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--backfill-dir", type=Path, default=DEFAULT_BACKFILL)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    entities_dir = args.vault / "entities"
    changed = []
    missing = []
    total_sections = 0
    for company, source in load_candidates(args.backfill_dir):
        path = entities_dir / f"{safe_filename(company)}.md"
        if not path.exists():
            missing.append(company)
            continue
        text = path.read_text(encoding="utf-8")
        marker = re.compile(r"^### \d{4}-\d{2}-\d{2}｜" + re.escape(source) + r"\n", re.M)
        count = len(marker.findall(text))
        if not count:
            continue
        new_text = remove_source_section(text, source)
        if new_text == text:
            continue
        total_sections += count
        changed.append({"file": str(path), "company": company, "source": source, "sections": count})
        if args.apply:
            backup = path.with_suffix(path.suffix + ".bak-fullmd-cleanup")
            if not backup.exists():
                backup.write_text(text, encoding="utf-8")
            path.write_text(new_text.rstrip() + "\n", encoding="utf-8")

    print(json.dumps({
        "apply": args.apply,
        "changed_files": len({item["file"] for item in changed}),
        "removed_sections": total_sections,
        "missing_entities": sorted(set(missing)),
        "changes": changed,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
