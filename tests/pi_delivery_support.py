"""Synthetic, sealed public deliveries for offline replay tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def seal_source(root: Path) -> None:
    entries = {}
    for name in ("plan.json", "RESULT.json", "pi-tools.jsonl", "pi-model-requests.jsonl"):
        data = (root / name).read_bytes()
        entries[name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    (root / "capture-manifest.json").write_text(json.dumps(entries))


def make_source(root: Path) -> Path:
    root.mkdir()
    public = {"tool": "finance_query", "status": "success", "ok": True,
              "observation": "ADMITTED_FACT: five of ten records match.", "evidence": [],
              "query_basis": {"total_rows": 10, "matching_rows": 5}, "gaps": []}
    plan = {"question": "Summarize the supplied market observation.", "model": "glm-5.3-flash",
            "information_cutoff": "2026-09-30", "today": "2026-10-09",
            "latest_data_date": "2026-09-30", "revision": "source-revision"}
    result = {"status": "completed", "inputs_unchanged": True, "processes_stopped": True,
              "arm": {"exit": 0, "stop_reason": "stop", "model_admission": True, "answer_chars": 12}}
    record = {"tool": "finance_query", "arguments": {"dataset": "fixture"},
              "observation": {"telemetry": "PRIVATE_AUDIT_SENTINEL"}, "model_observation": public}
    request = {"payload": {"messages": [
        {"role": "assistant", "content": "OLD_DRAFT_SENTINEL"},
        {"role": "tool", "content": json.dumps({"tool": "finance_query", "observation": public})},
    ]}}
    for name, value in (("plan.json", plan), ("RESULT.json", result),
                        ("pi-tools.jsonl", record), ("pi-model-requests.jsonl", request)):
        (root / name).write_text(json.dumps(value) + "\n")
    seal_source(root)
    return root
