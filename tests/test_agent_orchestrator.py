from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence.summary import WorkflowStep
from intelligence.workflows import agent_orchestrator as orch


class AgentOrchestratorTest(unittest.TestCase):
    def test_preview_renders_agent_daily_command_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            summary, result, answer = orch.run_agent_orchestrator(
                orch.OrchestratorOptions(
                    query="今天该看什么",
                    date="2026-06-26",
                    knowledge_wiki=Path(td) / "wiki",
                    finance_root=Path(td),
                    execute=False,
                )
            )

        self.assertEqual(summary.status, "PASS")
        self.assertEqual(result.paths[0].id, "agent_daily")
        self.assertIn("agent-daily", result.paths[0].command)
        self.assertIn("2026-06-26", result.paths[0].command)
        self.assertEqual(result.paths[0].status, "planned")
        self.assertIn("Execution Plan", answer)

    def test_execute_runs_only_low_risk_auto_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            step = WorkflowStep(name="execute:daily_ops_ledger", status="PASS", outputs=["ok"])
            with mock.patch.object(orch, "run_command_step", return_value=step) as run:
                summary, result, _ = orch.run_agent_orchestrator(
                    orch.OrchestratorOptions(
                        query="今天缺什么",
                        date="2026-06-26",
                        knowledge_wiki=Path(td) / "wiki",
                        finance_root=Path(td),
                        execute=True,
                    )
                )

        self.assertIn(summary.status, {"PASS", "WARN"})
        self.assertGreaterEqual(run.call_count, 1)
        executed = [path for path in result.paths if path.status == "executed"]
        self.assertTrue(executed)
        self.assertTrue(all(path.auto_execute and path.risk_level == "low" for path in executed))

    def test_execute_skips_non_auto_or_non_low_risk_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(orch, "run_command_step") as run:
                _summary, result, _ = orch.run_agent_orchestrator(
                    orch.OrchestratorOptions(
                        query="帮我跑今天的全量复盘",
                        date="2026-06-26",
                        knowledge_wiki=Path(td) / "wiki",
                        finance_root=Path(td),
                        execute=True,
                    )
                )

        self.assertFalse(run.called)
        self.assertEqual(result.paths[0].id, "daily_review")
        self.assertEqual(result.paths[0].status, "skipped")
        self.assertEqual(result.paths[0].skip_reason, "auto_execute_false")


if __name__ == "__main__":
    unittest.main()
