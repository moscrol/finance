from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence.services import agent, kb_rag, llm_refine
from intelligence.services.agent import AGENT_TOOLS, MARKET_LIVE_TOOL, AgentSession
from intelligence.services.ask import AskOptions
from intelligence.services.skill_tools import SkillResult
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
            {"search_market_snapshot", "search_graph", "search_evidence", "search_wiki", "run_theme_module", "run_skill"},
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

    def test_run_skill_rejects_unknown(self) -> None:
        s = _session()
        out = s.tool_run_skill("does-not-exist")
        self.assertIn("未知 skill", out)
        self.assertEqual(s.citations, [])

    def test_run_skill_cites_g_and_marks_source(self) -> None:
        s = _session()
        fake = SkillResult(
            name="serenity-alpha",
            ok=True,
            title="液冷 弹性/预期差候选（2 家）",
            highlights=[
                "概念定位：主匹配 液冷；命中 液冷、液冷温控",
                "候选 英维克（002837｜core｜证据5｜逻辑卡✓｜直接）：液冷温控龙头",
            ],
            follow_ups=["英维克 的最新逻辑卡/证据硬不硬", "横向比较候选池近 5/10/20 日涨幅"],
            citation_source="serenity-alpha · serenity_context.py（本地 wiki·只读）",
            citation_detail="--term 液冷",
            command="serenity_context.py --term 液冷 --vault <kb-wiki> --format json",
        )
        with mock.patch.object(agent, "run_skill", return_value=fake):
            out = s.tool_run_skill("serenity-alpha", "液冷")
        self.assertIn("serenity-alpha", out)
        self.assertIn("候选 英维克", out)
        self.assertIn("可继续追问", out)
        self.assertIn("[G1]", out)
        self.assertEqual(s.citations[0].tag, "G1")
        self.assertIn("serenity-alpha", s.citations[0].source)
        self.assertIn("skill", s.sources_used)

    def test_run_skill_degrades_when_no_output(self) -> None:
        s = _session()
        fake = SkillResult(name="serenity-alpha", ok=False, warning="知识库未命中该词")
        with mock.patch.object(agent, "run_skill", return_value=fake):
            out = s.tool_run_skill("serenity-alpha", "不存在的词")
        self.assertIn("无产出", out)
        self.assertNotIn("skill", s.sources_used)
        self.assertEqual(s.citations, [])


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
        # (self.messages is one mutable list passed by reference, so assert on the
        # protocol prefix / by-role rather than the live-mutated tail)
        second_messages = called.call_args_list[1].args[0]
        roles = [m["role"] for m in second_messages]
        self.assertEqual(roles[:4], ["system", "user", "assistant", "tool"])
        tool_msgs = [m for m in second_messages if m["role"] == "tool"]
        self.assertIn("英维克", tool_msgs[0]["content"])

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
        tool_msgs = [m for m in called.call_args_list[1].args[0] if m["role"] == "tool"]
        self.assertTrue(tool_msgs)
        self.assertIn("未知工具", tool_msgs[0]["content"])

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


