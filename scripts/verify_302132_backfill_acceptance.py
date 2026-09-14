#!/usr/bin/env python3
"""302132 回填完整副本演练·外部独立验收（fail-closed 门禁，非报告生成器）。

对象角色（两种用法同一语义）：
- `--production`：**不可变基线**库。演练复验 = 未动的真生产；生产执行后验收 =
  换库前备份文件（路径与 sha 见执行收据 backup 字段）。
- `--clone`：**换库后结果**库。演练 = 演练产物库；生产执行后 = canonical 生产库
  （收据按 `<clone>.repair-backfill-execution.<run_id>.json` 派生）。
- `--expected-production-sha256`：基线 sha（生产执行后 = 换库前生产 sha =
  执行收据 backup.backup_sha256），首尾各核一次（TOCTOU 闭环）。

实际执行的检查（文档只声称实现了的）：

预检（DuckDB connect/ATTACH 之前）：
- production / clone / parquet 均为常规文件且非符号链接；
- `os.path.samefile(production, clone)` 为假——覆盖同路径、符号链接、硬链接
  三种别名；无法判定（文件不存在等）按失败处理；不通过则跳过全部数据检查；
- production 基线 sha 开头核一次（结尾再核一次）。

收据（apply/verify 两份执行收据 + 其指向的独立子报告）：
- 完整 schema：kind/run_id/code_revision(40hex)/code_dirty==False/interpreter/
  trade_date/parent{swapped==True,rc==0,run_id一致}/backup{path,64hex sha}/
  spec{code,name,window_start,window_end,main_fill_end,shell_date,spec_version
  (非空、302132-backfill- 前缀),parquet_sha256(64hex),gap_parallel/gap_parquet
  (非空 list),pinned_technical_0911,pinned_windows_0911,expected_window_counts,
  expected_technical_count}/child_report{kind,spec_version,parquet_sha256,mode,
  run_id,code_revision,code_dirty}——缺字段/类型错/空值逐项记 check False，
  不抛异常逃逸，不缺项跳过；
- 身份：父=子 revision == --expected-revision、dirty==False、run_id 与命令行
  一致、apply/verify 模式各一、父=子 spec_version 一致且非空；
- 独立子报告文件：存在、可解析、与父收据嵌入 child_report 深比较相等；
- 冻结输入身份：spec.parquet_sha256 == child_report.parquet_sha256 ==
  sha256(--parquet 实际文件)；
- 备份身份：备份文件存在且其 sha256 == 收据记录值；apply 收据的备份 sha 还
  必须 == --expected-production-sha256（备份=基线绑定）；
- --expected-old-receipt 路径=sha256（可重复）：旧收据逐份存在且哈希不变
  （不传则不声称检查旧收据）。

数据合同（clone vs 基线双向对照 + 独立 oracle，预检不过不执行）：
- 他股 fact_stock_daily 全列双向零差；目标股窗外无行；保留 10 行全列
  （含 updated_at）逐字节相等；54 键集分母全字段 oracle；两派生表保护切片
  全列（含 calculated_at）双向零差；window 黄金三元组；technical 精确日期集；
  目标日 technical/window 钉值；fact_market_daily 双向零差。

用法（生产执行后）：
python3 scripts/verify_302132_backfill_acceptance.py \
  --production <换库前备份.duckdb> --clone <canonical 生产库> \
  --parquet <冻结 parquet> --run-apply <run_id> --run-verify <run_id> \
  --expected-revision <合入修订 40hex> \
  --expected-production-sha256 <换库前生产 sha=收据 backup sha> \
  [--expected-old-receipt <路径>=<sha256>]... --output <新验收 JSON 路径>
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
    ap.add_argument("--production", required=True, help="不可变基线库")
    ap.add_argument("--clone", required=True, help="换库后结果库")
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--run-apply", required=True)
    ap.add_argument("--run-verify", required=True)
    ap.add_argument("--expected-revision", required=True)
    ap.add_argument("--expected-production-sha256", required=True)
    ap.add_argument("--expected-old-receipt", action="append", default=[],
                    metavar="PATH=SHA256")
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

    # ── 预检：常规文件 + samefile 别名（含硬链接）────────────────────
    check("inputs_regular_files",
          all(p.is_file() and not p.is_symlink() for p in (prod, clone, pq)),
          [str(p) for p in (prod, clone, pq)
           if not (p.is_file() and not p.is_symlink())])
    try:
        same = os.path.samefile(prod, clone)
    except OSError as exc:
        same, same_err = None, f"{type(exc).__name__}: {exc}"
    else:
        same_err = ""
    check("clone_is_not_production_alias", same is False,
          same_err or {"production": os.path.realpath(prod),
                       "clone": os.path.realpath(clone)})
    preflight_ok = all(c["ok"] for c in checks)

    check("production_sha256_before",
          _sha256(prod) == args.expected_production_sha256,
          args.expected_production_sha256[:16])

    # ── 收据：读取 + 完整 schema + 身份 ──────────────────────────────
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

    def _schema(tag: str, r: dict, want_run: str, exp_rev: str) -> bool:
        bad: list[str] = []

        def req(cond: bool, field: str) -> None:
            if not cond:
                bad.append(field)

        req(r.get("kind") == KIND, "kind")
        req(isinstance(r.get("run_id"), str) and r["run_id"] == want_run, "run_id")
        req(isinstance(r.get("code_revision"), str)
            and r["code_revision"] == exp_rev, "code_revision")
        req(r.get("code_dirty") is False, "code_dirty")
        req(isinstance(r.get("interpreter"), str) and bool(r["interpreter"]),
            "interpreter")
        req(isinstance(r.get("trade_date"), str) and bool(r["trade_date"]),
            "trade_date")
        par = r.get("parent")
        req(isinstance(par, dict), "parent")
        if isinstance(par, dict):
            req(par.get("swapped") is True, "parent.swapped")
            req(par.get("rc") == 0, "parent.rc")
            req(par.get("run_id") == r.get("run_id"), "parent.run_id")
        b = r.get("backup")
        req(isinstance(b, dict), "backup")
        if isinstance(b, dict):
            req(isinstance(b.get("backup_path"), str) and bool(b["backup_path"]),
                "backup.backup_path")
            req(isinstance(b.get("backup_sha256"), str)
                and len(b["backup_sha256"]) == 64, "backup.backup_sha256")
        spec = r.get("spec")
        req(isinstance(spec, dict), "spec")
        if isinstance(spec, dict):
            for k in ("code", "name", "window_start", "window_end",
                      "main_fill_end", "shell_date", "spec_version",
                      "parquet_sha256"):
                req(isinstance(spec.get(k), str) and bool(spec[k]), f"spec.{k}")
            for k in ("gap_parallel", "gap_parquet"):
                req(isinstance(spec.get(k), list) and bool(spec[k]), f"spec.{k}")
            req(isinstance(spec.get("pinned_technical_0911"), dict),
                "spec.pinned_technical_0911")
            req(isinstance(spec.get("pinned_windows_0911"), list)
                and bool(spec["pinned_windows_0911"]),
                "spec.pinned_windows_0911")
            req(isinstance(spec.get("expected_window_counts"), dict),
                "spec.expected_window_counts")
            req(isinstance(spec.get("expected_technical_count"), int),
                "spec.expected_technical_count")
            if isinstance(spec.get("spec_version"), str):
                req(spec["spec_version"].startswith("302132-backfill-"),
                    "spec.spec_version:前缀")
            if isinstance(spec.get("parquet_sha256"), str):
                req(len(spec["parquet_sha256"]) == 64, "spec.parquet_sha256:长度")
        ch = r.get("child_report")
        req(isinstance(ch, dict), "child_report")
        if isinstance(ch, dict):
            req(ch.get("kind") == KIND, "child.kind")
            req(isinstance(ch.get("spec_version"), str)
                and bool(ch["spec_version"]), "child.spec_version")
            req(isinstance(spec, dict)
                and ch.get("spec_version") == spec.get("spec_version")
                and bool(ch.get("spec_version")), "child.spec_version==parent")
            req(isinstance(ch.get("parquet_sha256"), str)
                and len(ch["parquet_sha256"]) == 64, "child.parquet_sha256")
            req(isinstance(spec, dict)
                and ch.get("parquet_sha256") == spec.get("parquet_sha256"),
                "child.parquet_sha256==parent")
            req(ch.get("mode") == tag, "child.mode")
            req(ch.get("run_id") == r.get("run_id"), "child.run_id")
            req(ch.get("code_revision") == r.get("code_revision"),
                "child.code_revision")
            req(ch.get("code_dirty") is False, "child.code_dirty")
            req(isinstance(ch.get("protected_slices"), dict),
                "child.protected_slices")
        crp = r.get("child_report_path")
        req(isinstance(crp, str) and bool(crp), "child_report_path")
        check(f"receipt_{tag}_schema", not bad, bad[:8])
        return not bad

    schema_ok = True
    for tag, r in receipts.items():
        want = args.run_apply if tag == "apply" else args.run_verify
        schema_ok &= _schema(tag, r, want, args.expected_revision)

    # 独立子报告文件：存在 + 可解析 + 与父收据嵌入子报告深比较相等
    for tag, r in receipts.items():
        crp = r.get("child_report_path")
        if not (isinstance(crp, str) and crp):
            continue
        try:
            ext = json.loads(Path(crp).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            check(f"receipt_{tag}_child_report_file", False,
                  f"{type(exc).__name__}: {exc}")
            continue
        check(f"receipt_{tag}_child_report_file",
              isinstance(ext, dict) and ext == r.get("child_report"),
              "与父收据嵌入子报告深比较")

    # 备份身份：文件存在 + sha 与收据一致；apply 备份还须 == 基线 sha
    for tag, r in receipts.items():
        b = r.get("backup")
        if not isinstance(b, dict):
            continue
        bp = Path(str(b.get("backup_path", "")))
        want = b.get("backup_sha256")
        try:
            ok = (isinstance(want, str) and bp.is_file()
                  and _sha256(bp) == want)
            check(f"backup_{tag}_identity", ok, str(bp)[-48:])
        except OSError as exc:
            check(f"backup_{tag}_identity", False, str(exc))
    if isinstance(receipts.get("apply", {}).get("backup"), dict):
        check("backup_apply_matches_baseline",
              receipts["apply"]["backup"].get("backup_sha256")
              == args.expected_production_sha256,
              "apply 备份 sha == 基线 sha（换库前生产身份）")

    # 冻结输入身份：spec == child == 实际文件（三向）
    spec = receipts.get("apply", {}).get("spec")
    ch_apply = receipts.get("apply", {}).get("child_report")
    if (isinstance(spec, dict) and isinstance(spec.get("parquet_sha256"), str)
            and len(spec["parquet_sha256"]) == 64
            and isinstance(ch_apply, dict)
            and ch_apply.get("parquet_sha256") == spec["parquet_sha256"]):
        actual_pq = _sha256(pq)
        check("parquet_identity", actual_pq == spec["parquet_sha256"],
              {"expected": spec["parquet_sha256"][:16],
               "actual": actual_pq[:16]})
    else:
        check("parquet_identity", False,
              "收据 spec/child 缺 parquet_sha256 或父=子不一致（缺证据不发绿）")

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

    # ── 数据合同（预检/收据 schema 不过不执行，避免假阳性）────────────
    spec_ok = (preflight_ok and schema_ok and isinstance(spec, dict)
               and all(isinstance(spec.get(k), str) and spec[k] for k in (
                   "window_start", "window_end", "name"))
               and isinstance(spec.get("gap_parallel"), list)
               and isinstance(spec.get("gap_parquet"), list)
               and isinstance(spec.get("shell_date"), str))
    if spec_ok:
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
                f"EXCEPT ALL SELECT {sel} FROM prod.{table} {where})"
            ).fetchone()[0]
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
    else:
        check("data_checks_executed", False,
              "预检或收据 schema 未过，数据检查跳过（不发绿）")

    # ── 尾核：验收结束时基线 sha 仍等于期望（TOCTOU 闭环）─────────────
    check("production_sha256_after",
          _sha256(prod) == args.expected_production_sha256,
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
