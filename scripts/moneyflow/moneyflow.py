#!/usr/bin/env python3
"""大单资金流分析图

基于逐笔成交数据（深圳 share.trans / 上海 share.ngts_tick），
只统计单笔成交额 >= 阈值（默认50万）的大单：

- 红色线：主动买入净额 = 累计(主动买入金额 - 主动卖出金额)
- 紫色线：总买入净额 = 主动净额 + 被动净额
- 散点：大单买单（红）/ 卖单（绿），按时间和单笔金额绘制

主动方向判断：委托编号大的一方为主动方（后下单先成交）。
BuyNo > SellNo => 主动买入；SellNo > BuyNo => 主动卖出。

用法:
    python3 moneyflow.py <股票代码> <日期> [阈值万元]
    python3 moneyflow.py 300775 2026-07-03 50
"""
import ipaddress
import json
import os
import random
import socket
import subprocess
import sys
import time
import urllib.request

from config import HOST, PORT, USER, PASSWORD, out_path  # noqa: E402


def current_git_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _setup_matplotlib():
    """绘图依赖惰性加载，便于 preflight/单测在无 matplotlib 环境下 import。"""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt, mdates


def _ch_client_cls():
    from clickhouse_driver import Client

    return Client

# Shadowrocket / Clash Fake-IP 等常用网段；命中则判定 DNS 被代理劫持
_FAKE_IP_NETWORKS = (
    ipaddress.ip_network("198.18.0.0/15"),
)
_PUBLIC_DNS = tuple(
    s.strip()
    for s in os.environ.get("CH_PUBLIC_DNS", "223.5.5.5,8.8.8.8,1.1.1.1").split(",")
    if s.strip()
)


def _is_fake_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in _FAKE_IP_NETWORKS)


def _system_resolve(host: str) -> list[str]:
    ips: list[str] = []
    try:
        for family, _t, _p, _c, sockaddr in socket.getaddrinfo(
            host, None, type=socket.SOCK_STREAM
        ):
            if family == socket.AF_INET:
                ip = sockaddr[0]
                if ip not in ips:
                    ips.append(ip)
    except socket.gaierror:
        pass
    return ips


