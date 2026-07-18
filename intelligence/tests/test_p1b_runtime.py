"""P1-B runtime 回归测试：LLM 调用台账 / QueryLedger / agent 工具面。

对应 2026-07-19 P1-B 批次（planner-executor-reflector 状态机的前置件）。
"""

from __future__ import annotations

import contextvars
import io
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from intelligence.services import (
    agent_research,
    llm_refine,
    query_ledger,
    web_research,
)


def _fake_urlopen_response(payload: dict) -> mock.MagicMock:
    body = json.dumps(payload).encode("utf-8")
    response = mock.MagicMock()
    response.__enter__.return_value = io.BytesIO(body)
    response.__exit__.return_value = False
    return response


_CHAT_PAYLOAD = {
    "choices": [
        {"message": {"content": "ok"}, "finish_reason": "stop"},
    ]
}


class LLMCallLedgerTests(unittest.TestCase):
    """LLM 调用记账：provider 尝试粒度、跨线程聚合、嵌套复用。"""

    def _provider(self) -> llm_refine.LLMProvider:
        return llm_refine.LLMProvider(
            name="test",
            api_key="k",
            base_url="https://example.invalid/v1",
            model="test-model",
        )

    def test_complete_records_success_attempt(self) -> None:
        with llm_refine.provider_override(self._provider()):
            with mock.patch.object(
                llm_refine.urllib.request,
                "urlopen",
                return_value=_fake_urlopen_response(_CHAT_PAYLOAD),
            ):
                with llm_refine.call_ledger_scope() as ledger:
                    content, _prov, reason = llm_refine.complete(
                        [{"role": "user", "content": "hi"}]
                    )

        self.assertEqual(content, "ok")
        self.assertEqual(reason, "")
        self.assertEqual(len(ledger.records), 1)
        record = ledger.records[0]
        self.assertEqual(record.caller, "chat")
        self.assertEqual(record.provider, "test")
        self.assertEqual(record.status, "success")

    def test_failed_attempt_is_recorded(self) -> None:
        with llm_refine.provider_override(self._provider()):
            with mock.patch.object(
                llm_refine.urllib.request,
                "urlopen",
                side_effect=OSError("boom"),
            ):
                with llm_refine.call_ledger_scope() as ledger:
                    content, _prov, reason = llm_refine.complete(
                        [{"role": "user", "content": "hi"}]
                    )

        self.assertIsNone(content)
        self.assertTrue(reason)
        self.assertEqual(len(ledger.records), 1)
        self.assertEqual(ledger.records[0].status, "failed")
        self.assertEqual(ledger.summary()["failure_count"], 1)

    def test_no_ledger_scope_is_zero_overhead(self) -> None:
        with llm_refine.provider_override(self._provider()):
            with mock.patch.object(
                llm_refine.urllib.request,
                "urlopen",
                return_value=_fake_urlopen_response(_CHAT_PAYLOAD),
            ):
                content, _prov, _reason = llm_refine.complete(
                    [{"role": "user", "content": "hi"}]
                )
        self.assertEqual(content, "ok")
        self.assertIsNone(llm_refine.current_call_ledger())

    def test_nested_scope_reuses_outer_ledger(self) -> None:
        with llm_refine.call_ledger_scope() as outer:
            with llm_refine.call_ledger_scope() as inner:
                self.assertIs(outer, inner)

    def test_thread_propagation_via_copy_context(self) -> None:
        """skill 线程经 copy_context 记入同一本账（run_turn 的传播方式）。"""

        def worker() -> None:
            ledger = llm_refine.current_call_ledger()
            assert ledger is not None
            llm_refine._record_llm_call(
                "chat",
                self._provider(),
                "success",
                0.0,
            )

        with llm_refine.call_ledger_scope() as ledger:
            pool = ThreadPoolExecutor(max_workers=2)
            futures = [
                pool.submit(contextvars.copy_context().run, worker)
                for _ in range(3)
            ]
            for future in futures:
                future.result()
            pool.shutdown()

        self.assertEqual(len(ledger.records), 3)
        self.assertEqual(ledger.summary()["by_caller"], {"chat": 3})

    def test_synthesis_attempt_is_recorded(self) -> None:
        with llm_refine.provider_override(self._provider()):
            with mock.patch.object(
                llm_refine.urllib.request,
                "urlopen",
                return_value=_fake_urlopen_response(_CHAT_PAYLOAD),
            ):
                with llm_refine.call_ledger_scope() as ledger:
                    composed, reason = llm_refine.synthesize_messages(
                        [{"role": "user", "content": "hi"}]
                    )

        self.assertIsNotNone(composed)
        self.assertEqual(reason, "")
        self.assertEqual(
            [record.caller for record in ledger.records],
            ["synthesis"],
        )

    def test_hard_budget_rejects_over_limit_calls(self) -> None:
        """硬预算：尝试数达上限后新调用被拒发（不发 HTTP），graceful 降级。"""
        with llm_refine.provider_override(self._provider()):
            with mock.patch.object(
                llm_refine.urllib.request,
                "urlopen",
                return_value=_fake_urlopen_response(_CHAT_PAYLOAD),
            ) as urlopen:
                with llm_refine.call_ledger_scope(max_calls=1) as ledger:
                    first, _p1, r1 = llm_refine.complete(
                        [{"role": "user", "content": "a"}]
                    )
                    second, _p2, r2 = llm_refine.complete(
                        [{"role": "user", "content": "b"}]
                    )
                    composed, r3 = llm_refine.synthesize_messages(
                        [{"role": "user", "content": "c"}]
                    )

        self.assertEqual(first, "ok")
        self.assertEqual(r1, "")
        self.assertIsNone(second)
        self.assertIn("预算耗尽", r2)
        self.assertIsNone(composed)
        self.assertIn("预算耗尽", r3)
        self.assertEqual(urlopen.call_count, 1)
        summary = ledger.summary()
        self.assertEqual(summary["call_count"], 1)
        self.assertEqual(summary["rejected_count"], 2)
        self.assertEqual(summary["max_calls"], 1)

    def test_no_limit_never_rejects(self) -> None:
        with llm_refine.provider_override(self._provider()):
            with mock.patch.object(
                llm_refine.urllib.request,
                "urlopen",
                side_effect=lambda *a, **k: _fake_urlopen_response(
                    _CHAT_PAYLOAD
                ),
            ):
                with llm_refine.call_ledger_scope() as ledger:
                    for _ in range(3):
                        content, _p, _r = llm_refine.complete(
                            [{"role": "user", "content": "x"}]
                        )
                        self.assertEqual(content, "ok")

        self.assertEqual(ledger.summary()["rejected_count"], 0)
        self.assertEqual(len(ledger.records), 3)


