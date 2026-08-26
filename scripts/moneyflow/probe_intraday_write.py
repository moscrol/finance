#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盘中写入探针（P0，只读）。

设计：docs/superpowers/specs/2026-08-26-intraday-l2-sidecar-design.md §5.1
判别变量：交易日 10:00–14:30 盘中，深 share.trans / 沪 share.ngts_tick 的
max(成交时间) 相对墙钟的滞后。两表各出分表 verdict，收据落
~/.finance-runtime/intraday-l2-probe/YYYYMMDDTHHMMZ.json。

约束（照抄设计稿，不要放宽）：
- 复用 moneyflow.make_client()（Fake-IP 绕行 / 候选回退），不另写连法；
- 不写 DuckDB、不跑 scan_*、不动扫描阈值；
- 密码不出现在命令行/收据里（launchd 下自动 source ~/.secrets/clickhouse.env）；
- 盘后跑没有判别力 → 窗口外只写 invalid_window 收据并退出。

实现上比设计稿多做的三件事（都写进收据，可复核）：
1. 服务器时钟偏移：现役 fetch_trades 按 UTC 解析 CH 时间戳再转 +8，说明服务器
   时区未必是北京时间。先 SELECT now() 量出偏移再算滞后，否则会凭空多 8 小时。
2. 交易时段滞后 session_lag_seconds：午休 11:30–13:00 无成交，裸墙钟差会把
   live 误判成 stale；判读用交易时段秒数，裸差照样记录。
3. 双采样：间隔 90s 采两次。若交易时段内墙钟走了 ≥60s 而全市场 max_ts 纹丝
   不动，说明是刚落地的批量而不是流式写入 → suspect_batch。

用法：
  python3 probe_intraday_write.py                 # 盘中正式跑（写收据）
  python3 probe_intraday_write.py --check-only    # 连通性自检（不写收据，忽略窗口）
  python3 probe_intraday_write.py --force         # 忽略「今日已有结论收据」重跑

退出码：0=已有当日结论收据（live/batch_or_stale/suspect_batch）；
        2=connect_error；3=invalid_window；1=其它异常。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

CH_ENV_FILE = Path(
    os.environ.get("CH_ENV_FILE", "~/.secrets/clickhouse.env")
).expanduser()


def _load_ch_env() -> None:
    """launchd / 裸 shell 下自动加载凭证。

    config.py 在 import 时读环境变量，所以必须先于 import 执行；
    已有 CH_PASSWORD 时不覆盖（尊重调用方显式注入）。
    """
    if os.environ.get("CH_PASSWORD"):
        return
    if not CH_ENV_FILE.exists():
        return
    pat = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
    for line in CH_ENV_FILE.read_text().splitlines():
        m = pat.match(line.strip())
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        os.environ.setdefault(key, val)


_load_ch_env()
sys.path.insert(0, str(Path(__file__).resolve().parent))
from moneyflow import make_client, resolve_clickhouse_host  # noqa: E402
import config  # noqa: E402

CST = ZoneInfo("Asia/Shanghai")
RECEIPT_DIR = Path("~/.finance-runtime/intraday-l2-probe").expanduser()
WINDOW = (dtime(10, 0), dtime(14, 30))
MORNING = (dtime(9, 30), dtime(11, 30))
AFTERNOON = (dtime(13, 0), dtime(15, 0))
CONCLUSIVE = {"live", "batch_or_stale", "suspect_batch"}

TABLES = {
    "sz_share_trans": {
        "label": "深圳 share.trans",
        "sql": (
            "SELECT max(TradeTime) AS max_ts, count() AS n "
            "FROM share.trans WHERE TradeDate = today()"
        ),
        "sample_sql": (
            "SELECT max(TradeTime), count() FROM share.trans "
            "WHERE TradeDate = today() AND SecurityID = %(c)s"
        ),
    },
    "sh_share_ngts_tick": {
        "label": "上海 share.ngts_tick",
        "sql": (
            "SELECT max(TickTime) AS max_ts, count() AS n "
            "FROM share.ngts_tick "
            "WHERE TradeDate = today() AND TickType = 'T'"
        ),
        "sample_sql": (
            "SELECT max(TickTime), count() FROM share.ngts_tick "
            "WHERE TradeDate = today() AND TickType = 'T' AND SecurityID = %(c)s"
        ),
    },
}


