"""校验器的锚点日期与 composer 截断兜底（2026-10-05 Pi vs 8792 对照）。

现场：问 2026-07-22 的高标晋级，固定流程喂进来的是 09-30 的盘面。模型如实写了
「数据截至 2026-09-30，并不是 2026-07-22」，校验器却把题目自带的 2026-07-22 判成
「证据外日期」整句删掉——16 个 error 里 10 个是它。发布稿于是只剩 09-30 的数字、
没有任何日期标注，挂在 07-22 的问题下面。

这里钉两件事：用户问题里的日期不算模型编造；但事实句单独把它挂在别的交易日的
数字上，仍然要拦。
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from intelligence.services import ask, ask_synthesis, llm_refine
from intelligence.services.answer_model import (
    AnswerSpec,
    ClaimStatus,
    EvidenceRef,
    anchor_dates_for,
    evidence_atoms_from_answer_spec,
    make_claim,
    repair_grounded_composer_answer,
    resolve_answer_profile,
    trim_to_last_complete_grounded_line,
    validate_grounded_composer_answer,
)
from intelligence.services.llm_refine import LLMProvider

QUESTION = "2026-07-22 高标股的晋级情况如何，有没有出现空档"


def _spec(*, as_of: str | None = None) -> AnswerSpec:
    research_spec = resolve_answer_profile("市场复盘", profile="causal")
    if as_of is not None:
        research_spec = replace(research_spec, as_of=as_of)
    return AnswerSpec(
        research_spec=research_spec,
        summary=(),
        verified_facts=(
            make_claim(
                claim_id="base:fact:1",
                text="市场数据截至：2026-09-30。该日期是本轮整体盘面日期。",
                claim_type="supporting_fact",
                theme="市场复盘",
                status=ClaimStatus.VERIFIED,
                evidence_ids=("BASE",),
            ),
            make_claim(
                claim_id="base:fact:3",
                text="全市场成交额：14377.22 亿元；涨停 52 家。",
                claim_type="supporting_fact",
                theme="市场复盘",
                status=ClaimStatus.VERIFIED,
                evidence_ids=("BASE",),
            ),
        ),
        company_table=(),
        counter_evidence=(),
        gaps=(
            make_claim(
                claim_id="base:gap:1",
                text="本地资料未命中所问交易日的连板梯队数据。",
                claim_type="gap",
                theme="市场复盘",
                status=ClaimStatus.MISSING,
            ),
        ),
        triggers=(),
        next_actions=(),
        sources=(EvidenceRef("BASE", "本地行情"),),
        system_notices=(),
        presentation_profile="causal",
    )


def _atom(spec: AnswerSpec, claim_id: str) -> str:
    return next(
        atom.atom_id
        for atom in evidence_atoms_from_answer_spec(spec)
        if atom.provenance.get("claim_id") == claim_id
    )


def _gap(text: str) -> str:
    return f"{text}<!-- claim_ids=base:gap:1; evidence_atom_ids=; claim_type=gap -->"


def _fact(spec: AnswerSpec, claim_id: str, text: str) -> str:
    return (
        f"{text}<!-- claim_ids={claim_id}; "
        f"evidence_atom_ids={_atom(spec, claim_id)}; claim_type=fact -->"
    )


def _codes(answer: str, spec: AnswerSpec, question: str = "") -> dict[str, str]:
    return {
        issue.code: issue.message
        for issue in validate_grounded_composer_answer(answer, spec, question=question)
        if issue.severity == "error"
    }


class TestAnchorDates:
    def test_full_date_in_question(self) -> None:
        assert anchor_dates_for(QUESTION) == ("2026-07-22",)

    def test_month_day_inherits_the_only_year(self) -> None:
        assert anchor_dates_for(
            "2026-07-16 到 07-22 这几天，成交量和涨停家数的变化说明了什么"
        ) == ("2026-07-16", "2026-07-22")
        assert anchor_dates_for("2026年7月22日和7月23日的涨停") == (
            "2026-07-22",
            "2026-07-23",
        )

    def test_standing_date_comes_from_the_answer_spec(self) -> None:
        assert anchor_dates_for("复盘下今天A股整体情况", _spec(as_of="2026-07-23")) == (
            "2026-07-23",
        )

    def test_partial_dates_are_not_guessed_across_two_years(self) -> None:
        assert anchor_dates_for("2025-12-31 到 2026-01-05 之间 01-02 那天") == (
            "2025-12-31",
            "2026-01-05",
        )

    def test_impossible_dates_are_ignored(self) -> None:
        assert anchor_dates_for("2026-13-01 怎么样") == ()

    def test_decimals_in_the_question_are_not_month_days(self) -> None:
        """「10.27%」若被认成 10 月 27 日，正文里同一个数字就会借锚点逃过数字检查。"""

        assert anchor_dates_for("2026-07-22 成交额环比 10.27% 说明什么，12/31 前能修复吗") == (
            "2026-07-22",
            "2026-12-31",
        )


class TestValidatorAnchorDates:
    def test_old_behaviour_is_unchanged_without_question(self) -> None:
        spec = _spec()
        answer = _gap("本地资料未命中 2026-07-22 当日的连板梯队数据。")

        assert "grounded_composer_added_date" in _codes(answer, spec)

    def test_gap_sentence_may_name_the_question_date(self) -> None:
        spec = _spec()
        answer = _gap(
            "本地资料未命中 2026-07-22 当日的连板梯队数据，7 月 22 日是否出现空档无法判断，"
            "7 月下旬的梯队也未覆盖。"
        )

        codes = _codes(answer, spec, QUESTION)
        assert "grounded_composer_added_date" not in codes
        assert "grounded_composer_added_number" not in codes

    def test_fact_sentence_contrasting_its_own_date_with_the_question_date(self) -> None:
        spec = _spec()
        answer = _fact(
            spec,
            "base:fact:1",
            "本轮整体盘面数据截至 2026-09-30，并不是 2026-07-22，不能当作所问日期的行情。",
        )

        assert "grounded_composer_added_date" in _codes(answer, spec)
        codes = _codes(answer, spec, QUESTION)
        assert "grounded_composer_added_date" not in codes
        assert "grounded_composer_added_number" not in codes

    def test_fact_sentence_cannot_relabel_other_day_numbers_as_the_question_date(
        self,
    ) -> None:
        """09-30 的成交额被说成 07-22 的：这正是校验器该拦的张冠李戴。"""

        spec = _spec()
        answer = _fact(spec, "base:fact:3", "2026-07-22 全市场成交额 14377.22 亿元。")

        codes = _codes(answer, spec, QUESTION)
        assert "2026-07-22" in codes["grounded_composer_added_date"]

    def test_anchor_scrub_does_not_swallow_ordinary_numbers(self) -> None:
        spec = _spec()
        answer = _gap("本地资料未命中 2026-07-22 的连板梯队数据，最高 7 板的说法无从核实。")

        codes = _codes(answer, spec, QUESTION)
        assert "grounded_composer_added_date" not in codes
        message = codes["grounded_composer_added_number"]
        assert "7" in message
        assert "22" not in message

    def test_question_decimals_cannot_launder_unsupported_numbers(self) -> None:
        spec = _spec()
        answer = _gap("本地资料未命中 2026-07-22 的连板梯队数据，成交额环比 10.27% 无从核实。")

        codes = _codes(answer, spec, "2026-07-22 成交额环比 10.27% 说明什么")
        assert "10.27" in codes["grounded_composer_added_number"]

    def test_heading_with_the_question_date_is_advisory(self) -> None:
        spec = _spec()
        answer = "## 2026-07-22 连板梯队：缺口说明\n" + _gap("本地资料未命中所问交易日的连板梯队数据。")

        def heading_severity(question: str) -> str:
            return next(
                issue.severity
                for issue in validate_grounded_composer_answer(answer, spec, question=question)
                if issue.code == "grounded_composer_unverified_heading"
            )

        assert heading_severity("") == "error"
        assert heading_severity(QUESTION) == "warning"


def test_repair_keeps_the_date_disclosure_and_drops_the_relabelled_fact() -> None:
    spec = _spec()
    disclosure = "本轮整体盘面数据截至 2026-09-30，并不是 2026-07-22，不能当作所问日期的行情。"
    relabelled = "2026-07-22 全市场成交额 14377.22 亿元。"
    answer = "\n".join(
        (
            _fact(spec, "base:fact:1", disclosure),
            _fact(spec, "base:fact:3", relabelled),
            _gap("本地资料未命中 2026-07-22 当日的连板梯队数据。"),
        )
    )

    repaired = repair_grounded_composer_answer(
        answer, spec, drop_invalid=True, question=QUESTION
    )

    assert repaired is not None
    assert disclosure in repaired
    assert relabelled not in repaired
    assert "本地资料未命中 2026-07-22 当日的连板梯队数据。" in repaired

    without_question = repair_grounded_composer_answer(answer, spec, drop_invalid=True)
    assert without_question is None or disclosure not in without_question


class TestTruncatedComposerDraft:
    def test_keeps_complete_sentences_and_drops_the_cut_tail(self) -> None:
        complete = "句一。<!-- claim_ids=a; evidence_atom_ids=; claim_type=inference -->"
        draft = f"## 标题\n{complete}\n句二写到一半<!-- claim_ids=b; evidence_ato"

        assert trim_to_last_complete_grounded_line(draft) == f"## 标题\n{complete}"

    def test_returns_empty_when_nothing_complete_survives(self) -> None:
        assert trim_to_last_complete_grounded_line("只有半句，没有标记") == ""


def _provider() -> LLMProvider:
    return LLMProvider(
        name="zhipu",
        api_key="sk-test",
        base_url="https://example.invalid/v4",
        model="glm-5.3-flash",
    )


def test_synthesize_messages_returns_truncated_text_only_when_allowed(monkeypatch) -> None:
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_args, **_kwargs: _provider())
    monkeypatch.setattr(
        llm_refine,
        "_post_chat_synthesis",
        lambda *_args, **_kwargs: ("写完的一句。\n写到一半", "length"),
    )

    refused, reason = llm_refine.synthesize_messages([{"role": "user", "content": "q"}])
    assert refused is None
    assert "截断" in reason

    allowed, reason = llm_refine.synthesize_messages(
        [{"role": "user", "content": "q"}],
        allow_truncated=True,
    )
    assert reason == ""
    assert allowed is not None
    assert allowed.finish_reason == "length"
    assert allowed.answer.endswith("写到一半")


def _market_result() -> ask.AskResult:
    return ask.AskResult(
        query=QUESTION,
        trade_date="2026-07-22",
        matched_theme=None,
        candidate_tier=None,
        priority_score=None,
        answer_spec=_spec(as_of="2026-07-22"),
        prepared_synthesis_messages=[{"role": "user", "content": "占位"}],
    )


def test_composer_salvages_complete_sentences_from_a_truncated_draft(monkeypatch) -> None:
    result = _market_result()
    spec = result.answer_spec
    assert spec is not None
    disclosure = "本轮整体盘面数据截至 2026-09-30，并不是 2026-07-22，不能当作所问日期的行情。"
    composed = (
        _fact(spec, "base:fact:1", disclosure)
        + "\n"
        + _gap("本地资料未命中 2026-07-22 当日的连板梯队数据。")
        + "\n若后续补齐该日梯队数据<!-- claim_ids=base:ga"
    )
    judge = json.dumps(
        {"passed": True, "rejected_sentence_indexes": [], "issues": []},
        ensure_ascii=False,
    )
    calls: list[dict[str, object]] = []
    answers = [(composed, "length"), (judge, "stop")]

    def fake_synthesize_messages(messages, **kwargs):
        calls.append(kwargs)
        text, finish = answers[len(calls) - 1]
        if finish == "length" and not kwargs.get("allow_truncated"):
            return None, "LLM 合成响应被截断，已降级为模板"
        return (
            llm_refine.SynthesisResult(
                answer=text, provider="fake", model="fake-model", finish_reason=finish
            ),
            "",
        )

    monkeypatch.setattr(llm_refine, "synthesize_messages", fake_synthesize_messages)
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    ask_synthesis.synthesize_shadow_grounded_answer(
        ask.PreparedAnswer(
            options=ask.AskOptions(query=QUESTION, shadow_grounded_composer=True),
            result=result,
        ),
        repair_drop_invalid=True,
    )

    assert calls[0]["allow_truncated"] is True
    assert calls[0]["max_tokens"] == ask_synthesis.GROUNDED_COMPOSER_MAX_TOKENS
    phases = {phase.name: phase for phase in result.synthesis_phases}
    # status=ok + truncated_response = 截断后保住了写完的句子（不是整篇换模板）。
    assert phases["composer"].status == "ok"
    assert phases["composer"].reason_code == "truncated_response"
    shadow = result.grounded_composer_shadow
    assert shadow is not None
    assert shadow.status != "composer_unavailable"
    assert "若后续补齐该日梯队数据" not in (shadow.raw_answer or "")
    assert disclosure in (shadow.presented_answer or shadow.repaired_answer or shadow.raw_answer or "")


@pytest.mark.parametrize(
    "name, minimum",
    (
        ("GROUNDED_COMPOSER_MAX_TOKENS", 16_000),
        ("GROUNDING_JUDGE_MAX_TOKENS", 4_000),
    ),
)
def test_writer_and_judge_token_caps_leave_room_for_forced_thinking(
    name: str, minimum: int
) -> None:
    """旧值 2400 / 1200 在强制思考的 GLM 上会在正文写完前截断。"""

    assert getattr(ask_synthesis, name) >= minimum
