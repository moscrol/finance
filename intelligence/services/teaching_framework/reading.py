"""授课框架读数 → 带读里的句子与可分享的上证指数小卡片（SVG）。

两条边界（都是产品面的，不是数据面的）：

1. **只摆读数，不下结论。** 每一句都是旁路库里已算好的数字换成人话：阶段叫什么、几条视角命中、
   是不是亏钱效应日、王朝链走到覆灭第几天。判读（这些读数合起来意味着什么、该盯什么）属于母本，
   母本由创始人写，这里不生成。
2. **不出名单、不出代码。** 王朝成员与区间涨幅前 N 只报组成（申万一级几个、连板几只、载体几趋势几连板），
   名字与代码留在 river 切片里给操作者——带读是小白产品面，一列名字在读者眼里就是推荐，无论叫什么。
   句子里也不能有方向词 / 时点词 / 概率承诺，``guided_reading.lint_output`` 同一道门（测试锁死）。

卡片是纯 SVG（仓里没有 matplotlib / Pillow，不为一张图加依赖）：最近 N 个有标签交易日的上证收盘与周均线、
按我们判出的阶段涂底色、亏钱效应日打点，下面四行读数与免责一行。要 PNG 再说（Pillow 或浏览器截图）。
"""

from __future__ import annotations

import html
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from intelligence.services.methodology_backtest.store import open_labels_db

STAGE_COLORS = {
    "主流主升": "#f4c7c3", "主流主升2.0": "#f0a8a2", "高位震荡": "#fbe3b6", "共建主线": "#d9ecc7",
    "左底向下": "#c9d8f0", "左底向上": "#dbe9f7", "二次探底": "#e3e3f5", "缩量右底": "#e8f0e3",
    "ambiguous": "#f2f2f2", "no_evidence": "#f7f7f7",
}
DISCLAIMER = "只摆读数，不下结论；不构成任何投资建议。判读待授课框架母本。"


def _fmt(value: Any, digits: int = 1) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}" if isinstance(value, float) else str(value)
    return str(value)


def _composition(members: list[dict[str, Any]]) -> str:
    """名单 → 组成：申万一级前几、载体几连板几趋势。不出名字、不出代码。"""
    if not members:
        return "（无）"
    l1 = Counter(str(m.get("sw_l1")) for m in members if m.get("sw_l1"))
    forms = Counter(str(m.get("form")) for m in members if m.get("form"))
    l1_text = "、".join(f"{k} {v}" for k, v in l1.most_common(3)) or "一级未知"
    form_text = "，".join(f"{k} {v}" for k, v in sorted(forms.items())) if forms else ""
    return f"申万一级 {len(l1)} 个（{l1_text}）" + (f"；载体 {form_text}" if form_text else "")


