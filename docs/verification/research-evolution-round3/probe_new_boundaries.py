"""Read-only synthetic boundary probes. Usage: python probe_new_boundaries.py 01|04|05 [root]."""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

track = sys.argv[1]
root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(os.environ.get('RESEARCH_EVOLUTION_QC_ROOT', '/tmp/research-evolution-round3-qc')) / track
sys.path.insert(0, str(root))
out = {"synthetic": True, "track": track, "root": str(root), "sha": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(), "probes": {}}

if track == "01":
    from intelligence.tests.test_judgment_maintenance_assess import _binding, _version, _run, _live
    def view(versions):
        r = _run([_binding({"ann:old": "h1"}, created_at="2026-09-10T12:00:00+08:00", baseline_cutoff="2026-09-10")], versions)
        return {"counts": r.counts, "pit_grade": r.pit_grade, "gaps": [g.reason for g in r.gaps], "live": [{"change": i.change_type, "status": i.status, "epistemic": i.epistemic_state, "hash": [v.source_hash for v in i.current], "gaps": [g.reason for g in i.gaps]} for i in _live(r)]}
    tie = [_version("ann:old", "h1", "2026-09-10T10:00:00+08:00"), _version("ann:old", "h2", "2026-09-10T10:00:00+08:00")]
    out["probes"]["equal_time_distinct_hash"] = {"input": tie, "actual": view(tie)}
    mixed = [_version("ann:old", "h1", "2026-09-10T10:00:00+08:00"), _version("ann:old", "h2", "2026-09-10T03:00:00Z", expired_at="2026-09-11T18:00:00+08:00")]
    norm = copy.deepcopy(mixed)
    norm[1]["recorded_at"] = "2026-09-10T11:00:00+08:00"
    out["probes"]["mixed_offset_correction"] = {"input": mixed, "actual": view(mixed), "same_instant_normalized": view(norm)}

if track == "04":
    from intelligence.tests.test_research_diagnostics_review_20260913 import load_fixture, run_scenario, one_stale
    mr = load_fixture("maintenance_report_01.json")
    item = next(i for i in mr["items"] if i["id"] == "mi-004")
    item["before"][0].update(recorded_at=None, expired_at="2026-09-02T18:00:00+08:00", valid_to=None)
    baseline = one_stale(run_scenario(maintenance_reports=[mr]), "eu-004")
    # A later re-recording of the original hash cannot answer when the earlier expiry was known.
    item["current"][0].update(ref="ann:004", source_hash="n1", supersedes_ref=None, valid_from="2026-09-06", recorded_at="2026-09-06T18:00:00+08:00", expired_at=None, valid_to=None)
    actual = one_stale(run_scenario(maintenance_reports=[mr]), "eu-004")
    early, late = copy.deepcopy(mr), copy.deepcopy(mr)
    next(i for i in early["items"] if i["id"] == "mi-004")["before"][0]["recorded_at"] = "2026-09-01T18:00:00+08:00"
    next(i for i in late["items"] if i["id"] == "mi-004")["before"][0]["recorded_at"] = "2026-09-07T18:00:00+08:00"
    out["probes"]["later_reinstatement_masks_missing_time"] = {"item": item, "baseline": baseline.to_dict(), "actual": actual.to_dict(), "fill_early": one_stale(run_scenario(maintenance_reports=[early]), "eu-004").to_dict(), "fill_late": one_stale(run_scenario(maintenance_reports=[late]), "eu-004").to_dict()}

