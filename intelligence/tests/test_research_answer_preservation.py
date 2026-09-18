"""Quality review diagnoses research; only the security boundary may withhold it."""
from dataclasses import replace

import pytest

from intelligence.services.agent_research import StructuredObservation
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.session_projection import (
    CAUSE_EVIDENCE_GAP,
    CAUSE_JUDGE_UNAVAILABLE_HELD,
    CAUSE_MODEL_UNAVAILABLE,
    TerminalFacts,
    view,
)
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural


def _verify(frame, structural, judge=None):
    return SemanticEpisodeVerifier(judge_fn=judge or _judge(True)).verify(
        frame=frame, structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )


@pytest.mark.parametrize("draft", [
    "市场仍需观察。若上涨家数不足1500家则降级。",
    "若评分低于27则降级。",
    "市场仍需观察。若主线走弱则降级（E99）。",
    "7月22日（周一）市场仍需观察。",
])
def test_quality_findings_preserve_every_original_sentence(draft):
    frame, structural = _structural(draft)
    result = _verify(frame, structural)
    assert draft in result.public_answer
    assert "核验批注" in result.public_answer
    assert result.status != "completed"
    assert result.to_dict()["delivery_mode"] == "preserved_analysis"
    assert all(row["decision"] != "deleted" for row in result.sentence_verdicts)


def test_judge_rejection_is_visible_not_a_deletion_or_silent_pass():
    draft = "市场成交收缩。政策刺激必然导致板块上涨。"
    frame, structural = _structural(draft)
    result = _verify(frame, structural, _judge(False, rejected=(2,), issues=("第2句缺少因果依据",)))
    assert draft in result.public_answer
    assert "核验批注" in result.public_answer
    assert "政策刺激必然导致板块上涨" in result.public_answer
    assert result.status == "partial"
    assert result.judge_status != "passed"


@pytest.mark.parametrize("judge", [lambda _: None, lambda _: "not json"])
def test_review_outage_preserves_draft_but_not_review_pass(judge):
    draft = "市场成交收缩，优先比较持续强度与回撤风险。"
    frame, structural = _structural(draft)
    result = _verify(frame, structural, judge)
    assert draft in result.public_answer
    assert "未完成" in result.public_answer
    assert result.judge_status == "unavailable"
    assert result.status == "partial"
    assert "暂不能可靠回答" not in result.public_answer


def test_missing_binding_preserves_analysis_without_fabricating_evidence():
    draft = "PCB的持续强度可能更值得研究，仍需同窗数据核对。"
    frame, structural = _structural(draft)
    structural = verify_episode_outcome(
        structural.contract, replace(structural.outcome, bindings=()),
    )
    result = _verify(frame, structural)
    assert draft in result.public_answer
    assert "证据" in result.public_answer
    assert result.verified.missing_outputs == ("direct_assessment",)
    assert result.status == "partial"


def test_unattempted_claim_is_retained_with_explicit_correction():
    draft = "资讯未返回，可能没有催化。市场仍需观察。"
    frame, structural = _structural(draft)
    result = _verify(frame, structural)
    assert draft in result.public_answer
    assert "本轮未查询" in result.public_answer
    assert result.status == "partial"


def test_preservation_does_not_release_foreign_task_draft():
    frame, structural = _structural("其他用户的私有研究内容。")
    frame = replace(frame, raw_question="另一个任务")
    result = _verify(frame, structural)
    assert "其他用户的私有研究内容" not in result.public_answer
    assert result.status != "completed"


def test_private_tokens_and_credentials_are_not_resurrected():
    draft = "市场仍需观察。\nHASH_PRIVATE_SENTINEL 内部取数细节。\napi_key=not-a-real-key\n若评分低于27则降级。"
    frame, structural = _structural(draft)
    result = _verify(frame, structural)
    assert "市场仍需观察。" in result.public_answer
    assert "若评分低于27则降级。" in result.public_answer
    assert "HASH_PRIVATE_SENTINEL" not in result.public_answer
    assert "not-a-real-key" not in result.public_answer


