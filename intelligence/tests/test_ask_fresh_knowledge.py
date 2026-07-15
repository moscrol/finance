from __future__ import annotations

from intelligence.services import ask, web_research
from intelligence.services.closed_loop_retrieval import (
    BucketedHit,
    ClosedLoopRetrievalResult,
)
from intelligence.services.kb_rag import WikiHit
from intelligence.services.provider_observability import ProviderTrace


def test_latest_knowledge_query_adds_web_even_when_local_knowledge_matches(
    monkeypatch,
) -> None:
    local_hit = WikiHit(
        page_id="pqc",
        file_path="wiki/pqc.md",
        title="PQC 背景",
        score=1.0,
        excerpt="PQC 是后量子密码标准体系。",
        best_chunk_id="chunk-1",
    )
    monkeypatch.setattr(
        ask.closed_loop_retrieval,
        "retrieve_closed_loop",
        lambda *args, **kwargs: ClosedLoopRetrievalResult(
            conclusion=[BucketedHit("narrow", local_hit)]
        ),
    )
    monkeypatch.setattr(
        ask.web_research,
        "fetch_web_search",
        lambda query: web_research.WebSearchResult(
            items=(
                web_research.WebSearchItem(
                    title="PQC migration update",
                    url="https://example.com/pqc",
                    snippet="Organizations are publishing migration timelines.",
                ),
            ),
            trace=ProviderTrace(
                provider=web_research.PROVIDER_BING_WEB,
                capability="general_web_search",
                status="success",
                result_count=1,
            ),
        ),
    )

    result = ask.answer_query(
        ask.AskOptions(
            query="PQC最新消息",
            question_type_override="concept_definition",
            compose=False,
            synthesize=False,
        )
    )

    assert [citation.tag for citation in result.citations] == ["W1", "E1"]
    assert [trace.status for trace in result.provider_traces] == [
        "success",
        "success",
    ]
