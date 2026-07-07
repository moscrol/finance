#!/usr/bin/env python3
"""每日四问看板：daily-agent 导出 → 单页 HTML（复盘/lifecycle/index.html）。

「逻辑生命周期四问」每天对每个进入决策层的题材必须回答：

1. 它处在生命周期哪一段（八阶段判定）
2. 相对昨天变化了什么、为什么（阶段变化 + 变化原因）
3. 证据/盘面现在支持到什么程度（证据状态、触发信号、强势股）
4. 后续怎么升级、降级或证伪（下一步）

数据来自 ``market_feature_store/exports/<date>-daily-agent.json`` 的 decision
分区（old_logic_wakeup / new_logic_candidate / data_gap / noise_or_unconfirmed），
其中每行的 ``生命周期`` 字段即 logic_lifecycle 落盘的快照。全部日期内嵌为
JSON，页面内切日期即可回看。本页不入 git。

Usage:
    python3 scripts/render_lifecycle_qa.py
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "market_feature_store" / "exports"
OUT_PATH = ROOT / "复盘" / "lifecycle" / "index.html"

BUCKETS = [
    ("old_logic_wakeup", "旧逻辑唤醒"),
    ("new_logic_candidate", "新逻辑候选"),
    ("data_gap", "数据缺口"),
    ("noise_or_unconfirmed", "噪声/未确认"),
]

CSS = """
:root{--paper:#f6f0e6;--paper-2:#fffaf1;--ink:#17140f;--muted:#746b5d;--line:#d8cbbb;--line-strong:#18140f;--accent:#0057ff;--accent-2:#ff5a1f;--card:#fffdf8;--shadow:0 18px 45px rgba(38,28,13,.08)}
*{box-sizing:border-box}
body{margin:0;background:linear-gradient(90deg,rgba(23,20,15,.045) 1px,transparent 1px),linear-gradient(rgba(23,20,15,.035) 1px,transparent 1px),var(--paper);background-size:28px 28px;color:var(--ink);font-family:'Avenir Next','PingFang SC','Hiragino Sans GB',sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 24px}
.kicker{font-size:12px;letter-spacing:.28em;font-weight:900;color:var(--accent);text-transform:uppercase}
h1{font-family:'Bodoni 72','Songti SC',serif;font-size:52px;line-height:.95;letter-spacing:-.05em;margin:10px 0 8px}
.sub{color:var(--muted);font-size:14px;line-height:1.7;max-width:860px}
.bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:22px 0 6px}
select{min-height:40px;border:1px solid var(--line-strong);background:var(--paper-2);padding:8px 12px;font-weight:800;font-size:14px}
.meta{font-size:12px;color:var(--muted);margin-left:auto}
h2{display:flex;align-items:baseline;gap:10px;margin:30px 0 12px;padding-top:14px;border-top:3px solid var(--line-strong);font-family:'Songti SC','Noto Serif SC',serif;font-size:24px}
h2 .n{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;color:var(--muted);font-size:18px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px}
.card{border:1px solid var(--line-strong);background:var(--card);box-shadow:var(--shadow);padding:16px 18px;display:flex;flex-direction:column;gap:8px}
.card .theme{font-family:'Songti SC','Noto Serif SC',serif;font-size:20px;font-weight:900}
.badges{display:flex;gap:6px;flex-wrap:wrap}
.badge{font-size:11px;font-weight:800;padding:3px 8px;border:1px solid var(--line);background:var(--paper-2);color:var(--muted)}
.badge.stage{border-color:var(--accent);color:var(--accent)}
.badge.chg{border-color:var(--accent-2);color:var(--accent-2)}
.qa{font-size:13px;line-height:1.65}
.qa b{color:var(--accent)}
.qa .lbl{font-size:11px;letter-spacing:.14em;font-weight:900;color:var(--muted)}
.stocks{font-size:12px;color:var(--muted)}
a.home{color:var(--accent);font-weight:800;text-decoration:none;font-size:13px}
.empty{color:var(--muted);font-size:13px;border:1px dashed var(--line);padding:14px;background:var(--paper-2)}
"""

JS = """
const DATA=%(data)s;const BUCKETS=%(buckets)s;
let dt=null;
function dates(){return Object.keys(DATA).sort().reverse();}
function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function card(r){
  const lc=r['生命周期']||{};
  const stage=lc['生命周期阶段']||'-',chg=lc['阶段变化']||'-';
  const sig=(lc['当前触发信号']||[]).join(', ')||'-';
  const stocks=(r.strong_stocks||[]).slice(0,6).join(' · ');
  return `<div class="card">
    <div class="theme">${esc(r.matched_theme||r.query||'-')}</div>
    <div class="badges"><span class="badge stage">${esc(stage)}</span>
      <span class="badge chg">${esc(chg)}</span>
      <span class="badge">priority ${esc(lc['当前priority']??r.priority_score??'-')}</span>
      <span class="badge">连续 ${esc(lc['连续出现天数']??'-')} 天</span></div>
    <div class="qa"><span class="lbl">Q1 阶段</span><br><b>${esc(stage)}</b>（${esc(chg)}）</div>
    <div class="qa"><span class="lbl">Q2 变化与原因</span><br>${esc(lc['变化原因']||'-')}</div>
    <div class="qa"><span class="lbl">Q3 证据与盘面</span><br>证据状态：<b>${esc(lc['证据状态']||'-')}</b>；触发信号：${esc(sig)}</div>
    <div class="qa"><span class="lbl">Q4 下一步（升级/降级/证伪）</span><br>${esc(lc['下一步']||'-')}</div>
    ${stocks?`<div class="stocks">强势股：${esc(stocks)}</div>`:''}
  </div>`;
}
function render(){
  const ds=dates();if(!ds.includes(dt))dt=ds[0]||null;
  document.getElementById('date').innerHTML=ds.map(d=>`<option ${d===dt?'selected':''}>${d}</option>`).join('');
  const day=DATA[dt]||{};let html='',total=0;
  for(const [key,label] of BUCKETS){
    const rows=day[key]||[];total+=rows.length;
    html+=`<h2>${label} <span class="n">${rows.length}</span></h2>`;
    html+=rows.length?`<div class="grid">${rows.map(card).join('')}</div>`
      :'<div class="empty">当日无条目。</div>';
  }
  document.getElementById('main').innerHTML=html;
  document.getElementById('cnt').textContent=total+' 个题材';
}
document.getElementById('date').onchange=e=>{dt=e.target.value;render();};
render();
"""


def load() -> dict:
    data: dict = {}
    for f in sorted(EXPORTS.glob("*-daily-agent.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        date = str(doc.get("date") or f.name[:10])
        decision = doc.get("decision") or {}
        day = {}
        for key, _label in BUCKETS:
            rows = decision.get(key) or []
            day[key] = [
                {
                    "query": r.get("query"),
                    "matched_theme": r.get("matched_theme"),
                    "priority_score": r.get("priority_score"),
                    "strong_stocks": r.get("strong_stocks") or [],
                    "生命周期": r.get("生命周期") or r.get("logic_lifecycle") or {},
                }
                for r in rows
            ]
        data[date] = day
    return data


def main() -> int:
    data = load()
    built = datetime.date.today().isoformat()
    js = JS % {
        "data": json.dumps(data, ensure_ascii=False),
        "buckets": json.dumps(BUCKETS, ensure_ascii=False),
    }
    html = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>每日四问 · 逻辑生命周期</title>"
        f"<style>{CSS}</style></head><body><div class='wrap'>"
        '<a class="home" href="../index.html">← 驾驶舱总入口</a>'
        '<div class="kicker">Daily Four Questions</div><h1>每日四问看板</h1>'
        '<div class="sub">逻辑生命周期四问的每日落盘回看：每个进入决策层的题材回答'
        "①处在哪个阶段 ②相对昨天变化了什么/为什么 ③证据与盘面支持到什么程度 "
        "④后续怎么升级/降级/证伪。数据来自 daily-agent 导出（decision 分区 + "
        "logic_lifecycle 快照），切日期即可回看历史。</div>"
        '<div class="bar"><select id="date"></select>'
        f'<span class="meta"><span id="cnt"></span> · BUILT {built}</span></div>'
        '<div id="main"></div>'
        f"</div><script>{js}</script></body></html>"
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")
    print(OUT_PATH)
    print(f"dates: {len(data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
