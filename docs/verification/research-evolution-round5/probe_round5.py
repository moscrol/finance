"""Independent synthetic regression boundaries, no production IO."""
import contextlib
import copy
import io
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

track = sys.argv[1]
root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(os.environ.get("RESEARCH_EVOLUTION_QC_ROOT", str(Path(__file__).parent))) / track
sys.path.insert(0, str(root))
out = {"synthetic": True, "root": str(root), "sha": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(), "probes": {}}
if track == "01":
    from intelligence.tests.test_judgment_maintenance_assess import _binding, _version, _run, _obs, _condition

    def view(r):
        return {"counts": r.counts, "pit": r.pit_grade, "gaps": [g.reason for g in r.gaps], "items": [{"id": i.id, "version": i.item_version, "day": i.first_known_day, "status": i.status, "reason": i.reason_code, "epistemic": i.epistemic_state, "condition": i.condition_result, "current": [v.source_hash for v in i.current], "gaps": [g.reason for g in i.gaps], "supersedes": i.supersedes_item_id} for i in r.items]}

    def binding_view(stamp):
        b = _binding({"ann:old": "h1"}, created_at=stamp, baseline_cutoff="2026-09-10")
        vs = [_version("ann:old", "h1", "2026-09-10T10:00:00+08:00"), _version("ann:old", "h2", "2026-09-11T10:00:00+08:00")]
        return view(_run([b], vs, as_of="2026-09-11", cutoff="2026-09-11"))
    out["probes"]["binding_created_market_day"] = {"utc": binding_view("2026-09-11T16:30:00Z"), "market": binding_view("2026-09-12T00:30:00+08:00")}

    def condition_view(stamp):
        b = _binding({"ann:old": "h1"}, created_at="2026-09-10T12:00:00+08:00", baseline_cutoff="2026-09-10", conditions=[_condition()])
        obs = _obs("market_stage", "反弹", as_of="2026-09-11", recorded=stamp)
        return view(_run([b], [_version("ann:old", "h1", "2026-09-10T10:00:00+08:00")], [obs], as_of="2026-09-11", cutoff="2026-09-11"))
    out["probes"]["condition_known_market_day"] = {"utc": condition_view("2026-09-11T16:30:00Z"), "market": condition_view("2026-09-12T00:30:00+08:00"), "known_control": condition_view("2026-09-11T15:30:00Z")}

    b = _binding({"ann:old": "h1"}, created_at="2026-09-10T12:00:00+08:00", baseline_cutoff="2026-09-10")
    # h2 wins deterministic display; an incomparable lower-sort h0 arrives the next knowledge day.
    vs = [_version("ann:old", "h1", "2026-09-10T09:00:00+08:00"), _version("ann:old", "h2", "2026-09-10T20:00:00", valid_from="2026-09-02"), _version("ann:old", "h0", "2026-09-11T00:30:00+08:00", valid_from="2026-09-02")]
    out["probes"]["ambiguity_transition_item_identity"] = {"input": vs, "before": view(_run([b], vs, as_of="2026-09-10", cutoff="2026-09-10")), "after": view(_run([b], vs, as_of="2026-09-12", cutoff="2026-09-12"))}
    # A full-precision changed version is visible before a later date-only contender.
    vs2 = [_version("ann:old", "h1", "2026-09-10T09:00:00+08:00"), _version("ann:old", "h2", "2026-09-10T20:00:00+08:00"), _version("ann:old", "h0", "2026-09-11", expired_at="2026-09-12T10:00:00+08:00")]
    out["probes"]["ambiguity_resolved_same_hash"] = {"input": vs2, "actual": view(_run([b], vs2, as_of="2026-09-12", cutoff="2026-09-12"))}

elif track == "05":
    # Reuse only fixture construction from the original QC probe; actual receipts
    # are produced anew via the fixed candidate's public measure_pair entry point.
    saved = sys.argv
    sys.argv = ["probe_adjacent.py", "05", str(root)]
    with contextlib.redirect_stdout(io.StringIO()):
        ns = runpy.run_path(str(Path(__file__).with_name("probe_adjacent.py")))
    sys.argv = saved
    C, freeze = ns["C"], ns["freeze_protocol"]
    proto = copy.deepcopy(ns["proto"])
    proto.pop("protocol_hash")
    proto["criteria"]["cost"]["not_applicable_components"] = sorted(C.COST_COMPONENTS - {"writer_model", "review_model", "tool"})
    proto = freeze(proto)
    complete, evidence = ns["_clone_complete_pair"](1, "p10", proto["protocol_hash"], provenance="imported")
    reader = ns["InMemoryEvidenceReader"].from_json(evidence)
    events = copy.deepcopy(ns["events"])
    for e in events:
        if e["event_type"] == "assignment_created":
            e["payload"]["protocol_hash"] = proto["protocol_hash"]
    r1 = ns["measure_pair"](complete, proto, reader)
    template = copy.deepcopy(next(e for e in events if e["event_type"] == "task_abandoned"))

    def fee(component, amount):
        e = copy.deepcopy(template)
        e.update(event_id="qc-fee-" + component, event_type="cost_recorded", source_channel="server", object_refs=[], run_ids=[])
        e["payload"] = {"initiator": template["payload"]["initiator"], "assistance_source": template["payload"]["assistance_source"], "cost_item": {"cost_id": "qc-cost-" + component, "component": component, "run_id": None, "attempt_id": None, "span_id": None, "coverage_scope": "task", "quantity": 1, "unit": "calls", "amount": amount, "currency": "CNY", "certainty": "known", "evidence_ref": "invoice:" + component, "rate_version": "qc-rate-v1", "allocation_rule": None}}
        return e

    def measured(extra):
        evs = events + extra
        r2 = ns["measure_pair"](evs, proto, reader)
        assignments = [e for e in complete + evs if e["event_type"] == "assignment_created"]
        s = ns["summarize"]([r1, r2], assignments, proto, cohort_events=complete + evs, due_rechecks=[])
        return {"receipt": r2, "cost": next(m for m in s["metrics"] if m["metric_id"] == "cost_full_status")}

    out["probes"]["unrelated_task_fee_covers_models"] = {"before": measured([]), "tool_only": measured([fee("tool", 0.01)]), "writer_and_tool_only": measured([fee("tool", 0.01), fee("writer_model", 0.36)]), "all_components_control": measured([fee("tool", 0.01), fee("writer_model", 0.36), fee("review_model", 0.10)])}

print(json.dumps(out, ensure_ascii=False, indent=2))
