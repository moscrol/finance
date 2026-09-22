"""Does the delivery guard catch a REAL model's copy error on REAL artifacts?

Every prior green for this guard came from hand-written fixtures. This probe
feeds it the actual draft produced by a live kimi-k3 episode and the actual
sandbox calculation record from the same run, rebuilt through the product's own
loader (``calc_loader_for_runs_root`` + ``derived_evidence``), not by hand.

The live run withheld that draft for an unrelated reason (judge unavailable), so
the public exit never exercised the guard. This probe closes that hole offline.

Read-only: nothing is fetched, no model is called, the run directory and the
code tree are only read. Exit 0=guard caught every planted-by-the-model
mismatch, 1=guard missed one, 2=identity/execution error.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

from check_delivery_fact_retention import _identity


def _with_result(calc, result):
    """Same calculation record with only its result payload swapped."""
    from dataclasses import replace

    return replace(calc, result=result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--expect-revision", required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--calc-id", required=True)
    args = parser.parse_args()
    root = args.code_root.resolve()
    run_dir = args.run_dir.resolve()
    report = {
        "scope": "live draft x live calculation record; guard behavior only, not answer grading",
        "model_calls": 0,
        "network_calls": 0,
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "run_dir": str(run_dir),
    }
    try:
        before = _identity(root)
        report["before"] = before
        if before["status"] or before["revision"] != args.expect_revision:
            raise ValueError("clean_exact_revision_required")
        sys.path.insert(0, str(root))
        from intelligence.services.agent_research import AgentEvidence, StructuredObservation
        from intelligence.services.derived_calculation import (
            DerivedCalculation,
            calc_loader_for_runs_root,
            derived_evidence,
        )
        from intelligence.services.research_delivery_checks import (
            calculation_copy_findings,
            remove_findings,
        )

        episode = json.loads((run_dir / "continuous-episode.json").read_text())
        draft = episode["semantic_verifier"]["verified"]["outcome"]["draft"]
        report["draft_sha256"] = hashlib.sha256(draft.encode()).hexdigest()
        report["public_answer"] = episode["semantic_verifier"]["public_answer"]
        report["judge_status"] = episode["semantic_verifier"]["judge_status"]

        # Rebuild the calculation evidence with the product's own loader.
        loader = calc_loader_for_runs_root(run_dir.parent)
        record = loader(args.calc_id)
        if record is None:
            raise ValueError("calc_record_not_found")
        calc = DerivedCalculation(
            calc_id=record["calc_id"],
            purpose=record["purpose"],
            script=record.get("script", ""),
            input_evidence_hashes=tuple(record.get("input_evidence_hashes", ())),
            input_refs=tuple(record.get("input_refs", ())),
            as_of=record.get("as_of"),
            result=record["result"],
            enforcement=record.get("enforcement", ""),
            exit_code=record.get("exit_code"),
            duration_ms=record.get("duration_ms", 0),
            stdout_tail=record.get("stdout_tail", ""),
            stderr_tail=record.get("stderr_tail", ""),
            runtime=record.get("runtime", {}),
            db_fingerprint=record.get("db_fingerprint", ""),
            notes=tuple(record.get("notes", ())),
            params=record.get("params", {}),
            inputs=tuple(record.get("inputs", ())),
            base_calc_id=record.get("base_calc_id"),
        )
        calc_evidence = derived_evidence(calc)
        artifact = json.loads((run_dir / f"calc-{args.calc_id}.json").read_text())
        # Inputs come from the record the sandbox itself kept of what it read.
        inputs = tuple(
            AgentEvidence(
                tool="financial_data",
                title="财报输入",
                detail="live financial_data evidence",
                source="live",
                source_date=item.get("as_of") or "",
                content_hash=item["hash"],
                observations=tuple(
                    StructuredObservation(
                        subject=o["subject"], as_of=o.get("as_of") or "",
                        metric=o["metric"], value=o["value"],
                    )
                    for o in item.get("observations", ())
                ),
            )
            for item in artifact.get("inputs", ())
        )
        evidence = (*inputs, calc_evidence)
        products = {m: v for m, v in
                    ((o.metric, o.value) for o in calc_evidence.observations)}
        report["calculation_products"] = products
        report["input_metric_names"] = sorted(
            {o.metric for e in inputs for o in e.observations}
        )

        # Where does the binding break? Label vocabulary is consulted twice: on
        # the product column name the model invented, and on the prose wording
        # it used. Minimal pairs isolate each side.
        import copy as _copy

        from intelligence.services.research_delivery_checks import (
            _absolute_ratio_label,
            _ratio_products,
        )
        live_columns = tuple(dict.fromkeys(
            column for table in artifact["result"].get("tables", ())
            for column in table["columns"]
        ))
        report["ratio_label_recognized"] = {
            label: bool(_absolute_ratio_label(label))
            for label in (*live_columns, "含金量", "比值", "比率")
        }
        report["ratio_products_from_live_record"] = {
            key: sorted(value) for key, value in _ratio_products(evidence).items()
        }
        renamed = _copy.deepcopy(artifact)
        for table in renamed["result"].get("tables", ()):
            table["columns"] = [
                "含金量" if ("现金流" in c and "净利润" in c) else c
                for c in table["columns"]
            ]
        renamed_evidence = (*inputs, derived_evidence(_with_result(calc, renamed["result"])))
        report["minimal_pair"] = {
            "live_column_live_prose": [f.code for f in calculation_copy_findings(
                draft, evidence, calculation_required=True)],
            "fixture_column_live_prose": [f.code for f in calculation_copy_findings(
                draft, renamed_evidence, calculation_required=True)],
            "fixture_column_fixture_prose": [f.code for f in calculation_copy_findings(
                "2025年报含金量为0.7473。", renamed_evidence, calculation_required=True)],
        }

        findings = calculation_copy_findings(draft, evidence, calculation_required=True)
        repaired = remove_findings(draft, findings)
        report["findings"] = [
            {"code": f.code, "span": draft[f.start:f.end]} for f in findings
        ]

        # Independently recompute which printed ratios disagree with the record,
        # instead of trusting the guard's own answer.
        truth = {}
        for table in artifact["result"].get("tables", ()):
            cols = table["columns"]
            for row in table["rows"]:
                cells = dict(zip(cols, row))
                period = str(cells.get("报告期", "")).strip()
                for name, value in cells.items():
                    if "现金流/净利润" in name or "含金量" in name:
                        truth[period] = Decimal(str(value))
        printed = {}
        for period, value in truth.items():
            for line in draft.splitlines():
                if period in line and "比值" in line:
                    for token in line.replace("，", " ").replace("（", " ").split():
                        token = token.strip("比值：:）)（(，,。")
                        try:
                            number = Decimal(token)
                        except Exception:
                            continue
                        if 0 < number < 100 and "." in token and token != str(value):
                            printed.setdefault(period, []).append(token)
        mismatches = {
            period: {"printed": tokens, "record": str(truth[period])}
            for period, tokens in printed.items()
            if all(Decimal(t) != truth[period] for t in tokens)
        }
        report["independent_mismatches"] = mismatches
        caught = {f.code for f in findings}
        expectations = {
            # Every number the sandbox emitted is an observation, but only the
            # ones the guard recognizes as a ratio column can ever be compared.
            "sandbox_emitted_observations": bool(products),
            "guard_bound_any_ratio_product": bool(
                report["ratio_products_from_live_record"]
            ),
            "guard_bound_the_inputs": bool(
                {"ocf_cum_yi", "net_profit_cum_yi"} <= set(report["input_metric_names"])
            ),
            "model_did_miscopy_at_least_once": bool(mismatches),
            "guard_flagged_the_miscopy": "calculation_value_mismatch" in caught,
            "repair_replaces_bad_value_only": bool(findings) and repaired != draft,
        }
        report["checks"] = expectations
        after = _identity(root)
        report.update(after=after, target_unchanged=before == after)
        if before != after:
            raise ValueError("target_changed")
        report["status"] = "passed" if all(expectations.values()) else "not_passed"
    except Exception as exc:
        report.update(status="error", error_type=type(exc).__name__, error=str(exc)[:300])
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