def _dig_resolve(host: str, dns: str) -> list[str]:
    """用 dig @public-dns 绕过本机 Fake-IP 解析。"""
    try:
        out = subprocess.run(
            ["dig", f"@{dns}", "+short", "+time=2", "+tries=1", host, "A"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []
    ips = []
    for line in (out.stdout or "").splitlines():
        line = line.strip()
        if not line or line.endswith("."):
            continue
        try:
            ipaddress.ip_address(line)
        except ValueError:
            continue
        if line not in ips:
            ips.append(line)
    return ips


# 进程内缓存已连通的真实 IP，避免批次重建连接时 dig 瞬时失败拖死整轮
_WORKING_CH_HOSTS: list[str] = []


def _remember_working_host(host: str) -> None:
    if host and host not in _WORKING_CH_HOSTS and not _is_fake_ip(host):
        _WORKING_CH_HOSTS.insert(0, host)


def resolve_clickhouse_host(host: str | None = None) -> tuple[str, str, list[str]]:
    """解析 ClickHouse 可达 endpoint。

    返回 (connect_host, note, all_candidates)。
    - 若系统解析落在 Fake-IP 段，自动用公共 DNS 回退；
    - 可用 CH_HOST_FALLBACK 强制指定 IP（逗号分隔）。
    - 优先复用本进程已连通成功的 IP（防 dig 间歇失败）。
    """
    host = host or HOST
    # 已是字面 IP
    try:
        ipaddress.ip_address(host)
        if _is_fake_ip(host):
            raise RuntimeError(
                f"CH_HOST={host} 落在 Fake-IP 段（198.18.0.0/15）。"
                "请关闭代理对该库的劫持，或设置真实 IP 到 CH_HOST / CH_HOST_FALLBACK。"
            )
        return host, "literal-ip", [host]
    except ValueError:
        pass

    candidates: list[str] = []
    note_parts: list[str] = []

    # 优先已验证可达的 IP
    for ip in list(_WORKING_CH_HOSTS):
        if ip not in candidates:
            candidates.append(ip)
    if _WORKING_CH_HOSTS:
        note_parts.append(f"cached={','.join(_WORKING_CH_HOSTS)}")

    sys_ips = _system_resolve(host)
    if sys_ips:
        note_parts.append(f"system={','.join(sys_ips)}")
        for ip in sys_ips:
            if not _is_fake_ip(ip) and ip not in candidates:
                candidates.append(ip)

    fake_only = bool(sys_ips) and all(_is_fake_ip(ip) for ip in sys_ips)
    if fake_only or not candidates:
        if fake_only:
            print(
                f"WARN CH_HOST={host} 系统解析为 Fake-IP {sys_ips} "
                f"（常见于 Shadowrocket），改用公共 DNS 回退",
                flush=True,
            )
        for dns in _PUBLIC_DNS:
            dig_ips = _dig_resolve(host, dns)
            if dig_ips:
                note_parts.append(f"dig@{dns}={','.join(dig_ips)}")
                for ip in dig_ips:
                    if not _is_fake_ip(ip) and ip not in candidates:
                        candidates.append(ip)
                if candidates:
                    break

    fallback = os.environ.get("CH_HOST_FALLBACK", "").strip()
    if fallback:
        for ip in fallback.split(","):
            ip = ip.strip()
            if not ip:
                continue
            try:
                ipaddress.ip_address(ip)
            except ValueError:
                continue
            if _is_fake_ip(ip):
                continue
            if ip not in candidates:
                candidates.append(ip)
        note_parts.append(f"fallback={fallback}")

    if not candidates:
        raise RuntimeError(
            f"无法解析可用的 ClickHouse 地址 host={host} "
            f"({'；'.join(note_parts) or '无解析结果'})。"
            "请将 base32.cn 设为代理 DIRECT / 绕过 Fake-IP，"
            "或设置 CH_HOST_FALLBACK=真实IP。"
        )

    connect_host = candidates[0]
    note = "; ".join(note_parts) or "ok"
    return connect_host, note, candidates


def preflight_clickhouse(probe_code: str = "300308") -> dict:
    """开跑前自检：解析、连库、抽 1 只样例 count。失败抛 RuntimeError。"""
    connect_host, note, candidates = resolve_clickhouse_host(HOST)
    last_err: Exception | None = None
    Client = _ch_client_cls()
    for host in candidates:
        try:
            client = Client(
                host=host,
                port=PORT,
                user=USER,
                password=PASSWORD,
                connect_timeout=15,
                send_receive_timeout=60,
                settings={"max_execution_time": 30},
            )
            client.execute("SELECT 1")
            # 轻量探测：不取全表，只 count 一只活跃股近 3 日是否有数据
            n = client.execute(
                """
                SELECT count() FROM share.trans
                WHERE SecurityID = %(c)s
                  AND TradeDate >= addDays(today(), -5)
                """,
                {"c": probe_code},
            )[0][0]
            info = {
                "host": host,
                "configured": HOST,
                "note": note,
                "probe_code": probe_code,
                "probe_rows_5d": int(n),
            }
            print(
                f"CH preflight OK host={host} (configured={HOST}) "
                f"probe {probe_code} 5d_rows={n} [{note}]",
                flush=True,
            )
            _remember_working_host(host)
            try:
                client.disconnect()
            except Exception:
                pass
            return info
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"WARN CH preflight 失败 host={host}: {e}", flush=True)
            continue
    raise RuntimeError(
        f"ClickHouse preflight 全部候选失败 configured={HOST} "
        f"candidates={candidates} last_error={last_err}"
    )


_MAKE_CLIENT_PROBED = False


def make_client(*, skip_probe: bool = False):
    """创建 ClickHouse 客户端：自动绕过 Fake-IP，连上后 SELECT 1 校验。

    进程内首次连接会额外 probe 样例表（可用 CH_SKIP_PREFLIGHT=1 关闭）。
    """
    global _MAKE_CLIENT_PROBED
    connect_host, note, candidates = resolve_clickhouse_host(HOST)
    last_err: Exception | None = None
    do_probe = (
        not skip_probe
        and not _MAKE_CLIENT_PROBED
        and os.environ.get("CH_SKIP_PREFLIGHT", "").strip() not in {"1", "true", "yes"}
    )
    Client = _ch_client_cls()
    for host in candidates:
        try:
            client = Client(
                host=host,
                port=PORT,
                user=USER,
                password=PASSWORD,
                connect_timeout=20,
                send_receive_timeout=300,
                settings={"max_execution_time": 120},
            )
            client.execute("SELECT 1")
            _remember_working_host(host)
            if do_probe:
                n = client.execute(
                    """
                    SELECT count() FROM share.trans
                    WHERE SecurityID = '300308'
                      AND TradeDate >= addDays(today(), -5)
                    """
                )[0][0]
                print(
                    f"CH preflight OK host={host} (configured={HOST}) "
                    f"probe 300308 5d_rows={n} [{note}]",
                    flush=True,
                )
                _MAKE_CLIENT_PROBED = True
            elif host != HOST:
                print(
                    f"CH connect via {host} (configured={HOST}) [{note}]",
                    flush=True,
                )
            return client
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"WARN CH connect 失败 host={host}: {e}", flush=True)
            continue
    raise RuntimeError(
        f"ClickHouse 连接失败 configured={HOST} candidates={candidates} "
        f"last_error={last_err}"
    )


