"""Company context recovery must not turn a suffix match into entity evidence.

Exercise the real validator, drop-invalid repair and synthesis consumers. Provider
and semantic judge are stubs here; this is not natural-answer quality acceptance.
"""
from dataclasses import replace

import pytest

from intelligence.services import answer_model as am, ask, ask_synthesis, llm_refine


def _spec(text="三环集团；丽珠集团；中信证券。"):
    claims = tuple(
        am.make_claim(
            claim_id=claim_id, text=body, claim_type="supporting_fact",
            theme="市场复盘", status=am.ClaimStatus.VERIFIED, evidence_ids=(source,),
        )
        for claim_id, body, source in (
            ("bound", text, "S1"),
            ("neighbour", "华中三环集团；中原银行。", "S2"),
        )
    )
    return am.AnswerSpec(
        research_spec=am.resolve_answer_profile("市场如何", "市场复盘", "general"),
        summary=(), verified_facts=claims, company_table=(), counter_evidence=(),
        gaps=(), triggers=(), next_actions=(), system_notices=(),
        sources=(am.EvidenceRef("S1", "绑定证据"), am.EvidenceRef("S2", "邻句证据")),
    )


def _line(spec, text, claim_id="bound", claim_type="fact"):
    atoms = ",".join(
        atom.atom_id for atom in am.evidence_atoms_from_answer_spec(spec)
        if atom.provenance["claim_id"] == claim_id
    )
    return (
        f"{text}<!-- claim_ids={claim_id}; evidence_atom_ids={atoms}; "
        f"claim_type={claim_type} -->"
    )


def _errors(answer, spec):
    return [issue for issue in am.validate_grounded_composer_answer(answer, spec)
            if issue.severity == "error"]


@pytest.mark.parametrize("text,evidence", (
    ("公司暴露中三环集团", "公司暴露含三环集团（公司资料）"),
    ("公司暴露含丽珠集团", "医药公司：丽珠集团。"),
    ("算力方向的三环集团", "AI算力方向包含三环集团"),
    ("芯片方向包括中信证券", "中信证券。"),
    ("为重点的综合医药健康集团", "复星医药（以创新药为发展重点的综合医药健康集团）"),
    ("其中三环集团", "三环集团。"),
), ids=("exposure-in", "exposure-includes", "direction", "direction-includes", "descriptor", "legacy"))
def test_context_is_retained_by_validator_and_repair(text, evidence):
    spec = _spec(evidence)
    answer = _line(spec, text + "。")
    assert not _errors(answer, spec)
    assert am.repair_grounded_composer_answer(answer, spec, drop_invalid=True) == answer
    assert text in am.present_grounded_composer_answer(answer, spec)


@pytest.mark.parametrize("name", (
    "新三环集团", "华中三环集团", "华为三环集团", "新的三环集团", "华和三环集团",
    "新华及三环集团", "新华公司暴露中三环集团", "公司暴露中新三环集团",
    "公司暴露中华中三环集团", "公司暴露中和丰顺集团",
), ids=("new", "internal-zhong", "internal-wei", "internal-de", "internal-he", "internal-ji",
        "internal-phrase", "context-new", "context-internal", "no-second-prefix"))
def test_context_letters_inside_a_name_do_not_license_suffix_evidence(name):
    spec = _spec("三环集团；丰顺集团。")
    bad = _line(spec, name + "仍需核实。")
    assert "grounded_composer_added_company" in {i.code for i in _errors(bad, spec)}
    assert am.repair_grounded_composer_answer(bad, spec, drop_invalid=True) is None


@pytest.mark.parametrize("known", ("华中三环集团", "华为三环集团", "新的三环集团", "和丰顺集团"))
def test_full_company_with_context_letters_is_valid_when_evidenced(known):
    spec = _spec(f"公司：{known}。")
    assert not _errors(_line(spec, known + "仍需核实。"), spec)


