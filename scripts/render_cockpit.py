#!/usr/bin/env python3
"""驾驶舱总入口（cockpit home）。

把本地已生成的可视化产物——每日复盘、卖方机构胜率榜、晨汇边际变化、策略矩阵——
用卡片 / 导航串成一个可点进去的单页界面，输出到 `复盘/index.html`，浏览器双击即开。

视觉风格直接复用当前最新每日复盘 HTML 的 `<style>`（浅色投研 briefing 主题），
因此驾驶舱与每日复盘是同一套界面语言；找不到复盘文件时退回内置 paper 主题。

跨仓库：每日复盘 / 胜率榜 / 策略矩阵在本仓 `复盘/`，晨汇边际变化在知识库仓
`dashboard/index.html` 与 `wiki/briefings/`。
链接均为相对路径，指向本地已生成的产物；本页本身不入 git（只提交生成器）。

Usage:
    python3 scripts/render_cockpit.py
    python3 scripts/render_cockpit.py --knowledge-root "/Users/a77/Desktop/c c/知识库"
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUPAN = ROOT / "复盘"
DAILY = FUPAN / "daily"
WINRATE = FUPAN / "winrate"
MATRICES = FUPAN / "matrices"
HEADTOHEAD = FUPAN / "headtohead"
MONEYFLOW = FUPAN / "moneyflow" / "index.html"
DUALBLIND = FUPAN / "dualblind" / "index.html"
OUT_PATH = FUPAN / "index.html"

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

MATRIX_TITLES = {
    "strategy1-priority-stock-matrix.html": "策略1 · 每日优先个股",
    "strategy2-weak-market-matrix.html": "策略2 · 弱市三路径",
    "strategy3-touch-up-rebound-matrix.html": "策略3 · Touch-UP 反抽",
    "strategy4-dual-engine-matrix.html": "策略4 · 双引擎",
    "second-board-4plus-candidate-matrix.html": "二板冲四+ 候选",
    "strategy-review-workbench.html": "复盘策略统合工作台",
}

FALLBACK_CSS = """
:root{--paper:#f6f0e6;--paper-2:#fffaf1;--ink:#17140f;--muted:#746b5d;--line:#d8cbbb;--line-strong:#18140f;--accent:#0057ff;--accent-2:#ff5a1f;--card:#fffdf8;--shadow:0 18px 45px rgba(38,28,13,.08)}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:linear-gradient(90deg,rgba(23,20,15,.045) 1px,transparent 1px),linear-gradient(rgba(23,20,15,.035) 1px,transparent 1px),var(--paper);background-size:28px 28px;color:var(--ink);font-family:'Avenir Next','PingFang SC','Hiragino Sans GB',sans-serif}
.skip{position:absolute;left:-999px;top:12px;background:var(--accent);color:#fff;padding:10px 14px;border-radius:999px;z-index:10}.skip:focus{left:16px}
.shell{display:grid;grid-template-columns:320px minmax(0,1fr);gap:28px;max-width:1760px;margin:0 auto;padding:24px}
.rail{position:sticky;top:24px;height:calc(100dvh - 48px);overflow:auto;border:1px solid var(--line-strong);background:rgba(255,250,241,.88);backdrop-filter:blur(14px);box-shadow:var(--shadow);padding:22px}
.mark{font-family:'Bodoni 72','Songti SC',serif;font-size:42px;line-height:.86;letter-spacing:-.06em}
.date-card{margin:22px 0;padding:18px;border:1px solid var(--line);background:var(--card)}.date-card .label{font-size:11px;letter-spacing:.18em;color:var(--muted);font-weight:900}.date-card .date{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;font-size:38px;font-weight:900;margin-top:6px}
.tools{display:flex;gap:8px;margin:18px 0}.tools button{min-height:44px;border:1px solid var(--line-strong);background:var(--ink);color:var(--paper-2);padding:9px 12px;font-weight:800;cursor:pointer}
.toc{display:flex;flex-direction:column;gap:6px}.toc a{display:grid;grid-template-columns:36px 1fr;gap:8px;align-items:start;color:var(--muted);text-decoration:none;padding:8px 0;border-top:1px solid var(--line);font-size:13px;line-height:1.35}.toc a:hover,.toc a:focus{color:var(--ink)}.toc span{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;color:var(--accent);font-size:18px;line-height:1}
.content{min-width:0}
.hero{position:relative;border:1px solid var(--line-strong);background:var(--paper-2);padding:34px 38px 30px;margin-bottom:28px;box-shadow:var(--shadow);overflow:hidden}.hero:before{content:'';position:absolute;right:32px;top:28px;width:120px;height:120px;border:18px solid var(--accent);border-left-color:transparent;border-radius:50%;opacity:.9}.kicker{font-size:12px;letter-spacing:.28em;font-weight:900;color:var(--accent);text-transform:uppercase}.hero h1{font-family:'Bodoni 72','Songti SC',serif;font-size:72px;line-height:.92;letter-spacing:-.07em;margin:14px 0 20px;max-width:780px}.hero .summary{max-width:760px;color:var(--muted);font-size:17px;line-height:1.7}
h2{display:flex;align-items:baseline;gap:12px;margin:42px 0 14px;padding-top:18px;border-top:3px solid var(--line-strong);font-family:'Songti SC','Noto Serif SC',serif;font-size:30px;line-height:1.2;letter-spacing:-.02em}h2:before{content:'§';color:var(--accent-2);font-family:'Bodoni 72',serif}
.focus .rail{display:none}.focus .shell{display:block;max-width:1280px}
@media(max-width:980px){.shell{display:block;padding:14px}.rail{position:relative;height:auto;margin-bottom:16px}}
"""

EXTRA_CSS = """
.cockpit-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(264px,1fr));gap:18px;margin:14px 0 8px}
.cockpit-card{border:1px solid var(--line-strong);background:var(--card);box-shadow:var(--shadow);padding:20px;display:flex;flex-direction:column;gap:10px;min-height:150px;transition:transform .12s ease,box-shadow .12s ease}
.cockpit-card:hover{transform:translateY(-3px);box-shadow:0 26px 60px rgba(38,28,13,.16)}
.cockpit-card .c-label{font-size:11px;letter-spacing:.2em;font-weight:900;color:var(--accent);text-transform:uppercase}
.cockpit-card a.c-date{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;font-size:40px;font-weight:900;line-height:.9;text-decoration:none;color:var(--ink)}
.cockpit-card a.c-date:hover{color:var(--accent)}
.cockpit-card a.c-title{font-family:'Songti SC','Noto Serif SC',serif;font-size:22px;font-weight:900;line-height:1.15;text-decoration:none;color:var(--ink)}
.cockpit-card a.c-title:hover{color:var(--accent)}
.cockpit-card .c-meta{font-size:13px;color:var(--muted);line-height:1.5}
.cockpit-card .c-tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:auto}
.cockpit-card .c-tags a{font-size:12px;padding:4px 9px;border:1px solid var(--line);background:var(--paper-2);color:var(--muted);text-decoration:none;font-weight:700}
.cockpit-card .c-tags a:hover{border-color:var(--accent);color:var(--accent)}
.cockpit-card.empty{justify-content:center;align-items:flex-start;color:var(--muted);font-size:13px;line-height:1.6;background:var(--paper-2);border-style:dashed}
.section-count{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;color:var(--muted);font-size:20px;font-weight:900}
.kpi-row{display:flex;gap:14px;flex-wrap:wrap;margin:4px 0 8px}
.kpi{border:1px solid var(--line-strong);background:var(--paper-2);box-shadow:var(--shadow);padding:14px 18px;min-width:128px}
.kpi .n{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;font-size:34px;font-weight:900;line-height:1}
.kpi .l{font-size:11px;letter-spacing:.16em;color:var(--muted);font-weight:900;margin-top:4px}
.cross-note{font-size:13px;color:#3b2b1e;border-left:5px solid var(--accent-2);background:#fff4e9;padding:10px 14px;margin:6px 0 14px}
"""


def base_css() -> str:
    """cockpit 使用自己的独立主题（FALLBACK_CSS），不再继承每日复盘的 <style>。
    日复盘已升级为暗色主题（--bg/--green），与 cockpit 的 paper 主题 CSS var 不兼容
    （--paper/--card/--accent）。两套界面各自独立，避免 var 未定义导致样式崩溃。"""
    return FALLBACK_CSS


def date_of(name: str) -> str:
    match = DATE_RE.search(name)
    return match.group(1) if match else ""


def rel(target: Path) -> str:
    return os.path.relpath(target, OUT_PATH.parent).replace(os.sep, "/")


def card(label: str, head_html: str, meta: str, tags: list[tuple[str, str]]) -> str:
    tags_html = "".join(f'<a href="{escape(href)}">{escape(text)}</a>' for text, href in tags)
    return (
        '<div class="cockpit-card">'
        f'<div class="c-label">{escape(label)}</div>'
        f"{head_html}"
        f'<div class="c-meta">{escape(meta)}</div>'
        f'<div class="c-tags">{tags_html}</div>'
        "</div>"
    )


def empty_card(text: str) -> str:
    return f'<div class="cockpit-card empty">{escape(text)}</div>'


def daily_cards() -> list[str]:
    cards = []
    for d in sorted(DAILY.glob("*/"), reverse=True):
        date = date_of(d.name)
        review = d / f"{date}-daily-review.html"
        if not review.exists():
            continue
        tags: list[tuple[str, str]] = []
        brief = d / f"{date}-market-triggered-theme-brief.html"
        cand = d / f"{date}-theme-candidates.html"
        queue = d / f"{date}-research-queue.html"
        agent = d / f"{date}-daily-agent.html"
        if brief.exists():
            tags.append(("题材简报", rel(brief)))
        if cand.exists():
            tags.append(("题材候选", rel(cand)))
        if queue.exists():
            tags.append(("研究队列", rel(queue)))
        elif agent.exists():
            tags.append(("Agent 简报", rel(agent)))
        head = f'<a class="c-date" href="{rel(review)}">{date}</a>'
        cards.append(card("Daily Review", head, "每日复盘 · 指数/情绪/行业/双红题材", tags))
    return cards


def winrate_cards() -> list[str]:
    cards = []
    for f in sorted(WINRATE.glob("winrate-*.html"), reverse=True):
        date = date_of(f.name)
        head = f'<a class="c-date" href="{rel(f)}">{date}</a>'
        cards.append(card("Win-Rate", head, "卖方机构胜率榜 · T+3/5/7/10 超额", []))
    return cards


def matrix_cards() -> list[str]:
    cards = []
    files = sorted(p for p in MATRICES.glob("*.html"))
    sw = [p for p in files if p.name.startswith("sw-theme-matrix")]
    named = [p for p in files if p.name in MATRIX_TITLES]
    for f in named + sw:
        if f.name.startswith("sw-theme-matrix"):
            title, meta = "申万题材矩阵", date_of(f.name) and f"区间 {f.stem.split('sw-theme-matrix-')[-1]}" or "申万一级题材"
        else:
            title, meta = MATRIX_TITLES[f.name], "策略矩阵 · 跨日期"
        head = f'<a class="c-title" href="{rel(f)}">{escape(title)}</a>'
        cards.append(card("Strategy", head, meta, []))
    return cards


def headtohead_cards() -> list[str]:
    files = sorted(HEADTOHEAD.glob("headtohead-*.html"), reverse=True)
    if not files:
        return [empty_card(
            "暂无人机对照台账。生成：python3 scripts/headtohead_ledger.py "
            "--mine-selections 复盘/selections "
            "--machine-records evolution/records --strategy 1 "
            "--out 复盘/headtohead/headtohead-$(date +%F).html"
        )]
    cards = []
    for f in files:
        date = date_of(f.name) or f.stem
        head = f'<a class="c-date" href="{rel(f)}">{date}</a>'
        cards.append(card("Head-to-Head", head, "人机对照台账 · 你 vs 机器 · T+N 超额胜率/累计超额", []))
    return cards


def moneyflow_cards() -> list[str]:
    if not MONEYFLOW.exists():
        return [empty_card(
            "暂无资金流看板。生成：python3 scripts/render_moneyflow_html.py（需先用 "
            "scripts/moneyflow/ 扫描脚本写入 DuckDB）"
        )]
    head = f'<a class="c-title" href="{rel(MONEYFLOW)}">大单资金流看板</a>'
    return [card(
        "L2 Moneyflow", head,
        "昨日涨停榜 / 成交额前100榜 / 量化单榜 · 自有大单口径 · 按日期回看", [])]


def dualblind_cards() -> list[str]:
    if not DUALBLIND.exists():
        return [empty_card("暂无每日四问看板。生成：python3 scripts/render_dual_blind_qa.py")]
    head = f'<a class="c-title" href="{rel(DUALBLIND)}">每日四问看板</a>'
    return [card(
        "Dual-Blind Ledger", head,
        "Codex vs Claude 双盲问答台账 · 答卷/T+1 回填/批注/命中率 · 按日期回看", [])]


def briefing_cards(knowledge_root: Path) -> list[str]:
    dashboard = knowledge_root / "dashboard" / "index.html"
    briefings_dir = knowledge_root / "wiki" / "briefings"
    cards = []
    if dashboard.exists():
        head = f'<a class="c-title" href="{rel(dashboard)}">知识库驾驶舱</a>'
        cards.append(card("Knowledge Dashboard", head, "题材/个股搜索 · 提及趋势 · 催化日历 · 最近报告", []))
    if not briefings_dir.exists():
        if cards:
            return cards
        return [empty_card(
            "未找到知识库晨汇目录。当前查找："
            f"{briefings_dir}"
        )]
    files = sorted(briefings_dir.glob("*.html"), reverse=True)
    if not files:
        files = sorted(briefings_dir.glob("*.md"), key=lambda p: p.name, reverse=True)
    if not files:
        if cards:
            return cards
        return [empty_card(f"晨汇看板目录为空：{briefings_dir}")]
    for f in files[:40]:
        date = date_of(f.name) or f.stem
        head = f'<a class="c-date" href="{rel(f)}">{date}</a>'
        cards.append(card("Morning Brief", head, "晨汇边际变化 · T1/T2/T3 共振 · 映射标的", []))
    return cards


def section(sid: str, title: str, cards: list[str]) -> str:
    grid = "".join(cards) if cards else empty_card("暂无产物。")
    count = sum(1 for c in cards if "empty" not in c)
    return (
        f'<section id="{sid}"><h2>{escape(title)} '
        f'<span class="section-count">{count}</span></h2>'
        f'<div class="cockpit-grid">{grid}</div></section>'
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--knowledge-root",
        default=str(ROOT.parent / "知识库"),
        help="知识库仓根目录（默认取同级 知识库）",
    )
    args = parser.parse_args()
    knowledge_root = Path(args.knowledge_root).expanduser()

    daily = daily_cards()
    winrate = winrate_cards()
    briefing = briefing_cards(knowledge_root)
    matrices = matrix_cards()
    headtohead = headtohead_cards()
    moneyflow = moneyflow_cards()
    dualblind = dualblind_cards()

    built = datetime.date.today().isoformat()
    css = base_css() + EXTRA_CSS

    n_daily = len(daily)
    n_win = len(winrate)
    n_brief = sum(1 for c in briefing if "empty" not in c)
    n_matrix = len(matrices)
    n_h2h = sum(1 for c in headtohead if "empty" not in c)
    n_flow = sum(1 for c in moneyflow if "empty" not in c)
    n_db = sum(1 for c in dualblind if "empty" not in c)
    kpis = [
        (n_daily, "每日复盘"),
        (n_win, "胜率榜"),
        (n_brief, "晨汇看板"),
        (n_matrix, "策略矩阵"),
        (n_h2h, "人机台账"),
        (n_flow, "资金流"),
        (n_db, "每日四问"),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="n">{n}</div><div class="l">{escape(label)}</div></div>'
        for n, label in kpis
    )

    toc = "".join(
        f'<a href="#{sid}"><span>{i:02d}</span>{escape(title)}</a>'
        for i, (sid, title) in enumerate(
            [
                ("daily", "每日复盘"),
                ("winrate", "卖方机构胜率榜"),
                ("briefing", "晨汇边际变化"),
                ("matrices", "策略矩阵"),
                ("headtohead", "人机对照台账"),
                ("moneyflow", "大单资金流"),
                ("dualblind", "每日四问"),
            ],
            1,
        )
    )

    cross = (
        '<div class="cross-note">晨汇边际变化来自知识库仓 '
        "dashboard/index.html 与 wiki/briefings/，链接按本地相对路径生成；"
        "若打开 404，请用 --knowledge-root 指向正确知识库仓。</div>"
    )

    body = (
        '<section class="hero"><div class="kicker">Research Cockpit</div>'
        "<h1>驾驶舱<br>总入口</h1>"
        '<div class="summary">把每日复盘、卖方机构胜率榜、晨汇边际变化、策略矩阵串成一个'
        "可点进去的界面：左侧导航定位四类产物，右侧卡片按最新优先排列，点击即进入对应可视化页。"
        "界面语言与每日复盘共用同一套浅色投研 briefing 主题。</div></section>"
        f'<div class="kpi-row">{kpi_html}</div>'
        + section("daily", "每日复盘", daily)
        + section("winrate", "卖方机构胜率榜", winrate)
        + cross
        + section("briefing", "晨汇边际变化", briefing)
        + section("matrices", "策略矩阵", matrices)
        + section("headtohead", "人机对照台账", headtohead)
        + section("moneyflow", "大单资金流", moneyflow)
        + section("dualblind", "每日四问", dualblind)
    )

    html = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>驾驶舱总入口</title>"
        f"<style>{css}</style></head><body>"
        '<a class="skip" href="#main">跳到正文</a>'
        '<div class="shell"><aside class="rail">'
        '<div class="mark">Market<br>Cockpit</div>'
        f'<div class="date-card"><div class="label">BUILT</div><div class="date">{built}</div></div>'
        '<div class="tools"><button id="focus" type="button">专注阅读</button></div>'
        f'<nav class="toc" aria-label="驾驶舱目录">{toc}</nav></aside>'
        f'<main class="content" id="main">{body}</main></div>'
        '<script>document.getElementById("focus").onclick=()=>document.body.classList.toggle("focus");</script>'
        "</body></html>"
    )

    OUT_PATH.write_text(html, encoding="utf-8")
    print(OUT_PATH)
    print(
        f"daily: {n_daily} | winrate: {n_win} | briefing: {n_brief} | matrices: {n_matrix} "
        f"| headtohead: {n_h2h} | moneyflow: {n_flow} | dualblind: {n_db} "
        f"| size: {len(html) // 1024} KB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
