from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_protocol import (
    attach_evidence_ordinals,
    evidence_ordinal_table,
)
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
    _project_semantic_evidence,
    _semantic_evidence_projection,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchTaskContract,
)
from intelligence.services.task_frame import TaskFrame
from intelligence.tests.test_episode_semantic_verifier import _judge

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "judge-projection"


def _news_bound_after_unbound(
    *,
    task_frame_hash: str = "projection-offset-hash",
) -> tuple[AgentOutcome, AgentEvidence]:
    unbound_a = AgentEvidence(
        tool="web_search",
        title="未绑定标题甲",
        detail="UNBOUND_A",
        source="https://example.invalid/a",
        content_hash="unbound-a",
    )
    unbound_b = AgentEvidence(
        tool="web_search",
        title="未绑定标题乙",
        detail="UNBOUND_B",
        source="https://example.invalid/b",
        content_hash="unbound-b",
    )
    bound = AgentEvidence(
        tool="news_search",
        title="许继电气：中标国家电网特高压项目 金额合计约12.45亿元",
        detail="2026-07-22 18:13:19 界面新闻",
        source="https://example.invalid/news",
        source_date="2026-07-22",
        content_hash="bound-news",
    )
    outcome = AgentOutcome(
        task_frame_hash=task_frame_hash,
        status="completed",
        draft="【当前判断】电网设备发酵。",
        evidence=(unbound_a, unbound_b, bound),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(1, "task", {"task_frame_hash": task_frame_hash}),
        ),
        bindings=(
            OutputEvidenceBinding("direct_assessment", (bound.content_hash,)),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    return outcome, bound


def _load_fixture_outcome(name: str) -> AgentOutcome:
    payload = json.loads((_FIXTURE_DIR / name).read_text())
    evidence = tuple(
        AgentEvidence(
            tool=str(item.get("tool") or ""),
            title=str(item.get("title") or ""),
            detail=str(item.get("detail") or ""),
            source=str(item.get("source") or ""),
            source_date=item.get("source_date"),
            evidence_tier=str(item.get("evidence_tier") or ""),
            supports=tuple(item.get("supports") or ()),
            contradicts=tuple(item.get("contradicts") or ()),
            independent_key=str(item.get("independent_key") or ""),
            freshness=str(item.get("freshness") or "unknown"),
            content_hash=str(item.get("content_hash") or ""),
        )
        for item in payload["evidence"]
    )
    bindings = tuple(
        OutputEvidenceBinding(
            str(item["output_id"]),
            tuple(item.get("evidence_hashes") or ()),
            gap=str(item.get("gap") or ""),
            basis=str(item.get("basis") or "evidence"),
        )
        for item in payload["bindings"]
    )
    return AgentOutcome(
        task_frame_hash="fixture-hash",
        status="completed",
        draft=str(payload.get("draft") or "fixture"),
        evidence=evidence,
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": "fixture-hash"}),),
        bindings=bindings,
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )


def _registry_by_id(registry: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(row["evidence_id"]): row for row in registry}


def test_projection_reuses_episode_evidence_ordinals() -> None:
    outcome, bound = _news_bound_after_unbound()
    _bindings, registry = _semantic_evidence_projection(outcome)
    ordinals = evidence_ordinal_table(outcome.evidence)
    bound_ids = {ordinals[bound.content_hash]}
    assert {row["evidence_id"] for row in registry} == bound_ids
    assert registry[0]["evidence_id"] != "E1"
    assert registry[0]["evidence_id"] == "E3"


def test_projection_ids_match_model_facing_ids() -> None:
    outcome, _bound = _news_bound_after_unbound()
    ordinals = evidence_ordinal_table(outcome.evidence)
    model_rows = attach_evidence_ordinals(
        [
            {"content_hash": item.content_hash, "title": item.title}
            for item in outcome.evidence
        ],
        ordinals,
    )
    _bindings, registry = _semantic_evidence_projection(outcome)
    bound_hashes = {
        digest
        for binding in outcome.bindings
        for digest in binding.evidence_hashes
    }
    model_ids = {
        str(row["evidence_id"])
        for row in model_rows
        if str(row.get("content_hash") or "") in bound_hashes
    }
    assert {str(row["evidence_id"]) for row in registry} == model_ids
    by_hash = {
        item.content_hash: ordinals[item.content_hash]
        for item in outcome.evidence
        if item.content_hash in bound_hashes
    }
    for row in registry:
        digest = next(
            hash_ for hash_, eid in by_hash.items() if eid == row["evidence_id"]
        )
        assert row["evidence_id"] == ordinals[digest]


def test_projection_carries_title_when_body_lives_in_title() -> None:
    outcome, _bound = _news_bound_after_unbound()
    _bindings, registry = _semantic_evidence_projection(outcome)
    title = str(registry[0].get("title") or "")
    assert "许继电气" in title
    assert "12.45" in title
    assert str(registry[0].get("detail") or "").startswith("2026-07-22")


def test_projection_reports_zero_dropped_chars() -> None:
    frame = TaskFrame(
        raw_question="电网怎么发酵？",
        user_goal="回溯发酵",
        question_type="theme_analysis",
        subject="电网设备",
        subject_kind="theme",
        market_scope="A股",
        timeframe="当前",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="theme_multi_layer_evidence",
        confidence=0.9,
    )
    outcome, _bound = _news_bound_after_unbound(
        task_frame_hash=frame.task_frame_hash
    )
    contract = ResearchTaskContract(
        task_id="projection-stats",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("news_search",), True),
        ),
        allowed_capabilities=("news_search", "web_search"),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=verify_episode_outcome(contract, outcome),
        deadline=ResearchDeadline.from_timeout(5),
    )
    payload = result.to_dict()
    assert payload["projection_dropped_field_chars"] == 0
    assert payload["projection_ordinal_mismatch_count"] == 0
    assert payload["projection_cited_unbound_count"] == 0