class MultiTurnAgentTests(unittest.TestCase):
    def test_follow_up_reuses_history_without_re_calling_tools(self) -> None:
        s = _session()
        prov = _provider()
        with mock.patch.object(
            llm_refine,
            "chat_with_tools",
            side_effect=[
                # turn 1: dispatch a tool, then answer
                (_tool_call_msg("search_graph", {"query": "液冷"}), prov, ""),
                (_final_msg("液冷核心是英维克[G2]。（非投资建议）"), prov, ""),
                # turn 2 (follow-up): answer straight from memory, no tool call
                (_final_msg("英维克比川润证据更硬[G2]。（非投资建议）"), prov, ""),
            ],
        ) as called:
            t1 = s.start("液冷")
            cites_after_t1 = len(s.citations)
            t2 = s.ask("英维克和川润谁证据更硬")

        self.assertTrue(t1.ok)
        self.assertTrue(t2.ok)
        # follow-up answered with zero tool calls (reused history)
        self.assertEqual(t2.steps, [])
        # no new citations were registered on the follow-up turn
        self.assertEqual(len(s.citations), cites_after_t1)
        # the follow-up round-trip saw the full prior conversation + the new question
        followup_messages = called.call_args_list[2].args[0]
        roles = [m["role"] for m in followup_messages]
        self.assertEqual(roles[:6], ["system", "user", "assistant", "tool", "assistant", "user"])
        # turn-1 evidence (英维克) is still in the context the follow-up reasons over
        tool_msgs = [m for m in followup_messages if m["role"] == "tool"]
        self.assertIn("英维克", tool_msgs[0]["content"])
        # and the new follow-up question is tagged as such
        last_user = [m for m in followup_messages if m["role"] == "user"][-1]
        self.assertIn("追问", last_user["content"])
        self.assertIn("英维克和川润", last_user["content"])

    def test_follow_up_can_autonomously_call_more_tools(self) -> None:
        s = _session()
        prov = _provider()
        with mock.patch.object(
            llm_refine,
            "chat_with_tools",
            side_effect=[
                (_tool_call_msg("search_graph", {"query": "液冷"}), prov, ""),
                (_final_msg("液冷核心是英维克[G2]。（非投资建议）"), prov, ""),
                # follow-up: the agent decides it needs fresh evidence and calls a tool
                (_tool_call_msg("search_evidence", {"target": "英维克"}, call_id="c2"), prov, ""),
                (_final_msg("英维克有订单放量[R1]。（非投资建议）"), prov, ""),
            ],
        ):
            s.start("液冷")
            cites_after_t1 = len(s.citations)
            t2 = s.ask("英维克最新有什么硬证据")

        self.assertTrue(t2.ok)
        # the follow-up autonomously dispatched another tool
        self.assertEqual(len(t2.steps), 1)
        self.assertEqual(t2.steps[0].tool, "search_evidence")
        # which extended the cumulative citation registry
        self.assertGreater(len(s.citations), cites_after_t1)
        self.assertIn("R", s.sources_used)

    def test_failed_follow_up_rolls_back_history(self) -> None:
        s = _session()
        prov = _provider()
        with mock.patch.object(
            llm_refine,
            "chat_with_tools",
            side_effect=[
                (_tool_call_msg("search_graph", {"query": "液冷"}), prov, ""),
                (_final_msg("液冷核心是英维克[G2]。（非投资建议）"), prov, ""),
            ],
        ):
            s.start("液冷")
        msgs_before = len(s.messages)
        cites_before = len(s.citations)
        # the follow-up LLM call fails -> graceful degrade + rollback for a clean retry
        with mock.patch.object(llm_refine, "chat_with_tools", return_value=(None, prov, "LLM 调用 HTTP 503")):
            t2 = s.ask("会不会有风险")
        self.assertFalse(t2.ok)
        self.assertIn("503", t2.reason)
        self.assertEqual(len(s.messages), msgs_before)
        self.assertEqual(len(s.citations), cites_before)

    def test_ask_without_prior_turn_starts_conversation(self) -> None:
        s = _session()
        prov = _provider()
        with mock.patch.object(
            llm_refine,
            "chat_with_tools",
            side_effect=[(_final_msg("结论[G2]。（非投资建议）"), prov, "")],
        ):
            res = s.ask("液冷")
        self.assertTrue(res.ok)
        self.assertIsNotNone(s.messages)
        self.assertEqual(s.messages[0]["role"], "system")


