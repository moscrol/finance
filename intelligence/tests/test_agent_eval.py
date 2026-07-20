from __future__ import annotations

import json
import unittest
from pathlib import Path

from intelligence.eval import runner as R
from intelligence.eval.agent_eval import (
    CaseSpec,
    TurnInput,
    build_scorecard,
    extract_cited_tags,
    parse_wiki_step,
    score_case,
    score_turn,
)
from intelligence.eval.capability_monotonicity import (
    compare_capability,
    evaluate_capability_case,
)

GOOD_ANSWER = (
    "液冷题材盘面 double_red [S1]，图谱核心层英维克、高澜股份 [G1][G2]，"
    "证据库高澜股份逻辑卡 [R1]，wiki 命中液冷服务器 [W1]。"
    "外围标的列为 graph_only 待验证，过期证据已标 ⚠️过期。（非投资建议）"
)

REGISTRY = ["S1", "G1", "G2", "R1", "W1"]


def _spec(**kw) -> CaseSpec:
    base = dict(
        id="liquid-cooling",
        query="液冷",
        expect_entities=["英维克", "高澜股份", "申菱环境", "川润股份"],
        expect_concepts=["液冷"],
        expect_sources=["S", "G", "R", "W"],
        min_tool_calls=3,
        max_tool_calls=40,
        entity_recall_gate=0.5,
    )
    base.update(kw)
    return CaseSpec.from_dict(base)


def _good_turn(**kw) -> TurnInput:
    base = dict(
        question="液冷",
        answer=GOOD_ANSWER,
        tools_called=["search_market_snapshot", "search_graph", "search_evidence", "search_wiki"],
        registry_tags=list(REGISTRY),
        wiki_calls=1,
        wiki_hit_calls=1,
        wiki_top_relevances=[0.53],
        is_followup=False,
    )
    base.update(kw)
    return TurnInput(**base)


class TestPureHelpers(unittest.TestCase):
    def test_extract_cited_tags_order_and_dups(self):
        tags = extract_cited_tags("a [S1] b [G2] c [S1] d [W10]")
        self.assertEqual(tags, ["S1", "G2", "S1", "W10"])

    def test_extract_cited_tags_ignores_noise(self):
        # bracketed non-source tokens and bare numbers must not match
        self.assertEqual(extract_cited_tags("[X1] [12] [s1] (R1)"), [])

    def test_extract_cited_tags_none(self):
        self.assertEqual(extract_cited_tags(None), [])

    def test_parse_wiki_step_hit(self):
        hit, rel = parse_wiki_step("液冷服务器（相关度 0.5325）：摘录… [W1]")
        self.assertTrue(hit)
        self.assertAlmostEqual(rel, 0.5325)

    def test_parse_wiki_step_takes_max(self):
        _, rel = parse_wiki_step("a 相关度 0.20 b 相关度 0.41")
        self.assertAlmostEqual(rel, 0.41)

    def test_parse_wiki_step_miss(self):
        self.assertEqual(parse_wiki_step("wiki 语义召回无命中，建议放宽关键词"), (False, None))
        self.assertEqual(parse_wiki_step("wiki 检索不可用：索引不存在"), (False, None))


