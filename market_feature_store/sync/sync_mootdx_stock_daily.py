"""mootdx 全A股日线 -> fact_stock_daily (历史回补的日期参数化源)。

数据源: mootdx (通达信 TCP 7709)。不封 IP, 免费, 批量快, 一次可拉 800 根。
逐只抓取并写入, 默认跳过区间内已抓的股票, 可中断/续跑 (类似 sector-stocks)。

口径:
- amount 统一存为「亿」(mootdx 原始单位为元, /1e8), 与 fact_sector_daily 一致。
- 默认 qfq=False 存**裸收盘价**(与东财快照同基); pre_close = 前一根裸收盘,
  所以除息日 pct_chg 含股息缺口 (东财 f18 是除息调整后的昨收)。qfq=True 才是前复权。
- open/high/low/volume (2026-09-07 起): 新高/振幅等派生只能用日内最高价算, 收盘价算不出
  fupanhui 的新高家数 (双轨对账差 ±20%)。volume 单位「手」, 与东财 f5 一致。
- stock_name: TDX 定长字段带 \\x00 填充, 写入前剥掉 (2026-09-07 之前 29.9 万行带 NUL)。

ohlc_only=True: 只补 open/high/low/volume, 不碰东财行的 close/pre_close/pct_chg/name/source。
用于给已有的东财日线补齐 OHLC, 以及拉 3 年历史时对已有日期只填洞。
"""
from __future__ import annotations

import math
import re
import signal
import sys
import time
from datetime import datetime

from ..db import connect, init_db


class _BarsTimeout(Exception):
    """单只 mootdx bars 请求超时。"""


def _fetch_bars(client, code: str, offset: int, qfq: bool, timeout: int):
    """抓取单只日线; timeout>0 时用 SIGALRM 兜底, 卡住的请求超时即中断。

    SIGALRM 仅在主线程的类 Unix 平台可用; 不可用时退化为无超时直接抓取。
    """
    def _call():
        if qfq:
            return client.bars(symbol=code, frequency=9, offset=offset, adjust="qfq")
        return client.bars(symbol=code, frequency=9, offset=offset)

    if timeout and timeout > 0 and hasattr(signal, "SIGALRM"):
        def _handler(signum, frame):  # noqa: ANN001
            raise _BarsTimeout(f"bars timeout after {timeout}s")

        old = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(int(timeout))
        try:
            return _call()
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
    return _call()

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _isnan(x) -> bool:
    try:
        return math.isnan(float(x))
    except (TypeError, ValueError):
        return False

# 沪(6) / 深(0,3) / 北(8x,920) A股代码前缀
A_SHARE_PREFIXES = (
    "600", "601", "603", "605", "688", "689",
    "000", "001", "002", "003", "300", "301",
    "830", "831", "832", "833", "834", "835", "836", "837", "838", "839",
    "870", "871", "872", "873", "920",
)

FLUSH_EVERY = 200  # 每抓多少只 flush 一次

# 2026-09-07 加的日内价量列。老库靠 ensure_stock_daily_columns 追加; schema.sql 同步声明。
OHLC_COLUMNS = {"open": "DOUBLE", "high": "DOUBLE", "low": "DOUBLE", "volume": "DOUBLE"}

COLS = ["trade_date", "stock_ts_code", "stock_name", "close", "pre_close",
        "pct_chg", "amount", "turnover", "source", "updated_at",
        "open", "high", "low", "volume"]

_COL_LIST = ", ".join(COLS)

# 一次性批量 upsert (INSERT ... SELECT from DataFrame), 远快于逐行 executemany。
# 显式列清单: 老库 ALTER 追加的列顺序与 schema.sql 里新建的可能不同, SELECT * 会串位。
BULK_UPSERT_SQL = f"""
    INSERT INTO fact_stock_daily ({_COL_LIST}) SELECT {_COL_LIST} FROM _buf_df
    ON CONFLICT (trade_date, stock_ts_code) DO UPDATE SET
        stock_name = EXCLUDED.stock_name,
        close = EXCLUDED.close,
        pre_close = EXCLUDED.pre_close,
        pct_chg = EXCLUDED.pct_chg,
        amount = EXCLUDED.amount,
        turnover = EXCLUDED.turnover,
        source = EXCLUDED.source,
        updated_at = EXCLUDED.updated_at,
        open = COALESCE(EXCLUDED.open, fact_stock_daily.open),
        high = COALESCE(EXCLUDED.high, fact_stock_daily.high),
        low = COALESCE(EXCLUDED.low, fact_stock_daily.low),
        volume = COALESCE(EXCLUDED.volume, fact_stock_daily.volume)
"""

