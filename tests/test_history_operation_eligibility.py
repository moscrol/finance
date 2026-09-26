"""The slot whitelist must admit the operators the question actually requires.

Scoping history evidence per output slot is right: an analogue-similarity claim
should rest on an analogue search, not on a ranking. But the whitelist is only
sound if every operator the user's question needs appears somewhere. The four
continuation questions ask for a same-window ranking and a launch-to-peak path,
so rank_history/trace_history must be citable, or a correct answer is blocked.
"""

from datetime import date
from uuid import uuid4

import pytest

from intelligence.services.conversation_store import ConversationStore
from intelligence.services.episode_factory import (
    _ALL_HISTORY_OPERATIONS,
    build_episode_context,
)
from intelligence.services.historical_research.query import OPERATIONS
from intelligence.services.research_contract import InformationCutoff
from tests.test_history_live_seams import FIRST, FOLLOWUPS, _decide


@pytest.fixture
def contracts(tmp_path):
    store = ConversationStore("eligibility", root=tmp_path)
    conversation = store.create_conversation()
    built, previous = [], None
    for turn, question in enumerate((FIRST, *FOLLOWUPS), 1):
        decision = _decide(store, conversation, question, previous, turn - 1)
        previous = decision.turn_intent
        context = build_episode_context(
            decision.task_frame,
            task_id=f"eligibility-{uuid4().hex}",
            capabilities=("finance_query",),
            information_cutoff=InformationCutoff(date(2026, 9, 15), "requested"),
        )
        built.append({item.output_id: item for item in context.contract.required_outputs})
    return built


def test_every_declared_history_operation_is_citable_somewhere(contracts):
    # 每题至少要有一个槽位能装下它真正需要的算子，否则模型做对了也交不出去。
    for turn, outputs in enumerate(contracts, 1):
        gated = {
            output_id: set(item.allowed_history_operations)
            for output_id, item in outputs.items()
            if item.allowed_history_operations
        }
        assert gated, f"Q{turn} 没有任何受控历史槽位"
        citable = set().union(*gated.values())
        assert OPERATIONS[0] in citable  # inspect_history
        missing = {"rank_history", "trace_history"} - citable
        assert not missing, f"Q{turn} 无处引用 {sorted(missing)}；槽位={sorted(gated)}"


def test_process_questions_can_cite_ranking_and_path_in_the_answer_slot(contracts):
    for turn, outputs in enumerate(contracts, 1):
        answer = outputs.get("direct_assessment") or outputs.get("direct_answer")
        assert answer is not None, f"Q{turn} 没有主答槽"
        allowed = set(answer.allowed_history_operations)
        assert {"rank_history", "trace_history"} <= allowed, f"Q{turn} 主答槽={sorted(allowed)}"


def test_analogue_similarity_stays_scoped_to_an_actual_analogue_search(contracts):
    # 放宽不是取消：相似点仍只能由真的做过的类比检索支撑。
    for outputs in contracts:
        assert set(outputs["analog_similarities"].allowed_history_operations) == {
            "find_analogues"
        }


def test_the_fallback_whitelist_does_not_drift_from_the_engine(contracts):
    assert set(_ALL_HISTORY_OPERATIONS) == set(OPERATIONS)


def test_provenance_accepts_exactly_the_engine_operations():
    # 身份校验里那份算子清单也会漂：漏一个，该算子的每张卡都判无效。
    from intelligence.services.agent_research import HISTORY_OPERATIONS

    assert set(HISTORY_OPERATIONS) == set(OPERATIONS)


@pytest.mark.parametrize("operation", sorted(OPERATIONS))
def test_every_operation_can_produce_a_valid_evidence_identity(operation):
    _trace_evidence(operation=operation).history_provenance.validate()


def _trace_evidence(operation: str = "trace_history"):
    """One real trace_history card, built by the production projection."""
    from dataclasses import replace

    from intelligence.services.agent_research import evidence_content_hash
    from intelligence.services.historical_research.episode import _result

    payload = {
        "query_id": "q" * 32,
        "operation": operation,
        "purpose": "retrospective_discovery",
        "status": "research_only",
        "total_matched": 2,
        "returned_count": 2,
        "truncated": False,
        "spec": {"operation": operation, "start": "2026-09-01", "end": "2026-09-15",
                 "entity_codes": ["A.FP"], "entity_kind": "sector"},
        "preview": [{
            "record_kind": "launch_signal", "entity_code": "A.FP", "entity_kind": "sector",
            "signal_date": "2026-09-03", "signal_known_as_of": "2026-09-03",
            "signal_status": "observed", "features": {"return_pct": 5.0},
        }],
    }
    result = _result(payload, result_ref="run-eligibility/history-query-" + "a" * 64 + ".json")
    card = next(
        item for item in result.evidence
        if item.history_provenance is not None and item.history_provenance.row_index == 0
    )
    return replace(card, content_hash=evidence_content_hash(card))


