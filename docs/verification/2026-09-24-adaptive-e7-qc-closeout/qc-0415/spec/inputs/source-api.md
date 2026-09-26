# Raw candidate source excerpts, not host findings


## scripts/review_probes/prepare_adaptive_l6_runner.py:21 validate_deadline_admission
```python
def validate_deadline_admission(receipt: dict, revision: str) -> None:
    """Recompute strict coverage and timing before admitting any live sidecar."""
    from scripts.review_probes import diagnose_llm_timeout as probe

    current = probe.source_identity()
    if (receipt.get("schema_version") != 3 or current["revision"] != revision
            or current["working_tree_status"]
            or receipt.get("source_before") != current
            or receipt.get("source_after") != current):
        raise ValueError("strict receipt is not bound to this clean candidate")
    cases = receipt.get("cases")
    expected = set(probe.SCENARIOS + probe.JUDGE_SCENARIOS)
    if (not isinstance(cases, list) or len(cases) != len(expected)
            or any(not isinstance(case, dict) or not isinstance(case.get("scenario"), str) for case in cases)
            or {case.get("scenario") for case in cases} != expected):
        raise ValueError("strict receipt must contain every scenario exactly once")
    tolerance = receipt.get("scheduling_tolerance_seconds")
    if type(tolerance) not in (float, int) or not math.isfinite(tolerance) or not 0 <= tolerance <= 0.2:
        raise ValueError("strict scheduling tolerance exceeds admission policy")
    for case in cases:
        name = case["scenario"]
        budget = (0.0 if name in {"zero_deadline", "judge_root_expired"}
                  else 1.2 if name.startswith("synthesis_stream") else 0.8)
        elapsed = case.get("wall_elapsed_seconds")
        if (type(case.get("timeout_input_seconds")) not in (float, int)
                or case["timeout_input_seconds"] != budget
                or type(elapsed) not in (float, int) or not math.isfinite(elapsed) or elapsed < 0):
            raise ValueError("strict scenario budget or measurement is invalid")
    if (receipt.get("deadline_violations") != [] or receipt.get("coverage_gaps") != []
            or probe.violations(cases, tolerance) or probe.coverage_gaps(cases)):
        raise ValueError("strict receipt has deadline violations or coverage gaps")
```


## scripts/review_probes/probe_stalled_cancellation.py:34 run_case
```python
def run_case(llm, endpoint, name: str) -> dict:
    with endpoint("body_stall", 0.8) as (provider, requests, attempts):
        started = time.monotonic()
        cancelled = threading.Event()
        timer = None
        headers_at = None
        cancelled_at = None
        opener = llm._open_deadline_http_response

        def cancel():
            nonlocal cancelled_at
            cancelled_at = time.monotonic()
            cancelled.set()

        @contextmanager
        def arm_after_headers(*args, **kwargs):
            nonlocal timer, headers_at
            with opener(*args, **kwargs) as response:
                # Entering the lazy context, not constructing it, observes headers.
                headers_at = time.monotonic()
                timer = threading.Timer(0.3, cancel)
                timer.start()
                yield response

        error = None
        try:
            with (
                mock.patch.object(llm, "_open_deadline_http_response", arm_after_headers),
                llm.call_ledger_scope(max_calls=1, reuse_existing=False),
            ):
                deadline = llm.Deadline.from_timeout(10)
                messages = [{"role": "user", "content": "offline cancellation fixture"}]
                if name == "wrapper":
                    import urllib.request
                    request = urllib.request.Request(provider.base_url + "/chat/completions",
                                                     data=b"{}", method="POST")
                    with llm._open_deadline_http_response(request, 10, deadline=deadline,
                                                          is_cancelled=cancelled.is_set) as response:
                        response.read()
                elif name == "tools_stream":
                    llm._post_chat_message_stream(provider, messages, 10, 0, None, None,
                                                  None, lambda _: None, cancelled.is_set,
                                                  deadline=deadline)
                elif name == "synthesis_stream":
                    llm._post_chat_stream_raw(provider, messages, 10, 0, lambda _: None,
                                             None, cancelled.is_set, deadline, 128, 1000)
                else:
                    raise ValueError(name)
        except Exception as exc:
            error = type(exc).__name__
        finally:
            stopped_at = time.monotonic()
            elapsed = stopped_at - started
            if timer is not None:
                timer.cancel()
                timer.join()
        read_elapsed = stopped_at - headers_at if headers_at is not None else None
        cancel_latency = stopped_at - cancelled_at if cancelled_at is not None else None
        return {"path": name, "exception": error, "elapsed_seconds": elapsed,
                "headers_observed": headers_at is not None,
                "read_elapsed_seconds": read_elapsed, "cancel_to_stop_seconds": cancel_latency,
                "requests": len(requests), "attempts": len(attempts),
                "passed": error == "LLMStreamCancelled"
                and read_elapsed is not None and read_elapsed < 1.0
                and cancel_latency is not None and 0 <= cancel_latency < 0.7
                and len(requests) == len(attempts) == 1}
```


## intelligence/services/llm_http_transport.py
```python
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

```


## intelligence/services/llm_refine.py:120 LLMProvider
```python
class LLMProvider:
    name: str
    api_key: str = field(repr=False)
    base_url: str
    model: str
    transport: str = "http"
    response_schema: dict | None = None
```


