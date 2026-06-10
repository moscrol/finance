#!/usr/bin/env python3
"""opinion-store: 观点事件库（opinion-cross 的沉淀层）。

opinion-cross 是"单篇提纯器"；本脚本是它的**累积层**：把每篇研报提纯出的标的
展平成结构化「观点事件」行，append 进一个 append-only 的 JSONL 库（类公告库）。
N 篇研报沉淀进同一个库后，价值从"累积 + 回溯"涌现：
  - 跨研报聚合：同一标的/方向被反复提及 → 认知升温（单篇看不出，库里一眼可见）。
  - （后续）盘面回溯：事件带时间戳，可 T+N 拉盘面验证命中率、升 Tier1。

设计原则：
- **不碰 KB ground truth**：库是派生数据文件（默认 `<vault>/raw/theme-radar/opinion-events.jsonl`），
  不写 concepts/entities/relations。硬料若要进 KB，仍走 disclosure-archive 的人工审核 `--apply`。
- **append-only + 去重**：同(报告日期+来源+标的+硬证据指纹)重复入库自动跳过；
  不同日期/来源算新事件，这样才能看出"同标的被反复提"。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opinion_cross as oc  # noqa: E402  (复用单篇提纯逻辑)


SCHEMA_VERSION = 1


def default_store(vault: Path) -> Path:
    return vault / "raw" / "theme-radar" / "opinion-events.jsonl"


def _evidence_fingerprint(opp: dict) -> str:
    hp = opp.get("hardness", {})
    basis = hp.get("hard") or hp.get("soft") or [opp.get("kb", {}).get("concept", "")]
    return " | ".join(basis)[:200]


def make_event_id(report_date: str, source: str, target: str, fingerprint: str) -> str:
    raw = f"{report_date}|{source}|{target}|{fingerprint}"
    return "oce-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def opportunity_to_event(
    opp: dict, *, report_date: str, ingested_at: str, source: str, report_title: str, term: str
) -> dict:
    hp = opp.get("hardness", {})
    kb = opp.get("kb", {})
    stance = opp.get("stance", {})
    fingerprint = _evidence_fingerprint(opp)
    return {
        "event_id": make_event_id(report_date, source, opp.get("target", ""), fingerprint),
        "schema_version": SCHEMA_VERSION,
        "ingested_at": ingested_at,
        "report_date": report_date,
        "source": source,
        "report_title": report_title,
        "term": term,
        "target": opp.get("target", ""),
        "concept": kb.get("concept", ""),
        "chain_layer": kb.get("chain_layer", ""),
        "kb_strength": kb.get("strength", ""),
        "kb_fact_hardness": kb.get("kb_fact_hardness", ""),
        "stance": stance.get("stance", ""),
        "hardness": hp.get("dominant", ""),
        "hard_evidence": hp.get("hard", []),
        "soft_claims": hp.get("soft", []),
        "noise": hp.get("noise", []),
        "catalysts": opp.get("catalysts", []),
        "expectation_gap": stance.get("expectation_gap", []),
        "resonance_tier": opp.get("resonance_tier", "").split("：")[0].strip(),
        "mention_count": opp.get("mention_count", 0),
    }


def load_store(store: Path) -> list[dict]:
    if not store.exists():
        return []
    rows = []
    for line in store.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def append_events(store: Path, events: list[dict]) -> tuple[int, int]:
    existing = load_store(store)
    seen = {e.get("event_id") for e in existing}
    added, skipped = 0, 0
    store.parent.mkdir(parents=True, exist_ok=True)
    with store.open("a", encoding="utf-8") as fh:
        for ev in events:
            if ev["event_id"] in seen:
                skipped += 1
                continue
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
            seen.add(ev["event_id"])
            added += 1
    return added, skipped


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------
def cmd_ingest(args) -> int:
    vault = Path(args.vault).expanduser()
    store = Path(args.store).expanduser() if args.store else default_store(vault)
    text = Path(args.input).expanduser().read_text(encoding="utf-8")
    data = oc.build(args.term, text, vault)

    report_date = args.date or data.get("generated_at") or _dt.date.today().isoformat()
    ingested_at = _dt.date.today().isoformat()
    source = args.source or (data.get("sources") or ["未署名"])[0]

    events = [
        opportunity_to_event(
            opp,
            report_date=report_date,
            ingested_at=ingested_at,
            source=source,
            report_title=args.title,
            term=data.get("term") or args.term,
        )
        for opp in data.get("opportunities", [])
    ]
    added, skipped = append_events(store, events)
    print(
        json.dumps(
            {
                "store": str(store),
                "report_date": report_date,
                "source": source,
                "extracted": len(events),
                "added": added,
                "skipped_duplicate": skipped,
                "store_total": len(load_store(store)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_list(args) -> int:
    store = Path(args.store).expanduser()
    rows = load_store(store)
    if args.target:
        rows = [r for r in rows if r.get("target") == args.target]
    if args.term:
        rows = [r for r in rows if r.get("term") == args.term]
    rows.sort(key=lambda r: (r.get("report_date", ""), r.get("target", "")))
    print("| 报告日期 | 标的 | 题材 | Tier | 硬度 | 多空 | 来源 |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        print(
            f"| {r.get('report_date','')} | {r.get('target','')} | {r.get('concept','')} | "
            f"{r.get('resonance_tier','')} | {r.get('hardness','')} | {r.get('stance','')} | {r.get('source','')} |"
        )
    return 0


def _tier_rank(t: str) -> int:
    return {"Tier 1": 0, "Tier 2": 1, "Tier 3": 2}.get(t, 3)


def cmd_summary(args) -> int:
    """跨研报聚合：同标的被多少篇/多少天提及、硬度是否升级、多空是否分歧。"""
    store = Path(args.store).expanduser()
    rows = load_store(store)
    if args.term:
        rows = [r for r in rows if r.get("term") == args.term]

    by_target: dict[str, list[dict]] = {}
    for r in rows:
        by_target.setdefault(r.get("target", ""), []).append(r)

    agg = []
    for target, evs in by_target.items():
        dates = sorted({e.get("report_date", "") for e in evs})
        sources = sorted({e.get("source", "") for e in evs})
        stances = {e.get("stance", "") for e in evs}
        best_tier = min((e.get("resonance_tier", "") for e in evs), key=_tier_rank)
        has_hard = any(e.get("hard_evidence") for e in evs)
        agg.append(
            {
                "target": target,
                "concept": next((e.get("concept") for e in evs if e.get("concept")), ""),
                "mentions": len(evs),
                "days": len(dates),
                "sources": len(sources),
                "best_tier": best_tier,
                "has_hard_evidence": has_hard,
                "stance_split": "多空分歧" if {"看多", "看空"} <= stances else "、".join(s for s in stances if s),
                "first_seen": dates[0] if dates else "",
                "last_seen": dates[-1] if dates else "",
            }
        )
    # 排序：被提及越多、跨天越多、Tier 越高 → 越靠前（认知升温优先）
    agg.sort(key=lambda a: (_tier_rank(a["best_tier"]), -a["mentions"], -a["days"]))

    print(f"# 观点事件库聚合视图（共 {len(rows)} 条事件 / {len(by_target)} 个标的）")
    print()
    print("| 标的 | 题材 | 被提及 | 跨天 | 来源数 | 最佳Tier | 硬证据 | 多空 | 首见 | 最近 |")
    print("|---|---|---:|---:|---:|---|---|---|---|---|")
    for a in agg:
        print(
            f"| {a['target']} | {a['concept']} | {a['mentions']} | {a['days']} | {a['sources']} | "
            f"{a['best_tier']} | {'🟢' if a['has_hard_evidence'] else '—'} | {a['stance_split']} | "
            f"{a['first_seen']} | {a['last_seen']} |"
        )
    print()
    print("> 被多篇/多天/多来源反复提及且出现硬证据的标的 = 认知升温候选；")
    print("> 接盘面回溯（T+N）后即可把「市场热点」维度补齐、升至 Tier 1。")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="观点事件库：opinion-cross 的累积/沉淀层")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest", help="把一篇研报提纯并入库（append + 去重）")
    p_ing.add_argument("--term", default="", help="题材名（可选）")
    p_ing.add_argument("--input", required=True, help="研报/观点流文本文件")
    p_ing.add_argument("--date", default="", help="报告日期 YYYY-MM-DD（默认今天）")
    p_ing.add_argument("--source", default="", help="来源/机构（默认取文中首个【】或'未署名'）")
    p_ing.add_argument("--title", default="", help="研报标题（可选）")
    p_ing.add_argument("--vault", default=str(oc.DEFAULT_VAULT), help="知识库 wiki 根目录")
    p_ing.add_argument("--store", default="", help="事件库 JSONL 路径（默认 <vault>/raw/theme-radar/opinion-events.jsonl）")
    p_ing.set_defaults(func=cmd_ingest)

    p_list = sub.add_parser("list", help="列出库内事件")
    p_list.add_argument("--store", required=True)
    p_list.add_argument("--target", default="")
    p_list.add_argument("--term", default="")
    p_list.set_defaults(func=cmd_list)

    p_sum = sub.add_parser("summary", help="跨研报聚合：认知升温视图")
    p_sum.add_argument("--store", required=True)
    p_sum.add_argument("--term", default="")
    p_sum.set_defaults(func=cmd_summary)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
