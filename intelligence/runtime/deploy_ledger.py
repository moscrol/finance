"""部署切换审计账本：启动路径自报，而不是事后靠人改 inflight/main.md。

失败形状（W6 / 8792 a7e2d74f）：生产切换没有机器记录，验收时靠人对
readiness 才发现。人写台账会漏；launchd watcher 挂了也没人知道。

写入者 = 启动路径自己（BUILD.md「事实投递 > 提醒」）。账本只有一个家
``~/.finance-runtime/deploy-ledger.jsonl``（``default_ledger_path``）：不跟 snapshot（生产
PYTHONPATH 指向 ``~/.finance-runtime/finance-workspace-<sha>``，每切一次目录就换，写进快照等于
丢掉切换史），也不再跟 ``$FINANCE_WS/state/`` 或代码根。2026-09-09 工单 #44 量出那两级让账本
长出两个家——主树 ``state/`` 281 行（带 ``FINANCE_WS`` 的生产启动 + 部署脚本），
``~/.finance-runtime`` 24 行（链切规程显式 ``--ledger``），生产真实的 rev 只在后者里。解析结果
随环境变量与调用者目录变，就一定分家。旧位置由 ``legacy_ledger_candidates`` 列出，只供读取侧
过渡与 ``migrate-homes`` 并入。

进程 IO 放 runtime/（layer_audit 口径：做 IO → runtime）。lifespan 调用必须
fail-open：KeepAlive + ThrottleInterval 下，启动抛错会变成每 10 秒崩溃循环。
"""

from __future__ import annotations

from collections.abc import Sequence
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


def default_ledger_path() -> Path:
    """账本唯一的默认家：``~/.finance-runtime/deploy-ledger.jsonl``。

    这台机器上唯一不随快照、worktree、环境变量变的位置：hook（宿主 python3、无 ``FINANCE_WS``）、
    launchd 生产进程、部署脚本、手工链切四种写读者零配置都落到同一个文件；episode store 的末级
    也是它。``scripts/worktree_board.py`` 抄了这个地址（SessionStart 不 import 包），改址两处一起改。
    """

    return Path.home() / ".finance-runtime" / LEDGER_NAME


def resolve_ledger_path(
    repo_root: str | Path | None = None,
    ledger_path: str | Path | None = None,
) -> Path:
    """解析账本路径：显式 ``ledger_path``（CLI ``--ledger``）> ``FINANCE_DEPLOY_LEDGER`` > 唯一默认家。

    ``repo_root`` 保留在签名里（``create_app`` 与 CLI 仍在传），但**不再参与解析**：它与
    ``$FINANCE_WS/state/`` 两级正是「两个家」的来源（模块 docstring）。旧位置见
    ``legacy_ledger_candidates``。
    """

    if ledger_path:
        return Path(ledger_path).expanduser()
    override = os.environ.get("FINANCE_DEPLOY_LEDGER", "").strip()
    if override:
        return Path(override).expanduser()
    return default_ledger_path()


def legacy_ledger_candidates(
    repo_root: str | Path | None = None,
    *,
    finance_ws: str | None = None,
) -> list[Path]:
    """老写入序里会落账的两级：``$FINANCE_WS/state/``、``<repo_root>/state/``（按老顺序，去重）。

    只给读取侧过渡（旧代码的生产进程切流前仍往这里写 startup）与 ``migrate-homes`` 并入用；
    写入者不得再拿它当目标。
    """

    workspace = (
        finance_ws if finance_ws is not None else os.environ.get("FINANCE_WS", "")
    ).strip()
    candidates: list[Path] = []
    if workspace:
        candidates.append(Path(workspace).expanduser() / "state" / LEDGER_NAME)
    if repo_root is not None:
        candidates.append(Path(repo_root).expanduser() / "state" / LEDGER_NAME)
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def read_rows(path: Path) -> list[dict[str, Any]]:
    """读整本账；坏行跳过（与 ``last_relevant_row`` 同口径），文件不在回空。"""

    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _row_identity(row: dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def _row_order(row: dict[str, Any]) -> float:
    """排序键：``unix``，缺则解析 ``ts``；都没有的老格式行排最前（它们确实最老）。
    读者 ``last_relevant_row`` 按文件顺序取「最后一行」，所以并入后文件顺序必须是时间顺序。"""

    unix = row.get("unix")
    if isinstance(unix, (int, float)) and not isinstance(unix, bool):
        return float(unix)
    if isinstance(unix, str):
        try:
            return float(unix)
        except ValueError:
            pass
    ts = row.get("ts")
    if isinstance(ts, str) and ts:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return float("-inf")


def _stat_signature(path: Path) -> tuple[int, int] | None:
    try:
        info = path.stat()
    except FileNotFoundError:
        return None
    return (info.st_size, info.st_mtime_ns)


def _write_rows_atomic(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def merge_ledgers(
    sources: Sequence[str | Path],
    target: str | Path,
    *,
    apply: bool,
    stamp: str | None = None,
) -> dict[str, Any]:
    """把旧家并入唯一家。

    并集去重（整行 JSON 规范化后相等即重复）、按 ``unix``（缺则 ``ts``）稳定排序、原子覆写目标
    （tmp → fsync → ``os.replace``），旧文件改名 ``.migrated-<日期>`` 保留不删。默认只出计划；
    ``apply=True`` 才动文件。目标在读与替换之间被别人 append 了就放弃替换（不吞那一行），报告
    ``aborted=target_changed``，重跑即可——并入是幂等的。
    """

    target_path = Path(target).expanduser()
    before = _stat_signature(target_path)
    target_rows = read_rows(target_path)
    seen = {_row_identity(row) for row in target_rows}
    merged = list(target_rows)
    per_source: list[dict[str, Any]] = []
    for source in sources:
        source_path = Path(source).expanduser()
        if source_path.resolve() == target_path.resolve():
            continue
        rows = read_rows(source_path)
        added = 0
        for row in rows:
            key = _row_identity(row)
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)
            added += 1
        per_source.append(
            {
                "path": str(source_path),
                "exists": source_path.is_file(),
                "rows": len(rows),
                "added": added,
                "duplicates": len(rows) - added,
            }
        )
    merged.sort(key=_row_order)
    report: dict[str, Any] = {
        "target": str(target_path),
        "target_rows_before": len(target_rows),
        "target_rows_after": len(merged),
        "sources": per_source,
        "applied": False,
    }
    if not apply:
        return report
    if _stat_signature(target_path) != before:
        report["aborted"] = "target_changed"
        return report
    _write_rows_atomic(target_path, merged)
    suffix = f".migrated-{stamp or datetime.now(timezone.utc).strftime('%Y%m%d')}"
    renamed: list[dict[str, str]] = []
    for entry in per_source:
        source_path = Path(str(entry["path"]))
        if not source_path.is_file():
            continue
        destination = source_path.with_name(source_path.name + suffix)
        counter = 1
        while destination.exists():
            destination = source_path.with_name(f"{source_path.name}{suffix}.{counter}")
            counter += 1
        os.replace(source_path, destination)
        renamed.append({"from": str(source_path), "to": str(destination)})
    report["applied"] = True
    report["renamed"] = renamed
    return report


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