if track == "05":
    from intelligence.services.product_value import contracts as C
    from intelligence.services.product_value.evidence import InMemoryEvidenceReader
    from intelligence.services.product_value.measure import measure_pair
    from intelligence.services.product_value.protocol import freeze_protocol
    from intelligence.services.product_value.summarize import summarize
    from intelligence.tests.product_value_fixtures import SOURCE_SERVER, build_protocol, ev, scenario_cohort_signals, ts
    from intelligence.tests.test_product_value_summarize import _six_pair_protocol, _clone_complete_pair
    def metric(summary, key):
        return next(m for m in summary["metrics"] if m["metric_id"] == key)
    def reuse_view(summary):
        return {"metric": metric(summary, "proactive_reuse_rate"), "criterion": next(c for c in summary["criteria_results"] if c["criterion_id"] == "proactive_reuse")}
    proto = _six_pair_protocol()
    proto.pop("protocol_hash")
    proto["criteria"]["cost"] = {"not_applicable_components": sorted(C.COST_COMPONENTS - {"writer_model", "review_model"})}
    proto = freeze_protocol(proto)
    complete, evidence = _clone_complete_pair(1, "p10", proto["protocol_hash"], provenance="imported")
    second, _ = _clone_complete_pair(2, "p11", proto["protocol_hash"], provenance="imported")
    stubs = [e for e in second if e["event_type"] in ("consent_changed", "assignment_created")]
    reader = InMemoryEvidenceReader.from_json(evidence)
    r1 = measure_pair(complete, proto, reader)
    variants = {}
    for source in ("frontend", "server"):
        terminals = []
        for e in second:
            if e["event_type"] == "task_completed":
                t = copy.deepcopy(e)
                t.update(event_type="task_abandoned", event_id=e["event_id"] + "-abandoned", source_channel=source, object_refs=[], run_ids=[])
                t["payload"].update(completion_evidence_refs=[], terminal_reason="user stopped; cost not measured")
                terminals.append(t)
        events = stubs + terminals
        r2 = measure_pair(events, proto, reader)
        assignments = [e for e in complete + stubs if e["event_type"] == "assignment_created"]
        variants[source] = {"terminals": terminals, "receipt_status": r2["status"], "receipt_limitations": r2["limitations"], "receipt_cost_items": r2["cost_items"], "receipt_unknown": r2["unknown_cost_components"], "tasks": r2["tasks"], "without_receipt": metric(summarize([r1], assignments, proto, cohort_events=complete + events, due_rechecks=[]), "cost_full_status"), "with_receipt": metric(summarize([r1, r2], assignments, proto, cohort_events=complete + events, due_rechecks=[]), "cost_full_status")}
    out["probes"]["terminal_without_cost_evidence"] = variants
    proto = build_protocol()
    src, _, _ = scenario_cohort_signals(proto["protocol_hash"], provenance="imported")
    rt = next(e for e in src if e["event_type"] == "reuse_observed" and e["participant_id"] == "p04")
    rf = next(e for e in src if e["event_type"] == "reuse_observed" and e["participant_id"] == "p05")
    consent = next(e for e in src if e["event_type"] == "consent_changed")
    cohort, future = [], []
    for i in range(1, 7):
        who = f"q{i}"
        cohort.append(ev("task_started", event_id=f"start-{who}", at=ts("09-15", "10:00:00"), channel=SOURCE_SERVER, participant=who, task=f"{who}-a", provenance="imported", payload={"task_id": f"{who}-a", "policy_version": "v1", "view_id": "view-task", "client_at": ts("09-15", "10:00:00"), "initiator": "participant"}))
        granted = copy.deepcopy(consent)
        granted.update(participant_id=who, event_id=f"consent-{who}")
        cohort.append(granted)
        row = copy.deepcopy(rt if i <= 3 else rf)
        row.update(participant_id=who, event_id=f"reuse-{who}")
        row["payload"].update(first_task_id=f"{who}-a", new_task_id=f"{who}-b", new_task_started_at=ts("09-23", "10:00:00"))
        if i <= 3:
            cohort.append(row)
        else:
            row.update(event_at=ts("10-10", "12:00:00"), recorded_at=ts("10-10", "12:00:00"))
            row["payload"].update(new_task_id=f"{who}-c", new_task_started_at=ts("10-09", "10:00:00"), observation_window={"start": ts("10-05", "00:00:00"), "end": ts("10-18", "23:59:59")})
            future.append(row)
    out["probes"]["future_window_removes_task_started_cohort"] = {"cohort": cohort, "added": future, "before": reuse_view(summarize([], [], proto, cohort_events=cohort, due_rechecks=[], as_of="2026-10-11")), "after": reuse_view(summarize([], [], proto, cohort_events=cohort + future, due_rechecks=[], as_of="2026-10-11"))}

print(json.dumps(out, ensure_ascii=False, indent=2))
