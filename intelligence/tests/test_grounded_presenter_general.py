"""通用 Grounded Presenter（非 daily-agent compose 回答保留 LLM 措辞）测试。

覆盖：普通题材 AnswerSpec 走 Grounded Composer 链路后 synthesis 保留 LLM
自然语言（不再被 registry 原文替换）、开关关闭/市场回顾/LLM 不可用时的降级。
"""

from __future__ import annotations

import json

from intelligence.services import answer_model, ask, ask_synthesis, llm_refine
from intelligence.services.answer_model import (
    AnswerSpec,
    ClaimStatus,
    EvidenceRef,
    make_claim,
    resolve_theme_research_spec,
)


def _theme_spec() -> AnswerSpec:
    spec = resolve_theme_research_spec("分析液冷服务器产业链")
    verified = make_claim(
        claim_id="market-1",
        text="涨幅与边际成交同步转强：涨幅2.61%，边际量18.28%。",
        claim_type="market_signal",
        theme=spec.theme,
        status=ClaimStatus.VERIFIED,
        evidence_tier="L4",
        evidence_ids=("S1",),
    )
    summary = make_claim(
        claim_id="summary:market",
        text="盘面关注度升温，但仍需公司级证据确认。",
        claim_type="summary",
        theme=spec.theme,
        status=ClaimStatus.INFERRED,
        evidence_ids=("S1",),
    )
    return AnswerSpec(
        research_spec=spec,
        summary=(summary,),
        verified_facts=(verified,),
        company_table=(),
        counter_evidence=(),
        gaps=(),
        triggers=(),
        next_actions=("核对公告。",),
        sources=(EvidenceRef("S1", "盘面快照"),),
        system_notices=(),
    )


def _result_with_spec() -> ask.AskResult:
    return ask.AskResult(
        query="液冷服务器现在怎么看？",
        trade_date="2026-07-10",
        matched_theme="液冷服务器",
        candidate_tier=None,
        priority_score=None,
        answer_spec=_theme_spec(),
        prepared_synthesis_messages=[{"role": "user", "content": "占位"}],
    )


def _fake_llm(spec: AnswerSpec):
    atoms = answer_model.evidence_atoms_from_answer_spec(spec)
    atom_ids = [
        atom.atom_id
        for atom in atoms
        if atom.provenance.get("claim_id") == "market-1"
    ]
    brief = json.dumps(
        {
            "direct_answer": "盘面已给出量价共振，但公司级证据未落地。",
            "core_tension": "盘面热度与证据硬度不匹配。",
            "supports": ["market-1", "summary:market"],
        },
        ensure_ascii=False,
    )
    composed = (
        "## 液冷服务器\n"
        "资金正在用真金白银投票，量价同步转强说明这不是零星脉冲。"
        f"<!-- claim_ids=market-1; "
        f"evidence_atom_ids={','.join(atom_ids[:2])}; "
        "claim_type=fact -->\n"
        "在公司级证据落地之前，把热度当作待验证信号更稳妥。"
        f"<!-- claim_ids=market-1; "
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


class TestGeneralGroundedPresenter:
    def test_llm_wording_preserved_for_theme_answer(self, monkeypatch) -> None:
        result = _result_with_spec()
        spec = result.answer_spec
        assert spec is not None
        monkeypatch.setattr(
            llm_refine,
            "synthesize_messages",
            _fake_llm(spec),
        )
        options = ask.AskOptions(
            query=result.query,
            grounded_presenter=True,
        )
        assert ask.promote_grounded_answer(options, result)
        assert result.synthesis is not None
        assert "资金正在用真金白银投票" in result.synthesis
        assert "claim_ids=" not in result.synthesis
        assert not any(
            claim.text in result.synthesis for claim in spec.verified_facts
        )
        shadow = result.grounded_composer_shadow
        assert shadow is not None
        assert shadow.status == "accepted"

    def test_flag_off_keeps_legacy_path(self, monkeypatch) -> None:
        result = _result_with_spec()

        def must_not_call(messages, **kwargs):
            raise AssertionError("flag off 不应调用 LLM")

        monkeypatch.setattr(llm_refine, "synthesize_messages", must_not_call)
        options = ask.AskOptions(
            query=result.query,
            grounded_presenter=False,
        )
        assert not ask.promote_grounded_answer(options, result)
        assert result.synthesis is None
        assert not result.warnings

    def test_market_review_uses_grounded_presenter(self, monkeypatch) -> None:
        result = _result_with_spec()
        result.prepared_synthesis_is_market_review = True

        def accepted(prepared, **kwargs):
            del kwargs
            prepared.result.grounded_composer_shadow = (
                answer_model.GroundedComposerShadow(
                    status="accepted",
                    presented_answer=(
                        "## 结论\n"
                        "市场证据只支持谨慎判断。\n"
                        "下一交易日继续核验量价结构。"
                    ),
                    provider="judge",
                    model="judge-model",
                )
            )
            return prepared.result

        monkeypatch.setattr(
            ask_synthesis,
            "synthesize_shadow_grounded_answer",
            accepted,
        )
        options = ask.AskOptions(
            query=result.query,
            grounded_presenter=True,
        )
        assert ask.promote_grounded_answer(options, result)
        assert result.synthesis is not None
        assert "谨慎判断" in result.synthesis
        assert result.synthesis_diagnostic.state == "accepted"
        assert result.synthesis_diagnostic.reason_code == "validated"

    def test_falls_back_with_warning_when_llm_unavailable(
        self, monkeypatch
    ) -> None:
        result = _result_with_spec()

        def unavailable(messages, **kwargs):
            return None, "no_api_key"

        monkeypatch.setattr(llm_refine, "synthesize_messages", unavailable)
        options = ask.AskOptions(
            query=result.query,
            grounded_presenter=True,
        )
        assert ask.promote_grounded_answer(options, result)
        assert result.grounded_fallback_used
        assert result.synthesis_diagnostic.state == "rejected"
        assert (
            result.synthesis_diagnostic.reason_code
            == "grounded_required_fallback"
        )
        assert result.synthesis is not None
        assert "核心判断" in result.synthesis
        assert any(
            "Grounded Presenter" in warning and "已降级为可核验短答" in warning
            for warning in result.warnings
        )

    def test_grounded_failure_never_enters_legacy_stream(
        self, monkeypatch
    ) -> None:
        result = _result_with_spec()

        monkeypatch.setattr(
            llm_refine,
            "synthesize_messages",
            lambda _messages, **_kwargs: (None, "no_api_key"),
        )

        def legacy_stream_must_not_run(*_args, **_kwargs):
            raise AssertionError("grounded failure 不得绕回旧 marker 合成")

        monkeypatch.setattr(
            llm_refine,
            "synthesize_messages_stream",
            legacy_stream_must_not_run,
        )
        options = ask.AskOptions(
            query=result.query,
            grounded_presenter=True,
        )

        ask.synthesize_prepared_answer(
            ask.PreparedAnswer(options=options, result=result)
        )

        assert result.grounded_fallback_used
        assert result.synthesis is not None
        assert "盘面关注度升温" in result.synthesis
