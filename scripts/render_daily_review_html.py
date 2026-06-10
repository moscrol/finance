from __future__ import annotations

import re
import shutil
import sys
from html import escape
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_HTML = ROOT / "复盘/daily/2026-06-08/2026-06-08-daily-review.html"
EXTRA_CSS = """
body:before{content:"";position:fixed;inset:0;pointer-events:none;background-image:linear-gradient(#ffffff05 1px,transparent 1px),linear-gradient(90deg,#ffffff04 1px,transparent 1px);background-size:42px 42px;mask-image:linear-gradient(180deg,#000,transparent 78%)}.wrap{max-width:1840px}.side{box-shadow:0 24px 80px #0007}.brand{line-height:.92;background:linear-gradient(135deg,var(--green),var(--blue));-webkit-background-clip:text;color:transparent}.main{min-width:0}.hero{position:relative;overflow:hidden}.hero:after{content:"";position:absolute;right:-90px;top:-90px;width:280px;height:280px;border:1px solid #62ff9d55;border-radius:50%;box-shadow:0 0 90px #62ff9d22}.hero h1{letter-spacing:-.04em}.hero p{font-weight:900}.main>h1{display:none}.main h2{margin-top:34px;box-shadow:0 18px 60px #0004}.main h3{padding:10px 12px;border-left:3px solid var(--blue);background:#101820;border-radius:12px}.main p,.main li{line-height:1.8;color:#dce8e3}.main blockquote{border:1px solid #28513a;background:#10261a;border-radius:16px;padding:14px 16px;margin:12px 0;color:#dbefe4}.main blockquote p{margin:0}.main code{background:#172127;border:1px solid var(--line);border-radius:7px;padding:1px 6px;color:var(--green)}.report-table{overflow:auto;max-height:76vh;border:1px solid var(--line);border-radius:20px;background:linear-gradient(180deg,#0d1418,#0a0f12);margin:14px 0 26px;box-shadow:0 18px 50px #0005}.report-table table{width:max-content;min-width:100%}.report-table th{background:#142128;color:#bfffe0;text-transform:none}.report-table tr:hover td{background:#15232a}.board-table{max-height:none;border-color:#3f6f55;background:linear-gradient(135deg,#10251a,#0c1418)}.board-table table{font-size:14px}.board-table td:first-child{color:var(--green);font-weight:900}.board-table td:last-child{white-space:normal;min-width:520px}.main img{display:block;width:100%;max-height:620px;object-fit:contain;border-radius:18px;background:#fff;border:1px solid var(--line)}.toc a{transition:.18s ease}.toc a:hover{transform:translateX(4px)}.light{--bg:#f6f1e8;--panel:#fffaf0;--ink:#17211d;--muted:#66756f;--line:#d7cbbb;background:#f6f1e8;color:var(--ink)}.light body,.light .wrap{background:#f6f1e8}@media(max-width:980px){.wrap{display:block;padding:14px}.side{position:relative;height:auto;margin-bottom:16px}.hero{padding:28px}.hero h1{font-size:36px}.report-table{max-height:62vh}}"""


def slug(title: str) -> str:
    value = re.sub(r"[`*_#>|]", "", title).strip().lower()
    value = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "-", value).strip("-")
    return value or "section"


def enhance_body(body: str) -> str:
    body = re.sub(r"(<table>.*?</table>)", r'<div class="report-table">\1</div>', body, flags=re.S)
    body = body.replace('class="report-table"', 'class="report-table board-table"', 1)
    return body


def main() -> int:
    trade_date = sys.argv[1]
    md_path = ROOT / f"market_feature_store/exports/{trade_date}-daily-review.md"
    chart_path = ROOT / f"market_feature_store/exports/{trade_date}-advancers-ma5.png"
    out_dir = ROOT / f"复盘/daily/{trade_date}"
    out_path = out_dir / f"{trade_date}-daily-review.html"

    template = TEMPLATE_HTML.read_text(encoding="utf-8")
    css = re.search(r"<style>(.*?)</style>", template, re.S).group(1)
    text = md_path.read_text(encoding="utf-8")
    text = text.replace(str(chart_path), chart_path.name)
    body = enhance_body(markdown.markdown(text, extensions=["tables", "toc", "fenced_code"]))

    heads = re.findall(r"^(##+)\s+(.+)$", text, re.M)
    toc = "".join(
        f'<a href="#{slug(title)}"><span>{i:02d}</span>{escape(title)}</a>'
        for i, (_, title) in enumerate(heads, 1)
    )
    html = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{trade_date} 复盘可视化</title><style>{css}{EXTRA_CSS}</style></head><body><div class="wrap"><aside class="side"><div class="brand">MARKET<br>RADAR</div><div class="tools"><button id="compact">紧凑</button><button id="light">明亮</button></div><nav class="toc">{toc}</nav></aside><main class="main"><section class="hero"><p>DAILY MARKET REVIEW</p><h1>{trade_date}<br>复盘可视化</h1><div class="note">沿用 2026-06-08 HTML 模板；数据来自 market_feature_store。</div></section>{body}</main></div><script>document.getElementById("compact").onclick=()=>document.body.classList.toggle("compact");document.getElementById("light").onclick=()=>document.body.classList.toggle("light");</script></body></html>'''

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    shutil.copy2(chart_path, out_dir / chart_path.name)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
