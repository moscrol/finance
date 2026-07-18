from __future__ import annotations

from dataclasses import dataclass

from intelligence.services import evidence_judge, evidence_providers
from intelligence.services.closed_loop_retrieval import (
    BucketedHit,
    ClosedLoopRetrievalResult,
)
from intelligence.services.kb_rag import WikiHit


@dataclass
class _Options:
    query: str


@dataclass
class _Ctx:
    options: _Options


def _hit(title: str) -> WikiHit:
    return WikiHit(
        page_id=title,
        file_path=f"wiki/{title}.md",
        title=title,
        score=0.2,
        excerpt=f"{title} 的摘录，含支撑一词",
        best_chunk_id=f"{title}-c1",
    )


def _loop() -> ClosedLoopRetrievalResult:
    loop = ClosedLoopRetrievalResult()
    relevant = BucketedHit("narrow", _hit("科创50指数分析"))
    noise = BucketedHit("narrow", _hit("兰花科创"))
    counter_noise = BucketedHit("counter", _hit("世昌股份"))
    loop.conclusion.extend([relevant, noise])
    loop.counter_clues.append(counter_noise)
    loop.clues.append(counter_noise)
    return loop


def test_semantic_judge_moves_irrelevant_hits_to_discarded(monkeypatch) -> None:
    loop = _loop()
    monkeypatch.setattr(evidence_judge, "should_judge", lambda: True)
    monkeypatch.setattr(
        evidence_judge,
        "judge_relevance",
        lambda query, candidates, **kwargs: ({0}, "公司召回与指数问题无关"),
    )

    evidence_providers._apply_semantic_judge(
        _Ctx(_Options("科创50的支撑点位在哪")), loop
    )

    assert [item.hit.title for item in loop.conclusion] == ["科创50指数分析"]
    assert loop.counter_clues == []
    assert loop.clues == []
    assert {item.hit.title for item in loop.discarded} == {"兰花科创", "世昌股份"}
    assert any("语义闸门丢弃 2 条" in warning for warning in loop.warnings)


def test_semantic_judge_fails_open(monkeypatch) -> None:
    loop = _loop()
    monkeypatch.setattr(evidence_judge, "should_judge", lambda: True)
    monkeypatch.setattr(
        evidence_judge,
        "judge_relevance",
        lambda query, candidates, **kwargs: None,
    )

    evidence_providers._apply_semantic_judge(
        _Ctx(_Options("科创50的支撑点位在哪")), loop
    )

    assert len(loop.conclusion) == 2
    assert len(loop.counter_clues) == 1
    assert loop.discarded == []
    assert loop.warnings == []


def test_semantic_judge_disabled_is_noop(monkeypatch) -> None:
    loop = _loop()
    monkeypatch.setenv(evidence_judge.ENV_MODE, "off")

    evidence_providers._apply_semantic_judge(
        _Ctx(_Options("科创50的支撑点位在哪")), loop
    )

    assert len(loop.conclusion) == 2
    assert loop.discarded == []
