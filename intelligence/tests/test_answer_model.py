from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from intelligence.services.answer_model import (
    AnswerSpec,
    ClaimStatus,
    CompanyCandidate,
    CompanyTier,
    EvidenceRef,
    build_company_assessments,
    evaluate_answer_spec,
    finalize_answer_spec,
    humanize,
    make_claim,
    repair_llm_answer,
    evidence_atoms_from_answer_spec,
    present_llm_answer,
    render_answer_spec,
    resolve_theme_research_spec,
    validate_llm_answer,
)
from intelligence.services.ask import (
    AskOptions,
    answer_query,
    match_candidate,
    render_conversation_answer,
)


class ThemeResearchSpecTests(unittest.TestCase):
    def test_domain_packs_share_one_protocol(self) -> None:
        cases = {
            "稳定币支付": "stablecoin_payment",
            "人形机器人": "robotics",
            "AI 算力": "compute_infrastructure",
            "英维克液冷": "data_center_liquid_cooling",
            "ArF 光刻胶": "photoresist",
            "可回收火箭": "commercial_space",
            "AI 服务器 PCB": "ai_server_pcb",
            "固态电解质": "solid_state_battery",
            "AI 眼镜": "ai_glasses",
            "低空经济": "low_altitude_economy",
        }
        for query, pack_id in cases.items():
            spec = resolve_theme_research_spec(f"分析 2026-07-10 的{query}产业链")
            self.assertEqual(spec.pack_id, pack_id)
            self.assertEqual(spec.as_of, "2026-07-10")
            self.assertEqual(len(spec.chain_stages), 3)
            self.assertIn("company_mapping", spec.requested_sections)
            self.assertTrue(spec.evidence_requirements)
            self.assertTrue(spec.counter_evidence_requirements)
            self.assertTrue(spec.verification_actions)
        self.assertEqual(
            resolve_theme_research_spec("请个股深挖英维克的液冷业务").theme,
            "液冷",
        )

    def test_market_candidate_ignores_weak_peripheral_concept_match(self) -> None:
        doc = {
            "candidates": [
                {
                    "canonical_concept": "数据要素",
                    "matched_concepts": [{"concept": "液冷", "score": 2}],
                }
            ]
        }

        self.assertIsNone(match_candidate("请个股深挖英维克的液冷业务", doc))

    def test_generic_question_is_not_reused_as_theme_name(self) -> None:
        query = "如果一个A股题材连续上涨，怎么区分健康分歧和行情高潮？"

        spec = resolve_theme_research_spec(query)

        self.assertEqual(spec.theme, "未命名题材")
        self.assertNotEqual(spec.theme, query)


class ClaimAdjudicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = resolve_theme_research_spec("分析人形机器人产业链")

    def test_company_cannot_be_core_without_bound_verified_claim(self) -> None:
        candidate = CompanyCandidate(
            company="示例科技",
            ticker="000001",
            chain_stage="执行器",
            directness="直接",
            requested_tier=CompanyTier.CORE,
            evidence_layer="L3",
        )
        candidate_claim = make_claim(
            claim_id="candidate-1",
            text="示例科技存在机器人执行器候选资料。",
            claim_type="company_evidence",
            theme=self.spec.theme,
            status=ClaimStatus.CANDIDATE,
            evidence_tier="L1_L3_candidate",
            company="示例科技",
            evidence_ids=("R1",),
        )

        assessment = build_company_assessments([candidate], [candidate_claim])[0]

        self.assertEqual(assessment.tier, CompanyTier.CANDIDATE)
        self.assertIn("需公告、年报", assessment.evidence_gaps[0])

    def test_verified_company_claim_can_upgrade_core_tier(self) -> None:
        candidate = CompanyCandidate(
            company="示例科技",
            requested_tier=CompanyTier.CORE,
        )
        verified_claim = make_claim(
            claim_id="verified-1",
            text="示例科技公告披露机器人执行器量产订单。",
            claim_type="company_evidence",
            theme=self.spec.theme,
            status=ClaimStatus.VERIFIED,
            evidence_tier="L3",
            company="示例科技",
            evidence_ids=("L1",),
        )

        assessment = build_company_assessments([candidate], [verified_claim])[0]

        self.assertEqual(assessment.tier, CompanyTier.CORE)
        self.assertFalse(assessment.evidence_gaps)

    def test_verified_claim_does_not_override_candidate_directness(self) -> None:
        candidate = CompanyCandidate(
            company="示例科技",
            requested_tier=CompanyTier.CANDIDATE,
        )
        verified_claim = make_claim(
            claim_id="verified-2",
            text="示例科技公告披露机器人相关产品。",
            claim_type="company_evidence",
            theme=self.spec.theme,
            status=ClaimStatus.VERIFIED,
            evidence_tier="L3",
            company="示例科技",
            evidence_ids=("L2",),
        )

        assessment = build_company_assessments([candidate], [verified_claim])[0]

        self.assertEqual(assessment.tier, CompanyTier.CANDIDATE)

    def test_market_only_verified_claim_cannot_upgrade_core_tier(self) -> None:
        candidate = CompanyCandidate(
            company="示例科技",
            requested_tier=CompanyTier.CORE,
        )
        market_claim = make_claim(
            claim_id="market-only-company",
            text="示例科技当日涨幅居前。",
            claim_type="company_evidence",
            theme=self.spec.theme,
            status=ClaimStatus.VERIFIED,
            evidence_tier="market_data",
            company="示例科技",
            evidence_ids=("D7",),
        )

        assessment = build_company_assessments([candidate], [market_claim])[0]

        self.assertEqual(assessment.tier, CompanyTier.CANDIDATE)
        self.assertIn("需公告、年报", assessment.evidence_gaps[0])

    def test_unresolved_official_claim_is_downgraded_before_rendering(self) -> None:
        candidate = CompanyCandidate(
            company="示例科技",
            requested_tier=CompanyTier.CORE,
        )
        official_claim = make_claim(
            claim_id="unresolved-company",
            text="示例科技公告披露机器人订单。",
            claim_type="company_evidence",
            theme=self.spec.theme,
            status=ClaimStatus.VERIFIED,
            evidence_tier="L3",
            company="示例科技",
            evidence_ids=("R1",),
        )
        answer = AnswerSpec(
            research_spec=self.spec,
            summary=(official_claim,),
            verified_facts=(official_claim,),
            company_table=build_company_assessments(
                [candidate],
                [official_claim],
            ),
            counter_evidence=(),
            gaps=(
                make_claim(
                    claim_id="unresolved-gap",
                    text="来源尚未解析到官方证据层。",
                    claim_type="evidence_gap",
                    theme=self.spec.theme,
                    status=ClaimStatus.MISSING,
                ),
            ),
            triggers=(),
            next_actions=("重新核对公告来源。",),
            sources=(
                EvidenceRef("R1", "盘面快照", tier="market_data"),
            ),
            system_notices=(),
        )

        governed = finalize_answer_spec(answer)
        rendered = render_answer_spec(governed)

        self.assertEqual(
            governed.company_table[0].tier,
            CompanyTier.CANDIDATE,
        )
        self.assertNotIn("### 核心公司", rendered)
        self.assertIn("候选资料，需公告或年报确认", rendered)

    def test_quality_gate_rejects_candidate_as_verified_fact(self) -> None:
        candidate_fact = make_claim(
            claim_id="candidate-fact",
            text="示例科技已经形成量产收入。",
            claim_type="company_evidence",
            theme=self.spec.theme,
            status=ClaimStatus.CANDIDATE,
            evidence_ids=("R1",),
        )
        answer = AnswerSpec(
            research_spec=self.spec,
            summary=(candidate_fact,),
            verified_facts=(candidate_fact,),
            company_table=(),
            counter_evidence=(),
            gaps=(
                make_claim(
                    claim_id="gap-1",
                    text="缺少公告确认。",
                    claim_type="evidence_gap",
                    theme=self.spec.theme,
                    status=ClaimStatus.MISSING,
                ),
            ),
            triggers=(),
            next_actions=("核对公告。",),
            sources=(EvidenceRef("R1", "候选研报"),),
            system_notices=(),
        )

        report = evaluate_answer_spec(answer)

        self.assertFalse(report.passed)
        self.assertIn(
            "candidate_promoted_to_fact",
            {issue.code for issue in report.issues},
        )

    def test_quality_gate_detects_theme_contamination_and_term_leak(self) -> None:
        other_theme_claim = make_claim(
            claim_id="other-theme",
            text="graph_only 公司被误串入。",
            claim_type="company_mapping",
            theme="稳定币支付",
            status=ClaimStatus.CANDIDATE,
            evidence_ids=("G1",),
        )
        answer = AnswerSpec(
            research_spec=self.spec,
            summary=(other_theme_claim,),
            verified_facts=(),
            company_table=(),
            counter_evidence=(),
            gaps=(
                make_claim(
                    claim_id="gap-1",
                    text="缺少公司级证据。",
                    claim_type="evidence_gap",
                    theme=self.spec.theme,
                    status=ClaimStatus.MISSING,
                ),
            ),
            triggers=(),
            next_actions=("核对公告。",),
            sources=(EvidenceRef("G1", "图谱"),),
            system_notices=(),
        )

        report = evaluate_answer_spec(answer)
        codes = {issue.code for issue in report.issues}

        self.assertIn("theme_contamination", codes)
        self.assertNotIn("engineering_term_leak", codes)
        self.assertIn("仅有概念关联", humanize(other_theme_claim.text))