class TestCapabilityMonotonicity(unittest.TestCase):
    def test_fixture_cases_expose_all_advisory_dimensions(self):
        fixture = Path(__file__).parent / "fixtures" / "capability_monotonicity_cases.json"
        cases = json.loads(fixture.read_text(encoding="utf-8"))["cases"]

        self.assertGreaterEqual(len(cases), 6)
        for case in cases:
            score = evaluate_capability_case(case).to_dict()
            self.assertTrue(
                {
                    "directness",
                    "task_coverage",
                    "grounding",
                    "fallback_fidelity",
                    "template_signature",
                }.issubset(score),
                case["id"],
            )

    def test_pair_reports_constraint_induced_regression(self):
        minimal = {
            "id": "weekly-cause",
            "question": "本周为什么下跌",
            "answer": "风险偏好收缩是主因，成交和跌停扩散支持这一判断。",
            "direct_targets": ["风险偏好收缩"],
            "requirements": [{"id": "cause", "satisfy_any": ["风险偏好收缩"]}],
        }
        workbench = {
            **minimal,
            "answer": "# 每日市场复盘\n涨停集中在人工智能和电力。",
        }

        comparison = compare_capability(minimal, workbench)
        self.assertFalse(comparison.monotonic)
        self.assertIn("directness", comparison.regressions)
        self.assertIn("task_coverage", comparison.regressions)

    def test_methodology_terms_are_not_misclassified_as_control_plane_leaks(self):
        score = evaluate_capability_case(
            {
                "id": "methodology",
                "question": "RAG、BM25 和 DuckDB 怎么配合",
                "answer": "RAG 用 BM25 补词面召回，DuckDB 保存结构化事实。",
                "direct_targets": ["RAG"],
            }
        )
        self.assertEqual(score.control_plane_leak_score, 0.0)

    def test_composer_timeout_fallback_keeps_decision_brief(self):
        score = evaluate_capability_case(
            {
                "id": "timeout",
                "question": "为什么下跌",
                "answer": "风险偏好收缩是主因；内部量价支持，但外部证据不足。",
                "decision_brief": {
                    "direct_answer": "风险偏好收缩是主因",
                    "core_tension": "内部量价支持，但外部证据不足",
                },
                "direct_targets": ["风险偏好收缩"],
            }
        )
        self.assertEqual(score.fallback_fidelity, 1.0)


class TestTurnScoring(unittest.TestCase):
    def test_clean_turn_passes(self):
        ts = score_turn(_good_turn(), _spec())
        self.assertTrue(ts.passed, ts.failures)
        self.assertEqual(ts.citation_resolvable, 1.0)
        self.assertEqual(ts.dangling_citations, [])
        self.assertTrue(ts.disclaimer_present)
        self.assertTrue(ts.graph_only_flagged)
        self.assertTrue(ts.stale_flagged)
        self.assertEqual(ts.cited_sources, ["G", "R", "S", "W"])
        self.assertAlmostEqual(ts.wiki_top_relevance, 0.53)
        self.assertEqual(ts.wiki_miss_rate, 0.0)

    def test_hallucinated_citation_fails(self):
        ti = _good_turn(answer=GOOD_ANSWER + " 另据 [R99] 显示…")
        ts = score_turn(ti, _spec())
        self.assertFalse(ts.passed)
        self.assertIn("R99", ts.dangling_citations)
        self.assertLess(ts.citation_resolvable, 1.0)
        self.assertTrue(any("编造引用" in f for f in ts.failures))

    def test_missing_disclaimer_fails(self):
        ti = _good_turn(answer=GOOD_ANSWER.replace("（非投资建议）", ""))
        ts = score_turn(ti, _spec())
        self.assertFalse(ts.passed)
        self.assertTrue(any("免责声明" in f for f in ts.failures))

    def test_first_turn_below_min_tools_fails(self):
        ti = _good_turn(tools_called=["search_graph"])  # 1 < min 3
        ts = score_turn(ti, _spec())
        self.assertFalse(ts.passed)
        self.assertFalse(ts.tool_calls_in_range)

    def test_followup_zero_tools_ok(self):
        ti = _good_turn(tools_called=[], is_followup=True)
        ts = score_turn(ti, _spec())
        self.assertTrue(ts.passed, ts.failures)

    def test_over_max_tools_fails(self):
        ti = _good_turn(tools_called=["search_graph"] * 41)
        ts = score_turn(ti, _spec(max_tool_calls=40))
        self.assertFalse(ts.passed)

    def test_empty_answer_fails(self):
        ts = score_turn(_good_turn(answer=None), _spec())
        self.assertFalse(ts.passed)
        self.assertFalse(ts.answered)

    def test_wiki_miss_rate(self):
        ti = _good_turn(wiki_calls=4, wiki_hit_calls=1, wiki_top_relevances=[0.2])
        ts = score_turn(ti, _spec())
        self.assertAlmostEqual(ts.wiki_miss_rate, 0.75)


