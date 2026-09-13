"""Read-only synthetic probes of round-4 candidate boundaries; no production IO."""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

track = sys.argv[1]
root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(os.environ.get("RESEARCH_EVOLUTION_QC_ROOT", "/tmp/research-evolution-round4-qc")) / track
sys.path.insert(0, str(root))
out = {"synthetic": True, "track": track, "root": str(root), "sha": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(), "probes": {}}

if track == "01":
    from intelligence.tests.test_judgment_maintenance_assess import _binding, _version, _run, _live
    def view(versions, *, as_of="2026-09-12", cutoff="2026-09-12"):
        result = _run([_binding({"ann:old": "h1"}, created_at="2026-09-10T12:00:00+08:00", baseline_cutoff="2026-09-10")], versions, as_of=as_of, cutoff=cutoff)
        return {"counts": result.counts, "pit_grade": result.pit_grade, "gaps": [g.reason for g in result.gaps], "live": [{"change": i.change_type, "status": i.status, "hash": [v.source_hash for v in i.current], "gaps": [g.reason for g in i.gaps]} for i in _live(result)]}
    mixed = [_version("ann:old", "h1", "2026-09-10T10:00:00"), _version("ann:old", "h2", "2026-09-10T10:00:00+08:00")]
    early, late = copy.deepcopy(mixed), copy.deepcopy(mixed)
    early[0]["recorded_at"] += "+09:00"
    late[0]["recorded_at"] += "+07:00"
    out["probes"]["incomparable_precision"] = {"input": mixed, "actual": view(mixed), "fill_early": view(early), "fill_late": view(late)}
    tie_high = [_version("ann:old", "h1", "2026-09-10T10:00:00+08:00"), _version("ann:old", "h0", "2026-09-10T10:00:00+08:00")]
    tie_low = copy.deepcopy(tie_high)
    tie_low[1]["source_hash"] = "h2"
    out["probes"]["tie_baseline_sorts_last"] = {"input": tie_high, "actual": view(tie_high), "other_hash_sorts_last": view(tie_low)}
    midnight = [_version("ann:old", "h1", "2026-09-10T10:00:00+08:00"), _version("ann:old", "h2", "2026-09-11T16:30:00Z")]
    normalized = copy.deepcopy(midnight)
    normalized[1]["recorded_at"] = "2026-09-12T00:30:00+08:00"
    out["probes"]["cross_midnight_representation"] = {"input": midnight, "actual": view(midnight, as_of="2026-09-11", cutoff="2026-09-11"), "same_instant_normalized": view(normalized, as_of="2026-09-11", cutoff="2026-09-11")}

if track == "05":
    from intelligence.services.product_value import contracts as C
    from intelligence.services.product_value.evidence import InMemoryEvidenceReader
    from intelligence.services.product_value.measure import measure_pair
    from intelligence.services.product_value.protocol import freeze_protocol
    from intelligence.services.product_value.summarize import summarize
    from intelligence.tests.test_product_value_summarize import _six_pair_protocol, _clone_complete_pair
    proto = _six_pair_protocol()
    proto.pop("protocol_hash")
    proto["criteria"]["cost"] = {"not_applicable_components": sorted(C.COST_COMPONENTS - {"writer_model", "review_model"})}
    proto = freeze_protocol(proto)
    complete, evidence = _clone_complete_pair(1, "p10", proto["protocol_hash"], provenance="imported")
    second, _ = _clone_complete_pair(2, "p11", proto["protocol_hash"], provenance="imported")
    reader = InMemoryEvidenceReader.from_json(evidence)
    r1 = measure_pair(complete, proto, reader)
    # Original workflow keeps genuine manual time/artifact facts; assisted workflow
    # has only consent + assignment + start/abandon timestamps, no run or usage log.
    original = [e for e in second if e["event_type"] == "consent_changed" or e.get("assistance_condition") == "original"]
    assisted = [e for e in second if e.get("assistance_condition") == "assisted" and e["event_type"] in ("assignment_created", "task_started")]
    for e in second:
        if e.get("assistance_condition") == "assisted" and e["event_type"] == "task_completed":
            t = copy.deepcopy(e)
            t.update(event_type="task_abandoned", event_id=e["event_id"] + "-abandoned", object_refs=[], run_ids=[])
            t["payload"].update(completion_evidence_refs=[], terminal_reason="abandoned; run and billing records unavailable")
            assisted.append(t)
    events = original + assisted
    r2 = measure_pair(events, proto, reader)
    assignments = [e for e in complete + events if e["event_type"] == "assignment_created"]
    def cost(receipts):
        s = summarize(receipts, assignments, proto, cohort_events=complete + events, due_rechecks=[])
        return next(m for m in s["metrics"] if m["metric_id"] == "cost_full_status")
    out["probes"]["timed_assisted_without_usage"] = {"input": events, "receipt_status": r2["status"], "receipt_limitations": r2["limitations"], "assisted_task": r2["tasks"]["assisted"], "cost_items": r2["cost_items"], "cost_unknown": r2["unknown_cost_components"], "before": cost([r1]), "after": cost([r1, r2])}

print(json.dumps(out, ensure_ascii=False, indent=2))
