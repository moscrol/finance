#!/usr/bin/env python3
"""price_lib: 免费公开行情工具（新浪名称->代码 + 腾讯前复权日线 + 指数日线）。

为 opinion-cross 的 T+N 盘后回测（机构胜率）提供行情底座。
不依赖 eastmoney/iFinD/duckdb/飞书凭证——只用两个公开接口：
  - 新浪 suggest：股票名 -> 带交易所前缀的代码（sh/sz + 6 位）
  - 腾讯 fqkline：前复权日线 OHLC（个股，复权后可跨除权日比较）
  - 腾讯 kline：指数日线 OHLC（沪深300 等基准，指数无需复权）

磁盘缓存默认落在仓外（WINRATE_CACHE，默认 ~/kb_work/winrate_cache），
不进 git；重跑时命中缓存，避免重复抓取。
"""
from __future__ import annotations

import json
import os
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

CACHE = Path(os.environ.get("WINRATE_CACHE", str(Path.home() / "kb_work" / "winrate_cache")))
(CACHE / "prices").mkdir(parents=True, exist_ok=True)
(CACHE / "index").mkdir(parents=True, exist_ok=True)
_CODE_MAP = CACHE / "code_map.json"


def _get(url: str, headers: dict | None = None, retries: int = 3) -> bytes:
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20, context=_CTX) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.5 * (i + 1))
    raise last  # type: ignore[misc]


