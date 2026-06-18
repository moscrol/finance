#!/usr/bin/env python3
"""check_task_plan.validate 的单元测试（可 pytest，也可直接 python3 跑）。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_task_plan as ctp  # noqa: E402


def _valid_plan() -> dict:
    return {
        "task_id": "backfill-20260601-0615",
        "goal": "补 6/01–6/15 的 fact_stock_daily 缺口",
        "task_type": "批量回填",
        "scope": {
            "date_range": {"start": "2026-06-01", "end": "2026-06-15"},
            "symbols": [],
            "themes": [],
        },
        "data_source": ["fupanhui", "duckdb"],
        "target_sink": "duckdb",
        "env": {"branch": "raw-backfill/20260601-stock-daily"},
        "credentials_ready": True,
        "no_lookahead_ack": True,
        "require_dryrun_approval": True,
        "skip_rules": ["停牌跳过", "ST 跳过"],
        "on_missing_data": "pending",
        "handoff": ["duckdb-backfill"],
    }


def test_valid_plan_passes():
    assert ctp.validate(_valid_plan()) == []


def test_each_required_field_missing_fails():
    for key in (
        "task_id", "goal", "task_type", "scope", "data_source",
        "target_sink", "env", "credentials_ready", "no_lookahead_ack",
        "require_dryrun_approval", "skip_rules", "on_missing_data", "handoff",
    ):
        plan = _valid_plan()
        del plan[key]
        assert ctp.validate(plan), f"删除 {key} 后应报门控违规"


def test_branch_main_rejected():
    plan = _valid_plan()
    plan["env"]["branch"] = "main"
    assert any("branch" in i for i in ctp.validate(plan))


def test_invalid_task_type_rejected():
    plan = _valid_plan()
    plan["task_type"] = "随便玩玩"
    assert any("task_type" in i for i in ctp.validate(plan))


def test_invalid_target_sink_rejected():
    plan = _valid_plan()
    plan["target_sink"] = "mysql"
    assert any("target_sink" in i for i in ctp.validate(plan))


def test_invalid_data_source_rejected():
    plan = _valid_plan()
    plan["data_source"] = ["fupanhui", "bloomberg"]
    assert any("data_source" in i for i in ctp.validate(plan))


def test_empty_data_source_rejected():
    plan = _valid_plan()
    plan["data_source"] = []
    assert any("data_source" in i for i in ctp.validate(plan))


def test_invalid_on_missing_rejected():
    plan = _valid_plan()
    plan["on_missing_data"] = "maybe"
    assert any("on_missing_data" in i for i in ctp.validate(plan))


def test_scope_symbols_only_is_enough():
    plan = _valid_plan()
    plan["scope"] = {"date_range": {"start": "", "end": ""}, "symbols": ["600519"], "themes": []}
    assert ctp.validate(plan) == []


def test_scope_themes_only_is_enough():
    plan = _valid_plan()
    plan["task_type"] = "开新题材"
    plan["scope"] = {"date_range": {"start": "", "end": ""}, "symbols": [], "themes": ["固态电池"]}
    assert ctp.validate(plan) == []


def test_scope_partial_date_range_rejected():
    plan = _valid_plan()
    plan["scope"] = {"date_range": {"start": "2026-06-01", "end": ""}, "symbols": [], "themes": []}
    assert any("scope" in i for i in ctp.validate(plan))


def test_lookback_task_requires_no_lookahead_true():
    for tt in ("复盘批处理", "批量回填"):
        plan = _valid_plan()
        plan["task_type"] = tt
        plan["no_lookahead_ack"] = False
        assert any("no_lookahead_ack" in i for i in ctp.validate(plan)), f"{tt} 应要求 no_lookahead_ack=true"


def test_new_theme_allows_no_lookahead_false():
    plan = _valid_plan()
    plan["task_type"] = "开新题材"
    plan["scope"] = {"date_range": {"start": "", "end": ""}, "symbols": [], "themes": ["固态电池"]}
    plan["no_lookahead_ack"] = False
    assert ctp.validate(plan) == []


def test_writing_sink_requires_dryrun_true():
    for sink in ("feishu", "duckdb"):
        plan = _valid_plan()
        plan["target_sink"] = sink
        plan["require_dryrun_approval"] = False
        assert any("require_dryrun_approval" in i for i in ctp.validate(plan)), f"写 {sink} 应要求 dry-run"


def test_readonly_sink_allows_dryrun_false():
    plan = _valid_plan()
    plan["target_sink"] = "readonly"
    plan["require_dryrun_approval"] = False
    assert ctp.validate(plan) == []


def test_bool_fields_reject_nonbool():
    for key in ("credentials_ready", "no_lookahead_ack", "require_dryrun_approval"):
        plan = _valid_plan()
        plan[key] = "yes"
        assert any(key in i for i in ctp.validate(plan)), f"{key} 非 bool 应被拒"


def test_template_passes_only_after_fill():
    # 空白模板必须违规（强制采访），填满才放行
    assert ctp.validate(dict(ctp._TEMPLATE)), "空白模板应报门控违规"


def _run_standalone() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_standalone())