class PresenterAndLLMGateTests(unittest.TestCase):
    def _answer(self) -> AnswerSpec:
        spec = resolve_theme_research_spec("分析稳定币支付产业链")
        verified = make_claim(
            claim_id="market-1",
            text="涨幅与边际成交同步转强：涨幅2.61%，边际量18.28%。",
            claim_type="market_signal",
            theme=spec.theme,
            status=ClaimStatus.VERIFIED,
            evidence_tier="L4",
            evidence_ids=("S1",),
        )
        candidate = CompanyCandidate(
            company="示例科技",
            chain_stage="支付网关",
            directness="间接",
        )
        company_claim = make_claim(
            claim_id="company-1",
            text="示例科技仅有 graph_only 关联。",
            claim_type="company_mapping",
            theme=spec.theme,
            status=ClaimStatus.CANDIDATE,
            evidence_tier="graph_only",
            company="示例科技",
            evidence_ids=("G1",),
        )
        answer = AnswerSpec(
            research_spec=spec,
            summary=(
                make_claim(
                    claim_id="summary:definition",
                    text=f"{spec.theme}的研究范围是：{spec.definition}",
                    claim_type="summary",
                    theme=spec.theme,
                    status=ClaimStatus.INFERRED,
                ),
                make_claim(
                    claim_id="summary:market",
                    text="盘面关注度有所升温，但仍需公司级证据确认。",
                    claim_type="summary",
                    theme=spec.theme,
                    status=ClaimStatus.CANDIDATE,
                ),
                make_claim(
                    claim_id="summary:company-gap",
                    text="尚未形成可回查的公司级证据。",
                    claim_type="summary",
                    theme=spec.theme,
                    status=ClaimStatus.MISSING,
                ),
            ),
            verified_facts=(verified,),
            company_table=build_company_assessments(
                [candidate],
                [company_claim],
            ),
            counter_evidence=(),
            gaps=(
                make_claim(
                    claim_id="gap-1",
                    text="缺少公告或年报确认。",
                    claim_type="evidence_gap",
                    theme=spec.theme,
                    status=ClaimStatus.MISSING,
                ),
            ),
            triggers=(verified,),
            next_actions=("核对公告或年报。", "核对公告或年报。"),
            sources=(
                EvidenceRef("S1", "盘面快照"),
                EvidenceRef("G1", "公司概念图谱"),
            ),
            system_notices=(),
        )
        return finalize_answer_spec(answer)

    def test_presenter_uses_information_pyramid_and_hides_internal_terms(self) -> None:
        rendered = render_answer_spec(self._answer())

        self.assertIn("# 稳定币支付：研究结论", rendered)
        self.assertIn("## 核心判断", rendered)
        self.assertIn("**题材是什么：**", rendered)
        self.assertIn("## 题材怎么理解", rendered)
        self.assertIn("发行、储备、合规托管与清算基础设施", rendered)
        self.assertIn("## 为什么这样判断", rendered)
        self.assertIn(
            "这说明上涨同时得到新增成交支持，关注度并非只靠缩量拉升",
            rendered,
        )
        self.assertIn("## 公司证据", rendered)
        self.assertIn("## 反证与缺口", rendered)
        self.assertIn("## 下一步如何验证", rendered)
        self.assertIn("<details>", rendered)
        self.assertIn("候选资料，需公告或年报确认", rendered)
        self.assertNotIn("graph_only", rendered)
        self.assertEqual(rendered.count("核对公告或年报。"), 1)

    def test_presenter_humanizes_company_directness_and_verified_followup(self) -> None:
        spec = resolve_theme_research_spec("请个股深挖英维克的液冷业务")
        verified = make_claim(
            claim_id="company-verified",
            text="英维克公告披露液冷产品已应用于数据中心温控场景。",
            claim_type="company_evidence",
            theme=spec.theme,
            status=ClaimStatus.VERIFIED,
            evidence_tier="L3",
            company="英维克",
            evidence_ids=("R1",),
        )
        answer = AnswerSpec(
            research_spec=spec,
            summary=(verified,),
            verified_facts=(verified,),
            company_table=build_company_assessments(
                [
                    CompanyCandidate(
                        company="英维克",
                        chain_stage="温控设备与液冷系统",
                        directness="core",
                        requested_tier=CompanyTier.CORE,
                    ),
                    CompanyCandidate(
                        company="英维克关联方",
                        chain_stage="待核验环节",
                        directness="related",
                        requested_tier=CompanyTier.PERIPHERAL,
                    ),
                ],
                [verified],
            ),
            counter_evidence=(),
            gaps=(),
            triggers=(),
            next_actions=("核对收入贡献。",),
            sources=(EvidenceRef("R1", "公司公告", tier="L3"),),
            system_notices=(),
        )

        rendered = render_answer_spec(finalize_answer_spec(answer))

        self.assertIn("| 英维克 | 温控设备与液冷系统 | 直接 | 核心 |", rendered)
        self.assertIn("| 英维克关联方 | 待核验环节 | 相关 | 外围 |", rendered)
        self.assertNotIn("| related |", rendered)
        self.assertIn("已有公司级材料仍需持续复核业务贡献和兑现节奏", rendered)
        self.assertNotIn("公司级证据出现前", rendered)

    def test_presenter_separates_core_and_candidate_companies(self) -> None:
        spec = resolve_theme_research_spec("分析液冷产业链")
        verified = make_claim(
            claim_id="core-company",
            text="核心公司公告披露液冷订单。",
            claim_type="company_evidence",
            theme=spec.theme,
            status=ClaimStatus.VERIFIED,
            evidence_tier="L3",
            company="核心公司",
            evidence_ids=("L3-1",),
        )
        candidate = make_claim(
            claim_id="candidate-company",
            text="候选公司存在液冷概念映射。",
            claim_type="company_evidence",
            theme=spec.theme,
            status=ClaimStatus.CANDIDATE,
            evidence_tier="concept_graph",
            company="候选公司",
            evidence_ids=("G1",),
        )
        answer = AnswerSpec(
            research_spec=spec,
            summary=(verified,),
            verified_facts=(verified,),
            company_table=build_company_assessments(
                [
                    CompanyCandidate(
                        company="核心公司",
                        requested_tier=CompanyTier.CORE,
                    ),
                    CompanyCandidate(
                        company="候选公司",
                        requested_tier=CompanyTier.CORE,
                    ),
                ],
                [verified, candidate],
            ),
            counter_evidence=(),
            gaps=(
                make_claim(
                    claim_id="company-gap",
                    text="候选公司缺少公告确认。",
                    claim_type="evidence_gap",
                    theme=spec.theme,
                    status=ClaimStatus.MISSING,
                ),
            ),
            triggers=(),
            next_actions=("核对候选公司公告。",),
            sources=(
                EvidenceRef("L3-1", "公司公告", tier="L3"),
                EvidenceRef("G1", "概念图谱", tier="concept_graph"),
            ),
            system_notices=(),
        )

        rendered = render_answer_spec(finalize_answer_spec(answer))

        self.assertIn("### 核心公司", rendered)
        self.assertIn("### 候选与外围公司", rendered)
        self.assertLess(
            rendered.index("| 核心公司 |"),
            rendered.index("| 候选公司 |"),
        )

    def test_certainty_policy_is_claim_scoped_and_preserves_uncertainty(self) -> None:
        spec = resolve_theme_research_spec("分析液冷产业链")
        official = make_claim(
            claim_id="official",
            text="公司公告已确认液冷订单。",
            claim_type="company_evidence",
            theme=spec.theme,
            status=ClaimStatus.VERIFIED,
            evidence_tier="L3",
            company="示例科技",
            evidence_ids=("L3-1",),
        )
        weak = make_claim(
            claim_id="weak",
            text="板块未来必然上涨，但持续性仍不确定。",
            claim_type="market_signal",
            theme=spec.theme,
            status=ClaimStatus.VERIFIED,
            evidence_tier="market_data",
            evidence_ids=("D7",),
        )
        answer = AnswerSpec(
            research_spec=spec,
            summary=(weak,),
            verified_facts=(official, weak),
            company_table=build_company_assessments(
                [
                    CompanyCandidate(
                        company="示例科技",
                        requested_tier=CompanyTier.CORE,
                    )
                ],
                [official],
            ),
            counter_evidence=(),
            gaps=(
                make_claim(
                    claim_id="gap",
                    text="持续性仍不确定。",
                    claim_type="evidence_gap",
                    theme=spec.theme,
                    status=ClaimStatus.MISSING,
                ),
            ),
            triggers=(),
            next_actions=("继续核验成交持续性。",),
            sources=(
                EvidenceRef("L3-1", "公司公告", tier="L3"),
                EvidenceRef("D7", "市场数据", tier="market_data"),
            ),
            system_notices=(),
        )

        rendered = render_answer_spec(finalize_answer_spec(answer))

        self.assertIn("公司公告已确认液冷订单", rendered)
        self.assertNotIn("未来必然上涨", rendered)
        self.assertIn("持续性仍不确定", rendered)

    def test_presenter_formats_values_and_deduplicates_user_visible_sources(self) -> None:
        spec = resolve_theme_research_spec("分析人形机器人产业链")
        signal = make_claim(
            claim_id="market-noisy",
            text=(
                "信号 new_high_direction（61.35）：新高股63只，"
                "新高成交907.6599999999997亿，容量前三=True"
            ),
            claim_type="market_signal",
            theme=spec.theme,
            status=ClaimStatus.VERIFIED,
            evidence_tier="L4",
            evidence_ids=("S1",),
        )
        answer = AnswerSpec(
            research_spec=spec,
            summary=(signal,),
            verified_facts=(signal,),
            company_table=(),
            counter_evidence=(),
            gaps=(
                make_claim(
                    claim_id="gap-noisy",
                    text="缺少公司级公告。",
                    claim_type="evidence_gap",
                    theme=spec.theme,
                    status=ClaimStatus.MISSING,
                ),
            ),
            triggers=(signal,),
            next_actions=(
                "核验动作：核对客户和认证状态",
                "候选研究任务（人工 review）：做估值 sanity check",
            ),
            sources=(
                *tuple(
                    EvidenceRef(
                        f"R{index}",
                        "2026-07-01-theme-candidates.json · knowledge_evidence",
                    )
                    for index in range(1, 5)
                ),
                EvidenceRef(
                    "R5",
                    "knowledge-base · wiki/relations/concept_graph.json",
                    "iFinD baseline multi-source Provider",
                ),
            ),
            system_notices=(
                "未连接本地 DuckDB；本轮回退到截至 2026-07-01 的 snapshot/export。",
            ),
        )

        rendered = render_answer_spec(answer)

        self.assertIn("新高成交907.66亿", rendered)
        self.assertIn("且属于成交容量前三", rendered)
        self.assertIn("[R1–R4]", rendered)
        self.assertEqual(rendered.count("知识库候选资料"), 1)
        self.assertIn("人工复核", rendered)
        self.assertIn("合理性校验", rendered)
        self.assertIn("题材关系资料", rendered)
        self.assertIn("iFinD 基础资料 多来源交叉核验 数据提供方", rendered)
        for internal in (
            "new_high_direction",
            "knowledge_evidence",
            "DuckDB",
            "snapshot/export",
            "True",
            "907.6599999999997",
            "人工 review",
            "sanity check",
            "concept_graph",
            "baseline",
            "multi-source",
            "Provider",
        ):
            self.assertNotIn(internal, rendered)

    def test_base_finance_presenter_uses_five_element_conclusion(self) -> None:
        answer = replace(
            self._answer(),
            presentation_kind="base_finance",
            sources=(
                EvidenceRef(
                    "S1",
                    "fact_market_daily",
                    "DuckDB retrieval evidence_count=4",
                ),
            ),
        )

        rendered = render_answer_spec(answer)

        self.assertIn("**直接定性：**", rendered)
        self.assertIn("**最强证据：**", rendered)
        self.assertIn("**主要风险：**", rendered)
        self.assertIn("**条件边界：**", rendered)
        self.assertIn("**下一步验证：**", rendered)
        self.assertNotIn("fact_market_daily", rendered)
        self.assertNotIn("DuckDB", rendered)
        self.assertNotIn("retrieval", rendered)
        self.assertNotIn("evidence_count", rendered)

    def test_llm_gate_rejects_unbound_factual_content(self) -> None:
        issues = validate_llm_answer(
            "新增科技未来订单将达到 20 亿元。",
            self._answer(),
        )
        codes = {issue.code for issue in issues}

        self.assertEqual(codes, {"llm_missing_claim_binding"})

    def test_llm_gate_never_repairs_by_deleting_sentences(self) -> None:
        answer = (
            "## 核心判断\n"
            "当前证据只支持谨慎判断，已核验事实仍需持续跟踪。"
            "这是基于现有资料形成的边界判断，不代表未来结果。\n\n"
            "## 证据\n"
            "现有证据可以支持产业链位置判断，但不能支持订单规模外推。"
            "新增科技未来订单将达到 20 亿元。\n\n"
            "## 下一步\n"
            "继续核对公司公告、客户验证和收入传导，发现反证时下调结论。"
        )

        repaired = repair_llm_answer(answer, self._answer())

        self.assertIsNone(repaired)

    def test_llm_gate_validates_claim_and_atom_ids_then_renders_registry_claim(
        self,
    ) -> None:
        spec = self._answer()
        claim = spec.verified_facts[0]
        atom = next(
            atom
            for atom in evidence_atoms_from_answer_spec(spec)
            if atom.provenance["claim_id"] == claim.claim_id
        )
        answer = (
            "## 核心判断\n"
            f"- 模型不能借此注入任意新事实。"
            f"<!-- claim_id={claim.claim_id}; "
            f"evidence_atom_ids={atom.atom_id}; claim_type=fact -->"
        )

        self.assertEqual(validate_llm_answer(answer, spec), ())
        rendered = present_llm_answer(answer, spec)
        self.assertIn(claim.text, rendered)
        self.assertNotIn("模型不能借此注入", rendered)
        self.assertNotIn("claim_id=", rendered)

    def test_llm_gate_rejects_invalid_claim_id(self) -> None:
        spec = self._answer()
        answer = (
            "- 任意内容"
            "<!-- claim_id=claim-does-not-exist; "
            "evidence_atom_ids=atom-does-not-exist; claim_type=fact -->"
        )

        codes = {
            issue.code for issue in validate_llm_answer(answer, spec)
        }

        self.assertIn("llm_invalid_claim_id", codes)

    def test_llm_gate_rejects_invalid_evidence_atom_id(self) -> None:
        spec = self._answer()
        claim = spec.verified_facts[0]
        answer = (
            "- 任意内容"
            f"<!-- claim_id={claim.claim_id}; "
            "evidence_atom_ids=atom-does-not-exist; claim_type=fact -->"
        )

        codes = {
            issue.code for issue in validate_llm_answer(answer, spec)
        }

        self.assertIn("llm_invalid_evidence_atom_id", codes)

    def test_llm_gate_accepts_chinese_evidence_atom_delimiter(self) -> None:
        spec = self._answer()
        claim = spec.verified_facts[0]
        atom = next(
            atom
            for atom in evidence_atoms_from_answer_spec(spec)
            if atom.provenance["claim_id"] == claim.claim_id
        )
        answer = (
            "- 任意布局"
            f"<!-- claim_id={claim.claim_id}; "
            f"evidence_atom_ids={atom.atom_id}、{atom.atom_id}; "
            "claim_type=fact -->"
        )

        self.assertEqual(validate_llm_answer(answer, spec), ())


class AskIntegrationTests(unittest.TestCase):
    def test_answer_query_builds_answer_spec_before_presentation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = answer_query(
                AskOptions(
                    query="深研“稳定币支付”题材：给出定义、产业链、反证和核验动作。",
                    exports_dir=Path(tmp),
                    kb_wiki=Path(tmp),
                    use_modules=False,
                    use_wiki_rag=False,
                )
            )

        self.assertIsNotNone(result.answer_spec)
        assert result.answer_spec is not None
        self.assertEqual(
            result.answer_spec.research_spec.pack_id,
            "stablecoin_payment",
        )
        rendered = render_conversation_answer(result)
        self.assertIn("## 核心判断", rendered)
        self.assertIn("## 题材怎么理解", rendered)
        self.assertIn("## 为什么这样判断", rendered)
        self.assertIn("## 公司证据", rendered)
        self.assertNotIn("graph_only", rendered)
        self.assertNotIn("模块路由", rendered)


if __name__ == "__main__":
    unittest.main()
