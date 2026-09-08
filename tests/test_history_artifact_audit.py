"""Independent saved-fact arithmetic must reject mutated research results."""

from copy import deepcopy
import hashlib
import json

import pytest

from scripts.audit_historical_research_artifacts import audit_artifact, main


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def seal(doc):
    fingerprints = {k: digest(v) for k, v in doc["inputs"].items()}
    fingerprints["calendar_inputs"] = digest(doc["calendar_inputs"])
    doc["input_fingerprint"] = digest(fingerprints)
    doc["query_id"] = digest(
        [doc["spec"], fingerprints, doc["schema_version"], doc["feature_definitions"]]
    )
    doc["source_refs"] = [
        {
            "table": k,
            "row_count": len(v),
            "input_fingerprint": digest(v),
            "snapshot_ids": [],
        }
        for k, v in doc["inputs"].items()
    ]
    doc["preview"] = deepcopy(doc["rows"][:1])
    return doc


@pytest.fixture
def artifact(tmp_path):
    days = ["2026-01-05", "2026-01-06", "2026-01-07"]
    rows = []
    for start, value, x in [(days[0], -1.0, True), (days[1], -10.0, False)]:
        rows.append(
            {
                "entity_code": "A.FP",
                "start": start,
                "end": days[1],
                "features": {"return_pct": value},
                "feature_coverage": {
                    "return_pct": {
                        "status": "complete",
                        "expected_dates": 2 if x else 1,
                    }
                },
                "x": x,
                "y": True,
                "forward_return_pct": 10.0,
                "outcome_end": days[2],
                "comparison_state": "observed",
            }
        )
    doc = seal(
        {
            "schema_version": "historical-research-v1",
            "spec": {
                "operation": "compare_cases",
                "entity_kind": "sector",
                "features": ["return_pct"],
                "entity_codes": ["A.FP"],
                "condition": {"feature": "return_pct", "op": "gte", "value": -5},
                "outcome": {"horizon_days": 1, "threshold_pct": 0},
            },
            "feature_definitions": {
                "return_pct": {
                    "fields": ["pct_chg"],
                    "unit": "percent",
                    "rule": "compound every daily percentage in the declared window",
                    "version": "history-features-v1",
                    "entity_kind": "sector",
                }
            },
            "definition_refs": [
                "historical-research-v1",
                "history-features-v1",
                "return_pct@history-features-v1",
            ],
            "inputs": {
                "fact_sector_daily": [
                    {"trade_date": d, "sector_ts_code": "A.FP", "pct_chg": pct}
                    for d, pct in zip(days, [10, -10, 10], strict=True)
                ]
            },
            "calendar_inputs": [
                {
                    "start": days[0],
                    "end": days[-1],
                    "stock_dates": days,
                    "market_dates": days,
                }
            ],
            "rows": rows,
            "total_matched": 2,
            "returned_count": 1,
            "truncated": True,
            "comparison": {
                "four_cells": {
                    "x_true_y_true": 1,
                    "x_true_y_false": 0,
                    "x_false_y_true": 1,
                    "x_false_y_false": 0,
                },
                "enumerated": 2,
                "missing": 0,
                "immature": 0,
            },
        }
    )
    path = tmp_path / "history-query-fixture.json"
    path.write_text(json.dumps(doc))
    return path, doc


def write(path, doc):
    path.write_text(json.dumps(doc))
    return audit_artifact(path)


