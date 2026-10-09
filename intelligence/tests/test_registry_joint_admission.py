"""Atomic context must coexist with support; a brief cannot cite omitted rows."""
from dataclasses import replace
import json

import pytest

from intelligence.services import answer_model as am


def _claim(name, text, status):
    return am.Claim(name, text, "supporting_fact", "合成", evidence_ids=("D1",),
                    evidence_tier="L4_structured", status=status)


def _spec():
    return am.AnswerSpec(
        research_spec=am.resolve_answer_profile("合成核对", profile="general"),
        summary=(_claim("summary", "不可替代完整事实的摘要。" * 8, am.ClaimStatus.INFERRED),),
        verified_facts=tuple(_claim(f"fact:{i}", f"合成事实{i}。" * 12, am.ClaimStatus.VERIFIED) for i in range(3)),
        candidate_facts=(_claim("history", "完整推断及边界。" * 120, am.ClaimStatus.INFERRED),),
        company_table=(), counter_evidence=(_claim("counter", "合成反证。", am.ClaimStatus.INFERRED),),
        gaps=(_claim("gap", "尚未覆盖全部日期。", am.ClaimStatus.MISSING),),
        triggers=(), next_actions=(), sources=(), system_notices=(),
    )


def _rows(block):
    return [json.loads(line) for line in block.splitlines()]


def test_atomic_context_preserves_support_counter_and_truthful_omission():
    spec = _spec()
    full = {row["claim_id"]: row for row in _rows(am.grounded_claim_registry_block(spec))}
    def encode(row):
        return json.dumps(row, ensure_ascii=False, separators=(",", ": "))

    # Enough for history + one fact + counter + a bounded omission notice, not all claims.
    budget = sum(len(encode(full[k])) + 1 for k in ("history", "fact:0", "counter")) + 90
    block = am.grounded_claim_registry_block(spec, max_chars=budget, required_claim_ids=("history",), require_support=True)
    rows = _rows(block)
    by_id = {r["claim_id"]: r for r in rows if "claim_id" in r}
    assert len(block) <= budget
    assert by_id["history"] == full["history"]
    assert any(r["claim_type"] == "fact" for r in rows if "claim_id" in r)
    assert "counter" in by_id
    assert "未纳入" in rows[-1]["note"]
    dropped = int(rows[-1]["note"].split("另有 ")[1].split(" 条")[0])
    assert dropped == len(full) - len(by_id)
    assert all(row == full[name] for name, row in by_id.items())


def test_required_context_cannot_silently_displace_every_verified_fact():
    spec = _spec()
    history_only = replace(spec, summary=(), verified_facts=(), counter_evidence=(), gaps=())
    budget = len(am.grounded_claim_registry_block(history_only))
    with pytest.raises(ValueError, match="budget"):
        am.grounded_claim_registry_block(spec, max_chars=budget, required_claim_ids=("history",), require_support=True)


def test_joint_admission_reserves_each_fact_source_not_just_any_fact():
    spec = _spec()
    short = _claim("mainline", "主线成交额缺失，不能据此判零。", am.ClaimStatus.VERIFIED)
    short = replace(short, evidence_ids=("D4",))
    spec = replace(spec, verified_facts=(*spec.verified_facts, short))
    minimal = replace(spec, summary=(), verified_facts=(spec.verified_facts[0], short),
                      counter_evidence=(), gaps=())
    budget = len(am.grounded_claim_registry_block(minimal)) + 90
    rows = _rows(am.grounded_claim_registry_block(
        spec, max_chars=budget, required_claim_ids=("history",), require_support=True,
    ))
    delivered = {atom["source_id"] for row in rows if row.get("claim_type") == "fact"
                 for atom in row["evidence_atoms"]}
    assert delivered == {"D1", "D4"}
    assert "未纳入" in rows[-1]["note"]


def test_synthesis_budget_must_also_fit_omission_notice():
    spec = _spec()
    minimal = replace(spec, summary=(), verified_facts=spec.verified_facts[:1],
                      counter_evidence=(), gaps=())
    budget = len(am.grounded_claim_registry_block(minimal))
    with pytest.raises(ValueError, match="budget"):
        am.grounded_claim_registry_block(spec, max_chars=budget,
                                        required_claim_ids=("history",), require_support=True)


def test_admitted_view_closes_brief_and_validation_without_mutating_audit():
    spec = _spec()
    original = spec.to_dict()
    allowed = replace(spec, summary=(), verified_facts=spec.verified_facts[:1], gaps=())
    registry = am.grounded_claim_registry_block(allowed)
    view = am.answer_spec_for_registry(spec, registry)
    brief = am.build_deterministic_decision_brief(view)
    assert brief is not None
    ids = {r["claim_id"] for r in _rows(registry)}
    for value in brief.to_dict().values():
        if isinstance(value, list):
            assert set(value) <= ids
    assert brief.direct_answer == spec.verified_facts[0].text
    assert view.verified_facts == spec.verified_facts[:1]
    assert view.summary == () and view.gaps == ()
    assert spec.to_dict() == original
    unknown = spec.verified_facts[1]
    answer = f'{unknown.text} <!-- claim_ids={unknown.claim_id}; evidence_atom_ids=; claim_type=fact -->'
    assert any(issue.code == "grounded_composer_invalid_claim_id"
               for issue in am.validate_grounded_composer_answer(answer, view))


def test_registry_projection_rejects_unknown_or_rewritten_claim():
    spec = _spec()
    row = _rows(am.grounded_claim_registry_block(spec))[0]
    for changed in ({**row, "claim_id": "invented"}, {**row, "text": "改写的事实"},
                    {**row, "evidence_atoms": []}, {**row, "claim_type": "fact"},
                    {**row, "company": "another"}):
        with pytest.raises(ValueError):
            am.answer_spec_for_registry(spec, json.dumps(changed, ensure_ascii=False))
