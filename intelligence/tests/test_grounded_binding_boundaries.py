"""Each trailing marker owns only the prose before it, not an entire physical line.

10-05 D4 had 20 markers on 7 lines. The old parser discarded 13 bindings, then
validated whole paragraphs against their first claim. Do not repair this by
unioning evidence: a following marker or unbound tail cannot borrow a neighbour.
"""
from dataclasses import replace

import pytest

from intelligence.services import answer_model as am, ask, ask_synthesis, llm_refine
from intelligence.tests.test_entity_rebinding import _spec as _entity_spec


def _spec() -> am.AnswerSpec:
    claims = tuple(
        am.make_claim(
            claim_id=claim_id,
            text=text,
            claim_type="supporting_fact",
            theme="市场复盘",
            status=am.ClaimStatus.VERIFIED,
            evidence_ids=(evidence_id,),
        )
        for claim_id, text, evidence_id in (
            ("market:total", "成交额 26531.66 亿元。", "S1"),
            ("market:ladder", "最高 5 板，晋级率 8%。", "S2"),
        )
    )
    return am.AnswerSpec(
        research_spec=am.resolve_answer_profile("市场如何", "市场复盘", "general"),
        summary=(), verified_facts=claims, company_table=(),
        counter_evidence=(), gaps=(), triggers=(), next_actions=(),
        sources=(am.EvidenceRef("S1", "市场总量"), am.EvidenceRef("S2", "连板梯队")),
        system_notices=(),
    )


def _line(spec, claim_id, text, *, claim_type="fact") -> str:
    atoms = ",".join(
        atom.atom_id for atom in am.evidence_atoms_from_answer_spec(spec)
        if atom.provenance["claim_id"] == claim_id
    )
    return (
        f"{text}<!-- claim_ids={claim_id}; evidence_atom_ids={atoms}; "
        f"claim_type={claim_type} -->"
    )


def _pair(spec):
    return (
        _line(spec, "market:total", "成交额 26531.66 亿元。"),
        _line(spec, "market:ladder", "最高 5 板，晋级率 8%。"),
    )


def _errors(answer, spec):
    return tuple(i for i in am.validate_grounded_composer_answer(answer, spec)
                 if i.severity == "error")


@pytest.mark.parametrize("separator", ("", " ", "\n", "\r\n"))
def test_each_marker_keeps_its_own_body_ids_and_index(separator):
    spec = _spec()
    answer = separator.join(_pair(spec))
    sentences, unbound = am.parse_grounded_sentences(answer)
    assert unbound == ()
    assert [(s.sentence_index, s.text, s.claim_ids) for s in sentences] == [
        (1, "成交额 26531.66 亿元。", ("market:total",)),
        (2, "最高 5 板，晋级率 8%。", ("market:ladder",)),
    ]
    assert all(s.evidence_atom_ids and s.claim_type == "fact" for s in sentences)
    assert not _errors(answer, spec)


def test_multiple_sentences_with_one_marker_remain_one_binding_unit():
    spec = _spec()
    text = "成交额 26531.66 亿元。量能需观察；不能仅据此确认趋势。"
    sentences, unbound = am.parse_grounded_sentences(_line(spec, "market:total", text))
    assert len(sentences) == 1
    assert sentences[0].text == text
    assert not unbound


@pytest.mark.parametrize("wrong_first", (True, False))
def test_neighbour_cannot_donate_its_evidence_to_another_unit(wrong_first):
    spec = _spec()
    wrong = _line(spec, "market:total", "最高 5 板。")
    good = _pair(spec)[1]
    answer = wrong + good if wrong_first else good + wrong
    errors = _errors(answer, spec)
    assert [(i.code, i.message) for i in errors] == [
        ("grounded_composer_added_number", f"第 {1 if wrong_first else 2} 句增加证据外数字：5"),
    ]
    repaired = am.repair_grounded_composer_answer(answer, spec, drop_invalid=True)
    assert repaired == good


@pytest.mark.parametrize("field,code", (
    ("claim", "grounded_composer_invalid_claim_id"),
    ("atom", "grounded_composer_invalid_evidence_atom_id"),
    ("no_atom", "grounded_composer_fact_without_evidence"),
))
def test_invalid_later_binding_is_not_hidden_by_valid_first_marker(field, code):
    spec = _spec()
    good = _pair(spec)[0]
    bad = _line(spec, "market:total", "成交额仍需观察。")
    if field == "claim":
        bad = bad.replace("claim_ids=market:total;", "claim_ids=unknown;")
    else:
        atom_ids = am.parse_grounded_sentences(bad)[0][0].evidence_atom_ids
        assert atom_ids
        bad = bad.replace(",".join(atom_ids), "unknown-atom" if field == "atom" else "")
    assert any(i.code == code and "第 2 句" in i.message for i in _errors(good + bad, spec))
    assert am.repair_grounded_composer_answer(good + bad, spec, drop_invalid=True) == good


