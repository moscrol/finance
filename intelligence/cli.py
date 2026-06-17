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
    parser.add_argument("--interactions-file", default=None, help="用户反馈记录 jsonl（默认 users/<user>/interactions.jsonl，已 gitignore）")
    parser.add_argument("--no-interactions", dest="use_interactions", action="store_false", help="不读反馈回路、排序不加亲和加成（默认开启）")
    parser.add_argument("--interactions-window", type=int, default=200, help="只聚合最近 N 条反馈算亲和度（默认 200）")
    parser.add_argument("--affinity-half-life", type=float, default=14.0, help="反馈时间衰减半衰期（天，默认 14）")
    parser.add_argument("--affinity-boost", type=float, default=0.2, help="反馈加成上限权重（默认 0.2；0 关闭加成）")
    parser.set_defaults(use_interactions=True)
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON 而非 Markdown")
    parser.add_argument("--summary-json", default=None, help="写出 workflow summary JSON")
    parser.set_defaults(func=cmd_foresight)


def add_record_interaction_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "record-interaction",
        help="反馈回路：记一条对「猜你想问」的反馈（点开/追问/喜欢/忽略/打分）→ 越用越懂",
    )
    parser.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    parser.add_argument(
        "--kind",
        required=True,
        help="反馈类型：click/open/ask/like/follow/pin/view/skip/ignore/dismiss/mute/dislike/rate",
    )
    parser.add_argument("--question", default=None, help="被反馈的问题原文（可选，仅留痕）")
    parser.add_argument("--theme", dest="themes", action="append", default=[], help="关联题材（可多次）")
    parser.add_argument("--stock", dest="stocks", action="append", default=[], help="关联个股（可多次）")
    parser.add_argument("--weight", type=float, default=None, help="显式权重（覆盖 kind 默认；正升负降）")
    parser.add_argument("--rating", type=float, default=None, help="1~5 星评分（kind=rate 时用，映射到 [-1,1]）")
    parser.add_argument("--note", default=None, help="备注（可选）")
    parser.add_argument("--interactions-file", default=None, help="覆盖反馈记录文件路径")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--summary-json", default=None, help="写出 workflow summary JSON")
    parser.set_defaults(func=cmd_record_interaction)


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
            interactions_file=args.interactions_file,
            use_interactions=args.use_interactions,
            interactions_window=args.interactions_window,
            affinity_half_life=args.affinity_half_life,
            affinity_boost=args.affinity_boost,
        )
    )
    if args.summary_json:
        summary.write_json(args.summary_json)
    if args.json:
        print(_json.dumps(result_to_dict(result), ensure_ascii=False, indent=2))
    else:
        print(render(result), end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_record_interaction(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.workflows.record_interaction import (
        RecordInteractionOptions,
        render,
        run_record_interaction,
    )

    summary, record = run_record_interaction(
        RecordInteractionOptions(
            kind=args.kind,
            user=args.user,
            question=args.question,
            themes=args.themes,
            stocks=args.stocks,
            weight=args.weight,
            rating=args.rating,
            note=args.note,
            interactions_file=args.interactions_file,
        )
    )
    if args.summary_json:
        summary.write_json(args.summary_json)
    if args.json:
        print(_json.dumps(record, ensure_ascii=False, indent=2))
    else:
        path = summary.steps[0].outputs[0].split("=", 1)[1] if summary.steps else ""
        print(render(record, path), end="")
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


def add_serve_parser(subparsers: argparse._SubParsersAction) -> None:
    from intelligence import server

    parser = subparsers.add_parser(
        "serve",
        help="启动本地 Web GUI（猜你想问卡片流 + 亲和度榜 + 画像 + 策略 overlay；零依赖）",
    )
    server.add_arguments(parser)
    parser.set_defaults(func=cmd_serve)


def cmd_serve(args: argparse.Namespace) -> int:
    from intelligence import server

    server.serve(server.build_config(args))
    return 0


def add_feishu_bot_parser(subparsers: argparse._SubParsersAction) -> None:
    from intelligence.chat import feishu_bot

    parser = subparsers.add_parser(
        "feishu-bot",
        help="飞书 chat bot（B-S2，长连接 + in-process 调 ask 回六段；--echo 退回 B-S0 自检；"
        "凭证走 env / ~/.claude/shared/feishu_config.json）",
    )
    feishu_bot.add_arguments(parser)
    parser.set_defaults(func=cmd_feishu_bot)


def cmd_feishu_bot(args: argparse.Namespace) -> int:
    from intelligence.chat import feishu_bot

    return feishu_bot.run(feishu_bot.build_config(args))


def add_dream_collect_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "dream-collect",
        help="dream-loop C-1A-S0：对话源（S0 仅飞书）归一化+脱敏 → transcript store + manifest + 脱敏 digest（suggest-only，不碰 DuckDB）",
    )
    parser.add_argument("--source", default="feishu", choices=["feishu"], help="对话源（S0 仅 feishu）")
    parser.add_argument("--events", default=None, help="原始事件 jsonl（飞书 bot 的 --transcript-log 产物）")
    parser.add_argument(
        "--store-dir",
        default=None,
        help="transcript store 根目录（默认 env DREAM_TRANSCRIPT_STORE > 知识库 raw/transcripts > 本仓 _local 回退）",
    )
    parser.add_argument("--repo", default=None, help="标注来源仓库 tag（可选）")
    parser.add_argument("--digest-only", action="store_true", help="只用现有 store 重建 digest，不读 events")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON 摘要")
    parser.set_defaults(func=cmd_dream_collect)


def cmd_dream_collect(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.dream import collector

    summary = collector.run_collect(
        collector.CollectOptions(
            events_path=args.events,
            store_dir=args.store_dir,
            source=args.source,
            repo=args.repo,
            digest_only=args.digest_only,
        )
    )
    if args.json:
        print(_json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(collector.render_summary(summary), end="")
    return 0


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
    add_record_interaction_parser(subparsers)
    add_refresh_profile_parser(subparsers)
    add_adapter_smoke_parser(subparsers)
    add_daily_parser(subparsers)
    add_theme_parser(subparsers)
    add_serve_parser(subparsers)
    add_feishu_bot_parser(subparsers)
    add_dream_collect_parser(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
