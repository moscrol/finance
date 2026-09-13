"""Offline public-entry probes. All inputs are synthetic; fixture constructors only."""
import copy
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

track = sys.argv[1]
root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(os.environ["RESEARCH_EVOLUTION_QC_ROOT"]) / track
sys.path.insert(0, str(root))
out = {"synthetic": True, "root": str(root), "sha": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(), "probes": {}}

if track == "05":
    from intelligence.services.product_value import contracts as C
    from intelligence.services.product_value.evidence import InMemoryEvidenceReader
    from intelligence.services.product_value.measure import measure_pair
    from intelligence.services.product_value.protocol import freeze_protocol
    from intelligence.services.product_value.summarize import summarize
    from intelligence.tests.test_product_value_summarize import _six_pair_protocol, _clone_complete_pair

    proto = _six_pair_protocol()
    proto.pop("protocol_hash")
    proto["criteria"]["cost"] = {"not_applicable_components": sorted(C.COST_COMPONENTS - {"writer_model", "review_model", "tool"})}
    proto = freeze_protocol(proto)
    complete, evidence1 = _clone_complete_pair(1, "p10", proto["protocol_hash"], provenance="imported")
    second, evidence2 = _clone_complete_pair(2, "p11", proto["protocol_hash"], provenance="imported")
    fees = [e for e in second if e["event_type"] == "cost_recorded" and e["payload"]["cost_item"]["coverage_scope"] == "run"]
    writer = next(e for e in fees if e["payload"]["cost_item"]["component"] == "writer_model")
    review = next(e for e in fees if e["payload"]["cost_item"]["component"] == "review_model")
    base = [e for e in second if e["event_type"] != "cost_recorded"]

    def fee(component, amount, *, run_id=None, attempt_id=None, suffix=""):
        event = copy.deepcopy(writer)
        event["event_id"] = "qc-r7-" + component + suffix
        item = event["payload"]["cost_item"]
        item.update(cost_id=event["event_id"], component=component, amount=amount, quantity=1,
                    evidence_ref="invoice:" + event["event_id"])
        if component == "tool":
            item["unit"] = "calls"
        if run_id:
            item["run_id"] = run_id
            event["run_ids"] = [run_id]
        if attempt_id:
            item["attempt_id"] = attempt_id
        return event

    def result(events, runs):
        reader = InMemoryEvidenceReader.from_json({"runs": evidence1["runs"] + runs})
        r1 = measure_pair(complete, proto, reader)
        r2 = measure_pair(events, proto, reader)
        summary = summarize([r1, r2], [e for e in complete + events if e["event_type"] == "assignment_created"], proto, cohort_events=complete + events, due_rechecks=[])
        return {"receipt": r2, "summary_errors": summary["input_errors"],
                "cost": next(m for m in summary["metrics"] if m["metric_id"] == "cost_full_status")}

    # Single successful attempt: exercise the public shape, not the helper's local list.
    out["probes"]["missing_component_detail"] = result(base + [writer, fee("tool", .01)], evidence2["runs"])

    # Same assigned task, two fully successful executions. One complete run cannot
    # cover model calls in the second run; no amounts are patched in the receipt.
    run2, attempt2 = "qc-r7-run-2", "qc-r7-attempt-2"
    extra_events = []
    for event in base:
        if event["event_type"] in {"run_started", "run_finished"}:
            extra = copy.deepcopy(event)
            extra["event_id"] += "-second"
            extra["run_ids"] = [run2]
            extra["payload"].update(run_id=run2, attempt_id=attempt2)
            for key in ("event_at", "recorded_at"):
                extra[key] = (datetime.fromisoformat(extra[key]) + timedelta(minutes=8)).isoformat()
            extra_events.append(extra)
    evidence_extra = copy.deepcopy(evidence2["runs"][0])
    evidence_extra.update(run_id=run2, artifacts={})
    for key in ("created_at", "finished_at"):
        evidence_extra[key] = (datetime.fromisoformat(evidence_extra[key]) + timedelta(minutes=8)).isoformat()
    two_runs = evidence2["runs"] + [evidence_extra]
    two_base = base + extra_events + [writer, review]
    tool2 = fee("tool", .01, run_id=run2, attempt_id=attempt2)
    writer2 = fee("writer_model", .36, run_id=run2, attempt_id=attempt2, suffix="-second")
    review2 = fee("review_model", .10, run_id=run2, attempt_id=attempt2, suffix="-second")
    out["probes"]["two_successful_attempts"] = {
        "second_no_fees": result(two_base, two_runs),
        "second_tool_only": result(two_base + [tool2], two_runs),
        "second_writer_tool": result(two_base + [tool2, writer2], two_runs),
        "both_complete": result(two_base + [tool2, writer2, review2], two_runs),
    }

    # Failure-only task: tool-only billing must not erase the retry/model gap.
    failed_base = copy.deepcopy(base)
    for event in failed_base:
        if event["event_type"] == "run_finished":
            event["payload"].update(status="failed", error_ref="err:writer-timeout")
        if event["event_type"] == "task_completed" and event["assistance_condition"] == "assisted":
            event["event_type"] = "task_failed"
            event["payload"].update(completion_evidence_refs=[], terminal_reason="writer_timeout")
            event["object_refs"] = []
    failed_base = [e for e in failed_base if not (e["event_type"] == "quality_reviewed" and e["assistance_condition"] == "assisted")]
    failed_runs = copy.deepcopy(evidence2["runs"])
    failed_runs[0].update(status="failed", error="writer timeout", artifacts={})
    # Retry is applicable here. A separate task has an explicit retry bill, so
    # pilot-wide category existence cannot conceal the failed task's own gap.
    old_hash = proto["protocol_hash"]
    proto.pop("protocol_hash")
    proto["criteria"]["cost"]["not_applicable_components"].remove("retry")
    proto = freeze_protocol(proto)
    complete = json.loads(json.dumps(complete).replace(old_hash, proto["protocol_hash"]))
    failed_base = json.loads(json.dumps(failed_base).replace(old_hash, proto["protocol_hash"]))
    retry = copy.deepcopy(next(e for e in complete if e["event_type"] == "cost_recorded"))
    retry["event_id"] = "qc-r7-other-task-retry"
    retry["payload"]["cost_item"].update(cost_id="qc-r7-other-task-retry", component="retry", amount=.02)
    complete.append(retry)
    out["probes"]["all_failed_attempts"] = {
        "no_fees": result(failed_base, failed_runs),
        "tool_only": result(failed_base + [fee("tool", .01)], failed_runs),
        "model_and_tool": result(failed_base + [fee("tool", .01), writer], failed_runs),
    }

