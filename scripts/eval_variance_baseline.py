#!/usr/bin/env python3
"""同 rev 同题 N 次复跑，产出翻转率基线收据（W7）。

防的失败形状：N=1 探针的 degrade/judge transient 被记成产品回归。
A/B 观测差异小于本脚本给出的基线翻转率，不得下回归/改善结论。

两种模式：
  --replay PATH   离线：夹具 JSON 或已落盘的 run 目录（单测走这条，无网络）
  --live          经 intelligence.eval.live_probe 起 sidecar；默认端口 8796，
                  拒绝 8792/8793/8795/8799/8801。默认不 live。

对 441c60f2 出第一份真基线（本任务不自动跑）：

  python scripts/eval_variance_baseline.py --live --rev 441c60f2 --n 5 --port 8796
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.eval.variance_baseline import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
