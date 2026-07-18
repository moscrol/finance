"""P0 加固回归测试（对应 2026-07-18 双审查合并方案）。

覆盖六个 P0 修复：
1. 标题/<summary> 走私：白名单外标题在校验、repair、展示三层都被拦截；
2. candidate_facts 通道：agent/Web/模块候选证据能合法进入 AnswerSpec registry；
3. agent loop 跨管线查询去重（QueryLedger 种子版）；
4. 影子链 Deadline 钳制：子流程不得晚于 turn 根截止时间；
5. market-review 散文契约不再被 claim-marker 门禁误杀；
6. 数据块 claim 铸造：W7/M/V/D8 不再默认 VERIFIED。
"""

from __future__ import annotations

import time
import unittest
from unittest import mock

from intelligence.services import llm_refine
from intelligence.services.agent_research import AgentEvidence, run_agent_loop
from intelligence.services.answer_model import (
    AnswerSpec,
    ClaimStatus,
    EvidenceRef,
    evidence_atoms_from_answer_spec,
    finalize_answer_spec,
    grounded_claim_registry_block,
    make_claim,
    present_grounded_composer_answer,
    present_llm_answer,
    repair_grounded_composer_answer,
    resolve_theme_research_spec,
    structured_claim_registry_block,
    validate_grounded_composer_answer,
    validate_llm_answer,
)
from intelligence.services.ask import AskOptions, AskResult, PreparedAnswer
from intelligence.services.ask_synthesis import (
    _build_answer_spec_for_result,
    _build_base_answer_spec_from_sections,
    _claims_from_data_block,
    _shadow_deadline,
    synthesize_prepared_answer,
)
from intelligence.services.closed_loop_retrieval import retrieve_closed_loop
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchDeadline


def _spec() -> AnswerSpec:
    research = resolve_theme_research_spec("分析人形机器人产业链")
    fact = make_claim(
        claim_id="fact-1",
        text="盘面显示涨幅2.61%，量能同步放大。",
        claim_type="market_signal",
        theme=research.theme,
        status=ClaimStatus.VERIFIED,
        evidence_tier="L4",
        evidence_ids=("S1",),
    )
    summary = make_claim(
        claim_id="sum-1",
        text="主题当前以盘面驱动为主。",
        claim_type="summary",
        theme=research.theme,
        status=ClaimStatus.INFERRED,
        evidence_tier="base_finance",
        evidence_ids=("S1",),
    )
    gap = make_claim(
        claim_id="gap-1",
        text="缺少公司级公告证据。",
        claim_type="evidence_gap",
        theme=research.theme,
        status=ClaimStatus.MISSING,
    )
    spec = AnswerSpec(
        research_spec=research,
        summary=(summary,),
        verified_facts=(fact,),
        company_table=(),
        counter_evidence=(),
        gaps=(gap,),
        triggers=(),
        next_actions=("T+1 观察量能是否延续",),
        sources=(
            EvidenceRef(evidence_id="S1", source="盘面快照", detail="", tier="L4"),
        ),
        system_notices=(),
    )
    return finalize_answer_spec(spec)


def _fact_marker_line(spec: AnswerSpec, grounded: bool) -> str:
    atom = next(
        atom
        for atom in evidence_atoms_from_answer_spec(spec)
        if atom.provenance["claim_id"] == "fact-1"
    )
    if grounded:
        marker = (
            f"<!-- claim_ids=fact-1; evidence_atom_ids={atom.atom_id}; "
            "claim_type=fact -->"
        )
    else:
        marker = (
            f"<!-- claim_id=fact-1; evidence_atom_ids={atom.atom_id}; "
            "claim_type=fact -->"
        )
    return f"- 盘面显示涨幅2.61%，量能同步放大。 {marker}"


