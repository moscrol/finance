from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "market_feature_store" / "exports"

# Map a ledger gap/review action to an existing knowledge-base dry-run/read-only
# command. These commands are *rendered only* — this planner never executes them.
# Writing remains gated behind the KB scripts' own --apply flags + human review.
GAP_ACTIONS: dict[str, dict[str, str]] = {
    "missing_concept": {
        "command_kind": "kb_audit_missing_concepts",
        "risk": "low",
        "mode": "read_only",
        "template": "python3 scripts/audit_missing_concepts.py --vault {wiki}",
        "note": "先只读审计 missing concept，判断是真实概念、别名还是污染词，再决定是否建页。",
    },
    "missing_evidence": {
        "command_kind": "kb_materialize_source_stubs_dry_run",
        "risk": "low",
        "mode": "dry_run",
        "template": "python3 scripts/materialize_missing_source_stubs.py --vault {wiki}",
        "note": "默认 dry-run（would_create），找到 raw/source 后再加 --apply 落 source trace。",
    },
    "missing_entity_exposures": {
        "command_kind": "kb_ima_stock_ingest_dry_run",
        "risk": "low",
        "mode": "dry_run",
        "template": "python3 scripts/ima_stock_ingest_batch.py --vault {kb_root}",
        "note": "默认 dry-run 分类；确认个股卡 ready 后再加 --apply 写 entity/evidence。",
    },
    "placeholder_market_theme": {
        "command_kind": "manual_name_theme",
        "risk": "manual",
        "mode": "manual",
        "template": "",
        "note": "题材名是占位（如连板未映射），需要人工先确认题材名再进入补库。",
    },
}

DEFAULT_ACTION = {
    "command_kind": "manual_review",
    "risk": "manual",
    "mode": "manual",
    "template": "",
    "note": "未识别的缺口类型，需要人工判断。",
}

ACTION_ORDER = {"already_indexed": 0, "read_only": 1, "dry_run": 2, "manual": 3}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing input file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"json root is not an object: {path}")
    return data


def plan_item(item: dict[str, Any], wiki: Path, kb_root: Path) -> dict[str, Any]:
    gap_type = str(item.get("gap_type") or "")
    probe = item.get("index_probe") if isinstance(item.get("index_probe"), dict) else {}
    already_indexed = bool(probe.get("rag_indexed"))
    spec = GAP_ACTIONS.get(gap_type, DEFAULT_ACTION) if gap_type else DEFAULT_ACTION
    if already_indexed:
        action_mode = "already_indexed"
        command = ""
        risk = "none"
        command_kind = "skip_already_indexed"
        note = "概念页已在 RAG index 中，无需补库。"
    else:
        action_mode = spec["mode"]
        command = spec["template"].format(wiki=wiki, kb_root=kb_root) if spec["template"] else ""
        risk = spec["risk"]
        command_kind = spec["command_kind"]
        note = spec["note"]
    return {
        "id": item.get("id"),
        "ingest_status": item.get("ingest_status"),
        "index_status": item.get("index_status"),
        "gap_type": gap_type,
        "theme": item.get("theme"),
        "canonical_concept": item.get("canonical_concept"),
        "rank": item.get("rank") or 0,
        "action_mode": action_mode,
        "command_kind": command_kind,
        "risk": risk,
        "recommended_command": command,
        "note": note,
    }


def build_action_plan(indexed_ledger: dict[str, Any], wiki: Path, kb_root: Path, ledger_path: Path) -> dict[str, Any]:
    plans = []
    for item in as_list(indexed_ledger.get("items")):
        if not isinstance(item, dict):
            continue
        # Only items with a real gap need a write/ingest action.
        if not item.get("gap_type"):
            continue
        plans.append(plan_item(item, wiki, kb_root))
    plans.sort(key=lambda row: (ACTION_ORDER.get(str(row.get("action_mode")), 9), -int(row.get("rank") or 0), str(row.get("id") or "")))
    return {
        "trade_date": indexed_ledger.get("trade_date") or "",
        "source": "ingest-action-plan",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execute": False,
        "inputs": {
            "indexed_ledger": str(ledger_path),
            "knowledge_wiki": str(wiki),
            "knowledge_base_root": str(kb_root),
        },
        "item_count": len(plans),
        "action_mode_counts": dict(sorted(Counter(str(p["action_mode"]) for p in plans).items())),
        "command_kind_counts": dict(sorted(Counter(str(p["command_kind"]) for p in plans).items())),
        "items": plans,
    }


def md_table(items: list[dict[str, Any]]) -> str:
    lines = [
        "| Mode | Risk | Gap | 题材 | Concept | Recommended (dry-run) Command |",
        "|---|---|---|---|---|---|",
    ]
    for item in items:
        command = item.get("recommended_command") or item.get("note") or "-"
        lines.append(
            "| {mode} | {risk} | {gap} | {theme} | {concept} | `{cmd}` |".format(
                mode=item.get("action_mode") or "-",
                risk=item.get("risk") or "-",
                gap=item.get("gap_type") or "-",
                theme=str(item.get("theme") or "-").replace("|", "/"),
                concept=str(item.get("canonical_concept") or "-").replace("|", "/"),
                cmd=str(command).replace("|", "/"),
            )
        )
    return "\n".join(lines)


def render_markdown(payload: dict[str, Any]) -> str:
    items = [item for item in as_list(payload.get("items")) if isinstance(item, dict)]
    return "\n".join([
        f"# {payload.get('trade_date')} Ingest Action Plan (read-only)",
        "",
        "> 本计划只渲染已有知识库 dry-run / 只读命令；不执行任何写库动作。写库仍需各脚本自身 --apply + 人工确认。",
        "",
        "## 摘要",
        "",
        f"- **item_count**: {payload.get('item_count')}",
        f"- **action_mode_counts**: `{json.dumps(payload.get('action_mode_counts', {}), ensure_ascii=False)}`",
        f"- **command_kind_counts**: `{json.dumps(payload.get('command_kind_counts', {}), ensure_ascii=False)}`",
        "",
        "## 明细",
        "",
        md_table(items),
        "",
    ])


def output_paths_for(trade_date: str) -> tuple[Path, Path]:
    return (
        EXPORT_DIR / f"{trade_date}-ingest-action-plan.json",
        EXPORT_DIR / f"{trade_date}-ingest-action-plan.md",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render read-only ingest action plan from an indexed ingest ledger")
    parser.add_argument("date")
    parser.add_argument("--indexed-ledger", dest="ledger_path")
    parser.add_argument("--kb-root", required=True)
    parser.add_argument("--out-json", dest="out_json")
    parser.add_argument("--out-md", dest="out_md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ledger_path = Path(args.ledger_path).expanduser() if args.ledger_path else EXPORT_DIR / f"{args.date}-ingest-status-ledger-indexed.json"
    kb_root = Path(args.kb_root).expanduser()
    wiki = kb_root / "wiki"
    out_json, out_md = output_paths_for(args.date)
    if args.out_json:
        out_json = Path(args.out_json).expanduser()
    if args.out_md:
        out_md = Path(args.out_md).expanduser()
    payload = build_action_plan(load_json(ledger_path), wiki, kb_root, ledger_path)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown(payload), encoding="utf-8")
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    print(f"action_mode_counts={json.dumps(payload['action_mode_counts'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
