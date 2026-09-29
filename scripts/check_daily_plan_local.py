"""OPC 临时：跨日质检按 REVIEW_SYNC_PLAN（默认 local）走 sync 树 CLI。

生成段 cwd=WORKSPACE 时 -m market_feature_store 会加载主检出树旧包（无 --plan），
把 local 计划不产的龙虎榜/全球表判红。可逆：删本文件 + 还原 daily_review.py.bak-opc-20260917。
"""
from __future__ import annotations

import os
import sys

SYNC_ROOT = os.environ.get("FINANCE_SYNC_CODE_ROOT", "/Users/a77/.finance-runtime/finance-sync-0e7f77025409")  # path-literal-ok: 夜跑 sync 固定检出树（原 fe9fdb/finance-workspace-sync 已退役，launchd 见 intelligence/dream plist）
plan = os.environ.get("REVIEW_SYNC_PLAN", "local")

if len(sys.argv) < 2:
    sys.stderr.write("usage: check_daily_plan_local.py YYYY-MM-DD [--json path]\n")
    raise SystemExit(2)

date = sys.argv[1]
json_path = None
if "--json" in sys.argv:
    i = sys.argv.index("--json")
    json_path = sys.argv[i + 1] if i + 1 < len(sys.argv) else None

sys.path.insert(0, SYNC_ROOT)
argv = [
    "market_feature_store",
    "check-daily",
    "--trade-date",
    date,
    "--plan",
    plan,
]
if json_path:
    argv += ["--json", json_path]

sys.argv = argv
# run CLI main
from market_feature_store.cli import main  # noqa: E402  (包装器:需先改写 sys.argv)
raise SystemExit(main())
