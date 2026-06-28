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
        self.assertEqual([row["query"] for row in report["decision"]["old_logic_wakeup"]], ["液冷服务器"])
        self.assertEqual(report["decision"]["new_logic_candidate"], [])
        self.assertEqual(report["decision"]["data_gap"], [])
        self.assertEqual([row["query"] for row in report["decision"]["noise_or_unconfirmed"]], ["连板未映射"])

        row = report["decision"]["old_logic_wakeup"][0]
        self.assertEqual(row["route"], "题材地图 / 深度研究")
        self.assertEqual(row["生命周期"]["生命周期阶段"], "升温验证")
        self.assertEqual(row["生命周期"]["连续出现天数"], 2)
        self.assertEqual(row["生命周期"]["priority变化"], 18.0)
        self.assertEqual(row["生命周期"]["当前触发信号"], ["double_red", "limit_heat"])
        self.assertEqual(row["盘面验证"]["盘面验证强度"], "中等验证")
        self.assertEqual(row["盘面验证"]["当前盘面"]["涨停数"], 2)
        self.assertEqual(row["盘面验证"]["当前盘面"]["强势股数"], 1)
        self.assertEqual(row["盘面验证"]["边际变化"]["涨停变化"], 1)
        self.assertEqual(row["research_judgment"]["证据状态"], "能力栈候选")
        self.assertEqual(row["research_judgment"]["已有证据层"], ["L0 图谱登记", "L2 官方基线", "L4 盘面验证"])
        self.assertEqual(row["research_judgment"]["缺失证据层"], ["L3 官方验证"])
        self.assertNotEqual(row["research_judgment"].get("证据状态"), "已有事实验证")

        card = row["semantic_evidence_card"]
        self.assertEqual(card["标题"], "旧逻辑证据卡：液冷服务器")
        self.assertEqual(card["当前判断"], "旧逻辑唤醒")
        self.assertEqual(card["结构化检查"]["来源回溯"], "未发现缺口")
        self.assertEqual(card["向量旧材料"], {"状态": "未补", "检索词": "-", "命中数量": 0})
        self.assertEqual(card["证据裁判"]["证据状态"], "能力栈候选")
        self.assertEqual(card["证据裁判"]["缺失证据层"], ["L3 官方验证"])
        self.assertEqual(card["综合判断"], "未补语义证据")
        self.assertEqual(report["research_queue"]["summary"], {
            "today_do_ima": 0,
            "today_find_official_evidence": 1,
            "today_wait_market_validation": 0,
            "today_downgrade_or_watch": 0,
            "total": 1,
            "skipped": 1,
        })
        self.assertEqual(report["research_queue"]["today_find_official_evidence"][0]["目标"], "液冷服务器")
        self.assertIn("年报/F10 只证明能力栈：液冷服务器", "\n".join(report["next_actions"]))
        self.assertNotIn("旧逻辑证据卡：连板未映射", markdown)
        self.assertIn("## 今日研究任务队列", markdown)


if __name__ == "__main__":
    unittest.main()
