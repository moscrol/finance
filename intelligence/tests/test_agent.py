from __future__ import annotations

import json
import unittest
from unittest import mock

from intelligence.services import agent, kb_rag, llm_refine
from intelligence.services.agent import AGENT_TOOLS, AgentSession
from intelligence.services.ask import AskOptions
from intelligence.services.llm_refine import LLMProvider


def _provider() -> LLMProvider:
    return LLMProvider(name="deepseek", api_key="sk-test", base_url="https://api.deepseek.com/v1", model="deepseek-chat")


def _tool_call_msg(name: str, args: dict, call_id: str = "call_1", *, bad_json: bool = False) -> dict:
    arguments = "{not json" if bad_json else json.dumps(args, ensure_ascii=False)
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}
        ],
    }


def _final_msg(content: str) -> dict:
    return {"role": "assistant", "content": content}


class FakeKnowledge:
    """Stand-in for KnowledgeAdapter with deterministic canned hits."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: D401 - matches adapter ctor
        pass

    def get_concept_matches(self, query, limit=6):
        return {"found": True, "items": [{"concept": "液冷服务器", "score": 9}]}

    def get_exposure_matches(self, query, limit=12):
        return {
            "found": True,
            "items": [
                {"company": "英维克", "ticker": "002837", "role": "温控", "strength": "core", "confidence": "high", "evidence_layer": "L3"},
                {"company": "川润股份", "ticker": "002272", "role": "—", "strength": "", "confidence": "medium", "evidence_layer": "graph_only"},
            ],
        }

    def get_evidence(self, target, limit=8):
        return {
            "found": True,
            "items": [
                {"target": "英维克", "evidence": "液冷一次侧订单放量", "source": "公告", "source_date": "2026-05-20", "confidence": "high"},
            ],
        }


def _session(**opts) -> AgentSession:
    options = AskOptions(query="液冷", date="2026-06-11", **opts)
    with mock.patch.object(agent, "KnowledgeAdapter", FakeKnowledge):
        return AgentSession(options, max_steps=4)


class ToolSchemaTests(unittest.TestCase):
    def test_tool_schemas_well_formed(self) -> None:
        names = {t["function"]["name"] for t in AGENT_TOOLS}
        self.assertEqual(
            names,
            {"search_market_snapshot", "search_graph", "search_evidence", "search_wiki", "run_theme_module"},
        )
        for t in AGENT_TOOLS:
            self.assertEqual(t["type"], "function")
            fn = t["function"]
            self.assertTrue(fn["description"])
            self.assertEqual(fn["parameters"]["type"], "object")


class ToolBehaviourTests(unittest.TestCase):
    def test_search_graph_tiers_and_cites(self) -> None:
        s = _session()
        out = s.tool_search_graph("液冷")
        # concept gets [G1], companies get [G2]
        self.assertIn("命中概念", out)
        self.assertIn("核心层", out)
        self.assertIn("英维克", out)
        # graph_only company is demoted to the 待验证 peripheral tier, not core
        self.assertIn("川润股份", out.split("核心层")[1].split("外围")[-1])
        self.assertIn("待验证", out)
        self.assertEqual([c.tag for c in s.citations], ["G1", "G2"])
        self.assertIn("G", s.sources_used)

    def test_search_evidence_cites_with_source(self) -> None:
        s = _session()
        out = s.tool_search_evidence("英维克")
        self.assertIn("[R1]", out)
        self.assertIn("公告", out)
        self.assertEqual(s.citations[0].tag, "R1")
        self.assertIn("evidence_index", s.citations[0].source)

    def test_search_evidence_miss_returns_note(self) -> None:
        s = _session()
        s.knowledge.get_evidence = lambda target, limit=8: {"found": False, "items": []}
        out = s.tool_search_evidence("不存在的词")
        self.assertIn("未命中", out)
        self.assertEqual(s.citations, [])

    def test_search_wiki_degrades_on_unavailable_index(self) -> None:
        s = _session()
        fake = mock.Mock(ok=False, hits=[], warning="索引不存在")
        with mock.patch.object(kb_rag, "retrieve", return_value=fake):
            out = s.tool_search_wiki("液冷")
        self.assertIn("不可用", out)
        self.assertNotIn("W", s.sources_used)

    def test_run_theme_module_rejects_unknown(self) -> None:
        s = _session()
        out = s.tool_run_theme_module("does-not-exist")
        self.assertIn("未知模块", out)


class AgentLoopTests(unittest.TestCase):
    def test_degrades_without_provider(self) -> None:
        s = _session()
        with mock.patch.object(llm_refine, "chat_with_tools", return_value=(None, None, "未配置 LLM key。")):
            res = s.run("液冷")
        self.assertFalse(res.ok)
        self.assertIsNone(res.answer)
        self.assertIn("未配置 LLM key", res.reason)
        self.assertEqual(res.steps, [])

    def test_loop_dispatches_tool_then_answers(self) -> None:
        s = _session()
        prov = _provider()
        with mock.patch.object(
            llm_refine,
            "chat_with_tools",
            side_effect=[
                (_tool_call_msg("search_graph", {"query": "液冷"}), prov, ""),
                (_final_msg("液冷核心是英维克[G2]，川润仅 graph_only[G2]。（非投资建议）"), prov, ""),
            ],
        ) as called:
            res = s.run("液冷")
        self.assertTrue(res.ok)
        self.assertIn("[G2]", res.answer)
        self.assertEqual(res.provider, "deepseek")
        # exactly one tool was dispatched, recorded in the trace
        self.assertEqual(len(res.steps), 1)
        self.assertEqual(res.steps[0].tool, "search_graph")
        self.assertEqual(res.steps[0].args, {"query": "液冷"})
        # the tool actually ran (citations registered) and its result fed back in
        self.assertTrue(res.citations)
        # second round-trip carried the assistant tool_call echo + tool result message
        second_messages = called.call_args_list[1].args[0]
        roles = [m["role"] for m in second_messages]
        self.assertEqual(roles, ["system", "user", "assistant", "tool"])
        self.assertIn("英维克", second_messages[3]["content"])

    def test_unknown_tool_call_is_handled(self) -> None:
        s = _session()
        prov = _provider()
        with mock.patch.object(
            llm_refine,
            "chat_with_tools",
            side_effect=[
                (_tool_call_msg("nope_tool", {"x": 1}), prov, ""),
                (_final_msg("证据不足。（非投资建议）"), prov, ""),
            ],
        ) as called:
            res = s.run("液冷")
        self.assertTrue(res.ok)
        self.assertEqual(res.steps[0].tool, "nope_tool")
        self.assertIn("未知工具", res.steps[0].result_preview)
        # the error string was passed back as the tool result, loop continued
        tool_msg = called.call_args_list[1].args[0][-1]
        self.assertEqual(tool_msg["role"], "tool")
        self.assertIn("未知工具", tool_msg["content"])

    def test_bad_tool_arguments_do_not_crash(self) -> None:
        s = _session()
        prov = _provider()
        with mock.patch.object(
            llm_refine,
            "chat_with_tools",
            side_effect=[
                (_tool_call_msg("search_graph", {}, bad_json=True), prov, ""),
                (_final_msg("液冷[G2]。（非投资建议）"), prov, ""),
            ],
        ):
            res = s.run("液冷")
        # invalid JSON args degrade to {} -> search_graph() called with no kwargs -> TypeError caught
        self.assertTrue(res.ok)
        self.assertEqual(res.steps[0].args, {})
        self.assertIn("参数错误", res.steps[0].result_preview)

    def test_max_steps_forces_tool_free_final(self) -> None:
        s = _session()
        prov = _provider()
        # always ask for a tool -> never answers on its own -> budget exhausted
        with mock.patch.object(
            llm_refine,
            "chat_with_tools",
            return_value=(_tool_call_msg("search_graph", {"query": "液冷"}), prov, ""),
        ) as tool_call, mock.patch.object(
            llm_refine, "complete", return_value=("收尾回答[G2]。（非投资建议）", prov, "")
        ) as forced:
            res = s.run("液冷")
        self.assertTrue(res.ok)
        self.assertIn("收尾", res.answer)
        # tool round-trips capped at max_steps, then one forced tool-free completion
        self.assertEqual(tool_call.call_count, s.max_steps)
        self.assertEqual(forced.call_count, 1)
        self.assertIn("步数上限", res.reason)
        # the forced final call appended a tool-free nudge as the last user turn
        forced_messages = forced.call_args.args[0]
        self.assertEqual(forced_messages[-1]["role"], "user")


if __name__ == "__main__":
    unittest.main()
