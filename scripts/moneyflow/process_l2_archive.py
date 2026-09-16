"""从闲鱼日包 7z 抽出名单内「逐笔成交.csv」，按现有 moneyflow 口径写 DuckDB。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DUCKDB_PATH  # noqa: E402
from l2_paths import cache_dir, yyyymmdd  # noqa: E402
from moneyflow import (  # noqa: E402
    analyze,
    detect_quant_orders,
    duck_limitup_codes,
    duck_pct_chg_map,
    duck_top_turnover_codes,
    stock_info,
)
from write_to_duckdb import (  # noqa: E402
    begin_l2_run,
    mark_failed,
    write_capital_flow,
    write_quant_orders,
)

BIG_THR = float(os.environ.get("L2_BIG_THR_WAN", "100"))
QUANT_THR = float(os.environ.get("L2_QUANT_THR_WAN", "200"))
TOP_N = int(os.environ.get("L2_TOP_N", "100"))


def _seven_zip() -> str:
    found = shutil.which("7zz") or shutil.which("7z")
    if not found:
        raise FileNotFoundError("找不到 7zz/7z，homebrew 装 7zip")
    return found


def exch(code: str) -> str:
    return "SH" if code[0] in "69" else "SZ"


def folder(code: str) -> str:
    return f"{code}.{exch(code)}"


def prev_trade_date(date: str) -> str:
    import duckdb

    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        row = con.execute(
            "SELECT max(trade_date) FROM fact_stock_daily WHERE trade_date < ?",
            [date],
        ).fetchone()
    finally:
        con.close()
    if not row or not row[0]:
        raise RuntimeError(f"找不到 {date} 的前一交易日")
    return str(row[0])


def extract_trades(archive: Path, day: str, codes: list[str], outdir: Path) -> dict[str, Path]:
    if not codes:
        raise ValueError("no candidates to extract")
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    inners = [f"{day}/{folder(code)}/逐笔成交.csv" for code in codes]
    cmd = [_seven_zip(), "x", "-y", f"-o{outdir}", str(archive), *inners]
    print(f"7zz x {len(inners)} tick files", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        raise RuntimeError(
            f"7z extraction failed rc={result.returncode}: "
            f"{result.stdout[-800:]} {result.stderr[-400:]}"
        )
    extracted: dict[str, Path] = {}
    for code in codes:
        dest = outdir / day / folder(code) / "逐笔成交.csv"
        if dest.exists() and dest.stat().st_size > 0:
            extracted[code] = dest
        else:
            print(f"MISS {code}", flush=True)
    print(f"extracted {len(extracted)}/{len(codes)}", flush=True)
    return extracted


def load_ticks(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="gb18030", low_memory=False)
    price = pd.to_numeric(df["成交价格"], errors="coerce") / 10000.0
    volume = pd.to_numeric(df["成交数量"], errors="coerce")
    buy_no = pd.to_numeric(df["叫买序号"], errors="coerce")
    sell_no = pd.to_numeric(df["叫卖序号"], errors="coerce")
    out = pd.DataFrame(
        {
            "t": df["时间"].astype(str),
            "price": price,
            "volume": volume,
            "buy_no": buy_no,
            "sell_no": sell_no,
        }
    ).dropna()
    return out[out["price"] > 0].reset_index(drop=True)


def capital_from_ticks(ticks: pd.DataFrame) -> tuple[float, float, float]:
    if ticks.empty:
        return 0.0, 0.0, 0.0
    big = analyze(ticks, threshold_wan=BIG_THR)
    change = (ticks["price"].iloc[-1] / ticks["price"].iloc[0] - 1) * 100
    if big.empty:
        return 0.0, 0.0, float(change)
    active = float(big["active_net"].iloc[-1]) / 1e4
    total = float(big["total_net"].iloc[-1]) / 1e4
    return active, total, float(change)


def quant_from_ticks(ticks: pd.DataFrame) -> dict | None:
    if ticks.empty:
        return None
    work = ticks.copy()
    work["amount"] = work["price"] * work["volume"]
    thr = BIG_THR * 1e4
    buy_amt = work.groupby("buy_no")["amount"].sum()
    big_buys = buy_amt[buy_amt >= thr]
    if big_buys.empty:
        return None
    last_t = work.groupby("buy_no")["t"].last()
    buys = pd.DataFrame({"t": last_t.reindex(big_buys.index), "amount": big_buys}).dropna()
    infos, _ = detect_quant_orders(buys, min_amount=QUANT_THR * 1e4, top_n=100)
    if not infos:
        return None
    quant_total = sum(q["total"] for q in infos)
    buy_total = buys["amount"].sum() / 1e4
    biggest = max(infos, key=lambda q: q["total"])
    return {
        "量化单总额(万)": round(quant_total),
        "占大单买入%": round(quant_total / buy_total * 100, 2) if buy_total else 0.0,
        "簇数": len(infos),
        "笔数": sum(q["count"] for q in infos),
        "最大簇": f"{biggest['lo']:.0f}-{biggest['hi']:.0f}万x{biggest['count']}笔={biggest['total']:.0f}万",
    }


def rows_for_codes(
    extracted: dict[str, Path], codes: list[str], pct_map: dict[str, float]
) -> tuple[pd.DataFrame, dict]:
    recs = []
    for code in codes:
        path = extracted.get(code)
        if not path:
            raise RuntimeError(f"missing tick file for {code}")
        ticks = load_ticks(path)
        if ticks.empty:
            raise RuntimeError(f"no valid ticks for {code}; cannot confirm no trading")
        active, total, _change = capital_from_ticks(ticks)
        pct = pct_map.get(code)
        recs.append(
            {
                "code": code,
                "主买净额(万)": round(active),
                "总买净额(万)": round(total),
                # 当日涨幅%以日线口径为准（QC E3）；缺日线写 NULL，不拿日内末笔/首笔冒充。
                "当日涨幅%": None if pct is None else round(pct, 2),
            }
        )
        print(f"{code} 主买:{active:.0f}万 总买:{total:.0f}万", flush=True)
    stats = {
        "input_count": len(codes),
        "processed_count": len(recs),
        "failed_count": 0,
        "nonempty_count": len(recs),
        "empty_count": 0,
    }
    return pd.DataFrame(recs), stats


def attach_info(res: pd.DataFrame) -> pd.DataFrame:
    if res.empty:
        return res
    info = stock_info(list(res["code"]))
    out = res.copy()
    out["name"] = out["code"].map(lambda c: info.get(c, {}).get("name", ""))
    out["流通市值(亿)"] = out["code"].map(lambda c: info.get(c, {}).get("cap", 0.0))
    weighted = 0.7 * out["主买净额(万)"] + 0.3 * out["总买净额(万)"]
    cap = (out["流通市值(亿)"] * 1e4).replace(0, float("nan"))
    out["综合得分"] = (weighted / cap * 100).round(3)
    return out


def process_date(date: str, archive: Path) -> dict[str, int]:
    if not archive.exists():
        raise FileNotFoundError(f"missing {archive}")
    day = yyyymmdd(date)
    prev = prev_trade_date(date)
    limitup = duck_limitup_codes(prev)
    top100 = duck_top_turnover_codes(date, n=TOP_N)
    print(f"{date} prev={prev} limitup={len(limitup)} top100={len(top100)}", flush=True)
    if len(top100) < 80:
        print(f"WARN {date} top100 名单只有 {len(top100)} 只", flush=True)
    codes = sorted(set(limitup) | set(top100))
    pct_map = duck_pct_chg_map(date)
    if not pct_map:
        print(
            f"⚠️ {date} fact_stock_daily 无 pct_chg（行情缺口）："
            "当日涨幅% 写 NULL，不拿日内末笔/首笔口径冒充",
            flush=True,
        )
    extract_dir = cache_dir() / f"extract-{day}"
    begin_l2_run(date)
    try:
        if not limitup or len(top100) < TOP_N:
            raise RuntimeError(
                f"incomplete candidates: limitup={len(limitup)} top100={len(top100)}/{TOP_N}"
            )
        extracted = extract_trades(archive, day, codes, extract_dir)
        # Compute all three scans before publishing any result; missing ticks are not zero signals.
        lim_df, lim_stats = rows_for_codes(extracted, limitup, pct_map)
        top_df, top_stats = rows_for_codes(extracted, top100, pct_map)
        lim_df = attach_info(lim_df)
        top_df = attach_info(top_df)
        qrecs = []
        qprocessed = 0
        for code in top100:
            ticks = load_ticks(extracted[code])
            if ticks.empty:
                raise RuntimeError(f"no valid ticks for {code} during quant scan")
            quant = quant_from_ticks(ticks)
            qprocessed += 1
            if not quant:
                continue
            _active, _total, _change = capital_from_ticks(ticks)
            quant["code"] = code
            pct = pct_map.get(code)
            quant["当日涨幅%"] = None if pct is None else round(pct, 2)
            qrecs.append(quant)
        qdf = pd.DataFrame(qrecs)
        if not qdf.empty:
            info = stock_info(list(qdf["code"]))
            qdf["name"] = qdf["code"].map(lambda c: info.get(c, {}).get("name", ""))
        qstats = {
            "input_count": len(top100),
            "processed_count": qprocessed,
            "failed_count": 0,
            "nonempty_count": len(qrecs),
            "empty_count": qprocessed - len(qrecs),
        }
        write_capital_flow(
            date, "limitup", lim_df, BIG_THR, prev_limitup_date=prev, stats=lim_stats
        )
        write_capital_flow(date, "top100", top_df, BIG_THR, stats=top_stats)
        write_quant_orders(
            date,
            qdf if not qdf.empty else pd.DataFrame(),
            BIG_THR,
            QUANT_THR,
            stats=qstats,
        )
        print(
            f"wrote limitup={len(lim_df)} top100={len(top_df)} quant={len(qrecs)}",
            flush=True,
        )
        return {"limitup": len(lim_df), "top100": len(top_df), "quant": len(qrecs)}
    except Exception as exc:
        mark_failed(date, f"archive processing failed: {exc}")
        raise
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("用法: process_l2_archive.py YYYY-MM-DD archive.7z")
    process_date(sys.argv[1], Path(sys.argv[2]))
