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

    def test_l3_and_market_tools_are_registered_names(self) -> None:
        """l3_lookup/market_data 进白名单与描述表：注册后动态 prompt 自动宣传。"""
        self.assertIn("l3_lookup", agent_research._TOOL_NAMES)
        self.assertIn("market_data", agent_research._TOOL_NAMES)

        def stub_tool(query: str):
            return [], "无", None

        prompt = agent_research._system_prompt(
            {"l3_lookup": stub_tool, "market_data": stub_tool}
        )
        self.assertIn("l3_lookup", prompt)
        self.assertIn("market_data", prompt)
        self.assertNotIn("kb_search：", prompt)

    def test_block_lines_to_evidence_skips_headings(self) -> None:
        block = (
            "## 市场总览\n"
            "- 上证指数收于3764点，跌3.05%\n"
            "- 全市场成交额26547亿\n"
            "\n"
            "# 另一个标题\n"
            "涨停33家，跌停193家\n"
        )

        evidence, observation = agent_research.block_lines_to_evidence(
            "market_data", block, "本地 DuckDB · 市场总览"
        )

        self.assertEqual(len(evidence), 3)
        self.assertTrue(
            all(item.tool == "market_data" for item in evidence)
        )
        self.assertTrue(
            all(item.source == "本地 DuckDB · 市场总览" for item in evidence)
        )
        self.assertNotIn("市场总览\n", observation)
        self.assertIn("上证指数", observation)
        self.assertIn("涨停33家", observation)

    def test_block_lines_to_evidence_empty_block(self) -> None:
        evidence, observation = agent_research.block_lines_to_evidence(
            "market_data", "", "本地 DuckDB"
        )
        self.assertEqual(evidence, [])
        self.assertEqual(observation, "")


