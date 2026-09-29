#!/usr/bin/env python3
"""对**非生产**库按两源仲裁补桥缺口行（`market_feature_store.sync.bridge_gap_arbitration`）。

默认只打印计划（dry-run）；`--apply` 才写，且拒绝 canonical 生产库（`write_path.is_canonical_production`：
认得出主检出树与附属 worktree 两种位置——夜跑从冻结代码根跑，仓相对路径认不出真生产库）。
生产换库走 duckdb-backfill 的候选 → 验收 → 用户授权 → 发布链路；夜跑在 staging 上调用本脚本，随换库发布。

    .venv-workbench/bin/python scripts/backfill_bridge_gaps.py --db db/candidate-x/cand.duckdb \\
        --trade-date 2026-09-29 [--capture-dir db/quote-captures/tencent/2026-09-29] \\
        [--eastmoney-dir db/candidate-x/eastmoney-kline | --eastmoney-fetch-dir <新目录>] \\
        [--apply] [--receipt out.json]

`--db` 省略时取 `market_feature_store.db.DB_PATH`（随 `MARKET_FEATURE_STORE_DB`，夜跑即 staging）。
`--eastmoney-fetch-dir`：先只读列出缺口代码，逐只抓东财日 K 落盘到这个新目录再当证据读（尽力而为）。
`--capture-dir`：先用 `audit_dated_quote_capture.audit_capture` 验封存；验不过就不用它，并记进收据。

退出码：0 完成（含 0 行可补）；1 写入被拒（越界 / 冲突）；2 参数或输入错误。给了 `--receipt` 时三种都落收据。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402

from market_feature_store.sync.bridge_gap_arbitration import (  # noqa: E402
    POLICY_VERSION,
    apply_gap_fill,
    fetch_eastmoney_kline,
    gap_codes,
    load_eastmoney_kline,
    load_tencent_capture,
    plan_gap_fill,
)
from market_feature_store.sync.bridge_hithink_stock_daily import BridgeRefused  # noqa: E402

PRODUCTION_DB = (REPO_ROOT / "db" / "market_feature_store.duckdb").resolve()


def _sha256_dir(path: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(path.iterdir()) if p.is_file()}


def _is_production(db: Path, pinned: str) -> bool:
    from market_feature_store.write_path import is_canonical_production

    return db == Path(pinned).resolve() or is_canonical_production(db)


def _write_receipt(path: str | None, receipt: dict) -> None:
    if path:
        with Path(path).open("x", encoding="utf-8") as handle:  # 旧证据不覆盖
            handle.write(json.dumps(receipt, ensure_ascii=False, indent=2, default=str) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db")
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--capture-dir")
    evidence = parser.add_mutually_exclusive_group()
    evidence.add_argument("--eastmoney-dir")
    evidence.add_argument("--eastmoney-fetch-dir")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--receipt")
    parser.add_argument("--production-db", default=str(PRODUCTION_DB), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.receipt and Path(args.receipt).exists():
        print(f"收据 {args.receipt} 已存在；旧证据不覆盖，换一个新路径", file=sys.stderr)
        return 2
    try:
        date.fromisoformat(args.trade_date)
    except ValueError:
        print("--trade-date 须为 YYYY-MM-DD", file=sys.stderr)
        return 2
    if args.db:
        db = Path(args.db).resolve()
    else:
        from market_feature_store.db import DB_PATH

        db = Path(DB_PATH).resolve()
    receipt = {"kind": "bridge-gap-fill", "policy_version": POLICY_VERSION, "db_path": str(db),
               "trade_date": args.trade_date, "applied": False, "inputs": {},
               "authorization": "用户 2026-09-29 19:20「同意推荐方案」（两源一致才补）；生产只经换库发布"}
    if not db.is_file():
        print(f"库不存在：{db}", file=sys.stderr)
        _write_receipt(args.receipt, {**receipt, "refused": f"库不存在：{db}"})
        return 2
    if _is_production(db, args.production_db):
        message = f"拒绝：{db} 是生产库。先克隆出候选库（或在夜跑 staging 上）再补。"
        print(message, file=sys.stderr)
        _write_receipt(args.receipt, {**receipt, "refused": message})
        return 2

    evidence_sets: list[dict] = []
    if args.capture_dir:
        path = Path(args.capture_dir)
        if not path.is_dir():
            print(f"目录不存在：{path}", file=sys.stderr)
            _write_receipt(args.receipt, {**receipt, "refused": f"目录不存在：{path}"})
            return 2
        from scripts.audit_dated_quote_capture import audit_capture

        entry: dict = {"path": str(path), "files_sha256": _sha256_dir(path)}
        try:
            audit = audit_capture(path, date.fromisoformat(args.trade_date))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            entry["audit_error"] = f"{type(exc).__name__}: {exc}"
            print(f"封存捕获未通过审计，不作证据：{entry['audit_error']}", file=sys.stderr)
        else:
            entry["audit"] = {k: audit[k] for k in ("trade_date", "declared_scope_count",
                                                    "validated_quote_count", "capture_validated")}
            evidence_sets.append(load_tencent_capture(path))
        receipt["inputs"]["capture_dir"] = entry
    if args.eastmoney_fetch_dir:
        con = duckdb.connect(str(db), read_only=True)
        try:
            codes = gap_codes(con, args.trade_date)
        finally:
            con.close()
        fetch = fetch_eastmoney_kline(codes, args.trade_date, args.eastmoney_fetch_dir)
        receipt["inputs"]["eastmoney_fetch"] = fetch
        args.eastmoney_dir = args.eastmoney_fetch_dir
    if args.eastmoney_dir:
        path = Path(args.eastmoney_dir)
        if not path.is_dir():
            print(f"目录不存在：{path}", file=sys.stderr)
            _write_receipt(args.receipt, {**receipt, "refused": f"目录不存在：{path}"})
            return 2
        evidence_sets.append(load_eastmoney_kline(path, args.trade_date))
        receipt["inputs"]["eastmoney_dir"] = {"path": str(path), "files_sha256": _sha256_dir(path)}

    con = duckdb.connect(str(db), read_only=not args.apply)
    try:
        plan = plan_gap_fill(con, args.trade_date, evidence_sets)
        result = apply_gap_fill(con, plan) if args.apply else {"dry_run": True}
    except BridgeRefused as exc:
        print(f"拒绝：{exc}", file=sys.stderr)
        _write_receipt(args.receipt, {**receipt, "refused": str(exc)})
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        _write_receipt(args.receipt, {**receipt, "refused": f"{type(exc).__name__}: {exc}"})
        return 2
    finally:
        con.close()

    for item in plan["items"]:
        print(f"  {item['stock_ts_code']:<10} {item.get('kind', '-'):<10} {item['verdict']:<28} "
              f"候选 {item.get('internal_candidate')} → 前收 {item.get('pre_close')}")
    print(f"{args.trade_date}: 缺口 {plan['gap_count']}，可补 {plan['fill_count']}，"
          f"{'已写入 ' + str(result.get('inserted')) if args.apply else 'dry-run 未写'}")
    _write_receipt(args.receipt, {
        **receipt, "applied": bool(args.apply), "result": result,
        "plan": {k: v for k, v in plan.items() if k != "rows"},
        "rows": [[str(v) if v is not None else None for v in row] for row in plan["rows"]],
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
