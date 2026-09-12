"""Content addressed JSON files, atomically published without overwrites."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from .protocol import canonical_bytes, clock_now, digest, iso_date, validate_protocol

KINDS = frozenset({"history", "capture", "recheck"})
# 封存标记与活跃指针都不是「记录」：前者是协议级状态，后者是可变绑定，
# 都不走 write_record 的按日分区内容寻址路径。
SUPERSEDED_MARKER = "superseded.json"
ACTIVE_POINTER = "active.json"
_ID = re.compile(r"[0-9a-f]{64}")


def _check_id(value: str) -> None:
    if not _ID.fullmatch(value):
        raise ValueError("invalid content id")


def _read(path: Path) -> dict:
    if path.is_symlink():
        raise ValueError("symlink records are not supported")
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        canonical_bytes(result)
        if not isinstance(result, dict):
            raise ValueError("record must be an object")
        return result
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("invalid JSON record") from exc


def _publish(path: Path, value: dict) -> None:
    data = canonical_bytes(value)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".pending-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if _read(path) != value:
                raise ValueError("existing content differs or is corrupt") from None
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def register(root, protocol) -> Path:
    validate_protocol(protocol)
    parent = Path(root).expanduser().resolve()
    parent.mkdir(parents=True, exist_ok=True)
    directory = parent / protocol["protocol_id"]
    if directory.is_symlink():
        raise ValueError("symlink study directories are not supported")
    directory.mkdir(exist_ok=True)
    path = directory / "protocol.json"
    if path.exists():
        old = load_protocol(directory)
        if {k: v for k, v in old.items() if k != "created_at"} != {
            k: v for k, v in protocol.items() if k != "created_at"
        }:
            raise ValueError("protocol content differs")
        return directory
    try:
        _publish(
            path,
            {
                "schema_version": 1,
                "protocol": protocol,
                "content_sha256": digest(protocol),
            },
        )
    except ValueError:
        old = load_protocol(directory)
        if {k: v for k, v in old.items() if k != "created_at"} != {
            k: v for k, v in protocol.items() if k != "created_at"
        }:
            raise
    return directory


def load_protocol(study_dir) -> dict:
    directory = Path(study_dir)
    _check_id(directory.name)
    if directory.is_symlink():
        raise ValueError("symlink study directories are not supported")
    envelope = _read(directory / "protocol.json")
    if (
        set(envelope) != {"schema_version", "protocol", "content_sha256"}
        or envelope["schema_version"] != 1
        or envelope["content_sha256"] != digest(envelope["protocol"])
    ):
        raise ValueError("protocol envelope hash mismatch")
    protocol = envelope["protocol"]
    validate_protocol(protocol, require_current=False)
    if protocol["protocol_id"] != directory.name:
        raise ValueError("protocol directory id mismatch")
    return protocol


def write_record(study_dir, kind, payload) -> Path:
    if kind not in KINDS:
        raise ValueError("invalid record kind")
    directory = Path(study_dir)
    protocol = load_protocol(directory)
    if (
        not isinstance(payload, dict)
        or payload.get("protocol_id") != protocol["protocol_id"]
    ):
        raise ValueError("record must refer to its protocol")
    record = {"schema_version": 1, "kind": kind, "payload": payload}
    record["content_sha256"] = digest(record)
    if kind == "capture":
        if "outcomes" in payload or "comparison" in payload:
            raise ValueError("capture must contain features only")
        local_day = iso_date(payload["features"]["end"])
    else:
        local_day = clock_now().date().isoformat()
    parent = directory
    for part in (kind, local_day):
        parent = parent / part
        if parent.is_symlink():
            raise ValueError("symlink record directories are not supported")
        parent.mkdir(exist_ok=True)
    target = parent / (record["content_sha256"] + ".json")
    _publish(target, record)
    return target


def supersede(study_dir, *, successor_id=None, reason="", now=None) -> Path:
    """把一份协议**真正**停用：写封存标记，并让所有消费者不再枚举它。

    只写一条 `superseded` 记录是不够的——09-12 质检实测：手写标记后 `list_studies`
    照常枚举、`flywheel.fingerprint` 不变、standing 摘要仍 `fresh=True`，它最多是人工
    备忘，拦不住任何消费者。这里让标记带上运行语义（见 `list_studies`）。
    """
    directory = Path(study_dir).expanduser()
    protocol = load_protocol(directory)          # 顺带校验这确实是一份 study
    if successor_id is not None and not _ID.fullmatch(str(successor_id)):
        raise ValueError("invalid successor protocol id")
    marker = directory / SUPERSEDED_MARKER
    record = {
        "protocol_id": protocol["protocol_id"],
        "successor_id": successor_id,
        "reason": str(reason or ""),
        "superseded_at": clock_now(now).isoformat(),
    }
    if marker.is_file():
        # 同一封存意图重试要幂等：`superseded_at` 每次都是 now，直接 _publish 必然
        # 撞上不可覆盖发布而 ValueError（09-12 质检实测）。封存时刻以**首次**为准，
        # 重试不刷新；继任或理由不同则是另一件事, 必须报错而不是悄悄改写封存原因。
        existing = _read(marker)
        same = (existing.get("successor_id") == record["successor_id"]
                and existing.get("reason") == record["reason"])
        if not same:
            raise ValueError(
                "already superseded with a different successor/reason: "
                f"existing successor={existing.get('successor_id')!r} "
                f"reason={existing.get('reason')!r}"
            )
        return marker
    _publish(marker, record)
    return marker


def is_superseded(study_dir) -> bool:
    return (Path(study_dir).expanduser() / SUPERSEDED_MARKER).is_file()


def list_studies(root, *, include_superseded: bool = False) -> list:
    """Study directories under a root, oldest protocol id first; missing root → [].

    默认**跳过已封存的协议**：这是封存标记的运行语义所在。要做历史盘点/审计时
    显式传 `include_superseded=True`，让「看得到」和「还在消费」分开。
    """
    parent = Path(root).expanduser()
    if not parent.is_dir():
        return []
    out = []
    for child in sorted(parent.iterdir()):
        if _ID.fullmatch(child.name) and not child.is_symlink() and child.is_dir():
            if (child / "protocol.json").is_file():
                if include_superseded or not is_superseded(child):
                    out.append(child)
    return out


def set_active(root, study_dir, *, now=None) -> Path:
    """把夜跑等消费者的绑定切到某份协议。

    指针是**可变绑定**而非证据，所以用 `os.replace` 原子改写（覆盖是正确行为）；
    证据类写入仍走 `_publish` 的不可覆盖路径。
    """
    parent = Path(root).expanduser().resolve()
    directory = Path(study_dir).expanduser().resolve()
    # 指针只存目录名, 读回时按 root/名字 拼接。若不校验归属, 就能「写成功但读不回」：
    # study 在 users/linxiaoqi5111 下、指针却落到 users/default, activate 返回 0 而
    # 夜跑那个用户 active 返回 1（09-12 质检实测）。跨根输入一律拒绝, 不做半支持。
    if directory.parent != parent:
        raise ValueError(
            f"study_dir does not belong to root: study_dir={directory} root={parent}"
        )
    protocol = load_protocol(directory)
    if is_superseded(directory):
        raise ValueError("refusing to activate a superseded protocol")
    parent.mkdir(parents=True, exist_ok=True)
    pointer = parent / ACTIVE_POINTER
    data = canonical_bytes({
        "protocol_id": protocol["protocol_id"],
        "study_dir": directory.name,
        "activated_at": clock_now(now).isoformat(),
    })
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=parent, prefix=".pending-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, pointer)
        temporary = None
        descriptor = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    # 读回核对: 「写入返回 0」不等于「消费者读得到」, 这正是上一版漏掉的那步。
    if active_study(parent) != directory:
        raise ValueError(f"active pointer readback mismatch: {pointer}")
    return pointer


def active_binding(root) -> dict:
    """当前绑定的**三态**：从未配置 / 有效 / 配置过但失效。

    上一版把「没配过」和「配过但坏了」都压成 None, 夜跑于是一律回退内置默认——
    封存了活跃协议也只会静默换回旧实验, 没有任何告警（09-12 质检实测）。
    这两种情况的正确处置相反：前者兼容默认, 后者必须停下来喊人。
    """
    # resolve 一次：macOS 上 /var 是 /private/var 的符号链接, 不归一化就会出现
    # 「set_active 内部读回通过、CLI 读回核对失败」这种只差前缀的假不一致。
    # resolve 一次：macOS 上 /var 是 /private/var 的符号链接, 不归一化就会出现
    # 「set_active 内部读回通过、CLI 读回核对失败」这种只差前缀的假不一致。
    parent = Path(root).expanduser().resolve()
    pointer = parent / ACTIVE_POINTER
    # **只有确实不存在才算 unset。** 用 lexists 而不是 is_file()：目录、悬空软链
    # 都会让 is_file() 返回 False, 于是「指针坏了」被误判成「没配过」, 夜跑照样
    # 静默回退旧协议（09-12 质检实测）。存在但不是普通文件 → corrupt。
    if not os.path.lexists(pointer):
        return {"state": "unset", "study_dir": None, "detail": "未配置 active 指针"}
    if not pointer.is_file():
        return {"state": "corrupt", "study_dir": None,
                "detail": f"指针存在但不是普通文件（目录或悬空软链）: {pointer}"}
    try:
        doc = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"state": "corrupt", "study_dir": None, "detail": f"指针读不出: {exc}"}
    if not isinstance(doc, dict):
        # `[]` / `null` / `"x"` 都是合法 JSON, 但 doc.get 会抛 AttributeError,
        # 未捕获就成了进程 exit 1——恰好与「从未配置」的业务码撞车。
        return {"state": "corrupt", "study_dir": None,
                "detail": f"指针内容不是 JSON 对象: {type(doc).__name__}"}
    name = str(doc.get("study_dir") or "")
    if not _ID.fullmatch(name):
        return {"state": "corrupt", "study_dir": None,
                "detail": f"指针里的 study_dir 不是合法协议 id: {name!r}"}
    candidate = parent / name
    if not (candidate / "protocol.json").is_file():
        return {"state": "missing_target", "study_dir": None,
                "detail": f"指针指向的协议目录不存在或缺 protocol.json: {candidate}"}
    # 协议本身要能加载通过校验, 否则 --print-dir 说「有效」、普通模式说「损坏」,
    # 有效性由展示格式决定（质检实测 rc=0 vs rc=2）。判定只能有一处。
    try:
        load_protocol(candidate)
    except Exception as exc:  # noqa: BLE001 — 任何加载/校验失败都算坏协议
        return {"state": "corrupt", "study_dir": None,
                "detail": f"指针指向的协议加载失败: {type(exc).__name__}: {exc}"}
    if is_superseded(candidate):
        return {"state": "superseded", "study_dir": None,
                "detail": f"指针指向的协议已封存: {candidate}"}
    return {"state": "ok", "study_dir": candidate, "detail": ""}


def active_study(root) -> Path | None:
    """当前绑定的协议目录；未登记、指向不存在或已封存 → None（由调用方决定回退）。"""
    return active_binding(root)["study_dir"]


def list_records(study_dir, kind) -> list:
    """Record files of one kind, ordered by partition day then content id."""
    if kind not in KINDS:
        raise ValueError("invalid record kind")
    parent = Path(study_dir) / kind
    if not parent.is_dir():
        return []
    out = []
    for day in sorted(parent.iterdir()):
        if day.is_symlink() or not day.is_dir():
            continue
        try:
            iso_date(day.name)
        except ValueError:
            continue
        for path in sorted(day.glob("*.json")):
            if _ID.fullmatch(path.stem) and not path.is_symlink():
                out.append(path)
    return out


def publish_json(path, value) -> Path:
    """Atomically publish a derived JSON view; identical content is idempotent.

    Derived views (standing digests, candidate drafts) share the record
    discipline: never overwritten in place, always canonical bytes.
    """
    target = Path(path)
    if target.is_symlink():
        raise ValueError("symlink targets are not supported")
    target.parent.mkdir(parents=True, exist_ok=True)
    _publish(target, value)
    return target


def replace_json(path, value) -> Path:
    """Atomically (re)publish a derived cache view that may legitimately change.

    Standing digests carry ``generated_at``; re-deriving the same inputs must
    not fail on a stale timestamp, so this replaces instead of refusing. Only
    for caches keyed by an input fingerprint — records still use ``_publish``.
    """
    target = Path(path)
    if target.is_symlink():
        raise ValueError("symlink targets are not supported")
    target.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(value)
    with tempfile.NamedTemporaryFile(
        dir=target.parent, prefix=".pending-", delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, target)
    return target


def read_record(path) -> dict:
    path = Path(path)
    if path.suffix != ".json" or path.parent.parent.name not in KINDS:
        raise ValueError("invalid record path")
    _check_id(path.stem)
    iso_date(path.parent.name)
    protocol = load_protocol(path.parents[2])
    if path.parent.is_symlink() or path.parent.parent.is_symlink():
        raise ValueError("symlink record directories are not supported")
    record = _read(path)
    if set(record) != {"schema_version", "kind", "payload", "content_sha256"}:
        raise ValueError("invalid record fields")
    expected = digest({k: v for k, v in record.items() if k != "content_sha256"})
    if (
        record["schema_version"] != 1
        or record["kind"] != path.parent.parent.name
        or record["content_sha256"] != expected
        or path.stem != expected
        or not isinstance(record["payload"], dict)
        or record["payload"].get("protocol_id") != protocol["protocol_id"]
    ):
        raise ValueError("record hash or identity mismatch")
    return record
