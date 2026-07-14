import json
from typing import get_type_hints
from unittest.mock import patch

import pytest

from intelligence.services.conversation_store import (
    ConversationDataIntegrityError,
    ConversationStore,
    Message,
)


def test_citations_runtime_type_hints_use_object_values():
    assert get_type_hints(Message)["citations"] == list[dict[str, object]]
    assert get_type_hints(ConversationStore.append_message)["citations"] == (
        list[dict[str, object]] | None
    )


def test_rejects_top_level_non_dict_citation(tmp_path):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()

    with pytest.raises(TypeError, match="citation 必须是 JSON object"):
        store.append_message(
            conversation.conversation_id,
            "assistant",
            "回答",
            citations=["not-an-object"],  # type: ignore[list-item]
        )


def test_create_append_reload_and_archive_preserves_messages(tmp_path):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation("研究 sk-secretvalue")
    message = store.append_message(conversation.conversation_id, "user", "你好")

    reloaded = ConversationStore("alice", root=tmp_path)
    loaded = reloaded.load_conversation(conversation.conversation_id)
    assert loaded.title == "研究 [REDACTED]"
    assert reloaded.load_messages(conversation.conversation_id) == [message]

    conversation_dir = tmp_path / conversation.conversation_id
    assert (conversation_dir / "conversation.json").is_file()
    assert not (conversation_dir / "metadata.json").exists()

    archived = reloaded.archive_conversation(conversation.conversation_id)
    assert archived.status == "archived"
    assert reloaded.load_messages(conversation.conversation_id) == [message]


def test_terminal_answer_snapshot_metadata_round_trips_and_old_records_remain_readable(
    tmp_path,
):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    pending = store.append_message(
        conversation.conversation_id,
        "assistant",
        "草稿",
        status="pending",
    )

    completed = store.revise_message(
        conversation.conversation_id,
        pending.message_id,
        content="终稿",
        status="completed",
        answer_revision=2,
        answer_phase="validated_synthesis",
        answer_final=True,
    )

    assert completed.answer_revision == 2
    assert completed.answer_phase == "validated_synthesis"
    assert completed.answer_final is True
    assert store.load_messages(conversation.conversation_id) == [completed]

    path = tmp_path / conversation.conversation_id / "messages.jsonl"
    old_record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert "answer_revision" not in old_record
    assert "answer_phase" not in old_record
    assert "answer_final" not in old_record


@pytest.mark.parametrize(
    ("revision", "phase", "final"),
    [
        (0, "validated_synthesis", True),
        (2, "unknown", True),
        (2, "verified_draft", False),
        (2, "verified_fallback", False),
    ],
)
def test_rejects_invalid_persisted_terminal_answer_metadata(
    tmp_path, revision, phase, final
):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()

    with pytest.raises((TypeError, ValueError), match="answer"):
        store.append_message(
            conversation.conversation_id,
            "assistant",
            "回答",
            answer_revision=revision,
            answer_phase=phase,
            answer_final=final,
        )


@pytest.mark.parametrize(
    ("role", "status"),
    [
        ("assistant", "pending"),
        ("assistant", "failed"),
        ("assistant", "cancelled"),
        ("user", "completed"),
    ],
)
def test_rejects_terminal_answer_metadata_outside_completed_assistant_messages(
    tmp_path, role, status
):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()

    with pytest.raises(ValueError, match="answer.*assistant.*completed"):
        store.append_message(
            conversation.conversation_id,
            role,
            "回答",
            status=status,
            answer_revision=2,
            answer_phase="verified_fallback",
            answer_final=True,
        )


@pytest.mark.parametrize(
    "corrupt_metadata",
    [
        {"answer_revision": 2},
        {
            "answer_revision": 2,
            "answer_phase": "unknown",
            "answer_final": True,
        },
        {
            "answer_revision": 1,
            "answer_phase": "verified_draft",
            "answer_final": False,
        },
    ],
)
def test_load_messages_drops_invalid_terminal_metadata_but_keeps_message(
    tmp_path, corrupt_metadata
):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    original = store.append_message(
        conversation.conversation_id,
        "assistant",
        "旧消息正文仍须可读",
    )
    path = tmp_path / conversation.conversation_id / "messages.jsonl"
    record = json.loads(path.read_text(encoding="utf-8"))
    record.update(corrupt_metadata)
    path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    loaded = store.load_messages(conversation.conversation_id)

    assert len(loaded) == 1
    assert loaded[0].content == original.content
    assert loaded[0].status == original.status
    assert loaded[0].answer_revision is None
    assert loaded[0].answer_phase is None
    assert loaded[0].answer_final is None


