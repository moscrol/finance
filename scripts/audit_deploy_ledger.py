#!/usr/bin/env python3
"""部署切换账本 CLI：``record`` 写入、``check`` 对账 health rev。

失败形状
--------
8792 出现过无记录的切换（a7e2d74f）。生产台账 inflight/main.md 是人写的，会漏。
本脚本让链切五步（``ln -sfh`` 之后）和 rsync 部署脚本都能落 ``action=switch``，
不依赖人记得改文档。``check`` 拿账本最后相关行对 ``/api/health`` 的
``runtime.source_revision``，不一致 exit 1，可挂夜间回检。

测试必须 mock HTTP，禁止打 reserved 端口 8792。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from intelligence.runtime.deploy_ledger import (  # noqa: E402
    check_against_health,
    health_revision,
    infer_port,
    record_event,
    resolve_ledger_path,
)

DEFAULT_HEALTH_URL = "http://127.0.0.1:8792/api/health"
_USER_AGENT = "finance-workbench-deploy-ledger/1.0"


def fetch_health(url: str, timeout: float = 5.0) -> dict[str, Any]:
    """GET health JSON。测试里必须 mock 本函数或 ``urllib.request.urlopen``。"""

    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("health payload is not an object")
    return payload


def _parse_health_json(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("--health-json must be a JSON object")
    return payload


def _cmd_record(args: argparse.Namespace) -> int:
    health = _parse_health_json(args.health_json)
    rev = args.rev or (health_revision(health) if health else "")
    snapshot = args.snapshot_path
    if not snapshot and health:
        runtime = health.get("runtime")
        if isinstance(runtime, dict):
            snapshot = str(runtime.get("loaded_code_root") or "")
    if not rev:
        print("record: missing --rev (and --health-json has no source_revision)", file=sys.stderr)
        return 2
    record_event(
        action=args.action,
        rev=rev,
        snapshot_path=snapshot or None,
        port=args.port if args.port is not None else infer_port(),
        repo_root=args.repo_root,
        ledger_path=args.ledger or None,
        fail_open=False,
    )
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    ledger = resolve_ledger_path(args.repo_root, ledger_path=args.ledger or None)
    try:
        health = fetch_health(args.url)
    except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "health_unreachable",
                    "url": args.url,
                    "error": str(exc),
                },
                ensure_ascii=False,
            )
        )
        return 1
    report = check_against_health(ledger, health)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit_deploy_ledger.py",
        description=(
            "部署切换审计账本：record 追加一行 JSONL，"
            "check 把最后 startup/switch 行对上 /api/health 的 source_revision。"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="追加一行 action=startup|switch")
    record.add_argument("--action", required=True, choices=("startup", "switch"))
    record.add_argument("--rev", default="", help="git sha；可被 --health-json 补齐")
    record.add_argument("--snapshot-path", default="", help="快照目录或 loaded_code_root")
    record.add_argument(
        "--health-json",
        default="",
        help="完整 /api/health JSON，用来填 rev / loaded_code_root",
    )
    record.add_argument("--port", type=int, default=None)
    record.add_argument("--repo-root", default=None)
    record.add_argument(
        "--ledger",
        default="",
        help="覆盖路径；等价于环境变量 FINANCE_DEPLOY_LEDGER",
    )
    record.set_defaults(handler=_cmd_record)

    check = sub.add_parser("check", help="账本尾行 vs health rev，不一致 exit 1")
    check.add_argument("--url", default=DEFAULT_HEALTH_URL)
    check.add_argument("--ledger", default="", help="覆盖账本路径")
    check.add_argument("--repo-root", default=None)
    check.set_defaults(handler=_cmd_check)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2
    try:
        return int(handler(args))
    except Exception as exc:  # noqa: BLE001 - CLI 要把 IO 错误变成 exit 1
        print(f"{args.command} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
