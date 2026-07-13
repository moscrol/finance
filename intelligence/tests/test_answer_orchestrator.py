from __future__ import annotations

import json
import unittest
import tempfile
from pathlib import Path
from unittest import mock

from intelligence.services.answer_orchestrator import (
    DEPTH_DEEP,
    DEPTH_STANDARD,
    QUESTION_GENERAL,
    QUESTION_FINANCIAL_ANALYSIS,
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
from intelligence.services.kb_rag import (
    RetrievalTelemetry,
    WikiHit,
    WikiRagResult,
)


class AnswerOrchestratorTests(unittest.TestCase):
    def test_stale_theme_export_cannot_become_current_candidate_fact(self) -> None:
        duckdb = __import__("duckdb")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wiki = root / "wiki"
            exports = root / "exports"
            (wiki / "relations").mkdir(parents=True)
            exports.mkdir()
            (exports / "2026-07-01-theme-candidates.json").write_text(
                json.dumps(
                    {
                        "trade_date": "2026-07-01",
                        "candidates": [
                            {
                                "canonical_concept": "液冷",
                                "candidate_tier": "A",
                                "priority_score": 90,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            db_path = root / "market.duckdb"
            connection = duckdb.connect(str(db_path))
            connection.execute("create table fact_market_daily(trade_date date)")
            connection.execute(
                "insert into fact_market_daily values ('2026-07-13')"
            )
            connection.close()

            result = answer_query(
                AskOptions(
                    query="液冷现在是不是主线",
                    exports_dir=exports,
                    kb_wiki=wiki,
                    market_db_path=db_path,
                    compose=False,
                    use_modules=False,
                    use_wiki_rag=False,
                )
            )

        self.assertEqual(result.trade_date, "2026-07-13")
        self.assertEqual(result.snapshot_date, "2026-07-01")
        self.assertEqual(result.snapshot_freshness, "stale")
        self.assertFalse(result.found_market)
        self.assertIsNone(result.matched_theme)
        self.assertIsNone(result.candidate_tier)
        self.assertIsNone(result.priority_score)
        self.assertTrue(
            any("stale_derivative" in warning for warning in result.warnings)
        )

    def test_explicit_historical_date_can_use_its_matching_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wiki = root / "wiki"
            exports = root / "exports"
            (wiki / "relations").mkdir(parents=True)
            exports.mkdir()
            (exports / "2026-07-01-theme-candidates.json").write_text(
                json.dumps(
                    {
                        "trade_date": "2026-07-01",
                        "candidates": [
                            {
                                "canonical_concept": "液冷",
                                "candidate_tier": "A",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = answer_query(
                AskOptions(
                    query="液冷当时是不是主线",
                    date="2026-07-01",
                    exports_dir=exports,
                    kb_wiki=wiki,
                    compose=False,
                    use_modules=False,
                    use_wiki_rag=False,
                )
            )

        self.assertTrue(result.found_market)
        self.assertEqual(result.snapshot_freshness, "fresh")
        self.assertEqual(result.candidate_tier, "A")

    def test_empty_query_and_entity_anchor_are_preserved_in_query_envelope(
        self,
    ) -> None:
        empty = plan_answer_question("")
        anchored = plan_answer_question(
            "英维克怎么看",
            anchor=EntityAnchor(entity="英维克", ticker="002837.SZ"),
        )

        self.assertEqual(empty.query_envelope.subject_kind, "unknown")
        self.assertIsNone(empty.query_envelope.subject)
        self.assertEqual(anchored.query_envelope.subject_kind, "company")
        self.assertEqual(anchored.query_envelope.subject, "英维克")
        self.assertEqual(anchored.question_type, QUESTION_STOCK_DEEP_DIVE)

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

    def test_financial_analysis_has_its_own_plan_and_can_be_forced(self) -> None:
        classified = plan_answer_question("分析一下贵州茅台财报")
        forced = plan_answer_question(
            "贵州茅台怎么看",
            question_type_override=QUESTION_FINANCIAL_ANALYSIS,
        )

        for plan in (classified, forced):
            self.assertEqual(plan.question_type, QUESTION_FINANCIAL_ANALYSIS)
            self.assertEqual(plan.depth, DEPTH_DEEP)
            self.assertIn("财务验鲜", "\n".join(plan.required_lenses))
            self.assertIn("逐季财报", "\n".join(plan.retrieval_plan))
            self.assertIn("业绩兑现结论", "\n".join(plan.output_contract))
            self.assertIn("累计口径与单季口径不能混用", "\n".join(plan.missing_data_policy))
            assert plan.base_finance_mode is not None
            self.assertTrue(plan.base_finance_mode.require_financials)

        with self.assertRaisesRegex(ValueError, "unknown question type"):
            plan_answer_question("贵州茅台", question_type_override="unknown")

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
        self.assertEqual(result.question_plan.query_envelope.subject_kind, "company")
        self.assertEqual(result.question_plan.query_envelope.subject, "贵州茅台")

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

        self.assertEqual(plan.query_envelope.subject_kind, "theme")
        self.assertEqual(plan.query_envelope.subject, "液冷")
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

    def test_ambiguous_output_word_does_not_route_to_answer_review(self) -> None:
        plan = plan_answer_question("输出未来三天要验证的风险点")

        self.assertEqual(plan.question_type, QUESTION_GENERAL)
        self.assertLess(plan.confidence, 0.6)

    def test_bare_how_do_you_view_it_uses_general_base_finance_fallback(self) -> None:
        plan = plan_answer_question("怎么看")

        self.assertEqual(plan.question_type, QUESTION_GENERAL)
        self.assertLess(plan.confidence, 0.6)

    def test_short_query_does_not_default_to_theme_template(self) -> None:
        plan = plan_answer_question("人工智能")

        self.assertEqual(plan.question_type, QUESTION_GENERAL)
        self.assertLess(plan.confidence, 0.6)

    def test_generic_theme_lifecycle_question_stays_a_subjectless_market_pattern(
        self,
    ) -> None:
        plan = plan_answer_question(
            "如果一个A股题材连续上涨，但板块成交占比开始下降，我应该怎么判断"
            "它是健康分歧还是行情高潮？"
        )

        self.assertEqual(plan.query_envelope.subject_kind, "market_pattern")
        self.assertIsNone(plan.query_envelope.subject)
        self.assertEqual(plan.question_type, QUESTION_GENERAL)
        self.assertEqual(plan.confidence, plan.query_envelope.confidence)
        self.assertIsNone(plan.research_spec)
        self.assertEqual(
            plan.to_dict()["query_envelope"],
            plan.query_envelope.to_dict(),
        )

    def test_real_market_pattern_query_never_becomes_a_theme_or_claim_subject(
        self,
    ) -> None:
        query = (
            "如果一个A股题材连续上涨，但板块成交占比开始下降，我应该怎么判断"
            "它是健康分歧还是行情高潮？请给出直接判断、证据、反证和下一步验证。"
        )
        plan = plan_answer_question(query)

        self.assertEqual(plan.query_envelope.subject_kind, "market_pattern")
        self.assertIsNone(plan.query_envelope.subject)
        self.assertFalse(
            any("未高置信识别问题类型" in warning for warning in plan.warnings)
        )

        with tempfile.TemporaryDirectory() as tmp:
            result = answer_query(
                AskOptions(
                    query=query,
                    exports_dir=tmp,
                    kb_wiki=Path(tmp),
                    use_modules=False,
                    use_wiki_rag=False,
                    compose=False,
                    include_memory_block=False,
                    include_recall_block=False,
                )
            )

        self.assertIsNotNone(result.answer_spec)
        assert result.answer_spec is not None
        sections_text = json.dumps(result.sections, ensure_ascii=False)
        structured_text = json.dumps(result.answer_spec.to_dict(), ensure_ascii=False)
        module_text = json.dumps(result.detail_reports, ensure_ascii=False)
        self.assertNotIn(f"主题「{query}」", sections_text)
        self.assertNotIn(query, structured_text)
        self.assertNotIn(query, module_text)
        self.assertIn("问题「通用市场结构问题」", sections_text)
        self.assertEqual(
            result.answer_spec.research_spec.theme,
            "通用市场结构问题",
        )
        rendered = render_conversation_answer(result)
        self.assertIn("**直接定性：**", rendered)
        self.assertIn("**最强证据：**", rendered)
        self.assertIn("**主要风险：**", rendered)
        self.assertIn("**下一步验证：**", rendered)

    def test_safe_subject_fallback_preserves_explicit_quoted_and_company_targets(
        self,
    ) -> None:
        cases = (
            ("研究空芯光纤题材", None, "空芯光纤"),
            ("分析“机器人”板块", None, "机器人"),
            (
                "英维克怎么看",
                EntityAnchor(entity="英维克", ticker="002837.SZ"),
                "英维克",
            ),
        )

        for query, anchor, expected_subject in cases:
            with (
                self.subTest(query=query),
                tempfile.TemporaryDirectory() as tmp,
                mock.patch(
                    "intelligence.services.ask.entity_anchor.resolve_entity_anchor",
                    return_value=anchor,
                ),
            ):
                result = answer_query(
                    AskOptions(
                        query=query,
                        exports_dir=tmp,
                        kb_wiki=Path(tmp),
                        use_modules=False,
                        use_wiki_rag=False,
                        compose=False,
                        include_memory_block=False,
                        include_recall_block=False,
                    )
                )

            self.assertIsNotNone(result.answer_spec)
            assert result.answer_spec is not None
            self.assertEqual(
                result.answer_spec.research_spec.theme,
                expected_subject,
            )
            claims = (
                *result.answer_spec.summary,
                *result.answer_spec.verified_facts,
                *result.answer_spec.counter_evidence,
                *result.answer_spec.gaps,
                *result.answer_spec.triggers,
            )
            self.assertTrue(all(claim.theme == expected_subject for claim in claims))

    def test_company_anchor_stays_the_answer_subject_with_theme_aliases(self) -> None:
        anchor = EntityAnchor(entity="英维克", ticker="002837.SZ")
        for query in (
            "深挖英维克，它在液冷产业链的位置",
            "深挖英维克，它和“机器人”题材是什么关系",
        ):
            with self.subTest(query=query):
                plan = plan_answer_question(query, anchor=anchor)
                self.assertEqual(plan.query_envelope.subject_kind, "company")
                self.assertIsNotNone(plan.research_spec)
                assert plan.research_spec is not None
                self.assertEqual(plan.research_spec.theme, "英维克")

                with tempfile.TemporaryDirectory() as tmp, mock.patch(
                    "intelligence.services.ask.entity_anchor.resolve_entity_anchor",
                    return_value=anchor,
                ):
                    result = answer_query(
                        AskOptions(
                            query=query,
                            exports_dir=tmp,
                            kb_wiki=Path(tmp),
                            use_modules=False,
                            use_wiki_rag=False,
                            compose=False,
                            include_memory_block=False,
                            include_recall_block=False,
                        )
                    )

                self.assertIsNotNone(result.answer_spec)
                assert result.answer_spec is not None
                self.assertEqual(result.answer_spec.research_spec.theme, "英维克")
                self.assertEqual(
                    result.answer_spec.presentation_title,
                    "英维克：个股研究结论",
                )
                self.assertIn("公司「英维克」", "\n".join(result.sections["结论"]))
                self.assertIn(
                    "# 英维克：个股研究结论",
                    render_conversation_answer(result),
                )
                claims = (
                    *result.answer_spec.summary,
                    *result.answer_spec.verified_facts,
                    *result.answer_spec.counter_evidence,
                    *result.answer_spec.gaps,
                    *result.answer_spec.triggers,
                )
                self.assertTrue(all(claim.theme == "英维克" for claim in claims))

    def test_market_pattern_answer_uses_market_structure_not_theme_template(
        self,
    ) -> None:
        query = (
            "如果一个A股题材连续上涨，但板块成交占比开始下降，我应该怎么判断"
            "它是健康分歧还是行情高潮？请给出直接判断、证据、反证和下一步验证。"
        )
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch("intelligence.services.ask.kb_rag.retrieve") as retrieve,
            mock.patch("intelligence.services.ask.run_module") as run_module,
        ):
            result = answer_query(
                AskOptions(
                    query=query,
                    exports_dir=tmp,
                    kb_wiki=Path(tmp),
                    use_modules=True,
                    use_wiki_rag=True,
                    compose=False,
                    include_memory_block=False,
                    include_recall_block=False,
                )
            )

        retrieve.assert_not_called()
        run_module.assert_not_called()
        rendered = render_conversation_answer(result)
        self.assertIsNotNone(result.answer_spec)
        assert result.answer_spec is not None
        all_output = (
            rendered
            + json.dumps(result.sections, ensure_ascii=False)
            + json.dumps(result.answer_spec.to_dict(), ensure_ascii=False)
        )
        for required in (
            "单一的板块成交占比下降不足以判断",
            "广度",
            "龙头承接",
            "量价效率",
            "次日修复",
            "分母效应",
            "下一交易日",
        ):
            self.assertIn(required, all_output)
        for forbidden in (
            "题材怎么理解",
            "产业链",
            "公司映射",
            "公司证据",
            "公告",
            "年报",
            "官网",
            "concept-ingest",
            "disclosure-archive",
        ):
            self.assertNotIn(forbidden, all_output)
        self.assertIn("**直接定性：**", rendered)
        self.assertIn("**最强证据：**", rendered)
        self.assertIn("**主要风险：**", rendered)
        self.assertIn("**条件边界：**", rendered)
        self.assertIn("**下一步验证：**", rendered)

    def test_index_breadth_divergence_gets_a_structural_market_answer(self) -> None:
        query = "指数涨、涨停数降、成交额放大，应该怎么理解？"
        plan = plan_answer_question(query)

        self.assertEqual(plan.query_envelope.subject_kind, "market_pattern")
        self.assertEqual(
            plan.query_envelope.decision_goal,
            "解释指数上涨与赚钱效应收缩",
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = answer_query(
                AskOptions(
                    query=query,
                    exports_dir=tmp,
                    kb_wiki=Path(tmp),
                    use_modules=False,
                    use_wiki_rag=False,
                    compose=False,
                )
            )

        rendered = render_conversation_answer(result)
        for required in (
            "权重",
            "结构性上涨",
            "赚钱效应收缩",
            "成交额",
            "下一交易日",
        ):
            self.assertIn(required, rendered)

    def test_index_breadth_query_with_divergence_word_uses_specific_goal(
        self,
    ) -> None:
        query = "指数上涨但涨停家数减少，是否背离？"
        plan = plan_answer_question(query)

        self.assertEqual(plan.query_envelope.subject_kind, "market_pattern")
        self.assertEqual(
            plan.query_envelope.decision_goal,
            "解释指数上涨与赚钱效应收缩",
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = answer_query(
                AskOptions(
                    query=query,
                    exports_dir=tmp,
                    kb_wiki=Path(tmp),
                    use_modules=False,
                    use_wiki_rag=False,
                    compose=False,
                )
            )

        rendered = render_conversation_answer(result)
        for required in (
            "**直接定性：**",
            "**最强证据：**",
            "**主要风险：**",
            "**条件边界：**",
            "**下一步验证：**",
            "权重",
            "结构性上涨",
            "赚钱效应收缩",
        ):
            self.assertIn(required, rendered)
        self.assertNotIn("没有可安全识别的公司、板块或市场模式", rendered)

    def test_default_market_pattern_goal_has_safe_market_structure_guidance(
        self,
    ) -> None:
        query = "指数上涨且成交额放大，应该怎么判断？"
        plan = plan_answer_question(query)

        self.assertEqual(plan.query_envelope.subject_kind, "market_pattern")
        self.assertEqual(plan.query_envelope.decision_goal, "形成条件化判断")
        with tempfile.TemporaryDirectory() as tmp:
            result = answer_query(
                AskOptions(
                    query=query,
                    exports_dir=tmp,
                    kb_wiki=Path(tmp),
                    use_modules=False,
                    use_wiki_rag=False,
                    compose=False,
                )
            )

        rendered = render_conversation_answer(result)
        self.assertIsNotNone(result.answer_spec)
        assert result.answer_spec is not None
        all_output = rendered + json.dumps(
            result.answer_spec.to_dict(),
            ensure_ascii=False,
        )
        for required in (
            "**直接定性：**",
            "**最强证据：**",
            "**主要风险：**",
            "**条件边界：**",
            "**下一步验证：**",
            "不足以确认市场结构健康",
            "权重贡献",
            "上涨广度",
            "成交额集中度",
            "下一交易日",
        ):
            self.assertIn(required, all_output)
        self.assertNotIn("没有可安全识别的公司、板块或市场模式", all_output)
        for forbidden in (
            "题材怎么理解",
            "产业链",
            "公司映射",
            "公告",
            "年报",
            "官网",
            "concept-ingest",
        ):
            self.assertNotIn(forbidden, all_output)

    def test_generic_market_divergence_goal_never_uses_unknown_fallback(
        self,
    ) -> None:
        query = "指数上涨与板块成交占比出现背离，怎么看？"
        plan = plan_answer_question(query)

        self.assertEqual(plan.query_envelope.subject_kind, "market_pattern")
        self.assertEqual(plan.query_envelope.decision_goal, "解释市场背离")
        with tempfile.TemporaryDirectory() as tmp:
            result = answer_query(
                AskOptions(
                    query=query,
                    exports_dir=tmp,
                    kb_wiki=Path(tmp),
                    use_modules=False,
                    use_wiki_rag=False,
                    compose=False,
                )
            )

        rendered = render_conversation_answer(result)
        for required in (
            "市场背离本身不是涨跌方向结论",
            "关键证据",
            "统计口径",
            "条件边界",
            "下一交易日",
        ):
            self.assertIn(required, rendered)
        self.assertNotIn("没有可安全识别的公司、板块或市场模式", rendered)

    def test_unknown_general_answer_does_not_fall_into_theme_research_template(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = answer_query(
                AskOptions(
                    query="输出未来三天要验证的风险点",
                    exports_dir=tmp,
                    kb_wiki=Path(tmp),
                    use_modules=False,
                    use_wiki_rag=False,
                    compose=False,
                    clarify=False,
                )
            )

        rendered = render_conversation_answer(result)
        self.assertIn("# 金融问题裁决", rendered)
        self.assertIsNotNone(result.answer_spec)
        assert result.answer_spec is not None
        all_output = rendered + json.dumps(
            result.answer_spec.to_dict(),
            ensure_ascii=False,
        )
        for forbidden in (
            "题材怎么理解",
            "产业链",
            "公司映射",
            "公告",
            "年报",
            "官网",
            "concept-ingest",
        ):
            self.assertNotIn(forbidden, all_output)

    def test_subjectless_market_pattern_skips_subject_rag_and_module_fanout(
        self,
    ) -> None:
        query = (
            "如果一个A股题材连续上涨，但板块成交占比开始下降，我应该怎么判断"
            "它是健康分歧还是行情高潮？"
        )
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch("intelligence.services.ask.kb_rag.retrieve") as retrieve,
            mock.patch("intelligence.services.ask.run_module") as run_module,
        ):
            result = answer_query(
                AskOptions(
                    query=query,
                    exports_dir=tmp,
                    kb_wiki=Path(tmp),
                    use_modules=True,
                    use_wiki_rag=True,
                )
            )

        retrieve.assert_not_called()
        run_module.assert_not_called()
        assert result.question_plan is not None
        self.assertEqual(
            result.question_plan.query_envelope.subject_kind,
            "market_pattern",
        )
        self.assertIsNone(result.closed_loop_retrieval)
        assert result.retrieval_telemetry is not None
        self.assertEqual(
            result.retrieval_telemetry.wiki_degraded,
            "no explicit subject; subject RAG skipped",
        )

    def test_named_theme_uses_three_argument_retriever_and_at_most_one_dense(
        self,
    ) -> None:
        def fake_retrieve(
            _query: str,
            _wiki: Path,
            **kwargs: object,
        ) -> WikiRagResult:
            mode = str(kwargs["mode"])
            hits = (
                [
                    WikiHit(
                        page_id="liquid-cooling",
                        file_path="wiki/concepts/液冷.md",
                        title="液冷",
                        score=0.9,
                        excerpt="液冷产业链供需证据",
                        best_chunk_id="liquid-cooling::0",
                        content_hash="hash-liquid-cooling",
                        index_source_revision="rev-1",
                        index_freshness="fresh",
                        fact_hardness="hard",
                    )
                ]
                if mode == "hybrid"
                else []
            )
            return WikiRagResult(
                ok=bool(hits),
                hits=hits,
                telemetry=RetrievalTelemetry(
                    mode=mode,
                    status="ok" if hits else "empty",
                    hit_count=len(hits),
                    index_freshness="fresh" if hits else "",
                    dense_initializations=1 if mode == "hybrid" else 0,
                    timeout_seconds=float(kwargs["timeout"]),
                ),
            )

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch(
                "intelligence.services.ask.kb_rag.retrieve",
                side_effect=fake_retrieve,
            ) as retrieve,
        ):
            result = answer_query(
                AskOptions(
                    query="分析液冷板块",
                    exports_dir=tmp,
                    kb_wiki=Path(tmp),
                    use_modules=False,
                    use_wiki_rag=True,
                    wiki_rag_timeout=3,
                )
            )

        modes = [call.kwargs["mode"] for call in retrieve.call_args_list]
        timeouts = [call.kwargs["timeout"] for call in retrieve.call_args_list]
        self.assertEqual(modes.count("hybrid"), 1)
        self.assertEqual(modes.count("bm25"), 3)
        self.assertTrue(all(timeout == 3.0 for timeout in timeouts))
        assert result.closed_loop_retrieval is not None
        self.assertEqual(result.closed_loop_retrieval.dense_initializations, 1)
        self.assertEqual(
            result.closed_loop_retrieval.inspector_dict()["dense_initializations"],
            1,
        )
        self.assertTrue(
            all(
                attempt["timeout_seconds"] == 3.0
                for attempt in result.closed_loop_retrieval.inspector_dict()[
                    "attempts"
                ]
            )
        )
        assert result.wiki_rag_telemetry is not None
        wiki_citations = [
            citation for citation in result.citations if citation.tag.startswith("W")
        ]
        self.assertEqual(result.wiki_rag_telemetry.status, "ok")
        self.assertEqual(result.wiki_rag_telemetry.index_freshness, "fresh")
        self.assertEqual(result.wiki_rag_telemetry.index_source_revision, "rev-1")
        self.assertEqual(len(wiki_citations), 1)
        self.assertEqual(wiki_citations[0].index_source_revision, "rev-1")
        self.assertEqual(wiki_citations[0].index_freshness, "fresh")

    def test_zero_adapter_cap_preserves_zero_timeout_without_spawning(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch("subprocess.run") as run,
        ):
            result = answer_query(
                AskOptions(
                    query="分析液冷板块",
                    exports_dir=tmp,
                    kb_wiki=Path(tmp),
                    use_modules=False,
                    use_wiki_rag=True,
                    wiki_rag_timeout=0,
                )
            )

        run.assert_not_called()
        assert result.closed_loop_retrieval is not None
        assert result.wiki_rag_telemetry is not None
        self.assertEqual(result.wiki_rag_telemetry.timeout_seconds, 0.0)
        self.assertEqual(result.wiki_rag_telemetry.dense_initializations, 0)
        attempts = result.closed_loop_retrieval.inspector_dict()["attempts"]
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["timeout_seconds"], 0.0)

    def test_irrelevant_hybrid_hits_publish_empty_and_create_no_w_citations(
        self,
    ) -> None:
        def fake_retrieve(
            _query: str,
            _wiki: Path,
            **kwargs: object,
        ) -> WikiRagResult:
            mode = str(kwargs["mode"])
            hits = (
                [
                    WikiHit(
                        page_id=f"unrelated-{index}",
                        file_path=f"wiki/unrelated-{index}.md",
                        title=f"半导体设备{index}",
                        score=0.9 - index / 10,
                        excerpt="半导体设备订单增长",
                        best_chunk_id=f"unrelated::{index}",
                        content_hash=f"hash-{index}",
                        index_source_revision="rev-1",
                        index_freshness="fresh",
                        fact_hardness="hard",
                    )
                    for index in range(4)
                ]
                if mode == "hybrid"
                else []
            )
            return WikiRagResult(
                ok=bool(hits),
                hits=hits,
                telemetry=RetrievalTelemetry(
                    mode=mode,
                    status="ok" if hits else "empty",
                    hit_count=len(hits),
                    index_source_revision="rev-1" if hits else "",
                    index_freshness="fresh" if hits else "",
                    dense_initializations=1 if mode == "hybrid" else 0,
                    timeout_seconds=float(kwargs["timeout"]),
                ),
            )

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch(
                "intelligence.services.ask.kb_rag.retrieve",
                side_effect=fake_retrieve,
            ),
        ):
            result = answer_query(
                AskOptions(
                    query="分析液冷板块",
                    exports_dir=tmp,
                    kb_wiki=Path(tmp),
                    use_modules=False,
                    use_wiki_rag=True,
                )
            )

        assert result.closed_loop_retrieval is not None
        assert result.wiki_rag_telemetry is not None
        assert result.retrieval_telemetry is not None
        self.assertEqual(len(result.closed_loop_retrieval.discarded), 4)
        self.assertFalse(result.retrieval_telemetry.wiki_ok)
        self.assertFalse(
            any(citation.tag.startswith("W") for citation in result.citations)
        )
        self.assertEqual(result.wiki_rag_telemetry.status, "empty")
        self.assertEqual(result.wiki_rag_telemetry.hit_count, 0)
        self.assertTrue(result.wiki_rag_telemetry.degraded)
        self.assertIn("all retrieved hits rejected", result.wiki_rag_telemetry.warning)
        self.assertIn(
            "all retrieved hits rejected",
            result.retrieval_telemetry.wiki_degraded or "",
        )

    def test_explicit_stock_wording_still_routes_to_deep_dive(self) -> None:
        plan = plan_answer_question("这只股怎么看")

        self.assertEqual(plan.question_type, QUESTION_STOCK_DEEP_DIVE)

    def test_closed_loop_keeps_weak_positive_out_but_retains_counter_clue(
        self,
    ) -> None:
        calls = 0

        def fake_retrieve(query: str, *_args: object, **_kwargs: object):
            nonlocal calls
            calls += 1
            if calls == 1:
                hits = [
                    WikiHit(
                        page_id="weak",
                        file_path="wiki/weak.md",
                        title="弱相关首页",
                        score=0.2,
                        excerpt="液冷排名靠前但证据很弱",
                        best_chunk_id="weak",
                        index_freshness="fresh",
                    )
                ]
            elif "风险 证伪" in query:
                hits = [
                    WikiHit(
                        page_id="counter",
                        file_path="wiki/counter.md",
                        title="需求下滑风险",
                        score=0.1,
                        excerpt="液冷需求可能不及预期，仍待核验",
                        best_chunk_id="counter",
                        index_freshness="fresh",
                    )
                ]
            else:
                hits = []
            return WikiRagResult(
                ok=bool(hits),
                hits=hits,
                telemetry=RetrievalTelemetry(
                    status="ok" if hits else "empty",
                    hit_count=len(hits),
                    index_freshness="fresh" if hits else "",
                ),
            )

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch(
                "intelligence.services.ask.kb_rag.retrieve",
                side_effect=fake_retrieve,
            ),
        ):
            result = answer_query(
                AskOptions(
                    query="分析液冷板块最近怎么样",
                    exports_dir=tmp,
                    kb_wiki=Path(tmp),
                    use_modules=False,
                    use_wiki_rag=True,
                )
            )

        rendered = render_conversation_answer(result)
        self.assertNotIn("弱相关首页", rendered)
        self.assertIn("需求下滑风险", rendered)
        assert result.closed_loop_retrieval is not None
        self.assertEqual(len(result.closed_loop_retrieval.clues), 2)
        self.assertEqual(len(result.closed_loop_retrieval.counter_clues), 1)

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
