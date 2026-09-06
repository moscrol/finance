import duckdb

from intelligence.services.methodology_backtest.store import ensure_schema
from intelligence.services.river_query import cohort_compare
from intelligence.services.teaching_framework.leader_succession import build_succession
from intelligence.services.teaching_framework.readouts import eligible_baseline, handoff_readout


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


def test_eligible_baseline_excludes_missing_and_unmatured_dates():
    calendar = [f"2026-01-{day:02d}" for day in range(1, 7)]
    rows = [
        {"trade_date": calendar[0], "stock_ts_code": "A", "limit_times": 3, "limit_status": "U"},
        {"trade_date": calendar[1], "stock_ts_code": "B", "limit_times": 1, "limit_status": "U"},
        {"trade_date": calendar[2], "stock_ts_code": "A", "limit_times": 3, "limit_status": "U"},
        {"trade_date": calendar[3], "stock_ts_code": "B", "limit_times": 3, "limit_status": "U"},
    ]
    result = build_succession(calendar, rows, covered_dates=calendar)
    baseline = eligible_baseline(result, calendar)
    assert all(item["date"] in calendar for item in baseline)
    assert all(item["handoff"] in {True, False} for item in baseline)


def test_cohort_compare_reads_typed_sidecar_feature(tmp_path):
    source = tmp_path / "source.duckdb"
    sidecar = tmp_path / "labels.duckdb"
    src = duckdb.connect(str(source))
    src.execute("CREATE TABLE fact_market_daily (trade_date DATE, market_stage TEXT)")
    src.executemany("INSERT INTO fact_market_daily VALUES (?, ?)", [("2026-01-01", "x"), ("2026-01-02", "x")])
    src.close()
    side = duckdb.connect(str(sidecar))
    ensure_schema(side)
    side.executemany(
        "INSERT INTO history_teaching_labels (entity_type, entity_id, trade_date, label, value_num, value_text, label_version, framework_version, status, computed_at) VALUES ('market','market',?,?,?,?, 'supplier-v1', 'tf-v0.1+test', 'ok', TIMESTAMP '2026-01-03')",
        [("2026-01-01", "tf.stage_coarse", None, "左底向下"), ("2026-01-02", "tf.stage_coarse", None, "高位震荡")],
    )
    side.close()
    report = cohort_compare(["2026-01-01"], feature="tf.stage_coarse", db_path=source, labels_db_path=sidecar)
    assert report.feature == "tf.stage_coarse"
    assert {cell.value for cell in report.cells} == {"左底向下"}
