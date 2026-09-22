"""R5 financial-contract counterexamples: remove one guard, require assertion failures.

Isolated in-memory patches, no repository edits or model calls. The selected
regressions block Python sockets and use scripted models/providers. A load error,
zero selected tests, or a passing mutant is NOT evidence that a guard has teeth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
TEST = "intelligence/tests/test_financial_contracts_r5.py"
VARIANTS = {
    "cutoff_forwarding_removed": (
        "import intelligence.services.episode_factory as m\n"
        "m.requested_information_cutoff = lambda *a, **kw: None\n",
        "cutoff_role_reaches",
    ),
    "cutoff_provenance_removed": (
        "import intelligence.services.honesty_gates as m\n"
        "m._cutoff_instruction_text = lambda text: text\n",
        "non_cutoff_roles or material_boundaries",
    ),
    "report_year_role_removed": (
        "import re\nfrom datetime import date\n"
        "import intelligence.services.market_financials as m\n"
        "def first_year(text):\n"
        "    match = re.search(r'20\\d{2}', text)\n"
        "    return date(int(match[0]), 12, 31) if match else None\n"
        "m.target_report_end_from_query = first_year\n",
        "report_year_must",
    ),
    "cashflow_rows_removed": (
        "import intelligence.services.market_financials as m\n"
        "m.QUALITY_ROW_METRICS = ()\n",
        "all_financial_rows or complete_rows_have",
    ),
    "historical_disclosure_filter_removed": (
        "from dataclasses import replace\n"
        "import intelligence.services.financial_report_contract as m\n"
        "original = m.select_reports\n"
        "def unfiltered(bundle, **kwargs):\n"
        "    return replace(original(bundle, **kwargs), bundle=bundle)\n"
        "m.select_reports = unfiltered\n",
        "unconfirmed_disclosure",
    ),
    "report_binding_gate_removed": (
        "import intelligence.services.financial_report_contract as m\n"
        "m.report_binding_gaps = lambda *a, **kw: ()\n",
        "skipping_available or missing_cash_flow or candidate_with_no_numeric",
    ),
    "draft_period_check_removed": (
        "import intelligence.services.financial_report_contract as m\n"
        "m._mentions_period = lambda *a: True\n",
        "snapshot_expansion or local_report_gap",
    ),
    "calculation_product_gate_removed": (
        "import intelligence.services.financial_report_contract as m\n"
        "m.calculation_binding_gaps = lambda *a, **kw: ()\n",
        "unrelated_or_empty or required_ratio_missing",
    ),
    "calculation_id_binding_removed": (
        "import re\nimport intelligence.services.financial_report_contract as m\n"
        "m._CALC_REFERENCE = re.compile(r'(?!)')\n",
        "calculation_id_must",
    ),
    "conflicting_report_rows_accepted": (
        "import inspect\nimport intelligence.services.financial_report_contract as m\n"
        "source = inspect.getsource(m.select_reports)\n"
        "old = 'elif len(by_period[row.report_date]) > 1:'\n"
        "assert source.count(old) == 1\n"
        "exec(compile(source.replace(old, 'elif False:'), '<mutation>', 'exec'), m.__dict__)\n",
        "duplicate_period_rows",
    ),
    "calculation_error_projection_removed": (
        "from intelligence.services.research_tool_registry import ToolObservation\n"
        "ToolObservation.result_status_fields = lambda self: {'ok': True}\n",
        "domain_calculation_failure or actual_episode_exposes",
    ),
    "same_episode_calculation_cache_removed": (
        "import inspect\nimport intelligence.services.derived_calculation as m\n"
        "source = inspect.getsource(m.bind_derived_calculation_tool)\n"
        "old = 'record = records.get(base_calc_id)'\n"
        "assert source.count(old) == 1\n"
        "exec(compile(source.replace(old, 'record = None'), '<mutation>', 'exec'), m.__dict__)\n",
        "same_episode_can_reuse",
    ),
    "metric_obligation_optionalized": (
        "import intelligence.services.mandatory_satisfiability as m\n"
        "old = m.evidence_required_output_ids\n"
        "m.evidence_required_output_ids = lambda contract: old(contract) | frozenset({'metric_evidence'})\n",
        "local_report_gap or metric_is_not_downgraded",
    ),
    "all_financial_answers_rejected": (
        "import intelligence.services.financial_report_contract as m\n"
        "m.report_binding_gaps = lambda *a, **kw: ('blanket rejection',)\n",
        "bound_latest_pair_can_complete or later_success or explicitly_waived",
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    files = [TEST, "scripts/review_probes/run_financial_contract_mutations.py", *(
        f"intelligence/services/{name}.py" for name in (
            "derived_calculation", "episode_tools", "episode_verifier", "financial_report_contract",
            "honesty_gates", "mandatory_satisfiability", "market_financials", "research_harness",
            "research_tool_registry",
        )
    )]
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files}
    env = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
    results = {}
    for name, (patch, expression) in VARIANTS.items():
        junit = out / f"{name}.xml"
        selection = ["-q", TEST, "-k", expression, f"--junitxml={junit}"]
        code = patch + "\nimport pytest\nraise SystemExit(pytest.main(" + repr(selection) + "))\n"
        (out / f"{name}.py").write_text(code)
        with (out / f"{name}.log").open("w") as log:
            process = subprocess.run(
                [sys.executable, "-c", code], cwd=ROOT, env=env,
                stdout=log, stderr=subprocess.STDOUT,
            )
        counts = dict.fromkeys(("tests", "failures", "errors"), 0)
        for suite in ET.parse(junit).getroot().iter("testsuite") if junit.exists() else ():
            for key in counts:
                counts[key] += int(suite.get(key, "0"))
        results[name] = {"exit_code": process.returncode, **counts}
        (out / f"{name}.exit").write_text(f"{process.returncode}\n")
        print(name, results[name], flush=True)
    unchanged = all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in hashes.items())
    (out / "results.json").write_text(json.dumps({
        "revision": revision,
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "results": results, "sources_sha256": hashes, "sources_unchanged": unchanged,
    }, indent=2) + "\n")
    assert unchanged and all(
        r["exit_code"] == 1 and r["tests"] > 0 and r["failures"] > 0 and r["errors"] == 0
        for r in results.values()
    ), "require behavioral failures, not load errors/empty selections, for every removed guard"


if __name__ == "__main__":
    main()