# ---------- name -> code ----------
def _load_code_map() -> dict:
    if _CODE_MAP.exists():
        try:
            return json.loads(_CODE_MAP.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_code_map(m: dict) -> None:
    _CODE_MAP.write_text(json.dumps(m, ensure_ascii=False, indent=0), encoding="utf-8")


def name2code(name: str, _cache: dict | None = None) -> str | None:
    """新浪 suggest 解析股票名 -> 'shXXXXXX'/'szXXXXXX'。优先精确名匹配。
    None 表示未解析（非 A 股、改名、或检索不到）。结果缓存到磁盘。"""
    name = (name or "").strip()
    if not name:
        return None
    cache = _cache if _cache is not None else _load_code_map()
    if name in cache:
        return cache[name]
    code = None
    try:
        raw = _get(
            "https://suggest3.sinajs.cn/suggest/type=11,12&key=" + urllib.parse.quote(name),
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"},
        ).decode("gbk", "ignore")
        inside = raw.split('"', 2)
        if len(inside) >= 2 and inside[1]:
            rows = [r.split(",") for r in inside[1].split(";") if r]
            # 1) 精确名匹配
            for p in rows:
                if len(p) >= 4 and p[0] == name and (p[3].startswith("sh") or p[3].startswith("sz")):
                    code = p[3]
                    break
            # 2) 兜底：第一条 A 股
            if code is None:
                for p in rows:
                    if len(p) >= 4 and (p[3].startswith("sh") or p[3].startswith("sz")):
                        code = p[3]
                        break
    except Exception:  # noqa: BLE001
        code = None
    cache[name] = code
    if _cache is None:
        _save_code_map(cache)
    return code


# ---------- prices ----------
def _cache_read(cf: Path, start: str, end: str) -> list[tuple] | None:
    """范围感知缓存读：仅当缓存覆盖请求区间时复用（返回裁到 [start,end] 的子集）。"""
    if not cf.exists():
        return None
    try:
        blob = json.loads(cf.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(blob, dict) or "rows" not in blob:
        return None  # 旧格式（无范围元信息）一律重抓
    if blob.get("start", "9999") > start or blob.get("end", "0000") < end:
        return None  # 缓存区间不足覆盖
    return [tuple(x) for x in blob["rows"] if start <= x[0] <= end]


def _cache_write(cf: Path, start: str, end: str, rows: list[tuple]) -> None:
    cf.write_text(json.dumps({"start": start, "end": end, "rows": rows}, ensure_ascii=False), encoding="utf-8")


def qfq_daily(code: str, start: str, end: str) -> list[tuple]:
    """腾讯前复权日线。返回 [(date, open, close, high, low), ...]（升序）。范围感知磁盘缓存。"""
    cf = CACHE / "prices" / f"{code}.json"
    cached = _cache_read(cf, start, end)
    if cached is not None:
        return cached
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,{start},{end},640,qfq"
    j = json.loads(_get(url).decode("utf-8", "ignore"))
    d = j.get("data", {}).get(code, {})
    rows = d.get("qfqday") or d.get("day") or []
    out = [(r[0], float(r[1]), float(r[2]), float(r[3]), float(r[4])) for r in rows]
    _cache_write(cf, start, end, out)
    return out


def index_daily(code: str, start: str, end: str) -> list[tuple]:
    """腾讯指数日线（不复权）。返回 [(date, open, close, high, low), ...]。范围感知磁盘缓存。"""
    cf = CACHE / "index" / f"{code}.json"
    cached = _cache_read(cf, start, end)
    if cached is not None:
        return cached
    url = f"https://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={code},day,{start},{end},640"
    j = json.loads(_get(url).decode("utf-8", "ignore"))
    d = j.get("data", {}).get(code, {})
    rows = d.get("day") or d.get("qfqday") or []
    out = [(r[0], float(r[1]), float(r[2]), float(r[3]), float(r[4])) for r in rows]
    _cache_write(cf, start, end, out)
    return out


# ---------- forward metrics ----------
def _ret_pct(a: float, b: float) -> float:
    return round((a / b - 1) * 100, 2)


def fwd_metrics(klines: list[tuple], report_date: str, index_klines: list[tuple] | None = None) -> dict | None:
    """进场 = report_date 之后第一个交易日开盘价。
    输出 T+3/5/7/10 收盘收益、区间最高收益、峰值天数、峰值后回撤；
    若给 index_klines，则附带相对该基准的超额收益（剥大盘 beta）。
    每个窗口附 complete 标志（数据是否凑满该窗口）。"""
    dates = [k[0] for k in klines]
    entry_idx = next((i for i, dd in enumerate(dates) if dd > report_date), None)
    if entry_idx is None or entry_idx >= len(klines):
        return None
    entry_open = klines[entry_idx][1]
    if not entry_open:
        return None
    out: dict = {"entry_date": dates[entry_idx], "entry_open": round(entry_open, 4)}

    # index excess base: index open on the same entry date (fallback prev close)
    idx_entry = None
    if index_klines:
        idates = [k[0] for k in index_klines]
        if dates[entry_idx] in idates:
            idx_entry = index_klines[idates.index(dates[entry_idx])][1]

    for n in (3, 5, 7, 10):
        j = entry_idx + n
        if j < len(klines):
            out[f"ret_{n}d"] = _ret_pct(klines[j][2], entry_open)
            out[f"ret_{n}d_complete"] = True
            if index_klines and idx_entry:
                idates = [k[0] for k in index_klines]
                tgt = dates[j]
                if tgt in idates:
                    idx_ret = _ret_pct(index_klines[idates.index(tgt)][2], idx_entry)
                    out[f"excess_{n}d"] = round(out[f"ret_{n}d"] - idx_ret, 2)
        else:
            out[f"ret_{n}d"] = None
            out[f"ret_{n}d_complete"] = False

    window = klines[entry_idx : entry_idx + 11]  # entry + 10 trading days
    out["window_days"] = len(window) - 1
    if len(window) > 1:
        wdates = [w[0] for w in window]
        highs = [(w[0], w[3]) for w in window[1:]]  # exclude entry day itself
        peak_date, peak_high = max(highs, key=lambda x: x[1])
        out["interval_max_ret"] = _ret_pct(peak_high, entry_open)
        out["peak_day"] = wdates.index(peak_date)
        pk_i = wdates.index(peak_date)
        lows_after = [w[4] for w in window[pk_i + 1 :]]
        out["post_peak_dd"] = _ret_pct(min(lows_after), peak_high) if lows_after else 0.0
    return out


if __name__ == "__main__":
    # smoke test
    idx = index_daily("sh000300", "2026-05-15", "2026-06-12")
    print("index sh000300 rows:", len(idx), "| sample:", idx[:2], idx[-1:])
    kl = qfq_daily("sz002552", "2026-05-15", "2026-06-15")
    print("sz002552 rows:", len(kl))
    m = fwd_metrics(kl, "2026-05-22", idx)
    print("metrics:", json.dumps(m, ensure_ascii=False))
