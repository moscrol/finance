from __future__ import annotations

import unittest
from unittest import mock

from intelligence.services import llm_refine
from intelligence.services.ask import AskResult, render_answer
from intelligence.services.llm_refine import LLMProvider, SynthesisResult, synthesize


def _provider() -> LLMProvider:
    return LLMProvider(name="deepseek", api_key="sk-test", base_url="https://api.deepseek.com/v1", model="deepseek-chat")


class SynthesizeTests(unittest.TestCase):
    def test_degrades_without_provider(self) -> None:
        with mock.patch.object(llm_refine, "detect_provider", return_value=None):
            out, reason = synthesize("液冷", "液冷服务器", "## 证据链\n- foo [S1]")
        self.assertIsNone(out)
        self.assertIn("未配置 LLM key", reason)

    def test_composes_with_mocked_llm(self) -> None:
        with mock.patch.object(llm_refine, "detect_provider", return_value=_provider()), mock.patch.object(
            llm_refine, "_post_chat", return_value="液冷盘面强势[S1]。（非投资建议）"
        ) as posted:
            out, reason = synthesize(
                "液冷", "液冷服务器", "## 证据链\n- 新高10只 [S1]", citation_legend="[S1] 盘面快照"
            )
        self.assertEqual(reason, "")
        self.assertIsInstance(out, SynthesisResult)
        assert out is not None
        self.assertIn("[S1]", out.answer)
        self.assertEqual(out.provider, "deepseek")
        # 证据图例 + 用户问题都进了 prompt
        user_msg = posted.call_args.args[1][1]["content"]
        self.assertIn("液冷", user_msg)
        self.assertIn("[S1] 盘面快照", user_msg)

    def test_degrades_on_empty_content(self) -> None:
        with mock.patch.object(llm_refine, "detect_provider", return_value=_provider()), mock.patch.object(
            llm_refine, "_post_chat", return_value="   "
        ):
            out, reason = synthesize("液冷", "液冷服务器", "ev")
        self.assertIsNone(out)
        self.assertIn("空内容", reason)

    def test_degrades_on_exception(self) -> None:
        with mock.patch.object(llm_refine, "detect_provider", return_value=_provider()), mock.patch.object(
            llm_refine, "_post_chat", side_effect=RuntimeError("boom")
        ):
            out, reason = synthesize("液冷", "液冷服务器", "ev")
        self.assertIsNone(out)
        self.assertIn("降级为模板", reason)


class RenderComposeTests(unittest.TestCase):
    def _base_result(self, synthesis: str | None) -> AskResult:
        r = AskResult(
            query="液冷",
            trade_date="2026-06-11",
            matched_theme="液冷服务器",
            candidate_tier="watch",
            priority_score=80.57,
            found_market=True,
            found_graph=True,
        )
        r.sections = {"结论": ["x"], "证据链": [], "分歧反证": [], "后续验证点": [], "交易含义": ["y"], "引用来源": []}
        r.synthesis = synthesis
        r.llm_provider = "deepseek" if synthesis else None
        return r

    def test_compose_block_rendered_when_present(self) -> None:
        out = render_answer(self._base_result("有机融合后的回答[S1]。（非投资建议）"))
        self.assertIn("【对话式回答】", out)
        self.assertIn("deepseek", out)
        self.assertIn("有机融合后的回答[S1]", out)
        # 结构化证据仍保留在下方供核对
        self.assertIn("【证据链】", out)

    def test_no_compose_block_when_absent(self) -> None:
        out = render_answer(self._base_result(None))
        self.assertNotIn("【对话式回答】", out)
        self.assertIn("【结论】", out)


if __name__ == "__main__":
    unittest.main()
