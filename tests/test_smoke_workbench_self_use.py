from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts import smoke_workbench_self_use as smoke


class SmokeHandler(BaseHTTPRequestHandler):
    mode = "completed"
    event_calls = 0
    received_question = ""

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: object, status: int = 200) -> None:
        self._send(
            status,
            json.dumps(payload, ensure_ascii=False).encode(),
            "application/json",
        )

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == "/":
            self._send(200, b"<html>workbench</html>", "text/html")
            return
        if parsed.path == "/api/skills":
            self._json([{"skill_id": "daily-review", "title": "Daily"}])
            return
        if parsed.path == "/api/runs/run-1/events":
            type(self).event_calls += 1
            query = parse_qs(parsed.query)
            after = int(query.get("after", ["0"])[0])
            if type(self).event_calls == 1:
                assert after == 0
                events = [
                    (
                        "text.delta",
                        {
                            "event_type": "text.delta",
                            "seq": 1,
                            "payload": {"delta": "redacted answer"},
                        },
                    ),
                    (
                        "citation.ready",
                        {
                            "event_type": "citation.ready",
                            "seq": 2,
                            "payload": {
                                "citation": {
                                    "title": "private citation",
                                    "url": "https://example.invalid/private",
                                }
                            },
                        },
                    ),
                    ("timeout", {}),
                ]
            else:
                assert after == 2
                delta = (
                    "ghp_abcdefghijklmnopqrstuvwxyz"
                    if type(self).mode == "secret"
                    else "[REDACTED]"
                )
                events = [
                    (
                        "text.delta",
                        {
                            "event_type": "text.delta",
                            "seq": 3,
                            "payload": {"delta": delta},
                        },
                    ),
                    (
                        "message.complete",
                        {
                            "event_type": "message.complete",
                            "seq": 4,
                            "payload": {"message": {"status": "completed"}},
                        },
                    ),
                    (
                        "run",
                        {
                            "run_id": "run-1",
                            "status": (
                                type(self).mode
                                if type(self).mode in {"failed", "cancelled"}
                                else "completed"
                            ),
                            "degrades": (
                                ["llm_unavailable_template_answer"]
                                if type(self).mode == "degraded"
                                else []
                            ),
                        },
                    ),
                ]
            body = "".join(
                f"event: {name}\ndata: {json.dumps(payload)}\n\n"
                for name, payload in events
            ).encode()
            self._send(200, body, "text/event-stream")
            return
        if parsed.path == "/api/runs/run-1/report":
            report = {
                "status": "completed",
                "modules": [{"module_id": "daily_overview"}],
                "warnings": [],
                "llm": {"used": False, "provider": None, "model": None},
            }
            if type(self).mode == "protocol":
                report.pop("llm")
            self._json(report)
            return
        self._json({"detail": "not found"}, status=404)

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(content_length))
        if self.path == "/api/conversations":
            self._json({"conversation_id": "conversation-1"})
            return
        if self.path == "/api/conversations/conversation-1/messages":
            assert payload["skill_mode"] == "hybrid"
            assert payload["selected_skill_ids"] == []
            type(self).received_question = payload["content"]
            self._json(
                {
                    "conversation_id": "conversation-1",
                    "user_message_id": "message-1",
                    "assistant_message_id": "message-2",
                    "run_id": "run-1",
                },
                status=202,
            )
            return
        self._json({"detail": "not found"}, status=404)


@contextmanager
def smoke_server(mode: str):
    handler = type("ConfiguredSmokeHandler", (SmokeHandler,), {})
    handler.mode = mode
    handler.event_calls = 0
    handler.received_question = ""
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", handler
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def run_cli(tmp_path: Path, mode: str) -> tuple[int, dict[str, object], str]:
    output = tmp_path / "smoke.json"
    question = "今天市场怎么样"
    with smoke_server(mode) as (base_url, handler):
        exit_code = smoke.main(
            [
                "--base-url",
                base_url,
                "--user",
                "alice",
                "--question",
                question,
                "--timeout",
                "3",
                "--output",
                str(output),
            ]
        )
        assert handler.received_question == question
    return exit_code, json.loads(output.read_text()), output.read_text()


def test_completed_smoke_replays_sse_and_writes_redacted_summary(
    tmp_path: Path,
) -> None:
    exit_code, summary, raw_summary = run_cli(tmp_path, "completed")

    assert exit_code == 0
    assert summary["terminal_outcome"] == "completed"
    assert summary["sse"] == {
        "request_count": 2,
        "event_count": 6,
        "terminal_event_count": 2,
        "text_delta_count": 2,
        "replayed": True,
    }
    assert summary["report"] == {
        "present": True,
        "status": "completed",
        "module_count": 1,
    }
    assert summary["model"] == {
        "metadata_present": True,
        "used": False,
        "provider": None,
        "model": None,
    }
    assert summary["secret_scan"]["hit_count"] == 0
    assert "今天市场怎么样" not in raw_summary
    assert "private citation" not in raw_summary
    assert "example.invalid" not in raw_summary


def test_degraded_completed_smoke_returns_zero(tmp_path: Path) -> None:
    exit_code, summary, _ = run_cli(tmp_path, "degraded")

    assert exit_code == 0
    assert summary["terminal_outcome"] == "degraded"
    assert summary["degrade_count"] == 1


@pytest.mark.parametrize("status", ["failed", "cancelled"])
def test_failed_or_cancelled_smoke_returns_one(tmp_path: Path, status: str) -> None:
    exit_code, summary, _ = run_cli(tmp_path, status)

    assert exit_code == 1
    assert summary["terminal_outcome"] == status


def test_secret_scan_hit_returns_two_without_echoing_secret(tmp_path: Path) -> None:
    exit_code, summary, raw_summary = run_cli(tmp_path, "secret")

    assert exit_code == 2
    assert summary["terminal_outcome"] == "secret_scan_failed"
    assert summary["secret_scan"]["hit_count"] == 1
    assert summary["secret_scan"]["hits"] == [
        {"source": "sse.text.delta.payload.delta", "marker": "token_prefix"}
    ]
    assert "ghp_abcdefghijklmnopqrstuvwxyz" not in raw_summary


def test_completed_smoke_requires_model_metadata(tmp_path: Path) -> None:
    exit_code, summary, _ = run_cli(tmp_path, "protocol")

    assert exit_code == 2
    assert summary["terminal_outcome"] == "protocol_error"
    assert summary["failure_stage"] == "model_metadata"


def test_secret_scanner_ignores_redaction_placeholder() -> None:
    scanner = smoke.SecretScanner()

    scanner.scan({"value": "api_key=[REDACTED]"}, "fixture")

    assert scanner.hits == []


def test_secret_scanner_does_not_echo_unsafe_dictionary_keys() -> None:
    scanner = smoke.SecretScanner()

    scanner.scan({"/Users/private": "ghp_abcdefghijklmnopqrstuvwxyz"}, "fixture")

    assert scanner.hits == [{"source": "fixture.field", "marker": "token_prefix"}]
