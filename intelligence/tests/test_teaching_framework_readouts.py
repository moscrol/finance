from __future__ import annotations

import duckdb

from intelligence.services.methodology_backtest.store import ensure_schema
from intelligence.services.river_query import cohort_compare
from intelligence.services.teaching_framework.leader_succession import build_succession
from intelligence.services.teaching_framework.readouts import (
    baseline_by_stage,
    eligible_baseline,
    handoff_readout,
    receipt_summary,
    stage_handoff_readouts,
    succession_diagnostics,
)


def _row(day: str, stock: str, boards: int):
    return {"trade_date": day, "stock_ts_code": stock, "stock_name": stock, "limit_times": boards}


def test_handoff_readout_uses_shared_statistics_gate():
    nodes = [
        {"status": "ok", "break_day": "2026-01-01", "handoff": True},
        {"status": "ok", "break_day": "2026-01-02", "handoff": False},
        {"status": "open", "break_day": "2026-01-03", "handoff": None},
    ]
    result = handoff_readout(nodes, baseline=[True, False], min_n=10)
    assert result.n == 2
    assert result.k == 1
    assert result.verdict == "insufficient_n"


def _fixture():
    """Six days: A leads days 1-2, breaks day 3; B rises 1-2-3 and is born day 4; B leads to the end."""
    days = [f"2026-01-0{i}" for i in range(1, 7)]
    rows = [
        _row(days[0], "A", 3),
        _row(days[1], "A", 4), _row(days[1], "B", 1),
        _row(days[2], "B", 2), _row(days[2], "C", 1),
        _row(days[3], "B", 3),
        _row(days[4], "B", 4),
        _row(days[5], "B", 5),
    ]
    return days, rows


def test_eligible_baseline_counts_match_hand_derivation():
    days, rows = _fixture()
    context = {days[1]: {"stage_coarse": "共建主线阶段"}}
    result = build_succession(days, rows, covered_dates=days, context_by_date=context)
    baseline = eligible_baseline(result, days, context_by_date=context)
    # day 2 is the only eligible baseline day: A is still sealed and top, the
    # 3-day window sees B at 1-2 boards, and the next leader (B, day 4) is realized.
    # day 3 is A's break (event, not baseline); day 4 has no prior top; days 5-6
    # have B as prior with no realized successor (open tail) -> excluded.
    assert [(r["date"], r["handoff"], r["prior"], r["stage"]) for r in baseline] == [(days[1], True, "A", "共建主线阶段")]
    assert baseline[0]["successor"] == "B" and baseline[0]["successor_birth_day"] == days[3]
    summary = receipt_summary(result["nodes"], baseline)
    assert summary["nodes_total"] == 1  # A's break; B is still sealed when the data ends, so no node
    assert summary["nodes_ok"] == 1 and summary["nodes_open"] == 0 and summary["nodes_unverifiable"] == 0
    assert summary["baseline_n"] == 1 and summary["baseline_k"] == 1
    assert summary["baseline_tenures"] == 1 and summary["baseline_overlapping_windows"] == 0


def test_stage_buckets_keep_ambiguous_and_gap_separate_and_report_insufficient_n():
    nodes = [
        {"status": "ok", "break_day": "2026-01-01", "handoff": True, "context_break": {"stage_coarse": "ambiguous"}},
        {"status": "ok", "break_day": "2026-01-02", "handoff": False, "context_break": {"stage_coarse": "左底向下"}},
        {"status": "ok", "break_day": "2026-01-03", "handoff": False, "context_break": {}},
        {"status": "unverifiable", "break_day": "2026-01-04", "handoff": None, "context_break": {"stage_coarse": "左底向下"}},
    ]
    baseline_rows = [
        {"date": "2026-01-05", "stage": "ambiguous", "handoff": True},
        {"date": "2026-01-06", "stage": None, "handoff": False},
    ]
    grouped = baseline_by_stage(baseline_rows)
    assert grouped == {"ambiguous": [True], "gap": [False]}
    buckets = {b.stage: b for b in stage_handoff_readouts(nodes, grouped, min_n=10)}
    assert set(buckets) == {"ambiguous", "左底向下", "gap"}
    assert all(b.verdict == "insufficient_n" for b in buckets.values())
    assert buckets["左底向下"].readout.n == 1 and buckets["左底向下"].readout.baseline_n == 0


