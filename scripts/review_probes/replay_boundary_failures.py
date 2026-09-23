"""Read-only replay of the archived 8792 F1/F3 failure shapes.

Blocks socket connections and writes checkpoints only under TemporaryDirectory.
This checks parser/progress projections with original inputs, not model quality
or an entire Episode replay (the scripted-loop tests cover the latter seam).
Use --live-root for the sealed review directory; original files are never edited.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from intelligence.runtime.research_progress import ResearchProgressTracker, ToolCallDigest, normalize_query  # noqa: E402
from intelligence.services.agent_runtime import ModelToolCall  # noqa: E402
from intelligence.services.research_tool_registry import InvalidResearchToolArguments, parse_url_arguments  # noqa: E402
from intelligence.services.track_contract import ingest_next_watch, missing_contract_elements, parse_next_watch_items  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.live_root.resolve()
    output = args.output.resolve()
    if output.is_relative_to(root):
        parser.error("output must not be inside the sealed input directory")
    attempts = []

    def denied(*_args, **_kwargs):
        attempts.append("connect")
        raise AssertionError("offline replay must not connect")

    socket.socket.connect = denied
    socket.create_connection = denied
    sources = {}

    def read(path):
        data = path.read_bytes()
        sources[str(path.relative_to(root))] = hashlib.sha256(data).hexdigest()
        return data.decode("utf-8")

    answers = {
        case: read(root / "cases" / case / "artifacts" / "answer.md")
        for case in ("f1-opt-out", "positive-persistence")
    }
    assert missing_contract_elements(answers["f1-opt-out"]) == ("next_watch",)
    assert parse_next_watch_items(answers["f1-opt-out"], as_of="2026-09-18") == ()
    assert missing_contract_elements(answers["positive-persistence"]) == ()
    writer_checks = {}
    with tempfile.TemporaryDirectory(prefix="boundary-replay-") as tmp:
        for case, answer in answers.items():
            path = Path(tmp) / case / "checkpoints.jsonl"
            assert ingest_next_watch(path, answer, query="请跟踪，但不要登记为长期跟踪") == []
            assert not path.exists()
            rows = ingest_next_watch(
                path, answer, query="请跟踪并登记为长期跟踪", as_of="2026-09-18",
                session_id="offline-boundary-replay",
            )
            assert len(rows) == (0 if case == "f1-opt-out" else 1)
            assert all(row["due"] == "2026-10-21" for row in rows)
            assert all(row["session_id"] == "offline-boundary-replay" for row in rows)
            writer_checks[case] = {"opt_out_writes": 0, "authorized_writes": len(rows), "due": [row["due"] for row in rows]}

    run = json.loads(read(root / "cases" / "f3-formatted-financial" / "artifacts" / "run.json"))
    run_id = run.get("run_id") or run.get("id")
    assert run_id, "archive must carry exact run identity"
    event_files = list((root / "data" / "state" / "episodes").glob(f"{run_id}_*/events.jsonl"))
    assert len(event_files) == 1, "refuse ambiguous event source"
    events = [json.loads(line) for line in read(event_files[0]).splitlines()]
    event = next(event for event in reversed(events) if event["kind"] == "tool_request")
    raw = event["payload"]
    assert raw["name"] == "web_fetch" and raw["arguments"] == {"url": "file:///nonexistent"}
    call = ModelToolCall(raw["call_id"], raw["name"], raw["arguments"])
    try:
        parse_url_arguments(call.arguments)
    except InvalidResearchToolArguments as exc:
        assert exc.code == "invalid_query"
    else:
        raise AssertionError("file URL must remain rejected")
    tracker = ResearchProgressTracker()
    tracker.record_call(ToolCallDigest(call.name, call.arguments, "rejected"))
    tracker.close_batch()
    progress = tracker.model_view()
    assert progress["last_batch"][0]["query"] == normalize_query(raw["arguments"])
    assert progress["last_batch"][0]["result"] == "rejected"
    assert call.to_dict()["arguments"] == raw["arguments"]
    assert not attempts
    for name, digest in sources.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    report = {
        "scope": "original-input mechanical replay, not live/model acceptance",
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "sources_sha256": sources, "sources_unchanged": True,
        "writer_checks": writer_checks,
        "f3": {"event_count": len(events), "url_rejected": True, "progress_json_serializable": True},
        "network_connect_attempts": len(attempts),
    }
    json.dumps(progress)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
