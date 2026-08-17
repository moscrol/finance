from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from intelligence.services import ask_chat, llm_refine
from intelligence.services.ask import AskOptions, AskResult
from intelligence.services.llm_refine import (
    LLMProvider,
    SynthesisResult,
    build_synthesis_messages,
    followup_user_content,
    synthesize_messages,
)


class DataRepoRootTests(unittest.TestCase):
    def test_default_exports_dir_prefers_finance_ws_over_workbench_repo_root(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            code = Path(tmp) / "code-snapshot"
            data = Path(tmp) / "private-data"
            env = {
                **os.environ,
                "WORKBENCH_REPO_ROOT": str(code),
                "FINANCE_WS": str(data),
            }
            env.pop("FINANCE_ROOT", None)
            env.pop("MARKET_FEATURE_STORE_DB", None)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from intelligence.services.ask import DEFAULT_EXPORTS_DIR; print(DEFAULT_EXPORTS_DIR)",
                ],
                cwd=repo_root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            expected = data / "market_feature_store" / "exports"
            self.assertEqual(completed.stdout.strip(), str(expected))

    def test_default_exports_dir_ignores_workbench_repo_root_when_alone(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                **os.environ,
                "WORKBENCH_REPO_ROOT": tmp,
            }
            env.pop("FINANCE_WS", None)
            env.pop("FINANCE_ROOT", None)
            env.pop("MARKET_FEATURE_STORE_DB", None)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from intelligence.services.ask import DEFAULT_EXPORTS_DIR; print(DEFAULT_EXPORTS_DIR)",
                ],
                cwd=repo_root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            expected = repo_root / "market_feature_store" / "exports"
            self.assertEqual(completed.stdout.strip(), str(expected))
            self.assertNotIn(str(Path(tmp).resolve()), completed.stdout)


def _provider() -> LLMProvider:
    return LLMProvider(name="deepseek", api_key="sk-test", base_url="https://api.deepseek.com/v1", model="deepseek-chat")


class SynthesizeMessagesTests(unittest.TestCase):
    def test_build_messages_has_system_and_user_with_legend(self) -> None:
        msgs = build_synthesis_messages("液冷", "液冷服务器", "## 证据链\n- 新高10只 [S1]", "[S1] 盘面快照")
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[1]["role"], "user")
        self.assertIn("液冷", msgs[1]["content"])
        self.assertIn("[S1] 盘面快照", msgs[1]["content"])

    def test_followup_content_wraps_with_grounding_nudge(self) -> None:
        wrapped = followup_user_content("强瑞和冰轮哪个证据更硬")
        self.assertIn("强瑞和冰轮哪个证据更硬", wrapped)
        self.assertIn("追问", wrapped)
        self.assertIn("非投资建议", wrapped)

    def test_degrades_without_provider(self) -> None:
        with mock.patch.object(llm_refine, "detect_provider", return_value=None):
            out, reason = synthesize_messages(build_synthesis_messages("液冷", "液冷服务器", "ev"))
        self.assertIsNone(out)
        self.assertIn("未配置 LLM key", reason)

    def test_succeeds_with_mocked_llm(self) -> None:
        msgs = build_synthesis_messages("液冷", "液冷服务器", "## 证据链\n- 新高10只 [S1]")
        with mock.patch.object(llm_refine, "detect_provider", return_value=_provider()), mock.patch.object(
            llm_refine,
            "_post_chat_synthesis",
            return_value=("液冷盘面强势[S1]。（非投资建议）", "stop"),
        ) as posted:
            out, reason = synthesize_messages(msgs)
        self.assertEqual(reason, "")
        assert out is not None
        self.assertIn("[S1]", out.answer)
        self.assertEqual(out.provider, "deepseek")
        # the exact messages list we built is what gets posted
        self.assertIs(posted.call_args.args[1], msgs)


