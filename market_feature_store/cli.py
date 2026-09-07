"""Market Feature Store 命令行入口。

用法:
    python3 -m market_feature_store.cli init    # 初始化 schema (幂等)
    python3 -m market_feature_store.cli info    # 查看库内表与行数
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .db import DB_PATH, connect, init_db, list_tables


def _write_status_json(path: str | None, payload: dict[str, object]) -> None:
    if not path:
        return
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(target)


def cmd_init(_args) -> int:
    init_db()
    con = connect(read_only=True)
    try:
        tables = list_tables(con)
    finally:
        con.close()
    print(f"已初始化: {DB_PATH}")
    print(f"表数量: {len(tables)}")
    for t in tables:
        print(f"  - {t}")
    return 0


def cmd_sector_universe_preview(args) -> int:
    """只读迁移预览：不建表、不写入、不调 provider。

    在对生产库执行任何迁移或同步之前，先把"会发生什么"量出来：遗留物理行数、
    预计退役的身份、当前已发布代际的分母、以及目标快照哈希。全程 read_only
    连接，因此可以安全地对生产库跑。

    provider 分母需要实盘调用，本命令刻意不做——它属于 Task 8 Step 3 的授权范围。
    这里报告的是库内已发布代际的分母，以及缺口本身。
    """
    from .sector_universe import SectorUniverseStore

    con = connect(read_only=True)
    try:
        report: dict[str, object] = {"db_path": str(DB_PATH)}

        def _count(sql: str, params: list | None = None) -> int | None:
            try:
                return int(con.execute(sql, params or []).fetchone()[0])
            except Exception:
                return None

        report["legacy_sector_daily_rows"] = _count(
            "SELECT count(*) FROM fact_sector_daily_generation "
            "WHERE sector_universe_snapshot_id = 'legacy'"
        )
        report["legacy_member_rows"] = _count(
            "SELECT count(*) FROM fact_sector_stock_daily_generation "
            "WHERE sector_universe_snapshot_id = 'legacy'"
        )
        report["published_headers"] = _count(
            "SELECT count(*) FROM ops_sector_universe_snapshot_daily "
            "WHERE status = 'published'"
        )
        report["dim_sector_active"] = _count(
            "SELECT count(*) FROM dim_sector WHERE is_active IS TRUE"
        )
        # 预计退役：dim_sector 里仍 active、但不在最新已发布宇宙里的身份。
        report["predicted_retirements"] = _count(
            """
            SELECT count(*) FROM dim_sector AS d
            WHERE d.is_active IS TRUE AND NOT EXISTS (
                SELECT 1 FROM fact_sector_universe_daily AS u
                WHERE u.sector_ts_code = d.sector_ts_code
                  AND u.trade_date = (
                    SELECT max(trade_date) FROM ops_sector_universe_snapshot_daily
                    WHERE status = 'published'
                  )
            )
            """
        )
        # 代际 schema 尚未应用到目标库时，上面每一项都会是 None。这是预览要回答的
        # 头号问题（"这库迁过没有"），所以显式报告而不是抛异常。
        report["generation_schema_present"] = report["published_headers"] is not None
        target_date: str | None = args.trade_date
        if target_date is None and report["generation_schema_present"]:
            latest = con.execute(
                "SELECT max(trade_date) FROM ops_sector_universe_snapshot_daily "
                "WHERE status = 'published'"
            ).fetchone()
            target_date = str(latest[0]) if latest and latest[0] else None
        report["target_trade_date"] = target_date
        if target_date and report["generation_schema_present"]:
            audit = SectorUniverseStore(con).completion_audit(
                target_date,
                declared_tables=frozenset(
                    {"fact_sector_daily", "fact_sector_stock_daily"}
                ),
            )
            report["target_snapshot_id"] = audit.snapshot_id
            report["declared_sector_count"] = audit.declared_sector_count
            report["declared_relationship_count"] = audit.declared_relationship_count
            report["actual_relationship_count"] = audit.actual_relationship_count
            report["receipt_status_counts"] = dict(audit.status_counts)
            report["complete"] = audit.complete
            report["audit_brief"] = audit.brief()
        # 未迁移库的遗留量：迁移会把这两张物理表的现有行搬进 legacy 代际。
        if not report["generation_schema_present"]:
            report["premigration_sector_daily_rows"] = _count(
                "SELECT count(*) FROM fact_sector_daily"
            )
            report["premigration_member_rows"] = _count(
                "SELECT count(*) FROM fact_sector_stock_daily"
            )
        report["provider_denominator"] = None
        report["provider_denominator_note"] = (
            "requires an authorized live provider call (Task 8 Step 3); not performed"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    finally:
        con.close()
    return 0


def cmd_sync_sectors(args) -> int:
    from .sync.sync_fupanhui_sectors import sync_dim_sector

    stats = sync_dim_sector(trade_date=args.trade_date)
    print(f"拉取板块: {stats['fetched']}")
    print(f"dim_sector 总数: {stats['dim_sector_total']}")
    print(f"已映射申万一级: {stats['mapped_sw_l1']}")
    print(f"基准日期: {stats['seen_date']}")
    unmapped = stats["unmapped_names"]
    if unmapped:
        print(f"未映射板块 ({len(unmapped)}): {', '.join(unmapped)}")
    else:
        print("未映射板块: 0")
    return 0


def cmd_sync_sector_daily(args) -> int:
    from .sync.sync_fupanhui_sector_daily import sync_fact_sector_daily

    stats = sync_fact_sector_daily(trade_date=args.trade_date, days=args.days)
    print(f"板块数: {stats['sectors']} (空序列 {stats['empty_sectors']})")
    print(f"写入行: {stats['rows_written']}")
    print(f"fact_sector_daily 总数: {stats['fact_sector_daily_total']}")
    print(f"覆盖交易日: {stats['distinct_dates']} ({stats['date_min']} ~ {stats['date_max']})")
    return 0


def cmd_sync_sector_daily_range(args) -> int:
    from .sync.sync_fupanhui_sector_daily import sync_fact_sector_daily_range

    stats = sync_fact_sector_daily_range(
        start_date=args.start_date,
        end_date=args.end_date,
        days=args.days,
        chunk_days=args.chunk_days,
        refresh=args.refresh,
        sleep=args.sleep,
    )
    print(f"目标交易日: {stats['requested_dates']} 个 | 来源: {stats['date_source']}")
    print(f"同步: {stats['synced_dates']} | 跳过: {stats['skipped_dates']} | 失败批次: {stats['failed_chunks']}")
    print(f"本次写入/覆盖板块日行情: {stats['total_rows_written']} 行")
    print(f"fact_sector_daily: {stats['table_total']} 行, {stats['table_dates']} 交易日 ({stats['date_min']}~{stats['date_max']}), 空diff {stats['null_diff_ratio']}")
    if stats["skipped"]:
        print("跳过日期: " + ", ".join(f"{x['trade_date']}({x['existing_rows']}行)" for x in stats["skipped"][:20]))
    if stats["failures"]:
        print("失败批次: " + ", ".join(f"{x['trade_date']}({x['error']})" for x in stats["failures"][:10]))
    return 1 if stats["failures"] else 0


def cmd_sync_sector_stocks(args) -> int:
    from .sync.sync_fupanhui_sector_stock_daily import sync_fact_sector_stock_daily

    stats = sync_fact_sector_stock_daily(
        trade_date=args.trade_date,
        sector=args.sector,
        limit=args.limit,
        only_missing=not args.refresh,
        sleep=args.sleep,
        chunk=args.chunk,
        max_attempts=args.max_attempts,
    )
    print(f"交易日: {stats['trade_date']}")
    print(f"本次抓取板块: {stats['processed']} | 写入行: {stats['rows_written']}")
    print(f"当日已完成板块: {stats['sectors_done_today']}/{stats['sectors_total']} | 剩余: {stats['sectors_remaining']}")
    print(f"fact_sector_stock_daily 总数: {stats['table_total']}")
    if stats["failures"]:
        print(f"失败 {len(stats['failures'])}: " + ", ".join(c for c, _ in stats['failures'][:10]))
    return 0


def cmd_sync_mainline_sector_daily(args) -> int:
    from .sync.sync_fupanhui_mainline_sector_daily import sync
    from .sources import fupanhui_source as fs

    td = args.trade_date or fs.get_latest_date_public()
    stats = sync(td)
    print(f"交易日: {td} | 主线题材: {stats['themes']} | 写入板块行: {stats['sectors']}")
    failures = stats["failures"]
    if failures:
        print(f"失败题材 ({len(failures)}):")
        for f in failures:
            print(f"  - {f['theme_code']} {f['theme_name']}: {f['error']}")
    else:
        print("失败题材: 0")
    print(f"同步状态: {stats['status']}")
    return 0 if stats["status"] == "complete" else 2


def cmd_sync_index_daily(args) -> int:
    from .sync.sync_akshare_index_daily import sync_akshare_index_daily

    stats = sync_akshare_index_daily(
        trade_date=args.trade_date,
        start_date=args.start_date,
        end_date=args.end_date,
        symbol=args.symbol,
    )
    print(f"指数: {stats['symbol']} | 写入: {stats['rows_written']} 行")
    print(f"指数点位覆盖: {stats['close_count']} 行 ({stats['date_min']} ~ {stats['date_max']})")
    if stats["current"]:
        d, close, pct = stats["current"]
        print(f"当前: {d} 收盘={close} 涨跌幅={pct}%")
    return 0



def cmd_sync_sw_l1_daily(args) -> int:
    from .sync.sync_akshare_sw_l1_daily import sync_akshare_sw_l1_daily

    stats = sync_akshare_sw_l1_daily(
        trade_date=args.trade_date,
        days=args.days,
    )
    print(f"交易日: {stats['trade_date']} | 目标交易日: {stats['target_dates']} | 申万一级: {stats['industries']}")
    print(f"写入: {stats['rows_written']} 行")
    print(f"fact_sw_l1_daily: {stats['table_total']} 行, {stats['table_dates']} 交易日 ({stats['date_min']} ~ {stats['date_max']}), 复盘占比 {stats['ratio_count']} 行")
    focus = [row for row in stats["current"] if row[0] in ("电子", "通信", "机械设备", "电力设备")]
    for sw_l1, pct_chg, ratio, source in focus:
        print(f"{sw_l1}: 涨跌幅={pct_chg} 占比={ratio} 来源={source}")
    if stats.get("degraded_rows"):
        print(f"降级: {stats['degraded_rows']} 个申万一级使用复盘会板块聚合代理源")
    if stats.get("failures"):
        print("失败行业: " + ", ".join(f"{x['sw_l1']}({x['error'][:40]})" for x in stats["failures"][:10]))
    print(f"同步状态: {stats['status']}")
    return 0 if stats["status"] in {"complete", "degraded"} else 2


def cmd_sync_market_strength(args) -> int:
    from .sync.sync_fupanhui_market_daily import sync_fupanhui_market_strength

    stats = sync_fupanhui_market_strength(trade_date=args.trade_date, days=args.days)
    print(f"交易日: {stats['trade_date']} | 写入强度序列: {stats['rows_written']} 行")
    print(f"fact_market_daily 总数: {stats['table_total']} ({stats['date_min']} ~ {stats['date_max']})")
    print(f"强度覆盖: avg={stats['strength_avg_count']} amount_pct={stats['strength_amount_pct_count']} marginal={stats['strength_marginal_count']}")
    if stats["current"]:
        avg, amount_pct, amount, marginal, status = stats["current"]
        print(f"当前强度: 加权涨幅={avg}% 成交占比={amount_pct}% 成交额={amount}亿 成交环比={marginal}% 状态={status}")
    return 0


def cmd_sync_market_deviation(args) -> int:
    from .sync.sync_fupanhui_market_deviation import sync_market_deviation

    stats = sync_market_deviation(trade_date=args.trade_date)
    print(f"交易日: {stats['trade_date']} | 周均线={stats['sh_week_ma']} 偏离度={stats['sh_deviation_pct']}%")
    if stats["current"]:
        print(f"已写入: {stats['current']}")
    return 0


def cmd_sync_market_overview(args) -> int:
    from .sync.sync_fupanhui_market_daily import sync_fupanhui_market_overview

    stats = sync_fupanhui_market_overview(trade_date=args.trade_date, days=args.days)
    print(f"交易日: {stats['trade_date']} | 每日复盘结构化写入: {stats['rows_written']} 行")
    print(f"fact_market_daily 总数: {stats['table_total']} ({stats['date_min']} ~ {stats['date_max']})")
    print(f"覆盖: 成交额={stats['total_amount_count']} 涨家数={stats['advancers_count']} 前三行业={stats['top3_ratio_count']}")
    if stats["current"]:
        stage, stage_day, amount, ratio, adv, limit_up, limit_down, top3 = stats["current"]
        print(f"当前: {stage or '-'} 第{stage_day or '-'}天 | 成交额={amount}亿 量能比={ratio}% | 涨={adv} 涨停={limit_up} 跌停={limit_down} | 前三占比={top3}%")
    return 0


def cmd_sync_market_overview_range(args) -> int:
    from .sync.sync_fupanhui_market_daily import sync_fupanhui_market_overview_range

    stats = sync_fupanhui_market_overview_range(
        start_date=args.start_date,
        end_date=args.end_date,
        days=args.days,
        api_days=args.api_days,
        refresh=args.refresh,
        sleep=args.sleep,
    )
    print(f"目标交易日: {stats['requested_dates']} 个 | 来源: {stats['date_source']}")
    print(f"同步: {stats['synced_dates']} | 跳过: {stats['skipped_dates']} | 失败: {stats['failed_dates']}")
    print(f"fact_market_daily: {stats['table_total']} 行, {stats['table_dates']} 交易日 ({stats['date_min']}~{stats['date_max']})")
    print(f"覆盖: 成交额={stats['total_amount_count']} 涨家数={stats['advancers_count']} 前三行业={stats['top3_ratio_count']}")
    if stats["skipped"]:
        print("跳过日期: " + ", ".join(x["trade_date"] for x in stats["skipped"][:20]))
    if stats["failures"]:
        print("失败日期: " + ", ".join(f"{x['trade_date']}({x['error']})" for x in stats["failures"][:10]))
    return 1 if stats["failures"] else 0


def cmd_sync_stock_high(args) -> int:
    from .sync.sync_fupanhui_stock_high_daily import sync_fupanhui_stock_high

    stats = sync_fupanhui_stock_high(trade_date=args.trade_date, page_size=args.page_size)
    print(f"交易日: {stats['trade_date']} | 个股新高写入: {stats['unique_stocks']} 只")
    print("周期抓取: " + ", ".join(f"{k}={v}" for k, v in stats["fetched_by_period"].items()))
    print("市场新高家数: " + ", ".join(f"{k}={v}" for k, v in stats["counts"].items()))
    print(f"fact_stock_high_daily: {stats['table_total']} 行, {stats['table_dates']} 交易日 ({stats['date_min']}~{stats['date_max']})")
    print(f"其中 primary=历史新高: {stats['history_rows']} 行")
    return 0


def cmd_sync_stock_high_range(args) -> int:
    from .sync.sync_fupanhui_stock_high_daily import sync_fupanhui_stock_high_range

    stats = sync_fupanhui_stock_high_range(
        start_date=args.start_date,
        end_date=args.end_date,
        days=args.days,
        page_size=args.page_size,
        refresh=args.refresh,
        sleep=args.sleep,
    )
    print(f"目标交易日: {stats['requested_dates']} 个 | 来源: {stats['date_source']}")
    print(f"同步: {stats['synced_dates']} | 跳过: {stats['skipped_dates']} | 失败: {stats['failed_dates']}")
    print(f"本次同步个股新高合计: {stats['total_unique_stocks']} 只次")
    print("周期抓取合计: " + ", ".join(f"{k}={v}" for k, v in stats["total_period_fetches"].items()))
    print(f"fact_stock_high_daily: {stats['table_total']} 行, {stats['table_dates']} 交易日 ({stats['date_min']}~{stats['date_max']})")
    if stats["skipped"]:
        print("跳过日期: " + ", ".join(f"{x['trade_date']}({x['existing_rows']}行)" for x in stats["skipped"][:20]))
    if stats["failures"]:
        print("失败日期: " + ", ".join(f"{x['trade_date']}({x['error']})" for x in stats["failures"][:10]))
    return 1 if stats["failures"] else 0


def cmd_sync_limit_heat(args) -> int:
    from .sync.sync_fupanhui_limit_heat_daily import sync_fupanhui_limit_heat

    stats = sync_fupanhui_limit_heat(
        trade_date=args.trade_date,
        dimension=args.dimension,
        scope=args.scope,
        sector=args.sector,
        limit=args.limit,
        sleep=args.sleep,
        detail_chunk=args.detail_chunk,
    )
    print(f"交易日: {stats['trade_date']} | 涨停热力题材写入: {stats['heat_rows']} 个 | 涨停股明细写入: {stats['stock_rows']} 行")
    print(f"市场涨停家数: {stats['market_limit_up_count']} | 接口题材: {stats['items_total']} | 处理题材: {stats['items_processed']}")
    print(f"fact_theme_limit_heat_daily: {stats['table_total']} 行, {stats['table_dates']} 交易日 ({stats['date_min']}~{stats['date_max']})")
    print(f"fact_theme_limit_stock_daily: {stats['stock_table_total']} 行, {stats['stock_table_dates']} 交易日, {stats['stock_table_stocks']} 股")
    if stats["failures"]:
        print(f"失败 {len(stats['failures'])}: " + ", ".join(f"{c}/{n}" for c, n, _e in stats["failures"][:10]))
    return 0


def cmd_sync_mainline_daily(args) -> int:
    from .sync.sync_fupanhui_mainline_daily import sync as sync_mainline_daily

    td = args.trade_date
    if not td:
        con = connect(read_only=True)
        try:
            row = con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()
        finally:
            con.close()
        td = str(row[0]) if row and row[0] is not None else None
    s = sync_mainline_daily(td)
    print(f"交易日: {td} | 主线题材: {s['themes']} | 主线个股: {s['stocks']}")
    if s["failures"]:
        print(f"失败题材 ({len(s['failures'])}):")
        for failure in s["failures"]:
            print(
                f"  - {failure.get('theme_code', '')} "
                f"{failure.get('theme_name', '')}: {failure['error']}"
            )
    print(f"同步状态: {s['status']}")
    # degraded: 部分题材上游空 groups，已落库成功题材
    return 0 if s["status"] in {"complete", "degraded"} else 2


def cmd_sync_theme_flow_daily(args) -> int:
    from .sync.sync_fupanhui_theme_flow_daily import sync as sync_theme_flow_daily

    td = args.trade_date
    if not td:
        con = connect(read_only=True)
        try:
            row = con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()
        finally:
            con.close()
        td = str(row[0]) if row and row[0] is not None else None
    s = sync_theme_flow_daily(td)
    print(f"交易日: {td} | 题材资金面板: {s['panels']}")
    return 0


def cmd_sync_fupanhui_public_assets(args) -> int:
    from .sync.sync_fupanhui_public_assets import align_bounds, sync as sync_public_assets, sync_range

    if args.align or args.start_date or args.end_date or args.days:
        if args.align and not args.start_date and not args.end_date and not args.days:
            start, end = align_bounds()
        elif args.days:
            start, end = align_bounds()
            con = connect(read_only=True)
            try:
                rows = con.execute(
                    """
                    SELECT CAST(trade_date AS VARCHAR) FROM fact_market_daily
                    WHERE trade_date <= ?
                    ORDER BY trade_date DESC
                    LIMIT ?
                    """,
                    [end, int(args.days)],
                ).fetchall()
            finally:
                con.close()
            dates = [r[0] for r in reversed(rows)]
            if not dates:
                print("无交易日可回补")
                return 2
            start, end = dates[0], dates[-1]
        else:
            if not args.start_date or not args.end_date:
                print("范围回补需要 --start-date 与 --end-date，或使用 --align / --days")
                return 2
            start, end = args.start_date, args.end_date
        print(f"对齐窗口: {start} ~ {end} | sleep={args.sleep} refresh={args.refresh}"
              + (f" only={args.only}" if getattr(args, "only", None) else ""))
        only = tuple(args.only) if getattr(args, "only", None) else None
        s = sync_range(
            start,
            end,
            refresh=args.refresh,
            sleep=args.sleep,
            include_catalog=args.include_catalog,
            only=only,
        )
        print(
            f"日历 {s['calendar_days']} 日 | 同步 {s['synced']} | 跳过 {s['skipped']} | 失败 {s['failed']}"
        )
        for name, stats in (s.get("per_task") or {}).items():
            print(f"  {name}: {stats}")
        return 0 if s.get("ok") else 2

    td = args.trade_date
    if not td:
        con = connect(read_only=True)
        try:
            row = con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()
        finally:
            con.close()
        td = str(row[0]) if row and row[0] is not None else None
    if not td:
        print("无交易日：请传 --trade-date 或先同步 fact_market_daily")
        return 2
    plan = getattr(args, "plan", "full") or "full"
    s = sync_public_assets(td, plan=plan)
    print(f"交易日: {td} | plan={plan}" + (f" | 停跑: {', '.join(s['skipped'])}" if s.get("skipped") else ""))
    for name, result in (s.get("results") or {}).items():
        print(f"  {name}: {result}")
    if s.get("errors"):
        print("失败子任务:")
        for name, err in s["errors"].items():
            print(f"  {name}: {err}")
    return 0 if s.get("ok") else 2


def cmd_stitch_sector_stocks(args) -> int:
    from .sync.sync_local_sector_members import brief, stitch_sector_members

    kwargs = {}
    if getattr(args, "max_baseline_age_days", None):
        kwargs["max_baseline_age_days"] = args.max_baseline_age_days
    s = stitch_sector_members(
        args.trade_date,
        fetch_caps=not args.no_caps,
        dry_run=args.dry_run,
        **kwargs,
    )
    print(f"交易日: {s['trade_date']} | snapshot={s['snapshot_id'][:12]} | {s['identity']}")
    print(f"候选 {s['candidates']} | 拼接 {s['stitched']} | 剔除无值成员 {s['dropped_members']} | 市值现值 {s['caps_fetched']} 只")
    if s["skipped"]:
        for reason, n in s["skipped"].items():
            codes = s["skipped_codes"].get(reason) or []
            print(f"  跳过[{reason}] {n}: {', '.join(codes[:10])}{'…' if len(codes) > 10 else ''}")
    if s["failed"]:
        print(f"  回执失败 {len(s['failed'])}: {s['failed'][:10]}")
    print(f"基线日期分布: {s['baseline_dates']}")
    print(f"留给复盘会 delta 的板块: {s['pending_for_provider']}")
    if s.get("audit"):
        print(f"完成度审计: {s['audit']}")
    print(brief(s))
    return 0


def cmd_carry_forward_universe(args) -> int:
    from .sync.compute_local_stats import carry_forward_universe

    r = carry_forward_universe(args.trade_date, supersede=args.supersede, base_date=args.base_date)
    print(f"交易日: {r['trade_date']} | {r['action']} | snapshot={str(r['snapshot_id'])[:12]} | provider={r['provider_source']}"
          + (f" | 板块 {r['sectors']} 承接自 {r['base_date']}" if r.get("sectors") else ""))
    return 0


def cmd_compute_limit_stats_local(args) -> int:
    from .sync.compute_local_stats import compute_limit_stats_local

    r = compute_limit_stats_local(args.trade_date, force=args.force, min_boards=args.min_boards)
    if r["action"] != "written":
        print(f"交易日: {r['trade_date']} | {r['action']} {r.get('skipped', '')}（--force 覆盖）")
        return 0
    print(f"交易日: {r['trade_date']} | 全市场涨停 {r['market_limit_up']} 跌停 {r['market_limit_down']}（不计 ST/新股/停牌）")
    print(f"涨停题材 {r['sectors_with_limit_up']} 个 / 明细 {r['detail_rows']} 行 / 连板梯队 {r['ladder_rows']} 只 / 龙头高度 {r['leader_height']} | 成分行 {r['members_seen']}")
    return 0


def cmd_compute_market_overview_local(args) -> int:
    from .sync.compute_local_stats import compute_market_overview_local

    r = compute_market_overview_local(args.trade_date, force=args.force)
    if r["action"] != "written":
        print(f"交易日: {r['trade_date']} | {r['action']} source={r.get('source')}（--force 覆盖）")
        return 0
    print(f"交易日: {r['trade_date']} | 沪深成交额 {r['total_amount']} 亿 | 涨家数 {r['advancers']} | 涨停 {r['limit_up']} 跌停 {r['limit_down']}")
    print(f"MA20 {r['amount_ma20']} 量能比 {r['volume_ratio']}% | 前三行业 {r['top3']} 合计 {r['top3_ratio']}% | 20日新高 {r['stock_high_20d']} | 周均线 {r['sh_week_ma']}")
    return 0


def cmd_compute_market_editorial_local(args) -> int:
    from .sync.compute_local_stats import compute_market_editorial_local

    r = compute_market_editorial_local(args.trade_date, force=args.force)
    if r["action"] != "written":
        print(f"交易日: {r['trade_date']} | {r['action']} strength_source={r.get('strength_source')}（--force 覆盖）")
        return 0
    print(f"交易日: {r['trade_date']} | 强度(涨幅前5% {r['top_k']} 只) 均涨 {r['strength_avg_pct']}% 额 {r['strength_amount']} 亿 占比 {r['strength_amount_pct']}% "
          f"边际 {r['strength_marginal_pct']} → {r['strength_status']} | 量能状态 {r['volume_state']} | 冰点 {r['ice_level']}")
    return 0


def cmd_compute_stock_high_local(args) -> int:
    from .sync.compute_local_stats import compute_stock_high_local

    r = compute_stock_high_local(args.trade_date, force=args.force)
    if r["action"] != "written":
        print(f"交易日: {r['trade_date']} | {r['action']} {r.get('skipped', '')}（--force 覆盖）")
        return 0
    print(f"交易日: {r['trade_date']} | 新高名单 {r['rows']} 只 | {r['by_label']}")
    return 0


def cmd_train_market_stage(args) -> int:
    from .models.market_stage import ARTIFACT, train

    art = train(out_path=args.out or ARTIFACT)
    cv = art["cv"]
    print(f"训练 {art['train_days']} 日 {art['train_range'][0]}~{art['train_range'][1]} | 分块{cv['folds']}折 精确 {cv['exact_acc_mean']:.1%} 粗粒度 {cv['coarse_acc_mean']:.1%} "
          f"| 各块精确 {[round(x, 2) for x in cv['exact_acc_by_block']]} | 对照手写规则 37%/58%")
    print(f"产物: {args.out or ARTIFACT}")
    return 0


def cmd_compute_market_stage_local(args) -> int:
    from .models.market_stage import predict_stage

    r = predict_stage(args.trade_date, write=not args.dry_run)
    if r["action"] == "kept-fupanhui-label":
        print(f"交易日: {r['trade_date']} | 已有 fupanhui 标签 {r['market_stage']}，不覆盖")
        return 0
    top = sorted(r["proba"].items(), key=lambda kv: -kv[1])[:3]
    print(f"交易日: {r['trade_date']} | 周期阶段(自训 v1) {r['market_stage']} 第{r['stage_day']}天 置信 {r['confidence']} | argmax {r['argmax']} | 前一日 {r['prev_stage']} | top3 {top}")
    return 0


def cmd_compute_mainline_local(args) -> int:
    from .sync.compute_local_stats import compute_mainline_local

    r = compute_mainline_local(args.trade_date, force=args.force, topk=args.topk)
    if r["action"] != "written":
        print(f"交易日: {r['trade_date']} | {r['action']} {r.get('skipped', '')}（--force 覆盖）")
        return 0
    print(f"交易日: {r['trade_date']} | 主线题材(人气值 v1) {r['themes']} 分 {r['theme_scores']} | 核心板块 {r['sector_rows']} 行 / 主线个股 {r['stock_rows']} 只")
    return 0


def cmd_compute_core_stock_local(args) -> int:
    from .sync.compute_local_stats import compute_core_stock_local

    r = compute_core_stock_local(args.trade_date, force=args.force, topn=args.topn)
    if r["action"] != "written":
        print(f"交易日: {r['trade_date']} | {r['action']} {r.get('skipped', '')}（--force 覆盖）")
        return 0
    print(f"交易日: {r['trade_date']} | 核心个股(复刻 成交额前{args.topn}) {r['rows']} 行 | 榜首 {r['top1']} | "
          f"入围线 {r['amount_cut']} 亿 | 申万一级已填 {r['sw_l1_filled']}/{r['rows']}")
    return 0


def cmd_compute_core_leader_local(args) -> int:
    from .sync.compute_local_stats import CORE_LEADER_AUTH_WEIGHT, compute_core_leader_local

    weight = CORE_LEADER_AUTH_WEIGHT if args.auth_weight is None else args.auth_weight
    r = compute_core_leader_local(args.trade_date, force=args.force, topn=args.topn,
                                  per_theme=args.per_theme, auth_weight=weight,
                                  allow_no_kb=args.allow_no_kb)
    if r["action"] != "written":
        print(f"交易日: {r['trade_date']} | {r['action']} {r.get('skipped', '')}（--force 覆盖）")
        return 0
    print(f"交易日: {r['trade_date']} | 核心个股(自家 主线×正宗×人气) {r['rows']}/{r['pool']} 只 | "
          f"知识库 {r['kb_status']} 正宗权重 {r['auth_weight']} | 有正宗证据 {r['authentic']} 只 | "
          f"分题材 {r['by_theme']}")
    print(f"  前 5: {r['top']}")
    return 0


def cmd_sync_sector_daily_local(args) -> int:
    from .sync.sync_local_sector_daily import brief, sync_sector_daily_local

    s = sync_sector_daily_local(args.trade_date, prefer_payload=not args.no_payload)
    print(f"交易日: {s['trade_date']} | snapshot={s['snapshot_id'][:12]}")
    print(f"写入 {s['rows_written']} 行 | 涨幅官方 {s['pct_official']} / 等权 {s['pct_eqw']}")
    print(f"边际量基准日: {s['prev_date']} (是前一交易日: {s['prev_is_previous_trading_day']}) | 代理昨额板块: {s['prev_proxied']}")
    if s["prev_proxied_codes"]:
        print(f"  代理: {', '.join(s['prev_proxied_codes'][:10])}")
    print(brief(s))
    return 0


def cmd_reconcile_sector_daily(args) -> int:
    from .sync.sync_local_sector_daily import reconcile_sector_daily

    r = reconcile_sector_daily(args.trade_date, sample=args.sample, seed=args.seed)
    print(f"交易日: {r['trade_date']} | 抽样 {r['sampled']} | 复盘会返回 {r['provider_rows']} | 可比 {r['compared']}")
    print(f"成交额相对误差 中位 {r['amount_relerr_median']} 最大 {r['amount_relerr_max']}")
    print(f"涨幅绝对误差 中位 {r['pct_abs_err_median']} p95 {r['pct_abs_err_p95']} | 符号不一致 {r['pct_sign_mismatch']}")
    print(f"边际量绝对误差 中位 {r['diff_ratio_abs_err_median']} p95 {r['diff_ratio_abs_err_p95']}")
    print(f"双红翻转: {r['shuanghong_flips'] or '无'}")
    print(f"RESULT: {'PASS' if r['ok'] else 'FAIL'}")
    return 0 if r["ok"] else 2


def cmd_sync_dragon_seats_akshare(args) -> int:
    from .sync.sync_akshare_dragon_seats import sync_dragon_seats_akshare

    s = sync_dragon_seats_akshare(args.trade_date, sleep=args.sleep)
    print(f"交易日: {args.trade_date} | 榜单 {s['stocks']} 只 | 写入席位行 {s['rows']}")
    if s.get("errors"):
        print(f"失败 {len(s['errors'])}: {list(s['errors'].items())[:5]}")
    if s.get("note"):
        print(s["note"])
    return 0 if s["rows"] else 2


def cmd_registry_check(_args) -> int:
    from .consumption_registry import load_registry, summarize, validate_registry

    reg = load_registry()
    problems = validate_registry(reg)
    print(summarize(reg))
    if problems:
        print("registry 校验未通过:")
        for p in problems:
            print(f"  - {p}")
        return 2
    print("registry 校验通过（档位/表名/计划步骤归属）")
    return 0


def cmd_sync_limit_advance_feishu(_args) -> int:
    from .sync.sync_feishu_limit_advance import sync_limit_advance

    s = sync_limit_advance()
    print(f"连板晋级表 {s['table_id']}: 记录 {s['records']} 行, 股票 {s['stocks']}")
    print(f"展开写入 (stock×date 存在性): {s['rows_written']} 行")
    if s["unresolved_cols"]:
        print(f"无法对齐交易日的列 {len(s['unresolved_cols'])}: {s['unresolved_cols']}")
    print(f"fact_limit_advance_presence: {s['table_total']} 行, {s['table_dates']} 交易日, "
          f"{s['table_stocks']} 股 ({s['date_min']}~{s['date_max']})")
    return 0


def cmd_sync_limit_advance(args) -> int:
    from .sync.sync_fupanhui_limit_advance_daily import sync_fupanhui_limit_advance

    s = sync_fupanhui_limit_advance(
        trade_date=args.trade_date,
        min_boards=args.min_boards,
    )
    print(f"交易日: {s['trade_date']} | 最高连板: {s['max_limit_days']} | 晋级股写入: {s['rows_written']} 行")
    print(f"层级数: {s['levels']} | 跳过非晋级状态: {s['skipped_status']} | 跳过低于{args.min_boards}板: {s['skipped_boards']}")
    print(f"fact_limit_advance_daily: {s['table_total']} 行, {s['table_dates']} 交易日, "
          f"{s['table_stocks']} 股 ({s['date_min']}~{s['date_max']})")
    print(f"fact_limit_advance_presence: {s['presence_total']} 行, {s['presence_dates']} 交易日, "
          f"{s['presence_stocks']} 股 ({s['presence_date_min']}~{s['presence_date_max']})")
    return 0


def cmd_sync_limit_advance_range(args) -> int:
    from .sync.sync_fupanhui_limit_advance_daily import sync_fupanhui_limit_advance_range

    s = sync_fupanhui_limit_advance_range(
        start_date=args.start_date,
        end_date=args.end_date,
        days=args.days,
        min_boards=args.min_boards,
        refresh=args.refresh,
        sleep=args.sleep,
    )
    print(f"目标交易日: {s['requested_dates']} 个 | 来源: {s['date_source']}")
    print(f"同步: {s['synced_dates']} | 跳过: {s['skipped_dates']} | 失败: {s['failed_dates']}")
    print(f"本次写入连板晋级: {s['total_rows_written']} 行")
    print(f"fact_limit_advance_daily: {s['table_total']} 行, {s['table_dates']} 交易日, "
          f"{s['table_stocks']} 股 ({s['date_min']}~{s['date_max']})")
    print(f"fact_limit_advance_presence: {s['presence_total']} 行, {s['presence_dates']} 交易日, "
          f"{s['presence_stocks']} 股 ({s['presence_date_min']}~{s['presence_date_max']})")
    if s["skipped"]:
        print("跳过日期: " + ", ".join(f"{x['trade_date']}({x['existing_rows']}行)" for x in s["skipped"][:20]))
    if s["failures"]:
        print("失败日期: " + ", ".join(f"{x['trade_date']}({x['error']})" for x in s["failures"][:10]))
    return 1 if s["failures"] else 0


def cmd_sync_stock_daily(args) -> int:
    from .sync.sync_mootdx_stock_daily import sync_fact_stock_daily

    stats = sync_fact_stock_daily(
        start_date=args.start_date,
        offset=args.offset,
        limit=args.limit,
        only_missing=not args.refresh,
        sleep=args.sleep,
        qfq=args.qfq,
        timeout=args.timeout,
        progress_every=args.progress_every,
        end_date=args.end_date,
        ohlc_only=args.ohlc_only,
        skip=args.skip,
    )
    mode = " | 模式: 只补 OHLC" if args.ohlc_only else ""
    print(f"起始日: {stats['start_date']}{' ~ ' + args.end_date if args.end_date else ''} | 全A股池: {stats['universe']}{mode}")
    print(f"本次抓取: {stats['processed']} 只 | 写入行: {stats['rows_written']}")
    print(f"已覆盖个股: {stats['stocks_done']}/{stats['universe']} | 剩余: {stats['stocks_remaining']}")
    print(f"fact_stock_daily: {stats['table_total']} 行, {stats['distinct_stocks']} 股, "
          f"{stats['distinct_dates']} 交易日 ({stats['date_min']}~{stats['date_max']})")
    if stats["failures"]:
        print(f"失败 {len(stats['failures'])}: " + ", ".join(c for c, _ in stats['failures'][:10]))
    return 0


def cmd_fill_stock_daily_fallback(args) -> int:
    from .sync.fill_stock_daily_fallback import fill_stock_daily_fallback

    stats = fill_stock_daily_fallback(
        trade_date=args.trade_date,
        ma_window=args.ma_window,
        recompute_deviation=not args.no_deviation,
    )
    print(f"交易日: {stats['trade_date']} | 源板块成分行: {stats['source_rows']}")
    print(f"fact_stock_daily 当日: {stats['stock_rows']} 行 | source={stats.get('source')}")
    if stats.get("deviation"):
        d = stats["deviation"]
        print(f"上证均线复算: sh_week_ma={d['sh_week_ma']} sh_deviation_pct={d['sh_deviation_pct']} ({d['note']})")
    if stats.get("note"):
        print(f"提示: {stats['note']}")
    return 0 if stats["stock_rows"] else 1
def cmd_sync_stock_daily_snapshot(args) -> int:
    from .sync.sync_eastmoney_stock_snapshot import sync_fact_stock_daily_snapshot

    stats = sync_fact_stock_daily_snapshot(
        trade_date=args.trade_date,
        page_size=args.page_size,
        allow_misdated=args.allow_misdated,
    )
    print(f"交易日: {stats['trade_date']} | 快照实际日期: {stats['snapshot_trade_date']} | 来源: {stats['source']}")
    print(f"快照拉取: {stats['fetched']} 行 | 写入: {stats['rows_written']} | 跳过: {stats['skipped']}")
    print(f"当日入库: {stats['day_rows']} 股")
    print(f"fact_stock_daily: {stats['table_total']} 行, {stats['distinct_stocks']} 股, "
          f"{stats['distinct_dates']} 交易日 ({stats['date_min']}~{stats['date_max']})")
    return 0


def _daily_preflight_or_exit() -> int | None:
    """开跑前拦下「这个环境注定跑不完」的情况，exit 2 并说清缺什么、会挂哪几步。

    只挡 CLI 入口，不进 run_daily_update——测试与编排层直接调函数层，
    无 CDP 的环境不该被误拦。2026-08-12 实测：akshare 缺失直到第 4 步才暴露，
    整轮 7 分钟白跑；这里把同一事实提前到第 0 秒。
    """
    from .sync.sync_daily_full import preflight_daily_update

    verdict = preflight_daily_update()
    if verdict["ok"]:
        return None
    print("环境预检不通过（fail closed，未发起任何抓取）：")
    for problem in verdict["problems"]:
        print(f"  ✗ {problem}")
    return 2


def _refuse_production_write(direct: bool) -> int | None:
    from .write_path import production_write_blocked

    reason = production_write_blocked(direct)
    if reason is None:
        return None
    print(reason)
    return 2


def cmd_daily_update(args) -> int:
    from .sync.sync_daily_full import run_daily_update
    from .write_path import write_direct_receipt

    blocked = _daily_preflight_or_exit()
    if blocked is not None:
        return blocked
    refused = _refuse_production_write(bool(getattr(args, "direct", False)))
    if refused is not None:
        return refused
    result = run_daily_update(
        trade_date=args.trade_date,
        chart_table=args.chart_table,
        skip_long=args.skip_long,
        with_chart=not args.no_chart,
        stock_source=args.stock_source,
    )
    if getattr(args, "direct", False):
        receipt = write_direct_receipt(
            trade_date=str(result.get("trade_date") or args.trade_date or ""),
            command="daily-update --direct",
            ok=bool(result.get("ok")),
        )
        print(f"direct 收据: {receipt}")
    print(f"交易日: {result['trade_date']} | 日更状态: {'OK' if result['ok'] else 'CHECK'}")
    for step in result["steps"]:
        status = "OK" if step["ok"] else "FAIL"
        print(f"[{status}] {step['name']}")
        if not step["ok"]:
            print(f"  {step['error']}")
    v = result["validation"]
    print(f"质检: {'OK' if v['ok'] else 'CHECK'}")
    if v["missing_fields"]:
        print("缺字段: " + ", ".join(v["missing_fields"]))
    for t in v["tables"]:
        status = "OK" if t["ok"] else "MISS"
        print(f"  [{status}] {t['table']} max={t['max_date']} rows={t['rows']}")
    failed_steps = [step["name"] for step in result["steps"] if not step["ok"]]
    validation_ok = bool(v["ok"])
    structured_status = "PASS" if result["ok"] else ("WARN" if validation_ok else "FAIL")
    _write_status_json(args.status_json, {
        "status": structured_status,
        "ok": bool(result["ok"]),
        "validation_ok": validation_ok,
        "recoverable": structured_status == "WARN",
        "failed_steps": failed_steps,
        "trade_date": str(result["trade_date"]),
    })
    return 0 if result["ok"] else (1 if validation_ok else 2)


def cmd_daily_review(args) -> int:
    from .reports.daily_review import build_daily_review

    result = build_daily_review(
        trade_date=args.trade_date,
        output_path=args.output,
        chart_path=args.chart_output,
        start_date=args.start_date,
    )
    print(f"交易日: {result['trade_date']}")
    print(f"报告: {result['output_path']}")
    print(f"真本源 JSON: {result['json_path']}")
    if result["chart_path"]:
        print(f"图表: {result['chart_path']}")
    return 0


def cmd_daily_full(args) -> int:
    """staging 编排入口: 同步全程不持有生产库写锁 (bookgap S7)。

    真正的管道跑在 daily-full-exec 子进程里 (env 重定向到 staging 副本),
    这里只负责预检与编排结果的出口语义。rc: 0=全绿并已换名, 1=有失败步
    但按现状口径落库 (已换名), 2=fail closed (生产库未动)。
    """
    from .sync.sync_daily_full import run_daily_full_staged

    blocked = _daily_preflight_or_exit()
    if blocked is not None:
        return blocked
    result = run_daily_full_staged(
        trade_date=args.trade_date,
        chart_table=args.chart_table,
        skip_long=args.skip_long,
        stock_source=args.stock_source,
    )
    if result["swapped"]:
        print(f"全流程状态: {'OK' if result['rc'] == 0 else 'CHECK'} | 已原子换库")
    else:
        print(f"全流程状态: BLOCKED | 生产库未动 | {result['reason']}")
    return result["rc"]


def cmd_daily_full_exec(args) -> int:
    """(内部) daily-full 的子进程管道入口, 由 run_daily_full_staged 拉起。

    与旧 daily-full 完全同构 (跑管道+三道门+报告并打印), 差别只有:
    不做环境预检 (父进程已做), 并把结构化结果写 --status-json 交回父进程。
    """
    from .sync.sync_daily_full import run_daily_full

    refused = _refuse_production_write(bool(getattr(args, "direct", False)))
    if refused is not None:
        return refused
    result = run_daily_full(
        trade_date=args.trade_date,
        chart_table=args.chart_table,
        skip_long=args.skip_long,
        stock_source=args.stock_source,
    )
    print(f"交易日: {result['trade_date']} | 全流程状态: {'OK' if result['ok'] else 'CHECK'}")
    for step in result["update"]["steps"]:
        status = "OK" if step["ok"] else "FAIL"
        elapsed = step.get("elapsed_s")
        suffix = f" ({elapsed}s)" if elapsed is not None else ""
        print(f"[{status}] {step['name']}{suffix}")
        if not step["ok"]:
            print(f"  {step['error']}")
    cross_day = result["cross_day_gate"]
    print(f"跨日质检: {'OK' if cross_day['ok'] else 'FAIL'} | {cross_day['brief']}")
    if result["review"]:
        print(f"报告: {result['review']['output_path']}")
        if result["review"].get("chart_path"):
            print(f"图表: {result['review']['chart_path']}")
    else:
        print("报告: 未生成（质量门未通过）")
    _write_status_json(args.status_json, {
        "trade_date": str(result["trade_date"]),
        "ok": bool(result["ok"]),
        "validation_ok": bool(result["update"]["validation"]["ok"]),
        "cross_day_ok": bool(cross_day["ok"]),
        "sector_gate_ok": bool(result["sector_gate"]["ok"]),
        "steps": [
            {
                "name": s["name"],
                "ok": bool(s["ok"]),
                "elapsed_s": s.get("elapsed_s"),
            }
            for s in result["update"]["steps"]
        ],
    })
    return 0 if result["ok"] else 1


def cmd_weighted_gainers(args) -> int:
    from .query import weighted_gainers

    res = weighted_gainers(args.start, args.end, top=args.top, min_amount=args.min_amount)
    _print_interval_stock_rank(res, args.top, "加权涨幅排行", "weighted_gain")
    return 0


def cmd_interval_gainers(args) -> int:
    from .query import interval_gainers

    res = interval_gainers(args.start, args.end, top=args.top, min_amount=args.min_amount)
    _print_interval_stock_rank(res, args.top, "区间涨幅排行", "interval_gain")
    return 0


def _fmt_num(value, digits=2):
    if value is None:
        return "-"
    return f"{float(value):.{digits}f}"


def _short_text(value, max_len=18):
    text = str(value or "-").replace("\x00", "")
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


def _print_interval_stock_rank(res, top, title, sort_field):
    print(f"{title} {res['start']}~{res['end']} (实际数据 {res['actual_start']}~{res['actual_end']}, "
          f"日均成交≥{res['min_amount']}亿, Top{top})")
    print(f"题材/申万映射日期: {res.get('metadata_date') or '-'} | UP偏离度: 最新本地日线")
    print("| 排名 | 代码 | 简称 | 申万一级 | 题材 | 日均成交(亿) | 区间涨幅% | 加权涨幅 | UP偏离% |")
    print("|---:|---|---|---|---|---:|---:|---:|---:|")
    for i, s in enumerate(res["stocks"], 1):
        name = _short_text(s["stock_name"], 12)
        sectors = _short_text(s.get("sectors"), 18)
        sw_l1 = _short_text(s.get("sw_l1"), 12)
        print(f"| {i} | {s['stock_ts_code']} | {name} | {sw_l1} | {sectors} | "
              f"{_fmt_num(s['avg_amount'], 1)} | {_fmt_num(s['interval_gain'])} | "
              f"{_fmt_num(s['weighted_gain'])} | {_fmt_num(s.get('up_deviation_pct'))} |")
    if not res["stocks"]:
        print("  (无数据, 先运行 sync-stock-daily 回补该区间)")


def cmd_check(_args) -> int:
    from .query import health

    h = health()
    ds = h["dim_sector"]
    print(f"[dim_sector] {ds['total']} 板块, 映射申万一级 {ds['mapped_sw_l1']}")
    sd = h["fact_sector_daily"]
    print(f"[fact_sector_daily] {sd['rows']} 行, {sd['dates']} 交易日 "
          f"({sd['date_min']}~{sd['date_max']}), 空diff {sd['null_diff_ratio']}, 空sw_l1 {sd['null_sw_l1']}")
    ss = h["fact_sector_stock_daily"]
    print(f"[fact_sector_stock_daily] {ss['rows']} 行, {ss['dates']} 交易日, "
          f"{ss['sectors']} 板块, {ss['stocks']} 个股, 空code {ss['null_stock_code']}, 空sw_l1 {ss['null_sw_l1']}")
    md = h["fact_market_daily"]
    print(f"[fact_market_daily] {md['rows']} 行, {md['dates']} 交易日 "
          f"({md['date_min']}~{md['date_max']}), 空成交额 {md['null_total_amount']}")
    sk = h["fact_stock_daily"]
    print(f"[fact_stock_daily] {sk['rows']} 行, {sk['stocks']} 股, {sk['dates']} 交易日 "
          f"({sk['date_min']}~{sk['date_max']}), 空close {sk['null_close']}")
    if "coverage_latest" in h:
        c = h["coverage_latest"]
        print(f"[最新日 {c['date']}] 有成分股板块 {c['sectors_with_stocks']}/{c['dim_sector_total']}")
    return 0


def cmd_check_daily(args) -> int:
    import json as _json

    from .quality import check_daily

    res = check_daily(trade_date=args.trade_date, window=args.window, plan=args.plan)
    print(f"跨日质检 @{res['trade_date']} (日历窗口={args.window}" + (f", plan={args.plan}" if args.plan else "") + ")")
    for g in res["gaps"]:
        print(f"  [\u65ad\u6863] {g['table']}: {', '.join(g['missing_dates'])}" + (f" ({g['note']})" if g.get("note") else ""))
    for a in res["row_anomalies"]:
        print(f"  [\u884c\u6570\u5f02\u5e38] {a['table']}: {a['note']}")
    for v in res["range_violations"]:
        print(f"  [\u503c\u57df] {v['field']}={v['value']} {v['note']}")
    print(f"RESULT: {'PASS' if res['ok'] else 'FAIL'} | {res['brief']}")
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"json -> {out}")
    return 0 if res["ok"] else 2


def cmd_sector_stocks(args) -> int:
    from .query import sector_stocks

    res = sector_stocks(args.sector, trade_date=args.trade_date, top=args.top, order_by=args.order_by)
    print(f"{res['sector']} 成分股 @{res['trade_date']} (按{args.order_by}排序, Top{args.top})")
    for s in res["stocks"]:
        print(f"  {s['stock_name']:<8} {s['stock_ts_code']:<11} 涨{s['pct_chg']} 额{s['amount']}亿 "
              f"5日{s['pct_chg_5d']} {s['sw_industry']} 资金1d{s['fund_flow_1d']}")
    if not res["stocks"]:
        print("  (无数据, 检查板块名/代码或先同步该日成分股)")
    return 0


def cmd_stock_sectors(args) -> int:
    from .query import stock_sectors

    res = stock_sectors(args.stock, trade_date=args.trade_date)
    print(f"{res['stock']} 所属板块 @{res['trade_date']} (共{len(res['sectors'])}个)")
    for s in res["sectors"]:
        print(f"  {s['sector_name']:<12} ({s['sw_l1']}) 板块涨{s['pct_chg']} 额{s['amount']}亿")
    if not res["sectors"]:
        print("  (无数据, 检查个股名/代码或先同步该日成分股)")
    return 0


def _fmt_num(value, digits=2):
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def cmd_stock_highs(args) -> int:
    from .query import stock_highs

    res = stock_highs(
        trade_date=args.trade_date,
        period=args.period,
        top=args.top,
        sector_top=args.sector_top,
    )
    suffix = f" | 周期={args.period}" if args.period else ""
    print(f"新高个股 @{res['trade_date']}{suffix} | 个股 {res['stock_count']} 只 | 一级行业 {res['group_count']} 个")
    if res["market_counts"]:
        print("市场新高家数: " + ", ".join(f"{k}={v}" for k, v in res["market_counts"].items()))
    if not res["groups"]:
        print("  (无数据, 请先运行 sync-stock-high 回填该交易日)")
        return 0
    for group in res["groups"]:
        sectors = "、".join(group["top_sectors"][:args.sector_top]) if group["top_sectors"] else "-"
        print(f"\n## {group['sw_l1']} | 新高 {group['count']} 只 | 历史新高 {group['history_count']} 只 | 代表板块: {sectors}")
        for stock in group["stocks"][:args.top]:
            period_labels = "、".join(
                p.get("label") or p.get("period")
                for p in stock["high_periods"]
                if isinstance(p, dict)
            ) or stock["primary_high_label"]
            line = (
                f"  {stock['stock_name']:<8} {stock['stock_ts_code']:<11} "
                f"{period_labels} 涨{_fmt_num(stock['pct_chg'])}% "
                f"10日{_fmt_num(stock['pct_chg_10d'])}% "
                f"额{_fmt_num(stock['amount'])}亿 "
                f"市值{_fmt_num(stock['market_cap'])}亿"
            )
            if args.with_sectors:
                names = [s["sector_name"] for s in stock["sectors"] if s.get("sector_name")]
                if names:
                    line += " | 板块: " + "、".join(names[:args.sector_top])
            print(line)
    return 0


def cmd_limit_heat(args) -> int:
    from .query import limit_heat

    res = limit_heat(
        trade_date=args.trade_date,
        theme=args.theme,
        top=args.top,
        with_stocks=args.with_stocks,
        stock_top=args.stock_top,
    )
    suffix = f" | 题材={args.theme}" if args.theme else ""
    print(f"涨停热力 @{res['trade_date']}{suffix} | 题材 {res['count']} 个")
    if not res["heats"]:
        print("  (无数据, 请先运行 sync-limit-heat 回填该交易日)")
        return 0
    for item in res["heats"]:
        fd_yi = (item["fd_amount"] or 0) / 10000
        print(
            f"\n{item['rank']}. {item['sector_name']} {item['sector_ts_code']} | "
            f"涨停 {item['limit_up_count']}/{item['total_count']} | "
            f"占全市场 {item['market_share']}% | 封单 {fd_yi:.2f}亿"
        )
        names = [s.get("name") for s in item["top_stocks"] if isinstance(s, dict) and s.get("name")]
        if names:
            print("  代表股: " + "、".join(names))
        if args.with_stocks:
            for stock in item["stocks"]:
                sfd = (stock["fd_amount"] or 0) / 10000
                print(
                    f"  {stock['stock_name']:<8} {stock['stock_ts_code']:<11} "
                    f"{stock['limit_times'] or '-'}板 涨{_fmt_num(stock['pct_chg'])}% "
                    f"封单{sfd:.2f}亿 {stock['sw_l1'] or '-'} "
                    f"{stock['leader_plate'] or ''}"
                )
    return 0


def cmd_advancers_extrema(args) -> int:
    from .query import advancers_extrema

    res = advancers_extrema(delta=args.delta, smooth=args.smooth, smooth_mode=args.smooth_mode)
    base = f"MA{res['smooth']}({args.smooth_mode})" if res["smooth"] > 1 else "裸涨家数"
    print(f"涨家数波峰/波谷 (ZigZag on {base}, delta={res['delta']}, "
          f"{res['n_days']}个交易日): 波峰{res['peaks']} 波谷{res['troughs']}")
    for p in res["pivots"]:
        sm = f" MA{res['smooth']}≈{p['smoothed']}" if p["smoothed"] is not None else ""
        sw = f" 摆幅{p['swing_from_prev']:+d}" if p["swing_from_prev"] is not None else ""
        print(f"  {p['date']} {p['type']} 涨家数{p['advancers']}{sm}{sw}")
    return 0


def cmd_sw_l1_signal_peaks(args) -> int:
    from .query import sw_l1_signal_peaks

    res = sw_l1_signal_peaks(
        trade_date=args.trade_date,
        high_period=args.high_period,
        window=args.window,
        ratio_threshold=args.ratio,
        min_limit_count=args.min_limit_count,
        min_high_count=args.min_high_count,
        top=args.top,
    )
    print(
        f"申万一级涨停/新高波峰 @{res['trade_date']} | "
        f"新高周期={res['high_period']} | "
        f"涨停窗口={len(res['limit_history_dates'])}/{res['window']} | "
        f"新高窗口={len(res['high_history_dates'])}/{res['window']} | "
        f"阈值={res['ratio_threshold']}x"
    )
    for title, rows in (("涨停波峰", res["limit_rows"]), ("新高波峰", res["high_rows"])):
        print(f"\n## {title}")
        if not rows:
            print("  (无数据)")
            continue
        for row in rows:
            flag = "触发" if row["is_peak"] else "未触发"
            ratio = "∞" if row["ratio"] == float("inf") else _fmt_num(row["ratio"])
            print(
                f"  {flag} {row['sw_l1']:<8} "
                f"当日{row['current_count']:>3} | "
                f"20日均值{row['avg_20d']:.2f} | "
                f"倍数{ratio} | "
                f"最低数{row['min_count']}"
            )
    return 0


def cmd_strong_subtheme_trace(args) -> int:
    from .query import strong_subtheme_trace

    res = strong_subtheme_trace(
        start_date=args.start_date,
        end_date=args.end_date,
        days=args.days,
        high_period=args.high_period,
        window=args.window,
        ratio_threshold=args.ratio,
        min_limit_count=args.min_limit_count,
        min_high_count=args.min_high_count,
        top=args.top,
    )
    print(
        f"强细分信号回溯 {res['start_date']}~{res['end_date']} | "
        f"交易日{len(res['dates'])} | 新高周期={res['high_period']} | "
        f"波峰={res['ratio_threshold']}x"
    )
    sections = (
        ("双红题材首日", res["double_red_first"]),
        ("多周期共振首日", res["resonance_first"]),
        ("申万一级波峰首日", res["peak_first"]),
    )
    for title, rows in sections:
        print(f"\n## {title}")
        if not rows:
            print("  (无数据)")
            continue
        for row in rows[:args.top]:
            if "sector_name" in row:
                print(
                    f"  {row['trade_date']} {row['sector_name']} "
                    f"({row.get('sw_l1') or '-'}) "
                    f"涨{_fmt_num(row.get('pct_chg'))}% "
                    f"边际{_fmt_num(row.get('diff_ratio'))} "
                    f"额{_fmt_num(row.get('amount'))}亿"
                )
            else:
                ratio = "∞" if row["ratio"] == float("inf") else _fmt_num(row["ratio"])
                label = "涨停波峰" if row["signal"] == "limit_up_peak" else "新高波峰"
                print(
                    f"  {row['trade_date']} {label} {row['sw_l1']} "
                    f"当日{row['current_count']} "
                    f"均值{row['avg_20d']:.2f} "
                    f"倍数{ratio}"
                )
    return 0


def cmd_top_sectors(args) -> int:
    from .query import top_sectors

    res = top_sectors(trade_date=args.trade_date, top=args.top, order_by=args.order_by)
    print(f"板块排行 @{res['trade_date']} (按{res['order_by']}排序, Top{args.top})")
    for s in res["sectors"]:
        print(f"  {s['sector_name']:<12} ({s['sw_l1']}) 涨{s['pct_chg']} 边际{s['diff_ratio']} 额{s['amount']}亿")
    return 0


def cmd_info(_args) -> int:
    if not DB_PATH.exists():
        print(f"数据库不存在: {DB_PATH}", file=sys.stderr)
        print("请先运行: python3 -m market_feature_store.cli init", file=sys.stderr)
        return 1
    con = connect(read_only=True)
    try:
        tables = list_tables(con)
        print(f"数据库: {DB_PATH}")
        print(f"表数量: {len(tables)}")
        for t in tables:
            cnt = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            print(f"  {t}: {cnt}")
    finally:
        con.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="market_feature_store",
        description=f"Market Feature Store CLI v{__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="初始化 schema (幂等)").set_defaults(func=cmd_init)
    sub.add_parser("info", help="查看库内表与行数").set_defaults(func=cmd_info)

    p_preview = sub.add_parser(
        "sector-universe-preview",
        help="只读迁移预览: 遗留行数/预计退役/代际分母/目标快照, 不写库不调 provider",
    )
    p_preview.add_argument(
        "--trade-date", default=None, help="目标交易日 YYYY-MM-DD, 留空取最新已发布代际"
    )
    p_preview.set_defaults(func=cmd_sector_universe_preview)

    p_sectors = sub.add_parser("sync-sectors", help="同步复盘会板块清单到 dim_sector")
    p_sectors.add_argument("--trade-date", default=None, help="交易日期 YYYY-MM-DD, 留空取最新")
    p_sectors.set_defaults(func=cmd_sync_sectors)

    p_sd = sub.add_parser("sync-sector-daily", help="同步板块日行情+边际量到 fact_sector_daily")
    p_sd.add_argument("--trade-date", default=None, help="截止交易日 YYYY-MM-DD, 留空取最新")
    p_sd.add_argument(
        "--days",
        type=int,
        default=25,
        help="provider 回看窗口（只持久化目标日）, 默认25",
    )
    p_sd.set_defaults(func=cmd_sync_sector_daily)

    p_sdr = sub.add_parser("sync-sector-daily-range", help="批量同步板块日行情+边际量到 fact_sector_daily")
    p_sdr.add_argument("--start-date", default=None, help="起始交易日 YYYY-MM-DD")
    p_sdr.add_argument("--end-date", default=None, help="结束交易日 YYYY-MM-DD；--days 模式下可作为截止日")
    p_sdr.add_argument("--days", type=int, default=None, help="从 fact_market_daily 取最近 N 个交易日")
    p_sdr.add_argument(
        "--chunk-days",
        type=int,
        default=15,
        help="每组逐日精确同步的日期数, 默认15",
    )
    p_sdr.add_argument("--refresh", action="store_true", help="不跳过已同步日期, 强制重刷")
    p_sdr.add_argument("--sleep", type=float, default=0.2, help="批次间隔秒数, 默认0.2")
    p_sdr.set_defaults(func=cmd_sync_sector_daily_range)

    p_ss = sub.add_parser("sync-sector-stocks", help="批量回补成分股快照到 fact_sector_stock_daily")
    p_ss.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取最新")
    p_ss.add_argument("--sector", default=None, help="只抓单个板块 (代码或名称)")
    p_ss.add_argument("--limit", type=int, default=None, help="本次最多抓多少个板块")
    p_ss.add_argument("--refresh", action="store_true", help="不跳过已抓板块, 强制重抓")
    p_ss.add_argument("--sleep", type=float, default=0.3, help="chunk 间隔秒数, 默认0.3")
    p_ss.add_argument("--chunk", type=int, default=10, help="单次 eval 并发抓取的板块数, 默认10")
    p_ss.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help=(
            "单板块最多重试次数, 默认3。准入规则变更后需要重新驱动已耗尽重试的"
            "板块时调高它——这是正规入口, 不要手改 DuckDB"
        ),
    )
    p_ss.set_defaults(func=cmd_sync_sector_stocks)

    p_idx = sub.add_parser("sync-index-daily", help="同步上证指数点位/涨跌幅到 fact_market_daily")
    p_idx.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD；指定后只写该日")
    p_idx.add_argument("--start-date", default=None, help="起始日期 YYYY-MM-DD")
    p_idx.add_argument("--end-date", default=None, help="结束日期 YYYY-MM-DD；留空取 fact_market_daily 最新日")
    p_idx.add_argument("--symbol", default="sh000001", help="AkShare 指数代码, 默认 sh000001")
    p_idx.set_defaults(func=cmd_sync_index_daily)

    p_sw = sub.add_parser("sync-sw-l1-daily", help="同步申万一级行业指数涨跌幅与复盘会成交占比")
    p_sw.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取 fact_market_daily 最新日")
    p_sw.add_argument("--days", type=int, default=20, help="回看交易日数量, 默认20")
    p_sw.set_defaults(func=cmd_sync_sw_l1_daily)

    p_ms = sub.add_parser("sync-market-strength", help="同步复盘会市场强度到 fact_market_daily")
    p_ms.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取复盘会最新")
    p_ms.add_argument("--days", type=int, default=120, help="回看天数, 默认120")
    p_ms.set_defaults(func=cmd_sync_market_strength)

    p_md = sub.add_parser("sync-market-deviation", help="同步复盘会市场页周均线/偏离度到 fact_market_daily")
    p_md.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取 fact_market_daily 最新日")
    p_md.set_defaults(func=cmd_sync_market_deviation)

    p_mo = sub.add_parser("sync-market-overview", help="同步复盘会每日复盘结构化数据到 fact_market_daily")
    p_mo.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取复盘会最新")
    p_mo.add_argument("--days", type=int, default=60, help="market 接口回看天数, 默认60")
    p_mo.set_defaults(func=cmd_sync_market_overview)

    p_mor = sub.add_parser("sync-market-overview-range", help="批量同步复盘会每日复盘结构化数据")
    p_mor.add_argument("--start-date", default=None, help="起始交易日 YYYY-MM-DD")
    p_mor.add_argument("--end-date", default=None, help="结束交易日 YYYY-MM-DD；--days 模式下可作为截止日")
    p_mor.add_argument("--days", type=int, default=None, help="从 fact_market_daily 取最近 N 个交易日")
    p_mor.add_argument("--api-days", type=int, default=60, help="reviews/market 接口回看天数, 默认60")
    p_mor.add_argument("--refresh", action="store_true", help="不跳过已同步日期, 强制重刷")
    p_mor.add_argument("--sleep", type=float, default=0.2, help="日期间隔秒数, 默认0.2")
    p_mor.set_defaults(func=cmd_sync_market_overview_range)

    p_sh = sub.add_parser("sync-stock-high", help="同步复盘会个股新高状态与市场新高家数")
    p_sh.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取复盘会最新")
    p_sh.add_argument("--page-size", type=int, default=200, help="复盘会分页大小, 默认200")
    p_sh.set_defaults(func=cmd_sync_stock_high)

    p_shr = sub.add_parser("sync-stock-high-range", help="批量同步复盘会个股新高状态")
    p_shr.add_argument("--start-date", default=None, help="起始交易日 YYYY-MM-DD")
    p_shr.add_argument("--end-date", default=None, help="结束交易日 YYYY-MM-DD；--days 模式下可作为截止日")
    p_shr.add_argument("--days", type=int, default=None, help="从 fact_market_daily 取最近 N 个交易日")
    p_shr.add_argument("--page-size", type=int, default=200, help="复盘会分页大小, 默认200")
    p_shr.add_argument("--refresh", action="store_true", help="不跳过已同步日期, 强制重刷")
    p_shr.add_argument("--sleep", type=float, default=0.2, help="日期间隔秒数, 默认0.2")
    p_shr.set_defaults(func=cmd_sync_stock_high_range)

    p_lh = sub.add_parser("sync-limit-heat", help="同步复盘会涨停热力图题材汇总与涨停股明细")
    p_lh.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取复盘会最新")
    p_lh.add_argument("--dimension", default="sector", choices=["sector"], help="热力图维度, 默认sector")
    p_lh.add_argument("--scope", default="all", help="热力图范围, 默认all")
    p_lh.add_argument("--sector", default=None, help="只同步单个题材/板块代码或名称")
    p_lh.add_argument("--limit", type=int, default=None, help="最多处理前 N 个题材, 用于小样验证")
    p_lh.add_argument("--sleep", type=float, default=0.1, help="题材明细接口间隔秒数, 默认0.1")
    p_lh.add_argument("--detail-chunk", type=int, default=12, help="每批明细题材数, 默认12")
    p_lh.set_defaults(func=cmd_sync_limit_heat)

    p_mls = sub.add_parser("sync-mainline-sector-daily", help="同步复盘会每日主线题材→核心板块到 fact_mainline_sector_daily")
    p_mls.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取复盘会最新")
    p_mls.set_defaults(func=cmd_sync_mainline_sector_daily)

    p_la = sub.add_parser("sync-limit-advance", help="同步复盘会连板晋级到本地 DuckDB")
    p_la.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取复盘会最新")
    p_la.add_argument("--min-boards", type=int, default=2, help="最低连板数, 默认2")
    p_la.set_defaults(func=cmd_sync_limit_advance)

    p_lar = sub.add_parser("sync-limit-advance-range", help="批量同步复盘会连板晋级到本地 DuckDB")
    p_lar.add_argument("--start-date", default=None, help="起始交易日 YYYY-MM-DD")
    p_lar.add_argument("--end-date", default=None, help="结束交易日 YYYY-MM-DD；--days 模式下可作为截止日")
    p_lar.add_argument("--days", type=int, default=None, help="从 fact_market_daily 取最近 N 个交易日")
    p_lar.add_argument("--min-boards", type=int, default=2, help="最低连板数, 默认2")
    p_lar.add_argument("--refresh", action="store_true", help="不跳过已同步日期, 强制重刷")
    p_lar.add_argument("--sleep", type=float, default=0.2, help="日期间隔秒数, 默认0.2")
    p_lar.set_defaults(func=cmd_sync_limit_advance_range)

    sub.add_parser("sync-limit-advance-feishu", help="同步飞书连板晋级表到 fact_limit_advance_presence").set_defaults(func=cmd_sync_limit_advance_feishu)

    p_ml = sub.add_parser("sync-mainline-daily", help="同步复盘会主线题材+主线个股到 fact_mainline_theme_daily / fact_mainline_stock_daily")
    p_ml.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取 fact_market_daily 最新日")
    p_ml.set_defaults(func=cmd_sync_mainline_daily)

    p_tf = sub.add_parser("sync-theme-flow-daily", help="同步复盘会题材资金面板到 fact_theme_flow_daily")
    p_tf.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取 fact_market_daily 最新日")
    p_tf.set_defaults(func=cmd_sync_theme_flow_daily)

    p_pa = sub.add_parser(
        "sync-fupanhui-public-assets",
        help="同步复盘会公开增量资产（相似日/龙头高度/外盘/龙虎榜/监管/核心个股/竞价/事件/研报目录/题材挖掘）",
    )
    p_pa.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取 fact_market_daily 最新日")
    p_pa.add_argument("--align", action="store_true", help="按其它日表窗口回补缺口（默认新高表起点~market_daily 终点）")
    p_pa.add_argument("--start-date", default=None, help="范围回补起始日 YYYY-MM-DD")
    p_pa.add_argument("--end-date", default=None, help="范围回补结束日 YYYY-MM-DD")
    p_pa.add_argument("--days", type=int, default=None, help="从对齐窗口终点往回 N 个交易日")
    p_pa.add_argument("--sleep", type=float, default=0.2, help="子任务间隔秒数, 默认 0.2")
    p_pa.add_argument("--refresh", action="store_true", help="不跳过已有行, 强制重刷")
    p_pa.add_argument("--include-catalog", action="store_true", help="范围回补时也重拉研报目录/题材挖掘")
    p_pa.add_argument(
        "--only",
        nargs="+",
        default=None,
        help="范围回补只跑这些子任务（如 leader_height），可与 --refresh 联用定点重刷",
    )
    p_pa.add_argument(
        "--plan",
        choices=("full", "cheap"),
        default="full",
        help="单日同步分档：cheap = 竞价停抓、席位走 akshare、研报增量翻页（见 consumption_registry.yaml）",
    )
    p_pa.set_defaults(func=cmd_sync_fupanhui_public_assets)

    p_st = sub.add_parser(
        "stitch-sector-stocks",
        help="cheap 计划：identity 未动的板块用最近 fupanhui 名单 × 当日东财真值本地拼接成分行（0 复盘会请求）",
    )
    p_st.add_argument("--trade-date", required=True, help="交易日 YYYY-MM-DD（需已 sync-sectors 且 stock-daily 为东财源）")
    p_st.add_argument("--no-caps", action="store_true", help="不拉腾讯市值现值，按基线缩放")
    p_st.add_argument("--dry-run", action="store_true", help="只算不写")
    p_st.add_argument("--max-baseline-age-days", type=int, default=None,
                      help="identity 基线最多多旧（日历日），默认 10；名单冻结（fupanhui 停抓）时放宽到 120+")
    p_st.set_defaults(func=cmd_stitch_sector_stocks)

    p_cfu = sub.add_parser("carry-forward-universe",
                           help="名单冻结：把最近一份 published 宇宙按当日重新发布（provider=local:carry），供 stitch/sector-daily-local 使用")
    p_cfu.add_argument("--trade-date", required=True, help="交易日 YYYY-MM-DD")
    p_cfu.add_argument("--base-date", default=None, help="承接哪一天的快照，默认取之前最近一份 published")
    p_cfu.add_argument("--supersede", action="store_true", help="当日已有 published 快照也顶替（原快照留 superseded）——名单没抓全的那天用")
    p_cfu.set_defaults(func=cmd_carry_forward_universe)

    p_cls = sub.add_parser("compute-limit-stats-local",
                           help="本地涨跌停统计：题材涨停热度/涨停明细/连板梯队/龙头高度（不计 ST；沪深四舍五入、北交所向下取整）")
    p_cls.add_argument("--trade-date", required=True, help="交易日 YYYY-MM-DD")
    p_cls.add_argument("--min-boards", type=int, default=2, help="梯队最低连板数，默认 2")
    p_cls.add_argument("--force", action="store_true", help="当日已有非 local 来源行时也覆盖")
    p_cls.set_defaults(func=cmd_compute_limit_stats_local)

    p_cmo = sub.add_parser("compute-market-overview-local",
                           help="本地市场总览数字层：沪深总额/涨家数/涨跌停/量能/前三行业/新高家数/周均线（不碰周期阶段等编辑字段）")
    p_cmo.add_argument("--trade-date", required=True, help="交易日 YYYY-MM-DD")
    p_cmo.add_argument("--force", action="store_true", help="当日已有 fupanhui 数值时也覆盖")
    p_cmo.set_defaults(func=cmd_compute_market_overview_local)

    p_cme = sub.add_parser("compute-market-editorial-local",
                           help="编辑层自家替代版：强度(涨幅前5%个股)/量能状态/冰点 JSON；周期阶段留空")
    p_cme.add_argument("--trade-date", required=True, help="交易日 YYYY-MM-DD")
    p_cme.add_argument("--force", action="store_true", help="当日已有 fupanhui 强度值时也覆盖")
    p_cme.set_defaults(func=cmd_compute_market_editorial_local)

    p_csh = sub.add_parser("compute-stock-high-local",
                           help="新高名单 fact_stock_high_daily：按日内最高价 high 判 20/60/120日、1/2/3年、历史新高")
    p_csh.add_argument("--trade-date", required=True, help="交易日 YYYY-MM-DD")
    p_csh.add_argument("--force", action="store_true", help="当日已有非 local 来源行时也覆盖")
    p_csh.set_defaults(func=cmd_compute_stock_high_local)

    p_tms = sub.add_parser("train-market-stage", help="用 fupanhui 历史周期阶段标签训练本地分类器（numpy 逻辑回归），导出 JSON 权重并打印分块 CV 读数")
    p_tms.add_argument("--out", default=None, help="产物路径，默认 market_feature_store/models/market_stage_lr_v1.json")
    p_tms.set_defaults(func=cmd_train_market_stage)

    p_cms = sub.add_parser("compute-market-stage-local", help="周期阶段自训分类器 v1 预测并写 market_stage/stage_day（带 source/confidence；有 fupanhui 标签的日子不覆盖）")
    p_cms.add_argument("--trade-date", required=True, help="交易日 YYYY-MM-DD")
    p_cms.add_argument("--dry-run", action="store_true", help="只预测不写")
    p_cms.set_defaults(func=cmd_compute_market_stage_local)

    p_cml = sub.add_parser("compute-mainline-local", help="主线题材自家替代版：人气值（20日涨幅×2+5日涨停数+5日均额×0.5+5日双红×0.5）取 top4 题材，写三张 mainline 表")
    p_cml.add_argument("--trade-date", required=True, help="交易日 YYYY-MM-DD")
    p_cml.add_argument("--topk", type=int, default=4, help="主线题材数，默认 4")
    p_cml.add_argument("--force", action="store_true", help="当日已有非 local 来源行时也覆盖")
    p_cml.set_defaults(func=cmd_compute_mainline_local)

    p_ccs = sub.add_parser("compute-core-stock-local",
                           help="核心个股复刻版：fupanhui 口径反推 = 当日全市场成交额前 50（405 日实测集合一致 99.5%）")
    p_ccs.add_argument("--trade-date", required=True, help="交易日 YYYY-MM-DD")
    p_ccs.add_argument("--topn", type=int, default=50, help="取前 N 只，默认 50（fupanhui 口径）")
    p_ccs.add_argument("--force", action="store_true", help="当日已有非 local 来源行时也覆盖")
    p_ccs.set_defaults(func=cmd_compute_core_stock_local)

    p_ccl = sub.add_parser("compute-core-leader-local",
                           help="核心个股自家版：主线题材成员 × 知识库年报暴露度（正宗）× 人气（涨停/连板/成交额/新高）")
    p_ccl.add_argument("--trade-date", required=True, help="交易日 YYYY-MM-DD")
    p_ccl.add_argument("--topn", type=int, default=20, help="取前 N 只，默认 20")
    p_ccl.add_argument("--per-theme", type=int, default=8, help="每个题材最多几只，默认 8")
    p_ccl.add_argument("--auth-weight", type=float, default=None,
                       help="正宗度权重（与人气同在 [0,1]）；不给则用 CORE_LEADER_AUTH_WEIGHT，0 = 纯人气基线（消融对照）")
    p_ccl.add_argument("--allow-no-kb", action="store_true",
                       help="知识库读不到时也出（正宗度全 0，source 标 -nokb）；默认 fail-closed")
    p_ccl.add_argument("--force", action="store_true", help="当日已有非 local 来源行时也覆盖")
    p_ccl.set_defaults(func=cmd_compute_core_leader_local)

    p_sdl = sub.add_parser(
        "sync-sector-daily-local",
        help="cheap 计划：板块日行情本地派生（成交额=成分求和、边际量本地公式、涨幅优先 payload 官方值）",
    )
    p_sdl.add_argument("--trade-date", required=True, help="交易日 YYYY-MM-DD（需当日成分行齐全）")
    p_sdl.add_argument("--no-payload", action="store_true", help="忽略 payload 官方涨幅，全部用成分等权")
    p_sdl.set_defaults(func=cmd_sync_sector_daily_local)

    p_rc = sub.add_parser(
        "reconcile-sector-daily",
        help="周抽样对账：抽 N 个板块打复盘会 K 线，对比本地派生行（成本 = N 请求）",
    )
    p_rc.add_argument("--trade-date", required=True)
    p_rc.add_argument("--sample", type=int, default=20)
    p_rc.add_argument("--seed", type=int, default=None)
    p_rc.set_defaults(func=cmd_reconcile_sector_daily)

    p_ds = sub.add_parser(
        "sync-dragon-seats-akshare",
        help="龙虎榜席位明细换源 akshare（榜单仍来自 fact_dragon_tiger_daily）",
    )
    p_ds.add_argument("--trade-date", required=True)
    p_ds.add_argument("--sleep", type=float, default=0.1)
    p_ds.set_defaults(func=cmd_sync_dragon_seats_akshare)

    sub.add_parser(
        "registry-check",
        help="校验 consumption_registry.yaml：档位合法、表在 schema、计划步骤有归属",
    ).set_defaults(func=cmd_registry_check)

    p_skd = sub.add_parser("sync-stock-daily", help="mootdx 全A股日线回补到 fact_stock_daily (历史日的日期参数化源; 含 open/high/low/volume)")
    p_skd.add_argument("--start-date", default=None, help="起始交易日 YYYY-MM-DD, 留空对齐 fact_market_daily 最早日")
    p_skd.add_argument("--end-date", default=None, help="截止交易日(含); 与 --start-date 相同即只重写单日, 如东财快照写坏的那天")
    p_skd.add_argument("--ohlc-only", action="store_true", help="只补 open/high/low/volume, 不碰已有行的收盘/昨收/涨幅/名字/来源 (给东财日线补 OHLC / 拉长历史)")
    p_skd.add_argument("--offset", type=int, default=180, help="每只股票拉取日线根数, 默认180(~8个月); 3 年历史用 800")
    p_skd.add_argument("--limit", type=int, default=None, help="本次最多抓多少只 (续跑用)")
    p_skd.add_argument("--skip", type=int, default=0, help="跳过宇宙前 N 只; 与 --refresh --limit 配合做确定性分页 (第 i 批 skip=i*limit)")
    p_skd.add_argument("--refresh", action="store_true", help="不跳过已抓股票, 强制重抓")
    p_skd.add_argument("--sleep", type=float, default=0.0, help="股票间隔秒数, 默认0")
    p_skd.add_argument("--qfq", action="store_true", help="用前复权(慢, 吃CPU); 默认裸收盘价(快)")
    p_skd.add_argument("--timeout", type=int, default=10, help="单只 bars 请求超时秒数(SIGALRM 兜底), 超时跳过不卡死整批, 默认10; 0=关闭")
    p_skd.add_argument("--progress-every", type=int, default=200, help="每处理多少只打一行心跳进度, 默认200; 0=关闭")
    p_skd.set_defaults(func=cmd_sync_stock_daily)

    p_fsf = sub.add_parser("fill-stock-daily-fallback",
                           help="当日兜底: 用 fact_sector_stock_daily 行情聚合补 fact_stock_daily(标 fallback)")
    p_fsf.add_argument("--trade-date", required=True, help="交易日 YYYY-MM-DD")
    p_fsf.add_argument("--ma-window", type=int, default=5, help="复算上证均线偏离的回看交易日数, 默认5")
    p_fsf.add_argument("--no-deviation", action="store_true", help="不复算 sh_week_ma/sh_deviation_pct")
    p_fsf.set_defaults(func=cmd_fill_stock_daily_fallback)
    p_sks = sub.add_parser("sync-stock-daily-snapshot", help="东财全市场快照写单日 fact_stock_daily (盘后增量快路径)")
    p_sks.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取当天")
    p_sks.add_argument("--page-size", type=int, default=100, help="东财分页大小, 单页上限100")
    p_sks.add_argument("--allow-misdated", action="store_true",
                       help="快照实际日期(f297) ≠ --trade-date 时仍然写, source 标 -misdated。默认拒写——"
                            "补历史日请用 sync-stock-daily (mootdx), 07-20/08-06 两次事故都是这里写坏的")
    p_sks.set_defaults(func=cmd_sync_stock_daily_snapshot)

    p_du = sub.add_parser("daily-update", help="一键日更同步+补字段+质检")
    p_du.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取最新")
    p_du.add_argument("--chart-table", default=None, help="涨家数走势飞书表 table_id, 可选")
    p_du.add_argument("--skip-long", action="store_true", help="跳过板块成分股和全A日线等长任务")
    p_du.add_argument("--no-chart", action="store_true", help="不生成/同步涨家数 MA5 图")
    p_du.add_argument("--stock-source", choices=["snapshot", "mootdx"], default="snapshot",
                      help="全A日线取数: snapshot=东财快照(默认,快); mootdx=通达信逐只(慢,可拉历史)")
    p_du.add_argument("--status-json", default=None, help="写出结构化执行状态，供上层编排判断 PASS/WARN/FAIL")
    p_du.add_argument(
        "--direct",
        action="store_true",
        help="允许直写 canonical 生产库（默认拒绝）。会写 ops_sync_run / state/direct-write-*.json",
    )
    p_du.set_defaults(func=cmd_daily_update)

    p_dr = sub.add_parser("daily-review", help="从 DuckDB 生成每日复盘：JSON 真本源 + Markdown 渲染物（同名同目录）")
    p_dr.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取 fact_market_daily 最新日")
    p_dr.add_argument("--output", default=None, help="Markdown 输出路径, 默认 exports/YYYY-MM-DD-daily-review.md；JSON 落同名 .json")
    p_dr.add_argument("--chart-output", default=None, help="涨家数 MA5 图片路径, 默认 exports/YYYY-MM-DD-advancers-ma5.png")
    p_dr.add_argument("--start-date", default=None, help="启动日 YYYY-MM-DD, 用于生成启动日主线确认模块")
    p_dr.set_defaults(func=cmd_daily_review)

    p_df = sub.add_parser("daily-full", help="一键日更后生成完整每日复盘 (staging 写+原子换库, 生产库无写锁)")
    p_df.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取最新")
    p_df.add_argument("--chart-table", default=None, help="涨家数走势飞书表 table_id, 可选")
    p_df.add_argument("--skip-long", action="store_true", help="跳过板块成分股和全A日线等长任务")
    p_df.add_argument("--stock-source", choices=["snapshot", "mootdx"], default="snapshot",
                      help="全A日线取数: snapshot=东财快照(默认,快); mootdx=通达信逐只(慢,可拉历史)")
    p_df.set_defaults(func=cmd_daily_full)

    p_dfe = sub.add_parser("daily-full-exec",
                           help="(内部) daily-full 的 staging 子进程入口, 勿直接使用")
    p_dfe.add_argument("--trade-date", default=None)
    p_dfe.add_argument("--chart-table", default=None)
    p_dfe.add_argument("--skip-long", action="store_true")
    p_dfe.add_argument("--stock-source", choices=["snapshot", "mootdx"], default="snapshot")
    p_dfe.add_argument("--status-json", default=None,
                       help="结构化结果落盘路径, 父进程用它拼收据")
    p_dfe.add_argument(
        "--direct",
        action="store_true",
        help="允许对 canonical 生产库跑 exec（默认拒绝）。父进程指向 staging 时不需要",
    )
    p_dfe.set_defaults(func=cmd_daily_full_exec)

    sub.add_parser("check", help="数据体检 (行数/交易日/空值/覆盖度)").set_defaults(func=cmd_check)

    p_cd = sub.add_parser("check-daily", help="跨日质检 (历史断档/行数异常/值域越界); rc=2 表示未通过")
    p_cd.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取最新")
    p_cd.add_argument("--window", type=int, default=20, help="交易日历窗口, 默认20")
    p_cd.add_argument("--json", default=None, help="质检报告 JSON 落盘路径, 可选")
    p_cd.add_argument("--plan", default=None, help="计划档位 full/cheap/local；local 按 registry 裁剪期望表（自算链路不产 fupanhui 独有表）")
    p_cd.set_defaults(func=cmd_check_daily)

    p_wg = sub.add_parser("weighted-gainers", help="区间加权涨幅排行 (本地计算)")
    p_wg.add_argument("--start", required=True, help="区间起始交易日 YYYY-MM-DD")
    p_wg.add_argument("--end", required=True, help="区间结束交易日 YYYY-MM-DD")
    p_wg.add_argument("--top", type=int, default=20, help="返回前 N 只, 默认20")
    p_wg.add_argument("--min-amount", type=float, default=1.0, help="区间日均成交额下限(亿), 默认1.0")
    p_wg.set_defaults(func=cmd_weighted_gainers)

    p_ig = sub.add_parser("interval-gainers", help="区间涨幅排行 (本地计算)")
    p_ig.add_argument("--start", required=True, help="区间起始交易日 YYYY-MM-DD")
    p_ig.add_argument("--end", required=True, help="区间结束交易日 YYYY-MM-DD")
    p_ig.add_argument("--top", type=int, default=20, help="返回前 N 只, 默认20")
    p_ig.add_argument("--min-amount", type=float, default=1.0, help="区间日均成交额下限(亿), 默认1.0")
    p_ig.set_defaults(func=cmd_interval_gainers)

    p_q1 = sub.add_parser("sector-stocks", help="板块→个股: 查某板块成分股")
    p_q1.add_argument("sector", help="板块代码或名称, 如 885537.TI 或 3D打印")
    p_q1.add_argument("--trade-date", default=None, help="交易日, 留空取最新")
    p_q1.add_argument("--top", type=int, default=20, help="返回前 N 只, 默认20")
    p_q1.add_argument("--order-by", default="amount",
                      help="排序字段: amount/pct_chg/pct_chg_5d/fund_flow_1d 等")
    p_q1.set_defaults(func=cmd_sector_stocks)

    p_q2 = sub.add_parser("stock-sectors", help="个股→板块: 查某个股归属板块")
    p_q2.add_argument("stock", help="个股代码或名称, 如 300620.SZ 或 寒武纪")
    p_q2.add_argument("--trade-date", default=None, help="交易日, 留空取最新")
    p_q2.set_defaults(func=cmd_stock_sectors)

    p_qh = sub.add_parser("query-stock-high", help="按一级行业回溯查询某日新高个股")
    p_qh.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取最新")
    p_qh.add_argument("--period", default=None,
                      choices=["history", "3y", "2y", "1y", "120d", "60d", "20d"],
                      help="只看命中某周期的新高个股")
    p_qh.add_argument("--group-by", default="sw_l1", choices=["sw_l1"], help="聚合维度, 当前支持 sw_l1")
    p_qh.add_argument("--top", type=int, default=10, help="每个一级行业最多展示个股数, 默认10")
    p_qh.add_argument("--sector-top", type=int, default=5, help="每只个股/行业展示板块数, 默认5")
    p_qh.add_argument("--with-sectors", action="store_true", help="打印每只个股所属复盘会板块")
    p_qh.set_defaults(func=cmd_stock_highs)

    p_qlh = sub.add_parser("query-limit-heat", help="查询复盘会涨停热力题材榜")
    p_qlh.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取最新")
    p_qlh.add_argument("--theme", default=None, help="题材/板块代码或名称")
    p_qlh.add_argument("--top", type=int, default=20, help="展示前 N 个题材, 默认20")
    p_qlh.add_argument("--with-stocks", action="store_true", help="展示题材内涨停股明细")
    p_qlh.add_argument("--stock-top", type=int, default=20, help="每个题材展示涨停股数, 默认20")
    p_qlh.set_defaults(func=cmd_limit_heat)

    p_ae = sub.add_parser("advancers-extrema", help="涨家数波峰/波谷识别 (ZigZag)")
    p_ae.add_argument("--delta", type=float, default=1500, help="确认反转的最小摆幅(家数), 默认1500")
    p_ae.add_argument("--smooth", type=int, default=1, help="滚动均值窗口, 如5=MA5; 默认1(裸涨家数)")
    p_ae.add_argument("--smooth-mode", default="trailing", choices=["trailing", "center"],
                      help="trailing(同飞书MA5,默认) 或 center(无滞后)")
    p_ae.set_defaults(func=cmd_advancers_extrema)

    p_sp = sub.add_parser("sw-l1-signal-peaks", help="申万一级涨停/新高波峰: 当日数量 vs 自身过去N日均值")
    p_sp.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取最新")
    p_sp.add_argument("--high-period", default="20d",
                      choices=["history", "3y", "2y", "1y", "120d", "60d", "20d"],
                      help="新高周期, 默认20d；按 high_periods_json 复刻页面周期")
    p_sp.add_argument("--window", type=int, default=20, help="历史均值窗口, 默认20个有效交易日")
    p_sp.add_argument("--ratio", type=float, default=1.2, help="波峰倍数阈值, 默认1.2")
    p_sp.add_argument("--min-limit-count", type=int, default=3, help="涨停波峰最低当日家数, 默认3")
    p_sp.add_argument("--min-high-count", type=int, default=5, help="新高波峰最低当日家数, 默认5")
    p_sp.add_argument("--top", type=int, default=20, help="每类最多展示 N 个申万一级, 默认20")
    p_sp.set_defaults(func=cmd_sw_l1_signal_peaks)

    p_trace = sub.add_parser("strong-subtheme-trace", help="回溯双红题材首日、多周期共振首日、申万一级波峰首日")
    p_trace.add_argument("--start-date", default=None, help="起始交易日 YYYY-MM-DD")
    p_trace.add_argument("--end-date", default=None, help="结束交易日 YYYY-MM-DD；--days 模式下可作为截止日")
    p_trace.add_argument("--days", type=int, default=60, help="不指定 start-date 时取最近 N 个交易日, 默认60")
    p_trace.add_argument("--high-period", default="20d",
                         choices=["history", "3y", "2y", "1y", "120d", "60d", "20d"],
                         help="新高波峰周期, 默认20d")
    p_trace.add_argument("--window", type=int, default=20, help="波峰历史均值窗口, 默认20")
    p_trace.add_argument("--ratio", type=float, default=1.2, help="波峰倍数阈值, 默认1.2")
    p_trace.add_argument("--min-limit-count", type=int, default=3, help="涨停波峰最低当日家数, 默认3")
    p_trace.add_argument("--min-high-count", type=int, default=5, help="新高波峰最低当日家数, 默认5")
    p_trace.add_argument("--top", type=int, default=50, help="每类最多展示 N 条, 默认50")
    p_trace.set_defaults(func=cmd_strong_subtheme_trace)

    p_q3 = sub.add_parser("top-sectors", help="板块排行: 按边际量/涨幅/成交额")
    p_q3.add_argument("--trade-date", default=None, help="交易日, 留空取最新")
    p_q3.add_argument("--top", type=int, default=20, help="返回前 N 个, 默认20")
    p_q3.add_argument("--order-by", default="diff_ratio", help="排序字段: diff_ratio/pct_chg/amount")
    p_q3.set_defaults(func=cmd_top_sectors)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
