"""Grounded 链三段（brief/composer/judge）必须各留一条可观测记录。

为什么值得单独一个文件：2026-08-02 那批验收里 15 次降级的 warning 全都是同一句
「未通过门禁或不可用（LLM 合成超过共享截止时间）」——三段共用一个 deadline，任何
一段超时都产出**字面相同**的字符串，产物里既没有段名也没有耗时。于是「哪一段吃掉
了预算」只能靠读代码推，而推错的代价是去优化一段根本没坏的链路。

这里钉住的不变量只有两条，但缺了任何一条上面那件事就会重演：

1. **每段都留痕，包括没跑到的那段**——判定「composer 挂了所以 judge 从未开始」
   靠的是 judge 记录**不存在**，而不是靠猜。
2. **入口剩余预算 ``remaining_ms_at_entry`` 必须记**——它把「合成质量不行」和
   「合成压根没时间跑」分开。两者的修复方向相反：前者改 prompt/门禁，后者改预算。
"""

from __future__ import annotations

import json

import pytest

from intelligence.services import answer_model, ask, ask_synthesis, llm_refine
from intelligence.services.answer_model import (
    AnswerSpec,
    ClaimStatus,
    EvidenceRef,
    make_claim,
    resolve_theme_research_spec,
)

_DEADLINE_REASON = "LLM 合成超过共享截止时间，已降级为模板"


def _spec() -> AnswerSpec:
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


def _result() -> ask.AskResult:
    return ask.AskResult(
        query="液冷服务器现在怎么看？",
        trade_date="2026-07-10",
        matched_theme="液冷服务器",
        candidate_tier=None,
        priority_score=None,
        answer_spec=_spec(),
        prepared_synthesis_messages=[{"role": "user", "content": "占位"}],
    )


def _chain_answers(spec: AnswerSpec) -> list[str]:
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
    return [brief, composed, judge]


def _fake_chain(spec: AnswerSpec, *, fail_at: int | None = None):
    """按顺序返回 brief/composer/judge；``fail_at`` 指定第几次调用超时（0 基）。"""

    answers = _chain_answers(spec)
    calls = {"n": 0}

    def fake_synthesize_messages(messages, **kwargs):
        index = calls["n"]
        calls["n"] += 1
        if fail_at is not None and index == fail_at:
            return None, _DEADLINE_REASON
        return (
            llm_refine.SynthesisResult(
                answer=answers[index],
                provider="fake",
                model="fake-model",
            ),
            "",
        )

    return fake_synthesize_messages


def _run_shadow(monkeypatch, *, fail_at: int | None = None) -> ask.AskResult:
    result = _result()
    spec = result.answer_spec
    assert spec is not None
    monkeypatch.setattr(
        llm_refine,
        "synthesize_messages",
        _fake_chain(spec, fail_at=fail_at),
    )
    options = ask.AskOptions(
        query=result.query,
        shadow_grounded_composer=True,
    )
    ask_synthesis.synthesize_shadow_grounded_answer(
        ask.PreparedAnswer(options=options, result=result),
        repair_drop_invalid=True,
    )
    return result


class TestPhasesAreRecorded:
    def test_full_chain_records_three_phases_in_order(self, monkeypatch) -> None:
        result = _run_shadow(monkeypatch)

        assert [phase.name for phase in result.synthesis_phases] == [
            "brief",
            "composer",
            "judge",
        ]
        assert all(
            phase.status == "ok" for phase in result.synthesis_phases
        )

    def test_entry_budget_is_recorded_for_every_phase(self, monkeypatch) -> None:
        """入口剩余预算是区分「写得差」和「没时间写」的唯一依据。"""
        result = _run_shadow(monkeypatch)

        for phase in result.synthesis_phases:
            assert phase.remaining_ms_at_entry > 0
            assert phase.timeout_s > 0
            assert phase.elapsed_ms >= 0

    def test_budget_shrinks_monotonically_down_the_chain(
        self, monkeypatch
    ) -> None:
        """三段共用一个 deadline，后一段的入口余额不可能比前一段多。

        这条不是凑数：它是「共享预算」这个设计事实在遥测上的投影，一旦哪天有人
        给某段新建了 Deadline（历史上出过一次，见 ``_shadow_deadline`` 的注释），
        这条会先红。
        """
        result = _run_shadow(monkeypatch)

        budgets = [
            phase.remaining_ms_at_entry for phase in result.synthesis_phases
        ]
        assert budgets == sorted(budgets, reverse=True)


class TestFailingPhaseIsIdentifiable:
    """这一组就是 2026-08-02 分诊卡住的地方——当时只能标 residual uncertainty。"""

    @pytest.mark.parametrize(
        ("fail_at", "expected_failed", "expected_names"),
        [
            (0, "brief", ["brief"]),
            (1, "composer", ["brief", "composer"]),
            (2, "judge", ["brief", "composer", "judge"]),
        ],
    )
    def test_deadline_failure_names_the_phase(
        self,
        monkeypatch,
        fail_at: int,
        expected_failed: str,
        expected_names: list[str],
    ) -> None:
        result = _run_shadow(monkeypatch, fail_at=fail_at)

        phases = result.synthesis_phases
        # 没跑到的段**不留记录**——「judge 从未开始」要能被观察，而不是被推断。
        assert [phase.name for phase in phases] == expected_names
        failed = [phase for phase in phases if phase.status == "failed"]
        assert [phase.name for phase in failed] == [expected_failed]

    def test_failure_reason_is_normalized_not_raw(self, monkeypatch) -> None:
        """存归一码而不是原始串：原始串带 provider 措辞，不该进公开 trace。"""
        result = _run_shadow(monkeypatch, fail_at=1)

        failed = [
            phase for phase in result.synthesis_phases if phase.status == "failed"
        ]
        assert len(failed) == 1
        assert failed[0].reason_code == llm_refine.stable_llm_fallback_reason(
            _DEADLINE_REASON
        )
        assert "降级为模板" not in failed[0].reason_code

    def test_starvation_is_distinguishable_from_a_gate_failure(
        self, monkeypatch
    ) -> None:
        """同样是 composer 没产出，超时和门禁拒稿必须在遥测上分得开。"""
        starved = _run_shadow(monkeypatch, fail_at=1)
        composer = [
            phase
            for phase in starved.synthesis_phases
            if phase.name == "composer"
        ][0]

        assert composer.status == "failed"
        assert composer.reason_code  # 有归一码 = 链路层失败
        assert composer.remaining_ms_at_entry >= 0  # 且能看到当时还剩多少


