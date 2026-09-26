#!/usr/bin/env python3
"""把脚本生成的对外版 Markdown 排成 A4 PDF：按 PAGE_BREAK 强制分页，用本机 Chrome 无头打印。

先跑 ``build_bp_public.py --check`` 再调用本脚本；PDF 是二进制，不进仓，默认落到 ~/Downloads。
渲染后回读页数，页数与分页区块数不一致（某页溢出）时以非零退出，提醒压缩正文而不是缩字号。
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

import markdown

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "docs/bp/2026-09-finance-agent-bp-对外版.md"
CHROME = os.environ.get("CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
PAGE_BREAK = "<!-- PAGE_BREAK -->"

CSS = """
@page { size: A4; margin: 15mm 16mm 15mm 16mm;
        @bottom-right { content: "%(footer)s · " counter(page) " / " counter(pages);
                        font-family: "PingFang SC", sans-serif; font-size: 8pt; color: #666; } }
html, body { margin: 0; padding: 0; }
body { font-family: "PingFang SC", "Hiragino Sans GB", "Songti SC", "Arial Unicode MS", sans-serif;
       font-size: 10.4pt; line-height: 1.5; color: #111; }
h1 { font-size: 23pt; margin: 0 0 4pt 0; letter-spacing: 0.5pt; }
h2 { font-size: 16pt; margin: 0 0 8pt 0; padding-bottom: 4pt; border-bottom: 1.2pt solid #222; }
h1 + h2 { border-bottom: none; font-size: 14pt; color: #444; margin-bottom: 10pt; }
h3 { font-size: 11.8pt; margin: 11pt 0 4pt 0; }
p { margin: 0 0 6.5pt 0; text-align: justify; }
table { border-collapse: collapse; width: 100%%; margin: 4pt 0 8pt 0; font-size: 9.6pt; line-height: 1.4; }
th, td { border: 0.6pt solid #888; padding: 3pt 5pt; vertical-align: top; text-align: left; }
td:first-child, th:first-child { white-space: nowrap; }
th { background: #f0f0f0; }
ol { margin: 0; padding-left: 18pt; }
li { margin-bottom: 2pt; }
code { font-family: Menlo, monospace; font-size: 9.4pt; }
.page { page-break-after: always; }
.page:last-child { page-break-after: auto; }
"""


def version_of(text: str) -> str:
    m = re.search(r"^(v\d+\.\d+)(?:\s+对外版)?\s*[·：]", text, re.M)
    return m.group(1) if m else "v?"


def render(src: Path, out: Path) -> int:
    text = src.read_text()
    pages = text.split(PAGE_BREAK)
    version = version_of(text)
    sections = "".join(
        f'<section class="page">{markdown.markdown(p, extensions=["tables"])}</section>' for p in pages
    )
    css = CSS % {"footer": f"Foresight 商业计划书 {version}"}
    html = f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>{css}</style></head><body>{sections}</body></html>'
    html_path = out.with_suffix(".html")
    html_path.write_text(html)
    subprocess.run(
        [
            CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-margins",
            "--virtual-time-budget=4000", f"--print-to-pdf={out}", f"file://{html_path}",
        ],
        check=True, capture_output=True, timeout=120,
    )
    html_path.unlink()
    try:
        import fitz  # PyMuPDF，只用来回读页数
    except ImportError:
        print(f"Generated {out}; 未安装 PyMuPDF，无法回读页数")
        return 0
    n = len(fitz.open(str(out)))
    print(f"Generated {out}; {n} 页（分页区块 {len(pages)}）")
    if n != len(pages):
        print("ERROR: 页数与分页区块不一致，有页面溢出；请压缩该页正文", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", type=Path, default=SRC)
    p.add_argument("--out", type=Path, default=None, help="默认 ~/Downloads/Foresight-BP-对外版-<版本>-<日期>.pdf")
    args = p.parse_args()
    out = args.out
    if out is None:
        version = version_of(args.src.read_text())
        out = Path.home() / "Downloads" / f"Foresight-BP-对外版-{version}-{dt.date.today():%Y-%m-%d}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    return render(args.src, out)


if __name__ == "__main__":
    raise SystemExit(main())
