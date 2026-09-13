#!/usr/bin/env python3
"""hithink 修复对账严格门禁 v3（十二轮审查修补版，fail-closed、证据随提交走）。

针对 2026-09-11 fact_stock_daily 的 hithink 重建修复，在**生产库隔离克隆**上
复跑完整修复链（互斥→基线→子进程→换名前备份→原子换名），并对结果做
逐值/逐行核对。任一检查失败即 verdict=FAIL、exit 1；生产库全程只读。

与 v2 的差异（十二轮审查要求）：

- 脚本纳入候选 Git 提交（本文件），收据记录 ``--expect-revision`` 精确匹配
  的 HEAD、``git status --porcelain`` 为空、本脚本自哈希——证据与代码不再脱钩；
- 冻结输入真冻结：parquet 先复制进本轮 run 目录，对副本算 hash，
  CLI 只读副本；
- 顶层异常保护：任何异常都写结构化 FAIL 报告（run 目录创建失败则写
  兜底 FAIL 文件）；
- run 目录用 ``tempfile.mkdtemp`` 原子唯一创建；
- ops 收据绑定收紧：kind/ok/plan/trade_date/时间窗全部校验，备份 receipt
  的 run_id 必须等于该 ops 行；
- 非目标日期用 EXCEPT ALL（含重复行 multiplicity）。

用法（候选树内）::

    .venv-workbench/bin/python scripts/reconcile_hithink_gate.py \
        --expect-revision <候选代码提交 sha>

跑完把 run 目录下的 gate-report.json 复制进仓作证据并提交；收据绑定的
revision 是其父提交（先跑后提交收据，见候选交接文档）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

import duckdb

TREE = Path(__file__).resolve().parents[1]
TD_DEFAULT = "2026-09-11"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stat_id(path: Path) -> tuple:
    st = path.stat()
    return (st.st_ino, st.st_mtime_ns, st.st_size)


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=TREE, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# 门禁主流程
# ---------------------------------------------------------------------------

checks: list[dict] = []
inputs: dict = {}
RUN: Path | None = None
OUT_BASE: Path | None = None


def check(name: str, ok: bool, detail) -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def finalize(cli_rc: int) -> None:
    verdict = "PASS" if cli_rc == 0 and checks and all(c["ok"] for c in checks) else "FAIL"
    report = {
        "gate": Path(__file__).name + " v3",
        "verdict": verdict,
        "run_dir": str(RUN) if RUN else None,
        "trade_date": inputs.get("trade_date"),
        "inputs": inputs,
        "checks": checks,
        "failed": [c["name"] for c in checks if not c["ok"]],
    }
    if RUN is not None:
        out = RUN / "gate-report.json"
    else:
        # run 目录都没建起来：兜底 FAIL 文件，仍然留结构化证据
        base = OUT_BASE if OUT_BASE is not None else Path.cwd()
        out = base / f"gate-FAIL-{datetime.now():%Y%m%dT%H%M%S}-{os.getpid()}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
                   encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    sys.exit(0 if verdict == "PASS" else 1)


def run_gate() -> None:
    global RUN, OUT_BASE
    ap = argparse.ArgumentParser(description="hithink 修复对账严格门禁（隔离库）")
    ap.add_argument("--expect-revision", required=True,
                    help="候选代码提交 sha；HEAD 必须精确等于它且工作树干净")
    ap.add_argument("--trade-date", default=TD_DEFAULT)
    ap.add_argument("--parquet", default=os.path.expanduser(
        "~/.finance-runtime/db-repair/hithink-20260911/daily-k-10d.parquet"))
    ap.add_argument("--source-db", default=None,
                    help="被克隆的参照生产库；缺省 = git common-dir 主树 db/market_feature_store.duckdb")
    ap.add_argument("--output-base", default=os.path.expanduser(
        "~/.finance-runtime/reconcile-gate"), help="run 目录的父目录（仓外，不脏树）")
    args = ap.parse_args()
    td = args.trade_date

    OUT_BASE = Path(args.output_base)
    OUT_BASE.mkdir(parents=True, exist_ok=True)

    # ── 0. 代码版本绑定（先于一切副作用；FAIL 报告也落在仓外 OUT_BASE，
    #       绝不写进候选树自身——否则失败件会污染下一轮的 tree_clean）──
    head = git("rev-parse", "HEAD").stdout.strip()
    check("tree_revision_exact", head == args.expect_revision,
          {"head": head, "expected": args.expect_revision})
    porcelain = git("status", "--porcelain").stdout.strip()
    check("tree_clean", porcelain == "", porcelain or "(clean)")
    if head != args.expect_revision or porcelain:
        finalize(1)  # 版本不符：没有必要继续，证据已结构化

    RUN = Path(tempfile.mkdtemp(prefix="run-", dir=str(OUT_BASE)))
    run_start_local = datetime.now()

    common = git("rev-parse", "--git-common-dir").stdout.strip()
    main_tree = Path(common).resolve().parent
    source_db = Path(args.source_db) if args.source_db else \
        main_tree / "db" / "market_feature_store.duckdb"
    parquet_src = Path(args.parquet)
    clone = RUN / "clone.duckdb"
    before = RUN / "before.duckdb"

    inputs.update({
        "trade_date": td,
        "tree": str(TREE),
        "tree_revision": head,
        "tree_clean": True,
        "gate_script": str(Path(__file__).resolve()),
        "gate_script_sha256": sha256(Path(__file__).resolve()),
        "python": sys.executable,
        "source_db": str(source_db),
        "production_before": {"sha256": sha256(source_db), "stat": stat_id(source_db)},
    })

    # ── 1. 冻结输入：parquet 复制进 run 目录，对副本 hash，CLI 只读副本 ──
    parquet_frozen = RUN / "input-frozen.parquet"
    shutil.copy2(parquet_src, parquet_frozen)
    inputs["parquet_frozen"] = str(parquet_frozen)
    inputs["parquet_sha256"] = sha256(parquet_frozen)
    inputs["parquet_origin"] = str(parquet_src)

    # ── 2. 克隆绑定：before（对照）+ clone（修复目标），均须等于换前指纹 ──
    for suffix in (".staging", ".staging.wal", ".staging.status.json", ".run.lock", ".wal"):
        q = Path(str(clone) + suffix)
        if q.exists():
            q.unlink()
    shutil.copy2(source_db, before)
    shutil.copy2(source_db, clone)
    check("clones_match_production",
          sha256(before) == sha256(clone) == inputs["production_before"]["sha256"],
          "before/clone 两份克隆 sha256 均等于参照库换前指纹")

    # ── 3. CLI（rc 硬门禁：非零立即失败）──────────────────────────────
    sys.path.insert(0, str(TREE))  # stitch 测量用仓内实现；置于版本检查之后
    env = {**os.environ, "MARKET_FEATURE_STORE_DB": str(clone)}
    env.pop("PYTHONPATH", None)
    repair_report = RUN / "repair-report.json"
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "market_feature_store.cli",
             "repair-stock-daily-hithink", "--trade-date", td,
             "--parquet", str(parquet_frozen), "--report-path", str(repair_report)],
            cwd=str(TREE), env=env, capture_output=True, text=True, timeout=3600,
        )
        inputs["cli_rc"] = proc.returncode
        inputs["cli_stdout_tail"] = proc.stdout[-600:]
        if proc.returncode != 0:
            check("cli_rc", False,
                  f"rc={proc.returncode}; stderr={proc.stderr[-400:]}")
            finalize(1)
        check("cli_rc", True, 0)
    except subprocess.TimeoutExpired:
        check("cli_rc", False, "CLI 超时（3600s）——按失败处理，不读任何后续证据")
        finalize(1)

    # ── 4. 子进程报告绑定（run 目录内本轮唯一文件）─────────────────────
    child = json.loads(repair_report.read_text(encoding="utf-8"))
    check("child_trade_date", child["trade_date"] == td, td)
    check("child_parquet_bound",
          child["evidence"]["parquet_sha256"] == inputs["parquet_sha256"],
          "子进程报告内 parquet 指纹 == 本轮冻结副本指纹")
    check("child_counts",
          child["evidence"]["counts"]["written_rows"] == 5547
          and child["post"]["final_rows"] == 5553
          and len(child["post"]["kept_rows_identical"]) == 6
          and child["post"]["other_dates_unchanged"] is True,
          child["evidence"]["counts"])
    fd = child["evidence"]["field_diffs"]
    check("child_field_diffs",
          all(v == 0 for k, v in fd.items() if k != "amount")
          and fd.get("amount") == {"600176.SH": {"old": 113.6007, "new": 113.6006}},
          fd)
    derived = child["derived"]
    check("child_derived",
          derived["other_dates_unchanged"] is True
          and "302132.SZ" in derived["new_codes_unavailable"]
          and derived["new_code_rows_removed"].get("feature_stock_window") == 2
          and derived["new_code_rows_removed"].get("feature_stock_technical_daily") == 0,
          {"removed": derived["new_code_rows_removed"],
           "unavailable": list(derived["new_codes_unavailable"])})

    # ── 5. 库内逐值核对（read_only + ATTACH 对照）───────────────────────
    con = duckdb.connect(str(clone), read_only=True)
    con.execute(f"ATTACH '{before}' AS before (READ_ONLY)")

    breakdown = dict(con.execute(
        "SELECT source, COUNT(*) FROM fact_stock_daily WHERE trade_date=? GROUP BY 1", [td],
    ).fetchall())
    check("main_source_breakdown",
          breakdown == {"hithink:daily-k-10d": 5547, "eastmoney:snapshot": 6}, breakdown)

    row = con.execute(
        "SELECT close, pre_close, pct_chg, amount, volume FROM fact_stock_daily "
        "WHERE trade_date=? AND stock_ts_code='302132.SZ'", [td],
    ).fetchone()
    check("302132_pinned_values", row == (63.42, 64.35, -1.45, 5.9863, 94471.0), row)
    amt = con.execute(
        "SELECT amount FROM fact_stock_daily WHERE trade_date=? AND stock_ts_code='600176.SH'",
        [td],
    ).fetchone()[0]
    check("600176_amount", amt == 113.6006, amt)

    zero = {
        t: con.execute(
            f"SELECT COUNT(*) FROM {t} WHERE {dc}=? AND stock_ts_code='302132.SZ'", [td],
        ).fetchone()[0]
        for t, dc in (("feature_stock_technical_daily", "trade_date"),
                      ("feature_stock_window", "as_of_date"))
    }
    check("302132_derived_absent",
          zero == {"feature_stock_technical_daily": 0, "feature_stock_window": 0}, zero)

    day_counts = {
        "technical": con.execute(
            "SELECT COUNT(*) FROM feature_stock_technical_daily WHERE trade_date=?", [td],
        ).fetchone()[0],
        "window": con.execute(
            "SELECT COUNT(*) FROM feature_stock_window WHERE as_of_date=?", [td],
        ).fetchone()[0],
    }
    check("derived_day_counts", day_counts == {"technical": 5529, "window": 22115},
          day_counts)

    w_before = con.execute(
        "SELECT start_date, avg_amount FROM before.feature_stock_window "
        "WHERE as_of_date=? AND stock_ts_code='600176.SH' ORDER BY start_date", [td],
    ).fetchall()
    w_after = con.execute(
        "SELECT start_date, avg_amount FROM feature_stock_window "
        "WHERE as_of_date=? AND stock_ts_code='600176.SH' ORDER BY start_date", [td],
    ).fetchall()
    drift = [(b, a) for b, a in zip(w_before, w_after) if b != a]
    check("600176_window_drift",
          len(w_before) == len(w_after) and len(drift) == 1
          and drift[0][0][1] == 93.1063 and drift[0][1][1] == 93.1062, drift)

    def _except_all(table: str, dcol: str, only_non_target: bool = True) -> list[int]:
        where = f"WHERE {dcol} <> '{td}'" if only_non_target else ""
        fwd = con.execute(
            f"SELECT COUNT(*) FROM (SELECT * FROM before.{table} {where} EXCEPT ALL "
            f"SELECT * FROM {table} {where})").fetchone()[0]
        rev = con.execute(
            f"SELECT COUNT(*) FROM (SELECT * FROM {table} {where} EXCEPT ALL "
            f"SELECT * FROM before.{table} {where})").fetchone()[0]
        return [fwd, rev]

    diffs = {
        "fact_stock_daily": _except_all("fact_stock_daily", "trade_date"),
        "feature_stock_technical_daily": _except_all("feature_stock_technical_daily",
                                                     "trade_date"),
        "feature_stock_window": _except_all("feature_stock_window", "as_of_date"),
        "fact_market_daily(all_dates)": _except_all("fact_market_daily", "trade_date",
                                                    False),
    }
    check("non_target_except_all", all(v == [0, 0] for v in diffs.values()), diffs)

    # 板块拼接（dry_run、无外呼；before 为对照）
    from market_feature_store.sync.sync_local_sector_members import stitch_sector_members
    stitch_params = dict(fetch_caps=False, dry_run=True, include_completed=True,
                         max_baseline_age_days=180)
    td_date = date.fromisoformat(td)
    st_after = stitch_sector_members(td_date, con=con, **stitch_params)
    con2 = duckdb.connect(str(before), read_only=True)
    try:
        st_before = stitch_sector_members(td_date, con=con2, **stitch_params)
    finally:
        con2.close()
    check("stitch_403",
          st_after["stitched"] == st_after["candidates"] == 403
          and st_before["stitched"] == 403,
          {"after": st_after["stitched"], "candidates": st_after["candidates"],
           "before": st_before["stitched"]})

    # ops 收据：字段与时间窗全绑定
    ops = con.execute(
        "SELECT run_id, kind, ok, plan, trade_date, started_at, finished_at "
        "FROM ops_sync_run ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    now_local = datetime.now()
    check("ops_receipt_bound",
          ops[1] == "repair-stock-daily-hithink" and ops[2] is True
          and ops[3] == "staging-swap" and ops[4] == td
          and run_start_local <= ops[5] <= now_local
          and run_start_local <= ops[6] <= now_local,
          {"run_id": ops[0], "kind": ops[1], "ok": ops[2], "plan": ops[3],
           "trade_date": ops[4], "started_at": str(ops[5]), "finished_at": str(ops[6])})
    con.close()

    # ── 6. 备份：run 目录内恰 1 个 + run_id 绑定 ops 行 + 时间窗 ────────
    baks = [p for p in RUN.glob("clone.duckdb.bak-*") if p.suffix != ".json"]
    if len(baks) != 1:
        check("backup_binding", False, f"run 目录内备份数={len(baks)}，期望恰 1 个")
        finalize(1)
    bak = baks[0]
    receipt = json.loads(Path(str(bak) + ".receipt.json").read_text(encoding="utf-8"))
    created = datetime.fromisoformat(receipt["created_at"])
    check("backup_binding",
          receipt["run_id"] == ops[0] and receipt["source_db"] == str(clone)
          and run_start_local <= created <= now_local,
          {"receipt_run_id": receipt["run_id"], "ops_run_id": ops[0],
           "source_db": receipt["source_db"], "created_at": receipt["created_at"]})
    chain = (receipt["backup_sha256"], sha256(bak), sha256(before))
    check("backup_sha256_chain", chain[0] == chain[1] == chain[2],
          {"receipt": chain[0], "file": chain[1], "before": chain[2]})
    check("backup_restore_steps",
          bool(receipt.get("restore_steps")) and "张表" in receipt.get("readability_check", ""),
          {"steps": len(receipt.get("restore_steps", [])),
           "readability": receipt.get("readability_check")})

    # ── 7. 生产库未动 ─────────────────────────────────────────────────
    prod_after = {"sha256": sha256(source_db), "stat": stat_id(source_db)}
    check("production_untouched", prod_after == inputs["production_before"], prod_after)


def main() -> None:
    try:
        run_gate()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 —— 门禁要求任何异常都落成结构化 FAIL
        check("unhandled_exception", False, repr(exc))
        finalize(1)
    finalize(0)


if __name__ == "__main__":
    main()
