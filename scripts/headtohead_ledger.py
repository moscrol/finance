#!/usr/bin/env python3
"""人机对照台账：把「你的实选」与「机器(strategy-evolve)生成名单」放在同一套
T+N 相对沪深300超额口径下并排打分，量化「机器到底比你强/弱多少」。

口径与胜率榜(opinion-cross)完全一致，复用 price_lib.fwd_metrics：
  进场 = 报告日次日开盘；T+3/5/7/10 收盘；超额 = 个股收益 − 沪深300 同窗收益（剥大盘 beta）；
  另给区间最高收益(均最高) 与 峰值后回撤(均回撤)。
零 DuckDB 依赖：行情走腾讯/新浪公开接口（price_lib 自带仓外磁盘缓存）。

两边输入都是「日期 -> 名单」，名单元素可为 6 位代码 / 带 sh|sz|bj 前缀代码 / 个股名。
机器名单可直接从 strategy-evolve 的 evolution/records/*.json 读取（--machine-records）。

用法：
  # 你的名单 vs 机器名单（两个 picks 文件）
  python3 scripts/headtohead_ledger.py --mine mine.json --machine machine.json \
      --out 复盘/headtohead/headtohead-2026-06-17.html

  # 你的真实选股直接读 复盘/selections（无需手搓 mine.json）vs 机器记录
  python3 scripts/headtohead_ledger.py --mine-selections 复盘/selections \
      --machine-records evolution/records --strategy 1 \
      --out 复盘/headtohead/headtohead-2026-06-17.html

  # 机器侧直接读 strategy-evolve 记录（在你本地 evolve generate 之后）
  python3 scripts/headtohead_ledger.py --mine mine.json \
      --machine-records evolution/records --strategy 1 --scope T1CORE6

picks 文件两种格式（自动识别）：
  1) JSON 对象：{"2026-05-22": ["中际旭创","002552"], "2026-05-25": ["沪电股份"]}
  2) JSONL：每行 {"date":"2026-05-22","picks":["中际旭创","002552"]}
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "skills" / "opinion-cross" / "scripts"))
import price_lib  # noqa: E402

WINDOWS = (3, 5, 7, 10)
BENCH = "sh000300"  # 沪深300
CAL_BUFFER = 50      # 抓行情时往后多取的自然日，确保覆盖 T+10 交易日

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
SEL_CODE_RE = re.compile(r"(\d{6})\.(SH|SZ|BJ)", re.IGNORECASE)
SEL_HEAD_RE = re.compile(r"^\s*#{1,6}\s*(.+?)\s*$")
_EX2PREFIX = {"SH": "sh", "SZ": "sz", "BJ": "bj"}


# ---------- 输入解析 ----------
def to_tencent(token: str) -> str | None:
    """6 位代码 / 带前缀代码 -> 腾讯格式 shXXXXXX；个股名返回 None（交给 name2code）。"""
    t = (token or "").strip()
    if not t:
        return None
    low = t.lower()
    if len(low) == 8 and low[:2] in ("sh", "sz", "bj") and low[2:].isdigit():
        return low
    if t.isdigit() and len(t) == 6:
        if t[0] == "6":
            return "sh" + t
        if t[0] in ("0", "3"):
            return "sz" + t
        if t[0] in ("4", "8"):
            return "bj" + t
        return "sz" + t
    return None


def resolve_code(token: str, code_cache: dict) -> str | None:
    tc = to_tencent(token)
    if tc:
        return tc
    return price_lib.name2code(token, code_cache)


def load_picks(path: Path) -> dict[str, list[str]]:
    """读 picks 文件 -> {date: [token, ...]}。兼容 JSON 对象与 JSONL。"""
    text = path.read_text(encoding="utf-8").strip()
    out: dict[str, list[str]] = {}
    if not text:
        return out
    # 先试整体 JSON 对象（单行或多行均可）
    try:
        blob = json.loads(text)
        if isinstance(blob, dict):
            for d, picks in blob.items():
                out.setdefault(str(d), []).extend(str(x) for x in picks)
            return out
    except json.JSONDecodeError:
        pass
    # 退回 JSONL
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        d = str(rec.get("date"))
        picks = rec.get("picks") or rec.get("codes") or rec.get("stocks") or []
        out.setdefault(d, []).extend(str(x) for x in picks)
    return out


def load_machine_records(records_dir: Path, strategy: int, scope: str) -> dict[str, list[str]]:
    """从 strategy-evolve 的 evolution/records/{date}.json 抽取机器名单（按 scope 过滤）。"""
    sys.path.insert(0, str(REPO))
    from evolution import strategy1, strategy3, strategy4  # noqa: E402

    picker = {1: strategy1, 3: strategy3, 4: strategy4}[strategy]
    out: dict[str, list[str]] = {}
    for jf in sorted(records_dir.glob("*.json")):
        rec = json.loads(jf.read_text(encoding="utf-8"))
        date = str(rec.get("date") or jf.stem)
        payload = (rec.get("strategies") or {}).get(str(strategy))
        if not payload:
            continue
        picks = picker.picks_in_scope(payload, scope)
        codes = [p.get("code") for p in picks if p.get("code")]
        if codes:
            out[date] = [str(c) for c in codes]
    return out


def _selection_codes(text: str, include_observation: bool) -> list[str]:
    """从一篇选股 markdown 抽取股票代码（统一成 sh|sz|bj 前缀）。默认跳过「观察」段。"""
    codes: list[str] = []
    skip = False
    for line in text.splitlines():
        head = SEL_HEAD_RE.match(line)
        if head:
            skip = (not include_observation) and ("观察" in head.group(1))
            continue
        if skip:
            continue
        for num, ex in SEL_CODE_RE.findall(line):
            codes.append(_EX2PREFIX[ex.upper()] + num)
    return list(dict.fromkeys(codes))  # 去重保序


def load_selections(path: Path, include_observation: bool = False) -> dict[str, list[str]]:
    """读 复盘/selections 选股记录（.md 文件或目录）-> {date: [code, ...]}。
    日期取自文件名里的 YYYY-MM-DD；默认只计「梯队」选股、跳过「观察组」。"""
    files = sorted(path.glob("*.md")) if path.is_dir() else [path]
    out: dict[str, list[str]] = {}
    for f in files:
        m = DATE_RE.search(f.name)
        if not m:
            continue
        codes = _selection_codes(f.read_text(encoding="utf-8"), include_observation)
        if codes:
            out.setdefault(m.group(1), []).extend(codes)
    return {d: list(dict.fromkeys(cs)) for d, cs in out.items()}


# ---------- 打分 ----------
def score_side(picks_by_date: dict[str, list[str]], code_cache: dict,
               idx_klines: list[tuple]) -> list[dict]:
    """对一侧名单逐票打分。返回每条 {date, token, code, metrics or None}。"""
    rows = []
    for date in sorted(picks_by_date):
        end = (dt.date.fromisoformat(date) + dt.timedelta(days=CAL_BUFFER)).isoformat()
        for token in picks_by_date[date]:
            code = resolve_code(token, code_cache)
            rec = {"date": date, "token": token, "code": code, "metrics": None}
            if code:
                try:
                    kl = price_lib.qfq_daily(code, date, end)
                    rec["metrics"] = price_lib.fwd_metrics(kl, date, idx_klines)
                except Exception as e:  # noqa: BLE001
                    rec["error"] = str(e)
            rows.append(rec)
    return rows


def aggregate(rows: list[dict]) -> dict:
    """按窗口聚合：超额胜率/绝对胜率/均超额/中超额/均最高/均回撤；并出累计超额曲线。"""
    agg = {"by_window": {}, "curve": {}, "scored": 0, "total": 0}
    agg["total"] = len(rows)
    scored = [r for r in rows if r.get("metrics")]
    agg["scored"] = len(scored)
    for w in WINDOWS:
        exc = [r["metrics"].get(f"excess_{w}d") for r in scored
               if r["metrics"].get(f"ret_{w}d_complete") and r["metrics"].get(f"excess_{w}d") is not None]
        absr = [r["metrics"].get(f"ret_{w}d") for r in scored
                if r["metrics"].get(f"ret_{w}d_complete") and r["metrics"].get(f"ret_{w}d") is not None]
        mh = [r["metrics"].get("interval_max_ret") for r in scored
              if r["metrics"].get("interval_max_ret") is not None]
        dd = [r["metrics"].get("post_peak_dd") for r in scored
              if r["metrics"].get("post_peak_dd") is not None]
        agg["by_window"][w] = {
            "n": len(exc),
            "win_exc": round(100 * sum(x > 0 for x in exc) / len(exc), 1) if exc else None,
            "win_abs": round(100 * sum(x > 0 for x in absr) / len(absr), 1) if absr else None,
            "avg_exc": round(st.mean(exc), 2) if exc else None,
            "med_exc": round(st.median(exc), 2) if exc else None,
            "avg_maxhit": round(st.mean(mh), 2) if mh else None,
            "avg_dd": round(st.mean(dd), 2) if dd else None,
        }
    # 累计超额曲线（按日期，主窗口逐日均超额累加）
    for w in WINDOWS:
        by_date: dict[str, list[float]] = {}
        for r in scored:
            m = r["metrics"]
            if m.get(f"ret_{w}d_complete") and m.get(f"excess_{w}d") is not None:
                by_date.setdefault(r["date"], []).append(m[f"excess_{w}d"])
        cum = 0.0
        series = []
        for d in sorted(by_date):
            day_mean = st.mean(by_date[d])
            cum += day_mean
            series.append({"date": d, "day_mean": round(day_mean, 2), "cum": round(cum, 2)})
        agg["curve"][w] = series
    return agg


# ---------- 控制台 ----------
def print_console(label_a: str, agg_a: dict, label_b: str, agg_b: dict, main_w: int) -> None:
    print(f"\n人机对照台账 | 口径=T+N 相对沪深300超额 | 进场=次日开盘 | 主窗口=T+{main_w}")
    print(f"{label_a}: 打分 {agg_a['scored']}/{agg_a['total']} 票 | "
          f"{label_b}: 打分 {agg_b['scored']}/{agg_b['total']} 票\n")
    head = f"{'窗口':>5} {'指标':<8} {label_a:>10} {label_b:>10} {'Δ(你-机)':>10}"
    print(head)
    print("-" * len(head))

    def fmt(v, pct=False):
        if v is None:
            return "—"
        return (f"{v:+.1f}%" if pct else f"{v:+.1f}")

    metrics = [("超额胜率", "win_exc", True), ("均超额", "avg_exc", False),
               ("均最高", "avg_maxhit", False), ("均回撤", "avg_dd", False)]
    for w in WINDOWS:
        a, b = agg_a["by_window"][w], agg_b["by_window"][w]
        for name, key, is_pct in metrics:
            va, vb = a.get(key), b.get(key)
            delta = (va - vb) if (va is not None and vb is not None) else None
            tag = f"T+{w}" if key == "win_exc" else ""
            print(f"{tag:>5} {name:<8} {fmt(va, is_pct):>10} {fmt(vb, is_pct):>10} {fmt(delta, is_pct):>10}")
        print()


# ---------- HTML (paper) ----------
PAPER_CSS = """
:root{--paper:#f6f0e6;--paper-2:#fffaf1;--ink:#17140f;--muted:#746b5d;--line:#d8cbbb;
--line-strong:#18140f;--accent:#0057ff;--accent-2:#ff5a1f;--card:#fffdf8;
--mine:#0057ff;--mach:#ff5a1f;--pos:#0a7d3c;--neg:#c2401d;
--shadow:0 18px 45px rgba(38,28,13,.08)}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);
font-family:'Avenir Next','PingFang SC','Hiragino Sans GB',sans-serif;line-height:1.5}
.shell{display:grid;grid-template-columns:320px minmax(0,1fr);gap:28px;max-width:1700px;margin:0 auto;padding:24px}
.rail{position:sticky;top:24px;height:calc(100dvh - 48px);overflow:auto;border:1px solid var(--line-strong);
background:rgba(255,250,241,.88);backdrop-filter:blur(14px);box-shadow:var(--shadow);padding:22px}
.mark{font-family:'Bodoni 72','Songti SC',serif;font-size:40px;line-height:.86;letter-spacing:-.04em}
.date-card{margin-top:18px;border:1px solid var(--line);background:var(--paper-2);padding:12px 14px}
.date-card .k{font-size:11px;letter-spacing:.18em;color:var(--muted)}
.date-card .v{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;font-size:28px}
.legend{margin-top:16px;font-size:13px;color:var(--muted)}
.legend .sw{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.note{margin-top:16px;font-size:12px;color:var(--muted);border-top:1px dashed var(--line);padding-top:12px}
.content{min-width:0}
.hero{position:relative;border:1px solid var(--line-strong);background:var(--card);padding:30px 34px;box-shadow:var(--shadow);overflow:hidden}
.hero:before{content:'';position:absolute;right:32px;top:24px;width:120px;height:120px;
border:18px solid var(--accent);border-left-color:transparent;border-radius:50%;opacity:.9}
.kicker{font-size:12px;letter-spacing:.32em;color:var(--accent);font-weight:700}
.hero h1{font-family:'Bodoni 72','Songti SC',serif;font-size:46px;margin:.18em 0 .1em;line-height:.98}
.hero p{color:var(--muted);max-width:760px;margin:.4em 0 0}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:22px 0}
.kpi{border:1px solid var(--line);background:var(--card);padding:16px}
.kpi .v{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;font-size:34px;line-height:1}
.kpi .l{font-size:12px;color:var(--muted);margin-top:6px}
.kpi.pos .v{color:var(--pos)}.kpi.neg .v{color:var(--neg)}
h2{font-family:'Bodoni 72','Songti SC',serif;margin-top:34px;border-left:6px solid var(--accent);
padding:13px 18px;background:var(--paper-2)}
h2:before{content:'§ ';color:var(--accent-2)}
.panel{border:1px solid var(--line);background:var(--card);padding:20px;margin-top:14px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right}
th:first-child,td:first-child{text-align:left}
th{position:sticky;top:0;background:var(--ink);color:var(--paper-2);font-weight:900}
tr:hover td{background:#f4f7ff}
.pos{color:var(--pos)}.neg{color:var(--neg)}
.foot{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:14px}
"""


def _bar_chart(agg_a, label_a, agg_b, label_b):
    """超额胜率 分窗口分组柱状（你 vs 机器）。"""
    w, h, pad = 560, 240, 36
    bw = (w - pad * 2) / (len(WINDOWS) * 2 + len(WINDOWS))
    parts = [f'<svg viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="xMidYMid meet">']
    parts.append(f'<line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" stroke="#d8cbbb"/>')
    for gi, win in enumerate(WINDOWS):
        gx = pad + gi * (bw * 3) + bw * 0.4
        for bi, (agg, color) in enumerate([(agg_a, "#0057ff"), (agg_b, "#ff5a1f")]):
            val = agg["by_window"][win].get("win_exc")
            v = val if val is not None else 0
            bh = (h - pad * 2) * (v / 100.0)
            x = gx + bi * bw
            y = (h - pad) - bh
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw*0.86:.1f}" height="{bh:.1f}" fill="{color}"/>')
            parts.append(f'<text x="{x+bw*0.43:.1f}" y="{y-4:.1f}" font-size="11" text-anchor="middle" '
                         f'fill="#17140f">{("%.0f%%"%v) if val is not None else "—"}</text>')
        parts.append(f'<text x="{gx+bw:.1f}" y="{h-pad+16:.1f}" font-size="12" text-anchor="middle" '
                     f'fill="#746b5d">T+{win}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _line_chart(curve_a, curve_b):
    """累计超额曲线（你 vs 机器）。"""
    w, h, pad = 560, 240, 36
    allpts = [p["cum"] for p in curve_a] + [p["cum"] for p in curve_b]
    if not allpts:
        return '<p style="color:#746b5d">无完整窗口样本，暂无曲线。</p>'
    lo, hi = min(allpts + [0]), max(allpts + [0])
    span = (hi - lo) or 1
    n = max(len(curve_a), len(curve_b), 1)

    def xy(i, val, total):
        x = pad + (w - pad * 2) * (i / max(total - 1, 1))
        y = (h - pad) - (h - pad * 2) * ((val - lo) / span)
        return x, y

    zero_y = (h - pad) - (h - pad * 2) * ((0 - lo) / span)
    parts = [f'<svg viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="xMidYMid meet">']
    parts.append(f'<line x1="{pad}" y1="{zero_y:.1f}" x2="{w-pad}" y2="{zero_y:.1f}" stroke="#d8cbbb" stroke-dasharray="4 4"/>')
    for curve, color in [(curve_a, "#0057ff"), (curve_b, "#ff5a1f")]:
        if not curve:
            continue
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in
                       (xy(i, p["cum"], len(curve)) for i, p in enumerate(curve)))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5"/>')
        last = curve[-1]
        lx, ly = xy(len(curve) - 1, last["cum"], len(curve))
        parts.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.5" fill="{color}"/>')
        parts.append(f'<text x="{lx-4:.1f}" y="{ly-6:.1f}" font-size="11" text-anchor="end" '
                     f'fill="{color}">{last["cum"]:+.1f}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _cls(v):
    if v is None:
        return ""
    return "pos" if v > 0 else ("neg" if v < 0 else "")


def _cell(v, pct=False):
    if v is None:
        return '<td>—</td>'
    s = (f"{v:+.1f}%" if pct else f"{v:+.1f}")
    return f'<td class="{_cls(v)}">{s}</td>'


def build_html(label_a, agg_a, label_b, agg_b, stamp, main_w) -> str:
    a, b = agg_a["by_window"][main_w], agg_b["by_window"][main_w]

    def delta(key):
        va, vb = a.get(key), b.get(key)
        return (va - vb) if (va is not None and vb is not None) else None

    d_win, d_exc = delta("win_exc"), delta("avg_exc")
    kpis = [
        (f"{a['win_exc']:.0f}%" if a["win_exc"] is not None else "—", f"{label_a} 超额胜率 T+{main_w}", ""),
        (f"{b['win_exc']:.0f}%" if b["win_exc"] is not None else "—", f"{label_b} 超额胜率 T+{main_w}", ""),
        (f"{d_win:+.1f}pp" if d_win is not None else "—", "胜率差 (你−机)", "pos" if (d_win or 0) >= 0 else "neg"),
        (f"{d_exc:+.1f}" if d_exc is not None else "—", "均超额差 (你−机)", "pos" if (d_exc or 0) >= 0 else "neg"),
    ]
    kpi_html = "".join(f'<div class="kpi {c}"><div class="v">{v}</div><div class="l">{l}</div></div>'
                       for v, l, c in kpis)

    # 分窗口对照表
    trows = []
    for w in WINDOWS:
        ra, rb = agg_a["by_window"][w], agg_b["by_window"][w]
        for label, key, pct in [("超额胜率", "win_exc", True), ("绝对胜率", "win_abs", True),
                                 ("均超额", "avg_exc", False), ("中超额", "med_exc", False),
                                 ("均最高", "avg_maxhit", False), ("均回撤", "avg_dd", False)]:
            va, vb = ra.get(key), rb.get(key)
            dv = (va - vb) if (va is not None and vb is not None) else None
            wlabel = f"T+{w} (n={ra['n']}/{rb['n']})" if key == "win_exc" else ""
            trows.append(f"<tr><td>{wlabel}</td><td>{label}</td>"
                         f"{_cell(va, pct)}{_cell(vb, pct)}{_cell(dv, pct)}</tr>")
    table_html = "".join(trows)

    bar = _bar_chart(agg_a, label_a, agg_b, label_b)
    line = _line_chart(agg_a["curve"][main_w], agg_b["curve"][main_w])

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>人机对照台账 {stamp}</title><style>{PAPER_CSS}</style></head>
<body><div class="shell">
<aside class="rail">
<div class="mark">Head<br>to<br>Head</div>
<div class="date-card"><div class="k">GENERATED</div><div class="v">{stamp}</div></div>
<div class="legend">
<div><span class="sw" style="background:#0057ff"></span>{label_a}</div>
<div><span class="sw" style="background:#ff5a1f"></span>{label_b}</div>
</div>
<div class="note">口径=T+N 相对沪深300超额；进场=报告日次日开盘；超额=个股收益−沪深300同窗收益（剥大盘 beta）。
均最高=区间最高收益均值；均回撤=峰值后回撤均值。仅统计窗口完整的票。Δ&gt;0 表示你领先机器。</div>
</aside>
<main class="content" id="main">
<section class="hero"><div class="kicker">HUMAN VS MACHINE · STOCK PICKING</div>
<h1>人机对照台账</h1>
<p>把你的实选与机器(strategy-evolve)生成名单放在同一套 T+N 相对沪深300超额口径下并排打分，
量化「机器到底比你强/弱多少」。这是「逐步迭代进化做得比你更好」的指北针——先量化差距，再谈进化。</p></section>
<div class="kpis">{kpi_html}</div>
<h2>胜率 / 累计超额对照</h2>
<div class="panel"><b>超额胜率分窗口对照（{label_a} vs {label_b}）</b>{bar}</div>
<div class="panel"><b>累计超额曲线 T+{main_w}（逐日均超额累加）</b>{line}</div>
<h2>分窗口指标对照</h2>
<div class="panel"><table>
<thead><tr><th>窗口</th><th>指标</th><th>{label_a}</th><th>{label_b}</th><th>Δ (你−机)</th></tr></thead>
<tbody>{table_html}</tbody></table></div>
<div class="foot">生成于 {stamp} · 行情源 腾讯/新浪公开接口 · 口径同 opinion-cross 胜率榜 · 自包含静态页</div>
</main></div></body></html>"""


# ---------- main ----------
def main() -> int:
    ap = argparse.ArgumentParser(description="人机对照台账：你的实选 vs 机器生成名单（同口径 T+N 超额）")
    ap.add_argument("--mine", help="你的实选 picks 文件（JSON 对象或 JSONL）")
    ap.add_argument("--mine-selections",
                    help="改从 复盘/selections 读你的真实选股（.md 文件或目录；日期取自文件名）")
    ap.add_argument("--include-observation", action="store_true",
                    help="--mine-selections 时把「观察组」也计入你的名单（默认只算梯队选股）")
    ap.add_argument("--machine", help="机器名单 picks 文件")
    ap.add_argument("--machine-records", help="改从 strategy-evolve 的 evolution/records 目录读机器名单")
    ap.add_argument("--strategy", type=int, default=1, choices=[1, 3, 4], help="--machine-records 时用哪个策略")
    ap.add_argument("--scope", default=None, help="--machine-records 时的口径（默认各策略默认 scope）")
    ap.add_argument("--label-mine", default="我")
    ap.add_argument("--label-machine", default=None)
    ap.add_argument("--main-window", type=int, default=5, choices=list(WINDOWS))
    ap.add_argument("--json", dest="json_out", default=None)
    ap.add_argument("--out", default=None, help="输出 paper 主题 HTML 路径")
    args = ap.parse_args()

    if args.mine_selections:
        mine = load_selections(Path(args.mine_selections).expanduser(), args.include_observation)
    elif args.mine:
        mine = load_picks(Path(args.mine).expanduser())
    else:
        print("[ERR] 需要 --mine 或 --mine-selections 之一")
        return 1
    default_scope = {1: "T1CORE6", 3: "S3_ALL", 4: "S4_ALL"}
    if args.machine_records:
        scope = args.scope or default_scope[args.strategy]
        machine = load_machine_records(Path(args.machine_records).expanduser(), args.strategy, scope)
        label_b = args.label_machine or f"机器(策略{args.strategy}·{scope})"
    elif args.machine:
        machine = load_picks(Path(args.machine).expanduser())
        label_b = args.label_machine or "机器"
    else:
        print("[ERR] 需要 --machine 或 --machine-records 之一")
        return 1

    if not mine:
        print(f"[ERR] 你的名单为空：{args.mine_selections or args.mine}")
        return 1

    # 行情区间：覆盖两边全部日期
    all_dates = sorted(set(mine) | set(machine))
    if not all_dates:
        print("[ERR] 两边名单都为空")
        return 1
    idx_start = all_dates[0]
    idx_end = (dt.date.fromisoformat(all_dates[-1]) + dt.timedelta(days=CAL_BUFFER)).isoformat()
    print(f"[..] 抓沪深300基准 {idx_start} ~ {idx_end}")
    idx_klines = price_lib.index_daily(BENCH, idx_start, idx_end)

    code_cache: dict = {}
    print(f"[..] 打分 {args.label_mine} ...")
    rows_a = score_side(mine, code_cache, idx_klines)
    print(f"[..] 打分 {label_b} ...")
    rows_b = score_side(machine, code_cache, idx_klines)

    agg_a = aggregate(rows_a)
    agg_b = aggregate(rows_b)

    print_console(args.label_mine, agg_a, label_b, agg_b, args.main_window)

    stamp = dt.date.today().isoformat()
    if args.json_out:
        payload = {
            "stamp": stamp, "main_window": args.main_window,
            "sides": {
                args.label_mine: {"agg": agg_a, "rows": rows_a},
                label_b: {"agg": agg_b, "rows": rows_b},
            },
        }
        Path(args.json_out).expanduser().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] JSON -> {args.json_out}")

    if args.out:
        html = build_html(args.label_mine, agg_a, label_b, agg_b, stamp, args.main_window)
        outp = Path(args.out).expanduser()
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(html, encoding="utf-8")
        print(f"[OK] HTML -> {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
