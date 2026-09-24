"""Result-format success must mean renderable data, not just exit 0.

The nested-summary shape comes from run_20260918_124033_015953; values here
are a minimal frozen reproduction, not a new provider fetch or a live verdict.
"""

from copy import deepcopy

import pytest

from intelligence.services import derived_calculation as dc
from intelligence.services import derived_calculation_artifacts as art
from intelligence.tests.test_derived_calculation import _inputs


BAD_RESULT = {
    "schema": art.RESULT_SCHEMA_V1,
    "summary": {"2026中报": {"OCF": 706.91, "净利": 445.17, "含金量": 1.588}},
    "tables": [],
    "charts": [],
    "params": {},
    "formulas": [],
    "notes": [],
}
GOOD_RESULT = {
    "schema": art.RESULT_SCHEMA_V1,
    "summary": {},
    "tables": [
        {
            "name": "现金流比率",
            "columns": ["报告期", "含金量"],
            "rows": [["2026中报", 1.588], ["2025中报", None]],
        }
    ],
}


def test_frozen_nested_summary_is_not_success_or_derived_evidence():
    # Real sandbox; the producer is unchanged, admission validates its output.
    outcome = dc.run_derived_calculation(
        script=f"emit({BAD_RESULT!r})",
        purpose="现金流含金量",
        evidence=_inputs(),
    )
    assert isinstance(outcome, dc.CalculationError)
    assert outcome.code == "invalid_result_contract"
    assert outcome.retryable_by_rewriting
    result = dc.to_tool_result(outcome)
    assert result.trace.status == "error" and result.evidence == ()
    assert "summary" in result.observation and "tables" in result.observation
    assert "derived_calculation" not in result.telemetry
    assert result.telemetry["calculation_error"]["code"] == outcome.code


@pytest.mark.parametrize(
    "result,code",
    [
        (BAD_RESULT, "summary_non_scalar"),
        (
            {"schema": "derived_calculation.result/v99", "summary": {"v": 1}},
            "unsupported_result_schema",
        ),
        ({"schema": art.RESULT_SCHEMA_V1}, "no_renderable_result"),
        ({"schema": art.RESULT_SCHEMA_V1, "summary": []}, "summary_not_object"),
        (
            {"schema": art.RESULT_SCHEMA_V1, "summary": {"ratio": float("nan")}},
            "summary_non_scalar",
        ),
        (
            {"schema": art.RESULT_SCHEMA_V1, "tables": "private-path"},
            "tables_not_array",
        ),
        ({"schema": art.RESULT_SCHEMA_V1, "tables": [42]}, "table_not_object"),
        (
            {
                "schema": art.RESULT_SCHEMA_V1,
                "tables": [{"columns": ["v", "v"], "rows": [[1, 2]]}],
            },
            "table_columns_invalid",
        ),
        (
            {
                "schema": art.RESULT_SCHEMA_V1,
                "tables": [{"columns": ["v"], "rows": [[1, 2]]}],
            },
            "table_row_width",
        ),
        (
            {
                "schema": art.RESULT_SCHEMA_V1,
                "tables": [{"columns": ["v"], "rows": [{"other": 1}]}],
            },
            "table_row_keys",
        ),
        (
            {
                "schema": art.RESULT_SCHEMA_V1,
                "tables": [{"columns": ["v"], "rows": [[{"lost": 1}]]}],
            },
            "table_non_scalar",
        ),
        (
            {
                "schema": art.RESULT_SCHEMA_V1,
                "charts": [{"x": ["Q1"], "series": {"v": [1, 2]}}],
            },
            "chart_series_invalid",
        ),
        (
            {
                "schema": art.RESULT_SCHEMA_V1,
                "charts": [{"x": ["Q1"], "series": {"v": [1]}, "kind": []}],
            },
            "chart_series_invalid",
        ),
        (
            {"schema": art.RESULT_SCHEMA_V1, "notes": ["data missing"]},
            "no_renderable_result",
        ),
        (
            {"schema": art.RESULT_SCHEMA_V1, "summary": {"v": 1}, "hidden": {"v": 2}},
            "unsupported_result_fields",
        ),
        ({}, "no_renderable_result"),
    ],
)
def test_invalid_result_has_stable_codes_without_private_values(result, code):
    before = deepcopy(result)
    errors = art.result_contract_errors(result)
    assert code in errors
    assert "private-path" not in str(errors)
    assert result == before  # validator does not mutate archived data


@pytest.mark.parametrize(
    "result",
    [
        GOOD_RESULT,
        {
            "schema": art.RESULT_SCHEMA_V1,
            "summary": {"value": None, "consistent": False},
        },
        {
            "schema": art.RESULT_SCHEMA_V1,
            "charts": [{"kind": "bar", "x": ["Q1"], "series": {"v": [1]}}],
        },
        {"diff": 1.44, "inputs": ["E1", "E2"]},  # legacy emit still works
    ],
)
def test_valid_result_is_not_blanket_rejected(result):
    assert art.result_contract_errors(result) == ()


def test_valid_table_keeps_exact_cells_in_csv_html_and_observations():
    calc = dc.run_derived_calculation(
        script=f"emit({GOOD_RESULT!r})",
        purpose="现金流含金量",
        evidence=_inputs(),
    )
    assert isinstance(calc, dc.DerivedCalculation)
    result = dc.to_tool_result(calc)
    assert result.trace.status == "success"
    assert [(o.metric, o.value) for o in result.evidence[0].observations] == [
        ("现金流比率.含金量[2026中报]", 1.588),
    ]
    files = {f.renderer: f.content for f in art.artifact_files(calc.to_dict())}
    assert "2026中报,1.588\n" in files["table"]
    assert "<td>2026中报</td><td>1.588</td>" in files["html"]
    assert "2025中报,\n" in files["table"]
    assert "<td>2025中报</td><td>缺</td>" in files["html"]


def test_legacy_archive_inspection_still_exposes_the_loss():
    # Don't silently migrate sealed failures into new successes.
    view = art.normalize_result(BAD_RESULT)
    assert view.summary == {} and not view.tables
    assert art.numeric_observations(view) == ()
