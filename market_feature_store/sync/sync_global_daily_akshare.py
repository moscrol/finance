"""外盘指数与美股日线：AKShare（新浪）写入链（2026-10-06）。

替代停抓中的复盘会 global-market 接口（2026-09-07 起账号风控；`fact_global_*` 停在 2026-09-02，
另有上游回填时复制旧值的行）。口径与复盘会写入的 2025 行一致——2026-10-06 探针逐日核过
道指、恒指、苹果 06-08~06-12 的收盘与涨跌幅，完全相同：

- 主键是 A 股日历日 D；那一行放外盘「日历日 D」那一场，外盘休市取 D 之前最近一场，
  source_trade_date 如实写会话日。绝不拿 D 之后的会话填 D。
- 涨跌幅 = 本场收盘 ÷ 上一场收盘 − 1（未复权收盘，与复盘会同算法）；美股 5 日涨跌 = 本场 ÷ 五场前 − 1。
- 美元市值没有来源，写入的行留空；名称、交易所、业务、产业地位沿用该代码最近一行。

只写调用方点名的 (A 股日, 代码) 对：断档（目标表缺行的 A 股交易日）与复制旧值（与查询层
`finance_query._stale_clone_pairs` 同一判据）。其余已有行不动。默认只算不写；写入只允许落在
克隆库上（主库先克隆、验收、再原子换名，见 duckdb-backfill）。
"""

from __future__ import annotations

import time
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable

import duckdb

# (code, 接口, 新浪代码, 默认名称, 市场)
INDEX_SOURCES: dict[str, tuple[str, str, str, str]] = {
    "DJI": ("index_us_stock_sina", ".DJI", "道琼斯", "us"),
    "SPX": ("index_us_stock_sina", ".INX", "标普500", "us"),
    "IXIC": ("index_us_stock_sina", ".IXIC", "纳斯达克", "us"),
    "HSI": ("stock_hk_index_daily_sina", "HSI", "恒生指数", "hk"),
    "HKTECH": ("stock_hk_index_daily_sina", "HSTECH", "恒生科技", "hk"),
}
STOCK_SOURCE = "stock_us_daily"
SOURCE_PREFIX = "akshare:sina"
# 断档 / 复制行里取不到数的比例超过它，或任一指数取不到，就停下来问人（任务计划 G8）。
MAX_SKIP_RATIO = 0.05

# (接口名, 新浪代码) -> [(会话日, 收盘)]，按日期升序。测试注入假的，生产走 AKShare。
Fetcher = Callable[[str, str], list[tuple[date, float]]]

_CLONE_SQL = """
with x as (select {key} as k, trade_date, source_trade_date as s, close, pct_chg,
  lag(close) over w as pc, lag(pct_chg) over w as pp, lag(source_trade_date) over w as ps
  from {table} where trade_date <= ? window w as (partition by {key} order by trade_date))
select k, trade_date from x
where close = pc and pct_chg = pp and pct_chg <> 0 and s <> ps and trade_date >= ?
"""


@dataclass
class TableReport:
    table: str
    targets: dict[str, int] = field(default_factory=dict)
    computed: int = 0
    skipped: list[dict] = field(default_factory=list)
    samples: list[dict] = field(default_factory=list)
    validation: dict = field(default_factory=dict)


def akshare_fetcher(sleep: float = 0.5) -> Fetcher:
    """真实取数：每次请求后睡 ``sleep`` 秒。新浪接口一次返回整段历史。"""

    import akshare as ak
    import pandas as pd

    def fetch(function: str, symbol: str) -> list[tuple[date, float]]:
        if function == STOCK_SOURCE:
            frame = ak.stock_us_daily(symbol=symbol, adjust="")
        else:
            frame = getattr(ak, function)(symbol=symbol)
        time.sleep(sleep)
        days = pd.to_datetime(frame["date"]).dt.date
        return sorted(
            (day, float(close)) for day, close in zip(days, frame["close"]) if close == close
        )

    return fetch


def _a_share_days(con, start: date, end: date) -> list[date]:
    rows = con.execute(
        "select distinct trade_date from fact_market_daily where trade_date between ? and ? order by 1",
        [start, end],
    ).fetchall()
    return [row[0] for row in rows]


