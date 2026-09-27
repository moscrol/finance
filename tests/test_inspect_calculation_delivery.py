"""The saved-record inspector describes actual projection; it never executes code."""

import json

import pytest

from scripts.review_probes import inspect_calculation_delivery as probe


def test_nested_summary_reports_dropped_values_without_running_script(tmp_path):
    marker = tmp_path / "must-not-exist"
    record = {
        "exit_code": 0,
        "script": f"open({str(marker)!r}, 'w').write('unsafe')",
        "input_evidence_hashes": ["input-identity-only"],
        "result": {"schema": probe.artifacts.RESULT_SCHEMA_V1,
                   "summary": {"2026中报": {"ratio": 1.588}}, "tables": []},
    }
    report = probe.inspect_record(record, "| 2026中报 | 1.587 |")
    assert report["exit_code"] == 0
    assert report["dropped_summary_keys"] == ["2026中报"]
    assert report["normalized_summary"] == {}
    assert report["normalized_numeric_observations"] == []
    assert report["compact_result"] == ""
    assert report["raw_result"] == record["result"]
    assert report["answer_table_lines"] == ["| 2026中报 | 1.587 |"]
    assert "manual_required" in report["answer_comparison"]
    assert not marker.exists()


def test_valid_table_uses_existing_renderer_and_keeps_values():
    result = {"schema": probe.artifacts.RESULT_SCHEMA_V1, "summary": {"ratio": 1.588},
              "tables": [{"name": "含金量", "columns": ["报告期", "比率"],
                          "rows": [["2026中报", 1.588]]}]}
    report = probe.inspect_record({"result": result, "script": "rows=series('a','b')"})
    assert report["dropped_summary_keys"] == []
    assert report["normalized_summary"] == {"ratio": 1.588}
    assert report["normalized_table_count"] == 1
    assert ["含金量.比率[2026中报]", 1.588] in report["normalized_numeric_observations"]
    assert report["script_call_names_syntax_only"] == ["series"]
    assert "1.588" in report["compact_result"]


def test_cli_records_content_identity_and_is_read_only(tmp_path, capsys):
    calc = tmp_path / "calc.json"
    answer = tmp_path / "message.json"
    calc.write_text(json.dumps({"result": {"ratio": 1.588}}))
    answer.write_text(json.dumps({"content": "| H1 | 1.587 |"}))
    before = {p: p.read_bytes() for p in (calc, answer)}
    assert probe.main([str(calc), "--answer", str(answer)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert len(report["input_sha256"]) == len(report["answer_sha256"]) == 64
    assert report["answer_table_lines"] == ["| H1 | 1.587 |"]
    assert all(p.read_bytes() == raw for p, raw in before.items())


@pytest.mark.parametrize("record", [[], {}, {"result": []}])
def test_uninspectable_record_is_not_success(tmp_path, capsys, record):
    calc = tmp_path / "calc.json"
    calc.write_text(json.dumps(record))
    assert probe.main([str(calc)]) == 2
    assert not capsys.readouterr().out
