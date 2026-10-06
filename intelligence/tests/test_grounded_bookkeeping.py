"""Frozen 10-05 drafts lost conclusions to marker bookkeeping, not missing evidence.

Restore only known atom owners; retain fact/gap, unknown-ID and signed-number gates.
These offline regressions do not call a model or require the live run artifacts.
"""

from dataclasses import replace

import pytest

from intelligence.services import answer_model as model
from intelligence.tests.test_grounded_anchor_dates import _atom, _codes, _fact, _spec


def test_cited_atom_restores_its_owner_claim() -> None:
    spec = _spec()
    fact_atom = _atom(spec, "base:fact:3")
    answer = (
        "全市场成交额 14377.22 亿元，涨停 52 家。"
        f"<!-- claim_ids=base:gap:1; evidence_atom_ids={fact_atom}; claim_type=inference -->"
    )
    assert "grounded_composer_invalid_evidence_atom_id" in _codes(answer, spec)

    canonical = model.canonicalize_grounded_claim_ids(answer, spec)

    assert "claim_ids=base:gap:1,base:fact:3;" in canonical
    assert _codes(canonical, spec) == {}
    assert model.canonicalize_grounded_claim_ids(canonical, spec) == canonical


def test_recovered_claims_do_not_change_prose_or_duplicate_ids() -> None:
    spec = _spec()
    atom = _atom(spec, "base:fact:3")
    prose = "全市场成交额 14377.22 亿元。"
    answer = (
        f"{prose}<!-- claim_ids=base:fact:3; "
        f"evidence_atom_ids={atom},{atom}; claim_type=fact -->"
    )
    assert model.canonicalize_grounded_claim_ids(answer, spec) == answer


def test_restored_owner_cannot_promote_a_gap_to_fact() -> None:
    base = _spec()
    # The interrupted draft used `if gap_atoms:` and silently skipped its assertion:
    # the original gap has no evidence IDs. Give this gap an explicit source.
    spec = replace(base, gaps=(replace(base.gaps[0], evidence_ids=("BASE",)),))
    fact_atom = _atom(spec, "base:fact:3")
    gap_atom = _atom(spec, "base:gap:1")
    answer = (
        "全市场成交额 14377.22 亿元。"
        f"<!-- claim_ids=base:fact:3; evidence_atom_ids={fact_atom},{gap_atom}; claim_type=fact -->"
    )

    canonical = model.canonicalize_grounded_claim_ids(answer, spec)

    assert "claim_ids=base:fact:3,base:gap:1;" in canonical
    assert "grounded_composer_promoted_to_fact" in _codes(canonical, spec)


@pytest.mark.parametrize("unknown_field", ("claim", "atom"))
def test_unknown_ids_remain_invalid_after_owner_recovery(unknown_field) -> None:
    spec = _spec()
    known_atom = _atom(spec, "base:fact:3")
    claims = "base:gap:1,claim:unknown" if unknown_field == "claim" else "base:gap:1"
    atoms = f"{known_atom},atom-unknown" if unknown_field == "atom" else known_atom
    answer = (
        "全市场成交额 14377.22 亿元。"
        f"<!-- claim_ids={claims}; evidence_atom_ids={atoms}; claim_type=inference -->"
    )
    canonical = model.canonicalize_grounded_claim_ids(answer, spec)
    code = "grounded_composer_invalid_claim_id" if unknown_field == "claim" else "grounded_composer_invalid_evidence_atom_id"
    assert code in _codes(canonical, spec)


def _signed_spec(*, structured=True):
    base = _spec()
    claim = model.make_claim(
        claim_id="base:fact:9",
        text="全市场成交额较前一日 -10.27%。",
        claim_type="supporting_fact",
        theme="市场复盘",
        status=model.ClaimStatus.VERIFIED,
        evidence_ids=("BASE",),
    )
    spec = replace(base, verified_facts=(*base.verified_facts, claim))
    if not structured:
        atom = next(
            a for a in model.evidence_atoms_from_answer_spec(spec)
            if a.provenance.get("claim_id") == claim.claim_id
        )
        spec = replace(spec, research_evidence_atoms=(replace(atom, metric=None, value=None),))
    return spec


@pytest.mark.parametrize("structured", (True, False))
@pytest.mark.parametrize("wording", ("缩量 10.27%", "缩量10.27%", "缩量约 10.27%"))
def test_volume_shrink_magnitude_can_omit_minus(wording, structured) -> None:
    spec = _signed_spec(structured=structured)
    answer = _fact(spec, "base:fact:9", f"成交额较前一日{wording}。")
    assert _codes(answer, spec) == {}


@pytest.mark.parametrize("prose", (
    "成交额较前一日上涨 10.27%，涨跌结构偏强。",
    "缩量阶段已经结束，成交额上涨 10.27%。",
    "成交额缩量 10.27%，随后上涨 10.27%。",
    "成交额较前一日缩量 11.27%。",
))
def test_shrink_word_does_not_exempt_other_or_unknown_numbers(prose) -> None:
    spec = _signed_spec()
    answer = _fact(spec, "base:fact:9", prose)
    assert "grounded_composer_added_number" in _codes(answer, spec)
