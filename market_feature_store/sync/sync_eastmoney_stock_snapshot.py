"""东财(EastMoney)全市场快照 -> fact_stock_daily (单日盘后增量快路径)。

数据源: 东财 push2 clist 接口 (https://push2.eastmoney.com/api/qt/clist/get)。
一次/少数几次 HTTP 请求即可拿到全 A 当日 收盘/涨跌幅/昨收/成交额, 适合「单日盘后增量」,
把 daily-full 的全A日线一步从十几分钟 (mootdx 逐只 TCP) 压到数十秒。
历史多日回填仍走 mootdx (见 sync_mootdx_stock_daily / duckdb-backfill skill)。

与 mootdx 路径同 schema/口径:
- amount 统一存「亿」(东财 f6 单位为元, /1e8)
- close 为当日收盘 (不复权, 与 mootdx qfq=False 一致)
- pre_close=东财 f18, pct_chg=东财 f3 (百分数)
- turnover=东财 f8 (换手率%)。**mootdx 那条路径给不出换手率, 所以那批行仍是 NULL**——
  这是来源差异, 不是缺陷; 消费方按 NULL 处理即可, 不要拿 0 顶替。
- source 标 'eastmoney:snapshot'

注意: 快照取的是「最近一个交易日/最新」行情, 必须在交易日盘后调用并显式传入 trade_date。
盘中调用 close 会是实时价; 非交易日调用会把上一交易日的数据写到所传 trade_date 上。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import date, datetime

from ..db import connect, init_db
from .sync_mootdx_stock_daily import (
    A_SHARE_PREFIXES,
    BULK_UPSERT_SQL,
    COLS,
    _isnan,
    _ts_code,
)

# 复盘为盘后运行: 默认用延时行情 host (push2delay), 收盘后其值 == 实时收盘值;
# 且 push2 (实时) 在部分 IP 会 SSL 握手超时/被限流。失败时自动回退到 push2。
EM_URL = "https://push2delay.eastmoney.com/api/qt/clist/get"
EM_URL_FALLBACK = "https://push2.eastmoney.com/api/qt/clist/get"
# 东财 clist 单页硬上限: 请求更大 pz 也只回 100 条, 且 pn 偏移按所传 pz 计算,
# 所以请求 pz 必须 <=100, 否则翻页会跳过中间股票 (实测 2026-06)。
EM_PAGE_MAX = 100
# 沪深京 A 股 (与 akshare stock_zh_a_spot_em 同口径), fs 内 '+' 为东财字段分隔符须保留字面量
EM_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
# f12=代码 f14=名称 f2=最新价(收盘) f3=涨跌幅% f18=昨收 f6=成交额(元) f8=换手率%
#
# **请求了就必须接住**，由 tests/test_eastmoney_snapshot_fields.py 钉住。
# 曾经请求了 f13(市场) 却从不读它: 交易所后缀由 `_ts_code` 按代码前缀派生, 而且
# **必须与 mootdx 用同一套派生**——改用 f13 会让同一只股票在两个来源下拿到不同的
# stock_ts_code, 在同一张表里裂成两个实体。所以正解是不请求它, 不是改派生。
EM_FIELDS = "f12,f14,f2,f3,f18,f6,f8"
EM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}


def _num(x):
    """东财字段转 float; '-'/''/None/NaN 一律视为缺失返回 None。"""
    if x is None:
        return None
    if isinstance(x, str):
        x = x.strip()
        if x in ("", "-"):
            return None
        try:
            return float(x)
        except ValueError:
            return None
    if _isnan(x):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _get_json(url: str, timeout: float, retries: int = 6, backoff: float = 1.2) -> dict:
    """GET + json 解析, 对 502/超时等瞬时错误退避重试 (翻页几十次难免偶发 502)。

    默认打 push2delay; 若重试耗尽 (如该 host 偶发不可达), 自动把 host 换成 push2
    再试一轮, 双 host 兜底。"""
    targets = [url]
    if EM_URL in url:
        targets.append(url.replace(EM_URL, EM_URL_FALLBACK))
    last_err: Exception | None = None
    for target in targets:
        for attempt in range(retries):
            try:
                req = urllib.request.Request(target, headers=EM_HEADERS)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                last_err = exc
                time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"东财快照请求失败: {url}") from last_err


def fetch_snapshot(page_size: int = EM_PAGE_MAX, timeout: float = 20.0,
                   sleep: float = 0.1) -> list[dict]:
    """分页拉取东财全市场快照, 返回原始 diff 字典列表。fltt=2 保证字段为十进制实值。

    东财单页最多 100 条, 故实际 pz 取 min(page_size, 100); 翻页靠 pn 递增到 total。
    """
    pz = max(1, min(page_size, EM_PAGE_MAX))
    out: list[dict] = []
    pn = 1
    total: int | None = None
    while pn <= 1000:  # 安全上限 (~10万只), 防止接口异常时死循环
        url = (
            f"{EM_URL}?pn={pn}&pz={pz}&po=1&np=1&fltt=2&invt=2&fid=f3"
            f"&fs={EM_FS}&fields={EM_FIELDS}"
        )
        data = _get_json(url, timeout).get("data") or {}
        if total is None:
            total = int(data.get("total") or 0)
        diff = data.get("diff") or []
        if isinstance(diff, dict):  # 个别接口形态返回 {idx: row}
            diff = list(diff.values())
        if not diff:
            break
        out.extend(diff)
        if total and len(out) >= total:
            break
        pn += 1
        if sleep:
            time.sleep(sleep)
    return out


def sync_fact_stock_daily_snapshot(trade_date: str | None = None,
                                   page_size: int = EM_PAGE_MAX,
                                   timeout: float = 20.0,
                                   source: str = "eastmoney:snapshot") -> dict:
    """东财全市场快照写入 fact_stock_daily 的单个交易日 (盘后增量快路径)。

    trade_date: 目标交易日 YYYY-MM-DD, 留空取当天。
    page_size: 分页大小, 东财单页上限100, 超过按100处理 (全A约6千只, ~60页)。
    """
    if trade_date is None:
        trade_date = date.today().isoformat()

    init_db()
    con = connect()
    try:
        diff = fetch_snapshot(page_size=page_size, timeout=timeout)
        now = datetime.now()
        buf: list[tuple] = []
        skipped = 0
        for it in diff:
            code = str(it.get("f12") or "").strip()
            if not code or not code.startswith(A_SHARE_PREFIXES):
                skipped += 1
                continue
            close = _num(it.get("f2"))
            if close is None:  # 停牌 / 无成交 / 无效行
                skipped += 1
                continue
            name = str(it.get("f14") or "").strip()
            pre_close = _num(it.get("f18"))
            pct = _num(it.get("f3"))
            amt = _num(it.get("f6"))
            amt_yi = round(amt / 1e8, 4) if amt is not None else None
            # f8 一直在 EM_FIELDS 里被请求、数据也一直回来, 但这里曾经硬绑 None,
            # 理由是「与 mootdx 行口径一致」——代价是**能采到的那 23.7 万行也一起丢了**,
            # 且丢得没有痕迹: 只有把请求字段表和解析代码对着看才发现得了
            # (审计侧看到的是「turnover 全库非空 0 行」, 像极了「上游采不到」)。
            # 口径一致不该靠丢数据实现: 来源给不出就是 NULL, 给得出就存下来。
            turnover = _num(it.get("f8"))
            buf.append((
                trade_date,
                _ts_code(code),
                name,
                close,
                round(pre_close, 3) if pre_close is not None else None,
                round(pct, 2) if pct is not None else None,
                amt_yi,
                round(turnover, 4) if turnover is not None else None,
                source,
                now,
            ))

        rows_written = 0
        if buf:
            import pandas as pd
            _buf_df = pd.DataFrame(buf, columns=COLS)  # noqa: F841 (DuckDB 替换扫描引用)
            con.register("_buf_df", _buf_df)
            try:
                con.execute(BULK_UPSERT_SQL)
            finally:
                con.unregister("_buf_df")
            rows_written = len(buf)

        table_total = con.execute("SELECT COUNT(*) FROM fact_stock_daily").fetchone()[0]
        day_rows = con.execute(
            "SELECT COUNT(*) FROM fact_stock_daily WHERE trade_date = ?",
            [trade_date],
        ).fetchone()[0]
        agg = con.execute(
            "SELECT COUNT(DISTINCT stock_ts_code), COUNT(DISTINCT trade_date),"
            " MIN(trade_date), MAX(trade_date) FROM fact_stock_daily"
        ).fetchone()
    finally:
        con.close()

    return {
        "trade_date": trade_date,
        "source": source,
        "fetched": len(diff),
        "rows_written": rows_written,
        "skipped": skipped,
        "day_rows": day_rows,
        "table_total": table_total,
        "distinct_stocks": agg[0],
        "distinct_dates": agg[1],
        "date_min": str(agg[2]) if agg[2] else None,
        "date_max": str(agg[3]) if agg[3] else None,
    }
