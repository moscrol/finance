from __future__ import annotations

import re
import subprocess
import sys
from html import escape
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
STYLE = """
:root{--paper:#0f1412;--paper-2:#151d1a;--ink:#f5efe2;--muted:#a89f90;--line:#33413b;--line-strong:#e8d9b8;--accent:#b6ff4d;--accent-2:#ff7a3d;--card:#19231f;--shadow:0 24px 70px rgba(0,0,0,.32)}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 12% 8%,rgba(182,255,77,.14),transparent 30%),radial-gradient(circle at 86% 14%,rgba(255,122,61,.12),transparent 34%),linear-gradient(135deg,rgba(255,255,255,.045) 1px,transparent 1px),var(--paper);background-size:auto,auto,26px 26px;color:var(--ink);font-family:'Avenir Next','PingFang SC','Hiragino Sans GB',sans-serif}.skip{position:absolute;left:-999px;top:12px;background:var(--accent);color:#111;padding:10px 14px;border-radius:999px;z-index:10}.skip:focus{left:16px}.shell{display:grid;grid-template-columns:330px minmax(0,1fr);gap:28px;max-width:1840px;margin:0 auto;padding:24px}.rail{position:sticky;top:24px;height:calc(100dvh - 48px);overflow:auto;border:1px solid var(--line-strong);background:rgba(15,20,18,.82);backdrop-filter:blur(18px);box-shadow:var(--shadow);padding:22px}.mark{font-family:'Bodoni 72','Songti SC',serif;font-size:42px;line-height:.88;letter-spacing:-.06em;color:var(--ink)}.date-card{margin:22px 0;padding:18px;border:1px solid var(--line);background:linear-gradient(135deg,rgba(182,255,77,.12),rgba(255,255,255,.02))}.label{font-size:11px;letter-spacing:.18em;color:var(--muted);font-weight:900}.date{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;font-size:38px;font-weight:900;margin-top:6px;color:var(--accent)}.tools{display:flex;gap:8px;margin:18px 0}.tools button{min-height:44px;border:1px solid var(--line-strong);background:var(--accent);color:#10130f;padding:9px 12px;font-weight:900;cursor:pointer}.tools button:nth-child(2){background:transparent;color:var(--ink)}.toc{display:flex;flex-direction:column;gap:6px}.toc a{display:grid;grid-template-columns:36px 1fr;gap:8px;align-items:start;color:var(--muted);text-decoration:none;padding:8px 0;border-top:1px solid var(--line);font-size:13px;line-height:1.35}.toc a:hover,.toc a:focus{color:var(--accent)}.toc span{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;color:var(--accent-2);font-size:18px}.content{min-width:0}.hero{position:relative;min-height:330px;border:1px solid var(--line-strong);background:linear-gradient(135deg,rgba(25,35,31,.95),rgba(15,20,18,.86));box-shadow:var(--shadow);padding:34px;margin-bottom:24px;overflow:hidden}.hero:after{content:"";position:absolute;right:-90px;bottom:-120px;width:420px;height:420px;border:1px solid rgba(182,255,77,.45);border-radius:50%;box-shadow:inset 0 0 80px rgba(182,255,77,.08)}.kicker{font-size:12px;letter-spacing:.22em;text-transform:uppercase;color:var(--accent);font-weight:900}.hero h1{position:relative;margin:18px 0 16px;font-family:'Bodoni 72','Songti SC',serif;font-size:78px;line-height:.92;letter-spacing:-.055em;max-width:900px}.summary{position:relative;max-width:820px;color:var(--muted);font-size:17px;line-height:1.8}.content h2{margin:26px 0 12px;font-family:'Bodoni 72','Songti SC',serif;font-size:38px;letter-spacing:-.035em;border-bottom:1px solid var(--line-strong);padding-bottom:10px}.content h3{margin:24px 0 10px;color:var(--accent);font-size:18px;letter-spacing:.04em}.content p,.content li{line-height:1.78;color:#ded6c8}.content strong{color:var(--ink)}.content a{color:var(--accent)}.content code{background:#0a0d0c;border:1px solid var(--line);padding:2px 5px}.table-card{overflow:auto;border:1px solid var(--line);background:rgba(25,35,31,.84);box-shadow:0 14px 40px rgba(0,0,0,.18);margin:14px 0 22px}.table-card.board{border-color:var(--line-strong)}table{width:100%;border-collapse:collapse;min-width:860px}th,td{border-bottom:1px solid var(--line);border-right:1px solid rgba(51,65,59,.65);padding:10px 12px;text-align:left;vertical-align:top;font-size:13px;line-height:1.55}th{position:sticky;top:0;background:#101713;color:var(--accent);font-size:12px;letter-spacing:.08em;z-index:1}tr:hover td{background:rgba(182,255,77,.055)}body.compact th,body.compact td{padding:6px 8px;font-size:12px}body.focus .rail{display:none}body.focus .shell{display:block;max-width:1320px}.note{color:var(--muted);font-size:13px;margin-top:10px}@media(max-width:960px){.shell{display:block;padding:14px}.rail{position:relative;height:auto;margin-bottom:16px}.hero h1{font-size:52px}table{min-width:760px}}
"""