class TestCaseScoring(unittest.TestCase):
    def test_full_case_passes(self):
        turns = [
            _good_turn(),
            _good_turn(
                question="强瑞 vs 冰轮",
                answer="对比申菱环境与川润股份 [G2]。（非投资建议）",
                tools_called=[],
                is_followup=True,
            ),
        ]
        cs = score_case(turns, _spec())
        self.assertTrue(cs.passed, cs.failures)
        self.assertEqual(cs.entity_recall, 1.0)  # 4/4 across the two turns
        self.assertTrue(cs.source_coverage)

    def test_entity_recall_below_gate_fails(self):
        ti = _good_turn(answer="只提到了英维克 [S1][G1][R1][W1]。（非投资建议）")
        cs = score_case([ti], _spec(entity_recall_gate=0.5))
        self.assertFalse(cs.passed)
        self.assertEqual(cs.entity_recall, 0.25)  # 1/4
        self.assertTrue(any("实体召回" in f for f in cs.failures))

    def test_missing_source_fails(self):
        # answer never cites a W tag → W source uncovered
        ti = _good_turn(answer="英维克高澜股份申菱环境川润股份 [S1][G1][R1]。（非投资建议）")
        cs = score_case([ti], _spec())
        self.assertFalse(cs.passed)
        self.assertIn("W", cs.missing_sources)

    def test_turn_failure_bubbles_to_case(self):
        ti = _good_turn(answer=GOOD_ANSWER + " [R99]")
        cs = score_case([ti], _spec())
        self.assertFalse(cs.passed)
        self.assertTrue(any("首轮" in f and "编造引用" in f for f in cs.failures))


class TestFactualityAndLayerGates(unittest.TestCase):
    def test_false_attribution_entity_fails(self):
        # 宁德时代 is not a PCB constituent; surfacing it as one must fail.
        ti = _good_turn(answer=GOOD_ANSWER + " PCB 受益还有宁德时代。")
        cs = score_case([ti], _spec(forbid_entities=["宁德时代"]))
        self.assertFalse(cs.passed)
        self.assertIn("宁德时代", cs.false_attributions)
        self.assertTrue(any("错配题材实体" in f for f in cs.failures))

    def test_clean_answer_has_no_false_attribution(self):
        cs = score_case([_good_turn()], _spec(forbid_entities=["宁德时代"]))
        self.assertEqual(cs.false_attributions, [])

    def test_evidence_layer_overclaim_fails(self):
        ti = _good_turn(answer=GOOD_ANSWER + " 该题材业绩已兑现。")
        cs = score_case([ti], _spec(forbid_phrases=["业绩已兑现"]))
        self.assertFalse(cs.passed)
        self.assertIn("业绩已兑现", cs.overclaims)
        self.assertTrue(any("overclaim" in f for f in cs.failures))

    def test_no_overclaim_passes(self):
        cs = score_case([_good_turn()], _spec(forbid_phrases=["业绩已兑现"]))
        self.assertTrue(cs.passed, cs.failures)
        self.assertEqual(cs.overclaims, [])

    def test_forbid_fields_round_trip_offline(self):
        spec = _spec(forbid_entities=["宁德时代"], forbid_phrases=["业绩已兑现"])
        _, record = R.run_eval(
            [spec], 1.0, R.EvalRunOptions(),
            case_runner=lambda s, o: [_good_turn(answer=GOOD_ANSWER + " 宁德时代业绩已兑现。")],
        )
        record = json.loads(json.dumps(record, ensure_ascii=False))
        card = R.score_run(record, [spec])
        self.assertFalse(card.passed)


class TestScorecard(unittest.TestCase):
    def test_gate_pass_and_fail(self):
        good = score_case([_good_turn()], _spec(expect_entities=["英维克"]))
        bad = score_case([_good_turn(answer="无引用无声明")], _spec())
        self.assertTrue(build_scorecard([good], 1.0).passed)
        self.assertFalse(build_scorecard([good, bad], 1.0).passed)
        self.assertTrue(build_scorecard([good, bad], 0.5).passed)

    def test_format_scorecard_smoke(self):
        card = build_scorecard([score_case([_good_turn()], _spec(expect_entities=["英维克"]))], 1.0)
        out = R.format_scorecard(card)
        self.assertIn("记分卡", out)
        self.assertIn("PASS", out)
        self.assertIn("错配实体", out)
        self.assertIn("证据越级", out)

    def test_format_scorecard_surfaces_factuality_failures(self):
        bad = score_case(
            [_good_turn(answer=GOOD_ANSWER + " 宁德时代业绩已兑现。")],
            _spec(forbid_entities=["宁德时代"], forbid_phrases=["业绩已兑现"]),
        )
        card = build_scorecard([bad], 1.0)
        out = R.format_scorecard(card)
        self.assertIn("宁德时代", out)
        self.assertIn("业绩已兑现", out)
        self.assertIn("错配实体", out)
        self.assertIn("证据越级", out)


