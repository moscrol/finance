from __future__ import annotations

import json
import unittest
from unittest import mock

from intelligence.services import foresight
from intelligence.services.foresight import (
    ForesightOptions,
    Question,
    generate,
    rank_questions,
    render,
)


_DISTINCT = [
    "如果液冷服务器渗透率在2026Q4突破25%，中际旭创的毛利率拐点会怎样？",
    "美联储如果在9月转鸽，A股算力链的估值分位会先于盈利修复吗？",
    "固态电池量产时间表再次推迟的话，哪个上游材料会最先被杀逻辑？",
    "光模块涨价的领先指标是北美CAPEX还是国内招标节奏？",
    "如果AI从净通胀转向净通缩，哪类周期股会先反应？",
    "寒武纪国产替代叙事里，最被高估的二阶受益方是谁？",
    "工业富联的代工毛利率能不能证伪算力需求见顶？",
    "宏观流动性收紧时，高位成簇的新高方向会怎样扩散或退潮？",
]


def _canned_questions(n: int) -> str:
    items = [
        {
            "question": _DISTINCT[i % len(_DISTINCT)],
            "rationale": "把两个领域勾连，是市场没算的二阶账",
            "domains": ["AI算力", "宏观"],
            "leading_indicator": "北美云厂CAPEX指引 + 单机柜功率密度",
            "horizon": "2026Q4",
            "novelty": 0.6 + 0.03 * i,
            "relevance": 0.9 - 0.02 * i,
        }
        for i in range(n)
    ]
    return json.dumps({"questions": items}, ensure_ascii=False)


class RankingTests(unittest.TestCase):
    def test_rank_picks_top_n_by_combined_score(self) -> None:
        raw = [
            Question("甲问题完全不同的角度宏观流动性", novelty=0.9, relevance=0.9),
            Question("乙问题另一个独立角度固态电池", novelty=0.5, relevance=0.5),
            Question("丙问题第三个独立角度光模块价格", novelty=0.4, relevance=0.4),
        ]
        ranked = rank_questions(raw, asked=[], n=2)
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0].question, "甲问题完全不同的角度宏观流动性")
        self.assertTrue(all(q.score > 0 for q in ranked))

    def test_dedup_against_recent_questions(self) -> None:
        asked = ["液冷服务器渗透率拐点对毛利率意味着什么"]
        raw = [
            Question("液冷服务器渗透率拐点对毛利率意味着什么", novelty=0.9, relevance=0.9),
            Question("完全不一样的问题宏观流动性会如何收紧", novelty=0.4, relevance=0.4),
        ]
        ranked = rank_questions(raw, asked=asked, n=3)
        self.assertEqual(len(ranked), 1)
        self.assertIn("宏观流动性", ranked[0].question)

    def test_diversity_avoids_near_duplicate_candidates(self) -> None:
        raw = [
            Question("光模块涨价能持续到2026Q4吗领先指标是什么", novelty=0.9, relevance=0.9),
            Question("光模块涨价能持续到2026Q4吗领先指标究竟是什么", novelty=0.88, relevance=0.88),
            Question("固态电池量产时间表会不会再次推迟", novelty=0.6, relevance=0.6),
        ]
        ranked = rank_questions(raw, asked=[], n=2)
        self.assertEqual(len(ranked), 2)
        self.assertIn("固态电池", ranked[1].question)


class GenerateTests(unittest.TestCase):
    def test_generate_with_mocked_llm(self) -> None:
        with mock.patch.object(
            foresight.llm_refine,
            "complete",
            return_value=(_canned_questions(8), mock.Mock(name="deepseek"), ""),
        ) as patched:
            # mock provider .name
            patched.return_value[1].name = "deepseek"
            result = generate(ForesightOptions(n=3, candidates=8))
        self.assertTrue(result.llm_used)
        self.assertEqual(len(result.questions), 3)
        self.assertEqual(result.status, "PASS")
        out = render(result)
        self.assertIn("猜你想问", out)
        self.assertIn("1.", out)

    def test_generate_degrades_without_key(self) -> None:
        with mock.patch.object(
            foresight.llm_refine,
            "complete",
            return_value=(None, None, "未配置 LLM key"),
        ):
            result = generate(ForesightOptions(n=3))
        self.assertFalse(result.llm_used)
        self.assertEqual(result.questions, [])
        self.assertEqual(result.status, "WARN")
        self.assertTrue(result.prompt_preview)
        self.assertTrue(result.context_digest)
        out = render(result)
        self.assertIn("待发送提示词", out)
        self.assertIn("上下文摘要", out)

    def test_generate_handles_unparseable_llm_output(self) -> None:
        with mock.patch.object(
            foresight.llm_refine,
            "complete",
            return_value=("not json at all", mock.Mock(), ""),
        ):
            result = generate(ForesightOptions(n=3))
        self.assertFalse(result.llm_used)
        self.assertEqual(result.questions, [])


if __name__ == "__main__":
    unittest.main()
