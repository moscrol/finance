"""Reproduce the 2026-09-23 market recovery QC findings without live writes.

Run from a checkout containing PRs #861 and #871 with the workbench interpreter.
Only in-memory test fixtures and mocked CLI calls are used. Assertions describe
observed defects, NOT acceptance criteria: fixing the defects should break this
reproducer. This is a dated diagnostic, not a permanent regression gate.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
from unittest.mock import patch


def main() -> None:
    root = Path.cwd()
    sys.path.insert(0, str(root))
    from market_feature_store import cli
    from market_feature_store.sync import compute_local_stats as stats
    from market_feature_store.sync.bridge_hithink_stock_daily import (
        apply_bridge_day,
        build_bridge_day,
    )

    bridge = runpy.run_path(str(root / "tests/test_bridge_hithink_stock_daily.py"))
    local = runpy.run_path(str(root / "tests/test_compute_local_stats.py"))
    observations = {}

    # Rows arriving after planning must not bypass the default no-replace policy.
    with bridge["_con"](bridge["_codes"](3)) as con:
        bridge["_seed_canonical"](con, bridge["_codes"](3), bridge["PREV"])
        plan = build_bridge_day(con, bridge["TD"])
        assert plan["policy"]["allow_replace_existing"] is False
        bridge["_seed_canonical"](con, bridge["_codes"](3), bridge["TD"], close=99.0)
        result = apply_bridge_day(con, plan)
        assert result["deleted_replaced"] == 3
        observations["stale_plan_overwrites_despite_default_policy"] = {
            "allow_replace_existing": plan["policy"]["allow_replace_existing"],
            **result,
            "surviving_prices": con.execute(
                "SELECT DISTINCT close FROM fact_stock_daily WHERE trade_date = ?",
                [bridge["TD"]],
            ).fetchall(),
        }

    # Member rows alone do not prove the canonical bars used by the numerator.
    with local["_db"]() as con:
        local["_seed_two_days"](con)
        local["_seed_universe_and_members"](con)
        declared = {
            "990001.FP": ["600001.SH", "300001.SZ", "000001.SZ"],
            "990002.FP": ["002514.SZ"],
        }
        stats.compute_limit_stats_local("2026-09-02", con=con, recovery_members=declared)
        before = con.execute(
            "SELECT limit_up_count,total_count FROM fact_theme_limit_heat_daily"
        ).fetchall()
        con.execute(
            "DELETE FROM fact_stock_daily "
            "WHERE trade_date='2026-09-02' AND stock_ts_code='600001.SH'"
        )
        result = stats.compute_limit_stats_local(
            "2026-09-02", con=con, recovery_members=declared,
        )
        after = con.execute(
            "SELECT limit_up_count,total_count FROM fact_theme_limit_heat_daily"
        ).fetchall()
        coverage = result["recovery_member_coverage"]["990001.FP"]
        assert result["action"] == "written" and before == [(2, 3)] and after == [(1, 3)]
        assert coverage["observed_bar_fraction"] == 1.0
        observations["missing_canonical_bar_reports_full_coverage"] = {
            "before": before, "after": after,
            "action": result["action"], "coverage": coverage,
        }

    # Construct the actual nightly plan, but never execute any of its actions.
    spec = importlib.util.spec_from_file_location(
        "qc_run_review_sync", root / "skills/daily-full-review/scripts/run_review_sync.py",
    )
    nightly = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nightly)
    labels = [label for label, _ in nightly.build_local_plan("2026-09-22", 1, 1)]
    assert "bridge-stock-daily" not in labels
    observations["nightly_local_plan"] = {"labels": labels, "bridge_present": False}

    # Capture CLI transport before DB access; this is a wiring boundary, not a defect.
    mocked_result = {"trade_date": "2026-09-21", "action": "mocked"}
    with patch.object(stats, "compute_limit_stats_local", return_value=mocked_result) as call:
        with contextlib.redirect_stdout(io.StringIO()):
            cli.cmd_compute_limit_stats_local(
                SimpleNamespace(trade_date="2026-09-21", force=False, min_boards=2),
            )
        assert call.call_args.kwargs == {"force": False, "min_boards": 2}
        observations["cli_recovery_arguments"] = call.call_args.kwargs

    print(json.dumps(observations, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