def test_clean_answer_is_unchanged():
    draft = "市场仍需观察。"
    frame, structural = _structural(draft)
    result = _verify(frame, structural)
    assert result.public_answer == draft
    assert result.judge_status == "passed"


@pytest.mark.parametrize("cause", [CAUSE_EVIDENCE_GAP, CAUSE_JUDGE_UNAVAILABLE_HELD, CAUSE_MODEL_UNAVAILABLE])
def test_terminal_projection_never_discards_an_existing_public_body(cause):
    draft = "已完成的分析，不是缺口模板。"
    assert draft in view(TerminalFacts(cause=cause, public=draft))


@pytest.mark.parametrize("secret", [
    "Authorization: Bearer test-only-credential",
    "Bearer sk-test-only-credential",
    "Bearer test-only-credential",
    'api_key="test。secret？suffix"',
    '"authorization": "Digest key=test, signature=private"',
    "password='test\\'。escaped-secret'",
    'access_token="test\nmultiline。secret"',
])
def test_prose_security_boundaries_keep_adjacent_analysis(secret):
    from intelligence.runtime.continuous_turn_adapter import _safe_public_text
    from intelligence.runtime.conversation_orchestrator import (
        sanitize_conversation_answer, sanitize_user_visible_artifact_text,
    )
    from intelligence.services.answer_model import (
        AnswerSpec, present_grounded_composer_answer, present_llm_answer, resolve_answer_profile,
    )
    from intelligence.services.episode_semantic_verifier import _sanitize_public_answer
    from intelligence.services.run_store import redact_public_prose

    spec = AnswerSpec(
        research_spec=resolve_answer_profile("本周市场", profile="causal"),
        summary=(), verified_facts=(), company_table=(), counter_evidence=(),
        gaps=(), triggers=(), next_actions=(), sources=(), system_notices=(),
    )
    before, after = "市场仍需观察。", "板块强度应结合回撤比较。"
    draft = before + secret + "。" + after
    for sanitize in (
        redact_public_prose, _safe_public_text, sanitize_conversation_answer,
        sanitize_user_visible_artifact_text, present_grounded_composer_answer,
        lambda text: present_llm_answer(text, spec),
        lambda text: _sanitize_public_answer(text, (), ()),
    ):
        public = sanitize(draft)
        assert before in public and after in public, (sanitize, public)
        for private in ("credential", "secret", "suffix", "signature=private", "multiline"):
            assert private not in public, (sanitize, public)


@pytest.mark.parametrize("secret", [
    "Bearer sk-test-only-credential", "Bearer [REDACTED]",
    "api_key=test-only-credential", "- [REDACTED]。",
    "api_key=[REDACTED]", "`[REDACTED]`", "**Bearer [REDACTED]**",
    "[REDACTED] / [REDACTED]", "```\n[REDACTED]\n```",
    "```text\n[REDACTED]\n```", '{"api_key": [REDACTED]}',
])
def test_secret_only_public_projection_cannot_count_as_research(secret):
    from intelligence.runtime.continuous_turn_adapter import _safe_public_text
    from intelligence.runtime.conversation_orchestrator import (
        sanitize_conversation_answer, sanitize_user_visible_artifact_text,
    )
    from intelligence.services.answer_model import (
        AnswerSpec, present_grounded_composer_answer, present_llm_answer, resolve_answer_profile,
    )
    from intelligence.services.episode_semantic_verifier import _sanitize_public_answer
    from intelligence.services.run_store import redact_public_prose

    spec = AnswerSpec(
        research_spec=resolve_answer_profile("本周市场", profile="causal"),
        summary=(), verified_facts=(), company_table=(), counter_evidence=(),
        gaps=(), triggers=(), next_actions=(), sources=(), system_notices=(),
    )
    for sanitize in (
        redact_public_prose, _safe_public_text, sanitize_conversation_answer,
        sanitize_user_visible_artifact_text, present_grounded_composer_answer,
        lambda text: present_llm_answer(text, spec),
        lambda text: _sanitize_public_answer(text, (), ()),
    ):
        public = sanitize(secret)
        assert not public.strip(), (sanitize, secret)
        assert sanitize(public) == public


