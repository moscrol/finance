"""Offline fake-upstream tests. No model requests or credentials involved."""
from __future__ import annotations

import concurrent.futures
import http.client
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/review_probes/k3_review_shim.py"
FIRST = b'data: {"choices":[{"delta":{"content":"first"}}]}\n\n'
LAST = b"data: [DONE]\n\n"


def eventually(check, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if check():
            return
        time.sleep(0.01)
    assert check()


@pytest.fixture
def upstream():
    state = dict(payloads=[], received=threading.Event(), release=threading.Event(),
                 disconnected=threading.Event(), mode="normal", status=200)

    class Fake(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_POST(self):
            state["payloads"].append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            state["received"].set()
            self.close_connection = True
            try:
                if state["mode"] == "headers_stall":
                    state["release"].wait(3)
                self.send_response(state["status"])
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(FIRST) + len(LAST)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(FIRST)
                self.wfile.flush()
                if state["mode"] == "truncated":
                    return
                if state["mode"] == "body_stall":
                    end = time.monotonic() + 4
                    while not state["release"].is_set() and time.monotonic() < end:
                        if select.select([self.connection], [], [], 0.02)[0]:
                            if not self.connection.recv(1, socket.MSG_PEEK):
                                state["disconnected"].set()
                                return
                self.wfile.write(LAST)
                self.wfile.flush()
            except OSError:
                state["disconnected"].set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
    thread.start()
    state["port"] = server.server_address[1]
    yield state
    state["release"].set()
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def launch(tmp_path, upstream):
    processes = []

    def start(*, limit=8, request_seconds=3, lifetime_seconds=15):
        output = tmp_path / f"run-{len(processes)}"
        proc = subprocess.Popen(
            [sys.executable, str(SCRIPT), "--listen", "0", "--upstream-port", str(upstream["port"]),
             "--output", str(output), "--max-requests", str(limit),
             "--request-seconds", str(request_seconds), "--lifetime-seconds", str(lifetime_seconds)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        processes.append(proc)
        assert select.select([proc.stdout], [], [], 3)[0], "shim did not start"
        first = proc.stdout.readline()
        assert first, proc.stderr.read()
        port = json.loads(first)["port"]
        return proc, port, output

    yield start
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=6)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        stderr = proc.stderr.read()
        proc.stdout.close()
        proc.stderr.close()
        assert not stderr, stderr


def request(port, payload=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
    conn.request("POST", "/v1/chat/completions", json.dumps(payload or {"model": "kimi-k3", "messages": []}),
                 {"Content-Type": "application/json"})
    return conn, conn.getresponse()


def counts(output):
    return json.loads((output / "counts.json").read_text())


def events(output):
    return [json.loads(line) for line in (output / "requests.jsonl").read_text().splitlines()]


def test_first_chunk_arrives_before_upstream_eof_and_payload_is_preserved(launch, upstream):
    upstream["mode"] = "body_stall"
    proc, port, output = launch()
    payload = dict(model="kimi-k3", messages=[{"role": "user", "content": "offline"}],
                   temperature=1, stream=True, tools=[{"type": "function", "function": {"name": "read"}}],
                   tool_choice="auto", max_tokens=17, reasoning_effort="high")
    conn, response = request(port, payload)
    assert response.status == 200
    started = time.monotonic()
    assert response.read1(65536) == FIRST
    assert time.monotonic() - started < 0.5
    assert not upstream["release"].is_set()
    snapshot = counts(output)
    assert (snapshot["requests"], snapshot["dispatched"], snapshot["active"]) == (1, 1, 1)
    assert upstream["payloads"] == [{k: v for k, v in payload.items() if k != "temperature"}]
    upstream["release"].set()
    assert response.read() == LAST
    conn.close()
    eventually(lambda: counts(output)["completed"] == 1)
    proc.terminate()
    assert proc.wait(timeout=3) == 0
    assert counts(output)["shutdown_complete"]
    assert counts(output)["dropped_temperature"] == 1
    kinds = [row["event"] for row in events(output)]
    assert kinds.index("admitted") < kinds.index("dispatched") < kinds.index("headers") < kinds.index("finished")


def test_client_disconnect_closes_stalled_upstream(launch, upstream):
    upstream["mode"] = "body_stall"
    _, port, output = launch()
    conn, response = request(port)
    assert response.read1(65536) == FIRST
    response.close()
    conn.close()
    assert upstream["disconnected"].wait(0.8)
    eventually(lambda: counts(output)["cancelled"] == 1)
    assert counts(output)["active"] == 0


def test_sigterm_interrupts_read_and_persists_terminal_counts(launch, upstream):
    upstream["mode"] = "body_stall"
    proc, port, output = launch()
    conn, response = request(port)
    assert response.read1(65536) == FIRST
    proc.terminate()
    assert proc.wait(timeout=1) == 0
    assert upstream["disconnected"].wait(0.8)
    response.close()
    conn.close()
    value = counts(output)
    assert (value["requests"], value["dispatched"], value["cancelled"], value["active"]) == (1, 1, 1, 0)
    assert value["shutdown_complete"]


def test_sigkill_still_preserves_admission_without_claiming_completion(launch, upstream):
    upstream["mode"] = "body_stall"
    proc, port, output = launch()
    conn, response = request(port)
    assert response.read1(65536) == FIRST
    proc.send_signal(signal.SIGKILL)
    assert proc.wait(timeout=1) == -signal.SIGKILL
    response.close()
    conn.close()
    value = counts(output)
    assert value["requests"] == value["active"] == 1
    assert not value["shutdown_complete"]
    assert "finished" not in [row["event"] for row in events(output)]


@pytest.mark.parametrize("mode", ["headers_stall", "body_stall"])
def test_request_deadline_interrupts_stall(launch, upstream, mode):
    upstream["mode"] = mode
    _, port, output = launch(request_seconds=0.25)
    start = time.monotonic()
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    conn.request("POST", "/v1/chat/completions", json.dumps({"model": "kimi-k3"}))
    try:
        response = conn.getresponse()
        response.read()
    except (http.client.HTTPException, OSError):
        pass
    finally:
        conn.close()
    eventually(lambda: counts(output)["failed"] == 1)
    assert time.monotonic() - start < 1
    assert counts(output)["active"] == 0


@pytest.mark.parametrize("status", [400, 429])
def test_upstream_rejection_stops_new_dispatches_without_retry(launch, upstream, status):
    upstream["status"] = status
    _, port, output = launch()
    conn, response = request(port)
    assert response.status == status
    response.read()
    conn.close()
    conn, response = request(port)
    assert response.status == 503
    response.read()
    conn.close()
    eventually(lambda: counts(output)["failed"] == 1)
    assert len(upstream["payloads"]) == counts(output)["requests"] == counts(output)["dispatched"] == 1
    assert counts(output)["stopped_for"] == f"http_{status}"


def test_concurrent_requests_cannot_overspend_preallocated_quota(launch, upstream):
    _, port, output = launch(limit=2)

    def call(_):
        conn, response = request(port)
        status = response.status
        response.read()
        conn.close()
        return status

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(call, range(6)))
    assert sorted(results) == [200, 200, 503, 503, 503, 503]
    eventually(lambda: counts(output)["active"] == 0)
    assert counts(output)["requests"] == len(upstream["payloads"]) == 2


def test_truncated_upstream_is_not_reported_as_completed(launch, upstream):
    upstream["mode"] = "truncated"
    _, port, output = launch()
    conn, response = request(port)
    with pytest.raises(http.client.IncompleteRead):
        response.read()
    conn.close()
    eventually(lambda: counts(output)["failed"] == 1)
    assert counts(output)["completed"] == 0


def test_wrong_model_is_local_rejection_without_upstream_side_effect(launch, upstream):
    _, port, output = launch()
    conn, response = request(port, {"model": "different-model"})
    assert response.status == 400
    response.read()
    conn.close()
    assert counts(output)["requests"] == 0
    assert upstream["payloads"] == []


def test_lifetime_closes_listener_and_writes_shutdown(launch):
    proc, _, output = launch(lifetime_seconds=0.15)
    assert proc.wait(timeout=1) == 0
    assert counts(output)["shutdown_complete"]
