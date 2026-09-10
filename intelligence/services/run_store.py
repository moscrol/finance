"""Run/Artifact/Trace 协议的最小落盘实现（Agent Workbench 第 0 步）。

把「一次用户请求」固化成一个可保存、可复现、可分享的 **run 目录**：

    intelligence/users/<id>/runs/<run_id>/
        run.json      # run 元数据（单写入者：本模块；协议见 docs/superpowers/plans/2026-07-08-run-protocol.md）
        trace.jsonl   # 工具步骤流水（append-only，边跑边写，崩溃/刷新可重放）
        answer.md 等  # 产物文件，登记进 run.json 的 artifacts[]

设计取舍（教学）：

- **JSON + JSONL 文件，不用 SQLite**：与台账地图「按日期/ID 分区 + 单写入者」的
  纪律一致，git diff / jq 可直读，量级（每天几十个 run）远够。以后要全局检索再
  在其上建索引（投影），canonical 落点不变。
- **trace 用 append-only JSONL 而不是最后一次性写 trace.json**：任务可能跑几分
  钟，边跑边追加才能支持「浏览器刷新后凭 run_id 重连/重放」和崩溃后定位到哪一步。
  这就是 Agent observability 的最小可用形态（面试可讲：等价于结构化日志 + span）。
- **落在 users/<id>/ 用户态命名空间**：run 含个性化问题与产物，按仓库红线不入
  git（.gitignore 已加 ``intelligence/users/*/runs/``）；协议本身与 golden 样例
  （脱敏）入库做回归。
- **摘要一律过 redact()**：trace/run 是将来要「可分享」的产物，任何写入 UI 可见
  字段的文本先脱敏，把密钥泄漏消灭在写入口而不是展示层。
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from intelligence import userspace
from intelligence.services.workbench_db import DB_FILENAME, WorkbenchDB
from intelligence.api.stream_events import (
    STREAM_SCHEMA_VERSION,
    StreamEnvelope,
    canonical_event_type,
)

SCHEMA_VERSION = 1

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
RUN_STATUSES = (
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_CANCELLED,
)
_TERMINAL_STATUSES = (STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED)

STEP_STATUSES = ("running", "completed", "failed", "skipped")
ARTIFACT_VISIBILITIES = ("public", "internal")
HISTORY_ARTIFACT_KINDS = ("query", "case", "hypothesis")
_HISTORY_ARTIFACT_NAME = re.compile(
    r"history-(query|case|hypothesis)-([0-9a-f]{64})\.json"
)
_LEGACY_INTERNAL_ARTIFACT_PATHS = frozenset({"continuous-episode.json"})


def artifact_visibility(artifact: dict[str, Any]) -> str:
    """Resolve persisted visibility, failing closed for corrupt metadata."""

    value = artifact.get("visibility")
    if value in ARTIFACT_VISIBILITIES:
        return str(value)
    if value not in {None, ""}:
        return "internal"
    return (
        "internal"
        if str(artifact.get("path") or "") in _LEGACY_INTERNAL_ARTIFACT_PATHS
        else "public"
    )


# 常见密钥形态：Authorization 头/JWT、OpenAI/GitHub/飞书前缀 token，
# 以及 key=value 形式的赋值。先匹配完整 Authorization 头，避免只遮掉
# scheme 而把真正凭据留在后面。
_SECRET_FIELD_NAME = (
    r"(?:[A-Za-z0-9]+[_-])*"
    r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"client[_-]?secret|token|secret|password|authorization)"
)
_SECRET_PATTERNS = [
    re.compile(
        r"""(?ix)
        ["']authorization["']\s*:\s*
        (?:"[^"\r\n]*"|'[^'\r\n]*')
        """
    ),
    re.compile(r"(?i)\bauthorization\s*[=:]\s*[^\r\n]+"),
    re.compile(
        r"(?i)\bbearer\s+"
        r"[A-Za-z0-9_-]{4,}={0,2}\."
        r"[A-Za-z0-9_-]{4,}={0,2}\."
        r"[A-Za-z0-9_-]{4,}={0,2}"
    ),
    re.compile(
        rf"""(?ix)
        \b{_SECRET_FIELD_NAME}\s*[=:]\s*
        (?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;}}\]\r\n]+)
        """
    ),
    re.compile(r"\b(sk|ghp|gho|ghu|ghs|xoxb|xoxp)[-_][A-Za-z0-9_\-]{8,}"),
]
_SECRET_KEY_RE = re.compile(rf"(?i)^{_SECRET_FIELD_NAME}$")

# This makes append linearizable across RunStore instances in one process. A
# multi-process deployment still needs an OS/file lock or a transactional store.
_STREAM_LOCKS: dict[str, Lock] = {}
_STREAM_LOCKS_GUARD = Lock()


def _stream_lock(path: Path) -> Lock:
    key = str(path.resolve())
    with _STREAM_LOCKS_GUARD:
        return _STREAM_LOCKS.setdefault(key, Lock())


@contextmanager
def _file_transaction_lock(path: Path) -> Iterator[None]:
    """Hold a non-reentrant lock shared by threads, stores and processes."""
    with _stream_lock(path):
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


def redact(text: str) -> str:
    """写入 run/trace 任何 UI 可见字段前的脱敏：命中密钥形态一律替换为占位符。"""
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def redact_value(value: Any) -> Any:
    """Recursively sanitize strings and exact secret-valued mapping keys."""

    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            raw_key = str(key)
            safe_key = redact(raw_key)
            base_key = safe_key or "[REDACTED]"
            suffix = 2
            while safe_key in redacted:
                safe_key = f"{base_key}#{suffix}"
                suffix += 1
            redacted[safe_key] = (
                "[REDACTED]"
                if _SECRET_KEY_RE.fullmatch(raw_key.strip())
                else redact_value(item)
            )
        return redacted
    return value


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_run_id(now: datetime | None = None) -> str:
    """run_id：日期 + 时分秒 + 微秒，单机单进程下可读且几乎不撞。"""
    dt = now or datetime.now()
    return f"run_{dt.strftime('%Y%m%d_%H%M%S_%f')}"


def build_trace_step(
    *,
    step_id: str,
    name: str,
    status: str,
    input_summary: str = "",
    output_summary: str = "",
    started_at: str | None = None,
    finished_at: str | None = None,
    warnings: list[str] | None = None,
    tokens: int | None = None,
    retrieval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造一条 trace step（纯函数，不落盘）。

    为什么单独拆出来：``trace.jsonl`` 的字段形状是 `agent-run-triage` 这类
    分诊工具的输入契约。生产由 ``RunStore.append_step`` 写，离线试验台
    （``run_episode_seam_ladder``）也要写同样的东西——**但绝不能各写各的**。
    两份定义一旦漂移，分诊工具就只能认其中一份，而"试验台产出的东西生产工具
    读不了"恰恰是这套试验台反复吃亏的地方。

    所以这里是 schema 的**唯一定义处**，落盘方式（追加进 run 目录 / 写到试验台
    产物旁边）才是各自的事。脱敏在构造时完成，不留给调用方。
    """

    if status not in STEP_STATUSES:
        raise ValueError(f"非法 step status：{status!r}（允许：{STEP_STATUSES}）")
    step: dict[str, Any] = {
        "step_id": step_id,
        "name": name,
        "status": status,
        "started_at": started_at or _now_iso(),
        "finished_at": finished_at,
        "input_summary": redact(input_summary),
        "output_summary": redact(output_summary),
        "warnings": [redact(w) for w in (warnings or [])],
    }
    if tokens is not None:
        step["tokens"] = tokens
    if retrieval is not None:
        step["retrieval"] = retrieval
    return step


