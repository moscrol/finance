#!/usr/bin/env python3
"""consensus-bridge: 观点事件库 → per-theme 信号 → 持久化进 theme_signals.json。

把 opinion-events.jsonl 聚合成 theme-radar `radar.py` 能直接读的 per-theme 信号，
写进 `wiki/relations/theme_signals.json`，让雷达里长期「待补」的三块变成真数据：

  - **信号层**（radar 的 `## 信号层` / 三维交叉读 theme_signals 的
    order_signals / industry_progress / market_heat / sell_side_coverage）。
  - **认知演变时间线**（radar `recognition_timeline_section`，原来「待补：需要补充从
    暗流到一致认同的认知演变时间线」）。
  - **多方向发酵进度横向对比**（radar `progress_ruler_section`，原来「待补：需要补充
    相邻方向横向对比表」）。
  - 顺带给方向级**操作建议**（radar `action_plan_section`）。

★ 沉淀层适配：本桥**完全复用 consensus_staging 的下限语义**——
  阶段是「已入库证据至少支撑到哪一阶」，库 append-only 回补只升不降；单来源软料进观察池。
  写入的每个 theme 条目都带 `_meta.note` 提醒「随回补上升、为下限」。

幂等：每次都从整库重算覆盖 `_source==consensus_bridge` 的条目；**不碰**其它来源写的 theme
条目（保留人工/其它脚本写的信号）。只读 opinion 库，对 theme_signals 做 upsert。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opinion_store import load_store  # noqa: E402
from consensus_staging import (  # noqa: E402
    WATCH,
    coverage_label,
    cumulative_signals,
    decide_stage,
    fact_track,
    recognition_score,
    stage_label,
    timeline_for_target,
    upgrade_trigger,
    _stage_rank,
)

BRIDGE_TAG = "consensus_bridge"

NOTE = (
    "源自观点事件库(consensus_bridge)：阶段为『当前已入库证据』的认同度下限，"
    "库 append-only+去重、持续回补卖方研报 → 广度(N源/N天)随回补单调上升、仅作覆盖度参考；"
    "事实硬度轨(🟢硬证据/催化)robust 不随回补变。盘面兑现维待 b。"
)


def _short(text: str, limit: int = 80) -> str:
    t = " ".join(str(text or "").split())
    return t[:limit] + ("…" if len(t) > limit else "")


def _priority_bucket(stage: str) -> str:
    return {
        "一致认同": "最优先",
        "催化共振": "最优先",
        "第一轮": "次优先",
        "萌芽": "观察",
        WATCH: "暂不跟",
    }.get(stage, "观察")


def _evidence_snippets(events: list[dict], key: str, limit: int = 6) -> list[str]:
    """从一组事件里抽 key(hard_evidence/catalysts/soft_claims) 的去重短句，带标的前缀。"""
    out: list[str] = []
    seen: set[str] = set()
    for e in events:
        for item in e.get(key, []) or []:
            snip = _short(item, 70)
            if not snip or snip in seen:
                continue
            seen.add(snip)
            tgt = e.get("target", "")
            out.append(f"{tgt}：{snip}" if tgt else snip)
            if len(out) >= limit:
                return out
    return out


def build_recognition_timeline(term_events: list[dict]) -> list[dict]:
    """term 级认知演变：把整 term 事件按研报日累积，逐日截面阶段+当日驱动。"""
    by_date: dict[str, list[dict]] = {}
    for e in term_events:
        by_date.setdefault(e.get("report_date", ""), []).append(e)
    steps = timeline_for_target(term_events)
    rows = []
    for s in steps:
        day_evs = by_date.get(s["date"], [])
        directions = sorted({e.get("concept", "") for e in day_evs if e.get("concept")})
        entities = sorted({e.get("target", "") for e in day_evs if e.get("target")})
        hard = _evidence_snippets(day_evs, "hard_evidence", 1)
        cat = _evidence_snippets(day_evs, "catalysts", 1)
        soft = _evidence_snippets(day_evs, "soft_claims", 1)
        ev = hard or cat or soft
        sig = cumulative_signals([e for d in by_date if d <= s["date"] for e in by_date[d]])
        rows.append({
            "time_window": s["date"],
            "event": _short(s["reason"], 110),
            "recognition_stage": stage_label(s["stage"]) if s["jumped"] else s["stage"],
            "market_consensus": f"{sig['sources']}源/{sig['days']}天({coverage_label(sig)})",
            "fact_level": fact_track(sig),
            "direction": "、".join(directions[:4]),
            "related_entities": entities[:8],
            "evidence_summary": _short(ev[0], 100) if ev else "",
        })
    return rows


def build_progress_ruler(term_events: list[dict]) -> list[dict]:
    """term 下各方向(concept)横向对比发酵进度（下限）。"""
    by_concept: dict[str, list[dict]] = {}
    for e in term_events:
        c = e.get("concept", "")
        if c:
            by_concept.setdefault(c, []).append(e)
    rows = []
    for concept, evs in by_concept.items():
        sig = cumulative_signals(evs)
        stage, reasons = decide_stage(sig)
        targets = sorted({e.get("target", "") for e in evs if e.get("target")})
        hard_targets = sorted({e.get("target", "") for e in evs if e.get("hard_evidence") and e.get("target")})
        rep = hard_targets[0] if hard_targets else (
            max(targets, key=lambda t: sum(1 for e in evs if e.get("target") == t)) if targets else ""
        )
        rows.append({
            "direction": concept,
            "current_stage": stage_label(stage),
            "stage_position": recognition_score(stage, sig),
            "stage_reason": _short("；".join(reasons), 80),
            "related_catalyst": rep,
            "next_validation": upgrade_trigger(stage, sig),
            "_rank": _stage_rank(stage),
        })
    rows.sort(key=lambda r: (r["_rank"], r["stage_position"]), reverse=True)
    n = len(rows)
    for i, r in enumerate(rows):
        if n <= 1:
            r["relative_position"] = "—"
        elif i < n / 3:
            r["relative_position"] = "领先"
        elif i < 2 * n / 3:
            r["relative_position"] = "居中"
        else:
            r["relative_position"] = "落后"
        r.pop("_rank", None)
    return rows


def build_action_plan(term_events: list[dict]) -> list[dict]:
    """方向级操作建议（个股买点待 b 盘面）。"""
    by_concept: dict[str, list[dict]] = {}
    for e in term_events:
        c = e.get("concept", "")
        if c:
            by_concept.setdefault(c, []).append(e)
    rows = []
    for concept, evs in by_concept.items():
        sig = cumulative_signals(evs)
        stage, _ = decide_stage(sig)
        hard_targets = sorted({e.get("target", "") for e in evs if e.get("hard_evidence") and e.get("target")})
        targets = sorted({e.get("target", "") for e in evs if e.get("target")})
        rep = "、".join((hard_targets or targets)[:3])
        risks = []
        if sig["stance_split"]:
            risks.append("库内存在多空分歧")
        if coverage_label(sig) == "单点":
            risks.append("单点覆盖，结论为下限、待回补")
        rows.append({
            "priority_bucket": _priority_bucket(stage),
            "direction": concept,
            "core_logic": _short(f"{fact_track(sig)}｜{sig['sources']}源/{sig['days']}天｜代表：{rep}", 90),
            "action_thesis": "硬证据方向跟主线龙头、回调跟踪；广度方向等回补/催化确认再参与（个股买点待 b 盘面）",
            "wait_for": upgrade_trigger(stage, sig),
            "risk_warning": "；".join(risks) if risks else "—",
            "_rank": _stage_rank(stage),
        })
    rows.sort(key=lambda r: r.pop("_rank"), reverse=True)
    return rows


def build_signal_layer(term_events: list[dict]) -> dict:
    """radar 信号层/三维交叉读的字段。price_signals 留空待 b 盘面。"""
    sig = cumulative_signals(term_events)
    sources = sorted({e.get("source", "") for e in term_events if e.get("source")})
    n_targets = len({e.get("target", "") for e in term_events if e.get("target")})
    sell_side = []
    if sources:
        sell_side.append(f"{len(sources)}家卖方覆盖（随回补上升）：" + "、".join(sources[:8]) + ("…" if len(sources) > 8 else ""))
    market_heat = [f"{n_targets}个标的 / {sig['sources']}来源 / 跨{sig['days']}日，最高{sig['best_tier'] or '—'}"]
    return {
        "order_signals": _evidence_snippets(term_events, "hard_evidence", 6),
        "industry_progress": _evidence_snippets(term_events, "catalysts", 6),
        "sell_side_coverage": sell_side,
        "market_heat": market_heat,
        "price_signals": [],
    }


def build_theme_entry(term: str, term_events: list[dict]) -> dict:
    sig = cumulative_signals(term_events)
    stage, _ = decide_stage(sig)
    entry = build_signal_layer(term_events)
    entry["recognition_timeline"] = build_recognition_timeline(term_events)
    entry["progress_ruler"] = build_progress_ruler(term_events)
    entry["action_plan"] = build_action_plan(term_events)
    entry["_source"] = BRIDGE_TAG
    entry["_meta"] = {
        "theme": term,
        "stage_floor": stage_label(stage),
        "coverage": coverage_label(sig),
        "events": len(term_events),
        "sources": sig["sources"],
        "days": sig["days"],
        "note": NOTE,
    }
    return entry


def group_events(rows: list[dict], by: str) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for r in rows:
        key = r.get(by, "")
        if key:
            groups.setdefault(key, []).append(r)
    return groups


def concept_owner_term(events_by_concept: dict[str, list[dict]]) -> dict[str, str]:
    """每个 concept(方向) 归属其『主 term』(出现事件最多的 term)。

    避免 term-scoping 把跨 term/跨日的同一方向证据割裂：一个方向只算一次、归唯一 term，
    再在该 term 下用『全库该方向事件』聚合 → 与 consensus_staging --view board(按 concept 全局)一致。
    """
    owner: dict[str, str] = {}
    for concept, evs in events_by_concept.items():
        counts: dict[str, int] = {}
        for e in evs:
            t = e.get("term", "")
            if t:
                counts[t] = counts.get(t, 0) + 1
        owner[concept] = max(counts, key=counts.get) if counts else "(未分类)"
    return owner


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="观点事件库 → per-theme 信号 → theme_signals.json（下限语义、append-only 友好）")
    ap.add_argument("--store", required=True, help="opinion-events.jsonl 路径")
    ap.add_argument("--theme-signals", required=True, help="目标 theme_signals.json 路径")
    ap.add_argument("--also-concepts", action="store_true", help="除 term 外，也为每个 concept(方向) 生成条目")
    ap.add_argument("--dry-run", action="store_true", help="只打印将写入的 theme 列表，不落盘")
    args = ap.parse_args(argv)

    rows = load_store(Path(args.store))
    if not rows:
        print("空库，无事件可桥接", file=sys.stderr)
        return 1

    # 方向(concept)为信号原子单位，全库聚合；按『主 term』归属，term 条目=其名下各方向的全库事件并集。
    # 这样 term CPO 下的『1.6T CPO』用全库 8 事件(跨 06-09/06-10、4 源)→ 催化共振，与 board 一致，
    # 不再因 term-scoping(仅 06-10) 被低估为第一轮；单个被错标 concept 的事件也不会把外来方向拖进来。
    events_by_concept = group_events(rows, "concept")
    owner = concept_owner_term(events_by_concept)
    term_events: dict[str, list[dict]] = {}
    for concept, evs in events_by_concept.items():
        term_events.setdefault(owner[concept], []).extend(evs)
    for e in rows:  # 无 concept 的残余事件按其 term 兜底，确保 223 事件无静默丢失
        if not e.get("concept"):
            term_events.setdefault(e.get("term") or "(未分类)", []).append(e)

    new_entries: dict[str, dict] = {}
    for term, evs in term_events.items():
        new_entries[term] = build_theme_entry(term, evs)
    if args.also_concepts:
        for concept, evs in events_by_concept.items():
            if concept not in new_entries:  # term 优先，不覆盖同名
                new_entries[concept] = build_theme_entry(concept, evs)

    ts_path = Path(args.theme_signals)
    existing = {"version": 1, "themes": {}}
    if ts_path.exists():
        try:
            existing = json.loads(ts_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    if not isinstance(existing, dict):
        existing = {"version": 1, "themes": {}}
    themes = existing.setdefault("themes", {})

    preserved = sum(1 for v in themes.values() if isinstance(v, dict) and v.get("_source") != BRIDGE_TAG)
    # 先剪除上轮本桥写、但本轮不再生成的陈旧条目（归属变化/去重后 key 会变），保留其它来源 theme
    stale = [k for k, v in themes.items()
             if isinstance(v, dict) and v.get("_source") == BRIDGE_TAG and k not in new_entries]
    for k in stale:
        del themes[k]
    # 再 upsert 本轮条目（只动本桥 key，不碰其它来源写的 theme）
    for key, entry in new_entries.items():
        themes[key] = entry

    existing["version"] = existing.get("version", 1)
    existing.setdefault("updated", "")
    existing["updated"] = max(r.get("report_date", "") for r in rows)
    existing["bridge"] = {
        "source": BRIDGE_TAG,
        "store_events": len(rows),
        "themes_written": len(new_entries),
        "note": NOTE,
    }

    summary = sorted(
        ((k, v["_meta"]["stage_floor"], v["_meta"]["coverage"], v["_meta"]["events"]) for k, v in new_entries.items()),
        key=lambda x: -x[3],
    )
    print(f"桥接 {len(rows)} 事件 → {len(new_entries)} 个 theme 条目（保留非本桥 {preserved} 个，剪除陈旧本桥 {len(stale)} 个）")
    for k, st, cov, n in summary[:20]:
        print(f"  - {k}: {st} | 覆盖{cov} | {n} 事件")
    if len(summary) > 20:
        print(f"  …（共 {len(summary)} 个）")

    if args.dry_run:
        print("[dry-run] 未写盘")
        return 0

    ts_path.parent.mkdir(parents=True, exist_ok=True)
    ts_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {ts_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
