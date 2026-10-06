"""Cached text access is not a new source, semantic verdict, or compulsory step."""

from dataclasses import replace
from datetime import date
import json

import pytest

from intelligence.services.agent_research import (
    AgentEvidence,
    AgentToolContext,
    evidence_content_hash,
)
from intelligence.services.evidence_read import (
    EvidenceReadCoverage,
    bind_evidence_read_tool,
    evidence_read_enabled,
)
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
from intelligence.services.research_tool_registry import (
    InvalidResearchToolArguments,
    ResearchToolRegistry,
)
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ToolObservation
from intelligence.services.tool_result_budget import (
    MAX_EVIDENCE_DETAIL_CHARS,
    MAX_OBSERVATION_CHARS,
)
from intelligence.runtime.research_progress import (
    ResearchProgressTracker,
    ToolCallDigest,
)

# 模型在普通工具结果里看到 detail 的前 _SEEN 字（截断留一字给省略号）；读页要越过它才算新送达。
# 上限 2026-10-06 由 240 放到 800，下面的偏移量都按常量算，不手抄数。
_SEEN = MAX_EVIDENCE_DETAIL_CHARS - 1


def atom(text="背景" * 170 + "测试材料：交付日期为二月八日，尚未验收。", **kw):
    a = AgentEvidence(
        tool="fixture",
        title="合成测试材料",
        detail=text,
        source="fixture://source-a",
        source_date="2026-01-10",
        evidence_tier="test_material",
        contradicts=("complete",),
        independent_key="original-source",
        **kw,
    )
    return replace(a, content_hash=evidence_content_hash(a))


def tool_context():
    return AgentToolContext(
        ResearchDeadline.from_timeout(30),
        information_cutoff=InformationCutoff(date(2026, 2, 1), "requested"),
    )


def run_read(items, **args):
    spec = bind_evidence_read_tool(presented_evidence=lambda: tuple(items))
    value, _ = spec.parse_arguments({"evidence_id": "E1", **args})
    return spec.runner(value, tool_context())


def project(result, items):
    obs = ToolObservation(
        tool="evidence_read",
        query="read",
        evidence=result.evidence,
        observation=result.observation,
        trace=result.trace,
        evidence_hashes=tuple(a.content_hash for a in result.evidence),
    )
    return FinanceResearchHarness().project_tool_result(
        obs, evidence_so_far=tuple(items), seen_prose=set()
    )


def test_flag_is_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("ASK_EPISODE_EVIDENCE_READ", raising=False)
    assert evidence_read_enabled() is False
    monkeypatch.setenv("ASK_EPISODE_EVIDENCE_READ", "on")
    assert evidence_read_enabled() is True


def test_page_reads_original_tail_and_preserves_identity():
    a = atom()
    r = run_read([a], offset=239, limit=100)
    page = json.loads(r.observation)
    assert page["text"] == a.detail[239:339]
    assert page["next_offset"] == 339
    assert page["total_chars"] == len(a.detail)
    assert r.evidence == (a,)
    assert r.evidence[0].content_hash == a.content_hash
    assert r.evidence[0].source_date == a.source_date
    assert r.evidence[0].independent_key == a.independent_key
    assert r.evidence[0].contradicts == a.contradicts
    assert r.diagnostics == ()


def test_unicode_escape_heavy_pages_survive_actual_projection_losslessly():
    a = atom(('漢🙂\\"\n\t\x00' * 250))
    text, offset, pages = "", 0, 0
    while offset is not None:
        r = run_read([a], offset=offset, limit=600)
        assert len(r.observation) <= MAX_OBSERVATION_CHARS
        view = json.loads(project(r, [a]).model_content)
        page = json.loads(view["observation"])
        text += page["text"]
        assert page["offset"] == offset
        offset = page["next_offset"]
        pages += 1
        assert pages < 100
    assert text == a.detail
    assert pages > 2


def test_can_read_title_without_leaking_control_plane_fields():
    a = replace(atom(internal_locator="PRIVATE_LOCATOR"), title="标题" * 100)
    a = replace(a, content_hash=evidence_content_hash(a))
    r = run_read([a], field="title", offset=119)
    view = project(r, [a]).model_content
    assert json.loads(json.loads(view)["observation"])["text"] == a.title[119:]
    assert "PRIVATE_LOCATOR" not in view
    assert a.content_hash not in view


