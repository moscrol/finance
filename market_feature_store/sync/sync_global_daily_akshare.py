"""外盘指数与美股日线：AKShare（新浪）写入链（2026-10-06）。

替代停抓中的复盘会 global-market 接口（2026-09-07 起账号风控；`fact_global_*` 停在 2026-09-02，
另有上游回填时复制旧值的行）。口径与复盘会写入的行一致——2026-10-06 探针逐日核过道指、恒指、
苹果 06-08~06-12 的收盘与涨跌幅，完全相同：

- 主键是 A 股日历日 D；那一行放外盘「日历日 D」那一场，外盘休市取 D 之前最近一场，
  source_trade_date 如实写会话日。绝不拿 D 之后的会话填 D。
- 指数涨跌幅 = 本场收盘 ÷ 上一场收盘 − 1。美股收盘写实际收盘（未复权），涨跌幅与 5 日涨跌按前复权
  序列算（经济收益）——拆股日用未复权收盘相除会算出 -75% 这种假暴跌（2026-10-06 审计实见 CRWD）。
- 美股前复权缺失、错场或收益窗口不完整时跳过该行并记缺口，不用裸价收益兜底；拆股会让这种兜底伪造暴跌。
- 美元市值没有来源，按新值写入的美股行留空；名称、交易所、业务、产业地位沿用该行或该代码最近一行。

只写三类 (A 股日, 代码)：
- gap：表尾之后的 A 股交易日（全宇宙）；表内空洞只计数不写。
- clone：查询层 `finance_query._stale_clone_pairs` 同一判据（收盘与涨跌幅同上一行、涨跌幅非 0、会话日不同）。
- frozen：收盘与涨跌幅同上一行但没被上一条判据认出（会话日也一起被复制），且两条独立证据都成立——
  源头在两行之间确实开过新会话、新会话的真实涨跌幅与库里不同。只满足前者的是合法休市重复或停牌平盘，不动。
写入方式：本行与上一行对应同一场会话（外盘休市）时只改会话日、数值沿用上一行的有效值；
否则写新浪的实际值。默认只算不写；写入只允许落在克隆库上（主库先克隆、验收、再原子换名，见 duckdb-backfill）。
"""

from __future__ import annotations

import math
import time
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

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
STOCK_QFQ_SOURCE = "stock_us_daily_qfq"
SOURCE_PREFIX = "akshare:sina"
SESSION_FIX_SOURCE = f"{SOURCE_PREFIX}/session-fix"
# 断档 / 复制 / 冻结行里取不到数的比例超过它，或任一指数取不到，就停下来问人（任务计划 G8）。
MAX_SKIP_RATIO = 0.05
# 冻结行确认：源头新会话的涨跌幅与库里差超过它（百分点）才算库里是抄来的。
FROZEN_PCT_TOLERANCE = 0.02

# (接口名, 新浪代码) -> [(会话日, 收盘)]。测试注入假的，生产走 AKShare。
Fetcher = Callable[[str, str], list[tuple[date, float]]]

_CLONE_SQL = """
with x as (select {key} as k, trade_date, source_trade_date as s, close, pct_chg,
  lag(close) over w as pc, lag(pct_chg) over w as pp, lag(source_trade_date) over w as ps
  from {table} where trade_date <= ? window w as (partition by {key} order by trade_date))
select k, trade_date from x
where close = pc and pct_chg = pp and pct_chg <> 0 and s <> ps and trade_date >= ?
"""
_FROZEN_CANDIDATE_SQL = """
with x as (select {key} as k, trade_date, source_trade_date as s, close, pct_chg,
  lag(close) over w as pc, lag(pct_chg) over w as pp, lag(source_trade_date) over w as ps
  from {table} where trade_date <= ? window w as (partition by {key} order by trade_date))
select k, trade_date, pct_chg from x
where close = pc and pct_chg = pp and not (pct_chg <> 0 and s <> ps) and trade_date >= ?
"""


@dataclass
class TableReport:
    table: str
    targets: dict[str, int] = field(default_factory=dict)
    computed: int = 0
    written_as: dict[str, int] = field(default_factory=dict)
    skipped: list[dict] = field(default_factory=list)
    samples: list[dict] = field(default_factory=list)
    validation: dict = field(default_factory=dict)


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
    返回 (会话日, 收盘, 涨跌幅%, 5 场涨跌%)。
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