def _first_result(synthesis: str | None, with_messages: bool = True) -> AskResult:
    r = AskResult(
        query="液冷",
        trade_date="2026-06-11",
        matched_theme="液冷服务器",
        candidate_tier="watch",
        priority_score=80.57,
        found_market=True,
        found_graph=True,
    )
    r.synthesis = synthesis
    if synthesis and with_messages:
        r.llm_provider = "deepseek"
        r.synthesis_messages = [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "EVIDENCE [S1][R4][G2]"},
            {"role": "assistant", "content": synthesis},
        ]
    elif synthesis is None:
        r.warnings.append("未配置 LLM key，有机合成降级为模板。")
    return r


class AskConversationTests(unittest.TestCase):
    def _opts(self) -> AskOptions:
        return AskOptions(query="液冷", date="2026-06-11", use_wiki_rag=False, use_modules=False)

    def test_start_then_multi_turn_grows_history_and_reuses_evidence(self) -> None:
        first = _first_result("首轮合成[S1][R4]。（非投资建议）")
        with mock.patch.object(ask_chat, "answer_query", return_value=first):
            conv = ask_chat.AskConversation(self._opts())
            t1 = conv.start()
        self.assertTrue(t1.composed)
        self.assertTrue(conv.ready)
        self.assertEqual(conv.options.compose, True)
        # turn-1 messages = system + user(evidence) + assistant
        assert conv.messages is not None
        self.assertEqual(len(conv.messages), 3)

        f1 = SynthesisResult(answer="冰轮证据更硬[R4][G4]。（非投资建议）", provider="deepseek", model="deepseek-chat")
        f2 = SynthesisResult(answer="川润仅 graph_only[G3]。（非投资建议）", provider="deepseek", model="deepseek-chat")
        with mock.patch.object(llm_refine, "synthesize_messages", side_effect=[(f1, ""), (f2, "")]) as syn:
            t2 = conv.ask("强瑞和冰轮哪个证据更硬")
            t3 = conv.ask("那川润为啥算核心又说缺验证")
        self.assertTrue(t2.composed and t3.composed)
        self.assertIn("[R4]", t2.answer)
        # each follow-up appends user+assistant -> 3 + 2 + 2 = 7
        self.assertEqual(len(conv.messages), 7)
        self.assertEqual([m["role"] for m in conv.messages], ["system", "user", "assistant", "user", "assistant", "user", "assistant"])
        # follow-up content carries the grounding nudge; turn-1 evidence is still the only evidence block
        self.assertIn("追问", conv.messages[3]["content"])
        self.assertIn("强瑞和冰轮哪个证据更硬", conv.messages[3]["content"])
        self.assertEqual(conv.messages[1]["content"], "EVIDENCE [S1][R4][G2]")
        # the running history (with prior assistant answer) is what gets passed back in
        self.assertIs(syn.call_args_list[1].args[0], conv.messages)

    def test_start_degrades_without_llm(self) -> None:
        first = _first_result(None)
        with mock.patch.object(ask_chat, "answer_query", return_value=first):
            conv = ask_chat.AskConversation(self._opts())
            t1 = conv.start()
        self.assertFalse(t1.composed)
        self.assertFalse(conv.ready)
        self.assertIn("LLM", t1.warning)
        # asking after a degraded start does not crash, returns a clear error turn
        t2 = conv.ask("追问一下")
        self.assertFalse(t2.composed)
        self.assertIn("未就绪", t2.answer)

    def test_followup_failure_rolls_back_history(self) -> None:
        first = _first_result("首轮[S1]。（非投资建议）")
        with mock.patch.object(ask_chat, "answer_query", return_value=first):
            conv = ask_chat.AskConversation(self._opts())
            conv.start()
        assert conv.messages is not None
        before = len(conv.messages)
        with mock.patch.object(llm_refine, "synthesize_messages", return_value=(None, "LLM 合成 HTTP 503，已降级为模板")):
            turn = conv.ask("会不会超时")
        self.assertFalse(turn.composed)
        self.assertIn("降级", turn.answer)
        # the unanswered user turn is rolled back so history stays consistent for retry
        self.assertEqual(len(conv.messages), before)


if __name__ == "__main__":
    unittest.main()
