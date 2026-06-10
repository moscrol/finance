#!/usr/bin/env python3
"""consensus-staging: 观点事件库 → 舆情认同度 staging + 时间轴 + 跨方向横向对比。

opinion_store.py 把研报提纯成「观点事件」沉淀进 opinion-events.jsonl（累积+去重+来源归一）；
本脚本是它的**演化视图层**：把库里每个标的/方向的事件按时间累积，映射到 theme-radar 已有的
认同度阶梯 暗流→萌芽→第一轮(第一枪)→催化共振→一致认同（★1-5），回答"认同度演变"。

  1) stage    每个标的的认同度**下限** + 覆盖度 + 事实轨/广度轨 + 判定理由 + 升阶/待补触发。
  2) timeline 这个标的的认同度怎么一步步走上来的（哪天跳阶、被什么信号推上去）。
  3) board    各方向（concept）同尺横向对比发酵进度（图1 那块）。

★ 沉淀层适配（核心）：库是 **append-only + 去重**，用户在持续回补历史卖方研报，
  所以"当前快照"是**不完整**的，会随回补单调增长。本脚本据此做三件事，避免把
  "数据没补够"误读成"市场没认同"：

  - **阶段 = 下限语义**：输出的是"已入库证据**至少**支撑到哪一阶"。回补只会让某标的的
    来源/跨天/硬证据单调增加 → 阶段**只升不降**。绝不把低覆盖当成"市场冷"。
  - **单来源软料不判阶**：只有 1 个来源、且只有软推演的标的，归入「观察池·覆盖不足(待回补)」，
    **不**硬扣「暗流/萌芽」。出现**事实锚点（🟢硬证据/催化）或多来源广度**时才正式上阶梯。
  - **两条轨道分离**：
      · 事实硬度轨（robust）——有无订单/合同/入股/催化。这条**不随回补改变含义**：
        1 条硬证据就成立，是阶梯的主锚点。
      · 舆情广度轨（回补敏感）——几家在喊、跨几天。这条**强烈依赖入库进度**，只作
        覆盖度/置信度修饰，明确标"随回补上升、仅供参考"。

  阶梯标签/分值镜像 theme-radar `radar.py` 的 recognition 体系，保证两套视图同一把尺。
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

# 覆盖不足的前置桶：不在认同度阶梯上，专门收"单来源软料/证据未补全"，避免误判。
WATCH = "观察池"

# --- staging 阈值（集中放顶部便于调参；改这里即可调松紧）-----------------------
TH_RESONANCE_SOURCES = 3   # 催化共振：≥3 来源
TH_CONSENSUS_SOURCES = 5   # 一致认同：≥5 来源
TH_CONSENSUS_DAYS = 3      # 一致认同：≥3 个不同报告日


def _tier_rank(t: str) -> int:
    return {"Tier 1": 0, "Tier 2": 1, "Tier 3": 2}.get((t or "").strip(), 3)


def _stage_rank(stage: str) -> int:
    """认同度排序键；观察池(覆盖不足) 低于阶梯最低阶。"""
    if stage == WATCH:
        return -1
    return STAGE_LADDER.index(stage) if stage in STAGE_LADDER else -2


def stage_label(stage: str) -> str:
    """带 ★ 与别名的展示标签，如 '第一轮(第一枪) ★★★'；观察池标覆盖不足。"""
    if stage == WATCH:
        return "观察池·覆盖不足"
    star = "★" * STAGE_STAR.get(stage, 0)
    alias = STAGE_ALIAS.get(stage)
    name = f"{stage}({alias})" if alias else stage
    return f"{name} {star}".strip()


def coverage_label(sig: dict) -> str:
    """入库覆盖度——告诉用户广度轨可信几分（回补敏感）。"""
    if sig["sources"] >= 3 and sig["days"] >= 2:
        return "较充分"
    if sig["sources"] >= 2 or sig["days"] >= 2:
        return "有限"
    return "单点"


def fact_track(sig: dict) -> str:
    """事实硬度轨（robust，不随回补改变含义）。"""
    if sig["has_hard"]:
        return "🟢硬证据"
    if sig["has_catalyst"]:
        return "催化"
    if sig["has_soft"]:
        return "仅软推演"
    return "—"


def breadth_track(sig: dict) -> str:
    """舆情广度轨（回补敏感，仅供参考）。"""
    return f"{sig['sources']}源/{sig['days']}天"


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
        "has_soft": bool(soft_dates) or any(e.get("soft_claims") for e in events),
        "best_tier": best_tier,
        "stance_split": {"看多", "看空"} <= stances,
        "hardness_upgraded": hardness_upgraded,
    }


def decide_stage(sig: dict) -> tuple[str, list[str]]:
    """由可数信号判定认同度**下限**，返回(阶段, 理由串)。事实锚点优先，单来源软料不判阶。

    回补单调性：库 append-only，回补只会让 sources/days/has_hard 增加 →
    decide_stage 的结果只会沿阶梯上升或不变，绝不下降。
    """
    reasons: list[str] = []
    sources, days = sig["sources"], sig["days"]
    has_hard, has_cat = sig["has_hard"], sig["has_catalyst"]

    # ===== 事实硬度轨（robust：含义不随回补改变，是阶梯主锚点）=====
    if sources >= TH_CONSENSUS_SOURCES and days >= TH_CONSENSUS_DAYS and has_hard:
        reasons.append(f"{sources} 来源 / 跨 {days} 日反复印证且有🟢硬证据")
        reasons.append("已达 Tier 1 三重共振" if sig["best_tier"] == "Tier 1"
                       else "盘面维度待接(b)，暂以库内广度+硬度判一致认同")
        return "一致认同", reasons

    if sources >= TH_RESONANCE_SOURCES and has_hard and days >= 2:
        reasons.append(f"{sources} 来源跨 {days} 日共振 + 🟢硬证据")
        return "催化共振", reasons

    if has_hard or sig["hardness_upgraded"] or has_cat:
        # 事实锚点存在 → 第一轮下限，即便仅单来源也成立（硬证据 robust）
        if sig["hardness_upgraded"]:
            reasons.append(f"硬度升级：{sig['first_hard_date']} 软推演→🟢硬证据")
        elif has_hard:
            reasons.append(f"{sig['first_hard_date']} 出现🟢硬证据(订单/合同/入股/公告)")
        else:
            reasons.append("出现催化事件")
        if sources == 1:
            reasons.append("仅单来源入库，广度待回补（阶段为下限）")
        return "第一轮", reasons

    # ===== 舆情广度轨（回补敏感）：多来源/跨日的软共识 → 萌芽（弱信号）=====
    if sources >= 2 or days >= 2:
        reasons.append(f"{sources} 来源/跨 {days} 日的软推演共识（广度轨，回补敏感）")
        return "萌芽", reasons

    # ===== 覆盖不足：单来源单日软料 → 不判阶，进观察池待回补 =====
    reasons.append(f"仅 {sources} 来源入库（沉淀回补中），证据未补全，暂不判阶")
    return WATCH, reasons


def recognition_score(stage: str, sig: dict) -> int:
    """镜像 radar.recognition_score：stage 基分 + 提及量 + 多来源/硬证据/催化 加分，封顶 99。

    观察池不在阶梯上 → 给覆盖度分(很低)，强调"未判阶"。
    """
    base = 20 if stage == WATCH else STAGE_SCORE.get(stage, 35)
    score = base + min(sig["mentions"], 10)
    if sig["sources"] >= 2:
        score += 5
    if sig["has_hard"]:
        score += 8
    if sig["has_catalyst"]:
        score += 3
    return min(score, 99)


def upgrade_trigger(stage: str, sig: dict) -> str:
    """下一阶需要补什么；措辞贴合"持续回补"语境。"""
    if stage == WATCH:
        return "回补更多研报：再有来源/隔日提及，或出现🟢硬证据/催化 → 上阶梯"
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
        "coverage": coverage_label(sig),
        "fact_track": fact_track(sig),
        "breadth_track": breadth_track(sig),
        "recognition_score": recognition_score(stage, sig),
        "upgrade_trigger": upgrade_trigger(stage, sig),
    }


def timeline_for_target(events: list[dict]) -> list[dict]:
    """按报告日逐步累积，算每个日期截面的阶段下限，标出跳阶。

    注意：用 report_date（研报口径日），不是 ingested_at（入库日）。回补历史研报会
    在更早日期插入新点 → 该标的时间轴会被重算（这是对的：重建"按研报日，当前已入库
    证据下我们本应知道的认同度下限"）。所以 timeline 是**随回补刷新的**视图。
    """
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
BACKFILL_BANNER = (
    "> ⚠️ **沉淀层持续回补中**：本表是**当前已入库证据**的认同度**下限**判断。库 append-only+去重，"
    "回补只会让阶段**上升或不变**（单调），绝不下降。单来源软料归「观察池·覆盖不足」而非低估为某阶；"
    "事实硬度轨(🟢硬证据/催化)robust 不随回补变，舆情广度轨(N源/N天)随回补上升、仅作覆盖度参考。"
)


def _filter_rows(rows: list[dict], term: str, concept: str, since: str) -> list[dict]:
    if term:
        rows = [r for r in rows if r.get("term") == term]
    if concept:
        rows = [r for r in rows if r.get("concept") == concept]
    if since:
        rows = [r for r in rows if r.get("report_date", "") >= since]
    return rows


def view_stage(rows: list[dict], hide_watch: bool = False) -> tuple[str, list[dict]]:
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

    n_watch = sum(1 for a in agg if a["stage"] == WATCH)
    shown = [a for a in agg if not (hide_watch and a["stage"] == WATCH)]
    lines = [f"# 舆情认同度 staging（下限）（{len(rows)} 事件 / {len(agg)} 标的，其中观察池 {n_watch}）", ""]
    lines.append(BACKFILL_BANNER)
    lines.append("")
    lines.append("| 标的 | 方向 | 认同度(下限) | 下限分 | 覆盖度 | 事实轨(robust) | 广度轨(回补敏感) | 多空 | 判定理由 | 升阶/待补触发 |")
    lines.append("|---|---|---|---:|:--:|:--:|:--:|:--:|---|---|")
    for a in shown:
        lines.append(
            f"| {a['target']} | {a['concept']} | {stage_label(a['stage'])} | {a['recognition_score']} | "
            f"{a['coverage']} | {a['fact_track']} | {a['breadth_track']} | "
            f"{'⚔️分歧' if a['stance_split'] else '—'} | {a['stage_reason']} | {a['upgrade_trigger']} |"
        )
    lines.append("")
    lines.append("> 阶梯：观察池(覆盖不足)·→萌芽★★→第一轮(第一枪)★★★→催化共振★★★★→一致认同★★★★★。")
    lines.append("> 「市场是否兑现/透支」一维待 b（盘面回溯 outcomes.jsonl）接入。")
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
    lines = ["# 认同度时间轴演变（按研报日重算，随回补刷新）", ""]
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
                    f"  - **{s['date']} {frm}{s['stage']}**（下限分 {s['score']}）"
                    f"｜{s['reason']}｜当日来源：{'、'.join(x for x in s['day_sources'] if x)}"
                )
        lines.append("")
    if len(lines) <= 2:
        lines.append("（无跨日演化轨迹的标的；多数为单日提及。用 --target 看单标的逐日截面。）")
    return "\n".join(lines)


def view_board(rows: list[dict]) -> str:
    """各方向（concept）横向对比发酵进度——图1 那块。"""
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
        rep = hard_targets[0] if hard_targets else (
            max(targets, key=lambda t: sum(1 for e in evs if e.get("target") == t)) if targets else ""
        )
        board.append({
            "concept": concept,
            "stage": stage,
            "score": recognition_score(stage, sig),
            "coverage": coverage_label(sig),
            "targets": len(targets),
            "sources": sig["sources"],
            "days": sig["days"],
            "hard_targets": len(hard_targets),
            "rep": rep,
            "trigger": upgrade_trigger(stage, sig),
        })
    board.sort(key=lambda b: (_stage_rank(b["stage"]), b["score"]), reverse=True)

    lines = [f"# 方向 × 发酵进度横向对比（下限）（{len(board)} 方向）", ""]
    lines.append(BACKFILL_BANNER)
    lines.append("")
    lines.append("| 方向 | 发酵阶段(下限) | 下限分 | 覆盖度 | 标的数 | 硬证据标的 | 来源 | 跨天 | 代表标的 | 升阶/待补触发 |")
    lines.append("|---|---|---:|:--:|---:|---:|---:|---:|---|---|")
    for b in board:
        lines.append(
            f"| {b['concept']} | {stage_label(b['stage'])} | {b['score']} | {b['coverage']} | {b['targets']} | "
            f"{b['hard_targets']} | {b['sources']} | {b['days']} | {b['rep']} | {b['trigger']} |"
        )
    lines.append("")
    lines.append("> 同尺横向比较各方向发酵到哪一阶（下限）；越靠前=认同度越高(越接近一致/透支)，越靠后/观察池=越早期或覆盖未补足。")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="观点事件库 → 认同度 staging / 时间轴 / 跨方向横向对比（沉淀层下限语义）")
    ap.add_argument("--store", required=True, help="opinion-events.jsonl 路径")
    ap.add_argument("--view", choices=["stage", "timeline", "board", "all"], default="all")
    ap.add_argument("--term", default="", help="只看某题材")
    ap.add_argument("--concept", default="", help="只看某方向(concept)")
    ap.add_argument("--target", default="", help="timeline 视图聚焦单标的")
    ap.add_argument("--since", default="", help="只算该日期(含)之后的事件 YYYY-MM-DD")
    ap.add_argument("--hide-watch", action="store_true", help="stage 视图隐藏观察池(覆盖不足)标的，只看已上阶梯的")
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
        md, stage_agg = view_stage(rows, hide_watch=args.hide_watch)
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
