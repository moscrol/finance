"""09 连续研究：研究项目投影（services/research_project.py）单元测试。

全部用真实 writer（RunStore / ConversationStore / checkpoints.register_checkpoint）构造状态，
再断言只读投影；不 mock 内部函数（教训：mock 点会跟着实现漂）。
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

import pytest

from intelligence.services import checkpoints as checkpoints_svc
from intelligence.services import followups as followups_svc
from intelligence.services import research_project as rp
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.run_store import RunStore


@pytest.fixture()
def users_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "users"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(root))
    monkeypatch.delenv("FORESIGHT_USER", raising=False)
    return root


def _stores(user: str) -> tuple[RunStore, ConversationStore]:
    return RunStore(user_id=user), ConversationStore(user)


def _round(
    run_store: RunStore,
    conv_store: ConversationStore,
    conversation_id: str,
    question: str,
    answer: str,
    *,
    subject: str,
    gaps: tuple[str, ...] = (),
    source_date: str = "2026-09-08",
    continuation: dict[str, object] | None = None,
    citations: int = 1,
    finish: bool = True,
) -> str:
    conversation = conv_store.load_conversation(conversation_id)
    run = run_store.create_run(
        question,
        "ask",
        session_id=conversation_id,
        parent_run_id=conversation.last_run_id,
    )
    conv_store.append_message(
        conversation_id,
        "user",
        question,
        run_id=run.run_id,
        continuation=continuation,
    )
    assistant = conv_store.append_message(
        conversation_id, "assistant", "", status="pending", run_id=run.run_id
    )
    conv_store.update_summary(conversation_id, "", last_run_id=run.run_id)
    if not finish:
        return run.run_id
    for gap in gaps:
        run_store.add_degrade(run.run_id, gap)
    run_store.update_provenance(run.run_id, source_date=source_date)
    run_store.add_artifact(
        run.run_id, "answer.md", answer, renderer="markdown", title="对话回答"
    )
    state = followups_svc.project_continuous_state(
        subject=subject,
        question=question,
        open_gaps=gaps,
        status="degraded" if gaps else "completed",
        question_type="theme_track",
    )
    cards = followups_svc.compose_followups(state).followups
    conv_store.revise_message(
        conversation_id,
        assistant.message_id,
        content=answer,
        status="completed",
        citations=[{"tag": f"E{i}", "source": "本地市场数据"} for i in range(citations)],
        followups=[asdict(card) for card in cards],
        turn_intent={"primary_subject": subject, "question_type": "theme_track"},
    )
    run_store.finish_run(run.run_id, "completed")
    return run.run_id


def test_project_projects_rounds_from_existing_objects(users_root: Path) -> None:
    run_store, conv_store = _stores("alice")
    cid = conv_store.create_conversation("光模块研究").conversation_id
    first = _round(
        run_store,
        conv_store,
        cid,
        "光模块这个题材近三个月怎么演绎",
        "**基准判断：光模块仍是算力链主线。**\n证据见公告。",
        subject="光模块",
        gaps=("1.6T 订单口径",),
    )
    continuation = {
        "run_id": first,
        "kind": "gap_fill",
        "label": "补齐：1.6T 订单口径",
        "inherits": {"subject": "光模块", "standing_date": "2026-09-08"},
    }
    _round(
        run_store,
        conv_store,
        cid,
        "关于光模块，上一轮「1.6T 订单口径」未完成核验",
        "# 1.6T 订单口径已补齐\n来源为两份公告。",
        subject="光模块",
        source_date="2026-09-09",
        continuation=continuation,
        citations=2,
    )

    state = rp.load_project(conv_store, run_store, cid)

    assert [r.index for r in state.rounds] == [1, 2]
    assert len(state.completed_rounds) == 2
    assert state.subject == "光模块"
    assert state.question_type == "theme_track"
    assert state.as_of == "2026-09-09"
    assert state.current_judgment == "1.6T 订单口径已补齐"
    assert state.materials_read == 3
    assert state.artifacts == ("对话回答",)
    assert state.rounds[0].open_gaps == ("1.6T 订单口径",)
    # 运行告警（degrade）与研究缺口分列：缺口来自缺口镜像卡原文，告警来自 run.degrades。
    assert state.rounds[0].warnings == ("1.6T 订单口径",)
    assert state.rounds[0].answer_headline == "基准判断：光模块仍是算力链主线。"
    assert state.rounds[1].continuation == continuation
    assert all(card["kind"] and card["kind_label"] for card in state.rounds[0].followups)
    assert {card["kind"] for card in state.rounds[0].followups} >= {
        "gap_fill",
        "condition_test",
    }
    payload = state.to_dict()
    assert payload["completed_rounds"] == 2
    assert payload["rounds"][1]["continuation"]["kind"] == "gap_fill"


def test_degraded_round_is_not_treated_as_a_judgment(users_root: Path) -> None:
    """真实验收里看到的形状：模型 429 → 降级模板成了「上轮结论标题」。降级轮不算判断。"""
    import json

    run_store, conv_store = _stores("alice")
    cid = conv_store.create_conversation("光模块研究").conversation_id
    _round(run_store, conv_store, cid, "光模块怎么看", "**基准判断：主线延续。**", subject="光模块")
    degraded = _round(
        run_store,
        conv_store,
        cid,
        "再问一次",
        "关于“光模块”，现有证据不足，暂不能可靠回答。仍需核验：产业链层级。",
        subject="光模块",
        gaps=("产业链层级",),
    )
    run_store.add_degrade(degraded, "证据或语义核验未完全通过，已按证据边界降级。")
    run_store.add_artifact(
        degraded,
        "report.json",
        json.dumps({"research_status": "partial", "warnings": []}, ensure_ascii=False),
        renderer="structured_report",
        title="结构化对话报告",
    )
    current = _round(run_store, conv_store, cid, "第三问", "", subject="光模块", finish=False)

    state = rp.load_project(conv_store, run_store, cid, exclude_run_id=current)
    assert state.rounds[1].research_status == "partial"
    assert state.rounds[1].concluded is False
    assert state.rounds[0].concluded is True
    # 当前判断回退到更早那轮真正形成的结论。
    assert state.current_judgment == "基准判断：主线延续。"
    block, _ = rp.prior_for_turn(
        conv_store, run_store, conversation_id=cid, current_run_id=current, subject="光模块"
    )
    assert "上轮未形成可用结论（按证据边界降级），不要把它当既有判断。" in block
    assert "更早一轮的结论标题：基准判断：主线延续。" in block
    assert "现有证据不足" not in block.split("未解问题")[0]
    assert "未解问题：产业链层级" in block


def test_open_questions_come_from_latest_round_with_gaps(users_root: Path) -> None:
    run_store, conv_store = _stores("alice")
    cid = conv_store.create_conversation("缺口").conversation_id
    _round(run_store, conv_store, cid, "问一", "答一", subject="光模块", gaps=("缺口甲",))
    _round(run_store, conv_store, cid, "问二", "答二", subject="光模块")

    state = rp.load_project(conv_store, run_store, cid)

    # 最近一轮没有缺口，就往前找最近有缺口的一轮，不把旧缺口和新缺口混算。
    assert state.open_questions == ("缺口甲",)


def test_prompt_block_empty_without_completed_rounds(users_root: Path) -> None:
    run_store, conv_store = _stores("alice")
    cid = conv_store.create_conversation("首轮").conversation_id
    current = _round(run_store, conv_store, cid, "首问", "", subject="光模块", finish=False)

    state = rp.load_project(conv_store, run_store, cid, exclude_run_id=current)

    assert state.rounds == ()
    assert state.to_prompt_block() == ""
    block, status = rp.prior_for_turn(
        conv_store,
        run_store,
        conversation_id=cid,
        current_run_id=current,
        subject="光模块",
    )
    assert (block, status) == ("", None)


def test_prompt_block_mentions_state_and_stays_bounded(users_root: Path) -> None:
    run_store, conv_store = _stores("alice")
    cid = conv_store.create_conversation("光模块研究").conversation_id
    _round(
        run_store,
        conv_store,
        cid,
        "光模块怎么看",
        "**基准判断：光模块仍是算力链主线。**",
        subject="光模块",
        gaps=("1.6T 订单口径", "北美资本开支指引"),
    )
    _round(run_store, conv_store, cid, "再问", "**订单口径已补齐。**", subject="光模块")
    current = _round(run_store, conv_store, cid, "第三问", "", subject="光模块", finish=False)

    block, status = rp.prior_for_turn(
        conv_store,
        run_store,
        conversation_id=cid,
        current_run_id=current,
        subject="光模块",
        continuation={"kind": "condition_test", "label": "证伪条件"},
    )

    assert block.startswith("## 研究项目状态（跨轮先验，非市场事实）")
    assert "已研究 2 轮" in block
    assert "上轮结论标题：订单口径已补齐。" in block
    assert "未解问题：1.6T 订单口径；北美资本开支指引" in block
    assert "本轮延续：检验条件「证伪条件」" in block
    assert block.rstrip().endswith("以本轮检索为准。")
    assert len(block) <= rp.PROMPT_BLOCK_MAX_CHARS
    assert status is None


def test_verdict_changes_prior_and_reorders_next_questions(users_root: Path) -> None:
    run_store, conv_store = _stores("alice")
    cid = conv_store.create_conversation("光模块研究").conversation_id
    _round(
        run_store,
        conv_store,
        cid,
        "光模块怎么看",
        "**判断：主线延续。**",
        subject="光模块",
        gaps=("1.6T 订单口径",),
    )
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    ck_path = users_root / "alice" / "checkpoints.jsonl"
    _, record = checkpoints_svc.register_checkpoint(
        ck_path,
        claim="若北美云厂商上修资本开支指引，光模块龙头两周内创新高",
        due=yesterday,
        category="题材延续",
        themes=["光模块"],
        session_id=cid,
        metric={"type": "manual"},
    )

    pending = rp.load_project(conv_store, run_store, cid)
    assert pending.triggers[0].id == record["id"]
    assert pending.triggers[0].status == "due"
    assert pending.triggers[0].linked == "conversation"
    assert pending.prior_status == "pending"
    assert "到期待判" in pending.prior_note
    assert pending.next_questions[0]["kind"] == "gap_fill"

    checkpoints_svc.record_verdict(
        users_root / "alice" / "verdicts.jsonl",
        id=record["id"],
        verdict="miss",
        score=0.0,
        reason="两周内未创新高",
    )

    missed = rp.load_project(conv_store, run_store, cid)
    assert missed.triggers[0].status == "miss"
    assert missed.prior_status == "miss"
    assert missed.prior_note.startswith("上次「若北美云厂商上修资本开支指引")
    assert "落空" in missed.prior_note
    assert missed.next_questions[0]["kind"] == "condition_test"
    kinds_before = sorted(card["kind"] for card in pending.next_questions)
    kinds_after = sorted(card["kind"] for card in missed.next_questions)
    assert kinds_before == kinds_after  # 只改先后，不改张数与种类
    block = missed.to_prompt_block()
    assert "已登记可证伪点：「若北美云厂商上修资本开支指引" in block
    assert "→落空" in block
    assert "上次哪个判断让我这次这样查：" in block


def test_topic_switch_returns_empty_unless_continuation(users_root: Path) -> None:
    run_store, conv_store = _stores("alice")
    cid = conv_store.create_conversation("先光模块").conversation_id
    _round(run_store, conv_store, cid, "光模块怎么看", "**判断一。**", subject="光模块")
    current = _round(run_store, conv_store, cid, "农业怎么看", "", subject="农业", finish=False)

    switched = rp.prior_for_turn(
        conv_store,
        run_store,
        conversation_id=cid,
        current_run_id=current,
        subject="农业",
    )
    assert switched == ("", None)

    linked, _ = rp.prior_for_turn(
        conv_store,
        run_store,
        conversation_id=cid,
        current_run_id=current,
        subject="农业",
        continuation={"kind": "alternative_explanation", "label": "同链下一跳"},
    )
    assert "研究项目状态" in linked
    assert "本轮延续：比较替代解释" in linked

    unknown, _ = rp.prior_for_turn(
        conv_store,
        run_store,
        conversation_id=cid,
        current_run_id=current,
        subject="",
    )
    # 当前对象没识别出来时不判换题，沿用本会话项目。
    assert "研究项目状态" in unknown


def test_new_conversation_finds_related_project_by_subject(users_root: Path) -> None:
    run_store, conv_store = _stores("alice")
    old = conv_store.create_conversation("昨天的光模块").conversation_id
    _round(run_store, conv_store, old, "光模块怎么看", "**昨天的判断。**", subject="光模块")
    fresh = conv_store.create_conversation("新对话").conversation_id
    current = _round(run_store, conv_store, fresh, "接着昨天的光模块", "", subject="光模块", finish=False)

    assert rp.find_related_conversation(
        conv_store, subject="光模块", exclude_conversation_id=fresh
    ) == old
    assert (
        rp.find_related_conversation(conv_store, subject="农业", exclude_conversation_id=fresh)
        is None
    )
    block, _ = rp.prior_for_turn(
        conv_store,
        run_store,
        conversation_id=fresh,
        current_run_id=current,
        subject="光模块",
    )
    assert "（来自早先会话「昨天的光模块」）" in block
    assert "上轮结论标题：昨天的判断。" in block


def test_two_users_do_not_share_projects_or_triggers(users_root: Path) -> None:
    alice_runs, alice_convs = _stores("alice")
    alice_cid = alice_convs.create_conversation("光模块").conversation_id
    _round(alice_runs, alice_convs, alice_cid, "光模块怎么看", "**alice 的判断。**", subject="光模块")
    checkpoints_svc.register_checkpoint(
        users_root / "alice" / "checkpoints.jsonl",
        claim="光模块龙头两周内创新高",
        due="2030-01-01",
        themes=["光模块"],
        session_id=alice_cid,
    )

    bob_runs, bob_convs = _stores("bob")
    bob_cid = bob_convs.create_conversation("光模块").conversation_id
    current = _round(bob_runs, bob_convs, bob_cid, "光模块怎么看", "", subject="光模块", finish=False)

    block, status = rp.prior_for_turn(
        bob_convs,
        bob_runs,
        conversation_id=bob_cid,
        current_run_id=current,
        subject="光模块",
    )
    assert (block, status) == ("", None)
    bob_state = rp.load_project(bob_convs, bob_runs, bob_cid, exclude_run_id=current)
    assert bob_state.rounds == ()
    assert bob_state.triggers == ()
    alice_state = rp.load_project(alice_convs, alice_runs, alice_cid)
    assert alice_state.user_id == "alice"
    assert [t.claim for t in alice_state.triggers] == ["光模块龙头两周内创新高"]


def test_continuation_for_run_reads_user_message(users_root: Path) -> None:
    run_store, conv_store = _stores("alice")
    cid = conv_store.create_conversation("延续").conversation_id
    first = _round(run_store, conv_store, cid, "问一", "**答一。**", subject="光模块")
    continuation = {"run_id": first, "kind": "condition_test"}
    second = _round(
        run_store, conv_store, cid, "问二", "", subject="光模块", finish=False, continuation=continuation
    )
    messages = conv_store.load_messages(cid)
    assert rp.continuation_for_run(messages, second) == continuation
    assert rp.continuation_for_run(messages, first) is None
    assert rp.continuation_for_run(messages, "run_missing") is None


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("**基准判断：主线延续。**\n第二行", "基准判断：主线延续。"),
        ("# 标题\n正文", "标题"),
        ("\n\n- 要点一\n", "要点一"),
        ("", ""),
        ("x" * 200, "x" * 79 + "…"),
    ],
)
def test_headline_strips_markdown_and_bounds_length(content: str, expected: str) -> None:
    assert rp.headline_of(content) == expected


def test_gap_from_followup_only_reads_gap_cards() -> None:
    assert rp.gap_from_followup({"type": "gap", "label": "补齐：失效条件"}) == "失效条件"
    assert rp.gap_from_followup({"type": "gap", "label": "其它"}) is None
    assert rp.gap_from_followup({"type": "counter", "label": "补齐：假的"}) is None
    # label 会压缩空格并截到 20 字；full_prompt 里的「…」保留原文，优先取它。
    long_gap = "北美四大云厂商 2026 年资本开支指引是否上修"
    card = {
        "type": "gap",
        "label": "补齐：北美四大云厂商2026年资本开支…",
        "full_prompt": f"关于光模块，上一轮「{long_gap}」未完成核验：请只针对这一项补齐证据。",
    }
    assert rp.gap_from_followup(card) == long_gap


def test_followup_kind_mapping_and_prior_order() -> None:
    assert followups_svc.followup_kind(angle="A", type_="gap") == "gap_fill"
    assert followups_svc.followup_kind(angle="B", type_="alternative") == "alternative_explanation"
    assert followups_svc.followup_kind(angle="C", type_="recheck") == "condition_test"
    assert followups_svc.followup_kind(angle="D", type_="counter") == "condition_test"
    assert followups_svc.followup_kind(angle="", type_="continue") == "continue"
    assert followups_svc.followup_kind(angle="", type_="mystery") == "gap_fill"
    cards = [
        followups_svc.Followup("a", "gap", angle="A"),
        followups_svc.Followup("b", "alternative", angle="B"),
        followups_svc.Followup("c", "counter", angle="D"),
    ]
    assert [c.kind for c in followups_svc.order_by_prior(cards, None)] == [
        "gap_fill",
        "alternative_explanation",
        "condition_test",
    ]
    assert [c.kind for c in followups_svc.order_by_prior(cards, "miss")] == [
        "condition_test",
        "gap_fill",
        "alternative_explanation",
    ]
    assert [c.kind for c in followups_svc.order_by_prior(cards, "pending")][0] == "gap_fill"
    assert followups_svc.prior_kind_rank("hit") is None


def test_compose_attaches_inherits_coordinates() -> None:
    state = followups_svc.project_continuous_state(
        subject="光模块",
        question="光模块怎么看",
        open_gaps=("订单口径",),
        status="degraded",
        standing_date="2026-09-08",
        question_type="theme_track",
    )
    cards = followups_svc.compose_followups(state).followups
    assert cards
    for card in cards:
        assert card.inherits["subject"] == "光模块"
        assert card.inherits["standing_date"] == "2026-09-08"
        assert card.inherits["question_type"] == "theme_track"
        assert card.kind in followups_svc.FOLLOWUP_KINDS
        assert card.kind_label == followups_svc.KIND_LABELS[card.kind]
    # 三分法至少两类，且不是三个同义改写。
    assert len({card.kind for card in cards}) >= 2
    assert len({card.full_prompt for card in cards}) == len(cards)
