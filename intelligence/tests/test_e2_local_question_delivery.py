"""Local-only numbered delivery: preserve questions, never grant material-only evidence exemptions.

Offline author regressions. Temporary stores and a deterministic writer exercise
real consumers; these are not P7 natural-model or production acceptance.
"""
import json
from uuid import uuid4

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.episode_finalizer import EpisodeFinalizer
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome, AgentUsage, EpisodeEvent, ModelToolCall, ModelTurn, OutputEvidenceBinding,
)
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_protocol import build_episode_input, validate_episode_finish
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier, recheck_material_public_delivery,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.material_delivery import (
    material_input_output_ids, material_question_outputs,
)
from intelligence.services.material_grounding import ClaimSourceBinding, claim_finish_format
from intelligence.services.material_permissions import LOCAL_READ_CAPABILITIES
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import (
    ResearchContractError, ResearchDeadline, ResearchTaskContract,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry, ToolRunResult, ToolSpec,
)

QUERY = (
    "不要联网。\n\n"
    "1. 2026年7月24日市场成交额是多少？\n\n"
    "2. 写一份不超过200字的备忘录，说明本地数据口径。"
)
ANSWER = (
    "## q1\n当日成交额为22000亿元。[E1]\n\n"
    "## q2\n本地快照记录当日成交额22000亿元，仅代表该快照口径。[E1]\n\n"
    "## 证据边界\n本答复仅使用该日本地市场快照。[E1]"
)
GAP = "缺少历史成交额序列，无法判断成交是否持续扩大。"
GAP_Q1 = "缺少 2026 年 7 月 24 日的本地成交额快照，无法给出当日金额。"


def setup(query=QUERY):
    frame = understand_query(query).task_frame
    context = build_episode_context(
        frame, task_id="local-questions-" + uuid4().hex,
        capabilities=("finance_query",), today="2026-07-24", latest_data_date="2026-07-24",
    )
    return frame, context


def evidence(effect="local_read"):
    return AgentEvidence(
        "finance_query", "本地市场快照", "2026-07-24 成交额22000亿元", "local-fixture",
        content_hash="local-observation", io_effect=effect,
    )


def finish_payload(context, *, draft=ANSWER):
    return {
        "status": "completed", "draft": draft, "gaps": [],
        "bindings": [
            {"output_id": item.output_id, "basis": item.grounding_mode,
             "evidence_hashes": ["E1"], "gap": ""}
            for item in context.contract.required_outputs if item.required
        ],
    }


def outcome(context, payload=None, *, effect="local_read"):
    raw = finish_payload(context) if payload is None else payload
    return AgentOutcome(
        task_frame_hash=context.contract.task_frame_hash, status=raw["status"],
        draft=raw["draft"], evidence=(evidence(effect),), traces=(), gaps=(),
        stop_reason="model_finish", usage=AgentUsage(),
        events=(EpisodeEvent(1, "task", {"task_frame_hash": context.contract.task_frame_hash}),),
        bindings=tuple(OutputEvidenceBinding(
            row["output_id"], ("local-observation",) if row["evidence_hashes"] else (),
            gap=row["gap"], basis=row["basis"],
            claims=tuple(ClaimSourceBinding.from_dict(item) for item in row.get("claims", ())),
        ) for row in raw["bindings"]),
    )


def passing(request):
    return {"passed": True, "rejected_sentence_indexes": [], "issues": []}