## intelligence/services/llm_refine.py:184 Deadline
```python
class Deadline:
    expires_at: float

    @classmethod
    def from_timeout(cls, timeout: float) -> "Deadline":
        return cls(time.monotonic() + max(0.0, float(timeout)))

    def remaining(self) -> float:
        return max(0.0, self.expires_at - time.monotonic())

    def require_remaining(self, minimum: float = 0.0) -> float:
        remaining = self.remaining()
        if remaining < minimum:
            raise LLMDeadlineExceeded()
        return remaining

    def call_timeout(self, timeout: float, *, minimum: float = 1.0) -> float:
        """本次调用真正的超时 = min(调用方给的时间片, 共享 deadline 剩余)。

        修一个静默失效：``timeout`` 参数此前只在 ``deadline is None`` 时被用来
        构造 Deadline（``deadline or Deadline.from_timeout(timeout)``）。一旦调用
        方显式传 deadline —— grounded 三段链一直这么传 —— 时间片就只是个装饰，
        每一段都能吃掉整条 deadline。

        实测代价（2026-08-03 单题）：brief 分到 22s 片、实际跑了 69.7s，composer
        进场只剩 20.2s，必然超时降级。分片算得很认真，消费端根本没读——预算字段
        必须在**强制点**被读取，只是「传下去了」不等于「被执行了」。
        """

        remaining = self.require_remaining(minimum)
        limit = max(0.0, float(timeout or 0.0))
        return min(remaining, limit) if limit > 0 else remaining
```


## intelligence/services/llm_refine.py:219 _open_deadline_http_response
```python
def _open_deadline_http_response(request, timeout: float, *, deadline: Deadline, is_cancelled=None):
    opener = _HTTP_TRANSPORT_OVERRIDE.get() or llm_http_transport.urlopen
    try:
        with opener(
            request, timeout, deadline=deadline, is_cancelled=is_cancelled,
        ) as response:
            yield response
    except llm_http_transport.HTTPDeadlineExceeded as exc:
        raise LLMDeadlineExceeded() from exc
    except llm_http_transport.HTTPStreamCancelled as exc:
        raise LLMStreamCancelled() from exc
```


## intelligence/services/llm_refine.py:830 call_ledger_scope
```python
def call_ledger_scope(
    max_calls: int | None = None,
    *,
    reuse_existing: bool = True,
) -> Iterator[LLMCallLedger]:
    """开启 turn 级 LLM 调用台账；已有活动台账时复用（不重置嵌套作用域）。

    ``max_calls`` 只在新建台账时生效；嵌套复用时以外层限额为准。"""
    existing = _CALL_LEDGER.get()
    if existing is not None and reuse_existing:
        yield existing
        return
    ledger = LLMCallLedger(max_calls=max_calls)
    token = _CALL_LEDGER.set(ledger)
    try:
        yield ledger
    finally:
        _CALL_LEDGER.reset(token)
```


## intelligence/services/llm_refine.py:1139 _post_chat
```python
def _post_chat(
    provider: LLMProvider,
    messages: list[dict],
    timeout: float,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    *,
    deadline: Deadline | None = None,
) -> str:
    _reserve_llm_call()
    url = provider.base_url.rstrip("/") + "/chat/completions"
    payload = _chat_payload(provider, messages, temperature)
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    _apply_thinking_controls(
        payload, disable_thinking=os.environ.get("LLM_THINKING") == "disabled"
    )
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers=_llm_request_headers(provider),
        method="POST",
    )
    started = time.monotonic()
    attempt = _new_call_attempt(provider, messages)
    call_deadline = deadline or Deadline.from_timeout(timeout)
    try:
        with _open_deadline_http_response(req, timeout=timeout, deadline=call_deadline) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            call_deadline.require_remaining(0.001)
            attempt.observe_response(body, resp)
        content = body["choices"][0]["message"]["content"]
        attempt.observe_result(content)
    except Exception as exc:
        attempt.observe_response(response=exc)
        _record_llm_call("chat", provider, "failed", started, _failure_reason(exc), attempt=attempt)
        raise
    # 响应顶层 usage 此前被丢弃——API 判官走的就是这条路，判官侧 token 因此一直
    # 没有账（BP §7.3 只量到写手侧）。缺 usage 的响应记 None，不抛。
    input_tokens, output_tokens = token_usage_counts(
        body.get("usage") if isinstance(body, Mapping) else None
    )
    _record_llm_call(
        "chat",
        provider,
        "success",
        started,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        usage_source=USAGE_SOURCE_API,
        attempt=attempt,
    )
    return content
```


