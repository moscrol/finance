#!/usr/bin/env python3
"""render_winrate_html: 把「卖方机构胜率榜」渲染成自包含暗色 HTML（双击即开、零依赖）。

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
:root{--bg:#080b0d;--panel:#11181d;--ink:#eef7f2;--muted:#8ca09a;--line:#263239;--green:#62ff9d;--amber:#ffd166;--blue:#7bdcff;--red:#ff6b6b}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:radial-gradient(circle at 15% 0%,#123826,transparent 28%),linear-gradient(180deg,#07090b,#11161a);color:var(--ink);font-family:'Avenir Next','PingFang SC',sans-serif}
.wrap{display:grid;grid-template-columns:270px 1fr;gap:24px;max-width:1700px;margin:auto;padding:24px}
.side{position:sticky;top:20px;height:calc(100vh - 40px);overflow:auto;border:1px solid var(--line);border-radius:26px;background:#0c1114cc;padding:20px}
.brand{font-size:30px;font-weight:900;letter-spacing:.08em;background:linear-gradient(135deg,var(--green),var(--blue));-webkit-background-clip:text;color:transparent;line-height:.96}
.win-toggle{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}
.win-toggle button{border:1px solid var(--line);background:#172127;color:var(--ink);border-radius:12px;padding:8px 12px;cursor:pointer;font-weight:700}
.win-toggle button.active{border-color:var(--green);background:#10261a;color:var(--green)}
.legend{color:var(--muted);font-size:12px;line-height:1.7;margin-top:14px;border-top:1px dashed var(--line);padding-top:12px}
.legend b{color:var(--ink)}
.hero{border:1px solid var(--line);border-radius:34px;background:linear-gradient(135deg,#1a262b,#0d1114);padding:42px;margin-bottom:24px}
.hero p{color:var(--green);letter-spacing:.25em;margin:0 0 6px;font-size:13px}
.hero h1{font-size:46px;line-height:1.05;margin:6px 0}
.hero .sub{color:var(--muted);font-size:15px;margin-top:10px}
.kpis{display:flex;flex-wrap:wrap;gap:14px;margin-top:22px}
.kpi{border:1px solid var(--line);border-radius:16px;background:#0c1114;padding:14px 18px;min-width:130px}
.kpi .v{font-size:26px;font-weight:900;color:var(--green)}
.kpi .l{color:var(--muted);font-size:12px;margin-top:4px}
h2{margin-top:34px;border-left:6px solid var(--green);padding:13px 18px;background:#102019;border-radius:16px;font-size:20px}
.note{border:1px solid #28513a;background:#10261a;border-radius:16px;padding:14px 16px;margin:12px 0;color:#dbefe4;font-size:13px;line-height:1.7}
.charts{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:1100px){.charts{grid-template-columns:1fr}.wrap{grid-template-columns:1fr}.side{position:relative;height:auto}}
.card{border:1px solid var(--line);border-radius:20px;background:#0c1114;padding:16px}
.card h3{margin:0 0 6px;font-size:15px;color:#fff}
.card .cap{color:var(--muted);font-size:12px;margin-bottom:8px}
.tablebox{overflow:auto;max-height:80vh;border:1px solid var(--line);border-radius:20px;background:#0c1114;margin:14px 0 26px}
table{border-collapse:separate;border-spacing:0;width:100%;font-size:13px}
th,td{padding:9px 12px;border-bottom:1px solid #203039;white-space:nowrap;text-align:right}
th:nth-child(2),td:nth-child(2){text-align:left}
th{position:sticky;top:0;background:#142128;color:#bfffe0;cursor:pointer;user-select:none;z-index:2}
th:hover{color:#fff}
tr:hover td{background:#15232a}
td.rank{color:var(--muted);font-weight:700}
td.name{color:#fff;font-weight:700}
.bar-pos{color:var(--green)}.bar-neg{color:var(--red)}
.dot{cursor:default}
.tip{fill:#cfe9dd;font-size:11px}
.axis{stroke:#2a3a42}.axis-txt{fill:#7d918b;font-size:10px}
.foot{color:var(--muted);font-size:12px;margin:30px 0 8px;text-align:center}
</style></head><body><div class="wrap">
<aside class="side">
  <div class="brand">WINRATE<br>RANK</div>
  <div class="win-toggle" id="winToggle"></div>
  <div class="legend">
    <p><b>口径</b>：报告日次日开盘买入，持有至 T+N 收盘。</p>
    <p><b>超额</b> = 个股收益 − 沪深300 同窗收益（剥大盘 beta）。</p>
    <p><b>超额胜率</b> = 超额为正的看多事件占比，主排序键。</p>
    <p><b>均最高</b> = 区间最高收益均值（最好情形）；<b>均回撤</b> = 峰值后回撤均值（风险）。</p>
    <p>仅统计窗口完整的看多事件；样本不足门槛的机构不排。</p>
  </div>
</aside>
<main class="main">
  <section class="hero">
    <p>SELL-SIDE INSTITUTION WIN-RATE</p>
    <h1>卖方机构胜率榜</h1>
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
  lg.appendChild(el('stop',{offset:'0','stop-color':'#62ff9d'})); lg.appendChild(el('stop',{offset:'1','stop-color':'#7bdcff'}));
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
      fill:(r.win_exc>=0.6?'#62ff9d':'#ffd166'),'fill-opacity':0.55,stroke:'#0b1014',class:'dot'});
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
            .replace("__GENERATED__", f"生成于 {stamp}"))
    out.write_text(html, encoding="utf-8")
    print(f"[OK] winrate html -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