def _clone_pairs(con, table: str, key: str, start: date, end: date) -> set[tuple[str, date]]:
    rows = con.execute(_CLONE_SQL.format(key=key, table=table), [end, start]).fetchall()
    return {(str(code), day) for code, day in rows}


class _History:
    """取到的一只代码的历史：日期与收盘分列（升序），供二分。"""

    def __init__(self, items: list[tuple[date, float]]):
        ordered = sorted(items)
        self.dates = [item[0] for item in ordered]
        self.closes = [item[1] for item in ordered]

    def __bool__(self) -> bool:
        return bool(self.dates)


def _session_values(
    history: _History, day: date, complete_before: date
) -> tuple[date, float, float | None, float | None] | None:
    """A 股日 ``day`` 对应的会话：日历日 ``day`` 那一场，休市取之前最近一场。

    只用 ``complete_before`` 之前已收完的会话，也绝不用 ``day`` 之后的会话（无前视）。
    """

    bound = min(day, complete_before - timedelta(days=1))
    index = bisect_right(history.dates, bound)
    if index <= 0:
        return None
    closes = history.closes
    session, close = history.dates[index - 1], closes[index - 1]
    previous = closes[index - 2] if index >= 2 else None
    five_back = closes[index - 6] if index >= 6 else None
    pct = (close / previous - 1) * 100 if previous else None
    pct5 = (close / five_back - 1) * 100 if five_back else None
    return session, close, pct, pct5


def _targets(con, table: str, key: str, codes: Iterable[str], days: list[date], start: date, end: date):
    """断档 = 表尾之后的 A 股交易日（全宇宙）；复制行 = 查询层同一判据。内部空洞只计数不写。"""

    existing = {
        (str(code), day)
        for code, day in con.execute(
            f"select {key}, trade_date from {table} where trade_date between ? and ?", [start, end]
        ).fetchall()
    }
    last = con.execute(f"select max(trade_date) from {table}").fetchone()[0]
    tail_days = [day for day in days if last is None or day > last]
    gaps = {(code, day) for code in codes for day in tail_days}
    holes = sum(1 for code in codes for day in days if (last is None or day <= last) and (code, day) not in existing)
    clones = _clone_pairs(con, table, key, start, end)
    return gaps, clones, holes


