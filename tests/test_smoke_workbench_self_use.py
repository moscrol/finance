from __future__ import annotations

from argparse import Namespace
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts import smoke_workbench_self_use as smoke


_SUPPORTED_MODEL_LABELS = (
    "glm-5.2",
    "gpt-4.1",
    "chatgpt-4o-latest",
    "o1",
    "o1-mini",
    "o3",
    "o3-mini",
    "o4-mini",
    "deepseek-chat",
    "kimi-k2",
    "moonshot-v1-8k",
    "qwen-plus",
    "qwq-32b",
    "tongyi-qianwen",
    "claude-3-7-sonnet",
    "fixture",
    "fixture-model",
    "fixtureModel",
)
_UNKNOWN_MODEL_LABELS = (".model-safe", "-model-safe", "custom-model")
_CREDENTIAL_LABELS = (
    "sk-private-value",
    "sk-proj-abcdefghijklmnopqrstuvwxyz",
    "rk_live_abcdefghijklmnopqrstuvwxyz",
    "ghp_abcdefghijklmnopqrstuvwxyz",
    "gho_abcdefghijklmnopqrstuvwxyz",
    "ghu_abcdefghijklmnopqrstuvwxyz",
    "ghs_abcdefghijklmnopqrstuvwxyz",
    "ghr_abcdefghijklmnopqrstuvwxyz",
    "xoxb-1234567890-abcdefghijklmnop",
    "xoxa-1234567890-abcdefghijklmnop",
    "github_pat_abcdefghijklmnopqrstuvwxyz",
    "hf_abcdefghijklmnopqrstuvwxyz",
    "glpat-abcdefghijklmnopqrstuvwxyz",
    "xapp-1234567890-abcdefghijklmnop",
    "AKIAIOSFODNN7EXAMPLE",
    "ASIAIOSFODNN7EXAMPLE",
    "AIzaSyD-abcdefghijklmnopqrstuvwxyz1234567",
    "ya29.a0AfH6SMabcdefghijklmnopqrstuvwxyz",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhbGljZSJ9.dGVzdHNpZ25hdHVyZQ",
    "Bearer-credential-value",
    "aB3dE5fG7hJ9kL2mN4pQ6rS8tV0wX1yZ3cD5eF7gH9jK2mN4",
)


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
        if parsed.path == "/api/health/ready":
            cutoff = "2026-07-13"
            self._json(
                {
                    "status": "ready",
                    "capabilities": {
                        "market_data": {
                            "available": True,
                            "source": (
                                "snapshot"
                                if type(self).mode == "snapshot_source"
                                else "duckdb"
                            ),
                            "cutoff": cutoff,
                        }
                    },
                }
            )
            return
        if parsed.path == "/api/runs/run-1/events":
            type(self).event_calls += 1
            query = parse_qs(parsed.query)
            after = int(query.get("after", ["0"])[0])
            if type(self).event_calls == 1:
                assert after == 0
                draft_revision = 0 if type(self).mode == "invalid_revision" else 1
                draft_phase = (
                    "unknown_phase"
                    if type(self).mode == "unknown_phase"
                    else "verified_draft"
                )
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
                        "answer.snapshot",
                        {
                            "event_type": "answer.snapshot",
                            "seq": 2,
                            "payload": {
                                "revision": draft_revision,
                                "phase": draft_phase,
                                "text": "可核验草稿",
                                "final": False,
                            },
                        },
                    ),
                    (
                        "citation.ready",
                        {
                            "event_type": "citation.ready",
                            "seq": 3,
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
                if type(self).mode == "missing_draft":
                    events = [
                        event for event in events if event[0] != "answer.snapshot"
                    ]
                elif type(self).mode == "same_revision_replay":
                    events.insert(2, events[1])
                elif type(self).mode == "invalid_snapshot_payload":
                    events[1][1]["payload"]["internal"] = "must reject"
                elif type(self).mode == "unknown_event":
                    events[2] = ("private.debug", events[2][1])
            else:
                assert after == 3
                delta = (
                    "ghp_abcdefghijklmnopqrstuvwxyz"
                    if type(self).mode == "secret"
                    else "[REDACTED]"
                )
                terminal_text = (
                    "ghp_abcdefghijklmnopqrstuvwxyz"
                    if type(self).mode == "snapshot_secret"
                    else "已保留可核验版本"
                )
                events = [
                    (
                        "text.delta",
                        {
                            "event_type": "text.delta",
                            "seq": 4,
                            "payload": {"delta": delta},
                        },
                    ),
                    (
                        "answer.snapshot",
                        {
                            "event_type": "answer.snapshot",
                            "seq": 5,
                            "payload": {
                                "revision": 2,
                                "phase": "verified_fallback",
                                "text": terminal_text,
                                "final": True,
                            },
                        },
                    ),
                    (
                        "message.complete",
                        {
                            "event_type": "message.complete",
                            "seq": 6,
                            "payload": {"message": {"status": "completed"}},
                        },
                    ),
                    (
                        "run",
                        {
                            "run_id": "run-1",
                            "duckdb_cutoff": (
                                None
                                if type(self).mode == "missing_cutoff"
                                else (
                                    "C:/private/market.duckdb"
                                    if type(self).mode == "unsafe_cutoff"
                                    else (
                                        "latest"
                                        if type(self).mode == "bad_cutoff"
                                        else (
                                            "2026-07-10"
                                            if type(self).mode
                                            in {"older_cutoff", "snapshot_source"}
                                            else (
                                                "2026-07-14"
                                                if type(self).mode == "later_cutoff"
                                                else "2026-07-13"
                                            )
                                        )
                                    )
                                )
                            ),
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
                if type(self).mode == "missing_terminal":
                    events = [
                        event for event in events if event[0] != "answer.snapshot"
                    ]
                elif type(self).mode == "old_revision":
                    events.insert(
                        2,
                        (
                            "answer.snapshot",
                            {
                                "event_type": "answer.snapshot",
                                "seq": 6,
                                "payload": {
                                    "revision": 1,
                                    "phase": "verified_draft",
                                    "text": "旧草稿",
                                    "final": False,
                                },
                            },
                        ),
                    )
            body = "".join(
                f"event: {name}\ndata: {json.dumps(payload)}\n\n"
                for name, payload in events
            ).encode()
            self._send(200, body, "text/event-stream")
            return
        if parsed.path == "/api/runs/run-1/report":
            llm = {
                "configured": False,
                "attempted": False,
                "used": False,
                "provider": None,
                "model": None,
                "fallback_reason": "provider_unavailable",
            }
            if type(self).mode == "used":
                llm = {
                    "configured": True,
                    "attempted": True,
                    "used": True,
                    "provider": "zhipu",
                    "model": "glm-5.2",
                    "fallback_reason": None,
                }
            elif type(self).mode == "attempted":
                llm.update(
                    configured=True,
                    attempted=True,
                    fallback_reason="provider_timeout",
                )
            elif type(self).mode == "available":
                llm.update(configured=True, fallback_reason=None)
            elif type(self).mode == "unsafe_model":
                llm.update(
                    configured=True,
                    attempted=True,
                    used=True,
                    provider="/private/model-error",
                    model="glm-5.2",
                    fallback_reason=None,
                )
            elif type(self).mode == "unsafe_fallback":
                llm.update(
                    configured=True,
                    attempted=True,
                    fallback_reason="raw_provider_error",
                )
            report = {
                "status": "completed",
                "as_of": (
                    "/private/report-prompt"
                    if type(self).mode == "unsafe_as_of"
                    else "2026-07-14"
                ),
                "modules": [{"module_id": "daily_overview"}],
                "warnings": [],
                "llm": llm,
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
        "event_count": 8,
        "terminal_event_count": 2,
        "text_delta_count": 2,
        "replayed": True,
    }
    assert summary["answer_stream"] == {
        "draft_seen": True,
        "terminal_phase": "verified_fallback",
        "highest_revision": 2,
        "snapshot_count": 2,
    }
    assert summary["report"] == {
        "present": True,
        "status": "completed",
        "as_of": "2026-07-14",
        "module_count": 1,
        "llm": {
            "configured": False,
            "attempted": False,
            "used": False,
            "provider": None,
            "model": None,
            "fallback_reason": "provider_unavailable",
        },
    }
    assert summary["readiness"] == {"page": True, "health": True, "skills": True}
    assert summary["run"] == {"duckdb_cutoff": "2026-07-13"}
    assert summary["cutoffs"] == {
        "readiness": "2026-07-13",
        "terminal": "2026-07-13",
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


def test_completed_smoke_accepts_idempotent_same_revision_replay(
    tmp_path: Path,
) -> None:
    exit_code, summary, _ = run_cli(tmp_path, "same_revision_replay")

    assert exit_code == 0
    assert summary["answer_stream"] == {
        "draft_seen": True,
        "terminal_phase": "verified_fallback",
        "highest_revision": 2,
        "snapshot_count": 2,
    }


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (
            "used",
            {
                "configured": True,
                "attempted": True,
                "used": True,
                "provider": "zhipu",
                "model": "glm-5.2",
                "fallback_reason": None,
            },
        ),
        (
            "attempted",
            {
                "configured": True,
                "attempted": True,
                "used": False,
                "provider": None,
                "model": None,
                "fallback_reason": "provider_timeout",
            },
        ),
        (
            "available",
            {
                "configured": True,
                "attempted": False,
                "used": False,
                "provider": None,
                "model": None,
                "fallback_reason": None,
            },
        ),
    ],
)
def test_smoke_summary_keeps_canonical_llm_state(
    tmp_path: Path,
    mode: str,
    expected: dict[str, object],
) -> None:
    exit_code, summary, _ = run_cli(tmp_path, mode)

    assert exit_code == 0
    assert summary["report"]["llm"] == expected


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("zhipu", "zhipu"),
        ("QWEN", "qwen"),
        ("fixture", "fixture"),
        ("unknown-provider", None),
    ],
)
def test_smoke_provider_labels_use_an_allowlist(
    provider: str,
    expected: str | None,
) -> None:
    assert smoke._safe_optional_provider_label(provider, "model_metadata") == expected


@pytest.mark.parametrize(
    "model",
    _CREDENTIAL_LABELS,
)
def test_smoke_rejects_credential_shaped_model_labels(model: str) -> None:
    with pytest.raises(smoke.SmokeProtocolError, match="model_metadata"):
        smoke._safe_optional_model_label(model, "model_metadata")


@pytest.mark.parametrize("model", _SUPPORTED_MODEL_LABELS)
def test_smoke_keeps_legitimate_model_labels(model: str) -> None:
    assert smoke._safe_optional_model_label(model, "model_metadata") == model


@pytest.mark.parametrize("model", _UNKNOWN_MODEL_LABELS)
def test_smoke_hides_unknown_model_families(model: str) -> None:
    assert smoke._safe_optional_model_label(model, "model_metadata") is None


def _mock_smoke_summary_with_model(
    monkeypatch: pytest.MonkeyPatch,
    model: str,
) -> tuple[int, dict[str, object], str]:
    report = {
        "status": "completed",
        "as_of": "2026-07-14",
        "modules": [],
        "warnings": [],
        "llm": {
            "configured": True,
            "attempted": True,
            "used": True,
            "provider": "zhipu",
            "model": model,
            "fallback_reason": None,
        },
    }

    def request_json(*_args: object, stage: str, **_kwargs: object) -> object:
        return {
            "readiness_health": {
                "status": "ready",
                "capabilities": {
                    "market_data": {
                        "available": True,
                        "source": "duckdb",
                        "cutoff": "2026-07-13",
                    }
                },
            },
            "readiness_skills": [],
            "create_conversation": {"conversation_id": "conversation-1"},
            "create_message": {"run_id": "run-1"},
            "run_report": report,
        }[stage]

    monkeypatch.setattr(smoke, "_request_bytes", lambda *_args, **_kwargs: b"<html>")
    monkeypatch.setattr(smoke, "_request_json", request_json)
    monkeypatch.setattr(
        smoke,
        "_stream_until_terminal",
        lambda **_kwargs: (
            {
                "run_id": "run-1",
                "status": "completed",
                "degrades": [],
                "duckdb_cutoff": "2026-07-13",
            },
            {
                "request_count": 1,
                "event_count": 1,
                "terminal_event_count": 1,
                "text_delta_count": 0,
                "replayed": False,
                "stages": ["understanding", "synthesis"],
                "answer_stream": {
                    "draft_seen": True,
                    "terminal_phase": "verified_fallback",
                    "highest_revision": 2,
                    "snapshot_count": 2,
                },
            },
        ),
    )

    exit_code, summary = smoke.run_smoke(
        Namespace(
            base_url="http://127.0.0.1:1",
            user="alice",
            question="测试安全摘要",
            timeout=3.0,
        )
    )
    raw_summary = json.dumps(summary, ensure_ascii=False)

    return exit_code, summary, raw_summary


@pytest.mark.parametrize("model", _CREDENTIAL_LABELS)
def test_smoke_summary_never_echoes_credential_families(
    monkeypatch: pytest.MonkeyPatch,
    model: str,
) -> None:
    exit_code, summary, raw_summary = _mock_smoke_summary_with_model(
        monkeypatch,
        model,
    )

    assert exit_code == 2
    assert model not in raw_summary
    assert model[:12] not in raw_summary
    if model != _CREDENTIAL_LABELS[-1]:
        assert summary["secret_scan"]["hit_count"] >= 1


@pytest.mark.parametrize("model", _UNKNOWN_MODEL_LABELS)
def test_smoke_summary_hides_unknown_model_families(
    monkeypatch: pytest.MonkeyPatch,
    model: str,
) -> None:
    exit_code, summary, raw_summary = _mock_smoke_summary_with_model(
        monkeypatch,
        model,
    )

    assert exit_code == 0
    assert summary["report"]["llm"]["model"] is None
    assert model not in raw_summary


@pytest.mark.parametrize(
    ("mode", "failure_stage", "unsafe_value"),
    [
        ("unsafe_model", "model_metadata", "/private/model-error"),
        ("unsafe_fallback", "model_metadata", "raw_provider_error"),
        ("unsafe_as_of", "report_metadata", "/private/report-prompt"),
        (
            "unsafe_cutoff",
            "run_metadata",
            "C:/private/market.duckdb",
        ),
        ("bad_cutoff", "run_metadata", "latest"),
    ],
)
def test_smoke_rejects_unsafe_metadata_without_echoing_it(
    tmp_path: Path,
    mode: str,
    failure_stage: str,
    unsafe_value: str,
) -> None:
    exit_code, summary, raw_summary = run_cli(tmp_path, mode)

    assert exit_code == 2
    assert summary["failure_stage"] == failure_stage
    assert unsafe_value not in raw_summary


def test_degraded_completed_smoke_returns_zero(tmp_path: Path) -> None:
    exit_code, summary, _ = run_cli(tmp_path, "degraded")

    assert exit_code == 0
    assert summary["terminal_outcome"] == "degraded"
    assert summary["degrade_count"] == 1


def test_non_duckdb_readiness_does_not_override_terminal_run_cutoff(
    tmp_path: Path,
) -> None:
    exit_code, summary, _ = run_cli(tmp_path, "snapshot_source")

    assert exit_code == 0
    assert summary["run"] == {"duckdb_cutoff": "2026-07-10"}


def test_completed_duckdb_smoke_requires_terminal_run_cutoff(
    tmp_path: Path,
) -> None:
    exit_code, summary, _ = run_cli(tmp_path, "missing_cutoff")

    assert exit_code == 2
    assert summary["failure_stage"] == "run_metadata"


@pytest.mark.parametrize(
    ("mode", "expected_terminal"),
    [
        ("completed", "2026-07-13"),
        ("later_cutoff", "2026-07-14"),
    ],
)
def test_completed_duckdb_smoke_accepts_equal_or_later_terminal_cutoff(
    tmp_path: Path,
    mode: str,
    expected_terminal: str,
) -> None:
    exit_code, summary, _ = run_cli(tmp_path, mode)

    assert exit_code == 0
    assert summary["cutoffs"] == {
        "readiness": "2026-07-13",
        "terminal": expected_terminal,
    }


def test_completed_duckdb_smoke_rejects_terminal_cutoff_older_than_readiness(
    tmp_path: Path,
) -> None:
    exit_code, summary, _ = run_cli(tmp_path, "older_cutoff")

    assert exit_code == 2
    assert summary["failure_stage"] == "run_metadata"
    assert summary["cutoffs"] == {
        "readiness": "2026-07-13",
        "terminal": "2026-07-10",
    }


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


@pytest.mark.parametrize(
    "mode",
    [
        "invalid_revision",
        "unknown_phase",
        "old_revision",
        "missing_draft",
        "missing_terminal",
        "invalid_snapshot_payload",
    ],
)
def test_completed_smoke_rejects_invalid_answer_snapshot_stream(
    tmp_path: Path,
    mode: str,
) -> None:
    exit_code, summary, _ = run_cli(tmp_path, mode)

    assert exit_code == 2
    assert summary["terminal_outcome"] == "protocol_error"
    assert summary["failure_stage"] == "answer_snapshot"


def test_completed_smoke_rejects_non_public_event_type(tmp_path: Path) -> None:
    exit_code, summary, _ = run_cli(tmp_path, "unknown_event")

    assert exit_code == 2
    assert summary["failure_stage"] == "sse_event_type"


def test_secret_scanner_scans_answer_snapshot_payload(tmp_path: Path) -> None:
    exit_code, summary, raw_summary = run_cli(tmp_path, "snapshot_secret")

    assert exit_code == 2
    assert summary["terminal_outcome"] == "secret_scan_failed"
    assert summary["secret_scan"]["hits"] == [
        {"source": "sse.answer.snapshot.payload.text", "marker": "token_prefix"}
    ]
    assert "ghp_abcdefghijklmnopqrstuvwxyz" not in raw_summary


def test_secret_scanner_ignores_redaction_placeholder() -> None:
    scanner = smoke.SecretScanner()

    scanner.scan({"value": "api_key=[REDACTED]"}, "fixture")

    assert scanner.hits == []


def test_secret_scanner_does_not_echo_unsafe_dictionary_keys() -> None:
    scanner = smoke.SecretScanner()

    scanner.scan({"/Users/private": "ghp_abcdefghijklmnopqrstuvwxyz"}, "fixture")

    assert scanner.hits == [{"source": "fixture.field", "marker": "token_prefix"}]
