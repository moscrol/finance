from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest import mock

from intelligence.services import llm_refine
from intelligence.services.answer_model import resolve_theme_research_spec
from intelligence.services.ask import (
    AskResult,
    AskOptions,
    _company_exposure_tier,
    _customer_evidence_hardness_block_for_llm,
    _daily_market_overview_block_for_llm,
    _evidence_chain_with_llm_wiki,
    _mainline_context_block_for_llm,
    _market_review_mainline_context_block_for_llm,
    _market_value_block_for_llm,
    _resolve_market_data_context,
    _second_derivative_queue_block_for_llm,
    _theme_research_framing,
    answer_query,
    render_answer,
    render_conversation_answer,
)
from intelligence.services.llm_refine import (
    LLMProvider,
    SynthesisResult,
    build_decision_brief_messages,
    build_grounded_composer_messages,
    build_grounding_judge_messages,
    build_synthesis_messages,
    synthesize,
)


def _provider() -> LLMProvider:
    return LLMProvider(name="deepseek", api_key="sk-test", base_url="https://api.deepseek.com/v1", model="deepseek-chat")


class SynthesizeTests(unittest.TestCase):
    def test_shadow_prompts_separate_planning_composing_and_judging(self) -> None:
        registry = '{"claim_id":"c1","text":"事实"}'

        brief = build_decision_brief_messages("问题", registry)
        composer = build_grounded_composer_messages(
            "问题",
            '{"supports":["c1"]}',
            registry,
        )
        judge = build_grounding_judge_messages(
            "问题",
            "- 自然语言 <!-- claim_ids=c1; evidence_atom_ids=a1; "
            "claim_type=fact -->",
            registry,
        )

        self.assertIn("论证计划", brief[0]["content"])
        self.assertIn("最终措辞", composer[0]["content"])
        self.assertIn("事实蕴含", judge[0]["content"])

    def test_llm_prompt_uses_long_wiki_evidence_without_changing_display_chain(self) -> None:
        display = "A公司：展示短摘录 [W1]"
        llm = "A公司：命中块 a::1: 较完整证据；相邻块 a::0: 条件与风险 [W1]"
        evidence_chain = ["§§图谱·语义召回(wiki 向量)", display]

        prompt_chain = _evidence_chain_with_llm_wiki(evidence_chain, [(display, llm)])

        self.assertEqual(evidence_chain[1], display)
        self.assertEqual(prompt_chain[1], llm)

    def test_degrades_without_provider(self) -> None:
        with mock.patch.object(llm_refine, "detect_provider", return_value=None):
            out, reason = synthesize("液冷", "液冷服务器", "## 证据链\n- foo [S1]")
        self.assertIsNone(out)
        self.assertIn("未配置 LLM key", reason)

    def test_composes_with_mocked_llm(self) -> None:
        with mock.patch.object(llm_refine, "detect_provider", return_value=_provider()), mock.patch.object(
            llm_refine, "_post_chat_synthesis", return_value=("液冷盘面强势[S1]。（非投资建议）", "stop")
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

    def test_synthesis_prompt_includes_experience_guidance(self) -> None:
        msgs = llm_refine.build_synthesis_messages(
            "科技细分里哪个方向还有上涨空间",
            "光刻胶",
            "## 证据链\n- 双红 [S1]",
            experience_guidance="- 回答板块空间问题时必须说明阶段、证据层和反方。",
        )

        self.assertIn("历史经验卡片", msgs[1]["content"])
        self.assertIn("回答板块空间问题", msgs[1]["content"])

    def test_synthesis_prompt_requires_bounded_claim_selection(self) -> None:
        msgs = llm_refine.build_synthesis_messages(
            "中际旭创怎么看",
            "光模块",
            "## AnswerSpec registry\n- 53 条候选 claim",
        )

        self.assertIn("只选择 6-10 条", msgs[0]["content"])
        self.assertIn("正文绝对不得超过 12 行", msgs[0]["content"])
        self.assertIn("禁止遍历 registry", msgs[0]["content"])
        self.assertIn("正文硬上限 12 个带 marker 的行", msgs[1]["content"])

    def test_synthesis_prompt_includes_exemplar_guidance(self) -> None:
        msgs = llm_refine.build_synthesis_messages(
            "深挖汇成股份",
            "先进封装",
            "## 证据链\n- 扩产公告 [S1]",
            exemplar_guidance="### 样板：deep-dive-demo\n先说市场在交易什么……",
        )

        self.assertIn("高分样板", msgs[1]["content"])
        self.assertIn("严禁照抄", msgs[1]["content"])
        self.assertIn("deep-dive-demo", msgs[1]["content"])

    def test_synthesis_prompt_hides_internal_diagnostics_from_users(self) -> None:
        msgs = llm_refine.build_synthesis_messages(
            "请复盘最新交易日",
            "全市场",
            "## 主线题材结构数据块 [D4]\n- cycle_status=分歧",
            citation_legend="[D4] 本地 DuckDB 主线结构",
        )

        system = msgs[0]["content"]
        user = msgs[1]["content"]

        self.assertIn("不得在正文显示任何内部引用编号", system)
        self.assertIn("严禁输出原始 JSON", system)
        self.assertIn("L1/L2/L3/L4 必须分别转译", system)
        self.assertIn("graph_only、replay、Daily Review", system)
        self.assertIn("最终回答不得显示编号", user)

    def test_exemplar_guidance_loader_routes_by_question_type(self) -> None:
        from intelligence.services.ask import _exemplar_guidance_for
        from intelligence.services.answer_orchestrator import (
            QUESTION_STOCK_DEEP_DIVE,
            QUESTION_THEME_ANALYSIS,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "deep-dive-a.md").write_text("样板正文A", encoding="utf-8")
            (root / "forecast-b.md").write_text("样板正文B", encoding="utf-8")

            deep = _exemplar_guidance_for(QUESTION_STOCK_DEEP_DIVE, exemplar_dir=root)
            theme = _exemplar_guidance_for(QUESTION_THEME_ANALYSIS, exemplar_dir=root)

        self.assertIn("样板正文A", deep)
        self.assertNotIn("样板正文B", deep)
        self.assertEqual(theme, "")

    def test_synthesis_system_prompt_requires_daily_agent_reasoning(self) -> None:
        msgs = llm_refine.build_synthesis_messages(
            "深挖汇成股份",
            "先进封装",
            "## 证据链\n- priority=120，强验证 [S1]",
        )

        system = msgs[0]["content"]

        self.assertIn("daily-agent", system)
        self.assertIn("生命周期", system)
        self.assertIn("市场/板块/个股三层资金传导", system)
        self.assertIn("全量盘面数据的正反推导", system)
        self.assertIn("强板块弱个股", system)
        self.assertIn("市场正在奖励谁、抛弃谁、犹豫谁", system)
        self.assertIn("二阶导", system)
        self.assertIn("领先核心、同步确认、后排补涨", system)
        self.assertIn("输出前必须在内部做一次质检和反驳", system)
        self.assertIn("是否模板化", system)
        self.assertIn("是否孤立看个股", system)
        self.assertIn("证据是否够硬", system)
        self.assertIn("更优表达", system)
        self.assertIn("主线题材结构数据", system)
        self.assertIn("主线连续性", system)
        self.assertIn("缩量强修复/存量抱团", system)
        self.assertIn("先在内部写出核心矛盾句", system)
        self.assertIn("所有视角都必须服务这个核心矛盾", system)
        self.assertIn("禁止按公司本体、盘面、二阶导、反证逐项填空", system)
        self.assertIn("每一段都要回答这个事实改变了什么判断", system)
        self.assertIn("不要附加质检过程或审稿过程", system)
        self.assertIn("只能使用证据中“交易日历约束”给出的日期", system)
        self.assertIn("严禁自然日加一天或猜日期", system)

    def test_synthesis_system_prompt_obeys_question_specific_contract(self) -> None:
        msgs = llm_refine.build_synthesis_messages(
            "请复盘最新交易日的市场结构、主线、赚钱效应和主要风险。",
            "全市场",
            "## 问答编排计划\n- 问题类型：market_review",
        )

        system = msgs[0]["content"]

        self.assertIn("先服从证据中的「问答编排计划」", system)
        self.assertIn("结构和篇幅由问题复杂度决定", system)
        self.assertIn("不得为了显得完整而套用深度研究模板", system)

    def test_degrades_on_empty_content(self) -> None:
        with mock.patch.object(llm_refine, "detect_provider", return_value=_provider()), mock.patch.object(
            llm_refine, "_post_chat_synthesis", return_value=("   ", "stop")
        ):
            out, reason = synthesize("液冷", "液冷服务器", "ev")
        self.assertIsNone(out)
        self.assertIn("空内容", reason)

    def test_degrades_on_exception(self) -> None:
        with mock.patch.object(llm_refine, "detect_provider", return_value=_provider()), mock.patch.object(
            llm_refine, "_post_chat_synthesis", side_effect=RuntimeError("boom")
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
        self.assertIn("本轮没有形成可用于结论的可验证来源", out)

    def test_render_preserves_fupanhui_methodology_path(self) -> None:
        r = self._base_result(None)
        r.sections["分歧反证"] = [
            "市场结构推演路径：市场量能：用成交额、20日量能回归或放缩量状态判断有没有新增资金。",
            "市场结构推演路径：板块承接：用双红、边际量和成交额确认题材是否真正获得资金承接。",
        ]

        out = render_answer(r)

        self.assertIn("市场结构推演路径", out)
        self.assertIn("20日量能回归", out)
        self.assertIn("板块承接", out)

    def test_conversation_fallback_hides_internal_diagnostics(self) -> None:
        result = self._base_result(None)
        result.data_notice = (
            "**数据降级：当前未连接本地 DuckDB。** "
            "以下仅使用历史 snapshot/export，不能视为最新交易日复盘。"
        )
        result.warnings = ["命中 D4；发生降权"]

        out = render_conversation_answer(result)

        self.assertIn("不能视为最新交易日复盘", out)
        self.assertIn("运行详情", out)
        self.assertNotIn("命中主题", out)
        self.assertNotIn("模块路由", out)
        self.assertNotIn("D4", out)
        self.assertNotIn("降权", out)

    def test_conversation_fallback_uses_readable_duckdb_summary(self) -> None:
        result = self._base_result(None)
        result.data_notice = "**数据截至 2026-07-10。**"
        result.market_summary = (
            "## 本地 DuckDB 最新市场总览\n"
            "- 市场数据截至：2026-07-10。\n"
            "- 涨跌结构：上涨 3774 家；涨停 92 家；跌停 4 家。"
        )

        out = render_conversation_answer(result)

        self.assertIn("## 市场概览", out)
        self.assertIn("上涨 3774 家", out)
        self.assertNotIn("本地 DuckDB 最新市场总览", out)

    def test_conversation_fallback_includes_verified_next_trading_day(self) -> None:
        result = self._base_result(None)
        result.query = "请明确下一交易日日期"
        result.trade_date = "2026-07-10"
        result.next_trade_date = "2026-07-13"
        result.data_notice = "**数据截至 2026-07-10。**"

        out = render_conversation_answer(result)

        self.assertIn("下一交易日为 2026-07-13", out)
        self.assertNotIn("2026-07-11", out)

    def test_conversation_fallback_fails_closed_without_calendar(self) -> None:
        result = self._base_result(None)
        result.query = "T+1 是哪一天"
        result.next_trade_date = None

        out = render_conversation_answer(result)

        self.assertIn("日期待交易日历确认", out)
        self.assertNotIn("2026-06-12", out)

    def test_conversation_fallback_renders_deterministic_sections(self) -> None:
        result = self._base_result(None)
        result.citations = [
            type("CitationFixture", (), {"tag": "S1", "source": "fixture", "detail": ""})()
        ]
        result.sections = {
            "结论": ["稳定币支付仍需核验公司级证据。"],
            "证据链": ["四方精创：关联层，未达到核心层门槛。"],
            "分歧反证": ["缺少公告或客户验证。"],
            "后续验证点": ["核对公司公告。"],
            "交易含义": ["不把弱关联公司视为核心受益。"],
        }

        out = render_conversation_answer(result)

        self.assertIn("稳定币支付仍需核验公司级证据", out)
        self.assertIn("四方精创", out)
        self.assertIn("缺少公告或客户验证", out)
        self.assertIn("自然语言综合暂时不可用", out)

    def test_index_comparison_marks_unavailable_indices_without_guessing(self) -> None:
        duckdb = __import__("duckdb")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "market.duckdb"
            con = duckdb.connect(str(db_path))
            con.execute(
                """
                create table fact_market_daily(
                  trade_date date,
                  sh_index_close double,
                  sh_index_pct_chg double,
                  sh_index_amount double,
                  sh_index_volume double,
                  sh_index_source varchar
                )
                """
            )
            con.execute(
                """
                insert into fact_market_daily values
                ('2026-07-10', 3996.162, -1.0014, null, 62745006500,
                 'akshare:stock_zh_index_daily:sh000001')
                """
            )
            con.close()

            with mock.patch(
                "intelligence.services.ask_blocks.next_trading_day",
                return_value="2026-07-13",
            ):
                result = answer_query(
                    AskOptions(
                        query=(
                            "比较 2026-07-10 的上证指数、深证成指和创业板指，"
                            "逐项给出涨跌、成交、来源和截止日。"
                        ),
                        exports_dir=root,
                        market_db_path=db_path,
                    )
                )

        rendered = render_conversation_answer(result)
        self.assertIn("上证指数：收盘 3996.162", rendered)
        self.assertIn("当日涨跌 -1.00%", rendered)
        self.assertIn("成交额缺失；可用强弱指标为成交量 627.45 亿", rendered)
        self.assertIn("深证成指：当日涨跌、成交或强弱指标均缺失", rendered)
        self.assertIn("创业板指：当日涨跌、成交或强弱指标均缺失", rendered)
        self.assertIn("下一交易日为 2026-07-13", rendered)
        self.assertNotIn("2026-07-11", rendered)

    def test_company_core_requires_direct_high_confidence_evidence(self) -> None:
        self.assertEqual(
            _company_exposure_tier(
                {
                    "strength": "related",
                    "confidence": "high",
                    "evidence_layer": "L1_L3_candidate",
                }
            ),
            "other",
        )
        self.assertEqual(
            _company_exposure_tier(
                {
                    "strength": "core",
                    "confidence": "high",
                    "evidence_layer": "L3",
                }
            ),
            "core",
        )

    def test_generic_theme_protocol_covers_multiple_domain_packs(
        self,
    ) -> None:
        cases = (
            ("稳定币支付", "stablecoin_payment"),
            ("人形机器人", "robotics"),
            ("AI 算力", "compute_infrastructure"),
            ("低空经济", "low_altitude_economy"),
        )
        for theme, pack_id in cases:
            spec = resolve_theme_research_spec(
                f"深研“{theme}”题材：给出定义、产业链、事实边界和核验动作。"
            )
            framing = _theme_research_framing(spec, None)
            rendered = "\n".join(
                item
                for values in framing.values()
                for item in values
            )
            self.assertEqual(spec.pack_id, pack_id)
            self.assertIn("题材定义", rendered)
            self.assertIn("产业链上游", rendered)
            self.assertIn("产业链中游", rendered)
            self.assertIn("产业链下游", rendered)
            self.assertIn("事实、推测与待验证边界", rendered)
            self.assertIn("核验动作", rendered)


class DailyMarketOverviewTests(unittest.TestCase):
    def test_prefers_duckdb_date_over_older_snapshot(self) -> None:
        with mock.patch(
            "intelligence.services.ask._market_data_asof",
            return_value="2026-07-10",
        ):
            trade_date, source, notice, warnings = _resolve_market_data_context(
                "2026-07-01",
                "/tmp/market.duckdb",
            )

        self.assertEqual(trade_date, "2026-07-10")
        self.assertEqual(source, "duckdb")
        self.assertIn("2026-07-10", notice or "")
        self.assertIn("2026-07-01", warnings[0])

    def test_marks_snapshot_as_fallback_when_duckdb_is_missing(self) -> None:
        with mock.patch(
            "intelligence.services.ask._market_data_asof",
            return_value=None,
        ):
            trade_date, source, notice, warnings = _resolve_market_data_context(
                "2026-07-01",
                "/tmp/missing.duckdb",
            )

        self.assertEqual(trade_date, "2026-07-01")
        self.assertEqual(source, "snapshot_fallback")
        self.assertIn("不能视为最新交易日复盘", notice or "")
        self.assertIn("没有连接本地市场数据", warnings[0])
        self.assertNotIn("DuckDB", warnings[0])
        self.assertNotIn("snapshot/export", warnings[0])

    def test_builds_current_market_block_and_marks_lagging_subtable(self) -> None:
        duckdb = __import__("duckdb")
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "market.duckdb"
            con = duckdb.connect(str(db_path))
            con.execute(
                """
                create table fact_market_daily(
                  trade_date date,
                  market_stage varchar,
                  stage_day integer,
                  total_amount double,
                  amount_vs_yesterday_pct double,
                  volume_ratio double,
                  volume_state varchar,
                  advancers integer,
                  limit_up integer,
                  limit_down integer,
                  sh_index_close double,
                  sh_index_pct_chg double,
                  concentration_state varchar,
                  industry_1 varchar,
                  industry_1_ratio double,
                  strength_avg_pct double,
                  strength_marginal_pct double,
                  strength_status varchar
                )
                """
            )
            con.execute(
                """
                insert into fact_market_daily values (
                  '2026-07-10', '底部横盘阶段', 9, 33883.62, 16.3, 104.35,
                  '主线抱团', 3774, 92, 4, 3996.162, -1.0, '集中',
                  '电子', 35.4, 9.62, -69.37, '沸点'
                )
                """
            )
            con.execute(
                """
                create table fact_mainline_theme_daily(
                  trade_date date,
                  theme_name varchar,
                  sector_count integer,
                  min_sort integer
                )
                """
            )
            con.execute(
                "insert into fact_mainline_theme_daily values ('2026-07-10', '半导体', 3, 1)"
            )
            con.execute(
                "create table fact_mainline_sector_daily(trade_date date)"
            )
            con.execute(
                "insert into fact_mainline_sector_daily values ('2026-06-30')"
            )
            con.close()

            block = _daily_market_overview_block_for_llm(db_path)

        self.assertIn("市场数据截至：2026-07-10", block)
        self.assertIn("上涨 3774 家", block)
        self.assertIn("半导体（3 个核心板块）", block)
        self.assertIn("题材级主线汇总已更新到 2026-07-10", block)
        self.assertIn("核心板块明细仅更新到 2026-06-30", block)
        self.assertIn("当前核心板块、周期状态和标的未知", block)


class MarketValueBlockTests(unittest.TestCase):
    def test_market_value_block_adds_car_drawdown_and_alternative_queue(self) -> None:
        duckdb = __import__("duckdb")
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "market.duckdb"
            con = duckdb.connect(str(db_path))
            con.execute(
                """
                create table fact_stock_daily(
                  trade_date date, stock_ts_code varchar, stock_name varchar,
                  close double, pct_chg double, amount double
                )
                """
            )
            con.execute(
                """
                create table fact_sector_stock_daily(
                  trade_date date, sector_name varchar, sw_l1 varchar, stock_ts_code varchar,
                  stock_name varchar, pct_chg double, amount double, pct_chg_5d double,
                  pct_chg_10d double, high_status_label varchar, limit_times integer
                )
                """
            )
            con.execute(
                """
                create table fact_sector_daily(
                  trade_date date, sector_name varchar, pct_chg double, amount double, diff_ratio double
                )
                """
            )
            con.executemany(
                "insert into fact_stock_daily values (?, ?, ?, ?, ?, ?)",
                [
                    ("2026-06-01", "688008.SH", "澜起科技", 100.0, 0.0, 100.0),
                    ("2026-06-10", "688008.SH", "澜起科技", 150.0, 5.0, 180.0),
                    ("2026-06-26", "688008.SH", "澜起科技", 120.0, -6.0, 200.0),
                ],
            )
            con.executemany(
                "insert into fact_sector_daily values (?, ?, ?, ?, ?)",
                [("2026-06-26", "存储芯片", -0.5, 7500.0, 6.0)],
            )
            con.executemany(
                "insert into fact_sector_stock_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    ("2026-06-26", "存储芯片", "电子", "688008.SH", "澜起科技", -6.0, 200.0, -3.0, 14.0, "", None),
                    ("2026-06-26", "存储芯片", "电子", "688432.SH", "有研硅", 20.0, 20.0, 22.0, 34.0, "历史新高", 1),
                    ("2026-06-26", "存储芯片", "电子", "688596.SH", "正帆科技", 20.0, 23.0, 22.0, 19.0, "历史新高", 1),
                ],
            )
            con.close()

            block = _market_value_block_for_llm("深挖澜起科技", "存储芯片", db_path)

        self.assertIn("市场价值成绩单", block)
        self.assertIn("峰后回撤", block)
        self.assertIn("半衰期代理", block)
        self.assertIn("个股相对强度排名", block)
        self.assertIn("同题材强势替代队列", block)
        self.assertIn("有研硅", block)


class EvidenceDataBlockTests(unittest.TestCase):
    def test_market_review_mainline_block_hides_stale_theme_details(self) -> None:
        duckdb = __import__("duckdb")
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "market.duckdb"
            con = duckdb.connect(str(db_path))
            con.execute("create table fact_market_daily(trade_date date)")
            con.execute("insert into fact_market_daily values ('2026-07-10')")
            con.execute(
                "create table fact_mainline_sector_daily("
                "trade_date date, theme_name varchar, sector_name varchar)"
            )
            con.execute(
                "insert into fact_mainline_sector_daily values "
                "('2026-06-30', 'AI算力', '共封装光学(CPO)')"
            )
            con.close()

            block = _market_review_mainline_context_block_for_llm(
                "请复盘最新交易日的市场结构、主线、赚钱效应和主要风险。",
                None,
                db_path,
            )

        self.assertIn("当日市场总览截至 2026-07-10", block)
        self.assertIn("没有可用的同日主线题材汇总", block)
        self.assertIn("当前交易日的题材级主线未知", block)
        self.assertIn("核心板块明细仅截至 2026-06-30", block)
        self.assertNotIn("AI算力", block)
        self.assertNotIn("共封装光学", block)

    def test_market_review_mainline_block_keeps_current_themes_but_hides_stale_sectors(self) -> None:
        duckdb = __import__("duckdb")
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "market.duckdb"
            con = duckdb.connect(str(db_path))
            con.execute("create table fact_market_daily(trade_date date)")
            con.execute("insert into fact_market_daily values ('2026-07-10')")
            con.execute(
                "create table fact_mainline_theme_daily("
                "trade_date date, theme_name varchar, sector_count integer, min_sort integer)"
            )
            con.execute(
                "insert into fact_mainline_theme_daily values "
                "('2026-07-10', '半导体', 3, 1), "
                "('2026-07-10', 'AI算力', 2, 2)"
            )
            con.execute(
                "create table fact_mainline_sector_daily("
                "trade_date date, theme_name varchar, sector_name varchar)"
            )
            con.execute(
                "insert into fact_mainline_sector_daily values "
                "('2026-06-30', 'AI算力', '共封装光学(CPO)')"
            )
            con.close()

            block = _market_review_mainline_context_block_for_llm(
                "请复盘最新交易日的市场结构、主线、赚钱效应和主要风险。",
                None,
                db_path,
            )

        self.assertIn("题材级主线汇总均截至 2026-07-10", block)
        self.assertIn("当前主线题材为 半导体、AI算力", block)
        self.assertIn("核心板块明细仅截至 2026-06-30", block)
        self.assertIn("当前核心板块、周期状态和标的未知", block)
        self.assertNotIn("共封装光学", block)

    def test_mainline_context_block_adds_theme_sector_cycle_state(self) -> None:
        duckdb = __import__("duckdb")
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "market.duckdb"
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
                    ("2026-06-30", "TH1", "AI算力", "885959.TI", "PCB概念", 2, 3.77, 9, 2, 41966568.0, 41966568.0, -0.01, 24046907555.0, 2314.9, 2162.3, "小级别", "分歧", "2026-04-08", None, None, None, None, None, "history", "历史新高", 2.26, "", "test", "2026-06-30 15:30:00"),
                    ("2026-06-30", "TH2", "半导体", "881121.TI", "半导体", 3, 6.31, 15, 2, 62247258.0, 62247258.0, 0.02, 26892466542.0, 4124.2, 38.2, "小级别", "顺势", "2026-06-09", None, None, None, "history", "历史新高", None, None, None, "", "test", "2026-06-30 15:30:00"),
                ],
            )
            con.executemany(
                "insert into fact_sector_daily values (?, ?, ?, ?, ?, ?, ?)",
                [
                    ("2026-06-30", "886033.TI", "共封装光学(CPO)", "电子", 5.18, 7005.51, -5.68),
                    ("2026-06-30", "885959.TI", "PCB概念", "电子", 3.78, 4196.66, -8.45),
                    ("2026-06-30", "881121.TI", "半导体", "电子", 6.32, 6224.73, 12.0),
                ],
            )
            con.close()

            block = _mainline_context_block_for_llm("AI算力怎么看", "AI算力", db_path)

        self.assertIn("主线题材结构数据块 [D4]", block)
        self.assertIn("AI算力", block)
        self.assertIn("共封装光学(CPO)", block)
        self.assertIn("PCB概念", block)
        self.assertIn("顺势", block)
        self.assertIn("分歧", block)
        self.assertIn("缩量强修复/存量抱团", block)
        self.assertIn("历史新高", block)

    def test_customer_hardness_block_separates_hard_candidate_and_rebuttal(self) -> None:
        block = _customer_evidence_hardness_block_for_llm(
            [
                "顺络电子：公司互动平台确认 TLVR 电感已在数据中心市场批量销售 [R1]",
                "顺络电子：卖方研报预计 A 客户下半年导入钽电容，收入有望放量 [R2]",
                "顺络电子：市场预期 AI 电感空间较大，但缺少客户验证数字 [W1]",
            ],
            [
                "反方审稿：公司口径较保守，钽电容尚未进入财务，客户证据待验证 [Q1]",
            ],
        )

        self.assertIn("客户证据硬度数据块", block)
        self.assertIn("硬证据", block)
        self.assertIn("互动平台确认 TLVR", block)
        self.assertIn("候选证据", block)
        self.assertIn("A 客户", block)
        self.assertIn("弱证据/研报推断", block)
        self.assertIn("反证/缺口", block)
        self.assertIn("尚未进入财务", block)

    def test_second_derivative_queue_block_adds_p0_p1_p2(self) -> None:
        duckdb = __import__("duckdb")
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "market.duckdb"
            con = duckdb.connect(str(db_path))
            con.execute(
                """
                create table fact_stock_daily(
                  trade_date date, stock_ts_code varchar, stock_name varchar,
                  close double, pct_chg double, amount double
                )
                """
            )
            con.execute(
                """
                create table fact_sector_stock_daily(
                  trade_date date, sector_name varchar, sw_l1 varchar, stock_ts_code varchar,
                  stock_name varchar, pct_chg double, amount double, pct_chg_5d double,
                  pct_chg_10d double, high_status_label varchar, limit_times integer
                )
                """
            )
            con.execute(
                """
                create table fact_sector_daily(
                  trade_date date, sector_name varchar, pct_chg double, amount double, diff_ratio double
                )
                """
            )
            con.executemany(
                "insert into fact_stock_daily values (?, ?, ?, ?, ?, ?)",
                [
                    ("2026-06-26", "002138.SZ", "顺络电子", 68.82, -3.33, 27.48),
                ],
            )
            con.executemany(
                "insert into fact_sector_daily values (?, ?, ?, ?, ?)",
                [("2026-06-26", "元件", -2.65, 1870.86, -5.65)],
            )
            con.executemany(
                "insert into fact_sector_stock_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    ("2026-06-26", "元件", "电子", "002138.SZ", "顺络电子", -3.33, 27.48, 8.0, 30.0, "", None),
                    ("2026-06-26", "元件", "电子", "000823.SZ", "超声电子", 10.01, 18.0, 12.0, 20.0, "历史新高", 1),
                    ("2026-06-26", "元件", "电子", "001389.SZ", "广合科技", 10.0, 22.0, 15.0, 25.0, "60日新高", 1),
                ],
            )
            con.close()

            block = _second_derivative_queue_block_for_llm(
                "深挖一下顺络电子",
                "元件",
                db_path,
                "顺络电子 TLVR、钽电容、银浆、磁性材料、客户验证和量产是核心瓶颈。",
            )

        self.assertIn("二阶导研究队列数据块", block)
        self.assertIn("P0 盘面已选择", block)
        self.assertIn("超声电子", block)
        self.assertIn("P1 目标股再升级", block)
        self.assertIn("P2 产业瓶颈补盲", block)
        self.assertIn("TLVR", block)
        self.assertIn("钽电容", block)