elif track == "01":
    from intelligence.services import judgment_maintenance as jm
    from intelligence.tests.test_judgment_maintenance_assess import _binding, _version, _run
    from intelligence.tests.test_judgment_maintenance_actions import _cmd

    b = _binding({"ann:old": "h1"}, created_at="2026-09-10T12:00:00+08:00", baseline_cutoff="2026-09-10")
    vs = [_version("ann:old", "h1", "2026-09-10T09:00:00+08:00"),
          _version("ann:old", "h2", "2026-09-10T20:00:00+08:00"),
          _version("ann:old", "h0", "2026-09-11", expired_at="2026-09-12T10:00:00+08:00"),
          _version("ann:old", "g0", "2026-09-13", expired_at="2026-09-14T10:00:00+08:00")]
    reports = {day: _run([b], vs, as_of=day, cutoff=day) for day in ("2026-09-12", "2026-09-14", "2026-09-15")}
    def view(rep):
        return {"counts": rep.counts, "items": [{"id": i.id, "day": i.first_known_day, "status": i.status, "supersedes": i.supersedes_item_id} for i in rep.items], "management_log": rep.management_log}
    out["probes"]["repeat_and_scan_stability"] = {day: view(rep) for day, rep in reports.items()}
    target = next(i for i in reports["2026-09-14"].items if i.status == "open")
    action = jm.validate_action(item=target, command=_cmd(target, "qc-r7-recur-snooze", "snooze", acted_at="2026-09-14T22:00:00+08:00", snooze_until="2026-09-20T09:00:00+08:00"), owner_user_id="alice", now="2026-09-14T22:00:00+08:00")
    out["probes"]["new_action_next_scan"] = view(jm.reduce_actions(report=reports["2026-09-15"], events=[action.event.to_dict()], now="2026-09-15T22:00:00+08:00"))

print(json.dumps(out, ensure_ascii=False, indent=2))
