"""Cancellable urllib HTTP with one absolute monotonic deadline (POSIX).

Only this stdlib-only file is executed in the worker, never the caller's main
module. Prompts/credentials travel over anonymous pipes, not argv or files.
The parent owns callbacks and accounting; killing/reaping the worker closes
DNS/connect/TLS/proxy/body I/O without leaving a network thread behind.
"""

from __future__ import annotations

import base64
from email.message import Message
import http.client
import json
import math
import os
from pathlib import Path
import select
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


class HTTPDeadlineExceeded(RuntimeError):
    pass


class HTTPStreamCancelled(RuntimeError):
    pass


# A response frame contains at most one 64 KiB byte chunk or HTTP headers.
_CHUNK_BYTES = 64 * 1024
_MAX_FRAME_BYTES = 256 * 1024


def _headers(items) -> Message:
    result = Message()
    for key, value in items:
        result[key] = value
    return result


def _raise_remote_error(frame: dict) -> None:
    kind = frame["type"]
    if kind == "http_error":
        raise urllib.error.HTTPError("", frame["status"], "HTTP error", _headers(frame["headers"]), None)
    name = frame.get("name")
    if name == "TimeoutError":
        raise TimeoutError("HTTP network timeout")
    if name == "URLError":
        inner = frame.get("inner")
        reason = TimeoutError() if inner == "TimeoutError" else OSError("HTTP network failure")
        raise urllib.error.URLError(reason)
    classes = {
        "ConnectionError": ConnectionError,
        "ConnectionResetError": ConnectionResetError,
        "ConnectionRefusedError": ConnectionRefusedError,
        "ConnectionAbortedError": ConnectionAbortedError,
        "RemoteDisconnected": http.client.RemoteDisconnected,
        "IncompleteRead": http.client.IncompleteRead,
        "OSError": OSError,
    }
    cls = classes.get(name, RuntimeError)
    if cls is http.client.IncompleteRead:
        raise cls(b"")
    raise cls("HTTP worker network failure")


class HTTPResponse:
    def __init__(self, process: subprocess.Popen, expires_at: float, is_cancelled=None, observer=None):
        self.process = process
        self.expires_at = expires_at
        self.is_cancelled = is_cancelled
        self.observer = observer
        self.headers = Message()
        self.status = 0
        self._buffer = bytearray()
        self._closed = False
        self._eof = False

    def _check(self) -> float:
        if self.is_cancelled is not None and self.is_cancelled():
            raise HTTPStreamCancelled()
        remaining = self.expires_at - time.monotonic()
        if remaining <= 0:
            raise HTTPDeadlineExceeded()
        return remaining

    def _wait(self, fd: int, *, writing: bool = False) -> None:
        while True:
            remaining = self._check()
            readable, writable, _ = select.select(
                [] if writing else [fd], [fd] if writing else [], [],
                min(remaining, 0.05) if self.is_cancelled is not None else remaining,
            )
            self._check()
            if readable or writable:
                return

    def send_request(self, payload: bytes) -> None:
        fd = self.process.stdin.fileno()
        os.set_blocking(fd, False)
        view = memoryview(payload)
        while view:
            self._wait(fd, writing=True)
            try:
                count = os.write(fd, view[:_CHUNK_BYTES])
            except BlockingIOError:
                continue
            view = view[count:]
        self.process.stdin.close()
        self._check()

    def _receive(self) -> dict:
        fd = self.process.stdout.fileno()
        while True:
            self._check()
            newline = self._buffer.find(b"\n")
            if newline >= 0:
                raw = bytes(self._buffer[:newline])
                del self._buffer[:newline + 1]
                frame = json.loads(raw)
                self._check()
                if frame["type"] in {"http_error", "error"}:
                    _raise_remote_error(frame)
                return frame
            if len(self._buffer) > _MAX_FRAME_BYTES:
                raise OSError("HTTP worker frame too large")
            self._wait(fd)
            try:
                block = os.read(fd, _CHUNK_BYTES)
            except BlockingIOError:
                continue
            if not block:
                self._check()
                raise OSError("HTTP worker exited before response completion")
            self._buffer.extend(block)

    def open(self) -> None:
        frame = self._receive()
        if frame["type"] != "headers":
            raise OSError("HTTP worker did not return headers")
        self.headers = _headers(frame["headers"])
        self.status = frame["status"]
        if self.observer is not None:
            self.observer("headers", status=self.status)

    def _chunks(self):
        while not self._eof:
            frame = self._receive()
            if frame["type"] == "eof":
                self._eof = True
                if self.observer is not None:
                    self.observer("eof")
            elif frame["type"] == "data":
                data = base64.b64decode(frame["data"], validate=True)
                self._check()
                yield data
            else:
                raise OSError("Unexpected HTTP worker frame")
        self._check()

    def read(self) -> bytes:
        result = b"".join(self._chunks())
        self._check()
        return result

    def __iter__(self):
        pending = bytearray()
        for block in self._chunks():
            pending.extend(block)
            while (newline := pending.find(b"\n")) >= 0:
                line = bytes(pending[:newline + 1])
                del pending[:newline + 1]
                self._check()
                yield line
        if pending:
            self._check()
            yield bytes(pending)

    def __enter__(self):
        self._check()
        return self

    def __exit__(self, *_exc):
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close_started = time.monotonic()
        try:
            # No grace period for a socket owner: SIGKILL cannot be ignored and
            # wait() reaps it before the call ledger can be finalized.
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait()
        finally:
            if self.observer is not None:
                self.observer("closed", returncode=self.process.returncode,
                              reap_ms=round((time.monotonic() - close_started) * 1000))
            for stream in (self.process.stdin, self.process.stdout):
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass


