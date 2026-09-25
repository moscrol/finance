from __future__ import annotations

import json
import time
from datetime import date

from intelligence.services import agent_research
from intelligence.services.agent_research import (
    AgentEvidence,
    run_agent_loop,
    should_run,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
from intelligence.services.research_contract import RequiredOutput, ResearchTaskContract
from intelligence.services.research_state import ResearchState


def _tool(name: str, hits: int = 1):
    def runner(query: str):
        evidence = [
            AgentEvidence(
                tool=name,
                title=f"{query}-命中{index}",
                detail="摘要",
                source=f"wiki/{query}-{index}.md",
            )
            for index in range(hits)
        ]
        trace = ProviderTrace(
            provider=f"agent:{name}",
            capability="agent_loop",
            status="success" if evidence else "empty",
            result_count=len(evidence),
        )
        return evidence, "观察", trace

    return runner


def _scripted_complete(actions: list[dict]):
    remaining = list(actions)

    def complete(messages, timeout=0, temperature=0.0):
        if not remaining:
            return None, None, "script exhausted"
        return json.dumps(remaining.pop(0), ensure_ascii=False), None, ""

    return complete


def test_loop_executes_tools_then_finishes_with_gaps() -> None:
    result = run_agent_loop(
        "科创50的支撑点位在哪",
        tools={"kb_search": _tool("kb_search"), "web_search": _tool("web_search")},
        steps_budget=4,
        complete_fn=_scripted_complete(
            [
                {"tool": "web_search", "args": {"query": "科创50 当前点位"}},
                {
                    "tool": "finish",
                    "args": {
                        "sufficient": False,
                        "assessment": "周内行情证据不足，不能定性",
                        "gaps": ["缺指数日K行情"],
                    },
                },
            ]
        ),
    )

    assert [step.tool for step in result.steps] == ["web_search", "finish"]
    assert len(result.evidence) == 1
    assert result.sufficient is False
    assert result.assessment == "周内行情证据不足，不能定性"
    assert result.gaps == ("缺指数日K行情",)
    assert result.stop_reason == "agent finish"
    assert result.traces[0].provider == "agent:web_search"


def test_gap_finish_must_try_relevant_available_capability_once() -> None:
    """Agent 不能在相关白名单工具尚未尝试时直接把可补缺口交给用户。"""

    contract = ResearchTaskContract(
        task_id="gap-before-attempt",
        question="本周市场下跌的外部触发是什么",
        subject="A股市场",
        subject_kind="market_pattern",
        question_type="market_cause",
        required_outputs=(
            RequiredOutput(
                "external_cause_evidence",
                "时间对齐的外部触发",
                ("web_search", "news_search"),
                True,
            ),
        ),
        allowed_capabilities=("web_search", "news_search"),
        research_tier="quick",
    )
    calls: list[str] = []

    def web_tool(query: str):
        calls.append(query)
        return _tool("web_search")(query)

    result = run_agent_loop(
        contract.question,
        tools={"web_search": web_tool, "news_search": _tool("news_search", hits=0)},
        steps_budget=2,
        research_state=ResearchState.from_contract(contract),
        complete_fn=_scripted_complete(
            [
                {
                    "tool": "finish",
                    "args": {
                        "sufficient": False,
                        "assessment": "外部触发仍待核验",
                        "gaps": ["缺外部证据"],
                    },
                },
                {
                    "tool": "web_search",
                    "args": {"query": "本周 A 股下跌 外部触发"},
                },
                {
                    "tool": "finish",
                    "args": {
                        "sufficient": True,
                        "assessment": "已取得时间窗口内的外部线索",
                        "gaps": [],
                    },
                },
            ]
        ),
    )

    assert calls == ["本周 A 股下跌 外部触发"]
    assert [step.tool for step in result.steps] == ["finish", "web_search", "finish"]
    assert "白名单能力尚未尝试" in result.steps[0].observation
    assert result.sufficient is True


def test_gap_finish_is_accepted_after_relevant_tool_returned_empty() -> None:
    """空结果也算已尝试；stop gate 不做隐藏重试管线。"""

    contract = ResearchTaskContract(
        task_id="gap-after-empty",
        question="未知事件",
        subject=None,
        subject_kind=None,
        question_type="general_finance_qa",
        required_outputs=(
            RequiredOutput("supporting_evidence", "可回查来源", ("web_search",), True),
        ),
        allowed_capabilities=("web_search",),
        research_tier="quick",
    )
    result = run_agent_loop(
        contract.question,
        tools={"web_search": _tool("web_search", hits=0)},
        steps_budget=2,
        research_state=ResearchState.from_contract(contract),
        complete_fn=_scripted_complete(
            [
                {"tool": "web_search", "args": {"query": "未知事件"}},
                {
                    "tool": "finish",
                    "args": {"sufficient": False, "assessment": "", "gaps": ["无结果"]},
                },
            ]
        ),
    )

    assert [step.tool for step in result.steps] == ["web_search", "finish"]
    assert result.sufficient is False
    assert result.stop_reason == "agent finish"


def test_structured_evidence_gets_stable_content_hash() -> None:
    evidence, _ = agent_research.block_lines_to_evidence(
        "market_data",
        "2026-07-20：上证指数 -1.2%",
        "本地 DuckDB",
    )
    assert evidence[0].content_hash
    assert evidence[0].content_hash == agent_research.evidence_content_hash(evidence[0])


def test_structured_evidence_can_inherit_block_snapshot_date() -> None:
    evidence, _ = agent_research.block_lines_to_evidence(
        "market_data",
        "当前成交额21949亿元\n2026-07-20：指数上涨0.85%",
        "本地 DuckDB",
        source_date="2026-07-23",
    )

    assert [item.source_date for item in evidence] == [
        "2026-07-23",
        "2026-07-23",
    ]


def test_default_news_tool_passes_the_episode_information_cutoff(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_news(query: str, **kwargs):
        captured["query"] = query
        captured["as_of"] = kwargs.get("as_of")
        return agent_research.market_news.NewsFetchResult(
            (),
            ProviderTrace(
                provider="东财",
                capability="directional_news",
                status="empty",
            ),
        )

    monkeypatch.setattr(
        agent_research.market_news,
        "fetch_eastmoney_news_result",
        fake_news,
    )
    tools = agent_research.build_default_tools(lambda *_args, **_kwargs: object())
    context = agent_research.AgentToolContext(
        ResearchDeadline.from_timeout(5.0),
        lambda: False,
        InformationCutoff(date(2026, 7, 24), "requested"),
    )

    tools["news_search"]("A股下跌原因", context)

    assert captured == {
        "query": "A股下跌原因",
        "as_of": date(2026, 7, 24),
    }


def test_default_news_tool_tightens_cutoff_to_explicit_query_window(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_news(query: str, **kwargs):
        captured["query"] = query
        captured["as_of"] = kwargs.get("as_of")
        return agent_research.market_news.NewsFetchResult(
            (),
            ProviderTrace(
                provider="东财",
                capability="directional_news",
                status="empty",
            ),
        )

    monkeypatch.setattr(
        agent_research.market_news,
        "fetch_eastmoney_news_result",
        fake_news,
    )
    tools = agent_research.build_default_tools(lambda *_args, **_kwargs: object())
    context = agent_research.AgentToolContext(
        ResearchDeadline.from_timeout(5.0),
        lambda: False,
        InformationCutoff(date(2026, 7, 27), "runtime_default"),
    )

    tools["news_search"](
        "2026年7月24日 A股大跌原因 上证指数 7月20日至24日",
        context,
    )

    assert captured == {
        "query": "2026年7月24日 A股大跌原因 上证指数 7月20日至24日",
        "as_of": date(2026, 7, 24),
    }


def test_default_news_tool_keeps_legacy_context_without_cutoff_compatible(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_news(query: str, **kwargs):
        captured["query"] = query
        captured["as_of"] = kwargs.get("as_of")
        return agent_research.market_news.NewsFetchResult(
            (),
            ProviderTrace(
                provider="东财",
                capability="directional_news",
                status="empty",
            ),
        )

    monkeypatch.setattr(
        agent_research.market_news,
        "fetch_eastmoney_news_result",
        fake_news,
    )
    tools = agent_research.build_default_tools(lambda *_args, **_kwargs: object())

    tools["news_search"](
        "A股下跌原因",
        agent_research.AgentToolContext(ResearchDeadline.from_timeout(5.0)),
    )

    assert captured == {"query": "A股下跌原因", "as_of": None}


def test_tool_action_binds_evidence_to_known_hypothesis() -> None:
    contract = ResearchTaskContract(
        task_id="hypothesis-binding",
        question="明天是反弹还是继续下跌",
        subject="A股市场",
        subject_kind="market_pattern",
        question_type="market_forecast",
        required_outputs=(
            RequiredOutput("rebound_case", "反弹情景", ("web_search",), True),
        ),
        allowed_capabilities=("web_search",),
        research_tier="quick",
    )
    state = ResearchState.from_contract(contract)
    # RequiredOutput 也作为状态假设的来源，模拟通用 contract 的真实路径。
    state.add_hypothesis("rebound_case", "反弹情景")
    result = run_agent_loop(
        contract.question,
        tools={"web_search": _tool("web_search")},
        steps_budget=1,
        research_state=state,
        complete_fn=_scripted_complete(
            [
                {
                    "tool": "web_search",
                    "args": {
                        "query": "明天反弹触发条件",
                        "hypothesis_ids": ["rebound_case", "unknown"],
                        "stance": "support",
                    },
                }
            ]
        ),
    )
    assert result.evidence[0].supports == ("rebound_case",)
    assert result.steps[0].hypothesis_ids == ("rebound_case",)


def test_duplicate_query_is_intercepted_without_execution() -> None:
    calls: list[str] = []

    def counting_tool(query: str):
        calls.append(query)
        return [], "空", ProviderTrace(
            provider="agent:kb_search", capability="agent_loop", status="empty"
        )

    result = run_agent_loop(
        "问题",
        tools={"kb_search": counting_tool},
        steps_budget=3,
        complete_fn=_scripted_complete(
            [
                {"tool": "kb_search", "args": {"query": "同一查询"}},
                {"tool": "kb_search", "args": {"query": "同一 查询"}},
                {"tool": "finish", "args": {"sufficient": False, "gaps": []}},
            ]
        ),
    )

    assert calls == ["同一查询"]
    assert "重复查询已拦截" in result.steps[1].observation


def test_two_empty_tool_results_record_no_information_gain_gap() -> None:
    state = ResearchState(
        question="问题",
        subject=None,
        question_type="general_finance_qa",
    )
    result = run_agent_loop(
        "问题",
        tools={"kb_search": _tool("kb_search", hits=0)},
        steps_budget=3,
        research_state=state,
        complete_fn=_scripted_complete(
            [
                {"tool": "kb_search", "args": {"query": "第一次查询"}},
                {"tool": "kb_search", "args": {"query": "第二次查询"}},
            ]
        ),
    )

    expected_gap = "连续两次检索未获得新增信息，无法继续补全证据。"
    assert result.stop_reason == "no_information_gain"
    assert result.gaps == (expected_gap,)
    assert [gap.description for gap in state.gaps] == [expected_gap]
    assert len(result.steps) == len(result.traces) == 2


def test_llm_unavailable_returns_partial_result() -> None:
    result = run_agent_loop(
        "问题",
        tools={"kb_search": _tool("kb_search")},
        steps_budget=3,
        complete_fn=_scripted_complete(
            [{"tool": "kb_search", "args": {"query": "查一下"}}]
        ),
    )

    assert len(result.evidence) == 1
    assert result.stop_reason.startswith("LLM 不可用")


def test_illegal_tool_stops_loop() -> None:
    result = run_agent_loop(
        "问题",
        tools={"kb_search": _tool("kb_search")},
        steps_budget=3,
        complete_fn=_scripted_complete(
            [{"tool": "rm_rf", "args": {"query": "x"}}]
        ),
    )

    assert result.steps == []
    assert "非法工具" in result.stop_reason


def test_step_budget_is_hard_limit() -> None:
    result = run_agent_loop(
        "问题",
        tools={"kb_search": _tool("kb_search")},
        steps_budget=2,
        complete_fn=_scripted_complete(
            [
                {"tool": "kb_search", "args": {"query": "一"}},
                {"tool": "kb_search", "args": {"query": "二"}},
                {"tool": "kb_search", "args": {"query": "三"}},
            ]
        ),
    )

    assert len([step for step in result.steps if step.tool != "finish"]) == 2
    assert result.stop_reason == "预算耗尽：步数"


def test_zero_total_budget_has_no_llm_or_tool_side_effect() -> None:
    llm_calls: list[float] = []
    tool_calls: list[str] = []

    def complete(messages, timeout=0, temperature=0.0):
        del messages, temperature
        llm_calls.append(timeout)
        return (
            '{"tool":"kb_search","args":{"query":"不应执行"},"reason":"x"}',
            None,
            "",
        )

    def tool(query: str):
        tool_calls.append(query)
        return _tool("kb_search")(query)

    result = run_agent_loop(
        "问题",
        tools={"kb_search": tool},
        total_seconds=0,
        complete_fn=complete,
    )

    assert llm_calls == []
    assert tool_calls == []
    assert result.stop_reason == "预算耗尽：总时长"


def test_root_deadline_clamps_llm_timeout() -> None:
    observed: list[float] = []
    deadline = ResearchDeadline(time.monotonic() + 0.5)

    def complete(messages, timeout=0, temperature=0.0):
        del messages, temperature
        observed.append(timeout)
        return (
            '{"tool":"finish","args":{"sufficient":false,"gaps":[]},"reason":"x"}',
            None,
            "",
        )

    result = run_agent_loop(
        "问题",
        tools={"kb_search": _tool("kb_search")},
        total_seconds=60,
        llm_timeout=15,
        deadline=deadline,
        complete_fn=complete,
    )

    assert result.stop_reason == "agent finish"
    assert len(observed) == 1
    assert 0 < observed[0] <= 0.5


def test_agent_loop_preserves_synthesis_reserve_for_root_deadline() -> None:
    observed: dict[str, float] = {}
    deadline = ResearchDeadline(
        time.monotonic() + 1.0,
        synthesis_reserve=0.8,
    )

    def complete(messages, timeout=0, temperature=0.0):
        del messages, temperature
        observed["llm_timeout"] = timeout
        return (
            '{"tool":"finish","args":{"sufficient":false,"gaps":[]},"reason":"x"}',
            None,
            "",
        )

    result = run_agent_loop(
        "问题",
        tools={"kb_search": _tool("kb_search")},
        total_seconds=60,
        llm_timeout=15,
        deadline=deadline,
        complete_fn=complete,
    )

    assert result.stop_reason == "agent finish"
    assert 0 < observed["llm_timeout"] <= 0.25


def test_tool_exception_degrades_to_failed_trace() -> None:
    def broken(query: str):
        raise RuntimeError("boom")

    result = run_agent_loop(
        "问题",
        tools={"web_search": broken},
        steps_budget=2,
        complete_fn=_scripted_complete(
            [
                {"tool": "web_search", "args": {"query": "查"}},
                {"tool": "finish", "args": {"sufficient": False, "gaps": []}},
            ]
        ),
    )

    assert result.traces[0].status == "request_error"
    assert "工具执行失败" in result.steps[0].observation


def test_should_run_modes(monkeypatch) -> None:
    monkeypatch.setenv(agent_research.ENV_MODE, "off")
    assert not should_run(("web_search",))
    monkeypatch.setenv(agent_research.ENV_MODE, "auto")
    assert should_run(("market_quote", "web_search"))
    assert not should_run(("market_quote",))
    monkeypatch.setenv(agent_research.ENV_MODE, "on")
    assert should_run(())


def test_configured_step_budget_supports_deep_hard_ceiling(monkeypatch) -> None:
    monkeypatch.delenv(agent_research.ENV_MAX_STEPS, raising=False)
    assert agent_research.max_steps() == agent_research.DEFAULT_MAX_STEPS == 4

    monkeypatch.setenv(agent_research.ENV_MAX_STEPS, "24")
    assert agent_research.max_steps() == 24
    monkeypatch.setenv(agent_research.ENV_MAX_STEPS, "25")
    assert agent_research.max_steps() == 24
    monkeypatch.setenv(agent_research.ENV_MAX_STEPS, "0")
    assert agent_research.max_steps() == 1
    monkeypatch.setenv(agent_research.ENV_MAX_STEPS, "invalid")
    assert agent_research.max_steps() == agent_research.DEFAULT_MAX_STEPS


class TestKbSearchSeparatesFailureFromEmptiness:
    """检索**失败**不等于知识库**没有**——模型必须能区分这两件事。

    2026-08-12 历史对账：kb_search 22 次调用全部「无命中」，逐条统计后是
    **14 次 error + 6 次 timeout + 2 次真 empty**——即 20/22（91%）是工具故障，
    不是知识库为空。（初版据 3 条抽样写成「22/22 全部是 error」，是把抽样
    当成了全称断言，已更正。）
    模型没有理由把括号里那个 ``error`` 读成故障，于是把每一次故障都写成了
    「知识库没有回填」。

    更糟的是 ``ProviderTrace.status`` 记的是 ``empty`` 而非 ``error``：
    **任何按状态计数的下游审计都会看到零错误**，而覆盖率类检查永远发现不了
    这种静默降级。

    依据：ai-agent-book ch4「静默截断同样危险——Agent 会误以为自己看到了全部
    内容」；族 A 官方 custom-tools「Return isError: true ... so Claude can react
    to it」。
    """

    @staticmethod
    def _run(status: str, warning: str = "", hits=()):
        class _Telemetry:
            def __init__(self) -> None:
                self.status = status
                self.warning = warning

        class _Rag:
            def __init__(self) -> None:
                self.hits = list(hits)
                self.telemetry = _Telemetry()

        tools = agent_research.build_default_tools(lambda *_a, **_k: _Rag())
        context = agent_research.AgentToolContext(
            ResearchDeadline.from_timeout(5.0),
            lambda: False,
            InformationCutoff(date(2026, 7, 24), "requested"),
        )
        return tools["kb_search"]("瑞华泰 主营业务", context)

    def test_error_is_reported_as_a_failure_not_as_a_miss(self) -> None:
        evidence, observation, trace = self._run("error", "wiki-rag 调用失败")

        assert not evidence
        assert "检索失败" in observation
        assert "wiki-rag 调用失败" in observation
        # 反面同样要钉：不能再说成「无命中」
        assert "无命中" not in observation

    def test_error_is_counted_as_error_in_the_trace(self) -> None:
        """记成 empty 会让「工具坏了」在所有按状态计数的审计里消失。"""
        _evidence, _observation, trace = self._run("error", "wiki-rag 调用失败")

        assert trace.status == "error"

    def test_timeout_is_treated_the_same_way(self) -> None:
        _evidence, observation, trace = self._run("timeout", "wiki-rag 查询超时")

        assert trace.status == "error"
        assert "检索失败" in observation

    def test_a_genuine_miss_still_reads_as_a_miss(self) -> None:
        """真正的空结果不能被误报成故障——误报的代价是模型放弃一条本该走的路。"""
        _evidence, observation, trace = self._run("empty")

        assert "无命中" in observation
        assert trace.status == "empty"


class TestNoResultWordingSeparatesFailureFromEmptiness:
    """三个检索工具共用一条规则：查不了 ≠ 查不到。

    2026-08-12 历史对账，news_search 78 次「空手」拆开来看是四类：
      12 次 request_error（URLError / deadline exhausted）—— **故障**
      18 次 真的 empty
      12 次 其实是 harness 去重（「与本轮已有证据重复」）—— 压根不是失败
    kb_search 更极端：22 次「无命中」里 20 次是故障（14 error + 6 timeout）。

    危害不是少一条证据，而是模型据此写出**否定结论**——把「查不到」写成
    「不存在」。抽成一处而不是三个 runner 各写各的：同一条规则散在三处，
    改一处漏两处，且漏的时候没有任何门禁会红（BUILD 模式 6）。
    """

    def test_transport_failures_read_as_failures(self) -> None:
        for status in ("request_error", "proxy_unavailable", "parse_error", "timeout"):
            text = agent_research.describe_no_result("资讯", "无资讯", status, "URLError")

            assert "检索未能执行完成" in text, status
            assert "不要据此下否定结论" in text, status
            assert "无资讯" not in text, status

    def test_a_real_empty_keeps_its_own_wording(self) -> None:
        """误报的代价是模型放弃一条本该走的路，所以真空结果不能被写成故障。"""
        text = agent_research.describe_no_result("资讯", "无资讯", "empty", "title search")

        assert text.startswith("无资讯")
        assert "检索未能执行完成" not in text

    def test_wording_is_per_tool_not_shared(self) -> None:
        """共用规则 ≠ 共用措辞。

        第一版只传一个 kind 去拼 ``无{kind}``，对资讯读得通，
        对知识库就成了「无知识库」——中文读不通。
        """
        assert agent_research.describe_no_result(
            "知识库", "无命中", "empty"
        ).startswith("无命中")
        assert agent_research.describe_no_result(
            "网页", "无结果", "empty"
        ).startswith("无结果")


class TestRetrievalDegradationReachesTheModel:
    """检索降级必须跟着结果一起走——**哪怕这次有命中**。

    `kb_rag` 在稠密依赖不可用时把 hybrid/rerank 降到纯 BM25，并如实记
    `degraded` / `fallback_reason` / `recall_desc`。**遥测一直是诚实的，
    只是从没往上传**：`_kb_search` 只读 status 和 warning，有命中时观测就只是
    命中内容。于是模型拿到一份看起来完全正常的关键词命中，却不知道语义那一路
    根本没跑。

    这比报错更危险：报错至少是可见的失败，这是**成功外观下的能力降级**。
    ai-agent-book ch3 §混合检索：稀疏检索「读不懂同义词」（搜 kitty 找不到只写
    cat 的文档）——降级后丢的正是这一半能力，而这一半**无法从返回结果里看出来**。
    """

    @staticmethod
    def _telemetry(**kwargs):
        class _T:
            status = "ok"
            warning = ""
            degraded = False
            requested_mode = ""
            effective_mode = ""
            recall_desc = ""
            fallback_reason = ""

        tel = _T()
        for key, value in kwargs.items():
            setattr(tel, key, value)
        return tel

    def test_no_note_when_retrieval_was_not_degraded(self) -> None:
        """每次都挂一句「本次未降级」会训练模型忽略这一行，比不说更糟。"""
        assert agent_research._describe_retrieval_degradation(self._telemetry()) == ""

    def test_degraded_note_names_what_was_lost(self) -> None:
        note = agent_research._describe_retrieval_degradation(
            self._telemetry(
                degraded=True,
                requested_mode="hybrid",
                effective_mode="bm25",
                recall_desc="BM25 关键词",
                fallback_reason="dense_dependency_cached_unavailable",
            )
        )

        assert "已降级" in note
        assert "hybrid→bm25" in note
        # 关键：要说清丢的是什么能力，而不只是「降级了」
        assert "语义检索未生效" in note
        assert "不要据此下否定结论" in note

    def test_note_survives_missing_telemetry_fields(self) -> None:
        """字段不全也要报降级——认不出细节不等于可以不报（BUILD 模式 7）。"""
        note = agent_research._describe_retrieval_degradation(
            self._telemetry(degraded=True)
        )

        assert "已降级" in note

    def test_degradation_is_appended_even_when_there_are_hits(self) -> None:
        """有命中时也必须带上——这正是此前漏掉的那条路径。"""

        class _Hit:
            title = "瑞华泰"
            excerpt = "聚酰亚胺薄膜"
            file_path = "wiki/x.md"
            source_date = None

        class _Rag:
            hits = [_Hit()]
            telemetry = None

        _Rag.telemetry = TestRetrievalDegradationReachesTheModel._telemetry(
            degraded=True, requested_mode="hybrid", effective_mode="bm25"
        )
        tools = agent_research.build_default_tools(lambda *_a, **_k: _Rag())
        context = agent_research.AgentToolContext(
            ResearchDeadline.from_timeout(5.0),
            lambda: False,
            InformationCutoff(date(2026, 7, 24), "requested"),
        )

        evidence, observation, _trace = tools["kb_search"]("瑞华泰", context)

        assert evidence, "前提：这条用例要覆盖的是**有命中**的路径"
        assert "已降级" in observation


class TestKbSearchDeliveryTelemetry:
    """V7：kb tool_result 的送达遥测按实际 observation/evidence 计，不写死 800。"""

    def test_counts_actual_observation_chars_not_hardcoded_800(self) -> None:
        from intelligence.services.agent_research import (
            AgentEvidence,
            kb_delivery_telemetry,
        )

        evidence = [
            AgentEvidence(
                tool="kb_search",
                title="长电科技",
                detail="来源清单头部+半个 URL",
                source="本地知识库",
                internal_locator="wiki/entities/长电科技.md",
            )
        ]
        observation = "长电科技：来源清单头部+半个 URL"
        telemetry = kb_delivery_telemetry(evidence, observation)

        assert telemetry["delivered_chars"] == len(observation)
        assert telemetry["delivered_chars"] != 800
        assert telemetry["hit_count"] == 1
        assert telemetry["source_pages"] == ["wiki/entities/长电科技.md"]

    def test_kb_search_runner_matches_helper(self) -> None:
        from intelligence.services.agent_research import kb_delivery_telemetry

        class _Hit:
            title = "瑞华泰"
            excerpt = "聚酰亚胺薄膜"
            file_path = "wiki/entities/瑞华泰.md"
            source_date = None

        class _Rag:
            hits = [_Hit()]
            telemetry = None

        tools = agent_research.build_default_tools(lambda *_a, **_k: _Rag())
        context = agent_research.AgentToolContext(
            ResearchDeadline.from_timeout(5.0),
            lambda: False,
            InformationCutoff(date(2026, 7, 24), "requested"),
        )
        evidence, observation, _trace = tools["kb_search"]("瑞华泰", context)
        telemetry = kb_delivery_telemetry(evidence, observation)
        assert telemetry["hit_count"] == len(evidence)
        assert telemetry["delivered_chars"] == len(observation)
        assert "wiki/entities/瑞华泰.md" in telemetry["source_pages"]

    def test_detail_chars_counts_evidence_channel_not_observation_head(self) -> None:
        """R-15 测量缝：observation 每条截 [:80]，正文走 evidence.detail 通道。

        两通道必须分开计数，否则粗管道（V3）的送达量在传感器上永远显影不出来
        （2026-08-22 钙钛矿 live 探针：delivered_chars=580 而 detail 实为正文级）。
        """

        from intelligence.services.agent_research import (
            AgentEvidence,
            kb_delivery_telemetry,
        )

        detail = "正" * 300
        evidence = [
            AgentEvidence(
                tool="kb_search",
                title="曼恩斯特",
                detail=detail,
                source="本地知识库",
                internal_locator="wiki/entities/曼恩斯特.md",
            )
        ]
        observation = f"曼恩斯特：{detail[:80]}"
        telemetry = kb_delivery_telemetry(evidence, observation)

        assert telemetry["detail_chars"] == 300
        assert telemetry["delivered_chars"] == len(observation)
        assert telemetry["detail_chars"] > telemetry["delivered_chars"]


class TestKbSearchSemanticGate:
    """#424：kb_search 召回过 evidence_judge 语义闸（Engine A 主 KB 通道补闸）。

    该闸 Engine B 消融实测 +2.8/20；此前 kb_search 是全系统唯一不过闸的召回口。
    纪律：fail-open（裁判失败全量保留）、阈值触发（小结果集不花裁判预算）、
    滤除可见（送达≠召回必须能区分）、全滤≠无回填（语义闸正确工作不得被读成
    知识库缺口）。
    """

    @staticmethod
    def _hit(title: str) -> object:
        class _Hit:
            excerpt = f"{title} 的正文摘录"
            file_path = f"wiki/entities/{title}.md"
            source_date = None

        _Hit.title = title
        return _Hit()

    def _run(self, n_hits: int, *, judge=None, should=True):
        from unittest import mock

        hits = [self._hit(f"公司{i}") for i in range(n_hits)]

        class _Rag:
            telemetry = None

        _Rag.hits = hits
        tools = agent_research.build_default_tools(lambda *_a, **_k: _Rag())
        context = agent_research.AgentToolContext(
            ResearchDeadline.from_timeout(30.0),
            lambda: False,
            InformationCutoff(date(2026, 7, 24), "requested"),
        )
        judge_mock = mock.MagicMock(return_value=judge)
        with mock.patch.object(
            agent_research.evidence_judge, "should_judge", return_value=should
        ), mock.patch.object(
            agent_research.evidence_judge, "judge_relevance", judge_mock
        ):
            evidence, observation, trace = tools["kb_search"]("科创50 支撑位", context)
        return evidence, observation, trace, judge_mock

    def test_judge_filters_irrelevant_hits_and_notes_it(self) -> None:
        evidence, observation, _trace, judge_mock = self._run(
            5, judge=({0, 2}, "其余与本题无关")
        )
        assert judge_mock.called
        assert len(evidence) == 2
        assert {item.title for item in evidence} == {"公司0", "公司2"}
        assert "语义闸滤除 3 条" in observation

    def test_all_judged_out_reads_as_irrelevant_not_as_missing(self) -> None:
        evidence, observation, trace, _judge_mock = self._run(4, judge=(set(), "全部无关"))
        assert not evidence
        assert "全部判定与本题无关" in observation
        assert "非无回填" in observation
        assert "无命中" not in observation
        assert trace.status == "empty"

    def test_judge_failure_fails_open(self) -> None:
        evidence, observation, _trace, judge_mock = self._run(5, judge=None)
        assert judge_mock.called
        assert len(evidence) == 5
        assert "语义闸" not in observation

    def test_small_result_sets_skip_the_judge(self) -> None:
        evidence, _observation, _trace, judge_mock = self._run(
            agent_research.KB_JUDGE_MIN_HITS - 1, judge=({0}, "")
        )
        assert not judge_mock.called
        assert len(evidence) == agent_research.KB_JUDGE_MIN_HITS - 1

    def test_disabled_judge_skips_entirely(self) -> None:
        _evidence, _observation, _trace, judge_mock = self._run(
            6, judge=({0}, ""), should=False
        )
        assert not judge_mock.called