class TestRunnerAdapterAndReplay(unittest.TestCase):
    def _fake_result(self):
        from intelligence.services.agent import AgentResult, AgentStep
        from intelligence.services.ask import Citation

        return AgentResult(
            answer=GOOD_ANSWER,
            steps=[
                AgentStep(tool="search_market_snapshot", args={}, result_preview="double_red…"),
                AgentStep(tool="search_graph", args={}, result_preview="英维克…"),
                AgentStep(tool="search_wiki", args={"query": "液冷"}, result_preview="液冷服务器（相关度 0.5325）…"),
                AgentStep(tool="search_wiki", args={"query": "x"}, result_preview="wiki 语义召回无命中"),
            ],
            citations=[Citation(tag=t, source="src") for t in REGISTRY],
            provider="deepseek",
        )

    def test_turn_input_from_result(self):
        res = self._fake_result()
        ti = R.turn_input_from_result("液冷", res, [c.tag for c in res.citations], is_followup=False)
        self.assertEqual(ti.tools_called, ["search_market_snapshot", "search_graph", "search_wiki", "search_wiki"])
        self.assertEqual(ti.wiki_calls, 2)
        self.assertEqual(ti.wiki_hit_calls, 1)
        self.assertEqual(ti.wiki_top_relevances, [0.5325])
        self.assertEqual(ti.registry_tags, REGISTRY)
        self.assertTrue(score_turn(ti, _spec()).passed)

    def test_run_eval_with_injected_runner(self):
        spec = _spec(expect_entities=["英维克"], followups=["q2"])

        def fake_case_runner(s, opts):
            return [
                _good_turn(),
                _good_turn(question="q2", answer="英维克 [G1]。（非投资建议）", tools_called=[], is_followup=True),
            ]

        card, record = R.run_eval([spec], 1.0, R.EvalRunOptions(), case_runner=fake_case_runner)
        self.assertTrue(card.passed)
        self.assertEqual(len(record["cases"][0]["turns"]), 2)

    def test_score_run_offline_deterministic(self):
        spec = _spec(expect_entities=["英维克"])
        _, record = R.run_eval(
            [spec], 1.0, R.EvalRunOptions(), case_runner=lambda s, o: [_good_turn()]
        )
        # round-trip through JSON, then re-score twice — must be identical & deterministic
        record = json.loads(json.dumps(record, ensure_ascii=False))
        c1 = R.score_run(record, [spec])
        c2 = R.score_run(record, [spec])
        self.assertTrue(c1.passed)
        self.assertEqual(c1.to_dict(), c2.to_dict())

    def test_turn_input_dict_round_trip(self):
        ti = _good_turn()
        self.assertEqual(TurnInput.from_dict(ti.to_dict()).to_dict(), ti.to_dict())


class TestBundledCases(unittest.TestCase):
    def test_bundled_cases_load(self):
        path = Path(__file__).resolve().parents[1] / "eval" / "cases" / "agent_cases.json"
        specs, gate = R.load_cases(path)
        ids = {s.id for s in specs}
        self.assertEqual(
            ids,
            {"liquid-cooling", "photoresist", "commercial-aerospace", "pcb", "solid-state-battery", "ai-glasses"},
        )
        self.assertEqual(gate, 1.0)
        for s in specs:
            self.assertEqual(s.expect_sources, ["S", "G", "R", "W"])
            self.assertTrue(s.expect_entities)
            self.assertTrue(s.followups)

    def test_new_cases_carry_grounded_guard_fields(self):
        path = Path(__file__).resolve().parents[1] / "eval" / "cases" / "agent_cases.json"
        specs, _ = R.load_cases(path)
        by_id = {s.id: s for s in specs}
        # factuality traps are real cross-theme companies that must not be pulled in
        self.assertIn("宁德时代", by_id["pcb"].forbid_entities)
        self.assertIn("世运电路", by_id["solid-state-battery"].forbid_entities)
        # AI 眼镜 has no L3 in the KB -> overclaim guard present
        self.assertTrue(by_id["ai-glasses"].forbid_phrases)


if __name__ == "__main__":
    unittest.main()
