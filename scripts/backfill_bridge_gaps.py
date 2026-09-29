#!/usr/bin/env python3
"""对**非生产**库按两源仲裁补桥缺口行（`market_feature_store.sync.bridge_gap_arbitration`）。

默认只打印计划（dry-run）；`--apply` 才写，且拒绝指向生产库 `db/market_feature_store.duckdb`。
生产换库走 duckdb-backfill 的候选 → 验收 → 用户授权 → 发布链路，本脚本不做。

    .venv-workbench/bin/python scripts/backfill_bridge_gaps.py --db db/candidate-x/cand.duckdb \\
        --trade-date 2026-09-29 [--capture-dir db/quote-captures/tencent/2026-09-29] \\
        [--eastmoney-dir db/candidate-x/eastmoney-kline] [--apply] [--receipt out.json]

退出码：0 完成（含 0 行可补）；1 写入被拒（越界 / 冲突）；2 参数或输入错误。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402

from market_feature_store.sync.bridge_gap_arbitration import (  # noqa: E402
    POLICY_VERSION,
    apply_gap_fill,
    load_eastmoney_kline,
    load_tencent_capture,
    plan_gap_fill,
)
from market_feature_store.sync.bridge_hithink_stock_daily import BridgeRefused  # noqa: E402

PRODUCTION_DB = (REPO_ROOT / "db" / "market_feature_store.duckdb").resolve()


def _sha256_dir(path: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(path.iterdir()) if p.is_file()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", required=True)
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--capture-dir")
    parser.add_argument("--eastmoney-dir")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--receipt")
    parser.add_argument("--production-db", default=str(PRODUCTION_DB), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    db = Path(args.db).resolve()
    if not db.is_file():
        print(f"库不存在：{db}", file=sys.stderr)
        return 2
    if db == Path(args.production_db).resolve():
        print(f"拒绝：{db} 是生产库。先克隆出候选库再补。", file=sys.stderr)
        return 2
    evidence_sets, inputs = [], {}
    for flag, loader in (("capture_dir", load_tencent_capture), ("eastmoney_dir", None)):
        value = getattr(args, flag)
        if not value:
            continue
        path = Path(value)
        if not path.is_dir():
            print(f"目录不存在：{path}", file=sys.stderr)
            return 2
        evidence_sets.append(loader(path) if loader else load_eastmoney_kline(path, args.trade_date))
        inputs[flag] = {"path": str(path), "files_sha256": _sha256_dir(path)}

    con = duckdb.connect(str(db), read_only=not args.apply)
    try:
        plan = plan_gap_fill(con, args.trade_date, evidence_sets)
        result = apply_gap_fill(con, plan) if args.apply else {"dry_run": True}
    except BridgeRefused as exc:
        print(f"拒绝：{exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        con.close()

    for item in plan["items"]:
        print(f"  {item['stock_ts_code']:<10} {item.get('kind', '-'):<10} {item['verdict']:<28} "
              f"候选 {item.get('internal_candidate')} → 前收 {item.get('pre_close')}")
    print(f"{args.trade_date}: 缺口 {plan['gap_count']}，可补 {plan['fill_count']}，"
          f"{'已写入 ' + str(result.get('inserted')) if args.apply else 'dry-run 未写'}")
    if args.receipt:
        receipt = {
            "kind": "bridge-gap-fill", "policy_version": POLICY_VERSION, "db_path": str(db),
            "trade_date": args.trade_date, "applied": bool(args.apply), "result": result, "inputs": inputs,
            "plan": {k: v for k, v in plan.items() if k != "rows"},
            "rows": [[str(v) if v is not None else None for v in row] for row in plan["rows"]],
            "authorization": "用户 2026-09-29 19:20「同意推荐方案」（两源一致才补）；生产发布另需授权",
        }
        Path(args.receipt).write_text(json.dumps(receipt, ensure_ascii=False, indent=2, default=str) + "\n",
                                      encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
