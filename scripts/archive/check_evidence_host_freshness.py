#!/usr/bin/env python3
"""KC-20：按宿主出「有人在问但料是旧的」清单。

默认读 ``KNOWLEDGE_WIKI`` 的 evidence_index，并扫
``FORESIGHT_USERS_DIR``（缺省 ~/.local/share/finance-workbench/users）
下各用户 runs/*/run.json 的近 7 天问句。报告落到
``docs/verification/evidence-host-freshness-YYYY-MM-DD.md``。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.services.evidence_freshness import (  # noqa: E402
    collect_hits_from_run_store,
    render_freshness_report,
    report_path,
    summarize_hosts,
)


def _default_wiki() -> Path:
    raw = os.environ.get("KNOWLEDGE_WIKI")
    if raw:
        return Path(raw)
    return Path.home() / "knowledge-base-private" / "wiki"


def _default_users() -> Path:
    raw = os.environ.get("FORESIGHT_USERS_DIR")
    if raw:
        return Path(raw)
    return Path.home() / ".local/share/finance-workbench/users"


def _load_items(wiki: Path) -> list[object]:
    path = wiki / "relations" / "evidence_index.json"
    if not path.exists():
        raise SystemExit(f"找不到 {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    if not isinstance(items, list):
        raise SystemExit("evidence_index.items 不是列表")
    return items


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wiki", type=Path, default=_default_wiki())
    parser.add_argument("--users-dir", type=Path, default=_default_users())
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "docs" / "verification",
    )
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--write", action="store_true", help="写入约定路径；默认只打印")
    args = parser.parse_args()

    items = _load_items(args.wiki)
    hosts = {
        str(item.get("target") or "").strip()
        for item in items
        if isinstance(item, dict) and item.get("target")
    }
    hits: dict[str, tuple[int, date | None]] = {}
    if args.users_dir.exists():
        for user_dir in args.users_dir.iterdir():
            runs = user_dir / "runs"
            if runs.is_dir():
                chunk = collect_hits_from_run_store(runs, hosts, as_of=args.as_of)
                for host, (count, last) in chunk.items():
                    prev_count, prev_last = hits.get(host, (0, None))
                    latest = last if prev_last is None or (last and last > prev_last) else prev_last
                    hits[host] = (prev_count + count, latest)
    rows = summarize_hosts(items, as_of=args.as_of, hits=hits)
    text = render_freshness_report(rows, as_of=args.as_of)
    print(text, end="")
    if args.write:
        path = report_path(args.out_dir, args.as_of)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"\n写入 {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