def test_succession_diagnostics_cross_tabulate_the_measure():
    days, rows = _fixture()
    result = build_succession(days, rows, covered_dates=days)
    baseline = eligible_baseline(result, days)
    diag = succession_diagnostics(result, baseline)
    assert diag["event_handoff_by_birth_boards"] == {"3": {"n": 1, "k": 1}}
    assert diag["event_handoff_by_gap_days"] == {"1": {"n": 1, "k": 1}}
    # the baseline day (day 2) sits one day before A's break (day 3)
    assert diag["baseline_handoff_by_distance_to_next_break"] == {"1": {"n": 1, "k": 1}}
    assert diag["top_status_days"] == {"none": 1, "ok": 5}


def _sidecar_with_labels(path, rows):
    side = duckdb.connect(str(path))
    ensure_schema(side)
    side.executemany(
        "INSERT INTO history_teaching_labels (entity_type, entity_id, trade_date, label, value_num, value_text, label_version, framework_version, status, computed_at) VALUES ('market','market',?,?,?,?, 'supplier-v1', ?, 'ok', TIMESTAMP '2026-01-03')",
        rows,
    )
    side.close()


def test_cohort_compare_reads_typed_sidecar_feature_by_framework_version(tmp_path):
    source = tmp_path / "source.duckdb"
    sidecar = tmp_path / "labels.duckdb"
    src = duckdb.connect(str(source))
    src.execute("CREATE TABLE fact_market_daily (trade_date DATE, market_stage TEXT)")
    src.executemany("INSERT INTO fact_market_daily VALUES (?, ?)", [("2026-01-01", "x"), ("2026-01-02", "x")])
    src.close()
    _sidecar_with_labels(sidecar, [
        ("2026-01-01", "tf.stage_coarse", None, "左底向下", "tf-v0.1+test"),
        ("2026-01-02", "tf.stage_coarse", None, "ambiguous", "tf-v0.1+test"),
        ("2026-01-03", "tf.stage_coarse", None, "高位震荡阶段", "tf-v0.1+other"),
    ])
    report = cohort_compare(["2026-01-01"], feature="tf.stage_coarse", db_path=source, labels_db_path=sidecar, framework_version="tf-v0.1+test")
    assert report.feature == "tf.stage_coarse"
    assert report.baseline_size == 2  # the other framework version is filtered out
    assert {cell.value for cell in report.cells} == {"左底向下"}
    # Teaching values are bucketed as-is: no 「阶段」 suffix stripping, ambiguous is its own bucket.
    everything = cohort_compare(["2026-01-01", "2026-01-02", "2026-01-03"], feature="tf.stage_coarse", db_path=source, labels_db_path=sidecar)
    assert {cell.value for cell in everything.cells} == {"左底向下", "ambiguous", "高位震荡阶段"}


def test_cohort_compare_market_stage_path_keeps_null_days_as_unknown_bucket(tmp_path):
    source = tmp_path / "source.duckdb"
    src = duckdb.connect(str(source))
    src.execute("CREATE TABLE fact_market_daily (trade_date DATE, market_stage TEXT)")
    src.executemany("INSERT INTO fact_market_daily VALUES (?, ?)", [("2026-01-01", "主升阶段"), ("2026-01-02", None), ("2026-01-03", "主升")])
    src.close()
    report = cohort_compare(["2026-01-02"], feature="market_stage", db_path=source)
    assert report.baseline_size == 3
    assert {cell.value for cell in report.cells} == {"未知"}