def teaching_lines(objects: list[dict[str, Any]]) -> list[str]:
    """把 ``teaching_*`` 河对象（``RiverObject.to_dict()`` 形状）换成带读里的读数句。"""
    by_type = {str(o.get("object_type")): (o.get("payload") or {}) for o in objects if str(o.get("object_type", "")).startswith("teaching_")}
    lines: list[str] = []
    stage = by_type.get("teaching_stage")
    if stage:
        conf = (stage.get("evidence") or {}).get("confidence") or {}
        hits, possible = conf.get("hits"), conf.get("possible")
        missing = conf.get("missing") or []
        raw = stage.get("stage_coarse")
        coarse = {"ambiguous": "歧义（证据并列，当日未判）", "no_evidence": "无证据（当日未判）", None: "（当日无阶段）"}.get(raw, raw)
        fine = stage.get("stage_fine")
        head = f"阶段：{coarse}" + (f"（细分 {fine}）" if fine and fine not in (raw, "unassigned") else "")
        if hits is not None and possible is not None:
            head += f"｜置信：{hits}/{possible} 条视角命中" + (f"，缺 {len(missing)} 条" if missing else "") + (f"，领先第二名 {conf.get('margin')} 分" if conf.get("margin") is not None else "")
        src = (stage.get("evidence") or {}).get("from")
        if src:
            head += f"｜来源状态：{src}"
        turns = [name for name in ("turn_up", "turn_top", "turn_down") if stage.get(name) == 1]
        if turns:
            head += f"｜转点：{'、'.join(turns)}"
        lines.append(head)
        vol = f"量能：{stage.get('volume_band') or '—'}（量能比 {_fmt(stage.get('amount_vs_ma20_pct'), 0)}）"
        dev = f"偏离度带：{stage.get('deviation_band') or '—'}"
        side = stage.get("above_week_ma")
        ma = "周均线上方" if side == 1 else ("周均线下方" if side == 0 else "周均线位置未知")
        cyc = stage.get("below_ma_cycle_day")
        if side == 0 and cyc is not None:
            ma += f"第 {int(cyc)} 天（{'回踩' if stage.get('cross_below_kind') == 'retest' else '首次下穿'}周期）"
        lines.append(f"{vol}｜{dev}｜{ma}")
        losing = stage.get("money_losing_day")
        streak = stage.get("money_losing_streak")
        prem = stage.get("limit_premium_ma5_pct")
        if losing is None:
            lines.append("亏钱效应：当日无读数（承接 5 日均值缺）")
        else:
            yes = "亏钱效应：是" + (f"（连续第 {int(streak)} 天）" if streak is not None else "")
            lines.append((yes if losing == 1 else "亏钱效应：否") + f"｜承接 5 日均值 {_fmt(prem, 2)}%")
    cap = by_type.get("teaching_capital")
    if cap:
        parts = []
        if cap.get("dragon_net_amount") is not None:
            seg = f"龙虎榜席位净流入 {_fmt(cap.get('dragon_net_amount'), 1)} 亿"  # 「净买入」会撞合规门的动作词，产品面写「净流入」
            if cap.get("dragon_net_amount_ratio_pm") is not None:
                seg += f"（占全市场成交 {_fmt(cap.get('dragon_net_amount_ratio_pm'), 2)}‰"
                seg += f"，5 日均 {_fmt(cap.get('dragon_net_amount_ratio_pm_ma5'), 2)}‰）" if cap.get("dragon_net_amount_ratio_pm_ma5") is not None else "）"
            if cap.get("dragon_buy_sell_ratio") is not None:
                seg += f"，买盘/卖盘 {_fmt(cap.get('dragon_buy_sell_ratio'), 2)}"
                if cap.get("dragon_buy_sell_ratio_ma5") is not None:
                    seg += f"（5 日均 {_fmt(cap.get('dragon_buy_sell_ratio_ma5'), 2)}）"
            parts.append(seg)
        if cap.get("limit_seal_mv_ratio_median") is not None:
            seg = f"涨停封单占流通市值中位 {_fmt(cap.get('limit_seal_mv_ratio_median'), 0)}（万/亿）"
            if cap.get("limit_thick_seal_share_pct") is not None:
                seg += f"，厚封单占比 {_fmt(cap.get('limit_thick_seal_share_pct'), 0)}%"
            parts.append(seg)
        if cap.get("auction_zt_pct_median") is not None:
            seg = f"昨日涨停股竞价涨幅中位 {_fmt(cap.get('auction_zt_pct_median'), 2)}%"
            if cap.get("auction_zt_positive_share_pct") is not None:
                seg += f"，为正 {_fmt(cap.get('auction_zt_positive_share_pct'), 0)}%"
            parts.append(seg)
        if cap.get("top100_amount_share") is not None:
            parts.append(f"成交额前 100 占全市场 {_fmt(100 * float(cap['top100_amount_share']), 1)}%")
        if parts:
            lines.append("资金面：" + "｜".join(parts))
    nar = by_type.get("teaching_narrative")
    if not nar and stage and stage.get("narrative_gap"):
        reason = {
            "narrative_source_absent": "未接知识库（每日复盘没传 --kb-wiki）",
            "narrative_source_missing": "知识库里没有卖方观点事件文件",
            "narrative_stale": "卖方观点事件源断更（超过 7 天没有新报告），今日不出读数",
            "narrative_before_source": "早于卖方观点事件源的起点",
            "narrative_rows_absent": "当日无叙事行",
        }.get(str(stage["narrative_gap"]), str(stage["narrative_gap"]))
        lines.append(f"消息面：{reason}")
    if nar:
        parts = []
        if nar.get("narrative_events") is not None:
            seg = f"隔夜卖方事件 {int(nar['narrative_events'])} 条"
            if nar.get("narrative_events_ratio_ma20_pct") is not None:
                seg += f"（对 20 日均 {_fmt(nar.get('narrative_events_ratio_ma20_pct'), 0)}%）"
            if nar.get("narrative_concepts") is not None:
                seg += f"，覆盖概念 {int(nar['narrative_concepts'])} 个"
            if nar.get("narrative_new_concepts") is not None:
                seg += f"，其中首次出现 {int(nar['narrative_new_concepts'])} 个"
            parts.append(seg)
        detail = []
        if nar.get("narrative_hard_share_pct") is not None:
            detail.append(f"硬证据占比 {_fmt(nar.get('narrative_hard_share_pct'), 0)}%")
        if nar.get("narrative_top3_share_pct") is not None:
            detail.append(f"前三概念集中度 {_fmt(nar.get('narrative_top3_share_pct'), 0)}%")
        if detail:
            parts.append("，".join(detail))
        if nar.get("narrative_cover_rps5_pct") is not None:
            parts.append(f"今日赚钱效应板块里过去 5 天有卖方叙事的占 {_fmt(nar.get('narrative_cover_rps5_pct'), 0)}%")
        if parts:
            lines.append("消息面：" + "｜".join(parts))
    dyn = by_type.get("teaching_dynasty")
    if dyn:
        top = dyn.get("dynasty_top") or []
        line = (
            f"王朝链：最近见顶的王朝 W{dyn.get('wave_idx')}（{dyn.get('wave_start')} → {dyn.get('peak_end')}），"
            f"覆灭窗自 {dyn.get('collapse_start')} 起，至今有标签 {_fmt(dyn.get('labelled_days_since_collapse_start'))} 天、"
            f"亏钱效应日 {_fmt(dyn.get('money_losing_days_since_collapse_start'))} 天；其前 {len(top)}：{_composition(top)}"
        )
        handoff = dyn.get("last_completed_handoff")
        if handoff:
            members = handoff.get("new_members_in_old_collapse") or []
            sep = sum(1 for m in members if m.get("separation_relative"))
            nh = sum(1 for m in members if m.get("separation_new_high"))
            line += (
                f"｜进入这一波的衔接：上一王朝 W{handoff.get('old_wave_idx')} 覆灭窗 {handoff['old_collapse'][0]} → {handoff['old_collapse'][1] or '—'}，"
                f"本波前 {len(members)} 里 {sep} 只相对分离、{nh} 只窗内创新高"
            )
        lines.append(line)
    rl = by_type.get("teaching_range_leaders")
    if rl:
        parts = []
        for window, members in sorted((rl.get("windows") or {}).items(), key=lambda kv: int(kv[0])):
            limit_leaders = sum(1 for m in members if (m.get("limit_times") or 0) >= 3)
            tenures = [int(m["tenure_day"]) for m in members if m.get("tenure_day") is not None]
            tenure_med = sorted(tenures)[len(tenures) // 2] if tenures else None
            entry = min((m.get("gain_pct") for m in members if m.get("gain_pct") is not None), default=None)
            parts.append(
                f"{window} 日前 {len(members)}：{_composition(members).split('；')[0]}，连板高标 {limit_leaders} 只，"
                f"在位天数中位 {_fmt(tenure_med)}，入组门槛 {_fmt(entry, 0)}%"
            )
        if parts:
            lines.append("区间涨幅高标：" + "；".join(parts))
    return lines


# --------------------------------------------------------------------------- #
# 卡片
# --------------------------------------------------------------------------- #
def _series(labels_db: Path, as_of: str, days: int) -> tuple[list[dict[str, Any]], str | None]:
    con = open_labels_db(labels_db, read_only=True)
    try:
        rows = con.execute(
            """SELECT trade_date, label, value_num, value_text, framework_version FROM history_teaching_labels
               WHERE entity_type = 'market' AND status = 'ok' AND trade_date <= ?
                 AND label IN ('src.sh_index_close', 'src.sh_deviation_pct', 'tf.stage_coarse', 'tf.money_losing_day', 'tf.above_week_ma')
               ORDER BY trade_date""",
            [date.fromisoformat(as_of)],
        ).fetchall()
    finally:
        con.close()
    by_day: dict[Any, dict[str, Any]] = {}
    version: str | None = None
    for d, label, num, text, fw in rows:
        by_day.setdefault(d, {})[label] = text if text is not None else num
        version = fw
    series = [
        {"date": d, "close": v.get("src.sh_index_close"), "dev": v.get("src.sh_deviation_pct"),
         "stage": v.get("tf.stage_coarse"), "losing": v.get("tf.money_losing_day"), "above": v.get("tf.above_week_ma")}
        for d, v in sorted(by_day.items()) if v.get("src.sh_index_close") is not None
    ]
    return series[-days:], version


def _wrap(line: str, limit: int = 84) -> list[str]:
    """长句在「｜」「；」处折行，不在字中间截断；每段最多 limit 个字符。"""
    if len(line) <= limit:
        return [line]
    parts, cur = [], ""
    for piece in line.replace("；", "；\x00").replace("｜", "｜\x00").split("\x00"):
        if cur and len(cur) + len(piece) > limit:
            parts.append(cur)
            cur = piece
        else:
            cur += piece
    if cur:
        parts.append(cur)
    return [p if len(p) <= limit else p[: limit - 1] + "…" for p in parts]


def index_card_svg(labels_db: str | Path, as_of: str, lines: list[str], *, days: int = 60, width: int = 960, max_lines: int = 8) -> str:
    """上证指数 × 授课框架读数的分享卡片。纯 SVG 字符串；``lines`` 是 ``teaching_lines`` 的输出；高度随读数行数走。"""
    series, version = _series(Path(labels_db).expanduser(), as_of, days)
    pad_l, pad_r, pad_t = 64, 24, 64
    chart_h = 300
    wrapped = [w for line in lines for w in _wrap(line)][:max_lines]
    height = pad_t + chart_h + 56 + 22 * len(wrapped) + 40
    esc = html.escape
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="PingFang SC, Noto Sans CJK SC, sans-serif">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{pad_l}" y="36" font-size="22" font-weight="600" fill="#222">上证指数 · 授课框架读数 · {esc(as_of)}</text>',
    ]
    if not series:
        out.append(f'<text x="{pad_l}" y="{pad_t + 40}" font-size="16" fill="#666">{esc(as_of)} 之前没有有标签的交易日</text>')
    else:
        closes = [float(s["close"]) for s in series]
        mas = [float(s["close"]) / (1 + float(s["dev"]) / 100) if s.get("dev") is not None else None for s in series]
        lo = min(closes + [m for m in mas if m is not None]) * 0.995
        hi = max(closes + [m for m in mas if m is not None]) * 1.005
        n = len(series)
        step = (width - pad_l - pad_r) / max(1, n - 1)

        def x(i: int) -> float:
            return pad_l + i * step

        def y(v: float) -> float:
            return pad_t + chart_h - (v - lo) / (hi - lo) * chart_h

        # stage bands
        i = 0
        while i < n:
            stage = series[i].get("stage") or "no_evidence"
            j = i
            while j + 1 < n and (series[j + 1].get("stage") or "no_evidence") == stage:
                j += 1
            x0, x1 = x(i) - step / 2, x(j) + step / 2
            out.append(f'<rect x="{x0:.1f}" y="{pad_t}" width="{max(1.0, x1 - x0):.1f}" height="{chart_h}" fill="{STAGE_COLORS.get(str(stage), "#f2f2f2")}"/>')
            if j - i >= 2:
                out.append(f'<text x="{(x0 + x1) / 2:.1f}" y="{pad_t + 16}" font-size="11" text-anchor="middle" fill="#555">{esc(str(stage))}</text>')
            i = j + 1
        # gridlines + labels
        for k in range(5):
            v = lo + (hi - lo) * k / 4
            out.append(f'<line x1="{pad_l}" y1="{y(v):.1f}" x2="{width - pad_r}" y2="{y(v):.1f}" stroke="#ddd" stroke-width="1"/>')
            out.append(f'<text x="{pad_l - 8}" y="{y(v) + 4:.1f}" font-size="11" text-anchor="end" fill="#666">{v:.0f}</text>')
        ma_pts = " ".join(f"{x(i):.1f},{y(m):.1f}" for i, m in enumerate(mas) if m is not None)
        if ma_pts:
            out.append(f'<polyline points="{ma_pts}" fill="none" stroke="#e6a23c" stroke-width="1.5" stroke-dasharray="4 3"/>')
        pts = " ".join(f"{x(i):.1f},{y(c):.1f}" for i, c in enumerate(closes))
        out.append(f'<polyline points="{pts}" fill="none" stroke="#c0392b" stroke-width="2"/>')
        for i, s in enumerate(series):
            if s.get("losing") == 1:
                out.append(f'<circle cx="{x(i):.1f}" cy="{pad_t + chart_h + 10}" r="3" fill="#2c3e50"/>')
        first, last = str(series[0]["date"]), str(series[-1]["date"])
        out.append(f'<text x="{pad_l}" y="{pad_t + chart_h + 30}" font-size="11" fill="#666">{esc(first)}</text>')
        out.append(f'<text x="{width - pad_r}" y="{pad_t + chart_h + 30}" font-size="11" text-anchor="end" fill="#666">{esc(last)}</text>')
        out.append(f'<text x="{width - pad_r}" y="52" font-size="11" text-anchor="end" fill="#666">— 收盘　- - 周均线　● 亏钱效应日　底色 = 框架判出的阶段（{n} 个交易日）</text>')
    ty = pad_t + chart_h + 56
    for text in wrapped:
        out.append(f'<text x="{pad_l}" y="{ty}" font-size="13" fill="#333">{esc(text)}</text>')
        ty += 22
    out.append(f'<text x="{pad_l}" y="{height - 16}" font-size="11" fill="#888">{esc(DISCLAIMER)}{esc(" · " + version if version else "")}</text>')
    out.append("</svg>")
    return "\n".join(out)
