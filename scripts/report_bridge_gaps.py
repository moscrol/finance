#!/usr/bin/env python3
"""桥静默丢行的只读报告：同花顺当日有 bar、canonical `fact_stock_daily` 却没有的股票，逐只说清原因与可补证据。

## 为什么要有它

`bridge-stock-daily` 按 `hithink_stock_preview` 的合同，对「缺前一计划日 bar」（复牌、新股首日）和
「送转 / 配股」一律报缺口、不猜值——这是对的；但缺口只写进桥的返回 JSON，夜跑 quality-gate 的覆盖率
分母本身也不含这些票，于是**每天 3~10 只股票静默缺行**，没有任何红灯：

- 2026-09-28 漏 300096.SZ（复牌），17:05 发布验收未发现；
- 2026-09-29 漏 601238.SH 广汽集团 / 605303.SH / 300211.SZ（复牌）、301716.SZ / 920202.BJ（新股首日）、
  688808.SH（10 转 4.8）。

本脚本只把缺口摆上桌面，**不写库、不补值、不改桥**；它给出的「候选前收」只是证据，是否采用是
2026-09-22 决策请求 (d)「除权 / 送转两日行怎么补」与复牌例外的用户决策，不由本脚本代做。

## 每只缺口股给出什么

- `reasons`：`preview_stock_calculation` 对该股的原样缺口原因；
- `last_bar`：目标日之前同花顺最后一根 bar（日期、收盘）；
- `events_in_gap`：`fact_stock_adjustment_hithink` 中 ex_date ∈ (last_bar 日期, 目标日] 的事件；
- `candidate_pre_close` 与 `candidate_basis`：
  - `resumption_last_close_no_recorded_event`：前一计划日缺 bar、区间内无事件记录 → 最后收盘价
    （2024 年起东财 / 新浪可信源回测 65/65 一致；但「无记录」≠「证实无事件」，所以只是候选）；
  - `noncash_action_reference`：前一计划日有 bar、目标日恰一条送转 / 配股事件 →
    `(前收 − 派息 + 配股价×配股比例) / (1 + 送转比例 + 配股比例)`，四舍五入到分
    （同一回测只有 38/57 一致，**单独不可信**，必须有第二来源核对）；
  - 其他（首日无历史 bar、区间内有事件等）→ 无候选；
- `capture`（给了 `--capture-dir` 才有）：收盘后封存的腾讯报价里该股的名称、收盘、昨收；
- `verdict`：
  - `two-source-agree`：候选前收与封存报价昨收差 ≤ 0.005，且报价收盘与同花顺收盘差 ≤ 0.005；
  - `capture-only`：无候选，但封存报价有昨收（典型：新股首日，昨收即发行价）；
  - `conflict`：候选与报价不一致——两边至少一个错，不得补；
  - `no-capture`：封存报价里没有这只（例：捕获范围取自上一交易日有行的股票，复牌股天然不在内）；
  - `no-evidence`：既无候选也无报价。

## 用法

    .venv-workbench/bin/python scripts/report_bridge_gaps.py --trade-date 2026-09-29 \\
        [--db PATH] [--capture-dir db/quote-captures/tencent/2026-09-29] [--json out.json] [--fail-on-gaps]

默认库为 `market_feature_store.db.DB_PATH`，只读连接。夜跑持写锁时请勿运行。
退出码：0 报告完成（有无缺口都是 0）；`--fail-on-gaps` 时有缺口返回 1；2 参数 / 输入错误。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402

from market_feature_store.hithink_stock_preview import preview_stock_calculation  # noqa: E402
from market_feature_store.trading_days import previous_scheduled_trading_day  # noqa: E402

_CENT = Decimal("0.01")
PRICE_TOLERANCE = 0.005
_QUOTE = re.compile(r'v_(sh|sz|bj)(\d{6})="([^"]*)"')


def _dec(value) -> Decimal | None:
    if value is None:
        return None
    number = Decimal(str(value))
    return number if number.is_finite() else None


def load_capture(capture_dir: Path) -> dict[str, dict]:
    """读封存目录下全部 batch-*.raw（GBK）：代码 → 名称 / 收盘 / 昨收。只读，不校验封存完整性。"""
    quotes: dict[str, dict] = {}
    for path in sorted(capture_dir.glob("batch-*.raw")):
        text = path.read_bytes().decode("gbk", errors="replace")
        for match in _QUOTE.finditer(text):
            fields = match.group(3).split("~")
            if len(fields) < 5:
                continue
            code = f"{match.group(2)}.{match.group(1).upper()}"
            try:
                close, pre_close = float(fields[3]), float(fields[4])
            except ValueError:
                continue
            quotes[code] = {"name": fields[1], "close": close, "pre_close": pre_close}
    return quotes


def noncash_reference(prev_close, event: dict) -> Decimal | None:
    close = _dec(prev_close)
    cash, bonus, ratio, price = (_dec(event.get(k)) or Decimal(0) for k in (
        "dividend_per_share", "per_share_bonus", "allotment_ratio", "allotment_price"))
    if close is None or close <= 0:
        return None
    denominator = Decimal(1) + bonus + ratio
    if denominator <= 0:
        return None
    reference = ((close - cash + price * ratio) / denominator).quantize(_CENT, rounding=ROUND_HALF_UP)
    return reference if reference > 0 else None


def _candidate(td: date, prev: date, last_bar: dict | None, events: list[dict]):
    if last_bar is None:
        return None, "no_prior_bar"
    if last_bar["date"] < prev:
        if events:
            return None, "events_inside_suspension_gap"
        close = _dec(last_bar["close"])
        return (close.quantize(_CENT, rounding=ROUND_HALF_UP) if close else None,
                "resumption_last_close_no_recorded_event")
    if len(events) == 1 and events[0]["ex_date"] == td:
        event = events[0]
        if any((_dec(event.get(k)) or 0) != 0 for k in ("per_share_bonus", "allotment_ratio",
                                                        "allotment_price")):
            return noncash_reference(last_bar["close"], event), "noncash_action_reference"
    return None, "not_classified"


def _verdict(candidate, current_close, quote) -> str:
    if quote is None:
        return "no-capture" if candidate is not None else "no-evidence"
    if candidate is None:
        return "capture-only"
    agree_pre = abs(float(candidate) - quote["pre_close"]) <= PRICE_TOLERANCE
    agree_close = current_close is not None and abs(float(current_close) - quote["close"]) <= PRICE_TOLERANCE
    return "two-source-agree" if agree_pre and agree_close else "conflict"


def build_report(con, trade_date: str, capture: dict[str, dict] | None = None) -> dict:
    td = date.fromisoformat(trade_date)
    prev = previous_scheduled_trading_day(td)
    if prev is None:
        raise ValueError(f"{trade_date} 的前一计划交易日未知")
    vendor = {r[0]: r[1] for r in con.execute(
        "SELECT stock_ts_code, close FROM fact_stock_daily_hithink WHERE trade_date = ?", [td]).fetchall()}
    canonical = {r[0] for r in con.execute(
        "SELECT stock_ts_code FROM fact_stock_daily WHERE trade_date = ?", [td]).fetchall()}
    gap_codes = sorted(set(vendor) - canonical)
    reasons: dict[str, list[str]] = {}
    if gap_codes:
        preview = preview_stock_calculation(con, td, stock_codes=gap_codes)
        reasons = {g["stock_ts_code"]: g["reasons"] for g in preview["gaps"]}
    items = []
    for code in gap_codes:
        row = con.execute(
            "SELECT trade_date, close FROM fact_stock_daily_hithink "
            "WHERE stock_ts_code = ? AND trade_date < ? ORDER BY trade_date DESC LIMIT 1",
            [code, td]).fetchone()
        last_bar = {"date": row[0], "close": row[1]} if row else None
        low = last_bar["date"] if last_bar else date(1900, 1, 1)
        events = [dict(zip(("ex_date", "dividend_per_share", "per_share_bonus", "allotment_ratio",
                            "allotment_price"), r)) for r in con.execute(
            "SELECT ex_date, dividend_per_share, per_share_bonus, allotment_ratio, allotment_price "
            "FROM fact_stock_adjustment_hithink WHERE stock_ts_code = ? AND ex_date > ? AND ex_date <= ? "
            "ORDER BY ex_date", [code, low, td]).fetchall()]
        candidate, basis = _candidate(td, prev, last_bar, events)
        quote = capture.get(code) if capture is not None else None
        items.append({
            "stock_ts_code": code,
            "reasons": reasons.get(code, ["calculable-but-not-written"]),
            "current_close": vendor[code],
            "last_bar": ({"date": str(last_bar["date"]), "close": last_bar["close"]} if last_bar else None),
            "events_in_gap": [{**e, "ex_date": str(e["ex_date"])} for e in events],
            "candidate_pre_close": float(candidate) if candidate is not None else None,
            "candidate_basis": basis,
            "capture": quote,
            "verdict": _verdict(candidate, vendor[code], quote) if capture is not None else None,
        })
    verdicts: dict[str, int] = {}
    for item in items:
        if item["verdict"]:
            verdicts[item["verdict"]] = verdicts.get(item["verdict"], 0) + 1
    return {
        "trade_date": trade_date, "previous_scheduled_trading_day": str(prev),
        "vendor_codes": len(vendor), "canonical_rows": len(canonical),
        "canonical_not_in_vendor": len(canonical - set(vendor)),
        "gap_count": len(items), "verdicts": verdicts, "gaps": items,
        "capture_checked": capture is not None,
        "database_writes": False,
        "note": "候选前收只是证据；是否补行是用户决策（09-22 决策请求 (d) 与复牌例外）。",
    }


def _render(report: dict) -> str:
    lines = [f"{report['trade_date']}: 同花顺 {report['vendor_codes']} 只，canonical {report['canonical_rows']} 行，"
             f"缺口 {report['gap_count']} 只 {report['verdicts'] or ''}"]
    for g in report["gaps"]:
        cap = g["capture"]
        lines.append(
            f"  {g['stock_ts_code']:<10} {','.join(g['reasons']):<32} 收 {g['current_close']}"
            f" | 上一根 {g['last_bar']['date'] + ' ' + str(g['last_bar']['close']) if g['last_bar'] else '无'}"
            f" | 候选前收 {g['candidate_pre_close']} ({g['candidate_basis']})"
            f" | 报价 {cap['name'] + ' 昨收 ' + str(cap['pre_close']) if cap else '无'}"
            f" | {g['verdict'] or '-'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--db")
    parser.add_argument("--capture-dir")
    parser.add_argument("--json")
    parser.add_argument("--fail-on-gaps", action="store_true")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.trade_date):
        print("--trade-date 须为 YYYY-MM-DD", file=sys.stderr)
        return 2
    if args.db:
        db_path = Path(args.db)
    else:
        from market_feature_store.db import DB_PATH
        db_path = DB_PATH
    if not db_path.is_file():
        print(f"库不存在：{db_path}", file=sys.stderr)
        return 2
    capture = None
    if args.capture_dir:
        capture_dir = Path(args.capture_dir)
        if not capture_dir.is_dir():
            print(f"封存目录不存在：{capture_dir}", file=sys.stderr)
            return 2
        capture = load_capture(capture_dir)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        report = build_report(con, args.trade_date, capture)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        con.close()
    print(_render(report))
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if args.fail_on_gaps and report["gap_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