def urlopen(request, timeout: float, *, deadline=None, is_cancelled=None, loopback_only: bool = False, observer=None):
    parsed = urllib.parse.urlsplit(request.full_url)
    if loopback_only and (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port is None
    ):
        raise RuntimeError("Non-loopback HTTP request rejected")
    expires_at = time.monotonic() + float(timeout)
    if deadline is not None:
        expires_at = min(expires_at, deadline.expires_at)
    if not math.isfinite(expires_at) or expires_at <= time.monotonic():
        raise HTTPDeadlineExceeded()
    if is_cancelled is not None and is_cancelled():
        raise HTTPStreamCancelled()
    payload = json.dumps({
        "url": request.full_url,
        "body": base64.b64encode(request.data or b"").decode("ascii"),
        "headers": request.header_items(),
        "method": request.get_method(),
        "expires_at": expires_at,
        "loopback_only": loopback_only,
    }).encode("utf-8")
    if time.monotonic() >= expires_at:
        raise HTTPDeadlineExceeded()
    if observer is not None:
        observer("spawn_started")
    process = subprocess.Popen(
        [sys.executable, "-I", "-u", str(Path(__file__).resolve())],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    response = HTTPResponse(process, expires_at, is_cancelled, observer)
    try:
        if observer is not None:
            observer("spawned")
        os.set_blocking(process.stdout.fileno(), False)
        response.send_request(payload)
        if observer is not None:
            observer("request_sent")
        response.open()
        return response
    except BaseException:
        response.close()
        raise


def _worker() -> None:
    def emit(frame):
        sys.stdout.buffer.write(json.dumps(frame).encode("utf-8") + b"\n")
        sys.stdout.buffer.flush()

    config = json.load(sys.stdin)
    remaining = config["expires_at"] - time.monotonic()
    if remaining <= 0:
        return
    # This also closes I/O if a parent-side consumer is slow between reads.
    timer = threading.Timer(remaining, os._exit, args=(124,))
    timer.daemon = True
    timer.start()
    try:
        request = urllib.request.Request(
            config["url"], data=base64.b64decode(config["body"]),
            headers=dict(config["headers"]), method=config["method"],
        )
        opener = urllib.request.build_opener()
        if config["loopback_only"]:
            expected = urllib.parse.urlsplit(config["url"])

            class LoopbackOnly(urllib.request.BaseHandler):
                handler_order = 100

                def http_request(self, req):
                    parsed = urllib.parse.urlsplit(req.full_url)
                    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
                            or parsed.port != expected.port):
                        raise OSError("Non-loopback HTTP request rejected")
                    return req

                https_request = http_request

            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), LoopbackOnly())
        with opener.open(request, timeout=max(0.001, config["expires_at"] - time.monotonic())) as response:
            emit({"type": "headers", "headers": list(response.headers.items()), "status": response.status})
            while block := response.read1(_CHUNK_BYTES):
                emit({"type": "data", "data": base64.b64encode(block).decode("ascii")})
            emit({"type": "eof"})
    except urllib.error.HTTPError as exc:
        # Do not wait for an error body: status/headers own the retry decision.
        emit({"type": "http_error", "status": exc.code, "headers": list(exc.headers.items())})
        exc.close()
    except Exception as exc:
        emit({"type": "error", "name": type(exc).__name__,
              "inner": type(exc.reason).__name__ if isinstance(exc, urllib.error.URLError) else None})
    finally:
        timer.cancel()


if __name__ == "__main__":
    _worker()