# 只填 OHLC: 已有行 (多为东财快照) 的收盘/昨收/涨幅/名字/来源一律不动。
BULK_UPSERT_OHLC_ONLY_SQL = f"""
    INSERT INTO fact_stock_daily ({_COL_LIST}) SELECT {_COL_LIST} FROM _buf_df
    ON CONFLICT (trade_date, stock_ts_code) DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        volume = EXCLUDED.volume
"""


def ensure_stock_daily_columns(con) -> None:
    """老库补列 (幂等)。init_db 的 CREATE TABLE IF NOT EXISTS 不会给已有表加列。"""
    for name, typ in OHLC_COLUMNS.items():
        con.execute(f"ALTER TABLE fact_stock_daily ADD COLUMN IF NOT EXISTS {name} {typ}")


def clean_name(name) -> str:
    """TDX 定长字段的 \\x00 填充 + 首尾空白。"""
    return str(name or "").replace("\x00", "").strip()


def _ts_code(code: str) -> str:
    if code.startswith("6"):
        return code + ".SH"
    if code.startswith(("0", "3")):
        return code + ".SZ"
    return code + ".BJ"  # 8xx / 920 北交所


def get_universe(client) -> list[tuple[str, str]]:
    """从 mootdx 全证券里按前缀过滤出 A 股, 返回 [(code, name), ...]。"""
    import pandas as pd

    frames = []
    for mkt in (0, 1):
        df = client.stocks(market=mkt)
        if df is not None and not df.empty and "code" in df.columns:
            frames.append(df[["code", "name"]])
    if not frames:
        return []
    allc = pd.concat(frames, ignore_index=True)
    allc["code"] = allc["code"].astype(str)
    mask = allc["code"].str.startswith(A_SHARE_PREFIXES)
    uni = allc[mask].drop_duplicates("code")
    return [(str(c), clean_name(n)) for c, n in zip(uni["code"], uni["name"])]


