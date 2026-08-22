#!/usr/bin/env python3
"""held-out 题池探针电池（R3 §B2 / V10）。

每题：``POST /api/conversations`` → ``POST .../messages``（``skill_mode=auto``）
→ 轮询 messages 直到 assistant ``status=completed`` → 读 run 的
``continuous-episode.json``，汇总 reexcerpted / 正文头 / 指针丢弃。

硬约束
------
- ``--base-url`` 必填，**无默认值**（禁默认 8792）。
- pytest 环境（``PYTEST_CURRENT_TEST``）拒绝真联网；单测必须 mock HTTP。
- 本脚本只读遥测，不改生产行为，不打生产端口（执行方不得 live）。

runs 路径
---------
默认 ``{users_dir}/{user}/runs/{run_id}/continuous-episode.json``，
``users_dir`` 默认 ``~/.local/share/finance-workbench/users``。
``--runs-dir`` 可改成 ``{runs_dir}/{run_id}/continuous-episode.json``。

正文头判定复用 ``scripts/audit_kb_section_coverage.is_body_header``
（结构节启发式）。缺遥测字段记 None，不报 0。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Callable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audit_kb_section_coverage import is_body_header  # noqa: E402

DEFAULT_USERS_DIR = Path.home() / ".local/share/finance-workbench/users"
DEFAULT_POOL = (
    Path(__file__).resolve().parents[1]
    / "intelligence"
    / "eval"
    / "probe_pool"
    / "heldout-v1.json"
)
_FORBIDDEN_QUESTION_MARKERS = ("长电科技怎么看", "液冷服务器产业链怎么看", "钙钛矿")
_KINDS = frozenset({"concept", "stock", "chain"})
_TERMINAL = frozenset({"completed", "failed", "cancelled"})


def refuse_live_http_under_pytest() -> None:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        raise RuntimeError("pytest 环境拒绝真联网")


def http_json(
    method: str,
    url: str,
    payload: dict[str, object] | None = None,
    *,
    timeout: float = 30,
) -> object:
    refuse_live_http_under_pytest()
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method=method,
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        return json.loads(response.read())


def default_users_dir() -> Path:
    raw = os.environ.get("FORESIGHT_USERS_DIR")
    if raw and raw.strip():
        return Path(raw.strip()).expanduser()
    return DEFAULT_USERS_DIR


def episode_path(
    *,
    user: str,
    run_id: str,
    users_dir: Path | None = None,
    runs_dir: Path | None = None,
) -> Path:
    if runs_dir is not None:
        return Path(runs_dir).expanduser() / run_id / "continuous-episode.json"
    root = Path(users_dir).expanduser() if users_dir is not None else default_users_dir()
    return root / user / "runs" / run_id / "continuous-episode.json"


def load_pool(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("题池必须是 JSON object")
    questions = payload.get("questions")
    if not isinstance(questions, list):
        raise ValueError("题池须是 questions 数组")
    themes: set[str] = set()
    kinds: set[str] = set()
    for item in questions:
        if not isinstance(item, dict):
            raise ValueError("题池项必须是 object")
        question = str(item.get("question") or "")
        if any(marker in question for marker in _FORBIDDEN_QUESTION_MARKERS):
            raise ValueError(f"held-out 禁题：{question}")
        theme = str(item.get("theme") or "").strip()
        kind = str(item.get("kind") or "").strip()
        if not theme or kind not in _KINDS:
            raise ValueError("每题须有 theme 与 kind∈{concept,stock,chain}")
        themes.add(theme)
        kinds.add(kind)
    if len(questions) < 8:
        raise ValueError("题池须 ≥8 题")
    if len(themes) < 6:
        raise ValueError("题池须 ≥6 个不同题材")
    if kinds != _KINDS:
        raise ValueError("题池须覆盖 concept/stock/chain 三类问法")
    return payload


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _message_items(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [item for item in _as_list(payload.get("messages")) if isinstance(item, dict)]
    return []


def assistant_completed(payload: object) -> dict[str, Any] | None:
    for message in _message_items(payload):
        if message.get("role") != "assistant":
            continue
        status = str(message.get("status") or "")
        if status == "completed":
            return message
    return None


def collect_kb_telemetry(episode: dict[str, Any]) -> dict[str, Any]:
    delivered: list[int | None] = []
    detail_chars: list[int | None] = []
    hit_counts: list[int | None] = []
    pointer_dropped: list[int | None] = []
    reexcerpted_flags: list[bool] = []
    calls = 0
    for event in _as_list(episode.get("events")):
        if not isinstance(event, dict) or event.get("kind") != "tool_result":
            continue
        payload = _as_dict(event.get("payload"))
        if str(payload.get("tool") or "") != "kb_search":
            continue
        calls += 1
        tel = payload.get("telemetry")
        if not isinstance(tel, dict):
            delivered.append(None)
            detail_chars.append(None)
            hit_counts.append(None)
            pointer_dropped.append(None)
            continue
        delivered.append(
            int(tel["delivered_chars"])
            if isinstance(tel.get("delivered_chars"), (int, float))
            else None
        )
        detail_chars.append(
            int(tel["detail_chars"])
            if isinstance(tel.get("detail_chars"), (int, float))
            else None
        )
        hit_counts.append(
            int(tel["hit_count"]) if isinstance(tel.get("hit_count"), (int, float)) else None
        )
        pointer_dropped.append(
            int(tel["pointer_dropped"])
            if isinstance(tel.get("pointer_dropped"), (int, float))
            else None
        )
        raw = tel.get("reexcerpted")
        if isinstance(raw, bool):
            reexcerpted_flags.append(raw)
        elif isinstance(raw, (list, tuple)):
            reexcerpted_flags.extend(bool(item) for item in raw)
    return {
        "calls": calls,
        "delivered_chars": delivered,
        "detail_chars": detail_chars,
        "hit_count": hit_counts,
        "pointer_dropped": pointer_dropped,
        "reexcerpted_flags": reexcerpted_flags,
    }


def collect_evidence(episode: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    evidence = _as_dict(episode.get("outcome")).get("evidence") or episode.get("evidence")
    for item in _as_list(evidence):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "")
        detail = str(item.get("detail") or "")
        raw = item.get("reexcerpted")
        rows.append(
            {
                "title": title,
                "detail": detail,
                "reexcerpted": raw if isinstance(raw, bool) else None,
                "body_header": is_body_header(title, detail),
            }
        )
    return rows


def rate(flags: list[bool]) -> float | None:
    if not flags:
        return None
    return sum(1 for item in flags if item) / len(flags)


def inspect_episode(episode: dict[str, Any]) -> dict[str, Any]:
    telemetry = collect_kb_telemetry(episode)
    evidence = collect_evidence(episode)
    reexcerpted_flags = list(telemetry["reexcerpted_flags"])
    reexcerpted_flags.extend(
        item["reexcerpted"] for item in evidence if isinstance(item["reexcerpted"], bool)
    )
    body_flags = [bool(item["body_header"]) for item in evidence if item["title"] or item["detail"]]
    dropped = [item for item in telemetry["pointer_dropped"] if item is not None]
    return {
        "telemetry": telemetry,
        "evidence": evidence,
        "reexcerpted_rate": rate(reexcerpted_flags),
        "body_header_rate": rate(body_flags),
        "pointer_dropped_values": dropped,
    }


def run_one(
    *,
    base_url: str,
    user: str,
    question: dict[str, Any],
    users_dir: Path,
    runs_dir: Path | None,
    timeout: float,
    poll_seconds: float,
    http: Callable[..., object] = http_json,
    sleeper: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
    load_episode: Callable[[Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    base = base_url.rstrip("/")
    title = str(question.get("title") or question.get("question") or "probe")[:24]
    created = http(
        "POST",
        f"{base}/api/conversations",
        {"title": title, "user": user},
    )
    conversation = _as_dict(created)
    conversation_id = str(conversation.get("conversation_id") or "")
    if not conversation_id:
        raise RuntimeError(f"create conversation failed: {created!r}")
    posted = http(
        "POST",
        f"{base}/api/conversations/{conversation_id}/messages",
        {
            "content": str(question.get("question") or ""),
            "user": user,
            "skill_mode": "auto",
        },
    )
    posted_dict = _as_dict(posted)
    run_id = str(posted_dict.get("run_id") or "")
    if not run_id:
        raise RuntimeError(f"post message failed: {posted!r}")
    deadline = now() + timeout
    last_status = ""
    while now() < deadline:
        messages = http(
            "GET",
            f"{base}/api/conversations/{conversation_id}/messages?user={user}",
        )
        done = assistant_completed(messages)
        if done is not None:
            last_status = "completed"
            break
        for message in _message_items(messages):
            if message.get("role") == "assistant":
                last_status = str(message.get("status") or last_status)
        sleeper(poll_seconds)
    else:
        last_status = last_status or "timeout"
    path = episode_path(
        user=user, run_id=run_id, users_dir=users_dir, runs_dir=runs_dir
    )
    episode: dict[str, Any] = {}
    if load_episode is not None:
        episode = load_episode(path)
    elif path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))
        episode = raw if isinstance(raw, dict) else {}
    metrics = inspect_episode(episode) if episode else {
        "telemetry": {
            "calls": 0,
            "delivered_chars": [],
            "detail_chars": [],
            "hit_count": [],
            "pointer_dropped": [],
            "reexcerpted_flags": [],
        },
        "evidence": [],
        "reexcerpted_rate": None,
        "body_header_rate": None,
        "pointer_dropped_values": [],
    }
    return {
        "id": question.get("id"),
        "theme": question.get("theme"),
        "kind": question.get("kind"),
        "question": question.get("question"),
        "conversation_id": conversation_id,
        "run_id": run_id,
        "status": last_status,
        "episode_path": str(path),
        **metrics,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reexcerpted = [row["reexcerpted_rate"] for row in rows if row.get("reexcerpted_rate") is not None]
    body = [row["body_header_rate"] for row in rows if row.get("body_header_rate") is not None]
    dropped: list[int] = []
    for row in rows:
        dropped.extend(row.get("pointer_dropped_values") or [])
    dist = Counter(str(item) for item in dropped)
    return {
        "n": len(rows),
        "completed": sum(1 for row in rows if row.get("status") == "completed"),
        "reexcerpted_rate": (
            sum(reexcerpted) / len(reexcerpted) if reexcerpted else None
        ),
        "body_header_rate": sum(body) / len(body) if body else None,
        "pointer_dropped_distribution": dict(sorted(dist.items())),
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = _as_dict(report.get("summary"))
    lines = [
        f"# probe battery {report.get('pool_id')}",
        "",
        f"base_url: {report.get('base_url')}",
        f"user: {report.get('user')}",
        (
            f"n={summary.get('n')} completed={summary.get('completed')} "
            f"reexcerpted_rate={summary.get('reexcerpted_rate')} "
            f"body_header_rate={summary.get('body_header_rate')}"
        ),
        f"pointer_dropped: {summary.get('pointer_dropped_distribution')}",
        "",
        "| id | theme | kind | status | reexcerpted | body_header | dropped |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for row in _as_list(report.get("questions")):
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {row.get('id')} | {row.get('theme')} | {row.get('kind')} | "
            f"{row.get('status')} | {row.get('reexcerpted_rate')} | "
            f"{row.get('body_header_rate')} | {row.get('pointer_dropped_values')} |"
        )
    return "\n".join(lines) + "\n"


def run_battery(
    *,
    base_url: str,
    user: str,
    pool: dict[str, Any],
    users_dir: Path,
    runs_dir: Path | None = None,
    timeout: float = 900,
    poll_seconds: float = 5,
    http: Callable[..., object] = http_json,
    sleeper: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
    load_episode: Callable[[Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = [
        run_one(
            base_url=base_url,
            user=user,
            question=question,
            users_dir=users_dir,
            runs_dir=runs_dir,
            timeout=timeout,
            poll_seconds=poll_seconds,
            http=http,
            sleeper=sleeper,
            now=now,
            load_episode=load_episode,
        )
        for question in _as_list(pool.get("questions"))
        if isinstance(question, dict)
    ]
    return {
        "pool_id": pool.get("id"),
        "base_url": base_url,
        "user": user,
        "users_dir": str(users_dir),
        "runs_dir": str(runs_dir) if runs_dir else None,
        "questions": rows,
        "summary": summarize(rows),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base-url",
        required=True,
        help="Workbench base URL，必填，无默认值（禁默认 8792）",
    )
    parser.add_argument("--user", required=True, help="探针用户，字段名是 user")
    parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    parser.add_argument("--users-dir", type=Path, default=None)
    parser.add_argument("--runs-dir", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--poll-seconds", type=float, default=5)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--md-out", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pool = load_pool(args.pool)
    users_dir = args.users_dir or default_users_dir()
    report = run_battery(
        base_url=args.base_url,
        user=args.user,
        pool=pool,
        users_dir=users_dir,
        runs_dir=args.runs_dir,
        timeout=args.timeout,
        poll_seconds=args.poll_seconds,
    )
    text = render_markdown(report)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_out:
        args.json_out.write_text(encoded, encoding="utf-8")
    if args.md_out:
        args.md_out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0 if report["summary"]["completed"] == report["summary"]["n"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
