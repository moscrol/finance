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
    "fact_core_stock_daily",
    "fact_core_leader_daily",
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
    """按计划返回 (要检查的表, 要检查的 fact_market_daily 字段)。

    两个方向都从 ``consumption_registry`` 派生，不在这里写第二份名单：
    - local 只查 local 会写的表（fupanhui 独有的那些缺行是设计）；
    - full/cheap 也要**减掉**该计划根本不产的表（如 ``fact_core_leader_daily`` 只在 local 链路里算），
      否则把它加进 TABLES 就会让全量日凭空报缺。
    """
    from market_feature_store.consumption_registry import load_registry, tables_for_plan

    registry = load_registry()
    plan_key = "full" if (not plan or plan == "auto") else plan
    expected = tables_for_plan(registry, plan_key) | set(FEATURE_FAMILY)
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
        missing.extend(_check_stock_daily_not_copied(con, date))
        missing.extend(_check_fill_rates(con, date))
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


#: 当日个股日线与前一交易日逐股 (close, amount) 完全相同的比例超过这条线 → 判为「整天是复制」。
#: 真实市场里相邻两天同一只股收盘价与成交额都一模一样的极少 (长期停牌股), 5% 已经是很宽的线;
#: 2026-07-20 / 08-06 两次事故各是 99.96% / 100%。
STOCK_DAILY_DUP_MAX = 0.05


def _check_stock_daily_not_copied(con, date: str) -> list[str]:
    """个股日线不能是前一交易日的整份复制（工单 #32）。

    事故形状：东财快照只有「最新」语义，事后补历史日会把次日截面贴到历史日期上，整天 5500 行逐股与
    相邻日相同——行数、覆盖率、字段非空全部正常，只有逐股比对能看出来。这里比的是**前一交易日**：
    门禁跑在当天，「当天 == 前一天」抓的是「拿昨天的快照写今天」；「今天 == 明天」在当天还没法比，
    由 `qa_local_vs_fupanhui.py` 的全历史扫描兜底。
    """
    problems: list[str] = []
    row = con.execute(
        """
        WITH prev AS (
          SELECT MAX(trade_date) d FROM fact_stock_daily WHERE trade_date < ?
        )
        SELECT prev.d, COUNT(*),
               COUNT(*) FILTER (WHERE a.close = b.close AND a.amount = b.amount)
        FROM fact_stock_daily a
        JOIN fact_stock_daily b ON b.stock_ts_code = a.stock_ts_code
        JOIN prev ON b.trade_date = prev.d
        WHERE a.trade_date = ? AND a.close IS NOT NULL AND a.amount IS NOT NULL
        GROUP BY prev.d
        """,
        [date, date],
    ).fetchone()
    if not row or not row[1]:
        return problems  # 没有前一日或当日无行, 交给覆盖率/缺行检查去报
    prev_date, paired, same = row
    ratio = same / paired
    print(f"fact_stock_daily 与前一交易日 {prev_date} 逐股相同: {same}/{paired} = {ratio:.2%}")
    if ratio > STOCK_DAILY_DUP_MAX:
        problems.append(
            f"fact_stock_daily {date} 与 {prev_date} 逐股 close+amount 相同 {ratio:.1%} > {STOCK_DAILY_DUP_MAX:.0%}"
            f"——像是拿旧快照写了新日期 (07-20/08-06 同型)，用 mootdx sync-stock-daily --refresh 重抓"
        )
    return problems


#: 第四层拦截（2026-09-08 评审）：前三层（快照日期闸 / 相邻日复制扫描 / 当日逐股相同）只覆盖「复制 / 错日」
#: 一族，没有一层看空值。事实：`fact_market_daily.sh_index_pct_chg` 在 2026-08-17 为 NULL，事件定价当晚因此丢了
#: 77 个 market 锚点里的 3 个；`fact_stock_daily` 2025-09-19 的 pct_chg 填充率只有 79%，没人知道。
#: 这一层看**全历史**：必填列只许在钉住的日期为空、个股三列逐日填充率不得低于阈值；基线是 git 里的 JSON，
#: 改动走 diff 让人看见。基线只钉「已知的洞」，洞补上了不用改基线（少一个空值日不报）。
FILL_RATE_BASELINE_PATH = ROOT / "fill-rate-baseline.json"
STOCK_FILL_COLUMNS = ("close", "amount", "pct_chg")
#: 已知缺口再恶化多少个百分点算回归（同一天同一列，填充率比钉住的值还低）。
FILL_GAP_TOLERANCE_PCT = 0.5


