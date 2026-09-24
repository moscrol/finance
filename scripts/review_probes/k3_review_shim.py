"""Loopback-only K3 review proxy with streaming and durable request accounting.

Private acceptance tooling, never a production route. Only temperature is
removed from JSON payloads. No credentials, prompts, or response bodies are
logged. Each invocation requires a fresh output directory and finite budgets.
"""
from __future__ import annotations

import argparse
import http.client
import json
import math
import os
import select
import signal
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Ledger:
    def __init__(self, output: Path, max_requests: int):
        output.mkdir(parents=True, exist_ok=False)
        self.output = output
        self.limit = max_requests
        self.lock = threading.RLock()
        self.fd = os.open(output / "requests.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self.state = dict(requests=0, dispatched=0, completed=0, failed=0,
                          cancelled=0, active=0, dropped_temperature=0,
                          stopped_for=None, shutdown_complete=False)
        self.record("started")

    def record(self, event: str, **fields) -> None:
        with self.lock:
            row = dict(event=event, monotonic=time.monotonic(), **fields)
            data = (json.dumps(row, sort_keys=True) + "\n").encode()
            with os.fdopen(os.dup(self.fd), "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            temporary = self.output / "counts.pending"
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump(self.state, stream, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.output / "counts.json")

    def admit(self, dropped: bool) -> int | None:
        with self.lock:
            if self.state["stopped_for"] or self.state["requests"] >= self.limit:
                self.record("rejected", reason=self.state["stopped_for"] or "request_limit")
                return None
            self.state["requests"] += 1
            self.state["active"] += 1
            self.state["dropped_temperature"] += int(dropped)
            number = self.state["requests"]
            self.record("admitted", request=number, temperature_removed=dropped)
            return number

    def dispatched(self, number: int) -> None:
        with self.lock:
            self.state["dispatched"] += 1
            self.record("dispatched", request=number)

    def headers(self, number: int, status: int) -> None:
        with self.lock:
            if status in (400, 429):
                self.state["stopped_for"] = f"http_{status}"
            self.record("headers", request=number, status=status)

    def finish(self, number: int, outcome: str, status: int | None, started: float) -> None:
        with self.lock:
            self.state[outcome] += 1
            self.state["active"] -= 1
            self.record("finished", request=number, outcome=outcome, status=status,
                        elapsed_seconds=round(time.monotonic() - started, 6))

    def close(self) -> None:
        with self.lock:
            self.state["shutdown_complete"] = self.state["active"] == 0
            self.record("shutdown")
            os.close(self.fd)


def interrupt(sock) -> None:
    if sock is not None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


class ReviewServer(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True

    def __init__(self, port: int, upstream_port: int, ledger: Ledger,
                 request_seconds: float, lifetime_seconds: float):
        self.upstream_port = upstream_port
        self.ledger = ledger
        self.request_seconds = request_seconds
        self.expires_at = time.monotonic() + lifetime_seconds
        self.stopping = threading.Event()
        super().__init__(("127.0.0.1", port), Handler)

    def handle_error(self, request, client_address):
        # BaseHTTPRequestHandler tracebacks can expose upstream error content.
        self.ledger.record("handler_error")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(min(5.0, self.server.request_seconds))

    def log_message(self, *_args):
        pass

    def reject(self, status: int) -> None:
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()

    def do_GET(self):
        if self.path != "/_status":
            self.reject(404)
            return
        with self.server.ledger.lock:
            payload = json.dumps(self.server.ledger.state).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Content-Type", "application/json")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True

    def do_POST(self):
        server = self.server
        self.close_connection = True
        if (self.path != "/v1/chat/completions" or server.stopping.is_set()
                or time.monotonic() >= server.expires_at):
            self.reject(503)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4 * 1024 * 1024 or self.headers.get("Transfer-Encoding"):
                raise ValueError("invalid framing")
            body = self.rfile.read(length)
            payload = json.loads(body)
            if len(body) != length or not isinstance(payload, dict) or payload.get("model") != "kimi-k3":
                raise ValueError("invalid payload")
        except (ValueError, OSError):
            self.reject(400)
            return
        dropped = "temperature" in payload
        if dropped:
            del payload["temperature"]
            body = json.dumps(payload, ensure_ascii=False).encode()
        number = server.ledger.admit(dropped)
        if number is None:
            self.reject(503)
            return
        started = time.monotonic()
        deadline = min(server.expires_at, started + server.request_seconds)
        conn = http.client.HTTPConnection("127.0.0.1", server.upstream_port,
                                          timeout=max(0.01, deadline - started))
        done = threading.Event()
        cancelled = threading.Event()
        deadline_reached = threading.Event()
        status = None
        outcome = "failed"
        response_started = False
        upstream_socket = None

        def watch() -> None:
            while not done.wait(0.02):
                try:
                    readable, _, _ = select.select([self.connection], [], [], 0)
                    peer_closed = bool(readable) and not self.connection.recv(1, socket.MSG_PEEK)
                except OSError:
                    peer_closed = True
                expired = time.monotonic() >= deadline
                if peer_closed or server.stopping.is_set() or expired:
                    (deadline_reached if expired else cancelled).set()
                    # shutdown wakes reads, including getresponse() and read1().
                    interrupt(upstream_socket)
                    interrupt(self.connection)
                    return

        watcher = threading.Thread(target=watch)
        watcher.start()
        try:
            headers = {"Content-Type": "application/json", "Content-Length": str(len(body)),
                       "Connection": "close"}
            for name in ("Authorization", "Accept"):
                if name in self.headers:
                    headers[name] = self.headers[name]
            conn.connect()
            upstream_socket = conn.sock
            if cancelled.is_set() or deadline_reached.is_set() or server.stopping.is_set():
                raise ConnectionAbortedError()
            # Durable dispatch intent precedes IO; it is not a billing receipt.
            server.ledger.dispatched(number)
            conn.request("POST", self.path, body=body, headers=headers)
            with conn.getresponse() as response:
                status = response.status
                server.ledger.headers(number, status)
                self.send_response(status)
                for name in ("Content-Type", "Retry-After"):
                    if response.getheader(name):
                        self.send_header(name, response.getheader(name))
                self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Connection", "close")
                self.end_headers()
                response_started = True
                while chunk := response.read1(65536):
                    self.wfile.write(b"%X\r\n%s\r\n" % (len(chunk), chunk))
                    self.wfile.flush()
                if cancelled.is_set() or deadline_reached.is_set():
                    raise ConnectionAbortedError()
                if response.length not in (None, 0):
                    raise http.client.IncompleteRead(b"")
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
                outcome = "completed" if 200 <= status < 300 else "failed"
        except (OSError, http.client.HTTPException):
            if cancelled.is_set():
                outcome = "cancelled"
            if not response_started:
                try:
                    self.reject(504 if deadline_reached.is_set() else 502)
                except OSError:
                    pass
        finally:
            done.set()
            interrupt(upstream_socket)
            conn.close()
            watcher.join()
            server.ledger.finish(number, outcome, status, started)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen", type=int, required=True)
    parser.add_argument("--upstream-port", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    parser.add_argument("--request-seconds", type=float, default=120)
    parser.add_argument("--lifetime-seconds", type=float, default=620)
    args = parser.parse_args()
    if (not 1 <= args.max_requests <= 100 or not 0 <= args.listen <= 65535
            or not 1 <= args.upstream_port <= 65535
            or 8780 <= args.listen <= 8830 or 8780 <= args.upstream_port <= 8830
            or any(not math.isfinite(v) or v <= 0 for v in (args.request_seconds, args.lifetime_seconds))):
        parser.error("invalid budget or forbidden port")
    ledger = Ledger(args.output, args.max_requests)
    server = None
    try:
        server = ReviewServer(args.listen, args.upstream_port, ledger,
                              args.request_seconds, args.lifetime_seconds)

        def stop(*_args):
            if not server.stopping.is_set():
                server.stopping.set()
                threading.Thread(target=server.shutdown).start()

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        timer = threading.Timer(args.lifetime_seconds, stop)
        timer.start()
        ledger.record("listening", port=server.server_address[1])
        print(json.dumps({"port": server.server_address[1]}), flush=True)
        try:
            server.serve_forever(poll_interval=0.05)
        finally:
            timer.cancel()
            server.stopping.set()
            server.server_close()
    finally:
        if server is not None:
            server.stopping.set()
        ledger.close()


if __name__ == "__main__":
    main()
