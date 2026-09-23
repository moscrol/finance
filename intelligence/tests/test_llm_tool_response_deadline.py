"""Tool response reads share the original call window, not an idle timeout."""
from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time

import pytest

from intelligence.services import llm_refine


@contextmanager
def local_provider(*, streaming=False, header_delay=0.0, body_seconds=0.9, emit_first=False):
    stopped = threading.Event()
    handlers = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            handlers.append(threading.current_thread())
            self.rfile.read(int(self.headers["Content-Length"]))
            if stopped.wait(header_delay):
                return
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream" if streaming else "application/json")
                self.end_headers()
                if emit_first:
                    self.wfile.write(b'data: {"choices":[{"delta":{"content":"early"}}]}\n\n')
                    self.wfile.flush()
                end = time.monotonic() + body_seconds
                while time.monotonic() < end and not stopped.is_set():
                    # Each chunk is well inside the socket idle timeout.
                    self.wfile.write(b": heartbeat\n\n" if streaming else b" ")
                    self.wfile.flush()
                    stopped.wait(0.025)
                if streaming:
                    body = b'data: {"choices":[{"delta":{"content":"late"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
                else:
                    body = json.dumps({"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                                       "usage": {"prompt_tokens": 2, "completion_tokens": 1}}).encode()
                self.wfile.write(body)
                self.wfile.flush()
            except OSError:
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    try:
        yield llm_refine.LLMProvider("test", "local-test", f"http://127.0.0.1:{server.server_port}", "test")
    finally:
        stopped.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        for handler in handlers:
            handler.join(timeout=2)
        assert not thread.is_alive() and all(not handler.is_alive() for handler in handlers)


@pytest.fixture(autouse=True)
def local_only(monkeypatch):
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setattr(llm_refine, "_reserve_llm_call", lambda: None)
    timers = []
    real_timer = threading.Timer

    def tracked_timer(*args, **kwargs):
        timer = real_timer(*args, **kwargs)
        timers.append(timer)
        return timer

    monkeypatch.setattr(llm_refine.threading, "Timer", tracked_timer)
    yield
    assert all(not timer.is_alive() for timer in timers)


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("header_delay", [0.0, 0.18])
def test_trickling_response_cannot_renew_tool_call_window(monkeypatch, streaming, header_delay):
    records = []
    monkeypatch.setattr(llm_refine, "_record_llm_call", lambda *args, **kwargs: records.append(args))
    deltas = []
    with local_provider(streaming=streaming, header_delay=header_delay) as provider:
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            if streaming:
                llm_refine._post_chat_message_stream(provider, [], 0.35, 0.0, [], "auto", True, deltas.append)
            else:
                llm_refine._post_chat_message(provider, [], 0.35)
        elapsed = time.monotonic() - started
    assert elapsed < 0.65, f"response read renewed the 0.35s window: {elapsed:.3f}s"
    assert deltas == []
    assert len(records) == 1 and records[0][2] == "failed"


def test_in_window_response_preserves_message_usage_and_ledger(monkeypatch):
    records = []
    monkeypatch.setattr(llm_refine, "_record_llm_call", lambda *args, **kwargs: records.append(args))
    with local_provider(body_seconds=0.025) as provider:
        message = llm_refine._post_chat_message(provider, [], 1.0)
    assert message["content"] == "ok"
    assert message["_finish_reason"] == "stop"
    assert message["_usage"] == {"prompt_tokens": 2, "completion_tokens": 1}
    assert len(records) == 1 and records[0][2] == "success"


def test_response_deadline_does_not_add_provider_fallback(monkeypatch):
    with local_provider() as provider:
        calls = []
        monkeypatch.setattr(llm_refine, "detect_providers", lambda _: (provider, provider))
        monkeypatch.setattr(llm_refine, "_record_llm_call", lambda *args, **kwargs: calls.append(args))
        message, used, reason = llm_refine.chat_with_tools([], [], timeout=0.2, min_viable_seconds=0)
    assert message is None and used == provider and "TimeoutError" in reason
    assert len(calls) == 1


def test_expiry_after_first_delta_keeps_no_replay_rule(monkeypatch):
    deltas = []
    with local_provider(streaming=True, emit_first=True) as provider:
        calls = []
        monkeypatch.setattr(llm_refine, "detect_providers", lambda _: (provider, provider))
        monkeypatch.setattr(llm_refine, "_record_llm_call", lambda *args, **kwargs: calls.append(args))
        message, used, reason = llm_refine.chat_with_tools(
            [], [], timeout=0.2, min_viable_seconds=0, on_content_delta=deltas.append,
        )
    assert message is None and used == provider and reason == llm_refine._STREAM_FALLBACK_BLOCKED
    assert deltas == ["early"]
    assert len(calls) == 1 and calls[0][2] == "failed"


def test_late_result_without_socket_is_still_rejected(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(llm_refine.time, "monotonic", lambda: clock[0])
    with pytest.raises(TimeoutError):
        with llm_refine._tool_response_window(object(), llm_refine.Deadline(1.0)):
            clock[0] = 2.0


def test_exhausted_window_does_not_enter_response_reader():
    with pytest.raises(TimeoutError):
        with llm_refine._tool_response_window(object(), llm_refine.Deadline.from_timeout(0)):
            pytest.fail("expired response body must not be consumed")