@pytest.mark.parametrize(
    "args",
    [
        {"evidence_id": "../other-user"},
        {"evidence_id": "a" * 16},
        {"offset": -1},
        {"offset": True},
        {"limit": 0},
        {"limit": 601},
        {"limit": 1.5},
        {"field": "internal_locator"},
        {"path": "/tmp/other"},
    ],
)
def test_invalid_arguments_are_rejected_before_execution(args):
    spec = bind_evidence_read_tool(presented_evidence=lambda: ())
    with pytest.raises(InvalidResearchToolArguments):
        spec.parse_arguments({"evidence_id": "E1", **args})


def test_unknown_id_out_of_range_and_future_are_not_readable():
    a = atom()
    for items, args in [
        ([], {}),
        ([a], {"offset": len(a.detail) + 1}),
        ([replace(a, source_date="2026-03-01")], {}),
    ]:
        with pytest.raises(InvalidResearchToolArguments):
            run_read(items, **args)


def test_registry_requires_separate_explicit_authorization():
    registry = ResearchToolRegistry(
        (bind_evidence_read_tool(presented_evidence=lambda: (atom(),)),)
    )
    assert registry.tool_definitions(allowed=("fixture",)) == []
    assert [
        x["function"]["name"]
        for x in registry.tool_definitions(allowed=("evidence_read",))
    ] == ["evidence_read"]
    assert (
        registry.with_read_scope("material_only").tool_definitions(
            allowed=("evidence_read",)
        )
        == []
    )


def test_delivery_coverage_counts_only_unseen_exact_original_characters():
    a = atom("文" * (_SEEN + 700))
    tracker = EvidenceReadCoverage()
    preview = json.dumps(
        {
            "tool": "fixture",
            "evidence": [{"evidence_id": "E1", "detail": a.detail[:_SEEN] + "…"}],
        }
    )
    assert tracker.observe(preview, evidence=(a,)) == 0

    def observe(offset, limit):
        return tracker.observe(
            project(run_read([a], offset=offset, limit=limit), [a]).model_content,
            evidence=(a,),
        )

    assert observe(0, 600) == 0
    assert observe(_SEEN, 100) == 100
    assert observe(_SEEN, 100) == 0
    assert observe(_SEEN + 50, 100) == 50
    fake = json.loads(project(run_read([a], offset=_SEEN + 261, limit=100), [a]).model_content)
    p = json.loads(fake["observation"])
    p["text"] = "伪" * 100
    fake["observation"] = json.dumps(p)
    assert tracker.observe(json.dumps(fake), evidence=(a,)) == 0


def test_read_progress_is_not_new_evidence_and_does_not_false_stall():
    p = ResearchProgressTracker()
    p.record_call(
        ToolCallDigest(
            "evidence_read", "page1", "duplicate", total_evidence=1, new_read_chars=90
        )
    )
    p.close_batch()
    view = p.model_view()
    assert view["new_evidence"] == view["evidence_total"] == 0
    assert view["new_read_chars"] == 90
    assert view["stalled_batches"] == 0
    p.record_call(
        ToolCallDigest("evidence_read", "same-page", "duplicate", total_evidence=1)
    )
    p.close_batch()
    assert p.model_view()["stalled_batches"] == 1


