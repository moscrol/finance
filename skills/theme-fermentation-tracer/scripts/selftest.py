#!/usr/bin/env python3
"""theme-fermentation-tracer 自包含冒烟测试（零凭证、零真实数据）。

目的：在没有真实 market_feature_store.duckdb 的机器上，用合成样本数据
验证 trace.py 的 SQL 与发酵链路逻辑能端到端跑通，并产出四段报告。

做法：
  1. 在临时目录按 schema.sql 建一个最小样本 DuckDB，灌入一个虚构题材
     （测试题材 / 测试板块 / 样本龙头 / 样本补涨）的几行盘面数据。
  2. 在临时目录造一个最小知识库 vault（theme_signals / entity_exposures
     / evidence_index）。
  3. 用环境变量 MARKET_FEATURE_STORE_DB 把 trace.py 指向样本 DuckDB，
     以子进程跑 trace.py，断言 RC=0 且报告含双红启动/首板/补涨/涨停热度等关键标记。

样本数据全部虚构（题材、个股、价格均为假），仅用于逻辑自测，不代表任何市场结论。

用法：
    python3 skills/theme-fermentation-tracer/scripts/selftest.py
退出码：0=PASS，非 0=FAIL。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
SCHEMA_PATH = REPO_ROOT / "market_feature_store" / "schema.sql"
TRACE_PY = SCRIPT_DIR / "trace.py"

THEME = "测试题材"
SECTOR_CODE = "TEST.TI"
SECTOR_NAME = "测试板块"
START = "2026-06-01"
END = "2026-06-12"


def build_sample_db(db_path: Path) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute(SCHEMA_PATH.read_text(encoding="utf-8"))

        con.execute(
            "INSERT INTO config_theme_sector_link (theme, direction, sector_ts_code, sector_name, match_type, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [THEME, "long", SECTOR_CODE, SECTOR_NAME, "manual", 1.0],
        )

        # 板块逐日：06-02/03/04 连续双红（streak 1→3），06-04 多周期共振；06-05 断；06-09 再启动
        sector_rows = [
            ("2026-06-02", 1.2, 15.0, False),
            ("2026-06-03", 2.0, 30.0, False),
            ("2026-06-04", 1.8, 20.0, True),
            ("2026-06-05", -0.5, -10.0, False),
            ("2026-06-09", 1.0, 12.0, False),
        ]
        for d, pct, diff, mpr in sector_rows:
            con.execute(
                "INSERT INTO fact_sector_daily (trade_date, sector_ts_code, sector_name, pct_chg, amount, diff_ratio, multi_period_resonance) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [d, SECTOR_CODE, SECTOR_NAME, pct, 600.0, diff, mpr],
            )

        # 涨停热度：峰值在 06-04（5 家）
        heat_rows = [
            ("2026-06-03", "theme", "all", 3, 18, 3),
            ("2026-06-04", "theme", "all", 5, 20, 1),
        ]
        for d, dim, scope, luc, tot, rk in heat_rows:
            con.execute(
                "INSERT INTO fact_theme_limit_heat_daily (trade_date, sector_ts_code, sector_name, dimension, scope, limit_up_count, total_count, rank) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [d, SECTOR_CODE, SECTOR_NAME, dim, scope, luc, tot, rk],
            )

        # 样本龙头 06-02 首板
        con.execute(
            "INSERT INTO fact_limit_advance_daily (trade_date, stock_ts_code, stock_name, boards) VALUES (?, ?, ?, ?)",
            ["2026-06-02", "sz000001", "样本龙头", 1],
        )

        # 个股日线：样本龙头 06-02 起涨（首板），样本补涨 06-11 才量价突破（补涨）
        stock_rows = [
            ("2026-06-02", "sz000001", "样本龙头", 11.0, 10.0),
            ("2026-06-04", "sz000001", "样本龙头", 12.0, 1.0),
            ("2026-06-11", "sz000001", "样本龙头", 14.0, 2.0),
            ("2026-06-02", "sz000002", "样本补涨", 20.0, 1.0),
            ("2026-06-09", "sz000002", "样本补涨", 21.0, 3.0),
            ("2026-06-11", "sz000002", "样本补涨", 23.0, 8.0),
        ]
        for d, code, name, close, pct in stock_rows:
            con.execute(
                "INSERT INTO fact_stock_daily (trade_date, stock_ts_code, stock_name, close, pct_chg) VALUES (?, ?, ?, ?, ?)",
                [d, code, name, close, pct],
            )
    finally:
        con.close()


def build_sample_vault(vault: Path) -> None:
    relations = vault / "relations"
    relations.mkdir(parents=True, exist_ok=True)
    (relations / "theme_signals.json").write_text(json.dumps({
        "themes": {
            THEME: {
                "recognition_timeline": [
                    {"time_window": "2026-06-02", "recognition_stage": "硬证据",
                     "event": "样本龙头 InP 6 英寸衬底量产公告"},
                ],
                "sell_side_coverage": ["2026-06-03 某券商首次覆盖"],
            }
        }
    }, ensure_ascii=False), encoding="utf-8")

    (relations / "entity_exposures.json").write_text(json.dumps({
        "entities": {
            "E1": {"name": "样本龙头", "codes": ["sz000001"],
                   "concepts": {THEME: {"strength": "core"}}},
            "E2": {"name": "样本补涨", "codes": ["sz000002"],
                   "concepts": {THEME: {"strength": "related"}}},
        }
    }, ensure_ascii=False), encoding="utf-8")

    (relations / "evidence_index.json").write_text(json.dumps({
        "evidence": [
            {"concept": THEME, "evidence_layer": "L3", "updated": "2026-06-02",
             "summary": "样本龙头 6 英寸 InP 衬底规模化量产", "source_name": "公告_20260602"},
        ]
    }, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    if not SCHEMA_PATH.is_file():
        print(f"[FAIL] schema.sql 不存在: {SCHEMA_PATH}")
        return 1
    if not TRACE_PY.is_file():
        print(f"[FAIL] trace.py 不存在: {TRACE_PY}")
        return 1

    with tempfile.TemporaryDirectory(prefix="ferment-selftest-") as tmp:
        tmp_path = Path(tmp)
        db_path = tmp_path / "sample_feature_store.duckdb"
        vault = tmp_path / "wiki"
        out = tmp_path / "report.md"

        build_sample_db(db_path)
        build_sample_vault(vault)

        env = {**os.environ, "MARKET_FEATURE_STORE_DB": str(db_path)}
        proc = subprocess.run(
            [sys.executable, str(TRACE_PY), "--theme", THEME,
             "--start", START, "--end", END, "--vault", str(vault), "--out", str(out)],
            env=env, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            print(f"[FAIL] trace.py RC={proc.returncode}")
            print(proc.stdout)
            print(proc.stderr)
            return 1
        if not out.is_file():
            print("[FAIL] 报告文件未生成")
            return 1

        report = out.read_text(encoding="utf-8")
        checks = {
            "标题": f"{THEME} 发酵链路回溯" in report,
            "消息面时间线": "消息面时间线" in report,
            "认知跃迁/证据": ("认知跃迁" in report) and ("证据[L3]" in report),
            "卖方覆盖": "卖方覆盖" in report,
            "双红启动": "双红启动" in report,
            "双红加强(3连)": "双红加强(3连)" in report,
            "多周期共振": "多周期共振" in report,
            "涨停热度峰值": "涨停热度峰值" in report,
            "样本龙头首板起涨": ("样本龙头" in report) and ("首板" in report),
            "样本补涨补涨梯队": ("样本补涨" in report) and ("补涨" in report),
            "合并链路": "消息 × 盘面合并链路" in report,
        }
        failed = [k for k, ok in checks.items() if not ok]
        for k, ok in checks.items():
            print(f"[{'PASS' if ok else 'FAIL'}] {k}")
        if failed:
            print("\n--- 报告全文（便于排错）---")
            print(report)
            print(f"\n[FAIL] {len(failed)} 项断言未通过: {failed}")
            return 1
        print(f"\n[PASS] 全部 {len(checks)} 项断言通过；样本库 {len(checks)} 段链路逻辑端到端跑通。")
        return 0


if __name__ == "__main__":
    sys.exit(main())