def load_fill_rate_baseline(path: Path = FILL_RATE_BASELINE_PATH) -> dict:
    import json

    if not path.exists():
        return {"fact_market_daily": {"known_null_dates": {}}, "fact_stock_daily": {"min_fill_pct": {}, "known_gaps": []}}
    return json.loads(path.read_text(encoding="utf-8"))


def _fill_rate_scan(con) -> dict:
    """真库现状：必填列的空值日、个股三列逐日填充率。只读，不判。"""
    market_null_dates: dict[str, list[str]] = {}
    for field in MARKET_FIELDS:
        try:
            rows = con.execute(
                f'SELECT trade_date FROM fact_market_daily WHERE "{field}" IS NULL ORDER BY 1'
            ).fetchall()
        except Exception as exc:  # noqa: BLE001 - 字段不存在由当日检查报，这里不重复
            print(f"fill-rate: fact_market_daily.{field} 跳过（{exc.__class__.__name__}）")
            continue
        market_null_dates[field] = [str(r[0]) for r in rows]
    selects = ", ".join(
        f"ROUND(100.0 * COUNT({c}) / COUNT(*), 2) AS {c}_pct" for c in STOCK_FILL_COLUMNS
    )
    try:
        stock_rows = con.execute(
            f"SELECT trade_date, COUNT(*), {selects} FROM fact_stock_daily GROUP BY trade_date ORDER BY trade_date"
        ).fetchall()
    except Exception as exc:  # noqa: BLE001 - 表不存在由 TABLES 行数检查报
        print(f"fill-rate: fact_stock_daily 跳过（{exc.__class__.__name__}）")
        stock_rows = []
    stock_fill = {
        str(r[0]): {"rows": int(r[1]), **{c: float(r[2 + i]) for i, c in enumerate(STOCK_FILL_COLUMNS)}}
        for r in stock_rows
    }
    return {"fact_market_daily": market_null_dates, "fact_stock_daily": stock_fill}


def _check_fill_rates(con, date: str, baseline: dict | None = None) -> list[str]:
    """第四层拦截：全历史逐列填充率闸，对钉住的基线只许变好。

    - `fact_market_daily` 必填列（MARKET_FIELDS）：出现基线之外的空值日即报。当日那一行由上面的
      逐字段检查报，这里排除 `date` 免得同一件事报两遍。
    - `fact_stock_daily` close / amount / pct_chg：任一交易日填充率低于阈值且不在已知缺口里即报；
      已知缺口再掉超过 FILL_GAP_TOLERANCE_PCT 也报（钉的是「不许更坏」）。
    """
    baseline = baseline if baseline is not None else load_fill_rate_baseline()
    scan = _fill_rate_scan(con)
    problems: list[str] = []

    known_null = baseline.get("fact_market_daily", {}).get("known_null_dates", {})
    for field, null_dates in scan["fact_market_daily"].items():
        extra = sorted(set(null_dates) - set(known_null.get(field, [])) - {date})
        if extra:
            shown = ",".join(extra[:6]) + ("…" if len(extra) > 6 else "")
            problems.append(
                f"fact_market_daily.{field} 出现基线之外的空值日 {len(extra)} 个: {shown}"
                "——历史行被写空或补数漏列（08-17 同型），修数后若确认不可补再钉进 fill-rate-baseline.json"
            )

    stock_cfg = baseline.get("fact_stock_daily", {})
    min_fill = stock_cfg.get("min_fill_pct", {})
    known_gaps = {
        (g["trade_date"], g["column"]): float(g.get("fill_pct", 0.0))
        for g in stock_cfg.get("known_gaps", [])
    }
    for day, stats in scan["fact_stock_daily"].items():
        for column in STOCK_FILL_COLUMNS:
            threshold = min_fill.get(column)
            if threshold is None:
                continue
            pct = stats[column]
            if pct >= threshold:
                continue
            pinned = known_gaps.get((day, column))
            if pinned is None:
                problems.append(
                    f"fact_stock_daily {day} {column} 填充率 {pct:.2f}% < {threshold:.0f}%（{stats['rows']} 行）"
                    "——不在已知缺口里；先查源再决定补数还是钉基线"
                )
            elif pct < pinned - FILL_GAP_TOLERANCE_PCT:
                problems.append(
                    f"fact_stock_daily {day} {column} 填充率 {pct:.2f}% 比已知缺口钉住的 {pinned:.2f}% 更低——已知的洞变大了"
                )
    scanned_days = len(scan["fact_stock_daily"])
    print(f"fill-rate: fact_market_daily {len(scan['fact_market_daily'])} 列 / fact_stock_daily {scanned_days} 日已扫，问题 {len(problems)}")
    return problems