def now_cst() -> datetime:
    return datetime.now(CST).replace(tzinfo=None)


def _sec(t: dtime) -> float:
    return t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1e6


def trade_seconds(dt: datetime) -> float:
    """时刻 → 当日已流逝的交易秒数（盘前=0，午休钳在 7200，收盘=14400）。"""
    s = _sec(dt.time())
    m0, m1 = _sec(MORNING[0]), _sec(MORNING[1])
    a0, a1 = _sec(AFTERNOON[0]), _sec(AFTERNOON[1])
    return (min(max(s, m0), m1) - m0) + (min(max(s, a0), a1) - a0)


def market_open_check(today: date) -> dict:
    """腾讯行情 sh000001 的报价时间戳当天 → 今日开市（周中节假日兜底）。

    这是 moneyflow.stock_info 已在用的同一端点；失败时返回 unknown，
    由调用方按「周末已排除的工作日」近似放行并在收据标注。
    """
    url = "http://qt.gtimg.cn/q=sh000001"
    try:
        raw = urllib.request.urlopen(url, timeout=8).read().decode("gbk", "replace")
    except Exception as e:  # noqa: BLE001
        return {"source": url, "status": "unknown", "error": str(e)[:200]}
    stamps = re.findall(r"20\d{12}", raw)
    if not stamps:
        return {"source": url, "status": "unknown", "error": "no 14-digit timestamp"}
    try:
        quote_dt = datetime.strptime(max(stamps), "%Y%m%d%H%M%S")
    except ValueError:
        return {"source": url, "status": "unknown", "error": f"bad ts {max(stamps)}"}
    status = "open" if quote_dt.date() == today else "closed_or_holiday"
    return {"source": url, "status": status, "quote_ts": quote_dt.isoformat(sep=" ")}


