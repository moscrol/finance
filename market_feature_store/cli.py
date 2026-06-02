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
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
