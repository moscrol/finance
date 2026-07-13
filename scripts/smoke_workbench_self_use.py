#!/usr/bin/env python3
"""Run a redacted, end-to-end Workbench conversation smoke check."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import BinaryIO

TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}
SAFE_LABEL = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SAFE_SOURCE_COMPONENT = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
SECRET_PATTERNS = (
    (
        "token_prefix",
        re.compile(r"\b(?:sk|ghp|gho|ghu|ghs|xoxb|xoxp)[-_][A-Za-z0-9_-]{8,}"),
    ),
    (
        "secret_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|token|secret|password|authorization)"
            r"\s*[=:]\s*(?!\[REDACTED\](?:\s|$))\S+"
        ),
    ),
)
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
LOOPBACK_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class SmokeProtocolError(RuntimeError):
    def __init__(self, stage: str) -> None:
        super().__init__(stage)
        self.stage = stage


def smoke_metrics(
    *,
    started_at: float,
    finished_at: float,
    stage_events: list[str],
) -> dict[str, object]:
    elapsed = finished_at - started_at
    if not math.isfinite(elapsed):
        elapsed = 0.0
    stages: list[str] = []
    for stage in stage_events:
        if (
            isinstance(stage, str)
            and SAFE_SOURCE_COMPONENT.fullmatch(stage)
            and stage not in stages
        ):
            stages.append(stage)
    return {
        "elapsed_seconds": round(max(0.0, elapsed), 3),
        "stages": stages,
    }


class SecretScanner:
    def __init__(self) -> None:
        self.scanned_string_count = 0
        self.hits: list[dict[str, str]] = []

    def scan(self, value: object, source: str) -> None:
        if isinstance(value, str):
            self.scanned_string_count += 1
            for marker, pattern in SECRET_PATTERNS:
                if pattern.search(value):
                    self.hits.append({"source": source, "marker": marker})
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                self.scan(item, f"{source}[{index}]")
            return
        if isinstance(value, dict):
            for key, item in value.items():
                component = (
                    key
                    if isinstance(key, str) and SAFE_SOURCE_COMPONENT.fullmatch(key)
                    else "field"
                )
                self.scan(item, f"{source}.{component}")


def _validated_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("base URL must be an HTTP(S) origin")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip(
        "/"
    )


def _url(base_url: str, path: str, query: dict[str, object] | None = None) -> str:
    encoded = urllib.parse.urlencode(query or {})
    return f"{base_url}{path}" + (f"?{encoded}" if encoded else "")


def _open(
    request: urllib.request.Request,
    *,
    timeout: float,
    stage: str,
) -> BinaryIO:
    try:
        hostname = urllib.parse.urlsplit(request.full_url).hostname
        if hostname in LOOPBACK_HOSTS:
            return LOOPBACK_OPENER.open(request, timeout=timeout)
        return urllib.request.urlopen(request, timeout=timeout)
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
    ) as exc:
        raise SmokeProtocolError(stage) from exc


def _request_bytes(
    method: str,
    url: str,
    *,
    timeout: float,
    stage: str,
    payload: dict[str, object] | None = None,
) -> bytes:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with _open(request, timeout=timeout, stage=stage) as response:
        return response.read()


def _request_json(
    method: str,
    url: str,
    *,
    timeout: float,
    stage: str,
    payload: dict[str, object] | None = None,
) -> object:
    body = _request_bytes(
        method,
        url,
        timeout=timeout,
        stage=stage,
        payload=payload,
    )
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SmokeProtocolError(stage) from exc


def _iter_sse(response: BinaryIO):
    event_type = "message"
    event_id: str | None = None
    data_lines: list[str] = []
    for raw_line in response:
        try:
            line = raw_line.decode("utf-8").rstrip("\r\n")
        except UnicodeDecodeError as exc:
            raise SmokeProtocolError("sse_decode") from exc
        if not line:
            if data_lines:
                yield event_type, event_id, "\n".join(data_lines)
            event_type = "message"
            event_id = None
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        field, separator, value = line.partition(":")
        if not separator:
            continue
        value = value[1:] if value.startswith(" ") else value
        if field == "event":
            event_type = value
        elif field == "id":
            event_id = value
        elif field == "data":
            data_lines.append(value)
    if data_lines:
        yield event_type, event_id, "\n".join(data_lines)


def _json_object(data: str, stage: str) -> dict[str, object]:
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as exc:
        raise SmokeProtocolError(stage) from exc
    if not isinstance(payload, dict):
        raise SmokeProtocolError(stage)
    return payload


def _stream_until_terminal(
    *,
    base_url: str,
    user: str,
    run_id: str,
    timeout: float,
    scanner: SecretScanner,
) -> tuple[dict[str, object], dict[str, object]]:
    deadline = time.monotonic() + timeout
    cursor = 0
    request_count = 0
    event_count = 0
    terminal_event_count = 0
    text_delta_count = 0
    stage_events: list[str] = []
    no_progress_count = 0

    while time.monotonic() < deadline:
        request_count += 1
        previous_cursor = cursor
        remaining = max(0.1, deadline - time.monotonic())
        request = urllib.request.Request(
            _url(
                base_url,
                f"/api/runs/{urllib.parse.quote(run_id, safe='')}/events",
                {"user": user, "after": cursor},
            ),
            headers={"Accept": "text/event-stream"},
            method="GET",
        )
        with _open(
            request,
            timeout=remaining,
            stage="sse_connect",
        ) as response:
            for event_name, _, raw_data in _iter_sse(response):
                if not SAFE_SOURCE_COMPONENT.fullmatch(event_name):
                    raise SmokeProtocolError("sse_event_type")
                event_count += 1
                payload = _json_object(raw_data, "sse_payload")
                scanner.scan(payload, f"sse.{event_name}")

                if event_name == "timeout":
                    continue
                if event_name == "run":
                    status = payload.get("status")
                    if status not in TERMINAL_RUN_STATUSES:
                        raise SmokeProtocolError("sse_terminal_status")
                    terminal_event_count += 1
                    return payload, {
                        "request_count": request_count,
                        "event_count": event_count,
                        "terminal_event_count": terminal_event_count,
                        "text_delta_count": text_delta_count,
                        "replayed": request_count > 1,
                        "stages": list(dict.fromkeys(stage_events)),
                    }

                seq = payload.get("seq")
                if seq is not None:
                    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 1:
                        raise SmokeProtocolError("sse_sequence")
                    cursor = max(cursor, seq)

                canonical_type = payload.get("event_type")
                if canonical_type in {"message.complete", "message.error"}:
                    terminal_event_count += 1
                if canonical_type == "stage.progress":
                    event_payload = payload.get("payload")
                    stage = (
                        event_payload.get("stage")
                        if isinstance(event_payload, dict)
                        else None
                    )
                    if not isinstance(stage, str) or not SAFE_SOURCE_COMPONENT.fullmatch(
                        stage
                    ):
                        raise SmokeProtocolError("stage_progress")
                    stage_events.append(stage)
                if canonical_type == "text.delta":
                    event_payload = payload.get("payload")
                    delta = (
                        event_payload.get("delta")
                        if isinstance(event_payload, dict)
                        else None
                    )
                    if not isinstance(delta, str):
                        raise SmokeProtocolError("text_delta")
                    if delta.strip():
                        text_delta_count += 1

        if cursor == previous_cursor:
            no_progress_count += 1
            if no_progress_count >= 3:
                raise SmokeProtocolError("sse_no_progress")
        else:
            no_progress_count = 0

    raise SmokeProtocolError("sse_timeout")


def _safe_optional_label(value: object, stage: str) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not SAFE_LABEL.fullmatch(value)
        or any(pattern.search(value) for _, pattern in SECRET_PATTERNS)
    ):
        raise SmokeProtocolError(stage)
    return value


def _safe_identifier(value: object, stage: str) -> str:
    if (
        not isinstance(value, str)
        or not SAFE_IDENTIFIER.fullmatch(value)
        or any(pattern.search(value) for _, pattern in SECRET_PATTERNS)
    ):
        raise SmokeProtocolError(stage)
    return value


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def run_smoke(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    started_at = time.monotonic()
    deadline = started_at + args.timeout
    scanner = SecretScanner()
    stage_events: list[str] = []
    readiness = {"page": False, "skills": False}
    summary: dict[str, object] = {
        "schema_version": 1,
        "readiness": readiness,
        "terminal_outcome": "protocol_error",
    }

    def remaining(stage: str) -> float:
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise SmokeProtocolError(stage)
        return seconds

    try:
        page = _request_bytes(
            "GET",
            _url(args.base_url, "/"),
            timeout=remaining("readiness_page"),
            stage="readiness_page",
        )
        if not page.strip():
            raise SmokeProtocolError("readiness_page")
        readiness["page"] = True

        skills = _request_json(
            "GET",
            _url(args.base_url, "/api/skills"),
            timeout=remaining("readiness_skills"),
            stage="readiness_skills",
        )
        if not isinstance(skills, list):
            raise SmokeProtocolError("readiness_skills")
        readiness["skills"] = True

        conversation = _request_json(
            "POST",
            _url(args.base_url, "/api/conversations"),
            timeout=remaining("create_conversation"),
            stage="create_conversation",
            payload={"title": "Self-use smoke", "user": args.user},
        )
        if not isinstance(conversation, dict):
            raise SmokeProtocolError("create_conversation")
        conversation_id = _safe_identifier(
            conversation.get("conversation_id"),
            "create_conversation",
        )

        turn = _request_json(
            "POST",
            _url(
                args.base_url,
                f"/api/conversations/{urllib.parse.quote(conversation_id, safe='')}/messages",
            ),
            timeout=remaining("create_message"),
            stage="create_message",
            payload={
                "content": args.question,
                "skill_mode": "hybrid",
                "selected_skill_ids": [],
                "user": args.user,
            },
        )
        if not isinstance(turn, dict):
            raise SmokeProtocolError("create_message")
        run_id = _safe_identifier(turn.get("run_id"), "create_message")

        terminal_run, sse_summary = _stream_until_terminal(
            base_url=args.base_url,
            user=args.user,
            run_id=run_id,
            timeout=remaining("sse_timeout"),
            scanner=scanner,
        )
        raw_stage_events = sse_summary.get("stages")
        if not isinstance(raw_stage_events, list) or not all(
            isinstance(stage, str) and SAFE_SOURCE_COMPONENT.fullmatch(stage)
            for stage in raw_stage_events
        ):
            raise SmokeProtocolError("stage_progress")
        stage_events = raw_stage_events
        public_sse_summary = {
            key: value for key, value in sse_summary.items() if key != "stages"
        }
        run_status = terminal_run["status"]
        degrades = terminal_run.get("degrades", [])
        if not isinstance(degrades, list) or not all(
            isinstance(item, str) for item in degrades
        ):
            raise SmokeProtocolError("run_degrades")

        report = _request_json(
            "GET",
            _url(
                args.base_url,
                f"/api/runs/{urllib.parse.quote(run_id, safe='')}/report",
                {"user": args.user},
            ),
            timeout=remaining("run_report"),
            stage="run_report",
        )
        scanner.scan(terminal_run, "terminal_run")
        scanner.scan(report, "report")

        report_present = isinstance(report, dict)
        if run_status == "completed" and not report_present:
            raise SmokeProtocolError("run_report")
        report_payload = report if isinstance(report, dict) else {}
        modules = report_payload.get("modules", [])
        if not isinstance(modules, list):
            raise SmokeProtocolError("run_report_modules")
        llm = report_payload.get("llm")
        if run_status == "completed" and not isinstance(llm, dict):
            raise SmokeProtocolError("model_metadata")
        llm_payload = llm if isinstance(llm, dict) else {}
        llm_used = llm_payload.get("used")
        if llm_payload and not isinstance(llm_used, bool):
            raise SmokeProtocolError("model_metadata")

        outcome = (
            "degraded" if run_status == "completed" and degrades else str(run_status)
        )
        summary.update(
            {
                "run_id": run_id,
                "run_status": run_status,
                "terminal_outcome": outcome,
                "degrade_count": len(degrades),
                "sse": public_sse_summary,
                "report": {
                    "present": report_present,
                    "status": _safe_optional_label(
                        report_payload.get("status"),
                        "report_status",
                    ),
                    "module_count": len(modules),
                },
                "model": {
                    "metadata_present": isinstance(llm, dict),
                    "used": llm_used if isinstance(llm_used, bool) else None,
                    "provider": _safe_optional_label(
                        llm_payload.get("provider"),
                        "model_metadata",
                    ),
                    "model": _safe_optional_label(
                        llm_payload.get("model"),
                        "model_metadata",
                    ),
                },
            }
        )
        exit_code = 0 if run_status == "completed" else 1
    except SmokeProtocolError as exc:
        summary["failure_stage"] = exc.stage
        exit_code = 2

    summary["secret_scan"] = {
        "scanned_string_count": scanner.scanned_string_count,
        "hit_count": len(scanner.hits),
        "hits": scanner.hits,
    }
    summary.update(
        smoke_metrics(
            started_at=started_at,
            finished_at=time.monotonic(),
            stage_events=stage_events,
        )
    )
    if scanner.hits:
        summary["terminal_outcome"] = "secret_scan_failed"
        exit_code = 2
    return exit_code, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a redacted Workbench self-use smoke check"
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.base_url = _validated_base_url(args.base_url)
        args.user = args.user.strip()
        args.question = args.question.strip()
        if not args.user or not args.question or args.timeout <= 0:
            raise ValueError
        output = Path(args.output).expanduser()
    except ValueError:
        print("invalid smoke arguments", file=sys.stderr)
        return 2

    exit_code, summary = run_smoke(args)
    try:
        _atomic_write_json(output, summary)
    except OSError:
        print("failed to write smoke summary", file=sys.stderr)
        return 2
    print(f"smoke outcome: {summary['terminal_outcome']}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
