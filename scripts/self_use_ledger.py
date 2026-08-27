#!/usr/bin/env python3
"""自用摩擦台账 CLI：``add`` 追加一条使用记录、``summary`` 出 Gate 读数。

失败形状
--------
Self-use Maturity Gate（`docs/superpowers/specs/2026-07-11-workbench-self-use-to-invite-beta-design.md`
§3.1）要求「连续 10 个交易日自用 + 每日记录摩擦/失败/降级/救场 + 成功率 ≥95%」。
2026-08-26 盘点：生产 runs 里大头是 agent 探针与评测批跑，没有一份人的使用记录，
Gate 三项判据没有任何一项能算——不是产品不行，是没人记账。
本脚本是该台账的唯一写入者（schema 校验在写入口），人工修改也走这里。

用法
----
    python3 scripts/self_use_ledger.py add --task-type stock \
        --question "长电科技怎么看" --outcome ok --run-id run_2026... \
        --friction "首答缺现金流科目" --minutes-saved 15
    python3 scripts/self_use_ledger.py summary            # 全量
    python3 scripts/self_use_ledger.py summary --days 10  # 最近 10 个有记录日
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LEDGER_DIR = REPO_ROOT / "docs" / "learning" / "self-use-ledger"

TASK_TYPES = ("market", "theme", "stock", "news", "watchlist", "other")
OUTCOMES = ("ok", "degraded", "failed", "rescued")
# ok       = 一次性拿到可用结果
# degraded = 有降级/缺口但显式披露，结果仍可用
# failed   = 没拿到可用结果（含静默错误）
# rescued  = 需要人工救场（改文件/拼命令/重启）才拿到结果 —— Gate §3.1.5 单列
_CORE_TASK_TYPES = ("market", "theme", "stock", "news", "watchlist")


def _today() -> str:
    return dt.date.today().isoformat()


def _validate_date(text: str) -> str:
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise SystemExit(f"❌ date 必须是 YYYY-MM-DD：{text!r}（{exc}）")


def cmd_add(args: argparse.Namespace) -> int:
    date = _validate_date(args.date or _today())
    question = (args.question or "").strip()
    if not question:
        raise SystemExit("❌ --question 不能为空")
    if args.task_type not in TASK_TYPES:
        raise SystemExit(f"❌ --task-type 必须是 {TASK_TYPES}")
    if args.outcome not in OUTCOMES:
        raise SystemExit(f"❌ --outcome 必须是 {OUTCOMES}")
    if args.outcome in {"failed", "rescued"} and not (args.friction or "").strip():
        raise SystemExit("❌ failed/rescued 必须写 --friction（Gate 要记的正是这个）")

    entry = {
        "ts": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "date": date,
        "task_type": args.task_type,
        "question": question,
        "run_id": (args.run_id or "").strip() or None,
        "outcome": args.outcome,
        "friction": (args.friction or "").strip() or None,
        "minutes_saved": args.minutes_saved,
    }
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    path = LEDGER_DIR / f"{date}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"✅ 已记 {path.relative_to(REPO_ROOT)}：{args.task_type}/{args.outcome} {question[:40]}")
    return 0


def _load_entries() -> dict[str, list[dict]]:
    by_date: dict[str, list[dict]] = {}
    if not LEDGER_DIR.is_dir():
        return by_date
    for path in sorted(LEDGER_DIR.glob("*.jsonl")):
        entries = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"❌ {path.name}:{line_no} 不是合法 JSON：{exc}")
        if entries:
            by_date[path.stem] = entries
    return by_date


def cmd_summary(args: argparse.Namespace) -> int:
    by_date = _load_entries()
    if not by_date:
        print("台账为空。先用 add 记第一条。")
        return 0
    dates = sorted(by_date)
    if args.days:
        dates = dates[-args.days :]

    total = ok = degraded = failed = rescued = 0
    types_seen: set[str] = set()
    problem_lines: list[str] = []
    print(f"{'日期':<12}{'条数':>4}{'ok':>4}{'降级':>4}{'失败':>4}{'救场':>4}  当日任务类型")
    for date in dates:
        entries = by_date[date]
        counts = {o: sum(1 for e in entries if e.get("outcome") == o) for o in OUTCOMES}
        day_types = sorted({e.get("task_type", "?") for e in entries})
        types_seen.update(day_types)
        total += len(entries)
        ok += counts["ok"]
        degraded += counts["degraded"]
        failed += counts["failed"]
        rescued += counts["rescued"]
        print(
            f"{date:<12}{len(entries):>4}{counts['ok']:>4}{counts['degraded']:>4}"
            f"{counts['failed']:>4}{counts['rescued']:>4}  {','.join(day_types)}"
        )
        for e in entries:
            if e.get("outcome") in {"failed", "rescued"}:
                problem_lines.append(
                    f"  {date} [{e.get('task_type')}] {e.get('question','')[:50]}"
                    f" —— {e.get('friction') or '(未写摩擦)'}"
                )

    usable = ok + degraded
    print("-" * 60)
    print(f"记录日 {len(dates)} 天，共 {total} 条")
    print(f"成功率（ok）          {ok}/{total} = {ok / total:.1%}")
    print(f"可用率（ok+降级披露） {usable}/{total} = {usable / total:.1%}   ← Gate §3.1.4 口径")
    print(f"人工救场              {rescued} 条                     ← Gate §3.1.5 要求为 0 常态")
    missing = [t for t in _CORE_TASK_TYPES if t not in types_seen]
    print(f"五类任务覆盖          {sorted(types_seen & set(_CORE_TASK_TYPES))}"
          + (f"，缺 {missing}" if missing else "，齐 ← Gate §3.1.2"))
    if problem_lines:
        print("失败/救场明细：")
        for line in problem_lines:
            print(line)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="追加一条使用记录")
    p_add.add_argument("--date", help="YYYY-MM-DD，默认今天")
    p_add.add_argument("--task-type", required=True, choices=TASK_TYPES)
    p_add.add_argument("--question", required=True)
    p_add.add_argument("--run-id")
    p_add.add_argument("--outcome", required=True, choices=OUTCOMES)
    p_add.add_argument("--friction", help="摩擦点/失败原因；failed/rescued 必填")
    p_add.add_argument("--minutes-saved", type=int, help="主观估计节省分钟数，可为负")
    p_add.set_defaults(func=cmd_add)

    p_sum = sub.add_parser("summary", help="按日聚合出 Gate 读数")
    p_sum.add_argument("--days", type=int, help="只看最近 N 个有记录日")
    p_sum.set_defaults(func=cmd_summary)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
