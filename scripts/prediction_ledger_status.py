#!/usr/bin/env python3
"""预测台账周报：证实 / 证伪 / 待定 / 过期，以及「台账多久没新增」。只读，不改台账。

为什么要有它（2026-10-01 质检 P0④）：台账最后一个编号停在 R-20260916-03，表头
last_updated 停在 08-29；Open 表里 100 条 pending 从没有到期规则，于是「证伪满 3
条就升级」几乎不会触发——判错的修补被记成「还没测」，命中率永远攒不出来。

判读口径：
- 以 ``### Open（pending）`` 表为当前态（台账规则：分诊开工先读 Open 表）。
- outcome 单元格按首个状态词归类：confirmed / partially_confirmed / refuted / pending；
  其余（自由文本、未达标）归 other，原样计数，不猜。
- 过期 = pending 且编号日期距今超过 ``--expire-days``（默认 14 天）。过期不是证伪，
  只是「该回填了」；本脚本不替人改状态。
- 证伪连击：按编号顺序，同一 fix_type 的已决条目里末尾连续 refuted 的条数（≥3 即
  触发台账规则里的升格）。

退出码：0 正常；1 带 ``--max-silence-days`` 且最新编号已超过该天数（可接 SessionStart / CI 提醒）。
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime
import json
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[1]
LEDGER = REPO / "docs" / "prediction-ledger.md"
_ID = re.compile(r"`?(R-(\d{8})-\d+[a-z]?)`?")
_STATES = ("partially_confirmed", "confirmed", "refuted", "pending")
# 台账规则里的冻结枚举；单元格常带「（候…）」之类注释，只取枚举值本身。
_FIX_TYPE = re.compile(
    r"SYSTEM_PROMPT_FIX|TOOL_DESCRIPTION_FIX|ROUTING_FIX|DATA_CONTRACT_FIX|HARNESS_FIX|EVAL_ONLY|NO_SYSTEM_FIX"
)


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def open_rows(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.startswith("### Open"))
    except StopIteration as exc:
        raise SystemExit("台账里找不到 ### Open 段") from exc
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for line in lines[start + 1:]:
        if line.startswith("### "):
            break
        if not line.startswith("|"):
            continue
        cells = _cells(line)
        if header is None:
            header = cells
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def classify(outcome: str) -> str:
    lowered = outcome.lower()
    hits = [(lowered.find(state), state) for state in _STATES if state in lowered]
    if not hits:
        return "other"
    return min(hits)[1]


def summarize(text: str, today: date, expire_days: int) -> dict[str, object]:
    counts: Counter[str] = Counter()
    by_fix: dict[str, Counter[str]] = defaultdict(Counter)
    decided: dict[str, list[str]] = defaultdict(list)
    expired: list[str] = []
    latest: date | None = None
    for row in open_rows(text):
        match = _ID.search(row.get("ID", ""))
        if not match:
            continue
        ident, day = match.group(1), datetime.strptime(match.group(2), "%Y%m%d").date()
        latest = max(latest, day) if latest else day
        state = classify(row.get("outcome", ""))
        fix_match = _FIX_TYPE.search(row.get("fix_type", ""))
        fix = fix_match.group(0) if fix_match else "?"
        if state == "pending" and (today - day).days > expire_days:
            state = "expired"
            expired.append(ident)
        counts[state] += 1
        by_fix[fix][state] += 1
        if state in {"confirmed", "partially_confirmed", "refuted"}:
            decided[fix].append(state)
    streaks = {}
    for fix, states in decided.items():
        run = 0
        for state in reversed(states):
            if state != "refuted":
                break
            run += 1
        streaks[fix] = run
    return {
        "today": today.isoformat(),
        "expire_days": expire_days,
        "total": sum(counts.values()),
        "counts": dict(counts),
        "by_fix_type": {fix: dict(c) for fix, c in sorted(by_fix.items())},
        "refuted_streak_by_fix_type": {k: v for k, v in sorted(streaks.items()) if v},
        "escalation_triggered": sorted(k for k, v in streaks.items() if v >= 3),
        "latest_id_date": latest.isoformat() if latest else None,
        "days_since_latest_id": (today - latest).days if latest else None,
        "expired_ids": expired,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    parser.add_argument("--expire-days", type=int, default=14)
    parser.add_argument("--max-silence-days", type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = summarize(args.ledger.read_text(encoding="utf-8"), args.today, args.expire_days)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        c = report["counts"]
        print(f"台账 {report['total']} 条（截至 {report['today']}，pending 超过 {args.expire_days} 天记为过期）")
        print("  证实 {} / 部分证实 {} / 证伪 {} / 待定 {} / 过期 {} / 其他 {}".format(
            c.get("confirmed", 0), c.get("partially_confirmed", 0), c.get("refuted", 0),
            c.get("pending", 0), c.get("expired", 0), c.get("other", 0)))
        print(f"  最新编号日期 {report['latest_id_date']}，已 {report['days_since_latest_id']} 天没有新预测")
        for fix, states in report["by_fix_type"].items():
            print(f"  {fix:<22} " + "  ".join(f"{k}={v}" for k, v in sorted(states.items())))
        if report["escalation_triggered"]:
            print(f"  ⚠ 证伪连击 ≥3，按台账规则升格：{report['escalation_triggered']}")
    silence = report["days_since_latest_id"]
    if args.max_silence_days is not None and silence is not None and silence > args.max_silence_days:
        print(f"[prediction_ledger_status] 台账已 {silence} 天没有新预测（上限 {args.max_silence_days}）",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