def test_recomputes_complete_rows_beyond_preview_and_default_cli_is_read_only(
    artifact, capsys
):
    path, _ = artifact
    before = path.read_bytes()
    receipt = audit_artifact(path)
    assert receipt["result"] == "checked"
    assert receipt["calculation_checks"]["return_pct"] == 2
    assert receipt["calculation_checks"]["forward_return_pct"] == 2
    assert receipt["calculation_checks"]["four_cell_summary"] == 1
    assert main([str(path.parent)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["certification_eligible"] is False
    assert path.read_bytes() == before
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize(
    "mutation,field",
    [
        (lambda d: d["rows"][1]["features"].update(return_pct=123), "return_pct"),
        (lambda d: d["comparison"]["four_cells"].update(x_true_y_true=9), "four_cells"),
        (
            lambda d: d["inputs"]["fact_sector_daily"][0].update(pct_chg=11),
            "input_fingerprint",
        ),
        (lambda d: d["rows"][0].update(y=False), "y"),
    ],
)
def test_corrupt_results_inputs_and_four_cells_are_nonzero(
    artifact, mutation, field, capsys
):
    path, doc = artifact
    mutation(doc)
    result = write(path, doc)
    assert result["result"] == "error"
    assert any(e["field"] == field for e in result["errors"])
    assert main([str(path)]) == 1
    capsys.readouterr()


def test_duplicate_reads_are_explicit_and_conflicting_facts_rejected(artifact):
    path, doc = artifact
    doc["inputs"]["fact_sector_daily"].append(
        deepcopy(doc["inputs"]["fact_sector_daily"][0])
    )
    result = write(path, seal(doc))
    assert result["result"] == "checked"
    assert result["duplicate_facts"]["fact_sector_daily"]["identical_repeats"] == 1
    doc["inputs"]["fact_sector_daily"][-1]["pct_chg"] = 999
    result = write(path, seal(doc))
    assert result["result"] == "error"
    assert any(e["field"] == "duplicate_fact_key" for e in result["errors"])


def test_unsupported_versions_do_not_claim_calculation_success(artifact, capsys):
    path, doc = artifact
    doc["schema_version"] = "historical-research-v999"
    result = write(path, doc)
    assert result["result"] == "unsupported"
    assert not result["calculation_checks"]
    assert result["skips"]
    assert main([str(path)]) == 2
    capsys.readouterr()


def test_unknown_feature_version_is_skipped_even_with_familiar_feature_name(artifact):
    path, doc = artifact
    doc["feature_definitions"]["return_pct"]["version"] = "history-features-v999"
    result = write(path, seal(doc))
    assert "return_pct" not in result["calculation_checks"]
    assert "condition_x" not in result["calculation_checks"]
    assert any(s["reason"] == "unsupported_feature_version" for s in result["skips"])


def test_unknown_feature_version_still_rejects_impossible_missing_state(
    artifact, capsys
):
    path, doc = artifact
    doc["feature_definitions"]["return_pct"]["version"] = "history-features-v999"
    doc["rows"][0].update(x=None, y=True, comparison_state="missing_feature")
    doc["comparison"]["four_cells"]["x_true_y_true"] = 0
    doc["comparison"]["missing"] = 1
    result = write(path, seal(doc))
    assert any(e["field"] == "comparison_state_contract" for e in result["errors"])
    assert main([str(path)]) == 1
    capsys.readouterr()


def test_null_claim_with_complete_facts_is_an_error(artifact):
    path, doc = artifact
    doc["rows"][0]["features"]["return_pct"] = None
    result = write(path, doc)
    assert any(e["field"] == "return_pct" for e in result["errors"])


@pytest.mark.parametrize(
    "text",
    [
        '{"rows":',
        '{"schema_version":1,"schema_version":2}',
        '{"bad":NaN}',
        '{"schema_version":"historical-research-v1","query_id":1e309}',
        "[]",
    ],
)
def test_bad_json_and_duplicate_object_keys_fail_closed(tmp_path, text, capsys):
    path = tmp_path / "bad.json"
    path.write_text(text)
    assert main([str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["artifacts"][0]["errors"]


def test_digest_filename_tampering_and_overwriting_inputs_are_rejected(
    artifact, capsys
):
    path, doc = artifact
    original = path.read_bytes()
    renamed = path.with_name(
        f"history-query-{hashlib.sha256(original).hexdigest()}.json"
    )
    path.rename(renamed)
    assert audit_artifact(renamed)["result"] == "checked"
    renamed.write_text(json.dumps(doc, indent=2))
    assert any(e["field"] == "file_sha256" for e in audit_artifact(renamed)["errors"])
    assert main([str(renamed), "--output", str(renamed)]) == 1
    capsys.readouterr()


def test_missing_paths_and_empty_run_directory_are_errors(tmp_path, capsys):
    assert main([str(tmp_path)]) == 1
    capsys.readouterr()
    assert main([str(tmp_path / "missing.json")]) == 1
    capsys.readouterr()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(inputs=[]),
        lambda d: d["comparison"]["four_cells"].update(x_true_y_true=True),
    ],
)
def test_malformed_shapes_and_counts_are_reported_not_raised(
    artifact, mutation, capsys
):
    path, doc = artifact
    mutation(doc)
    path.write_text(json.dumps(doc))
    assert main([str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["summary"]["errors"] > 0


def test_finite_inputs_that_overflow_compounding_fail_with_json_receipt(
    artifact, capsys
):
    path, doc = artifact
    for row in doc["inputs"]["fact_sector_daily"]:
        row["pct_chg"] = 1e308
    write(path, seal(doc))
    assert main([str(path)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert any(
        "non-finite independent calculation" in e.get("reason", "")
        for e in report["artifacts"][0]["errors"]
    )
