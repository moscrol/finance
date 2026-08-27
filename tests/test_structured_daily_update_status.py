import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from intelligence.paths import ProjectPaths
from intelligence.runner import run_command_step
from intelligence.summary import WorkflowStep
from intelligence.workflows.daily_review import (
    DailyReviewOptions,
    build_daily_review_plan,
    can_downgrade_daily_update_failure,
    run_daily_review,
)
from market_feature_store import cli


def daily_update_result(ok: bool, validation_ok: bool) -> dict:
    return {
        "trade_date": "2026-07-09",
        "ok": ok,
        "steps": [
            {"name": "sync-market", "ok": True},
            {"name": "sync-sector", "ok": ok, "error": None if ok else "upstream unavailable"},
        ],
        "validation": {
            "ok": validation_ok,
            "missing_fields": [],
            "tables": [{"table": "fact_market_daily", "ok": validation_ok, "max_date": "2026-07-09", "rows": 1}],
        },
    }


def patch_preflight_ok():
    """放行 CLI 的环境预检——本组用例只验结构化状态产物。

    预检本身（缺 akshare/duckdb/CDP 时 fail closed）在 test_daily_full_preflight.py
    里单独覆盖；不放行的话，任何缺 akshare 的解释器（含 CI）都跑不到被 patch 的
    run_daily_update。
    """
    return patch(
        "market_feature_store.sync.sync_daily_full.preflight_daily_update",
        return_value={"ok": True, "problems": []},
    )


