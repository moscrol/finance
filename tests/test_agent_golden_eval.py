import tempfile
import unittest
from pathlib import Path

from tests import test_daily_agent as daily_agent_fixture
from intelligence.workflows.daily_agent import DailyAgentOptions, run_daily_agent


class AgentGoldenEvalTest(unittest.TestCase):
    def test_daily_agent_golden_guardrails(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = daily_agent_fixture.DailyAgentTest().make_fixture(Path(tmp))

            summary, report, markdown = run_daily_agent(
                DailyAgentOptions(
                    date="2026-06-11",
                    finance_root=paths.finance_root,
                    kb_wiki=paths.knowledge_wiki,
                    top_per_date=2,
                    semantic_rag_top_n=0,
                )
            )

        self.assertIn(summary.status, {"PASS", "WARN"})
        real_rows = report["decision"]["old_logic_wakeup"] + report["decision"]["new_logic_candidate"] + report["decision"]["data_gap"]
        self.assertTrue(real_rows)
        for row in real_rows:
            self.assertIn("生命周期", row)
            self.assertIn("盘面验证", row)
            self.assertIn("research_judgment", row)
            self.assertIn("证据裁判", row["semantic_evidence_card"])
            self.assertNotEqual(row["research_judgment"].get("证据状态"), "已有事实验证")
        self.assertEqual(report["decision"]["noise_or_unconfirmed"][0]["query"], "连板未映射")
        self.assertNotIn("旧逻辑证据卡：连板未映射", markdown)
        self.assertIn("## 今日研究任务队列", markdown)


if __name__ == "__main__":
    unittest.main()
