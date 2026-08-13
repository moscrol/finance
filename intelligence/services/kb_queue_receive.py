"""把金融仓当日 kb-ingest-queue 归档进知识库 wiki/raw（只 receive，不入库）。

夜跑和 `intelligence.cli daily` 在写出研究队列后调用这一步，让缺口任务包进入
`wiki/raw/cross-repo-ingest-queue/<date>/` 并生成 receipt.json。

硬约束：
- 只调用知识库仓 `scripts/kb_ingest_queue.py receive`
- 不传 `--apply`、不调用 `mark`、不改 `auto_apply`
- 缺文件或 receive 失败时降级为 skipped/warn，不抛、不阻断复盘
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


RECEIVE_SUBCOMMAND = "receive"
FORBIDDEN_TOKENS = ("--apply", "apply", "mark")


@dataclass(frozen=True)
class ReceiveResult:
    status: str
    reason: str
    argv: list[str] = field(default_factory=list)
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def kb_ingest_queue_path(finance_root: str | Path, date: str) -> Path:
    return Path(finance_root).expanduser() / "market_feature_store" / "exports" / f"{date}-kb-ingest-queue.json"


def kb_receive_script(kb_wiki: str | Path) -> Path:
    return Path(kb_wiki).expanduser().resolve().parent / "scripts" / "kb_ingest_queue.py"


def _assert_receive_only(argv: list[str]) -> None:
    lowered = [token.lower() for token in argv]
    for token in FORBIDDEN_TOKENS:
        if token in lowered:
            raise ValueError(f"kb-queue-receive must not include {token!r}: {argv}")
    if RECEIVE_SUBCOMMAND not in argv:
        raise ValueError(f"kb-queue-receive argv must include {RECEIVE_SUBCOMMAND!r}: {argv}")


def receive_kb_ingest_queue(
    *,
    date: str,
    finance_root: str | Path,
    kb_wiki: str | Path,
    python: str | None = None,
    receive_script: str | Path | None = None,
    timeout_sec: float = 60,
) -> ReceiveResult:
    queue_path = kb_ingest_queue_path(finance_root, date)
    script = Path(receive_script).expanduser() if receive_script else kb_receive_script(kb_wiki)
    wiki = Path(kb_wiki).expanduser()
    if not queue_path.is_file():
        return ReceiveResult(status="skipped", reason=f"queue missing: {queue_path}")
    if not script.is_file():
        return ReceiveResult(status="skipped", reason=f"receive script missing: {script}")

    argv = [
        python or sys.executable,
        str(script),
        RECEIVE_SUBCOMMAND,
        str(queue_path),
        "--wiki-root",
        str(wiki),
    ]
    _assert_receive_only(argv)
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except Exception as exc:
        return ReceiveResult(status="warn", reason=str(exc), argv=argv)

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        return ReceiveResult(
            status="warn",
            reason=stderr or stdout or f"receive exit {proc.returncode}",
            argv=argv,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
        )
    payload: dict[str, Any] | None = None
    try:
        parsed = json.loads(stdout) if stdout else None
        if isinstance(parsed, dict):
            payload = parsed
    except json.JSONDecodeError:
        payload = None
    return ReceiveResult(
        status="received",
        reason="ok" if payload is None else ("idempotent" if payload.get("idempotent") else "archived"),
        argv=argv,
        returncode=proc.returncode,
        stdout=stdout,
        stderr=stderr,
        payload=payload,
    )
