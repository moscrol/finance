"""历史日全A日线回补：新浪通道（akshare.stock_zh_a_daily）。

为什么需要它（2026-09-11 补 09-08 实测）：
  - mootdx：本机 14 台 HQ 服务器**全部**返回 0 根、每次恰好 ~3.95s（TDX 7709 二进制
    协议走不通；本机 TCP 出口是 198.18.0.1 的 TUN 假地址段）。51 分钟 0 提交。
  - 东财 push2his（runbook 原先记的备用源）：前 ~12 个请求正常，随后整站级拒连，
    `push2his / 1. / 5. / 8. / 92.push2his` 全部 "Empty reply from server"。
    注意生产快照用的是 **push2**（另一台），未受影响，实测仍 HTTP 200。
  - iFinD：仓内无 `skills/ifind/mcp_config.json`，无 token。
  - 腾讯 / 新浪 CN_MarketData：通，但**只有量没有成交额**，市场总额与板块金额算不出来。
  → 唯一既通、又带 amount、又覆盖北交所的历史源是新浪的 stock_zh_a_daily。

量纲（用 600000.SH 的 09-07 行与库内既有值三方对账得到，勿凭记忆改）：
    amount   元   ÷ 1e8  → 亿元
    volume   股   ÷ 100  → 手
    turnover 小数 × 100  → 百分数
    pre_close = 返回序列里 D 的前一根收盘（裸价链，与 mootdx 同基；东财快照是除息调整基，
                所以次日锚会有 0.1~0.3% 的除息股对不上，属已知语义差异）

三个子命令分开跑，取数阶段**不持数据库连接**（避免长事务把生产端只读连接饿死）：
    fetch    --trade-date D [--out rows.jsonl]     只取数落盘
    validate --trade-date D [--rows rows.jsonl]    只读对账，不写
    write    --trade-date D [--rows rows.jsonl]    单次短事务 upsert + 回读

写库前 validate 必须 PASS。四条对账见 validate 的输出。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

SOURCE = "sina:stock_zh_a_daily"
_PREFIX = {"SH": "sh", "SZ": "sz", "BJ": "bj"}


def _db_path() -> str:
    from market_feature_store.db import DB_PATH

    return str(DB_PATH)


def _default_rows(trade_date: str) -> Path:
    return Path(f"/tmp/backfill-sina-{trade_date}.jsonl")


def _neighbours(con, d: date) -> tuple[str, str]:
    """目标日前后各一个已有数据的交易日，用来取宇宙/名字与做次日锚。"""
    prev = con.execute(
        "SELECT max(trade_date) FROM fact_stock_daily WHERE trade_date < ?", [d]
    ).fetchone()[0]
    nxt = con.execute(
        "SELECT min(trade_date) FROM fact_stock_daily WHERE trade_date > ?", [d]
    ).fetchone()[0]
    return str(prev), str(nxt) if nxt else str(prev)


def cmd_fetch(args) -> int:
    import akshare as ak
    import duckdb

    d = date.fromisoformat(args.trade_date)
    out = Path(args.out) if args.out else _default_rows(args.trade_date)
    con = duckdb.connect(_db_path(), read_only=True)
    try:
        prev, nxt = _neighbours(con, d)
        uni = con.execute(
            """
            SELECT stock_ts_code, any_value(stock_name)
            FROM fact_stock_daily
            WHERE trade_date IN (?, ?)
              AND stock_ts_code NOT IN (SELECT stock_ts_code FROM fact_stock_daily WHERE trade_date = ?)
            GROUP BY 1 ORDER BY 1
            """,
            [prev, nxt, args.trade_date],
        ).fetchall()
    finally:
        con.close()
    print(f"[fetch] 宇宙取自 {prev} ∪ {nxt}，待抓 {len(uni)} 只", file=sys.stderr, flush=True)

    win_start = (d - timedelta(days=10)).strftime("%Y%m%d")
    win_end = d.strftime("%Y%m%d")
    ok = suspended = 0
    fails: list[tuple[str, str]] = []
    t0 = time.time()
    with out.open("w", encoding="utf-8") as fh:
        for i, (code, name) in enumerate(uni, start=1):
            num, ex = code.split(".")
            try:
                df = ak.stock_zh_a_daily(symbol=_PREFIX[ex] + num, start_date=win_start,
                                         end_date=win_end, adjust="")
                recs = df.to_dict("records") if df is not None else []
                target = prev_close = None
                for j, r in enumerate(recs):
                    if str(r["date"])[:10] == args.trade_date:
                        target = r
                        prev_close = float(recs[j - 1]["close"]) if j > 0 else None
                        break
                if target is None:
                    suspended += 1
                    continue
                close = float(target["close"])
                fh.write(json.dumps({
                    "trade_date": args.trade_date, "stock_ts_code": code, "stock_name": name,
                    "close": round(close, 3),
                    "pre_close": round(prev_close, 3) if prev_close else None,
                    "pct_chg": round((close / prev_close - 1) * 100, 4) if prev_close else None,
                    "amount": round(float(target["amount"]) / 1e8, 4),
                    "turnover": round(float(target["turnover"]) * 100, 4),
                    "source": SOURCE,
                    "open": round(float(target["open"]), 3),
                    "high": round(float(target["high"]), 3),
                    "low": round(float(target["low"]), 3),
                    "volume": round(float(target["volume"]) / 100, 1),
                }, ensure_ascii=False) + "\n")
                ok += 1
            except Exception as e:  # noqa: BLE001
                fails.append((code, f"{type(e).__name__}:{str(e)[:60]}"))
                time.sleep(0.5)
            if i % 200 == 0:
                el = time.time() - t0
                print(f"[fetch] {i}/{len(uni)} ok={ok} 停牌={suspended} 失败={len(fails)} "
                      f"{el:.0f}s 预计剩 {el / i * (len(uni) - i):.0f}s", file=sys.stderr, flush=True)
    print(f"[fetch] 完成 ok={ok} 停牌={suspended} 失败={len(fails)} → {out}", file=sys.stderr, flush=True)
    for code, err in fails:
        print(f"[fetch]   失败 {code}: {err}", file=sys.stderr)
    return 0


def cmd_validate(args) -> int:
    import duckdb

    d = date.fromisoformat(args.trade_date)
    rows = [json.loads(line) for line in (Path(args.rows) if args.rows else _default_rows(args.trade_date))
            .read_text(encoding="utf-8").splitlines() if line.strip()]
    by = {r["stock_ts_code"]: r for r in rows}
    con = duckdb.connect(_db_path(), read_only=True)
    try:
        prev, nxt = _neighbours(con, d)
        prev_close = dict(con.execute(
            "SELECT stock_ts_code, close FROM fact_stock_daily WHERE trade_date = ?", [prev]).fetchall())
        next_pre = dict(con.execute(
            "SELECT stock_ts_code, pre_close FROM fact_stock_daily WHERE trade_date = ?", [nxt]).fetchall())
        neigh = con.execute(
            "SELECT trade_date, round(sum(amount),1), round(median(turnover),3), count(*)"
            " FROM fact_stock_daily WHERE trade_date IN (?, ?) GROUP BY 1 ORDER BY 1", [prev, nxt]).fetchall()
    finally:
        con.close()

    fails = []
    c1 = [(c, r["pre_close"], prev_close[c]) for c, r in by.items()
          if r["pre_close"] is not None and c in prev_close]
    b1 = [x for x in c1 if abs(x[1] - x[2]) > 0.011]
    print(f"① pre_close 链 vs {prev} close: 可比 {len(c1)} 不符 {len(b1)} "
          f"({len(b1) / max(len(c1), 1) * 100:.2f}%)")
    if c1 and len(b1) / len(c1) > 0.02:
        fails.append("pre_close 链不符 >2%")

    c2 = [(c, r["close"], next_pre[c]) for c, r in by.items() if next_pre.get(c) is not None]
    b2 = [x for x in c2 if abs(x[1] - x[2]) > 0.011]
    print(f"② 次日锚 {nxt}.pre_close == 本日 close: 可比 {len(c2)} 不符 {len(b2)} "
          f"({len(b2) / max(len(c2), 1) * 100:.2f}%)  ← 除息股会差，>2% 才算红")
    if c2 and len(b2) / len(c2) > 0.02:
        fails.append("次日锚不符 >2%")

    b3 = [r for r in rows if r["pct_chg"] is not None and r["pre_close"]
          and abs(r["pct_chg"] - (r["close"] / r["pre_close"] - 1) * 100) > 0.05]
    print(f"③ pct_chg 重算: 不符 {len(b3)}")
    if len(b3) > len(rows) * 0.001:
        fails.append("pct_chg 重算不符 >0.1%")

    b4 = [r for r in rows if r["volume"]
          and not (r["low"] * 0.98 <= r["amount"] * 1e8 / (r["volume"] * 100) <= r["high"] * 1.02)]
    print(f"④ 量纲闭环（amount/volume 反推均价落在 [low,high]）: 越界 {len(b4)}/{len(rows)}")
    if b4:
        fails.append(f"量纲闭环越界 {len(b4)} 只")
    print(f"   本次 sum(amount)={sum(r['amount'] for r in rows):.1f} 亿")
    for td, s, t, n in neigh:
        print(f"   邻日 {td}: {n} 只 sum(amount)={s} 亿 turnover中位={t}%")

    print("\n" + ("RESULT: FAIL —— " + "; ".join(fails) if fails else "RESULT: PASS"))
    return 1 if fails else 0


def cmd_write(args) -> int:
    import duckdb
    import pandas as pd

    from market_feature_store.sync.sync_mootdx_stock_daily import BULK_UPSERT_SQL, COLS

    rows = [json.loads(line) for line in (Path(args.rows) if args.rows else _default_rows(args.trade_date))
            .read_text(encoding="utf-8").splitlines() if line.strip()]
    now = datetime.now()
    for r in rows:
        r["updated_at"] = now
    _buf_df = pd.DataFrame([[r[c] for c in COLS] for r in rows], columns=COLS)  # noqa: F841
    con = duckdb.connect(_db_path())
    try:
        before = con.execute("SELECT count(*) FROM fact_stock_daily WHERE trade_date = ?",
                             [args.trade_date]).fetchone()[0]
        con.register("_buf_df", _buf_df)
        con.execute(BULK_UPSERT_SQL)
        con.unregister("_buf_df")
        after = con.execute("SELECT count(*) FROM fact_stock_daily WHERE trade_date = ?",
                            [args.trade_date]).fetchone()[0]
        # TDX 定长字段的 NUL 填充（runbook 坑③）：写完就地清掉，别留给下游
        con.execute(
            r"UPDATE fact_stock_daily SET stock_name = rtrim(stock_name, chr(0))"
            r" WHERE trade_date = ? AND stock_name LIKE '%' || chr(0) || '%'", [args.trade_date])
        print(f"{args.trade_date} 行数 {before} → {after}")
        print("来源:", con.execute("SELECT source, count(*) FROM fact_stock_daily WHERE trade_date = ?"
                                 " GROUP BY 1 ORDER BY 2 DESC", [args.trade_date]).fetchall())
        print("空值(close/amount/pct):", con.execute(
            "SELECT count(*) FILTER (WHERE close IS NULL), count(*) FILTER (WHERE amount IS NULL),"
            " count(*) FILTER (WHERE pct_chg IS NULL) FROM fact_stock_daily WHERE trade_date = ?",
            [args.trade_date]).fetchone())
    finally:
        con.close()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("fetch", cmd_fetch), ("validate", cmd_validate), ("write", cmd_write)):
        sp = sub.add_parser(name)
        sp.add_argument("--trade-date", required=True, help="交易日 YYYY-MM-DD")
        sp.add_argument("--rows" if name != "fetch" else "--out", default=None,
                        help="JSONL 路径，默认 /tmp/backfill-sina-<D>.jsonl")
        sp.set_defaults(func=fn)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