class HeadingSmuggleTests(unittest.TestCase):
    """标题不是自由文本：白名单外标题按未验证内容处理。"""

    def test_grounded_validator_rejects_fact_smuggled_in_heading(self) -> None:
        spec = _spec()
        answer = "## 招商银行今年利润已翻倍\n" + _fact_marker_line(spec, grounded=True)

        issues = validate_grounded_composer_answer(answer, spec)

        self.assertTrue(
            any(
                issue.code == "grounded_composer_unverified_heading"
                and issue.severity == "error"
                for issue in issues
            )
        )

    def test_grounded_repair_drops_disallowed_heading(self) -> None:
        spec = _spec()
        answer = "## 招商银行今年利润已翻倍\n" + _fact_marker_line(spec, grounded=True)

        repaired = repair_grounded_composer_answer(answer, spec)

        self.assertIsNotNone(repaired)
        assert repaired is not None
        self.assertNotIn("招商银行", repaired)
        presented = present_grounded_composer_answer(repaired, spec)
        self.assertNotIn("招商银行", presented)
        self.assertIn("量能同步放大", presented)

    def test_allowed_headings_survive(self) -> None:
        spec = _spec()
        answer = (
            f"# {spec.research_spec.theme}\n\n## 结论\n"
            + _fact_marker_line(spec, grounded=True)
        )

        issues = validate_grounded_composer_answer(answer, spec)

        self.assertFalse(
            any("heading" in issue.code for issue in issues),
            msg=str(issues),
        )
        presented = present_grounded_composer_answer(answer, spec)
        self.assertIn("## 结论", presented)

    def test_summary_tag_smuggle_is_flagged(self) -> None:
        spec = _spec()
        answer = (
            "<details><summary>某科技公司订单已翻倍</summary>\n"
            + _fact_marker_line(spec, grounded=True)
            + "\n</details>"
        )

        issues = validate_grounded_composer_answer(answer, spec)

        self.assertTrue(
            any(
                issue.code == "grounded_composer_unverified_heading"
                for issue in issues
            )
        )

    def test_structured_presenter_drops_disallowed_heading(self) -> None:
        spec = _spec()
        answer = "## 招商银行今年利润已翻倍\n" + _fact_marker_line(
            spec, grounded=False
        )

        issues = validate_llm_answer(answer, spec)
        presented = present_llm_answer(answer, spec)

        self.assertTrue(
            any(
                issue.code == "llm_unverified_heading"
                and issue.severity == "warning"
                for issue in issues
            )
        )
        self.assertFalse(
            any(issue.severity == "error" for issue in issues),
            msg=str(issues),
        )
        self.assertNotIn("招商银行", presented)
        self.assertIn("量能同步放大", presented)

    def test_prose_without_markers_keeps_headings(self) -> None:
        """无 marker 的散文契约（市场复盘）不受标题剔除影响。"""
        spec = _spec()
        prose = "## 市场状态\n今天市场放量上涨。"

        presented = present_llm_answer(prose, spec)

        self.assertIn("## 市场状态", presented)


