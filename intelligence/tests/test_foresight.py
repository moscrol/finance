from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
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


def _provider(name: str) -> mock.Mock:
    m = mock.Mock()
    m.name = name
    return m


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
            return_value=(_canned_questions(8), _provider("deepseek"), ""),
        ):
            result = generate(ForesightOptions(n=3, candidates=8, use_memory=False))
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
            result = generate(ForesightOptions(n=3, use_memory=False))
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
            result = generate(ForesightOptions(n=3, use_memory=False))
        self.assertFalse(result.llm_used)
        self.assertEqual(result.questions, [])


class MemoryTests(unittest.TestCase):
    def test_append_then_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mem.jsonl")
            appended, warn = foresight.append_asked_memory(
                path,
                [Question("问题一宏观流动性", score=0.9), Question("问题二算力拐点", score=0.8)],
                trade_date="2026-06-11",
            )
            self.assertIsNone(warn)
            self.assertEqual(appended, 2)
            questions, load_warn = foresight.load_asked_memory(path)
            self.assertIsNone(load_warn)
            self.assertEqual(questions, ["问题一宏观流动性", "问题二算力拐点"])

    def test_load_missing_file_is_empty(self) -> None:
        questions, warn = foresight.load_asked_memory("/nonexistent/dir/mem.jsonl")
        self.assertEqual(questions, [])
        self.assertIsNone(warn)

    def test_load_window_keeps_most_recent(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mem.jsonl")
            for i in range(5):
                foresight.append_asked_memory(path, [Question(f"问题{i}独立角度")])
            questions, _ = foresight.load_asked_memory(path, window=2)
            self.assertEqual(questions, ["问题3独立角度", "问题4独立角度"])

    def test_generate_appends_selected_questions(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mem.jsonl")
            with mock.patch.object(
                foresight.llm_refine,
                "complete",
                return_value=(_canned_questions(8), _provider("deepseek"), ""),
            ):
                result = generate(ForesightOptions(n=3, candidates=8, memory_file=path))
            self.assertEqual(result.memory_appended, 3)
            self.assertEqual(result.memory_loaded, 0)
            stored, _ = foresight.load_asked_memory(path)
            self.assertEqual(len(stored), 3)

    def test_generate_dedups_against_memory(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mem.jsonl")
            foresight.append_asked_memory(path, [Question(_DISTINCT[0])])
            with mock.patch.object(
                foresight.llm_refine,
                "complete",
                return_value=(_canned_questions(8), _provider("deepseek"), ""),
            ):
                result = generate(ForesightOptions(n=8, candidates=8, memory_file=path))
            picked = [q.question for q in result.questions]
            self.assertEqual(result.memory_loaded, 1)
            self.assertNotIn(_DISTINCT[0], picked)


class KbThemesTests(unittest.TestCase):
    def _write_theme_signals(self, root: Path) -> None:
        (root / "relations").mkdir(parents=True, exist_ok=True)
        payload = {
            "updated": "2026-06-15",
            "version": 1,
            "themes": {
                "液冷服务器": {
                    "recognition_timeline": [
                        {"time_window": "2026-06-10", "recognition_stage": "★★★★"},
                    ],
                    "progress_ruler": [{"current_stage": "★★★", "stage_position": 60}],
                    "market_heat": ["噪声文本 / Tier 1"],
                },
                "固态电池": {
                    "recognition_timeline": [{"time_window": "2026-05-01", "recognition_stage": "★★"}],
                    "market_heat": ["Tier 3"],
                },
            },
        }
        (root / "relations" / "theme_signals.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def test_kb_themes_enter_context_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_theme_signals(root)
            context, digest, warnings = foresight.build_context(
                ForesightOptions(kb_wiki=str(root), use_memory=False, use_interactions=False)
            )
        names = [t["theme"] for t in context["kb_themes"]]
        self.assertEqual(names[0], "液冷服务器")
        self.assertEqual(context["kb_themes"][0]["stars"], 4)
        self.assertEqual(context["kb_themes"][0]["tier"], 1)
        self.assertTrue(any("知识库题材" in d for d in digest))
        self.assertEqual(context["_kb_wiki_path"], str(root))
        self.assertFalse(any("知识库题材未接入" in w for w in warnings))

    def test_missing_kb_degrades_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope"
            context, digest, warnings = foresight.build_context(
                ForesightOptions(kb_wiki=str(missing), use_memory=False, use_interactions=False)
            )
        self.assertEqual(context["kb_themes"], [])
        self.assertTrue(any("未接入" in d for d in digest))
        self.assertTrue(any("知识库题材未接入" in w for w in warnings))

    def test_no_kb_flag_skips_entirely(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_theme_signals(root)
            context, digest, warnings = foresight.build_context(
                ForesightOptions(
                    kb_wiki=str(root), use_kb=False, use_memory=False, use_interactions=False
                )
            )
        self.assertEqual(context["kb_themes"], [])
        self.assertIsNone(context["_kb_wiki_path"])
        self.assertFalse(any("知识库题材" in d for d in digest))
        self.assertFalse(any("知识库" in w for w in warnings))

    def test_generate_feeds_kb_themes_into_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_theme_signals(root)
            with mock.patch.object(
                foresight.llm_refine,
                "complete",
                return_value=(_canned_questions(8), _provider("deepseek"), ""),
            ):
                result = generate(
                    ForesightOptions(
                        kb_wiki=str(root), n=3, candidates=8, use_memory=False, use_interactions=False
                    )
                )
        self.assertEqual(result.kb_themes_loaded, 2)
        self.assertEqual(result.kb_wiki_path, str(root))
        # 题材进了发给 LLM 的提示词；本地路径不得泄漏
        self.assertIn("液冷服务器", result.prompt_preview)
        self.assertIn("kb_themes", result.prompt_preview)
        self.assertNotIn("_kb_wiki_path", result.prompt_preview)
        self.assertIn("调入 2 个题材", render(result))


class MethodologyTests(unittest.TestCase):
    def test_methodology_injected_into_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            meth = Path(tmp) / "m.md"
            meth.write_text("分级不二元；预期差导向；二阶追问", encoding="utf-8")
            with mock.patch.object(
                foresight.llm_refine,
                "complete",
                return_value=(_canned_questions(8), _provider("deepseek"), ""),
            ):
                result = generate(
                    ForesightOptions(
                        n=3,
                        candidates=8,
                        use_memory=False,
                        use_interactions=False,
                        methodology_file=str(meth),
                        use_corrections=False,
                    )
                )
        self.assertEqual(result.methodology_path, str(meth))
        self.assertEqual(result.methodology_chars, len("分级不二元；预期差导向；二阶追问"))
        self.assertIn("分级不二元", result.prompt_preview)
        self.assertIn("思考宪法", result.prompt_preview)
        self.assertIn("注入思考宪法", render(result))

    def test_missing_methodology_warns_not_crashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.md"
            with mock.patch.object(
                foresight.llm_refine,
                "complete",
                return_value=(_canned_questions(8), _provider("deepseek"), ""),
            ):
                result = generate(
                    ForesightOptions(
                        n=3,
                        candidates=8,
                        use_memory=False,
                        use_interactions=False,
                        methodology_file=str(missing),
                        use_corrections=False,
                    )
                )
        self.assertEqual(result.methodology_chars, 0)
        self.assertTrue(any("方法论文件不存在" in w for w in result.warnings))

    def test_no_methodology_flag_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            meth = Path(tmp) / "m.md"
            meth.write_text("分级不二元", encoding="utf-8")
            with mock.patch.object(
                foresight.llm_refine,
                "complete",
                return_value=(_canned_questions(8), _provider("deepseek"), ""),
            ):
                result = generate(
                    ForesightOptions(
                        n=3,
                        candidates=8,
                        use_memory=False,
                        use_interactions=False,
                        methodology_file=str(meth),
                        use_methodology=False,
                        use_corrections=False,
                    )
                )
        self.assertEqual(result.methodology_chars, 0)
        self.assertNotIn("分级不二元", result.prompt_preview)


class CorrectionsInjectionTests(unittest.TestCase):
    def test_corrections_injected_and_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cpath = Path(tmp) / "corrections.jsonl"
            foresight.corrections.record_correction(
                cpath,
                correction="先判断板块在哪一阶再下结论",
                original="氟化工要爆发了",
                principle="分级不二元",
                themes=["氟化工"],
            )
            with mock.patch.object(
                foresight.llm_refine,
                "complete",
                return_value=(_canned_questions(8), _provider("deepseek"), ""),
            ):
                result = generate(
                    ForesightOptions(
                        n=3,
                        candidates=8,
                        use_memory=False,
                        use_interactions=False,
                        use_methodology=False,
                        corrections_file=str(cpath),
                    )
                )
        self.assertEqual(result.corrections_loaded, 1)
        self.assertEqual(result.corrections_path, str(cpath))
        self.assertIn("纠偏记录", result.prompt_preview)
        self.assertIn("分级不二元", result.prompt_preview)
        self.assertIn("先判断板块在哪一阶再下结论", result.prompt_preview)
        self.assertIn("带 1 条纠偏", render(result))

    def test_no_corrections_file_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cpath = Path(tmp) / "corrections.jsonl"
            with mock.patch.object(
                foresight.llm_refine,
                "complete",
                return_value=(_canned_questions(8), _provider("deepseek"), ""),
            ):
                result = generate(
                    ForesightOptions(
                        n=3,
                        candidates=8,
                        use_memory=False,
                        use_interactions=False,
                        use_methodology=False,
                        corrections_file=str(cpath),
                    )
                )
        self.assertEqual(result.corrections_loaded, 0)
        self.assertNotIn("纠偏记录", result.prompt_preview)


class JudgmentsInjectionTests(unittest.TestCase):
    def test_judgments_injected_and_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jpath = Path(tmp) / "judgments.jsonl"
            foresight.judgments.record_judgment(
                jpath,
                memo="HVLP铜箔技术验证完成但产能爬坡滞后，2026Q3是估值切换关键窗口",
                themes=["铜箔"],
                stocks=["铜冠铜箔"],
                session_id="2026-06-18-1530",
            )
            with mock.patch.object(
                foresight.llm_refine,
                "complete",
                return_value=(_canned_questions(8), _provider("deepseek"), ""),
            ):
                result = generate(
                    ForesightOptions(
                        n=3,
                        candidates=8,
                        use_memory=False,
                        use_interactions=False,
                        use_methodology=False,
                        use_corrections=False,
                        judgments_file=str(jpath),
                    )
                )
        self.assertEqual(result.judgments_loaded, 1)
        self.assertEqual(result.judgments_path, str(jpath))
        self.assertIn("核心判断", result.prompt_preview)
        self.assertIn("HVLP铜箔技术验证完成", result.prompt_preview)
        self.assertIn("承接 1 条核心判断往前推", render(result))

    def test_no_judgments_flag_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jpath = Path(tmp) / "judgments.jsonl"
            foresight.judgments.record_judgment(jpath, memo="某条判断", themes=["液冷"])
            with mock.patch.object(
                foresight.llm_refine,
                "complete",
                return_value=(_canned_questions(8), _provider("deepseek"), ""),
            ):
                result = generate(
                    ForesightOptions(
                        n=3,
                        candidates=8,
                        use_memory=False,
                        use_interactions=False,
                        use_methodology=False,
                        use_corrections=False,
                        judgments_file=str(jpath),
                        use_judgments=False,
                    )
                )
        self.assertEqual(result.judgments_loaded, 0)
        self.assertNotIn("某条判断", result.prompt_preview)

    def test_window_limits_injected_judgments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jpath = Path(tmp) / "judgments.jsonl"
            for i in range(4):
                foresight.judgments.record_judgment(
                    jpath, memo=f"判断{i}", ts=f"2026-06-1{i}T00:00:00"
                )
            with mock.patch.object(
                foresight.llm_refine,
                "complete",
                return_value=(_canned_questions(8), _provider("deepseek"), ""),
            ):
                result = generate(
                    ForesightOptions(
                        n=3,
                        candidates=8,
                        use_memory=False,
                        use_interactions=False,
                        use_methodology=False,
                        use_corrections=False,
                        judgments_file=str(jpath),
                        judgments_window=2,
                    )
                )
        self.assertEqual(result.judgments_loaded, 2)
        self.assertIn("判断3", result.prompt_preview)
        self.assertIn("判断2", result.prompt_preview)
        self.assertNotIn("判断0", result.prompt_preview)

    def test_no_judgments_file_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jpath = Path(tmp) / "judgments.jsonl"
            with mock.patch.object(
                foresight.llm_refine,
                "complete",
                return_value=(_canned_questions(8), _provider("deepseek"), ""),
            ):
                result = generate(
                    ForesightOptions(
                        n=3,
                        candidates=8,
                        use_memory=False,
                        use_interactions=False,
                        use_methodology=False,
                        use_corrections=False,
                        judgments_file=str(jpath),
                    )
                )
        self.assertEqual(result.judgments_loaded, 0)
        self.assertNotIn("核心判断", result.prompt_preview)


if __name__ == "__main__":
    unittest.main()
