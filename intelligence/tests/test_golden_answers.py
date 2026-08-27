"""黄金快照 e2e 回归测试：固定 fixture + 冻结日期 + mock LLM/网络，
对 render_answer 全文与 compose prompt（AnswerSpec 证据消息）做全文快照断言。

目的：作为 ask 主链路（S/G/R/W 证据链、引用编号、AnswerSpec、模板呈现）
重构前后的安全网 —— 任何字节级变化都会在这里显形。

更新快照：GOLDEN_UPDATE=1 python -m pytest intelligence/tests/test_golden_answers.py
"""
from __future__ import annotations

import os
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from intelligence.services import ask, llm_refine
from intelligence.services import evidence_registry
from intelligence.services.ask import AskOptions, answer_query, render_answer
from intelligence.services.closed_loop_retrieval import (
    BucketedHit,
    ClosedLoopRetrievalResult,
)
from intelligence.services.kb_rag import WikiHit

FIXTURES = Path(__file__).parent / "fixtures" / "golden_answers"
SNAPSHOTS = FIXTURES / "snapshots"
UPDATE = os.environ.get("GOLDEN_UPDATE") == "1"

FROZEN_TODAY = date(2026, 7, 10)


class _FrozenDate(date):
    @classmethod
    def today(cls) -> date:  # type: ignore[override]
        return FROZEN_TODAY


def _wiki_loop(query: str) -> ClosedLoopRetrievalResult:
    del query
    conclusion_hit = WikiHit(
        page_id="liquid-cooling",
        file_path="wiki/concepts/液冷服务器.md",
        title="液冷服务器",
        score=0.92,
        excerpt="液冷渗透率随机柜功率密度提升而上行，冷板方案先行。",
        best_chunk_id="chunk-1",
    )
    counter_hit = WikiHit(
        page_id="liquid-cooling-risk",
        file_path="wiki/concepts/液冷服务器.md",
        title="液冷服务器",
        score=0.61,
        excerpt="部分数据中心仍以风冷为主，液冷改造节奏可能低于预期。",
        best_chunk_id="chunk-9",
    )
    return ClosedLoopRetrievalResult(
        conclusion=[BucketedHit("narrow", conclusion_hit)],
        clues=[BucketedHit("counter", counter_hit)],
        counter_clues=[BucketedHit("counter", counter_hit)],
    )


def _empty_loop(query: str) -> ClosedLoopRetrievalResult:
    del query
    return ClosedLoopRetrievalResult()


class GoldenAnswerSnapshotTests(unittest.TestCase):
    maxDiff = None

    def _options(self, query: str, **overrides) -> AskOptions:
        base = dict(
            query=query,
            exports_dir=FIXTURES / "exports",
            kb_wiki=FIXTURES / "kb_wiki",
            market_db_path=FIXTURES / "no-such.duckdb",
            use_modules=False,
            use_llm=False,
            synthesize=False,
            enabled_providers=evidence_registry.without_providers(
                "M", "V", "D5", "D7", "W7"
            ),
            use_l3_lookup=False,
            shadow_grounded_composer=False,
            parallel_blocks=False,
            user="golden-test",
        )
        base.update(overrides)
        return AskOptions(**base)

    def _run(self, options: AskOptions, *, wiki_loop=_wiki_loop):
        with (
            mock.patch.object(ask, "date_cls", _FrozenDate),
            mock.patch(
                "intelligence.services.output_review.date", _FrozenDate
            ),
            mock.patch.object(
                ask.closed_loop_retrieval,
                "retrieve_closed_loop",
                side_effect=lambda query, **kwargs: wiki_loop(query),
            ),
            mock.patch.object(llm_refine, "detect_provider", return_value=None),
            mock.patch.object(
                ask.web_research,
                "fetch_web_search",
                side_effect=AssertionError("golden test must not hit the web"),
            ),
        ):
            return answer_query(options)

    def _assert_snapshot(self, name: str, content: str) -> None:
        path = SNAPSHOTS / name
        if UPDATE or not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            if UPDATE:
                return
            self.fail(f"snapshot {name} 不存在，已生成，请 review 后重跑")
        self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_theme_analysis_template_snapshot(self) -> None:
        """题材问题：S/G/R/W 全命中的模板路径（compose=False）。"""
        result = self._run(self._options("液冷服务器题材怎么看", compose=False))
        self.assertEqual(result.matched_theme, "液冷服务器")
        self._assert_snapshot("theme_analysis.md", render_answer(result))
        self._assert_snapshot(
            "theme_analysis.citations.txt",
            "\n".join(
                f"[{c.tag}] {c.source} — {c.detail}" for c in result.citations
            )
            + "\n",
        )

    def test_theme_analysis_compose_prompt_snapshot(self) -> None:
        """compose=True（不实际调 LLM）：快照 AnswerSpec 合成 prompt 的证据消息。"""
        result = self._run(self._options("液冷服务器题材怎么看", compose=True))
        self.assertIsNotNone(result.answer_spec)
        messages = result.prepared_synthesis_messages or []
        self.assertTrue(messages, "compose 路径应产出 prepared_synthesis_messages")
        user_messages = [m["content"] for m in messages if m["role"] == "user"]
        self._assert_snapshot(
            "theme_analysis.compose_prompt.txt",
            "\n\n===== NEXT USER MESSAGE =====\n\n".join(user_messages),
        )

    def test_stock_deep_dive_anchor_snapshot(self) -> None:
        """个股问题：实体锚定命中 fixture 实体（英维克）。"""
        result = self._run(self._options("英维克怎么看", compose=False))
        self._assert_snapshot("stock_anchor.md", render_answer(result))

    def test_theme_without_local_hits_snapshot(self) -> None:
        """本地无命中：候选/图谱/wiki 全空时的诚实降级输出。"""
        result = self._run(
            self._options("固态电池题材怎么看", compose=False),
            wiki_loop=_empty_loop,
        )
        self._assert_snapshot("theme_no_hits.md", render_answer(result))


if __name__ == "__main__":
    unittest.main()