## intelligence/services/llm_refine.py:1195 _post_chat_synthesis
```python
def _post_chat_synthesis(
    provider: LLMProvider,
    messages: list[dict],
    timeout: float,
    temperature: float,
    max_tokens: int,
    max_chars: int,
    *,
    deadline: Deadline | None = None,
) -> tuple[str, str | None]:
    _reserve_llm_call()
    url = provider.base_url.rstrip("/") + "/chat/completions"
    payload = _chat_payload(provider, messages, temperature, max_tokens=max_tokens)
    _apply_thinking_controls(payload, disable_thinking=synthesis_thinking_disabled())
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_llm_request_headers(provider),
        method="POST",
    )
    started = time.monotonic()
    attempt = _new_call_attempt(provider, messages)
    call_deadline = deadline or Deadline.from_timeout(timeout)
    try:
        with _open_deadline_http_response(request, timeout=timeout, deadline=call_deadline) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            call_deadline.require_remaining(0.001)
            attempt.observe_response(body, resp)
        choice = body["choices"][0]
        content = choice["message"]["content"]
        attempt.observe_result(content)
    except Exception as exc:
        attempt.observe_response(response=exc)
        _record_llm_call("synthesis", provider, "failed", started, _failure_reason(exc), attempt=attempt)
        raise
    if len(content) > max_chars:
        _record_llm_call("synthesis", provider, "failed", started, "output_too_long", attempt=attempt)
        raise LLMOutputTooLong()
    _record_llm_call("synthesis", provider, "success", started, attempt=attempt)
    return content, _stable_finish_reason(choice.get("finish_reason"))
```


## intelligence/services/llm_refine.py:1237 complete
```python
def complete(
    messages: list[dict],
    model_override: str | None = None,
    timeout: float = DEFAULT_LLM_TIMEOUT,
    temperature: float = 0.2,
    *,
    min_viable_seconds: float | None = None,
    max_tokens: int | None = None,
) -> tuple[str | None, "LLMProvider | None", str]:
    """Generic OpenAI-compatible chat call shared across services.

    Returns ``(content, provider, reason)``. On any failure (no key, HTTP error,
    network error) ``content`` is ``None`` and ``reason`` explains why so callers
    can degrade gracefully — same contract as :func:`refine_or_reason`.
    """
    context = _CALL_PROVENANCE.get()
    if context is not None:
        context.selected_attempt_id = None
        context.identity_state = IDENTITY_NOT_CALLED
    rejection = _budget_rejection()
    if rejection is not None:
        return None, None, rejection
    providers = detect_providers(model_override)
    if not providers:
        return None, None, (
            "未配置 LLM key。设置 DEEPSEEK_API_KEY / MOONSHOT_API_KEY / "
            "DASHSCOPE_API_KEY / ZHIPU_API_KEY / OPENAI_API_KEY 或通用 "
            "LLM_API_KEY(+LLM_BASE_URL,+LLM_MODEL) 即可启用"
        )
    insufficient = _insufficient_budget_reason(timeout, min_viable_seconds)
    if insufficient is not None:
        return None, None, insufficient
    deadline = Deadline.from_timeout(timeout)
    failures: list[tuple[LLMProvider, str]] = []
    from intelligence.services.grok_cli_judge import is_cli_judge_provider

    for provider in providers:
        try:
            remaining = deadline.require_remaining(0.001)
            if is_cli_judge_provider(provider):
                content = _complete_cli_judge(provider, messages, remaining)
            else:
                if max_tokens is None:
                    content = _post_chat(
                        provider,
                        messages,
                        remaining,
                        temperature,
                        deadline=deadline,
                    )
                else:
                    content = _post_chat(
                        provider,
                        messages,
                        remaining,
                        temperature,
                        max_tokens=max_tokens,
                        deadline=deadline,
                    )
        except LLMCallBudgetExceeded as exc:
            return None, None, str(exc)
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            failures.append((provider, f"LLM 调用 HTTP {exc.code}"))
        except Exception as exc:  # pragma: no cover - network
            failures.append((provider, f"LLM 调用失败（{type(exc).__name__}）"))
        else:
            if deadline.remaining() <= 0:
                return None, provider, "LLM 调用失败（LLMDeadlineExceeded）"
            return content, provider, ""
        if deadline.remaining() <= 0:
            break
    provider, reason = _provider_failure_reason(failures)
    return None, provider, reason
```