def duck_limitup_codes(prev_date):
    """从本地 DuckDB 取 prev_date 收盘涨停名单（免打 ClickHouse 重聚合）。
    涨停比例：创业/科创 20%，ST 主板 5%，其余主板 10%。"""
    import duckdb
    from config import DUCKDB_PATH
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        rows = con.execute(
            "SELECT stock_ts_code, stock_name, close, pre_close "
            "FROM fact_stock_daily WHERE trade_date = ? AND pre_close > 0",
            [prev_date]).fetchall()
    finally:
        con.close()
    codes = []
    for ts, name, close, pre in rows:
        code = ts.split(".")[0]
        if code[:2] not in ("00", "30", "60", "68"):
            continue
        if code[:2] in ("30", "68"):
            ratio = 1.2
        elif "ST" in (name or ""):
            ratio = 1.05
        else:
            ratio = 1.1
        if abs(close - round(pre * ratio, 2)) < 0.005:
            codes.append(code)
    return sorted(codes)


def duck_top_turnover_codes(date, n=50):
    """从本地 DuckDB 取当日成交额前 n 名单（免打 ClickHouse 重聚合）。"""
    import duckdb
    from config import DUCKDB_PATH
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        rows = con.execute(
            "SELECT stock_ts_code FROM fact_stock_daily "
            "WHERE trade_date = ? AND substr(stock_ts_code, 1, 2) IN ('00','30','60','68') "
            "AND amount IS NOT NULL ORDER BY amount DESC LIMIT ?",
            [date, n]).fetchall()
    finally:
        con.close()
    return [r[0].split(".")[0] for r in rows]


def fetch_trades_retry(client, code, date, retries=3):
    """带重连重试的 fetch_trades，返回 (client, df)。
    退避时长指数增长并加随机抖动，避免限流后同步重试再次撞限。"""
    for k in range(retries):
        try:
            return client, fetch_trades(client, code, date)
        except Exception:
            if k == retries - 1:
                raise
            time.sleep(min(60.0, 5.0 * (2 ** k)) + random.uniform(0, 3))
            try:
                client.disconnect()
            except Exception:
                pass
            client = make_client()


class AdaptiveThrottle:
    """自适应限速：报错/限流时指数加大逐股间隔，连续成功后逐步回落到基准。"""

    def __init__(self, base=0.3, max_sleep=30.0):
        self.base, self.max, self.cur = base, max_sleep, base

    def wait(self):
        time.sleep(self.cur + random.uniform(0, self.cur * 0.3))

    def ok(self):
        self.cur = max(self.base, self.cur * 0.8)

    def fail(self):
        self.cur = min(self.max, max(self.cur * 2.0, 2.0))