def akshare_fetcher(sleep: float = 0.5) -> Fetcher:
    """真实取数：每次请求后睡 ``sleep`` 秒。新浪接口一次返回整段历史。"""

    import akshare as ak
    import pandas as pd

    def fetch(function: str, symbol: str) -> list[tuple[date, float]]:
        if function == STOCK_SOURCE:
            frame = ak.stock_us_daily(symbol=symbol, adjust="")
        elif function == STOCK_QFQ_SOURCE:
            frame = ak.stock_us_daily(symbol=symbol, adjust="qfq")
        else:
            frame = getattr(ak, function)(symbol=symbol)
        time.sleep(sleep)
        days = pd.to_datetime(frame["date"]).dt.date
        return sorted(
            (day, float(close)) for day, close in zip(days, frame["close"]) if close == close
        )

    return fetch


@dataclass(frozen=True)
class _Spec:
    table: str
    key: str
    is_stock: bool


_INDEX = _Spec("fact_global_index_daily", "code", False)
_STOCK = _Spec("fact_global_stock_daily", "ts_code", True)


def _a_share_days(con, start: date, end: date) -> list[date]:
    rows = con.execute(
        "select distinct trade_date from fact_market_daily where trade_date between ? and ? order by 1",
        [start, end],
    ).fetchall()
    return [row[0] for row in rows]


def plan_rebuild(
    con,
    *,
    start: date,
    end: date,
    fetch: Fetcher,
    complete_before: date | None = None,
    validate_days: int = 60,
) -> dict:
    """算出要写的行与对账结果，不写库。返回 {status, reasons, window, reports, index_rows, stock_rows}。"""

    complete_before = complete_before or date.today()
    days = _a_share_days(con, start, end)
    now = datetime.now()
    out: dict = {}
    reports = []
    index_codes: list[str] = []
    for spec in (_INDEX, _STOCK):
        report = TableReport(spec.table)
        rows, codes = _plan_table(con, spec, days=days, start=start, end=end, fetch=fetch,
                                  complete_before=complete_before, now=now, report=report,
                                  validate_days=validate_days)
        out["stock_rows" if spec.is_stock else "index_rows"] = rows
        if not spec.is_stock:
            index_codes = codes
        reports.append(report)
    status, reasons = _verdict(reports[0], reports[1], index_codes)
    return {
        "status": status,
        "reasons": reasons,
        "window": {"start": start.isoformat(), "end": end.isoformat(), "a_share_days": len(days),
                   "complete_before": complete_before.isoformat()},
        "reports": [vars(report) for report in reports],
        **out,
    }


