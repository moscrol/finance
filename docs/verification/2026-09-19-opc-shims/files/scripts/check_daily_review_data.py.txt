"""OPC 临时 shim（2026-09-17）：转发到 FINANCE_CODE_ROOT 质检闸门。

原因：intelligence.cli 在 WORKSPACE cwd 下跑相对路径 scripts/check_daily_review_data.py，
主检出树那份不认 REVIEW_SYNC_PLAN=local，会把 plan=local 设计上不抓的
fact_theme_flow_daily 判成断档。nightly_full_review.sh 已钉住 CODE_ROOT 的守卫，
生成段尚未（见脚本注释「遗留未修」）。本 shim 可逆：旁边有 .bak-opc-20260917。
"""
from __future__ import annotations

import os
import runpy
import sys

CODE_ROOT = os.environ.get("FINANCE_CODE_ROOT", "/Users/a77/finance-workspace-runtime")
TARGET = os.path.join(CODE_ROOT, "scripts", "check_daily_review_data.py")
if not os.path.isfile(TARGET):
    sys.stderr.write(f"shim: missing CODE_ROOT checker: {TARGET}\n")
    raise SystemExit(2)

os.environ.setdefault("REVIEW_SYNC_PLAN", "local")
# 让 consumption_registry.tables_for_plan 从 runtime 加载
if CODE_ROOT not in sys.path:
    sys.path.insert(0, CODE_ROOT)

sys.argv[0] = TARGET
runpy.run_path(TARGET, run_name="__main__")
