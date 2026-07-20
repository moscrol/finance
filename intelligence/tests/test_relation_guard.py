from intelligence.services.relation_guard import relation_edge_supported, relation_gap_text
from intelligence.services.ask import AskOptions, answer_query, render_conversation_answer


def test_cooccurrence_without_direction_is_not_a_relation_edge() -> None:
    rows = [{"company": "A", "concept": "液冷", "strength": "core"}]
    assert relation_edge_supported("液冷和PCB谁在上游", rows) is False
    assert "关系边" in relation_gap_text("液冷和PCB谁在上游")


def test_explicit_chain_stage_can_support_direction() -> None:
    rows = [{"company": "A", "concept": "液冷", "chain_stage": "上游材料"}]
    assert relation_edge_supported("液冷上游有哪些公司", rows) is True


def test_relation_question_without_edge_fails_closed_and_traces_graph_guard(tmp_path) -> None:
    wiki = tmp_path / "wiki"
    (wiki / "relations").mkdir(parents=True)
    result = answer_query(
        AskOptions(
            query="液冷和PCB谁在上游，关系是什么？",
            exports_dir=tmp_path,
            kb_wiki=wiki,
            use_modules=False,
            use_wiki_rag=False,
            compose=False,
            include_memory_block=False,
            include_recall_block=False,
            include_news_block=False,
            parallel_blocks=False,
        )
    )
    rendered = render_conversation_answer(result)
    assert "图谱暂未提供可核验的“上游”关系边" in rendered
    assert "不能据此拼接产业链关系" in rendered
    assert any(
        trace.provider == "relation_graph_guard" and trace.status == "empty"
        for trace in result.provider_traces
    )
