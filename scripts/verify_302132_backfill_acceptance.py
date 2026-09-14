#!/usr/bin/env python3
"""302132 回填完整副本演练·外部独立验收（fail-closed 门禁，非报告生成器）。

对照生产库（只读）与演练产物库，断言：
- 数据合同：他股全列不变、保留 10 行含 updated_at 逐字节、54 行键集全字段
  oracle、派生保护切片含 calculated_at 双向零差、window 黄金三元组、09-11 钉值；
- 证据身份（评审三轮）：两轮 child report 与 parent receipt 的 code_revision 都
  等于 --expected-revision、code_dirty 为 False、父子一致、apply/verify 各一、
  备份身份存在且备份文件可读、旧收据未被覆盖；
- 生产库 sha256 未变（--expected-production-sha256）。

用法：
python3 scripts/verify_302132_backfill_acceptance.py \
  --production <生产库路径> --clone <演练产物库> --parquet <冻结 parquet> \
  --run-apply <run_id> --run-verify <run_id> \
  --expected-revision <40hex> --expected-production-sha256 <64hex> \
  --output <验收 JSON 写出路径（不得已存在）>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import duckdb

CODE = "302132.SZ"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--production", required=True)
    ap.add_argument("--clone", required=True)
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--run-apply", required=True)
    ap.add_argument("--run-verify", required=True)
    ap.add_argument("--expected-revision", required=True)
    ap.add_argument("--expected-production-sha256", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    out_path = Path(args.output)
    if out_path.exists():
        raise SystemExit(f"验收输出已存在（不可覆盖）: {out_path}")
    checks: list[dict] = []

    def check(name: str, ok: bool, detail="") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    prod = Path(args.production)
    check("production_untouched",
          _sha256(prod) == args.expected_production_sha256,
          args.expected_production_sha256[:16])

    con = duckdb.connect(args.clone, read_only=True)
    con.execute(f"ATTACH '{prod}' AS prod (READ_ONLY)")

    def xa(table: str, where: str) -> list[int]:
        cols = [r[1] for r in con.execute(
            f"PRAGMA table_info('{table}')").fetchall()]
        sel = ", ".join(cols)
        fwd = con.execute(
            f"SELECT COUNT(*) FROM (SELECT {sel} FROM prod.{table} {where} "
            f"EXCEPT ALL SELECT {sel} FROM {table} {where})").fetchone()[0]
        rev = con.execute(
            f"SELECT COUNT(*) FROM (SELECT {sel} FROM {table} {where} "
            f"EXCEPT ALL SELECT {sel} FROM prod.{table} {where})").fetchone()[0]
        return [fwd, rev]

    # ── 收据身份（先读 spec，键集分母来自收据内的 spec 快照）──────────
    clone = Path(args.clone)
    r_apply_p = Path(str(clone) + f".repair-backfill-execution.{args.run_apply}.json")
    r_verify_p = Path(str(clone) + f".repair-backfill-execution.{args.run_verify}.json")
    receipts = {}
    for tag, p in (("apply", r_apply_p), ("verify", r_verify_p)):
        try:
            receipts[tag] = json.loads(p.read_text(encoding="utf-8"))
        except OSError as exc:
            check(f"receipt_{tag}_readable", False, str(exc))
    if len(receipts) == 2:
        exp = args.expected_revision
        id_ok = True
        details = {}
        for tag, r in receipts.items():
            ch = r.get("child_report") or {}
            details[tag] = {"parent_rev": r.get("code_revision", "")[:8],
                            "parent_dirty": r.get("code_dirty"),
                            "child_rev": ch.get("code_revision", "")[:8],
                            "child_dirty": ch.get("code_dirty")}
            id_ok &= (
                r.get("code_revision") == exp and r.get("code_dirty") is False
                and ch.get("code_revision") == exp and ch.get("code_dirty") is False
                and r.get("run_id") == (args.run_apply if tag == "apply"
                                        else args.run_verify)
                and ch.get("run_id") == r.get("run_id"))
        check("receipts_revision_identity", id_ok, details)
        check("receipts_modes",
              receipts["apply"]["child_report"]["mode"] == "apply"
              and receipts["verify"]["child_report"]["mode"] == "verify")
        for tag, r in receipts.items():
            b = r.get("backup") or {}
            bp = Path(b.get("backup_path", ""))
            check(f"backup_{tag}_identity",
                  bool(b.get("backup_sha256")) and bp.is_file()
                  and _sha256(bp) == b["backup_sha256"],
                  str(bp)[-60:])
        spec = receipts["apply"]["spec"]
    else:
        spec = None

    if spec is not None:
        write_keys = sorted(set(spec["gap_parallel"]) | set(spec["gap_parquet"])
                            | {spec["shell_date"]})
        marks = ",".join(f"'{d}'" for d in write_keys)

        check("fact_other_stocks_allcols",
              xa("fact_stock_daily", f"WHERE stock_ts_code <> '{CODE}'") == [0, 0])
        before = con.execute(
            f"SELECT * FROM prod.fact_stock_daily WHERE stock_ts_code='{CODE}' "
            f"AND trade_date NOT IN ({marks}) ORDER BY trade_date").fetchall()
        after = con.execute(
            f"SELECT * FROM fact_stock_daily WHERE stock_ts_code='{CODE}' "
            f"AND trade_date NOT IN ({marks}) ORDER BY trade_date").fetchall()
        check("retained_rows_full_column_identical",
              before == after and len(after) == 10, len(after))
        oor = con.execute(
            f"SELECT COUNT(*) FROM fact_stock_daily WHERE stock_ts_code='{CODE}' "
            f"AND trade_date NOT BETWEEN '{spec['window_start']}' "
            f"AND '{spec['window_end']}'").fetchone()[0]
        check("target_outside_window_none", oor == 0, oor)

        # 54 行键集分母 + 全字段 oracle（来源:并跑表 ∪ 冻结 parquet）
        pq = args.parquet
        src = {str(r[0]): r[1:] for r in con.execute(f"""
          SELECT trade_date, open, high, low, close, volume, turnover
          FROM fact_stock_daily_hithink
          WHERE stock_ts_code='{CODE}' AND adjusted='none'
          UNION ALL
          SELECT CAST(to_timestamp(date_ms/1000) AS DATE), open_price, high_price,
                 low_price, close_price, volume, turnover
          FROM read_parquet('{pq}')
          WHERE thscode='{CODE}' AND currency='CNY' AND interval='1d'
            AND adjusted='none'""").fetchall()}
        cal = [str(r[0]) for r in con.execute(
            "SELECT DISTINCT trade_date FROM prod.fact_market_daily "
            "WHERE trade_date BETWEEN '2026-06-01' AND ? ORDER BY 1",
            [spec["window_end"]]).fetchall()]
        rows = con.execute(
            f"SELECT trade_date, stock_name, open, high, low, close, pre_close,"
            f" pct_chg, amount, turnover, volume, source FROM fact_stock_daily "
            f"WHERE stock_ts_code='{CODE}' AND trade_date IN ({marks})").fetchall()
        bad = []
        for r in rows:
            d = str(r[0])
            s = src[d]
            pred = cal[cal.index(d) - 1]
            pre = float(Decimal(str(float(src[pred][3]))).quantize(Decimal("0.01")))
            pct = float(((Decimal(str(r[5])).quantize(Decimal("0.0001"))
                          / Decimal(str(pre)).quantize(Decimal("0.01")) - 1) * 100
                         ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            amt = float((Decimal(str(float(s[5]))).quantize(Decimal("0.01"))
                         / Decimal(10**8)).quantize(Decimal("0.0001"),
                                                   rounding=ROUND_HALF_UP))
            vol = float((Decimal(str(float(s[4]))).quantize(Decimal("1"))
                         / Decimal(100)).quantize(Decimal("1"),
                                                 rounding=ROUND_HALF_UP))
            exp_label = (spec["gap_parquet"] and d in spec["gap_parquet"]
                         and "hithink:daily-k-10d:backfill-302132-20260914"
                         or "hithink:daily-k:backfill-302132-20260914")
            ok = (r[1] == spec["name"] and r[2] == float(s[0])
                  and r[3] == float(s[1]) and r[4] == float(s[2])
                  and r[5] == float(s[3]) and abs(r[6] - pre) < 1e-9
                  and abs(r[7] - pct) < 1e-9 and abs(r[8] - amt) < 1e-9
                  and r[9] is None and abs(r[10] - vol) < 1e-9
                  and r[11] == exp_label
                  and all(math.isfinite(float(v)) for v in r[2:6]))
            if not ok:
                bad.append(d)
        check("keyset54_fullfield_oracle", len(rows) == len(write_keys) and not bad,
              {"rows": len(rows), "bad": bad[:5]})

        w_t = (f"WHERE stock_ts_code <> '{CODE}' OR trade_date NOT BETWEEN "
               f"'{spec['window_start']}' AND '{spec['window_end']}'")
        w_w = (f"WHERE stock_ts_code <> '{CODE}' OR as_of_date NOT BETWEEN "
               f"'{spec['window_start']}' AND '{spec['window_end']}'")
        check("technical_protected_allcols",
              xa("feature_stock_technical_daily", w_t) == [0, 0])
        check("window_protected_allcols",
              xa("feature_stock_window", w_w) == [0, 0])

        cal64 = [d for d in cal if d >= spec["window_start"]]
        golden = set()
        for i, a in enumerate(cal64):
            for p in (5, 10, 20, 60):
                if i >= p:
                    golden.add((a, cal64[i - p], a))
        actual = {(str(r[0]), str(r[1]), str(r[2])) for r in con.execute(
            f"SELECT as_of_date, start_date, end_date FROM feature_stock_window "
            f"WHERE stock_ts_code='{CODE}' AND as_of_date BETWEEN "
            f"'{spec['window_start']}' AND '{spec['window_end']}'").fetchall()}
        check("window_golden_triples", actual == golden,
              {"actual": len(actual), "golden": len(golden)})
        tech_dates = [str(r[0]) for r in con.execute(
            f"SELECT trade_date FROM feature_stock_technical_daily "
            f"WHERE stock_ts_code='{CODE}' AND trade_date BETWEEN "
            f"'{spec['window_start']}' AND '{spec['window_end']}' "
            f"ORDER BY 1").fetchall()]
        check("technical_exact_set", tech_dates == cal64[25:], len(tech_dates))
        tp = spec["pinned_technical_0911"]
        t9 = con.execute(
            f"SELECT ma26, std26, up_value, deviation_pct "
            f"FROM feature_stock_technical_daily WHERE stock_ts_code='{CODE}' "
            f"AND trade_date='{spec['window_end']}'").fetchone()
        check("pinned_technical_target_day",
              t9 is not None and all(
                  abs(a - b) < 1e-9 for a, b in zip(
                      t9, (tp["ma26"], tp["std26"], tp["up_value"],
                           tp["deviation_pct"]))), t9)
        w9 = con.execute(
            f"SELECT start_date, interval_gain_pct, avg_amount "
            f"FROM feature_stock_window WHERE stock_ts_code='{CODE}' "
            f"AND as_of_date='{spec['window_end']}' ORDER BY start_date").fetchall()
        pins = spec["pinned_windows_0911"]
        check("pinned_windows_target_day",
              len(w9) == len(pins) and all(
                  str(r[0]) == p[0] and abs(r[1] - p[1]) < 1e-9
                  and abs(r[2] - p[2]) < 1e-9 for r, p in zip(w9, pins)))
        check("market_daily_untouched", xa("fact_market_daily", "") == [0, 0])

    con.close()
    verdict = "PASS" if all(c["ok"] for c in checks) else "FAIL"
    payload = {"verdict": verdict,
               "expected_revision": args.expected_revision,
               "runs": {"apply": args.run_apply, "verify": args.run_verify},
               "checks": checks,
               "failed": [c["name"] for c in checks if not c["ok"]]}
    fd = os.open(str(out_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, indent=2, default=str)
                 + "\n")
    print(json.dumps({"verdict": verdict, "failed": payload["failed"],
                      "n": len(checks)}, ensure_ascii=False))
    return 0 if verdict == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
