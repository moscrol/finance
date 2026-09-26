"""Offline cancellation triplet against an explicitly pinned, clean candidate.

Baseline / AST keyword-deletion mutation / restoration all execute the same
wall-clock assertion. Mutation is in process memory, never in the checkout.
This is author tooling evidence, not an independent review or live-model test.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import hashlib
import inspect
import json
from pathlib import Path
import platform
import subprocess
import sys
import textwrap
import threading
import time
from unittest import mock


def identity(tree: Path) -> dict:
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tree), *args], text=True).strip()
    return {"revision": git("rev-parse", "HEAD"), "status": git("status", "--porcelain"),
            "source_sha256": {name: hashlib.sha256((tree / name).read_bytes()).hexdigest()
                              for name in ("intelligence/services/llm_refine.py",
                                           "intelligence/services/llm_http_transport.py")}}


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


def remove_forwarding(function, globals_dict):
    module = ast.parse(textwrap.dedent(inspect.getsource(function)))
    removed = 0
    for node in ast.walk(module):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "opener":
            before = len(node.keywords)
            node.keywords = [keyword for keyword in node.keywords if keyword.arg != "is_cancelled"]
            removed += before - len(node.keywords)
    if removed != 1:
        raise ValueError(f"expected one keyword deletion, found {removed}")
    namespace = dict(globals_dict)
    exec(compile(ast.fix_missing_locations(module), "<offline-cancel-forwarding-mutant>", "exec"), namespace)
    return namespace[function.__name__]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    tree = args.candidate.resolve()
    before = identity(tree)
    if before["revision"] != args.revision or before["status"]:
        parser.error("candidate identity is not the requested clean revision")
    sys.path.insert(0, str(tree))
    from intelligence.services import llm_refine as llm
    from scripts.review_probes.diagnose_llm_timeout import local_endpoint
    assert Path(llm.__file__).resolve().is_relative_to(tree)
    original = llm._open_deadline_http_response
    mutant = remove_forwarding(original, llm.__dict__)
    with args.output.open("x", encoding="utf-8") as stream:
        phases = {}
        for phase, function in (("baseline", original), ("mutation", mutant), ("restored", original)):
            with mock.patch.object(llm, "_open_deadline_http_response", function):
                phases[phase] = [run_case(llm, local_endpoint, name)
                                 for name in ("wrapper", "tools_stream", "synthesis_stream")]
        after = identity(tree)
        passed = (before == after and all(row["passed"] for row in phases["baseline"])
                  and not any(row["passed"] for row in phases["mutation"])
                  and all(row["passed"] for row in phases["restored"]))
        record = {"status": "PASS" if passed else "FAIL", "scope": "host author probe only",
                  "live_model_requests": 0, "source_before": before, "source_after": after,
                  "python": sys.executable, "python_version": platform.python_version(),
                  "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "mutation": "AST delete exactly one is_cancelled keyword at wrapper opener call",
                  "mutation_storage": "in process memory only; candidate files untouched",
                  "call_budget_seconds": 10, "cancel_after_headers_seconds": 0.3,
                  "upstream_stall_seconds": 1.6, "read_assertion_max_seconds": 1.0,
                  "cancel_to_stop_max_seconds": 0.7,
                  "phases": phases}
        json.dump(record, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": record["status"], "output": str(args.output), "phases": phases}))
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())
