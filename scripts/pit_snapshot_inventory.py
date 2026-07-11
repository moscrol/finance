#!/usr/bin/env python3
"""Freeze daily PIT inputs and inventory provable historical artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.eval.pit_snapshot import (  # noqa: E402
    build_historical_inventory,
    freeze_daily_snapshot,
    render_historical_inventory,
    validate_frozen_snapshot,
)


def _write_json(path: str | Path, body: dict) -> None:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(body, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def cmd_freeze(args: argparse.Namespace) -> int:
    manifest = freeze_daily_snapshot(
        args.db,
        as_of=args.as_of,
        finance_root=args.finance_root,
        kb_root=args.kb_root,
        out_dir=args.out_dir,
        lookback=args.lookback,
        dry_run=args.dry_run,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
    return 0 if manifest["status"] != "pending" else 2


def cmd_inventory(args: argparse.Namespace) -> int:
    inventory = build_historical_inventory(
        args.db,
        finance_root=args.finance_root,
        kb_root=args.kb_root,
        start=args.start,
        end=args.end,
    )
    _write_json(args.out_json, inventory)
    markdown = render_historical_inventory(inventory)
    out_md = Path(args.out_md).expanduser()
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(markdown, encoding="utf-8")
    print(json.dumps(inventory["status_counts"], ensure_ascii=False))
    print(f"written: {args.out_json}")
    print(f"written: {args.out_md}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    manifest = validate_frozen_snapshot(args.out_dir, args.as_of)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    freeze = sub.add_parser("freeze", help="冻结最新或指定交易日的不可变输入快照")
    freeze.add_argument("--db", required=True)
    freeze.add_argument("--finance-root", required=True)
    freeze.add_argument("--kb-root", required=True)
    freeze.add_argument("--out-dir", required=True)
    freeze.add_argument("--as-of")
    freeze.add_argument("--lookback", type=int, default=20)
    freeze.add_argument("--dry-run", action="store_true")
    freeze.set_defaults(func=cmd_freeze)

    validate = sub.add_parser(
        "validate",
        help="校验冻结快照、manifest checksum 与前序 hash chain",
    )
    validate.add_argument("--out-dir", required=True)
    validate.add_argument("--as-of", required=True)
    validate.set_defaults(func=cmd_validate)

    inventory = sub.add_parser(
        "inventory", help="盘点 cutoff 前已存在的 DuckDB 行与 Git 资料"
    )
    inventory.add_argument("--db", required=True)
    inventory.add_argument("--finance-root", required=True)
    inventory.add_argument("--kb-root", required=True)
    inventory.add_argument("--start", required=True)
    inventory.add_argument("--end", required=True)
    inventory.add_argument("--out-json", required=True)
    inventory.add_argument("--out-md", required=True)
    inventory.set_defaults(func=cmd_inventory)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
