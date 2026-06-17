#!/usr/bin/env python3
"""render_winrate_html: 把「卖方机构胜率榜」渲染成自包含浅色 paper HTML（双击即开、零依赖）。

复用 winrate_rank.py 的聚合逻辑，一次性算好 T+3/5/7/10 四个窗口的榜单内联进页面，
前端切换窗口、排序、画「超额胜率柱状图」与「均超额 vs 均回撤 风险收益散点」。

  python3 render_winrate_html.py [--vault <wiki>] [--outcomes <path>]
                                 [--min-calls 5] [--windows 3,5,7,10]
                                 [--out <html>] [--date <YYYY-MM-DD>]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from winrate_rank import (  # noqa: E402
    aggregate_winrate,
    load_outcomes,
    load_sources,
    resolve_store,
    resolve_vault,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

PAGE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--paper:#f6f0e6;--paper-2:#fffaf1;--ink:#17140f;--muted:#746b5d;--line:#d8cbbb;--line-strong:#18140f;--accent:#0057ff;--accent-2:#ff5a1f;--card:#fffdf8;--shadow:0 18px 45px rgba(38,28,13,.08);--pos:#0a7d3c;--neg:#c2401d}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:linear-gradient(90deg,rgba(23,20,15,.045) 1px,transparent 1px),linear-gradient(rgba(23,20,15,.035) 1px,transparent 1px),var(--paper);background-size:28px 28px;color:var(--ink);font-family:'Avenir Next','PingFang SC','Hiragino Sans GB',sans-serif}
.skip{position:absolute;left:-999px;top:12px;background:var(--accent);color:#fff;padding:10px 14px;border-radius:999px;z-index:10}.skip:focus{left:16px}
.shell{display:grid;grid-template-columns:320px minmax(0,1fr);gap:28px;max-width:1760px;margin:0 auto;padding:24px}
.rail{position:sticky;top:24px;height:calc(100dvh - 48px);overflow:auto;border:1px solid var(--line-strong);background:rgba(255,250,241,.88);backdrop-filter:blur(14px);box-shadow:var(--shadow);padding:22px}
.mark{font-family:'Bodoni 72','Songti SC',serif;font-size:42px;line-height:.86;letter-spacing:-.06em}
.date-card{margin:22px 0;padding:18px;border:1px solid var(--line);background:var(--card)}.date-card .label{font-size:11px;letter-spacing:.18em;color:var(--muted);font-weight:900}.date-card .date{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;font-size:34px;font-weight:900;margin-top:6px}
.win-toggle{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}
.win-toggle button{min-height:40px;border:1px solid var(--line-strong);background:var(--paper-2);color:var(--ink);padding:8px 14px;cursor:pointer;font-weight:800}
.win-toggle button.active{background:var(--ink);color:var(--paper-2)}
.legend{color:var(--muted);font-size:12px;line-height:1.7;margin-top:14px;border-top:1px solid var(--line);padding-top:12px}
.legend b{color:var(--ink)}
.content{min-width:0}
.hero{position:relative;border:1px solid var(--line-strong);background:var(--paper-2);padding:34px 38px 30px;margin-bottom:24px;box-shadow:var(--shadow);overflow:hidden}
.hero:before{content:'';position:absolute;right:32px;top:28px;width:120px;height:120px;border:18px solid var(--accent);border-left-color:transparent;border-radius:50%;opacity:.9}
.kicker{font-size:12px;letter-spacing:.28em;font-weight:900;color:var(--accent);text-transform:uppercase}
.hero h1{font-family:'Bodoni 72','Songti SC',serif;font-size:60px;line-height:.92;letter-spacing:-.05em;margin:14px 0 16px;max-width:780px}
.hero .sub{max-width:760px;color:var(--muted);font-size:16px;line-height:1.7}
.kpis{display:flex;flex-wrap:wrap;gap:14px;margin-top:22px}
.kpi{border:1px solid var(--line-strong);background:var(--card);box-shadow:var(--shadow);padding:14px 18px;min-width:130px}
.kpi .v{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;font-size:32px;font-weight:900;line-height:1;color:var(--ink)}
.kpi .l{color:var(--muted);font-size:11px;letter-spacing:.14em;font-weight:900;margin-top:4px}
h2{display:flex;align-items:baseline;gap:12px;margin:38px 0 14px;padding-top:18px;border-top:3px solid var(--line-strong);font-family:'Songti SC','Noto Serif SC',serif;font-size:28px;line-height:1.2;letter-spacing:-.02em}
h2:before{content:'§';color:var(--accent-2);font-family:'Bodoni 72',serif}
.note{border-left:5px solid var(--accent-2);background:#fff4e9;padding:12px 16px;margin:12px 0;color:#3b2b1e;font-size:13px;line-height:1.7}
.charts{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:1100px){.charts{grid-template-columns:1fr}}
@media(max-width:980px){.shell{display:block;padding:14px}.rail{position:relative;height:auto;margin-bottom:16px}}
.card{border:1px solid var(--line-strong);background:var(--card);box-shadow:var(--shadow);padding:18px}
.card h3{margin:0 0 6px;font-size:16px;color:var(--ink);font-family:'Songti SC','Noto Serif SC',serif}
.card .cap{color:var(--muted);font-size:12px;margin-bottom:8px}
.tablebox{overflow:auto;max-height:80vh;border:1px solid var(--line-strong);background:var(--card);box-shadow:var(--shadow);margin:14px 0 26px}
table{border-collapse:separate;border-spacing:0;width:100%;font-size:13px}
th,td{padding:10px 12px;border-bottom:1px solid var(--line);white-space:nowrap;text-align:right}
th:nth-child(2),td:nth-child(2){text-align:left}
th{position:sticky;top:0;background:var(--ink);color:var(--paper-2);cursor:pointer;user-select:none;z-index:2;font-weight:900}
th:hover{color:#fff}
tr:hover td{background:#f4f7ff}
td.rank{color:var(--muted);font-weight:700}
td.name{color:var(--ink);font-weight:900}
.bar-pos{color:var(--pos)}.bar-neg{color:var(--neg)}
.dot{cursor:default}
.tip{fill:#4a4234;font-size:11px}
.axis{stroke:var(--line-strong)}.axis-txt{fill:var(--muted);font-size:10px}
.foot{color:var(--muted);font-size:12px;margin:30px 0 8px;text-align:center}
</style></head><body><a class="skip" href="#main">跳到正文</a><div class="shell">
<aside class="rail">
  <div class="mark">Win<br>Rate</div>
  <div class="date-card"><div class="label">GENERATED</div><div class="date">__STAMP__</div></div>
  <div class="win-toggle" id="winToggle"></div>
  <div class="legend">
    <p><b>口径</b>：报告日次日开盘买入，持有至 T+N 收盘。</p>
    <p><b>超额</b> = 个股收益 − 沪深300 同窗收益（剥大盘 beta）。</p>
    <p><b>超额胜率</b> = 超额为正的看多事件占比，主排序键。</p>
    <p><b>均最高</b> = 区间最高收益均值（最好情形）；<b>均回撤</b> = 峰值后回撤均值（风险）。</p>
    <p>仅统计窗口完整的看多事件；样本不足门槛的机构不排。</p>
  </div>
</aside>
<main class="content" id="main">
  <section class="hero">
    <div class="kicker">SELL-SIDE INSTITUTION WIN-RATE</div>
    <h1>卖方机构<br>胜率榜</h1>
    <div class="sub" id="heroSub"></div>
    <div class="kpis" id="kpis"></div>
  </section>
  <h2 id="charts-h">胜率分布 · 风险收益</h2>
  <div class="charts">
    <div class="card"><h3>超额胜率排行</h3><div class="cap">前 15 名机构，按当前窗口超额胜率</div><div id="barChart"></div></div>
    <div class="card"><h3>均超额 vs 均回撤</h3><div class="cap">右上=高收益低风险；点大小∝样本数</div><div id="scatterChart"></div></div>
  </div>
  <h2 id="table-h">机构胜率榜</h2>
  <div class="note" id="tableNote"></div>
  <div class="tablebox"><table id="rankTable"><thead></thead><tbody></tbody></table></div>
  <div class="foot">__GENERATED__ · 数据源 opinion-store/outcomes.jsonl · 自包含静态页</div>
</main></div>
<script>
const DATA = __DATA__;
const COLS = [
  {k:'rank', t:'#'}, {k:'name', t:'机构'}, {k:'n', t:'样本n'},
  {k:'win_exc', t:'超额胜率', pct:true}, {k:'win_abs', t:'绝对胜率', pct:true},
  {k:'avg_exc', t:'均超额', sign:true}, {k:'med_exc', t:'中位超额', sign:true},
  {k:'avg_maxhit', t:'均最高', sign:true}, {k:'avg_dd', t:'均回撤', sign:true}
];
let curWin = DATA.windows[0];
let sortKey = 'win_exc', sortDir = -1;

function rowsFor(w){ return DATA.byWindow[w].rows; }
function fmt(v, col){
  if(col.pct) return (v*100).toFixed(0)+'%';
  if(col.sign) return (v>=0?'+':'')+v.toFixed(1);
  return v;
}
function renderToggle(){
  const box = document.getElementById('winToggle'); box.innerHTML='';
  DATA.windows.forEach(w=>{
    const b=document.createElement('button'); b.textContent='T+'+w;
    if(w===curWin) b.className='active';
    b.onclick=()=>{curWin=w; renderAll();}; box.appendChild(b);
  });
}
function renderHero(){
  const m = DATA.byWindow[curWin];
  document.getElementById('heroSub').textContent =
    '当前窗口 T+'+curWin+' · 相对沪深300超额 · 有效看多 ≥ '+DATA.min_calls+' 次才入榜';
  const kpis=[['合格机构',m.rows.length],['样本事件',m.events],
    ['全胜机构(100%)',m.rows.filter(r=>r.win_exc>=1).length],
    ['榜首超额胜率',(m.rows.length?(m.rows[0].win_exc*100).toFixed(0):'0')+'%']];
  document.getElementById('kpis').innerHTML = kpis.map(k=>
    '<div class="kpi"><div class="v">'+k[1]+'</div><div class="l">'+k[0]+'</div></div>').join('');
  document.getElementById('tableNote').textContent =
    '口径=T+'+curWin+' 相对沪深300超额>0 | 门槛=有效看多≥'+DATA.min_calls+'次 | 合格机构='
    +m.rows.length+' | 样本事件='+m.events+' | 点击表头排序';
}
function sortedRows(){
  const rows = rowsFor(curWin).slice();
  rows.sort((a,b)=>{
    if(sortKey==='name') return sortDir*(''+a.name).localeCompare(''+b.name,'zh');
    return sortDir*((a[sortKey]??0)-(b[sortKey]??0));
  });
  return rows;
}
function renderTable(){
  const rows = sortedRows();
  const thead = document.querySelector('#rankTable thead');
  thead.innerHTML = '<tr>'+COLS.map(c=>{
    const arrow = (c.k===sortKey)?(sortDir<0?' ▾':' ▴'):'';
    return '<th data-k="'+c.k+'">'+c.t+arrow+'</th>';
  }).join('')+'</tr>';
  thead.querySelectorAll('th').forEach(th=>th.onclick=()=>{
    const k=th.dataset.k;
    if(k===sortKey) sortDir=-sortDir; else {sortKey=k; sortDir=(k==='name')?1:-1;}
    renderTable();
  });
  const tb = document.querySelector('#rankTable tbody');
  tb.innerHTML = rows.map((r,i)=>'<tr>'+COLS.map(c=>{
    if(c.k==='rank') return '<td class="rank">'+(i+1)+'</td>';
    if(c.k==='name') return '<td class="name">'+r.name+'</td>';
    let v=r[c.k]; let cls='';
    if(c.sign) cls = v>=0?'bar-pos':'bar-neg';
    return '<td class="'+cls+'">'+fmt(v,c)+'</td>';
  }).join('')+'</tr>').join('');
}
function svg(w,h){ const s=document.createElementNS('http://www.w3.org/2000/svg','svg');
  s.setAttribute('viewBox','0 0 '+w+' '+h); s.setAttribute('width','100%'); s.setAttribute('height',h); return s;}
function el(tag,attrs,txt){ const e=document.createElementNS('http://www.w3.org/2000/svg',tag);
  for(const k in attrs) e.setAttribute(k,attrs[k]); if(txt!=null) e.textContent=txt; return e;}
function renderBar(){
  const box=document.getElementById('barChart'); box.innerHTML='';
  const rows = rowsFor(curWin).slice().sort((a,b)=>b.win_exc-a.win_exc).slice(0,15);
  const W=560, rowH=24, padL=128, padR=46, H=rows.length*rowH+20;
  const s=svg(W,H); const maxX=W-padR;
  rows.forEach((r,i)=>{
    const y=i*rowH+14; const bw=(maxX-padL)*r.win_exc;
    s.appendChild(el('text',{x:padL-8,y:y+11,'text-anchor':'end',class:'tip'}, r.name.slice(0,9)));
    s.appendChild(el('rect',{x:padL,y:y,width:Math.max(2,bw),height:14,rx:4,fill:'url(#g)'}));
    s.appendChild(el('text',{x:padL+bw+6,y:y+11,class:'tip'}, (r.win_exc*100).toFixed(0)+'% ('+r.n+')'));
  });
  const defs=el('defs',{}); const lg=el('linearGradient',{id:'g',x1:'0',x2:'1'});
  lg.appendChild(el('stop',{offset:'0','stop-color':'#0057ff'})); lg.appendChild(el('stop',{offset:'1','stop-color':'#ff5a1f'}));
  defs.appendChild(lg); s.appendChild(defs); box.appendChild(s);
}
function renderScatter(){
  const box=document.getElementById('scatterChart'); box.innerHTML='';
  const rows=rowsFor(curWin); const W=560,H=360,padL=46,padB=34,padT=14,padR=14;
  const xs=rows.map(r=>r.avg_dd), ys=rows.map(r=>r.avg_exc);
  const xMin=Math.min(-1,...xs), xMax=Math.max(1,...xs), yMin=Math.min(-1,...ys), yMax=Math.max(1,...ys);
  const sx=v=>padL+(v-xMin)/(xMax-xMin)*(W-padL-padR);
  const sy=v=>H-padB-(v-yMin)/(yMax-yMin)*(H-padB-padT);
  const s=svg(W,H);
  s.appendChild(el('line',{x1:padL,y1:sy(0),x2:W-padR,y2:sy(0),class:'axis'}));
  s.appendChild(el('line',{x1:sx(0),y1:padT,x2:sx(0),y2:H-padB,class:'axis'}));
  s.appendChild(el('text',{x:W-padR,y:sy(0)-6,'text-anchor':'end',class:'axis-txt'},'均回撤 →'));
  s.appendChild(el('text',{x:sx(0)+6,y:padT+10,class:'axis-txt'},'↑ 均超额'));
  const nMax=Math.max(...rows.map(r=>r.n));
  rows.forEach(r=>{
    const rad=4+8*(r.n/nMax);
    const c=el('circle',{cx:sx(r.avg_dd),cy:sy(r.avg_exc),r:rad,
      fill:(r.win_exc>=0.6?'#0a7d3c':'#ff5a1f'),'fill-opacity':0.5,stroke:'#fffaf1',class:'dot'});
    c.appendChild(el('title',{}, r.name+' · 胜率'+(r.win_exc*100).toFixed(0)+'% · n='+r.n
      +' · 均超额'+(r.avg_exc>=0?'+':'')+r.avg_exc.toFixed(1)+' · 均回撤'+r.avg_dd.toFixed(1)));
    s.appendChild(c);
  });
  box.appendChild(s);
}
function renderAll(){ renderToggle(); renderHero(); renderTable(); renderBar(); renderScatter(); }
renderAll();
</script></body></html>"""


