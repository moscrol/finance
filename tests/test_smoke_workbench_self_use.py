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
                draft_text = (
                    "ghp_abcdefghijklmnopqrstuvwxyz"
                    if type(self).mode == "secret"
                    else "redacted draft"
                )
                events = [
                    (
                        "answer.snapshot",
                        {
                            "event_type": "answer.snapshot",
                            "seq": 1,
                            "payload": {
                                "revision": (
                                    0
                                    if type(self).mode == "invalid_revision"
                                    else 1
                                ),
                                "phase": (
                                    "unknown"
                                    if type(self).mode == "unknown_phase"
                                    else "verified_draft"
                                ),
                                "text": draft_text,
                                "final": type(self).mode == "invalid_final",
                            },
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
                if type(self).mode == "public_event_leak":
                    events[1] = (
                        "citation.ready",
                        {
                            "event_type": "citation.ready",
                            "seq": 2,
                            "payload": {
                                "citation": {
                                    "title": (
                                        'Traceback File '
                                        '"/Users/alice/private/rag_index.py", line 9'
                                    ),
                                    "warnings": ["provider_timeout"],
                                }
                            },
                        },
                    )
                if type(self).mode == "missing_draft":
                    events = events[1:]
                if type(self).mode == "replay":
                    events.insert(1, ("answer.snapshot", events[0][1]))
            else:
                assert after == 2
                events = [
                    (
                        "answer.snapshot",
                        {
                            "event_type": "answer.snapshot",
                            "seq": 3,
                            "payload": {
                                "revision": 2,
                                "phase": "verified_fallback",
                                "text": "redacted terminal",
                                "final": True,
                            },
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
                if type(self).mode == "missing_terminal":
                    events = events[1:]
                if type(self).mode == "conflict":
                    events.insert(
                        1,
                        (
                            "answer.snapshot",
                            {
                                "event_type": "answer.snapshot",
                                "seq": 4,
                                "payload": {
                                    "revision": 2,
                                    "phase": "validated_synthesis",
                                    "text": "conflicting terminal",
                                    "final": True,
                                },
                            },
                        ),
                    )
                if type(self).mode == "stale_revision":
                    events.insert(
                        1,
                        (
                            "answer.snapshot",
                            {
                                "event_type": "answer.snapshot",
                                "seq": 4,
                                "payload": {
                                    "revision": 1,
                                    "phase": "verified_draft",
                                    "text": "stale draft",
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
            report = {
                "status": "completed",
                "modules": [{"module_id": "daily_overview"}],
                "warnings": [],
                "llm": {
                    "used": False,
                    "provider": None,
                    "model": None,
                    "fallback_reason": "provider_timeout",
                },
            }
            if type(self).mode == "protocol":
                report.pop("llm")
            elif type(self).mode == "model_secret":
                report["llm"] = {
                    "used": True,
                    "provider": "zhipu",
                    "model": "ghp_abcdefghijklmnopqrstuvwxyz",
                }
            elif type(self).mode == "model_unknown":
                report["llm"] = {
                    "used": True,
                    "provider": "unknown-provider",
                    "model": "custom-model",
                }
            elif type(self).mode == "model_safe":
                report["llm"] = {
                    "used": True,
                    "provider": "QWEN",
                    "model": "qwen-plus",
                }
            self._json(report)
            return
        if parsed.path == "/api/runs/run-1/trace":
            if type(self).mode == "trace_leak":
                self._json(
                    [
                        {
                            "name": "ask_retrieve_compose",
                            "output_summary": (
                                'Traceback File '
                                '"/Users/alice/private/rag_index.py", line 9'
                            ),
                        }
                    ]
                )
                return
            self._json(
                [
                    {
                        "name": "ask_retrieve_compose",
                        "output_summary": json.dumps(
                            {
                                "wiki_rag": {
                                    "requested_mode": "hybrid",
                                    "effective_mode": "bm25",
                                    "fallback_reason": "dense_dependency_missing",
                                }
                            }
                        ),
                    }
                ]
            )
            return
        if parsed.path == "/api/conversations/conversation-1/messages":
            messages = (
                [
                    {
                        "role": "assistant",
                        "content": "可核验回答",
                        "degrades": [
                            'Traceback File '
                            '"/Users/alice/private/rag_index.py", line 9',
                            "provider_timeout",
                        ],
                    }
                ]
                if type(self).mode == "message_leak"
                else []
            )
            self._json(messages)
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
        "text_delta_count": 0,
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
        "module_count": 1,
    }
    assert summary["model"] == {
        "metadata_present": True,
        "used": False,
        "provider": None,
        "model": None,
    }
    assert summary["retrieval"] == {
        "requested_mode": "hybrid",
        "effective_mode": "bm25",
        "fallback_reason": "dense_dependency_missing",
    }
    assert summary["secret_scan"]["hit_count"] == 0
    assert summary["public_scan"]["hit_count"] == 0
    assert "今天市场怎么样" not in raw_summary
    assert "private citation" not in raw_summary
    assert "example.invalid" not in raw_summary
    assert "redacted draft" not in raw_summary
    assert "redacted terminal" not in raw_summary


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
        {
            "source": "sse.answer.snapshot.payload.text",
            "marker": "token_prefix",
        }
    ]
    assert "ghp_abcdefghijklmnopqrstuvwxyz" not in raw_summary


@pytest.mark.parametrize(
    "mode",
    ["public_event_leak", "message_leak", "trace_leak"],
)
def test_public_scan_covers_canonical_events_messages_and_trace(
    tmp_path: Path,
    mode: str,
) -> None:
    exit_code, summary, raw_summary = run_cli(tmp_path, mode)

    assert exit_code == 2
    assert summary["terminal_outcome"] == "public_scan_failed"
    assert summary["public_scan"]["hit_count"] > 0
    assert "Traceback" not in raw_summary
    assert "/Users/alice" not in raw_summary
    assert "provider_timeout" not in raw_summary


def test_completed_smoke_requires_model_metadata(tmp_path: Path) -> None:
    exit_code, summary, _ = run_cli(tmp_path, "protocol")

    assert exit_code == 2
    assert summary["terminal_outcome"] == "protocol_error"
    assert summary["failure_stage"] == "model_metadata"


def test_smoke_rejects_credential_shaped_model_without_echoing_it(
    tmp_path: Path,
) -> None:
    exit_code, summary, raw_summary = run_cli(tmp_path, "model_secret")

    assert exit_code == 2
    assert summary["terminal_outcome"] == "secret_scan_failed"
    assert summary["secret_scan"]["hit_count"] > 0
    assert "ghp_abcdefghijklmnopqrstuvwxyz" not in raw_summary


def test_smoke_hides_unknown_model_metadata(tmp_path: Path) -> None:
    exit_code, summary, raw_summary = run_cli(tmp_path, "model_unknown")

    assert exit_code == 0
    assert summary["model"]["provider"] is None
    assert summary["model"]["model"] is None
    assert "unknown-provider" not in raw_summary
    assert "custom-model" not in raw_summary


def test_smoke_keeps_allowlisted_model_metadata(tmp_path: Path) -> None:
    exit_code, summary, _ = run_cli(tmp_path, "model_safe")

    assert exit_code == 0
    assert summary["model"]["provider"] == "qwen"
    assert summary["model"]["model"] == "qwen-plus"


@pytest.mark.parametrize(
    "model",
    [
        "AKIAIOSFODNN7EXAMPLE",
        "ya29.a0AfH6SMabcdefghijklmnopqrstuvwxyz",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhbGljZSJ9.dGVzdHNpZ25hdHVyZQ",
        "aB3dE5fG7hJ9kL2mN4pQ6rS8tV0wX1yZ3cD5eF7gH9jK2mN4",
    ],
)
def test_model_label_rejects_other_credential_families(model: str) -> None:
    with pytest.raises(smoke.SmokeProtocolError, match="model_metadata"):
        smoke._safe_optional_model_label(model, "model_metadata")


@pytest.mark.parametrize(
    ("mode", "failure_stage"),
    [
        ("missing_draft", "answer_snapshot_draft"),
        ("missing_terminal", "answer_snapshot_terminal"),
        ("invalid_revision", "answer_snapshot"),
        ("unknown_phase", "answer_snapshot"),
        ("invalid_final", "answer_snapshot"),
        ("conflict", "answer_snapshot_conflict"),
        ("stale_revision", "answer_snapshot_revision"),
    ],
)
def test_completed_smoke_rejects_invalid_snapshot_state(
    tmp_path: Path,
    mode: str,
    failure_stage: str,
) -> None:
    exit_code, summary, _ = run_cli(tmp_path, mode)

    assert exit_code == 2
    assert summary["terminal_outcome"] == "protocol_error"
    assert summary["failure_stage"] == failure_stage


def test_completed_smoke_accepts_idempotent_snapshot_replay(
    tmp_path: Path,
) -> None:
    exit_code, summary, _ = run_cli(tmp_path, "replay")

    assert exit_code == 0
    assert summary["answer_stream"]["snapshot_count"] == 2


def test_secret_scanner_ignores_redaction_placeholder() -> None:
    scanner = smoke.SecretScanner()

    scanner.scan({"value": "api_key=[REDACTED]"}, "fixture")

    assert scanner.hits == []


def test_secret_scanner_does_not_echo_unsafe_dictionary_keys() -> None:
    scanner = smoke.SecretScanner()

    scanner.scan({"/Users/private": "ghp_abcdefghijklmnopqrstuvwxyz"}, "fixture")

    assert scanner.hits == [{"source": "fixture.field", "marker": "token_prefix"}]


# ── 缺口锚点：用上游抽好的 subject，别从问句里猜 ────────────────────────────
# 2026-08-14 实测的判据倒挂：问句「液冷服务器现在发酵到什么阶段？主线还是补涨？…」
# 只被猜出唯一锚点「主线」，于是 741 字实质回答判红、185 字复述题干的拒答判绿。
# 收据：~/.local/share/finance-workbench/users/smoke-quality-0814/runs/
#       run_20260814_112138_376189（实质）与 run_20260814_134100_771575（拒答）

_THEME_QUESTION = (
    "液冷服务器现在发酵到什么阶段？主线还是补涨？核心受益公司有哪些，"
    "各自的证据和风险是什么，接下来一周的验证点是什么"
)
_SUBSTANTIVE_ANSWER = (
    "截至8月13日的基准判断：液冷服务器处于AI算力内部扩散的早期至中段，"
    "更像算力主线的补涨。中石科技是当前最强交易核心之一；"
    "康盛股份现有材料仅支持液冷关联，缺少可核验的液冷服务器产品及订单资料，风险更高。"
)
_REFUSAL_ECHOING_QUESTION = (
    f"关于“{_THEME_QUESTION}”，现有证据不足，暂不能可靠回答。"
    "本轮已取得 36 条证据，但未完成核验绑定，暂不能引用。"
)


def test_substantive_gap_passes_when_it_names_the_upstream_subject() -> None:
    """实质回答点名了 subject（液冷服务器）就该算说清了缺口。"""
    assert smoke._has_task_specific_gap(
        _THEME_QUESTION, _SUBSTANTIVE_ANSWER, "液冷服务器"
    )


def test_refusal_that_only_echoes_the_question_is_not_a_gap_statement() -> None:
    """复述题干会把每个锚点都带进来，不能算「说清了缺什么」。"""
    assert not smoke._has_task_specific_gap(
        _THEME_QUESTION, _REFUSAL_ECHOING_QUESTION, "液冷服务器"
    )


def test_subject_anchor_is_load_bearing() -> None:
    """变异测试：拿掉 subject 就退回旧行为，实质回答会被误杀。

    没有这条，任何人把 subject 参数删掉都不会有测试变红。
    """
    assert not smoke._has_task_specific_gap(_THEME_QUESTION, _SUBSTANTIVE_ANSWER, "")


def test_question_echo_exclusion_is_load_bearing() -> None:
    """变异测试：不排除复述题干时，拒答会蒙混过关。"""
    segments = smoke._gap_segments(_REFUSAL_ECHOING_QUESTION.split("。")[0])
    asserts_gap = [s for s in segments if smoke._segment_asserts_gap(s)]
    assert asserts_gap, "样本本身要含缺口断言，否则这条变异测试测了个寂寞"
    assert any("液冷服务器" in s for s in asserts_gap), "复述确实把锚点带了进来"
    assert all(smoke._echoes_question(s, _THEME_QUESTION) for s in asserts_gap)


def test_semantic_issues_reads_subject_from_report_task_frame() -> None:
    """端到端：subject 走 report.task_frame，缺字段时不 fail closed。"""
    report = {"answer_status": "partial", "task_frame": {"subject": "液冷服务器"}}
    messages = [{"role": "assistant", "content": _SUBSTANTIVE_ANSWER}]
    assert "answer_status='partial'" not in smoke.semantic_answer_issues(
        _THEME_QUESTION, report, messages
    )
    no_frame = {"answer_status": "partial"}
    assert smoke.semantic_answer_issues(_THEME_QUESTION, no_frame, messages) is not None