def _seed_market_db(db_path: str, trade_date: str = "2026-06-11") -> None:
    """建一个带真实 schema 的合成 DuckDB：写入某交易日的大盘环境 + 一个双红/涨停热度题材
    (液冷服务器) + 题材内强势股 & 新高股。供 P2.5 search_market_live 单测使用，无需外部库。"""
    import duckdb

    from market_feature_store.db import SCHEMA_PATH

    con = duckdb.connect(db_path)
    try:
        con.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        con.execute(
            "INSERT INTO fact_market_daily (trade_date, market_stage, total_amount, "
            "amount_vs_yesterday_pct, advancers, limit_up, limit_down, top3_industry_ratio, "
            "industry_1, industry_1_ratio, industry_2, industry_2_ratio, industry_3, industry_3_ratio) "
            "VALUES (?, '主升', 18234.5, 6.2, 3120, 64, 8, 32.0, '电子', 18.0, '电力设备', 9.0, '通信', 5.0)",
            [trade_date],
        )
        con.execute(
            "INSERT INTO fact_sector_daily (trade_date, sector_ts_code, sector_name, sw_l1, "
            "pct_chg, amount, diff_ratio) VALUES (?, 'BK0001', '液冷服务器', '电子', 4.8, 820.0, 22.5)",
            [trade_date],
        )
        con.execute(
            "INSERT INTO fact_theme_limit_heat_daily (trade_date, sector_ts_code, sector_name, "
            "dimension, scope, limit_up_count, total_count, market_share, fd_amount, rank) "
            "VALUES (?, 'BK0001', '液冷服务器', 'theme', 'all', 5, 18, 0.12, 3.4, 1)",
            [trade_date],
        )
        con.execute(
            "INSERT INTO fact_sector_stock_daily (trade_date, sector_ts_code, sector_name, sw_l1, "
            "stock_ts_code, stock_name, pct_chg, amount, high_status, high_status_label) VALUES "
            "(?, 'BK0001', '液冷服务器', '电子', '002837.SZ', '英维克', 10.0, 25.6, 'new_high', '创年内新高'),"
            "(?, 'BK0001', '液冷服务器', '电子', '300017.SZ', '网宿科技', 6.4, 12.1, '', '')",
            [trade_date, trade_date],
        )
        con.execute(
            "INSERT INTO fact_stock_high_daily (trade_date, stock_ts_code, stock_name, "
            "primary_high_label, amount, pct_chg) VALUES (?, '002837.SZ', '英维克', '创年内新高', 25.6, 10.0)",
            [trade_date],
        )
    finally:
        con.close()


