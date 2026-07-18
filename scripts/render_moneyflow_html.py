#!/usr/bin/env python3
"""大单资金流看板：DuckDB feature 表 → 单页 HTML（复盘/moneyflow/index.html）。

数据来自 market_feature_store 的两张特征表（由 scripts/moneyflow/ 扫描后写入）：

- ``feature_l2_capital_flow_daily``：昨日涨停榜(limitup) / 成交额前100榜(top100)
- ``feature_l2_quant_orders_daily``：量化买单榜

全部日期的数据内嵌为 JSON，页面内用日期下拉 + 三个页签切换，表头点击排序，
不依赖任何外部资源，双击即开。视觉沿用驾驶舱 paper 主题。本页不入 git。

Usage:
    python3 scripts/render_moneyflow_html.py
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from market_feature_store.db import connect  # noqa: E402

_DATA_ROOT = Path(os.environ.get("FINANCE_DATA_ROOT", ROOT)).expanduser()
OUT_PATH = _DATA_ROOT / "复盘" / "moneyflow" / "index.html"

FLOW_COLS = [
    ("rank", "名次"), ("stock_code", "代码"), ("stock_name", "名称"),
    ("score", "综合得分"), ("main_buy_net_wan", "主买净额(万)"),
    ("total_buy_net_wan", "总买净额(万)"), ("float_mktcap_yi", "流通市值(亿)"),
    ("pct_change", "当日涨幅%"),
]
QUANT_COLS = [
    ("rank", "名次"), ("stock_code", "代码"), ("stock_name", "名称"),
    ("quant_pct_of_big_buy", "量化占大单买入%"), ("quant_amount_wan", "量化单总额(万)"),
    ("cluster_count", "簇数"), ("order_count", "笔数"),
    ("biggest_cluster", "最大簇"), ("pct_change", "当日涨幅%"),
]

CSS = """
:root{--paper:#f6f0e6;--paper-2:#fffaf1;--ink:#17140f;--muted:#746b5d;--line:#d8cbbb;--line-strong:#18140f;--accent:#0057ff;--accent-2:#ff5a1f;--card:#fffdf8;--shadow:0 18px 45px rgba(38,28,13,.08)}
*{box-sizing:border-box}
body{margin:0;background:linear-gradient(90deg,rgba(23,20,15,.045) 1px,transparent 1px),linear-gradient(rgba(23,20,15,.035) 1px,transparent 1px),var(--paper);background-size:28px 28px;color:var(--ink);font-family:'Avenir Next','PingFang SC','Hiragino Sans GB',sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:28px 24px}
.kicker{font-size:12px;letter-spacing:.28em;font-weight:900;color:var(--accent);text-transform:uppercase}
h1{font-family:'Bodoni 72','Songti SC',serif;font-size:52px;line-height:.95;letter-spacing:-.05em;margin:10px 0 8px}
.sub{color:var(--muted);font-size:14px;line-height:1.7;max-width:860px}
.bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:22px 0 14px}
.tabs{display:flex;gap:8px}
.tabs button{min-height:40px;border:1px solid var(--line-strong);background:var(--paper-2);color:var(--ink);padding:8px 16px;font-weight:800;cursor:pointer;font-size:14px}
.tabs button.on{background:var(--ink);color:var(--paper-2)}
select{min-height:40px;border:1px solid var(--line-strong);background:var(--paper-2);padding:8px 12px;font-weight:800;font-size:14px}
.meta{font-size:12px;color:var(--muted);margin-left:auto}
table{width:100%;border-collapse:collapse;background:var(--card);box-shadow:var(--shadow);border:1px solid var(--line-strong)}
th,td{padding:9px 12px;border-bottom:1px solid var(--line);font-size:13px;text-align:right;white-space:nowrap}
th{background:var(--paper-2);font-size:12px;letter-spacing:.06em;cursor:pointer;user-select:none;position:sticky;top:0}
th:hover{color:var(--accent)}
td:nth-child(2),td:nth-child(3),th:nth-child(2),th:nth-child(3){text-align:left}
tr:nth-child(even) td{background:rgba(23,20,15,.02)}
td.pos{color:#b02318;font-weight:700}td.neg{color:#0a7a3d;font-weight:700}
.note{font-size:12px;color:var(--muted);margin-top:12px;line-height:1.7}
a.home{color:var(--accent);font-weight:800;text-decoration:none;font-size:13px}
"""

JS = """
const COLS={flow:%(flow_cols)s,quant:%(quant_cols)s};
const DATA=%(data)s;
let tab='limitup',dt=null,sortKey=null,sortDesc=true;
const PCT_COLS=new Set(['pct_change','score','quant_pct_of_big_buy']);
function dates(){return Object.keys(DATA[tab]||{}).sort().reverse();}
function fmt(v,k){if(v===null||v===undefined)return'-';if(typeof v==='number'){return Math.abs(v)>=100?v.toLocaleString('en-US',{maximumFractionDigits:0}):v.toLocaleString('en-US',{maximumFractionDigits:2});}return v;}
function render(){
  const ds=dates();if(!ds.includes(dt))dt=ds[0]||null;
  const sel=document.getElementById('date');sel.innerHTML=ds.map(d=>`<option ${d===dt?'selected':''}>${d}</option>`).join('');
  document.querySelectorAll('.tabs button').forEach(b=>b.classList.toggle('on',b.dataset.t===tab));
  const kind=tab==='quant'?'quant':'flow';const cols=COLS[kind];
  let rows=(DATA[tab][dt]||[]).slice();
  if(sortKey)rows.sort((a,b)=>{const x=a[sortKey],y=b[sortKey];if(x===y)return 0;if(x===null)return 1;if(y===null)return -1;return (x<y?-1:1)*(sortDesc?-1:1);});
  const thead='<tr>'+cols.map(([k,l])=>`<th data-k="${k}">${l}${sortKey===k?(sortDesc?' ↓':' ↑'):''}</th>`).join('')+'</tr>';
  const tbody=rows.map(r=>'<tr>'+cols.map(([k])=>{
    let cls='';if(typeof r[k]==='number'&&['main_buy_net_wan','total_buy_net_wan','pct_change','score'].includes(k))cls=r[k]>0?'pos':(r[k]<0?'neg':'');
    return `<td class="${cls}">${fmt(r[k],k)}</td>`;}).join('')+'</tr>').join('');
  document.getElementById('tbl').innerHTML=thead+tbody;
  document.getElementById('cnt').textContent=rows.length+' 只';
  document.querySelectorAll('th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;if(sortKey===k)sortDesc=!sortDesc;else{sortKey=k;sortDesc=true;}render();});
}
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{tab=b.dataset.t;sortKey=null;render();});
document.getElementById('date').onchange=e=>{dt=e.target.value;render();};
render();
"""


def fetch() -> dict:
    con = connect(read_only=True)
    try:
        data: dict = {"limitup": {}, "top100": {}, "quant": {}}
        for st in ("limitup", "top100"):
            rows = con.execute(
                "SELECT trade_date, rank, stock_code, stock_name, score, main_buy_net_wan, "
                "total_buy_net_wan, float_mktcap_yi, pct_change "
                "FROM feature_l2_capital_flow_daily WHERE scan_type=? ORDER BY trade_date, rank",
                [st]).fetchall()
            for r in rows:
                data[st].setdefault(str(r[0]), []).append(dict(zip(
                    [c for c, _ in FLOW_COLS], [r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]])))
        rows = con.execute(
            "SELECT trade_date, rank, stock_code, stock_name, quant_pct_of_big_buy, quant_amount_wan, "
            "cluster_count, order_count, biggest_cluster, pct_change "
            "FROM feature_l2_quant_orders_daily ORDER BY trade_date, rank").fetchall()
        for r in rows:
            data["quant"].setdefault(str(r[0]), []).append(dict(zip(
                [c for c, _ in QUANT_COLS], [r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9]])))
        return data
    finally:
        con.close()


def main() -> int:
    data = fetch()
    n = {k: sum(len(v) for v in d.values()) for k, d in data.items()}
    built = datetime.date.today().isoformat()
    js = JS % {
        "flow_cols": json.dumps(FLOW_COLS, ensure_ascii=False),
        "quant_cols": json.dumps(QUANT_COLS, ensure_ascii=False),
        "data": json.dumps(data, ensure_ascii=False),
    }
    html = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>大单资金流看板</title>"
        f"<style>{CSS}</style></head><body><div class='wrap'>"
        '<a class="home" href="../index.html">← 驾驶舱总入口</a>'
        '<div class="kicker">L2 Capital Flow</div><h1>大单资金流看板</h1>'
        '<div class="sub">数据源 ClickHouse 逐笔成交（自有大单口径：同一委托单当日累计≥50万，'
        "委托编号判主动方向），综合得分 = (0.7×主买 + 0.3×总买) ÷ 流通市值 ×100。"
        "结果由 scripts/moneyflow/ 扫描后写入 DuckDB 特征表，本页按日期展示全部入选股，"
        "点表头可排序。</div>"
        '<div class="bar"><div class="tabs">'
        '<button data-t="limitup">昨日涨停榜</button>'
        '<button data-t="top100">成交额前100榜</button>'
        '<button data-t="quant">量化单榜</button></div>'
        '<select id="date"></select><span class="meta"><span id="cnt"></span>'
        f" · BUILT {built}</span></div>"
        '<table id="tbl"></table>'
        '<div class="note">量化单 = 金额±1%窄带、反复出现≥10笔的大买单簇（单笔≥200万）；'
        "占比越高说明买盘越机器化。数据缺日期时先运行 scripts/moneyflow/ 的扫描脚本回填。</div>"
        f"</div><script>{js}</script></body></html>"
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")
    print(OUT_PATH)
    print(f"limitup: {n['limitup']} | top100: {n['top100']} | quant: {n['quant']} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
