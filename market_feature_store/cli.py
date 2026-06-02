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

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