## intelligence/services/llm_refine.py:1366 _post_chat_message_stream
```python
def _post_chat_message_stream(
    provider: LLMProvider,
    messages: list[dict],
    timeout: float,
    temperature: float,
    tools: list[dict] | None,
    tool_choice: str | dict | None,
    disable_thinking: bool | None,
    on_content_delta: Callable[[str], None],
    is_cancelled: Callable[[], bool] | None = None,
    *,
    deadline: Deadline | None = None,
) -> dict:
    """Stream one tools-enabled turn, returning the same message dict shape.

    Everything downstream (``ModelTurn`` parsing, the agent loop, the episode
    ledger) consumes the non-streaming shape, so this returns exactly that and
    keeps streaming an implementation detail of the transport.  The only extra
    is ``_streamed_chars``: the caller needs to know whether anything already
    crossed to the user before deciding it may retry.
    """

    _reserve_llm_call()
    url = provider.base_url.rstrip("/") + "/chat/completions"
    payload = _chat_payload(
        provider, messages, temperature, stream=True,
        # 没有它就拿不到 usage：非流式响应里 usage 是顶层字段，流式下只在
        # 最后一个 chunk 出现，且要显式开。丢了它 episode 的 token 账会归零。
        stream_options={"include_usage": True},
    )
    _apply_thinking_controls(
        payload,
        disable_thinking=(
            disable_thinking is True
            or (disable_thinking is None and os.environ.get("LLM_THINKING") == "disabled")
        ),
    )
    if tools:
        payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_llm_request_headers(provider, Accept="text/event-stream"),
        method="POST",
    )
    started = time.monotonic()
    attempt = _new_call_attempt(provider, messages)
    content_chunks: list[str] = []
    streamed_chars = 0
    calls = _ToolCallAssembler()
    finish_reason: str | None = None
    usage: dict | None = None
    served_model = ""
    saw_any_chunk = False
    call_deadline = deadline or Deadline.from_timeout(timeout)
    try:
        with _open_deadline_http_response(
            request, timeout=timeout, deadline=call_deadline, is_cancelled=is_cancelled,
        ) as response:
            attempt.observe_response(response=response)
            for raw_line in response:
                if is_cancelled is not None and is_cancelled():
                    raise LLMStreamCancelled()
                line = raw_line.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                saw_any_chunk = True
                attempt.observe_response(event)
                if not served_model and isinstance(event, dict):
                    served_model = _served_model_from_body(event)
                event_usage = event.get("usage")
                if isinstance(event_usage, dict):
                    usage = dict(event_usage)
                choices = event.get("choices")
                if not isinstance(choices, list) or not choices:
                    continue
                choice = choices[0]
                if not isinstance(choice, dict):
                    continue
                finish_reason = (
                    _stable_finish_reason(choice.get("finish_reason")) or finish_reason
                )
                delta = choice.get("delta")
                if not isinstance(delta, dict):
                    continue
                calls.add(delta.get("tool_calls"))
                piece = delta.get("content")
                if isinstance(piece, str) and piece:
                    content_chunks.append(piece)
                    # 回调放在**收集之后**：即便下游抛异常，已收到的正文也已
                    # 记账，重试资格的判断不会因为回调炸了而误判成"还没吐字"。
                    streamed_chars += len(piece)
                    on_content_delta(piece)
            if call_deadline.remaining() <= 0:
                raise LLMDeadlineExceeded()
    except Exception as exc:
        attempt.observe_result({"content": "".join(content_chunks), "tool_calls": calls.assembled()})
        _record_llm_call(
            "chat_tools_stream", provider, "failed", started, _failure_reason(exc), attempt=attempt,
        )
        if streamed_chars:
            raise LLMStreamAlreadyEmitted(str(exc)) from exc
        raise
    if not saw_any_chunk:
        _record_llm_call(
            "chat_tools_stream", provider, "failed", started, "streaming_unsupported", attempt=attempt,
        )
        raise LLMStreamingUnsupported()
    message: dict = {
        "role": "assistant",
        "content": "".join(content_chunks),
        "_streamed_chars": streamed_chars,
    }
    assembled = calls.assembled()
    if assembled:
        message["tool_calls"] = assembled
    # EOF / [DONE] closes transport, not model generation. Keep the received
    # content and usage, but never pass a known-incomplete stream as legacy.
    message["_finish_reason"] = finish_reason or "missing_finish_reason"
    if usage is not None:
        message["_usage"] = usage
    message["_served_model"] = served_model
    attempt.observe_result(message)
    _record_llm_call(
        "chat_tools_stream", provider, "success" if finish_reason else "failed", started,
        "" if finish_reason else "incomplete_model_response:missing_finish_reason",
        attempt=attempt,
    )
    return message
```


## intelligence/services/llm_refine.py:1506 _post_chat_message
```python
def _post_chat_message(
    provider: LLMProvider,
    messages: list[dict],
    timeout: float,
    temperature: float = 0.2,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
    disable_thinking: bool | None = None,
    *,
    deadline: Deadline | None = None,
) -> dict:
    """Like :func:`_post_chat` but returns the full assistant *message* dict.

    The message may contain ``tool_calls`` (OpenAI-compatible function calling)
    in addition to / instead of ``content`` — needed to drive an agent loop."""
    _reserve_llm_call()
    url = provider.base_url.rstrip("/") + "/chat/completions"
    payload = _chat_payload(provider, messages, temperature)
    _apply_thinking_controls(
        payload,
        disable_thinking=(
            disable_thinking is True
            or (disable_thinking is None and os.environ.get("LLM_THINKING") == "disabled")
        ),
    )
    if tools:
        payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers=_llm_request_headers(provider),
        method="POST",
    )
    started = time.monotonic()
    attempt = _new_call_attempt(provider, messages)
    call_deadline = deadline or Deadline.from_timeout(timeout)
    try:
        with _open_deadline_http_response(req, timeout=timeout, deadline=call_deadline) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            call_deadline.require_remaining(0.001)
            attempt.observe_response(body, resp)
        choice = body["choices"][0]
        message = dict(choice["message"])
        finish_reason = _stable_finish_reason(choice.get("finish_reason"))
        if finish_reason is not None:
            message["_finish_reason"] = finish_reason
        attempt.observe_result(message)
    except Exception as exc:
        attempt.observe_response(response=exc)
        _record_llm_call(
            "chat_tools", provider, "failed", started, _failure_reason(exc), attempt=attempt,
        )
        raise
    _record_llm_call("chat_tools", provider, "success", started, attempt=attempt)
    usage = body.get("usage")
    if isinstance(usage, dict):
        # Usage is adapter metadata only. Preserve counts without returning the
        # request prompt, provider body, or hidden reasoning payload.
        message["_usage"] = dict(usage)
    message["_served_model"] = _served_model_from_body(body)
    return message
```


