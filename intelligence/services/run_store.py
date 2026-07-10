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

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from intelligence import userspace

SCHEMA_VERSION = 1

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
RUN_STATUSES = (STATUS_QUEUED, STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED)
_TERMINAL_STATUSES = (STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED)

STEP_STATUSES = ("running", "completed", "failed", "skipped")

# 常见密钥形态：OpenAI/GitHub/飞书等前缀 token、以及 key=value 形式的赋值。
_SECRET_PATTERNS = [
    re.compile(r"\b(sk|ghp|gho|ghu|ghs|xoxb|xoxp)[-_][A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password|authorization)\s*[=:]\s*\S+"),
]


def redact(text: str) -> str:
    """写入 run/trace 任何 UI 可见字段前的脱敏：命中密钥形态一律替换为占位符。"""
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_value(item) for key, item in value.items()}
    return value


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_run_id(now: datetime | None = None) -> str:
    """run_id：日期 + 时分秒 + 微秒，单机单进程下可读且几乎不撞。"""
    dt = now or datetime.now()
    return f"run_{dt.strftime('%Y%m%d_%H%M%S_%f')}"


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
        self.root = root if root is not None else us.root / "runs"

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
        if status not in STEP_STATUSES:
            raise ValueError(f"非法 step status：{status!r}（允许：{STEP_STATUSES}）")
        step = {
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
    ) -> dict[str, Any]:
        event = {
            "event_id": redact(event_id),
            "event_type": redact(event_type),
            "created_at": _now_iso(),
            "payload": _redact_value(payload),
        }
        with self.stream_path(run_id).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def add_artifact(
        self,
        run_id: str,
        filename: str,
        content: str | bytes,
        *,
        renderer: str,
        title: str,
    ) -> Artifact:
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
        )
        run = self.load_run(run_id)
        run.artifacts = [a for a in run.artifacts if a.get("path") != filename]
        run.artifacts.append(asdict(artifact))
        self._write_run(run)
        return artifact

    def add_degrade(self, run_id: str, reason: str) -> None:
        """数据源降级一等公民化：录屏里「ftshare 不可用」这类事件落到 run 元数据。"""
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
        if status not in _TERMINAL_STATUSES:
            raise ValueError(f"finish_run 只接受终态：{_TERMINAL_STATUSES}，得到 {status!r}")
        run = self.load_run(run_id)
        run.status = status
        run.finished_at = _now_iso()
        run.error = redact(error) if error else None
        self._write_run(run)
        return run

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

    def load_stream_events(self, run_id: str) -> list[dict[str, Any]]:
        path = self.stream_path(run_id)
        if not path.exists():
            return []
        events = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                events.append(json.loads(line))
        return events

    def list_runs(self) -> list[Run]:
        if not self.root.exists():
            return []
        runs = []
        for run_file in sorted(self.root.glob("run_*/run.json")):
            runs.append(Run(**json.loads(run_file.read_text(encoding="utf-8"))))
        return runs

    # ---------- 内部 ----------

    def _write_run(self, run: Run) -> None:
        path = self.run_path(run.run_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(run), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)  # 原子替换，避免读到写了一半的 run.json