@pytest.mark.parametrize("joiner", ("和", "及", "与", "、", "", "方向的"))
def test_known_neighbour_does_not_hide_an_unknown_company(joiner):
    spec = _spec("丽珠集团。")
    bad = _line(spec, f"新三环集团{joiner}丽珠集团。")
    assert "grounded_composer_added_company" in {i.code for i in _errors(bad, spec)}


def test_adjacent_known_companies_are_checked_separately():
    spec = _spec()
    assert not _errors(_line(spec, "三环集团和丽珠集团及中信证券。"), spec)


@pytest.mark.parametrize("evidence", ("新三环集团。", "华中三环集团。", "华为三环集团。"),
                         ids=("new", "internal-zhong", "internal-wei"))
def test_recovered_name_must_be_whole_in_its_evidence(evidence):
    spec = _spec(evidence)
    bad = _line(spec, "公司暴露中三环集团仍需核实。")
    assert "grounded_composer_added_company" in {i.code for i in _errors(bad, spec)}


def test_recovery_never_borrows_a_neighbouring_binding():
    spec = _spec()
    bad = _line(spec, "公司暴露中中原银行仍需核实。")
    good = _line(spec, "中原银行仍需核实。", "neighbour")
    issues = _errors(bad + good, spec)
    assert [(i.code, i.message) for i in issues] == [
        ("grounded_composer_added_company", "第 1 句增加证据外公司：公司暴露中中原银行"),
    ]
    assert am.repair_grounded_composer_answer(bad + good, spec, drop_invalid=True) == good


def test_context_recovery_does_not_relax_numbers_or_claim_types():
    spec = _spec()
    gap = am.make_claim(claim_id="gap", text="三环集团尚缺公告。", claim_type="gap",
                        theme="市场复盘", status=am.ClaimStatus.MISSING)
    spec = replace(spec, gaps=(gap,))
    good = _line(spec, "公司暴露中三环集团仍需核实。")
    number = _line(spec, "公司暴露中三环集团上涨99%。")
    promoted = _line(spec, "公司暴露中三环集团。", "gap")
    issues = _errors(good + number + promoted, spec)
    assert {i.code for i in issues} >= {
        "grounded_composer_added_number", "grounded_composer_promoted_to_fact",
    }
    assert am.repair_grounded_composer_answer(good + number + promoted, spec, drop_invalid=True) == good


@pytest.mark.parametrize("judge_off", (True, False), ids=("judge-off", "judge-stub"))
def test_synthesis_retains_supported_context_but_rejects_a_new_company(monkeypatch, judge_off):
    spec = _spec()
    good = _line(spec, "公司暴露中三环集团仍需核实。")
    bad = _line(spec, "华中三环集团仍需核实。")
    calls = []

    def synthesize(messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            answer = good + bad
        else:
            assert good in messages[-1]["content"]
            assert bad not in messages[-1]["content"]
            answer = '{"passed":true,"rejected_sentence_indexes":[],"issues":[]}'
        return llm_refine.SynthesisResult(answer=answer, provider="fake", model="test"), ""

    monkeypatch.setattr(llm_refine, "synthesize_messages", synthesize)
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    monkeypatch.setattr(ask_synthesis, "semantic_judge_mode", lambda: "off" if judge_off else "llm")
    options = ask.AskOptions(query="市场如何", shadow_grounded_composer=True)
    result = ask.AskResult(query=options.query, answer_spec=spec, trade_date=None,
                           matched_theme="市场复盘", candidate_tier=None, priority_score=None)
    ask_synthesis.synthesize_shadow_grounded_answer(
        ask.PreparedAnswer(options=options, result=result), repair_drop_invalid=True,
    )
    shadow = result.grounded_composer_shadow
    assert shadow is not None and shadow.presented_answer is not None
    assert "三环集团仍需核实" in shadow.presented_answer
    assert "华中三环集团" not in shadow.presented_answer
    assert len(calls) == (1 if judge_off else 2)