def _plan_table(con, spec: _Spec, *, days, start, end, fetch, complete_before, now, report: TableReport,
                validate_days: int):
    key, table = spec.key, spec.table
    codes = [row[0] for row in con.execute(f"select distinct {key} from {table} order by 1").fetchall()]
    lookback = start - timedelta(days=40)
    stored: dict[str, dict[date, tuple]] = {}
    if spec.is_stock:
        query = (f"select {key}, trade_date, source_trade_date, close, pct_chg, pct_chg_5d, market_cap_usd, "
                 f"name_cn, name_en, exchange, business, industry_position from {table} where trade_date between ? and ?")
    else:
        query = (f"select {key}, trade_date, source_trade_date, close, pct_chg, null, null, name, market_group, "
                 f"null, null, null from {table} where trade_date between ? and ?")
    for row in con.execute(query, [lookback, end]).fetchall():
        stored.setdefault(str(row[0]), {})[row[1]] = row[2:]
    latest_meta = {}
    if spec.is_stock:
        for row in con.execute(
            "select ts_code, arg_max(name_cn, trade_date), arg_max(name_en, trade_date), arg_max(exchange, trade_date), "
            "arg_max(business, trade_date), arg_max(industry_position, trade_date) from fact_global_stock_daily group by 1"
        ).fetchall():
            latest_meta[row[0]] = row[1:]
    else:
        for row in con.execute(
            "select code, arg_max(name, trade_date), arg_max(market_group, trade_date) from fact_global_index_daily group by 1"
        ).fetchall():
            latest_meta[row[0]] = row[1:]

    last = con.execute(f"select max(trade_date) from {table}").fetchone()[0]
    tail_days = [day for day in days if last is None or day > last]
    gaps = {(code, day) for code in codes for day in tail_days}
    report.validation["internal_holes_not_written"] = sum(
        1 for code in codes for day in days if (last is None or day <= last) and day not in stored.get(code, {})
    )
    clones = {(str(code), day) for code, day in
              con.execute(_CLONE_SQL.format(key=key, table=table), [end, start]).fetchall()}
    candidates = con.execute(_FROZEN_CANDIDATE_SQL.format(key=key, table=table), [end, start]).fetchall()

    histories: dict[str, tuple[_History | None, _History | None]] = {}
    unavailable_returns: dict[tuple[str, date], str] = {}

    def history(code: str) -> tuple[_History | None, _History | None]:
        if code in histories:
            return histories[code]
        try:
            if spec.is_stock:
                main = _History(fetch(STOCK_SOURCE, code))
                try:
                    adjusted = _History(fetch(STOCK_QFQ_SOURCE, code))
                except Exception as exc:  # noqa: BLE001 — 留缺口，不以裸价收益冒充经济收益
                    report.skipped.append({"code": code, "reason": f"adjusted_fetch_failed: {type(exc).__name__}"})
                    adjusted = None
            else:
                function, symbol, _name, _group = INDEX_SOURCES[code]
                main = _History(fetch(function, symbol))
                adjusted = None
        except Exception as exc:  # noqa: BLE001 — 单只取不到记账，不拖垮整批
            report.skipped.append({"code": code, "reason": f"fetch_failed: {type(exc).__name__}"})
            main, adjusted = None, None
        histories[code] = (main or None, adjusted or None)
        return histories[code]

    def returns(code: str, day: date):
        """(会话日, 实际收盘, 涨跌幅, 5 场涨跌)；美股涨跌按前复权口径。"""

        main, adjusted = history(code)
        if not main:
            return None
        values = _session_values(main, day, complete_before)
        if values is None:
            return None
        if spec.is_stock:
            reason = ""
            adjusted_values = None
            if not adjusted:
                reason = "adjusted_history_unavailable"
            else:
                # 当前、前一场和前五场必须是同一组会话；只比最后一天会漏掉中间缺场。
                raw_end = bisect_right(main.dates, values[0])
                adjusted_end = bisect_right(adjusted.dates, values[0])
                raw_days = main.dates[max(0, raw_end - 6):raw_end]
                adjusted_days = adjusted.dates[max(0, adjusted_end - 6):adjusted_end]
                if raw_days != adjusted_days:
                    reason = "adjusted_session_window_mismatch"
                elif any(not math.isfinite(close) or close <= 0
                         for close in adjusted.closes[max(0, adjusted_end - 6):adjusted_end]):
                    reason = "adjusted_invalid_close"
                else:
                    adjusted_values = _session_values(adjusted, day, complete_before)
            if adjusted_values is None:
                unavailable_returns[(code, day)] = reason or "adjusted_no_session"
                return None
            return values[0], values[1], adjusted_values[2], adjusted_values[3]
        return values

    frozen = set()
    for code, day, stored_pct in candidates:
        code = str(code)
        if (code, day) in clones or (spec.table == _INDEX.table and code not in INDEX_SOURCES):
            continue
        earlier = [d for d in stored.get(code, {}) if d < day]
        if not earlier:
            continue
        now_values, prev_values = returns(code, day), returns(code, max(earlier))
        if now_values is None or prev_values is None or now_values[0] == prev_values[0] or now_values[2] is None:
            continue
        # 候选行收盘与上一行相同，而源头确实开了新会话：只有真平盘（真实涨跌≈0 且库里涨跌≈0）才自洽。
        # 真实涨跌不为 0（收盘本该动了）或库里涨跌与真实不符（抄的上一行），都是冻结。
        true_pct = now_values[2]
        flat = abs(true_pct) <= FROZEN_PCT_TOLERANCE and abs(stored_pct or 0.0) <= FROZEN_PCT_TOLERANCE
        if not flat:
            frozen.add((code, day))

    report.targets = {"gap": len(gaps), "clone": len(clones - gaps), "frozen": len(frozen - gaps - clones)}
    kinds = {target: "gap" for target in gaps}
    kinds.update({target: "clone" for target in clones if target not in kinds})
    kinds.update({target: "frozen" for target in frozen if target not in kinds})

    rows: list[tuple] = []
    written_as = {"values": 0, "session_fix": 0}
    by_code: dict[str, list[date]] = {}
    for code, day in kinds:
        by_code.setdefault(code, []).append(day)
    for code in sorted(by_code):
        if not spec.is_stock and code not in INDEX_SOURCES:
            report.skipped.append({"code": code, "reason": "no_source_mapping"})
            continue
        effective = dict(stored.get(code, {}))  # day -> (session, close, pct, pct5, cap, d1..d5)
        for day in sorted(by_code[code]):
            values = returns(code, day)
            if values is None:
                if history(code)[0]:
                    report.skipped.append({"code": code, "day": day.isoformat(),
                                           "reason": unavailable_returns.get((code, day), "no_session")})
                continue
            session, close, pct, pct5 = values
            earlier = [d for d in effective if d < day]
            previous_day = max(earlier) if earlier else None
            previous_session = returns(code, previous_day)[0] if previous_day and returns(code, previous_day) else None
            own = stored.get(code, {}).get(day)
            descriptors = own[5:] if own else latest_meta.get(code, (None,) * (5 if spec.is_stock else 2))
            if not spec.is_stock:
                descriptors = descriptors[:2]
            if previous_day is not None and previous_session == session:
                # 外盘休市：与上一行同一场会话，数值沿用上一行的有效值，只把会话日写对。
                _, close, pct, pct5, cap = effective[previous_day][:5]
                source = SESSION_FIX_SOURCE
                written_as["session_fix"] += 1
            else:
                cap = None
                source = f"{SOURCE_PREFIX}/{STOCK_SOURCE if spec.is_stock else INDEX_SOURCES[code][0]}"
                written_as["values"] += 1
            effective[day] = (session, close, pct, pct5, cap, *descriptors)
            if spec.is_stock:
                name_cn, name_en, exchange, business, position = (tuple(descriptors) + (None,) * 5)[:5]
                rows.append((day, session, code, name_cn, name_en, exchange, close, pct, pct5, cap,
                             business, position, source, now))
            else:
                name, group = (tuple(descriptors) + (None, None))[:2]
                if name is None:
                    name, group = INDEX_SOURCES[code][2], INDEX_SOURCES[code][3]
                rows.append((day, session, code, name, group, close, pct, "final", source, now))
    report.computed = len(rows)
    report.written_as = written_as
    report.samples = [_row_sample(row) for row in rows[:5]]
    report.validation.update(_validate(con, spec, set(kinds), returns, upper=end, validate_days=validate_days))
    return rows, codes


