"""Offline public-entry probes for receipt cost selection and component coverage.

Usage: python product_value_selection.py <target-worktree> <output.json>
Only synthetic event fixtures are built; no receipt mutation or external IO.
"""
# ruff: noqa: E402 -- imports must resolve from the specified target revision
import copy
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from intelligence.services.product_value.evidence import InMemoryEvidenceReader
from intelligence.services.product_value.measure import measure_pair
from intelligence.services.product_value.summarize import summarize
from intelligence.tests.test_product_value_summarize import _r7_fee, _r7_setup


def main(output):
    proto, complete, ev1, _, ev2, writer, review, base = _r7_setup()
    aid1 = writer["payload"]["cost_item"]["attempt_id"]
    rid2, aid2 = "qc-selection-run2", "qc-selection-attempt2"
    extra = []
    for event in base:
        if event["event_type"] not in {"run_started", "run_finished"}:
            continue
        event = copy.deepcopy(event)
        event["event_id"] += "-second"
        event["run_ids"] = [rid2]
        event["payload"].update(run_id=rid2, attempt_id=aid2)
        for key in ("event_at", "recorded_at"):
            event[key] = (datetime.fromisoformat(event[key]) + timedelta(minutes=8)).isoformat()
        extra.append(event)
    run = copy.deepcopy(ev2["runs"][0])
    run.update(run_id=rid2, artifacts={})
    for key in ("created_at", "finished_at"):
        run[key] = (datetime.fromisoformat(run[key]) + timedelta(minutes=8)).isoformat()
    reader = InMemoryEvidenceReader.from_json({"runs": ev1["runs"] + ev2["runs"] + [run]})

    def fees(aid, scope, suffix):
        events = []
        for component, amount in (("tool", 0.01), ("writer_model", 0.36), ("review_model", 0.10)):
            event = _r7_fee(writer, component, amount, run_id=rid2, attempt_id=aid, suffix=suffix)
            event["payload"]["cost_item"]["coverage_scope"] = scope
            events.append(event)
        return events

    def report(additions):
        events = base + extra + [writer, review] + additions
        receipt = measure_pair(events, proto, reader)
        summary = summarize(
            [measure_pair(complete, proto, reader), receipt],
            [e for e in complete + events if e["event_type"] == "assignment_created"],
            proto, cohort_events=complete + events, due_rechecks=[],
        )
        cost = next(m for m in summary["metrics"] if m["metric_id"] == "cost_full_status")
        return {"receipt": receipt, "cost": cost, "summary_errors": summary["input_errors"]}

    coarse_mismatch = fees(aid1, "run", "-coarse-mismatch")
    fine_correct = fees(aid2, "attempt", "-fine-correct")
    coarse_correct = fees(aid2, "run", "-coarse-correct")
    tool = next(e for e in coarse_correct if e["payload"]["cost_item"]["component"] == "tool")
    writer2 = next(e for e in coarse_correct if e["payload"]["cost_item"]["component"] == "writer_model")
    out = {
        "mismatch_without_fine": report(coarse_mismatch),
        "mismatch_with_unselected_fine": report(coarse_mismatch + fine_correct),
        "consistent_coarse_with_fine": report(coarse_correct + fine_correct),
        "fine_only_control": report(fine_correct),
        "second_tool_only": report([tool]),
        "second_writer_tool": report([tool, writer2]),
        "all_components_control": report(coarse_correct),
    }
    Path(output).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    for label, result in out.items():
        r = result["receipt"]
        print(json.dumps({
            "case": label, "status": r["status"], "invalid": r["invalid_reasons"],
            "rejected": r["event_accounting"]["rejected"], "receipt_unknown": r["unknown_cost_components"],
            "receipt_known": r["known_cost_by_currency"],
            "items_run2": [{k: i[k] for k in ("component", "attempt_id", "run_id", "selected", "dedup_reason")}
                           for i in r["cost_items"] if i["run_id"] == rid2],
            "summary_status": result["cost"]["detail"]["full_cost_status"],
            "summary_unknown": result["cost"]["unknown"],
        }, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[2])