def test_repair_refuses_to_wipe_every_required_output() -> None:
    frame = TaskFrame(
        raw_question="电网设备这波是怎么发酵的？",
        user_goal="回溯发酵链路",
        question_type="theme_analysis",
        subject="电网设备",
        subject_kind="theme",
        market_scope="A股",
        timeframe="当前",
        required_outputs=("direct_assessment", "chain_mapping", "counterpoint"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="theme_multi_layer_evidence",
        confidence=0.9,
    )
    evidence = AgentEvidence(
        tool="news_search",
        title="许继电气：中标国家电网特高压项目 金额合计约12.45亿元",
        detail="2026-07-22 18:13:19 界面新闻",
        source="界面新闻",
        source_date="2026-07-22",
        content_hash="wipe-news",
    )
    draft = (
        "【当前判断】据E99，电网设备已发酵到高位。\n"
        "【产业链】据E98，许继电气位于设备中游。\n"
        "【反证】据E97，量能尚未确认放量。\n"
        "以上内容供研究参考。"
    )
    contract = ResearchTaskContract(
        task_id="repair-wipe-floor",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("news_search",), True),
            RequiredOutput("chain_mapping", "链条映射", ("news_search",), True),
            RequiredOutput("counterpoint", "反证", ("news_search",), True),
        ),
        allowed_capabilities=("news_search",),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft=draft,
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=tuple(
            OutputEvidenceBinding(item.output_id, (evidence.content_hash,))
            for item in contract.required_outputs
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    structural = verify_episode_outcome(contract, outcome)
    result = SemanticEpisodeVerifier(
        judge_fn=_judge(False, rejected=(1, 2, 3), issues=("假否证",))
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    blob = " ".join(result.issues)
    assert "repair_wiped_all_outputs" in blob
    assert result.to_dict().get("repair_withheld") is True
    assert "当前判断" in result.public_answer
    assert "产业链" in result.public_answer
    assert result.gap_output_ids == ()
    missing = [
        item.output_id
        for item in result.verified.completion.outputs
        if item.status == "missing"
    ]
    assert missing != ["direct_assessment", "chain_mapping", "counterpoint"]


def test_projection_includes_prose_cited_unbound_evidence() -> None:
    # R-20260821-06（E4 案 live 复现）：正文显式引用注册表真有的证据，只是漏写进
    # bindings 数组 → 判官注册表看不到该卡，按「引用不存在」删掉真因果句。引用
    # 本身就是答案对依赖的声明（比记账数组更显式），投影选集改为
    # 绑定 ∪ 正文可反解引用；未引用未绑定的卡仍不送判官，绑定纪律不放宽。
    outcome, _bound = _news_bound_after_unbound()
    outcome = replace(
        outcome,
        draft="【当前判断】发酵初期（E1 未证实线索）；中标已验证（E3）。",
    )
    _bindings, registry = _semantic_evidence_projection(outcome)
    by_id = _registry_by_id(registry)
    assert set(by_id) == {"E1", "E3"}
    assert "未绑定标题甲" in str(by_id["E1"].get("title") or "")
    # E2 未引用且未绑定：仍然不送判官。
    assert "E2" not in by_id


def test_projection_ignores_lookalike_and_out_of_table_refs() -> None:
    # 越界引用（表里没有 E9）不做模糊纠正，留给判官照旧否证——fail-closed 不变；
    # PE10 / 1.5E8 这类形似 token 不算引用。
    outcome, _bound = _news_bound_after_unbound()
    outcome = replace(
        outcome,
        draft="PE10 偏高；市值 1.5E8；引用 E9 越界。已验证事实见 E3。",
    )
    _bindings, registry = _semantic_evidence_projection(outcome)
    assert {str(row["evidence_id"]) for row in registry} == {"E3"}


def test_prose_cited_rows_keep_ordinal_sentinel_quiet() -> None:
    # D2 哨兵（projection_ordinal_mismatch_count）语义是「绑定集合的发放 id 与
    # 投影 id 是否错位」；引用补送的行不属于绑定集合，不得把哨兵点亮。
    outcome, _bound = _news_bound_after_unbound()
    outcome = replace(outcome, draft="（E1）线索；（E3）中标。")
    _bindings, _registry, telemetry = _project_semantic_evidence(outcome)
    assert telemetry.ordinal_mismatch_count == 0
    assert telemetry.cited_unbound_count == 1


def test_frozen_perovskite_restores_cited_unbound_e4() -> None:
    # 冻结自 run_20260821_171744_929436（2026-08-21 钙钛矿换形探针）：正文 18 处
    # E 引用，绑定覆盖 17 个，唯独 E4（财联社「反式钙钛矿电池实现产业化验证」，
    # 注册表真有）漏绑 → 判官删掉引用它的两句真因果。修后 E4 必须在注册表。
    outcome = _load_fixture_outcome("pv-perovskite-e4.json")
    _bindings, registry, telemetry = _project_semantic_evidence(outcome)
    by_id = _registry_by_id(registry)
    assert "反式钙钛矿" in str(by_id["E4"].get("title") or "")
    assert telemetry.cited_unbound_count == 1
    # 已绑定但未引用的仍在（E13/E30）；未绑定未引用的仍不在（E2/E31）。
    assert "E13" in by_id and "E30" in by_id
    assert "E2" not in by_id and "E31" not in by_id
    assert len(registry) == 20


def test_frozen_b4_keeps_writer_title_on_e31() -> None:
    _bindings, registry = _semantic_evidence_projection(
        _load_fixture_outcome("b4-power-grid.json")
    )
    row = _registry_by_id(registry)["E31"]
    blob = f"{row.get('title') or ''}{row.get('detail') or ''}"
    assert "许继电气" in blob
    assert "12.45" in blob
    outcome = _load_fixture_outcome("b4-power-grid.json")
    assert len(outcome.evidence) - len(registry) == 0


def test_frozen_a3_keeps_writer_e9_as_july_13_not_unbound_e4() -> None:
    outcome = _load_fixture_outcome("a3-lixin-energy.json")
    _bindings, registry = _semantic_evidence_projection(outcome)
    by_id = _registry_by_id(registry)
    e9 = f"{by_id['E9'].get('title') or ''} {by_id['E9'].get('detail') or ''}"
    assert "2026-07-13" in e9
    assert "-2.84" in e9
    assert "E4" not in by_id
    assert len(outcome.evidence) - len(registry) == 9


def test_frozen_b1_keeps_rongda_at_writer_e11() -> None:
    outcome = _load_fixture_outcome("b1-photoresist.json")
    _bindings, registry = _semantic_evidence_projection(outcome)
    by_id = _registry_by_id(registry)
    blob = f"{by_id['E11'].get('title') or ''} {by_id['E11'].get('detail') or ''}"
    assert "容大感光" in blob
    e6 = by_id.get("E6")
    assert e6 is None or "容大感光" not in f"{e6.get('title') or ''}{e6.get('detail') or ''}"
    assert len(outcome.evidence) - len(registry) == 8


def test_frozen_b3_registry_max_id_is_writer_e37() -> None:
    outcome = _load_fixture_outcome("b3-solid-state.json")
    _bindings, registry = _semantic_evidence_projection(outcome)
    max_id = max(int(str(row["evidence_id"])[1:]) for row in registry)
    assert max_id == 37
    assert len(outcome.evidence) - len(registry) == 7
