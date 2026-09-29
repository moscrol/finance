#!/usr/bin/env python3
"""给同花顺桥接行补「当日具名名」：只填桥接行的空名，名字取自封存的同场次报价捕获。

为什么（2026-09-26 回补 09-23/09-24 实测）
------------------------------------------
同花顺日线桥（``bridge_hithink_stock_daily``）的名称政策是「库内该股此前最近一条非空
名」。新上市股票在库里没有此前的名字，桥只能留 NULL；``compute-limit-stats-local``
随后按设计拒跑（``InvalidStockName``）——名字决定它是不是 N/C 新股：猜错会把无涨跌幅
限制的新股算进涨跌停，或把真跌停漏掉。门是对的，缺的是一个合规的名称来源。

名称来源 = ``scripts/audit_dated_quote_capture.py`` 验过的封存捕获：receipt 覆盖面、
逐批 sha256、每条报价时间戳必须落在目标交易日收盘后——也就是「判定只用当日名」。
**接受这个来源是数据合同决定**（09-22 决策页合同 1；``hithink_recovery_candidate`` 的
``name_source_acceptance``），本脚本只是执行件，用不用由人拍板。

硬约束（任一条不满足 → 一行不写，退出 2）
------------------------------------------
- 目标库不是 canonical 生产库（``write_path.is_canonical_production``）：只在 staging
  上跑，经正式换库发布；
- 只动 ``source`` 为 ``hithink:*`` 且 ``stock_name`` 为空的行；已有名字的行永不覆盖，
  别的来源出现空名直接拒跑（那不是桥的缺口，是别的问题）；
- 每个待填行都必须在捕获里有报价，且 close / pre_close / pct_chg 相等、amount（亿）与
  捕获成交额之差 ≤ 1e-4 亿（桥的四位小数舍入）——证明捕获描述的是同一根 bar；
- 名字满足 ``InvalidStockName`` 的同一口径（非空、无控制字符）；
- 收据路径必须是新文件（先查再写，最后以 ``x`` 模式落盘），旧证据不覆盖。
只改 ``stock_name`` 一列；单事务；写后逐行回读。

过时名更正（``--refresh-stale-names``；合同 1 扩展，用户 2026-09-29 约 23:50「同意，你按照最优推进就行」）
------------------------------------------------------------------------------------------
桥的名称政策是「库内此前最近一条非空名」，于是改名永远跟不上：09-29 实测 5559 行桥接行里 46 行过时——
摘帽（ST易联众→易联众）、新股过了首 5 日仍挂 C（C信诺维，科创板被当作无涨跌幅限制）、除权日后仍挂
XD（XD雅戈尔）、mootdx 截断（华润新能→华润新能源）、公司更名（通行宝→苏交数智）；格式差异 0 例。
开关打开时，同一份封存报价里名字**非空但与报价名不同**的同花顺桥接行改用报价名：
- 只动 ``source`` 以 ``hithink:`` 开头的行（东财等主源的名字本来就是当日名）；
- 与补空名同一组「同一根 bar」钉（close / pre_close / pct_chg / amount）；报价名须合法；
- 对不上的**逐只跳过**并写进收据，不连坐、也不影响补空名（维持原名不比接线前更糟）；
- 补空名仍是全有或全无：它拒跑时本步整体不写，更正也不做。

用法::

    MARKET_FEATURE_STORE_DB=<staging> python3 skills/duckdb-backfill/scripts/attach_capture_names.py \\
        --trade-date 2026-09-23 --capture-dir <封存捕获目录> --receipt <新收据.json> [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

NAME_SOURCE = "tencent:captured-dated-quote"
PRICE_TOLERANCE = 1e-6
AMOUNT_TOLERANCE_YI = 1e-4


class AttachRefused(RuntimeError):
    """前置条件不满足；没有写任何行。消息带可追的明细。"""


def valid_name(name) -> bool:
    """与 compute_local_stats._limit_flags 的 InvalidStockName 同一口径。"""
    return (isinstance(name, str) and bool(name.strip())
            and not any(ord(char) < 32 or ord(char) == 127 for char in name))


def load_capture(capture_dir: Path, trade_date: date, *,
                 expect_receipt_sha256: str | None = None) -> tuple[dict, dict[str, dict]]:
    """用仓内既有验证器验整份捕获，再取逐只报价（每批读取时再核一次 sha256）。

    receipt.json 会被读两次（验证器一次、取报价一次）：两次的 sha256 必须相同，
    否则中途被换过的 receipt 可以带着自己的批次哈希绕过范围校验。给了
    expect_receipt_sha256 时还要等于封存清单里记的那个值。
    """
    from scripts.audit_dated_quote_capture import audit_capture, checked_raw, parse_quotes

    receipt_path = capture_dir / "receipt.json"
    before = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    if expect_receipt_sha256 is not None and before != expect_receipt_sha256:
        raise ValueError(f"capture receipt sha256 {before} != pinned {expect_receipt_sha256}")
    audit = audit_capture(capture_dir, trade_date)
    receipt_bytes = receipt_path.read_bytes()
    if hashlib.sha256(receipt_bytes).hexdigest() != before:
        raise ValueError("capture receipt changed during validation")
    receipt = json.loads(receipt_bytes)
    quotes: dict[str, dict] = {}
    for batch in receipt["batches"]:
        quotes.update(parse_quotes(checked_raw(capture_dir, batch), trade_date))
    audit["receipt_sha256"] = before
    return audit, quotes


def _bar_diffs(close, pre_close, pct_chg, amount, quote: dict) -> list[str]:
    """捕获与这一行是不是同一根 bar：四个钉任一超容差即不是。"""
    pins = (
        ("close", close, quote["close"], PRICE_TOLERANCE),
        ("pre_close", pre_close, quote["pre_close"], PRICE_TOLERANCE),
        ("pct_chg", pct_chg, quote["pct_chg"], PRICE_TOLERANCE),
        ("amount", amount, quote["amount_yuan"] / 1e8, AMOUNT_TOLERANCE_YI),
    )
    return [f"{field} {ours}!={theirs}" for field, ours, theirs, tolerance in pins
            if ours is None or abs(float(ours) - float(theirs)) > tolerance]


def plan_targets(con, trade_date: date, quotes: dict[str, dict]) -> list[dict]:
    rows = con.execute(
        """
        SELECT stock_ts_code, stock_name, close, pre_close, pct_chg, amount, source
        FROM fact_stock_daily
        WHERE trade_date = ? AND (stock_name IS NULL OR trim(stock_name) = '')
        ORDER BY stock_ts_code
        """,
        [trade_date],
    ).fetchall()
    targets: list[dict] = []
    problems: list[str] = []
    for code, name, close, pre_close, pct_chg, amount, source in rows:
        if not str(source or "").startswith("hithink:"):
            problems.append(f"{code}: 空名行来源 {source!r} 不是同花顺桥接行")
            continue
        quote = quotes.get(code)
        if quote is None:
            problems.append(f"{code}: 捕获里没有这只的报价")
            continue
        if not valid_name(quote["name"]):
            problems.append(f"{code}: 捕获名 {quote['name']!r} 不合法")
            continue
        diffs = _bar_diffs(close, pre_close, pct_chg, amount, quote)
        if diffs:
            problems.append(f"{code}: 捕获与桥接行不是同一根 bar（{'; '.join(diffs)}）")
            continue
        targets.append({
            "stock_ts_code": code, "stock_name_before": name, "stock_name": quote["name"],
            "name_source": NAME_SOURCE, "quote_timestamp": quote["quote_timestamp"],
            "row_source": source, "close": close, "pre_close": pre_close,
            "pct_chg": pct_chg, "amount": amount,
        })
    if problems:
        raise AttachRefused("; ".join(problems))
    return targets


def attach(con, trade_date: date, targets: list[dict]) -> None:
    con.execute("BEGIN TRANSACTION")
    try:
        for target in targets:
            hit = con.execute(
                """
                UPDATE fact_stock_daily SET stock_name = ?
                WHERE trade_date = ? AND stock_ts_code = ? AND source = ?
                  AND (stock_name IS NULL OR trim(stock_name) = '')
                RETURNING stock_ts_code
                """,
                [target["stock_name"], trade_date, target["stock_ts_code"], target["row_source"]],
            ).fetchall()
            if len(hit) != 1:
                raise AttachRefused(f"{target['stock_ts_code']}: 预期改 1 行，实际 {len(hit)} 行")
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    codes = [t["stock_ts_code"] for t in targets]
    got = dict(con.execute(
        f"SELECT stock_ts_code, stock_name FROM fact_stock_daily WHERE trade_date = ? "
        f"AND stock_ts_code IN ({','.join('?' for _ in codes)})",
        [trade_date, *codes],
    ).fetchall())
    wrong = [c for c in codes if got.get(c) != next(t["stock_name"] for t in targets if t["stock_ts_code"] == c)]
    if wrong:
        raise RuntimeError(f"写后回读不一致: {wrong}")


def plan_refresh(con, trade_date: date, quotes: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """桥接行名字非空但与当日封存报价名不同 → (可更正, 跳过及原因)。只读。"""
    rows = con.execute(
        """
        SELECT stock_ts_code, stock_name, close, pre_close, pct_chg, amount, source
        FROM fact_stock_daily
        WHERE trade_date = ? AND stock_name IS NOT NULL AND trim(stock_name) <> ''
          AND source LIKE 'hithink:%'
        ORDER BY stock_ts_code
        """,
        [trade_date],
    ).fetchall()
    refresh: list[dict] = []
    skipped: list[dict] = []
    for code, name, close, pre_close, pct_chg, amount, source in rows:
        quote = quotes.get(code)
        if quote is None or quote["name"] == name:
            continue
        reason = None
        if not valid_name(quote["name"]):
            reason = f"捕获名 {quote['name']!r} 不合法"
        else:
            diffs = _bar_diffs(close, pre_close, pct_chg, amount, quote)
            if diffs:
                reason = f"捕获与桥接行不是同一根 bar（{'; '.join(diffs)}）"
        if reason:
            skipped.append({"stock_ts_code": code, "stock_name": name, "capture_name": quote["name"],
                            "reason": reason})
            continue
        refresh.append({
            "stock_ts_code": code, "stock_name_before": name, "stock_name": quote["name"],
            "name_source": NAME_SOURCE, "quote_timestamp": quote["quote_timestamp"], "row_source": source,
        })
    return refresh, skipped


def apply_refresh(con, trade_date: date, targets: list[dict]) -> None:
    """单事务：逐行 UPDATE（带旧名与来源做乐观锁），任一行命中数 != 1 回滚；写后回读。"""
    con.execute("BEGIN TRANSACTION")
    try:
        for target in targets:
            hit = con.execute(
                """
                UPDATE fact_stock_daily SET stock_name = ?
                WHERE trade_date = ? AND stock_ts_code = ? AND source = ? AND stock_name = ?
                RETURNING stock_ts_code
                """,
                [target["stock_name"], trade_date, target["stock_ts_code"], target["row_source"],
                 target["stock_name_before"]],
            ).fetchall()
            if len(hit) != 1:
                raise AttachRefused(f"{target['stock_ts_code']}: 更正预期改 1 行，实际 {len(hit)} 行")
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    for target in targets:
        got = con.execute("SELECT stock_name FROM fact_stock_daily WHERE trade_date = ? AND stock_ts_code = ?",
                          [trade_date, target["stock_ts_code"]]).fetchone()
        if not got or got[0] != target["stock_name"]:
            raise RuntimeError(f"更正写后回读不一致: {target['stock_ts_code']}")


def run(trade_date: date, capture_dir: Path, receipt_path: Path, *, db_path: Path,
        dry_run: bool = False, expect_receipt_sha256: str | None = None,
        refresh_stale: bool = False) -> dict:
    import duckdb

    from market_feature_store.write_path import is_canonical_production

    if is_canonical_production(db_path):
        raise AttachRefused(f"目标 {db_path} 是 canonical 生产库；只在 staging 上跑，经正式换库发布")
    if receipt_path.exists():
        raise AttachRefused(f"收据 {receipt_path} 已存在；旧证据不覆盖，换一个新路径")
    audit, quotes = load_capture(capture_dir, trade_date, expect_receipt_sha256=expect_receipt_sha256)
    con = duckdb.connect(str(db_path))
    try:
        targets = plan_targets(con, trade_date, quotes)
        refresh, skipped = plan_refresh(con, trade_date, quotes) if refresh_stale else ([], [])
        if targets and not dry_run:
            attach(con, trade_date, targets)
        if refresh and not dry_run:
            apply_refresh(con, trade_date, refresh)
    finally:
        con.close()
    result = {
        "kind": "attach-capture-names", "trade_date": trade_date.isoformat(),
        "db_path": str(db_path), "dry_run": dry_run, "applied": bool(targets) and not dry_run,
        "name_source": NAME_SOURCE, "capture_dir": str(capture_dir),
        "capture_audit": audit, "targets": targets,
        "refresh_stale": refresh_stale, "refreshed": refresh if not dry_run else [],
        "refresh_planned": refresh, "refresh_skipped": skipped,
        "decision_required": "name_source_acceptance (09-22 决策页合同 1)"
                             + ("；过时名更正 = 合同 1 扩展（用户 2026-09-29 约 23:50 同意）" if refresh_stale else ""),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
    }
    with receipt_path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--trade-date", type=date.fromisoformat, required=True)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True, help="新收据文件路径（已存在则拒跑）")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--expect-receipt-sha256", help="封存清单里记的 receipt.json sha256（建议总是给）")
    parser.add_argument("--refresh-stale-names", action="store_true",
                        help="同时把名字非空但与报价名不同的桥接行改用报价名（合同 1 扩展，见文档）")
    args = parser.parse_args(argv)
    from market_feature_store.db import DB_PATH

    try:
        result = run(args.trade_date, args.capture_dir, args.receipt, db_path=DB_PATH,
                     dry_run=args.dry_run, expect_receipt_sha256=args.expect_receipt_sha256,
                     refresh_stale=args.refresh_stale_names)
    except (AttachRefused, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"attached": False, "error_type": type(exc).__name__, "error": str(exc)},
                         ensure_ascii=False))
        return 2
    print(json.dumps({k: result[k] for k in ("trade_date", "dry_run", "applied", "name_source")}
                     | {"targets": [(t["stock_ts_code"], t["stock_name"], t["quote_timestamp"])
                                    for t in result["targets"]],
                        "refreshed": [(t["stock_ts_code"], t["stock_name_before"], t["stock_name"])
                                      for t in result["refreshed"]],
                        "refresh_skipped": len(result["refresh_skipped"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
