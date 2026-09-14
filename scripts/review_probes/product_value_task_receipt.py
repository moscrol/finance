"""Offline public-entry probes: no-run task receipt and component projection.

Usage: python product_value_task_receipt.py <target-worktree> <output.json>
Only fixture events/evidence are built. Receipts are never mutated.
"""
# ruff: noqa: E402 -- resolve imports from the explicit target revision
import copy
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from intelligence.services.product_value import contracts as C
from intelligence.services.product_value.evidence import InMemoryEvidenceReader
from intelligence.services.product_value.measure import measure_pair
from intelligence.services.product_value.protocol import freeze_protocol
from intelligence.services.product_value.summarize import summarize
from intelligence.tests.test_product_value_summarize import _r7_fee, _r7_setup


def main(output):
    proto, complete, ev1, _, ev2, writer, review, base = _r7_setup()
    reader = InMemoryEvidenceReader.from_json({"runs": ev1["runs"] + ev2["runs"]})
    # Preserve consent, trusted task timing and independent quality review. Remove
    # assisted run lifecycle; the task is abandoned with no claimed completion.
    no_run = []
    for event in copy.deepcopy(base):
        if event.get("assistance_condition") == "assisted":
            if event["event_type"] in {"run_started", "run_finished"}:
                continue
            event["run_ids"] = []
            if event["event_type"] == "task_completed":
                event.update(event_type="task_abandoned", event_id=event["event_id"] + "-abandoned", object_refs=[])
                event["payload"].update(completion_evidence_refs=[], terminal_reason="abandoned; run and billing records unavailable")
        no_run.append(event)

    def fee(component, amount):
        event = _r7_fee(writer, component, amount, suffix="-task")
        event["run_ids"] = []
        event["payload"]["cost_item"].update(run_id=None, attempt_id=None, span_id=None, coverage_scope="task")
        return event

    def report(events, protocol=proto, first=complete):
        receipt = measure_pair(events, protocol, reader)
        summary = summarize(
            [measure_pair(first, protocol, reader), receipt],
            [e for e in first + events if e["event_type"] == "assignment_created"],
            protocol, cohort_events=first + events, due_rechecks=[],
        )
        cost = next(m for m in summary["metrics"] if m["metric_id"] == "cost_full_status")
        return {"receipt": receipt, "cost": cost, "summary_errors": summary["input_errors"]}

    out = {}
    for name, components in (
        ("no_fees", []), ("tool_only", [("tool", .01)]),
        ("writer_tool", [("tool", .01), ("writer_model", .36)]),
        ("complete", [("tool", .01), ("writer_model", .36), ("review_model", .10)]),
    ):
        out["task_" + name] = report(no_run + [fee(c, a) for c, a in components])
    out["attempt_no_fees"] = report(base)
    extra = []
    rid2, aid2 = "qc-task-run2", "qc-task-attempt2"
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
    # Swap which component is missing in each attempt: the public unknown list
    # must be able to distinguish the two different repair actions.
    out["split_gaps_a"] = report(base + extra + [
        writer, _r7_fee(review, "review_model", .10, run_id=rid2, attempt_id=aid2, suffix="-split-review"),
    ])
    out["split_gaps_b"] = report(base + extra + [
        review, _r7_fee(writer, "writer_model", .36, run_id=rid2, attempt_id=aid2, suffix="-split-writer"),
    ])
    # Freeze a protocol exemption before measuring, updating assignment bindings.
    exempt = copy.deepcopy(proto)
    exempt.pop("protocol_hash")
    exempt["criteria"]["cost"]["not_applicable_components"] = sorted(C.COST_COMPONENTS - {"writer_model", "tool"})
    exempt = freeze_protocol(exempt)
    exempt_base, exempt_first = copy.deepcopy(base), copy.deepcopy(complete)
    for event in exempt_base + exempt_first:
        if event["event_type"] == "assignment_created":
            event["payload"]["protocol_hash"] = exempt["protocol_hash"]
    out["protocol_review_exempt"] = report(
        exempt_base + [writer, _r7_fee(writer, "tool", .01, suffix="-exempt")], exempt, exempt_first,
    )
    Path(output).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    for label, result in out.items():
        receipt = result["receipt"]
        print(json.dumps({
            "case": label, "receipt_status": receipt["status"],
            "invalid": receipt["invalid_reasons"], "rejected": receipt["event_accounting"]["rejected"],
            "limitations": receipt["limitations"], "receipt_gaps": receipt["unknown_cost_components"],
            "attempts": receipt["tasks"]["assisted"]["attempts"],
            "cost_status": result["cost"]["detail"]["full_cost_status"],
            "cost_known": result["cost"]["detail"]["known_cost_by_currency"],
            "cost_unknown": result["cost"]["unknown"],
            "summary_errors": result["summary_errors"],
        }, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[2])
