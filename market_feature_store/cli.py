"""Market Feature Store 命令行入口。

用法:
    python3 -m market_feature_store.cli init    # 初始化 schema (幂等)
    python3 -m market_feature_store.cli info    # 查看库内表与行数
"""
import argparse
import sys

from . import __version__
from .db import DB_PATH, connect, init_db, list_tables


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


def cmd_sync_sector_stocks(args) -> int:
    from .sync.sync_fupanhui_sector_stock_daily import sync_fact_sector_stock_daily

    stats = sync_fact_sector_stock_daily(
        trade_date=args.trade_date,
        sector=args.sector,
        limit=args.limit,
        only_missing=not args.refresh,
        sleep=args.sleep,
    )
    print(f"交易日: {stats['trade_date']}")
    print(f"本次抓取板块: {stats['processed']} | 写入行: {stats['rows_written']}")
    print(f"当日已完成板块: {stats['sectors_done_today']}/{stats['sectors_total']} | 剩余: {stats['sectors_remaining']}")
    print(f"fact_sector_stock_daily 总数: {stats['table_total']}")
    if stats["failures"]:
        print(f"失败 {len(stats['failures'])}: " + ", ".join(c for c, _ in stats['failures'][:10]))
    return 0


def cmd_sync_market_daily(_args) -> int:
    from .sync.sync_feishu_market_daily import sync_fact_market_daily

    stats = sync_fact_market_daily()
    print(f"飞书拉取: {stats['fetched']} 条 | 写入: {stats['written']} 条")
    print(f"fact_market_daily 总数: {stats['table_total']} ({stats['date_min']} ~ {stats['date_max']})")
    print(f"空成交额行: {stats['null_total_amount']}")
    if stats["skipped"]:
        print(f"跳过(无效日期) {len(stats['skipped'])}: " + ", ".join(str(s) for s in stats['skipped'][:10]))
    return 0


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
    if "coverage_latest" in h:
        c = h["coverage_latest"]
        print(f"[最新日 {c['date']}] 有成分股板块 {c['sectors_with_stocks']}/{c['dim_sector_total']}")
    return 0


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

    p_sectors = sub.add_parser("sync-sectors", help="同步复盘会板块清单到 dim_sector")
    p_sectors.add_argument("--trade-date", default=None, help="交易日期 YYYY-MM-DD, 留空取最新")
    p_sectors.set_defaults(func=cmd_sync_sectors)

    p_sd = sub.add_parser("sync-sector-daily", help="同步板块日行情+边际量到 fact_sector_daily")
    p_sd.add_argument("--trade-date", default=None, help="截止交易日 YYYY-MM-DD, 留空取最新")
    p_sd.add_argument("--days", type=int, default=25, help="每板块回看天数, 默认25")
    p_sd.set_defaults(func=cmd_sync_sector_daily)

    p_ss = sub.add_parser("sync-sector-stocks", help="逐板块回补成分股快照到 fact_sector_stock_daily")
    p_ss.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD, 留空取最新")
    p_ss.add_argument("--sector", default=None, help="只抓单个板块 (代码或名称)")
    p_ss.add_argument("--limit", type=int, default=None, help="本次最多抓多少个板块")
    p_ss.add_argument("--refresh", action="store_true", help="不跳过已抓板块, 强制重抓")
    p_ss.add_argument("--sleep", type=float, default=0.3, help="板块间隔秒数, 默认0.3")
    p_ss.set_defaults(func=cmd_sync_sector_stocks)

    sub.add_parser("sync-market-daily", help="同步飞书每日指标表到 fact_market_daily").set_defaults(func=cmd_sync_market_daily)

    sub.add_parser("check", help="数据体检 (行数/交易日/空值/覆盖度)").set_defaults(func=cmd_check)

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

    p_ae = sub.add_parser("advancers-extrema", help="涨家数波峰/波谷识别 (ZigZag)")
    p_ae.add_argument("--delta", type=float, default=1500, help="确认反转的最小摆幅(家数), 默认1500")
    p_ae.add_argument("--smooth", type=int, default=1, help="滚动均值窗口, 如5=MA5; 默认1(裸涨家数)")
    p_ae.add_argument("--smooth-mode", default="trailing", choices=["trailing", "center"],
                      help="trailing(同飞书MA5,默认) 或 center(无滞后)")
    p_ae.set_defaults(func=cmd_advancers_extrema)

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