def _num_or_none(values, i):
    if i >= len(values):
        return None
    v = values[i]
    if v is None or _isnan(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _build_rows(df, code: str, name: str, start_date: str, now: datetime,
                source: str, end_date: str | None = None) -> list[tuple]:
    """把 mootdx 日线 df 转成 fact_stock_daily 行 (只保留 start_date <= d <= end_date)。"""
    # mootdx 裸价模式下 datetime 同时是索引和列, 先 drop 索引消除歧义
    df = df.reset_index(drop=True)
    if "datetime" not in df.columns or "close" not in df.columns:
        return []
    df = df.sort_values("datetime")
    closes = df["close"].tolist()
    n = len(closes)
    amounts = df["amount"].tolist() if "amount" in df.columns else [None] * n
    opens = df["open"].tolist() if "open" in df.columns else [None] * n
    highs = df["high"].tolist() if "high" in df.columns else [None] * n
    lows = df["low"].tolist() if "low" in df.columns else [None] * n
    vols = df["vol"].tolist() if "vol" in df.columns else (df["volume"].tolist() if "volume" in df.columns else [None] * n)
    dts = df["datetime"].tolist()
    ts = _ts_code(code)
    name = clean_name(name)
    rows = []
    prev_close = None
    for i in range(n):
        d = str(dts[i])[:10]
        if not _DATE_RE.match(d):  # 跳过 nan / 停牌占位行
            continue
        close = _num_or_none(closes, i)
        if close is None:
            continue
        pre_close = prev_close
        pct = ((close / pre_close - 1) * 100) if (close and pre_close) else None
        amt = _num_or_none(amounts, i)
        amt_yi = amt / 1e8 if amt is not None else None
        if d >= start_date and (end_date is None or d <= end_date):
            rows.append((
                d, ts, name, close,
                round(pre_close, 3) if pre_close is not None else None,
                round(pct, 2) if pct is not None else None,
                round(amt_yi, 4) if amt_yi is not None else None,
                None, source, now,
                _num_or_none(opens, i), _num_or_none(highs, i), _num_or_none(lows, i), _num_or_none(vols, i),
            ))
        prev_close = close
    return rows


def sync_fact_stock_daily(start_date: str | None = None, offset: int = 180,
                          limit: int | None = None, only_missing: bool = True,
                          sleep: float = 0.0, qfq: bool = False,
                          timeout: int = 0, progress_every: int = 200,
                          end_date: str | None = None, ohlc_only: bool = False,
                          skip: int = 0) -> dict:
    """回补全A股日线到 fact_stock_daily。

    start_date: 起始交易日 (YYYY-MM-DD), 默认对齐 fact_market_daily 最早日。
    end_date: 截止交易日 (含), 默认不限; 与 start_date 相同即只重写单日 (如东财快照写坏的那天)。
    offset: 每只股票拉取的日线根数 (>= 区间交易日数, 默认180 ≈ 8个月; 3 年用 800)。
    limit: 本次最多抓多少只 (续跑用)。
    only_missing: True 时跳过区间内已抓的股票 (可续跑); ohlc_only 模式下「已抓」= 区间内已有 high。
    qfq: True 用前复权(慢, mootdx 除权重算很吃CPU); 默认 False 用裸收盘价(快)。
         短区间加权涨幅 裸价≈前复权, 个别除权股误差微小。
    timeout: 单只 bars 请求超时秒数 (>0 启用 SIGALRM 兜底); 超时记 failure 跳过, 不卡死整批。
    progress_every: 每处理多少只打一行心跳进度 (0 关闭); 避免长时间无输出被误判卡死。
    ohlc_only: 只写 open/high/low/volume; 已有行的其余字段不动 (给东财日线补 OHLC / 拉长历史)。
    skip: 跳过宇宙前 N 只 (与 --refresh + --limit 配合做确定性分页: 第 i 批 skip=i*limit)。
          ohlc_only 的 only_missing 启发式 (区间内已有 high) 在「先补过单日」的库上会把所有股票都当已抓,
          2026-09-07 3 年回拉就是这样一行没拉; 分页模式不依赖它。
    """
    from mootdx.quotes import Quotes

    source = "mootdx:qfq" if qfq else "mootdx"
    upsert_sql = BULK_UPSERT_OHLC_ONLY_SQL if ohlc_only else BULK_UPSERT_SQL
    init_db()
    con = connect()
    try:
        ensure_stock_daily_columns(con)
        if start_date is None:
            row = con.execute("SELECT MIN(trade_date) FROM fact_market_daily").fetchone()
            start_date = str(row[0]) if row and row[0] else "2025-10-09"

        done = set()
        if only_missing:
            done_sql = (
                "SELECT DISTINCT stock_ts_code FROM fact_stock_daily WHERE trade_date >= ?"
                + (" AND high IS NOT NULL" if ohlc_only else "")
                + (" AND trade_date <= ?" if end_date else "")
            )
            params = [start_date] + ([end_date] if end_date else [])
            done = {r[0] for r in con.execute(done_sql, params).fetchall()}

        client = Quotes.factory(market="std")
        universe = get_universe(client)
        universe_n = len(universe)
        pending = [(c, n) for c, n in universe if _ts_code(c) not in done]
        if skip:
            pending = pending[skip:]
        if limit:
            pending = pending[:limit]

        now = datetime.now()
        processed = 0
        rows_written = 0
        failures: list[tuple[str, str]] = []
        buf: list[tuple] = []

        def flush():
            nonlocal rows_written
            if not buf:
                return
            import pandas as pd
            _buf_df = pd.DataFrame(buf, columns=COLS)  # noqa: F841 (DuckDB 替换扫描引用)
            con.register("_buf_df", _buf_df)
            try:
                con.execute(upsert_sql)
            finally:
                con.unregister("_buf_df")
            rows_written += len(buf)
            buf.clear()

        pending_n = len(pending)
        for seen, (code, name) in enumerate(pending, start=1):
            try:
                df = _fetch_bars(client, code, offset, qfq, timeout)
            except _BarsTimeout:
                failures.append((code, f"timeout:{timeout}s"))
                continue
            except Exception as e:  # noqa: BLE001
                failures.append((code, f"bars:{type(e).__name__}"))
                continue
            if df is None or len(df) == 0:
                failures.append((code, "empty"))
                continue
            recs = _build_rows(df, code, name, start_date, now, source, end_date=end_date)
            buf.extend(recs)
            processed += 1
            if processed % FLUSH_EVERY == 0:
                flush()
            if progress_every and seen % progress_every == 0:
                print(f"[stock-daily] {seen}/{pending_n} 已处理 写入{rows_written}行 失败{len(failures)} 最近{code}",
                      file=sys.stderr, flush=True)
            if sleep:
                time.sleep(sleep)
        flush()

        total = con.execute("SELECT COUNT(*) FROM fact_stock_daily").fetchone()[0]
        agg = con.execute(
            "SELECT COUNT(DISTINCT stock_ts_code), COUNT(DISTINCT trade_date),"
            " MIN(trade_date), MAX(trade_date) FROM fact_stock_daily"
        ).fetchone()
        done_after = con.execute(
            "SELECT COUNT(DISTINCT stock_ts_code) FROM fact_stock_daily WHERE trade_date >= ?",
            [start_date],
        ).fetchone()[0]
    finally:
        con.close()

    return {
        "start_date": start_date,
        "universe": universe_n,
        "processed": processed,
        "rows_written": rows_written,
        "stocks_done": done_after,
        "stocks_remaining": max(0, universe_n - done_after),
        "table_total": total,
        "distinct_stocks": agg[0],
        "distinct_dates": agg[1],
        "date_min": str(agg[2]) if agg[2] else None,
        "date_max": str(agg[3]) if agg[3] else None,
        "failures": failures,
    }
