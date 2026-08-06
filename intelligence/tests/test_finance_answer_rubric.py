from __future__ import annotations

import unittest
import subprocess
import sys
import tempfile
import json
from pathlib import Path

from intelligence.eval.finance_answer_rubric import (
    EVIDENCE_FULL_CREDIT,
    evidence_marker_count,
    score_answer,
)


# 合成测试数据：数字与引用编号为夹具，不是真实财务事实。
# 保留原有全部论证内容，另补上数据锚点——rubric 的证据密度闸门要求「有据可依」
# 的维度必须看得到股票代码/日期/百分比/金额/引用编号，光有行话拿不到分。
STRONG_ANSWER = """
我会先按本地知识库和金融 repo 看，不把 web 当主来源。瑞华泰（688323）当前不是纯业绩
兑现股，而是 PI 膜国产替代的能力验证/事实验证之间，盘面已经经历 6 月 9 日、6 月 10 日
连续放量上涨，两日涨幅 12.4%、成交额放大到 8.6 亿，所以更像预期交易后的兑现分歧 [S1]。

证据分层看：L1 是 PI 膜、AI 散热、电子 PI、折叠屏这些产业叙事；L2 是公司主营高性能
聚酰亚胺薄膜、2026Q1 营收 3.2 亿但毛利率仅 18.7%、仍处亏损 [R1]；L3 是嘉兴产能、
热控 PI 量产供货，但中芯/台积电/CoWoS/TGV 已被公司 2026-05-21 互动易问答否认 [G1]；
L4 是金融 repo 里 2026-06-10 的强势异动和成交放大 [S2]。

反方审稿：第一，这是不是老预期？先进封装和商业航天已经被交易过且部分证伪。第二，
上涨空间有没有？有，但主要来自情绪二波或新的 L3 订单/客户/收入占比，不来自当前报表。
第三，一阶受益是热控 PI 和电子 PI，二阶要看 FPC/AI 散热产业链扩散；如果没有客户验证，
就容易利好兑现。

结论：可以观察，但高置信看涨不足。后续看 AI 散热订单、嘉兴产能利用率（当前 62%）、
毛利率能否回到 25% 以上、电子 PI 头部客户确认，以及双红题材是否继续扩散而不是缩量
冲高。（非投资建议）
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

    def test_jargon_shell_cannot_outscore_a_grounded_answer(self) -> None:
        """回归护栏：把 rubric 词表念一遍、但零事实的空壳，不得高过有据可依的真答案。

        修复前实测：191 字的空壳拿 91/100(A)，8720 字、13 个股票代码、28 条引用编号的
        真实题材答案只有 60/100(D)——指标与它声称要测的东西反相关，而低分还会经
        experience_cards 变成「避免同类扣分」规则，等于教系统去刷这套话术。
        """
        shell = (
            "本地知识库与金融 repo 优先。证据分层按 L1-L4 区分产业叙事、基本面、"
            "公司硬事实与盘面情绪。盘面阶段处于预期交易向兑现分歧过渡，需警惕退潮与"
            "利好兑现；量价上看双红、放量、缩量、扩散、承接与流动性。产业推导：上游、"
            "中游、下游传导，量价利润弹性。反方审稿：反证、风险、除非、证伪条件如下。"
            "结论可用性：建议关注，目标区间与止损位。个人方法论贴合：符合边际变化与"
            "预期差框架。"
        )

        shell_score = score_answer("液冷服务器", shell, question_type="theme_analysis")
        real_score = score_answer("瑞华泰还有上涨空间吗", STRONG_ANSWER)

        self.assertEqual(evidence_marker_count(shell), 0)
        self.assertGreaterEqual(evidence_marker_count(STRONG_ANSWER), EVIDENCE_FULL_CREDIT)
        self.assertLess(shell_score.percent, real_score.percent)
        self.assertIn(shell_score.grade, {"D", "F"})
        # 闸门必须在「有据可依」的维度上生效，而不是靠别处凑分数
        for key in ("evidence_layering", "market_stage", "industry_reasoning"):
            self.assertEqual(shell_score.dimension(key).score, 0, key)

    def test_dimensions_not_applicable_to_question_type_are_dropped(self) -> None:
        """题型结构上不产出的维度整维剔除，不计入满分——对不存在的东西要证据是范畴错误。"""
        scored = score_answer("什么是液冷服务器", STRONG_ANSWER, question_type="concept_definition")

        keys = [d.key for d in scored.dimensions]
        self.assertNotIn("market_stage", keys)
        self.assertNotIn("actionability", keys)
        self.assertEqual(scored.max_score, 100 - 20 - 10)

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

        self.assertEqual(proc.returncode, 0)  # 评分仅供审稿，显式保存卡片仍由人工决定。
        self.assertEqual(payload["experience_card_path"], str(card_path))
        self.assertEqual(payload["role"], "advisory_review")
        self.assertFalse(payload["decision_eligible"])
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


class EvidenceMarkerCJKBoundaryTests(unittest.TestCase):
    """证据标记必须在「中文紧贴数字」的真实写法下也能命中。

    起因（2026-08-06 实测）：三次真实 run 的自评都是 12/100（F），评分器报
    「只有关键词、缺股票代码/日期/引用编号」，但答案正文里明明有 603267、
    2026-06-03、[W5]。

    根因**不是**评分器读了另一段文本，而是正则的词边界在 CJK 里失效：
    Python 的 ``\\w`` 包含中文，所以「技」和「6」之间**不存在** ``\\b``，
    ``r"\\b\\d{6}\\b"`` 在「川环科技603267在」里直接失配。中文财经文本不会在
    数字两侧加空格，于是 stock_code 与 iso_date 两个模式在真实答案里恒为 0，
    证据密度闸门（``EVIDENCE_GATED_KEYS``）把五个维度全压到低分。

    可迁移教训：**别在混排 CJK 的文本上用 ``\\b``**。同样的坑存在于分词、
    高亮、敏感词匹配、日志抽取——凡是中英数混排的中文语料都要用显式环视
    （``(?<!\\d)`` / ``(?!\\d)``）代替词边界。
    """

    # 中文紧贴数字，无空格——这是真实答案的写法
    CJK_TIGHT = "川环科技603267在2026-06-03的公告显示，营收12.4亿元，毛利率31.2% [G1][W5]"
    # 同样内容，数字两侧留空格
    SPACED = "川环科技 603267 在 2026-06-03 的公告显示，营收 12.4 亿元，毛利率 31.2% [G1][W5]"

    def test_cjk_tight_and_spaced_writing_count_the_same(self) -> None:
        """紧贴写法与空格写法必须给出同一个标记数——差异只来自排版，不是证据密度。"""
        self.assertEqual(
            evidence_marker_count(self.CJK_TIGHT),
            evidence_marker_count(self.SPACED),
        )

    def test_stock_code_and_iso_date_hit_when_glued_to_chinese(self) -> None:
        """紧贴中文的股票代码与 ISO 日期必须被识别（修复前这两项恒为 0）。"""
        count = evidence_marker_count(self.CJK_TIGHT)
        # 6 项：stock_code + iso_date + citation×2 + percent + amount
        self.assertGreaterEqual(count, 6)

    def test_grounded_cjk_answer_is_not_gated_like_an_empty_shell(self) -> None:
        """带真实锚点的中文答案，不该和零事实空壳落到同一档证据密度。"""
        shell = "科技方向都不错，可以关注，注意风险。"
        self.assertEqual(evidence_marker_count(shell), 0)
        self.assertGreater(evidence_marker_count(self.CJK_TIGHT), 0)

    def test_word_boundary_regex_would_fail_this_case(self) -> None:
        """变异测试：把模式换回 ``\\b`` 版本，本用例必须失败。

        没有这条，任何人「顺手」把环视改回 ``\\b`` 都不会有测试变红——
        而那正是本次 bug 的形态。
        """
        import re

        glued = "川环科技603267在2026-06-03的公告"
        # 旧写法：CJK 侧无词边界 → 失配
        self.assertEqual(re.findall(r"\b\d{6}\b", glued), [])
        self.assertEqual(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", glued), [])
        # 新写法：显式数字环视 → 命中
        self.assertEqual(re.findall(r"(?<!\d)\d{6}(?!\d)", glued), ["603267"])
        self.assertEqual(
            re.findall(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)", glued), ["2026-06-03"]
        )

    def test_long_digit_runs_are_not_sliced_into_fake_codes(self) -> None:
        """环视不能放水：7 位以上纯数字串不得被截出一个 6 位「股票代码」。"""
        self.assertEqual(evidence_marker_count("流水号1234567"), 0)
        self.assertEqual(evidence_marker_count("订单号12345678"), 0)


if __name__ == "__main__":
    unittest.main()