def slug(title: str) -> str:
    value = re.sub(r"[`*_#>|]", "", title).strip().lower()
    value = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "-", value).strip("-")
    return value or "section"


def add_heading_ids(body: str, ids: list[str]) -> str:
    idx = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal idx
        level, title = match.group(1), match.group(2)
        value = ids[idx] if idx < len(ids) else slug(re.sub(r"<.*?>", "", title))
        idx += 1
        return f'<h{level} id="{value}">{title}</h{level}>'

    return re.sub(r"<h([23])>(.*?)</h\1>", replace, body)


def enhance_body(body: str, ids: list[str]) -> str:
    body = add_heading_ids(body, ids)
    body = re.sub(r"(<table>.*?</table>)", r'<div class="table-card">\1</div>', body, flags=re.S)
    body = body.replace('class="table-card"', 'class="table-card board"', 1)
    return body


def main() -> int:
    trade_date = sys.argv[1]
    build = subprocess.run([sys.executable, str(ROOT / "scripts/build_market_triggered_theme_brief.py"), trade_date], cwd=str(ROOT))
    if build.returncode:
        return build.returncode

    md_path = ROOT / f"market_feature_store/exports/{trade_date}-market-triggered-theme-brief.md"
    out_dir = ROOT / f"复盘/daily/{trade_date}"
    out_path = out_dir / f"{trade_date}-market-triggered-theme-brief.html"
    text = md_path.read_text(encoding="utf-8")
    heads = [(title, slug(title)) for _, title in re.findall(r"^(##+)\s+(.+)$", text, re.M)]
    body = markdown.markdown(text, extensions=["tables", "fenced_code"])
    body = enhance_body(body, [item[1] for item in heads])
    toc = "".join(f'<a href="#{sid}"><span>{i:02d}</span>{escape(title)}</a>' for i, (title, sid) in enumerate(heads, 1))
    html = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{trade_date} 盘面触发题材雷达</title><style>{STYLE}</style></head><body><a class="skip" href="#main">跳到正文</a><div class="shell"><aside class="rail"><div class="mark">Theme<br>Radar</div><div class="date-card"><div class="label">TRADE DATE</div><div class="date">{trade_date}</div><div class="note">盘面信号 → 知识库解释 → 次日验证点</div></div><div class="tools"><button id="compact" type="button">紧凑表格</button><button id="focus" type="button">专注阅读</button></div><nav class="toc" aria-label="题材雷达目录">{toc}</nav></aside><main class="content" id="main"><section class="hero"><div class="kicker">Market Triggered Theme Intelligence</div><h1>{trade_date}<br>题材雷达</h1><div class="summary">从日终盘面自动识别双红、连板、新高和多周期方向，再回到本地知识库做概念映射、公司暴露、证据覆盖和次日验证拆解。</div></section>{body}</main></div><script>document.getElementById("compact").onclick=()=>document.body.classList.toggle("compact");document.getElementById("focus").onclick=()=>document.body.classList.toggle("focus");</script></body></html>'''
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
