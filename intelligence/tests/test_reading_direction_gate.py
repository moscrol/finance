"""读向一致性闸 P0（R-20260825-12，spec §7 #1–#14）。"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from intelligence.runtime.conversation_orchestrator import TurnOrchestrator
from intelligence.runtime.continuous_turn_adapter import ContinuousTurnResult
from intelligence.services.agent_research import StructuredObservation
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.reading_direction_gate import (
    apply_reading_direction_gate,
    collect_direction_observations,
)
from intelligence.services.research_contract import TurnIntent
from intelligence.services.run_store import RunStore
from intelligence.services.task_frame import TaskFrame
from intelligence.services.turn_controller import TurnDecision

STANDING = "2026-08-24"

SEMICONDUCTOR = StructuredObservation(
    subject="半导体",
    as_of=STANDING,
    metric="diff_ratio",
    value=16.25,
)
MEDICINE = StructuredObservation(
    subject="医药",
    as_of=STANDING,
    metric="diff_ratio",
    value=-21.28,
)
MEDICAL = StructuredObservation(
    subject="医药医疗",
    as_of=STANDING,
    metric="diff_ratio",
    value=-20.34,
)
QUANTUM = StructuredObservation(
    subject="量子科技",
    as_of=STANDING,
    metric="diff_ratio",
    value=4.0,
)
AMOUNT_ONLY = StructuredObservation(
    subject="半导体",
    as_of=STANDING,
    metric="amount",
    value=2906.55,
)


def _obs(*items: StructuredObservation) -> tuple[StructuredObservation, ...]:
    return items


def test_signature_has_no_question_type() -> None:
    """#13 变异锁：抄 watch 闸题型参数 → 红。"""

    assert "question_type" not in inspect.signature(apply_reading_direction_gate).parameters


def test_mismatch_semiconductor_shrink_against_positive() -> None:
    """§7 #1：半导体 08-24 缩量 vs +16.25 → mismatch 六字段齐。"""

    text = "半导体 08-24 缩量下跌。"
    receipt = apply_reading_direction_gate(
        text, observations=_obs(SEMICONDUCTOR), standing=STANDING
    )
    assert receipt.applied
    assert receipt.text == text
    assert receipt.checked == 1
    assert len(receipt.mismatches) == 1
    item = receipt.mismatches[0]
    assert item.subject == "半导体"
    assert item.date == STANDING
    assert item.word == "缩量"
    assert item.registered_sign == "+"
    assert item.registered_value == 16.25
    assert "缩量" in item.excerpt


def test_sign_flip_is_mutation_sensitive() -> None:
    """#1 变异：符号判定反转会把正确句判成 mismatch。"""

    text = "半导体 08-24 放量下跌。"
    receipt = apply_reading_direction_gate(
        text, observations=_obs(SEMICONDUCTOR), standing=STANDING
    )
    assert receipt.checked == 1
    assert receipt.mismatches == ()
    flipped = "+" if SEMICONDUCTOR.value < 0 else "-"
    assert flipped != receipt.payload()["mismatches"]  # payload 空列表，不是符号


def test_matching_expand_is_checked_clean() -> None:
    """§7 #2：同数据写放量下跌 → checked+1、无 mismatch。"""

    receipt = apply_reading_direction_gate(
        "半导体 08-24 放量下跌。",
        observations=_obs(SEMICONDUCTOR),
        standing=STANDING,
    )
    assert receipt.checked == 1
    assert receipt.mismatches == ()
    assert receipt.skipped == 0


def test_medicine_does_not_borrow_medical_value() -> None:
    """§7 #3：医药与医药医疗并存，锚到医药用 -21.28。"""

    receipt = apply_reading_direction_gate(
        "医药 当日缩量回踩。",
        observations=_obs(MEDICINE, MEDICAL),
        standing=STANDING,
    )
    assert receipt.checked == 1
    assert receipt.mismatches == ()
    # 变异：contains 会吃到医药医疗 -20.34。精确锚必须用 -21.28 且判对。
    assert MEDICINE.value == -21.28
    assert MEDICAL.value == -20.34


def test_contains_anchor_would_mix_boards() -> None:
    """#3 变异锁：若用 contains，「医药」会吃到「医药医疗」。"""

    text = "医药 当日缩量回踩。"
    receipt = apply_reading_direction_gate(
        text, observations=_obs(MEDICINE, MEDICAL), standing=STANDING
    )
    assert receipt.checked == 1
    # 精确相等：候选「医药」≠「医药医疗」。
    subjects = {obs.subject for obs in _obs(MEDICINE, MEDICAL) if obs.subject in text}
    assert subjects == {"医药"}
    assert "医药医疗" not in text


def test_tech_does_not_anchor_quantum_tech() -> None:
    """§7 #4：稿提科技、注册只有量子科技 → skipped，不是不可见。"""

    receipt = apply_reading_direction_gate(
        "科技 08-24 缩量下跌。",
        observations=_obs(QUANTUM),
        standing=STANDING,
    )
    assert receipt.applied
    assert receipt.skipped == 1
    assert receipt.checked == 0
    assert receipt.mismatches == ()


