"""Independent offline boundary probes; only fixture constructors are reused."""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

track = sys.argv[1]
root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(os.environ.get("RESEARCH_EVOLUTION_QC_ROOT", str(Path(__file__).parent))) / track
sys.path.insert(0, str(root))
out = {"synthetic": True, "root": str(root), "sha": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(), "probes": {}}

if track == "01":
    from intelligence.services import judgment_maintenance as jm
    from intelligence.tests.test_judgment_maintenance_assess import _binding, _version, _run
    from intelligence.tests.test_judgment_maintenance_actions import _cmd

    def view(rep):
        return {"counts": rep.counts, "gaps": [g.reason for g in rep.gaps], "items": [{"id": i.id, "version": i.item_version, "day": i.first_known_day, "status": i.status, "supersedes": i.supersedes_item_id, "current": [v.source_hash for v in i.current]} for i in rep.items], "management_log": rep.management_log}

    stamps = {}
    vs = [_version("ann:old", "h1", "2026-09-12T00:00:00+08:00")]
    for stamp in ("2026-09-11T16:30:00Z", "2026-09-12T00:30:00+08:00", "2026-09-12T00:30:00+14:00", "2026-09-11T18:30:00+08:00"):
        b = _binding({"ann:old": "h1"}, created_at=stamp, baseline_cutoff="2026-09-12")
        try:
            stamps[stamp] = {"accepted": True, "report": view(_run([b], vs))}
        except jm.MaintenanceContractError as exc:
            stamps[stamp] = {"accepted": False, "error": exc.code}
    out["probes"]["binding_validation_market_day"] = stamps

    b = _binding({"ann:old": "h1"}, created_at="2026-09-10T12:00:00+08:00", baseline_cutoff="2026-09-10")
    vs = [_version("ann:old", "h1", "2026-09-10T09:00:00+08:00"), _version("ann:old", "h2", "2026-09-10T20:00:00+08:00"), _version("ann:old", "h0", "2026-09-11", expired_at="2026-09-12T10:00:00+08:00")]
    r = _run([b], vs)
    by_id = {i.id: i for i in r.items}
    cycles = []
    for item in r.items:
        seen = []
        pointer = item.id
        while pointer in by_id:
            if pointer in seen:
                cycles.append(seen + [pointer])
                break
            seen.append(pointer)
            pointer = by_id[pointer].supersedes_item_id
    out["probes"]["resolution_supersedes_cycle"] = {"input": vs, "report": view(r), "cycles": cycles}

    # A (clear) -> B (ambiguous) -> A. Test management replay, not merely assess.
    vs = [_version("ann:old", "h1", "2026-09-10T09:00:00+08:00"),
          _version("ann:old", "h2", "2026-09-10T20:00:00", valid_from="2026-09-02"),
          _version("ann:old", "h0", "2026-09-11T00:30:00+08:00", valid_from="2026-09-02", expired_at="2026-09-12T10:00:00+08:00")]
    before = _run([b], vs[:3], as_of="2026-09-10", cutoff="2026-09-10")
    first = next(i for i in before.items if i.status == "open")
    cmd = _cmd(first, "qc-r6-old-snooze", "snooze", acted_at="2026-09-10T22:00:00+08:00", snooze_until="2026-09-20T09:00:00+08:00")
    accepted = jm.validate_action(item=first, command=cmd, owner_user_id="alice", now="2026-09-10T22:00:00+08:00")
    after = _run([b], vs[:3], as_of="2026-09-12", cutoff="2026-09-12")
    reduced = jm.reduce_actions(report=after, events=[accepted.event.to_dict()], now="2026-09-12T22:00:00+08:00")
    out["probes"]["old_action_after_resolution"] = {"before": view(before), "after_assess": view(after), "after_reduce": view(reduced)}

elif track == "05":
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
    reader = InMemoryEvidenceReader.from_json({"runs": evidence1["runs"] + evidence2["runs"]})
    r1 = measure_pair(complete, proto, reader)
    fees = [e for e in second if e["event_type"] == "cost_recorded" and e["payload"]["cost_item"]["coverage_scope"] == "run"]
    template = next(e for e in fees if e["payload"]["cost_item"]["component"] == "writer_model")
    base = [e for e in second if e["event_type"] != "cost_recorded"]
    tool = copy.deepcopy(template)
    tool["event_id"] = "qc-r6-run-tool-fee"
    tool["payload"]["cost_item"].update(cost_id="qc-r6-tool", component="tool", amount=0.01, quantity=1, unit="calls", evidence_ref="invoice:tool")
    writer = next(e for e in fees if e["payload"]["cost_item"]["component"] == "writer_model")
    review = next(e for e in fees if e["payload"]["cost_item"]["component"] == "review_model")

    def result(extra):
        events = base + extra
        r2 = measure_pair(events, proto, reader)
        summary = summarize([r1, r2], [e for e in complete + events if e["event_type"] == "assignment_created"], proto, cohort_events=complete + events, due_rechecks=[])
        return {"receipt": r2, "cost": next(m for m in summary["metrics"] if m["metric_id"] == "cost_full_status")}

    out["probes"]["run_component_coverage"] = {"no_fees": result([]), "tool_only": result([tool]), "writer_tool": result([writer, tool]), "all_components": result([writer, review, tool])}

print(json.dumps(out, ensure_ascii=False, indent=2))