def test_a_correct_trace_answer_is_not_blocked_at_finalization(contracts):
    from intelligence.services.agent_runtime import (
        AgentOutcome,
        AgentUsage,
        EpisodeEvent,
        OutputEvidenceBinding,
    )
    from intelligence.services.episode_issues import IssueCode
    from intelligence.services.episode_verifier import verify_episode_outcome
    from intelligence.services.research_contract import (
        RequiredOutput,
        ResearchTaskContract,
    )

    card = _trace_evidence()
    allowed = contracts[1]["direct_assessment"].allowed_history_operations
    contract = ResearchTaskContract(
        task_id="history-trace-eligibility",
        question=FOLLOWUPS[0],
        subject="板块启动过程",
        subject_kind="theme",
        question_type="comparison_analog",
        required_outputs=(
            RequiredOutput("direct_assessment", "当时谁走强及其启动过程", ("history_query",),
                           allowed_history_operations=allowed),
        ),
        allowed_capabilities=("finance_query",),
        task_frame_hash="history-trace-eligibility",
    )
    verified = verify_episode_outcome(contract, AgentOutcome(
        task_frame_hash="history-trace-eligibility",
        status="completed",
        draft="该板块的启动信号出现在2026-09-03。",
        evidence=(card,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": "history-trace-eligibility"}),),
        bindings=(OutputEvidenceBinding("direct_assessment", (card.content_hash,)),),
        usage=AgentUsage(),
    ))
    assert not any(
        item.code == IssueCode.HISTORY_OPERATION_UNSUPPORTED for item in verified.issue_items
    )
    assert verified.completion.outputs[0].status == "fulfilled"


def _slot_contract(output_id, allowed, question="历史比较"):
    from intelligence.services.research_contract import RequiredOutput, ResearchTaskContract

    return ResearchTaskContract(
        task_id=f"history-{output_id}",
        question=question,
        subject="板块启动过程",
        subject_kind="theme",
        question_type="comparison_analog",
        required_outputs=(
            RequiredOutput(output_id, "说明", ("history_query",), allowed_history_operations=allowed),
        ),
        allowed_capabilities=("finance_query",),
        task_frame_hash=f"history-{output_id}",
    )


def _outcome(contract, cards):
    from intelligence.services.agent_runtime import (
        AgentOutcome,
        AgentUsage,
        EpisodeEvent,
        OutputEvidenceBinding,
    )

    output_id = contract.required_outputs[0].output_id
    return AgentOutcome(
        task_frame_hash=contract.task_frame_hash,
        status="completed",
        draft="结论见原件。",
        evidence=tuple(cards),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": contract.task_frame_hash}),),
        bindings=(
            OutputEvidenceBinding(output_id, tuple(card.content_hash for card in cards)),
        ),
        usage=AgentUsage(),
    )


def test_one_ineligible_citation_is_stripped_not_fatal():
    """引错算子只剪掉那一条引用，不该让整篇有据的回答退成缺口模板。"""
    from intelligence.services.episode_issues import IssueCode
    from intelligence.services.episode_verifier import verify_episode_outcome

    contract = _slot_contract("key_differences", ("trace_history", "compare_cases"))
    legal = _trace_evidence(operation="trace_history")
    illegal = _trace_evidence(operation="find_analogues")
    verified = verify_episode_outcome(contract, _outcome(contract, [legal, illegal]))

    codes = {item.code for item in verified.issue_items}
    assert IssueCode.HISTORY_OPERATION_STRIPPED in codes
    assert IssueCode.HISTORY_OPERATION_UNSUPPORTED not in codes
    output = verified.completion.outputs[0]
    assert output.status == "fulfilled"
    # 剪掉的是那一条，不是整格：合法引用仍然在正文里。
    assert legal.content_hash in output.evidence_ids
    assert illegal.content_hash not in output.evidence_ids


def test_a_slot_with_nothing_eligible_still_blocks():
    from intelligence.services.episode_issues import IssueCode, ReleaseAction, release_action
    from intelligence.services.episode_verifier import verify_episode_outcome

    contract = _slot_contract("analog_similarities", ("find_analogues",))
    verified = verify_episode_outcome(
        contract, _outcome(contract, [_trace_evidence(operation="trace_history")])
    )
    codes = {item.code for item in verified.issue_items}
    assert IssueCode.HISTORY_OPERATION_UNSUPPORTED in codes
    assert release_action(IssueCode.HISTORY_OPERATION_UNSUPPORTED) is ReleaseAction.BLOCK
    assert verified.completion.outputs[0].status == "missing"


def test_forged_identity_still_blocks_even_next_to_legal_evidence():
    """伪造身份与引错算子不同等：账本完整性问题旁边有合法引用也必须拦。"""
    from dataclasses import replace

    from intelligence.services.agent_research import evidence_content_hash
    from intelligence.services.episode_issues import IssueCode
    from intelligence.services.episode_verifier import verify_episode_outcome

    contract = _slot_contract("key_differences", ("trace_history", "compare_cases"))
    legal = _trace_evidence(operation="trace_history")
    # 改了行摘要却没重算证据卡哈希：卡面与内容对不上，这是账本层面的不一致。
    forged = _trace_evidence(operation="compare_cases")
    assert forged.content_hash == evidence_content_hash(forged)
    forged = replace(forged, history_provenance=replace(forged.history_provenance, row_hash="f" * 16))
    verified = verify_episode_outcome(contract, _outcome(contract, [legal, forged]))

    codes = {item.code for item in verified.issue_items}
    assert IssueCode.HISTORY_OPERATION_UNSUPPORTED in codes
    assert IssueCode.HISTORY_OPERATION_STRIPPED not in codes