class OwnerRawResultChannelTests(unittest.TestCase):
    """P1-B：owner 完整 ResearchResult 通道（替代有损重建）。"""

    def _contract_and_output(self, spec):
        from intelligence.workbench_skills.contracts import (
            SkillAnswerContract,
            SkillOutput,
        )

        contract = SkillAnswerContract(
            retrieval_plan=("S",),
            output_contract=("结论",),
            answer_spec=spec,
        )
        output = SkillOutput(
            skill_id="stock-deep-dive",
            modules=[],
            citations=[{"title": "公司公告", "source": "巨潮"}],
            warnings=["skill 级警告"],
            as_of="2026-07-17",
            raw_result_ref=None,
            answer_contract=contract,
        )
        return contract, output

    def _spec(self):
        from intelligence.services.answer_model import (
            AnswerSpec,
            ClaimStatus,
            EvidenceRef,
            finalize_answer_spec,
            make_claim,
            resolve_theme_research_spec,
        )

        research = resolve_theme_research_spec("分析人形机器人产业链")
        fact = make_claim(
            claim_id="fact-1",
            text="盘面显示涨幅2.61%。",
            claim_type="market_signal",
            theme=research.theme,
            status=ClaimStatus.VERIFIED,
            evidence_tier="L4",
            evidence_ids=("S1",),
        )
        return finalize_answer_spec(
            AnswerSpec(
                research_spec=research,
                summary=(fact,),
                verified_facts=(fact,),
                company_table=(),
                counter_evidence=(),
                gaps=(),
                triggers=(),
                next_actions=("T+1 复核",),
                sources=(
                    EvidenceRef(evidence_id="S1", source="盘面快照", tier="L4"),
                ),
                system_notices=(),
            )
        )

    def _raw_result(self, spec):
        from intelligence.services.ask import AskResult, Citation
        from intelligence.services.provider_observability import ProviderTrace

        raw = AskResult(
            query="分析液冷",
            trade_date="2026-07-17",
            matched_theme="液冷",
            candidate_tier=None,
            priority_score=None,
            found_market=True,
        )
        raw.answer_spec = spec
        raw.warnings = ["raw 级警告"]
        raw.citations = [Citation("W1", "knowledge-base · a.md", "chunk=c1")]
        raw.provider_traces.append(
            ProviderTrace(
                provider="local_wiki",
                capability="theme_recall",
                status="success",
                result_count=3,
            )
        )
        raw.prepared_synthesis_messages = [{"role": "user", "content": "旧"}]
        return raw

    def test_raw_result_is_consumed_with_contract_spec(self) -> None:
        from intelligence.services.conversation_orchestrator import (
            _resolve_owner_result,
        )

        spec = self._spec()
        contract_spec = self._spec()  # 不同对象（模拟继承合并后的契约 spec）
        raw = self._raw_result(spec)
        contract, output = self._contract_and_output(contract_spec)
        cache: dict[str, object] = {"owner_raw_result:stock-deep-dive": raw}

        resolved = _resolve_owner_result("分析液冷", output, cache)

        self.assertIs(resolved, raw)
        self.assertIs(resolved.answer_spec, contract.answer_spec)
        self.assertEqual(resolved.trade_date, "2026-07-17")
        self.assertEqual(resolved.citations[0].tag, "W1")
        self.assertEqual(resolved.provider_traces[0].provider, "local_wiki")
        # spec 被契约替换 → owner 预备的旧合成消息必须清除（防 claim_id 失配）
        self.assertIsNone(resolved.prepared_synthesis_messages)

    def test_same_spec_keeps_prepared_messages(self) -> None:
        from intelligence.services.conversation_orchestrator import (
            _resolve_owner_result,
        )

        spec = self._spec()
        raw = self._raw_result(spec)
        _contract, output = self._contract_and_output(spec)  # 同一对象
        cache: dict[str, object] = {"owner_raw_result:stock-deep-dive": raw}

        resolved = _resolve_owner_result("分析液冷", output, cache)

        self.assertIsNotNone(resolved.prepared_synthesis_messages)

    def test_cache_miss_falls_back_to_rebuild(self) -> None:
        from intelligence.services.conversation_orchestrator import (
            _resolve_owner_result,
        )

        spec = self._spec()
        _contract, output = self._contract_and_output(spec)

        resolved = _resolve_owner_result("分析液冷", output, {})

        self.assertEqual(resolved.trade_date, "2026-07-17")
        self.assertEqual(resolved.citations[0].tag, "K1")


class PublicProjectionTests(unittest.TestCase):
    """P2 公共投影分离：控制面 section 不进用户报告模块。"""

    def test_control_plane_sections_excluded_from_modules(self) -> None:
        from intelligence.api.structured_reports import ask_result_modules
        from intelligence.services.ask import AskResult

        result = AskResult(
            query="测试",
            trade_date="2026-07-17",
            matched_theme=None,
            candidate_tier=None,
            priority_score=None,
        )
        result.sections = {
            "结论": ["主题以盘面驱动为主。"],
            "证据链": ["证据 A"],
            "检索可观测": ["检索方式=hybrid k=8"],
            "输出质检": ["✓ 本地数据新鲜度"],
            "交易含义": ["观察为主。"],
            "数据源状态": ["local_wiki｜success"],
            "引用来源": ["[S1] 盘面快照"],
        }

        modules = ask_result_modules(result)
        titles = [module["title"] for module in modules]

        self.assertNotIn("检索可观测", titles)
        self.assertNotIn("输出质检", titles)
        self.assertNotIn("数据源状态", titles)
        self.assertIn("结论", titles)
        self.assertIn("证据链", titles)
        # 过滤后重编号连续（module_id 不跳号）
        section_ids = [
            module["module_id"]
            for module in modules
            if module["module_id"].startswith("research_")
        ]
        indexes = [int(mid.split("_")[1]) for mid in section_ids]
        self.assertEqual(indexes, list(range(1, len(indexes) + 1)))


if __name__ == "__main__":
    unittest.main()