def test_local_numbered_contract_preserves_original_questions_and_read_ceiling():
    frame, context = setup()
    contract = context.contract
    assert [item.output_id for item in contract.required_outputs] == ["answer_q1", "answer_q2", "evidence_boundary"]
    assert [item.description for item in contract.required_outputs[:2]] == [q.text for q in frame.material_contract.questions]
    assert all(item.required and item.grounding_mode == "evidence" for item in contract.required_outputs)
    # 本地题保留读取权限，但只保留本地白名单内的能力；逐题槽照常挂工具证据类型。
    assert contract.allowed_capabilities and set(contract.allowed_capabilities) <= set(LOCAL_READ_CAPABILITIES)
    assert all(item.evidence_types == contract.allowed_capabilities for item in contract.required_outputs)
    assert contract.evidence_plan.requirements
    assert all(item.capability in contract.allowed_capabilities for item in contract.evidence_plan.requirements)
    assert ResearchTaskContract.from_dict(contract.to_dict()) == contract


def test_writer_and_finalizer_get_question_shape_without_zero_read_exemption():
    frame, context = setup()
    payload = json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))
    delivery = payload["material_delivery"]
    assert [(row["question_id"], row["output_id"]) for row in delivery["questions"]] == [("q1", "answer_q1"), ("q2", "answer_q2")]
    assert delivery["questions"][1]["delivery_kind"] == "memo"
    assert delivery["questions"][1]["max_chars"] == 200
    assert "local_only" in delivery["rules"] and "legal_gap" not in delivery["rules"]
    assert material_input_output_ids(context.contract) == frozenset()
    assert claim_finish_format(context.contract) is None
    calls = []

    class FinalWriter:
        def complete(self, *, messages, tools, timeout):
            calls.append(json.loads(messages[1]["content"]))
            return ModelTurn(json.dumps(finish_payload(context)), (), "offline", "")

    EpisodeFinalizer(FinalWriter()).recover(
        task_frame=frame, context=context, evidence=(evidence(),), gaps=(), failure_reason="model_exception",
    )
    assert calls[0]["material_delivery"] == delivery


@pytest.mark.parametrize("mutation", ["omit", "duplicate", "title_only", "quoted_only", "memo_overflow"])
def test_complete_bindings_do_not_hide_missing_or_invalid_question_bodies(mutation):
    _, context = setup()
    bad = {
        "omit": ANSWER.replace("## q2\n本地快照记录当日成交额22000亿元，仅代表该快照口径。[E1]\n\n", ""),
        "duplicate": ANSWER + "\n\n## q2\n重复回答。",
        "title_only": ANSWER.replace("本地快照记录当日成交额22000亿元，仅代表该快照口径。[E1]", ""),
        "quoted_only": ANSWER.replace("本地快照记录当日成交额22000亿元，仅代表该快照口径。[E1]", "> 只引用旧答，不交付正文。"),
        "memo_overflow": ANSWER.replace("本地快照记录当日成交额22000亿元，仅代表该快照口径。[E1]", "甲" * 201),
    }[mutation]
    payload = finish_payload(context, draft=bad)
    with pytest.raises(ValueError, match="answer_q2"):
        validate_episode_finish(payload, context=context, evidence=(evidence(),))
    checked = verify_episode_outcome(context.contract, outcome(context, payload))
    assert checked.verified_status == "partial" and "answer_q2" in checked.missing_outputs


@pytest.mark.parametrize("effect", ["local_read", "unknown", "external_or_mixed"])
def test_numbered_delivery_does_not_relax_source_io_purity(effect):
    _, context = setup()
    raw = finish_payload(context)
    if effect == "local_read":
        assert validate_episode_finish(raw, context=context, evidence=(evidence(effect),)).status == "completed"
        assert verify_episode_outcome(context.contract, outcome(context, effect=effect)).verified_status == "completed"
    else:
        with pytest.raises(ValueError, match="frozen data scope"):
            validate_episode_finish(raw, context=context, evidence=(evidence(effect),))
        assert verify_episode_outcome(context.contract, outcome(context, effect=effect)).verified_status == "partial"