class MarketLiveToolTests(unittest.TestCase):
    """P2.5 实时盘面 opt-in 工具 search_market_live（合成 DuckDB，不依赖外部库）。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db_path = str(Path(self._tmp.name) / "market_feature_store.duckdb")
        _seed_market_db(self.db_path, trade_date="2026-06-11")

    def test_not_registered_without_db_path(self) -> None:
        # opt-in：未配置 market_db_path → 默认 6 件套逐字节不变，工具不注册
        s = _session()
        self.assertFalse(s._market_live_available)
        self.assertIs(s._tools, AGENT_TOOLS)
        self.assertEqual(len(s._tools), 6)
        self.assertNotIn("search_market_live", {t["function"]["name"] for t in s._tools})

    def test_tool_is_optin_and_wellformed(self) -> None:
        # MARKET_LIVE_TOOL 刻意不在 AGENT_TOOLS 里，但自身 schema 合法
        self.assertNotIn("search_market_live", {t["function"]["name"] for t in AGENT_TOOLS})
        self.assertEqual(MARKET_LIVE_TOOL["type"], "function")
        fn = MARKET_LIVE_TOOL["function"]
        self.assertEqual(fn["name"], "search_market_live")
        self.assertTrue(fn["description"])
        self.assertEqual(fn["parameters"]["type"], "object")
        self.assertIn("theme", fn["parameters"]["properties"])

    def test_registered_when_db_available(self) -> None:
        s = _session(market_db_path=self.db_path)
        self.assertTrue(s._market_live_available)
        names = {t["function"]["name"] for t in s._tools}
        self.assertIn("search_market_live", names)
        self.assertEqual(len(s._tools), 7)
        # 默认套件常量本身没有被污染
        self.assertEqual(len(AGENT_TOOLS), 6)
        self.assertNotIn("search_market_live", {t["function"]["name"] for t in AGENT_TOOLS})

    def test_reports_environment_and_cites_S(self) -> None:
        s = _session(market_db_path=self.db_path)
        out = s.tool_search_market_live("液冷")
        self.assertIn("实时盘面（2026-06-11", out)
        self.assertIn("主升", out)
        self.assertIn("电子", out)  # 容量前三板块
        self.assertIn("[S1]", out)
        self.assertIn("S", s.sources_used)
        # 复用 [S#]，绝不新增其它前缀（评测闸只认 S/G/R/W）
        self.assertTrue(s.citations)
        self.assertTrue(all(c.tag.startswith("S") for c in s.citations))

    def test_hits_double_red_and_limit_heat_and_theme_stocks(self) -> None:
        s = _session(market_db_path=self.db_path)
        out = s.tool_search_market_live("液冷")
        self.assertIn("双红题材命中「液冷服务器」", out)
        self.assertIn("落在容量前三板块", out)
        self.assertIn("涨停热度命中「液冷服务器」", out)
        self.assertIn("涨停 5 家 / 共 18 家", out)
        # 题材个股：强势股按量价加权、新高股映射
        self.assertIn("英维克", out)
        self.assertIn("创年内新高", out)

    def test_theme_miss_is_graceful(self) -> None:
        s = _session(market_db_path=self.db_path)
        out = s.tool_search_market_live("锂电池")
        # 题材未上榜：如实说明，仍给出大盘环境与 [S#]，不报错
        self.assertIn("实时盘面（2026-06-11", out)
        self.assertIn("未进入双红题材榜", out)
        self.assertNotIn("双红题材命中", out)
        self.assertIn("S", s.sources_used)

    def test_theme_match_helper(self) -> None:
        match = AgentSession._theme_match
        self.assertEqual(match("液冷服务器", ["液冷服务器"]), "液冷服务器")  # 精确
        self.assertEqual(match("液冷", ["液冷服务器"]), "液冷服务器")  # 子串
        self.assertEqual(match("液冷服务器概念", ["液冷服务器"]), "液冷服务器")  # 反向子串
        self.assertEqual(match(" 液 冷 ", ["光模块", "液冷服务器"]), "液冷服务器")  # 去空白
        self.assertIsNone(match("锂电池", ["液冷服务器"]))  # 未命中
        self.assertIsNone(match("", ["液冷服务器"]))  # 空词

    def test_degrades_on_broken_db_and_query_error(self) -> None:
        # (a) 损坏库：路径在但不是合法 DuckDB → 优雅降级，工具不注册，默认 6 件套不变
        broken = str(Path(self._tmp.name) / "broken.duckdb")
        Path(broken).write_bytes(b"not a duckdb file at all")
        s_broken = _session(market_db_path=broken)
        self.assertFalse(s_broken._market_live_available)
        self.assertEqual(len(s_broken._tools), 6)
        self.assertNotIn("search_market_live", {t["function"]["name"] for t in s_broken._tools})

        # (b) 查询期异常守护：库可用但底层查询抛错 → 返回降级提示，不抛、不污染来源/引用
        s_ok = _session(market_db_path=self.db_path)
        self.assertTrue(s_ok._market_live_available)
        with mock.patch.object(type(s_ok._market_adapter), "get_market_daily", side_effect=RuntimeError("boom")):
            out = s_ok.tool_search_market_live("液冷")
        self.assertIn("实时盘面查询失败", out)
        self.assertNotIn("S", s_ok.sources_used)
        self.assertEqual(s_ok.citations, [])


if __name__ == "__main__":
    unittest.main()
