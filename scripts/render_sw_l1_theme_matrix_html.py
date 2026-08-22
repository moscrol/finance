from __future__ import annotations

import argparse
import html
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# Direct execution needs the repository root on sys.path before project imports.
from market_feature_store.db import connect  # noqa: E402
from market_feature_store.signals import DOUBLE_RED_SQL, is_double_red, is_single_red  # noqa: E402

DEFAULT_SW_L1 = ["电子", "通信", "电力设备", "机械设备"]
DEFAULT_OUTPUT_DIR = Path("/Users/lbq/Desktop/复盘")


def fmt(value, digits: int = 1) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def fmt_pct(value, digits: int = 1) -> str:
    if value is None:
        return "-"
    return f"{float(value):.{digits}f}%"


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def latest_trade_date() -> str:
    con = connect(read_only=True)
    try:
        row = con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()
    finally:
        con.close()
    if not row or not row[0]:
        raise RuntimeError("fact_market_daily 中没有可用交易日")
    return str(row[0])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成申万一级曾双红题材区间透视表 HTML")
    parser.add_argument("--start-date", default="2026-04-08", help="开始交易日 YYYY-MM-DD")
    parser.add_argument("--end-date", default=None, help="结束交易日 YYYY-MM-DD；不传则取 fact_market_daily 最新日")
    parser.add_argument("--sw-l1", nargs="+", default=DEFAULT_SW_L1, help="申万一级列表")
    parser.add_argument("--output", default=None, help="输出 HTML 路径")
    return parser.parse_args()


def trade_dates(con, start: str, end: str) -> list[str]:
    rows = con.execute(
        """
        SELECT trade_date
        FROM fact_market_daily
        WHERE trade_date BETWEEN ? AND ?
        ORDER BY trade_date
        """,
        [start, end],
    ).fetchall()
    return [str(row[0]) for row in rows]


def market_map(con, start: str, end: str) -> dict[str, dict]:
    rows = con.execute(
        """
        SELECT trade_date, industry_1, industry_2, industry_3,
               industry_1_ratio, industry_2_ratio, industry_3_ratio,
               total_amount, sh_index_pct_chg
        FROM fact_market_daily
        WHERE trade_date BETWEEN ? AND ?
        ORDER BY trade_date
        """,
        [start, end],
    ).fetchall()
    out = {}
    for row in rows:
        d, i1, i2, i3, r1, r2, r3, amount, sh_pct = row
        out[str(d)] = {
            "industries": [x for x in [i1, i2, i3] if x],
            "ratios": {i1: r1, i2: r2, i3: r3},
            "amount": amount,
            "sh_pct": sh_pct,
        }
    return out


def sector_names(con, start: str, end: str, sw_l1: str) -> list[dict]:
    rows = con.execute(
        f"""
        SELECT sector_name, COUNT(*) AS dr_days, MIN(trade_date) AS first_day, MAX(trade_date) AS last_day,
               MAX(amount) AS max_amount, AVG(amount) AS avg_amount
        FROM fact_sector_daily
        WHERE trade_date BETWEEN ? AND ?
          AND sw_l1 = ?
          AND {DOUBLE_RED_SQL}
        GROUP BY sector_name
        ORDER BY dr_days DESC, max_amount DESC, sector_name
        """,
        [start, end, sw_l1],
    ).fetchall()
    return [
        {
            "name": row[0],
            "dr_days": int(row[1] or 0),
            "first_day": str(row[2]),
            "last_day": str(row[3]),
            "max_amount": row[4],
            "avg_amount": row[5],
        }
        for row in rows
    ]


def parent_map(con, start: str, end: str, sw_l1: str) -> dict[str, tuple]:
    rows = con.execute(
        """
        SELECT trade_date, fupanhui_ratio, pct_chg
        FROM fact_sw_l1_daily
        WHERE trade_date BETWEEN ? AND ? AND sw_l1 = ?
        """,
        [start, end, sw_l1],
    ).fetchall()
    return {str(row[0]): (row[1], row[2]) for row in rows}