@pytest.mark.parametrize("kind", ["unknown", "single_source", "stale"])
@pytest.mark.parametrize("secret", ["", "Bearer sk-test-only-credential", "api_key=test-only-credential", 'access_token="test\nmultiline。secret"'])
@pytest.mark.parametrize("tail_body", [False, True])
def test_claim_notes_cannot_resurrect_an_empty_or_redacted_claim(kind, secret, tail_body):
    from intelligence.services import answer_model as model

    claim = model.Claim(
        claim_id="known", text="需要核对公司公告。", claim_type="company_evidence",
        theme="市场", evidence_ids=("S1",), status=model.ClaimStatus.VERIFIED,
        independent_source_count=1 if kind == "single_source" else 0,
        freshness="superseded" if kind == "stale" else None,
    )
    spec = model.AnswerSpec(
        research_spec=model.resolve_answer_profile("本周市场", profile="causal"),
        summary=(), verified_facts=(claim,), company_table=(), counter_evidence=(),
        gaps=(), triggers=(), next_actions=(), sources=(model.EvidenceRef("S1", "公告"),),
        system_notices=(),
    )
    atom_id = model.evidence_atoms_from_answer_spec(spec)[0].atom_id
    marker = (
        f"<!-- claim_id={'missing' if kind == 'unknown' else 'known'}; "
        f"evidence_atom_ids={atom_id}; claim_type=fact -->"
    )
    prose = "市场仍需观察。"
    public = model.present_llm_answer(secret + marker + ("\n" + prose if tail_body else ""), spec)
    assert public == (prose if tail_body else "")
    assert model.present_llm_answer(public, spec) == public
    # Notes still apply when the marked sentence actually has public content.
    legitimate = model.present_llm_answer(prose + marker, spec)
    assert legitimate.startswith(prose)
    assert {"unknown": "引用未核验", "single_source": "单源", "stale": "证据已被取代"}[kind] in legitimate


def test_repeated_public_redaction_keeps_analysis_and_ordinary_markdown():
    from intelligence.services.run_store import redact_public_prose
    draft = "## 市场分析\n市场仍需观察。Bearer [REDACTED]。\n\n---\n| 方向 | 判断 |\n| --- | --- |\n| 主线 | 待核验 |"
    expected = draft.replace("Bearer [REDACTED]", "[REDACTED]")
    assert redact_public_prose(draft) == expected
    assert redact_public_prose(expected) == expected
    # Words inside a code fence are still content, not just formatting residue.
    code = "```text\n市场仍需观察。\n[REDACTED]\n```"
    public = redact_public_prose(code)
    assert "市场仍需观察。" in public and public.count("```") == 2


def test_unclosed_quoted_secret_is_withheld_conservatively():
    from intelligence.services.run_store import redact_public_prose
    assert redact_public_prose('市场仍需观察。api_key="test。secret尾部') == "市场仍需观察。[REDACTED]"


def test_validation_excludes_only_exact_runtime_appendix():
    from intelligence.services.research_annotations import (
        annotate_research_answer, research_body_for_validation,
    )
    body = "## q1\n原始分析。\n## q2\n"
    notes = ("## q2 这只是批注，不是第二题的答案。",)
    public = annotate_research_answer(body, notes)
    assert research_body_for_validation(public, notes) == body
    assert research_body_for_validation(public, ()) == public
    assert research_body_for_validation(public, ("其他说明",)) == public
    changed = public.replace("这只是批注", "这一段被下游更改")
    assert research_body_for_validation(changed, notes) == changed
    assert annotate_research_answer(body, ()) == body
    assert annotate_research_answer(body, (*notes, *notes)) == public