def run_scan(client, codes, date, tag, compute, passes=3, batch_size=20, batch_rest=15.0):
    """逐股扫描骨架：自适应限速 + 小批量冷却 + 断点缓存 + 失败股票多轮兜底重试。

    每处理 batch_size 只后落盘缓存、休息 batch_rest 秒（带抖动）并重建连接，
    避免长连接一次性扫描过多触发限流。

    compute(client, code) -> (client, row|None)；row 为 None 表示该股无结果。
    已完成结果缓存到 outputs/scan_cache_<tag>_<date>.json，中断重跑不重复打库。
    **null 结果不视为已完成**（避免 VPN/空响应写出的全 None 缓存卡死重跑）。
    返回 (client, rows, stats)；stats 含 input_count/processed_count/failed_count，
    供写库时落入 ops_pipeline_run_daily 审计。"""
    codes = list(codes)
    code_set = set(codes)
    cache_file = out_path(f"scan_cache_{tag}_{date}.json")
    done = {}
    if os.environ.get("L2_FORCE_RESCAN", "").strip() in {"1", "true", "yes"}:
        print(f"L2_FORCE_RESCAN=1，忽略断点缓存 {cache_file}", flush=True)
    elif os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                raw = json.load(f)
            # 只保留有效结果；null/过期条目下次重扫
            done = {k: v for k, v in (raw or {}).items() if v and k in code_set}
            skipped = len(raw or {}) - len(done)
            print(
                f"断点缓存 {cache_file}: 有效 {len(done)} 只"
                + (f"（忽略 null/过期 {skipped}）" if skipped else ""),
                flush=True,
            )
        except Exception:
            done = {}

    def save():
        temporary = f"{cache_file}.tmp"
        with open(temporary, "w") as f:
            json.dump(done, f, ensure_ascii=False)
        os.replace(temporary, cache_file)

    throttle = AdaptiveThrottle()
    pending = [c for c in codes if c not in done]
    scan_cache_hits = len(done)
    # 成功拉到数据但无大单的代码（本轮）；最终计入 processed，但不落 cache
    empty_ok: set[str] = set()
    print(
        f"扫描 {tag} {date}: input={len(codes)} cache_hits={len(done)} pending={len(pending)}",
        flush=True,
    )
    for rnd in range(1, passes + 1):
        if not pending:
            break
        if rnd > 1:
            print(f"== 第{rnd}轮兜底重试: {len(pending)} 只 ==")
            time.sleep(min(120.0, 20.0 * rnd))
        failed = []
        for i, code in enumerate(pending, 1):
            try:
                client, row = compute(client, code)
                if row:
                    done[code] = row
                    empty_ok.discard(code)
                else:
                    # 空结果视为“已处理无命中”，不重扫（量化榜大量空是正常的；
                    # 真连接故障会走 except → failed 多轮兜底）
                    empty_ok.add(code)
                throttle.ok()
            except Exception as e:
                print(f"[{i}/{len(pending)}] {code} 失败: {e}")
                failed.append(code)
                throttle.fail()
            # 更勤落盘，避免长任务中途 SIGTERM 丢有效进度
            if i % 5 == 0 or i == len(pending):
                save()
            throttle.wait()
            if batch_size and i % batch_size == 0 and i < len(pending):
                save()
                print(f"-- 批次冷却: 已处理 {i}/{len(pending)}，休息 {batch_rest:.0f}s 并重建连接 --")
                time.sleep(batch_rest + random.uniform(0, batch_rest * 0.3))
                try:
                    client.disconnect()
                except Exception:
                    pass
                client = make_client()
        save()
        pending = failed  # 仅异常失败进入下一轮
    if pending:
        print(f"!! 兜底后仍失败 {len(pending)} 只: {','.join(pending[:20])}")
    nonempty = sum(1 for v in done.values() if v)
    processed = sum(1 for c in codes if c in done or c in empty_ok)
    stats = {
        "input_count": len(codes),
        "processed_count": processed,
        "failed_count": len(pending),
        "nonempty_count": nonempty,
        "empty_count": len(empty_ok),
        "scan_cache_hits": scan_cache_hits,
    }
    print(f"扫描统计 {tag} {date}: {stats}", flush=True)
    # 大批量名单却几乎全空：高概率是链路/数据源异常，而非真的无大单
    if (
        len(codes) >= 20
        and not pending
        and nonempty == 0
        and os.environ.get("L2_ALLOW_ALL_EMPTY", "").strip() not in {"1", "true", "yes"}
    ):
        raise RuntimeError(
            f"scan {tag} {date}: 处理 {len(codes)} 只全部空结果"
            f"（empty={len(empty_ok)}）。"
            "疑似 ClickHouse 空响应 / VPN 劫持 / 数据未到。"
            "修复网络后重跑；若确认当日确无数据可设 L2_ALLOW_ALL_EMPTY=1。"
        )
    return client, [r for c, r in done.items() if r], stats