class QueryLedgerTests(unittest.TestCase):
    """turn 级查询台账：同 provider+query 每 turn 最多真实执行一次。"""

    def test_same_key_executes_once_and_reuses(self) -> None:
        calls: list[str] = []

        def fetch() -> str:
            calls.append("hit")
            return "result"

        with query_ledger.query_ledger_scope() as ledger:
            first = query_ledger.executed("web_search", "AI 算力", fetch)
            second = query_ledger.executed("web_search", "AI 算力", fetch)

        self.assertEqual(first, "result")
        self.assertIs(first, second)
        self.assertEqual(calls, ["hit"])
        summary = ledger.summary()
        self.assertEqual(summary["executed_count"], 1)
        self.assertEqual(summary["deduped_count"], 1)

    def test_query_normalization_merges_whitespace_and_case(self) -> None:
        calls: list[str] = []

        with query_ledger.query_ledger_scope():
            query_ledger.executed(
                "web_search", "  AI   算力 GPU ", lambda: calls.append("a")
            )
            query_ledger.executed(
                "web_search", "ai 算力 gpu", lambda: calls.append("b")
            )

        self.assertEqual(calls, ["a"])

    def test_different_as_of_not_deduped(self) -> None:
        calls: list[str] = []

        with query_ledger.query_ledger_scope():
            query_ledger.executed(
                "news_search", "液冷", lambda: calls.append("a"), as_of="days=7"
            )
            query_ledger.executed(
                "news_search", "液冷", lambda: calls.append("b"), as_of="days=30"
            )

        self.assertEqual(calls, ["a", "b"])

    def test_no_scope_is_passthrough(self) -> None:
        calls: list[str] = []
        query_ledger.executed("web_search", "q", lambda: calls.append("a"))
        query_ledger.executed("web_search", "q", lambda: calls.append("b"))
        self.assertEqual(calls, ["a", "b"])
        self.assertIsNone(query_ledger.current_query_ledger())

    def test_concurrent_same_key_single_execution(self) -> None:
        calls: list[str] = []

        def fetch() -> str:
            calls.append("hit")
            return "r"

        with query_ledger.query_ledger_scope():
            pool = ThreadPoolExecutor(max_workers=4)
            futures = [
                pool.submit(
                    contextvars.copy_context().run,
                    query_ledger.executed,
                    "web_search",
                    "并发查询",
                    fetch,
                )
                for _ in range(6)
            ]
            results = [future.result() for future in futures]
            pool.shutdown()

        self.assertEqual(calls, ["hit"])
        self.assertTrue(all(item == "r" for item in results))

    def test_web_search_tool_layer_dedupes_in_scope(self) -> None:
        sentinel = web_research.WebSearchResult((), mock.Mock())

        with mock.patch.object(
            web_research,
            "_fetch_web_search_uncached",
            return_value=sentinel,
        ) as fetch:
            with query_ledger.query_ledger_scope():
                first = web_research.fetch_web_search("宁德时代 新闻")
                second = web_research.fetch_web_search("宁德时代  新闻")

        self.assertIs(first, sentinel)
        self.assertIs(second, sentinel)
        self.assertEqual(fetch.call_count, 1)