def test_unbound_tail_cannot_borrow_the_preceding_marker_even_with_known_numbers():
    spec = _spec()
    first = _pair(spec)[0]
    tail = "成交额 26531.66 亿元，这一句没有出处。"
    sentences, unbound = am.parse_grounded_sentences(first + tail)
    assert len(sentences) == 1
    assert unbound == (tail,)
    assert "grounded_composer_missing_binding" in {i.code for i in _errors(first + tail, spec)}
    assert am.repair_grounded_composer_answer(first + tail, spec, drop_invalid=True) == first


@pytest.mark.parametrize("drop_invalid", (True, False))
def test_repair_acts_only_on_the_invalid_unit_and_preserves_neighbours(drop_invalid):
    spec = _spec()
    first, third = _pair(spec)
    bad = _line(spec, "market:total", "成交额 99999 亿元。")
    repaired = am.repair_grounded_composer_answer(first + bad + third, spec, drop_invalid=drop_invalid)
    assert repaired is not None
    assert first in repaired and third in repaired
    assert "99999" not in repaired
    sentences, unbound = am.parse_grounded_sentences(repaired)
    assert len(sentences) == (2 if drop_invalid else 3)
    assert not unbound and not _errors(repaired, spec)


def test_rejected_index_means_the_same_unit_to_parser_and_repair():
    spec = _spec()
    first, second = _pair(spec)
    repaired = am.repair_grounded_composer_answer(
        first + second, spec, rejected_sentence_indexes=(2,), drop_invalid=True,
    )
    assert repaired == first


def test_dropped_inline_predecessor_does_not_leave_a_dangling_connective():
    spec = _spec()
    first = _pair(spec)[0]
    second = _line(spec, "market:ladder", "反之，最高 5 板，晋级率 8%。")
    repaired = am.repair_grounded_composer_answer(
        first + second, spec, rejected_sentence_indexes=(1,), drop_invalid=True,
    )
    assert repaired is not None and repaired.startswith("最高 5 板")
    assert "反之" not in repaired


def test_an_empty_extra_marker_is_rejected_not_merged_or_discarded():
    spec = _spec()
    first = _pair(spec)[0]
    empty = _line(spec, "market:ladder", "")
    assert "grounded_composer_empty_binding" in {i.code for i in _errors(first + empty, spec)}
    repaired = am.repair_grounded_composer_answer(first + empty, spec, drop_invalid=True)
    assert repaired == first


def test_wrapped_marker_and_next_line_marker_share_the_same_boundary_rule():
    spec = _spec()
    first, second = _pair(spec)
    answer = first.replace("; evidence_atom_ids=", ";\n evidence_atom_ids=")
    answer += second.replace("<!--", "\n<!--")
    sentences, unbound = am.parse_grounded_sentences(answer)
    assert len(sentences) == 2 and not unbound
    assert sentences[0].claim_ids == ("market:total",)
    assert sentences[1].claim_ids == ("market:ladder",)
    assert not _errors(answer, spec)


@pytest.mark.parametrize("barrier", ("\n\n", "\n## 边界\n"))
def test_orphan_marker_cannot_reach_back_across_a_blank_or_heading(barrier):
    spec = _spec()
    text = "成交额 26531.66 亿元。"
    answer = text + barrier + _line(spec, "market:total", "")
    sentences, unbound = am.parse_grounded_sentences(answer)
    assert unbound == (text,)
    assert len(sentences) == 1 and sentences[0].text == ""
    assert am.repair_grounded_composer_answer(answer, spec, drop_invalid=True) is None


def test_second_orphan_marker_is_not_silently_discarded_or_unioned():
    spec = _spec()
    answer = "成交额 26531.66 亿元。\n" + _line(spec, "market:total", "")
    answer += _line(spec, "unknown", "")
    sentences, unbound = am.parse_grounded_sentences(answer)
    assert not unbound and len(sentences) == 2
    assert sentences[0].claim_ids == ("market:total",)
    assert sentences[1].claim_ids == ("unknown",) and sentences[1].text == ""
    assert "grounded_composer_invalid_claim_id" in {i.code for i in _errors(answer, spec)}


def test_partial_marker_never_becomes_a_complete_binding():
    spec = _spec()
    broken = _pair(spec)[1].removesuffix("-->")
    sentences, unbound = am.parse_grounded_sentences(_pair(spec)[0] + broken)
    assert len(sentences) == 1 and unbound == (broken.strip(),)
    assert "grounded_composer_missing_binding" in {
        i.code for i in _errors(_pair(spec)[0] + broken, spec)
    }


