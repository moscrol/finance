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

**日期闸（2026-09-07 起，工单 #32）**：上面这句警告只写在文档里、代码不拦，结果 07-20 与 08-06 两次
「事后补历史日」把次日截面贴了历史日期，整天 5500 行逐股与次日相同，坏日阈值 10% 抓不到。现在每行
多请求 ``f297``（行情自身的交易日期 YYYYMMDD），全场占多数的那个日期 ≠ 所传 ``trade_date`` 就**拒写**；
回不了 ``f297`` 也拒写（认不出日期不给写）。历史日的源是 mootdx ``sync-stock-daily``，不是这里。
``allow_misdated=True`` 才放行，且 source 标 ``eastmoney:snapshot-misdated``，事后能从库里认出这批。
"""
from __future__ import annotations

import http.client
import json
import socket
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime

from ..db import connect, init_db
from .sync_mootdx_stock_daily import (
    A_SHARE_PREFIXES,
    BULK_UPSERT_SQL,
    COLS,
    _isnan,
    _ts_code,
    ensure_stock_daily_columns,
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
# f17=今开 f15=最高 f16=最低 f5=成交量(手) —— 2026-09-07 起落 open/high/low/volume,
# 新高等派生要日内最高价, 收盘价对不上 fupanhui 新高家数 (双轨对账差 ±20%)。
#
# **请求了就必须接住**，由 tests/test_eastmoney_snapshot_fields.py 钉住。
# 曾经请求了 f13(市场) 却从不读它: 交易所后缀由 `_ts_code` 按代码前缀派生, 而且
# **必须与 mootdx 用同一套派生**——改用 f13 会让同一只股票在两个来源下拿到不同的
# stock_ts_code, 在同一张表里裂成两个实体。所以正解是不请求它, 不是改派生。
#
# f297=该行行情的交易日期 (YYYYMMDD 整数)。只用来判「这份快照到底是哪天的」, 不落库——
# 落库日期是所传 trade_date, 两者不一致就是不该写 (见模块 docstring「日期闸」)。
EM_FIELDS = "f12,f14,f2,f3,f18,f6,f8,f17,f15,f16,f5,f297"
#: 日期闸的判定线: 全部行里, 最多的那个 f297 日期要**超过**这个比例才算「认出了快照日期」。
SNAPSHOT_DATE_QUORUM = 0.5


class SnapshotMisdated(RuntimeError):
    """快照数据日 ≠ 所传 trade_date (或认不出日期)。不是瞬时错误, 重试没用; 历史日请走 mootdx。"""


def snapshot_trade_date(diff: list[dict]) -> str | None:
    """从 f297 里读出这份快照实际是哪个交易日 (ISO)。

    占多数的日期不足 ``SNAPSHOT_DATE_QUORUM``、或压根没有 f297 → None (认不出)。
    个别行日期不同是正常的 (长期停牌股的 f297 停在最后成交日), 所以按多数判, 不要求全场一致。
    """
    counts: dict[str, int] = {}
    for it in diff:
        raw = it.get("f297")
        if raw is None or raw == "-" or raw == "":
            continue
        s = str(raw).strip()
        if not (len(s) == 8 and s.isdigit()):
            continue
        counts[s] = counts.get(s, 0) + 1
    if not counts or not diff:
        return None
    best, n = max(counts.items(), key=lambda kv: kv[1])
    if n <= SNAPSHOT_DATE_QUORUM * len(diff):  # 要「过半」, 恰好一半算认不出
        return None
    return f"{best[:4]}-{best[4:6]}-{best[6:]}"
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


# ── 传输层 ────────────────────────────────────────────────────────────
#
# 2026-09-22 夜跑事故（09-21 同形）: 一次取数失败拖垮整晚复盘, 主库停在 09-18。
# 两个独立缺陷与实测证据见 tests/test_eastmoney_transport.py 模块头。

#: 绕开本机代理 fake-IP 劫持用的公共 DNS
PUBLIC_DNS = ("223.5.5.5", "119.29.29.29", "8.8.8.8")
#: 代理 fake-IP 模式的伪地址段 (RFC 2544 基准测试段, 真实公网不会用)
PROXY_FAKE_IP_PREFIX = "198.18."
#: 这一发没打通 → 重试。URLError / TimeoutError 本身就是 OSError;
#: RemoteDisconnected 同时是 ConnectionResetError(OSError) 与 HTTPException——
#: 旧版只写 URLError **接不住它**, 因为 urllib 只把「发请求阶段」的 OSError 包成
#: URLError, 而连接是在 getresponse() 阶段断的, 异常原样穿透整个调用栈。
#: ValueError 收 JSON 解析失败 (上游偶尔回非 JSON 的挡板页)。
TRANSIENT_FETCH_ERRORS = (OSError, http.client.HTTPException, ValueError)
#: 「连上即空回应」的形状: TCP 连得上、TLS 握手成功、证书验证通过,
#: 对端接下连接却一个字节响应体都不给。2026-09-22 19:2x 东财对 `/api/qt/clist/get`
#: 拒绝服务时就是这个形状 (curl 侧为 `52 Empty reply from server`)。
#: 21:55 根因修正: 不是按出口 IP 封禁——同一主机、同一 IP 上 `/` 返 404、
#: `ulist.np/get` 返 200, 被针对的是端点; 且连发 clist 会把同主机其他端点一起
#: 拖成空回应 (冷却 45–75s 不恢复)。所以它与瞬时抖动的区别在于
#: **重试无用, 且每多打一发都在扩大伤害面**。
EMPTY_REPLY_ERRORS = (http.client.RemoteDisconnected,)
#: 同一 host 连续这么多发都是空回应 → 判定被拒, 立刻停手。
#: 取 3 = 容两次真抖动; 判据是「连续」不是「累计」, 成功一发即清零。
EMPTY_REPLY_STREAK_LIMIT = 3


class UpstreamRefusing(RuntimeError):
    """上游在应用层拒绝服务 (连上即空回应)——重试解决不了, 继续打只会扩大伤害面。

    继承 ``RuntimeError`` 是为了不破坏既有 ``except RuntimeError`` 的调用方;
    单独的类型是为了让调用方**能够**区分「上游不让我们取」与「重试耗尽」
    ——前者该停手换源/换时间窗口, 后者可以等一会儿再试。
    """


_ip_cache: dict[str, str | None] = {}
_ip_lock = threading.Lock()
#: 已知「系统解析这条路打不通」的 host。失败一次就记住——否则 60 页每页都白打一发。
_transport_cache: dict[str, str] = {}
#: host → 连续空回应次数 (成功即清零)
_empty_reply_streak: dict[str, int] = {}
#: 本进程内已判定「上游在拒」的 host。进程级而非持久化:
#: 夜跑每晚是新进程, 不会把一晚的封禁结论带到下一晚。
_refusing_hosts: set[str] = set()


def reset_transport_state() -> None:
    """清空进程级传输状态 (解析缓存 / 选路 / 熔断)。

    有了进程级可变状态就必须有重置入口, 否则两头出事:
    长驻进程换网络环境后无法自愈; 测试用例之间串味。
    本补丁开发时先踩了后者: 新增 ``_refusing_hosts`` 后, 既有 9 个用例
    单独跑绿、一起跑红——因为前面的用例把 host 标进了熔断集。
    """
    with _ip_lock:
        _ip_cache.clear()
    _transport_cache.clear()
    _empty_reply_streak.clear()
    _refusing_hosts.clear()


def _system_ip(host: str) -> str | None:
    """系统解析结果 (urllib 真正会用的那条路径); 解析不出来返回 None。"""
    try:
        return socket.gethostbyname(host)
    except OSError:
        return None


def _looks_hijacked(host: str) -> bool:
    """系统解析落进代理伪地址段 = 这条路一定不通, 别等它断连再学。"""
    ip = _system_ip(host)
    return bool(ip and ip.startswith(PROXY_FAKE_IP_PREFIX))


def _direct_ip(host: str) -> str | None:
    """用公共 DNS 取真实 IP (绕代理 fake-IP)。拿不到返回 None → 退回系统解析。"""
    with _ip_lock:
        if host in _ip_cache:
            return _ip_cache[host]
    ip = None
    for ns in PUBLIC_DNS:
        try:
            out = subprocess.run(
                ["dig", "+short", f"@{ns}", host, "A"],
                capture_output=True, text=True, timeout=8,
            ).stdout
            ip = next(
                (ln.strip() for ln in out.splitlines()
                 if ln.strip() and ln.strip()[0].isdigit()
                 and not ln.startswith(PROXY_FAKE_IP_PREFIX)),  # 首行常是 CNAME
                None,
            )
            if ip:
                break
        except Exception:  # noqa: BLE001 — dig 不存在/超时都退回系统解析
            continue
    # 只缓存成功结果。把 None 也写进去等于 negative caching without TTL:
    # 公共 DNS 首次全超时 → 本进程此后每一发都退回被劫持的系统解析,
    # 失败形态与修复前同形, 排查时极易误以为补丁没生效。
    if ip:
        with _ip_lock:
            _ip_cache[host] = ip
    return ip


def _tls_connection(ip: str, host: str, timeout: float) -> http.client.HTTPSConnection:
    """连真实 IP, 但 TLS SNI 与 Host 仍填域名 (等价 curl --resolve)。"""
    sock = socket.create_connection((ip, 443), timeout)
    try:
        ssock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
    except Exception:
        sock.close()
        raise
    conn = http.client.HTTPSConnection(host, timeout=timeout)
    conn.sock = ssock
    return conn


def _urllib_get_json(url: str, timeout: float) -> dict:
    req = urllib.request.Request(url, headers=EM_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _direct_get_json(host: str, path: str, timeout: float) -> dict:
    """直连真实 IP + SNI 保持域名; 没有真实 IP 时退回系统解析。"""
    ip = _direct_ip(host)
    if not ip:
        return _urllib_get_json(f"https://{host}{path}", timeout)
    conn = _tls_connection(ip, host, timeout)
    try:
        conn.request("GET", path, headers={**EM_HEADERS, "Host": host})
        return json.loads(conn.getresponse().read().decode("utf-8"))
    finally:
        conn.close()


def _get_json(url: str, timeout: float, retries: int = 6, backoff: float = 1.2) -> dict:
    """GET + json 解析, 对断连/超时/502 等瞬时错误退避重试 (翻页几十次难免偶发)。

    默认打 push2delay; 若重试耗尽 (如该 host 偶发不可达), 自动把 host 换成 push2
    再试一轮, 双 host 兜底。被本机代理 fake-IP 劫持的 host 直接走真实 IP 直连;
    系统解析看着正常、实际却打不通的, 失败一次后也降级到直连。
    """
    targets = [url]
    if EM_URL in url:
        targets.append(url.replace(EM_URL, EM_URL_FALLBACK))
    last_err: Exception | None = None
    hosts: list[str] = []
    for target in targets:
        parts = urllib.parse.urlsplit(target)
        host = parts.netloc
        hosts.append(host)
        path = parts.path + (f"?{parts.query}" if parts.query else "")
        if host in _refusing_hosts:
            # 已判定被拒: 一发都不再打。否则 60 页 × 每页重试 = 给封禁计时器不断续命。
            continue
        for attempt in range(retries):
            try:
                if _transport_cache.get(host) == "direct" or _looks_hijacked(host):
                    data = _direct_get_json(host, path, timeout)
                else:
                    data = _urllib_get_json(target, timeout)
            except EMPTY_REPLY_ERRORS as exc:
                # 连上即空回应。单发可能是抖动, 连续多发就是上游在拒。
                last_err = exc
                _empty_reply_streak[host] = _empty_reply_streak.get(host, 0) + 1
                if _empty_reply_streak[host] >= EMPTY_REPLY_STREAK_LIMIT:
                    _refusing_hosts.add(host)
                    break
                _transport_cache[host] = "direct"
                time.sleep(backoff * (attempt + 1))
            except ValueError as exc:
                # 内容层: 上游回了非 JSON 的挡板页。链路可能完全正常,
                # 所以既不改传输选路, 也不计入熔断——只走原有重试阶梯。
                last_err = exc
                time.sleep(backoff * (attempt + 1))
            except TRANSIENT_FETCH_ERRORS as exc:
                last_err = exc
                # 系统解析这条路这次没打通 → 下一发换直连, 不在同一条坏路上耗满重试。
                _transport_cache[host] = "direct"
                time.sleep(backoff * (attempt + 1))
            else:
                _empty_reply_streak[host] = 0
                return data
    if hosts and all(h in _refusing_hosts for h in hosts):
        raise UpstreamRefusing(
            f"东财在应用层拒绝服务 (连上即空回应, 已试 {', '.join(hosts)}): {url}\n"
            "重试不会解决, 只会把同主机其他端点一起拖垮。停本轮/等窗口过去/换数据源再来。"
        ) from last_err
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
                                   source: str = "eastmoney:snapshot",
                                   allow_misdated: bool = False) -> dict:
    """东财全市场快照写入 fact_stock_daily 的单个交易日 (盘后增量快路径)。

    trade_date: 目标交易日 YYYY-MM-DD, 留空取当天。
    page_size: 分页大小, 东财单页上限100, 超过按100处理 (全A约6千只, ~60页)。
    allow_misdated: 快照实际日期 ≠ trade_date (或认不出) 时仍然写, source 加 ``-misdated`` 后缀。
        默认 False → 抛 ``SnapshotMisdated``, 一行都不写。
    """
    if trade_date is None:
        trade_date = date.today().isoformat()

    init_db()
    con = connect()
    try:
        ensure_stock_daily_columns(con)
        diff = fetch_snapshot(page_size=page_size, timeout=timeout)
        # 日期闸: 先于一切写入。快照是「最新」语义, 这里是它与所传日期唯一一次对账的机会。
        actual = snapshot_trade_date(diff)
        if actual != trade_date:
            if not allow_misdated:
                raise SnapshotMisdated(
                    f"东财快照实际是 {actual or '认不出的日期 (无 f297)'} 的行情, 所传 trade_date={trade_date}, 拒写。"
                    f"快照只有「最新」语义; 补历史日用 mootdx: sync-stock-daily --start-date {trade_date} "
                    f"--end-date {trade_date} --refresh。确认要写请 allow_misdated (source 会标 -misdated)。"
                )
            source = source + "-misdated"
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
                _num(it.get("f17")),  # open
                _num(it.get("f15")),  # high
                _num(it.get("f16")),  # low
                _num(it.get("f5")),   # volume 手
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
        "snapshot_trade_date": actual,
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