@dataclass
class Artifact:
    """一个产物文件的登记信息（文件本体在 run 目录内，path 为相对 run 目录）。"""

    artifact_id: str
    path: str
    renderer: str  # markdown / html / json / table / image
    title: str
    sha256: str
    bytes: int
    previewable: bool = True
    downloadable: bool = True
    visibility: str = "public"


@dataclass
class Run:
    """一次用户请求的元数据（协议 v1，字段语义见 run-protocol 文档）。"""

    run_id: str
    user: str
    question: str
    task_type: str
    status: str = STATUS_QUEUED
    schema_version: int = SCHEMA_VERSION
    session_id: str | None = None
    parent_run_id: str | None = None
    created_at: str = field(default_factory=_now_iso)
    finished_at: str | None = None
    source_date: str | None = None
    duckdb_cutoff: str | None = None
    kb_commit: str | None = None
    kb_index_built_at: str | None = None
    kb_index_freshness: str | None = None
    manifest_ref: str | None = None
    degrades: list[str] = field(default_factory=list)
    error: str | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)


class RunStore:
    """Run 目录的唯一写入者（单 writer 原则，同台账地图其它台账一致）。"""

    def __init__(self, user_id: str | None = None, root: Path | None = None) -> None:
        us = userspace.user_space(user_id)
        self.user_id = us.user_id
        if root is not None:
            self.root = root
            db_path = Path(root) / DB_FILENAME
        else:
            self.root = us.root / "runs"
            db_path = us.root / DB_FILENAME
        self.db = WorkbenchDB(db_path)
        self._state_lock = threading.RLock()

    # ---------- 写路径 ----------

    def create_run(
        self,
        question: str,
        task_type: str,
        *,
        session_id: str | None = None,
        parent_run_id: str | None = None,
        source_date: str | None = None,
        duckdb_cutoff: str | None = None,
        kb_commit: str | None = None,
        manifest_ref: str | None = None,
    ) -> Run:
        run = Run(
            run_id=new_run_id(),
            user=self.user_id,
            question=redact(question),
            task_type=task_type,
            status=STATUS_RUNNING,
            session_id=session_id,
            parent_run_id=parent_run_id,
            source_date=source_date,
            duckdb_cutoff=duckdb_cutoff,
            kb_commit=kb_commit,
            manifest_ref=manifest_ref,
        )
        run_dir = self.run_dir(run.run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        with self._run_state_lock(run.run_id):
            self._write_run(run)
        return run

    def append_step(
        self,
        run_id: str,
        *,
        step_id: str,
        name: str,
        status: str,
        input_summary: str = "",
        output_summary: str = "",
        started_at: str | None = None,
        finished_at: str | None = None,
        warnings: list[str] | None = None,
        tokens: int | None = None,
        retrieval: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        step = build_trace_step(
            step_id=step_id,
            name=name,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            started_at=started_at,
            finished_at=finished_at,
            warnings=warnings,
            tokens=tokens,
            retrieval=retrieval,
        )
        with self.trace_path(run_id).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(step, ensure_ascii=False) + "\n")
        return step

    def append_stream_event(
        self,
        run_id: str,
        *,
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
        conversation_id: str | None = None,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        run = self.load_run(run_id)
        path = self.stream_path(run_id)
        safe_id = redact(event_id)
        safe_type = canonical_event_type(redact(event_type))
        if not safe_id.strip():
            raise ValueError("event_id must not be blank")
        if not safe_type.strip():
            raise ValueError("event_type must not be blank")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        source_conversation = (
            conversation_id if conversation_id is not None else run.session_id
        )
        safe_conversation = (
            redact(source_conversation) if source_conversation is not None else None
        )
        safe_message = redact(message_id) if message_id is not None else None
        safe_payload = redact_value(payload)
        with _stream_lock(path):
            if (
                path.exists()
                and path.stat().st_size
                and not path.read_bytes().endswith(b"\n")
            ):
                raise ValueError(
                    "refuse append: nonempty stream file lacks final newline"
                )
            if self.db.count_run_events(run_id) == 0:
                legacy = self._load_stream_events_from_file(run_id)
                if legacy:
                    self.db.insert_run_events(run_id, legacy)
            existing = self.db.get_run_events(run_id)
            for event in existing:
                if event["event_id"] != safe_id:
                    continue
                identity = (safe_type, safe_conversation, safe_message, safe_payload)
                stored = (
                    event["event_type"],
                    event["conversation_id"],
                    event["message_id"],
                    event["payload"],
                )
                if identity == stored:
                    return event
                raise ValueError(f"conflicting duplicate event_id: {safe_id}")
            envelope = StreamEnvelope(
                schema_version=STREAM_SCHEMA_VERSION,
                event_id=safe_id,
                event_type=safe_type,
                run_id=run_id,
                conversation_id=safe_conversation,
                message_id=safe_message,
                seq=(existing[-1]["seq"] + 1 if existing else 1),
                created_at=_now_iso(),
                payload=safe_payload,
            )
            event = asdict(envelope)
            self.db.insert_run_event(run_id, event["seq"], safe_id, event)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            return event

    def add_artifact(
        self,
        run_id: str,
        filename: str,
        content: str | bytes,
        *,
        renderer: str,
        title: str,
        visibility: str = "public",
        previewable: bool = True,
        downloadable: bool = True,
    ) -> Artifact:
        with self._run_state_lock(run_id):
            if visibility not in ARTIFACT_VISIBILITIES:
                raise ValueError(f"invalid artifact visibility: {visibility!r}")
            data = content.encode("utf-8") if isinstance(content, str) else content
            path = self.run_dir(run_id) / filename
            path.write_bytes(data)
            artifact = Artifact(
                artifact_id=f"artifact_{filename.replace('.', '_')}",
                path=filename,
                renderer=renderer,
                title=title,
                sha256=hashlib.sha256(data).hexdigest(),
                bytes=len(data),
                previewable=previewable,
                downloadable=downloadable,
                visibility=visibility,
            )
            run = self.load_run(run_id)
            run.artifacts = [a for a in run.artifacts if a.get("path") != filename]
            run.artifacts.append(asdict(artifact))
            self._write_run(run)
            return artifact

    def add_history_artifact(
        self,
        run_id: str,
        kind: str,
        payload: dict[str, Any],
        *,
        visibility: str = "public",
    ) -> Artifact:
        """Commit a complete JSON original without replacing earlier evidence.

        A retry repairs an unregistered, intact content file after a failed index
        write. Registered files that disappeared or changed always fail closed.
        The caller supplies research JSON; unlike summaries it is not truncated
        or rewritten. The normal artifact visibility rules still apply.
        """
        with self._state_lock:
            self._history_run(run_id)
            if kind not in HISTORY_ARTIFACT_KINDS:
                raise ValueError(f"invalid history artifact kind: {kind!r}")
            if visibility not in ARTIFACT_VISIBILITIES:
                raise ValueError(f"invalid artifact visibility: {visibility!r}")
            data = self._history_json_bytes(payload)
            digest = hashlib.sha256(data).hexdigest()
            filename = f"history-{kind}-{digest}.json"
            artifact = Artifact(
                artifact_id=f"artifact_{filename.replace('.', '_')}",
                path=filename,
                renderer="json",
                title=f"History {kind}",
                sha256=digest,
                bytes=len(data),
                visibility=visibility,
            )
            with self._run_state_lock(run_id):
                run, run_dir = self._history_run(run_id)
                path = self._history_path(run_dir, filename)
                registered = [a for a in run.artifacts if a.get("path") == filename]
                if registered:
                    if len(registered) != 1:
                        raise ValueError(
                            "history artifact integrity: duplicate registration"
                        )
                    self._verified_history_bytes(path, registered[0])
                    if registered[0] != asdict(artifact):
                        raise ValueError("conflicting history artifact registration")
                    return artifact

                # Publish a fully written file with link(2), which cannot replace
                # an existing destination. An interrupted index write leaves an
                # intact orphan that this same path can verify and register.
                if not path.exists():
                    with tempfile.NamedTemporaryFile(
                        dir=run_dir, prefix=".history-", suffix=".tmp", delete=False
                    ) as fh:
                        temporary = Path(fh.name)
                        try:
                            fh.write(data)
                            fh.flush()
                            os.fsync(fh.fileno())
                            try:
                                os.link(temporary, path)
                            except FileExistsError:
                                pass
                        finally:
                            temporary.unlink(missing_ok=True)
                self._verified_history_bytes(path, asdict(artifact))
                directory_fd = os.open(run_dir, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
                run.artifacts.append(asdict(artifact))
                self._write_run(run)
                return artifact

    def read_history_artifact(self, run_id: str, filename: str) -> dict[str, Any]:
        """Read only a registered, public original owned by this store's user."""
        with self._state_lock:
            run, run_dir = self._history_run(run_id)
            path = self._history_path(run_dir, filename)
            registered = [a for a in run.artifacts if a.get("path") == filename]
            if len(registered) > 1:
                raise ValueError("history artifact integrity: duplicate registration")
            if (
                not registered
                or artifact_visibility(registered[0]) != "public"
                or registered[0].get("downloadable", True) is not True
            ):
                raise FileNotFoundError(f"history artifact not available: {filename}")
            data = self._verified_history_bytes(path, registered[0])
            payload = json.loads(data)
            self._history_json_bytes(payload)
            return payload

    @contextmanager
    def history_case_transaction(
        self, conversation_id: str, case_id: str
    ) -> Iterator[None]:
        """Coordinate case-head checks and writes to existing run artifacts.

        The caller refreshes authorized conversation references, reads the head,
        validates the revision and saves through this RunStore while holding the
        transaction. The empty lock file is coordination, not another index or
        ledger. Always acquire this case lock before any per-run metadata lock;
        ordinary run writers never acquire a case lock. Neither lock is reentrant.
        """
        for name, value in (("conversation_id", conversation_id), ("case_id", case_id)):
            if not isinstance(value, str) or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}", value
            ):
                raise ValueError(f"invalid history {name}")
        identity = json.dumps(
            [self.user_id, conversation_id, case_id], separators=(",", ":")
        ).encode("utf-8")
        directory = self.root / ".history-case-locks"
        if directory.is_symlink() or directory.resolve().parent != self.root.resolve():
            raise ValueError("invalid history case lock path")
        directory.mkdir(mode=0o700, exist_ok=True)
        path = directory / f"{hashlib.sha256(identity).hexdigest()}.lock"
        with _file_transaction_lock(path):
            yield

    def _history_run(self, run_id: str) -> tuple[Run, Path]:
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("invalid history run path")
        run_dir = self.run_dir(run_id)
        if run_dir.is_symlink() or run_dir.resolve().parent != self.root.resolve():
            raise ValueError("invalid history run path")
        run_path = run_dir / "run.json"
        if run_path.is_symlink():
            raise ValueError("invalid history run metadata path")
        if not run_path.is_file():
            raise FileNotFoundError(f"run not found: {run_id}")
        run = self.load_run(run_id)
        if run.user != self.user_id:
            raise PermissionError("history artifact belongs to another user")
        if run.run_id != run_id:
            raise ValueError("history run identity mismatch")
        return run, run_dir

    @contextmanager
    def _run_state_lock(self, run_id: str) -> Iterator[None]:
        # Every metadata read/modify/write uses the same per-run lock, including
        # cancellation, ordinary artifacts and recovery. Locking only history
        # writes would let another store commit a stale Run over their result.
        # No locked operation calls another metadata writer: the file lock is
        # intentionally non-reentrant. O_NOFOLLOW rejects lock-file symlinks.
        path = self.run_dir(run_id) / ".run-state.lock"
        with _file_transaction_lock(path):
            yield

    @staticmethod
    def _history_json_bytes(payload: dict[str, Any]) -> bytes:
        def validate(value: Any) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if not isinstance(key, str):
                        raise ValueError("history JSON object keys must be strings")
                    validate(item)
            elif isinstance(value, list):
                for item in value:
                    validate(item)
            elif value is not None and not isinstance(value, (str, int, float, bool)):
                raise ValueError("history payload must contain only JSON values")

        if not isinstance(payload, dict):
            raise ValueError("history payload must be a JSON object")
        validate(payload)
        return (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")

    @staticmethod
    def _history_path(run_dir: Path, filename: str) -> Path:
        if not isinstance(filename, str) or not _HISTORY_ARTIFACT_NAME.fullmatch(
            filename
        ):
            raise ValueError("invalid history artifact path")
        path = run_dir / filename
        if path.is_symlink() or path.resolve().parent != run_dir.resolve():
            raise ValueError("invalid history artifact path")
        return path

    @staticmethod
    def _verified_history_bytes(path: Path, artifact: dict[str, Any]) -> bytes:
        if path.is_symlink():
            raise ValueError("invalid history artifact path")
        if not path.is_file():
            raise FileNotFoundError(f"history artifact missing: {path.name}")
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as fh:
            data = fh.read()
        match = _HISTORY_ARTIFACT_NAME.fullmatch(path.name)
        digest = hashlib.sha256(data).hexdigest()
        if (
            match is None
            or match[2] != digest
            or artifact.get("sha256") != digest
            or type(artifact.get("bytes")) is not int
            or artifact["bytes"] != len(data)
            or artifact.get("renderer") != "json"
        ):
            raise ValueError("history artifact integrity check failed")
        return data

    def add_degrade(self, run_id: str, reason: str) -> None:
        """数据源降级一等公民化：录屏里「ftshare 不可用」这类事件落到 run 元数据。"""
        with self._run_state_lock(run_id):
            run = self.load_run(run_id)
            reason = redact(reason)
            if reason not in run.degrades:
                run.degrades.append(reason)
                self._write_run(run)

    def update_provenance(
        self,
        run_id: str,
        *,
        source_date: str | None = None,
        duckdb_cutoff: str | None = None,
        kb_commit: str | None = None,
        kb_index_built_at: str | None = None,
        kb_index_freshness: str | None = None,
    ) -> Run:
        with self._run_state_lock(run_id):
            run = self.load_run(run_id)
            if source_date is not None:
                run.source_date = source_date
            if duckdb_cutoff is not None:
                run.duckdb_cutoff = duckdb_cutoff
            if kb_commit is not None:
                run.kb_commit = kb_commit
            if kb_index_built_at is not None:
                run.kb_index_built_at = kb_index_built_at
            if kb_index_freshness is not None:
                run.kb_index_freshness = kb_index_freshness
            self._write_run(run)
            return run

    def finish_run(self, run_id: str, status: str, *, error: str | None = None) -> Run:
        run, _claimed = self.claim_terminal_run(run_id, status, error=error)
        return run

    def claim_terminal_run(
        self,
        run_id: str,
        status: str,
        *,
        error: str | None = None,
    ) -> tuple[Run, bool]:
        """Atomically claim an active run's terminal transition."""

        if status not in _TERMINAL_STATUSES:
            raise ValueError(
                f"finish_run 只接受终态：{_TERMINAL_STATUSES}，得到 {status!r}"
            )
        with self._run_state_lock(run_id):
            run = self.load_run(run_id)
            if run.status in _TERMINAL_STATUSES:
                return run, False
            run.status = status
            run.finished_at = _now_iso()
            run.error = redact(error) if error else None
            self._write_run(run)
            return run, True

    def mark_queued(self, run_id: str) -> Run:
        """已受理、等 worker 空出来。终态不回退。"""
        with self._run_state_lock(run_id):
            run = self.load_run(run_id)
            if run.status in _TERMINAL_STATUSES:
                return run
            run.status = STATUS_QUEUED
            run.finished_at = None
            run.error = None
            self._write_run(run)
            return run

    def mark_running(self, run_id: str) -> Run:
        with self._run_state_lock(run_id):
            run = self.load_run(run_id)
            if run.status in _TERMINAL_STATUSES:
                return run
            run.status = STATUS_RUNNING
            run.finished_at = None
            run.error = None
            self._write_run(run)
            return run

    def claim_failed_run(
        self,
        run_id: str,
        *,
        error: str,
        degrade: str,
    ) -> tuple[Run, bool]:
        """Atomically claim failure together with its public degradation reason."""

        with self._run_state_lock(run_id):
            run = self.load_run(run_id)
            if run.status in _TERMINAL_STATUSES:
                return run, False
            degrade = redact(degrade)
            if degrade not in run.degrades:
                run.degrades.append(degrade)
            run.status = STATUS_FAILED
            run.finished_at = _now_iso()
            run.error = redact(error)
            self._write_run(run)
            return run, True

    def fail_active_run(self, run_id: str, *, error: str, degrade: str) -> Run:
        run, _claimed = self.claim_failed_run(
            run_id,
            error=error,
            degrade=degrade,
        )
        return run

    def requeue_incomplete_runs(self, *, reason: str) -> list[Run]:
        recovered: list[Run] = []
        for candidate in self.list_runs():
            with self._run_state_lock(candidate.run_id):
                # The listing can be stale by the time this run's lock is held.
                run = self.load_run(candidate.run_id)
                if run.status not in {STATUS_QUEUED, STATUS_RUNNING}:
                    continue
                if reason not in run.degrades:
                    run.degrades.append(redact(reason))
                run.status = STATUS_QUEUED
                run.finished_at = None
                run.error = None
                self._write_run(run)
                self.append_stream_event(
                    run.run_id,
                    event_id=f"recovery:{_now_iso()}",
                    event_type="run_recovered",
                    payload={"reason": reason},
                )
                recovered.append(run)
        return recovered

    # ---------- 读路径 ----------

    def run_dir(self, run_id: str) -> Path:
        if "/" in run_id or "\\" in run_id or run_id in {".", ".."}:
            raise ValueError(f"非法 run_id：{run_id!r}")
        return self.root / run_id

    def run_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "run.json"

    def trace_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "trace.jsonl"

    def stream_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "stream.jsonl"

    def load_run(self, run_id: str) -> Run:
        self.run_dir(run_id)  # 校验 run_id 合法性（防路径穿越）
        payload = self.db.get_run(run_id)
        if payload is None:
            payload = json.loads(self.run_path(run_id).read_text(encoding="utf-8"))
        return Run(**payload)

    def load_trace(self, run_id: str) -> list[dict[str, Any]]:
        path = self.trace_path(run_id)
        if not path.exists():
            return []
        steps = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                steps.append(json.loads(line))
        return steps

    def load_stream_events(self, run_id: str, after: int = 0) -> list[dict[str, Any]]:
        if isinstance(after, bool) or not isinstance(after, int) or after < 0:
            raise ValueError("stream cursor must be nonnegative")
        if self.db.count_run_events(run_id):
            return self.db.get_run_events(run_id, after)
        return self._load_stream_events_from_file(run_id, after)

    def _load_stream_events_from_file(
        self, run_id: str, after: int = 0
    ) -> list[dict[str, Any]]:
        """旧 JSONL 读路径（SQLite 无该 run 事件时的回退 + 懒回填数据源）。"""
        path = self.stream_path(run_id)
        if not path.exists():
            return []
        run = self.load_run(run_id)
        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        events: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        previous_seq = 0
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                if index == len(lines) - 1 and not raw.endswith("\n"):
                    break
                raise ValueError(f"corrupt stream row {index + 1}") from exc
            expected_seq = previous_seq + 1
            if not isinstance(row, dict):
                raise ValueError(f"invalid stream row {index + 1}")
            native_fields = {
                "schema_version",
                "run_id",
                "conversation_id",
                "message_id",
                "seq",
            }
            is_native = bool(native_fields.intersection(row))
            if is_native:
                valid_optional_ids = all(
                    value is None or (isinstance(value, str) and bool(value.strip()))
                    for value in (row.get("conversation_id"), row.get("message_id"))
                )
                seq = row.get("seq")
                valid = (
                    row.get("schema_version") == STREAM_SCHEMA_VERSION
                    and not isinstance(row.get("schema_version"), bool)
                    and row.get("run_id") == run_id
                    and isinstance(seq, int)
                    and not isinstance(seq, bool)
                    and seq == expected_seq
                    and valid_optional_ids
                    and isinstance(row.get("event_id"), str)
                    and bool(row["event_id"].strip())
                    and isinstance(row.get("event_type"), str)
                    and bool(row["event_type"].strip())
                    and isinstance(row.get("created_at"), str)
                    and bool(row["created_at"].strip())
                    and isinstance(row.get("payload"), dict)
                )
            else:
                seq = expected_seq
                valid = (
                    isinstance(row.get("event_id"), str)
                    and bool(row["event_id"].strip())
                    and isinstance(row.get("event_type"), str)
                    and bool(row["event_type"].strip())
                    and isinstance(row.get("created_at"), str)
                    and bool(row["created_at"].strip())
                    and isinstance(row.get("payload"), dict)
                )
            event_id = row.get("event_id")
            if not valid or event_id in seen_ids:
                raise ValueError(f"invalid stream row {index + 1}")
            previous_seq = seq
            seen_ids.add(event_id)
            event = asdict(
                StreamEnvelope(
                    schema_version=STREAM_SCHEMA_VERSION,
                    event_id=event_id,
                    event_type=canonical_event_type(row["event_type"]),
                    run_id=run_id,
                    conversation_id=(
                        row.get("conversation_id") if is_native else run.session_id
                    ),
                    message_id=row.get("message_id") if is_native else None,
                    seq=seq,
                    created_at=row["created_at"],
                    payload=row["payload"],
                )
            )
            if seq > after:
                events.append(event)
        return events

    def list_runs(self) -> list[Run]:
        merged: dict[str, Run] = {}
        if self.root.exists():
            for run_file in sorted(self.root.glob("run_*/run.json")):
                run = Run(**json.loads(run_file.read_text(encoding="utf-8")))
                merged[run.run_id] = run
        for payload in self.db.list_runs():
            run = Run(**payload)
            merged[run.run_id] = run
        return [merged[run_id] for run_id in sorted(merged)]

    # ---------- 内部 ----------

    def _write_run(self, run: Run) -> None:
        path = self.run_path(run.run_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(asdict(run), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(path)  # 原子替换，避免读到写了一半的 run.json
        self.db.upsert_run(asdict(run))
