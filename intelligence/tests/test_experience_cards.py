from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.eval.finance_answer_rubric import score_answer
from intelligence.services import experience_cards


class ExperienceCardTests(unittest.TestCase):
    def test_build_record_load_and_render_card(self) -> None:
        scored = score_answer(
            "科技细分里哪个方向还有上涨空间",
            "科技都很好，可以看好。（非投资建议）",
            local_sources=["market_feature_store"],
        )
        card = experience_cards.build_card_from_score(
            scored,
            corrected_principle="方向判断必须先定市场阶段，再拆证据层和反方。",
            applies_to=["题材方向判断", "上涨空间判断"],
            prompt_rule="回答板块空间问题时必须说明阶段、资金容量、证据层、反方、验证指标。",
            local_sources=["market_feature_store"],
            ts="2026-06-29T12:00:00+00:00",
        )

        self.assertEqual(card["question"], "科技细分里哪个方向还有上涨空间")
        self.assertIn("题材方向判断", card["applies_to"])
        self.assertTrue(card["failure_modes"])

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "experience_cards.jsonl"
            experience_cards.record_card(path, card)
            loaded, warn = experience_cards.load_cards(path)

        self.assertIsNone(warn)
        self.assertEqual(len(loaded), 1)
        selected = experience_cards.select_relevant_cards(loaded, "科技还有上涨空间吗")
        rendered = experience_cards.render_for_prompt(selected)
        self.assertIn("回答板块空间问题", rendered)
        self.assertIn("历史得分", rendered)

    def test_load_skips_bad_json_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cards.jsonl"
            path.write_text(
                "not-json\n"
                + json.dumps({"question": "Q", "prompt_rule": "R"}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            loaded, warn = experience_cards.load_cards(path)

        self.assertIsNone(warn)
        self.assertEqual([x["question"] for x in loaded], ["Q"])

    def test_deep_dive_query_matches_methodology_card_by_intent(self) -> None:
        cards = [
            {
                "question": "深挖裕太微",
                "answer_score": 60,
                "applies_to": ["个股深挖", "第一性原理", "产业链分析", "二阶导", "市场结构推演路径"],
                "prompt_rule": "个股深挖必须覆盖公司本体、产业链暴露、二阶导机会和市场结构生命周期。",
            }
        ]

        selected = experience_cards.select_relevant_cards(cards, "深挖汇成股份")
        rendered = experience_cards.render_for_prompt(selected)

        self.assertEqual(len(selected), 1)
        self.assertIn("产业链暴露", rendered)
        self.assertIn("二阶导", rendered)

    def test_full_review_terms_match_market_review_card_by_intent(self) -> None:
        cards = [
            {
                "question": "市场结构推演路径盘面分析硬性视角",
                "answer_score": 55,
                "applies_to": ["全量复盘映射", "申万一级映射", "周均线偏离度", "新高集群", "涨停结构", "个股流动性", "加权涨幅"],
                "prompt_rule": "个股回答必须覆盖周均线偏离度、申万一级映射、同题材新高、涨停结构、双红演变和加权涨幅。",
            }
        ]

        selected = experience_cards.select_relevant_cards(cards, "深挖汇成股份，要看申万一级和周均线偏离度")
        rendered = experience_cards.render_for_prompt(selected)

        self.assertEqual(len(selected), 1)
        self.assertIn("周均线偏离度", rendered)
        self.assertIn("申万一级", rendered)
        self.assertIn("加权涨幅", rendered)

    def test_daily_agent_terms_match_lifecycle_card_by_intent(self) -> None:
        cards = [
            {
                "question": "daily-agent 生命周期和盘面验证必须进入问答",
                "answer_score": 60,
                "applies_to": ["daily-agent底层逻辑", "逻辑-盘面匹配", "生命周期判断", "盘面验证"],
                "prompt_rule": "个股回答必须判断旧逻辑唤醒/新逻辑候选、盘面验证强弱和生命周期阶段。",
            }
        ]

        selected = experience_cards.select_relevant_cards(cards, "这个票用盘面验证和升温验证看一下")
        rendered = experience_cards.render_for_prompt(selected)

        self.assertEqual(len(selected), 1)
        self.assertIn("旧逻辑唤醒", rendered)
        self.assertIn("生命周期阶段", rendered)

    def test_reverse_market_reasoning_terms_match_card_by_intent(self) -> None:
        cards = [
            {
                "question": "盘面反向解读必须用第一性原理",
                "answer_score": 80,
                "applies_to": ["盘面反向解读", "第一性原理", "全量复盘映射", "市场真实选择", "强板块弱个股"],
                "prompt_rule": "个股回答必须解释全量复盘数据支持什么、反证什么，并判断市场奖励谁、抛弃谁、犹豫谁。",
            }
        ]

        selected = experience_cards.select_relevant_cards(cards, "盘面反向的解读欠缺，没有第一性原理")
        rendered = experience_cards.render_for_prompt(selected)

        self.assertEqual(len(selected), 1)
        self.assertIn("支持什么、反证什么", rendered)
        self.assertIn("市场奖励谁", rendered)

    def test_self_review_terms_match_quality_gate_card_by_intent(self) -> None:
        cards = [
            {
                "question": "回答质检器与用户影子反驳",
                "answer_score": 85,
                "applies_to": ["回答质检器", "用户影子反驳", "防模板化", "完整分析路径", "二阶导"],
                "prompt_rule": "最终输出前必须先检查是否漏视角，再模拟用户反问是否模板化、是否孤立看个股、证据是否够硬、是否找到更优表达。",
            }
        ]

        selected = experience_cards.select_relevant_cards(cards, "生成回答后需要质检，并让影子 agent 反驳模板化问题")
        rendered = experience_cards.render_for_prompt(selected)

        self.assertEqual(len(selected), 1)
        self.assertIn("回答质检器", rendered)
        self.assertIn("是否模板化", rendered)
        self.assertIn("更优表达", rendered)

    def test_sellside_winrate_query_matches_divergence_framework_card_by_intent(self) -> None:
        cards = [
            {
                "question": "晚间卖方与机构胜率发散框架",
                "answer_score": 85,
                "applies_to": ["晚间卖方发散", "机构胜率", "覆盖密度", "证据硬度", "盘面位置", "二阶导"],
                "prompt_rule": "晚间卖方回答必须用机构胜率、覆盖密度、证据硬度和盘面位置做交叉，分成优先发散、只作确认、反向谨慎。",
            }
        ]

        selected = experience_cards.select_relevant_cards(cards, "胜率高的机构在晚间卖方里推什么方向，做一下发散")
        rendered = experience_cards.render_for_prompt(selected)

        self.assertEqual(len(selected), 1)
        self.assertIn("机构胜率", rendered)
        self.assertIn("覆盖密度", rendered)
        self.assertIn("优先发散、只作确认、反向谨慎", rendered)

    def test_high_position_mainline_query_matches_rebuttal_framework_by_intent(self) -> None:
        cards = [
            {
                "question": "高位主线反证与生命周期框架",
                "answer_score": 85,
                "applies_to": ["高位主线反证", "边际预期", "产业瑕疵审查", "事件锚点", "主线生命周期", "拥挤度"],
                "prompt_rule": "回答 AI硬件/CPO/PCB/半导体等高位主线时，必须先看边际预期和流动性，再做产业瑕疵审查、事件锚点生命周期和缩量拥挤反证。",
            }
        ]

        selected = experience_cards.select_relevant_cards(cards, "AI硬件主线缩量后，CPO和PCB是不是兑现了")
        rendered = experience_cards.render_for_prompt(selected)

        self.assertEqual(len(selected), 1)
        self.assertIn("边际预期", rendered)
        self.assertIn("产业瑕疵审查", rendered)
        self.assertIn("缩量拥挤反证", rendered)

    def test_analysis_path_query_matches_entrypoint_framework_by_intent(self) -> None:
        cards = [
            {
                "question": "个股与题材完整分析路径",
                "answer_score": 85,
                "applies_to": ["个股完整分析路径", "公司本体", "产业链暴露", "逻辑生命周期四问", "市场价值成绩单", "二阶导"],
                "prompt_rule": "回答个股/题材必须覆盖公司本体、产业链暴露、证据层、大盘流动性、市场风格、行业容量、题材结构、个股相对强度、生命周期四问、市场价值成绩单、二阶导和条件化结论。",
            }
        ]

        selected = experience_cards.select_relevant_cards(cards, "这套分析路径固定了吗，生命周期四问和市场价值也要有")
        rendered = experience_cards.render_for_prompt(selected)

        self.assertEqual(len(selected), 1)
        self.assertIn("公司本体", rendered)
        self.assertIn("生命周期四问", rendered)
        self.assertIn("市场价值", rendered)

    def test_customer_revenue_lifecycle_terms_match_feikai_template_by_intent(self) -> None:
        cards = [
            {
                "question": "飞凯材料补齐版优秀样板",
                "answer_score": 88,
                "applies_to": ["客户证据硬度表", "收入结构", "板块生命周期", "强反证", "个股深挖"],
                "prompt_rule": "深挖多逻辑个股时，必须补客户证据表、收入结构与财务传导、板块生命周期判断和强反证压力。",
            }
        ]

        selected = experience_cards.select_relevant_cards(cards, "补齐客户证据表、收入结构、板块生命周期判断和更强反证")
        rendered = experience_cards.render_for_prompt(selected)

        self.assertEqual(len(selected), 1)
        self.assertIn("客户证据表", rendered)
        self.assertIn("收入结构", rendered)
        self.assertIn("强反证", rendered)


class ResidentCardTests(unittest.TestCase):
    def test_methodology_cards_are_resident_even_without_query_match(self) -> None:
        cards = [
            {
                "ts": "2026-08-01T00:00:00",
                "question": "无关问题",
                "promotion": "methodology",
                "prompt_rule": "结论必须带成立条件",
                "applies_to": ["条件化结论"],
            },
            {
                "ts": "2026-08-02T00:00:00",
                "question": "液冷怎么看",
                "promotion": "candidate",
                "prompt_rule": "液冷要看渗透率",
                "applies_to": ["液冷"],
            },
        ]
        resident = experience_cards.select_resident_cards(cards)
        self.assertEqual(len(resident), 1)
        self.assertEqual(resident[0]["promotion"], "methodology")
        merged = experience_cards.merge_cards_for_prompt(
            resident,
            experience_cards.select_relevant_cards(cards, "固态电池近况"),
        )
        self.assertEqual(merged[0]["promotion"], "methodology")


if __name__ == "__main__":
    unittest.main()
