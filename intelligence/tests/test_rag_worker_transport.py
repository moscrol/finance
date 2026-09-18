"""Real pipe + real consumer; deterministic framing, no model/KB or sleeping worker."""
from __future__ import annotations

from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

from intelligence.services import rag_worker


def _reply(request_id: str, stdout: str = "当前响应") -> bytes:
    return (json.dumps({"id": request_id, "stdout": stdout, "returncode": 0,
                        "model_load_count": 1}, ensure_ascii=False) + "\n").encode("utf-8")


@contextmanager
def _pipe_worker(monkeypatch, on_request):
    """Text wrapper recreates old read-ahead; the new consumer must own all reads."""
    read_fd, write_fd = os.pipe()
    reader = io.TextIOWrapper(io.BufferedReader(io.FileIO(read_fd, "r")), encoding="utf-8")
    ended = False

    def send(data):
        assert os.write(write_fd, data) == len(data)

    def end():
        nonlocal ended
        if not ended:
            ended = True
            os.close(write_fd)

    class RequestSink(io.StringIO):
        def flush(self):
            request = json.loads(self.getvalue())
            self.seek(0)
            self.truncate()
            on_request(request, send, end)

    process = SimpleNamespace(stdin=RequestSink(), stdout=reader,
                              poll=lambda: 0 if ended else None, terminate=end,
                              kill=end, wait=lambda **kwargs: 0)
    worker = rag_worker.PersistentRagWorker(sys.executable, Path("unused-kb"), Path("unused-index"))
    worker._process = process
    worker.model_load_count = 1
    worker._state = "ready"
    monkeypatch.setattr(worker, "_ensure_process", lambda: process)
    try:
        yield worker
    finally:
        worker.close()
        end()
        reader.close()


def test_coalesced_abandoned_and_current_responses_are_both_consumed(monkeypatch):
    def respond(request, send, end):
        send(_reply("old", "旧响应") + _reply(request["id"]))

    with _pipe_worker(monkeypatch, respond) as worker:
        worker._abandoned.add("old")
        worker._consecutive_timeouts = 1
        response = worker.query(["query", "current"], timeout=0.1)
        assert response.stdout == "当前响应"
        assert worker.healthy()
        assert worker._abandoned == set()
        assert worker._consecutive_timeouts == 0
        assert worker.counters["stale_responses_drained"] == 1
        assert worker.counters["timeouts_killed"] == 0
        # Exact same process handles the following request, not a fresh replacement.
        process = worker._process
        worker._abandoned.add("old")
        assert worker.query(["query", "again"], timeout=0.1).stdout == "当前响应"
        assert worker._process is process
        assert worker.counters["queries_served"] == 2


def test_partial_utf8_response_survives_abandonment_until_next_request(monkeypatch):
    tail = b""
    calls = 0
    watchdogs = []

    def respond(request, send, end):
        nonlocal tail, calls
        calls += 1
        if calls == 1:
            data = _reply(request["id"], "旧响应")
            split = data.index("旧".encode("utf-8")) + 1
            send(data[:split])
            tail = data[split:]
            # Bound an incorrect blocking readline: a failure must not hang pytest.
            timer = threading.Timer(1, end)
            timer.daemon = True
            timer.start()
            watchdogs.append(timer)
        else:
            send(tail + _reply(request["id"]))

    try:
        with _pipe_worker(monkeypatch, respond) as worker:
            with pytest.raises(rag_worker.WorkerRequestAbandoned):
                worker.query(["query", "old"], timeout=0.03)
            assert worker.healthy(), "a partial line must time out without killing a warm worker"
            assert worker.query(["query", "current"], timeout=0.2).stdout == "当前响应"
            assert worker.counters["stale_responses_drained"] == 1
            assert worker.counters["timeouts_abandoned_kept_warm"] == 1
            assert worker.counters["timeouts_killed"] == 0
    finally:
        for timer in watchdogs:
            timer.cancel()
            timer.join()


