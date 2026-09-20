#!/usr/bin/env python3
"""Extract paired research traces without treating activity as semantic quality.

Optionally archive the exact durable episodes from an explicitly supplied store.
Includes private observations, failures and answer stages, not a public export.
Use --output outside a sealed pair to reinspect without changing its archive.
Never modifies source runs; refuses to overwrite an existing inspection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.services.episode_store import JsonlEpisodeStore  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def summarize(episode: dict, events: list[dict]) -> dict:
    rounds = []
    calls = []
    tool_events = []
    plans = []
    feedback = []
    checkpoints = []
    configuration = {}
    for event in events:
        kind, payload = event["kind"], event["payload"]
        # Keep empty/error observations and call IDs; an E-card list omits both.
        if kind in {"tool_request", "tool_result", "tool_error"}:
            tool_events.append({"sequence": event["sequence"], "kind": kind, "payload": payload})
        if kind == "configure":
            configuration = {key: payload.get(key) for key in (
                "research_tier", "allowed_capabilities", "authorized_tools",
                "policy_total_seconds", "policy_max_steps", "llm_timeout", "harness",
            )}
        elif kind == "model_turn":
            rounds.append({
                "sequence": event["sequence"],
                **{key: payload.get(key) for key in (
                    "content", "tool_calls", "served_model", "input_tokens", "output_tokens", "error",
                )},
            })
        elif kind == "tool_request":
            calls.append({"sequence": event["sequence"], **{key: payload.get(key) for key in ("call_id", "name", "arguments")}})
        elif kind == "plan":
            plans.append({"sequence": event["sequence"], "plan": payload})
        elif kind == "model_input" and payload.get("source") == "adaptive_research_checkpoint":
            checkpoints.append(event["sequence"])
        elif kind == "tool_budget_state":
            progress = payload.get("runtime_budget", {}).get("research_progress", {})
            if "adaptive_research" in progress:
                feedback.append({"sequence": event["sequence"], "batch": progress.get("batch"), **progress["adaptive_research"]})
    outcome = episode["outcome"]
    semantic = episode.get("semantic_verifier", {})
    verified = semantic.get("verified", {}).get("outcome", {})
    return {
        "configuration": configuration,
        "usage": outcome.get("usage"),
        "status": outcome.get("status"),
        "stop_reason": outcome.get("stop_reason"),
        "declared_gaps": outcome.get("gaps"),
        "answer_stages": {
            "submitted_draft": outcome.get("draft"),
            "verified_draft": verified.get("draft"),
            "verified_gaps": verified.get("gaps"),
            "public_answer": semantic.get("public_answer"),
            "judge_status": semantic.get("judge_status"),
            "sentence_verdicts": semantic.get("sentence_verdicts"),
        },
        "tool_events": tool_events,
        "plan_count": len(plans),
        "checkpoint_count": len(checkpoints),
        "feedback_batches": len(feedback),
        "served_models": sorted({row["served_model"] for row in rounds if row["served_model"]}),
        "plans": plans,
        "feedback": feedback,
        "checkpoints": checkpoints,
        "rounds": rounds,
        "calls": calls,
        "semantic_quality": "not_scored; inspect original answers and supporting observations",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pair", type=Path)
    parser.add_argument("--episode-store", type=Path)
    parser.add_argument("--output", type=Path, help="new inspection directory, including outside the source pair")
    args = parser.parse_args()
    args.pair = args.pair.resolve()
    arms = load(args.pair / "protocol.json")["arms"]
    if not arms or len(set(arms)) != len(arms) or set(arms) - {"off", "on"}:
        parser.error("invalid arms in protocol")
    destination = args.output.resolve() if args.output else args.pair / "inspection"
    destination.mkdir(parents=True, exist_ok=False)
    summaries = {}
    fingerprints = {}
    for arm in arms:
        source = args.pair / arm
        episode = load(source / "raw-run/continuous-episode.json")
        events = episode["events"]
        if args.episode_store is not None:
            store = JsonlEpisodeStore(args.episode_store)
            original = store.episode_dir(episode["runtime_handle"]["episode_id"])
            archive = destination / arm
            archive.mkdir()
            for name in (store.EVENTS_NAME, store.STATE_NAME):
                shutil.copy2(original / name, archive / name)
            events = [json.loads(line) for line in (archive / store.EVENTS_NAME).read_text().splitlines() if line.strip()]
        summary = summarize(episode, events)
        answer_path = source / "answer.md"
        summary["delivered_answer"] = answer_path.read_text(encoding="utf-8") if answer_path.is_file() else None
        summary["elapsed_seconds"] = load(source / "result.json")["elapsed_seconds"]
        summaries[arm] = summary
        dump(destination / f"{arm}.json", summary)
        fingerprints[arm] = load(source / "health.json")["runtime"]["loaded_tree_fingerprint"]
    paired = len(arms) == 2
    controls = {
        "paired": paired,
        "same_loaded_code": fingerprints["off"] == fingerprints["on"] if paired else None,
        "loaded_fingerprints": fingerprints,
        "same_initial_configuration": summaries["off"]["configuration"] == summaries["on"]["configuration"] if paired else None,
        "data_frozen": False,
        "independent_semantic_review": False,
    }
    dump(destination / "controls.json", controls)
    paths = [path for arm in arms for path in (args.pair / arm / "raw-run").rglob("*") if path.is_file()]
    paths.extend(path for arm in arms for name in ("answer.md", "result.json", "health.json") if (path := args.pair / arm / name).is_file())
    paths.append(args.pair / "protocol.json")
    paths.extend(path for path in destination.rglob("*") if path.is_file())
    dump(destination / "sha256.json", {
        str(path.relative_to(args.pair) if path.is_relative_to(args.pair) else path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    })
    print(json.dumps({"controls": controls, **{arm: {key: row[key] for key in ("usage", "plan_count", "checkpoint_count", "feedback_batches", "elapsed_seconds")} for arm, row in summaries.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
