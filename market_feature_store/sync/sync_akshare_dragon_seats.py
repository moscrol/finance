"""龙虎榜席位明细换源：akshare（东方财富数据中心）替代复盘会 /data/dragon/detail。

为什么：席位明细是复盘会配额第二大消耗（逐股一次 detail，45~105 请求/日），而它
本质是交易所公开披露，东财与复盘会同源。2026-09-04 实测 002536.SZ @09-02：深股通专用
买 1.515e8 元 / 占比 0.046482 ↔ 复盘会 1.52 亿 / 4.65%，三个席位逐项对上。

单位与口径换算（写进代码而不是只写在文档里，见 to_rows）：
- 金额：东财 元 → 表内 亿（÷1e8）
- 占比：东财 小数（0.0465）→ 表内 %（×100）
- seat_type / hm_name 是复盘会增值标注。这里按席位名启发式：
  「机构专用」→ 机构；带「股通」→ 游资且 hm_name = 席位名（复盘会实测就是这么标的）；
  其余 → 营业部，hm_name 留 NULL，不伪造游资识别。

名单来自 fact_dragon_tiger_daily（复盘会榜单，1 请求，仍保留）——不再向东财另拉榜单，
两张表的股票集合天然一致。
"""
from __future__ import annotations

from datetime import date, datetime
import time

from ..db import connect, init_db

SOURCE = "akshare:eastmoney/lhb-stock-detail"

# akshare stock_lhb_stock_detail_em 的返回列（2026-09 实测 akshare 1.18.64）。
COL_SEAT = "交易营业部名称"
COL_BUY = "买入金额"
COL_BUY_RATE = "买入金额-占总成交比例"
COL_SELL = "卖出金额"
COL_SELL_RATE = "卖出金额-占总成交比例"
COL_NET = "净额"


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _num(val):
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def _yi(val):
    f = _num(val)
    return None if f is None else round(f / 1e8, 4)


def _pct(val):
    f = _num(val)
    return None if f is None else round(f * 100.0, 4)


def classify_seat(exalter: str) -> tuple[str, str | None]:
    """席位名 → (seat_type, hm_name)。"""
    name = (exalter or "").strip()
    if "机构专用" in name:
        return "机构", None
    if "股通" in name:
        return "游资", name
    return "营业部", None


def _symbol(ts_code: str) -> str:
    return str(ts_code).split(".")[0]


def to_rows(
    frame,
    *,
    trade_date: date,
    stock_ts_code: str,
    stock_name: str | None,
    side: str,
    now: datetime,
) -> list[tuple]:
    """把一侧（买入/卖出）的 DataFrame 压成 fact_dragon_seat_daily 的行。"""
    rows: list[tuple] = []
    if frame is None or getattr(frame, "empty", True):
        return rows
    seen: set[str] = set()
    for idx, rec in enumerate(frame.to_dict("records"), start=1):
        exalter = str(rec.get(COL_SEAT) or "").strip()
        if not exalter or exalter in seen:
            continue
        seen.add(exalter)
        seat_type, hm_name = classify_seat(exalter)
        buy = _yi(rec.get(COL_BUY))
        sell = _yi(rec.get(COL_SELL))
        net = _yi(rec.get(COL_NET))
        if net is None and buy is not None and sell is not None:
            net = round(buy - sell, 4)
        rows.append(
            (
                trade_date,
                stock_ts_code,
                stock_name,
                side,
                idx,
                exalter,
                seat_type,
                hm_name,
                buy,
                sell,
                _pct(rec.get(COL_BUY_RATE)),
                _pct(rec.get(COL_SELL_RATE)),
                net,
                SOURCE,
                now,
            )
        )
    return rows


UPSERT_SQL = """
    INSERT INTO fact_dragon_seat_daily
        (trade_date, stock_ts_code, stock_name, side, seat_no, exalter,
         seat_type, hm_name, buy, sell, buy_rate, sell_rate, net_buy,
         source, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date, stock_ts_code, side, exalter) DO UPDATE SET
        stock_name = excluded.stock_name,
        seat_no = excluded.seat_no,
        seat_type = excluded.seat_type,
        hm_name = excluded.hm_name,
        buy = excluded.buy,
        sell = excluded.sell,
        buy_rate = excluded.buy_rate,
        sell_rate = excluded.sell_rate,
        net_buy = excluded.net_buy,
        source = excluded.source,
        updated_at = excluded.updated_at
"""


def _listing(con, td: date) -> list[tuple[str, str | None]]:
    return con.execute(
        "SELECT stock_ts_code, stock_name FROM fact_dragon_tiger_daily WHERE trade_date = ? ORDER BY 1",
        [td],
    ).fetchall()


def sync_dragon_seats_akshare(
    trade_date,
    *,
    con=None,
    sleep: float = 0.1,
    fetch=None,
) -> dict:
    """逐股两次 akshare 调用（买入/卖出），写 fact_dragon_seat_daily。

    ``fetch(symbol, yyyymmdd, flag) -> DataFrame`` 可注入（测试 / 换实现）；默认 akshare。
    单股失败不拖垮整日：记入 errors，缺行由调用方决定是否回退复盘会。
    """
    td = _as_date(trade_date)
    if fetch is None:
        import akshare as ak  # noqa: PLC0415 —— 只有真跑时才需要

        fetch = ak.stock_lhb_stock_detail_em
    own = con is None
    if own:
        init_db()
        con = connect()
    try:
        listing = _listing(con, td)
        if not listing:
            return {"rows": 0, "stocks": 0, "errors": {}, "note": "fact_dragon_tiger_daily 当日无榜单，先跑 dragon"}
        now = datetime.now()
        ymd = td.strftime("%Y%m%d")
        rows: list[tuple] = []
        errors: dict[str, str] = {}
        for ts_code, name in listing:
            for side, flag in (("buy", "买入"), ("sell", "卖出")):
                try:
                    frame = fetch(symbol=_symbol(ts_code), date=ymd, flag=flag)
                except Exception as exc:  # noqa: BLE001
                    errors[f"{ts_code}:{side}"] = f"{type(exc).__name__}: {str(exc)[:80]}"
                    continue
                rows.extend(
                    to_rows(frame, trade_date=td, stock_ts_code=ts_code, stock_name=name, side=side, now=now)
                )
                if sleep:
                    time.sleep(sleep)
        if rows:
            con.execute("BEGIN TRANSACTION")
            try:
                con.executemany(UPSERT_SQL, rows)
                con.execute("COMMIT")
            except Exception:
                con.execute("ROLLBACK")
                raise
    finally:
        if own:
            con.close()
    return {"rows": len(rows), "stocks": len(listing), "errors": errors, "source": SOURCE}
