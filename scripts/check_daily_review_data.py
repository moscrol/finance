from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Direct execution needs the repository root on sys.path before project imports.
# The E402 below is therefore an ordering requirement, not an oversight.
from market_feature_store.db import (  # noqa: E402
    DB_PATH,
    DatabaseLockedError,
    connect,
    connect_read_only_with_retry,
    staging_path,
)
from market_feature_store.trading_days import is_trading_day  # noqa: E402

# 闸门没能执行（duckdb 写锁占用超出重试窗）≠ 数据不完整。
# 专用退出码让 nightly_full_review.sh 等外层如实播报，而不是误报缺数。
EXIT_BLOCKED = 3


def _lock_retry_config() -> tuple[int, float]:
    """锁重试参数（次数, 间隔秒）。

    默认 13 次 × 10s ≈ 2 分钟：够等 sync 单步写事务收尾，又不至于让
    launchd 任务吊死在整晚 backfill 上。环境变量供演练/联调时收窄窗口。
    """
    attempts = int(os.environ.get("REVIEW_GATE_LOCK_ATTEMPTS", "13"))
    delay = float(os.environ.get("REVIEW_GATE_LOCK_DELAY_SECONDS", "10"))
    return attempts, delay


def _connect_read_only():
    # opener 走本模块的 connect 绑定：既有测试 monkeypatch 的就是这个符号。
    attempts, delay = _lock_retry_config()
    return connect_read_only_with_retry(
        attempts=attempts,
        delay_seconds=delay,
        opener=lambda: connect(read_only=True),
    )


