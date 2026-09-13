"""06 的单 writer：管理元数据（依赖绑定 / 管理动作事件）、05 原始事件、冻结协议与不可变收据。

落点 ``UserSpace.root/research_evolution/``（spec 06 §5，ledger-map 已登记）：

```
dependency_bindings.jsonl      judgment-maintenance-binding/v1 + 06 封套（append-only）
maintenance_actions.jsonl      judgment-maintenance-event/v1 + 06 封套（append-only；含 idempotency_key）
product_value_events.jsonl     product-value-event/v1（append-only；同 event_id 同内容不重复追加）
run_links.jsonl                维护请求 ↔ 新 run 的关联登记（append-only；item_id+run_id 幂等）
protocols/<protocol_hash>.json 冻结协议（不可变）
receipts/<receipt_id>.json     measurement-receipt/v1（不可变）
summaries/<summary_id>.json    pilot-summary/v1（不可变；新版本带 supersedes）
registrations/<id>.json        试点登记（协议 / case_pair / assignment；不可变）
process_receipts.jsonl         04 用的流程收据：coverage / exposure / exercise_seen / evidence_use …（append-only）
```

并发与幂等（spec 06 §5「单 writer 仍需跨进程幂等与并发保护」）：

- 复用 ``run_store._file_transaction_lock`` 的做法：进程内 ``Lock`` + ``fcntl.flock`` 独占锁文件；
  读-判-追加在同一把锁内完成，两个动作基于同一 ``expected_management_revision`` 竞争时至多一个成功；
- 追加：单行 JSON + flush + fsync；重试不重复（同键同内容 → 返回已存在的那条，不追加）；
- 不可变发布：tmp + ``os.link``（已存在则比对内容：同 → 幂等返回；异 → 冲突），与 03 ``Repository.publish`` 同原语；
- 任一行解析失败 → ``StoreCorrupt``：拒绝继续业务写入并返回可见错误，不静默跳行。

这层**不**解释业务：``expected_*`` 的比较由 facade 在 ``transaction()`` 内用 01 的 ``validate_action`` 完成；
本模块只保证「锁内读到的就是提交时的台账」。
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any, Iterator, Mapping

from intelligence.services.research_evolution.contracts import (
    ERR_IDEMPOTENCY_MISMATCH,
    ApiError,
    StoreCorrupt,
    canonical_json,
    digest,
)

BINDINGS_FILE = "dependency_bindings.jsonl"
ACTIONS_FILE = "maintenance_actions.jsonl"
PRODUCT_VALUE_EVENTS_FILE = "product_value_events.jsonl"
PROCESS_RECEIPTS_FILE = "process_receipts.jsonl"
RUN_LINKS_FILE = "run_links.jsonl"
PROTOCOLS_DIR = "protocols"
RECEIPTS_DIR = "receipts"
SUMMARIES_DIR = "summaries"
REGISTRATIONS_DIR = "registrations"
LOCK_FILE = ".research_evolution.lock"

_LOCKS: dict[str, Lock] = {}
_LOCKS_GUARD = Lock()


class StoreLockTimeout(RuntimeError):
    """``try_transaction`` 在有界等待内拿不到锁。观察器类写入方拿它当「跳过本次测量」的信号。"""


def _process_lock(path: Path) -> Lock:
    key = str(path)
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, Lock())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise StoreCorrupt(
                    f"台账 {path.name} 第 {lineno} 行不是合法 JSON，已停止业务写入",
                    detail={"file": path.name, "line": lineno},
                ) from exc
            if not isinstance(row, dict):
                raise StoreCorrupt(f"台账 {path.name} 第 {lineno} 行不是对象", detail={"file": path.name, "line": lineno})
            rows.append(row)
    return rows


def _append_line(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


class EvolutionStore:
    """一个 owner 的私有台账根。所有写方法都要求在 ``transaction()`` 内调用（否则自行加锁）。"""

    def __init__(self, root: str | Path, owner_user_id: str) -> None:
        self.root = Path(root)
        self.owner_user_id = owner_user_id
        self._in_txn = False

    # ---- 路径 -------------------------------------------------------------- #
    @property
    def bindings_path(self) -> Path:
        return self.root / BINDINGS_FILE

    @property
    def actions_path(self) -> Path:
        return self.root / ACTIONS_FILE

    @property
    def product_value_events_path(self) -> Path:
        return self.root / PRODUCT_VALUE_EVENTS_FILE

    @property
    def process_receipts_path(self) -> Path:
        return self.root / PROCESS_RECEIPTS_FILE

    @property
    def run_links_path(self) -> Path:
        return self.root / RUN_LINKS_FILE

    def _dir(self, name: str) -> Path:
        return self.root / name

    # ---- 事务 -------------------------------------------------------------- #
    @contextmanager
    def transaction(self) -> Iterator["EvolutionStore"]:
        """进程内锁 + 文件锁；锁内读到的台账就是提交时的台账。非重入。"""
        self.root.mkdir(parents=True, exist_ok=True)
        lock_path = self.root / LOCK_FILE
        with _process_lock(lock_path):
            fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                self._in_txn = True
                yield self
            finally:
                self._in_txn = False
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

    @contextmanager
    def try_transaction(self, timeout: float = 0.25) -> Iterator["EvolutionStore"]:
        """有界等待的事务：拿不到锁（进程锁或文件锁）就抛 ``StoreLockTimeout``，不无限等。

        给观察器 / 测量类写入方用：测量绝不能把被测对象（真实 run 生命周期）堵在锁上（QC Q9）。
        """
        import time as _time

        self.root.mkdir(parents=True, exist_ok=True)
        lock_path = self.root / LOCK_FILE
        lock = _process_lock(lock_path)
        if not lock.acquire(timeout=timeout):
            raise StoreLockTimeout(f"进程内锁等待超过 {timeout}s：{lock_path}")
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            deadline = _time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if _time.monotonic() >= deadline:
                        raise StoreLockTimeout(f"文件锁等待超过 {timeout}s：{lock_path}") from None
                    _time.sleep(0.01)
            self._in_txn = True
            try:
                yield self
            finally:
                self._in_txn = False
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
            lock.release()

    def _locked(self) -> Iterator[None]:
        if self._in_txn:
            yield
            return
        with self.transaction():
            yield

    # ---- 读 --------------------------------------------------------------- #
    def list_bindings(self) -> list[dict[str, Any]]:
        return [r for r in _read_jsonl(self.bindings_path) if r.get("owner_user_id") == self.owner_user_id]

    def list_action_records(self) -> list[dict[str, Any]]:
        return [r for r in _read_jsonl(self.actions_path) if r.get("owner_user_id") == self.owner_user_id]

    def list_events(self) -> list[dict[str, Any]]:
        """01 ``ManagementEvent`` 台账顺序（去掉 06 封套）。"""
        return [dict(r["event"]) for r in self.list_action_records() if isinstance(r.get("event"), dict)]

    def list_product_value_events(self) -> list[dict[str, Any]]:
        return [r for r in _read_jsonl(self.product_value_events_path) if r.get("owner_user_id") == self.owner_user_id]

    def list_process_receipts(self) -> list[dict[str, Any]]:
        return [r for r in _read_jsonl(self.process_receipts_path) if r.get("owner_user_id") == self.owner_user_id]

    def list_immutable(self, dirname: str) -> list[dict[str, Any]]:
        folder = self._dir(dirname)
        if not folder.exists():
            return []
        out: list[dict[str, Any]] = []
        for path in sorted(folder.glob("*.json")):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise StoreCorrupt(f"{dirname}/{path.name} 不是合法 JSON", detail={"file": f"{dirname}/{path.name}"}) from exc
            if isinstance(row, dict) and row.get("owner_user_id") in (None, self.owner_user_id):
                out.append(row)
        return out

    def read_immutable(self, dirname: str, content_id: str) -> dict[str, Any] | None:
        path = self._immutable_path(dirname, content_id)
        if not path.exists():
            return None
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StoreCorrupt(f"{dirname}/{path.name} 不是合法 JSON", detail={"file": f"{dirname}/{path.name}"}) from exc
        if not isinstance(row, dict) or row.get("owner_user_id") not in (None, self.owner_user_id):
            return None
        return row

    # ---- 追加（幂等） ------------------------------------------------------ #
    def append_once(self, path: Path, row: Mapping[str, Any], *, key: str, key_value: str) -> tuple[dict[str, Any], bool]:
        """同键已存在：同内容 → 返回原行 (row, False)；异内容 → ``idempotency_payload_mismatch``。"""
        for _ in self._locked():
            rows = _read_jsonl(path)
            for existing in rows:
                if str(existing.get(key) or "") == key_value and existing.get("owner_user_id") == self.owner_user_id:
                    if existing.get("content_digest") == row.get("content_digest"):
                        return existing, False
                    raise ApiError(
                        ERR_IDEMPOTENCY_MISMATCH,
                        "同一幂等键已绑定不同载荷，不得复用",
                        detail={"key": key, "value": key_value},
                    )
            stored = dict(row)
            _append_line(path, stored)
            return stored, True
        raise AssertionError("unreachable")

    def append_binding(self, binding: Mapping[str, Any], *, created_at: str, source: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        if binding.get("owner_user_id") != self.owner_user_id:
            raise ApiError("owner_forbidden", "绑定归属与台账 owner 不一致")
        content = {"binding": dict(binding), "source": dict(source)}
        row = {
            "schema_version": "research-evolution-binding-record/v1",
            "owner_user_id": self.owner_user_id,
            "binding_id": binding["binding_id"],
            "binding_version": binding["binding_version"],
            "created_at": created_at,
            "content_digest": digest(content),
            **content,
        }
        return self.append_once(self.bindings_path, row, key="binding_id", key_value=str(binding["binding_id"]))

    def append_action(
        self,
        event: Mapping[str, Any],
        *,
        idempotency_key: str,
        action: str,
        payload_digest: str,
        recorded_at: str,
        conversation_id: str | None,
        result: Mapping[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        if event.get("owner_user_id") != self.owner_user_id:
            raise ApiError("owner_forbidden", "事件归属与台账 owner 不一致")
        content = {"event": dict(event), "action": action, "payload_digest": payload_digest}
        row = {
            "schema_version": "research-evolution-action-record/v1",
            "owner_user_id": self.owner_user_id,
            "idempotency_key": idempotency_key,
            "item_id": event.get("item_id"),
            "conversation_id": conversation_id,
            "recorded_at": recorded_at,
            "content_digest": digest(content),
            "result": dict(result),
            **content,
        }
        return self.append_once(self.actions_path, row, key="idempotency_key", key_value=idempotency_key)

    def append_action_record(
        self,
        *,
        idempotency_key: str,
        action: str,
        payload_digest: str,
        recorded_at: str,
        conversation_id: str | None,
        item_id: str | None,
        result: Mapping[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        """无 01 事件的幂等记录（link_run 运行中登记、select_task 选择）：动作已被接受，但没有状态迁移。

        ``list_events`` 只取 ``event`` 是 dict 的行，这里 ``event=None`` 不进 01 折叠，安全。
        """
        row = {
            "schema_version": "research-evolution-action-record/v1",
            "owner_user_id": self.owner_user_id,
            "idempotency_key": idempotency_key,
            "item_id": item_id,
            "conversation_id": conversation_id,
            "recorded_at": recorded_at,
            "event": None,
            "action": action,
            "payload_digest": payload_digest,
            "content_digest": digest({"event": None, "action": action, "payload_digest": payload_digest}),
            "result": dict(result),
        }
        return self.append_once(self.actions_path, row, key="idempotency_key", key_value=idempotency_key)

    def find_action(self, idempotency_key: str) -> dict[str, Any] | None:
        for row in self.list_action_records():
            if row.get("idempotency_key") == idempotency_key:
                return row
        return None

    def find_binding(self, binding_id: str) -> dict[str, Any] | None:
        """按 binding_id 定位已提交的绑定记录（幂等重试要先找到它，复用首个服务端时间）。"""
        for row in self.list_bindings():
            if str(row.get("binding_id") or "") == str(binding_id):
                return row
        return None

    def find_product_value_event(self, event_id: str) -> dict[str, Any] | None:
        for row in self.list_product_value_events():
            if str(row.get("event_id") or "") == str(event_id):
                return row
        return None

    # ---- 维护请求 ↔ run 关联登记 ------------------------------------------- #
    def append_run_link(self, link: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        """登记「本次维护请求发起了这个 run」。同 (item_id, run_id) 同内容幂等；异内容冲突。

        这是 link_run 在 run 终态时核验「持久化关联」的锚点之一（另一个是用户消息上的
        continuation.inherits.maintenance_item_id）：接受消息 ≠ 研究完成，但关联从接受那一刻就落盘。
        """
        if link.get("owner_user_id") != self.owner_user_id:
            raise ApiError("owner_forbidden", "关联登记归属与台账 owner 不一致")
        row = {**dict(link), "content_digest": digest(dict(link))}
        return self.append_once(self.run_links_path, row, key="link_id", key_value=str(link["link_id"]))

    def list_run_links(self, *, item_id: str | None = None) -> list[dict[str, Any]]:
        rows = [r for r in _read_jsonl(self.run_links_path) if r.get("owner_user_id") == self.owner_user_id]
        if item_id is not None:
            rows = [r for r in rows if str(r.get("item_id") or "") == str(item_id)]
        return rows

    def find_run_link(self, *, item_id: str, run_id: str) -> dict[str, Any] | None:
        for row in self.list_run_links(item_id=item_id):
            if str(row.get("run_id") or "") == str(run_id):
                return row
        return None

    def latest_run_link(self, *, item_id: str) -> dict[str, Any] | None:
        rows = self.list_run_links(item_id=item_id)
        return rows[-1] if rows else None

    def append_product_value_event(self, event: Mapping[str, Any], *, content_hash: str) -> tuple[dict[str, Any], bool]:
        """同 event_id 同内容 → 不重复追加；同 id 异内容 → 冲突（05 ``prepare_events`` 的口径）。"""
        if event.get("owner_user_id") != self.owner_user_id:
            raise ApiError("owner_forbidden", "事件归属与台账 owner 不一致")
        row = {**dict(event), "content_digest": content_hash}
        return self.append_once(self.product_value_events_path, row, key="event_id", key_value=str(event["event_id"]))

    def append_process_receipt(self, receipt: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        """04 的流程收据（``coverage`` / ``exposure`` / ``exercise_seen`` / ``evidence_use`` …）。"""
        if receipt.get("owner_user_id") != self.owner_user_id:
            raise ApiError("owner_forbidden", "收据归属与台账 owner 不一致")
        row = {**dict(receipt), "content_digest": digest(dict(receipt))}
        return self.append_once(self.process_receipts_path, row, key="receipt_id", key_value=str(receipt["receipt_id"]))

    # ---- 不可变发布 --------------------------------------------------------- #
    def _immutable_path(self, dirname: str, content_id: str) -> Path:
        safe = str(content_id).strip()
        if not safe or "/" in safe or "\\" in safe or safe in {".", ".."} or safe.startswith("."):
            raise ApiError("invalid_request", "非法内容 id", detail={"where": f"{dirname}.id"})
        return self._dir(dirname) / f"{safe}.json"

    def publish_immutable(self, dirname: str, content_id: str, value: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        """tmp + ``os.link``：已存在则比对内容，同 → (原件, False)；异 → 冲突。"""
        target = self._immutable_path(dirname, content_id)
        for _ in self._locked():
            target.parent.mkdir(parents=True, exist_ok=True)
            # **不往正文里塞 owner**：这些件是内容寻址的（协议哈希、收据 id 都由正文算出），
            # 多一个字段就把它自己的哈希打坏——05 的 `validate_protocol` 会当场报
            # 「protocol_hash 与内容不符（冻结后被改过？）」。归属靠路径隔离：
            # 每个 owner 的根是 `user_space(owner).root/research_evolution/`，文件不共享。
            payload = dict(value)
            text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
            if target.exists():
                try:
                    existing = json.loads(target.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    raise StoreCorrupt(f"{dirname}/{target.name} 不是合法 JSON", detail={"file": f"{dirname}/{target.name}"}) from exc
                if canonical_json(_strip_volatile(existing)) == canonical_json(_strip_volatile(payload)):
                    return existing, False
                raise ApiError(
                    ERR_IDEMPOTENCY_MISMATCH,
                    "同一内容 id 已发布不同内容，拒绝覆盖",
                    detail={"dir": dirname, "id": content_id},
                )
            fd, name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(text)
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    os.link(name, target)
                except FileExistsError:
                    existing = json.loads(target.read_text(encoding="utf-8"))
                    if canonical_json(_strip_volatile(existing)) == canonical_json(_strip_volatile(payload)):
                        return existing, False
                    raise ApiError(ERR_IDEMPOTENCY_MISMATCH, "同一内容 id 已发布不同内容，拒绝覆盖", detail={"dir": dirname, "id": content_id}) from None
            finally:
                try:
                    os.unlink(name)
                except FileNotFoundError:
                    pass
            return payload, True
        raise AssertionError("unreachable")


_VOLATILE_KEYS = ("generated_at", "stored_at")


def _strip_volatile(value: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in value.items() if k not in _VOLATILE_KEYS}


__all__ = [
    "ACTIONS_FILE",
    "BINDINGS_FILE",
    "PROCESS_RECEIPTS_FILE",
    "LOCK_FILE",
    "PRODUCT_VALUE_EVENTS_FILE",
    "RUN_LINKS_FILE",
    "PROTOCOLS_DIR",
    "RECEIPTS_DIR",
    "REGISTRATIONS_DIR",
    "SUMMARIES_DIR",
    "EvolutionStore",
]