@pytest.mark.parametrize(
    ("role", "status"),
    [
        ("assistant", "pending"),
        ("assistant", "failed"),
        ("assistant", "cancelled"),
        ("user", "completed"),
    ],
)
def test_load_messages_drops_terminal_metadata_from_invalid_message_context(
    tmp_path, role, status
):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    original = store.append_message(
        conversation.conversation_id,
        role,
        "上下文非法但正文仍须可读",
        status=status,
    )
    path = tmp_path / conversation.conversation_id / "messages.jsonl"
    record = json.loads(path.read_text(encoding="utf-8"))
    record.update(
        {
            "answer_revision": 2,
            "answer_phase": "verified_fallback",
            "answer_final": True,
        }
    )
    path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    loaded = store.load_messages(conversation.conversation_id)

    assert len(loaded) == 1
    assert loaded[0].content == original.content
    assert loaded[0].role == role
    assert loaded[0].status == status
    assert loaded[0].answer_revision is None
    assert loaded[0].answer_phase is None
    assert loaded[0].answer_final is None


def test_message_perspective_selection_persists_without_leaking_to_other_conversations(
    tmp_path,
):
    store = ConversationStore("alice", root=tmp_path)
    first = store.create_conversation("风远视角")
    second = store.create_conversation("数据中立")

    stored = store.append_message(
        first.conversation_id,
        "user",
        "怎么看今天行情",
        perspective_mode="single",
        selected_perspective_ids=["fengyuan94"],
    )
    neutral = store.append_message(second.conversation_id, "user", "复盘")

    assert stored.perspective_mode == "single"
    assert stored.selected_perspective_ids == ["fengyuan94"]
    assert store.load_messages(first.conversation_id)[0] == stored
    assert neutral.perspective_mode == "neutral"
    assert neutral.selected_perspective_ids == []


def test_defaults_to_demo_user(tmp_path):
    store = ConversationStore(root=tmp_path)
    conversation = store.create_conversation()

    assert store.user_id == "demo"
    assert conversation.user_id == "demo"


@pytest.mark.parametrize("conversation_id", ["../escape", "a/b", "", ".", "..", "bad id"])
def test_rejects_invalid_conversation_ids(tmp_path, conversation_id):
    store = ConversationStore("alice", root=tmp_path)
    with pytest.raises(ValueError):
        store.load_conversation(conversation_id)


def test_rejects_traversal_user_id(tmp_path):
    with pytest.raises(ValueError):
        ConversationStore("../alice", root=tmp_path)


def test_messages_are_append_only_and_ordered(tmp_path):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation("顺序测试")
    first = store.append_message(conversation.conversation_id, "user", "第一条")
    second = store.append_message(conversation.conversation_id, "assistant", "第二条")

    assert store.load_messages(conversation.conversation_id) == [first, second]
    raw_lines = (tmp_path / conversation.conversation_id / "messages.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    assert [json.loads(line)["message_id"] for line in raw_lines] == [
        first.message_id,
        second.message_id,
    ]


def test_redacts_all_visible_strings_including_nested_fields(tmp_path):
    secret = "sk-supersecret123"
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation(f"标题 {secret}")
    store.update_summary(conversation.conversation_id, f"摘要 {secret}", last_run_id=f"run-{secret}")
    store.append_message(
        conversation.conversation_id,
        f"user-{secret}",
        f"正文 {secret}",
        status=f"status-{secret}",
        run_id=f"run-{secret}",
        selected_skill_ids=[f"selected-{secret}"],
        invoked_skill_ids=[f"invoked-{secret}"],
        citations=[{"title": f"来源 {secret}", "nested": [f"链接 {secret}"]}],
        degrades=[f"降级 {secret}"],
    )

    disk_text = "\n".join(
        path.read_text(encoding="utf-8") for path in tmp_path.rglob("*.json*")
    )
    assert secret not in disk_text
    assert "[REDACTED]" in disk_text


def test_rejects_user_id_that_redaction_would_change(tmp_path):
    with pytest.raises(ValueError, match="user_id.*敏感信息"):
        ConversationStore("sk-supersecret123", root=tmp_path)


