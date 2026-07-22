from __future__ import annotations

from intelligence.services import l3_evidence
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_tools import build_episode_registry
from intelligence.services.task_frame import TaskFrame


def test_explicit_l3_capability_is_registered_and_returns_official_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    frame = TaskFrame(
        raw_question="瑞华泰是否已有量产订单",
        user_goal="核验公司端兑现",
        question_type="stock_deep_dive",
        subject="瑞华泰",
        subject_kind="company",
        market_scope="A股",
        timeframe="最近30日",
        required_outputs=("direct_assessment", "evidence_boundary"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_official_evidence",
        confidence=0.95,
    )
    context = build_episode_context(
        frame,
        task_id="l3-episode-test",
        capabilities=("l3_lookup",),
        timeout=30.0,
    )
    monkeypatch.setattr(
        l3_evidence,
        "lookup_l3_company",
        lambda *_args, **_kwargs: l3_evidence.L3EvidenceBundle(
            query="瑞华泰",
            items=[
                l3_evidence.L3EvidenceItem(
                    source_type="cninfo",
                    title="瑞华泰关于项目进展的公告",
                    summary="公告确认嘉兴项目进入试生产阶段。",
                    citation="https://example.invalid/announcement",
                )
            ],
        ),
    )

    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
    )
    observation = registry.execute(
        "l3_lookup",
        "瑞华泰",
        context=context,
        step_id="l3-episode-test:1",
    )

    assert "l3_lookup" in registry.names()
    assert len(observation.evidence) == 1
    assert observation.evidence[0].evidence_tier == "L3"
    assert observation.evidence[0].source.endswith("announcement")
    assert observation.trace.capability == "l3_lookup"
    assert observation.trace.status == "success"
