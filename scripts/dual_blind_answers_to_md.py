#!/usr/bin/env python3
"""答卷 JSON → 人读版台账 md：无人工台账的日期自动生成 YYYY-MM-DD.md。

数据来自 ``docs/learning/forecast-review-ledger/YYYY-MM-DD.answer.<agent>.json``。
已存在人工撰写的 ``YYYY-MM-DD.md`` 时跳过（不覆盖）；自动生成的文件带
``<!-- auto-generated from answer JSON -->`` 标记，重复运行会刷新这些文件。

Usage:
    python3 scripts/dual_blind_answers_to_md.py [YYYY-MM-DD ...]
    （不带参数时补齐台账目录里所有缺 md 的日期）
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "learning" / "forecast-review-ledger"
DB_PATH = ROOT / "db" / "market_feature_store.duckdb"
AUTO_MARK = "<!-- auto-generated from answer JSON -->"
AGENTS = ("codex", "claude")


def _connect_db():
    try:
        import duckdb
        return duckdb.connect(str(DB_PATH), read_only=True)
    except Exception:
        return None


def _fetch_row(con, sql: str, params: list) -> dict | None:
    try:
        cur = con.execute(sql, params)
        row = cur.fetchone()
        if row is None:
            return None
        return dict(zip([d[0] for d in cur.description], row))
    except Exception:
        return None


def _fetch_all(con, sql: str, params: list) -> list[dict]:
    try:
        cur = con.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        return []


def _fmt(v, pct: bool = False) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.2f}%" if pct else f"{v:.2f}"
    return f"{v}%" if pct else str(v)


def _market_row(con, date: str) -> dict | None:
    return _fetch_row(
        con, "select * from fact_market_daily where trade_date = ?", [date])


def _prev_trade_date(con, date: str) -> str | None:
    row = _fetch_row(
        con,
        "select max(trade_date) d from fact_market_daily where trade_date < ?",
        [date])
    return str(row["d"]) if row and row.get("d") else None


MARKET_FIELDS: list[tuple[str, object]] = [
    ("市场阶段", lambda r: f"{r.get('market_stage') or '-'}第 {r.get('stage_day') or '-'} 天"),
    ("成交额(亿)", "total_amount"),
    ("较前一日", lambda r: _fmt(r.get("amount_vs_yesterday_pct"), pct=True)),
    ("量比", "volume_ratio"),
    ("量能状态", "volume_state"),
    ("涨家数", "advancers"),
    ("涨停", "limit_up"),
    ("跌停", "limit_down"),
    ("上证涨跌幅", lambda r: _fmt(r.get("sh_index_pct_chg"), pct=True)),
    ("第一大成交行业", lambda r: (
        f"{r.get('industry_1')}（{_fmt(r.get('industry_1_ratio'), pct=True)}）"
        if r.get("industry_1") else "-")),
    ("前三行业占比", lambda r: _fmt(r.get("top3_industry_ratio"), pct=True)),
    ("集中度", "concentration_state"),
    ("历史新高数", "stock_high_count_history"),
    ("120 日新高数", "stock_high_count_120d"),
    ("20 日新高数", "stock_high_count_20d"),
]


def _market_field(row: dict, spec) -> str:
    if callable(spec):
        try:
            return spec(row)
        except Exception:
            return "-"
    return _fmt(row.get(spec))


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


def _table(rows: list[list[str]], header: list[str]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for r in rows:
        lines.append("| " + " | ".join(str(x).replace("\n", " ") for x in r) + " |")
    return lines


def market_section(answers: dict[str, dict], con=None, persp: str | None = None) -> list[str]:
    if con is not None and persp:
        cur = _market_row(con, persp)
        if cur:
            prev_date = _prev_trade_date(con, persp)
            prev = _market_row(con, prev_date) if prev_date else None
            lines = ["## 1. 当时市场底稿", "",
                     "### 1.1 大盘与广度", ""]
            if prev:
                rows = [[label, _market_field(prev, spec), _market_field(cur, spec)]
                        for label, spec in MARKET_FIELDS]
                lines += _table(rows, ["字段", str(prev_date), str(persp)])
            else:
                rows = [[label, _market_field(cur, spec)]
                        for label, spec in MARKET_FIELDS]
                lines += _table(rows, ["字段", str(persp)])
            lines.append("")
            sw = _fetch_all(con, (
                "select sw_l1, pct_chg, amount from fact_sw_l1_daily "
                "where trade_date = ? order by amount desc limit 9"), [persp])
            if sw:
                lines += ["### 1.2 行业成交结构（申万一级，成交前 9）", ""]
                lines += _table(
                    [[r["sw_l1"], _fmt(r["pct_chg"], pct=True),
                      _fmt(r["amount"] / 100 if isinstance(r["amount"], (int, float)) else r["amount"])]
                     for r in sw], ["行业", "涨跌幅", "成交(亿)"])
                lines.append("")
            dbl = _fetch_all(con, (
                "select sector_name, pct_chg, diff_ratio, amount "
                "from fact_sector_daily where trade_date = ? "
                "and pct_chg > 0 and diff_ratio > 0 "
                "order by diff_ratio desc limit 10"), [persp])
            if dbl:
                lines += ["### 1.3 双红板块（涨幅>0 且 diff_ratio>0，按 diff 前 10）", ""]
                lines += _table(
                    [[r["sector_name"], _fmt(r["pct_chg"], pct=True),
                      _fmt(r["diff_ratio"]), _fmt(r["amount"])] for r in dbl],
                    ["板块", "涨跌幅", "diff_ratio", "成交(亿)"])
                lines.append("")
            return lines
    ans = answers.get("codex") or {}
    dfq = ans.get("daily_four_questions") or {}
    cv = (dfq.get("duckdb_flow") or {}).get("core_values")
    if not isinstance(cv, dict):
        return []
    lines = ["## 1. 当时市场底稿", ""]
    lines += _table([[k, v] for k, v in cv.items()], ["字段", "数值"])
    lines.append("")
    return lines


def judgment_section(answers: dict[str, dict]) -> list[str]:
    lines = ["## 2. 核心判断", ""]
    for agent, ans in answers.items():
        lines.append(f"### {agent}")
        lines.append("")
        if ans.get("stage"):
            lines.append(f"- 阶段：{ans['stage']}")
        if ans.get("main_judgment"):
            lines.append(f"- 判断：{ans['main_judgment']}")
        lines.append("")
    return lines


def direction_section(answers: dict[str, dict]) -> list[str]:
    lines = ["## 3. 方向排序与验证条件", ""]
    for agent, ans in answers.items():
        dr = ans.get("direction_ranking")
        if isinstance(dr, list) and dr:
            lines.append(f"### {agent} 方向排序")
            lines.append("")
            for i, x in enumerate(dr, 1):
                if isinstance(x, dict):
                    sector = x.get("sector") or x.get("direction") or ""
                    rationale = x.get("rationale") or x.get("reason") or ""
                    lines.append(f"{i}. {sector}" + (f"：{rationale}" if rationale else ""))
                else:
                    lines.append(f"{i}. {x}")
            lines.append("")
        th = ans.get("thresholds")
        if isinstance(th, dict) and th:
            lines.append(f"### {agent} 验证阈值")
            lines.append("")
            names = {"market": "市场", "direction": "方向", "targets": "标的", "falsify": "证伪"}
            lines += _table(
                [[names.get(k, k), _threshold_text(v)] for k, v in th.items()],
                ["维度", "条件"])
            lines.append("")
    return lines


def _threshold_text(v) -> str:
    if isinstance(v, dict):
        return "；".join(f"{k}={_threshold_text(x)}" for k, x in v.items())
    if isinstance(v, list):
        return "；".join(_threshold_text(x) for x in v)
    return str(v)


def picks_section(answers: dict[str, dict]) -> list[str]:
    lines = ["## 4. 观察标的", "",
             "> 方向观察样本，不是买卖建议。", ""]
    for agent, ans in answers.items():
        picks = ans.get("picks")
        if not (isinstance(picks, list) and picks and isinstance(picks[0], dict)):
            continue
        lines.append(f"### {agent} 观察标的")
        lines.append("")
        keys = list(picks[0].keys())
        lines += _table([[p.get(k, "") for k in keys] for p in picks], keys)
        lines.append("")
    return lines


def hypotheses_section(answers: dict[str, dict]) -> list[str]:
    rows = []
    for agent, ans in answers.items():
        for h in ans.get("hypotheses") or []:
            if isinstance(h, dict):
                rows.append([agent, h.get("id", ""),
                             h.get("claim") or h.get("text") or "",
                             h.get("metric", ""), h.get("falsify_when", "")])
    if not rows:
        return []
    lines = ["## 5. 待验证假设", ""]
    lines += _table(rows, ["agent", "id", "claim", "metric", "证伪条件"])
    lines.append("")
    return lines


def recheck_section(answers: dict[str, dict]) -> list[str]:
    lines = ["## 6. T+1/T+3 回检", ""]
    has = False
    for agent, ans in answers.items():
        rec = ans.get("recheck")
        if not isinstance(rec, dict):
            continue
        if rec.get("benchmark") is None and not any(
                rec.get(k) for k in ("pick_returns_t1", "pick_returns_t3")):
            continue
        has = True
        lines.append(f"### {agent}")
        lines.append("")
        picks = ans.get("picks") or []
        for label, key in (("T+1", "pick_returns_t1"), ("T+3", "pick_returns_t3")):
            rows = rec.get(key)
            if not (isinstance(rows, list) and rows):
                continue
            lines.append(f"{label} 标的回报：")
            lines.append("")
            if isinstance(rows[0], dict):
                ks = list(rows[0].keys())
                lines += _table([[r.get(k, "") for k in ks] for r in rows], ks)
            else:
                trows = []
                for i, r in enumerate(rows):
                    pick = picks[i] if i < len(picks) and isinstance(picks[i], dict) else {}
                    trows.append([pick.get("code", ""), pick.get("name", ""), r])
                lines += _table(trows, ["code", "name", "回报%"])
            lines.append("")
        info = [f"基准 {rec.get('benchmark')}"]
        if rec.get("recheck_t1_date"):
            info.append(f"T+1 回检日 {rec['recheck_t1_date']}")
        if rec.get("benchmark_return_t3") is not None:
            info.append(f"基准 T+3 回报 {rec['benchmark_return_t3']}")
        if rec.get("recheck_generated_at"):
            info.append(f"回检生成于 {rec['recheck_generated_at']}")
        lines.append("- " + "；".join(info))
        lines.append("")
    return lines if has else []


def _ranked_sectors(answers: dict[str, dict]) -> list[str]:
    seen: list[str] = []
    for ans in answers.values():
        for x in ans.get("direction_ranking") or []:
            if isinstance(x, dict):
                names = [x.get("sector") or x.get("direction") or ""]
            else:
                head = re.split(r"[：:，,（(]", str(x))[0]
                names = head.split("/")
            for n in names:
                n = n.strip()
                if n and n not in seen:
                    seen.append(n)
    return seen


def _pick_ts_code(pick: dict) -> str | None:
    for k in ("ts_code", "stock_ts_code", "code"):
        v = pick.get(k)
        if isinstance(v, str) and "." in v:
            return v.upper()
    code = str(pick.get("code") or "")
    if re.fullmatch(r"\d{6}", code):
        if code.startswith(("6", "9")):
            return f"{code}.SH"
        if code.startswith(("4", "8")):
            return f"{code}.BJ"
        return f"{code}.SZ"
    return None


def verification_section(date: str, answers: dict[str, dict], con) -> list[str]:
    if con is None:
        return []
    actual = _market_row(con, date)
    if not actual:
        return []
    lines = [f"## 7. {date} 收盘后验证", "",
             "> 以下实际值由主库自动回填，命中/证伪结论以 verdict 与人工批注为准。", "",
             "### 7.1 市场路径实际结果", ""]
    rows = [[label, _market_field(actual, spec)] for label, spec in MARKET_FIELDS]
    lines += _table(rows, ["字段", f"{date} 实际值"])
    lines.append("")
    sectors = _ranked_sectors(answers)
    if sectors:
        srows = []
        for name in sectors:
            r = _fetch_row(con, (
                "select sector_name, pct_chg, diff_ratio from fact_sector_daily "
                "where trade_date = ? and sector_name = ?"), [date, name])
            if not r:
                continue
            heat = _fetch_row(con, (
                "select limit_up_count from fact_theme_limit_heat_daily "
                "where trade_date = ? and sector_name like '%' || ? || '%' "
                "order by limit_up_count desc limit 1"),
                [date, name.removesuffix("概念")])
            dbl = (r.get("pct_chg") or 0) > 0 and (r.get("diff_ratio") or 0) > 0
            srows.append([name, _fmt(r["pct_chg"], pct=True), _fmt(r["diff_ratio"]),
                          _fmt((heat or {}).get("limit_up_count", 0) or 0),
                          "✅" if dbl else "✖"])
        if srows:
            lines += ["### 7.2 方向路径实际结果（取两份答卷方向排序并集）", ""]
            lines += _table(srows, ["方向", "涨跌幅", "diff_ratio", "涨停数", "双红"])
            lines.append("")
    bench = actual.get("sh_index_pct_chg")
    prow_lines = []
    for agent, ans in answers.items():
        picks = ans.get("picks") or []
        prows = []
        for p in picks:
            if not isinstance(p, dict):
                continue
            ts = _pick_ts_code(p)
            if not ts:
                continue
            r = _fetch_row(con, (
                "select stock_name, pct_chg, amount from fact_stock_daily "
                "where trade_date = ? and stock_ts_code = ?"), [date, ts])
            if not r:
                continue
            verdict = "-"
            if isinstance(bench, (int, float)) and isinstance(r.get("pct_chg"), (int, float)):
                verdict = "跑赢上证" if r["pct_chg"] > bench else "跑输上证"
            prows.append([r.get("stock_name") or p.get("name", ""), ts,
                          _fmt(r["pct_chg"], pct=True), _fmt(r["amount"]), verdict])
        if prows:
            prow_lines.append(f"#### {agent} 标的")
            prow_lines.append("")
            prow_lines += _table(prows, ["标的", "代码", "涨跌幅", "成交", "vs 上证"])
            prow_lines.append("")
    if prow_lines:
        lines += ["### 7.3 代表标的观察结果", ""] + prow_lines
    return lines


def annotation_section() -> list[str]:
    lines = ["## 8. 用户批注区", ""]
    for i in (1, 2, 3):
        lines += [f"### 批注 {i}", "",
                  "- 问题：", "- 应该改成：", "- 下次硬规则：", ""]
    return lines


def build_md(date: str, answers: dict[str, dict], con=None) -> str:
    persp = None
    for ans in answers.values():
        persp = (ans.get("perspective_date")
                 or (ans.get("date_policy") or {}).get("perspective_trade_date"))
        if persp:
            break
    if not persp and con is not None:
        persp = _prev_trade_date(con, date)
    sha = next((a.get("manifest_sha") for a in answers.values()
                if a.get("manifest_sha")), "")
    lines = [
        AUTO_MARK,
        f"# {date} 复盘推演验证台账",
        "",
        f"> 观察视角：站在 {persp or '前一交易日'} 盘后，前瞻 {date} 行情。",
        f"> 本页由双盲答卷 JSON 自动生成（{' / '.join(answers)}），"
        f"manifest `{sha}`。",
        "> 说明：本页不是投资建议，是“可证伪推演 + 次日回检表”。",
        "",
    ]
    lines += market_section(answers, con=con, persp=persp)
    for sec in (judgment_section, direction_section,
                picks_section, hypotheses_section, recheck_section):
        lines += sec(answers)
    lines += verification_section(date, answers, con)
    lines += annotation_section()
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str]) -> int:
    if argv:
        dates = argv
    else:
        dates = sorted({
            m.group(1)
            for f in LEDGER.iterdir()
            if (m := re.match(r"^(\d{4}-\d{2}-\d{2})\.answer\.", f.name))
        })
    con = _connect_db()
    for date in dates:
        md_path = LEDGER / f"{date}.md"
        if md_path.exists() and AUTO_MARK not in md_path.read_text(encoding="utf-8")[:200]:
            print(f"skip {date}（已有人工台账）")
            continue
        answers = load_answers(date)
        if not answers:
            print(f"skip {date}（无答卷 JSON）")
            continue
        md_path.write_text(build_md(date, answers, con=con), encoding="utf-8")
        print(f"write {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