def value_map(con, start: str, end: str, sw_l1: str, sectors: list[str]) -> dict[tuple[str, str], tuple]:
    if not sectors:
        return {}
    placeholders = ",".join("?" for _ in sectors)
    rows = con.execute(
        f"""
        SELECT trade_date, sector_name, pct_chg, diff_ratio, amount
        FROM fact_sector_daily
        WHERE trade_date BETWEEN ? AND ?
          AND sw_l1 = ?
          AND sector_name IN ({placeholders})
        """,
        [start, end, sw_l1] + sectors,
    ).fetchall()
    return {(str(row[0]), row[1]): (row[2], row[3], row[4]) for row in rows}


def build_data(start: str, end: str, sw_l1_list: list[str]) -> dict:
    con = connect(read_only=True)
    try:
        dates = trade_dates(con, start, end)
        market = market_map(con, start, end)
        groups = []
        for sw in sw_l1_list:
            sectors = sector_names(con, start, end, sw)
            names = [item["name"] for item in sectors]
            parent = parent_map(con, start, end, sw)
            values = value_map(con, start, end, sw, names)
            groups.append({"sw_l1": sw, "sectors": sectors, "parent": parent, "values": values})
        return {"start": start, "end": end, "dates": dates, "market": market, "groups": groups}
    finally:
        con.close()


def cell_payload(value) -> dict:
    if value is None:
        return {"text": "-", "klass": "empty", "title": "无数据"}
    pct, diff, amount = value
    if pct is None or diff is None or amount is None:
        return {"text": "-", "klass": "empty", "title": "无数据"}
    is_double = is_double_red(pct, diff, amount)
    is_divergence = pct < 0 and diff > 10 and amount > 500  # 放量分歧，另一族谓词
    is_single = is_single_red(pct, diff, amount)
    klass = "cell"
    if is_double:
        klass += " double"
    elif is_divergence:
        klass += " divergence"
    elif is_single:
        klass += " single"
    elif pct > 0:
        klass += " up"
    elif pct < 0:
        klass += " down"
    text = f"{fmt_pct(pct)}/{fmt(diff)}/{fmt(amount, 0)}"
    if is_double:
        text = "🔥" + text
    title = f"涨幅 {fmt_pct(pct)}，边际量 {fmt(diff)}，成交额 {fmt(amount, 0)}亿"
    return {"text": text, "klass": klass, "title": title}


def render_table(group: dict, dates: list[str], market: dict[str, dict]) -> str:
    sw = group["sw_l1"]
    lines = []
    lines.append('<div class="matrix-wrap">')
    lines.append('<table class="matrix">')
    lines.append("<thead><tr>")
    lines.append('<th class="topic-col">题材</th>')
    for d in dates:
        lines.append(f'<th class="date-col">{esc(d[5:])}</th>')
    lines.append("</tr></thead>")
    lines.append("<tbody>")
    lines.append('<tr class="meta-row">')
    lines.append(f'<th class="topic-col">申万一级：{esc(sw)}<span>占比/涨跌幅</span></th>')
    for d in dates:
        ratio, pct = group["parent"].get(d, (None, None))
        text = "-" if ratio is None and pct is None else f"{fmt_pct(ratio)}/{fmt_pct(pct)}"
        lines.append(f'<td class="meta-cell">{esc(text)}</td>')
    lines.append("</tr>")
    lines.append('<tr class="meta-row top3-row">')
    lines.append('<th class="topic-col">容量前三状态<span>Top3/占比</span></th>')
    for d in dates:
        rec = market.get(d, {})
        industries = rec.get("industries", [])
        ratios = rec.get("ratios", {})
        if sw in industries:
            text = f"Top3/{fmt_pct(ratios.get(sw))}"
            klass = "meta-cell top3-hit"
        else:
            text = "-"
            klass = "meta-cell"
        lines.append(f'<td class="{klass}">{esc(text)}</td>')
    lines.append("</tr>")
    for item in group["sectors"]:
        name = item["name"]
        lines.append(f'<tr class="topic-row" data-topic="{esc(name.lower())}">')
        badge = f'{item["dr_days"]}次'
        lines.append(f'<th class="topic-col"><strong>{esc(name)}</strong><span>{esc(badge)}｜{esc(item["first_day"][5:])}~{esc(item["last_day"][5:])}</span></th>')
        for d in dates:
            payload = cell_payload(group["values"].get((d, name)))
            lines.append(f'<td class="{payload["klass"]}" title="{esc(payload["title"])}">{esc(payload["text"])}</td>')
        lines.append("</tr>")
    lines.append("</tbody></table></div>")
    return "".join(lines)