def fetch_trades(client, code, date):
    """拉取单只股票单日逐笔成交。返回 DataFrame[time, price, volume, buy_no, sell_no]"""
    import pandas as pd

    if code.startswith("6"):  # 上海
        sql = """
        SELECT TickTime AS t, toFloat64(Price) AS price, Volume AS volume,
               BuyNo AS buy_no, SellNo AS sell_no
        FROM share.ngts_tick
        WHERE SecurityID = %(code)s AND TradeDate = %(date)s AND TickType = 'T'
        ORDER BY t
        """
    else:  # 深圳
        sql = """
        SELECT TradeTime AS t, toFloat64(TradePrice) AS price, TradeVolume AS volume,
               BuyNo AS buy_no, SellNo AS sell_no
        FROM share.trans
        WHERE SecurityID = %(code)s AND TradeDate = %(date)s AND ExecType = '1'
        ORDER BY t
        """
    rows = client.execute(sql, {"code": code, "date": date})
    df = pd.DataFrame(rows, columns=["t", "price", "volume", "buy_no", "sell_no"])
    if not df.empty:
        # CH 可能返回 datetime 或混有微秒/无微秒的 ISO 字符串
        t = pd.to_datetime(df["t"], format="ISO8601", utc=True)
        df["t"] = t.dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
    return df


def analyze(df, threshold_wan=50.0):
    df = df.copy()
    df["amount"] = df["price"] * df["volume"]
    df["active_buy"] = df["buy_no"] > df["sell_no"]

    # 大资金口径：同一委托单当日累计成交额 >= 阈值
    thr = threshold_wan * 1e4
    buy_order_amt = df.groupby("buy_no")["amount"].sum()
    sell_order_amt = df.groupby("sell_no")["amount"].sum()
    big_buy_orders = set(buy_order_amt[buy_order_amt >= thr].index)
    big_sell_orders = set(sell_order_amt[sell_order_amt >= thr].index)

    df["buyer_big"] = df["buy_no"].isin(big_buy_orders)
    df["seller_big"] = df["sell_no"].isin(big_sell_orders)
    big = df[df["buyer_big"] | df["seller_big"]].copy()

    # 主动买入净额 = cumsum(主动买入 - 主动卖出)，仅统计大资金一侧
    active_flow = (
        big["amount"] * (big["active_buy"] & big["buyer_big"])
        - big["amount"] * (~big["active_buy"] & big["seller_big"])
    )
    # 被动净额 = 被动买入 - 被动卖出（挂单被动成交的大资金）
    passive_flow = (
        big["amount"] * (~big["active_buy"] & big["buyer_big"])
        - big["amount"] * (big["active_buy"] & big["seller_big"])
    )
    big["active_net"] = active_flow.cumsum()
    big["total_net"] = (active_flow + passive_flow).cumsum()
    return big


def stock_info(codes):
    """通过腾讯行情接口批量获取股票名称与流通市值（亿元），
    返回 {code: {"name": str, "cap": float}}"""
    info = {}
    codes = list(codes)
    for i in range(0, len(codes), 50):
        batch = codes[i:i + 50]
        q = ",".join(("sh" if c.startswith("6") else "sz") + c for c in batch)
        try:
            raw = urllib.request.urlopen(
                f"http://qt.gtimg.cn/q={q}", timeout=10).read().decode("gbk")
            for line in raw.strip().split(";"):
                if "=" not in line:
                    continue
                _, val = line.split("=", 1)
                parts = val.strip('"').split("~")
                if len(parts) > 44:
                    cap = float(parts[44]) if parts[44] else 0.0
                    info[parts[2]] = {"name": parts[1], "cap": cap}
        except Exception as e:
            print(f"获取行情信息失败: {e}")
    return info


def stock_names(codes):
    return {c: v["name"] for c, v in stock_info(codes).items()}


