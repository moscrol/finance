"""Audit final text against archived boundary-live-retest evidence, without IO tools.

This is a read-only diagnostic, not an acceptance gate or full Episode replay.
It exposes disagreements among sentence verdicts, parser completeness, persisted
checkpoints and tool-envelope success. Numeric checks project archived fields
into the production pure function; no fake judge or fresh model is invoked.
Output must be outside the input root and must not already exist.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from intelligence.services import episode_semantic_verifier as semantic  # noqa: E402
from intelligence.services import track_contract as track  # noqa: E402
from intelligence.services import user_task  # noqa: E402
from intelligence.services.research_contract import ResearchTaskContract  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root, output = args.live_root.resolve(), args.output.resolve()
    if output.is_relative_to(root) or output.exists():
        parser.error("output must be new and outside the archived input root")
    attempts: list[str] = []

    def denied(*_args, **_kwargs):
        attempts.append("connect")
        raise AssertionError("offline diagnostic must not connect")

    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied
    sources: dict[str, str] = {}

    def read(path: Path) -> str:
        data = path.read_bytes()
        sources[str(path.relative_to(root))] = hashlib.sha256(data).hexdigest()
        return data.decode("utf-8")

    protocol = json.loads(read(root / "protocol.json"))
    assert protocol["schema"] == "boundary-live-retest/v1"
    results = []
    for case in protocol["cases"]:
        directory = root / "cases" / case["id"]
        receipt = json.loads(read(directory / "receipt.json"))
        answer = read(directory / "artifacts" / "answer.md")
        episode_path = directory / "artifacts" / "continuous-episode.json"
        episode = json.loads(read(episode_path)) if episode_path.exists() else {}
        question = case["question"]
        assert hashlib.sha256(question.encode()).hexdigest() == case["question_sha256"]
        material_matches = [
            {"text": m.group(), "span": m.span()}
            for m in user_task._MATERIAL_REFERENCE_RE.finditer(re.sub(r"\s+", "", question))
        ]
        section = track._watch_section_body(answer)
        claims = track._split_watch_claims(section)
        entry = {
            "case": case["id"], "run_id": receipt["run_id"],
            "references_material": user_task.references_material(question),
            "material_reference_matches": material_matches,
            "request_material_count": len(user_task.split_user_message(question).materials),
            "watch_missing": track.missing_contract_elements(answer),
            "watch_chunks": [{"text": c, "registerable": track._is_registerable_watch(c)} for c in claims],
            "watch_items": [{"claim": i.claim, "due": i.due} for i in track.parse_next_watch_items(answer, as_of="2026-09-18")],
            "demoted_sentences_still_public": [
                v for v in episode.get("semantic_verifier", {}).get("sentence_verdicts", [])
                if v.get("decision") == "demoted_to_issue" and v.get("sentence") in answer
            ],
        }
        if episode:
            outcome = episode["outcome"]
            contract = ResearchTaskContract.from_dict(episode["contract"])
            assert contract is not None
            projected_outcome = SimpleNamespace(
                evidence=tuple(
                    SimpleNamespace(**{**e, "observations": tuple(SimpleNamespace(**o) for o in e.get("observations", []))})
                    for e in outcome["evidence"]
                ),
                bindings=tuple(SimpleNamespace(**b) for b in outcome["bindings"]),
            )
            projected = SimpleNamespace(contract=contract, outcome=projected_outcome)
            sentences = semantic._numbered_sentences(answer)
            rejected = semantic._novel_numeric_condition_indexes(sentences, projected)
            entry["public_numeric_gate_rejects"] = [s for s in sentences if s["index"] in rejected]
            quantities = semantic._bound_evidence_quantities(projected_outcome)
            entry["threshold_quantity_supported"] = {
                q: semantic._quantity_supported_by_evidence(q, quantities, sentence="净现比回升≥50%或净现比<0.2")
                for q in ("50%", "0.2")
            }
            entry["public_threshold_sentences"] = [
                {**s, "trigger_match": (m.group() if (m := semantic._CONDITION_TRIGGER_RE.search(str(s["text"]))) else None),
                 "rejected": s["index"] in rejected}
                for s in sentences if re.search(r"≥50%|<0\.2", str(s["text"]))
            ]
            entry["available_q1_evidence"] = [
                {k: e.get(k) for k in ("content_hash", "title", "source_date", "source")}
                for e in outcome["evidence"] if "2026一季报" in e.get("title", "")
            ]
            stores = list((root / "data/state/episodes").glob(
                receipt["run_id"] + "_" + receipt["assistant_message_id"] + "-*/events.jsonl"
            ))
            assert len(stores) == 1
            events = [json.loads(line) for line in read(stores[0]).splitlines() if line.strip()]
            tool_results = [(i, e["payload"]) for i, e in enumerate(events) if e["kind"] == "tool_result"]
            entry["tool_envelope_failures"] = [
                {"event_index": i, "tool": p.get("tool"), "error_code": p.get("error_code")}
                for i, p in tool_results if p.get("ok") is False or p.get("error_code") or p.get("error_kind")
            ]
            entry["calculation_failures_inside_ok_envelope"] = [
                {"event_index": i, "tool": p.get("tool"), "ok": p.get("ok"),
                 "observation": p["observation"],
                 "subsequent_finish": any(e["kind"] == "finish" for e in events[i + 1:])}
                for i, p in tool_results if str(p.get("observation", "")).startswith("派生计算未产出")
            ]
            entry["invalid_actions"] = [e["payload"] for e in events if e["kind"] == "invalid_action"]
            entry["repair_goals"] = [e["payload"] for e in events if e["kind"] == "repair_goal"]
            entry["zero_tool_repair_dispatches"] = [
                {"repair_goal_id": e["payload"]["repair_goal_id"],
                 "subsequent_tool_requests": sum(v["kind"] == "tool_request" for v in events[i + 1:])}
                for i, e in enumerate(events)
                if e["kind"] == "repair_goal" and e["payload"].get("remaining_calls") == 0
            ]
        results.append(entry)
    assert not attempts
    assert all(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest for name, digest in sources.items())
    report = {
        "scope": "archived input diagnostics; not full episode replay, financial certification or gate fix",
        "live_revision": protocol["code_revision"],
        "inspection_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "inspection_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip()),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "sources_sha256": sources, "sources_unchanged": True,
        "network_connect_attempts": len(attempts), "runs": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"output": str(output), "cases": len(results), "network_connect_attempts": len(attempts)}))


if __name__ == "__main__":
    main()