def stat_cards(data: dict) -> str:
    total_topics = sum(len(g["sectors"]) for g in data["groups"])
    dates = len(data["dates"])
    total_double = sum(item["dr_days"] for g in data["groups"] for item in g["sectors"])
    cards = [
        ("区间", f'{data["start"]} → {data["end"]}'),
        ("交易日", f"{dates} 天"),
        ("申万一级", f"{len(data['groups'])} 个"),
        ("曾双红题材", f"{total_topics} 个"),
        ("双红记录", f"{total_double} 条"),
    ]
    return "".join(f'<article class="card"><span>{esc(k)}</span><strong>{esc(v)}</strong></article>' for k, v in cards)


def render_html(data: dict) -> str:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nav = "".join(f'<a href="#{esc(g["sw_l1"])}">{esc(g["sw_l1"])}<span>{len(g["sectors"])}</span></a>' for g in data["groups"])
    sections = []
    for group in data["groups"]:
        top_topics = "、".join(item["name"] for item in group["sectors"][:6]) or "-"
        sections.append(
            f'''
            <section class="panel" id="{esc(group["sw_l1"])}" data-sw="{esc(group["sw_l1"])}">
              <div class="panel-head">
                <div>
                  <p class="eyebrow">SW L1 Matrix</p>
                  <h2>{esc(group["sw_l1"])}</h2>
                  <p class="hint">曾双红题材 {len(group["sectors"])} 个；高频题材：{esc(top_topics)}</p>
                </div>
                <button class="collapse" type="button">收起/展开</button>
              </div>
              {render_table(group, data["dates"], data["market"])}
            </section>
            '''
        )
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>主线容量板块题材透视表 {esc(data["start"])}~{esc(data["end"])}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #080b0f;
  --panel: rgba(18, 24, 32, 0.86);
  --panel2: rgba(11, 16, 22, 0.92);
  --line: rgba(173, 191, 209, 0.16);
  --text: #e6edf5;
  --muted: #8c9aaa;
  --gold: #f4c76b;
  --red: #ff5d57;
  --green: #38d88a;
  --blue: #76b8ff;
  --orange: #ff9b50;
  --shadow: 0 24px 80px rgba(0, 0, 0, 0.42);
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  margin: 0;
  color: var(--text);
  background:
    radial-gradient(circle at 8% 0%, rgba(244,199,107,0.14), transparent 28rem),
    radial-gradient(circle at 88% 12%, rgba(118,184,255,0.13), transparent 24rem),
    linear-gradient(135deg, #06080c 0%, #0c1118 46%, #05070a 100%);
  font-family: "Baskerville", "Songti SC", "Noto Serif CJK SC", serif;
}}
body::before {{
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  opacity: 0.22;
  background-image: linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px);
  background-size: 34px 34px;
  mask-image: linear-gradient(to bottom, black, transparent 78%);
}}
.header {{
  position: sticky;
  top: 0;
  z-index: 20;
  backdrop-filter: blur(18px);
  background: rgba(8, 11, 15, 0.78);
  border-bottom: 1px solid var(--line);
}}
.header-inner {{
  max-width: 1680px;
  margin: 0 auto;
  padding: 18px 24px;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 18px;
  align-items: center;
}}
h1 {{
  margin: 0;
  font-size: clamp(28px, 4vw, 58px);
  letter-spacing: -0.05em;
  line-height: 0.95;
}}
.subtitle {{ margin: 8px 0 0; color: var(--muted); font-family: "Avenir Next", "PingFang SC", sans-serif; }}
.toolbar {{ display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }}
.toolbar input, .toolbar button {{
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.06);
  color: var(--text);
  border-radius: 999px;
  padding: 10px 14px;
  font-family: "Avenir Next", "PingFang SC", sans-serif;
}}
.toolbar input {{ min-width: 240px; outline: none; }}
.toolbar button {{ cursor: pointer; }}
.shell {{ max-width: 1680px; margin: 0 auto; padding: 28px 24px 80px; }}
.cards {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; margin-bottom: 18px; }}
.card {{
  background: linear-gradient(145deg, rgba(255,255,255,0.09), rgba(255,255,255,0.03));
  border: 1px solid var(--line);
  border-radius: 22px;
  padding: 18px;
  box-shadow: var(--shadow);
}}
.card span {{ display: block; color: var(--muted); font-family: "Avenir Next", "PingFang SC", sans-serif; font-size: 12px; text-transform: uppercase; letter-spacing: .12em; }}
.card strong {{ display: block; margin-top: 8px; font-size: 24px; }}
.nav {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 18px 0 26px; }}
.nav a {{
  color: var(--text);
  text-decoration: none;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 10px 14px;
  background: rgba(255,255,255,0.05);
  font-family: "Avenir Next", "PingFang SC", sans-serif;
}}
.nav span {{ margin-left: 8px; color: var(--gold); }}
.legend {{
  color: var(--muted);
  border: 1px solid var(--line);
  background: rgba(0,0,0,0.25);
  padding: 14px 16px;
  border-radius: 18px;
  font-family: "Avenir Next", "PingFang SC", sans-serif;
  margin-bottom: 20px;
}}
.panel {{
  margin: 26px 0;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 28px;
  overflow: hidden;
  box-shadow: var(--shadow);
}}
.panel-head {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 24px;
  background: linear-gradient(90deg, rgba(244,199,107,0.12), rgba(118,184,255,0.06), transparent);
  border-bottom: 1px solid var(--line);
}}
.eyebrow {{ margin: 0 0 6px; color: var(--gold); font-family: "Avenir Next", "PingFang SC", sans-serif; letter-spacing: .18em; text-transform: uppercase; font-size: 12px; }}
h2 {{ margin: 0; font-size: 34px; letter-spacing: -0.03em; }}
.hint {{ margin: 8px 0 0; color: var(--muted); font-family: "Avenir Next", "PingFang SC", sans-serif; }}
.collapse {{ border: 1px solid var(--line); background: rgba(0,0,0,0.26); color: var(--text); border-radius: 999px; padding: 10px 14px; cursor: pointer; }}
.matrix-wrap {{ overflow: auto; max-height: 76vh; background: var(--panel2); }}
.matrix {{ border-collapse: separate; border-spacing: 0; width: max-content; min-width: 100%; font-family: "Avenir Next", "PingFang SC", sans-serif; font-size: 12px; }}
th, td {{ border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); padding: 8px 10px; white-space: nowrap; }}
thead th {{ position: sticky; top: 0; z-index: 5; background: #111923; color: var(--gold); }}
.topic-col {{ position: sticky; left: 0; z-index: 6; min-width: 210px; max-width: 260px; background: #101721; text-align: left; }}
thead .topic-col {{ z-index: 8; }}
.topic-col strong {{ display: block; font-size: 13px; }}
.topic-col span {{ display: block; margin-top: 4px; color: var(--muted); font-size: 11px; }}
.meta-row .topic-col {{ color: var(--blue); }}
.meta-cell {{ color: var(--muted); background: rgba(118,184,255,0.04); }}
.top3-hit {{ color: var(--gold); background: rgba(244,199,107,0.12); }}
.cell {{ text-align: right; color: #cbd7e3; }}
.double {{ color: #fff3e8; background: linear-gradient(180deg, rgba(255,93,87,0.42), rgba(244,199,107,0.16)); font-weight: 800; }}
.divergence {{ color: #c9ffdf; background: rgba(56,216,138,0.18); }}
.single {{ color: #f8e2a3; background: rgba(244,199,107,0.10); }}
.up {{ color: #ffcbc6; background: rgba(255,93,87,0.08); }}
.down {{ color: #b9f7d4; background: rgba(56,216,138,0.08); }}
.empty {{ color: #46515f; text-align: center; }}
.panel.is-collapsed .matrix-wrap {{ display: none; }}
.topic-row.is-hidden {{ display: none; }}
.footer {{ color: var(--muted); font-family: "Avenir Next", "PingFang SC", sans-serif; margin-top: 36px; }}
@media (max-width: 980px) {{
  .header-inner {{ grid-template-columns: 1fr; }}
  .toolbar {{ justify-content: flex-start; }}
  .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
}}
</style>
</head>
<body>
<header class="header">
  <div class="header-inner">
    <div>
      <h1>主线容量板块题材透视表</h1>
      <p class="subtitle">{esc(data["start"])} 至 {esc(data["end"])}｜涨幅 / 边际量 / 成交额亿｜每日可刷新追加</p>
    </div>
    <div class="toolbar">
      <input id="search" type="search" placeholder="搜索题材，例如 CPO、光伏、机器人">
      <button id="doubleOnly" type="button">只看含双红行</button>
      <button id="expandAll" type="button">展开全部</button>
    </div>
  </div>
</header>
<main class="shell">
  <div class="cards">{stat_cards(data)}</div>
  <nav class="nav">{nav}</nav>
  <div class="legend">🔥 双红 = 涨幅 &gt; 0、边际量 &gt; 10、成交额 &gt; 500亿，使用红色系；绿色系 = 下跌/放量分歧；金底无🔥 = 小容量单红或未过双红阈值。首列与表头已冻结，可横向滚动查看全区间。</div>
  {''.join(sections)}
  <p class="footer">生成时间：{esc(generated)}｜脚本：scripts/render_sw_l1_theme_matrix_html.py</p>
</main>
<script>
const searchInput = document.getElementById('search');
const doubleButton = document.getElementById('doubleOnly');
const expandButton = document.getElementById('expandAll');
let onlyDouble = false;
function applyFilter() {{
  const q = searchInput.value.trim().toLowerCase();
  document.querySelectorAll('.topic-row').forEach(row => {{
    const hitText = !q || row.dataset.topic.includes(q);
    const hitDouble = !onlyDouble || !!row.querySelector('.double');
    row.classList.toggle('is-hidden', !(hitText && hitDouble));
  }});
}}
searchInput.addEventListener('input', applyFilter);
doubleButton.addEventListener('click', () => {{
  onlyDouble = !onlyDouble;
  doubleButton.textContent = onlyDouble ? '显示全部行' : '只看含双红行';
  applyFilter();
}});
expandButton.addEventListener('click', () => {{
  document.querySelectorAll('.panel').forEach(panel => panel.classList.remove('is-collapsed'));
}});
document.querySelectorAll('.collapse').forEach(button => {{
  button.addEventListener('click', () => button.closest('.panel').classList.toggle('is-collapsed'));
}});
</script>
</body>
</html>'''


def main() -> int:
    args = parse_args()
    end_date = args.end_date or latest_trade_date()
    output = Path(args.output).expanduser().resolve() if args.output else DEFAULT_OUTPUT_DIR / f"sw-theme-matrix-{args.start_date}-{end_date}.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    data = build_data(args.start_date, end_date, args.sw_l1)
    output.write_text(render_html(data), encoding="utf-8")
    print(f"HTML: {output}")
    print(f"区间: {args.start_date} ~ {end_date}")
    print("申万一级: " + "、".join(args.sw_l1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