def test_late_guided_rejudge_cannot_lift_a_prior_rejection(monkeypatch):
    from intelligence.services import research_contract
    from intelligence.tests.test_v11_judge_guided_retrieval import _kb_card

    now = [0.0]
    monkeypatch.setattr(research_contract.time, "monotonic", lambda: now[0])
    frame, structural = _structural("量能修复。散热升级推动液冷渗透率提升。")
    calls = []
    def judge(request):
        calls.append(request)
        if len(calls) == 1:
            return {"passed": False, "rejected_sentence_indexes": [2], "issues": ["第2句因果无据"]}
        now[0] = 61.0
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame, structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(60),
        retrieve_fn=lambda _query, _seconds: (_kb_card(),),
    )
    assert len(calls) == 2
    assert result.judge_status == "rejected"
    assert result.status == "partial"
    assert result.guided_retrieval.outcome == "retrieved_no_rejudge"
    assert "原稿第2句" in result.public_answer
    assert not any(row["decision"] == "lifted" for row in result.sentence_verdicts)


def test_adapter_rejects_foreign_semantic_outcome_before_public_projection():
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeOutcome
    frame, structural = _structural("当前任务的分析。")
    foreign = replace(
        structural,
        outcome=replace(
            structural.outcome,
            task_frame_hash="foreign",
            draft="外任务私有分析。",
            events=tuple(
                replace(event, payload={**event.payload, "task_frame_hash": "foreign"})
                for event in structural.outcome.events
            ),
        ),
    )
    class Verifier:
        def verify(self, **_kwargs):
            return SemanticEpisodeOutcome(verified=foreign, status="completed", judge_status="passed", public_answer="外任务私有分析。")
    adapter = ContinuousTurnAdapter(runtime=object(), semantic_verifier=Verifier(), mode="on")
    with pytest.raises(ValueError, match="task identity mismatch"):
        adapter._verify_semantics(frame=frame, structural=structural, deadline=ResearchDeadline.from_timeout(5), retrieve_fn=None)


@pytest.mark.parametrize(("reason", "message"), [
    ("no_candidate_claim", "尚未形成对应的可核验回答"),
    ("text_absent", "已取得相关线索，但正文尚未回答这一部分"),
    ("evidence_unbound", "正文已有相关分析，但支持证据尚未核对对应"),
    ("marker_absent", "正文尚未清楚说明这一部分"),
    ("unspecified", "仍需核对回答是否完整"),
    ("", "仍需核对回答是否完整"),
])
def test_completion_notes_use_public_vocabulary_not_arbitrary_diagnostics(reason, message):
    from intelligence.services.episode_factory import public_output_label
    from intelligence.services.task_fulfillment import (
        FulfillmentItem, FulfillmentVerdict, public_fulfillment_notes,
    )
    private = "registry claim TaskFrame /private/diagnostic key=private-value"
    verdict = FulfillmentVerdict("partial", (
        FulfillmentItem("direct_assessment", "fulfilled", gap=private),
        FulfillmentItem("customer_validation", "missing", gap=private, reason_code=reason),
        FulfillmentItem(private, "missing", gap=private, reason_code=reason),
    ))
    notes = public_fulfillment_notes(verdict)
    assert notes == (
        f"给出客户或订单侧的可核验证据：{message}。",
        f"本题第3项要求：{message}。",
    )
    assert public_output_label(private) == ""
    assert private not in "".join(notes)
    assert verdict.to_dict()["items"][1]["gap"] == private
    assert public_fulfillment_notes(FulfillmentVerdict("complete", (verdict.items[0],))) == ()


