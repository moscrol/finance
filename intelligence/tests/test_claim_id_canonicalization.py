"""composer 把 atom id 串位写进 claim_ids 时，要还原成所属 claim，而不是毙掉整答案。

实测 2026-07-31：合成器写出 2127 字的好答案，逐家写清 12 家候选公司的产业链环节、
层级和缺口（万润新能，正负极材料环节，候选——两条证据均已超 45 天时效阈值…），
被确定性门禁以 grounded_composer_invalid_claim_id 全部否决，理由是：

  <!-- claim_ids=summary:definition,atom-4f0c5f5ec8d2;
       evidence_atom_ids=atom-4f0c5f5ec8d2; claim_type=inference -->

同一个 atom id 同时出现在两个字段里。atom id 不是合法 claim id，于是句句判无效、
确定性修复失败、整份答案被换成 190 字的「请补充数据源」。

这是字段串位，不是无出处引用：atom id 唯一指向它的所属 claim，可确定还原。
parse_decision_brief 对 brief 早就做了同样的规范化，这里把规则补到 composer 侧。
"""
from __future__ import annotations

from intelligence.services.answer_model import (
    AnswerSpec,
    ClaimStatus,
    canonicalize_grounded_claim_ids,
    evidence_atoms_from_answer_spec,
    make_claim,
    resolve_answer_profile,
    validate_grounded_composer_answer,
)


def _spec() -> AnswerSpec:
    claim = make_claim(
        claim_id="summary:definition",
        text="固态电池的研究范围覆盖电解质与制造设备。",
        claim_type="fact",
        theme="固态电池",
        status=ClaimStatus.VERIFIED,
        evidence_ids=("G1",),
    )
    return AnswerSpec(
        research_spec=resolve_answer_profile("固态电池现在怎么看"),
        summary=(claim,),
        verified_facts=(),
        company_table=(),
        counter_evidence=(),
        gaps=(),
        triggers=(),
        next_actions=(),
        sources=(),
        system_notices=(),
    )


def _atom_id(spec: AnswerSpec) -> str:
    atoms = evidence_atoms_from_answer_spec(spec)
    assert atoms, "fixture 需要至少一个 EvidenceAtom"
    return atoms[0].atom_id


def test_atom_id_in_claim_ids_is_mapped_back_to_its_claim() -> None:
    spec = _spec()
    atom = _atom_id(spec)
    answer = (
        "固态电池的研究范围覆盖电解质与制造设备。 "
        f"<!-- claim_ids=summary:definition,{atom}; "
        f"evidence_atom_ids={atom}; claim_type=fact -->"
    )

    out = canonicalize_grounded_claim_ids(answer, spec)

    assert "claim_ids=summary:definition;" in out
    # atom id 仍留在它该在的字段里。
    assert f"evidence_atom_ids={atom}" in out


def test_canonicalized_answer_passes_validation() -> None:
    """还原之后，原本句句判无效的答案应当能通过校验。"""
    spec = _spec()
    atom = _atom_id(spec)
    broken = (
        "固态电池的研究范围覆盖电解质与制造设备。 "
        f"<!-- claim_ids={atom}; evidence_atom_ids={atom}; claim_type=fact -->"
    )

    before = validate_grounded_composer_answer(broken, spec)
    after = validate_grounded_composer_answer(
        canonicalize_grounded_claim_ids(broken, spec), spec
    )

    assert any(i.code == "grounded_composer_invalid_claim_id" for i in before)
    assert not any(i.code == "grounded_composer_invalid_claim_id" for i in after)


def test_valid_claim_ids_are_left_untouched() -> None:
    spec = _spec()
    atom = _atom_id(spec)
    answer = (
        "固态电池的研究范围覆盖电解质与制造设备。 "
        f"<!-- claim_ids=summary:definition; evidence_atom_ids={atom}; claim_type=fact -->"
    )

    assert canonicalize_grounded_claim_ids(answer, spec) == answer


def test_unknown_ids_are_not_invented_away() -> None:
    """既不是 claim 也不是 atom 的 id 原样保留，让门禁照旧拒绝。"""
    spec = _spec()
    answer = (
        "一句话。 <!-- claim_ids=claim:查无此条; evidence_atom_ids=; claim_type=fact -->"
    )

    out = canonicalize_grounded_claim_ids(answer, spec)

    assert "claim:查无此条" in out
    assert any(
        i.code == "grounded_composer_invalid_claim_id"
        for i in validate_grounded_composer_answer(out, spec)
    )


def test_duplicates_collapse() -> None:
    spec = _spec()
    atom = _atom_id(spec)
    answer = (
        "固态电池的研究范围覆盖电解质与制造设备。 "
        f"<!-- claim_ids=summary:definition,{atom},summary:definition; "
        f"evidence_atom_ids={atom}; claim_type=fact -->"
    )

    out = canonicalize_grounded_claim_ids(answer, spec)

    assert out.count("summary:definition") == 1
