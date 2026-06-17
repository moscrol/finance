#!/usr/bin/env python3
"""pan_realize: 盘面兑现维（b 阶段）——把 outcomes.jsonl 的盘后回测聚成「兑现/透支」判定。

consensus_staging 回答的是「库内认同度」（几家卖方在喊、跨几天、有无硬证据）；它判不了
「市场价格到底兑现了没、是不是已经透支」——那一维一直标着「盘面维度待接(b)」。

本模块就是接这一维：读 build_outcomes.py 产出的 outcomes.jsonl（看多事件→进场后
T+3/5/7/10 收益 + 区间最高 + 峰值天数 + 峰值后回撤 + 相对沪深300 超额，全部来自
免凭证公开行情：腾讯前复权 + 新浪名称→代码），按标的/方向聚合成一个**盘面兑现判定**：

  已兑现持稳 / 兑现中 / 冲高透支 / 未兑现·跑输 / 待观察

判定喂回 consensus_staging：让「一致认同★★★★★」能进一步分成
  · 一致认同 + 已兑现   = 认同被价格确认
  · 一致认同 + 冲高透支 = **透支预警**（热点≠机会，右侧追高接盘风险）——这才是最该提示用户的

★ 市场假设验证红线：这里的判定是**已入库样本**上的**启发式读数**，不是定律。
  - 同时看 3/5/7/10 多窗口 + 区间最高 + 峰值天数 + 峰值后回撤，不只看单一窗口收盘；
  - 每个标的/方向附样本数 n、完整窗口数、原始中位数指标，凭证全摆出来供 agent 复核；
  - 窗口未凑满的近端事件标「待观察」，不计入判定；
  - 阈值集中在顶部，要调松紧改这里即可。
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

# --- 兑现判定阈值（启发式，集中放顶部便于调参；改这里即可调松紧）-----------------
RZ_STRONG_EXCESS = 5.0    # T+5 相对沪深300 超额 ≥ +5% → 明显兑现
RZ_SPIKE_MAX = 12.0       # 区间最高收益 ≥ +12% → 期间出现过明显冲高
RZ_GIVEBACK_DD = -12.0    # 峰值后回撤 ≤ -12% → 大幅回吐（冲高透支特征）
RZ_HOLD_DD = -10.0        # 峰值后回撤 > -10% → 基本持稳
MAIN_WINDOW = 5           # 主口径窗口（镜像胜率榜 T+5 主口径）

# 判定排序键：越靠前=越接近透支/危险（与认同度阶梯同向，方便和 staging 并排读）
VERDICT_RANK = {
    "冲高透支": 0,
    "已兑现持稳": 1,
    "兑现中": 2,
    "未兑现·跑输": 3,
    "待观察": 4,
}


def load_outcomes(path: Path) -> list[dict]:
    """读 outcomes.jsonl；只取看多（build_outcomes 已只产看多，这里再兜一道底）。"""
    recs: list[dict] = []
    if not path.exists():
        return recs
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if (r.get("stance") or "").strip() and r.get("stance") != "看多":
            continue
        recs.append(r)
    return recs


def _median(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 2) if xs else None


def _excess_or_ret(r: dict, n: int) -> float | None:
    """T+n 相对沪深300 超额；缺基准时退回绝对收益。"""
    ex = r.get(f"excess_{n}d")
    return ex if ex is not None else r.get(f"ret_{n}d")


def realize_verdict(metrics: dict) -> tuple[str, str]:
    """由聚合中位数指标判盘面兑现；返回 (判定标签, 说明)。优先级见函数体。"""
    if metrics["n_complete"] == 0:
        return "待观察", "完整窗口=0（近端样本，T+5 未凑满），盘面兑现待坐实"
    ex = metrics["excess_med"]
    imr = metrics["interval_max_med"]
    dd = metrics["post_peak_dd_med"]
    pk = metrics["peak_day_med"]
    ex_s = "—" if ex is None else f"{ex:+g}%"
    # 1) 冲高透支：期间明显冲高 + 峰值后大幅回吐（即便 T+5 收正也先报透支）
    if imr is not None and dd is not None and imr >= RZ_SPIKE_MAX and dd <= RZ_GIVEBACK_DD:
        return "冲高透支", f"区间最高+{imr:g}%/峰值后回撤{dd:g}%(峰值T+{pk:g})→冲高后大幅回吐，T+5超额{ex_s}"
    # 2) 未兑现·跑输：T+5 没跑赢大盘
    if ex is not None and ex <= 0:
        return "未兑现·跑输", f"T+5 超额 {ex_s}（未跑赢沪深300），区间最高+{imr:g}%" if imr is not None else f"T+5 超额 {ex_s}"
    # 3) 已兑现持稳：超额明显 + 峰值后基本持稳
    if ex is not None and ex >= RZ_STRONG_EXCESS and dd is not None and dd > RZ_HOLD_DD:
        return "已兑现持稳", f"T+5 超额 {ex_s} 且峰值后回撤仅 {dd:g}%（持稳）"
    # 4) 兑现中：温和正超额
    return "兑现中", f"T+5 超额 {ex_s}（温和），区间最高+{imr:g}%/峰值后回撤{dd:g}%" if imr is not None else f"T+5 超额 {ex_s}（温和）"


def _aggregate_group(recs: list[dict]) -> dict:
    """一组（同标的或同方向）看多回测事件 → 聚合中位数指标 + 兑现判定。"""
    n = len(recs)
    comp = [r for r in recs if r.get(f"ret_{MAIN_WINDOW}d_complete")]
    metrics = {
        "n": n,
        "n_complete": len(comp),
        "excess_med": _median([_excess_or_ret(r, MAIN_WINDOW) for r in comp]),
        "interval_max_med": _median([r.get("interval_max_ret") for r in comp]),
        "peak_day_med": _median([r.get("peak_day") for r in comp]),
        "post_peak_dd_med": _median([r.get("post_peak_dd") for r in comp]),
        "first_report": min((r.get("report_date", "") for r in recs if r.get("report_date")), default=""),
        "last_report": max((r.get("report_date", "") for r in recs if r.get("report_date")), default=""),
    }
    verdict, detail = realize_verdict(metrics)
    metrics["verdict"] = verdict
    metrics["detail"] = detail
    # 给 consensus_staging 用的两句话（slot 进认同度判定/升阶触发）
    metrics["stage_note"] = f"盘面兑现：{verdict}（{detail}）"
    metrics["trigger_note"] = (
        f"盘面已回测：{verdict}——透支回吐，等回踩均线或缩量企稳再看" if verdict == "冲高透支"
        else f"盘面已回测：{verdict}"
    )
    return metrics


def realize_map(outcomes: list[dict], key: str) -> dict[str, dict]:
    """按 key（'target' 或 'concept'）聚合，返回 {key 值: 兑现聚合}。"""
    groups: dict[str, list[dict]] = {}
    for r in outcomes:
        k = (r.get(key) or "").strip()
        if not k:
            continue
        groups.setdefault(k, []).append(r)
    return {k: _aggregate_group(v) for k, v in groups.items()}


# ---------------------------------------------------------------------------
# 独立视图
# ---------------------------------------------------------------------------
REALIZE_BANNER = (
    "> ⚠️ **盘面兑现维（启发式，非定律）**：基于**已入库看多事件**的免凭证盘后回测"
    "（腾讯前复权+新浪，相对沪深300 超额）。同看 3/5/7/10 多窗口+区间最高+峰值天数+峰值后回撤；"
    "窗口未满标「待观察」不计入；样本数 n 与原始中位数指标全列出供复核。"
)


def view_realize(outcomes: list[dict], by: str, term: str = "", concept: str = "") -> str:
    recs = outcomes
    if term:
        recs = [r for r in recs if r.get("term") == term]
    if concept:
        recs = [r for r in recs if r.get("concept") == concept]
    m = realize_map(recs, by)
    rows = sorted(
        m.items(),
        key=lambda kv: (VERDICT_RANK.get(kv[1]["verdict"], 9), -(kv[1]["n_complete"])),
    )
    head = "标的" if by == "target" else "方向"
    lines = [f"# 盘面兑现维（{head}，{len(recs)} 看多回测事件 / {len(m)} {head}）", ""]
    lines.append(REALIZE_BANNER)
    lines.append("")
    lines.append(f"| {head} | 兑现判定 | n(完整) | T+5超额(中位) | 区间最高(中位) | 峰值后回撤(中位) | 峰值日 | 说明 |")
    lines.append("|---|---|:--:|--:|--:|--:|:--:|---|")
    for k, a in rows:
        ex = "—" if a["excess_med"] is None else f"{a['excess_med']:+g}%"
        imr = "—" if a["interval_max_med"] is None else f"+{a['interval_max_med']:g}%"
        dd = "—" if a["post_peak_dd_med"] is None else f"{a['post_peak_dd_med']:g}%"
        pk = "—" if a["peak_day_med"] is None else f"T+{a['peak_day_med']:g}"
        lines.append(
            f"| {k} | {a['verdict']} | {a['n']}({a['n_complete']}) | {ex} | {imr} | {dd} | {pk} | {a['detail']} |"
        )
    lines.append("")
    lines.append("> 判定序：冲高透支(透支预警) → 已兑现持稳 → 兑现中 → 未兑现·跑输 → 待观察。")
    lines.append("> 与认同度 staging 并读：**一致认同 + 冲高透支 = 透支区（热点≠机会）**；早期阶段 + 已兑现 = 边际机会被价格确认。")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="盘面兑现维：outcomes.jsonl → 标的/方向 兑现判定")
    ap.add_argument("--outcomes", required=True, help="outcomes.jsonl 路径")
    ap.add_argument("--by", choices=["target", "concept"], default="concept")
    ap.add_argument("--term", default="", help="只看某题材")
    ap.add_argument("--concept", default="", help="只看某方向(concept)")
    ap.add_argument("--markdown", default="", help="把报告写到文件")
    args = ap.parse_args(argv)

    outcomes = load_outcomes(Path(args.outcomes).expanduser())
    if not outcomes:
        print("（outcomes.jsonl 为空或不存在——先跑 build_outcomes.py 灌盘后回测）")
        return 0
    report = view_realize(outcomes, args.by, args.term, args.concept)
    print(report)
    if args.markdown:
        Path(args.markdown).expanduser().write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