class CandidateFactsChannelTests(unittest.TestCase):
    """agent/Web/模块候选证据必须能合法进入 registry（不再是死证据）。"""

    def _result(self) -> AskResult:
        return AskResult(
            query="人形机器人还能追吗",
            trade_date=None,
            matched_theme="人形机器人",
            candidate_tier=None,
            priority_score=None,
        )

    def test_agent_candidate_claim_enters_registry(self) -> None:
        research = resolve_theme_research_spec("分析人形机器人产业链")
        agent_claim = make_claim(
            claim_id="agent:A1",
            text="某研报提到执行器降本进展。 [A1]",
            claim_type="theme_evidence",
            theme=research.theme,
            status=ClaimStatus.CANDIDATE,
            evidence_tier="agent_retrieval",
        )
        from intelligence.services.ask_types import Citation

        spec = _build_answer_spec_for_result(
            result=self._result(),
            research_spec=research,
            conclusion_lines=["盘面驱动为主。"],
            structured_claims=[agent_claim],
            company_candidates=[],
            counter_lines=[],
            gap_lines=["缺少公司级证据"],
            trigger_lines=[],
            follow_ups=["T+1 观察量能"],
            citations=[Citation("A1", "agent 补检索 · web_search", "http://example.com")],
        )

        self.assertIn(
            "agent:A1",
            [claim.claim_id for claim in spec.candidate_facts],
        )
        self.assertIn("agent:A1", structured_claim_registry_block(spec))
        self.assertIn('"claim_type": "candidate"', grounded_claim_registry_block(spec))
        self.assertIn("候选证据", spec.to_prompt_block())

    def test_company_bound_candidates_not_duplicated(self) -> None:
        """已随公司表进 registry 的 claim 不重复进入 candidate_facts。"""
        research = resolve_theme_research_spec("分析人形机器人产业链")
        from intelligence.services.answer_model import CompanyCandidate, CompanyTier
        from intelligence.services.ask_types import Citation

        company_claim = make_claim(
            claim_id="company:示例科技:R1",
            text="示例科技存在执行器候选资料。 [R1]",
            claim_type="company_evidence",
            theme=research.theme,
            status=ClaimStatus.CANDIDATE,
            evidence_tier="L1_L3_candidate",
            company="示例科技",
        )
        spec = _build_answer_spec_for_result(
            result=self._result(),
            research_spec=research,
            conclusion_lines=["盘面驱动为主。"],
            structured_claims=[company_claim],
            company_candidates=[
                CompanyCandidate(
                    company="示例科技",
                    requested_tier=CompanyTier.CANDIDATE,
                )
            ],
            counter_lines=[],
            gap_lines=["缺少公司级证据"],
            trigger_lines=[],
            follow_ups=["T+1 观察量能"],
            citations=[Citation("R1", "evidence_index", "")],
        )

        self.assertNotIn(
            "company:示例科技:R1",
            [claim.claim_id for claim in spec.candidate_facts],
        )


class AgentQueryLedgerTests(unittest.TestCase):
    """agent 不得重发主链已执行过的查询。"""

    def test_pipeline_attempted_query_is_intercepted(self) -> None:
        responses = iter(
            (
                '{"tool": "kb_search", "args": {"query": "人形机器人 产业链"}, '
                '"reason": "补检索"}',
                '{"tool": "finish", "args": {"sufficient": true, "gaps": []}, '
                '"reason": "证据足够"}',
            )
        )

        def fake_complete(messages, **kwargs):
            return next(responses), None, ""

        def kb_runner(query: str):
            raise AssertionError("重复查询不应触达工具层")

        result = run_agent_loop(
            "人形机器人还能追吗",
            tools={"kb_search": kb_runner},
            complete_fn=fake_complete,
            attempted_queries=(("kb_search", "人形机器人 产业链"),),
        )

        self.assertIn("重复查询已拦截", result.steps[0].observation)
        self.assertEqual(result.steps[1].tool, "finish")
        self.assertTrue(result.sufficient)


class DeadlineClampTests(unittest.TestCase):
    """子流程截止时间 = min(自身超时, turn 根 Deadline)。"""

    def test_shadow_deadline_never_exceeds_turn_deadline(self) -> None:
        parent = ResearchDeadline(expires_at=time.monotonic() + 5.0)
        options = AskOptions(
            query="测试",
            shadow_grounded_timeout=240,
            deadline=parent,
        )

        clamped = _shadow_deadline(options)

        self.assertLessEqual(clamped.expires_at, parent.expires_at + 1e-6)

    def test_shadow_deadline_uses_own_timeout_without_parent(self) -> None:
        options = AskOptions(query="测试", shadow_grounded_timeout=1)

        clamped = _shadow_deadline(options)

        self.assertLessEqual(
            clamped.expires_at,
            time.monotonic() + 1.5,
        )

    def test_closed_loop_respects_zero_budget(self) -> None:
        def retrieve(query: str):
            raise AssertionError("预算为零时不应发起检索")

        result = retrieve_closed_loop(
            "液冷",
            anchor=None,
            retrieve=retrieve,
            total_seconds=0.0,
        )

        self.assertEqual(result.attempts, [])