def _row_sample(row: tuple) -> dict:
    stock = len(row) == 14
    return {"trade_date": row[0].isoformat(), "source_trade_date": row[1].isoformat(), "code": row[2],
            "close": row[6] if stock else row[5], "pct_chg": row[7] if stock else row[6],
            "source": row[12] if stock else row[8]}


def _validate(con, spec: _Spec, targets: set, returns, *, upper: date, validate_days: int) -> dict:
    """库内旧行对账：表里最近 ``validate_days`` 个已有交易日上、不在写入目标里的旧行，用新源重算后
    逐行比对收盘、涨跌幅与会话日。旧行来自复盘会，是与新源独立的一份数。"""

    rows = con.execute(
        f"select {spec.key}, trade_date, source_trade_date, close, pct_chg from {spec.table} "
        f"where trade_date <= ? and trade_date >= (select min(trade_date) from (select distinct trade_date "
        f"from {spec.table} where trade_date <= ? order by trade_date desc limit ?))",
        [upper, upper, validate_days],
    ).fetchall()
    checked = exact = session_mismatch = 0
    worst: list[dict] = []
    for code, day, session_day, close, pct in rows:
        if (str(code), day) in targets:
            continue
        values = returns(str(code), day)
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
            worst.append({"code": str(code), "day": day.isoformat(),
                          "old": [session_day.isoformat() if session_day else None, close, pct],
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
        # 每一行要么按新值写、要么只修会话日；对不上说明有行走了第三条没人审过的路。
        if sum(report.written_as.values()) != report.computed:
            reasons.append(f"{report.table} 写入方式计数 {report.written_as} 与算出行数 {report.computed} 对不上")
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