def test_contains_would_hit_quantum_tech() -> None:
    """#4 变异锁：contains 会把「科技」锚到「量子科技」。"""

    assert "科技" in "量子科技"
    receipt = apply_reading_direction_gate(
        "科技 08-24 缩量下跌。",
        observations=_obs(QUANTUM),
        standing=STANDING,
    )
    assert receipt.mismatches == ()
    assert receipt.skipped == 1


def test_zero_and_conflict_skip() -> None:
    """§7 #5：注册值为 0 skip；同日无值（不注册）skip。"""

    zero = StructuredObservation(
        subject="半导体", as_of=STANDING, metric="diff_ratio", value=0.0
    )
    zero_receipt = apply_reading_direction_gate(
        "半导体 08-24 放量下跌。",
        observations=_obs(zero),
        standing=STANDING,
    )
    assert zero_receipt.applied
    assert zero_receipt.skipped == 1
    assert zero_receipt.checked == 0

    missing = apply_reading_direction_gate(
        "有色 08-24 放量下跌。",
        observations=_obs(SEMICONDUCTOR),
        standing=STANDING,
    )
    assert missing.skipped == 1
    assert missing.checked == 0


def test_multi_date_clause_skips() -> None:
    """§7 #6：连续两天多日期子句 skip。"""

    receipt = apply_reading_direction_gate(
        "医药医疗 08-21 与 08-24 连续两天放量下跌。",
        observations=_obs(MEDICAL),
        standing=STANDING,
    )
    assert receipt.skipped == 1
    assert receipt.checked == 0
    assert receipt.mismatches == ()


def test_two_independent_wrong_sentences_do_not_rewrite() -> None:
    """§7 #7：两句独立单日错句 → 稿字节不变、2 条 mismatch、不占 degrade。"""

    text = "医药 08-24 放量回踩。半导体 08-24 缩量续跌。"
    receipt = apply_reading_direction_gate(
        text,
        observations=_obs(MEDICINE, SEMICONDUCTOR),
        standing=STANDING,
    )
    assert receipt.text == text
    assert len(receipt.mismatches) == 2
    assert receipt.checked == 2


def test_no_direction_words_still_traced_when_gate_open() -> None:
    """§7 #8：门开、无读向词 → checked=0、applied 仍 True。"""

    receipt = apply_reading_direction_gate(
        "结构以电为主，宽度尚可。",
        observations=_obs(SEMICONDUCTOR),
        standing=STANDING,
    )
    assert receipt.applied
    assert receipt.checked == 0
    assert receipt.skipped == 0
    assert receipt.mismatches == ()


def test_gate_closed_without_diff_ratio() -> None:
    """§7 #9：本轮无 diff_ratio → 不 applied。"""

    receipt = apply_reading_direction_gate(
        "半导体 08-24 缩量下跌。",
        observations=_obs(AMOUNT_ONLY),
        standing=STANDING,
    )
    assert not receipt.applied
    assert receipt.checked == 0
    assert receipt.mismatches == ()


def test_internal_exception_returns_empty() -> None:
    """§7 #10：内部异常回空，不改稿。"""

    class Boom(list):
        def __iter__(self):
            raise RuntimeError("boom")

    text = "半导体 08-24 缩量下跌。"
    receipt = apply_reading_direction_gate(
        text, observations=Boom(), standing=STANDING
    )
    assert not receipt.applied
    assert receipt.text == text
    assert receipt.payload() == {
        "checked": 0,
        "skipped": 0,
        "mismatches": [],
    }


def test_negation_skips() -> None:
    """§7 #11：并未放量 / 尚未转正 → skipped。"""

    for text in ("半导体 08-24 并未放量。", "半导体 08-24 尚未转正。"):
        receipt = apply_reading_direction_gate(
            text, observations=_obs(SEMICONDUCTOR), standing=STANDING
        )
        assert receipt.skipped == 1, text
        assert receipt.checked == 0, text
        assert receipt.mismatches == (), text


def test_quoted_profile_excerpt_skips() -> None:
    """§7 #12：引号内画像引文 skip。"""

    receipt = apply_reading_direction_gate(
        "画像写「如果大盘放量回升到 2.6 万亿」。",
        observations=_obs(SEMICONDUCTOR),
        standing=STANDING,
    )
    assert receipt.skipped == 1
    assert receipt.checked == 0


def test_conditional_skips() -> None:
    receipt = apply_reading_direction_gate(
        "看半导体 08-24 能否缩量回踩。",
        observations=_obs(SEMICONDUCTOR),
        standing=STANDING,
    )
    assert receipt.skipped == 1
    assert receipt.checked == 0