class _FakeKnowledge:
    """KnowledgeAdapter 鸭子类型桩：graph/evidence 工具消费的三个方法。"""

    def get_concept_matches(self, query: str, limit: int = 5) -> dict:
        return {
            "found": True,
            "items": [{"concept": "液冷服务器", "score": 20}],
        }

    def get_exposure_matches(self, query: str, limit: int = 8) -> dict:
        return {
            "found": True,
            "items": [
                {
                    "company": "川环科技",
                    "concept": "液冷服务器",
                    "strength": "related",
                    "evidence_layer": "L1_L3_candidate",
                },
                {"company": "", "concept": "液冷服务器"},
            ],
        }

    def get_evidence(self, target: str, concept=None, limit: int = 6) -> dict:
        return {
            "found": True,
            "items": [
                {
                    "target": "川环科技",
                    "evidence": "券商研报提及其为液冷管路潜在供应商",
                    "source": "券商研报",
                    "source_date": "2026-05-20",
                    "confidence": "medium",
                }
            ],
        }


class AgentGraphToolsTests(unittest.TestCase):
    """P1-B agent 工具面扩展：graph_lookup / evidence_lookup + 动态 prompt。"""

    def test_graph_lookup_returns_concepts_and_exposures(self) -> None:
        tools = agent_research.build_graph_tools(_FakeKnowledge())

        evidence, observation, trace = tools["graph_lookup"]("液冷")

        self.assertEqual(trace.provider, "agent:graph_lookup")
        self.assertEqual(trace.status, "success")
        titles = [item.title for item in evidence]
        self.assertIn("概念 液冷服务器", titles)
        self.assertIn("川环科技", titles)
        self.assertNotIn("", titles)
        self.assertIn("川环科技", observation)

    def test_evidence_lookup_formats_index_entries(self) -> None:
        tools = agent_research.build_graph_tools(_FakeKnowledge())

        evidence, observation, trace = tools["evidence_lookup"]("川环科技")

        self.assertEqual(trace.provider, "agent:evidence_lookup")
        self.assertEqual(len(evidence), 1)
        self.assertIn("券商研报", evidence[0].detail)
        self.assertIn("2026-05-20", evidence[0].detail)
        self.assertIn("evidence_index.json", evidence[0].source)
        self.assertIn("川环科技", observation)

    def test_system_prompt_lists_only_registered_tools(self) -> None:
        """宣传=注册：未接入 graph 工具时 prompt 不得宣传（否则触发非法工具中断）。"""
        base_tools = {"kb_search": lambda q: ([], "", None)}
        prompt = agent_research._system_prompt(base_tools)
        self.assertIn("kb_search", prompt)
        self.assertNotIn("graph_lookup", prompt)

        full_tools = {
            **base_tools,
            **agent_research.build_graph_tools(_FakeKnowledge()),
        }
        full_prompt = agent_research._system_prompt(full_tools)
        self.assertIn("graph_lookup", full_prompt)
        self.assertIn("evidence_lookup", full_prompt)
        self.assertIn("finish", full_prompt)

    def test_loop_can_drive_graph_lookup(self) -> None:
        responses = iter(
            (
                '{"tool": "graph_lookup", "args": {"query": "液冷"}, '
                '"reason": "定位公司映射"}',
                '{"tool": "finish", "args": {"sufficient": true, "gaps": []}, '
                '"reason": "图谱已给出映射"}',
            )
        )

        def fake_complete(messages, **kwargs):
            return next(responses), None, ""

        result = agent_research.run_agent_loop(
            "液冷还有哪些公司",
            tools=agent_research.build_graph_tools(_FakeKnowledge()),
            complete_fn=fake_complete,
        )

        self.assertEqual(result.steps[0].tool, "graph_lookup")
        self.assertGreater(result.steps[0].hit_count, 0)
        self.assertTrue(
            any(item.tool == "graph_lookup" for item in result.evidence)
        )
        self.assertTrue(result.sufficient)


if __name__ == "__main__":
    unittest.main()
