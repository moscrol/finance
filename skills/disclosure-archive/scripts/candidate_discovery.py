#!/usr/bin/env python3
"""
Disclosure Archive — Candidate Discovery。

当用户只给 theme_term 时，输出候选公司列表（最多 10 家），
供下一步选择进入实际 archive。

候选公司不能被当作已证实核心公司，仅作为调研起点。
"""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_VAULT = Path.home() / "Desktop" / "c c" / "知识库" / "wiki"
DEFAULT_BATCHES_DIR = DEFAULT_VAULT / "raw" / "disclosures" / "batches"
TZ = timezone(timedelta(hours=8))

VALID_CHAIN_LAYERS = {
    "upstream_materials", "upstream_equipment",
    "midstream_manufacturing", "midstream_service",
    "downstream_application", "ecosystem",
}
VALID_PRIORITIES = {"high", "medium", "low"}
VALID_CANDIDATE_SOURCES = {
    "knowledge_base", "web_search", "industry_report",
    "supply_chain_map", "user_input", "other",
}


def validate_candidate(c: dict, index: int) -> list:
    """校验单条候选公司，返回错误列表。"""
    errors = []
    prefix = f"候选 #{index}"

    required = [
        "company", "code",
        "chain_layer", "expected_role", "candidate_source",
        "candidate_reason", "priority",
    ]
    for field in required:
        val = c.get(field)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            errors.append(f"{prefix} 缺少必填字段: {field}")

    if c.get("chain_layer") and c["chain_layer"] not in VALID_CHAIN_LAYERS:
        errors.append(f"{prefix} chain_layer 非法值: {c['chain_layer']}")

    if c.get("priority") and c["priority"] not in VALID_PRIORITIES:
        errors.append(f"{prefix} priority 非法值: {c['priority']}")

    if c.get("candidate_source") and c["candidate_source"] not in VALID_CANDIDATE_SOURCES:
        errors.append(f"{prefix} candidate_source 非法值: {c['candidate_source']}")

    return errors


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Candidate Discovery — 输出候选公司列表，供下一步选择归档"
    )
    parser.add_argument("--theme-term", required=True, help="题材名称")
    parser.add_argument("--canonical-concept", required=True, help="规范概念名")
    parser.add_argument("--aliases", nargs="*", default=[], help="别名列表")
    parser.add_argument("--candidates", required=True, nargs="+",
                        help="候选公司 JSON 文件路径，或内联 JSON")
    parser.add_argument("--batches-dir", default=str(DEFAULT_BATCHES_DIR),
                        help="输出目录（默认为 batches/）")
    parser.add_argument("--dry-run", action="store_true", help="只校验不写入")
    args = parser.parse_args()

    # ── 解析候选公司列表 ──
    candidates = []
    for src in args.candidates:
        data = None
        # Try JSON parse first (handles inline JSON strings)
        try:
            data = json.loads(src)
        except json.JSONDecodeError:
            # Not valid JSON — try as file path
            path = Path(src)
            if path.exists():
                data = json.loads(path.read_text())
            else:
                print(f"[ERR] 无法解析为 JSON 且不是有效文件路径: {src}", file=sys.stderr)
                sys.exit(1)

        if isinstance(data, list):
            candidates.extend(data)
        else:
            candidates.append(data)

    if len(candidates) > 10:
        print(f"[WARN] 候选公司超过 10 家（{len(candidates)}），将截断至前 10 家", file=sys.stderr)
        candidates = candidates[:10]

    # ── 从 CLI 继承 theme_term / canonical_concept ──
    for c in candidates:
        if "theme_term" not in c or not c["theme_term"]:
            c["theme_term"] = args.theme_term
        if "canonical_concept" not in c or not c["canonical_concept"]:
            c["canonical_concept"] = args.canonical_concept

    if not candidates:
        print("[ERR] 候选公司列表为空", file=sys.stderr)
        sys.exit(1)

    # ── 校验 ──
    all_errors = []
    for i, c in enumerate(candidates, 1):
        all_errors.extend(validate_candidate(c, i))

    if all_errors:
        print("候选公司校验失败:", file=sys.stderr)
        for e in all_errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    # ── 统计 ──
    high_priority = [c for c in candidates if c.get("priority") == "high"]
    chain_layers = set(c.get("chain_layer", "") for c in candidates)
    priority_counts = {}
    for c in candidates:
        p = c.get("priority", "unknown")
        priority_counts[p] = priority_counts.get(p, 0) + 1

    # ── 输出 ──
    discovery = {
        "discovery_id": f"disc-{datetime.now(TZ).strftime('%Y%m%d')}-discovery",
        "theme_term": args.theme_term,
        "canonical_concept": args.canonical_concept,
        "aliases": args.aliases,
        "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "candidate_count": len(candidates),
        "high_priority_count": len(high_priority),
        "by_chain_layer": list(chain_layers),
        "by_priority": priority_counts,
        "candidates": candidates,
        "recommendation": (
            f"建议选择 priority=high 的前 3-5 家进入实际 archive。"
            f"当前高优先级 {len(high_priority)} 家。"
        ),
        "safety_statement": (
            "此为候选发现阶段，尚未产生任何归档记录。"
            "未修改 entities/concepts/relations，未运行 writer。"
        ),
    }

    # ── 写入 ──
    if args.dry_run:
        print("[DRY RUN] 候选发现结果:")
        print(json.dumps(discovery, ensure_ascii=False, indent=2))
        return

    batches_dir = Path(args.batches_dir)
    batches_dir.mkdir(parents=True, exist_ok=True)

    filename = f"discovery_{args.theme_term}_{datetime.now(TZ).strftime('%Y%m%d_%H%M%S')}.json"
    path = batches_dir / filename
    path.write_text(json.dumps(discovery, ensure_ascii=False, indent=2) + "\n")
    print(f"[OK] 候选发现结果写入: {path}")
    print(f"     候选公司: {len(candidates)} 家")
    print(f"     高优先级: {len(high_priority)} 家")
    print(f"     产业链层: {', '.join(sorted(chain_layers))}")
    print(f"     推荐: {discovery['recommendation']}")


if __name__ == "__main__":
    main()