def _to_naive_cst(v, server_offset: timedelta) -> datetime | None:
    """CH 返回值 → 北京时间 naive datetime。tz-aware 直接换算；naive 加实测偏移。"""
    if v is None:
        return None
    if isinstance(v, datetime):
        dt = v
    else:
        s = str(v).strip().replace("T", " ")
        dt = None
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(s, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            return None
    if dt.tzinfo is not None:
        return dt.astimezone(CST).replace(tzinfo=None)
    return dt + server_offset


def measure_server_offset(client) -> tuple[timedelta, str]:
    """实测「CH now() → 本机北京时间」的偏移，取整到 15 分钟吃掉网络抖动。"""
    row = client.execute("SELECT now(), timezone()")[0]
    srv_now, srv_tz = row[0], str(row[1])
    if isinstance(srv_now, datetime) and srv_now.tzinfo is not None:
        return timedelta(0), f"{srv_tz} (tz-aware)"
    delta = (now_cst() - srv_now).total_seconds()
    offset = timedelta(seconds=round(delta / 900) * 900)
    return offset, f"{srv_tz} (naive, applied_offset={offset})"


def sample_tables(client, server_offset: timedelta) -> dict:
    out = {}
    wall = now_cst()
    for key, spec in TABLES.items():
        raw_max, n = client.execute(spec["sql"])[0]
        out[key] = {
            "wall_clock_cst": wall.isoformat(sep=" "),
            "max_ts": None,
            "n": int(n),
        }
        max_dt = _to_naive_cst(raw_max, server_offset)
        if int(n) > 0 and max_dt is not None and max_dt.year > 2000:
            out[key]["max_ts"] = max_dt.isoformat(sep=" ")
    return out


def classify_table(
    today: date, s1: dict, s2: dict, sample_stock: dict | None
) -> dict:
    """按设计稿 §5.1 判读表 + 双采样推进检查，返回收据里的一张表结论。"""
    now2 = datetime.fromisoformat(s2["wall_clock_cst"])
    max2 = datetime.fromisoformat(s2["max_ts"]) if s2["max_ts"] else None
    max1 = datetime.fromisoformat(s1["max_ts"]) if s1["max_ts"] else None
    n2 = s2["n"]

    result: dict = {
        "n": n2,
        "max_ts": s2["max_ts"],
        "lag_seconds": None,
        "session_lag_seconds": None,
        "samples": [s1, s2],
        "advanced_seconds": None,
    }
    if sample_stock:
        result["sample_stock"] = sample_stock

    if n2 <= 0 or max2 is None or max2.date() < today:
        result["verdict"] = "batch_or_stale"
        result["note"] = "今日分区无行或 max_ts 停在昨日"
        return result

    lag = (now2 - max2).total_seconds()
    session_lag = trade_seconds(now2) - trade_seconds(max2)
    result["lag_seconds"] = round(lag, 1)
    result["session_lag_seconds"] = round(session_lag, 1)
    if max1 is not None:
        result["advanced_seconds"] = round((max2 - max1).total_seconds(), 1)

    if lag < -60:
        result["verdict"] = "suspect_batch"
        result["note"] = "max_ts 超前墙钟，疑似截面快照/时钟异常"
        return result
    if max2.time() >= dtime(14, 50) and now2.time() < dtime(14, 35):
        result["verdict"] = "suspect_batch"
        result["note"] = "墙钟未到尾盘而 max_ts 已是 14:5x，疑似批量截面"
        return result

    if session_lag <= 120:
        elapsed = trade_seconds(now2) - trade_seconds(
            datetime.fromisoformat(s1["wall_clock_cst"])
        )
        if max1 is not None and elapsed >= 60 and max2 <= max1:
            result["verdict"] = "suspect_batch"
            result["note"] = "滞后小但两次采样 max_ts 未推进，疑似刚落地的批量"
        else:
            result["verdict"] = "live"
        return result

    result["verdict"] = "batch_or_stale"
    result["note"] = "max_ts 落后交易时段墙钟超过 120s"
    return result


def overall_verdict(sz: str, sh: str) -> str:
    if "connect_error" in (sz, sh):
        return "connect_error"
    if "suspect_batch" in (sz, sh):
        return "suspect_batch"
    if sz == sh == "live":
        return "live"
    return "batch_or_stale"


def existing_conclusive(today: date) -> Path | None:
    if not RECEIPT_DIR.exists():
        return None
    for p in sorted(RECEIPT_DIR.glob("*.json"), reverse=True):
        try:
            doc = json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            continue
        if doc.get("trading_day") == today.isoformat() and doc.get("verdict") in CONCLUSIVE:
            return p
    return None


def write_receipt(doc: dict) -> Path:
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ") + ".json"
    path = RECEIPT_DIR / name
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    return path


def git_revision() -> str:
    import subprocess

    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def base_doc(now: datetime) -> dict:
    return {
        "schema": "intraday-l2-probe/v1",
        "wall_clock_cst": now.isoformat(sep=" "),
        "trading_day": now.date().isoformat(),
        "probe": "scripts/moneyflow/probe_intraday_write.py",
        "code_tree": str(Path(__file__).resolve().parents[2]),
        "git_revision": git_revision(),
        "interpreter": sys.executable,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check-only", action="store_true", help="连通性自检：不写收据、忽略窗口")
    ap.add_argument("--force", action="store_true", help="忽略今日已有结论收据，重新探测")
    ap.add_argument("--assume-trading-day", action="store_true", help="跳过腾讯开市核对（周末仍硬挡）")
    ap.add_argument("--gap-seconds", type=float, default=90.0, help="双采样间隔，默认 90s")
    ap.add_argument("--sz-sample", default="300308", help="深市样例股，默认沿用 preflight 的 300308")
    ap.add_argument("--sh-sample", default="600519", help="沪市样例股，默认 600519")
    args = ap.parse_args()

    now = now_cst()
    today = now.date()
    doc = base_doc(now)

    if args.check_only:
        try:
            connect_host, note, _ = resolve_clickhouse_host(config.HOST)
            client = make_client()
            offset, tz_note = measure_server_offset(client)
            tables = sample_tables(client, offset)
            client.disconnect()
        except Exception as e:  # noqa: BLE001
            print(f"CHECK FAIL: {e}")
            return 2
        doc.update(
            {
                "mode": "check_only（无判别力，仅验证链路）",
                "host_note": note,
                "server_tz": tz_note,
                "market_open_check": market_open_check(today),
                "tables": tables,
            }
        )
        print(json.dumps(doc, ensure_ascii=False, indent=2))
        return 0

    prior = existing_conclusive(today)
    if prior and not args.force:
        print(f"今日已有结论收据，跳过：{prior}")
        return 0

    # ---- 窗口与交易日守门（收据 verdict=invalid_window，退出码 3）----
    invalid_reason = None
    if now.weekday() >= 5:
        invalid_reason = "周末休市"
    elif not (WINDOW[0] <= now.time() <= WINDOW[1]):
        invalid_reason = f"墙钟 {now.time():%H:%M} 不在 10:00–14:30 窗口内"
    open_check = {"status": "skipped(--assume-trading-day)"}
    if invalid_reason is None and not args.assume_trading_day:
        open_check = market_open_check(today)
        if open_check["status"] == "closed_or_holiday":
            invalid_reason = f"腾讯行情最新报价停在 {open_check.get('quote_ts')}，今日未开市"
    doc["market_open_check"] = open_check
    if invalid_reason:
        doc.update({"verdict": "invalid_window", "reason": invalid_reason})
        path = write_receipt(doc)
        print(f"invalid_window: {invalid_reason}\n收据: {path}")
        return 3

    # ---- 连接 + 双采样 ----
    try:
        _, note, _ = resolve_clickhouse_host(config.HOST)
        client = make_client()
        offset, tz_note = measure_server_offset(client)
        doc.update({"host_note": note, "server_tz": tz_note})

        s1 = sample_tables(client, offset)
        time.sleep(max(args.gap_seconds, 0))
        s2 = sample_tables(client, offset)

        samples = {}
        for key, code in (
            ("sz_share_trans", args.sz_sample),
            ("sh_share_ngts_tick", args.sh_sample),
        ):
            raw_max, n = client.execute(TABLES[key]["sample_sql"], {"c": code})[0]
            dt = _to_naive_cst(raw_max, offset)
            samples[key] = {
                "code": code,
                "n": int(n),
                "max_ts": dt.isoformat(sep=" ") if dt and dt.year > 2000 else None,
            }
        client.disconnect()
    except Exception as e:  # noqa: BLE001
        doc.update(
            {
                "verdict": "connect_error",
                "sz_verdict": "connect_error",
                "sh_verdict": "connect_error",
                "error": str(e)[:500],
            }
        )
        path = write_receipt(doc)
        print(f"connect_error: {e}\n收据: {path}")
        return 2

    tables = {}
    for key in TABLES:
        tables[key] = classify_table(today, s1[key], s2[key], samples.get(key))
    doc["tables"] = tables
    doc["sz_verdict"] = tables["sz_share_trans"]["verdict"]
    doc["sh_verdict"] = tables["sh_share_ngts_tick"]["verdict"]
    doc["verdict"] = overall_verdict(doc["sz_verdict"], doc["sh_verdict"])
    doc["wall_clock_cst_end"] = now_cst().isoformat(sep=" ")

    path = write_receipt(doc)
    print(
        f"verdict={doc['verdict']} sz={doc['sz_verdict']} sh={doc['sh_verdict']}\n"
        f"收据: {path}"
    )
    return 0 if doc["verdict"] in CONCLUSIVE else 2


if __name__ == "__main__":
    sys.exit(main())
