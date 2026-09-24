import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

from intelligence.paths import ProjectPaths
from intelligence.runner import run_command_step
from intelligence.services.ima_gap_report import build_ima_gap_report, classify_page
from intelligence.workflows.daily_review import DailyReviewOptions, build_daily_review_plan


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


@pytest.mark.parametrize("queue_state", ["missing", "empty", "populated", "invalid_json"])
def test_cli_status_reaches_real_workflow_runner(tmp_path, queue_state):
    paths = ProjectPaths(tmp_path, tmp_path / "wiki", tmp_path / "site", tmp_path / "snapshot", tmp_path / "index")
    (paths.knowledge_wiki / "concepts").mkdir(parents=True)
    (paths.knowledge_wiki / "entities").mkdir()
    (paths.knowledge_wiki / "sources").mkdir()
    paths.market_exports.mkdir(parents=True)
    day = "2026-09-18"
    queue = paths.market_exports / f"{day}-research-queue.json"
    if queue_state != "missing":
        payload = {"date": day, "today_do_ima": [], "today_find_official_evidence": []}
        if queue_state == "populated":
            (paths.knowledge_wiki / "concepts" / "test-theme.md").write_text("# test-theme\n", encoding="utf-8")
            payload["today_do_ima"].append({"目标": "test-theme", "优先级": 100, "强势股": []})
        queue.write_text("{" if queue_state == "invalid_json" else json.dumps(payload), encoding="utf-8")

    spec = next(s for s in build_daily_review_plan(
        DailyReviewOptions(date=day, skip_sync=True, plan="full"), paths,
    ) if s.name == "ima-gap-report")
    code_root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(code_root), "FINANCE_WS": str(tmp_path),
           "KB_VAULT": str(paths.knowledge_wiki)}
    step = run_command_step(
        spec.name, [sys.executable, *spec.argv[1:]], cwd=tmp_path,
        outputs=spec.outputs, env=env, timeout_sec=30,
    )
    if queue_state in {"missing", "invalid_json"}:
        assert step.status == "FAIL"
        assert step.returncode not in (None, 0)
        assert step.errors
        assert not any(Path(p).exists() for p in spec.outputs)
        if queue_state == "missing":
            result = json.loads("\n".join(step.stdout_tail))
            assert result["ok"] is False
            assert str(queue) in result["error"]
    else:
        assert step.status == "PASS"
        assert step.returncode == 0
        assert not step.errors
        assert all(Path(p).is_file() for p in spec.outputs)
        report = json.loads(Path(spec.outputs[0]).read_text(encoding="utf-8"))
        assert report["theme_run"] == (["test-theme"] if queue_state == "populated" else [])


if __name__ == "__main__":
    unittest.main()
