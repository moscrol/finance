#!/usr/bin/env python3
"""答卷 JSON → 双盲并排对比页：YYYY-MM-DD.html（Claude / Codex 两栏）。

已存在人工撰写的 ``YYYY-MM-DD.html`` 时跳过（不覆盖）；自动生成的文件带
``<!-- auto-generated from answer JSON -->`` 标记，重复运行会刷新这些文件。

Usage:
    python3 scripts/render_dual_blind_pair_html.py [YYYY-MM-DD ...]
    （不带参数时补齐台账目录里所有有答卷 JSON 的日期）
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "learning" / "forecast-review-ledger"
AUTO_MARK = "<!-- auto-generated from answer JSON -->"
AGENTS = ("claude", "codex")

CSS = """
:root { --bg:#f7f8fa; --text:#1f2933; --muted:#64748b; --line:#d9dee7; --panel:#fff; --ink:#0f172a; --blue:#2563eb; }
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.55}
header{background:#111827;color:#fff;padding:24px 32px}
header h1{margin:0 0 6px;font-size:24px} header p{margin:0;color:#cbd5e1}
.wrap{display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:24px;max-width:1500px;margin:0 auto}
@media(max-width:960px){.wrap{grid-template-columns:1fr}}
.col h2{color:var(--ink);border-bottom:2px solid var(--blue);padding-bottom:6px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 18px;margin-bottom:14px}
.card h3{margin:0 0 8px;font-size:15px;color:var(--blue)}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:#eef2f7}
code{background:#eef2f7;padding:1px 5px;border-radius:4px;font-size:12px}
.muted{color:var(--muted);font-size:12.5px}
.note{max-width:1500px;margin:0 auto;padding:0 24px 24px;color:var(--muted);font-size:13px}
ul,ol{margin:6px 0;padding-left:20px} li{margin-bottom:6px}
"""

THRESHOLD_NAMES = {"market": "市场", "direction": "方向", "targets": "标的", "falsify": "证伪"}


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def card(title: str, body: str) -> str:
    return f'<section class="card"><h3>{esc(title)}</h3>{body}</section>'


def table(header: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in header)
    trs = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"


def freeze_card(ans: dict) -> str:
    items = []
    cutoff = ans.get("duckdb_cutoff") or (ans.get("input_freeze") or {}).get("duckdb_cutoff")
    if cutoff:
        items.append(f"<li>DuckDB 截止：{esc(cutoff)}</li>")
    if ans.get("manifest_sha"):
        items.append(f"<li>manifest_sha：<code>{esc(ans['manifest_sha'])}</code></li>")
    freeze = ans.get("input_freeze")
    if isinstance(freeze, dict):
        for k in ("materials_note", "note", "notes", "warnings"):
            v = freeze.get(k)
            if isinstance(v, str) and v:
                items.append(f'<li class="muted">{esc(v)}</li>')
            elif isinstance(v, list):
                items += [f'<li class="muted">{esc(x)}</li>' for x in v]
    return card("0. 输入冻结", f"<ul>{''.join(items)}</ul>") if items else ""


def direction_card(ans: dict) -> str:
    dr = ans.get("direction_ranking")
    if not (isinstance(dr, list) and dr):
        return ""
    reasoning = ans.get("direction_reasoning")
    lis = []
    for i, x in enumerate(dr):
        if isinstance(x, dict):
            name = x.get("sector") or x.get("direction") or ""
            why = x.get("rationale") or x.get("reason") or ""
        else:
            parts = re.split(r"[：:]", str(x), maxsplit=1)
            name = parts[0].strip()
            why = parts[1].strip() if len(parts) > 1 else ""
            if not why and isinstance(reasoning, list) and i < len(reasoning):
                why = str(reasoning[i])
        lis.append(f"<li><b>{esc(name)}</b>" + (f" — {esc(why)}" if why else "") + "</li>")
    return card("3. 方向排序", f"<ol>{''.join(lis)}</ol>")


def picks_card(ans: dict) -> str:
    picks = ans.get("picks")
    if not (isinstance(picks, list) and picks and isinstance(picks[0], dict)):
        return ""
    rows = []
    for p in picks:
        code = p.get("ts_code") or p.get("code") or ""
        rows.append([
            f"<b>{esc(p.get('name', ''))}</b><br><code>{esc(code)}</code>",
            esc(p.get("strategy", "")), esc(p.get("reason", ""))])
    return card("4. 标的池", table(["标的", "策略", "理由（绑定§1证据）"], rows))


def thresholds_card(ans: dict) -> str:
    th = ans.get("thresholds")
    if not (isinstance(th, dict) and th):
        return ""
    rows = [[esc(THRESHOLD_NAMES.get(k, k)), esc(v)] for k, v in th.items()]
    return card("5. 验证阈值", table(["维度", "条件"], rows))


def hypotheses_card(ans: dict) -> str:
    hyps = [h for h in ans.get("hypotheses") or [] if isinstance(h, dict)]
    if not hyps:
        return ""
    lis = []
    for h in hyps:
        claim = h.get("claim") or h.get("text") or ""
        extra = []
        if h.get("metric"):
            extra.append(f"指标：{h['metric']}")
        if h.get("falsify_when"):
            extra.append(f"证伪：{h['falsify_when']}")
        tail = f' <span class="muted">（{esc("；".join(extra))}）</span>' if extra else ""
        lis.append(f"<li><b>{esc(h.get('id', ''))}</b> {esc(claim)}{tail}</li>")
    return card("6. 待验证假设", f"<ul>{''.join(lis)}</ul>")


def recheck_card(ans: dict) -> str:
    rec = ans.get("recheck")
    if not isinstance(rec, dict):
        return ""
    picks = ans.get("picks") or []
    parts = []
    for label, key in (("T+1", "pick_returns_t1"), ("T+3", "pick_returns_t3")):
        rows_raw = rec.get(key)
        if not (isinstance(rows_raw, list) and rows_raw):
            continue
        if isinstance(rows_raw[0], dict):
            ks = list(rows_raw[0].keys())
            rows = [[esc(r.get(k, "")) for k in ks] for r in rows_raw]
            parts.append(f"<p><b>{label} 标的回报</b></p>" + table(ks, rows))
        else:
            rows = []
            for i, r in enumerate(rows_raw):
                p = picks[i] if i < len(picks) and isinstance(picks[i], dict) else {}
                rows.append([esc(p.get("code", "")), esc(p.get("name", "")), esc(r)])
            parts.append(f"<p><b>{label} 标的回报</b></p>"
                         + table(["code", "name", "回报%"], rows))
    info = [f"基准 {esc(rec.get('benchmark'))}"]
    if rec.get("recheck_t1_date"):
        info.append(f"T+1 回检日 {esc(rec['recheck_t1_date'])}")
    if rec.get("recheck_generated_at"):
        info.append(f"回检生成于 {esc(rec['recheck_generated_at'])}")
    parts.append(f'<p class="muted">{"；".join(info)}</p>')
    return card("7. T+1/T+3 回检", "".join(parts))


def column(agent: str, ans: dict) -> str:
    cards = [freeze_card(ans)]
    if ans.get("stage"):
        cards.append(card("阶段", f"<p>{esc(ans['stage'])}</p>"))
    if ans.get("main_judgment"):
        cards.append(card("2. 主判断", f"<p>{esc(ans['main_judgment'])}</p>"))
    cards += [direction_card(ans), picks_card(ans), thresholds_card(ans),
              hypotheses_card(ans), recheck_card(ans)]
    return f'<div class="col"><h2>{agent.capitalize()}</h2>{"".join(c for c in cards if c)}</div>'


def load_answers(date: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for agent in AGENTS:
        p = LEDGER / f"{date}.answer.{agent}.json"
        if p.exists():
            try:
                out[agent] = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    return out


def build_html(date: str, answers: dict[str, dict]) -> str:
    sha = next((a.get("manifest_sha") for a in answers.values()
                if a.get("manifest_sha")), "")
    cutoff = next((a.get("duckdb_cutoff")
                   or (a.get("input_freeze") or {}).get("duckdb_cutoff")
                   for a in answers.values()), None)
    sub = [f"manifest_sha <code>{esc(sha)}</code>"]
    if cutoff:
        sub.append(f"DuckDB 冻结至 {esc(cutoff)}")
    sub.append("双盲：" + " / ".join(a.capitalize() for a in answers) + " 互不可见")
    sub.append("回检：收盘后 recheck + verdict")
    cols = "".join(column(agent, ans) for agent, ans in answers.items())
    return (
        "<!doctype html>\n"
        f"{AUTO_MARK}\n"
        '<html lang="zh-CN">\n<head>\n'
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{date} 双盲答卷并排页</title>\n<style>{CSS}</style>\n</head>\n<body>\n"
        f"<header><h1>{date} 双盲答卷并排页</h1>\n<p>{' · '.join(sub)}</p></header>\n"
        f'<div class="wrap">\n{cols}\n</div>\n'
        f'<p class="note"><a href="{date}.md">人读版台账 md</a> · <a href="index.html">台账索引</a></p>\n'
        "</body></html>\n")


def main(argv: list[str]) -> int:
    if argv:
        dates = argv
    else:
        dates = sorted({
            m.group(1)
            for f in LEDGER.iterdir()
            if (m := re.match(r"^(\d{4}-\d{2}-\d{2})\.answer\.", f.name))
        })
    for date in dates:
        out = LEDGER / f"{date}.html"
        if out.exists() and AUTO_MARK not in out.read_text(encoding="utf-8")[:200]:
            print(f"skip {date}（已有人工并排页）")
            continue
        answers = load_answers(date)
        if not answers:
            print(f"skip {date}（无答卷 JSON）")
            continue
        out.write_text(build_html(date, answers), encoding="utf-8")
        print(f"write {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
