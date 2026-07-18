"""Chat-first 会话的用户态文件存储。

每个会话使用原子替换的 ``conversation.json`` 和仅追加的 ``messages.jsonl``。
本模块是该目录的唯一写入者。
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from intelligence import userspace
from intelligence.services.run_store import redact
from intelligence.services.workbench_db import DB_FILENAME, WorkbenchDB

_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class ConversationDataIntegrityError(RuntimeError):
    """持久化会话数据违反完整性约束。"""


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def _validate_component(value: str, label: str) -> str:
    if not _SAFE_COMPONENT.fullmatch(value) or value in {".", ".."}:
        raise ValueError(f"非法 {label}：{value!r}")
    return value


def _redact_json(value: object) -> object:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("citation JSON object 的 key 必须是字符串")
            redacted_key = redact(key)
            if redacted_key in redacted:
                raise TypeError("citation JSON object 的 key 脱敏后发生碰撞")
            redacted[redacted_key] = _redact_json(item)
        return redacted
    return value


@dataclass
class Conversation:
    conversation_id: str
    user_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    summary: str = ""
    last_run_id: str | None = None


@dataclass
class Message:
    message_id: str
    conversation_id: str
    role: str
    content: str
    created_at: str
    status: str
    run_id: str | None = None
    skill_mode: str = "hybrid"
    selected_skill_ids: list[str] = field(default_factory=list)
    perspective_mode: str = "neutral"
    selected_perspective_ids: list[str] = field(default_factory=list)
    invoked_skill_ids: list[str] = field(default_factory=list)
    citations: list[dict[str, object]] = field(default_factory=list)
    degrades: list[str] = field(default_factory=list)
    followups: list[dict[str, object]] = field(default_factory=list)
    turn_intent: dict[str, object] | None = None
    research_plan: dict[str, object] | None = None


class ConversationStore:
    """``users/<id>/conversations`` 的唯一写入者。"""

    def __init__(self, user_id: str = "demo", root: Path | None = None) -> None:
        self.user_id = _validate_component(user_id, "user_id")
        if redact(self.user_id) != self.user_id:
            raise ValueError("非法 user_id：不得包含会被脱敏的敏感信息")
        if root is None:
            us_root = userspace.user_space(self.user_id).root
            self.root = us_root / "conversations"
            db_path = us_root / DB_FILENAME
        else:
            self.root = Path(root)
            db_path = self.root / DB_FILENAME
        self.db = WorkbenchDB(db_path)

    def create_conversation(self, title: str = "新对话") -> Conversation:
        now = _now_iso()
        conversation = Conversation(
            conversation_id=f"conv_{uuid4().hex}",
            user_id=redact(self.user_id),
            title=redact(title),
            status="active",
            created_at=now,
            updated_at=now,
        )
        directory = self._conversation_dir(conversation.conversation_id)
        directory.mkdir(parents=True, exist_ok=False)
        self._write_metadata(conversation)
        return conversation

    def list_conversations(self) -> list[Conversation]:
        conversation_ids = set(self.db.list_conversation_ids())
        if self.root.exists():
            conversation_ids.update(
                path.name
                for path in self.root.iterdir()
                if path.is_dir() and (path / "conversation.json").is_file()
            )
        conversations = [
            self.load_conversation(conversation_id)
            for conversation_id in conversation_ids
        ]
        return sorted(conversations, key=lambda item: item.updated_at, reverse=True)

    def load_conversation(self, conversation_id: str) -> Conversation:
        requested_id = _validate_component(conversation_id, "conversation_id")
        data = self.db.get_conversation(requested_id)
        if data is None:
            path = self._conversation_dir(requested_id) / "conversation.json"
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        conversation = Conversation(**data)
        if conversation.conversation_id != requested_id:
            raise ConversationDataIntegrityError(
                "conversation_id 完整性错误：元数据与请求目录不一致"
            )
        if conversation.user_id != self.user_id:
            raise ConversationDataIntegrityError(
                "user_id 完整性错误：元数据与当前 store 不一致"
            )
        return conversation

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        status: str = "completed",
        run_id: str | None = None,
        skill_mode: str = "hybrid",
        selected_skill_ids: list[str] | None = None,
        perspective_mode: str = "neutral",
        selected_perspective_ids: list[str] | None = None,
        invoked_skill_ids: list[str] | None = None,
        citations: list[dict[str, object]] | None = None,
        degrades: list[str] | None = None,
        followups: list[dict[str, object]] | None = None,
        turn_intent: dict[str, object] | None = None,
        research_plan: dict[str, object] | None = None,
    ) -> Message:
        conversation = self.load_conversation(conversation_id)
        message = Message(
            message_id=f"msg_{uuid4().hex}",
            conversation_id=conversation.conversation_id,
            role=redact(role),
            content=redact(content),
            created_at=_now_iso(),
            status=redact(status),
            run_id=redact(run_id) if run_id is not None else None,
            skill_mode=redact(skill_mode),
            selected_skill_ids=[redact(item) for item in (selected_skill_ids or [])],
            perspective_mode=redact(perspective_mode),
            selected_perspective_ids=[
                redact(item) for item in (selected_perspective_ids or [])
            ],
            invoked_skill_ids=[redact(item) for item in (invoked_skill_ids or [])],
            citations=[_redact_mapping(item) for item in (citations or [])],
            degrades=[redact(item) for item in (degrades or [])],
            followups=[_redact_mapping(item) for item in (followups or [])],
            turn_intent=(
                _redact_mapping(turn_intent) if turn_intent is not None else None
            ),
            research_plan=(
                _redact_mapping(research_plan) if research_plan is not None else None
            ),
        )
        self._append_message_record(message)
        return message

    def revise_message(
        self,
        conversation_id: str,
        message_id: str,
        *,
        content: str,
        status: str,
        selected_skill_ids: list[str] | None = None,
        invoked_skill_ids: list[str] | None = None,
        citations: list[dict[str, object]] | None = None,
        degrades: list[str] | None = None,
        followups: list[dict[str, object]] | None = None,
        turn_intent: dict[str, object] | None = None,
        research_plan: dict[str, object] | None = None,
    ) -> Message:
        messages = self.load_messages(conversation_id)
        original = next(
            (message for message in messages if message.message_id == message_id),
            None,
        )
        if original is None:
            raise FileNotFoundError(f"message 不存在：{message_id}")
        revision = Message(
            message_id=original.message_id,
            conversation_id=original.conversation_id,
            role=original.role,
            content=redact(content),
            created_at=original.created_at,
            status=redact(status),
            run_id=original.run_id,
            skill_mode=original.skill_mode,
            selected_skill_ids=[
                redact(item)
                for item in (
                    selected_skill_ids
                    if selected_skill_ids is not None
                    else original.selected_skill_ids
                )
            ],
            perspective_mode=original.perspective_mode,
            selected_perspective_ids=list(original.selected_perspective_ids),
            invoked_skill_ids=[
                redact(item)
                for item in (
                    invoked_skill_ids
                    if invoked_skill_ids is not None
                    else original.invoked_skill_ids
                )
            ],
            citations=[
                _redact_mapping(item)
                for item in (
                    citations if citations is not None else original.citations
                )
            ],
            degrades=[
                redact(item)
                for item in (
                    degrades if degrades is not None else original.degrades
                )
            ],
            followups=[
                _redact_mapping(item)
                for item in (
                    followups if followups is not None else original.followups
                )
            ],
            turn_intent=(
                _redact_mapping(turn_intent)
                if turn_intent is not None
                else original.turn_intent
            ),
            research_plan=(
                _redact_mapping(research_plan)
                if research_plan is not None
                else original.research_plan
            ),
        )
        self._append_message_record(revision)
        return revision

    def _append_message_record(self, message: Message) -> None:
        messages_path = self._messages_path(message.conversation_id)
        if messages_path.exists() and messages_path.stat().st_size:
            with messages_path.open("rb") as handle:
                handle.seek(-1, os.SEEK_END)
                if handle.read(1) != b"\n":
                    raise ConversationDataIntegrityError(
                        "messages.jsonl 末尾缺少换行，拒绝追加以避免记录粘连"
                    )
        if self.db.count_messages(message.conversation_id) == 0:
            legacy = self._load_messages_from_file(message.conversation_id)
            if legacy:
                self.db.append_messages([asdict(item) for item in legacy])
        self.db.append_message(asdict(message))
        with messages_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(message), ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        conversation = self.load_conversation(message.conversation_id)
        conversation.updated_at = _now_iso()
        self._write_metadata(conversation)

    def load_messages(self, conversation_id: str) -> list[Message]:
        self.load_conversation(conversation_id)
        if self.db.count_messages(conversation_id):
            return _dedup_revisions(
                Message(**payload) for payload in self.db.get_messages(conversation_id)
            )
        return self._load_messages_from_file(conversation_id)

    def _load_messages_from_file(self, conversation_id: str) -> list[Message]:
        """旧 JSONL 读路径（SQLite 无该会话消息时的回退 + 懒回填数据源）。"""
        path = self._messages_path(conversation_id)
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        records: list[Message] = []
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                message = Message(**json.loads(line))
            except (json.JSONDecodeError, TypeError, KeyError) as error:
                is_truncated_final = line_number == len(lines) and not line.endswith("\n")
                if is_truncated_final and isinstance(error, json.JSONDecodeError):
                    break
                raise ConversationDataIntegrityError(
                    f"messages.jsonl 第 {line_number} 行数据损坏"
                ) from error
            records.append(message)
        return _dedup_revisions(records)

    def update_summary_text(
        self, conversation_id: str, summary: str
    ) -> Conversation:
        conversation = self.load_conversation(conversation_id)
        conversation.summary = redact(summary)
        return self._touch_and_write(conversation)

    def rename_conversation(self, conversation_id: str, title: str) -> Conversation:
        conversation = self.load_conversation(conversation_id)
        conversation.title = redact(title)
        return self._touch_and_write(conversation)

    def archive_conversation(self, conversation_id: str) -> Conversation:
        conversation = self.load_conversation(conversation_id)
        conversation.status = "archived"
        return self._touch_and_write(conversation)

    def update_summary(
        self, conversation_id: str, summary: str, *, last_run_id: str | None = None
    ) -> Conversation:
        conversation = self.load_conversation(conversation_id)
        conversation.summary = redact(summary)
        conversation.last_run_id = redact(last_run_id) if last_run_id is not None else None
        return self._touch_and_write(conversation)

    def _touch_and_write(self, conversation: Conversation) -> Conversation:
        conversation.updated_at = _now_iso()
        self._write_metadata(conversation)
        return conversation

    def _conversation_dir(self, conversation_id: str) -> Path:
        return self.root / _validate_component(conversation_id, "conversation_id")

    def _messages_path(self, conversation_id: str) -> Path:
        return self._conversation_dir(conversation_id) / "messages.jsonl"

    def _write_metadata(self, conversation: Conversation) -> None:
        directory = self._conversation_dir(conversation.conversation_id)
        directory.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".conversation-", suffix=".tmp", dir=directory
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(asdict(conversation), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, directory / "conversation.json")
        finally:
            temporary.unlink(missing_ok=True)
        self.db.upsert_conversation(asdict(conversation))


def _dedup_revisions(records) -> list[Message]:
    """同 message_id 的后续记录是修订：保留首次出现的位置，内容取最后一条。"""
    messages: list[Message] = []
    positions: dict[str, int] = {}
    for message in records:
        position = positions.get(message.message_id)
        if position is None:
            positions[message.message_id] = len(messages)
            messages.append(message)
        else:
            messages[position] = message
    return messages


def _redact_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("citation 必须是 JSON object")
    redacted: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError("citation JSON object 的 key 必须是字符串")
        redacted_key = redact(key)
        if redacted_key in redacted:
            raise TypeError("citation JSON object 的 key 脱敏后发生碰撞")
        redacted[redacted_key] = _redact_json(item)
    return redacted