def _l2_allow_all_empty() -> bool:
    return os.environ.get("L2_ALLOW_ALL_EMPTY", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _l2_paused() -> bool:
    return os.environ.get("L2_PAUSED", "").strip().lower() in {"1", "true", "yes"}

TABLES = [
    "fact_market_daily",
    "fact_sector_daily",
    "fact_sw_l1_daily",
    "fact_sector_stock_daily",
    "fact_stock_high_daily",
    "fact_theme_limit_heat_daily",
    "fact_theme_limit_stock_daily",
    "fact_limit_advance_daily",
    "fact_stock_daily",
    "fact_mainline_theme_daily",
    "fact_mainline_stock_daily",
    "fact_mainline_sector_daily",
    "fact_theme_flow_daily",
    "fact_sector_period_rank_daily",
    "feature_market_window",
    "feature_sector_window",
    "feature_stock_window",
    "feature_stock_technical_daily",
]
DATE_COLUMNS = {
    "feature_market_window": "as_of_date",
    "feature_sector_window": "as_of_date",
    "feature_stock_window": "as_of_date",
    "feature_stock_technical_daily": "trade_date",
}
# 有 fact_market_daily 当日行就必须有这组派生；缺任何一张 = 半成品，不是源没抓到。
FEATURE_FAMILY = (
    "fact_sector_period_rank_daily",
    "feature_market_window",
    "feature_sector_window",
    "feature_stock_window",
    "feature_stock_technical_daily",
)
L2_TABLES = [
    "feature_l2_capital_flow_daily",
    "feature_l2_quant_orders_daily",
]
L2_STEPS = ("limitup", "top100", "quant")
L2_RESULT_SQL = {
    "limitup": "SELECT COUNT(*) FROM feature_l2_capital_flow_daily "
               "WHERE trade_date = ? AND scan_type = 'limitup'",
    "top100": "SELECT COUNT(*) FROM feature_l2_capital_flow_daily "
              "WHERE trade_date = ? AND scan_type = 'top100'",
    "quant": "SELECT COUNT(*) FROM feature_l2_quant_orders_daily WHERE trade_date = ?",
}
SW_L1_COUNT = 31
STOCK_COVERAGE_MIN = 0.98
MARKET_FIELDS = [
    "sh_index_close",
    "sh_index_pct_chg",
    "sh_week_ma",
    "sh_deviation_pct",
    "total_amount",
    "amount_vs_yesterday_pct",
    "amount_ma20",
    "volume_ratio",
    "advancers",
    "limit_up",
    "limit_down",
    "top3_industry_ratio",
    "strength_avg_pct",
    "strength_amount_pct",
    "strength_status",
]
# 计划档位裁剪：local（fupanhui 停抓后的自算链路）不产这些字段，缺它们是设计不是缺数。
# 表的裁剪不写死在这里——从 consumption_registry.tables_for_plan 派生（单一真本源）。
# local 现在自算强度（涨幅前 5% 口径，compute-market-editorial-local），MARKET_FIELDS 全部可检；留字典给未来的裁剪。
PLAN_UNAVAILABLE_MARKET_FIELDS: dict[str, set[str]] = {
    "local": set(),
}


def plan_scope(plan: str | None) -> tuple[list[str], list[str]]:
    """按计划返回 (要检查的表, 要检查的 fact_market_daily 字段)。plan 为空/full/cheap = 全量不变。"""
    if not plan or plan in ("full", "cheap", "auto"):
        return list(TABLES), list(MARKET_FIELDS)
    from market_feature_store.consumption_registry import load_registry, tables_for_plan

    expected = tables_for_plan(load_registry(), plan) | set(FEATURE_FAMILY)
    tables = [t for t in TABLES if t in expected]
    fields = [f for f in MARKET_FIELDS if f not in PLAN_UNAVAILABLE_MARKET_FIELDS.get(plan, set())]
    return tables, fields


PLACEHOLDERS = [
    "| 周均线 | - |",
    "| 偏离度 | - |",
    "| 涨停方向 | 核心涨停题材： |",
    "暂无",
    "未返回",
]


def is_null(value: object) -> bool:
    return value is None or str(value) in {"nan", "NaT", "None"}


def _feature_family_gap(counts: dict[str, int], date: str) -> list[str]:
    """有当日 fact、缺派生层：一条家族结论，避免被拆成五条「表空」噪声。"""
    if not counts.get("fact_market_daily"):
        return []
    missing_family = [table for table in FEATURE_FAMILY if not counts.get(table)]
    if not missing_family:
        return []
    return [
        "派生层未跑：fact_market_daily 有 "
        f"{date} 而 {', '.join(missing_family)} 无行——"
        "先 compute_features，不要当源数据没抓到"
    ]


def _print_staging_contrast(date: str, prod_counts: dict[str, int]) -> None:
    """INCOMPLETE 时对照 sibling .staging：区分「没写」和「写了没晋升」。"""
    import duckdb

    staging = staging_path(DB_PATH)
    try:
        if not staging.exists() or staging.resolve() == Path(DB_PATH).resolve():
            return
    except OSError:
        return
    print(f"STAGING CONTRAST {date} ({staging.name})")
    try:
        con = duckdb.connect(str(staging), read_only=True)
    except Exception as exc:  # noqa: BLE001
        print(f"- staging 打不开: {exc}")
        return
    try:
        for table in TABLES:
            date_column = DATE_COLUMNS.get(table, "trade_date")
            try:
                _max_date, count = con.execute(
                    f"SELECT MAX({date_column}), COUNT(*) FILTER (WHERE {date_column} = ?) FROM {table}",
                    [date],
                ).fetchone()
            except Exception:
                continue
            prod = int(prod_counts.get(table) or 0)
            stg = int(count or 0)
            if prod == stg:
                continue
            if stg and not prod:
                label = "未晋升（staging 有、生产没有）"
            elif prod and not stg:
                label = "两套库已分叉（生产有、staging 没有）"
            else:
                label = "行数不一致"
            print(f"- {table}: 生产={prod} staging={stg} → {label}")
    finally:
        con.close()


def check_data(date: str, plan: str | None = None) -> list[str]:
    missing: list[str] = []
    tables, market_fields = plan_scope(plan)
    con = _connect_read_only()
    try:
        print(f"CHECK DATA {date}" + (f" (plan={plan}: {len(tables)}/{len(TABLES)} 表)" if plan and len(tables) != len(TABLES) else ""))
        counts: dict[str, int] = {}
        for table in tables:
            date_column = DATE_COLUMNS.get(table, "trade_date")
            max_date, count = con.execute(
                f"SELECT MAX({date_column}), COUNT(*) FILTER (WHERE {date_column} = ?) FROM {table}",
                [date],
            ).fetchone()
            counts[table] = int(count or 0)
            print(f"{table}: rows={count} max={max_date}")
            if not count:
                missing.append(f"{table} 无 {date} 数据，最新 {max_date}")

        cursor = con.execute("select * from fact_market_daily where trade_date=?", [date])
        values = cursor.fetchone()
        if values is None:
            missing.append("fact_market_daily 缺失整行")
        else:
            row = {column[0]: value for column, value in zip(cursor.description, values)}
            for field in market_fields:
                if field not in row:
                    missing.append(f"fact_market_daily.{field} 字段不存在")
                    continue
                value = row[field]
                if is_null(value):
                    missing.append(f"fact_market_daily.{field} 为空")

        empty_detail = con.execute(
            """
            SELECT h.sector_ts_code, h.sector_name, h.limit_up_count, COUNT(s.stock_ts_code) AS stock_rows
            FROM fact_theme_limit_heat_daily h
            LEFT JOIN fact_theme_limit_stock_daily s
              ON h.trade_date = s.trade_date AND h.sector_ts_code = s.sector_ts_code
            WHERE h.trade_date = ? AND COALESCE(h.limit_up_count, 0) > 0
            GROUP BY 1, 2, 3
            HAVING COUNT(s.stock_ts_code) = 0
            ORDER BY h.limit_up_count DESC
            """,
            [date],
        ).fetchall()
        for code, name, limit_up_count, _stock_rows in empty_detail:
            missing.append(f"涨停题材 {code}/{name} 有 {limit_up_count} 个涨停但明细为空")
        mainline_gaps = con.execute(
            """
            SELECT t.theme_code, t.theme_name,
                   COUNT(DISTINCT s.stock_ts_code) AS stock_rows,
                   COUNT(DISTINCT m.sector_ts_code) AS sector_rows
            FROM fact_mainline_theme_daily t
            LEFT JOIN fact_mainline_stock_daily s
              ON t.trade_date = s.trade_date AND t.theme_code = s.theme_code
            LEFT JOIN fact_mainline_sector_daily m
              ON t.trade_date = m.trade_date AND t.theme_code = m.theme_code
            WHERE t.trade_date = ?
            GROUP BY 1, 2
            HAVING COUNT(DISTINCT s.stock_ts_code) = 0
                OR COUNT(DISTINCT m.sector_ts_code) = 0
            ORDER BY 1
            """,
            [date],
        ).fetchall()
        for code, name, stock_rows, sector_rows in mainline_gaps:
            missing.append(
                f"主线题材 {code}/{name} 覆盖不完整：个股 {stock_rows} 行，核心板块 {sector_rows} 行"
            )

        missing.extend(_check_sw_l1(con, date))
        missing.extend(_check_sector_coverage(con, date))
        missing.extend(_check_sector_stock_fields(con, date))
        missing.extend(_check_stock_coverage(con, date))
        missing.extend(_feature_family_gap(counts, date))
        if missing:
            _print_staging_contrast(date, counts)
        return missing
    finally:
        con.close()


def _check_sw_l1(con, date: str) -> list[str]:
    """申万一级：31 个行业齐全、close/pct_chg/amount 非空、不接受 degraded 代理源。"""
    problems: list[str] = []
    rows = con.execute(
        "SELECT sw_l1, close, pct_chg, amount, source FROM fact_sw_l1_daily "
        "WHERE trade_date = ? ORDER BY sw_l1",
        [date],
    ).fetchall()
    if len(rows) != SW_L1_COUNT:
        problems.append(f"fact_sw_l1_daily {date} 只有 {len(rows)} 个行业，应为 {SW_L1_COUNT}")
    for sw_l1, close, pct_chg, amount, source in rows:
        empties = [name for name, v in
                   (("close", close), ("pct_chg", pct_chg), ("amount", amount))
                   if is_null(v)]
        if empties:
            problems.append(f"fact_sw_l1_daily {sw_l1} 字段为空: {','.join(empties)}")
        if source and str(source).startswith("degraded"):
            problems.append(f"fact_sw_l1_daily {sw_l1} 使用降级代理源: {source}")
    return problems


def _check_sector_coverage(con, date: str) -> list[str]:
    """板块行情：相邻交易日名称覆盖连续，且 pct_chg/amount 非空。

    dim_sector 是跨日期目录，供应商会更换代码、保留历史别名，不能作为单日
    行情的全覆盖基准。用唯一名称的相邻交易日连续性发现真实的日线断流。
    """
    problems: list[str] = []
    previous_date = con.execute(
        "SELECT MAX(trade_date) FROM fact_sector_daily WHERE trade_date < ?", [date]
    ).fetchone()[0]
    current_count, = con.execute(
        "SELECT COUNT(DISTINCT sector_name) FROM fact_sector_daily WHERE trade_date = ?", [date]
    ).fetchone()
    if not current_count:
        problems.append(f"fact_sector_daily 无 {date} 板块行情")
    elif previous_date:
        previous_count, continued_count = con.execute(
            """
            WITH previous_names AS (
                SELECT DISTINCT sector_name
                FROM fact_sector_daily
                WHERE trade_date = ?
            ), current_names AS (
                SELECT DISTINCT sector_name
                FROM fact_sector_daily
                WHERE trade_date = ?
            )
            SELECT COUNT(*), COUNT(current_names.sector_name)
            FROM previous_names
            LEFT JOIN current_names USING (sector_name)
            """,
            [previous_date, date],
        ).fetchone()
        continuity = continued_count / previous_count if previous_count else 1.0
        print(
            f"fact_sector_daily 名称连续性: {continued_count}/{previous_count} = {continuity:.2%} "
            f"(前一交易日 {previous_date})"
        )
        if continuity < 0.95:
            problems.append(
                f"fact_sector_daily 名称连续性 {continuity:.2%} < 95% "
                f"({continued_count}/{previous_count}, 前一交易日 {previous_date})"
            )
    null_rows = con.execute(
        "SELECT sector_ts_code, sector_name FROM fact_sector_daily "
        "WHERE trade_date = ? AND (pct_chg IS NULL OR amount IS NULL) ORDER BY 1",
        [date],
    ).fetchall()
    for code, name in null_rows:
        problems.append(f"fact_sector_daily {code}/{name} pct_chg/amount 为空")
    return problems


def _check_sector_stock_fields(con, date: str) -> list[str]:
    """板块成员行情：每个有行情板块当日都有成员，且 price/pct_chg/amount 非空。"""
    problems: list[str] = []
    no_member = con.execute(
        """
        SELECT f.sector_ts_code, f.sector_name
        FROM fact_sector_daily f
        LEFT JOIN fact_sector_stock_daily s
          ON s.trade_date = f.trade_date AND s.sector_ts_code = f.sector_ts_code
        WHERE f.trade_date = ?
        GROUP BY f.trade_date, 1, 2
        HAVING COUNT(s.stock_ts_code) = 0
          -- 排除从未有过成员的板块（fupanhui 新加、还没分配股票的空板块不应卡门；
          -- 只校验「历史上有过成员、今天突然没了」的真正同步缺口）
          AND EXISTS (
              SELECT 1 FROM fact_sector_stock_daily s2
              WHERE s2.sector_ts_code = f.sector_ts_code
                AND s2.trade_date < ?
              LIMIT 1
          )
        ORDER BY 1
        """,
        [date, date],
    ).fetchall()
    for code, name in no_member:
        problems.append(f"fact_sector_stock_daily 板块 {code}/{name} 无当日成员行")
    null_cnt, = con.execute(
        "SELECT COUNT(*) FROM fact_sector_stock_daily WHERE trade_date = ? "
        "AND (price IS NULL OR pct_chg IS NULL OR amount IS NULL)",
        [date],
    ).fetchone()
    if null_cnt:
        problems.append(f"fact_sector_stock_daily 有 {null_cnt} 行 price/pct_chg/amount 为空")
    return problems


def _check_stock_coverage(con, date: str) -> list[str]:
    """个股日线覆盖：对比当日板块成员去重股票数，覆盖率 ≥ 98%。"""
    problems: list[str] = []
    member_cnt, covered_cnt = con.execute(
        """
        SELECT COUNT(DISTINCT m.stock_ts_code),
               COUNT(DISTINCT m.stock_ts_code) FILTER (WHERE d.stock_ts_code IS NOT NULL)
        FROM fact_sector_stock_daily m
        LEFT JOIN fact_stock_daily d
          ON d.trade_date = m.trade_date AND d.stock_ts_code = m.stock_ts_code
        WHERE m.trade_date = ?
        """,
        [date],
    ).fetchone()
    if not member_cnt:
        return problems  # 成员表缺失已在前面报错, 避免重复
    ratio = covered_cnt / member_cnt
    print(f"fact_stock_daily 覆盖率: {covered_cnt}/{member_cnt} = {ratio:.2%}")
    if ratio < STOCK_COVERAGE_MIN:
        missing_codes = [r[0] for r in con.execute(
            """
            SELECT DISTINCT m.stock_ts_code
            FROM fact_sector_stock_daily m
            LEFT JOIN fact_stock_daily d
              ON d.trade_date = m.trade_date AND d.stock_ts_code = m.stock_ts_code
            WHERE m.trade_date = ? AND d.stock_ts_code IS NULL
            ORDER BY 1 LIMIT 30
            """,
            [date],
        ).fetchall()]
        problems.append(
            f"fact_stock_daily 覆盖率 {ratio:.2%} < {STOCK_COVERAGE_MIN:.0%} "
            f"({covered_cnt}/{member_cnt})，缺失示例: {','.join(missing_codes)}"
        )
    return problems


def check_report(date: str) -> list[str]:
    missing: list[str] = []
    report = Path(f"market_feature_store/exports/{date}-daily-review.md")
    if not report.exists():
        missing.append(f"{report} 不存在")
    else:
        text = report.read_text(encoding="utf-8")
        for token in PLACEHOLDERS:
            count = text.count(token)
            if count:
                missing.append(f"日报存在占位/缺失：{token} x{count}")
    return missing


def check_l2(date: str) -> list[str]:
    if not is_trading_day(date):
        print(f"CHECK L2 {date} 非交易日，自动放行")
        return []
    if _l2_paused():
        print(
            f"CHECK L2 {date} L2 已挂账暂停（L2_PAUSED=1），跳过检查；"
            "欠账日期待鉴权恢复后用 run_l2_pipeline.sh 回补"
        )
        return []
    missing: list[str] = []
    con = _connect_read_only()
    try:
        print(f"CHECK L2 {date}")
        for step in L2_STEPS:
            row = con.execute(
                """
                SELECT status, row_count, input_count, processed_count, failed_count, finished_at
                FROM ops_pipeline_run_daily
                WHERE trade_date = ? AND pipeline = 'l2-moneyflow' AND step = ?
                """,
                [date, step],
            ).fetchone()
            print(f"l2-moneyflow/{step}: {row or 'missing'}")
            if row is None:
                missing.append(f"L2 步骤 {step} 无 {date} 完成记录")
                continue
            status, row_count, input_count, processed_count, failed_count, _finished = row
            if status != "complete":
                missing.append(f"L2 步骤 {step} 状态为 {status}，未完成")
                continue
            if input_count is None or processed_count is None or failed_count is None:
                missing.append(f"L2 步骤 {step} 缺处理统计（input/processed/failed），不可审计")
                continue
            if input_count <= 0:
                missing.append(f"L2 步骤 {step} input_count={input_count}，无扫描候选")
            if step == "top100" and input_count < 100:
                missing.append(f"L2 步骤 top100 input_count={input_count} < 100")
            if failed_count:
                missing.append(f"L2 步骤 {step} failed_count={failed_count}")
            if processed_count != input_count:
                missing.append(
                    f"L2 步骤 {step} processed_count={processed_count} != input_count={input_count}"
                )
            actual, = con.execute(L2_RESULT_SQL[step], [date]).fetchone()
            if row_count is None or actual != row_count:
                missing.append(
                    f"L2 步骤 {step} 状态表 row_count={row_count} 与结果表实际 {actual} 行不一致"
                )
            # capital 榜：有扫描候选却 0 行 → 视为链路异常（VPN/空响应），不得 COMPLETE
            if (
                not _l2_allow_all_empty()
                and step in {"limitup", "top100"}
                and status == "complete"
                and (row_count or 0) == 0
                and (input_count or 0) > 0
            ):
                missing.append(
                    f"L2 步骤 {step} complete 但 row_count=0（input={input_count}）；"
                    "疑似 CH 空响应/VPN，拒绝通过"
                )
        for table in L2_TABLES:
            max_date, count = con.execute(
                f"SELECT MAX(trade_date), COUNT(*) FILTER (WHERE trade_date = ?) FROM {table}",
                [date],
            ).fetchone()
            print(f"{table}: rows={count} max={max_date}")
        # 汇总：两个 capital 榜合计为 0 也拦（即便单步漏检）
        if not _l2_allow_all_empty():
            capital_n, = con.execute(
                "SELECT COUNT(*) FROM feature_l2_capital_flow_daily WHERE trade_date = ?",
                [date],
            ).fetchone()
            if capital_n == 0:
                capital_ran = con.execute(
                    """
                    SELECT COUNT(*) FROM ops_pipeline_run_daily
                    WHERE trade_date = ? AND pipeline = 'l2-moneyflow'
                      AND step IN ('limitup', 'top100') AND status = 'complete'
                    """,
                    [date],
                ).fetchone()[0]
                if capital_ran:
                    missing.append(
                        f"feature_l2_capital_flow_daily {date} 合计 0 行但 capital 步骤已 complete；"
                        "拒绝通过（L2_ALLOW_ALL_EMPTY=1 可放行）"
                    )
        return missing
    finally:
        con.close()


def main(argv: list[str] | str | None = None, data_only: bool = False) -> int:
    direct_date = isinstance(argv, str)
    if direct_date:
        argv = [argv]
    if data_only:
        argv = [*(argv or []), "--phase", "data"]
    parser = argparse.ArgumentParser()
    parser.add_argument("date")
    parser.add_argument("--phase", choices=("data", "report", "l2", "all"), default="all")
    parser.add_argument(
        "--plan", default=os.environ.get("REVIEW_SYNC_PLAN") or None,
        help="计划档位（full/cheap/local）；local 按 registry 裁剪期望表与字段。默认读 REVIEW_SYNC_PLAN",
    )
    args = parser.parse_args(argv)

    missing: list[str] = []
    try:
        if args.phase in {"data", "all"}:
            missing.extend(check_data(args.date, plan=args.plan))
        if args.phase in {"report", "all"}:
            missing.extend(check_report(args.date))
        if args.phase in {"l2", "all"}:
            missing.extend(check_l2(args.date))
    except DatabaseLockedError as exc:
        # 检查没有执行成功，完整性未知；不得冒充 INCOMPLETE（缺数）结论。
        print("RESULT: BLOCKED")
        print(f"- 质检闸门未能执行：{exc}")
        print("- 处置：等写进程（sync/backfill）收工后重跑本检查，勿按缺数补录")
        return EXIT_BLOCKED

    print("RESULT:", "INCOMPLETE" if missing else "COMPLETE")
    for item in missing:
        print("-", item)
    if not missing:
        return 0
    return 1 if direct_date else 2


if __name__ == "__main__":
    raise SystemExit(main())
