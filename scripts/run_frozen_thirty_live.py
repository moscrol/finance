#!/usr/bin/env python3
"""CLI wrapper: python scripts/run_frozen_thirty_live.py --only A1-market-overview."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.eval.frozen_thirty_live import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
