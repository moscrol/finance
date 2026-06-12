#!/usr/bin/env python3
"""题材发酵链路回溯：消息面（知识库）× 盘面（market_feature_store DuckDB）按日期对齐。

用法:
    python3 trace.py --theme 可控核聚变 [--start 2026-04-01] [--end 2026-06-12]
                     [--window 60] [--vault PATH] [--out PATH]

输出 markdown 报告:
  1. 消息面时间线: evidence_index 证据、theme_signals recognition_timeline、卖方覆盖
  2. 板块时间线: 边际量转正/双红(量价齐升)序列、多周期共振、涨停热度
  3. 个股梯队: 每只成员股的起涨日(首板或量价突破)、起涨股 vs 补涨股分层
  4. 合并链路: 消息 → 首板 → 板块双红 → 补涨扩散 的逐日对照表
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from market_feature_store import db as mfs_db  # noqa: E402


# ---------------------------------------------------------------- 知识库路径

def default_vault() -> Path:
    for var in ("KB_VAULT", "CONCEPT_VAULT", "ENTITY_VAULT"):
        val = os.environ.get(var)
        if val:
            return Path(os.path.expanduser(val))
    if REPO_ROOT.parent.is_dir():
        for sibling in sorted(REPO_ROOT.parent.iterdir()):
            if sibling != REPO_ROOT and (sibling / "wiki" / "relations").is_dir():
                return sibling / "wiki"
    return Path(os.path.expanduser("~/Desktop/c c/知识库/wiki"))


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ---------------------------------------------------------------- 消息面

DATE_RE = re.compile(r"(20\d{2})[-/年]?(\d{1,2})[-/月]?(\d{1,2})")


def parse_date(text: str) -> date | None:
    if not text:
        return None
    m = DATE_RE.search(str(text))
    if not m:
        m2 = re.search(r"_(20\d{2})(\d{2})(\d{2})", str(text))
        if not m2:
            return None
        m = m2
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def theme_concept_names(theme: str, relations: Path) -> list[str]:
    """主题相关概念集合：theme 本身 + theme_signals/exposures 中包含 theme 的概念名。"""
    names = {theme}
    signals = load_json(relations / "theme_signals.json").get("themes", {})
    for name in signals:
        if theme in name or name in theme:
            names.add(name)
    exposures = load_json(relations / "entity_exposures.json").get("entities", {})
    for ent in exposures.values():
        for cname in (ent.get("concepts") or {}):
            if theme in cname or cname in theme:
                names.add(cname)
    return sorted(names)


def collect_news_events(theme: str, vault: Path) -> tuple[list[dict], list[str]]:
    """返回 (消息面事件列表, 概念命中名单)。事件: {date, kind, text, source}。"""
    relations = vault / "relations"
    concepts = theme_concept_names(theme, relations)
    events: list[dict] = []

    ev_index = load_json(relations / "evidence_index.json").get("evidence", [])
    if isinstance(ev_index, dict):
        ev_index = list(ev_index.values())
    for item in ev_index:
        cname = item.get("concept") or ""
        if not any(c in cname or cname in c for c in concepts):
            continue
        d = parse_date(item.get("updated")) or parse_date(item.get("source_name"))
        events.append({
            "date": d,
            "kind": f"证据[{item.get('evidence_layer', '?')}]",
            "text": (item.get("summary") or "")[:120],
            "source": item.get("source_name") or "",
        })

    signals = load_json(relations / "theme_signals.json").get("themes", {})
    for name, theme_obj in signals.items():
        if name not in concepts:
            continue
        for rec in theme_obj.get("recognition_timeline") or []:
            events.append({
                "date": parse_date(rec.get("time_window")),
                "kind": f"认知跃迁[{rec.get('recognition_stage', '?')}]",
                "text": (rec.get("event") or "")[:120],
                "source": name,
            })
        for cov in theme_obj.get("sell_side_coverage") or []:
            events.append({
                "date": parse_date(cov),
                "kind": "卖方覆盖",
                "text": str(cov)[:120],
                "source": name,
            })
    return events, concepts


def collect_member_stocks(theme: str, concepts: list[str], vault: Path) -> dict[str, dict]:
    """从 entity_exposures 取成员公司: name -> {codes, strength, concepts}。"""
    exposures = load_json(vault / "relations" / "entity_exposures.json").get("entities", {})
    rank = {"core": 0, "related": 1, "peripheral": 2}
    members: dict[str, dict] = {}
    for name, ent in exposures.items():
        best = None
        hit = []
        for cname, c in (ent.get("concepts") or {}).items():
            if any(k in cname or cname in k for k in concepts):
                hit.append(cname)
                s = c.get("strength") or "peripheral"
                if best is None or rank.get(s, 2) < rank.get(best, 2):
                    best = s
        if hit:
            members[ent.get("name") or name] = {
                "codes": ent.get("codes") or [],
                "strength": best or "peripheral",
                "concepts": hit,
            }
    return members


# ---------------------------------------------------------------- 盘面

def query(con, sql: str, params: list) -> list[dict]:
    try:
        cur = con.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as exc:
        print(f"[warn] 查询失败: {exc}", file=sys.stderr)
        return []


def theme_sectors(con, theme: str) -> list[dict]:
    rows = query(con, "SELECT sector_ts_code, sector_name, match_type, confidence FROM config_theme_sector_link WHERE theme = ?", [theme])
    if rows:
        return rows
    return query(con, "SELECT DISTINCT sector_ts_code, sector_name, 'fuzzy' AS match_type, 0.5 AS confidence FROM fact_sector_daily WHERE sector_name LIKE ?", [f"%{theme}%"])


def sector_timeline(con, sector_codes: list[str], start: date, end: date) -> list[dict]:
    """板块逐日: 双红(pct_chg>0 且 diff_ratio>0)、连续双红天数、多周期共振。"""
    if not sector_codes:
        return []
    ph = ",".join("?" for _ in sector_codes)
    rows = query(con, f"""
        SELECT trade_date, sector_name, pct_chg, amount, diff_ratio, multi_period_resonance
        FROM fact_sector_daily
        WHERE sector_ts_code IN ({ph}) AND trade_date BETWEEN ? AND ?
        ORDER BY sector_name, trade_date
    """, sector_codes + [start, end])
    streak: dict[str, int] = defaultdict(int)
    for r in rows:
        red = (r.get("pct_chg") or 0) > 0 and (r.get("diff_ratio") or 0) > 0
        name = r["sector_name"]
        streak[name] = streak[name] + 1 if red else 0
        r["double_red"] = red
        r["double_red_streak"] = streak[name]
    return rows


def limit_heat(con, sector_codes: list[str], start: date, end: date) -> list[dict]:
    if not sector_codes:
        return []
    ph = ",".join("?" for _ in sector_codes)
    return query(con, f"""
        SELECT trade_date, sector_name, limit_up_count, total_count, rank
        FROM fact_theme_limit_heat_daily
        WHERE sector_ts_code IN ({ph}) AND trade_date BETWEEN ? AND ?
        ORDER BY trade_date
    """, sector_codes + [start, end])


def member_interval_gains(con, members: dict[str, dict], start: date, end: date) -> dict[str, float]:
    """成员股窗口区间涨幅%: 优先 fact_stock_daily(按 codes), 兜底 fact_sector_stock_daily(按名称)。"""
    gains: dict[str, float] = {}
    for name, info in members.items():
        gain = None
        codes = info["codes"]
        if codes:
            ph = ",".join("?" for _ in codes)
            rows = query(con, f"""
                SELECT (LAST(close ORDER BY trade_date) / FIRST(close ORDER BY trade_date) - 1) * 100 AS g
                FROM fact_stock_daily
                WHERE stock_ts_code IN ({ph}) AND close IS NOT NULL AND trade_date BETWEEN ? AND ?
            """, codes + [start, end])
            if rows and rows[0].get("g") is not None:
                gain = rows[0]["g"]
        if gain is None:
            rows = query(con, """
                SELECT (LAST(price ORDER BY trade_date) / FIRST(price ORDER BY trade_date) - 1) * 100 AS g
                FROM fact_sector_stock_daily
                WHERE stock_name = ? AND price IS NOT NULL AND price > 0 AND trade_date BETWEEN ? AND ?
            """, [name, start, end])
            if rows and rows[0].get("g") is not None:
                gain = rows[0]["g"]
        if gain is not None:
            gains[name] = float(gain)
    return gains


def filter_members_by_gain(members: dict[str, dict], gains: dict[str, float], max_members: int) -> tuple[dict[str, dict], int]:
    """命中多时按区间涨幅取 Top N（core 层保底全留）, 命中少则全列。返回 (筛后成员, 被筛掉数)。"""
    for name, info in members.items():
        info["gain"] = gains.get(name)
    if len(members) <= max_members:
        return members, 0
    ranked = sorted(members.items(), key=lambda kv: kv[1]["gain"] if kv[1]["gain"] is not None else -1e9, reverse=True)
    keep = {n: i for n, i in ranked[:max_members]}
    for n, i in members.items():
        if i["strength"] == "core" and n not in keep:
            keep[n] = i
    return keep, len(members) - len(keep)


def stock_start_days(con, members: dict[str, dict], sector_codes: list[str], start: date, end: date,
                     pct_th: float = 7.0) -> list[dict]:
    """每只成员股的起涨日: 首板日(优先, fact_theme_limit_stock_daily/fact_limit_advance_daily)
    或首次单日涨幅>=pct_th(fact_stock_daily/fact_sector_stock_daily)。"""
    out = []
    for name, info in members.items():
        codes = info["codes"]
        first_limit = None
        first_surge = None
        rows = query(con, """
            SELECT MIN(trade_date) AS d FROM fact_limit_advance_daily
            WHERE stock_name = ? AND trade_date BETWEEN ? AND ?
        """, [name, start, end])
        if rows and rows[0].get("d"):
            first_limit = rows[0]["d"]
        if first_limit is None and sector_codes:
            ph = ",".join("?" for _ in sector_codes)
            rows = query(con, f"""
                SELECT MIN(trade_date) AS d FROM fact_theme_limit_stock_daily
                WHERE stock_name = ? AND sector_ts_code IN ({ph})
                  AND COALESCE(limit_times, 0) >= 1 AND trade_date BETWEEN ? AND ?
            """, [name] + sector_codes + [start, end])
            if rows and rows[0].get("d"):
                first_limit = rows[0]["d"]
        if codes:
            ph = ",".join("?" for _ in codes)
            rows = query(con, f"""
                SELECT MIN(trade_date) AS d FROM fact_stock_daily
                WHERE stock_ts_code IN ({ph}) AND pct_chg >= ? AND trade_date BETWEEN ? AND ?
            """, codes + [pct_th, start, end])
            if rows and rows[0].get("d"):
                first_surge = rows[0]["d"]
        rows = query(con, """
            SELECT MIN(trade_date) AS d FROM fact_sector_stock_daily
            WHERE stock_name = ? AND pct_chg >= ? AND trade_date BETWEEN ? AND ?
        """, [name, pct_th, start, end])
        if rows and rows[0].get("d"):
            d = rows[0]["d"]
            first_surge = min(first_surge, d) if first_surge else d
        start_day = first_limit or first_surge
        if start_day is None:
            continue
        out.append({
            "name": name,
            "strength": info["strength"],
            "gain": info.get("gain"),
            "start_day": start_day,
            "by_limit": first_limit is not None and (first_surge is None or first_limit <= first_surge),
        })
    out.sort(key=lambda r: (r["start_day"], r["strength"]))
    return out


# ---------------------------------------------------------------- 报告

def fmt_d(d) -> str:
    if isinstance(d, (date, datetime)):
        return d.strftime("%Y-%m-%d")
    return str(d or "未知")


def build_report(theme: str, start: date, end: date, concepts: list[str], news: list[dict],
                 members: dict[str, dict], sectors: list[dict], sec_tl: list[dict],
                 heat: list[dict], starts: list[dict], dropped: int = 0) -> str:
    lines = [f"# {theme} 发酵链路回溯", "",
             f"窗口：{fmt_d(start)} ~ {fmt_d(end)}　|　命中概念：{', '.join(concepts) or '无'}　|　成员公司：{len(members)}", ""]

    lines += ["## 1. 消息面时间线（知识库）", ""]
    dated = sorted([e for e in news if e["date"] and start <= e["date"] <= end], key=lambda e: e["date"])
    if dated:
        lines += ["| 日期 | 类型 | 内容 | 来源 |", "|---|---|---|---|"]
        lines += [f"| {fmt_d(e['date'])} | {e['kind']} | {e['text']} | {e['source']} |" for e in dated]
    else:
        lines.append("窗口内无带日期的消息面事件。")
    undated = len(news) - len([e for e in news if e["date"]])
    if undated:
        lines.append(f"\n（另有 {undated} 条无日期事件未列出）")
    lines.append("")

    lines += ["## 2. 板块发酵时间线", ""]
    if sectors:
        lines.append("映射板块：" + "、".join(f"{s['sector_name']}({s.get('match_type','')})" for s in sectors))
    key_days = [r for r in sec_tl if r.get("double_red_streak") in (1, 3) or r.get("multi_period_resonance")]
    if key_days:
        lines += ["", "| 日期 | 板块 | 涨幅% | 边际量% | 事件 |", "|---|---|---|---|---|"]
        for r in key_days:
            ev = []
            if r.get("double_red_streak") == 1:
                ev.append("双红启动")
            if r.get("double_red_streak") == 3:
                ev.append("双红加强(3连)")
            if r.get("multi_period_resonance"):
                ev.append("多周期共振")
            lines.append(f"| {fmt_d(r['trade_date'])} | {r['sector_name']} | {r.get('pct_chg') or 0:.2f} | {r.get('diff_ratio') or 0:.2f} | {'、'.join(ev)} |")
    else:
        lines.append("\n窗口内无双红/共振关键日（或缺板块数据）。")
    if heat:
        peak = max(heat, key=lambda r: r.get("limit_up_count") or 0)
        lines.append(f"\n涨停热度峰值：{fmt_d(peak['trade_date'])} {peak['sector_name']} 涨停 {peak.get('limit_up_count')} 家（rank {peak.get('rank')}）")
    lines.append("")

    lines += ["## 3. 个股启动梯队（起涨 vs 补涨，按区间涨幅筛选）", ""]
    if dropped:
        lines.append(f"命中公司较多，已按窗口区间涨幅取前 {len(members)} 名（core 层保底），筛掉 {dropped} 家。\n")
    if starts:
        first_day = starts[0]["start_day"]
        lines += ["| 启动日 | 公司 | 区间涨幅% | 知识库分层 | 触发 | 梯队 |", "|---|---|---|---|---|---|"]
        for r in starts:
            lag = (r["start_day"] - first_day).days if hasattr(r["start_day"] - first_day, "days") else 0
            tier = "起涨" if lag <= 2 else ("第二梯队" if lag <= 7 else "补涨")
            trig = "首板" if r["by_limit"] else "量价突破"
            g = f"{r['gain']:.1f}" if r.get("gain") is not None else "-"
            lines.append(f"| {fmt_d(r['start_day'])} | {r['name']} | {g} | {r['strength']} | {trig} | {tier}(+{lag}d) |")
    else:
        lines.append("窗口内无成员股启动记录（或 DuckDB 缺个股数据）。")
    lines.append("")

    lines += ["## 4. 消息 × 盘面合并链路", ""]
    seen = set()
    merged = []
    for e in dated:
        key = (e["date"], e["kind"], e["text"][:60])
        if key in seen:
            continue
        seen.add(key)
        merged.append((e["date"], f"📰 [{e['source']}] {e['kind']}：{e['text'][:60]}"))
    merged += [(r["trade_date"] if isinstance(r["trade_date"], date) else r["trade_date"].date() if hasattr(r["trade_date"], 'date') else r["trade_date"],
                f"📈 {r['sector_name']} {'双红启动' if r.get('double_red_streak') == 1 else '双红加强'}")
               for r in key_days if r.get("double_red_streak") in (1, 3)]
    merged += [(r["start_day"] if isinstance(r["start_day"], date) else r["start_day"],
                f"🚀 {r['name']} {'首板' if r['by_limit'] else '起涨'}（{r['strength']}）") for r in starts]
    merged = [(d if isinstance(d, date) else (d.date() if hasattr(d, "date") else None), t) for d, t in merged]
    merged = sorted([m for m in merged if m[0]], key=lambda m: m[0])
    if merged:
        cur = None
        for d, t in merged:
            if d != cur:
                lines.append(f"\n**{fmt_d(d)}**")
                cur = d
            lines.append(f"- {t}")
    else:
        lines.append("无可合并事件。")
    lines += ["", "---", f"生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}；数据源：知识库 wiki/relations + market_feature_store DuckDB（只读）。"]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="题材发酵链路回溯（消息面×盘面，只读）")
    ap.add_argument("--theme", required=True)
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--window", type=int, default=60, help="未指定 start 时回看的自然日数")
    ap.add_argument("--vault", default=None, help="知识库 wiki 目录")
    ap.add_argument("--pct-threshold", type=float, default=7.0, help="量价突破的单日涨幅阈值")
    ap.add_argument("--max-members", type=int, default=30, help="命中超过此数时按区间涨幅取 Top N（core 保底）")
    ap.add_argument("--out")
    args = ap.parse_args()

    vault = Path(os.path.expanduser(args.vault)) if args.vault else default_vault()
    if not (vault / "relations").is_dir():
        print(f"[error] 找不到知识库 relations: {vault}", file=sys.stderr)
        return 1
    end = date.fromisoformat(args.end) if args.end else date.today()
    start = date.fromisoformat(args.start) if args.start else end - timedelta(days=args.window)

    news, concepts = collect_news_events(args.theme, vault)
    members = collect_member_stocks(args.theme, concepts, vault)

    if not mfs_db.DB_PATH.is_file():
        print(f"[error] DuckDB 不存在: {mfs_db.DB_PATH}（需先在本机同步 market_feature_store）", file=sys.stderr)
        return 1
    con = mfs_db.connect(read_only=True)
    try:
        sectors = theme_sectors(con, args.theme)
        codes = [s["sector_ts_code"] for s in sectors if s.get("sector_ts_code")]
        sec_tl = sector_timeline(con, codes, start, end)
        heat = limit_heat(con, codes, start, end)
        gains = member_interval_gains(con, members, start, end)
        members, dropped = filter_members_by_gain(members, gains, args.max_members)
        starts = stock_start_days(con, members, codes, start, end, args.pct_threshold)
    finally:
        con.close()

    report = build_report(args.theme, start, end, concepts, news, members, sectors, sec_tl, heat, starts, dropped)
    out = Path(args.out) if args.out else Path(f"/tmp/fermentation-{args.theme}-{end.isoformat()}.md")
    out.write_text(report, encoding="utf-8")
    print(f"报告已写入: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