def build_data(vault: Path, outcomes_path: Path, min_calls: int, windows: list[int]) -> dict:
    store = resolve_store(vault)
    names = load_sources(store)
    rows = load_outcomes(outcomes_path)
    by_window = {}
    for w in windows:
        agg = aggregate_winrate(rows, names, w, min_calls)
        by_window[str(w)] = {
            "rows": [
                {
                    "name": a["name"],
                    "n": a["n"],
                    "win_exc": round(a["win_exc"], 4),
                    "win_abs": round(a["win_abs"], 4),
                    "avg_exc": round(a["avg_exc"], 2),
                    "med_exc": round(a["med_exc"], 2),
                    "avg_maxhit": round(a["avg_maxhit"], 2),
                    "avg_dd": round(a["avg_dd"], 2),
                }
                for a in agg
            ],
            "events": sum(a["n"] for a in agg),
        }
    return {"windows": [str(w) for w in windows], "byWindow": by_window, "min_calls": min_calls}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=None, help="知识库 wiki 根（含 raw/theme-radar/opinion-store/）")
    ap.add_argument("--outcomes", default=None, help="覆盖 outcomes.jsonl 路径")
    ap.add_argument("--min-calls", type=int, default=5)
    ap.add_argument("--windows", default="3,5,7,10", help="逗号分隔 T+N 窗口，默认 3,5,7,10")
    ap.add_argument("--out", default=None, help="输出 HTML 路径；默认 复盘/winrate/winrate-<date>.html")
    ap.add_argument("--date", default=None, help="标注日期戳 YYYY-MM-DD；默认今天")
    args = ap.parse_args()

    vault = resolve_vault(args.vault)
    store = resolve_store(vault)
    outcomes_path = Path(args.outcomes).expanduser() if args.outcomes else store / "outcomes.jsonl"
    if not outcomes_path.exists():
        print(f"[ERR] outcomes not found: {outcomes_path}")
        return 1
    windows = [int(x) for x in args.windows.split(",") if x.strip()]
    stamp = args.date or _dt.date.today().isoformat()

    data = build_data(vault, outcomes_path, args.min_calls, windows)
    if not any(data["byWindow"][w]["rows"] for w in data["windows"]):
        print("[WARN] 所有窗口都没有合格机构（可能 outcomes.jsonl 未回填 excess 或样本不足）。")

    out = Path(args.out).expanduser() if args.out else REPO_ROOT / "复盘" / "winrate" / f"winrate-{stamp}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    title = f"卖方机构胜率榜 {stamp}"
    html = (PAGE
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__TITLE__", escape(title))
            .replace("__STAMP__", stamp)
            .replace("__GENERATED__", f"生成于 {stamp}"))
    out.write_text(html, encoding="utf-8")
    print(f"[OK] winrate html -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
