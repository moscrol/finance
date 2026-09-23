import tempfile
import unittest
from pathlib import Path

from intelligence.services.ima_gap_report import build_ima_gap_report, classify_page


class ImaGapReportTest(unittest.TestCase):
    def test_classify_page_depths(self):
        self.assertEqual(classify_page(""), "missing")
        stub = "---\ntags: [\"待补证\"]\n---\n# 壳\n占位概念页：x\n## 待补证定义\n"
        self.assertEqual(classify_page(stub), "stub")
        thin = "---\ntags: [AIGC, ConceptCard]\n---\n# AIGC\n一句话。\n## 产业链位置\n上游。\n## 相关概念\n[[AI]]\n"
        self.assertEqual(classify_page(thin), "thin_card")
        l1 = "---\ntitle: 通信设备\n---\n# 通信设备\n" + "\n".join(
            ["x"] * 20 + ["## 核心机制", "正文", "## 产业链", "链", "## 关键公司", "表"]
        )
        self.assertEqual(classify_page(l1), "l1")
        deep = "---\ntags: [ima_deep_dive]\nsources: [\"[[种植业_DeepDive_ThemeRadar_20260829]]\"]\n---\n# 种植业\n"
        self.assertEqual(classify_page(deep), "has_deepdive")
        polyester = (
            "---\ntitle: 涤纶\n---\n# 涤纶\n"
            "下游纤维篮。完整 15 章必须先有 IMA；本次不伪造 15 章。\n"
        )
        self.assertEqual(classify_page(polyester), "l1")

    def test_queue_splits_run_and_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            (wiki / "concepts").mkdir(parents=True)
            (wiki / "entities").mkdir()
            (wiki / "sources").mkdir()
            (wiki / "concepts" / "种植业.md").write_text(
                "---\ntags: [种植业]\n---\n# 种植业\n相关概念\n[[种业]]\n",
                encoding="utf-8",
            )
            (wiki / "concepts" / "医药.md").write_text(
                "---\ntags: [\"待补证\"]\n---\n# 医药\n占位概念页：x\n## 待补证定义\n",
                encoding="utf-8",
            )
            (wiki / "concepts" / "通信设备.md").write_text(
                "---\ntitle: 通信设备\n---\n# 通信设备\n"
                + "\n".join(["行"] * 25 + ["## 核心机制", "机制", "## 产业链", "链", "## 关键公司", "公司"]),
                encoding="utf-8",
            )
            (wiki / "concepts" / "医疗服务.md").write_text(
                "---\ntitle: 医疗服务\n---\n# 医疗服务\n一句话。\n## 产业链位置\n上游。\n",
                encoding="utf-8",
            )
            (wiki / "concepts" / "涤纶.md").write_text(
                "---\ntitle: 涤纶\n---\n# 涤纶\n下游纤维篮。本次不伪造 15 章。\n",
                encoding="utf-8",
            )
            (wiki / "entities" / "众兴菌业.md").write_text("# 众兴菌业\n", encoding="utf-8")
            payload = {
                "date": "2026-08-28",
                "today_do_ima": [
                    {"目标": "种植业", "优先级": 133, "强势股": ["众兴菌业", "海南橡胶"]},
                    {"目标": "医药", "优先级": 123, "强势股": ["千金药业"]},
                    {"目标": "通信设备", "优先级": 180, "强势股": []},
                    {"目标": "医疗服务", "优先级": 90, "强势股": ["万邦医药"]},
                    {"目标": "涤纶", "优先级": 80, "强势股": ["天富龙"]},
                ],
                "today_find_official_evidence": [
                    {"目标": "化工", "优先级": 170, "强势股": ["多氟多"]},
                ],
            }
            report = build_ima_gap_report(payload, wikis=[wiki], date="2026-08-28")
            by_theme = {row["theme"]: row["action"] for row in report["themes"]}
            self.assertEqual(by_theme["种植业"], "run_deepdive")
            self.assertEqual(by_theme["医药"], "skip_mega")
            self.assertEqual(by_theme["通信设备"], "skip_have_l1")
            self.assertEqual(by_theme["医疗服务"], "skip_mega")
            self.assertEqual(by_theme["涤纶"], "skip_have_l1")
            self.assertEqual(by_theme["化工"], "route_disclosure")
            by_stock = {row["company"]: row["action"] for row in report["stocks"]}
            self.assertEqual(by_stock["众兴菌业"], "run_stock_card")
            self.assertEqual(by_stock["海南橡胶"], "skip_no_entity")
            self.assertEqual(report["theme_run"], ["种植业"])


if __name__ == "__main__":
    unittest.main()
