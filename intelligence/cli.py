from __future__ import annotations

import argparse
import sys

# NOTE: workflow modules are imported lazily inside each command handler so the
# CLI (and the duckdb-free `ask` command) can run in environments without the
# market database driver installed.


def add_ask_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "ask", help="Unified multi-source ask: KB graph (G/R) + market 盘面 snapshot (S)"
    )
    parser.add_argument("query", help="Question / theme term, e.g. 液冷服务器")
    parser.add_argument("--date", default=None, help="theme-candidates export date YYYY-MM-DD; defaults to latest")
    parser.add_argument("--exports-dir", default=None, help="Override market_feature_store/exports dir")
    parser.add_argument("--kb-wiki", default=None, help="Knowledge-base wiki root (contains relations/); defaults to env/auto")
    parser.add_argument("--top-companies", type=int, default=12, help="Max exposed companies to recall")
    parser.add_argument(
        "--modules",
        default=None,
        help="Comma-separated theme-radar backends to fan out to "
        "(brief,front-map,deep-dive,replay,scan,migrate). Default: auto-route by query.",
    )
    parser.add_argument("--no-modules", action="store_true", help="Disable theme-radar module fan-out (graph+盘面 only)")
    parser.add_argument("--module-timeout", type=int, default=180, help="Per-module subprocess timeout in seconds")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Refine 结论/交易含义 with an LLM (needs DEEPSEEK_API_KEY/MOONSHOT_API_KEY/"
        "DASHSCOPE_API_KEY/ZHIPU_API_KEY/OPENAI_API_KEY or LLM_API_KEY). No key -> template fallback.",
    )
    parser.add_argument("--llm-model", default=None, help="Override LLM model id (else provider default / LLM_MODEL)")
    parser.add_argument("--llm-timeout", type=int, default=60, help="LLM HTTP timeout in seconds")
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Append each routed module's FULL report as a per-module 钻取 appendix (折叠块).",
    )
    parser.add_argument("--summary-json", default=None, help="Write workflow summary JSON")
    parser.set_defaults(func=cmd_ask)


def add_foresight_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "foresight",
        help="猜你想问 / 潜意识：基于盘面现实+用户画像，主动生成「你还没想到但该问」的追问",
    )
    parser.add_argument("--user", default=None, help="用户 id（应用态命名空间 intelligence/users/<id>/；默认 default 或环境变量 FORESIGHT_USER）")
    parser.add_argument("--profile", default=None, help="显式画像 JSON 单文件（覆盖用户命名空间；默认走 users/<user>/ 合并）")
    parser.add_argument("--news-file", default=None, help="可选实时情报文件（今日财经日历/新闻），无则跳过实时层")
    parser.add_argument("--date", default=None, help="theme-candidates 盘面快照日期 YYYY-MM-DD；默认取最新")
    parser.add_argument("--exports-dir", default=None, help="覆盖 market_feature_store/exports 目录")
    parser.add_argument("--kb-wiki", default=None, help="知识库 wiki 根（预留，当前主要用盘面快照锚定）")
    parser.add_argument("-n", "--num", type=int, default=3, help="最终展示问题数（默认 3）")
    parser.add_argument("--candidates", type=int, default=8, help="让 LLM 先生成的候选数（默认 8，再排序取前 N）")
    parser.add_argument(
        "--llm-model",
        default=None,
        help="覆盖 LLM 模型 id（需 DEEPSEEK_API_KEY/MOONSHOT_API_KEY/DASHSCOPE_API_KEY/"
        "ZHIPU_API_KEY/OPENAI_API_KEY 或 LLM_API_KEY；无 key 自动降级为摘要+提示词预览）",
    )
    parser.add_argument("--llm-timeout", type=int, default=60, help="LLM HTTP 超时秒数")
    parser.add_argument("--temperature", type=float, default=0.8, help="生成温度，越高越发散（默认 0.8）")
    parser.add_argument("--memory-file", default=None, help="问过的问题记忆 jsonl（默认 intelligence/foresight_memory.jsonl，已 gitignore）")
    parser.add_argument("--no-memory", dest="use_memory", action="store_false", help="不读/不写记忆回路（默认开启）")
    parser.add_argument("--memory-window", type=int, default=50, help="只用最近 N 条历史提问去重（默认 50）")
    parser.set_defaults(use_memory=True)
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON 而非 Markdown")
    parser.add_argument("--summary-json", default=None, help="写出 workflow summary JSON")
    parser.set_defaults(func=cmd_foresight)


