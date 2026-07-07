#!/usr/bin/env python3
"""每日四问看板：双盲问答台账 → 单页 HTML（复盘/dualblind/index.html）。

数据来自 ``docs/learning/forecast-review-ledger/``——Codex 与 Claude 的双盲
盘后推演答卷、T+1 回填与用户批注（``YYYY-MM-DD.md``），以及机器可读台账
（``.manifest.json`` / ``.answer.<agent>.json`` / ``.verdict.json``，存在时
解析状态与命中率）。全部日期内嵌为 JSON，切日期即可回看。本页不入 git。

Usage:
    python3 scripts/render_dual_blind_qa.py
"""
from __future__ import annotations

import datetime
import html as html_mod
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "learning" / "forecast-review-ledger"
FUPAN = ROOT / "复盘"
OUT_PATH = FUPAN / "dualblind" / "index.html"

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
.badges{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}
.badge{font-size:11px;font-weight:800;padding:3px 8px;border:1px solid var(--line);background:var(--paper-2);color:var(--muted)}
.badge.ok{border-color:var(--accent);color:var(--accent)}
.badge.warn{border-color:var(--accent-2);color:var(--accent-2)}
.links a{color:var(--accent);font-weight:800;font-size:13px;margin-right:14px}
details{border:1px solid var(--line-strong);background:var(--card);box-shadow:var(--shadow);margin:12px 0;padding:0 18px}
details>summary{cursor:pointer;padding:14px 0;font-family:'Songti SC','Noto Serif SC',serif;font-size:20px;font-weight:900;list-style:none}
details>summary::before{content:'§ ';color:var(--accent-2)}
.md{font-size:14px;line-height:1.75;padding-bottom:16px}
.md h3{font-family:'Songti SC','Noto Serif SC',serif;font-size:17px;margin:18px 0 6px;border-bottom:1px solid var(--line);padding-bottom:4px}
.md table{border-collapse:collapse;margin:8px 0;font-size:13px;max-width:100%}
.md th,.md td{border:1px solid var(--line);padding:5px 9px;text-align:left}
.md th{background:var(--paper-2)}
.md blockquote{margin:8px 0;padding:6px 14px;border-left:3px solid var(--accent);background:var(--paper-2);color:var(--muted)}
.md code{background:var(--paper-2);border:1px solid var(--line);padding:1px 5px;font-size:12px}
.md ul,.md ol{padding-left:22px;margin:6px 0}
.md b,.md strong{color:var(--accent)}
a.home{color:var(--accent);font-weight:800;text-decoration:none;font-size:13px}
.empty{color:var(--muted);font-size:13px;border:1px dashed var(--line);padding:14px;background:var(--paper-2)}
"""

JS = """
const DATA=%(data)s;
let dt=null;
function dates(){return Object.keys(DATA).sort().reverse();}
function render(){
  const ds=dates();if(!ds.includes(dt))dt=ds[0]||null;
  document.getElementById('date').innerHTML=ds.map(d=>`<option ${d===dt?'selected':''}>${d}</option>`).join('');
  const day=DATA[dt]||{};
  let html='<div class="badges">'+(day.badges||[]).map(b=>`<span class="badge ${b[1]}">${b[0]}</span>`).join('')+'</div>';
  if((day.links||[]).length)html+='<div class="links">'+day.links.map(l=>`<a href="${l[1]}">${l[0]} ↗</a>`).join('')+'</div>';
  html+=(day.sections||[]).map((s,i)=>`<details ${i<2?'open':''}><summary>${s[0]}</summary><div class="md">${s[1]}</div></details>`).join('')
    ||'<div class="empty">当日无台账内容。</div>';
  document.getElementById('main').innerHTML=html;
  document.getElementById('cnt').textContent=(day.sections||[]).length+' 个板块';
}
document.getElementById('date').onchange=e=>{dt=e.target.value;render();};
render();
"""

_INLINE = [
    (re.compile(r"\*\*(.+?)\*\*"), r"<b>\1</b>"),
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)"), r'<a href="\2">\1</a>'),
]


def _inline(text: str) -> str:
    out = html_mod.escape(text, quote=False)
    for pat, rep in _INLINE:
        out = pat.sub(rep, out)
    return out


def md_to_html(lines: list[str]) -> str:
    """极简 markdown 渲染：标题/表格/列表/引用/段落，足够读台账正文。"""
    out: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        if s.startswith("###"):
            out.append(f"<h3>{_inline(s.lstrip('#').strip())}</h3>")
            i += 1
        elif s.startswith("|"):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                head = "".join(f"<th>{_inline(c)}</th>" for c in rows[0])
                body = "".join(
                    "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>"
                    for r in rows[1:]
                )
                out.append(f"<table><tr>{head}</tr>{body}</table>")
        elif s.startswith(">"):
            quote = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(f"<blockquote>{_inline(' '.join(quote))}</blockquote>")
        elif s.startswith(("- ", "* ")) or re.match(r"^\d+\.\s", s):
            ordered = bool(re.match(r"^\d+\.\s", s))
            tag = "ol" if ordered else "ul"
            items = []
            while i < n and (
                lines[i].strip().startswith(("- ", "* "))
                or re.match(r"^\d+\.\s", lines[i].strip())
            ):
                items.append(re.sub(r"^(-|\*|\d+\.)\s+", "", lines[i].strip()))
                i += 1
            out.append(
                f"<{tag}>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + f"</{tag}>"
            )
        elif s.startswith("---"):
            i += 1
        else:
            out.append(f"<p>{_inline(s)}</p>")
            i += 1
    return "".join(out)


def split_sections(md: str) -> list[tuple[str, str]]:
    """按 H2 切分，H2 之前的引言归入「台账头注」。"""
    sections: list[tuple[str, list[str]]] = [("台账头注", [])]
    for line in md.splitlines():
        if line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif line.startswith("# "):
            continue
        else:
            sections[-1][1].append(line)
    return [
        (title, md_to_html(body))
        for title, body in sections
        if any(x.strip() for x in body)
    ]


def machine_badges(date: str) -> list[tuple[str, str]]:
    badges: list[tuple[str, str]] = []
    manifest = LEDGER / f"{date}.manifest.json"
    badges.append(
        ("manifest ✓", "ok") if manifest.exists() else ("manifest 缺", "warn"))
    for agent in ("codex", "claude"):
        p = LEDGER / f"{date}.answer.{agent}.json"
        if p.exists():
            badges.append((f"{agent} 答卷 ✓", "ok"))
    vpath = LEDGER / f"{date}.verdict.json"
    if vpath.exists():
        try:
            entries = json.loads(vpath.read_text(encoding="utf-8")).get("verdicts") or []
            hit = sum(1 for e in entries if e.get("verdict") == "hit")
            judged = sum(1 for e in entries if e.get("verdict") in ("hit", "miss", "partial"))
            badges.append((f"verdict {hit}/{judged} hit", "ok"))
        except (json.JSONDecodeError, OSError):
            badges.append(("verdict 解析失败", "warn"))
    else:
        badges.append(("verdict 待回检", "warn"))
    return badges


def day_links(date: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    rel_ledger = Path("..") / ".." / "docs" / "learning" / "forecast-review-ledger"
    if (LEDGER / f"{date}.html").exists():
        links.append(("台账原文 HTML", str(rel_ledger / f"{date}.html")))
    compare = FUPAN / "daily" / date / f"dual-blind-compare-{date}.html"
    if compare.exists():
        links.append(("双盲并排对比页", f"../daily/{date}/dual-blind-compare-{date}.html"))
    return links


def _answer_md_lines(ans: dict) -> list[str]:
    """把机器答卷 JSON 转成台账风格 markdown 行（无人读版 md 时兜底展示）。"""
    lines: list[str] = []
    if ans.get("stage"):
        lines += ["### 阶段判断", str(ans["stage"]), ""]
    if ans.get("main_judgment"):
        lines += ["### 核心判断", str(ans["main_judgment"]), ""]
    if isinstance(ans.get("direction_ranking"), list) and ans["direction_ranking"]:
        lines.append("### 方向排序")
        lines += [f"{i}. {x}" for i, x in enumerate(ans["direction_ranking"], 1)]
        lines.append("")
    picks = ans.get("picks")
    if isinstance(picks, list) and picks and isinstance(picks[0], dict):
        keys = list(picks[0].keys())
        lines.append("### 观察标的")
        lines.append("| " + " | ".join(keys) + " |")
        lines.append("|" + "---|" * len(keys))
        for p in picks:
            lines.append("| " + " | ".join(str(p.get(k, "")) for k in keys) + " |")
        lines.append("")
    dfq = ans.get("daily_four_questions")
    if isinstance(dfq, dict):
        lines.append("### 每日四问")
        for k, v in dfq.items():
            if isinstance(v, dict):
                cv = v.get("core_values")
                detail = "；".join(f"{a}={b}" for a, b in cv.items()) if isinstance(cv, dict) else (v.get("answer") or v.get("summary") or v.get("status") or "")
                lines.append(f"- **{k}**（{v.get('status', '')}）：{detail}")
            else:
                lines.append(f"- **{k}**：{v}")
        lines.append("")
    return lines


def answer_sections(date: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for agent in ("codex", "claude"):
        p = LEDGER / f"{date}.answer.{agent}.json"
        if not p.exists():
            continue
        try:
            ans = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        lines = _answer_md_lines(ans)
        if lines:
            sections.append((f"{agent} 答卷（自动渲染）", md_to_html(lines)))
    return sections


def load() -> dict:
    data: dict = {}
    dates = set()
    for f in LEDGER.iterdir():
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\.", f.name)
        if m:
            dates.add(m.group(1))
    for date in sorted(dates):
        md_file = LEDGER / f"{date}.md"
        if md_file.exists():
            sections = split_sections(md_file.read_text(encoding="utf-8"))
        else:
            sections = answer_sections(date)
        if not sections:
            continue
        data[date] = {
            "sections": sections,
            "badges": machine_badges(date),
            "links": day_links(date),
        }
    return data


def main() -> int:
    data = load()
    built = datetime.date.today().isoformat()
    js = JS % {"data": json.dumps(data, ensure_ascii=False)}
    html = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>每日四问 · 双盲问答台账</title>"
        f"<style>{CSS}</style></head><body><div class='wrap'>"
        '<a class="home" href="../index.html">← 驾驶舱总入口</a>'
        '<div class="kicker">Dual-Blind Forecast Ledger</div><h1>每日四问看板</h1>'
        '<div class="sub">Codex 与 Claude 的双盲盘后推演台账回看：每日答卷'
        "（市场底稿→核心判断→方向排序→观察标的→待验证假设）+ T+1 回填 + 用户批注。"
        "数据来自 docs/learning/forecast-review-ledger/，机器可读台账"
        "（manifest/answer/verdict）存在时展示校验状态与命中率，切日期即可回看。</div>"
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
