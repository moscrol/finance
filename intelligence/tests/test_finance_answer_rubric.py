from __future__ import annotations

import unittest
import subprocess
import sys
import tempfile
import json
from pathlib import Path

from intelligence.eval.finance_answer_rubric import score_answer


STRONG_ANSWER = """
我会先按本地知识库和金融 repo 看，不把 web 当主来源。瑞华泰当前不是纯业绩兑现股，
而是 PI 膜国产替代的能力验证/事实验证之间，盘面已经经历 6 月 9 日、10 日连续放量上涨，
所以更像预期交易后的兑现分歧。

证据分层看：L1 是 PI 膜、AI 散热、电子 PI、折叠屏这些产业叙事；L2 是公司主营高性能
聚酰亚胺薄膜、2025 和 2026Q1 仍亏损；L3 是嘉兴产能、热控 PI 量产供货，但中芯/台积电/
CoWoS/TGV 已被公司互动易否认；L4 是金融 repo 里的强势异动和成交放大。

反方审稿：第一，这是不是老预期？先进封装和商业航天已经被交易过且部分证伪。第二，
上涨空间有没有？有，但主要来自情绪二波或新的 L3 订单/客户/收入占比，不来自当前报表。
第三，一阶受益是热控 PI 和电子 PI，二阶要看 FPC/AI 散热产业链扩散；如果没有客户验证，
就容易利好兑现。

结论：可以观察，但高置信看涨不足。后续看 AI 散热订单、嘉兴产能利用率、毛利率改善、
电子 PI 头部客户确认，以及双红题材是否继续扩散而不是缩量冲高。（非投资建议）
"""


WEAK_ANSWER = """
瑞华泰是 PI 膜龙头，AI 散热和先进封装空间很大，最近市场关注度很高，
我认为后面还有上涨空间，可以继续看好。（非投资建议）
"""


class FinanceAnswerRubricTests(unittest.TestCase):
    def test_strong_finance_answer_gets_high_score_with_dimension_breakdown(self) -> None:
        scored = score_answer(
            "瑞华泰还有上涨空间吗",
            STRONG_ANSWER,
            local_sources=["knowledge-base-private", "market_feature_store"],
        )

        self.assertGreaterEqual(scored.total_score, 80)
        self.assertEqual(scored.grade, "A")
        self.assertFalse(scored.failures)
        self.assertEqual(scored.dimension("local_data_priority").score, 15)
        self.assertEqual(
            [d.key for d in scored.dimensions],
            [
                "local_data_priority",
                "evidence_layering",
                "market_stage",
                "industry_reasoning",
                "critic_review",
                "actionability",
                "personal_methodology",
            ],
        )
        self.assertTrue(any("L1-L4" in d.reason for d in scored.dimensions))

    def test_weak_answer_is_penalized_for_missing_financial_reasoning(self) -> None:
        scored = score_answer("瑞华泰还有上涨空间吗", WEAK_ANSWER)

        self.assertLess(scored.total_score, 55)
        self.assertIn(scored.grade, {"D", "F"})
        joined = "\n".join(scored.failures)
        self.assertIn("证据分层", joined)
        self.assertIn("盘面阶段", joined)
        self.assertIn("反方审稿", joined)

    def test_local_source_bonus_requires_actual_local_reference_in_answer(self) -> None:
        scored = score_answer(
            "瑞华泰怎么看",
            WEAK_ANSWER,
            local_sources=["knowledge-base-private", "market_feature_store"],
        )

        dim = scored.dimension("local_data_priority")
        self.assertLess(dim.score, dim.max_score)
        self.assertIn("未体现本地", dim.reason)

    def test_personal_methodology_rewards_fupanhui_system_principles(self) -> None:
        answer = (
            "先按全量盘面体系看：资金推动价格，量能决定周期。市场层看 20日量能回归，"
            "再看情绪、结构、行业聚散度；板块层看成交占比环比是否持续提升；"
            "个股层再确认龙头、新高、量价结构和产业逻辑。这个票目前更像顶部横盘后的"
            "高位承接分歧，不应只因为题材好就外推上涨。（非投资建议）"
        )

        scored = score_answer("瑞华泰怎么看", answer)

        dim = scored.dimension("personal_methodology")
        self.assertEqual(dim.score, dim.max_score)
        self.assertIn("资金推动价格", dim.hits)
        self.assertIn("成交占比环比", dim.hits)

    def test_cli_scores_answer_file_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            answer_path = Path(tmp) / "answer.md"
            answer_path.write_text(STRONG_ANSWER, encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "intelligence.cli",
                    "answer-score",
                    "--question",
                    "瑞华泰还有上涨空间吗",
                    "--answer-file",
                    str(answer_path),
                    "--local-source",
                    "knowledge-base-private",
                    "--local-source",
                    "market_feature_store",
                    "--json",
                ],
                cwd=Path(__file__).resolve().parents[2],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('"grade": "A"', proc.stdout)
        self.assertIn("local_data_priority", proc.stdout)

    def test_cli_can_save_experience_card(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            answer_path = Path(tmp) / "answer.md"
            card_path = Path(tmp) / "cards.jsonl"
            answer_path.write_text(WEAK_ANSWER, encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "intelligence.cli",
                    "answer-score",
                    "--question",
                    "科技细分里哪个方向还有上涨空间",
                    "--answer-file",
                    str(answer_path),
                    "--local-source",
                    "market_feature_store",
                    "--save-card",
                    "--card-file",
                    str(card_path),
                    "--corrected-principle",
                    "方向判断必须先定市场阶段，再拆证据层和反方。",
                    "--prompt-rule",
                    "回答板块空间问题时必须说明阶段、证据层和反方。",
                    "--applies-to",
                    "题材方向判断",
                    "--json",
                ],
                cwd=Path(__file__).resolve().parents[2],
                text=True,
                capture_output=True,
                check=False,
            )

            payload = json.loads(proc.stdout)
            rows = [json.loads(line) for line in card_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(proc.returncode, 1)  # 低分仍保留评分退出码，但卡片已保存。
        self.assertEqual(payload["experience_card_path"], str(card_path))
        self.assertEqual(rows[0]["question"], "科技细分里哪个方向还有上涨空间")
        self.assertIn("回答板块空间问题", rows[0]["prompt_rule"])

    def test_bundled_golden_examples_score_in_expected_ranges(self) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "eval"
            / "cases"
            / "finance_answer_rubric_cases.json"
        )
        doc = json.loads(path.read_text(encoding="utf-8"))

        for case in doc["cases"]:
            scored = score_answer(
                case["question"],
                case["answer"],
                local_sources=list(case.get("local_sources") or []),
            )
            if "expected_min_score" in case:
                self.assertGreaterEqual(scored.total_score, case["expected_min_score"], case["id"])
            if "expected_max_score" in case:
                self.assertLessEqual(scored.total_score, case["expected_max_score"], case["id"])


if __name__ == "__main__":
    unittest.main()
