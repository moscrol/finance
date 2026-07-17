"""Daily Agent 专用契约 + Grounded Composer 正式 Presenter 测试。

覆盖：typed EvidenceAtom 抽取、语义命题 claim（不含模板文案）、
数据新鲜度护栏、LLM 最终措辞保留、门禁失败降级。
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from intelligence.services import answer_model, ask, llm_refine
from intelligence.services.run_store import RunStore
from intelligence.workbench_skills.contracts import SkillExecutionContext
from intelligence.workbench_skills.daily_agent import (
    DailyAgentSkill,
    staleness_warning,
)
from intelligence.workbench_skills.daily_agent_contract import (
    DAILY_AGENT_PRESENTATION_KIND,
    build_daily_agent_answer_contract,
)


def _payload(date: str = "2026-07-10") -> dict:
    return {
        "date": date,
        "generated_at": f"{date}T20:00:00+08:00",
        "decision": {
            "old_logic_wakeup": [
                {
                    "matched_theme": "氢能源",
                    "priority_score": 194.57,
                    "strong_stocks": ["金宏气体"],
                    "logic_lifecycle": {
                        "生命周期阶段": "旧逻辑唤醒",
                        "阶段变化": "旧材料唤醒",
                    },
                    "research_judgment": {
                        "证据状态": "旧逻辑待验证",
                        "缺失证据层": ["L3 官方验证"],
                        "建议动作": "查公告和订单。",
                    },
                    "market_validation": {
                        "验证结论": "多信号共振，盘面给出较强 L4 验证（涨停 3 只，新高 2 只）。",
                        "盘面验证强度": "strong",
                        "当前盘面": {"涨停数": 3, "新高数": 2},
                        "边际变化": {"涨停数": 2},
                    },
                }
            ],
            "new_logic_candidate": [
                {
                    "matched_theme": "创新药",
                    "priority_score": 120.5,
                    "strong_stocks": ["泰格医药"],
                    "logic_lifecycle": {"生命周期阶段": "候选观察"},
                    "research_judgment": {
                        "证据状态": "候选",
                        "缺失证据层": ["L3 官方验证"],
                        "建议动作": "跟踪商业化订单。",
                    },
                    "market_validation": {
                        "验证结论": "多信号共振，盘面给出较强 L4 验证（涨停 5 只，新高 4 只）。",
                        "盘面验证强度": "strong",
                        "当前盘面": {"涨停数": 5, "新高数": 4},
                    },
                }
            ],
            "data_gap": [],
            "noise_or_unconfirmed": [
                {
                    "matched_theme": "跨境电商",
                    "priority_score": 30.0,
                    "logic_lifecycle": {"生命周期阶段": "退坡观察"},
                    "research_judgment": {"证据状态": "待确认"},
                    "market_validation": {
                        "验证结论": "有零星盘面信号，但扩散不足。",
                        "盘面验证强度": "weak",
                        "当前盘面": {"涨停数": 0, "新高数": 0},
                    },
                }
            ],
        },
        "research_queue": {
            "today_do_ima": [],
            "today_find_official_evidence": [
                {
                    "目标": "氢能源",
                    "理由": "旧逻辑需要官方事实确认。",
                    "优先级": 194.57,
                    "建议动作": "查公告和订单。",
                }
            ],
            "today_wait_market_validation": [],
            "today_downgrade_or_watch": [],
            "summary": {
                "today_do_ima": 0,
                "today_find_official_evidence": 1,
                "today_wait_market_validation": 0,
                "today_downgrade_or_watch": 0,
                "total": 1,
            },
        },
        "notes": ["只读研究入口，不自动交易。"],
    }


def _contract():
    contract = build_daily_agent_answer_contract(
        _payload(),
        source="market_feature_store/exports/2026-07-10-daily-agent.json",
        as_of="2026-07-10",
        warnings=[],
        retrieval_plan=("读取最新 canonical Daily Agent 研究队列",),
        output_contract=("先裁决研究优先级，再给证据缺口和可执行核验动作",),
    )
    assert contract is not None
    return contract


def _all_claim_texts(spec: answer_model.AnswerSpec) -> list[str]:
    return [
        claim.text
        for claim in (
            *spec.summary,
            *spec.verified_facts,
            *spec.counter_evidence,
            *spec.gaps,
            *spec.triggers,
        )
    ]


class TestDailyAgentContract:
    def test_builds_dedicated_presentation_kind(self) -> None:
        spec = _contract().answer_spec
        assert spec.presentation_kind == DAILY_AGENT_PRESENTATION_KIND
        assert spec.presentation_title == "研究雷达"

    def test_typed_evidence_atoms_keep_structured_fields(self) -> None:
        spec = _contract().answer_spec
        atoms = {
            (atom.provenance.get("field"), atom.metric): atom
            for atom in spec.research_evidence_atoms
            if atom.provenance.get("claim_id")
            == "daily-agent:theme:old_logic_wakeup:氢能源"
        }
        assert atoms[("priority", "priority_score")].value == 194.57
        assert atoms[("market:涨停数", "涨停数")].value == 3
        assert atoms[("market:新高数", "新高数")].value == 2
        assert atoms[("lifecycle", "lifecycle_stage")].value == "旧逻辑唤醒"
        assert atoms[("delta:涨停数", "涨停数边际变化")].value == 2
        assert atoms[("gap:1", "evidence_gap")].value == "L3 官方验证"
        assert atoms[("action", "action_code")].value == "查公告和订单。"
        assert (
            atoms[("stock:1", "strong_stock")].entity_id == "金宏气体"
        )
        for atom in atoms.values():
            assert atom.source_date == "2026-07-10"
            assert atom.evidence_tier == "canonical"

    def test_claims_are_semantic_propositions_not_template_prose(self) -> None:
        spec = _contract().answer_spec
        texts = _all_claim_texts(spec)
        assert not any("多信号共振" in text for text in texts)
        assert not any("有零星盘面信号" in text for text in texts)
        theme_claims = [
            claim for claim in spec.verified_facts if claim.theme == "氢能源"
        ]
        assert theme_claims
        assert "优先级=194.57" in theme_claims[0].text
        assert "涨停数=3" in theme_claims[0].text
        assert "生命周期=旧逻辑唤醒" in theme_claims[0].text

    def test_cross_theme_claims_are_distinct(self) -> None:
        spec = _contract().answer_spec
        theme_texts = [claim.text for claim in spec.verified_facts]
        assert len(theme_texts) == len(set(theme_texts))
        stripped = [
            text.split("：", 1)[-1].replace(text.split("：", 1)[0], "")
            for text in theme_texts
        ]
        assert len(stripped) == len(set(stripped))

    def test_weak_themes_enter_counter_evidence(self) -> None:
        spec = _contract().answer_spec
        assert any(
            claim.theme == "跨境电商"
            and claim.status == answer_model.ClaimStatus.CANDIDATE
            for claim in spec.counter_evidence
        )

    def test_deterministic_render_fallback_works(self) -> None:
        rendered = answer_model.render_answer_spec(_contract().answer_spec)
        assert "## 结论" in rendered
        assert "研究雷达" in rendered


class TestFreshnessGuard:
    def test_staleness_warning_when_newer_export_exists(
        self, tmp_path: Path
    ) -> None:
        exports = tmp_path / "exports"
        exports.mkdir()
        (exports / "2026-07-11-theme-candidates.json").write_text("{}")
        warning = staleness_warning(exports, "2026-07-10")
        assert warning is not None
        assert "2026-07-10" in warning
        assert "2026-07-11" in warning

    def test_no_warning_when_up_to_date(self, tmp_path: Path) -> None:
        exports = tmp_path / "exports"
        exports.mkdir()
        (exports / "2026-07-10-theme-candidates.json").write_text("{}")
        assert staleness_warning(exports, "2026-07-10") is None

    def test_skill_surfaces_staleness_warning(self, tmp_path: Path) -> None:
        exports = tmp_path / "market_feature_store" / "exports"
        exports.mkdir(parents=True)
        (exports / "2026-07-10-daily-agent.json").write_text(
            json.dumps(_payload(), ensure_ascii=False),
            encoding="utf-8",
        )
        (exports / "2026-07-11-theme-candidates.json").write_text("{}")
        store = RunStore(user_id="demo", root=tmp_path / "runs")
        run = store.create_run("今天研究雷达？", "daily")
        output = DailyAgentSkill().execute(
            SkillExecutionContext(
                query="今天研究雷达？",
                task_type="daily",
                user_id="demo",
                run_id=run.run_id,
                conversation_id="conversation-1",
                repo_root=tmp_path,
                run_store=store,
            )
        )
        assert any("落后于最新导出快照" in warning for warning in output.warnings)
        assert output.answer_contract is not None
        spec = output.answer_contract.answer_spec
        assert spec.presentation_kind == DAILY_AGENT_PRESENTATION_KIND
        assert any(
            "落后于最新导出快照" in claim.text for claim in spec.gaps
        )


def _result_with_spec() -> ask.AskResult:
    return ask.AskResult(
        query="今天的研究雷达怎么看？",
        trade_date="2026-07-10",
        matched_theme=None,
        candidate_tier=None,
        priority_score=None,
        answer_spec=_contract().answer_spec,
        prepared_synthesis_messages=[{"role": "user", "content": "占位"}],
    )


class TestGroundedPresenterPromotion:
    def _fake_llm(self, spec: answer_model.AnswerSpec):
        theme_claim_id = "daily-agent:theme:old_logic_wakeup:氢能源"
        atoms = answer_model.evidence_atoms_from_answer_spec(spec)
        atom_ids = [
            atom.atom_id
            for atom in atoms
            if atom.provenance.get("claim_id") == theme_claim_id
        ]
        brief = json.dumps(
            {
                "direct_answer": "旧逻辑重新活跃，但官方证据未跟上。",
                "core_tension": "盘面热度与证据层级不匹配。",
                "supports": [theme_claim_id, "daily-agent:summary"],
            },
            ensure_ascii=False,
        )
        composed = (
            "## 研究雷达\n"
            "氢能源更像旧逻辑重新被资金唤醒，盘面热度先行，"
            "但官方层面的证据还没有跟上，热度不等于逻辑被重定价。"
            f"<!-- claim_ids={theme_claim_id}; "
            f"evidence_atom_ids={','.join(atom_ids[:2])}; "
            "claim_type=fact -->\n"
            "在公告或订单落地之前，把它当作待验证的旧逻辑更稳妥。"
            f"<!-- claim_ids={theme_claim_id}; "
            f"evidence_atom_ids={atom_ids[0]}; "
            "claim_type=fact -->\n"
            "（非投资建议）"
        )
        judge = json.dumps(
            {"passed": True, "rejected_sentence_indexes": [], "issues": []},
            ensure_ascii=False,
        )
        answers = iter((brief, composed, judge))

        def fake_synthesize_messages(messages, **kwargs):
            return (
                llm_refine.SynthesisResult(
                    answer=next(answers),
                    provider="fake",
                    model="fake-model",
                ),
                "",
            )

        return fake_synthesize_messages

    def test_llm_wording_is_preserved_not_replaced_by_registry(
        self, monkeypatch
    ) -> None:
        result = _result_with_spec()
        spec = result.answer_spec
        assert spec is not None
        monkeypatch.setattr(
            llm_refine,
            "synthesize_messages",
            self._fake_llm(spec),
        )
        options = ask.AskOptions(
            query=result.query,
            daily_agent_grounded_presenter=True,
        )
        assert ask.promote_daily_agent_grounded_answer(options, result)
        assert result.synthesis is not None
        assert "更像旧逻辑重新被资金唤醒" in result.synthesis
        assert "claim_ids=" not in result.synthesis
        registry_texts = [
            claim.text for claim in spec.verified_facts
        ]
        assert not any(text in result.synthesis for text in registry_texts)
        shadow = result.grounded_composer_shadow
        assert shadow is not None
        assert shadow.status == "accepted"

    def test_falls_back_when_composer_unavailable(self, monkeypatch) -> None:
        result = _result_with_spec()

        def unavailable(messages, **kwargs):
            return None, "no_api_key"

        monkeypatch.setattr(llm_refine, "synthesize_messages", unavailable)
        options = ask.AskOptions(
            query=result.query,
            daily_agent_grounded_presenter=True,
        )
        assert not ask.promote_daily_agent_grounded_answer(options, result)
        assert result.synthesis is None
        assert any("已降级回结构化合成" in warning for warning in result.warnings)

    def test_flag_off_keeps_legacy_path(self, monkeypatch) -> None:
        result = _result_with_spec()

        def must_not_call(messages, **kwargs):
            raise AssertionError("flag off 不应调用 LLM")

        monkeypatch.setattr(llm_refine, "synthesize_messages", must_not_call)
        options = ask.AskOptions(
            query=result.query,
            daily_agent_grounded_presenter=False,
        )
        assert not ask.promote_daily_agent_grounded_answer(options, result)

    def test_brief_accepts_atom_ids_normalized_to_owner_claim(self) -> None:
        spec = _contract().answer_spec
        theme_claim_id = "daily-agent:theme:old_logic_wakeup:氢能源"
        atoms = answer_model.evidence_atoms_from_answer_spec(spec)
        atom_id = next(
            atom.atom_id
            for atom in atoms
            if atom.provenance.get("claim_id") == theme_claim_id
        )
        brief, issues = answer_model.parse_decision_brief(
            json.dumps(
                {
                    "direct_answer": "旧逻辑重新活跃。",
                    "core_tension": "热度与证据不匹配。",
                    "supports": [atom_id],
                },
                ensure_ascii=False,
            ),
            spec,
        )
        assert issues == ()
        assert brief is not None
        assert brief.supports == (theme_claim_id,)

    def test_repair_drops_unbound_lines_instead_of_failing(self) -> None:
        spec = _contract().answer_spec
        theme_claim_id = "daily-agent:theme:old_logic_wakeup:氢能源"
        atoms = answer_model.evidence_atoms_from_answer_spec(spec)
        atom_ids = [
            atom.atom_id
            for atom in atoms
            if atom.provenance.get("claim_id") == theme_claim_id
        ]
        answer = (
            "凭空多出的一句没有任何绑定。\n"
            "氢能源旧逻辑被资金重新唤醒。"
            f"<!-- claim_ids={theme_claim_id}; "
            f"evidence_atom_ids={atom_ids[0]}; claim_type=fact -->"
        )
        repaired = answer_model.repair_grounded_composer_answer(answer, spec)
        assert repaired is not None
        assert "凭空多出的一句" not in repaired
        assert "氢能源" in repaired

    def test_brief_filters_hallucinated_ids_keeps_valid_supports(self) -> None:
        spec = _contract().answer_spec
        theme_claim_id = "daily-agent:theme:old_logic_wakeup:氢能源"
        brief, issues = answer_model.parse_decision_brief(
            json.dumps(
                {
                    "direct_answer": "旧逻辑重新活跃。",
                    "core_tension": "热度与证据不匹配。",
                    "supports": [theme_claim_id, "daily-agent:不存在:gap:9"],
                    "unknowns": ["daily-agent:也不存在"],
                },
                ensure_ascii=False,
            ),
            spec,
        )
        assert issues == ()
        assert brief is not None
        assert brief.supports == (theme_claim_id,)
        assert brief.unknowns == ()

    def test_repair_drop_invalid_keeps_llm_wording_no_template_backfill(
        self,
    ) -> None:
        spec = _contract().answer_spec
        theme_claim_id = "daily-agent:theme:old_logic_wakeup:氢能源"
        atoms = answer_model.evidence_atoms_from_answer_spec(spec)
        atom_id = next(
            atom.atom_id
            for atom in atoms
            if atom.provenance.get("claim_id") == theme_claim_id
        )
        good = (
            "氢能源旧逻辑被资金重新唤醒，热度先于证据。"
            f"<!-- claim_ids={theme_claim_id}; "
            f"evidence_atom_ids={atom_id}; claim_type=fact -->"
        )
        bad = (
            "凭空断言涨停 99 只创历史纪录。"
            f"<!-- claim_ids={theme_claim_id}; "
            f"evidence_atom_ids={atom_id}; claim_type=fact -->"
        )
        repaired = answer_model.repair_grounded_composer_answer(
            f"{good}\n{bad}",
            spec,
            drop_invalid=True,
        )
        assert repaired is not None
        assert "热度先于证据" in repaired
        assert "99 只" not in repaired
        registry_texts = [claim.text for claim in spec.verified_facts]
        assert not any(text in repaired for text in registry_texts)

    def test_repair_drop_invalid_fails_when_nothing_survives(self) -> None:
        spec = _contract().answer_spec
        theme_claim_id = "daily-agent:theme:old_logic_wakeup:氢能源"
        bad = (
            "凭空断言涨停 99 只。"
            f"<!-- claim_ids={theme_claim_id}; "
            "evidence_atom_ids=无; claim_type=fact -->"
        )
        assert (
            answer_model.repair_grounded_composer_answer(
                bad,
                spec,
                drop_invalid=True,
            )
            is None
        )

    def test_strip_empty_sections_and_min_body_guard(self) -> None:
        stripped = ask._strip_empty_grounded_sections(
            "# 标题\n\n## 空段落\n\n\n## 有内容\n正文一句。\n（非投资建议）"
        )
        assert "空段落" not in stripped
        assert "有内容" in stripped
        assert "\n\n\n" not in stripped
        assert ask._grounded_body_line_count(stripped) == 1

    def test_non_daily_agent_spec_is_untouched(self) -> None:
        result = _result_with_spec()
        spec = result.answer_spec
        assert spec is not None
        result.answer_spec = replace(
            spec, presentation_kind="base_finance"
        )
        options = ask.AskOptions(
            query=result.query,
            daily_agent_grounded_presenter=True,
        )
        assert not ask.promote_daily_agent_grounded_answer(options, result)