def plan_rebuild(
    con,
    *,
    start: date,
    end: date,
    fetch: Fetcher,
    complete_before: date | None = None,
    validate_days: int = 60,
) -> dict:
    """算出要写的行与对账结果，不写库。返回 {status, reports, index_rows, stock_rows}。"""

    complete_before = complete_before or date.today()
    days = _a_share_days(con, start, end)
    index_codes = [row[0] for row in con.execute("select distinct code from fact_global_index_daily order by 1").fetchall()]
    stock_codes = [row[0] for row in con.execute("select distinct ts_code from fact_global_stock_daily order by 1").fetchall()]
    now = datetime.now()

    index_report = TableReport("fact_global_index_daily")
    stock_report = TableReport("fact_global_stock_daily")
    index_gaps, index_clones, index_holes = _targets(con, "fact_global_index_daily", "code", index_codes, days, start, end)
    stock_gaps, stock_clones, stock_holes = _targets(con, "fact_global_stock_daily", "ts_code", stock_codes, days, start, end)
    index_report.targets = {"gap": len(index_gaps), "clone": len(index_clones - index_gaps)}
    stock_report.targets = {"gap": len(stock_gaps), "clone": len(stock_clones - stock_gaps)}
    index_report.validation["internal_holes_not_written"] = index_holes
    stock_report.validation["internal_holes_not_written"] = stock_holes

    histories: dict[str, list[tuple[date, float]] | None] = {}

    def history(code: str, function: str, symbol: str, report: TableReport):
        if code not in histories:
            try:
                histories[code] = _History(fetch(function, symbol))
            except Exception as exc:  # noqa: BLE001 — 单只取不到记账，不拖垮整批
                histories[code] = None
                report.skipped.append({"code": code, "reason": f"fetch_failed: {type(exc).__name__}"})
        return histories[code]

    index_meta = {
        code: (name, group)
        for code, name, group in con.execute(
            "select code, arg_max(name, trade_date), arg_max(market_group, trade_date) from fact_global_index_daily group by 1"
        ).fetchall()
    }
    stock_meta = {
        row[0]: row[1:]
        for row in con.execute(
            "select ts_code, arg_max(name_cn, trade_date), arg_max(name_en, trade_date), arg_max(exchange, trade_date), "
            "arg_max(business, trade_date), arg_max(industry_position, trade_date) from fact_global_stock_daily group by 1"
        ).fetchall()
    }

    index_rows: list[tuple] = []
    for code, day in sorted(index_gaps | index_clones):
        function, symbol, default_name, default_group = INDEX_SOURCES.get(code, (None, None, code, None))
        if function is None:
            index_report.skipped.append({"code": code, "day": day.isoformat(), "reason": "no_source_mapping"})
            continue
        values = history(code, function, symbol, index_report)
        session = _session_values(values, day, complete_before) if values else None
        if session is None:
            if values:
                index_report.skipped.append({"code": code, "day": day.isoformat(), "reason": "no_session"})
            continue
        name, group = index_meta.get(code, (default_name, default_group))
        session_day, close, pct, _ = session
        index_rows.append((day, session_day, code, name, group, close, pct, "final", f"{SOURCE_PREFIX}/{function}", now))
    index_report.computed = len(index_rows)

    stock_rows: list[tuple] = []
    for code, day in sorted(stock_gaps | stock_clones):
        values = history(code, STOCK_SOURCE, code, stock_report)
        session = _session_values(values, day, complete_before) if values else None
        if session is None:
            if values:
                stock_report.skipped.append({"code": code, "day": day.isoformat(), "reason": "no_session"})
            continue
        name_cn, name_en, exchange, business, position = stock_meta.get(code, (None, None, None, None, None))
        session_day, close, pct, pct5 = session
        stock_rows.append((day, session_day, code, name_cn, name_en, exchange, close, pct, pct5, None,
                           business, position, f"{SOURCE_PREFIX}/{STOCK_SOURCE}", now))
    stock_report.computed = len(stock_rows)

    for report, rows in ((index_report, index_rows), (stock_report, stock_rows)):
        report.samples = [_row_sample(row) for row in rows[:5]]
    index_report.validation.update(_validate(con, "fact_global_index_daily", "code", histories, upper=end,
                                             validate_days=validate_days, clones=index_clones,
                                             complete_before=complete_before))
    stock_report.validation.update(_validate(con, "fact_global_stock_daily", "ts_code", histories, upper=end,
                                             validate_days=validate_days, clones=stock_clones,
                                             complete_before=complete_before))

    status, reasons = _verdict(index_report, stock_report, index_codes)
    return {
        "status": status,
        "reasons": reasons,
        "window": {"start": start.isoformat(), "end": end.isoformat(), "a_share_days": len(days),
                   "complete_before": complete_before.isoformat()},
        "reports": [vars(index_report), vars(stock_report)],
        "index_rows": index_rows,
        "stock_rows": stock_rows,
    }


def _row_sample(row: tuple) -> dict:
    return {"trade_date": row[0].isoformat(), "source_trade_date": row[1].isoformat(), "code": row[2],
            "close": row[5] if len(row) == 10 else row[6], "pct_chg": row[6] if len(row) == 10 else row[7]}


def _validate(con, table, key, histories, *, upper, validate_days, clones, complete_before):
    """库内旧行对账：表里最近 ``validate_days`` 个已有交易日上、非复制的旧行，用新源重算后逐行比对
    收盘、涨跌幅与会话日。旧行来自复盘会，是与新源独立的一份数。"""

    rows = con.execute(
        f"select {key}, trade_date, source_trade_date, close, pct_chg from {table} "
        f"where trade_date <= ? and trade_date >= (select min(trade_date) from (select distinct trade_date "
        f"from {table} where trade_date <= ? order by trade_date desc limit ?))",
        [upper, upper, validate_days],
    ).fetchall()
    checked = exact = session_mismatch = 0
    worst: list[dict] = []
    for code, day, session_day, close, pct in rows:
        if (str(code), day) in clones or not histories.get(str(code)):
            continue
        values = _session_values(histories[str(code)], day, complete_before)
        if values is None:
            continue
        checked += 1
        new_session, new_close, new_pct, _ = values
        close_ok = close is not None and abs(new_close - close) <= max(1e-6, abs(close) * 1e-6)
        pct_ok = pct is None or new_pct is None or abs(new_pct - pct) <= 0.005
        if new_session != session_day:
            session_mismatch += 1
        if close_ok and pct_ok and new_session == session_day:
            exact += 1
        elif len(worst) < 10:
            worst.append({"code": str(code), "day": day.isoformat(), "old": [session_day.isoformat() if session_day else None, close, pct],
                          "new": [new_session.isoformat(), new_close, new_pct]})
    return {"checked": checked, "exact": exact, "session_mismatch": session_mismatch,
            "exact_ratio": round(exact / checked, 4) if checked else None, "mismatches": worst}


