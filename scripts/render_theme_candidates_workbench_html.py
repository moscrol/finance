from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "market_feature_store" / "exports"
DAILY_ROOT = ROOT / "复盘" / "daily"
STYLE = """
:root{--paper:#f6f0e6;--paper-2:#fffaf1;--ink:#17140f;--muted:#746b5d;--line:#d8cbbb;--line-strong:#18140f;--accent:#0057ff;--accent-2:#ff5a1f;--critical:#c9152e;--high:#ff7a00;--card:#fffdf8;--shadow:0 22px 60px rgba(38,28,13,.10)}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:linear-gradient(90deg,rgba(23,20,15,.045) 1px,transparent 1px),linear-gradient(rgba(23,20,15,.035) 1px,transparent 1px),var(--paper);background-size:28px 28px;color:var(--ink);font-family:'Avenir Next','PingFang SC','Hiragino Sans GB',sans-serif}.shell{max-width:1680px;margin:0 auto;padding:26px}.hero{border:1px solid var(--line-strong);background:rgba(255,250,241,.92);box-shadow:var(--shadow);padding:28px;display:grid;grid-template-columns:minmax(0,1.2fr) minmax(300px,.8fr);gap:22px}.kicker{font-size:11px;letter-spacing:.22em;color:var(--muted);font-weight:900;text-transform:uppercase}.hero h1{font-family:'Bodoni 72','Songti SC',serif;font-size:58px;line-height:.9;letter-spacing:-.06em;margin:10px 0 0}.summary{color:var(--muted);line-height:1.7;margin-top:14px;max-width:760px}.stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.stat{border:1px solid var(--line);background:var(--card);padding:14px}.stat b{display:block;font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;font-size:34px;line-height:1;color:var(--accent)}.stat span{font-size:11px;letter-spacing:.16em;color:var(--muted);font-weight:900}.grid{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(340px,.75fr);gap:18px;margin-top:18px}.panel{border:1px solid var(--line-strong);background:rgba(255,250,241,.94);box-shadow:var(--shadow);padding:18px;min-width:0}.panel h2{margin:0 0 12px;font-size:20px;letter-spacing:-.02em}.table-wrap{overflow:auto;border:1px solid var(--line);background:var(--card)}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:10px 9px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}th{position:sticky;top:0;background:var(--ink);color:var(--paper-2);font-size:11px;letter-spacing:.12em;text-transform:uppercase;z-index:1}tr:last-child td{border-bottom:0}.rank{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;font-size:22px;font-weight:900}.theme{font-weight:900}.muted{color:var(--muted)}.score{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;font-size:22px;font-weight:900;color:var(--accent)}.badges{display:flex;flex-wrap:wrap;gap:5px}.badge{border:1px solid var(--line);background:#fff;padding:3px 6px;font-size:11px;font-weight:800;white-space:nowrap}.badge.critical{background:var(--critical);border-color:var(--critical);color:#fff}.badge.high{background:var(--high);border-color:var(--high);color:#1a1208}.counts{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;font-size:18px}.queue{display:grid;gap:8px}.queue-item{border:1px solid var(--line);background:var(--card);padding:12px}.queue-head{display:flex;justify-content:space-between;gap:10px;align-items:start}.reason{margin-top:6px;color:var(--muted);line-height:1.55;font-size:12px}.details{margin-top:18px;display:grid;gap:10px}.detail-card{border:1px solid var(--line);background:var(--card);padding:14px}.detail-card h3{margin:0 0 8px;font-size:16px}.detail-row{display:grid;grid-template-columns:130px 76px 1fr;gap:8px;padding:7px 0;border-top:1px solid var(--line);font-size:12px}.detail-row:first-of-type{border-top:0}.section-title{display:flex;align-items:end;justify-content:space-between;gap:12px}.section-title small{color:var(--muted);font-weight:700}.empty{border:1px dashed var(--line);background:rgba(255,255,255,.45);padding:18px;color:var(--muted)}@media(max-width:1100px){.hero,.grid{grid-template-columns:1fr}.hero h1{font-size:46px}}
"""


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"json root is not an object: {path}")
    return data


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def text(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def fmt(value: Any, digits: int = 2) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return text(value)


def badges(values: list[Any], limit: int = 5) -> str:
    parts = [f'<span class="badge">{escape(str(item))}</span>' for item in values[:limit]]
    if len(values) > limit:
        parts.append(f'<span class="badge">+{len(values) - limit}</span>')
    return '<div class="badges">' + "".join(parts) + "</div>"


def candidate_table(rows: list[dict[str, Any]], empty_text: str) -> str:
    if not rows:
        return f'<div class="empty">{escape(empty_text)}</div>'
    body = []
    for row in rows:
        status = row.get("knowledge_status") if isinstance(row.get("knowledge_status"), dict) else {}
        body.append(
            "<tr>"
            f'<td class="rank">{escape(text(row.get("rank")))}</td>'
            f'<td><div class="theme">{escape(text(row.get("market_theme")))}</div><div class="muted">{escape(text(row.get("canonical_concept")))}</div></td>'
            f'<td>{escape(text(row.get("sw_l1")))}</td>'
            f'<td class="score">{escape(fmt(row.get("priority_score")))}</td>'
            f'<td>{badges(as_list(row.get("trigger_types")))}</td>'
            f'<td class="counts">{escape(text(status.get("concept_count", 0)))}/{escape(text(status.get("exposure_count", 0)))}/{escape(text(status.get("evidence_count", 0)))}</td>'
            "</tr>"
        )
    return '<div class="table-wrap"><table><thead><tr><th>#</th><th>题材</th><th>行业</th><th>Score</th><th>触发信号</th><th>C/E/V</th></tr></thead><tbody>' + "".join(body) + "</tbody></table></div>"


def queue_panel(queue: dict[str, Any]) -> str:
    items = [item for item in as_list(queue.get("items")) if isinstance(item, dict) and item.get("priority") in {"critical", "high"}]
    if not items:
        return '<div class="empty">暂无 Critical / High 补库项。</div>'
    cards = []
    for item in items[:18]:
        priority = str(item.get("priority") or "")
        cards.append(
            '<div class="queue-item">'
            '<div class="queue-head">'
            f'<div><div class="theme">#{escape(text(item.get("rank")))} {escape(text(item.get("theme")))}</div><div class="muted">{escape(text(item.get("gap_type")))}</div></div>'
            f'<span class="badge {escape(priority)}">{escape(priority.upper())}</span>'
            '</div>'
            f'<div class="reason">{escape(text(item.get("reason")))}</div>'
            f'{badges(as_list(item.get("trigger_types")), limit=4)}'
            '</div>'
        )
    if len(items) > 18:
        cards.append(f'<div class="empty">还有 {len(items) - 18} 条 Critical / High 项未展开。</div>')
    return '<div class="queue">' + "".join(cards) + "</div>"


def score_details(rows: list[dict[str, Any]]) -> str:
    cards = []
    for row in rows[:10]:
        details = [item for item in as_list(row.get("score_detail")) if isinstance(item, dict)]
        detail_rows = []
        for item in details[:6]:
            detail_rows.append(
                '<div class="detail-row">'
                f'<div>{escape(text(item.get("signal")))}</div>'
                f'<div>{escape(fmt(item.get("score")))}</div>'
                f'<div class="muted">{escape(text(item.get("reason")))}</div>'
                '</div>'
            )
        cards.append(
            '<article class="detail-card">'
            f'<h3>#{escape(text(row.get("rank")))} {escape(text(row.get("market_theme")))}</h3>'
            + ("".join(detail_rows) if detail_rows else '<div class="empty">暂无评分明细。</div>')
            + '</article>'
        )
    return '<div class="details">' + "".join(cards) + "</div>"


def render(candidates: dict[str, Any], queue: dict[str, Any]) -> str:
    trade_date = text(candidates.get("trade_date"))
    context = candidates.get("market_context") if isinstance(candidates.get("market_context"), dict) else {}
    tier = candidates.get("tier_summary") if isinstance(candidates.get("tier_summary"), dict) else {}
    priority = queue.get("priority_counts") if isinstance(queue.get("priority_counts"), dict) else {}
    deep = [row for row in as_list(candidates.get("deep_candidates")) if isinstance(row, dict)]
    watch = [row for row in as_list(candidates.get("watch_candidates")) if isinstance(row, dict)]
    capacity = as_list(context.get("capacity_sectors"))
    capacity_text = " / ".join(str(item.get("name")) for item in capacity if isinstance(item, dict) and item.get("name")) or "-"
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(trade_date)} 题材候选工作台</title><style>{STYLE}</style></head><body><main class="shell"><section class="hero"><div><div class="kicker">Theme Candidates Workbench</div><h1>{escape(trade_date)}<br>题材候选</h1><div class="summary">读取本地 theme-candidates 与 theme-backfill-queue 产物，聚焦 Deep / Watch 候选和 Critical / High 知识库缺口。不调用大模型，不包含买卖指令。</div></div><div class="stats"><div class="stat"><b>{escape(text(candidates.get("candidate_count", 0)))}</b><span>CANDIDATES</span></div><div class="stat"><b>{escape(text(tier.get("deep_count", 0)))}/{escape(text(tier.get("watch_count", 0)))}</b><span>DEEP / WATCH</span></div><div class="stat"><b>{escape(text(priority.get("critical", 0)))}/{escape(text(priority.get("high", 0)))}</b><span>CRITICAL / HIGH</span></div><div class="stat"><b>{escape(text(context.get("market_stage")))}</b><span>MARKET STAGE</span></div></div></section><section class="grid"><div class="panel"><div class="section-title"><h2>Deep Top10</h2><small>容量前三：{escape(capacity_text)}</small></div>{candidate_table(deep, "暂无 Deep 候选。")}<div class="section-title" style="margin-top:18px"><h2>Watch Top11-30</h2><small>观察池</small></div>{candidate_table(watch, "暂无 Watch 候选。")}</div><aside class="panel"><div class="section-title"><h2>Critical / High Queue</h2><small>知识库补强</small></div>{queue_panel(queue)}</aside></section><section class="panel" style="margin-top:18px"><div class="section-title"><h2>Deep 评分明细</h2><small>score_detail</small></div>{score_details(deep)}</section></main></body></html>'''


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: render_theme_candidates_workbench_html.py YYYY-MM-DD")
    trade_date = sys.argv[1]
    candidates = read_json(EXPORTS / f"{trade_date}-theme-candidates.json")
    queue = read_json(EXPORTS / f"{trade_date}-theme-backfill-queue.json")
    out_dir = DAILY_ROOT / trade_date
    out_path = out_dir / f"{trade_date}-theme-candidates.html"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(candidates, queue), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
