"""从 canonical Market Feature Store 输出无前视转折信号。"""

from __future__ import annotations

import argparse
import sys
from datetime import date as date_cls
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from market_feature_store.analysis.sector_data import SectorDataProvider  # noqa: E402
from market_feature_store.analysis.turning_points import Signal, SignalDetector  # noqa: E402
from market_feature_store.db import DB_PATH as CANONICAL_DB_PATH  # noqa: E402

DB_PATH = CANONICAL_DB_PATH


def _date_arg(value: str) -> str:
    try:
        return date_cls.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期必须是 YYYY-MM-DD") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检测市场放量和 MA5 峰谷确认信号")
    parser.add_argument("--from", dest="start", type=_date_arg, help="起始交易日 YYYY-MM-DD")
    parser.add_argument("--to", dest="end", type=_date_arg, help="结束交易日 YYYY-MM-DD")
    parser.add_argument(
        "--db-path",
        default=str(DB_PATH),
        help="canonical DuckDB 路径，默认读取 MARKET_FEATURE_STORE_DB 或主库",
    )
    return parser


def detect(
    provider: SectorDataProvider,
    start: str,
    end: str,
) -> tuple[list[dict], list[dict], list[Signal]]:
    market_data = provider.get_market_data(start, end)
    advancers = provider.get_advancers(start, end)
    signals = SignalDetector().detect(market_data, advancers)
    return market_data, advancers, signals


def print_results(market_data: list[dict], advancers: list[dict], signals: list[Signal]) -> None:
    market_by_date = {row["date"]: row for row in market_data}
    signal_by_date: dict[str, list[Signal]] = {}
    for signal in signals:
        signal_by_date.setdefault(signal.date, []).append(signal)

    print(f"{'日期':<12} {'涨家数':>6} {'MA5':>8} {'信号'}")
    print("-" * 75)
    for row in advancers:
        date = row["date"]
        ma5 = row.get("ma5")
        market = market_by_date.get(date, {})
        signal_text = "; ".join(
            f"{signal.type}({signal.detail})"
            for signal in signal_by_date.get(date, [])
        )
        ma5_text = f"{ma5:.1f}" if ma5 is not None else ""
        volume_change = market.get("volume_change")
        volume_text = (
            f"成交额变化 {float(volume_change):+.1f}%"
            if volume_change is not None
            else ""
        )
        details = "; ".join(item for item in (volume_text, signal_text) if item)
        marker = " ◀" if details else ""
        print(f"{date:<12} {str(row.get('count') or ''):>6} {ma5_text:>8} {details}{marker}")

    volume_signals = [signal for signal in signals if "volume_surge" in signal.type]
    peak_signals = [signal for signal in signals if "peak" in signal.type]
    valley_signals = [signal for signal in signals if "valley" in signal.type]
    print(f"\n{'=' * 75}")
    print("信号汇总:")
    print(f"  放量信号日: {len(volume_signals)} 天")
    print(f"  MA5 顶点确认: {', '.join(signal.date for signal in peak_signals) or '-'}")
    print(f"  MA5 谷底确认: {', '.join(signal.date for signal in valley_signals) or '-'}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    provider = None
    try:
        provider = SectorDataProvider(args.db_path)
        auto_start, auto_end = provider.get_date_range()
        start = args.start or auto_start
        end = args.end or auto_end
        if start is None or end is None:
            parser.error("fact_sector_daily 没有可用交易日")
        if start > end:
            parser.error("--from 不能晚于 --to")
        market_data, advancers, signals = detect(provider, start, end)
        if not advancers:
            parser.error(f"{start} 到 {end} 没有可用 fact_market_daily 数据")
        print_results(market_data, advancers, signals)
        return 0
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    finally:
        if provider is not None:
            provider.close()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