def detect_quant_orders(buys, tol=0.01, min_count=10, min_amount=0.0, top_n=5):
    """规律量化单识别：金额高度相近、反复出现的大买单簇。

    按金额排序后扫描，整簇金额落在 [x, x*(1+tol)] 的窄带内且
    笔数 >= min_count 的认为是量化单。返回簇列表及命中的行。
    """
    if buys.empty:
        return [], buys.iloc[0:0]
    b = buys.sort_values("amount").reset_index(drop=True)
    clusters, start = [], 0
    for i in range(1, len(b) + 1):
        if i == len(b) or b["amount"][i] > b["amount"][start] * (1 + tol):
            if i - start >= min_count:
                clusters.append(b.iloc[start:i])
            start = i
    # 组合金额在阈值边缘的密集小单容易误判，只保留明显高于阈值的簇，
    # 并按总额取前 top_n
    clusters = [c for c in clusters if c["amount"].min() >= min_amount]
    clusters = sorted(clusters, key=lambda c: c["amount"].sum(), reverse=True)[:top_n]
    infos, hit_idx = [], []
    for c in clusters:
        infos.append({
            "lo": c["amount"].min() / 1e4, "hi": c["amount"].max() / 1e4,
            "count": len(c), "total": c["amount"].sum() / 1e4,
            "t0": c["t"].min(), "t1": c["t"].max(),
        })
        hit_idx += list(c.index)
    return infos, b.loc[hit_idx]


def plot(big, code, date, threshold_wan, out_path, name=""):
    plt, mdates = _setup_matplotlib()
    fig, (ax0, ax1) = plt.subplots(
        2, 1, figsize=(14, 9), sharex=True,
        gridspec_kw={"height_ratios": [1, 2.6]})
    # 上方分时价格线（用逐笔成交价，便于对比背离）
    ax0.plot(big["t"], big["price"], c="black", lw=0.8)
    ax0.set_ylabel("分时价格")
    ax0.grid(alpha=0.3)

    # 每个大资金委托单聚合为一个点：时间取最后成交时间，金额为累计成交额
    buys = (big[big["buyer_big"]].groupby("buy_no")
            .agg(t=("t", "last"), amount=("amount", "sum")).reset_index())
    sells = (big[big["seller_big"]].groupby("sell_no")
             .agg(t=("t", "last"), amount=("amount", "sum")).reset_index())
    ax1.scatter(buys["t"], buys["amount"] / 1e4, s=12, c="red", label="买单")
    ax1.scatter(sells["t"], sells["amount"] / 1e4, s=12, c="green", label="卖单")
    ax1.set_ylabel("单笔成交额（万元）")
    ax1.set_xlabel("时间")

    ax2 = ax1.twinx()
    ax2.plot(big["t"], big["active_net"] / 1e4, c="red", lw=1.2, label="主动买入净额")
    ax2.plot(big["t"], big["total_net"] / 1e4, c="purple", lw=1.2, label="总买入净额")
    ax2.axhline(0, c="orange", ls="--", lw=0.8)
    ax2.set_ylabel("累计净额（万元）")

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left")

    # 规律量化买单标注
    infos, hits = detect_quant_orders(buys, min_amount=threshold_wan * 1e4 * 1.5)
    if infos:
        ax1.scatter(hits["t"], hits["amount"] / 1e4, s=40,
                    facecolors="none", edgecolors="blue", lw=0.8)
        lines = [
            f"量化买单{i+1}: 金额({q['lo']:.0f}-{q['hi']:.0f}万) 笔数:{q['count']} "
            f"时间:{q['t0']:%H:%M:%S} -> {q['t1']:%H:%M:%S} 总额 {q['total']:.0f}万"
            for i, q in enumerate(infos)]
        fig.text(0.01, -0.005, "\n".join(lines), fontsize=9, va="top", c="blue")

    buy_amt = buys["amount"].sum() / 1e4
    sell_amt = sells["amount"].sum() / 1e4
    ax0.set_title(
        f"{code} {name} {date} 大单资金流（单笔≥{threshold_wan:.0f}万） "
        f"B:S={len(buys)}:{len(sells)} 主买净额:{big['active_net'].iloc[-1]/1e4:.0f}万 "
        f"总额:{buy_amt+sell_amt:.0f}万"
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    print(f"saved: {out_path}  大单数: {len(big)}")


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "300775"
    date = sys.argv[2] if len(sys.argv) > 2 else "2026-07-03"
    threshold = float(sys.argv[3]) if len(sys.argv) > 3 else 50.0
    client = make_client()
    df = fetch_trades(client, code, date)
    if df.empty:
        print("无数据，请检查代码/日期")
        return
    big = analyze(df, threshold)
    if big.empty:
        print("当日无满足阈值的大单")
        return
    out = out_path(f"moneyflow_{code}_{date}.png")
    name = stock_names([code]).get(code, "")
    plot(big, code, date, threshold, out, name)


if __name__ == "__main__":
    main()