def test_normalization_is_idempotent_and_ordinary_one_marker_lines_are_unchanged():
    spec = _spec()
    first, second = _pair(spec)
    normal = f"## 结论\n\n{first}\n{second}\n\n（非投资建议）"
    assert am.normalize_grounded_binding_lines(normal) == normal
    inline = am.normalize_grounded_binding_lines(first + second)
    assert inline == first + "\n" + second
    assert am.normalize_grounded_binding_lines(inline) == inline


def test_company_rebinding_does_not_move_the_previous_units_source():
    spec = _entity_spec()
    first = _line(spec, "gap:1", "仅有间接或候选证据。", claim_type="candidate")
    second = _line(spec, "gap:1", "华灿光电仍是候选。", claim_type="candidate")
    rebound = am.rebind_entity_claim_ids(first + second, spec)
    sentences, unbound = am.parse_grounded_sentences(rebound)
    assert not unbound and len(sentences) == 2
    assert [s.claim_ids for s in sentences] == [("gap:1",), ("company:1",)]
    assert first in rebound


def test_mixed_fact_and_gap_keep_their_individual_types():
    base = _spec()
    gap = am.make_claim(claim_id="gap:missing", text="反方证据不足。",
                        claim_type="gap", theme="市场复盘", status=am.ClaimStatus.MISSING)
    spec = replace(base, gaps=(gap,))
    answer = _pair(spec)[0] + _line(spec, gap.claim_id, gap.text, claim_type="gap")
    sentences, _ = am.parse_grounded_sentences(answer)
    assert [s.claim_type for s in sentences] == ["fact", "gap"]
    assert not _errors(answer, spec)


def test_presentation_drops_only_the_unit_with_an_internal_term():
    spec = _spec()
    first, last = _pair(spec)
    leaked = _line(spec, "market:total", "registry 是内部说明。")
    presented = am.present_grounded_composer_answer(first + leaked + last, spec)
    assert "成交额 26531.66 亿元。" in presented
    assert "最高 5 板，晋级率 8%。" in presented
    assert "registry" not in presented and "claim_ids" not in presented


def test_truncation_keeps_completed_units_before_an_inline_partial_tail():
    spec = _spec()
    first, second = _pair(spec)
    tail = "未写完<!-- claim_ids=market:total;"
    assert am.trim_to_last_complete_grounded_line(first + second + tail) == first + "\n" + second
    assert am.trim_to_last_complete_grounded_line(tail) == ""


def test_judge_messages_present_the_same_units_used_for_indexing():
    spec = _spec()
    first, second = _pair(spec)
    messages = llm_refine.build_grounding_judge_messages("市场如何", first + second, "registry")
    assert f"待审答案：\n{first}\n{second}\n\n用户问题" in messages[-1]["content"]


@pytest.mark.parametrize("judge_off", (False, True))
@pytest.mark.parametrize("include_bad", (False, True))
def test_real_synthesis_consumers_preserve_inline_bindings(monkeypatch, judge_off, include_bad):
    """Exercise author -> deterministic drop -> judge -> presentation, not just parse."""
    spec = _spec()
    first, second = _pair(spec)
    bad = _line(spec, "market:total", "成交额 99999 亿元。")
    calls = []

    def synthesize(messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            answer = first + (bad if include_bad else "") + second
        else:
            assert f"待审答案：\n{first}\n{second}\n\n用户问题" in messages[-1]["content"]
            answer = '{"passed":false,"rejected_sentence_indexes":[2],"issues":[]}'
        return llm_refine.SynthesisResult(answer=answer, provider="fake", model="test"), ""

    monkeypatch.setattr(llm_refine, "synthesize_messages", synthesize)
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    monkeypatch.setattr(ask_synthesis, "semantic_judge_mode", lambda: "off" if judge_off else "llm")
    options = ask.AskOptions(query="市场如何", shadow_grounded_composer=True)
    result = ask.AskResult(
        query=options.query, answer_spec=spec, trade_date=None,
        matched_theme="市场复盘", candidate_tier=None, priority_score=None,
    )
    ask_synthesis.synthesize_shadow_grounded_answer(
        ask.PreparedAnswer(options=options, result=result), repair_drop_invalid=True,
    )
    shadow = result.grounded_composer_shadow
    assert shadow is not None and shadow.presented_answer is not None
    assert "成交额 26531.66 亿元。" in shadow.presented_answer
    assert ("最高 5 板" in shadow.presented_answer) == judge_off
    assert "99999" not in shadow.presented_answer
    assert len(calls) == (1 if judge_off else 2)
    assert shadow.status == ("deterministic_only" if judge_off else "repaired")
    if not judge_off:
        assert shadow.judge_applied_sentence_indexes == (2,)
