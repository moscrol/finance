"""Measure real HTTP wall time against the granted budget, using loopback only.

Run from the repository root with the workbench interpreter:
    PYTHONPATH=. python scripts/review_probes/diagnose_llm_timeout.py --output <new.json>

No external model, credentials, production port, or old research request is used.
The HTTP implementation is real; only the endpoint and proxy/redirect handlers
are isolated. Successful diagnostics do NOT mean deadline enforcement passed:
``--assert-deadline`` exits 1 for overruns. Fixing the transport should turn that
same check green. Short synthetic budgets do not change production budgets.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from unittest import mock

from intelligence.services import episode_semantic_verifier as semantic
from intelligence.services import llm_refine
from intelligence.services.research_contract import ResearchDeadline, ResearchPolicy


ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = (
    "fast", "header_delay", "body_stall", "headers_then_body",
    "body_trickle", "tools_stream_trickle", "tools_stream_partial_line",
    "synthesis_stream_trickle", "synthesis_stream_partial_line", "zero_deadline",
)
JUDGE_SCENARIOS = ("judge_window_stalls", "judge_late_report", "judge_root_expired")
CONTENT = '{"passed":true,"rejected_sentence_indexes":[],"issues":[]}'
BODY = json.dumps({
    "id": "offline-response", "model": "offline-model",
    "choices": [{"message": {"content": CONTENT}, "finish_reason": "stop"}],
}).encode()
STREAM_LINE = b'data: {"choices":[{"delta":{"content":"x"}}]}\n\n'
STREAM_END = b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError("diagnostic redirects are forbidden")


@contextmanager
def local_endpoint(scenario: str, budget: float):
    """Finite responses and cooperative shutdown leave no handler threads behind."""
    stop = threading.Event()
    requests: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def wait(self, seconds):
            return stop.wait(seconds)

        def send(self, data):
            if stop.is_set():
                return False
            try:
                self.wfile.write(data)
                self.wfile.flush()
                return True
            except OSError:
                return False

        def do_POST(self):  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append({"stream_requested": body.get("stream", False)})
            if scenario == "header_delay" and self.wait(budget * 2):
                return
            if scenario == "headers_then_body" and self.wait(budget * 0.7):
                return
            streaming = "stream" in scenario
            payload = (STREAM_LINE * 9 + STREAM_END) if streaming else BODY
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream" if streaming else "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
            except OSError:
                return
            if scenario == "body_stall":
                self.send(payload[:1])
                if not self.wait(budget * 2):
                    self.send(payload[1:])
            elif scenario == "headers_then_body":
                if not self.wait(budget * 0.7):
                    self.send(payload)
            elif scenario == "body_trickle" or streaming:
                if scenario == "body_trickle":
                    width = math.ceil(len(payload) / 10)
                    pieces = [payload[i:i + width] for i in range(0, len(payload), width)]
                elif scenario.endswith("stream_partial_line"):
                    # No full SSE line arrives until after the deadline.
                    pieces = [STREAM_LINE[i:i + 5] for i in range(0, len(STREAM_LINE), 5)]
                    pieces.append(STREAM_LINE * 8 + STREAM_END)
                else:
                    pieces = [STREAM_LINE] * 9 + [STREAM_END]
                for index, piece in enumerate(pieces):
                    if index and self.wait(budget * 0.4):
                        return
                    if not self.send(piece):
                        return
            else:
                self.send(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = False
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/v1"
    provider = llm_refine.LLMProvider("offline-diagnostic", "fixture", base, "offline-model")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    attempts: list[dict] = []

    class ObservedResponse:
        def __init__(self, response, attempt, started):
            self.response, self.attempt, self.started = response, attempt, started
            self.headers = response.headers

        def __enter__(self):
            self.response.__enter__()
            return self

        def __exit__(self, *exc):
            return self.response.__exit__(*exc)

        def close(self):
            self.response.close()

        def read(self):
            self.attempt["phase"] = "body_read"
            data = self.response.read()
            self.attempt["phase"] = "body_complete"
            return data

        def __iter__(self):
            self.attempt["phase"] = "stream_read"
            for line in self.response:
                self.attempt.setdefault("first_line_ms", round((time.monotonic() - self.started) * 1000))
                yield line

    def open_local(request, timeout):
        parsed = urllib.parse.urlsplit(request.full_url)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port != server.server_port:
            raise RuntimeError("diagnostic non-loopback request rejected")
        attempt = {"timeout_seconds": timeout, "phase": "open_response"}
        attempts.append(attempt)
        started = time.monotonic()
        response = opener.open(request, timeout=timeout)
        attempt["headers_ms"] = round((time.monotonic() - started) * 1000)
        return ObservedResponse(response, attempt, started)

    try:
        with mock.patch.object(llm_refine.urllib.request, "urlopen", open_local):
            yield provider, requests, attempts
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        thread.join()


def run_case(scenario: str, budget: float = 0.8) -> dict:
    if scenario not in SCENARIOS:
        raise ValueError(scenario)
    with local_endpoint(scenario, budget) as (provider, requests, attempts):
        deltas: list[str] = []
        timeout = 0.0 if scenario == "zero_deadline" else budget
        with (
            llm_refine.call_ledger_scope(max_calls=1, reuse_existing=False) as ledger,
            llm_refine.provider_override(provider),
        ):
            started = time.monotonic()
            messages = [{"role": "user", "content": "synthetic offline deadline probe"}]
            if scenario.startswith("tools_stream"):
                result, _, reason = llm_refine.chat_with_tools(
                    messages, [], timeout=timeout, on_content_delta=deltas.append,
                )
            elif scenario.startswith("synthesis_stream"):
                # Its public API has a 1s minimum. Use a scaled case, without
                # changing that floor or any production policy.
                result, reason = llm_refine.synthesize_messages_stream(
                    messages, timeout=timeout, on_delta=deltas.append,
                )
            else:
                result, _, reason = llm_refine.complete(messages, timeout=timeout)
            elapsed = time.monotonic() - started
        summary = ledger.summary()
        return {
            "scenario": scenario,
            "timeout_input_seconds": timeout,
            "wall_elapsed_seconds": elapsed,
            "request_count": len(requests),
            "attempts": attempts,
            "requests": requests,
            "content_present": result is not None,
            "reason": reason,
            "emitted_chars": sum(map(len, deltas)),
            "reserved_count": summary["reserved_count"],
            "records": [{key: row.get(key) for key in ("caller", "elapsed_ms", "status", "reason")}
                        for row in summary["records"]],
        }


def run_judge_case(scenario: str, budget: float = 0.8) -> dict:
    """Isolate the real attempt allocator, not full answer/content verification."""
    if scenario not in JUDGE_SCENARIOS:
        raise ValueError(scenario)
    response_kind = "body_trickle" if scenario == "judge_late_report" else "header_delay"
    cap = budget / 2 if scenario == "judge_window_stalls" else budget
    with local_endpoint(response_kind, budget) as (provider, requests, attempts):
        verifier = semantic.SemanticEpisodeVerifier(judge_timeout=cap)
        verifier._active_policy = ResearchPolicy.for_tier("standard")
        with (
            mock.patch.object(llm_refine, "judge_provider_chain", return_value=(provider,)),
            mock.patch.dict(os.environ, {"ASK_SEMANTIC_JUDGE_WINDOW": str(budget)}),
            llm_refine.call_ledger_scope(max_calls=3, reuse_existing=False) as ledger,
        ):
            deadline = ResearchDeadline.from_timeout(0 if scenario == "judge_root_expired" else budget * 12)
            started = time.monotonic()
            call = verifier._run_judge_once({"sentences": []}, deadline)
            elapsed = time.monotonic() - started
        return {
            "scenario": scenario,
            "timeout_input_seconds": 0.0 if scenario == "judge_root_expired" else budget,
            "wall_elapsed_seconds": elapsed,
            "request_count": len(requests), "attempts": attempts,
            "remaining_root_seconds": deadline.remaining(),
            "final_timeout_asked": call.timeout_asked,
            "final_attempt_index": call.judge_attempt_index,
            "final_exc_class": call.exc_class,
            "final_issue": call.issue,
            "report_received": call.report is not None,
            "unavailable": call.unavailable,
            "last_dispatched_failure": call.last_dispatched_failure,
            "records": [{key: row.get(key) for key in ("caller", "elapsed_ms", "status", "reason", "purpose")}
                        for row in ledger.summary()["records"]],
        }


def violations(cases: list[dict], tolerance: float) -> list[str]:
    return [case["scenario"] for case in cases
            if case["wall_elapsed_seconds"] > case["timeout_input_seconds"] + tolerance]


def source_identity() -> dict:
    def git(*args):
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()

    paths = [Path(__file__).relative_to(ROOT), Path(llm_refine.__file__).relative_to(ROOT),
             Path(semantic.__file__).relative_to(ROOT), Path("intelligence/services/research_contract.py")]
    return {
        "revision": git("rev-parse", "HEAD"),
        "working_tree_status": git("status", "--porcelain"),
        "python": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "source_sha256": {str(path): hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=0.8)
    parser.add_argument("--tolerance", type=float, default=0.2)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assert-deadline", action="store_true")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or not 0.5 <= args.timeout <= 3.0:
        parser.error("timeout must be finite and between 0.5 and 3 seconds")
    if not math.isfinite(args.tolerance) or not 0 <= args.tolerance < args.timeout * 0.5:
        parser.error("tolerance must be finite and less than half the budget")
    # Refuse to overwrite prior receipts, including symlinks.
    with args.output.open("x", encoding="utf-8") as output:
        before = source_identity()
        cases = [run_case(name, max(1.2, args.timeout) if name.startswith("synthesis_stream") else args.timeout)
                 for name in SCENARIOS]
        cases.extend(run_judge_case(name, args.timeout) for name in JUDGE_SCENARIOS)
        overruns = violations(cases, args.tolerance)
        result = {
            "schema_version": 1,
            "scope": "synthetic loopback HTTP; no live model or content acceptance",
            "source_before": before,
            "source_after": source_identity(),
            "scheduling_tolerance_seconds": args.tolerance,
            "deadline_violations": overruns,
            "cases": cases,
        }
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps({"receipt": str(args.output), "deadline_violations": overruns}))
    return int(args.assert_deadline and bool(overruns))


if __name__ == "__main__":
    raise SystemExit(main())