if __name__ == "__main__":
    unittest.main()


class StyleLooseningTests(unittest.TestCase):
    def test_exemplar_guidance_samples_one_of_many(self) -> None:
        import random as random_mod

        from intelligence.services.ask_synthesis import _exemplar_guidance_for
        from intelligence.services.answer_orchestrator import QUESTION_STOCK_DEEP_DIVE

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "deep-dive-a.md").write_text("样板A", encoding="utf-8")
            (root / "deep-dive-b.md").write_text("样板B", encoding="utf-8")
            guidance = _exemplar_guidance_for(
                QUESTION_STOCK_DEEP_DIVE,
                exemplar_dir=root,
                rng=random_mod.Random(0),
            )
        # 多篇范文只随机选一，避免固定拼接同一套结构
        self.assertEqual(guidance.count("### 样板："), 1)
        self.assertTrue("样板A" in guidance or "样板B" in guidance)
        self.assertFalse("样板A" in guidance and "样板B" in guidance)

    def test_subjective_temperature_default_and_clamp(self) -> None:
        from unittest import mock

        from intelligence.services.ask_synthesis import _subjective_temperature

        with mock.patch.dict("os.environ", {}, clear=False):
            import os as os_mod

            os_mod.environ.pop("ASK_SUBJECTIVE_TEMPERATURE", None)
            self.assertEqual(_subjective_temperature(), 0.6)
        with mock.patch.dict(
            "os.environ", {"ASK_SUBJECTIVE_TEMPERATURE": "0.5"}
        ):
            self.assertEqual(_subjective_temperature(), 0.5)
        with mock.patch.dict(
            "os.environ", {"ASK_SUBJECTIVE_TEMPERATURE": "9"}
        ):
            self.assertEqual(_subjective_temperature(), 1.0)
        with mock.patch.dict(
            "os.environ", {"ASK_SUBJECTIVE_TEMPERATURE": "bogus"}
        ):
            self.assertEqual(_subjective_temperature(), 0.6)

    def test_section_title_and_body_helpers(self) -> None:
        from intelligence.services.ask_synthesis import (
            _section_bodies,
            _section_titles,
        )

        text = "# 结论\n正文一\n\n## 证据链\n正文二\n# 空节\n"
        self.assertEqual(_section_titles(text), ["结论", "证据链", "空节"])
        bodies = _section_bodies(text)
        self.assertEqual(bodies["结论"], "正文一")
        self.assertEqual(bodies["证据链"], "正文二")
        self.assertEqual(bodies["空节"], "")
