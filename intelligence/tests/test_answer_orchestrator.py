from __future__ import annotations

import json
import unittest
import tempfile
from pathlib import Path
from unittest import mock

from intelligence.services.answer_orchestrator import (
    DEPTH_DEEP,
    DEPTH_STANDARD,
    QUESTION_MARKET_FORECAST,
    QUESTION_MARKET_REVIEW,
    QUESTION_NEWS_IMPACT,
    QUESTION_STOCK_DEEP_DIVE,
    QUESTION_THEME_ANALYSIS,
    QUESTION_VALUATION,
    plan_answer_question,
)
from intelligence.services.ask import AskOptions, answer_query, render_conversation_answer
from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services.llm_refine import SynthesisResult


class AnswerOrchestratorTests(unittest.TestCase):
    def test_base_finance_mode_keeps_retrieval_floor_for_quick_answers(self) -> None:
        plan = plan_answer_question("600519 快答：最近消息、产业链和财务估值怎么看")

        self.assertIsNotNone(plan.base_finance_mode)
        assert plan.base_finance_mode is not None
        self.assertTrue(plan.base_finance_mode.require_market)
        self.assertTrue(plan.base_finance_mode.require_memory)
        self.assertTrue(plan.base_finance_mode.require_news)
        self.assertTrue(plan.base_finance_mode.require_graph)
        self.assertTrue(plan.base_finance_mode.require_financials)
        self.assertTrue(plan.base_finance_mode.quick_answer)
        prompt = plan.to_prompt_block()
        self.assertIn("“快答”只缩短表达，不得跳过已触发的检索", prompt)
        self.assertIn("直接定性、最强证据、主要风险、条件边界", prompt)
        self.assertIn("用户观点只作为待检验假设", prompt)
        self.assertIn("缺 X → 仍可判 Y → 验证窗口 Z", prompt)

    def test_stock_deep_dive_plan_requires_multilens_and_hybrid_rag(self) -> None:
        plan = plan_answer_question("用 hybrid 深挖飞凯材料，还有没有上涨空间")

        self.assertEqual(plan.question_type, QUESTION_STOCK_DEEP_DIVE)
        self.assertEqual(plan.depth, DEPTH_DEEP)
        joined_lenses = "\n".join(plan.required_lenses)
        joined_sources = "\n".join(plan.retrieval_plan)
        joined_gates = "\n".join(plan.quality_gates)
        self.assertIn("公司本体", joined_lenses)
        self.assertIn("市场结构", joined_lenses)
        self.assertIn("板块生命周期", joined_lenses)
        self.assertIn("二阶导", joined_lenses)
        self.assertIn("wiki hybrid RAG", joined_sources)
        self.assertIn("L3 evidence tools", joined_sources)
        self.assertIn("D1/D2/D3", joined_sources)
        self.assertIn("L3 硬证据", "\n".join(plan.missing_data_policy))
        self.assertIn("市场正在奖励谁、抛弃谁、犹豫谁", joined_gates)

    def test_entity_anchor_turns_on_market_and_memory_floor(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch(
                "intelligence.services.ask.entity_anchor.resolve_entity_anchor",
                return_value=EntityAnchor(
                    entity="贵州茅台",
                    ticker="600519.SH",
                    concepts=("白酒",),
                ),
            ),
        ):
            result = answer_query(
                AskOptions(
                    query="茅台最近怎么样",
                    exports_dir=tmp,
                    kb_wiki=Path(tmp),
                    use_modules=False,
                    use_wiki_rag=False,
                )
            )

        self.assertIsNotNone(result.question_plan)
        assert result.question_plan is not None
        self.assertIsNotNone(result.question_plan.base_finance_mode)
        assert result.question_plan.base_finance_mode is not None
        self.assertTrue(result.question_plan.base_finance_mode.require_market)
        self.assertTrue(result.question_plan.base_finance_mode.require_memory)

    def test_general_base_presenter_does_not_echo_question_as_title(self) -> None:
        query = "E2E-desktop-123 第三轮有哪些风险"
        with tempfile.TemporaryDirectory() as tmp:
            result = answer_query(
                AskOptions(
                    query=query,
                    exports_dir=tmp,
                    kb_wiki=Path(tmp),
                    use_modules=False,
                    use_wiki_rag=False,
                )
            )

        rendered = render_conversation_answer(result)
        self.assertIn("# 金融问题裁决", rendered)
        self.assertNotIn(f"# {query}", rendered)

    def test_market_forecast_plan_requires_verifiable_hypotheses(self) -> None:
        plan = plan_answer_question("站在6.29视角，6.30的行情怎么看")

        self.assertEqual(plan.question_type, QUESTION_MARKET_FORECAST)
        self.assertEqual(plan.depth, DEPTH_STANDARD)
        joined_lenses = "\n".join(plan.required_lenses)
        joined_sources = "\n".join(plan.retrieval_plan)
        joined_contract = "\n".join(plan.output_contract)
        self.assertIn("大盘阶段", joined_lenses)
        self.assertIn("MA5", joined_lenses)
        self.assertIn("风格判断", joined_lenses)
        self.assertIn("四源合议", joined_lenses)
        self.assertIn("全量复盘硬字段", joined_lenses)
        self.assertIn("双红演变", joined_lenses)
        self.assertIn("策略三", joined_lenses)
        self.assertIn("策略二", joined_lenses)
        self.assertIn("策略一/策略四", joined_lenses)
        self.assertIn("策略选择器", joined_lenses)
        self.assertIn("DuckDB market context", joined_sources)
        self.assertIn("全量复盘数据块", joined_sources)
        self.assertIn("diff_ratio", joined_sources)
        self.assertIn("晚间卖方", joined_sources)
        self.assertIn("晨汇", joined_sources)
        self.assertIn("外盘双源", joined_sources)
        self.assertIn("/reviews/global-market", joined_sources)
        self.assertIn("web/finance search", joined_sources)
        self.assertIn("daily-agent 策略候选", joined_sources)
        self.assertIn("forecast_preflight", joined_sources)
        self.assertIn("DeepDive", joined_sources)
        self.assertIn("source_trade_date", "\n".join(plan.quality_gates))
        self.assertIn("复盘前置查漏门", "\n".join(plan.quality_gates))
        self.assertIn("正式复盘", "\n".join(plan.quality_gates))
        self.assertIn("双红题材", "\n".join(plan.quality_gates))
        self.assertIn("核心个股", "\n".join(plan.quality_gates))
        self.assertIn("可盘后验证", joined_contract)
        self.assertIn("四源合议", joined_contract)
        self.assertIn("个股深挖里的盘面视角", joined_contract)
        self.assertIn("策略组合", joined_contract)
        self.assertIn("先补 DeepDive", "\n".join(plan.missing_data_policy))

    def test_latest_trading_day_review_routes_to_compact_market_review(self) -> None:
        plan = plan_answer_question(
            "请复盘最新交易日的市场结构、主线、赚钱效应和主要风险。"
        )

        self.assertEqual(plan.question_type, QUESTION_MARKET_REVIEW)
        self.assertEqual(plan.depth, DEPTH_STANDARD)
        joined_lenses = "\n".join(plan.required_lenses)
        joined_sources = "\n".join(plan.retrieval_plan)
        joined_contract = "\n".join(plan.output_contract)
        self.assertIn("市场结构", joined_lenses)
        self.assertIn("主线与赚钱效应", joined_lenses)
        self.assertIn("DuckDB market context", joined_sources)
        self.assertIn("Daily Review", joined_sources)
        self.assertIn("内部表名", "\n".join(plan.quality_gates))
        self.assertIn("少量自然小标题", joined_contract)
        self.assertIn("不要机械覆盖公司本体", joined_contract)
        self.assertIn("按数据粒度表述主线缺口", joined_contract)
        self.assertIn("不要出现反方审稿", joined_contract)
        self.assertIn("最多使用 5 个二级标题", joined_contract)

    def test_short_market_review_phrases_route_to_market_review(self) -> None:
        for query in (
            "今日复盘",
            "市场总览",
            "复盘一下今天的赚钱效应",
        ):
            with self.subTest(query=query):
                self.assertEqual(
                    plan_answer_question(query).question_type,
                    QUESTION_MARKET_REVIEW,
                )

    def test_deep_dive_trigger_beats_industry_chain_keyword(self) -> None:
        plan = plan_answer_question("深挖英维克，它在液冷产业链的位置")

        self.assertEqual(plan.question_type, QUESTION_STOCK_DEEP_DIVE)

    def test_forecast_prior_short_query_routes_to_market_forecast(self) -> None:
        plan = plan_answer_question("复盘先验")

        self.assertEqual(plan.question_type, QUESTION_MARKET_FORECAST)

    def test_valuation_triggers_route_to_valuation_plan(self) -> None:
        plan = plan_answer_question("帮我拍估值：寒武纪现在贵不贵")

        self.assertEqual(plan.question_type, QUESTION_VALUATION)
        self.assertEqual(plan.depth, "deep")
        joined_lenses = "\n".join(plan.required_lenses)
        self.assertIn("可比公司估值带", joined_lenses)
        self.assertIn("隐含增长率反推", joined_lenses)
        self.assertIn("禁止输出单点目标价", "\n".join(plan.quality_gates))

    def test_deep_dive_trigger_beats_valuation_keyword(self) -> None:
        plan = plan_answer_question("深挖汇成股份，顺便看下估值分位")

        self.assertEqual(plan.question_type, QUESTION_STOCK_DEEP_DIVE)

    def test_news_impact_plan_starts_from_fact_extraction(self) -> None:
        plan = plan_answer_question("读一下这条公告，对产业链有什么传导冲击")

        self.assertEqual(plan.question_type, QUESTION_NEWS_IMPACT)
        joined_lenses = "\n".join(plan.required_lenses)
        joined_sources = "\n".join(plan.retrieval_plan)
        joined_gates = "\n".join(plan.quality_gates)
        self.assertIn("事实抽取", joined_lenses)
        self.assertIn("产业链传导", joined_lenses)
        self.assertIn("disclosure/interaction API", joined_sources)
        self.assertIn("不能直接跳到受益股", joined_gates)

    def test_theme_plan_handles_bare_sector_question(self) -> None:
        plan = plan_answer_question("科技细分里哪个方向还有上涨空间")

        self.assertEqual(plan.question_type, QUESTION_THEME_ANALYSIS)
        joined_lenses = "\n".join(plan.required_lenses)
        joined_sources = "\n".join(plan.retrieval_plan)
        self.assertIn("题材结构", joined_lenses)
        self.assertIn("强势股队列", joined_lenses)
        self.assertIn("theme candidates", joined_sources)

    def test_prompt_block_exposes_plan_without_requiring_template_output(self) -> None:
        plan = plan_answer_question("深挖顺络电子")
        block = plan.to_prompt_block()

        self.assertIn("问答编排计划", block)
        self.assertIn("问题类型：stock_deep_dive", block)
        self.assertIn("不要机械复述", block)
        self.assertIn("输出前质检门槛", block)

    def test_ask_compose_injects_question_plan_into_llm_prompt(self) -> None:
        captured: dict[str, str] = {}

        def fake_synthesize(messages: list[dict], **_: object):
            captured["prompt"] = str(messages[1]["content"])
            return None, "mocked"

        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "intelligence.services.ask.llm_refine.synthesize_messages_with_review",
            side_effect=fake_synthesize,
        ):
            wiki = Path(tmp) / "wiki"
            (wiki / "relations").mkdir(parents=True)
            result = answer_query(
                AskOptions(
                    query="深挖飞凯材料",
                    exports_dir=tmp,
                    kb_wiki=wiki,
                    use_modules=False,
                    use_wiki_rag=False,
                    compose=True,
                )
            )

        self.assertIsNotNone(result.question_plan)
        assert result.question_plan is not None
        self.assertEqual(result.question_plan.question_type, QUESTION_STOCK_DEEP_DIVE)
        self.assertIn("问答编排计划", captured["prompt"])
        self.assertIn("问题类型：stock_deep_dive", captured["prompt"])
        self.assertIn("公司本体", captured["prompt"])

    def test_market_review_compose_uses_daily_evidence_without_topic_graph(
        self,
    ) -> None:
        captured: dict[str, str] = {}

        def fake_synthesize(messages: list[dict], **_: object):
            captured["system"] = str(messages[0]["content"])
            captured["prompt"] = str(messages[1]["content"])
            return (
                SynthesisResult(
                    answer="7月10日指数弱、个股强，成交放大。",
                    provider="fixture",
                    model="fixture-model",
                ),
                "",
            )

        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "intelligence.services.ask.llm_refine.synthesize_messages",
            side_effect=fake_synthesize,
        ):
            wiki = Path(tmp) / "wiki"
            (wiki / "relations").mkdir(parents=True)
            result = answer_query(
                AskOptions(
                    query="请复盘最新交易日的市场结构和主要风险",
                    exports_dir=tmp,
                    kb_wiki=wiki,
                    supplemental_evidence=(
                        "### daily-review（截至 2026-07-10）\n"
                        "- 今日核心\n"
                        "  - 指标：上涨 3774 只；涨停 92 只；跌停 4 只"
                    ),
                    use_modules=False,
                    use_wiki_rag=False,
                    compose=True,
                )
            )

        self.assertEqual(result.question_plan.question_type, QUESTION_MARKET_REVIEW)
        self.assertIsNone(result.matched_theme)
        self.assertEqual(result.synthesis, "7月10日指数弱、个股强，成交放大。")
        self.assertIn("daily-review", captured["prompt"])
        self.assertIn("普通投资者", captured["system"])
        self.assertNotIn("知识图谱", captured["prompt"])

    def test_market_review_compose_injects_memory_as_incremental_prior(
        self,
    ) -> None:
        captured: dict[str, str] = {}

        def fake_synthesize(messages: list[dict], **_: object):
            captured["prompt"] = str(messages[1]["content"])
            return None, "mocked"

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch(
                "intelligence.services.ask.llm_refine.synthesize_messages",
                side_effect=fake_synthesize,
            ),
            mock.patch(
                "intelligence.services.ask.user_memory.memory_block_for_query",
                return_value="## 用户记忆检索块 [M]\n- 上次判断：缩量轮动",
            ),
            mock.patch(
                "intelligence.services.ask.checkpoint_recall.recall_block_for_query",
                return_value="## 回检块 [V]\n- 上次判断已半对",
            ),
            mock.patch(
                "intelligence.services.ask.experience_cards.load_cards",
                return_value=([], None),
            ),
            mock.patch(
                "intelligence.services.ask.experience_cards.render_for_prompt",
                return_value="- 只讲相较上次的新变化",
            ),
        ):
            wiki = Path(tmp) / "wiki"
            (wiki / "relations").mkdir(parents=True)
            result = answer_query(
                AskOptions(
                    query="请复盘最新交易日的市场结构和主要风险",
                    exports_dir=tmp,
                    kb_wiki=wiki,
                    supplemental_evidence="### daily-review\n- 上涨 3774 只",
                    use_modules=False,
                    use_wiki_rag=False,
                    compose=True,
                )
            )

        self.assertIn("以下历史记忆只作为先验", captured["prompt"])
        self.assertIn("相较上次", captured["prompt"])
        self.assertIn("用户记忆检索块 [M]", captured["prompt"])
        self.assertIn("回检块 [V]", captured["prompt"])
        self.assertIn("只讲相较上次的新变化", captured["prompt"])
        self.assertEqual({citation.tag for citation in result.citations}, {"M", "V"})

    def test_market_review_without_memory_keeps_prior_block_absent(self) -> None:
        captured: dict[str, str] = {}

        def fake_synthesize(messages: list[dict], **_: object):
            captured["prompt"] = str(messages[1]["content"])
            return None, "mocked"

        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "intelligence.services.ask.llm_refine.synthesize_messages",
            side_effect=fake_synthesize,
        ):
            wiki = Path(tmp) / "wiki"
            (wiki / "relations").mkdir(parents=True)
            result = answer_query(
                AskOptions(
                    query="请复盘最新交易日的市场结构和主要风险",
                    exports_dir=tmp,
                    kb_wiki=wiki,
                    supplemental_evidence="### daily-review\n- 上涨 3774 只",
                    use_modules=False,
                    use_wiki_rag=False,
                    compose=True,
                    include_memory_block=False,
                    include_recall_block=False,
                )
            )

        self.assertNotIn("以下历史记忆只作为先验", captured["prompt"])
        self.assertEqual(result.citations, [])

    def test_market_review_compose_excludes_deep_dive_evidence_blocks(self) -> None:
        captured: dict[str, str] = {}

        def fake_synthesize(messages: list[dict], **_: object):
            captured["prompt"] = str(messages[1]["content"])
            return None, "mocked"

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch(
                "intelligence.services.ask.llm_refine.synthesize_messages",
                side_effect=fake_synthesize,
            ),
            mock.patch(
                "intelligence.services.ask._market_review_mainline_context_block_for_llm",
                return_value=(
                    "## 市场复盘主线数据边界\n"
                    "- 当日市场总览截至 2026-07-10；主线题材快照仅截至 2026-06-30。\n"
                    "- 当前交易日主线未知。"
                ),
            ),
        ):
            wiki = Path(tmp) / "wiki"
            (wiki / "relations").mkdir(parents=True)
            result = answer_query(
                AskOptions(
                    query="请复盘最新交易日的市场结构、主线、赚钱效应和主要风险。",
                    exports_dir=tmp,
                    kb_wiki=wiki,
                    use_modules=False,
                    use_wiki_rag=False,
                    compose=True,
                )
            )

        self.assertIsNotNone(result.question_plan)
        assert result.question_plan is not None
        self.assertEqual(result.question_plan.question_type, QUESTION_MARKET_REVIEW)
        self.assertIn("问题类型：market_review", captured["prompt"])
        self.assertNotIn("图谱·公司分层", captured["prompt"])
        self.assertNotIn("客户证据硬度数据块", captured["prompt"])
        self.assertNotIn("二阶导研究队列数据块", captured["prompt"])
        self.assertNotIn("检索遥测", captured["prompt"])
        self.assertNotIn("市场结构状态机", captured["prompt"])
        self.assertNotIn("回答质量约束", captured["prompt"])
        self.assertNotIn("第一性原理门槛", captured["prompt"])
        self.assertNotIn("- 反方审稿：", captured["prompt"])
        self.assertIn("当前交易日主线未知", captured["prompt"])
        self.assertIsNotNone(result.answer_spec)
        rendered = render_conversation_answer(result)
        self.assertIn("**直接定性：**", rendered)
        self.assertIn("**最强证据：**", rendered)
        self.assertIn("**主要风险：**", rendered)
        self.assertIn("**条件边界：**", rendered)
        self.assertIn("**下一步验证：**", rendered)
        self.assertNotIn("检索遥测", rendered)

    def test_ask_compose_injects_canonical_next_trading_day(self) -> None:
        duckdb = __import__("duckdb")
        captured: dict[str, str] = {}

        def fake_synthesize(messages: list[dict], **_: object):
            captured["prompt"] = str(messages[1]["content"])
            return None, "mocked"

        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "intelligence.services.ask.llm_refine.synthesize_messages_with_review",
            side_effect=fake_synthesize,
        ):
            base = Path(tmp)
            wiki = base / "wiki"
            (wiki / "relations").mkdir(parents=True)
            market_db = base / "market.duckdb"
            con = duckdb.connect(str(market_db))
            con.execute("create table fact_stock_daily(trade_date date)")
            con.execute("insert into fact_stock_daily values ('2026-07-10')")
            con.execute("create table fact_market_daily(trade_date date)")
            con.execute("insert into fact_market_daily values ('2026-07-10')")
            con.close()

            answer_query(
                AskOptions(
                    query="请预测下一交易日的市场风险",
                    exports_dir=base,
                    kb_wiki=wiki,
                    market_db_path=market_db,
                    use_modules=False,
                    use_wiki_rag=False,
                    compose=True,
                )
            )

        self.assertIn("下一交易日：2026-07-13", captured["prompt"])
        self.assertNotIn("下一交易日：2026-07-11", captured["prompt"])

    def test_market_forecast_compose_injects_forecast_preflight_gate(self) -> None:
        captured: dict[str, str] = {}

        def fake_synthesize(messages: list[dict], **_: object):
            captured["prompt"] = str(messages[1]["content"])
            return None, "mocked"

        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "intelligence.services.ask.llm_refine.synthesize_messages_with_review",
            side_effect=fake_synthesize,
        ):
            base = Path(tmp)
            wiki = base / "wiki"
            exports = base / "exports"
            (wiki / "relations").mkdir(parents=True)
            exports.mkdir()
            (exports / "2026-07-01-daily-agent.json").write_text(
                json.dumps(
                    {
                        "research_queue": {
                            "today_do_ima": [
                                {
                                    "目标": "IDC",
                                    "动作": "今日该做 IMA",
                                    "理由": "PR188 真增量但缺 L1/L2。",
                                    "优先级": 194.0,
                                    "生命周期阶段": "旧逻辑唤醒",
                                    "缺失证据层": ["L2 基线"],
                                    "强势股": ["润泽科技"],
                                }
                            ],
                            "today_find_official_evidence": [],
                            "today_wait_market_validation": [],
                            "today_downgrade_or_watch": [],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = answer_query(
                AskOptions(
                    query="站在7.1视角，7.2行情怎么看",
                    date="2026-07-01",
                    exports_dir=exports,
                    kb_wiki=wiki,
                    use_modules=False,
                    use_wiki_rag=False,
                    compose=True,
                )
            )

        self.assertIsNotNone(result.forecast_preflight)
        assert result.forecast_preflight is not None
        self.assertEqual(result.forecast_preflight["status"], "needs_deepdive")
        self.assertIn("forecast_preflight", captured["prompt"])
        self.assertIn("需要先补的 DeepDive", captured["prompt"])
        self.assertIn("IDC", captured["prompt"])
        self.assertIn("正式复盘", "\n".join(result.warnings))

    def test_ask_compose_injects_mainline_context_block_into_llm_prompt(self) -> None:
        captured: dict[str, str] = {}

        def fake_synthesize(messages: list[dict], **_: object):
            captured["prompt"] = str(messages[1]["content"])
            return None, "mocked"

        duckdb = __import__("duckdb")
        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "intelligence.services.ask.llm_refine.synthesize_messages_with_review",
            side_effect=fake_synthesize,
        ):
            base = Path(tmp)
            wiki = base / "wiki"
            (wiki / "relations").mkdir(parents=True)
            db_path = base / "market.duckdb"
            con = duckdb.connect(str(db_path))
            con.execute(
                """
                create table fact_mainline_sector_daily(
                  trade_date date, theme_code varchar, theme_name varchar,
                  sector_ts_code varchar, sector_name varchar, sort_no integer,
                  today_pct double, limit_up_count integer, max_limit_height integer,
                  amount double, amount_estimated double, amount_relative_ratio double,
                  net_inflow_1d double, strength double, strength_chg double,
                  cycle_level varchar, cycle_status varchar,
                  startup_date_small date, startup_date_big date,
                  startup_date_super date, startup_date_extend date,
                  high_status varchar, high_status_label varchar,
                  near_breakout_status varchar, near_breakout_label varchar,
                  near_breakout_gap_pct double, note varchar, source varchar, updated_at timestamp
                )
                """
            )
            con.execute(
                """
                create table fact_sector_daily(
                  trade_date date, sector_ts_code varchar, sector_name varchar,
                  sw_l1 varchar, pct_chg double, amount double, diff_ratio double
                )
                """
            )
            con.executemany(
                "insert into fact_mainline_sector_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    ("2026-06-30", "TH1", "AI算力", "886033.TI", "共封装光学(CPO)", 1, 5.17, 15, 2, 70055142.0, 70055142.0, -0.02, 52086112744.0, 4175.6, 4048.9, "小级别", "顺势", "2026-04-01", None, None, None, None, None, "history", "历史新高", 1.44, "", "test", "2026-06-30 15:30:00"),
                ],
            )
            con.executemany(
                "insert into fact_sector_daily values (?, ?, ?, ?, ?, ?, ?)",
                [("2026-06-30", "886033.TI", "共封装光学(CPO)", "电子", 5.18, 7005.51, -5.68)],
            )
            con.close()

            result = answer_query(
                AskOptions(
                    query="AI算力怎么看",
                    exports_dir=tmp,
                    kb_wiki=wiki,
                    market_db_path=db_path,
                    use_modules=False,
                    use_wiki_rag=False,
                    compose=True,
                )
            )

        self.assertIn("主线题材结构数据块 [D4]", captured["prompt"])
        self.assertIn("共封装光学(CPO)", captured["prompt"])
        self.assertIn("缩量强修复/存量抱团", captured["prompt"])
        self.assertTrue(any(c.tag == "D4" for c in result.citations))


if __name__ == "__main__":
    unittest.main()