def update_fill_rate_baseline(con, path: Path = FILL_RATE_BASELINE_PATH, *, today: str | None = None) -> dict:
    """把真库现状写成基线：已有缺口的 reason 保留，新缺口标「待查」。写出的 diff 就是评审对象。"""
    import json

    previous = load_fill_rate_baseline(path)
    scan = _fill_rate_scan(con)
    prev_gaps = {
        (g["trade_date"], g["column"]): g for g in previous.get("fact_stock_daily", {}).get("known_gaps", [])
    }
    min_fill = previous.get("fact_stock_daily", {}).get("min_fill_pct") or {c: 99.0 for c in STOCK_FILL_COLUMNS}
    gaps = []
    for day, stats in scan["fact_stock_daily"].items():
        for column in STOCK_FILL_COLUMNS:
            if stats[column] < min_fill.get(column, 99.0):
                old = prev_gaps.get((day, column), {})
                gaps.append({
                    "trade_date": day,
                    "column": column,
                    "fill_pct": stats[column],
                    "rows": stats["rows"],
                    "reason": old.get("reason") or f"待查（{today or 'unknown'} 填充率闸量出）",
                })
    baseline = {
        "_doc": previous.get("_doc") or (
            "第四层拦截：逐列填充率闸（check_daily_review_data._check_fill_rates）。"
            "fact_market_daily 必填列全历史只许在这里钉住的日期为空；fact_stock_daily 三列逐日填充率 ≥ min_fill_pct，"
            "已知缺口带原因列在 known_gaps。更新：check_daily_review_data.py <date> --update-fill-rate-baseline，改动进 git diff。"
        ),
        "fact_market_daily": {"known_null_dates": scan["fact_market_daily"]},
        "fact_stock_daily": {"min_fill_pct": min_fill, "known_gaps": gaps},
    }
    path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return baseline


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
    parser.add_argument(
        "--update-fill-rate-baseline", action="store_true",
        help="只做一件事：把真库现状写进 fill-rate-baseline.json（已有缺口的 reason 保留，新缺口标待查），然后退出",
    )
    args = parser.parse_args(argv)

    missing: list[str] = []
    try:
        if args.update_fill_rate_baseline:
            con = _connect_read_only()
            try:
                baseline = update_fill_rate_baseline(con, today=args.date)
            finally:
                con.close()
            gaps = baseline["fact_stock_daily"]["known_gaps"]
            print(f"fill-rate-baseline.json 已写：fact_market_daily {len(baseline['fact_market_daily']['known_null_dates'])} 列，fact_stock_daily 已知缺口 {len(gaps)} 条")
            for g in gaps:
                print(f"- {g['trade_date']} {g['column']} {g['fill_pct']}% — {g['reason']}")
            return 0
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