## intelligence/services/llm_refine.py:2236 _post_chat_stream
```python
def _post_chat_stream(
    provider: LLMProvider,
    messages: list[dict],
    timeout: int,
    temperature: float,
    on_delta: Callable[[str], None],
    on_connected: Callable[[], None] | None,
    is_cancelled: Callable[[], bool] | None,
    deadline: Deadline,
    max_tokens: int,
    max_chars: int,
) -> tuple[str, str | None]:
    _reserve_llm_call()
    started = time.monotonic()
    attempt = _new_call_attempt(provider, messages)
    try:
        result = _post_chat_stream_raw(
            provider,
            messages,
            timeout,
            temperature,
            on_delta,
            on_connected,
            is_cancelled,
            deadline,
            max_tokens,
            max_chars,
            attempt=attempt,
        )
        attempt.observe_result(result[0])
    except Exception as exc:
        attempt.observe_response(response=exc)
        _record_llm_call(
            "synthesis_stream", provider, "failed", started, _failure_reason(exc), attempt=attempt,
        )
        raise
    _record_llm_call("synthesis_stream", provider, "success", started, attempt=attempt)
    return result
```


## intelligence/services/llm_refine.py:2276 _post_chat_stream_raw
```python
def _post_chat_stream_raw(
    provider: LLMProvider,
    messages: list[dict],
    timeout: int,
    temperature: float,
    on_delta: Callable[[str], None],
    on_connected: Callable[[], None] | None,
    is_cancelled: Callable[[], bool] | None,
    deadline: Deadline,
    max_tokens: int,
    max_chars: int,
    *,
    attempt: _LLMCallAttempt | None = None,
) -> tuple[str, str | None]:
    url = provider.base_url.rstrip("/") + "/chat/completions"
    payload = _chat_payload(
        provider, messages, temperature, stream=True, max_tokens=max_tokens,
    )
    _apply_thinking_controls(payload, disable_thinking=synthesis_thinking_disabled())
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_llm_request_headers(provider, Accept="text/event-stream"),
        method="POST",
    )
    chunks: list[str] = []
    output_chars = 0
    finish_reason: str | None = None
    with _open_deadline_http_response(
        request, timeout=timeout, deadline=deadline, is_cancelled=is_cancelled,
    ) as response:
        if attempt is not None:
            attempt.observe_response(response=response)
        if on_connected is not None:
            on_connected()
        try:
            for raw_line in response:
                if deadline.remaining() <= 0:
                    raise LLMDeadlineExceeded()
                if is_cancelled is not None and is_cancelled():
                    raise LLMStreamCancelled()
                line = raw_line.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    if finish_reason is None and chunks:
                        finish_reason = "stop"
                    break
                try:
                    event = json.loads(data)
                    if attempt is not None:
                        attempt.observe_response(event)
                    choice = event["choices"][0]
                    finish_reason = (
                        _stable_finish_reason(choice.get("finish_reason"))
                        or finish_reason
                    )
                    delta = choice["delta"].get("content")
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    continue
                if isinstance(delta, str) and delta:
                    output_chars += len(delta)
                    if output_chars > max_chars:
                        raise LLMOutputTooLong()
                    on_delta(delta)
                    chunks.append(delta)
        except (OSError, ValueError) as exc:
            if deadline.remaining() <= 0:
                raise LLMDeadlineExceeded() from exc
            raise
        finally:
            if attempt is not None:
                attempt.observe_result("".join(chunks))
    deadline.require_remaining(0.001)
    if not chunks:
        raise LLMStreamingUnsupported()
    return "".join(chunks), finish_reason
```


## intelligence/services/episode_semantic_verifier.py:159 semantic_judge_window_seconds
```python
def semantic_judge_window_seconds(policy: ResearchPolicy | None = None) -> float:
    """Total window shared by all judge attempts.

    Bookgap S3: the source of truth is ``derive_stage_caps`` (a fraction of
    synthesis reserve).  ``ASK_SEMANTIC_JUDGE_WINDOW`` can only lower it.
    One complete attempt is ``min(per_attempt_cap, window)`` — the 0.5
    pre-split was retired after the 08-20 grok tail (46.7s) could not fit
    in half of the 50s floor.
    """

    caps = derive_stage_caps(policy or policy_for_env())
    return apply_env_ceiling(caps.judge_window_seconds, "ASK_SEMANTIC_JUDGE_WINDOW")
```


## intelligence/services/episode_semantic_verifier.py:173 judge_attempt_seconds
```python
def judge_attempt_seconds(
    configured_attempt_timeout: float,
    policy: ResearchPolicy | None = None,
) -> float:
    """Per-attempt cap: the configured value, floored by the tier's own cap.

    档位地板只有 max 档有（``derive_stage_caps``）；其余档位返回配置值，
    与改动前逐字节一致。``policy`` 缺省走 ``policy_for_env()``——注意那读的是
    ``ASK_RESEARCH_TIER``，生产设的是 ``WORKBENCH_RESEARCH_TIER``，所以 episode
    路径必须把合同上的真实档位传进来，不能靠缺省。
    """

    configured = max(0.1, float(configured_attempt_timeout))
    floor = derive_stage_caps(policy or policy_for_env()).judge_attempt_seconds
    if floor is None:
        return configured
    return max(configured, float(floor))
```