@pytest.mark.parametrize(("body", "supplement", "expected"), [
    ("原稿。", "", "原稿。"),
    ("原稿。", "原稿。", "原稿。"),
    ("", "补充。", "补充。"),
    ("原稿。", "原稿。补充。", "原稿。补充。"),
    ("原稿。", "修订。", "原稿。\n\n### 补充与修订（原分析保留）\n修订。"),
])
def test_supplements_only_skip_empty_identical_or_exactly_preserved_prefixes(body, supplement, expected):
    from intelligence.services.research_annotations import append_research_supplement
    assert append_research_supplement(body, supplement) == expected


def test_episode_repair_combines_drafts_without_claiming_failed_execution_succeeded():
    from intelligence.runtime.continuous_turn_adapter import _preserve_repair_analysis
    frame, structural = _structural("原稿市场偏弱（E1）。")
    previous = structural.outcome
    candidate = replace(previous, draft="补充：需继续观察量能。", status="partial", stop_reason="repair_deadline_exhausted")
    combined = _preserve_repair_analysis(previous, candidate, task_frame_hash=frame.task_frame_hash)
    assert combined.draft.startswith(previous.draft)
    assert candidate.draft in combined.draft
    assert combined.status == "partial"
    assert combined.stop_reason == "repair_deadline_exhausted"
    assert combined.evidence == previous.evidence
    assert combined.bindings == previous.bindings


@pytest.mark.parametrize("kind", ["foreign_task", "changed_card", "reordered_ordinal", "resurrected_ordinal"])
def test_episode_repair_cannot_rebind_prior_or_candidate_citations(kind):
    from intelligence.runtime.continuous_turn_adapter import _preserve_repair_analysis
    frame, structural = _structural("原稿市场偏弱（E1）。")
    previous = structural.outcome
    candidate = replace(previous, draft="补充分析。")
    card = previous.evidence[0]
    if kind == "foreign_task":
        candidate = replace(candidate, task_frame_hash="foreign", events=tuple(
            replace(event, payload={**event.payload, "task_frame_hash": "foreign"}) for event in candidate.events
        ))
    elif kind == "changed_card":
        candidate = replace(candidate, evidence=(replace(card, detail="另一份同哈希证据"),))
    elif kind == "reordered_ordinal":
        candidate = replace(candidate, evidence=(replace(card, content_hash="new-card"), card))
    else:
        # Appending a retained card must not legitimize the candidate's unknown E1.
        candidate = replace(candidate, draft="补充据E1得出结论。", evidence=())
        previous = replace(previous, draft="原稿暂不判断。")
    with pytest.raises(ValueError, match="repair .*identity"):
        _preserve_repair_analysis(previous, candidate, task_frame_hash=frame.task_frame_hash)


@pytest.mark.parametrize("changes", [
    {"source_date": "2026-08-01"}, {"evidence_tier": "public_web"},
    {"freshness": "current"}, {"supports": ("another_slot",)},
    {"contradicts": ("direct_assessment",)}, {"independent_key": "new-source"},
    {"derived_from": ("new-parent",)}, {"publisher_kind": "official"},
    {"document_type": "disclosure"}, {"internal_locator": "another-private-source"},
    {"observations": (StructuredObservation("市场", "2026-07-22", "amount", 123.0),)},
])
def test_repair_same_hash_cannot_replace_evidence_semantics(changes):
    from intelligence.runtime.continuous_turn_adapter import _preserve_repair_analysis
    frame, structural = _structural("原稿市场偏弱（E1）。")
    original = structural.outcome
    candidate = replace(original, draft="补充。", evidence=(replace(original.evidence[0], **changes),))
    with pytest.raises(ValueError, match="evidence identity changed"):
        _preserve_repair_analysis(original, candidate, task_frame_hash=frame.task_frame_hash)


def test_repair_same_hash_can_update_observational_telemetry_only():
    from intelligence.runtime.continuous_turn_adapter import _preserve_repair_analysis
    frame, structural = _structural("原稿市场偏弱（E1）。")
    original = structural.outcome
    card = replace(
        original.evidence[0], reexcerpted=True, pointer_dropped=2,
        deep_read=True, structural_neighbor_demoted=True,
    )
    candidate = replace(original, draft="补充。", evidence=(card,))
    combined = _preserve_repair_analysis(original, candidate, task_frame_hash=frame.task_frame_hash)
    assert original.draft in combined.draft and candidate.draft in combined.draft
    assert combined.evidence == (card,)