def test_local_gaps_are_not_material_legal_gaps_or_completed():
    _, context = setup()
    raw = finish_payload(context, draft=ANSWER.replace(
        "本地快照记录当日成交额22000亿元，仅代表该快照口径。[E1]", GAP,
    ))
    raw["bindings"][1].update(evidence_hashes=[], gap=GAP)
    with pytest.raises(ValueError, match="missing_evidence|required output lacks evidence"):
        validate_episode_finish(raw, context=context, evidence=(evidence(),))
    raw["status"] = "partial"
    parsed = validate_episode_finish(raw, context=context, evidence=(evidence(),))
    assert parsed.status == "partial" and not parsed.draft.startswith("仅凭本轮材料")
    checked = verify_episode_outcome(context.contract, outcome(context, raw))
    assert checked.verified_status == "partial"
    assert "answer_q2" in checked.missing_outputs
    assert not any(item.status == "legal_gap" for item in checked.completion.outputs)


def test_all_gap_local_turn_is_not_framed_as_a_material_shortage():
    """「仅凭本轮材料」是 material_only 的公开口径；本地题本可以去读，不能借这句免责。"""
    _, context = setup()
    raw = finish_payload(context, draft=ANSWER.replace(
        "当日成交额为22000亿元。[E1]", GAP_Q1,
    ).replace("本地快照记录当日成交额22000亿元，仅代表该快照口径。[E1]", GAP))
    raw["status"] = "partial"
    raw["bindings"][0].update(evidence_hashes=[], gap=GAP_Q1)
    raw["bindings"][1].update(evidence_hashes=[], gap=GAP)
    parsed = validate_episode_finish(raw, context=context, evidence=(evidence(),))
    assert "仅凭本轮材料" not in parsed.draft and parsed.draft.startswith("## q1")
    checked = verify_episode_outcome(context.contract, outcome(context, raw))
    assert checked.verified_status == "partial"
    assert {"answer_q1", "answer_q2"} <= set(checked.missing_outputs)


def test_local_answer_cannot_complete_with_only_reasoning_claims():
    _, context = setup()
    raw = finish_payload(context)
    raw["bindings"][0].update(evidence_hashes=[], claims=[ClaimSourceBinding("仅做方法说明。", "reasoning").to_dict()])
    raw["draft"] = ANSWER.replace("当日成交额为22000亿元。[E1]", "仅做方法说明。")
    with pytest.raises(ValueError, match="required output lacks evidence"):
        validate_episode_finish(raw, context=context, evidence=(evidence(),))
    checked = verify_episode_outcome(context.contract, outcome(context, raw))
    assert "answer_q1" in checked.missing_outputs


@pytest.mark.parametrize("mutation", ["remove", "optional", "reasoning"])
def test_restore_cannot_erase_or_weaken_a_local_question(mutation):
    _, context = setup()
    raw = context.contract.to_dict()
    if mutation == "remove":
        raw["required_outputs"] = raw["required_outputs"][1:]
    elif mutation == "optional":
        raw["required_outputs"][0]["required"] = False
    else:
        raw["required_outputs"][0]["grounding_mode"] = "model_reasoning"
    with pytest.raises(ResearchContractError, match="local_only"):
        ResearchTaskContract.from_dict(raw)


def test_semantic_and_final_public_projection_keep_question_ownership():
    frame, context = setup()
    calls = []
    result = SemanticEpisodeVerifier(judge_fn=lambda request: (calls.append(request), passing(request))[1]).verify(
        frame=frame, structurally_verified=verify_episode_outcome(context.contract, outcome(context)),
        deadline=ResearchDeadline.from_timeout(60),
    )
    assert result.status == "completed", result.issues
    assert calls[0]["material_delivery"]["question_states"] == {"q1": "answered", "q2": "answered"}
    assert "material_claims" not in calls[0] and "material_outputs" not in calls[0]
    projected = result.public_answer.split("## q2")[0]
    checked = recheck_material_public_delivery(result, projected=projected)
    assert checked.status == "partial" and "answer_q2" in checked.repair_output_ids