def add_refresh_profile_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "refresh-profile",
        help="第 2 层：从 DuckDB 强势股 + 知识库 theme_signals 自动派生画像候选（不碰飞书）",
    )
    parser.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    parser.add_argument("--lookback", type=int, default=20, help="回看交易日数（预留，当前按最新快照派生）")
    parser.add_argument("--date", default=None, help="盘面快照日期 YYYY-MM-DD；默认取 DuckDB 最新")
    parser.add_argument("--top", type=int, default=12, help="候选 focus_themes / watchlist 各取前 N（默认 12）")
    parser.add_argument("--kb-wiki", default=None, help="知识库 wiki 根（含 relations/）；默认 env/auto")
    parser.add_argument("--db-path", default=None, help="覆盖 DuckDB 路径；默认 market_feature_store 约定路径")
    parser.add_argument("--apply", action="store_true", help="落盘 users/<user>/profile.derived.json（默认仅预览 diff）")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON（proposal+diff）而非 Markdown")
    parser.add_argument("--summary-json", default=None, help="写出 workflow summary JSON")
    parser.set_defaults(func=cmd_refresh_profile)


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
    parser.add_argument("--skip-legacy-theme", action="store_true", help="Skip legacy triggered-themes brief")
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


def cmd_ask(args: argparse.Namespace) -> int:
    from intelligence.workflows.ask import AskWorkflowOptions, run_ask

    modules = tuple(m.strip() for m in args.modules.split(",") if m.strip()) if args.modules else None
    summary, _result, answer = run_ask(
        AskWorkflowOptions(
            query=args.query,
            date=args.date,
            exports_dir=args.exports_dir,
            kb_wiki=args.kb_wiki,
            top_companies=args.top_companies,
            use_modules=not args.no_modules,
            modules=modules,
            module_timeout=args.module_timeout,
            use_llm=args.llm,
            llm_model=args.llm_model,
            llm_timeout=args.llm_timeout,
            detail=args.detail,
        )
    )
    if args.summary_json:
        summary.write_json(args.summary_json)
    print(answer, end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_foresight(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.services.foresight import render, result_to_dict
    from intelligence.workflows.foresight import ForesightWorkflowOptions, run_foresight

    summary, result, answer = run_foresight(
        ForesightWorkflowOptions(
            profile=args.profile,
            user=args.user,
            news_file=args.news_file,
            date=args.date,
            exports_dir=args.exports_dir,
            kb_wiki=args.kb_wiki,
            n=args.num,
            candidates=args.candidates,
            llm_model=args.llm_model,
            llm_timeout=args.llm_timeout,
            temperature=args.temperature,
            memory_file=args.memory_file,
            use_memory=args.use_memory,
            memory_window=args.memory_window,
        )
    )
    if args.summary_json:
        summary.write_json(args.summary_json)
    if args.json:
        print(_json.dumps(result_to_dict(result), ensure_ascii=False, indent=2))
    else:
        print(render(result), end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_refresh_profile(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.workflows.refresh_profile import RefreshProfileWorkflowOptions, run_refresh_profile

    summary, proposal, diff, answer = run_refresh_profile(
        RefreshProfileWorkflowOptions(
            user=args.user,
            lookback=args.lookback,
            date=args.date,
            top=args.top,
            kb_wiki=args.kb_wiki,
            db_path=args.db_path,
            apply=args.apply,
        )
    )
    if args.summary_json:
        summary.write_json(args.summary_json)
    if args.json:
        print(_json.dumps({"proposal": proposal, "diff": diff}, ensure_ascii=False, indent=2))
    else:
        print(answer, end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_daily(args: argparse.Namespace) -> int:
    from intelligence.workflows.daily_review import DailyReviewOptions, dry_run_daily_review, run_daily_review

    options = DailyReviewOptions(
        date=args.date,
        skip_sync=args.skip_sync,
        skip_long=args.skip_long,
        skip_theme=args.skip_theme,
        skip_legacy_theme=args.skip_legacy_theme,
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
    from intelligence.workflows.adapter_smoke import AdapterSmokeOptions, run_adapter_smoke

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
    from intelligence.workflows.theme_radar import ThemeRadarOptions, run_theme_radar

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
    add_ask_parser(subparsers)
    add_foresight_parser(subparsers)
    add_refresh_profile_parser(subparsers)
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