@pytest.mark.parametrize("side", ["previous", "candidate"])
def test_repair_must_not_normalize_duplicate_evidence_identities(side):
    from intelligence.runtime.continuous_turn_adapter import _preserve_repair_analysis
    frame, structural = _structural("原稿市场偏弱（E1）。")
    previous = structural.outcome
    candidate = replace(previous, draft="补充。")
    invalid = previous if side == "previous" else candidate
    invalid = replace(invalid, evidence=invalid.evidence * 2)
    if side == "previous":
        previous = invalid
    else:
        candidate = invalid
    with pytest.raises(ValueError, match="duplicate .*identity"):
        _preserve_repair_analysis(previous, candidate, task_frame_hash=frame.task_frame_hash)


def test_duplicate_bindings_are_rejected_before_a_repair_candidate_exists():
    _, structural = _structural("本题分析。")
    original = structural.outcome
    with pytest.raises(ValueError, match="duplicate output binding"):
        replace(original, bindings=original.bindings * 2)


@pytest.mark.parametrize("basis", ["evidence", "model_reasoning", "user_premise"])
def test_repair_keeps_both_versions_supporting_cards_for_the_same_basis(basis):
    from intelligence.runtime.continuous_turn_adapter import _preserve_repair_analysis
    from intelligence.services.agent_runtime import OutputEvidenceBinding
    frame, structural = _structural("原稿市场偏弱。")
    previous = structural.outcome
    first = previous.evidence[0]
    second = replace(first, content_hash="supplement-card", detail="本轮修复仍需观察。")
    previous = replace(previous, bindings=(OutputEvidenceBinding("direct_assessment", (first.content_hash,), basis=basis),))
    candidate = replace(
        previous, draft="补充。", evidence=(first, second),
        bindings=(OutputEvidenceBinding("direct_assessment", (second.content_hash,), basis=basis),),
    )
    combined = _preserve_repair_analysis(previous, candidate, task_frame_hash=frame.task_frame_hash)
    assert combined.bindings[0].evidence_hashes == (second.content_hash, first.content_hash)
    assert combined.bindings[0].basis == basis
    assert previous.draft in combined.draft and candidate.draft in combined.draft


@pytest.mark.parametrize("conflict", ["basis", "gap"])
def test_repair_does_not_turn_conflicting_binding_into_fulfilled(conflict):
    from intelligence.runtime.continuous_turn_adapter import _preserve_repair_analysis
    frame, structural = _structural("原稿市场偏弱。")
    previous = structural.outcome
    changes = {"basis": "model_reasoning"} if conflict == "basis" else {"gap": "缺少同期证据", "evidence_hashes": ()}
    binding = replace(previous.bindings[0], **changes)
    candidate = replace(previous, draft="补充仍不确定。", bindings=(binding,))
    combined = _preserve_repair_analysis(previous, candidate, task_frame_hash=frame.task_frame_hash)
    assert combined.bindings == (binding,)
    checked = verify_episode_outcome(structural.contract, combined)
    assert checked.verified_status != "completed"
    assert not any(item.status == "fulfilled" for item in checked.completion.outputs)


def test_repair_contract_must_have_same_task_identity_even_without_previous_body():
    from intelligence.runtime.continuous_turn_adapter import _preserve_repair_analysis
    frame, structural = _structural("本题原稿。")
    previous = replace(structural.outcome, draft="", status="partial")
    with pytest.raises(ValueError, match="task identity mismatch"):
        _preserve_repair_analysis(
            previous, structural.outcome, task_frame_hash=frame.task_frame_hash,
            contract=replace(structural.contract, task_frame_hash="foreign"),
        )

