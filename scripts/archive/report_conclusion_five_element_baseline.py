#!/usr/bin/env python3
"""KC-13：对冻结黄金快照批跑结论五元素在场率。

默认扫 intelligence/tests/fixtures/golden_answers/snapshots。
约定落点 docs/verification/conclusion-five-element-baseline.md。
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.services.conclusion_five_element_lint import (  # noqa: E402
    render_presence_baseline,
)

DEFAULT_SNAPSHOTS = (
    ROOT / "intelligence" / "tests" / "fixtures" / "golden_answers" / "snapshots"
)
DEFAULT_OUT = ROOT / "docs" / "verification" / "conclusion-five-element-baseline.md"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    corpus = {
        path.stem: path.read_text(encoding="utf-8")
        for path in sorted(args.snapshots.glob("*.md"))
    }
    if not corpus:
        raise SystemExit(f"没有快照：{args.snapshots}")
    text = render_presence_baseline(corpus, as_of=args.as_of)
    print(text, end="")
    if args.write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"\n写入 {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
