#!/usr/bin/env python3
"""
Disclosure Archive — Review Queue 生成。

从 manifest.jsonl 按 theme_term / canonical_concept 筛选记录，
分组为 entity_delta / baseline / concept_delta / evidence_index / reject_or_watchlist 候选，
输出到 wiki/raw/disclosures/review-queue/。

只生成候选，不运行 writer，不修改知识库。
"""
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_VAULT = Path.home() / "Desktop" / "c c" / "知识库" / "wiki"
DEFAULT_DISCLOSURES_DIR = DEFAULT_VAULT / "raw" / "disclosures"
DEFAULT_REVIEW_DIR = DEFAULT_DISCLOSURES_DIR / "review-queue"
TZ = timezone(timedelta(hours=8))

# review queue 每组的保留字段
CANDIDATE_FIELDS = [
    "archive_id", "quoted_text", "extracted_facts", "url",
    "source_type", "evidence_layer", "update_type",
    "chain_layer", "role", "confidence",
]


def load_manifest(disclosures_dir: Path) -> list:
    manifest_path = disclosures_dir / "manifest.jsonl"
    if not manifest_path.exists():
        print(f"[ERR] manifest.jsonl 不存在: {manifest_path}", file=sys.stderr)
        sys.exit(1)
    records = []
    with manifest_path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[WARN] manifest 第 {i} 行解析失败: {e}", file=sys.stderr)
    return records


def extract_candidate(rec: dict) -> dict:
    """从完整记录中提取候选所需字段。"""
    return {k: rec.get(k) for k in CANDIDATE_FIELDS}


def group_candidates(records: list) -> dict:
    """按 payload 类型分组。"""
    groups = {
        "entity_delta_candidates": [],
        "baseline_candidates": [],
        "concept_delta_candidates": [],
        "evidence_index_candidates": [],
        "reject_or_watchlist": [],
    }

    for rec in records:
        ut = rec.get("update_type", "")
        el = rec.get("evidence_layer", "")
        es = rec.get("exposure_strength", "")
        go = rec.get("graph_only", False)
        eo = rec.get("exposure_only", False)
        ut_reject = ut == "reject"

        # reject
        if ut_reject:
            groups["reject_or_watchlist"].append(extract_candidate(rec))
            continue

        # entity_delta: hard_delta + L2
        if ut == "hard_delta" and el in ("L2",):
            groups["entity_delta_candidates"].append(extract_candidate(rec))
            continue

        # baseline: baseline + L2
        if ut == "baseline" and el == "L2" and not go and not eo:
            groups["baseline_candidates"].append(extract_candidate(rec))
            continue

        # concept_delta: non-watchlist with chain_layer + role info
        if es != "watchlist" and rec.get("chain_layer") and rec.get("role"):
            groups["concept_delta_candidates"].append(extract_candidate(rec))
            continue

        # evidence_index: non-watchlist, non-graph-only
        if es != "watchlist" and not go:
            groups["evidence_index_candidates"].append(extract_candidate(rec))
            continue

        # fallback
        groups["reject_or_watchlist"].append(extract_candidate(rec))

    return groups


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="从 manifest.jsonl 生成 review queue"
    )
    parser.add_argument("--theme-term", default="",
                        help="筛选 theme_term（留空不过滤）")
    parser.add_argument("--canonical-concept", default="",
                        help="筛选 canonical_concept（留空不过滤）")
    parser.add_argument("--disclosures-dir", default=str(DEFAULT_DISCLOSURES_DIR))
    parser.add_argument("--review-dir", default=str(DEFAULT_REVIEW_DIR))
    parser.add_argument("--dry-run", action="store_true",
                        help="只输出不写入")
    args = parser.parse_args()

    disclosures_dir = Path(args.disclosures_dir)
    review_dir = Path(args.review_dir)

    records = load_manifest(disclosures_dir)

    # ── 筛选 ──
    if args.theme_term:
        records = [r for r in records if r.get("theme_term") == args.theme_term]
    if args.canonical_concept:
        records = [r for r in records if r.get("canonical_concept") == args.canonical_concept]

    if not records:
        print("[ERR] 筛选后无记录", file=sys.stderr)
        sys.exit(1)

    groups = group_candidates(records)

    # ── 组装 ──
    queue = {
        "queue_id": f"queue-{datetime.now(TZ).strftime('%Y%m%d-%H%M%S')}",
        "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "source_count": len(records),
        "filter": {
            "theme_term": args.theme_term or None,
            "canonical_concept": args.canonical_concept or None,
        },
        "groups": {k: v for k, v in groups.items() if v},
        "group_counts": {k: len(v) for k, v in groups.items() if v},
        "safety_statement": (
            "此为 review queue 草案，仅用于人工审核参考。"
            "未运行 entity_delta_writer / baseline_writer / concept_writer，"
            "未修改 entities/concepts/relations。"
            "审核通过后由人工或主流程驱动写入。"
        ),
    }

    # ── 输出摘要 ──
    print(f"Review Queue 生成: {queue['queue_id']}")
    print(f"  源记录数: {len(records)}")
    print(f"  分组:")
    for group_name, candidates in groups.items():
        if candidates:
            print(f"    {group_name}: {len(candidates)} 条")
    print()

    if args.dry_run:
        print("[DRY RUN] 内容:")
        print(json.dumps(queue, ensure_ascii=False, indent=2))
        return

    # ── 写入 ──
    review_dir.mkdir(parents=True, exist_ok=True)
    filename = f"review-queue_{args.theme_term or 'all'}_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    path = review_dir / filename
    path.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n")
    print(f"[OK] 写入: {path}")
    print(f"     共 {len(records)} 条记录，{sum(len(v) for v in groups.values())} 个候选")


if __name__ == "__main__":
    main()
