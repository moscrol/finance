from intelligence.services.relation_guard import relation_edge_supported, relation_gap_text


def test_cooccurrence_without_direction_is_not_a_relation_edge() -> None:
    rows = [{"company": "A", "concept": "液冷", "strength": "core"}]
    assert relation_edge_supported("液冷和PCB谁在上游", rows) is False
    assert "关系边" in relation_gap_text("液冷和PCB谁在上游")


def test_explicit_chain_stage_can_support_direction() -> None:
    rows = [{"company": "A", "concept": "液冷", "chain_stage": "上游材料"}]
    assert relation_edge_supported("液冷上游有哪些公司", rows) is True
