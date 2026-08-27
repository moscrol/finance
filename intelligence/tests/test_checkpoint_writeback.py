"""方案 5 写侧（workspace）：回检 miss 写回 overlay + 门禁「fact 不得只绑过期原子」。"""

import json
from pathlib import Path

from intelligence.services import answer_model
from intelligence.services.answer_model import (
    AnswerSpec,
    ClaimStatus,
    EvidenceRef,
    make_claim,
    resolve_theme_research_spec,
    validate_llm_answer,
)
from intelligence.services.checkpoint_writeback import writeback_miss_verdict


# --------------------------------------------------------------------------- #
# 回检 miss → invalidation_links overlay 写回
# --------------------------------------------------------------------------- #
def _wiki(tmp_path: Path, items: list[dict]) -> Path:
    relations = tmp_path / "relations"
    relations.mkdir(parents=True)
    (relations / "evidence_index.json").write_text(
        json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8"
    )
    return tmp_path


def _item(target: str, concept: str, source_date: str, evidence: str) -> dict:
    return {
        "target": target,
        "target_type": "entity",
        "concept": concept,
        "source": "[[src]]",
        "source_date": source_date,
        "evidence": evidence,
    }


CHECKPOINT = {
    "id": "ck-2026-06-01-abc123",
    "ts": "2026-06-01T10:00:00",
    "claim": "宁德时代固态电池 Q3 量产",
    "stocks": ["宁德时代"],
    "themes": ["固态电池"],
}
MISS = {"id": "ck-2026-06-01-abc123", "verdict": "miss", "checked_at": "2026-07-18T02:00:00", "reason": "到期未量产"}


def test_miss_verdict_writes_hard_links(tmp_path: Path):
    wiki = _wiki(tmp_path, [
        _item("宁德时代", "固态电池", "2026-05-20", "Q3 量产在即"),
        _item("宁德时代", "机器人", "2026-05-20", "无关概念不写回"),
        _item("比亚迪", "固态电池", "2026-05-20", "其他标的不写回"),
        _item("宁德时代", "固态电池", "2026-06-15", "checkpoint 之后的新证据不背锅"),
    ])
    result = writeback_miss_verdict(CHECKPOINT, MISS, wiki_root=wiki)
    assert result == {"written": 1, "matched": 1, "skipped_reason": None}

    overlay = json.loads((wiki / "relations" / "invalidation_links.json").read_text(encoding="utf-8"))
    (link,) = overlay["links"]
    assert link["strength"] == "hard"
    assert link["negation"]["source"] == "checkpoint:ck-2026-06-01-abc123"
    assert link["negation"]["hits"] == ["checkpoint_miss"]
    assert link["invalidates"][0]["evidence"] == "Q3 量产在即"

    # 读侧消费同一 overlay：hard 链 → invalidated，默认不再返回
    from intelligence.adapters.knowledge import KnowledgeAdapter

    got = KnowledgeAdapter(wiki_root=wiki).get_evidence("宁德时代", concept="固态电池")
    dates = [item["source_date"] for item in got["items"]]
    assert "2026-05-20" not in dates and "2026-06-15" in dates


def test_miss_writeback_is_idempotent(tmp_path: Path):
    wiki = _wiki(tmp_path, [_item("宁德时代", "固态电池", "2026-05-20", "Q3 量产在即")])
    assert writeback_miss_verdict(CHECKPOINT, MISS, wiki_root=wiki)["written"] == 1
    second = writeback_miss_verdict(CHECKPOINT, MISS, wiki_root=wiki)
    assert second["written"] == 0
    assert "幂等" in second["skipped_reason"]


def test_non_miss_or_unlocatable_checkpoints_skip(tmp_path: Path):
    wiki = _wiki(tmp_path, [_item("宁德时代", "固态电池", "2026-05-20", "x")])
    hit = writeback_miss_verdict(CHECKPOINT, {**MISS, "verdict": "hit"}, wiki_root=wiki)
    assert hit["written"] == 0 and "miss" in hit["skipped_reason"]
    no_stocks = writeback_miss_verdict({**CHECKPOINT, "stocks": []}, MISS, wiki_root=wiki)
    assert no_stocks["written"] == 0 and "stocks" in no_stocks["skipped_reason"]
    assert not (wiki / "relations" / "invalidation_links.json").exists()


# --------------------------------------------------------------------------- #
# validate_llm_answer：fact 不得只绑 superseded/invalidated 原子
# --------------------------------------------------------------------------- #
def _spec_with_fact(freshness: str) -> AnswerSpec:
    spec = resolve_theme_research_spec("分析固态电池产业链")
    fact = make_claim(
        claim_id="fact-1",
        text="26H1 出货 9 万台。",
        claim_type="company_evidence",
        theme=spec.theme,
        status=ClaimStatus.VERIFIED,
        evidence_tier="L2",
        evidence_ids=("R1",),
        freshness=freshness,
    )
    return AnswerSpec(
        research_spec=spec,
        summary=(),
        verified_facts=(fact,),
        company_table=(),
        counter_evidence=(),
        gaps=(),
        triggers=(),
        next_actions=(),
        sources=(EvidenceRef(evidence_id="R1", source="[[src]]", source_date="2025-04-01"),),
        system_notices=(),
    )


def _answer_binding(spec: AnswerSpec) -> str:
    claim = spec.verified_facts[0]
    atoms = answer_model.evidence_atoms_from_answer_spec(spec)
    atom_ids = ",".join(atom.atom_id for atom in atoms)
    return (
        f"- {claim.text}"
        f"<!-- claim_id={claim.claim_id}; "
        f"evidence_atom_ids={atom_ids}; claim_type=fact -->"
    )


def test_fact_bound_only_to_superseded_atoms_is_rejected():
    spec = _spec_with_fact("superseded")
    codes = {issue.code for issue in validate_llm_answer(_answer_binding(spec), spec)}
    assert "llm_fact_only_superseded_evidence" in codes


def test_fact_bound_to_current_atoms_passes_staleness_gate():
    spec = _spec_with_fact("current")
    codes = {issue.code for issue in validate_llm_answer(_answer_binding(spec), spec)}
    assert "llm_fact_only_superseded_evidence" not in codes


# --------------------------------------------------------------------------- #
# 降桶标注：只绑已取代/已证伪证据的事实不退稿，但要在正文里标出来
# --------------------------------------------------------------------------- #
def test_superseded_fact_is_tiered_in_the_body_not_dropped():
    """降级要让读答案的人看见——记在 warnings 里用户读到的仍是笃定结论。"""

    spec = _spec_with_fact("superseded")
    presented = answer_model.present_llm_answer(_answer_binding(spec), spec)

    assert "26H1 出货 9 万台" in presented
    assert answer_model.STALE_EVIDENCE_TIER_NOTE in presented


def test_current_evidence_fact_carries_no_tier_note():
    """对偶：证据是当前的就不许标——无条件加标注等于没标。"""

    spec = _spec_with_fact("current")
    presented = answer_model.present_llm_answer(_answer_binding(spec), spec)

    assert "26H1 出货 9 万台" in presented
    assert answer_model.STALE_EVIDENCE_TIER_NOTE not in presented
