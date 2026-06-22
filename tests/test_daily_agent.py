import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence.paths import ProjectPaths
from intelligence.services import kb_rag
from intelligence.workflows.daily_agent import DailyAgentOptions, render_daily_agent_html, run_daily_agent


class DailyAgentTest(unittest.TestCase):
    def make_fixture(self, root: Path) -> ProjectPaths:
        finance = root / "finance"
        exports = finance / "market_feature_store" / "exports"
        daily_dir = finance / "复盘" / "daily" / "2026-06-11"
        wiki = root / "wiki"
        relations = wiki / "relations"
        sources = wiki / "sources"
        briefings = wiki / "briefings"
        exports.mkdir(parents=True)
        daily_dir.mkdir(parents=True)
        relations.mkdir(parents=True)
        sources.mkdir(parents=True)
        briefings.mkdir(parents=True)

        for path in [
            exports / "2026-06-11-daily-review.md",
            exports / "2026-06-11-theme-candidates.md",
            exports / "2026-06-11-theme-backfill-queue.json",
            exports / "2026-06-11-theme-backfill-review-queue.json",
            exports / "2026-06-11-theme-backfill-review-queue.md",
            daily_dir / "2026-06-11-daily-review.html",
            daily_dir / "2026-06-11-theme-candidates.html",
            exports / "2026-06-11-daily-workflow-summary.json",
        ]:
            path.write_text("ok\n", encoding="utf-8")
        (exports / "2026-06-11-advancers-ma5.png").write_bytes(b"png")

        (briefings / "2026-06-11.md").write_text("# 晨汇\n", encoding="utf-8")
        (exports / "2026-06-11-theme-candidates.json").write_text(
            json.dumps(
                {
                    "found": True,
                    "trade_date": "2026-06-11",
                    "candidates": [
                        {
                            "market_theme": "液冷服务器",
                            "canonical_concept": "液冷服务器",
                            "priority_score": 88,
                            "trigger_types": ["double_red"],
                            "market_evidence": {
                                "strong_stocks": [
                                    {"stock_name": "强瑞技术", "stock_ts_code": "301128.SZ", "pct_chg": 12.3}
                                ]
                            },
                        },
                        {
                            "market_theme": "连板未映射",
                            "canonical_concept": "连板未映射",
                            "priority_score": 80,
                            "trigger_types": ["limit_heat"],
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (relations / "concept_graph.json").write_text(
            json.dumps({"concepts": {"液冷服务器": {"sources": ["[[液冷服务器深度报告]]"]}}}, ensure_ascii=False),
            encoding="utf-8",
        )
        (relations / "entity_exposures.json").write_text(
            json.dumps(
                {
                    "entities": {
                        "强瑞技术": {
                            "codes": ["301128"],
                            "concepts": {"液冷服务器": {"strength": "core", "role": "液冷测试设备"}},
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (relations / "evidence_index.json").write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "target": "液冷服务器",
                            "evidence": "液冷服务器需求提升。",
                            "source": "[[液冷服务器深度报告]]",
                            "source_date": "2026-06-01",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (relations / "theme_signals.json").write_text("{}", encoding="utf-8")
        (relations / "catalyst_calendar.json").write_text("{}", encoding="utf-8")
        (relations / "mention_frequency.json").write_text("{}", encoding="utf-8")
        (sources / "液冷服务器深度报告.md").write_text("# source\n", encoding="utf-8")
        return ProjectPaths(finance_root=finance, knowledge_wiki=wiki, finance_site=root / "site")

    def test_daily_agent_summarizes_daily_surfaces_and_logic_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_fixture(Path(tmp))

            summary, report, markdown = run_daily_agent(
                DailyAgentOptions(
                    date="2026-06-11",
                    finance_root=paths.finance_root,
                    kb_wiki=paths.knowledge_wiki,
                    top_per_date=2,
                )
            )

            self.assertIn(summary.status, {"PASS", "WARN"})
            self.assertEqual(report["date"], "2026-06-11")
            self.assertEqual(report["ledger"]["status"], "PASS")
            self.assertEqual(report["logic_batch"]["summary"]["old_logic_wakeup_count"], 1)
            self.assertEqual(report["decision"]["old_logic_wakeup"][0]["query"], "液冷服务器")
            self.assertEqual(report["decision"]["noise_or_unconfirmed"][0]["query"], "连板未映射")
            self.assertIn("## 今日判断", markdown)
            self.assertIn("液冷服务器", markdown)
            self.assertIn("连板未映射", markdown)
            self.assertNotIn("旧逻辑证据卡：连板未映射", markdown)

    def test_daily_agent_builds_chinese_semantic_evidence_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_fixture(Path(tmp))
            fake_rag = kb_rag.WikiRagResult(
                ok=True,
                hits=[
                    kb_rag.WikiHit(
                        page_id="液冷服务器_DeepDive",
                        file_path="wiki/sources/液冷服务器_DeepDive_数据抽取.md",
                        title="液冷服务器_DeepDive_数据抽取",
                        score=0.42,
                        excerpt="液冷服务器旧逻辑主线来自 AI 算力密度提升。",
                    )
                ],
            )

            with mock.patch("intelligence.workflows.daily_agent.kb_rag.retrieve", return_value=fake_rag):
                summary, report, markdown = run_daily_agent(
                    DailyAgentOptions(
                        date="2026-06-11",
                        finance_root=paths.finance_root,
                        kb_wiki=paths.knowledge_wiki,
                        top_per_date=2,
                        semantic_rag_top_n=1,
                    )
                )

            self.assertIn(summary.status, {"PASS", "WARN"})
            row = report["decision"]["old_logic_wakeup"][0]
            card = row["semantic_evidence_card"]
            self.assertEqual(card["标题"], "旧逻辑证据卡：液冷服务器")
            self.assertEqual(card["结构化检查"]["概念"], "已命中")
            self.assertEqual(card["向量旧材料"]["命中数量"], 1)
            self.assertEqual(card["命中材料"][0]["类型"], "旧深度研究")
            self.assertEqual(card["命中材料"][0]["作用"], "旧逻辑主线")
            self.assertIn("可以进入题材地图/深度研究", card["下一步"])
            self.assertIn("## 逻辑证据卡", markdown)
            self.assertIn("结构化：概念=已命中", markdown)
            self.assertIn("回溯：已命中来源页", markdown)

            html = render_daily_agent_html(report, markdown)
            self.assertIn("马上看：旧逻辑唤醒", html)
            self.assertIn("需要回补：概念 / 公司 / 证据 / 来源", html)
            self.assertIn("逻辑证据卡", html)
            self.assertIn("evidence-card", html)
            self.assertNotIn("<pre>", html)


if __name__ == "__main__":
    unittest.main()
