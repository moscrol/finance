#!/usr/bin/env python3
"""换库锁跨平台自检：本机上 hold_swap_lock 排不排另一个进程的 duckdb 写者。

用法::

    python scripts/check_swap_lock_platform.py          # 人读
    python scripts/check_swap_lock_platform.py --json   # 机读

退出码：0 = 排得掉（macOS 预期如此）；1 = 排不掉（Linux 预期如此：flock 与 duckdb 的
POSIX 记录锁互不相干），此时 daily-full 的环境预检会拒绝开跑。

只在临时目录的临时库上测，不碰任何真实库。判定逻辑在
``market_feature_store/db.py`` 的 ``swap_lock_platform_probe``。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from market_feature_store.db import swap_lock_platform_probe  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="换库锁跨平台自检（只读，临时库）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = swap_lock_platform_probe()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        mark = {True: "排得掉", False: "排不掉", None: "没测成"}
        print(f"平台 {result['platform']} · duckdb {result['duckdb']}")
        print(f"  写者在场时换库锁拿锁失败：{mark[result['writer_blocks_lock']]}")
        print(f"  持换库锁时另一进程的写者打不开：{mark[result['lock_blocks_writer']]}")
        print(("✅ " if result["excludes_writers"] else "❌ ") + result["detail"])
    return 0 if result["excludes_writers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
