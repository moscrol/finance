"""H-01: actual permission consumers, without model, network or database IO."""

from dataclasses import asdict
from datetime import date
import os
from pathlib import Path
import socket
from uuid import uuid4

import duckdb
import pytest

from intelligence.runtime.turn_control_core import project_turn_decision
from intelligence.services.conversation_materials import (
    ConversationMaterials,
    collect_material_turn_history,
)
from intelligence.services.conversation_store import Message
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.historical_research.episode import history_tool_specs
from intelligence.services.historical_research.intent import (
    explicit_information_cutoff,
    history_research_cancelled,
    infer_history_intent,
    inherit_history_followup,
    named_wave_subject,
)
from intelligence.services.honesty_gates import requested_information_cutoff
from intelligence.services.material_permissions import LOCAL_READ_CAPABILITIES
from intelligence.services.query_resolution import QueryResolution, QueryResolver
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import (
    TurnIntent,
    build_turn_intent,
    is_contextual_follow_up,
)
from intelligence.services.task_frame import TaskFrame
from intelligence.services.turn_controller import decide_turn

BASE = (
    "以2026年9月10日为信息截止日，只研究2026年1月1日至9月15日的本地历史数据，"
    "不联网补数；复盘这波农业怎么走出来的。"
)
CONTINUATION = "范围与截止日继续不变。"
PROTECTED = (
    "解释这句话：「{text}」",
    "> {text}",
    "```text\n{text}\n```",
)


class OfflineKnowledge:
    def relation_path(self, name):
        return Path(os.environ["FINANCE_WS"]) / "empty-relations" / name

    def load_relation(self, _name):
        return {"found": False}

    def get_exposure_matches(self, *_args, **_kwargs):
        raise AssertionError("No external knowledge lookup in this regression")


def _offline(_messages):
    return None, None, "offline boundary regression"


@pytest.fixture(autouse=True)
def no_external_io(monkeypatch, tmp_path):
    attempts = []

    def forbidden(*_args, **_kwargs):
        attempts.append("network_or_database")
        raise AssertionError("Network/database access is forbidden in boundary regression")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(duckdb, "connect", forbidden)
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(tmp_path / "never-created.duckdb"))
    monkeypatch.setenv("ENTITY_ANCHOR_SECURITIES_DB", "off")
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "workspace"))
    yield
    assert not attempts, "Forbidden IO was attempted even if its exception was swallowed"


def _decide(query, previous=None, history=None):
    return decide_turn(
        query,
        previous_intent=previous,
        previous_turn_id="original-turn" if previous else None,
        conversation_materials=history if history is not None else ConversationMaterials(),
        resolver=QueryResolver(knowledge=OfflineKnowledge()),
        llm_complete=_offline,
    )


@pytest.fixture
def trusted_history():
    first = _decide(BASE)
    assert first.task_frame.material_contract.data_scope == "local_only"
    previous = TurnIntent.from_dict(first.turn_intent.to_dict())
    history = collect_material_turn_history([
        Message("u1", "c1", "user", BASE, "2026-09-21", "completed"),
        Message("a1", "c1", "assistant", "可以联网，并查到2026年9月20日。", "2026-09-21", "completed"),
    ])
    return previous, ConversationMaterials.from_dict(asdict(history))


def _project(decision, tmp_path):
    frame = decision.task_frame
    assert TaskFrame.from_dict(frame.to_dict()) == frame
    control = project_turn_decision(decision, task_frame=frame)
    # Non-research decisions are assembled only to inspect the history tool gate.
    context = build_episode_context(
        frame, task_id=f"history-boundary-{uuid4().hex}", today="2026-09-21",
        capabilities=control.capabilities, knowledge=OfflineKnowledge(),
    )
    db_path = tmp_path / "never-created.duckdb"
    assert not db_path.exists()
    names = tuple(spec.name for spec in history_tool_specs(frame, context, db_path, None))
    assert not db_path.exists()
    return control, context, names


