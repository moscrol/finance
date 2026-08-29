#!/usr/bin/env python3
"""离线重跑 ``judge_status=unavailable`` 的判官；只写收据，不改已发布答案。

Pending 索引（gitignore / 家目录，勿提交 live 大包）：
  默认  ~/.finance-runtime/rejudge-pending/index.jsonl
  覆盖  --index PATH  或环境变量 FINANCE_REJUDGE_PENDING_INDEX
  仓库内可选  state/rejudge-pending/index.jsonl（须自行 gitignore）

例：
  python scripts/rejudge_pending.py --fixture intelligence/eval/fixtures/rejudge-unavailable-run.json
  python scripts/rejudge_pending.py --index ~/.finance-runtime/rejudge-pending/index.jsonl --receipt-dir intelligence/eval/runs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.services.rejudge_pending import (  # noqa: E402
    DEFAULT_INDEX,
    RECEIPT_DIR,
    load_json_object,
    pending_index_path,
    pending_row_slug,
    replayable_pending_rows,
    run_offline_rejudge,
    summarize_receipts,
)


def _default_judge(request: dict) -> dict:
    """Deterministic fixture seam. Live callers pass --judge-fn via tests."""

    del request
    raise SystemExit(
        "offline rejudge needs an injected judge (tests) or a configured "
        "LLM_JUDGE provider; this CLI entry is the ledger + receipt writer"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replay pending semantic-judge rows offline. Writes *-rejudge "
            "receipts only; never rewrites the published answer. "
            f"Default pending index: {DEFAULT_INDEX}"
        )
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=None,
        help=f"pending JSONL (default {DEFAULT_INDEX} or FINANCE_REJUDGE_PENDING_INDEX)",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        action="append",
        default=[],
        help="unavailable-run JSON fixture (repeatable); used by tests and replay",
    )
    parser.add_argument(
        "--receipt-dir",
        type=Path,
        default=REPO / RECEIPT_DIR,
        help="directory for *-rejudge.json receipts",
    )
    parser.add_argument(
        "--published-answer",
        type=Path,
        default=None,
        help="optional answer.md to assert it is not rewritten",
    )
    parser.add_argument(
        "--export-fixtures",
        type=Path,
        default=None,
        help=(
            "把索引里可重放的 pending 行（行内自带 judge_request，"
            "R-20260829-04 起的新式行）导出为夹具文件，供外部判官批量裁决；"
            "同时报告 stale（旧式、不可重放）行数"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    index = pending_index_path(args.index)
    if args.export_fixtures is not None:
        replayable, stale = replayable_pending_rows(args.index)
        target = args.export_fixtures
        target.mkdir(parents=True, exist_ok=True)
        written = []
        for row in replayable:
            slug = pending_row_slug(row)
            path = target / f"{slug}.json"
            path.write_text(
                json.dumps(row, ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8",
            )
            written.append(str(path))
        print(
            json.dumps(
                {
                    "index": str(index),
                    "replayable_exported": len(written),
                    "stale_rows": len(stale),
                    "fixtures_dir": str(target),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    fixtures = list(args.fixture)
    if not fixtures:
        print(
            json.dumps(
                {
                    "index": str(index),
                    "index_exists": index.is_file(),
                    "hint": "pass --fixture PATH or append pending rows first",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    receipts = []
    for fixture_path in fixtures:
        fixture = load_json_object(fixture_path)
        slug = str(fixture.get("run_id") or fixture_path.stem)
        receipt_path = args.receipt_dir / f"{slug}-rejudge.json"
        judge_payload = fixture.get("replay_report")
        if isinstance(judge_payload, dict):

            def _judge(_request: dict, *, _report=judge_payload) -> dict:
                return _report

        else:
            _judge = _default_judge
        receipts.append(
            run_offline_rejudge(
                fixture,
                _judge,
                receipt_path=receipt_path,
                published_answer_path=args.published_answer,
            )
        )
    print(json.dumps(summarize_receipts(receipts), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
