from __future__ import annotations

import argparse
import sys

from intelligence.workflows.adapter_smoke import AdapterSmokeOptions, run_adapter_smoke
from intelligence.workflows.daily_review import DailyReviewOptions, dry_run_daily_review, run_daily_review
from intelligence.workflows.theme_radar import ThemeRadarOptions, run_theme_radar


def add_adapter_smoke_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("adapter-smoke", help="Run read-only adapter smoke checks")
    parser.add_argument("--date", default=None, help="Trade date YYYY-MM-DD; defaults to latest available")
    parser.add_argument("--entity", default="ASML", help="Entity name for knowledge adapter checks")
    parser.add_argument("--concept", default=None, help="Optional concept filter for evidence lookup")
    parser.add_argument("--summary-json", default=None, help="Write workflow summary JSON")
    parser.set_defaults(func=cmd_adapter_smoke)


def add_daily_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("daily", help="Run daily review workflow")
    parser.add_argument("--date", required=True, help="Trade date YYYY-MM-DD")
    parser.add_argument("--skip-sync", action="store_true", help="Skip market data sync")
    parser.add_argument("--skip-long", action="store_true", help="Pass --skip-long to daily-update")
    parser.add_argument("--skip-theme", action="store_true", help="Skip market-triggered theme brief")
    parser.add_argument("--skip-workbench", action="store_true", help="Skip review workbench render")
    parser.add_argument("--start-date", default=None, help="Optional start date for daily-review")
    parser.add_argument("--from-step", default=None, help="Start workflow from this step")
    parser.add_argument("--only-step", default=None, help="Run only this step")
    parser.add_argument("--continue-on-warn", action="store_true", help="Continue when a recoverable step is downgraded to WARN")
    parser.add_argument("--summary-json", default=None, help="Write workflow summary JSON")
    parser.add_argument("--dry-run", action="store_true", help="Print command plan without execution")
    parser.set_defaults(func=cmd_daily)


def add_theme_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("theme", help="Run theme radar workflows")
    parser.add_argument("--date", required=True, help="Trade date YYYY-MM-DD")
    parser.add_argument("--market-triggered", action="store_true", required=True, help="Build market-triggered theme candidates")
    parser.add_argument("--top", type=int, default=50, help="Maximum number of market-triggered candidates")
    parser.add_argument("--out-json", default=None, help="Write market-triggered candidates JSON")
    parser.add_argument("--out-md", default=None, help="Write market-triggered candidates Markdown brief")
    parser.add_argument("--summary-json", default=None, help="Write workflow summary JSON")
    parser.set_defaults(func=cmd_theme)


def cmd_daily(args: argparse.Namespace) -> int:
    options = DailyReviewOptions(
        date=args.date,
        skip_sync=args.skip_sync,
        skip_long=args.skip_long,
        skip_theme=args.skip_theme,
        skip_workbench=args.skip_workbench,
        start_date=args.start_date,
        dry_run=args.dry_run,
        from_step=args.from_step,
        only_step=args.only_step,
        continue_on_warn=args.continue_on_warn,
    )
    summary = dry_run_daily_review(options) if args.dry_run else run_daily_review(options)
    if args.summary_json:
        summary.write_json(args.summary_json)
    print(summary.to_json(), end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_adapter_smoke(args: argparse.Namespace) -> int:
    options = AdapterSmokeOptions(
        date=args.date,
        entity=args.entity,
        concept=args.concept,
    )
    summary = run_adapter_smoke(options)
    if args.summary_json:
        summary.write_json(args.summary_json)
    print(summary.to_json(), end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_theme(args: argparse.Namespace) -> int:
    options = ThemeRadarOptions(
        date=args.date,
        market_triggered=args.market_triggered,
        top=args.top,
        out_json=args.out_json,
        out_md=args.out_md,
    )
    summary = run_theme_radar(options)
    if args.summary_json:
        summary.write_json(args.summary_json)
    print(summary.to_json(), end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Financial intelligence product CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_adapter_smoke_parser(subparsers)
    add_daily_parser(subparsers)
    add_theme_parser(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