def test_local_gap_keeps_ordinary_partial_review_instead_of_material_only_settlement():
    frame, context = setup()
    raw = finish_payload(context, draft=ANSWER.replace(
        "本地快照记录当日成交额22000亿元，仅代表该快照口径。[E1]", GAP,
    ))
    raw["status"] = "partial"
    raw["bindings"][1].update(evidence_hashes=[], gap=GAP)
    calls = []
    result = SemanticEpisodeVerifier(judge_fn=lambda request: (calls.append(request), passing(request))[1]).verify(
        frame=frame, structurally_verified=verify_episode_outcome(context.contract, outcome(context, raw)),
        deadline=ResearchDeadline.from_timeout(60),
    )
    assert calls and result.status == "partial"
    assert "answer_q2" in result.verified.missing_outputs


def test_local_unnumbered_and_full_numbered_tasks_keep_existing_slot_shape():
    for query in ("不要联网。今天市场怎么样？", QUERY.replace("不要联网。", "可以查真实数据。")):
        _, context = setup(query)
        assert not material_question_outputs(context.contract)
        assert not any(item.output_id.startswith("answer_q") for item in context.contract.required_outputs)


def _slot_shape(query):
    return [(item.output_id, item.required) for item in setup(query)[1].contract.required_outputs]


def test_local_unnumbered_task_matches_the_ordinary_slot_shape():
    """未编号本地题不走逐题分支：槽位与同题普通形状一致，不被压成只剩 evidence_boundary。

    2026-09-27 接手复核撤保护：把工厂分支的 ``and material.questions`` 换成恒真，
    上一条只查「没有 answer_q*」仍然全绿；对照普通形状才会变红。
    """
    assert _slot_shape("不要联网。今天市场怎么样？") == _slot_shape("今天市场怎么样？")


def test_pre_numbering_local_contract_still_restores():
    """跨轮恢复的判据是「合同里已有 answer_q*」，不是「有编号问题」。

    本改动之前落盘的 local_only 会话带编号问题、却是普通槽位形状；恢复时不得因缺
    answer_qN 集体报错。2026-09-27 接手复核撤保护：判据换成恒真，原有测试全绿，这条变红。
    """
    legacy = setup("不要联网。今天市场怎么样？")[1].contract.to_dict()
    legacy["material_contract"]["questions"] = setup()[1].contract.to_dict()["material_contract"]["questions"]
    restored = ResearchTaskContract.from_dict(legacy)
    assert len(restored.material_contract.questions) == 2
    assert not any(item.output_id.startswith("answer_q") for item in restored.required_outputs)


def test_real_episode_reads_local_source_then_delivers_numbered_answers():
    frame, context = setup()
    reads = []

    def runner(arguments, context):
        reads.append(arguments)
        return ToolRunResult((evidence(),), evidence().detail, ProviderTrace("offline", "finance_query", "ok"))

    registry = ResearchToolRegistry((ToolSpec(
        "finance_query", "finance_query", "fixture local read", "local", "stable", runner, io_effect="local_read",
    ),))

    class Writer:
        def __init__(self):
            self.calls = 0

        def complete(self, *, messages, tools, timeout):
            self.calls += 1
            if self.calls == 1:
                payload = json.loads(messages[1]["content"])
                assert [row["output_id"] for row in payload["material_delivery"]["questions"]] == ["answer_q1", "answer_q2"]
                return ModelTurn("", (ModelToolCall("local-call", "finance_query", {"query": "fixture"}),), "offline", "")
            return ModelTurn(json.dumps(finish_payload(context)), (), "offline", "")

    writer = Writer()
    result = ContinuousAgentEpisode(writer).run(task_frame=frame, context=context, registry=registry)
    assert reads and writer.calls == 2
    assert result.status == "completed", result.stop_reason
    assert [item.output_id for item in result.bindings] == ["answer_q1", "answer_q2", "evidence_boundary"]
    assert result.evidence[0].io_effect == "local_read"