def test_rejects_citation_key_collision_after_redaction(tmp_path):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()

    with pytest.raises(TypeError, match="citation.*key.*碰撞"):
        store.append_message(
            conversation.conversation_id,
            "assistant",
            "回答",
            citations=[{"sk-firstsecret123": 1, "sk-secondsecret456": 2}],
        )


def test_rename_and_summary_updates_persist_redacted_values(tmp_path):
    secret = "sk-supersecret123"
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()

    store.rename_conversation(conversation.conversation_id, f"标题 {secret}")
    store.update_summary(
        conversation.conversation_id,
        f"摘要 {secret}",
        last_run_id=f"run-{secret}",
    )

    loaded = store.load_conversation(conversation.conversation_id)
    assert loaded.title == "标题 [REDACTED]"
    assert loaded.summary == "摘要 [REDACTED]"
    assert loaded.last_run_id == "run-[REDACTED]"


def test_degrades_remains_a_redacted_string_list(tmp_path):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()

    message = store.append_message(
        conversation.conversation_id,
        "assistant",
        "回答",
        degrades=["provider sk-supersecret123 unavailable", "template fallback"],
    )

    assert message.degrades == ["provider [REDACTED] unavailable", "template fallback"]
    assert store.load_messages(conversation.conversation_id)[0].degrades == message.degrades


def test_failed_atomic_replace_preserves_old_metadata_and_cleans_temp(tmp_path):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    conversation_dir = tmp_path / conversation.conversation_id
    original = (conversation_dir / "conversation.json").read_bytes()

    def failing_replace(source, destination):
        raise OSError("injected replace failure")

    with patch("os.replace", side_effect=failing_replace):
        with pytest.raises(OSError, match="injected replace failure"):
            store.rename_conversation(conversation.conversation_id, "新标题")

    assert (conversation_dir / "conversation.json").read_bytes() == original
    assert not list(conversation_dir.glob(".*.tmp"))
    assert store.load_conversation(conversation.conversation_id).title == "新对话"


def test_truncated_final_record_is_ignored_and_prior_messages_remain_readable(tmp_path):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    first = store.append_message(conversation.conversation_id, "user", "完整消息")
    path = tmp_path / conversation.conversation_id / "messages.jsonl"
    with path.open("ab") as handle:
        handle.write(b'{"message_id":"truncated"')

    assert store.load_messages(conversation.conversation_id) == [first]


def test_append_refuses_existing_non_newline_truncated_tail(tmp_path):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    store.append_message(conversation.conversation_id, "user", "完整消息")
    path = tmp_path / conversation.conversation_id / "messages.jsonl"
    with path.open("ab") as handle:
        handle.write(b'{"message_id":"truncated"')

    before = path.read_bytes()
    with pytest.raises(ConversationDataIntegrityError, match="末尾.*换行"):
        store.append_message(conversation.conversation_id, "assistant", "不能粘连")
    assert path.read_bytes() == before


def test_invalid_middle_record_raises_integrity_error_with_line_number(tmp_path):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    first = store.append_message(conversation.conversation_id, "user", "第一条")
    store.append_message(conversation.conversation_id, "assistant", "第二条")
    path = tmp_path / conversation.conversation_id / "messages.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text(lines[0] + "not-json\n" + lines[1], encoding="utf-8")

    with pytest.raises(ConversationDataIntegrityError, match="第 2 行"):
        store.load_messages(conversation.conversation_id)
    assert json.loads(lines[0])["message_id"] == first.message_id


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [("conversation_id", "conv_other"), ("user_id", "bob")],
)
def test_load_conversation_rejects_metadata_identity_mismatch(
    tmp_path, field, bad_value
):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    path = tmp_path / conversation.conversation_id / "conversation.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data[field] = bad_value
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ConversationDataIntegrityError, match=field):
        store.load_conversation(conversation.conversation_id)


def test_archived_conversations_are_listed_and_readable(tmp_path):
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation("归档可读")
    store.append_message(conversation.conversation_id, "user", "仍可读取")
    store.archive_conversation(conversation.conversation_id)

    assert [item.conversation_id for item in store.list_conversations()] == [
        conversation.conversation_id
    ]
    assert store.load_conversation(conversation.conversation_id).status == "archived"
    assert store.load_messages(conversation.conversation_id)[0].content == "仍可读取"
