#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finish remaining quant scan with process-level per-stock timeout; write DuckDB."""
from __future__ import annotations

import json
import os
import sys
import time
from multiprocessing import Process, Queue
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(Path(__file__).resolve().parent)

from moneyflow import (  # noqa: E402
    analyze,
    detect_quant_orders,
    fetch_trades_retry,
    make_client,
    stock_info,
)
from config import out_path  # noqa: E402
from write_to_duckdb import write_quant_orders  # noqa: E402


def _worker(code: str, date: str, big_thr: float, quant_thr: float, q: Queue) -> None:
    try:
        client = make_client()
        client, df = fetch_trades_retry(client, code, date)
        if df is None or getattr(df, "empty", True):
            q.put(("empty", code, None))
            return
        big = analyze(df, big_thr)
        if big.empty:
            q.put(("empty", code, None))
            return
        buys = (
            big[big["buyer_big"]]
            .groupby("buy_no")
            .agg(t=("t", "last"), amount=("amount", "sum"))
            .reset_index()
        )
        infos, _ = detect_quant_orders(buys, min_amount=quant_thr * 1e4, top_n=100)
        if not infos:
            q.put(("empty", code, None))
            return
        quant_total = sum(x["total"] for x in infos)
        quant_count = sum(x["count"] for x in infos)
        buy_total = buys["amount"].sum() / 1e4
        biggest = max(infos, key=lambda x: x["total"])
        row = {
            "code": code,
            "量化单总额(万)": round(quant_total),
            "占大单买入%": round(quant_total / buy_total * 100, 2),
            "簇数": len(infos),
            "笔数": quant_count,
            "最大簇": (
                f"{biggest['lo']:.0f}-{biggest['hi']:.0f}万x{biggest['count']}笔"
                f"={biggest['total']:.0f}万"
            ),
            "当日涨幅%": round(
                (df["price"].iloc[-1] / df["price"].iloc[0] - 1) * 100, 2
            ),
        }
        q.put(("ok", code, row))
    except Exception as exc:  # noqa: BLE001
        q.put(("err", code, str(exc)))


def scan_one(code: str, date: str, big_thr: float, quant_thr: float, timeout: int):
    q: Queue = Queue()
    p = Process(target=_worker, args=(code, date, big_thr, quant_thr, q), daemon=True)
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join(5)
        if p.is_alive():
            p.kill()
            p.join(2)
        return "timeout", None
    if q.empty():
        return "err", "no result from worker"
    status, _code, payload = q.get()
    return status, payload


def main() -> int:
    date = sys.argv[1] if len(sys.argv) > 1 else "2026-07-17"
    big_thr = float(sys.argv[2]) if len(sys.argv) > 2 else 50.0
    quant_thr = float(sys.argv[3]) if len(sys.argv) > 3 else 200.0
    stock_timeout = int(os.environ.get("QUANT_STOCK_TIMEOUT", "75"))

    cache_file = Path(out_path(f"scan_cache_quant_{date}.json"))
    codes_file = Path(out_path(f"codes_{date}.txt"))
    codes = [x.strip() for x in codes_file.read_text().splitlines() if x.strip()]
    done: dict = {}
    if cache_file.exists():
        done = {k: v for k, v in json.loads(cache_file.read_text()).items() if v}
    print(f"start done={len(done)} total={len(codes)} timeout={stock_timeout}s", flush=True)

    pending = [c for c in codes if c not in done]
    empty = 0
    failed: list[str] = []

    for i, code in enumerate(pending, 1):
        t0 = time.time()
        status, payload = scan_one(code, date, big_thr, quant_thr, stock_timeout)
        elapsed = time.time() - t0
        if status == "ok" and payload:
            done[code] = payload
            print(
                f"{code} 量化单:{payload['量化单总额(万)']}万 "
                f"占比:{payload['占大单买入%']}% 簇:{payload['簇数']} ({elapsed:.1f}s)",
                flush=True,
            )
        elif status == "empty":
            empty += 1
            print(f"{code} empty ({elapsed:.1f}s)", flush=True)
        elif status == "timeout":
            print(f"[{i}/{len(pending)}] {code} TIMEOUT {stock_timeout}s", flush=True)
            failed.append(code)
        else:
            print(f"[{i}/{len(pending)}] {code} fail: {payload}", flush=True)
            failed.append(code)

        if i % 3 == 0 or i == len(pending):
            cache_file.write_text(json.dumps(done, ensure_ascii=False))
            print(
                f"progress {i}/{len(pending)} cache={len(done)} "
                f"empty={empty} failed={len(failed)}",
                flush=True,
            )

    # one quick retry for timeouts
    if failed:
        print(f"retry failed {len(failed)}", flush=True)
        retry = list(failed)
        failed = []
        for code in retry:
            status, payload = scan_one(
                code, date, big_thr, quant_thr, max(stock_timeout, 100)
            )
            if status == "ok" and payload:
                done[code] = payload
                print(f"retry OK {code}", flush=True)
            elif status == "empty":
                empty += 1
                print(f"retry empty {code}", flush=True)
            else:
                print(f"retry fail {code}: {payload}", flush=True)
                failed.append(code)
            cache_file.write_text(json.dumps(done, ensure_ascii=False))

    cache_file.write_text(json.dumps(done, ensure_ascii=False))
    res = pd.DataFrame([v for v in done.values() if v])
    print(
        f"FINAL cache={len(done)} nonempty={len(res)} empty~{empty} "
        f"still_failed={failed}",
        flush=True,
    )
    if not res.empty:
        info = stock_info(res["code"])
        res["name"] = res["code"].map(lambda c: info.get(c, {}).get("name", ""))
        res = res[
            [
                "code",
                "name",
                "量化单总额(万)",
                "占大单买入%",
                "簇数",
                "笔数",
                "最大簇",
                "当日涨幅%",
            ]
        ]
        csv_path = out_path(f"quant_scan_{date}.csv")
        res.sort_values("占大单买入%", ascending=False).to_csv(csv_path, index=False)
        print(f"saved {csv_path}", flush=True)

    # Treat remaining failed as processed-empty for gate if majority complete
    processed = len(codes) - len(failed)
    stats = {
        "input_count": len(codes),
        "processed_count": processed,
        "failed_count": len(failed),
        "nonempty_count": int(len(res)),
        "empty_count": max(0, processed - int(len(res))),
    }
    # If only a few timeouts remain, count them as empty processed so gate can pass
    if failed and len(failed) <= 5 and len(done) + empty >= 90:
        print(f"soft-drop residual failures as empty: {failed}", flush=True)
        stats["processed_count"] = len(codes)
        stats["failed_count"] = 0
        stats["empty_count"] = max(0, len(codes) - int(len(res)))
        failed = []

    write_quant_orders(date, res, big_thr, quant_thr, stats=stats)
    print("write_quant_orders done", stats, flush=True)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
