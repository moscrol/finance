from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "复盘/matrices/strategy-review-workbench.html"
DAILY_ROOT = ROOT / "复盘/daily"


def daily_reviews() -> list[dict[str, str]]:
    items = []
    for path in sorted(DAILY_ROOT.glob("*/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-daily-review.html")):
        date = path.parent.name
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            continue
        rel = Path(os.path.relpath(path, OUT.parent)).as_posix()
        items.append({"date": date, "src": rel, "title": f"{date} 每日市场复盘"})
    return sorted(items, key=lambda item: item["date"], reverse=True)


def main() -> int:
    reviews = daily_reviews()
    if not reviews:
        raise SystemExit("未找到每日复盘 HTML")
    latest = reviews[0]
    reviews_json = json.dumps(reviews, ensure_ascii=False)
    options = "".join(
        f'<option value="{item["date"]}">{item["date"]}</option>' for item in reviews
    )
    html = f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>复盘与策略组合工作台</title>
<style>
:root{{--paper:#f6f0e6;--paper-2:#fffaf1;--ink:#17140f;--muted:#746b5d;--line:#d8cbbb;--line-strong:#18140f;--accent:#0057ff;--card:#fffdf8;--shadow:0 18px 45px rgba(38,28,13,.08)}}*{{box-sizing:border-box}}body{{margin:0;height:100vh;overflow:hidden;background:linear-gradient(90deg,rgba(23,20,15,.045) 1px,transparent 1px),linear-gradient(rgba(23,20,15,.035) 1px,transparent 1px),var(--paper);background-size:28px 28px;color:var(--ink);font-family:'Avenir Next','PingFang SC','Hiragino Sans GB',sans-serif}}.shell{{height:100vh;display:grid;grid-template-columns:320px minmax(0,1fr);gap:24px;padding:24px}}.rail{{min-height:0;overflow:auto;border:1px solid var(--line-strong);background:rgba(255,250,241,.9);backdrop-filter:blur(14px);box-shadow:var(--shadow);padding:22px}}.mark{{font-family:'Bodoni 72','Songti SC',serif;font-size:42px;line-height:.86;letter-spacing:-.06em}}.date-card{{margin:22px 0;padding:18px;border:1px solid var(--line);background:var(--card)}}.label{{font-size:11px;letter-spacing:.18em;color:var(--muted);font-weight:900}}.date{{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;font-size:38px;font-weight:900;margin-top:6px}}.group{{margin-top:18px}}.group-title{{margin:0 0 8px;font-size:12px;letter-spacing:.18em;color:var(--muted);font-weight:900;text-transform:uppercase}}.nav{{display:grid;gap:8px}}.tab{{min-height:48px;text-align:left;border:1px solid var(--line-strong);background:var(--paper-2);color:var(--ink);padding:10px 12px;cursor:pointer;font-weight:900;transition:.16s ease}}.tab small{{display:block;color:var(--muted);font-weight:700;margin-top:3px}}.tab:hover,.tab:focus{{transform:translateX(3px);box-shadow:6px 6px 0 var(--line)}}.tab.active{{background:var(--ink);color:var(--paper-2);box-shadow:6px 6px 0 var(--accent)}}.tab.active small{{color:#d7cfbf}}.daily-picker{{display:grid;gap:8px;margin-top:10px;padding:12px;border:1px solid var(--line);background:var(--card)}}.daily-picker select{{width:100%;min-height:44px;border:1px solid var(--line-strong);background:var(--paper-2);color:var(--ink);padding:8px 10px;font-weight:900;font-size:15px}}.daily-picker .hint{{font-size:12px;line-height:1.45;color:var(--muted)}}.subnav{{display:grid;gap:6px;margin-top:10px;padding-left:12px;border-left:3px solid var(--line)}}.subtab{{min-height:40px;border:1px solid var(--line);background:#fff7eb;color:var(--ink);padding:8px 10px;text-align:left;cursor:pointer;font-weight:800}}.subtab.active{{background:var(--accent);border-color:var(--accent);color:#fff}}.content{{min-width:0;display:grid;grid-template-rows:auto auto 1fr;gap:14px}}.hero{{position:relative;overflow:hidden;border:1px solid var(--line-strong);background:var(--paper-2);box-shadow:var(--shadow);padding:20px 24px}}.hero:before{{content:"";position:absolute;right:24px;top:18px;width:86px;height:86px;border:13px solid var(--accent);border-left-color:transparent;border-radius:50%;opacity:.9}}.kicker{{font-size:12px;letter-spacing:.28em;font-weight:900;color:var(--accent);text-transform:uppercase}}.hero h1{{position:relative;margin:8px 0 8px;font-family:'Bodoni 72','Songti SC',serif;font-size:44px;line-height:.95;letter-spacing:-.06em}}.meta{{position:relative;display:flex;gap:8px;flex-wrap:wrap;color:var(--muted)}}.pill{{border:1px solid var(--line);background:var(--card);padding:6px 10px;font-size:12px;font-weight:800}}.bar{{display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid var(--line-strong);background:var(--card);padding:10px 12px;box-shadow:var(--shadow)}}.bar b{{color:var(--accent)}}.open{{min-height:44px;display:inline-flex;align-items:center;border:1px solid var(--line-strong);background:var(--ink);color:var(--paper-2);text-decoration:none;padding:8px 12px;font-weight:900}}.framebox{{min-height:0;border:1px solid var(--line-strong);background:var(--card);box-shadow:var(--shadow)}}iframe{{display:block;width:100%;height:100%;border:0;background:white}}@media(max-width:980px){{body{{height:auto;overflow:auto}}.shell{{display:block;padding:14px}}.rail{{margin-bottom:14px}}.content{{height:80vh}}.hero h1{{font-size:34px}}.hero:before{{width:58px;height:58px;border-width:9px}}}}@media(prefers-reduced-motion:reduce){{*{{transition:none!important}}}}
</style>
</head>
<body>
<div class="shell">
  <aside class="rail">
    <div class="mark">Market<br>Brief</div>
    <div class="date-card"><div class="label">TRADE DATE</div><div class="date" id="activeDate">{latest['date']}</div></div>
    <section class="group">
      <p class="group-title">Workspace</p>
      <nav class="nav" aria-label="主页面切换">
        <button class="tab active" data-mode="daily">每日复盘<small>选择日期查看当日复盘</small></button>
        <button class="tab" data-mode="strategy">策略组合<small>策略一 / 策略二 / 策略三 / 二板晋级</small></button>
      </nav>
      <div class="daily-picker" id="dailyPicker">
        <label class="label" for="dailyDate">复盘日期</label>
        <select id="dailyDate" aria-label="选择每日复盘日期">{options}</select>
        <div class="hint">这里只做日期切换；嵌入视图会隐藏日报内部目录，保留正文模块。</div>
      </div>
    </section>
    <section class="group">
      <p class="group-title">Strategy Pages</p>
      <nav class="subnav" aria-label="策略矩阵切换">
        <button class="subtab active" data-src="strategy1-priority-stock-matrix.html" data-title="策略一优先股矩阵">策略一</button>
        <button class="subtab" data-src="strategy2-weak-market-matrix.html" data-title="策略二弱市三路径矩阵">策略二</button>
        <button class="subtab" data-src="strategy3-touch-up-rebound-matrix.html" data-title="策略三Touch UP左侧反抽矩阵">策略三</button>
        <button class="subtab" data-src="second-board-4plus-candidate-matrix.html" data-title="二板冲四板以上候选矩阵">二板晋级</button>
      </nav>
    </section>
  </aside>
  <main class="content">
    <section class="hero"><div class="kicker">Daily Review + Strategy Matrix</div><h1>复盘与策略组合</h1><div class="meta"><span class="pill">统一 Market Brief UI</span><span class="pill">每日复盘可选日期</span><span class="pill">策略矩阵独立维护</span></div></section>
    <div class="bar"><span>当前视图：<b id="viewTitle">{latest['title']}</b></span><a id="openLink" class="open" href="{latest['src']}" target="_blank" rel="noopener">新窗口打开</a></div>
    <section class="framebox"><iframe id="viewFrame" src="{latest['src']}" title="{latest['title']}"></iframe></section>
  </main>
</div>
<script>
const dailyReviews={reviews_json};
const mainTabs=[...document.querySelectorAll('.tab')],subTabs=[...document.querySelectorAll('.subtab')],frame=document.getElementById('viewFrame'),title=document.getElementById('viewTitle'),openLink=document.getElementById('openLink'),dailyDate=document.getElementById('dailyDate'),activeDate=document.getElementById('activeDate');
let currentMode='daily';
function currentDaily(){{return dailyReviews.find(x=>x.date===dailyDate.value)||dailyReviews[0];}}
function setFrame(src,text){{frame.src=src;frame.title=text;title.textContent=text;openLink.href=src;}}
function setMode(mode){{currentMode=mode;mainTabs.forEach(x=>x.classList.toggle('active',x.dataset.mode===mode));if(mode==='daily'){{const item=currentDaily();activeDate.textContent=item.date;setFrame(item.src,item.title);}}else{{const active=subTabs.find(x=>x.classList.contains('active'))||subTabs[0];setFrame(active.dataset.src,active.dataset.title);}}}}
function hideDailyToc(){{if(currentMode!=='daily')return;try{{const doc=frame.contentDocument;if(!doc)return;const style=doc.createElement('style');style.textContent='.rail,.side{{display:none!important}}.shell,.wrap{{display:block!important;max-width:1280px!important;padding:18px!important}}.content,.main{{width:100%!important;max-width:none!important}}.hero{{margin-top:0!important}}';doc.head.appendChild(style);}}catch(e){{}}}}
mainTabs.forEach(btn=>btn.addEventListener('click',()=>setMode(btn.dataset.mode)));
dailyDate.addEventListener('change',()=>setMode('daily'));
subTabs.forEach(btn=>btn.addEventListener('click',()=>{{subTabs.forEach(x=>x.classList.toggle('active',x===btn));setMode('strategy');}}));
frame.addEventListener('load',hideDailyToc);
hideDailyToc();
</script>
</body>
</html>
'''
    OUT.write_text(html, encoding="utf-8")
    print(OUT)
    print("daily_reviews", ", ".join(item["date"] for item in reviews))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
