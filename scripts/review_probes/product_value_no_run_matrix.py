"""Offline round-10 boundary matrix; public measure_pair -> summarize only.

Usage: python product_value_no_run_matrix.py <target-worktree> <output.json>
Fixture constructors create inputs; no receipts are edited. Checks every model
exemption/billing subset, unknown/estimated bills, unusable coverage, foreign-task
bills and input-order stability. No production data or external calls.
"""
# ruff: noqa: E402 -- import the explicit candidate, not the probe checkout
import copy
import itertools
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from intelligence.services.product_value import contracts as C
from intelligence.services.product_value.evidence import InMemoryEvidenceReader
from intelligence.services.product_value.measure import measure_pair
from intelligence.services.product_value.protocol import freeze_protocol
from intelligence.services.product_value.summarize import summarize
from intelligence.tests.test_product_value_summarize import _r7_fee, _r7_setup


def main():
    proto, complete, ev1, _, ev2, writer, _, base = _r7_setup()
    reader = InMemoryEvidenceReader.from_json({"runs": ev1["runs"] + ev2["runs"]})
    task_id = writer["task_id"]
    no_run = []
    for event in copy.deepcopy(base):
        if event.get("assistance_condition") == "assisted":
            if event["event_type"] in {"run_started", "run_finished"}:
                continue
            event["run_ids"] = []
            if event["event_type"] == "task_completed":
                event.update(event_type="task_abandoned", object_refs=[])
                event["payload"].update(completion_evidence_refs=[], terminal_reason="billing unavailable")
        no_run.append(event)

    def fee(component):
        event = _r7_fee(writer, component, 0.1, suffix="-r10-matrix")
        event["run_ids"] = []
        event["payload"]["cost_item"].update(run_id=None, attempt_id=None, span_id=None, coverage_scope="task")
        return event

    out = {}

    def report(label, events, protocol=proto):
        first = copy.deepcopy(complete)
        events = copy.deepcopy(events)
        for event in first + events:
            if event["event_type"] == "assignment_created":
                event["payload"]["protocol_hash"] = protocol["protocol_hash"]
        receipt = measure_pair(events, protocol, reader)
        assert receipt["invalid_reasons"] == [], label
        assert receipt["event_accounting"]["rejected"] == [], label
        for condition in ("original", "assisted"):
            assert receipt["tasks"][condition]["attempts"] == [], label
            assert receipt["tasks"][condition]["timing"]["reason"] is None, label
        summary = summarize(
            [measure_pair(first, protocol, reader), receipt],
            [e for e in first + events if e["event_type"] == "assignment_created"],
            protocol, cohort_events=first + events, due_rechecks=[],
        )
        assert summary["input_errors"] == [], label
        cost = next(m for m in summary["metrics"] if m["metric_id"] == "cost_full_status")
        gaps = {u["component"] for u in receipt["unknown_cost_components"] if u["reason"] == "no_usage_evidence_for_task"}
        projected = [u for u in cost["unknown"] if u["reason"] == "no_usage_evidence_for_task"]
        assert {u["component"] for u in projected} == gaps, label
        assert all(u["task_id"] == u["id"] == task_id for u in projected), label
        reverse = measure_pair(reversed(events), protocol, reader)
        assert reverse["receipt_id"] == receipt["receipt_id"], label
        out[label] = {"receipt": receipt, "cost": cost}
        return receipt, cost, gaps

    models = ["writer_model", "review_model"]
    subsets = [set(m for m, enabled in zip(models, flags) if enabled) for flags in itertools.product([False, True], repeat=2)]
    for required, billed in itertools.product(subsets, repeat=2):
        protocol = copy.deepcopy(proto)
        protocol.pop("protocol_hash")
        protocol["criteria"]["cost"]["not_applicable_components"] = sorted(C.COST_COMPONENTS - required - {"tool"})
        protocol = freeze_protocol(protocol)
        label = f"required={sorted(required)};billed={sorted(billed)}"
        receipt, cost, gaps = report(label, no_run + [fee(c) for c in sorted(billed | {"tool"})], protocol)
        assert gaps == required - billed, label
        assert receipt["status"] == ("incomplete" if gaps else "valid"), label
        assert cost["detail"]["full_cost_status"] == ("unknown" if gaps else "known"), label

    for kind in ("estimated", "unknown", "coverage_unknown", "foreign_task"):
        fees = [fee(c) for c in ["writer_model", "review_model", "tool"]]
        item = fees[1]["payload"]["cost_item"]
        if kind == "estimated":
            item["certainty"] = "estimated"
        elif kind == "unknown":
            item.update(certainty="unknown", amount=None, rate_version=None)
        elif kind == "coverage_unknown":
            item["coverage_scope"] = None
        else:
            original = next(e for e in base if e["event_type"] == "assignment_created" and e["assistance_condition"] == "original")
            for key in ("task_id", "participant_id", "case_id", "case_version", "assistance_condition"):
                fees[1][key] = original[key]
            if "task_id" in fees[1]["payload"]:
                fees[1]["payload"]["task_id"] = original["task_id"]
        receipt, cost, gaps = report(kind, no_run + fees)
        assert receipt["status"] == ("valid" if kind == "estimated" else "incomplete"), kind
        assert cost["detail"]["full_cost_status"] == ("estimated" if kind == "estimated" else "unknown"), kind
        assert gaps == ({"review_model"} if kind in {"coverage_unknown", "foreign_task"} else set()), kind

    result = {
        "target_revision": subprocess.check_output(["git", "-C", sys.argv[1], "rev-parse", "HEAD"], text=True).strip(),
        "scenario_count": len(out), "cases": out,
    }
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"{len(out)} scenarios passed; input-order and public task/component identity checked for each")


if __name__ == "__main__":
    main()
