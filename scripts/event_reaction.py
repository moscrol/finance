#!/usr/bin/env python3
"""event_reaction —— 事件定价第一刀 CLI（事件锚点日历 / 锚点标签 / 事件反应 / 读数 / latest_known）。

    python scripts/event_reaction.py build-calendar --kb-wiki ~/knowledge-base-private/wiki   # fact_event_daily + 官方日程 + 卖方观点事件文件 → history_event_calendar
    python scripts/event_reaction.py build-anchors           # → history_event_anchors（market / sector 两层）
    python scripts/event_reaction.py build-reaction          # → history_event_reaction + 横截面（需先 build-labels / outcomes）
    python scripts/event_reaction.py report                  # 四态读数 + 收据（methodology/receipts/event_pricing/）
    python scripts/event_reaction.py latest-known --indicator cn_cpi --as-of 2026-07-08
    python scripts/event_reaction.py all                     # 三步构建 + 收据

设计稿：docs/superpowers/specs/2026-09-07-event-pricing-slice1-calendar-reaction-design.md
前置：旁路库须已有 methodology_backtest 的 build-labels 与 outcomes（3/5/10 日）。
路径：主库默认 ``MARKET_FEATURE_STORE_DB`` 或 ``db/market_feature_store.duckdb``（只读 ATTACH）；
旁路库默认与主库同目录 ``history_labels.duckdb``；参数默认 ``methodology/events/event_reaction_params.v0.1.json``。
解释器一律 ``.venv-workbench/bin/python``。

退出码：0 成功；2 输入 / 数据不可用；3 主库被写锁占用。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date as date_cls
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.services.event_pricing.anchors import build_anchors  # noqa: E402
from intelligence.services.event_pricing.event_calendar import build_calendar, latest_known  # noqa: E402
from intelligence.services.event_pricing.params import DEFAULT_PARAMS_PATH, load_params  # noqa: E402
from intelligence.services.event_pricing.reaction import build_reaction  # noqa: E402
from intelligence.services.event_pricing.readouts import build_receipt, render_markdown, write_receipt  # noqa: E402
from intelligence.services.methodology_backtest.store import default_labels_db_path, open_labels_db  # noqa: E402
from market_feature_store.db import DB_PATH as CANONICAL_DB_PATH  # noqa: E402
from market_feature_store.db import DatabaseLockedError  # noqa: E402

RECEIPTS_DIR = ROOT / "methodology" / "receipts"
EXIT_INPUT = 2
EXIT_LOCKED = 3


def _print(report) -> None:
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


def _params(args):
    return load_params(args.params, schedule_dir=args.schedule_dir)


def cmd_build_calendar(args) -> int:
    _print(build_calendar(args.db_path, args.labels_db, params=_params(args), kb_wiki=args.kb_wiki))
    return 0


def cmd_build_anchors(args) -> int:
    _print(build_anchors(args.db_path, args.labels_db, params=_params(args)))
    return 0


def cmd_build_reaction(args) -> int:
    _print(build_reaction(args.db_path, args.labels_db, params=_params(args)))
    return 0


def cmd_report(args) -> int:
    receipt = build_receipt(args.db_path, args.labels_db, params=_params(args))
    if args.json:
        print(json.dumps(receipt, ensure_ascii=False, indent=2, default=str))
    else:
        print(render_markdown(receipt), end="")
    if not args.no_write:
        jp, mp = write_receipt(args.receipts_dir, receipt, date_str=date_cls.today().isoformat())
        print(f"→ {jp}\n→ {mp}")
    return 0


def cmd_latest_known(args) -> int:
    labels_db = Path(args.labels_db).expanduser()
    con = open_labels_db(labels_db, read_only=True)
    try:
        out = latest_known(con, args.indicator, args.as_of)
    finally:
        con.close()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_all(args) -> int:
    params = _params(args)
    _print(build_calendar(args.db_path, args.labels_db, params=params, kb_wiki=args.kb_wiki))
    _print(build_anchors(args.db_path, args.labels_db, params=params))
    _print(build_reaction(args.db_path, args.labels_db, params=params))
    receipt = build_receipt(args.db_path, args.labels_db, params=params)
    print(render_markdown(receipt), end="")
    if not args.no_write:
        jp, mp = write_receipt(args.receipts_dir, receipt, date_str=date_cls.today().isoformat())
        print(f"→ {jp}\n→ {mp}")
    return 0


def _date_arg(value: str) -> str:
    try:
        return date_cls.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期必须是 YYYY-MM-DD") from exc


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db-path", default=str(CANONICAL_DB_PATH), help="主库路径（只读 ATTACH）")
    p.add_argument("--labels-db", default=None, help="旁路库路径，默认与主库同目录的 history_labels.duckdb")
    p.add_argument("--params", default=str(DEFAULT_PARAMS_PATH), help="参数文件")
    p.add_argument("--schedule-dir", default=None, help="官方日程目录，默认参数文件里的 schedule_dir")
    p.add_argument("--kb-wiki", default=None, help="知识库 wiki 根目录（读卖方观点事件文件作 narrative 源）；不给则 narrative 类记 source_absent 缺口")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="事件定价第一刀：日历 / 锚点 / 反应 / 读数")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn, help_text in (
        ("build-calendar", cmd_build_calendar, "编辑日历 + 官方日程 → history_event_calendar"),
        ("build-anchors", cmd_build_anchors, "→ history_event_anchors"),
        ("build-reaction", cmd_build_reaction, "→ history_event_reaction + 横截面"),
    ):
        p = sub.add_parser(name, help=help_text)
        _common(p)
        p.set_defaults(func=fn)
    r = sub.add_parser("report", help="四态读数 + 收据")
    _common(r)
    r.add_argument("--receipts-dir", default=str(RECEIPTS_DIR))
    r.add_argument("--no-write", action="store_true")
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=cmd_report)
    lk = sub.add_parser("latest-known", help="站在 as_of 已知最新一期是哪期 / 尚未发布（不返回数值）")
    _common(lk)
    lk.add_argument("--indicator", required=True)
    lk.add_argument("--as-of", required=True, type=_date_arg)
    lk.set_defaults(func=cmd_latest_known)
    a = sub.add_parser("all", help="build-calendar → build-anchors → build-reaction → report")
    _common(a)
    a.add_argument("--receipts-dir", default=str(RECEIPTS_DIR))
    a.add_argument("--no-write", action="store_true")
    a.set_defaults(func=cmd_all)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if getattr(args, "labels_db", None) is None:
        args.labels_db = str(default_labels_db_path(getattr(args, "db_path", None)))
    try:
        return int(args.func(args) or 0)
    except DatabaseLockedError as exc:
        print(f"主库被写锁占用（夜跑 / 回填在写），稍后重试：{exc}", file=sys.stderr)
        return EXIT_LOCKED
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return EXIT_INPUT


if __name__ == "__main__":
    raise SystemExit(main())