def test_live_twin_one_mismatch_one_skip() -> None:
    """§7 #14：5.2 原文双句 → mismatch=1 且 skipped≥1，不是 2。"""

    text = (
        "医药医疗 08-21 与 08-24 连续两天放量下跌（边际量 -16.8/-20.3）。"
        "半导体 08-24 缩量续跌。"
    )
    receipt = apply_reading_direction_gate(
        text,
        observations=_obs(MEDICAL, SEMICONDUCTOR),
        standing=STANDING,
    )
    assert receipt.text == text
    assert len(receipt.mismatches) == 1
    assert receipt.skipped >= 1
    assert receipt.mismatches[0].subject == "半导体"


def test_explicit_positive_same_long_sentence() -> None:
    """同一长句里 08-20 放量（显式、符号为正）应判对。"""

    text = "半导体 08-20 放量大涨双红后，08-21 与 08-24 连续两天缩量。"
    day_0820 = StructuredObservation(
        subject="半导体", as_of="2026-08-20", metric="diff_ratio", value=57.47
    )
    receipt = apply_reading_direction_gate(
        text,
        observations=_obs(day_0820, SEMICONDUCTOR),
        standing=STANDING,
    )
    assert receipt.checked >= 1
    assert all(item.subject != "半导体" or item.date != "2026-08-20" for item in receipt.mismatches)


def test_collect_from_private_artifact() -> None:
    payload = {
        "evidence": [
            {
                "tool": "asof_prefetch",
                "title": "台阶",
                "detail": "",
                "source": "prefetch",
                "observations": [
                    {
                        "subject": "半导体",
                        "as_of": STANDING,
                        "metric": "diff_ratio",
                        "value": 16.25,
                    }
                ],
            }
        ]
    }
    got = collect_direction_observations(payload)
    assert got == _obs(SEMICONDUCTOR)


def _prepare_continuous(tmp_path: Path, query: str):
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run = run_store.create_run(
        query,
        "ask",
        session_id=conversation.conversation_id,
        parent_run_id=conversation.last_run_id,
    )
    conversation_store.append_message(
        conversation.conversation_id,
        "user",
        query,
        run_id=run.run_id,
    )
    assistant = conversation_store.append_message(
        conversation.conversation_id,
        "assistant",
        "",
        status="pending",
        run_id=run.run_id,
    )
    conversation_store.update_summary(
        conversation.conversation_id,
        conversation.summary,
        last_run_id=run.run_id,
    )
    return conversation_store, run_store, conversation, run.run_id, assistant.message_id


def test_general_finance_qa_wires_without_question_type_guard(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """§7 #13：general_finance_qa + diff_ratio + 错句 → 步在场；稿不变。"""

    query = "半导体和医药接下来的走势怎么看"
    conversation_store, run_store, conversation, run_id, assistant_id = (
        _prepare_continuous(tmp_path, query)
    )
    planted = "半导体 08-24 缩量续跌，结构仍弱。"
    frame = TaskFrame(
        raw_question=query,
        user_goal="判断板块走势",
        question_type="general_finance_qa",
        subject="半导体",
        subject_kind="theme",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.9,
    )
    intent = TurnIntent(
        primary_subject=frame.subject,
        secondary_topics=(),
        question_type=frame.question_type,
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
        timeframe=frame.timeframe,
        required_outputs=frame.required_outputs,
        task_frame_hash=frame.task_frame_hash,
    )

    def controller(_query: str, **_kwargs: object) -> TurnDecision:
        return TurnDecision(
            lane="research",
            needs_retrieval=True,
            needs_memory=False,
            needs_template=True,
            question_type=frame.question_type,
            capabilities=("market_news",),
            task_frame=frame,
            turn_intent=intent,
        )

    class Adapter:
        def handle(self, *, frame: TaskFrame, control):
            del frame, control
            return ContinuousTurnResult(
                handled=True,
                status="completed",
                answer=planted,
                as_of=STANDING,
                citations=(),
                warnings=(),
                private_artifact={
                    "evidence": [
                        {
                            "tool": "asof_prefetch",
                            "title": "半导体台阶",
                            "detail": "diff_ratio=+16.25",
                            "source": "prefetch",
                            "observations": [
                                {
                                    "subject": "半导体",
                                    "as_of": STANDING,
                                    "metric": "diff_ratio",
                                    "value": 16.25,
                                }
                            ],
                        }
                    ]
                },
                events=(),
            )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy path must not run")

    orchestrator = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=forbidden,
        route_skills_fn=forbidden,
        lane_answer_fn=forbidden,
        turn_controller_fn=controller,
        continuous_turn_adapter=Adapter(),
    )
    result = orchestrator.run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )
    assert result.status == "completed"
    assert planted in result.content
    run = run_store.load_run(run_id)
    assert "reading_direction_gate" not in list(run.degrades)
    steps = run_store.load_trace(run_id)
    payloads = [
        json.loads(step.get("output_summary") or "{}")
        for step in steps
        if step.get("name") == "reading_direction_gate"
    ]
    assert payloads, "抄 watch 题型守卫会让本步消失"
    assert payloads[-1]["checked"] == 1
    assert len(payloads[-1]["mismatches"]) == 1
    assert payloads[-1]["mismatches"][0]["subject"] == "半导体"