@pytest.mark.parametrize(
    "enabled,authorized", [(False, True), (True, False), (True, True)]
)
def test_native_episode_wiring_is_gated_and_reread_does_not_mint_evidence(
    monkeypatch, enabled, authorized
):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
    from intelligence.services.provider_observability import ProviderTrace
    from intelligence.services.research_tool_registry import ToolSpec
    from intelligence.tests.test_derived_calculation import _frame, _context

    monkeypatch.setenv("ASK_EPISODE_EVIDENCE_READ", "on" if enabled else "off")
    monkeypatch.setenv("WORKBENCH_RESEARCH_STALL_FINALIZE_BATCHES", "1")
    a = replace(atom("文" * (_SEEN + 700)), tool="financial_data")
    a = replace(a, content_hash=evidence_content_hash(a))
    frame = _frame()
    context = _context(frame, task_id=f"read-native-{enabled}-{authorized}")
    context = replace(
        context,
        contract=replace(
            context.contract,
            allowed_capabilities=("financial_data",)
            + (("evidence_read",) if authorized else ()),
        ),
    )
    spec = ToolSpec(
        name="financial_data",
        capability="financial_data",
        description="合成测试",
        cost="local",
        freshness="original",
        runner=lambda q, c: (
            [a],
            "合成材料已交付",
            ProviderTrace(
                provider="fixture",
                capability="financial_data",
                status="success",
                result_count=1,
            ),
        ),
        contract="合成材料，仅供零网测试",
        io_effect="local_read",
    )

    class Model:
        def __init__(self):
            self.calls = 0
            self.tools = []

        def complete(self, *, messages, tools, timeout):
            self.calls += 1
            self.tools.append([v["function"]["name"] for v in tools])
            if self.calls == 1:
                return ModelTurn(
                    "",
                    (ModelToolCall("get", "financial_data", {"query": "fixture"}),),
                    "scripted",
                )
            if enabled and authorized and self.calls <= 3:
                return ModelTurn(
                    "",
                    (
                        ModelToolCall(
                            f"read-{self.calls}",
                            "evidence_read",
                            {
                                "evidence_id": "E1",
                                "offset": _SEEN + (self.calls - 2) * 100,
                                "limit": 100,
                            },
                        ),
                    ),
                    "scripted",
                )
            return ModelTurn(
                json.dumps(
                    {
                        "status": "completed",
                        "draft": "这是一条合成测试材料。",
                        "gaps": [],
                        "bindings": [
                            {
                                "output_id": "direct_assessment",
                                "evidence_hashes": ["E1"],
                                "basis": "evidence",
                            }
                        ],
                    }
                ),
                (),
                "scripted",
            )

    model = Model()
    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame, context=context, registry=ResearchToolRegistry((spec,))
    )
    assert ("evidence_read" in model.tools[0]) is (enabled and authorized)
    assert len(outcome.evidence) == 1
    assert outcome.evidence[0].content_hash == a.content_hash
    assert outcome.evidence[0].independent_key == a.independent_key
    reads = [
        e.payload
        for e in outcome.events
        if e.kind == "tool_result" and e.payload.get("tool") == "evidence_read"
    ]
    if enabled and authorized:
        assert len(reads) == 2, (outcome.stop_reason, reads)
        assert [
            json.loads(json.loads(r["model_content"])["observation"])["text"]
            for r in reads
        ] == [a.detail[_SEEN:_SEEN + 100], a.detail[_SEEN + 100:_SEEN + 200]]
        assert not any(
            e.kind == "finalization" and e.payload.get("reason") == "research_stalled"
            for e in outcome.events
        )
        assert outcome.usage.tool_calls == 3
    else:
        assert not reads


def test_prefetch_and_full_narrative_are_not_counted_as_new_read_text():
    a = atom("原文" * 300)
    c = EvidenceReadCoverage()
    c.note_complete((a,))
    assert (
        c.observe(
            project(run_read([a], offset=239, limit=200), [a]).model_content,
            evidence=(a,),
        )
        == 0
    )
    c = EvidenceReadCoverage()
    c.observe(
        json.dumps({"tool": "fixture", "observation": "引文：" + a.detail}),
        evidence=(a,),
    )
    assert (
        c.observe(
            project(run_read([a], offset=239, limit=200), [a]).model_content,
            evidence=(a,),
        )
        == 0
    )


def test_clipped_narrative_prefix_also_seeds_delivered_coverage():
    a = atom("原文" * (_SEEN + 300))
    c = EvidenceReadCoverage()
    c.observe(
        json.dumps({"tool": "fixture", "observation": "引文：" + a.detail[:_SEEN + 160] + "…"}),
        evidence=(a,),
    )
    assert (
        c.observe(
            project(run_read([a], offset=_SEEN + 110, limit=100), [a]).model_content,
            evidence=(a,),
        )
        == 50
    )


def test_two_episode_bindings_do_not_share_ordinal_cache_inside_one_query_scope():
    from intelligence.services import query_ledger
    from intelligence.tests.test_derived_calculation import _frame, _context

    a, b = atom("甲" * 300), atom("乙" * 300)
    c = _context(_frame())
    c = replace(
        c,
        contract=replace(
            c.contract, allowed_capabilities=("financial_data", "evidence_read")
        ),
    )
    with query_ledger.query_ledger_scope():
        observed = []
        for item in (a, b):
            registry = ResearchToolRegistry(
                (bind_evidence_read_tool(presented_evidence=lambda item=item: (item,)),)
            )
            r = registry.execute(
                "evidence_read",
                {"evidence_id": "E1", "offset": 239},
                context=c,
                step_id="read",
            )
            observed.append(json.loads(r.observation)["text"])
    assert observed == [a.detail[239:], b.detail[239:]]
