"""Reproduce select/readline read-ahead after a discarded RAG worker reply.

Runs the real _query_locked consumer against an OS pipe, not a model or KB.
Both old and current replies enter the same pipe write. TextIO read-ahead can
consume both while select sees only the kernel buffer; the current reply is
then stranded in Python despite being fully received. A byte-wise diagnostic
reader controls for this buffering difference. It is NOT a production fix.

No child process, socket, database, timing retry, or production configuration.
Output must be new. --expect failure (default) checks the old failure shape;
--expect repaired requires both inputs to return the current response. Neither
mode relabels an older full-suite or live failure as passed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from intelligence.services.rag_worker import PersistentRagWorker  # noqa: E402
from intelligence.services.kb_code_identity import code_identity  # noqa: E402


class _OneLineReader:
    """Diagnostic-only no-read-ahead adapter, not a proposed worker transport."""

    def __init__(self, fd: int) -> None:
        self.fd = fd

    def fileno(self) -> int:
        return self.fd

    def readline(self) -> str:
        data = bytearray()
        while True:
            byte = os.read(self.fd, 1)
            if not byte:
                break
            data.extend(byte)
            if byte == b"\n":
                break
        return data.decode()

    def close(self) -> None:
        os.close(self.fd)


def _observe(read_ahead: bool) -> dict[str, object]:
    reader_fd, writer_fd = os.pipe()
    reader = (
        io.TextIOWrapper(io.BufferedReader(io.FileIO(reader_fd, "r")))
        if read_ahead else _OneLineReader(reader_fd)
    )
    sent: list[str] = []

    class RequestSink(io.StringIO):
        def flush(self) -> None:
            request = json.loads(self.getvalue())
            sent.append(request["id"])
            replies = [
                {"id": "abandoned", "returncode": 0, "stdout": "old", "model_load_count": 1},
                {"id": request["id"], "returncode": 0, "stdout": "current", "model_load_count": 1},
            ]
            for row in replies:
                row["code_identity"] = worker._code_identity
            data = "".join(json.dumps(row) + "\n" for row in replies).encode()
            assert os.write(writer_fd, data) == len(data)

    temporary = TemporaryDirectory(prefix="rag-framing-probe-")
    kb_root = Path(temporary.name)
    (kb_root / "scripts").mkdir()
    (kb_root / "scripts/rag_index.py").write_text("# synthetic identity only\n")
    worker = PersistentRagWorker(sys.executable, kb_root, kb_root / "unused-index")
    worker._code_identity = code_identity(kb_root)
    process = SimpleNamespace(stdin=RequestSink(), stdout=reader, poll=lambda: None)
    worker._process = process
    worker._ensure_process = lambda: process
    stops: list[bool] = []
    worker._stop_process = lambda: stops.append(True)
    worker.model_load_count = 1
    worker._abandoned.add("abandoned")
    worker._consecutive_timeouts = 1
    stranded = None
    try:
        try:
            reply = worker._query_locked(["query", "current", "--json"], timeout=0.03, allow_abandon=True)
            result, stdout = "response", reply.stdout
        except TimeoutError as exc:
            result, stdout = type(exc).__name__, None
            # EOF makes this inspection bounded if an implementation differs.
            os.close(writer_fd)
            writer_fd = -1
            line = reader.readline()
            if line:
                value = json.loads(line)
                stranded = {"matches_request": value["id"] == sent[0], "stdout": value["stdout"]}
        return {
            "reader": "TextIOWrapper+BufferedReader" if read_ahead else "byte-wise diagnostic control",
            "result": result, "stdout": stdout, "stranded_response": stranded,
            "stale_drained": worker.counters["stale_responses_drained"],
            "timeouts_killed": worker.counters["timeouts_killed"], "stop_requested": bool(stops),
        }
    finally:
        if writer_fd >= 0:
            os.close(writer_fd)
        reader.close()
        worker.close()
        temporary.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expect", choices=("failure", "repaired"), default="failure")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output must be a new file")
    buffered, control = _observe(True), _observe(False)
    observed = (
        buffered["result"] == "TimeoutError"
        and buffered["stranded_response"] == {"matches_request": True, "stdout": "current"}
        and buffered["stale_drained"] == 1
        and control["result"] == "response" and control["stdout"] == "current"
        and control["stale_drained"] == 1 and not control["stop_requested"]
    )
    repaired = all(
        item["result"] == "response" and item["stdout"] == "current"
        and item["stale_drained"] == 1 and item["timeouts_killed"] == 0
        and not item["stop_requested"] for item in (buffered, control)
    )
    expectation_met = observed if args.expect == "failure" else repaired
    root = Path(__file__).resolve().parents[2]
    payload = {
        "schema": "rag-buffered-reply-diagnosis/v2",
        "expected": args.expect, "expectation_met": expectation_met,
        "repaired_behavior_observed": repaired,
        "revision": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
        "dirty_paths": subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True).splitlines(),
        "consumer_sha256": hashlib.sha256((root / "intelligence/services/rag_worker.py").read_bytes()).hexdigest(),
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "buffered": buffered, "diagnostic_control": control, "failure_reproduced": observed,
        "scope": "real query consumer, synthetic process/pipe, no query/provider/network/database",
        "production_deployment_performed": False, "full_suite_reclassified": False,
    }
    with args.output.open("x", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(0 if expectation_met else 1)


if __name__ == "__main__":
    main()
