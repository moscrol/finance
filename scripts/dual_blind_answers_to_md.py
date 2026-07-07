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
AUTO_MARK = "<!-- auto-generated from answer JSON -->"
AGENTS = ("codex", "claude")


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


def market_section(answers: dict[str, dict]) -> list[str]:
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
            lines += [f"{i}. {x}" for i, x in enumerate(dr, 1)]
            lines.append("")
        th = ans.get("thresholds")
        if isinstance(th, dict) and th:
            lines.append(f"### {agent} 验证阈值")
            lines.append("")
            names = {"market": "市场", "direction": "方向", "targets": "标的", "falsify": "证伪"}
            lines += _table(
                [[names.get(k, k), v] for k, v in th.items()], ["维度", "条件"])
            lines.append("")
    return lines


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
                rows.append([agent, h.get("id", ""), h.get("claim", ""),
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
        has = True
        lines.append(f"### {agent}")
        lines.append("")
        for label, key in (("T+1", "pick_returns_t1"), ("T+3", "pick_returns_t3")):
            rows = rec.get(key)
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                ks = list(rows[0].keys())
                lines.append(f"{label} 标的回报：")
                lines.append("")
                lines += _table([[r.get(k, "") for k in ks] for r in rows], ks)
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


def build_md(date: str, answers: dict[str, dict]) -> str:
    persp = None
    for ans in answers.values():
        persp = (ans.get("perspective_date")
                 or (ans.get("date_policy") or {}).get("perspective_trade_date"))
        if persp:
            break
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
    for sec in (market_section, judgment_section, direction_section,
                picks_section, hypotheses_section, recheck_section):
        lines += sec(answers)
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
    for date in dates:
        md_path = LEDGER / f"{date}.md"
        if md_path.exists() and AUTO_MARK not in md_path.read_text(encoding="utf-8")[:200]:
            print(f"skip {date}（已有人工台账）")
            continue
        answers = load_answers(date)
        if not answers:
            print(f"skip {date}（无答卷 JSON）")
            continue
        md_path.write_text(build_md(date, answers), encoding="utf-8")
        print(f"write {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