class TestDiagnosticCarriesPhases:
    def test_promote_copies_phases_and_shadow_status(self, monkeypatch) -> None:
        result = _result()
        spec = result.answer_spec
        assert spec is not None
        monkeypatch.setattr(
            llm_refine,
            "synthesize_messages",
            _fake_chain(spec),
        )
        options = ask.AskOptions(
            query=result.query,
            grounded_presenter=True,
        )

        assert ask.promote_grounded_answer(options, result)

        diagnostic = result.synthesis_diagnostic
        assert diagnostic.shadow_status == "accepted"
        assert [phase.name for phase in diagnostic.phases] == [
            "brief",
            "composer",
            "judge",
        ]


class TestPublicTraceWhitelist:
    """遥测要能出去，但这条通道以前只走过三个计数，别让它变成新的泄漏面。"""

    @staticmethod
    def _step(diagnostic: dict) -> dict:
        return {
            "name": "answer_synthesis",
            "output_summary": json.dumps(
                {"diagnostic": diagnostic}, ensure_ascii=False
            ),
        }

    @staticmethod
    def _base_diagnostic(**extra) -> dict:
        base = {
            "state": "rejected",
            "reason_code": "grounded_required_fallback",
            "detail": "deterministic fallback used",
            "prepared_message_count": 2,
            "candidate_claim_count": 17,
            "bound_claim_count": 17,
        }
        base.update(extra)
        return base

    def test_valid_phases_pass_through(self) -> None:
        from intelligence.api import app

        public = app._public_synthesis_diagnostic(
            self._step(
                self._base_diagnostic(
                    shadow_status="composer_unavailable",
                    phases=[
                        {
                            "name": "brief",
                            "status": "ok",
                            "remaining_ms_at_entry": 20000,
                            "timeout_s": 5,
                            "elapsed_ms": 4200,
                            "reason_code": "",
                        },
                        {
                            "name": "composer",
                            "status": "failed",
                            "remaining_ms_at_entry": 15800,
                            "timeout_s": 7,
                            "elapsed_ms": 7000,
                            "reason_code": "deadline_exhausted_local",
                        },
                    ],
                )
            )
        )

        assert public is not None
        assert public["shadow_status"] == "composer_unavailable"
        assert [phase["name"] for phase in public["phases"]] == [
            "brief",
            "composer",
        ]
        assert public["phases"][1]["remaining_ms_at_entry"] == 15800

    @pytest.mark.parametrize(
        "bad_phase",
        [
            pytest.param({"name": "../etc", "status": "ok"}, id="bad_name"),
            pytest.param(
                {"name": "brief", "status": "exploded"}, id="bad_status"
            ),
            pytest.param(
                {
                    "name": "brief",
                    "status": "ok",
                    "remaining_ms_at_entry": -1,
                    "timeout_s": 5,
                    "elapsed_ms": 1,
                },
                id="negative_budget",
            ),
            pytest.param(
                {
                    "name": "brief",
                    "status": "ok",
                    "remaining_ms_at_entry": 1,
                    "timeout_s": 5,
                    "elapsed_ms": "很久",
                },
                id="non_int_elapsed",
            ),
        ],
    )
    def test_malformed_phase_is_dropped(self, bad_phase: dict) -> None:
        from intelligence.api import app

        public = app._public_synthesis_diagnostic(
            self._step(self._base_diagnostic(phases=[bad_phase]))
        )

        assert public is not None
        assert "phases" not in public

    def test_free_text_reason_cannot_ride_along(self) -> None:
        """reason_code 是枚举位，不是第二条正文通道。"""
        from intelligence.api import app

        public = app._public_synthesis_diagnostic(
            self._step(
                self._base_diagnostic(
                    phases=[
                        {
                            "name": "judge",
                            "status": "failed",
                            "remaining_ms_at_entry": 900,
                            "timeout_s": 1,
                            "elapsed_ms": 900,
                            "reason_code": "provider said: /Users/a77/secret",
                        }
                    ]
                )
            )
        )

        assert public is not None
        assert "reason_code" not in public["phases"][0]

    def test_phase_count_is_bounded(self) -> None:
        from intelligence.api import app

        public = app._public_synthesis_diagnostic(
            self._step(
                self._base_diagnostic(
                    phases=[
                        {
                            "name": "brief",
                            "status": "ok",
                            "remaining_ms_at_entry": 1,
                            "timeout_s": 1,
                            "elapsed_ms": 1,
                        }
                    ]
                    * 40
                )
            )
        )

        assert public is not None
        assert len(public["phases"]) <= 8


def test_acceptance_capture_keeps_phase_fields() -> None:
    """验收产物必须留下这两个字段，否则埋点到不了分诊现场。"""
    from intelligence.eval import acceptance

    assert "phases" in acceptance._SYNTHESIS_DIAGNOSTIC_FIELDS
    assert "shadow_status" in acceptance._SYNTHESIS_DIAGNOSTIC_FIELDS
