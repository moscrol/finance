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

from intelligence.services import llm_refine, query_ledger, web_research


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


if __name__ == "__main__":
    unittest.main()
