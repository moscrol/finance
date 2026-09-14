#!/usr/bin/env python3
"""302132 回填完整副本演练·外部独立验收（fail-closed 门禁，非报告生成器）。

实际执行的检查（文档只声称实现了的）：

预检：
- production / clone / parquet 均为常规文件，且 production 与 clone 不是同一
  文件或别名（realpath 相等即拒，数据检查跳过——同源假阳性路径封堵）；
- production sha256 在验收开始与结束各核一次，都必须等于
  --expected-production-sha256（TOCTOU 首尾闭环；验收只读、不持锁，写入方
  并发改动会被尾核抓住）；
- --parquet 实际文件 sha256 == 收据 spec.parquet_sha256（冻结输入身份绑定）。

收据（apply/verify。
- 结构正确；
- 父收据 kind/swapped==True/rc==0、子报告 kind；
- 父收据与子报告的 code_revision 均 == --expected-revision、code_dirty 为
  False、父=子一致、run_id 与命令行一致且父=子一致、apply/verify 模式正确；
- spec_version 父=子一致；
- child_report_path 存在且可读；
- 备份身份：备份文件存在且其 sha256 == 收据记录值；
- --expected-old-receipt path=sha256（可重复）：旧收据逐份存在且哈希不变
  （「旧收据未被覆盖」由此参数显式核验；不传则不声称检查）。

数据合同（clone vs production 双向对照 + 独立 oracle）：
- 他股 fact_stock_daily 全列双向零差；目标股窗外无行；保留 10 行全列
  （含 updated_at）逐字节相等；54 键集分母全字段 oracle（名称/OHLC/昨收/
  涨跌/额/量/turnover NULL/来源标签/有限性）；两派生表保护切片全列
  （含 calculated_at）双向零差；window 黄金三元组（市场历索引构造）；technical
  精确日期集；目标日 technical/window 钉值；fact_market_daily 双向零差。

用法：
python3 scripts/verify_302132_backfill_acceptance.py \
  --production <生产库> --clone <演练产物库> --parquet <冻结 parquet> \
  --run-apply <run_id> --run-verify <run_id> \
  --expected-revision <40hex> --expected-production-sha256 <64hex> \
  [--expected-old-receipt <路径>=<64hex>]... \
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
KIND = "repair-backfill-302132"


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
    ap.add_argument("--expected-old-receipt", action="append", default=[],
                    metavar="PATH=SHA256",
                    help="旧收据路径=入场时 sha256；逐份核验存在且未变（可重复）")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    out_path = Path(args.output)
    if out_path.exists():
        raise SystemExit(f"验收输出已存在（不可覆盖）: {out_path}")
    checks: list[dict] = []

    def check(name: str, ok: bool, detail="") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    prod, clone, pq = (Path(args.production), Path(args.clone),
                       Path(args.parquet))

    # ── 预检：常规文件 + production/clone 非同一文件或别名 ─────────────
    check("inputs_regular_files",
          all(p.is_file() and not p.is_symlink() for p in (prod, clone, pq)),
          [str(p) for p in (prod, clone, pq)
           if not (p.is_file() and not p.is_symlink())])
    same = os.path.realpath(prod) == os.path.realpath(clone)
    check("clone_is_not_production_alias", not same,
          {"production": os.path.realpath(prod), "clone": os.path.realpath(clone)})
    preflight_ok = all(c["ok"] for c in checks)

    check("production_sha256_before", _sha256(prod)
          == args.expected_production_sha256,
          args.expected_production_sha256[:16])

    # ── 收据读取（健壮：损坏/缺字段一律记 check False，不抛异常逃逸）───
    receipts: dict[str, dict] = {}

    def _read_receipt(tag: str, run_id: str) -> None:
        p = Path(str(clone) + f".repair-backfill-execution.{run_id}.json")
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            check(f"receipt_{tag}_readable", False, f"{type(exc).__name__}: {exc}")
            return
        if not isinstance(raw, dict):
            check(f"receipt_{tag}_readable", False, type(raw).__name__)
            return
        check(f"receipt_{tag}_readable", True)
        receipts[tag] = raw

    _read_receipt("apply", args.run_apply)
    _read_receipt("verify", args.run_verify)

    spec = None
    if len(receipts) == 2:
        exp = args.expected_revision
        id_detail, id_ok = {}, True
        for tag, r in receipts.items():
            ch = r.get("child_report")
            ch = ch if isinstance(ch, dict) else {}
            want_run = args.run_apply if tag == "apply" else args.run_verify
            parent = r.get("parent") if isinstance(r.get("parent"), dict) else {}
            ok = (
                r.get("kind") == KIND
                and parent.get("swapped") is True and parent.get("rc") == 0
                and r.get("code_revision") == exp and r.get("code_dirty") is False
                and r.get("run_id") == want_run
                and ch.get("kind") == KIND
                and ch.get("code_revision") == exp and ch.get("code_dirty") is False
                and ch.get("run_id") == r.get("run_id")
                and ch.get("mode") == tag
                and isinstance(r.get("spec"), dict)
                and r["spec"].get("spec_version") == ch.get("spec_version")
            )
            crp = r.get("child_report_path")
            crp_ok = bool(crp) and Path(str(crp)).is_file()
            id_detail[tag] = {"parent_rev": str(r.get("code_revision"))[:8],
                              "child_rev": str(ch.get("code_revision"))[:8],
                              "child_report_path_exists": crp_ok}
            id_ok &= ok and crp_ok
        check("receipts_identity", id_ok, id_detail)
        for tag, r in receipts.items():
            b = r.get("backup") if isinstance(r.get("backup"), dict) else {}
            bp = Path(str(b.get("backup_path", "")))
            try:
                ok = (bool(b.get("backup_sha256")) and bp.is_file()
                      and _sha256(bp) == b["backup_sha256"])
                check(f"backup_{tag}_identity", ok, str(bp)[-48:])
            except OSError as exc:
                check(f"backup_{tag}_identity", False, str(exc))
        if isinstance(receipts["apply"].get("spec"), dict):
            spec = receipts["apply"]["spec"]

    # ── 冻结输入身份：parquet 实际文件 == spec 记录 ────────────────────
    if spec is not None and spec.get("parquet_sha256"):
        actual_pq = _sha256(pq)
        check("parquet_identity", actual_pq == spec["parquet_sha256"],
              {"expected": spec["parquet_sha256"][:16], "actual": actual_pq[:16]})

    # ── 旧收据保留（显式参数核验；未传则不声称检查）────────────────────
    for item in args.expected_old_receipt:
        if "=" not in item:
            check("old_receipt_arg_format", False, item)
            continue
        path_s, want_sha = item.rsplit("=", 1)
        op = Path(path_s)
        if not op.is_file():
            check(f"old_receipt:{op.name}", False, "不存在")
            continue
        check(f"old_receipt:{op.name}", _sha256(op) == want_sha, want_sha[:12])

    # ── 数据合同（预检同源/非常规文件时跳过，避免假阳性）─────────────
    if preflight_ok and spec is not None:
        con = duckdb.connect(str(clone), read_only=True)
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

        d0, d1 = spec["window_start"], spec["window_end"]
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
            f"AND trade_date NOT BETWEEN '{d0}' AND '{d1}'").fetchone()[0]
        check("target_outside_window_none", oor == 0, oor)

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
            [d1]).fetchall()]
        rows = con.execute(
            f"SELECT trade_date, stock_name, open, high, low, close, pre_close,"
            f" pct_chg, amount, turnover, volume, source FROM fact_stock_daily "
            f"WHERE stock_ts_code='{CODE}' AND trade_date IN ({marks})").fetchall()
        bad = []
        for r in rows:
            d = str(r[0])
            s = src[d]
            pred = cal[cal.index(d) - 1]
            pre = float(Decimal(str(float(src[pred][3]))).quantize(
                Decimal("0.01")))
            pct = float(((Decimal(str(r[5])).quantize(Decimal("0.0001"))
                          / Decimal(str(pre)).quantize(Decimal("0.01")) - 1) * 100
                         ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            amt = float((Decimal(str(float(s[5]))).quantize(Decimal("0.01"))
                         / Decimal(10**8)).quantize(Decimal("0.0001"),
                                                   rounding=ROUND_HALF_UP))
            vol = float((Decimal(str(float(s[4]))).quantize(Decimal("1"))
                         / Decimal(100)).quantize(Decimal("1"),
                                                 rounding=ROUND_HALF_UP))
            exp_label = ("hithink:daily-k-10d:backfill-302132-20260914"
                         if d in spec["gap_parquet"]
                         else "hithink:daily-k:backfill-302132-20260914")
            ok = (r[1] == spec["name"] and r[2] == float(s[0])
                  and r[3] == float(s[1]) and r[4] == float(s[2])
                  and r[5] == float(s[3]) and abs(r[6] - pre) < 1e-9
                  and abs(r[7] - pct) < 1e-9 and abs(r[8] - amt) < 1e-9
                  and r[9] is None and abs(r[10] - vol) < 1e-9
                  and r[11] == exp_label
                  and all(math.isfinite(float(v)) for v in r[2:6]))
            if not ok:
                bad.append(d)
        check("keyset54_fullfield_oracle",
              len(rows) == len(write_keys) and not bad,
              {"rows": len(rows), "bad": bad[:5]})

        w_t = (f"WHERE stock_ts_code <> '{CODE}' OR trade_date NOT BETWEEN "
               f"'{d0}' AND '{d1}'")
        w_w = (f"WHERE stock_ts_code <> '{CODE}' OR as_of_date NOT BETWEEN "
               f"'{d0}' AND '{d1}'")
        check("technical_protected_allcols",
              xa("feature_stock_technical_daily", w_t) == [0, 0])
        check("window_protected_allcols",
              xa("feature_stock_window", w_w) == [0, 0])
        cal64 = [d for d in cal if d >= d0]
        golden = set()
        for i, a in enumerate(cal64):
            for p_ in (5, 10, 20, 60):
                if i >= p_:
                    golden.add((a, cal64[i - p_], a))
        actual = {(str(r[0]), str(r[1]), str(r[2])) for r in con.execute(
            f"SELECT as_of_date, start_date, end_date FROM feature_stock_window "
            f"WHERE stock_ts_code='{CODE}' AND as_of_date BETWEEN '{d0}' "
            f"AND '{d1}'").fetchall()}
        check("window_golden_triples", actual == golden,
              {"actual": len(actual), "golden": len(golden)})
        tech_dates = [str(r[0]) for r in con.execute(
            f"SELECT trade_date FROM feature_stock_technical_daily "
            f"WHERE stock_ts_code='{CODE}' AND trade_date BETWEEN '{d0}' "
            f"AND '{d1}' ORDER BY 1").fetchall()]
        check("technical_exact_set", tech_dates == cal64[25:], len(tech_dates))
        tp = spec["pinned_technical_0911"]
        t9 = con.execute(
            f"SELECT ma26, std26, up_value, deviation_pct "
            f"FROM feature_stock_technical_daily WHERE stock_ts_code='{CODE}' "
            f"AND trade_date='{d1}'").fetchone()
        check("pinned_technical_target_day",
              t9 is not None and all(
                  abs(a - b) < 1e-9 for a, b in zip(
                      t9, (tp["ma26"], tp["std26"], tp["up_value"],
                           tp["deviation_pct"]))), t9)
        w9 = con.execute(
            f"SELECT start_date, interval_gain_pct, avg_amount "
            f"FROM feature_stock_window WHERE stock_ts_code='{CODE}' "
            f"AND as_of_date='{d1}' ORDER BY start_date").fetchall()
        pins = spec["pinned_windows_0911"]
        check("pinned_windows_target_day",
              len(w9) == len(pins) and all(
                  str(r[0]) == p[0] and abs(r[1] - p[1]) < 1e-9
                  and abs(r[2] - p[2]) < 1e-9 for r, p in zip(w9, pins)))
        check("market_daily_untouched", xa("fact_market_daily", "") == [0, 0])
        con.close()

    # ── 尾核：验收结束时生产 sha256 仍等于期望（TOCTOU 闭环）──────────
    check("production_sha256_after", _sha256(prod)
          == args.expected_production_sha256,
          args.expected_production_sha256[:16])

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
