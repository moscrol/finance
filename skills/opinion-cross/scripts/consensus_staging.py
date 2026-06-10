#!/usr/bin/env python3
"""consensus-staging: 观点事件库 → 舆情认同度 staging + 时间轴 + 跨方向横向对比。

opinion_store.py 把研报提纯成「观点事件」沉淀进 opinion-events.jsonl（累积+去重+来源归一）；
本脚本是它的**演化视图层**：把库里每个标的/方向的事件按时间累积，映射到 theme-radar 已有的
认同度阶梯 暗流→萌芽→第一轮→催化共振→一致认同（★1-5），回答三个问题：

  1) stage    每个标的现在处在哪一阶（当前阶段 + 认同度分 + 判定理由 + 升阶触发）。
  2) timeline 这个标的的认同度怎么一步步走上来的（哪天跳阶、被什么信号推上去）。
  3) board    7 大方向（concept）同尺横向对比发酵进度（图1 那块）。

设计原则（沿用 opinion-cross 哲学）：
- **规则层不臆造**：阶段由库里可数信号决定（跨天数/来源数/硬度是否升级/催化/最佳Tier），
  每一阶都给出可复核的理由串；缺证据就停在低阶，不脑补。
- **盘面维度留空位**：认同度的「市场是否兑现」一维要等 b（盘面回溯 outcomes.jsonl）接进来，
  当前用库内信号（硬度/跨日/多来源）staging，盘面项标「待补」。
- **复用 radar 阶梯**：阶梯标签与分值镜像 theme-radar `radar.py` 的 recognition 体系
  （暗流30/萌芽45/第一轮60/催化共振78/一致认同90），保证两套视图同一把尺。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opinion_store import load_store  # noqa: E402  (复用库加载/JSONL 解析)

# --- 认同度阶梯（镜像 theme-radar radar.py 的 recognition 体系，保证同尺）---------
STAGE_LADDER = ["暗流", "萌芽", "第一轮", "催化共振", "一致认同"]
STAGE_SCORE = {"暗流": 30, "萌芽": 45, "第一轮": 60, "催化共振": 78, "一致认同": 90}
STAGE_STAR = {"暗流": 1, "萌芽": 2, "第一轮": 3, "催化共振": 4, "一致认同": 5}
STAGE_ALIAS = {"第一轮": "第一枪"}  # 图里叫「第一枪」，引擎里叫「第一轮」，同义

# --- staging 阈值（集中放顶部便于调参；改这里即可调松紧）-----------------------
TH_RESONANCE_SOURCES = 3   # 催化共振：≥3 来源
TH_CONSENSUS_SOURCES = 5   # 一致认同：≥5 来源
TH_CONSENSUS_DAYS = 3      # 一致认同：≥3 个不同报告日


def _tier_rank(t: str) -> int:
    return {"Tier 1": 0, "Tier 2": 1, "Tier 3": 2}.get((t or "").strip(), 3)


def _stage_rank(stage: str) -> int:
    return STAGE_LADDER.index(stage) if stage in STAGE_LADDER else -1


def stage_label(stage: str) -> str:
    """带 ★ 与别名的展示标签，如 '第一轮(第一枪) ★★★'。"""
    star = "★" * STAGE_STAR.get(stage, 0)
    alias = STAGE_ALIAS.get(stage)
    name = f"{stage}({alias})" if alias else stage
    return f"{name} {star}".strip()


def cumulative_signals(events: list[dict]) -> dict:
    """把一组事件（同标的或同方向）聚成可数信号。"""
    dates = sorted({e.get("report_date", "") for e in events if e.get("report_date")})
    sources = sorted({e.get("source_id") or e.get("source", "") for e in events})
    hard_dates = sorted(
        {e.get("report_date", "") for e in events if e.get("hard_evidence")}
    )
    catalyst_dates = sorted(
        {e.get("report_date", "") for e in events if e.get("catalysts")}
    )
    stances = {e.get("stance", "") for e in events}
    best_tier = min((e.get("resonance_tier", "") for e in events), key=_tier_rank) if events else ""
    soft_dates = sorted(
        {e.get("report_date", "") for e in events if e.get("soft_claims") and not e.get("hard_evidence")}
    )
    # 硬度升级 = 在更早出现过软推演之后，后续某天才出现硬证据
    hardness_upgraded = bool(hard_dates and soft_dates and hard_dates[0] > soft_dates[0])
    return {
        "mentions": len(events),
        "days": len(dates),
        "sources": len(sources),
        "first_seen": dates[0] if dates else "",
        "last_seen": dates[-1] if dates else "",
        "has_hard": bool(hard_dates),
        "first_hard_date": hard_dates[0] if hard_dates else "",
        "has_catalyst": bool(catalyst_dates),
        "best_tier": best_tier,
        "stance_split": {"看多", "看空"} <= stances,
        "hardness_upgraded": hardness_upgraded,
    }


def decide_stage(sig: dict) -> tuple[str, list[str]]:
    """由可数信号判定认同度阶段，返回(阶段, 理由串列表)。高阶优先匹配。"""
    reasons: list[str] = []
    sources, days, mentions = sig["sources"], sig["days"], sig["mentions"]
    has_hard, has_cat = sig["has_hard"], sig["has_catalyst"]

    # 一致认同：广泛多来源 + 跨多日 + 有硬证据（Tier1 作加分项，非门槛，因盘面维度待接）
    if sources >= TH_CONSENSUS_SOURCES and days >= TH_CONSENSUS_DAYS and has_hard:
        reasons.append(f"{sources} 来源 / 跨 {days} 日反复印证且出现🟢硬证据")
        if sig["best_tier"] == "Tier 1":
            reasons.append("已达 Tier 1 三重共振")
        else:
            reasons.append("盘面维度待接(b)，暂以库内广度+硬度判一致认同")
        return "一致认同", reasons

    # 催化共振：多来源(≥3) + 有硬证据 + 跨日
    if sources >= TH_RESONANCE_SOURCES and has_hard and days >= 2:
        reasons.append(f"{sources} 来源跨 {days} 日共振 + 🟢硬证据")
        return "催化共振", reasons

    # 第一轮(第一枪)：首次出现硬证据 / 硬度升级 / 催化且有多来源印证
    if has_hard or sig["hardness_upgraded"] or (has_cat and sources >= 2):
        if sig["hardness_upgraded"]:
            reasons.append(f"硬度升级：{sig['first_hard_date']} 软推演→🟢硬证据")
        elif has_hard:
            reasons.append(f"{sig['first_hard_date']} 出现🟢硬证据(订单/合同/入股/公告)")
        else:
            reasons.append(f"出现催化且 {sources} 来源印证")
        return "第一轮", reasons

    # 萌芽：被反复提及但仍是软推演（跨天 / 多来源 / 多次）
    if mentions >= 2 or days >= 2 or sources >= 2:
        reasons.append(f"被提及 {mentions} 次 / {sources} 来源 / 跨 {days} 日，仍属软推演")
        return "萌芽", reasons

    # 暗流：单次软提及，未被关注
    reasons.append("单来源单日提及，尚未被关注")
    return "暗流", reasons


def recognition_score(stage: str, sig: dict) -> int:
    """镜像 radar.recognition_score：stage 基分 + 提及量 + 多来源/硬证据/催化 加分，封顶 99。"""
    score = STAGE_SCORE.get(stage, 35) + min(sig["mentions"], 10)
    if sig["sources"] >= 2:
        score += 5
    if sig["has_hard"]:
        score += 8
    if sig["has_catalyst"]:
        score += 3
    return min(score, 99)


def upgrade_trigger(stage: str, sig: dict) -> str:
    """下一阶需要补什么，可执行的升阶触发。"""
    if stage == "暗流":
        return "再被 1+ 来源/隔日提及 → 萌芽"
    if stage == "萌芽":
        return "出现🟢硬证据(订单/合同/入股)或催化 → 第一轮"
    if stage == "第一轮":
        return f"再增至 {TH_RESONANCE_SOURCES} 来源跨日共振 → 催化共振"
    if stage == "催化共振":
        return f"扩到 {TH_CONSENSUS_SOURCES}+ 来源跨 {TH_CONSENSUS_DAYS}+ 日 / 接盘面兑现(b) → 一致认同"
    return "已达顶阶；接盘面回溯(b)判是否透支/兑现"


def stage_a_target(events: list[dict]) -> dict:
    sig = cumulative_signals(events)
    stage, reasons = decide_stage(sig)
    return {
        **sig,
        "stage": stage,
        "stage_reason": "；".join(reasons),
        "recognition_score": recognition_score(stage, sig),
        "upgrade_trigger": upgrade_trigger(stage, sig),
    }


def timeline_for_target(events: list[dict]) -> list[dict]:
    """按报告日逐步累积，算每个日期截面的阶段，标出跳阶。"""
    by_date: dict[str, list[dict]] = {}
    for e in events:
        by_date.setdefault(e.get("report_date", ""), []).append(e)
    steps = []
    seen: list[dict] = []
    prev_stage = None
    for date in sorted(d for d in by_date if d):
        seen.extend(by_date[date])
        sig = cumulative_signals(seen)
        stage, reasons = decide_stage(sig)
        jumped = prev_stage is not None and _stage_rank(stage) > _stage_rank(prev_stage)
        steps.append({
            "date": date,
            "stage": stage,
            "score": recognition_score(stage, sig),
            "jumped": jumped or prev_stage is None,
            "from_stage": prev_stage,
            "reason": "；".join(reasons),
            "day_sources": sorted({e.get("source", "") for e in by_date[date]}),
        })
        prev_stage = stage
    return steps


# ---------------------------------------------------------------------------
# 视图
# ---------------------------------------------------------------------------
def _filter_rows(rows: list[dict], term: str, concept: str, since: str) -> list[dict]:
    if term:
        rows = [r for r in rows if r.get("term") == term]
    if concept:
        rows = [r for r in rows if r.get("concept") == concept]
    if since:
        rows = [r for r in rows if r.get("report_date", "") >= since]
    return rows


def view_stage(rows: list[dict]) -> tuple[str, list[dict]]:
    by_target: dict[str, list[dict]] = {}
    for r in rows:
        by_target.setdefault(r.get("target", ""), []).append(r)
    agg = []
    for target, evs in by_target.items():
        if not target:
            continue
        s = stage_a_target(evs)
        s["target"] = target
        s["concept"] = next((e.get("concept") for e in evs if e.get("concept")), "")
        agg.append(s)
    agg.sort(key=lambda a: (_stage_rank(a["stage"]), a["recognition_score"]), reverse=True)

    lines = [f"# 舆情认同度 staging（{len(rows)} 事件 / {len(agg)} 标的）", ""]
    lines.append("| 标的 | 方向 | 认同度阶段 | 认同度分 | 跨天 | 来源 | 硬证据 | 多空 | 判定理由 | 升阶触发 |")
    lines.append("|---|---|---|---:|---:|---:|:--:|:--:|---|---|")
    for a in agg:
        lines.append(
            f"| {a['target']} | {a['concept']} | {stage_label(a['stage'])} | {a['recognition_score']} | "
            f"{a['days']} | {a['sources']} | {'🟢' if a['has_hard'] else '—'} | "
            f"{'⚔️分歧' if a['stance_split'] else '—'} | {a['stage_reason']} | {a['upgrade_trigger']} |"
        )
    lines.append("")
    lines.append("> 阶梯：暗流★→萌芽★★→第一轮(第一枪)★★★→催化共振★★★★→一致认同★★★★★。")
    lines.append("> 「市场是否兑现」一维待 b（盘面回溯 outcomes.jsonl）接入；当前以库内 广度×跨日×硬度 判定。")
    return "\n".join(lines), agg


def view_timeline(rows: list[dict], only_target: str) -> str:
    by_target: dict[str, list[dict]] = {}
    for r in rows:
        by_target.setdefault(r.get("target", ""), []).append(r)
    targets = [only_target] if only_target else [
        t for t, _ in sorted(
            by_target.items(),
            key=lambda kv: (-len({e.get("report_date") for e in kv[1]}), -len(kv[1])),
        )
    ]
    lines = ["# 认同度时间轴演变", ""]
    for target in targets:
        evs = by_target.get(target)
        if not evs:
            continue
        steps = timeline_for_target(evs)
        if len(steps) < 2 and not only_target:
            continue  # 列表视图只展示有演化轨迹的标的
        track = " → ".join(
            f"{s['date']} {stage_label(s['stage']) if s['jumped'] else s['stage']}"
            for s in steps
        )
        lines.append(f"## {target}")
        lines.append(f"- 轨迹：{track}")
        for s in steps:
            if s["jumped"]:
                frm = f"{s['from_stage']}→" if s["from_stage"] else ""
                lines.append(
                    f"  - **{s['date']} {frm}{s['stage']}**（认同度 {s['score']}）"
                    f"｜{s['reason']}｜当日来源：{'、'.join(x for x in s['day_sources'] if x)}"
                )
        lines.append("")
    if len(lines) <= 2:
        lines.append("（无跨日演化轨迹的标的；多数为单日提及。用 --target 看单标的逐日截面。）")
    return "\n".join(lines)


def view_board(rows: list[dict]) -> str:
    """跨方向（concept）横向对比发酵进度——图1 那块。"""
    by_concept: dict[str, list[dict]] = {}
    for r in rows:
        c = r.get("concept", "")
        if not c:
            continue
        by_concept.setdefault(c, []).append(r)
    board = []
    for concept, evs in by_concept.items():
        sig = cumulative_signals(evs)
        stage, _ = decide_stage(sig)
        targets = sorted({e.get("target", "") for e in evs if e.get("target")})
        hard_targets = sorted({e.get("target", "") for e in evs if e.get("hard_evidence") and e.get("target")})
        # 代表标的：有硬证据的优先，否则被提及最多的
        rep = hard_targets[0] if hard_targets else (
            max(targets, key=lambda t: sum(1 for e in evs if e.get("target") == t)) if targets else ""
        )
        board.append({
            "concept": concept,
            "stage": stage,
            "score": recognition_score(stage, sig),
            "targets": len(targets),
            "sources": sig["sources"],
            "days": sig["days"],
            "hard_targets": len(hard_targets),
            "rep": rep,
            "trigger": upgrade_trigger(stage, sig),
        })
    board.sort(key=lambda b: (_stage_rank(b["stage"]), b["score"]), reverse=True)

    lines = [f"# 方向 × 发酵进度横向对比（{len(board)} 方向）", ""]
    lines.append("| 方向 | 发酵阶段 | 认同度分 | 标的数 | 硬证据标的 | 来源 | 跨天 | 代表标的 | 升阶触发 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---|---|")
    for b in board:
        lines.append(
            f"| {b['concept']} | {stage_label(b['stage'])} | {b['score']} | {b['targets']} | "
            f"{b['hard_targets']} | {b['sources']} | {b['days']} | {b['rep']} | {b['trigger']} |"
        )
    lines.append("")
    lines.append("> 横向同尺比较各方向发酵到哪一阶；越靠前 = 认同度越高（越接近一致/透支），越靠后 = 越早期(暗流/萌芽，潜在布局区)。")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="观点事件库 → 认同度 staging / 时间轴 / 跨方向横向对比")
    ap.add_argument("--store", required=True, help="opinion-events.jsonl 路径")
    ap.add_argument("--view", choices=["stage", "timeline", "board", "all"], default="all")
    ap.add_argument("--term", default="", help="只看某题材")
    ap.add_argument("--concept", default="", help="只看某方向(concept)")
    ap.add_argument("--target", default="", help="timeline 视图聚焦单标的")
    ap.add_argument("--since", default="", help="只算该日期(含)之后的事件 YYYY-MM-DD")
    ap.add_argument("--markdown", default="", help="把报告写到文件")
    ap.add_argument("--json", action="store_true", help="额外输出结构化 JSON 到 stdout")
    args = ap.parse_args(argv)

    rows = _filter_rows(load_store(Path(args.store).expanduser()), args.term, args.concept, args.since)
    if not rows:
        print("（库为空或过滤后无事件）")
        return 0

    blocks = []
    stage_agg = None
    if args.view in ("stage", "all"):
        md, stage_agg = view_stage(rows)
        blocks.append(md)
    if args.view in ("timeline", "all"):
        blocks.append(view_timeline(rows, args.target))
    if args.view in ("board", "all"):
        blocks.append(view_board(rows))
    report = "\n\n".join(blocks)
    print(report)

    if args.markdown:
        Path(args.markdown).expanduser().write_text(report, encoding="utf-8")
    if args.json and stage_agg is not None:
        print("\n--- JSON ---")
        print(json.dumps(stage_agg, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