class MarketReviewProseContractTests(unittest.TestCase):
    """市场复盘散文不再被 claim-marker 门禁整答退稿。"""

    def test_market_review_prose_survives_gate(self) -> None:
        result = AskResult(
            query="复盘今天的A股",
            trade_date="2026-07-17",
            matched_theme=None,
            candidate_tier=None,
            priority_score=None,
        )
        result.answer_spec = _build_base_answer_spec_from_sections(
            result,
            theme="市场复盘",
            evidence_blocks=("今日市场总览：放量上涨。",),
            direct_lines=("市场放量上涨。",),
        )
        result.prepared_synthesis_messages = [
            {"role": "system", "content": "market review"},
            {"role": "user", "content": "复盘"},
        ]
        result.prepared_synthesis_is_market_review = True
        prose = "今天市场放量上涨，主线集中在算力方向。（非投资建议）"
        composed = llm_refine.SynthesisResult(
            answer=prose,
            provider="test",
            model="test-model",
            finish_reason="stop",
        )
        options = AskOptions(query="复盘今天的A股", synthesize=False)

        with mock.patch.object(
            llm_refine,
            "synthesize_messages",
            return_value=(composed, ""),
        ):
            synthesize_prepared_answer(
                PreparedAnswer(options=options, result=result)
            )

        self.assertIsNotNone(result.synthesis)
        assert result.synthesis is not None
        self.assertIn("放量上涨", result.synthesis)
        self.assertNotEqual(result.llm_fallback_reason, "quality_gate_rejected")


class DataBlockClaimStatusTests(unittest.TestCase):
    """VERIFIED 不能靠关键词缺席铸造：W7/M/V/D8 默认降档。"""

    def test_w7_news_lines_are_candidate(self) -> None:
        claims = _claims_from_data_block(
            "- 2026-07-17 某媒体《公司获得大额订单》",
            "W7",
            "web 事件检索",
            "人形机器人",
        )

        self.assertTrue(claims)
        self.assertTrue(
            all(claim.status == ClaimStatus.CANDIDATE for claim in claims)
        )

    def test_d8_analog_lines_are_inferred(self) -> None:
        claims = _claims_from_data_block(
            "- 与 2026-03 窗口形态距离 0.12，后续 5 日上涨",
            "D8",
            "历史类比检索",
            "人形机器人",
        )

        self.assertTrue(claims)
        self.assertTrue(
            all(claim.status == ClaimStatus.INFERRED for claim in claims)
        )

    def test_duckdb_blocks_stay_verified(self) -> None:
        claims = _claims_from_data_block(
            "- 近5日成交额均值 812 亿",
            "D6",
            "多日中期趋势",
            "人形机器人",
        )

        self.assertTrue(claims)
        self.assertTrue(
            all(claim.status == ClaimStatus.VERIFIED for claim in claims)
        )


class AgentEvidenceTraceSmokeTests(unittest.TestCase):
    """agent 证据行→claim 的最小烟囱：确保 AgentEvidence/ProviderTrace 形态未破坏。"""

    def test_agent_evidence_shape(self) -> None:
        evidence = AgentEvidence(
            tool="web_search",
            title="标题",
            detail="摘要",
            source="http://example.com",
        )
        trace = ProviderTrace(
            provider="agent:web_search",
            capability="agent_loop",
            status="success",
            result_count=1,
        )

        self.assertEqual(evidence.tool, "web_search")
        self.assertEqual(trace.to_dict()["provider"], "agent:web_search")


if __name__ == "__main__":
    unittest.main()