## intelligence/services/episode_semantic_verifier.py:1188 _JudgeCall
```python
class _JudgeCall:
    report: answer_model.GroundingJudgeReport | None
    unavailable: bool
    correlated: bool
    issue: str = ""
    root_deadline_exhausted: bool = False
    transient_provider_failure: bool = False
    # Fail closed: only explicitly classified deadline/transient failures may
    # opt into deletion-only candidate release. Malformed provider output must
    # never inherit release eligibility from a dataclass default.
    monotonic_release_safe: bool = False
    timeout_asked: float | None = None
    timeout_configured: float | None = None
    remaining_seconds_at_entry: float | None = None
    exc_class: str | None = None
    http_status: int | None = None
    judge_attempt_index: int | None = None
    request: dict[str, object] | None = None
    material_review_calls: tuple[dict[str, object], ...] = ()
    last_dispatched_failure: dict[str, object] | None = None
```


## intelligence/services/episode_semantic_verifier.py:3097 _run_judge_once
```python
    def _run_judge_once(
        self,
        request: dict[str, object],
        deadline: ResearchDeadline,
    ) -> _JudgeCall:
        policy = self._active_policy
        attempt_cap = self._judge_attempt_cap()
        total_window = semantic_total_judge_window(
            deadline, configured_attempt_timeout=attempt_cap, policy=policy
        )
        attempt_timeouts = semantic_attempts_for_window(
            total_window,
            configured_attempt_timeout=attempt_cap,
            policy=policy,
        )
        if not attempt_timeouts:
            return self._clocked_judge_call(
                asked=0.0,
                remaining=_deadline_remaining_seconds(deadline),
                correlated=False,
                unavailable=True,
                issue=ROOT_DEADLINE_EXHAUSTED_ISSUE,
                root_deadline_exhausted=True,
                monotonic_release_safe=True,
            )

        # R-20260829-03 判官备链：主判官 + 显式配置的备胎（永不自动追加合成
        # 主链——「不静默退回相关自审」红线不变）。链退化为单主时行为与改动
        # 前逐字节一致。
        providers: tuple[object, ...] = ()
        try:
            providers = llm_refine.judge_provider_chain()
        except Exception:
            providers = ()
        provider = providers[0] if providers else None
        if provider is not None:
            leftover = _deadline_remaining_seconds(deadline)
            if leftover_window_blocks_complete_attempt(
                leftover, attempt_cap, policy
            ):
                return self._clocked_judge_call(
                    asked=0.0,
                    remaining=leftover,
                    correlated=False,
                    unavailable=True,
                    issue=LEFTOVER_WINDOW_ISSUE,
                    root_deadline_exhausted=True,
                    monotonic_release_safe=True,
                )
            messages = [
                {"role": "system", "content": _judge_system_prompt(request)},
                {
                    "role": "user",
                    "content": dumps_judge_request(request),
                },
            ]
            prior_failures_release_safe = True
            last_failure: _JudgeCall | None = None
            # 窗口余额账：报价是「一次完整尝试」，真正的封顶是这里。
            # 用 deadline 读数扣账而不是另起时钟——冻结时间的测试才不会两套钟打架。
            window_left = total_window
            previous_remaining: float | None = None
            for attempt, timeout_limit in enumerate(attempt_timeouts):
                remaining_at_entry = _deadline_remaining_seconds(deadline)
                if previous_remaining is not None and remaining_at_entry is not None:
                    window_left -= max(0.0, previous_remaining - remaining_at_entry)
                previous_remaining = remaining_at_entry
                timeout_limit = min(timeout_limit, max(0.0, window_left))
                if leftover_window_blocks_complete_attempt(
                    remaining_at_entry, attempt_cap, policy
                ):
                    return self._clocked_judge_call(
                        asked=0.0,
                        judge_attempt_index=attempt,
                        remaining=remaining_at_entry,
                        correlated=False,
                        unavailable=True,
                        issue=LEFTOVER_WINDOW_ISSUE,
                        last_dispatched_failure=last_failure,
                        root_deadline_exhausted=True,
                        monotonic_release_safe=True,
                    )
                attempt_timeout = deadline.synthesis_timeout(timeout_limit)
                if attempt_timeout <= 0.001:
                    failure_chain_release_safe = (
                        attempt == 0 or prior_failures_release_safe
                    )
                    # root_deadline_exhausted 保持 True：释放语义（预算到点 →
                    # 只删不改地放行早先完成的报告）对「窗被吃光」同样成立，
                    # 这里只把归因写对，不改放行行为。
                    return self._clocked_judge_call(
                        asked=attempt_timeout,
                        judge_attempt_index=attempt,
                        remaining=remaining_at_entry,
                        correlated=False,
                        unavailable=True,
                        issue=self._window_starved_issue(attempt, deadline),
                        last_dispatched_failure=last_failure,
                        root_deadline_exhausted=True,
                        monotonic_release_safe=failure_chain_release_safe,
                    )
                # 槽位轮转：attempt 0 走主判官，之后的槽走链上下一位（链短于
                # 槽数时停在最后一位）。哪位判官真正服务了本轮，由 LLM 调用
                # 台账逐 attempt 记 provider 名，不另加 schema。
                active_provider = providers[min(attempt, len(providers) - 1)]
                try:
                    # purpose=judge 只包住真正发请求的这一层（INDEX #23）：三处
                    # ``_judge_request`` 都汇到这里，修复轮的写手调用发生在本方法
                    # 之外，不会被误标。提示词 / 超时 / 判定逻辑一律不动。
                    with llm_refine.provider_override(active_provider):
                        with llm_refine.call_purpose("judge"):
                            content, _used, reason = llm_refine.complete(
                                messages,
                                timeout=attempt_timeout,
                                temperature=0.0,
                            )
                except Exception as exc:  # pragma: no cover - adapter boundary
                    issue, retryable, release_safe = _stable_semantic_judge_error(
                        type(exc).__name__
                    )
                    should_retry = _should_retry_semantic_judge(
                        attempt,
                        retryable=retryable,
                        release_safe=release_safe,
                        prior_failures_release_safe=(
                            prior_failures_release_safe
                        ),
                        deadline=deadline,
                    )
                    prior_failures_release_safe &= release_safe
                    if not should_retry and _next_slot_switches_judge(
                        attempt, len(providers), len(attempt_timeouts), deadline
                    ):
                        # 主判官放弃但链上还有没上场的备胎：下一槽换人再试。
                        # 释放安全账照常累计，不因换人清零（R-20260829-03）。
                        should_retry = True
                    last_failure = self._clocked_judge_call(
                        asked=attempt_timeout,
                        judge_attempt_index=attempt,
                        remaining=remaining_at_entry,
                        correlated=False,
                        unavailable=True,
                        issue=issue,
                        failure=exc,
                        transient_provider_failure=(
                            prior_failures_release_safe
                        ),
                        monotonic_release_safe=prior_failures_release_safe,
                    )
                    if should_retry:
                        continue
                    return last_failure
                report = self._parse_report(content, len(request["sentences"]), material_claims=request.get("material_claims"), material_outputs=request.get("material_outputs"))
                if report is not None:
                    return self._clocked_judge_call(
                        asked=attempt_timeout,
                        judge_attempt_index=attempt,
                        remaining=remaining_at_entry,
                        correlated=False,
                        unavailable=False,
                        report=report,
                        monotonic_release_safe=prior_failures_release_safe,
                    )
                failure = reason or "invalid semantic judge output"
                issue, retryable, release_safe = _stable_semantic_judge_error(failure)
                should_retry = _should_retry_semantic_judge(
                    attempt,
                    retryable=retryable,
                    release_safe=release_safe,
                    prior_failures_release_safe=prior_failures_release_safe,
                    deadline=deadline,
                )
                prior_failures_release_safe &= release_safe
                if not should_retry and _next_slot_switches_judge(
                    attempt, len(providers), len(attempt_timeouts), deadline
                ):
                    # 同上：链上还有备胎时不在主判官身上判死刑。
                    should_retry = True
                last_failure = self._clocked_judge_call(
                    asked=attempt_timeout,
                    judge_attempt_index=attempt,
                    remaining=remaining_at_entry,
                    correlated=False,
                    unavailable=True,
                    issue=issue,
                    failure=failure,
                    transient_provider_failure=prior_failures_release_safe,
                    monotonic_release_safe=prior_failures_release_safe,
                )
                if should_retry:
                    continue
                return last_failure
            return self._clocked_judge_call(
                asked=None,
                remaining=_deadline_remaining_seconds(deadline),
                correlated=False,
                unavailable=True,
                issue="semantic judge unavailable",
                last_dispatched_failure=last_failure,
            )

        # Explicit injection is the deterministic test/canary seam only when
        # no independent LLM_JUDGE provider is configured.  It is correlated
        # because it normally shares the primary composer model.
        if self._judge_fn is not None:
            remaining_at_entry = _deadline_remaining_seconds(deadline)
            asked = deadline.synthesis_timeout(attempt_timeouts[0])
            return self._invoke_injected(
                self._judge_fn,
                request,
                asked,
                True,
                timeout_configured=attempt_cap,
                remaining_seconds_at_entry=remaining_at_entry,
            )

        primary = self._primary_judge
        if primary is None and self._finalizer is not None:
            primary = getattr(self._finalizer, "_model", None)
        if primary is None:
            return self._clocked_judge_call(
                asked=None,
                remaining=_deadline_remaining_seconds(deadline),
                correlated=True,
                unavailable=True,
                issue="semantic judge unavailable",
            )
        if callable(primary) and not hasattr(primary, "complete"):
            remaining_at_entry = _deadline_remaining_seconds(deadline)
            asked = deadline.synthesis_timeout(attempt_timeouts[0])
            return self._invoke_injected(
                cast(JudgeFn, primary),
                request,
                asked,
                True,
                timeout_configured=attempt_cap,
                remaining_seconds_at_entry=remaining_at_entry,
            )
        messages = [
            {"role": "system", "content": _judge_system_prompt(request)},
            {
                "role": "user",
                "content": dumps_judge_request(request),
            },
        ]
        prior_failures_release_safe = True
        last_failure: _JudgeCall | None = None
        # 与 provider 分支同一本窗口余额账，见 _semantic_attempt_timeouts。
        window_left = total_window
        previous_remaining: float | None = None
        for attempt, timeout_limit in enumerate(attempt_timeouts):
            remaining_at_entry = _deadline_remaining_seconds(deadline)
            if previous_remaining is not None and remaining_at_entry is not None:
                window_left -= max(0.0, previous_remaining - remaining_at_entry)
            previous_remaining = remaining_at_entry
            attempt_timeout = deadline.synthesis_timeout(
                min(timeout_limit, max(0.0, window_left))
            )
            if attempt_timeout <= 0.001:
                failure_chain_release_safe = (
                    attempt == 0 or prior_failures_release_safe
                )
                return self._clocked_judge_call(
                    asked=attempt_timeout,
                        judge_attempt_index=attempt,
                    remaining=remaining_at_entry,
                    correlated=True,
                    unavailable=True,
                    issue=self._window_starved_issue(attempt, deadline),
                    last_dispatched_failure=last_failure,
                    root_deadline_exhausted=True,
                    monotonic_release_safe=failure_chain_release_safe,
                )
            try:
                # 相关判官（共用写手模型）同样是判官调用，一样标 judge。
                with llm_refine.call_purpose("judge"):
                    turn = primary.complete(
                        messages=messages,
                        tools=_judge_report_tools(request),
                        timeout=attempt_timeout,
                    )
            except Exception as exc:
                issue, retryable, release_safe = _stable_semantic_judge_error(
                    type(exc).__name__
                )
                should_retry = _should_retry_semantic_judge(
                    attempt,
                    retryable=retryable,
                    release_safe=release_safe,
                    prior_failures_release_safe=prior_failures_release_safe,
                    deadline=deadline,
                )
                prior_failures_release_safe &= release_safe
                last_failure = self._clocked_judge_call(
                    asked=attempt_timeout,
                    judge_attempt_index=attempt,
                    remaining=remaining_at_entry,
                    correlated=True,
                    unavailable=True,
                    issue=issue,
                    failure=exc,
                    transient_provider_failure=prior_failures_release_safe,
                    monotonic_release_safe=prior_failures_release_safe,
                )
                if should_retry:
                    continue
                return last_failure
            if not isinstance(turn, ModelTurn):
                return self._clocked_judge_call(
                    asked=attempt_timeout,
                        judge_attempt_index=attempt,
                    remaining=remaining_at_entry,
                    correlated=True,
                    unavailable=True,
                    issue="semantic judge invalid provider response",
                )
            if turn.error:
                issue, retryable, release_safe = _stable_semantic_judge_error(
                    turn.error
                )
                should_retry = _should_retry_semantic_judge(
                    attempt,
                    retryable=retryable,
                    release_safe=release_safe,
                    prior_failures_release_safe=prior_failures_release_safe,
                    deadline=deadline,
                )
                prior_failures_release_safe &= release_safe
                last_failure = self._clocked_judge_call(
                    asked=attempt_timeout,
                    judge_attempt_index=attempt,
                    remaining=remaining_at_entry,
                    correlated=True,
                    unavailable=True,
                    issue=issue,
                    failure=turn.error,
                    transient_provider_failure=prior_failures_release_safe,
                    monotonic_release_safe=prior_failures_release_safe,
                )
                if should_retry:
                    continue
                return last_failure
            if turn.tool_calls:
                report = self._parse_tool_report(
                    turn,
                    len(request["sentences"]),
                    material_claims=request.get("material_claims"), material_outputs=request.get("material_outputs"),
                )
                if report is None:
                    return self._clocked_judge_call(
                        asked=attempt_timeout,
                        judge_attempt_index=attempt,
                        remaining=remaining_at_entry,
                        correlated=True,
                        unavailable=True,
                        issue="semantic judge returned an invalid tool call",
                    )
                return self._clocked_judge_call(
                    asked=attempt_timeout,
                        judge_attempt_index=attempt,
                    remaining=remaining_at_entry,
                    correlated=True,
                    unavailable=False,
                    report=report,
                    monotonic_release_safe=prior_failures_release_safe,
                )
            report = self._parse_report(turn.content, len(request["sentences"]), material_claims=request.get("material_claims"), material_outputs=request.get("material_outputs"))
            if report is None:
                return self._clocked_judge_call(
                    asked=attempt_timeout,
                        judge_attempt_index=attempt,
                    remaining=remaining_at_entry,
                    correlated=True,
                    unavailable=True,
                    issue="invalid semantic judge output",
                )
            return self._clocked_judge_call(
                asked=attempt_timeout,
                        judge_attempt_index=attempt,
                remaining=remaining_at_entry,
                correlated=True,
                unavailable=False,
                report=report,
                monotonic_release_safe=prior_failures_release_safe,
            )
        return self._clocked_judge_call(
            asked=None,
            remaining=_deadline_remaining_seconds(deadline),
            correlated=True,
            unavailable=True,
            issue="semantic judge unavailable",
            last_dispatched_failure=last_failure,
        )
```