def _verdict(index_report: TableReport, stock_report: TableReport, index_codes: list[str]) -> tuple[str, list[str]]:
    reasons = []
    failed_indices = {item["code"] for item in index_report.skipped}
    if failed_indices & set(index_codes):
        reasons.append(f"指数取不到：{sorted(failed_indices & set(index_codes))}")
    for report in (index_report, stock_report):
        total = sum(report.targets.values())
        missing = total - report.computed
        if total and missing / total > MAX_SKIP_RATIO:
            reasons.append(f"{report.table} 缺口 {missing}/{total} 超过 {MAX_SKIP_RATIO:.0%}")
    return ("needs_user" if reasons else "ok"), reasons


def apply_rows(con, index_rows: list[tuple], stock_rows: list[tuple]) -> dict:
    """把算好的行 UPSERT 进 ``con`` 指向的库（只该是克隆库）。一个事务，全成或全不成。"""

    con.execute("begin")
    try:
        if index_rows:
            con.executemany(
                """insert into fact_global_index_daily
                   (trade_date, source_trade_date, code, name, market_group, close, pct_chg, data_stage, source, updated_at)
                   values (?,?,?,?,?,?,?,?,?,?)
                   on conflict (trade_date, code) do update set
                     source_trade_date = excluded.source_trade_date, name = excluded.name,
                     market_group = excluded.market_group, close = excluded.close, pct_chg = excluded.pct_chg,
                     data_stage = excluded.data_stage, source = excluded.source, updated_at = excluded.updated_at""",
                index_rows,
            )
        if stock_rows:
            con.executemany(
                """insert into fact_global_stock_daily
                   (trade_date, source_trade_date, ts_code, name_cn, name_en, exchange, close, pct_chg, pct_chg_5d,
                    market_cap_usd, business, industry_position, source, updated_at)
                   values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   on conflict (trade_date, ts_code) do update set
                     source_trade_date = excluded.source_trade_date, name_cn = excluded.name_cn,
                     name_en = excluded.name_en, exchange = excluded.exchange, close = excluded.close,
                     pct_chg = excluded.pct_chg, pct_chg_5d = excluded.pct_chg_5d,
                     market_cap_usd = excluded.market_cap_usd, business = excluded.business,
                     industry_position = excluded.industry_position, source = excluded.source,
                     updated_at = excluded.updated_at""",
                stock_rows,
            )
        con.execute("commit")
    except Exception:
        con.execute("rollback")
        raise
    return {"index_rows": len(index_rows), "stock_rows": len(stock_rows)}


def run(
    db_path: Path,
    *,
    start: date,
    end: date,
    apply: bool,
    main_db_path: Path,
    fetch: Fetcher | None = None,
    complete_before: date | None = None,
    validate_days: int = 60,
) -> dict:
    """CLI 入口。``apply`` 只在状态 ok 且 ``db_path`` 不是主库时写。"""

    db_path = Path(db_path).expanduser().resolve()
    if apply and db_path == Path(main_db_path).expanduser().resolve():
        return {"status": "refused", "reasons": ["--apply 不写主库：先 clone_to_staging，在克隆库上写入并验收，再原子换名"]}
    con = duckdb.connect(str(db_path), read_only=not apply)
    try:
        plan = plan_rebuild(con, start=start, end=end, fetch=fetch or akshare_fetcher(),
                            complete_before=complete_before, validate_days=validate_days)
        result = {key: value for key, value in plan.items() if key not in {"index_rows", "stock_rows"}}
        result["applied"] = None
        if apply and plan["status"] == "ok":
            result["applied"] = apply_rows(con, plan["index_rows"], plan["stock_rows"])
        return result
    finally:
        con.close()
