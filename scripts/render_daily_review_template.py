from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from market_feature_store.db import connect
from market_feature_store.reports.daily_review import build_daily_review

DEFAULT_OUTPUT_DIR = Path("/Users/lbq/Desktop/复盘")


def latest_trade_date() -> str:
    con = connect(read_only=True)
    try:
        row = con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()
    finally:
        con.close()
    if not row or not row[0]:
        raise RuntimeError("fact_market_daily 中没有可用交易日")
    return str(row[0])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="快速按 6.5 模板生成完整每日市场复盘")
    parser.add_argument("--trade-date", default=None, help="交易日 YYYY-MM-DD；不传则取 fact_market_daily 最新日")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="输出目录，默认 /Users/lbq/Desktop/复盘")
    parser.add_argument("--output-name", default=None, help="Markdown 文件名，默认 {trade_date}-daily-review.md")
    parser.add_argument("--chart-name", default=None, help="涨家数 MA5 图片文件名，默认 {trade_date}-advancers-ma5.png")
    parser.add_argument("--update-template", action="store_true", help="同时覆盖 daily-review-template.md 和 {trade_date}-daily-review-template.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    trade_date = args.trade_date or latest_trade_date()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    output_name = args.output_name or f"{trade_date}-daily-review.md"
    chart_name = args.chart_name or f"{trade_date}-advancers-ma5.png"
    output_path = output_dir / output_name
    chart_path = output_dir / chart_name

    result = build_daily_review(
        trade_date=trade_date,
        output_path=str(output_path),
        chart_path=str(chart_path),
    )

    template_paths = []
    if args.update_template:
        for name in ("daily-review-template.md", f"{trade_date}-daily-review-template.md"):
            dst = output_dir / name
            shutil.copy2(output_path, dst)
            template_paths.append(dst)

    print(f"交易日: {result['trade_date']}")
    print(f"报告: {result['output_path']}")
    if result.get("chart_path"):
        print(f"图表: {result['chart_path']}")
    for path in template_paths:
        print(f"模板: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
