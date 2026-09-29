"""桥缺口的两源仲裁补行：复牌 / 新股首日 / 送转三类，**两个独立来源给出同一前收才补**。

用户决策（2026-09-29 19:20 CST，原话「同意推荐方案」）：接受
`docs/superpowers/specs/2026-09-29-bridge-silent-gap-decision-request.md` 的推荐——
桥对这三类股票继续拒算（`hithink_stock_preview` 合同不变、不「缺前日就向前找」），
由本模块在**另有独立来源一致**时补行；不一致或证据不足就保持缺行并如实报出。

## 三类缺口与各自的两个来源

| 类型 | 判定 | 来源 1（库内） | 来源 2（外部，至少一个且全部一致） |
|---|---|---|---|
| 复牌 | 目标日有 bar；上一根 bar 早于前一计划交易日；区间 (上一根, 目标日] 无除权记录 | 上一根收盘价 | 封存腾讯报价「昨收」/ 东财日 K 涨跌额反推 |
| 送转 / 配股 | 前一计划日有 bar；目标日恰一条非现金事件 | `(前收 − 派息 + 配股价×配股比例)/(1 + 送转 + 配股)` | 同上 |
| 新股首日 | 同花顺十年历史里没有任何更早 bar | 无 | **至少两个外部来源**且彼此一致 |

所有外部来源还必须报出与同花顺相同的当日收盘（差 ≤ 0.005），否则视为对不上号、不补。
任何一个外部来源与候选不一致 → `conflict`，不补。

东财日 K 在送转日给的是**未除权**前收（09-22 300803.SZ 反推跌 29.8%），所以东财对送转类不算数：
`EASTMONEY_KLINE` 只用于复牌与新股首日。

## 写什么

- 行形状与桥完全相同（14 列），算术口径与 `hithink_stock_preview._calculate` 相同：
  `pct_chg=(close−pre)×100/pre` 半进到 0.01；`amount`=成交额元/1e8 到 0.0001；`volume`=股/100 取整。
- `source` = bar 自己的来源 + `:gapfill-two-source`（沿 `…:backfill-302132-20260914` 先例，前缀仍是 `hithink:`）。
- `stock_name`：封存腾讯报价的名称（合同 1 已接受）优先；否则沿桥政策取库内最近历史名（去 NUL，标 unverified）。
- 只 INSERT 目标日缺的代码；目标日已有行逐行不动，其他日期不动——单事务内用整行 hash 核对，越界即回滚。
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Context, Decimal, DivisionByZero, InvalidOperation, Overflow, localcontext
from pathlib import Path
from typing import Any

import duckdb

from ..hithink_stock_preview import _ADJUSTMENT_SOURCE, _bar_gaps, preview_stock_calculation
from ..trading_days import previous_scheduled_trading_day
from .bridge_hithink_stock_daily import BridgeRefused, _resolve_names

POLICY_VERSION = "bridge-gap-two-source-v1"
SOURCE_SUFFIX = ":gapfill-two-source"
TENCENT_CAPTURE = "tencent:captured-dated-quote"
EASTMONEY_KLINE = "eastmoney:kline-daily-unadjusted"
TOLERANCE = Decimal("0.005")
_CENT = Decimal("0.01")
_ARBITRABLE = {"missing-previous-bar", "unsupported-noncash-action"}
_QUOTE = re.compile(r'v_(sh|sz|bj)(\d{6})="([^"]*)"')
_BAR_COLUMNS = ("stock_ts_code", "trade_date", "open", "high", "low", "close", "volume", "turnover",
                "adjusted", "source", "updated_at")


@dataclass(frozen=True)
class Evidence:
    source: str
    close: Decimal
    pre_close: Decimal
    name: str | None = None


def _dec(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def load_tencent_capture(capture_dir: Path | str) -> dict[str, Evidence]:
    """封存目录 batch-*.raw（GBK）→ 代码: Evidence。字段 1 名称、3 现价（收盘后即收盘）、4 昨收。"""
    out: dict[str, Evidence] = {}
    for path in sorted(Path(capture_dir).glob("batch-*.raw")):
        for match in _QUOTE.finditer(path.read_bytes().decode("gbk", errors="replace")):
            fields = match.group(3).split("~")
            if len(fields) < 5:
                continue
            close, pre = _dec(fields[3]), _dec(fields[4])
            if close is None or pre is None or close <= 0 or pre <= 0:
                continue
            code = f"{match.group(2)}.{match.group(1).upper()}"
            out[code] = Evidence(TENCENT_CAPTURE, close, pre, fields[1] or None)
    return out


def load_eastmoney_kline(kline_dir: Path | str, trade_date: str) -> dict[str, Evidence]:
    """`{代码}.json` = push2his kline/get（fqt=0，fields2=f51,f52,f53,f54,f55,f56,f57,f59,f60）原样响应。

    取目标日那根：收盘 = 第 3 列，前收 = 收盘 − 涨跌额（第 9 列）。名称是东财**当前**名，不作名称来源。
    """
    out: dict[str, Evidence] = {}
    for path in sorted(Path(kline_dir).glob("*.json")):
        code = path.stem
        try:
            data = json.loads(path.read_text(encoding="utf-8")).get("data") or {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        for line in data.get("klines") or []:
            parts = line.split(",")
            if len(parts) != 9 or parts[0] != trade_date:
                continue
            close, change = _dec(parts[2]), _dec(parts[8])
            if close is None or change is None or close <= 0:
                continue
            pre = close - change
            if pre > 0:
                out[code] = Evidence(EASTMONEY_KLINE, close, pre, None)
    return out


EASTMONEY_KLINE_ENDPOINT = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_FETCH_CAP = 50  # 一晚缺口通常 3~10 只；超出说明上游或桥出了别的事，不该靠逐只抓来掩盖


def gap_codes(con: duckdb.DuckDBPyConnection, trade_date: str) -> list[str]:
    """只读：目标日同花顺有 bar、canonical 无行的代码。"""
    return [r[0] for r in con.execute(
        "SELECT h.stock_ts_code FROM fact_stock_daily_hithink AS h WHERE h.trade_date = ? AND NOT EXISTS ("
        "SELECT 1 FROM fact_stock_daily AS d WHERE d.trade_date = h.trade_date "
        "AND d.stock_ts_code = h.stock_ts_code) ORDER BY 1", [date.fromisoformat(trade_date)]).fetchall()]


def eastmoney_kline_url(code: str, trade_date: str) -> str:
    """目标日一根不复权日 K；fields2 与 `load_eastmoney_kline` 的 9 列约定一致（第 9 列涨跌额）。"""
    plain, _, market = code.partition(".")
    day = trade_date.replace("-", "")
    return (f"{EASTMONEY_KLINE_ENDPOINT}?secid={'1' if market.upper() == 'SH' else '0'}.{plain}"
            "&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f59,f60"
            f"&klt=101&fqt=0&beg={day}&end={day}")


def fetch_eastmoney_kline(codes: list[str], trade_date: str, out_dir: Path | str, *,
                          get_json=None, timeout: float = 15.0) -> dict[str, Any]:
    """逐只抓东财日 K 落盘成 `{代码}.json`，供 `load_eastmoney_kline` 当第二来源读。

    尽力而为：单只失败记原因不影响其他只；上游判定拒服务（`UpstreamRefusing`）立刻停，
    剩余代码记 not-requested——再打只会给封禁计时器续命。传输层只回解析后的 dict，
    所以落盘的是它的规范化重序列化（sort_keys），另写 SHA256SUMS。目录必须是新的。
    """
    from .sync_eastmoney_stock_snapshot import UpstreamRefusing

    if get_json is None:
        from .sync_eastmoney_stock_snapshot import _get_json

        def get_json(url: str) -> dict:
            return _get_json(url, timeout, retries=2)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    wanted = sorted(set(codes))
    status: dict[str, str] = {code: "not-requested:over-cap" for code in wanted[EASTMONEY_FETCH_CAP:]}
    sums: list[str] = []
    for index, code in enumerate(wanted[:EASTMONEY_FETCH_CAP]):
        try:
            data = get_json(eastmoney_kline_url(code, trade_date))
        except UpstreamRefusing:
            status[code] = "error:UpstreamRefusing"
            status.update({rest: "not-requested:upstream-refusing"
                           for rest in wanted[index + 1:EASTMONEY_FETCH_CAP]})
            break
        except Exception as exc:  # noqa: BLE001 — 证据尽力而为，缺一只只是少一个来源
            status[code] = f"error:{type(exc).__name__}"
            continue
        body = (json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        (out / f"{code}.json").write_bytes(body)
        sums.append(f"{hashlib.sha256(body).hexdigest()}  {code}.json")
        status[code] = "ok"
    (out / "SHA256SUMS").write_text("".join(f"{line}\n" for line in sums), encoding="utf-8")
    return {"source": EASTMONEY_KLINE, "trade_date": trade_date, "requested": len(wanted),
            "fetched": sum(1 for v in status.values() if v == "ok"), "status": dict(sorted(status.items()))}


def _bars(con, sql: str, params: list) -> list[dict]:
    return [dict(zip(_BAR_COLUMNS, r, strict=True)) for r in con.execute(sql, params).fetchall()]


def _noncash_reference(prev_close: Decimal, event: dict) -> Decimal | None:
    cash, bonus, ratio, price = (event[k] for k in (
        "dividend_per_share", "per_share_bonus", "allotment_ratio", "allotment_price"))
    denominator = Decimal(1) + bonus + ratio
    if denominator <= 0:
        return None
    reference = ((prev_close - cash + price * ratio) / denominator).quantize(_CENT, rounding=ROUND_HALF_UP)
    return reference if reference > 0 else None


def _classify(td: date, prev: date, last: dict | None, events: list[dict], reasons: list[str]):
    """返回 (kind, 库内候选前收 | None, 拒绝原因 | None)。"""
    if last is None:
        if reasons != ["missing-previous-bar"]:
            return "first_day", None, "unexpected-reasons"
        return "first_day", None, None
    if last["trade_date"] < prev:
        if reasons != ["missing-previous-bar"]:
            return "resumption", None, "unexpected-reasons"
        if events:
            return "resumption", None, "events-inside-suspension-gap"
        return "resumption", _dec(last["close"]).quantize(_CENT, rounding=ROUND_HALF_UP), None
    if reasons != ["unsupported-noncash-action"]:
        return "other", None, "unexpected-reasons"
    if len(events) != 1 or events[0]["ex_date"] != td:
        return "noncash", None, "event-shape"
    event = events[0]
    if event["source"] != _ADJUSTMENT_SOURCE or event["currency"] != "CNY":
        return "noncash", None, "adjustment-provenance"
    values = {k: _dec(event[k]) for k in ("dividend_per_share", "per_share_bonus", "allotment_ratio",
                                          "allotment_price")}
    if any(v is None or v < 0 for v in values.values()):
        return "noncash", None, "invalid-adjustment-values"
    reference = _noncash_reference(_dec(last["close"]), values)
    return ("noncash", reference, None) if reference is not None else ("noncash", None, "invalid-reference")


def _valid_name(name) -> bool:
    """与 compute_local_stats 的 InvalidStockName 同一口径：非空、无控制字符。"""
    return (isinstance(name, str) and bool(name.strip())
            and not any(ord(char) < 32 or ord(char) == 127 for char in name))


def _usable(kind: str, ev: Evidence) -> bool:
    # 东财日 K 在送转日给未除权前收，不能为送转作证。
    return not (kind == "noncash" and ev.source == EASTMONEY_KLINE)


def _arbitrate(kind: str, candidate: Decimal | None, close: Decimal, evidence: list[Evidence]):
    """返回 (verdict, 采用的前收 | None, 明细)。"""
    usable = [ev for ev in evidence if _usable(kind, ev)]
    detail = [{"source": ev.source, "close": float(ev.close), "pre_close": float(ev.pre_close),
               "close_agrees": abs(ev.close - close) <= TOLERANCE} for ev in usable]
    if not usable:
        return "no-external-evidence", None, detail
    if any(not d["close_agrees"] for d in detail):
        return "conflict-close", None, detail
    if kind == "first_day":
        if len(usable) < 2:
            return "first-day-needs-two-external", None, detail
        base = usable[0].pre_close
        if any(abs(ev.pre_close - base) > TOLERANCE for ev in usable):
            return "conflict-pre-close", None, detail
        return "two-source-agree", base.quantize(_CENT, rounding=ROUND_HALF_UP), detail
    if candidate is None:
        return "no-internal-candidate", None, detail
    if any(abs(ev.pre_close - candidate) > TOLERANCE for ev in usable):
        return "conflict-pre-close", None, detail
    return "two-source-agree", candidate, detail


def _row(td: date, current: dict, pre_close: Decimal, name: str | None, now) -> tuple:
    context = Context(prec=50, rounding=ROUND_HALF_UP, Emin=-999999, Emax=999999, capitals=1, clamp=0,
                      flags=[], traps=[InvalidOperation, DivisionByZero, Overflow])
    with localcontext(context):
        close = _dec(current["close"])
        pct = ((close - pre_close) * Decimal(100) / pre_close).quantize(_CENT)
        amount = (_dec(current["turnover"]) / Decimal(100_000_000)).quantize(Decimal("0.0001"))
        volume = (_dec(current["volume"]) / Decimal(100)).quantize(Decimal(1))
    return (td, current["stock_ts_code"], name, float(close), float(pre_close), float(pct) or 0.0,
            float(amount), None, f"{current['source']}{SOURCE_SUFFIX}", now,
            float(_dec(current["open"])), float(_dec(current["high"])), float(_dec(current["low"])),
            float(volume))


def plan_gap_fill(con: duckdb.DuckDBPyConnection, trade_date: str, evidence_sets: list[dict[str, Evidence]],
                  *, now=None) -> dict[str, Any]:
    """只读：对目标日「同花顺有 bar、canonical 无行」的代码逐只仲裁，给出可写行与逐只证据。"""
    from datetime import datetime

    td = date.fromisoformat(trade_date)
    prev = previous_scheduled_trading_day(td)
    if prev is None:
        raise BridgeRefused(f"{trade_date} 前一计划交易日未知")
    now = now or datetime.now()
    vendor = {b["stock_ts_code"]: b for b in _bars(
        con, f"SELECT {', '.join(_BAR_COLUMNS)} FROM fact_stock_daily_hithink WHERE trade_date = ?", [td])}
    canonical = {r[0] for r in con.execute(
        "SELECT stock_ts_code FROM fact_stock_daily WHERE trade_date = ?", [td]).fetchall()}
    if not canonical:
        raise BridgeRefused(f"{trade_date} canonical 整日 0 行——先走桥，补缺口只针对已桥接的日子")
    gap_codes = sorted(set(vendor) - canonical)
    reasons = {}
    if gap_codes:
        reasons = {g["stock_ts_code"]: g["reasons"] for g in
                   preview_stock_calculation(con, td, stock_codes=gap_codes)["gaps"]}
    items, fills = [], []
    for code in gap_codes:
        current = vendor[code]
        item: dict[str, Any] = {"stock_ts_code": code, "reasons": reasons.get(code, [])}
        items.append(item)
        if not item["reasons"] or not set(item["reasons"]) <= _ARBITRABLE:
            item["verdict"] = "not-arbitrable"
            continue
        bad = _bar_gaps(current, "current")
        last_rows = _bars(con, f"SELECT {', '.join(_BAR_COLUMNS)} FROM fact_stock_daily_hithink "
                               "WHERE stock_ts_code = ? AND trade_date < ? ORDER BY trade_date DESC LIMIT 1",
                          [code, td])
        last = last_rows[0] if last_rows else None
        if last is not None:
            bad += _bar_gaps(last, "previous")
        if bad:
            item["verdict"], item["bar_gaps"] = "invalid-bar", bad
            continue
        low = last["trade_date"] if last else date(1900, 1, 1)
        events = [dict(zip(("ex_date", "dividend_per_share", "per_share_bonus", "allotment_ratio",
                            "allotment_price", "currency", "source"), r)) for r in con.execute(
            "SELECT ex_date, dividend_per_share, per_share_bonus, allotment_ratio, allotment_price, currency, "
            "source FROM fact_stock_adjustment_hithink WHERE stock_ts_code = ? AND ex_date > ? AND ex_date <= ? "
            "ORDER BY ex_date", [code, low, td]).fetchall()]
        kind, candidate, refusal = _classify(td, prev, last, events, item["reasons"])
        item.update({"kind": kind, "last_bar": ({"date": str(last["trade_date"]), "close": last["close"]}
                                                if last else None),
                     "events_in_gap": len(events),
                     "internal_candidate": float(candidate) if candidate is not None else None})
        if refusal:
            item["verdict"] = refusal
            continue
        evidence = [s[code] for s in evidence_sets if code in s]
        verdict, pre_close, detail = _arbitrate(kind, candidate, _dec(current["close"]), evidence)
        item.update({"verdict": verdict, "evidence": detail})
        if verdict != "two-source-agree":
            continue
        item["pre_close"] = float(pre_close)
        names = [ev.name for ev in evidence if ev.source == TENCENT_CAPTURE and ev.name]
        item["name_source"] = TENCENT_CAPTURE if names else "db_history_latest_unverified"
        fills.append((code, current, pre_close, names[0] if names else None))
    history = _resolve_names(con, [c for c, _, _, n in fills if n is None], trade_date)
    by_code = {item["stock_ts_code"]: item for item in items}
    rows = []
    for code, current, pre_close, name in fills:
        name = name or (history.get(code) or "").replace("\x00", "").strip() or None
        if not _valid_name(name):
            # 无名行进 canonical 会让 limit-stats-local 按设计拒跑（InvalidStockName），拖垮整晚发布。
            by_code[code]["verdict"] = "no-valid-name"
            continue
        rows.append(_row(td, current, pre_close, name, now))
    return {
        "policy_version": POLICY_VERSION, "trade_date": trade_date, "previous_trade_date": str(prev),
        "vendor_codes": len(vendor), "canonical_rows_before": len(canonical),
        "gap_count": len(gap_codes), "fill_count": len(rows), "items": items, "rows": rows,
        "evidence_sources": sorted({ev.source for s in evidence_sets for ev in s.values()}),
    }


def _fingerprints(con, td: date) -> tuple[dict, tuple]:
    days = {str(r[0]): (r[1], r[2]) for r in con.execute(
        "SELECT trade_date, count(*), sum(hash(d)::HUGEINT) FROM fact_stock_daily AS d GROUP BY 1").fetchall()}
    return days, days.get(str(td), (0, 0))


def apply_gap_fill(con: duckdb.DuckDBPyConnection, plan: dict[str, Any]) -> dict[str, Any]:
    """单事务 INSERT 计划行；目标日原有行与其他日期逐一核对未动，越界回滚。"""
    td = date.fromisoformat(plan["trade_date"])
    rows = plan["rows"]
    if not rows:
        return {"trade_date": plan["trade_date"], "inserted": 0}
    codes = [r[1] for r in rows]
    con.execute("BEGIN TRANSACTION")
    try:
        before, _ = _fingerprints(con, td)
        clash = con.execute("SELECT stock_ts_code FROM fact_stock_daily WHERE trade_date = ? AND stock_ts_code "
                            "IN (SELECT unnest(?::VARCHAR[]))", [td, codes]).fetchall()
        if clash:
            raise BridgeRefused(f"{td} 已有这些代码的行，补缺口只插不改：{[c[0] for c in clash]}")
        keep_before = con.execute("SELECT count(*), sum(hash(d)::HUGEINT) FROM fact_stock_daily AS d "
                                  "WHERE trade_date = ?", [td]).fetchone()
        con.executemany(
            "INSERT INTO fact_stock_daily (trade_date, stock_ts_code, stock_name, close, pre_close, pct_chg, "
            "amount, turnover, source, updated_at, open, high, low, volume) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows)
        after, _ = _fingerprints(con, td)
        drift = sorted(d for d in before.keys() | after.keys() if d != str(td) and before.get(d) != after.get(d))
        if drift:
            raise BridgeRefused(f"写入越界：其他日期被改动 {drift[:10]}")
        keep_after = con.execute(
            "SELECT count(*), sum(hash(d)::HUGEINT) FROM fact_stock_daily AS d WHERE trade_date = ? "
            "AND stock_ts_code NOT IN (SELECT unnest(?::VARCHAR[]))", [td, codes]).fetchone()
        if tuple(keep_after) != tuple(keep_before):
            raise BridgeRefused(f"{td} 原有行被改动：{keep_before} → {keep_after}")
        final = con.execute("SELECT count(*) FROM fact_stock_daily WHERE trade_date = ?", [td]).fetchone()[0]
        if final != keep_before[0] + len(rows):
            raise BridgeRefused(f"{td} 行数 {final} != {keep_before[0]} + {len(rows)}")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return {"trade_date": plan["trade_date"], "inserted": len(rows), "rows_before": keep_before[0],
            "rows_after": final, "existing_rows_unchanged": True, "other_days_unchanged": True}
