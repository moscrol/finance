#!/usr/bin/env python3
"""部署切换账本 CLI：``record`` 写入、``check`` 对账 health rev、``homes`` / ``migrate-homes`` 收家。

失败形状
--------
8792 出现过无记录的切换（a7e2d74f）。生产台账 inflight/main.md 是人写的，会漏。
本脚本让链切五步（``ln -sfh`` 之后）和 rsync 部署脚本都能落 ``action=switch``，
不依赖人记得改文档。``check`` 拿账本最后相关行对 ``/api/health`` 的
``runtime.source_revision``，不一致 exit 1，可挂夜间回检。

2026-09-09（工单 #44）：账本曾有两个家（``$FINANCE_WS/state/`` 与 ``~/.finance-runtime``），
写入侧现在只认 ``~/.finance-runtime/deploy-ledger.jsonl``。``homes`` 列出唯一家与旧家各自的行数
与末次 switch / startup，旧家还有行就 exit 1（可当门）；``migrate-homes`` 把旧家并入唯一家
（并集去重、按时刻排序、原子覆写，旧文件改名 ``.migrated-<日期>``），默认只出计划、``--apply`` 才动。

测试必须 mock HTTP，禁止打 reserved 端口 8792。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from intelligence.runtime.deploy_ledger import (  # noqa: E402
    LEDGER_NAME,
    check_against_health,
    health_revision,
    infer_port,
    legacy_ledger_candidates,
    merge_ledgers,
    read_rows,
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


_REPO_ROOT_IGNORED = (
    "--repo-root 已不参与账本路径解析（账本只有一个家，见 deploy_ledger.default_ledger_path）；已忽略"
)


def _warn_repo_root(args: argparse.Namespace) -> None:
    if getattr(args, "repo_root", None):
        print(_REPO_ROOT_IGNORED, file=sys.stderr)


def _git_common_dir_parent(root: Path) -> Path | None:
    """主检出树（git common-dir 的父目录）：从 worktree 里跑时旧家可能在主树 ``state/``。"""

    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    return Path(completed.stdout.strip()).resolve().parent


def _legacy_paths(home: Path, extra: Sequence[str]) -> list[Path]:
    """旧家候选：``$FINANCE_WS/state/``、本仓 ``state/``、主树 ``state/``、``--extra``；去重、剔掉唯一家本身。"""

    candidates = legacy_ledger_candidates(repo_root=REPO_ROOT)
    common = _git_common_dir_parent(REPO_ROOT)
    if common is not None:
        candidates.append(common / "state" / LEDGER_NAME)
    candidates.extend(Path(item).expanduser() for item in extra)
    unique: list[Path] = []
    seen: set[str] = {str(home.resolve())}
    for path in candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _summarize(path: Path, port: int | None) -> dict[str, Any]:
    rows = read_rows(path)

    def last(action: str) -> dict[str, Any] | None:
        chosen: dict[str, Any] | None = None
        for row in rows:
            if row.get("action") != action:
                continue
            row_port = row.get("port")
            if port is not None and row_port is not None and row_port != port:
                continue
            chosen = row
        if chosen is None:
            return None
        return {"ts": chosen.get("ts"), "rev": str(chosen.get("rev") or "")[:12]}

    return {
        "path": str(path),
        "exists": path.is_file(),
        "rows": len(rows),
        "last_switch": last("switch"),
        "last_startup": last("startup"),
    }


def _cmd_homes(args: argparse.Namespace) -> int:
    home = resolve_ledger_path(None, ledger_path=args.ledger or None)
    legacy = [_summarize(path, args.port) for path in _legacy_paths(home, args.extra)]
    legacy_present = any(entry["exists"] and entry["rows"] > 0 for entry in legacy)
    report = {
        "ok": not legacy_present,
        "home": _summarize(home, args.port),
        "legacy": legacy,
        "legacy_present": legacy_present,
        "hint": "" if not legacy_present else "旧家还有行：audit_deploy_ledger.py migrate-homes --apply 并入",
    }
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


def _cmd_migrate_homes(args: argparse.Namespace) -> int:
    home = resolve_ledger_path(None, ledger_path=args.ledger or None)
    sources = [path for path in _legacy_paths(home, args.extra) if path.is_file()]
    report = merge_ledgers(sources, home, apply=args.apply)
    report["mode"] = "apply" if args.apply else "dry_run"
    print(json.dumps(report, ensure_ascii=False))
    return 1 if report.get("aborted") else 0


def _cmd_record(args: argparse.Namespace) -> int:
    _warn_repo_root(args)
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
    _warn_repo_root(args)
    ledger = resolve_ledger_path(None, ledger_path=args.ledger or None)
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
    # 账本是全端口共用的（sidecar 也自报），对账只看被检 URL 那个端口的行，
    # 否则最后一条 sidecar 启动行会把生产对账顶成假 rev_mismatch。
    port = urlsplit(args.url).port
    report = check_against_health(ledger, health, port=port)
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
    record.add_argument("--repo-root", default=None, help="已废弃：不再参与路径解析（账本只有一个家）")
    record.add_argument(
        "--ledger",
        default="",
        help="覆盖路径；等价于环境变量 FINANCE_DEPLOY_LEDGER",
    )
    record.set_defaults(handler=_cmd_record)

    check = sub.add_parser("check", help="账本尾行 vs health rev，不一致 exit 1")
    check.add_argument("--url", default=DEFAULT_HEALTH_URL)
    check.add_argument("--ledger", default="", help="覆盖账本路径")
    check.add_argument("--repo-root", default=None, help="已废弃：不再参与路径解析（账本只有一个家）")
    check.set_defaults(handler=_cmd_check)

    homes = sub.add_parser(
        "homes",
        help="列出唯一家与旧家（$FINANCE_WS/state、本仓 state、主树 state）各自的行数与末次 switch/startup；旧家还有行就 exit 1",
    )
    homes.add_argument("--ledger", default="", help="覆盖唯一家路径；等价于环境变量 FINANCE_DEPLOY_LEDGER")
    homes.add_argument("--port", type=int, default=8792, help="末次 switch/startup 按哪个端口取（默认 8792）")
    homes.add_argument("--extra", action="append", default=[], help="额外要检查的旧账本路径（可重复）")
    homes.set_defaults(handler=_cmd_homes)

    migrate = sub.add_parser(
        "migrate-homes",
        help="把旧家并入唯一家：并集去重、按时刻排序、原子覆写；旧文件改名 .migrated-<日期>。默认只出计划，--apply 才动文件",
    )
    migrate.add_argument("--ledger", default="", help="覆盖唯一家路径；等价于环境变量 FINANCE_DEPLOY_LEDGER")
    migrate.add_argument("--extra", action="append", default=[], help="额外要并入的旧账本路径（可重复）")
    migrate.add_argument("--apply", action="store_true", help="真动文件；不带只打印计划")
    migrate.set_defaults(handler=_cmd_migrate_homes)
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