@pytest.mark.parametrize("chunk_size", [1, 2, 7, 65536])
def test_fragmented_utf8_and_long_line_reassemble_before_decode(monkeypatch, chunk_size):
    # Payload > one os.read chunk; no large pipe write that could itself block.
    expected = "液冷😀\\n" * 14000
    payload = bytearray()
    clock = [0.0]

    class ChunkSelector:
        def register(self, *args):
            pass

        def select(self, timeout):
            clock[0] += 0.000001
            return [True] if payload else []

        def close(self):
            pass

    def respond(request, send, end):
        payload.extend(_reply(request["id"], expected))

    def read(fd, count):
        data = bytes(payload[:min(count, chunk_size)])
        del payload[:len(data)]
        return data

    with _pipe_worker(monkeypatch, respond) as worker:
        monkeypatch.setattr(rag_worker.selectors, "DefaultSelector", ChunkSelector)
        monkeypatch.setattr(rag_worker.os, "read", read)
        monkeypatch.setattr(rag_worker.time, "monotonic", lambda: clock[0])
        assert worker.query(["query", "unicode"], timeout=2).stdout == expected
        assert not payload


def test_stale_and_partial_chunks_do_not_extend_absolute_deadline(monkeypatch):
    clock = [0.0]
    waits = []
    selections = 0

    class TrickleSelector:
        def register(self, *args):
            pass

        def select(self, timeout):
            nonlocal selections
            waits.append(timeout)
            clock[0] += min(0.03, timeout)
            selections += 1
            assert selections <= 10, "deadline was extended by incoming chunks"
            return [True]

        def close(self):
            pass

    def read(fd, count):
        return _reply("old") if selections == 1 else b" "

    with _pipe_worker(monkeypatch, lambda *args: None) as worker:
        worker._abandoned.add("old")
        worker._consecutive_timeouts = 1
        monkeypatch.setattr(rag_worker.selectors, "DefaultSelector", TrickleSelector)
        monkeypatch.setattr(rag_worker.os, "read", read)
        monkeypatch.setattr(rag_worker.time, "monotonic", lambda: clock[0])
        with pytest.raises(TimeoutError) as error:
            worker.query(["query", "current"], timeout=0.1)
        assert not isinstance(error.value, rag_worker.WorkerRequestAbandoned)
        assert clock[0] == pytest.approx(0.1)
        assert waits == pytest.approx([0.1, 0.07, 0.04, 0.01])
        assert worker.counters["stale_responses_drained"] == 1
        assert worker.counters["timeouts_killed"] == 1
        assert not worker.healthy()


@pytest.mark.parametrize("prefix", [b"", b'{"id":"partial"'])
def test_eof_does_not_accept_an_unterminated_response(monkeypatch, prefix):
    def respond(request, send, end):
        if prefix:
            send(prefix)
        end()

    with _pipe_worker(monkeypatch, respond) as worker:
        with pytest.raises(RuntimeError, match="rag worker exited"):
            worker.query(["query", "eof"], timeout=1)
        assert worker._state == "failed"
        assert not worker.healthy()
        assert worker.counters["queries_served"] == 0


@pytest.mark.parametrize("kind", ["unknown-id", "duplicate-old", "invalid-json", "invalid-utf8"])
def test_invalid_frame_is_not_mistaken_for_the_current_response(monkeypatch, kind):
    def respond(request, send, end):
        bad = {"unknown-id": _reply("other"), "duplicate-old": _reply("old") * 2,
               "invalid-json": b"not json\n", "invalid-utf8": b"\xff\n"}[kind]
        send(bad + _reply(request["id"]))

    with _pipe_worker(monkeypatch, respond) as worker:
        worker._abandoned.add("old")
        with pytest.raises((RuntimeError, ValueError)):
            worker.query(["query", "current"], timeout=1)
        assert worker._state == "failed"
        assert worker.counters["queries_served"] == 0
        assert not worker.healthy()


def test_spurious_readability_does_not_block_or_fail_the_worker(monkeypatch):
    real_read = os.read
    calls = 0

    def read(fd, count):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise BlockingIOError()
        return real_read(fd, count)

    def respond(request, send, end):
        send(_reply(request["id"]))

    with _pipe_worker(monkeypatch, respond) as worker:
        monkeypatch.setattr(rag_worker.os, "read", read)
        assert worker.query(["query", "current"], timeout=1).stdout == "当前响应"
        assert calls == 2
        assert worker.healthy()
