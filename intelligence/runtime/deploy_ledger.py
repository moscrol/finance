"""部署切换审计账本：启动路径自报，而不是事后靠人改 inflight/main.md。

失败形状（W6 / 8792 a7e2d74f）：生产切换没有机器记录，验收时靠人对
readiness 才发现。人写台账会漏；launchd watcher 挂了也没人知道。

写入者 = 启动路径自己（BUILD.md「事实投递 > 提醒」）。账本必须落在数据仓
（``FINANCE_WS/state/``），不能跟 snapshot：生产 PYTHONPATH 指向
``~/.finance-runtime/finance-workspace-<sha>``，每切一次目录就换，写进快照
等于丢掉切换史。

进程 IO 放 runtime/（layer_audit 口径：做 IO → runtime）。lifespan 调用必须
fail-open：KeepAlive + ThrottleInterval 下，启动抛错会变成每 10 秒崩溃循环。
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LEDGER_NAME = "deploy-ledger.jsonl"
RELEVANT_ACTIONS = frozenset({"startup", "switch"})
_HEX_REV = re.compile(r"[^0-9a-f]")
_MIN_REV_PREFIX = 7


def resolve_ledger_path(
    repo_root: str | Path | None = None,
    ledger_path: str | Path | None = None,
) -> Path:
    """解析账本路径。覆盖序刻意把数据仓排在代码根前面。

    1. 显式 ``ledger_path`` 参数（CLI ``--ledger``）
    2. ``FINANCE_DEPLOY_LEDGER``（测试 / 显式覆盖）
    3. ``$FINANCE_WS/state/deploy-ledger.jsonl``（生产数据仓，跨快照）
    4. ``<repo_root>/state/deploy-ledger.jsonl``（create_app 传入的代码根）
    5. ``~/.finance-runtime/deploy-ledger.jsonl``（无数据仓、无代码根时）
    """

    if ledger_path:
        return Path(ledger_path).expanduser()
    override = os.environ.get("FINANCE_DEPLOY_LEDGER", "").strip()
    if override:
        return Path(override).expanduser()
    finance_ws = os.environ.get("FINANCE_WS", "").strip()
    if finance_ws:
        return Path(finance_ws).expanduser() / "state" / LEDGER_NAME
    if repo_root is not None:
        return Path(repo_root).expanduser() / "state" / LEDGER_NAME
    return Path.home() / ".finance-runtime" / LEDGER_NAME


def infer_port(argv: list[str] | None = None) -> int | None:
    """从 env 或 uvicorn argv 推断监听端口；认不出来就 None，不猜 8792。"""

    for key in ("PORT", "UVICORN_PORT"):
        raw = os.environ.get(key, "").strip()
        if raw.isdigit():
            return int(raw)
    args = list(sys.argv if argv is None else argv)
    if "--port" in args:
        index = args.index("--port")
        if index + 1 < len(args):
            token = args[index + 1]
            if token.isdigit():
                return int(token)
    return None


def utc_now_iso(unix: float | None = None) -> str:
    stamp = time.time() if unix is None else unix
    return (
        datetime.fromtimestamp(stamp, tz=timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def build_row(
    *,
    action: str,
    rev: str,
    snapshot_path: str | Path | None = None,
    port: int | None = None,
    pid: int | None = None,
    argv: list[str] | None = None,
    unix: float | None = None,
) -> dict[str, Any]:
    stamp = time.time() if unix is None else unix
    return {
        "ts": utc_now_iso(stamp),
        "unix": stamp,
        "rev": str(rev or ""),
        "snapshot_path": "" if snapshot_path is None else str(snapshot_path),
        "port": port,
        "pid": os.getpid() if pid is None else pid,
        "argv": list(sys.argv if argv is None else argv),
        "action": action,
    }


def append_row(path: Path, row: dict[str, Any]) -> None:
    """追加一行 JSONL 并 fsync。父目录不存在就建。失败向上抛。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    descriptor = os.open(path, flags, 0o644)
    try:
        offset = 0
        while offset < len(encoded):
            offset += os.write(descriptor, encoded[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def record_event(
    *,
    action: str,
    rev: str,
    snapshot_path: str | Path | None = None,
    port: int | None = None,
    pid: int | None = None,
    argv: list[str] | None = None,
    repo_root: str | Path | None = None,
    ledger_path: str | Path | None = None,
    fail_open: bool = False,
) -> Path | None:
    """写一行账本。``fail_open=True`` 时 IO 失败只记 warning、返回 None。"""

    row = build_row(
        action=action,
        rev=rev,
        snapshot_path=snapshot_path,
        port=port,
        pid=pid,
        argv=argv,
    )
    path = resolve_ledger_path(repo_root, ledger_path=ledger_path)
    try:
        append_row(path, row)
    except Exception as exc:  # noqa: BLE001 - lifespan 不得因账本 IO 崩
        logger.warning("deploy ledger write failed path=%s err=%s", path, exc)
        if fail_open:
            return None
        raise
    return path


def record_startup(
    *,
    rev: str,
    snapshot_path: str | Path | None = None,
    repo_root: str | Path | None = None,
    port: int | None = None,
) -> Path | None:
    """create_app lifespan 入口。pytest 默认跳过，避免污染夹具目录。

    测试要覆盖 lifespan 时显式设 ``FINANCE_DEPLOY_LEDGER`` 即可重新打开。
    """

    if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get(
        "FINANCE_DEPLOY_LEDGER", ""
    ).strip():
        return None
    return record_event(
        action="startup",
        rev=rev,
        snapshot_path=snapshot_path,
        port=infer_port() if port is None else port,
        repo_root=repo_root,
        fail_open=True,
    )


def last_relevant_row(path: Path, port: int | None = None) -> dict[str, Any] | None:
    """最后一条 ``startup`` / ``switch``。坏行跳过，认不出来当没有。

    ``port`` 给定时只统计该端口的行——sidecar（如 8796）与生产（8792）共用
    同一本账，不过滤会拿 sidecar 启动行去对生产 health（实测 2026-08-19 假
    ``rev_mismatch``）。``port`` 为 ``None`` 的行（旧版 switch 未记端口、或
    infer 失败）计入任何端口：宁可误报生产切换，也不因缺字段漏报。
    """

    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    last: dict[str, Any] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if row.get("action") not in RELEVANT_ACTIONS:
            continue
        if port is not None:
            row_port = row.get("port")
            if row_port is not None and row_port != port:
                continue
        last = row
    return last


def normalize_rev(value: object) -> str:
    return _HEX_REV.sub("", str(value or "").lower())


def revs_match(left: object, right: object) -> bool:
    """短 sha 与全 sha 视为同一 rev（最短 7 hex，git 默认短名下限）。"""

    first, second = normalize_rev(left), normalize_rev(right)
    if not first or not second:
        return False
    shorter, longer = sorted((first, second), key=len)
    return len(shorter) >= _MIN_REV_PREFIX and longer.startswith(shorter)


def health_revision(payload: dict[str, Any]) -> str:
    runtime = payload.get("runtime")
    if not isinstance(runtime, dict):
        return ""
    return str(runtime.get("source_revision") or "")


def check_against_health(
    ledger_path: Path, health: dict[str, Any], port: int | None = None
) -> dict[str, Any]:
    """账本最后相关行 vs health 实报 rev。不一致 / 缺账本 → ok=False。

    ``port`` 给定时按端口过滤账本行（见 ``last_relevant_row``），避免其他
    端口的 sidecar 启动行顶掉被检服务的尾行。
    """

    row = last_relevant_row(ledger_path, port=port)
    live_rev = health_revision(health)
    ledger_rev = "" if row is None else str(row.get("rev") or "")
    if row is None:
        reason = "missing_ledger_row"
        ok = False
    elif not live_rev:
        reason = "missing_health_rev"
        ok = False
    elif not revs_match(ledger_rev, live_rev):
        reason = "rev_mismatch"
        ok = False
    else:
        reason = "ok"
        ok = True
    return {
        "ok": ok,
        "reason": reason,
        "ledger_path": str(ledger_path),
        "ledger_rev": ledger_rev,
        "ledger_action": None if row is None else row.get("action"),
        "health_rev": live_rev,
        "port": port,
    }