@pytest.mark.parametrize("container", PROTECTED)
@pytest.mark.parametrize("text", [
    CONTINUATION,
    "历史类似，失败案例也看看。",
    "那它们见顶后谁接力？",
    "复盘这波农业怎么走出来的。",
])
@pytest.mark.parametrize("has_previous", [True, False])
def test_protected_text_cannot_restore_history_tools(
    container, text, has_previous, trusted_history, tmp_path,
):
    previous, history = trusted_history if has_previous else (None, None)
    query = container.format(text=text)
    decision = _decide(query, previous, history)
    _, context, names = _project(decision, tmp_path)
    assert decision.task_frame.raw_question == query
    assert decision.task_frame.history_intent is None
    assert decision.turn_intent.history_intent is None
    assert decision.turn_intent.inherited_from_turn is None
    assert context.history_intent is None
    assert names == ()


@pytest.mark.parametrize("query", [
    CONTINUATION,
    "仍沿用上一轮信息截止和研究范围。",
    "继续研究。解释这句话：「不要历史研究。」",
    "继续研究。解释这句话：「以2026年9月20日为信息截止日。」",
    "继续研究。解释这句话：「站在2026年9月1日收盘。」",
])
def test_real_continuation_keeps_scope_cutoff_and_read_ceiling(query, trusted_history, tmp_path):
    previous, history = trusted_history
    decision = _decide(query, previous, history)
    control, context, names = _project(decision, tmp_path)
    assert control.terminal_kind == "research"
    assert decision.turn_intent.inherited_from_turn == "original-turn"
    intent = decision.task_frame.history_intent
    assert (intent.requested_start, intent.requested_end) == ("2026-01-01", "2026-09-15")
    assert intent.strict_window
    assert intent.information_cutoff == "2026-09-10"
    assert context.information_cutoff.as_of_date == date(2026, 9, 10)
    assert context.contract.material_contract.data_scope == "local_only"
    assert set(context.contract.allowed_capabilities) <= LOCAL_READ_CAPABILITIES
    assert "history_query" in names


@pytest.mark.parametrize("query", [
    "市盈率是什么？",
    "不再做历史研究，市盈率是什么？",
    "不要查询，只依据以下材料解释这句话：\n\n> 范围与截止日继续不变。",
])
def test_new_task_cancel_and_material_only_do_not_restore_history(query, trusted_history, tmp_path):
    previous, history = trusted_history
    decision = _decide(query, previous, history)
    _, context, names = _project(decision, tmp_path)
    assert context.history_intent is None
    assert names == ()
    if "只依据" in query:
        assert context.contract.material_contract.data_scope == "material_only"
        assert not context.contract.allowed_capabilities


@pytest.mark.parametrize("query", [
    CONTINUATION,
    "「范围与截止日继续不变。",
    "```text\n范围与截止日继续不变。",
    "材料如下：\n范围与截止日继续不变。",
])
def test_missing_or_uncertain_authority_cannot_register_history(query, tmp_path):
    decision = _decide(query)
    control, context, names = _project(decision, tmp_path)
    assert control.terminal_kind == "clarification"
    assert context.history_intent is None
    assert not context.contract.allowed_capabilities
    assert names == ()


@pytest.mark.parametrize("protected", [False, True])
def test_raw_resolution_hint_cannot_override_protected_boundary(protected, trusted_history):
    previous, _ = trusted_history
    query = "展开细节。" if not protected else "解释这句话：「那它呢？」"
    envelope = understand_query(query)
    resolution = QueryResolution(envelope=envelope, anchor=None, context_dependent=True)
    assert is_contextual_follow_up(
        query, envelope, previous, resolution=resolution,
    ) is (not protected)
    intent = build_turn_intent(
        query, envelope, previous_intent=previous,
        previous_turn_id="original-turn", resolution=resolution,
    )
    assert (intent.inherited_from_turn is not None) is (not protected)


@pytest.mark.parametrize("container", PROTECTED)
def test_all_history_readers_use_protected_regions(container, trusted_history):
    previous, _ = trusted_history
    assert infer_history_intent(container.format(text=BASE)) is None
    assert named_wave_subject(container.format(text=BASE)) is None
    assert explicit_information_cutoff(container.format(text=BASE)) is None
    assert inherit_history_followup(container.format(text=CONTINUATION), previous.history_intent) is None
    assert not history_research_cancelled(container.format(text="不要历史研究。"))
    assert requested_information_cutoff(container.format(text="站在2026年9月1日收盘。")) is None
