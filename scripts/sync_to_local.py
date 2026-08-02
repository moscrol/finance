"""旧版本地同步入口的正式退役 shim。

复盘事实统一由 market_feature_store.cli 的 daily-full 写入 canonical 库。
此文件保留路径，避免旧自动化得到一个看似成功但实际写错库的结果。
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="旧版本地同步入口（已退役）")
    parser.add_argument("--incremental", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    build_parser().parse_args(args)
    print(
        "sync_to_local.py 已退役；复盘数据统一使用 "
        "python3 -m market_feature_store.cli daily-full --help。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
