from __future__ import annotations

import json

import pytest

from scripts.measure_sector_member_latency import (
    main,
    project_wall_clock,
    select_probe_batches,
    select_probe_sectors,
)


def test_select_probe_sectors_spans_small_median_high_and_largest_counts() -> None:
    counts = (5, 10, 20, 40, 80, 160, 320, 640, 1204)
    sectors = [
        {"ts_code": f"BK{index:04d}", "name": f"板块{index}", "stock_count": count}
        for index, count in enumerate(counts)
    ]

    selected = select_probe_sectors(sectors)

    assert [row["stock_count"] for row in selected] == [5, 80, 640, 1204]


def test_project_wall_clock_uses_batch_p95_for_nightly_projection() -> None:
    projection = project_wall_clock(
        sector_count=407,
        batch_size=10,
        batch_elapsed_seconds=(8, 10, 12, 14),
        nightly_window_seconds=7200,
    )

    assert projection == {
        "batches": 41,
        "batch_p50_seconds": 11.0,
        "batch_p95_seconds": 14.0,
        "projected_seconds": 574.0,
        "nightly_window_seconds": 7200.0,
        "fits_nightly_window": True,
    }


def test_select_probe_batches_centres_windows_and_deduplicates_tail() -> None:
    sectors = [
        {"ts_code": f"BK{index:04d}", "stock_count": count}
        for index, count in enumerate((5, 10, 20, 40, 80, 160, 320, 640, 1204))
    ]

    batches = select_probe_batches(sectors, batch_size=3)

    assert batches == (
        ("BK0000", "BK0001", "BK0002"),
        ("BK0003", "BK0004", "BK0005"),
        ("BK0006", "BK0007", "BK0008"),
    )


@pytest.mark.parametrize(
    ("failing_stage", "expected_stage"),
    (("list", "list_sectors"), ("individual", "individual_probe"), ("batch", "batch_probe")),
)
def test_probe_sanitises_provider_failures_without_leaving_a_receipt(
    tmp_path, capsys, failing_stage: str, expected_stage: str
) -> None:
    canary = f"SECRET_PROVIDER_CANARY_{failing_stage}"

    class FailingProvider:
        def list_sectors(self, *, trade_date: str):
            if failing_stage == "list":
                raise RuntimeError(canary)
            return [
                {"ts_code": f"BK{index:04d}", "name": f"板块{index}", "stock_count": count}
                for index, count in enumerate((1, 2, 3, 4, 5, 6, 7, 8, 9))
            ]

        def get_sector_stocks(self, code: str, *, trade_date: str):
            if failing_stage == "individual":
                raise RuntimeError(canary)
            count = int(code.removeprefix("BK")) + 1
            return {"stocks": [{"ts_code": f"S{item:04d}"} for item in range(count)]}

        def get_sector_stocks_batch(self, codes, *, trade_date: str, batch: int):
            if failing_stage == "batch":
                raise RuntimeError(canary)
            return {}

    output = tmp_path / "receipt.json"
    output.write_text("stale receipt", encoding="utf-8")

    exit_code = main(
        ["--trade-date", "2026-07-28", "--output", str(output)],
        provider=FailingProvider(),
    )
    captured = capsys.readouterr()

    assert exit_code == 3
    assert captured.out == ""
    assert canary not in captured.err
    assert json.loads(captured.err) == {
        "error_code": "provider_exception",
        "exception_type": "RuntimeError",
        "stage": expected_stage,
    }
    assert not output.exists()


@pytest.mark.parametrize("invalid_response", ("empty", "missing_code", "empty_st", "count_mismatch"))
def test_probe_rejects_incomplete_batch_responses(
    tmp_path, capsys, invalid_response: str
) -> None:
    sectors = [
        {"ts_code": f"BK{index:04d}", "name": f"板块{index}", "stock_count": count}
        for index, count in enumerate((1, 2, 3, 4, 5, 6, 7, 8, 9))
    ]

    class BatchProvider:
        def list_sectors(self, *, trade_date: str):
            return sectors

        def get_sector_stocks(self, code: str, *, trade_date: str):
            count = int(code.removeprefix("BK")) + 1
            return {"stocks": [{"ts_code": f"S{item:04d}"} for item in range(count)]}

        def get_sector_stocks_batch(self, codes, *, trade_date: str, batch: int):
            if invalid_response == "empty":
                return {}
            response = {
                code: {
                    "st": [
                        {"c": f"S{item:04d}"}
                        for item in range(int(code.removeprefix("BK")) + 1)
                    ]
                }
                for code in codes
            }
            if invalid_response == "missing_code":
                response.pop(codes[-1])
            elif invalid_response == "empty_st":
                response[codes[0]]["st"] = []
            elif invalid_response == "count_mismatch":
                response[codes[-1]]["st"].pop()
            return response

    output = tmp_path / "receipt.json"
    output.write_text("stale receipt", encoding="utf-8")

    exit_code = main(
        ["--trade-date", "2026-07-28", "--output", str(output)],
        provider=BatchProvider(),
    )
    captured = capsys.readouterr()

    assert exit_code == 3
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error_code": "provider_contract_error",
        "exception_type": "InvalidBatchResponse",
        "stage": "batch_probe",
    }
    assert not output.exists()


def test_probe_writes_receipt_only_after_complete_batch_validation(tmp_path, capsys) -> None:
    sectors = [
        {"ts_code": f"BK{index:04d}", "name": f"板块{index}", "stock_count": count}
        for index, count in enumerate((1, 2, 3, 4, 5, 6, 7, 8, 9))
    ]

    class CompleteProvider:
        def list_sectors(self, *, trade_date: str):
            return sectors

        def get_sector_stocks(self, code: str, *, trade_date: str):
            count = int(code.removeprefix("BK")) + 1
            return {"stocks": [{"ts_code": f"S{item:04d}"} for item in range(count)]}

        def get_sector_stocks_batch(self, codes, *, trade_date: str, batch: int):
            return {
                code: {
                    "st": [
                        {"c": f"S{item:04d}"}
                        for item in range(int(code.removeprefix("BK")) + 1)
                    ]
                }
                for code in codes
            }

    output = tmp_path / "receipt.json"

    exit_code = main(
        ["--trade-date", "2026-07-28", "--output", str(output)],
        provider=CompleteProvider(),
    )
    captured = capsys.readouterr()
    receipt = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out) == receipt["projection"]
    assert sorted(receipt) == [
        "batch_size",
        "individual_probes",
        "projection",
        "schema_version",
        "sector_count",
        "trade_date",
    ]
    assert receipt["schema_version"] == 1
    assert receipt["sector_count"] == 9
    assert all(probe["count_matches"] for probe in receipt["individual_probes"])
    assert receipt["projection"]["fits_nightly_window"] is True