class StructuredDailyUpdateStatusTest(unittest.TestCase):
    def test_step_timeout_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "step_timeout_sec must be positive"):
            DailyReviewOptions(date="2026-07-09", step_timeout_sec=0)

    def test_cli_writes_structured_warn_status(self):
        with tempfile.TemporaryDirectory() as td:
            status_path = Path(td) / "status.json"
            args = SimpleNamespace(
                trade_date="2026-07-09",
                chart_table=None,
                skip_long=False,
                no_chart=False,
                stock_source="snapshot",
                status_json=str(status_path),
                direct=False,
            )
            with patch_preflight_ok(), patch(
                "market_feature_store.write_path.is_canonical_production",
                return_value=False,
            ), patch(
                "market_feature_store.sync.sync_daily_full.run_daily_update",
                return_value=daily_update_result(ok=False, validation_ok=True),
            ):
                returncode = cli.cmd_daily_update(args)

            payload = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(returncode, 1)
            self.assertEqual(payload["status"], "WARN")
            self.assertTrue(payload["recoverable"])
            self.assertEqual(payload["failed_steps"], ["sync-sector"])

    def test_cli_uses_hard_failure_exit_code_when_validation_fails(self):
        with tempfile.TemporaryDirectory() as td:
            status_path = Path(td) / "status.json"
            args = SimpleNamespace(
                trade_date="2026-07-09",
                chart_table=None,
                skip_long=False,
                no_chart=False,
                stock_source="snapshot",
                status_json=str(status_path),
                direct=False,
            )
            with patch_preflight_ok(), patch(
                "market_feature_store.write_path.is_canonical_production",
                return_value=False,
            ), patch(
                "market_feature_store.sync.sync_daily_full.run_daily_update",
                return_value=daily_update_result(ok=False, validation_ok=False),
            ):
                returncode = cli.cmd_daily_update(args)

            payload = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(returncode, 2)
            self.assertEqual(payload["status"], "FAIL")
            self.assertFalse(payload["recoverable"])

    def test_workflow_downgrade_requires_structured_warn(self):
        options = DailyReviewOptions(date="2026-07-09", continue_on_warn=True)
        text_only = WorkflowStep(
            name="daily-update",
            status="FAIL",
            stdout_tail=["质检: OK"],
        )
        structured = WorkflowStep(
            name="daily-update",
            status="FAIL",
            structured_result={"status": "WARN", "recoverable": True},
        )

        self.assertFalse(can_downgrade_daily_update_failure(text_only, options))
        self.assertTrue(can_downgrade_daily_update_failure(structured, options))

    def test_runner_loads_status_json_from_child_command(self):
        with tempfile.TemporaryDirectory() as td:
            status_path = Path(td) / "status.json"
            script = (
                "import json,sys;"
                "open(sys.argv[2],'w',encoding='utf-8').write(json.dumps({'status':'WARN','recoverable':True}));"
                "sys.exit(1)"
            )
            step = run_command_step(
                "child",
                [sys.executable, "-c", script, "--status-json", str(status_path)],
                cwd=td,
            )

        self.assertEqual(step.status, "FAIL")
        self.assertEqual(step.structured_result, {"status": "WARN", "recoverable": True})

    def test_runner_terminates_timed_out_command(self):
        with tempfile.TemporaryDirectory() as td:
            step = run_command_step(
                "slow-child",
                [sys.executable, "-c", "import time; time.sleep(2)"],
                cwd=td,
                timeout_sec=0.05,
            )

        self.assertEqual(step.status, "FAIL")
        self.assertEqual(step.errors, ["command timed out after 0.05 seconds"])
        self.assertLess(step.duration_sec, 1)

    def test_failed_workflow_sends_operational_alert(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = ProjectPaths(
                finance_root=root,
                knowledge_wiki=root / "wiki",
                finance_site=root / "site",
                market_snapshot_dir=root / "snapshots",
                vector_index_dir=root / "vectors",
            )
            failure = WorkflowStep(
                name="quality-gate",
                status="FAIL",
                errors=["quality gate failed"],
            )
            with patch(
                "intelligence.workflows.daily_review.run_command_step",
                return_value=failure,
            ), patch(
                "intelligence.workflows.daily_review.record_daily_review_metrics",
                return_value=None,
            ), patch(
                "intelligence.workflows.daily_review.send_alert",
                return_value=True,
            ) as alert:
                summary = run_daily_review(
                    DailyReviewOptions(
                        date="2026-07-09",
                        skip_sync=True,
                    ),
                    paths,
                )

        self.assertEqual(summary.status, "FAIL")
        alert.assert_called_once()
        self.assertIn("quality-gate", alert.call_args.args[0])

    def test_alert_delivery_failure_is_recorded_without_masking_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = ProjectPaths(
                finance_root=root,
                knowledge_wiki=root / "wiki",
                finance_site=root / "site",
                market_snapshot_dir=root / "snapshots",
                vector_index_dir=root / "vectors",
            )
            failure = WorkflowStep(name="quality-gate", status="FAIL", errors=["bad"])
            with patch(
                "intelligence.workflows.daily_review.run_command_step",
                return_value=failure,
            ), patch(
                "intelligence.workflows.daily_review.send_alert",
                return_value=False,
            ), patch(
                "intelligence.workflows.daily_review.record_daily_review_metrics",
                return_value=None,
            ):
                summary = run_daily_review(
                    DailyReviewOptions(date="2026-07-09", skip_sync=True),
                    paths,
                )

        self.assertEqual(summary.status, "FAIL")
        self.assertIn("operational alert delivery failed", summary.warnings)

    def test_workflow_metrics_use_a_separate_runtime_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            users_root = root / "users"
            paths = ProjectPaths(
                finance_root=root,
                knowledge_wiki=root / "wiki",
                finance_site=root / "site",
                market_snapshot_dir=root / "snapshots",
                vector_index_dir=root / "vectors",
            )
            success = WorkflowStep(
                name="quality-gate",
                status="PASS",
                duration_sec=1.25,
            )
            with patch.dict(
                "os.environ",
                {"FORESIGHT_USERS_DIR": str(users_root)},
            ), patch(
                "intelligence.workflows.daily_review.run_command_step",
                return_value=success,
            ):
                summary = run_daily_review(
                    DailyReviewOptions(
                        date="2026-07-09",
                        user="runtime-test",
                        skip_sync=True,
                        alerts_enabled=False,
                    ),
                    paths,
                )

            metrics_path = users_root / "runtime-test" / "workflow_metrics.jsonl"
            record = json.loads(metrics_path.read_text(encoding="utf-8"))

        self.assertEqual(summary.status, "PASS")
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(
            record["duration_sec"],
            round(sum(step.duration_sec or 0 for step in summary.steps), 3),
        )
        self.assertEqual(record["failed_steps"], [])

    def test_daily_update_plan_requests_structured_status(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = ProjectPaths(
                finance_root=root,
                knowledge_wiki=root / "wiki",
                finance_site=root / "site",
                market_snapshot_dir=root / "snapshots",
                vector_index_dir=root / "vectors",
            )
            plan = build_daily_review_plan(DailyReviewOptions(date="2026-07-09"), paths)

        daily_update = next(step for step in plan if step.name == "daily-update")
        self.assertIn("--status-json", daily_update.argv)
        self.assertTrue(daily_update.argv[-1].endswith("daily-update-2026-07-09.json"))


if __name__ == "__main__":
    unittest.main()
