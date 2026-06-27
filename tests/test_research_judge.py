import json
import tempfile
import unittest
from pathlib import Path

from intelligence.services.research_judge import judge_research_target


class ResearchJudgeTest(unittest.TestCase):
    def make_wiki(self, root: Path) -> Path:
        wiki = root / "wiki"
        relations = wiki / "relations"
        relations.mkdir(parents=True)
        (relations / "entity_exposures.json").write_text(
            json.dumps(
                {
                    "entities": {
                        "贝达药业": {
                            "codes": ["300558"],
                            "concepts": {"创新药": {"strength": "core", "role": "创新药管线"}},
                        },
                        "铭普光磁": {
                            "codes": ["002902"],
                            "concepts": {"AI服务器电源": {"strength": "core", "role": "磁性元件/电源"}},
                        },
                        "阿石创": {
                            "codes": ["300706"],
                            "concepts": {"靶材": {"strength": "core", "role": "PVD 镀膜材料"}},
                        },
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (relations / "concept_graph.json").write_text(
            json.dumps(
                {
                    "concepts": {
                        "创新药": {},
                        "AI服务器电源": {},
                        "靶材": {},
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
                            "target": "贝达药业",
                            "concept": "创新药",
                            "evidence_layer": "L2",
                            "update_type": "annual_report_baseline",
                            "source_quality": "official_disclosure",
                            "source": "[[贝达药业 2025年年度报告 baseline]]",
                            "evidence": "年报披露创新药研发管线和商业化进展。",
                        },
                        {
                            "target": "铭普光磁",
                            "concept": "AI服务器电源",
                            "evidence_layer": "L2",
                            "update_type": "annual_report_baseline",
                            "source_quality": "official_disclosure",
                            "source": "[[铭普光磁 2025年年度报告 baseline]]",
                            "evidence": "年报披露磁性元件、光通信和电源相关业务。",
                        },
                        {
                            "target": "铭普光磁",
                            "concept": "AI服务器电源",
                            "evidence_layer": "L1_L3_candidate",
                            "update_type": "ima_hard_delta_review",
                            "source_quality": "ima_composite",
                            "source": "[[铭普光磁 IMA 个股逻辑]]",
                            "evidence": "IMA 提到 AI 服务器电源链条的硬事实候选。",
                        },
                        {
                            "target": "阿石创",
                            "concept": "靶材",
                            "evidence_layer": "L2",
                            "update_type": "f10_baseline",
                            "source_quality": "structured_profile",
                            "source": "[[阿石创 F10 baseline]]",
                            "evidence": "F10 显示公司主营 PVD 镀膜材料。",
                        },
                        {
                            "target": "阿石创",
                            "concept": "靶材",
                            "evidence_layer": "L1_L3_candidate",
                            "update_type": "ima_hard_delta_review",
                            "source_quality": "curated_research",
                            "source": "[[阿石创 IMA 个股逻辑]]",
                            "evidence": "IMA 提到先进制程靶材国产替代候选逻辑。",
                        },
                        {
                            "target": "光刻胶",
                            "source": "[[光刻胶_DeepDive_数据抽取_20260613]]",
                            "evidence": "DeepDive 记录了光刻胶旧逻辑和产业链公司。",
                        },
                        {
                            "target": "光刻胶",
                            "source": "[[iFinD baseline 2026-05-25]]",
                            "evidence": "iFinD baseline 记录相关公司主营业务。",
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return wiki

    def test_l2_annual_baseline_waits_for_fact_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            wiki = self.make_wiki(Path(tmp))

            judgment = judge_research_target("贝达药业", kb_wiki=wiki, concept="创新药")

            self.assertEqual(judgment["目标类型"], "公司")
            self.assertEqual(judgment["证据状态"], "能力栈候选")
            self.assertIn("L2 官方基线", judgment["已有证据层"])
            self.assertIn("L3 官方验证", judgment["缺失证据层"])
            self.assertIn("L4 盘面验证", judgment["缺失证据层"])
            self.assertIn("找公告", judgment["建议动作"])

    def test_l2_plus_ima_candidate_becomes_priority_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            wiki = self.make_wiki(Path(tmp))

            judgment = judge_research_target("铭普光磁", kb_wiki=wiki, concept="AI服务器电源")

            self.assertEqual(judgment["证据状态"], "重点验证")
            self.assertIn("L2 官方基线", judgment["已有证据层"])
            self.assertIn("L3 候选硬事实", judgment["已有证据层"])
            self.assertIn("L3 官方验证", judgment["缺失证据层"])
            self.assertIn("公告/互动/调研", judgment["建议动作"])
            self.assertTrue(any("候选硬事实" in reason for reason in judgment["不可升级原因"]))

    def test_f10_baseline_plus_candidate_is_not_treated_as_official_l3(self):
        with tempfile.TemporaryDirectory() as tmp:
            wiki = self.make_wiki(Path(tmp))

            judgment = judge_research_target("阿石创", kb_wiki=wiki, concept="靶材")

            self.assertEqual(judgment["证据状态"], "重点验证")
            self.assertIn("L2 基线", judgment["已有证据层"])
            self.assertIn("L3 候选硬事实", judgment["已有证据层"])
            self.assertIn("L3 官方验证", judgment["缺失证据层"])
            self.assertNotIn("已有事实验证", judgment["证据状态"])

    def test_legacy_unlayered_sources_are_mapped_to_readable_layers(self):
        with tempfile.TemporaryDirectory() as tmp:
            wiki = self.make_wiki(Path(tmp))

            judgment = judge_research_target("光刻胶", kb_wiki=wiki, has_market_signal=True)

            self.assertEqual(judgment["证据状态"], "能力栈候选")
            self.assertIn("L1 叙事线索", judgment["已有证据层"])
            self.assertIn("L2 基线", judgment["已有证据层"])
            self.assertIn("L4 盘面验证", judgment["已有证据层"])
            self.assertIn("L3 官方验证", judgment["缺失证据层"])


if __name__ == "__main__":
    unittest.main()
