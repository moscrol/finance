"""问题驱动补数：请求合并 / 覆盖检查（反向验证五类）/ 完成信号与恢复的幂等。"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb

from intelligence.services import data_requests as dr
from intelligence.services.tool_hunger import (
    EVENT_WINDOW_UNCOVERED,
    HUNGER_FILENAME,
    JsonlHungerSink,
    hunger_context,
    record_window_uncovered,
    uncovered_side,
)
from market_feature_store.db import init_db

TODAY = date(2026, 9, 9)
NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)


def _write_run(
    users_root: Path,
    user: str,
    run_id: str,
    question: str,
    events: list[dict[str, object]],
    *,
    conversation_id: str = "conv_x",
) -> Path:
    run_dir = users_root / user / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "user": user,
                "question": question,
                "status": "completed",
                "session_id": conversation_id,
                "created_at": "2026-09-09T10:00:00+08:00",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    lines = []
    for event in events:
        payload = {
            "event_type": EVENT_WINDOW_UNCOVERED,
            "ts": "2026-09-09T10:01:00+08:00",
            "run_id": run_id,
            "lane": "episode",
            "requested_name": event.get("dataset"),
            "row_count": 0,
            "uncovered": "all",
            **event,
        }
        lines.append(json.dumps(payload, ensure_ascii=False))
    (run_dir / HUNGER_FILENAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return run_dir


def _gap(dataset: str, start: str, end: str, metrics: list[str], **extra: object) -> dict[str, object]:
    return {
        "dataset": dataset,
        "table": f"fact_{dataset}",
        "metrics": metrics,
        "dimensions": ["trade_date"],
        "requested_start": start,
        "requested_end": end,
        **extra,
    }


def _staging_db(tmp_path: Path) -> Path:
    path = tmp_path / "staging.duckdb"
    con = duckdb.connect(str(path))
    try:
        init_db(con)
        # 交易日历来源：fact_stock_daily 覆盖 2024-06 的 4 个交易日。
        for day in ("2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06"):
            con.execute(
                "INSERT INTO fact_stock_daily (trade_date, stock_ts_code, close, pct_chg, amount) VALUES (?, '000001.SZ', 10.0, 0.5, 1.0)",
                [day],
            )
    finally:
        con.close()
    return path


def _insert_market_rows(path: Path, days: list[str], *, close: float | None = 3000.0, source: str = "akshare:stock_zh_index_daily:sh000001") -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute("ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS sh_index_close DOUBLE")
        con.execute("ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS sh_index_source TEXT")
        for day in days:
            con.execute(
                "INSERT INTO fact_market_daily (trade_date, sh_index_close, sh_index_source, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (trade_date) DO UPDATE SET sh_index_close = excluded.sh_index_close, sh_index_source = excluded.sh_index_source, updated_at = excluded.updated_at",
                [day, close, source, datetime(2026, 9, 9, 11, 0)],
            )
    finally:
        con.close()


# ---------------------------------------------------------------------------
# 事件 → 请求
# ---------------------------------------------------------------------------


def test_uncovered_side_matches_requested_vs_covered() -> None:
    assert uncovered_side(("2024-06-01", "2024-06-30"), None, row_count=0) == "all"
    assert uncovered_side(("2024-06-01", "2024-06-30"), "2024-06-10..2024-06-30", row_count=5) == "front"
    assert uncovered_side(("2024-06-01", "2024-06-30"), "2024-06-01..2024-06-20", row_count=5) == "back"
    assert uncovered_side(("2024-06-01", "2024-06-30"), "2024-06-05..2024-06-20", row_count=5) == "both"
    assert uncovered_side(("2024-06-01", "2024-06-30"), "2024-06-01..2024-06-30", row_count=19) is None
    assert uncovered_side(None, None, row_count=0) is None


def test_record_window_uncovered_writes_event_only_when_uncovered(tmp_path: Path) -> None:
    from intelligence.services.finance_query import FinanceQuerySpec

    spec = FinanceQuerySpec.from_arguments(
        {
            "dataset": "market_daily",
            "metrics": ["total_amount"],
            "dimensions": ["trade_date"],
            "filters": [],
            "time_range": {"start": "2024-06-01", "end": "2024-06-30"},
            "limit": 5,
        }
    )
    sink = JsonlHungerSink(tmp_path / HUNGER_FILENAME, run_id="run_a")
    with hunger_context(sink, run_id="run_a"):
        record_window_uncovered(spec, covered_range=None, row_count=0)
        record_window_uncovered(spec, covered_range="2024-06-01..2024-06-30", row_count=19)
    events = [json.loads(line) for line in (tmp_path / HUNGER_FILENAME).read_text(encoding="utf-8").splitlines()]
    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "window_uncovered"
    assert event["dataset"] == "market_daily"
    assert event["table"] == "fact_market_daily"
    assert event["requested_start"] == "2024-06-01"
    assert event["requested_end"] == "2024-06-30"
    assert event["uncovered"] == "all"
    assert event["metrics"] == ["total_amount"]


def test_build_requests_merges_overlapping_windows_and_keeps_consumers(tmp_path: Path) -> None:
    users = tmp_path / "users"
    _write_run(users, "u1", "run_1", "2024年6月上证指数月度涨跌幅？", [_gap("market_daily", "2024-06-01", "2024-06-30", ["sh_index_close"])])
    _write_run(users, "u1", "run_2", "2024年6月上证偏离度最大是哪天？", [_gap("market_daily", "2024-06-10", "2024-07-05", ["sh_index_close", "sh_week_ma"])])
    _write_run(users, "u2", "run_3", "2024年6月申万一级谁涨最多？", [_gap("sw_l1_daily", "2024-06-01", "2024-06-30", ["pct_chg"])])
    _write_run(users, "u2", "run_4", "2023年3月龙头高度？", [_gap("leader_height_daily", "2023-03-01", "2023-03-31", ["height"])])
    events = dr.collect_gap_events(users)
    assert len(events) == 4
    requests = dr.build_requests(events, now=NOW)
    by_dataset = {r.dataset: r for r in requests}
    assert set(by_dataset) == {"market_daily", "sw_l1_daily", "leader_height_daily"}
    merged = by_dataset["market_daily"]
    assert (merged.window_start, merged.window_end) == ("2024-06-01", "2024-07-05")
    assert {c["run_id"] for c in merged.consumers} == {"run_1", "run_2"}
    assert merged.fields == ["sh_index_close", "sh_week_ma"]
    assert merged.event_count == 2
    assert merged.fill_route["mode"] == "auto"
    assert merged.request_id == dr.request_id_for("market_daily", "2024-06-01", "2024-07-05")
    # 两个消费者的请求排在单消费者前面。
    assert requests[0].dataset == "market_daily"
    # fupanhui 家族只登记、显示真正缺什么，不给自动路线。
    manual = by_dataset["leader_height_daily"]
    assert manual.fill_route["mode"] == "manual"
    assert "CDP" in manual.fill_route["condition"]
    assert any("返回 0 行" in s for s in manual.sources_tried)
    assert merged.consumers[0]["question"].startswith("2024年6月")
    assert merged.consumers[0]["conversation_id"] == "conv_x"


def test_priority_decays_for_stale_requests(tmp_path: Path) -> None:
    users = tmp_path / "users"
    _write_run(users, "u1", "run_old", "老问题", [_gap("market_daily", "2024-01-01", "2024-01-31", ["total_amount"])])
    events = dr.collect_gap_events(users)
    fresh = dr.build_requests(events, now=NOW)[0].priority
    stale = dr.build_requests(events, now=datetime(2026, 12, 1, tzinfo=timezone.utc))[0].priority
    assert stale < fresh


def test_since_filters_old_events(tmp_path: Path) -> None:
    users = tmp_path / "users"
    _write_run(users, "u1", "run_1", "q", [_gap("market_daily", "2024-06-01", "2024-06-30", ["total_amount"])])
    cutoff = dr.parse_since("2026-09-10T00:00:00+08:00")
    assert dr.collect_gap_events(users, since=cutoff) == []
    assert len(dr.collect_gap_events(users, since=dr.parse_since("all"))) == 1


# ---------------------------------------------------------------------------
# 覆盖检查：反向验证五类
# ---------------------------------------------------------------------------


def _request(dataset: str = "market_daily", fields: list[str] | None = None, start: str = "2024-06-01", end: str = "2024-06-30") -> dr.DataRequest:
    return dr.DataRequest(
        request_id=dr.request_id_for(dataset, start, end),
        dataset=dataset,
        table=f"fact_{dataset}",
        window_start=start,
        window_end=end,
        fields=fields if fields is not None else ["sh_index_close"],
        consumers=[{"run_id": "run_1", "user": "u1", "question": "q", "conversation_id": "conv_x"}],
        sources_tried=[],
        fill_route=dr.route_for(dataset),
        priority=1.0,
        first_asked_at=None,
        last_asked_at=None,
        event_count=1,
    )


def test_check_open_when_window_has_no_rows(tmp_path: Path) -> None:
    db = _staging_db(tmp_path)
    completion = dr.check_request(_request(), db_path=db, today=TODAY)
    assert completion.status == dr.STATUS_OPEN
    assert completion.expected_dates == 4
    assert completion.present_dates == 0
    assert completion.data_version is None
    assert completion.satisfied_dependencies["stock_daily"] == dr.STATUS_SATISFIED
    assert completion.satisfied_dependencies["sw_l1_daily"] == dr.STATUS_OPEN


def test_check_partial_when_only_some_dates_filled(tmp_path: Path) -> None:
    db = _staging_db(tmp_path)
    _insert_market_rows(db, ["2024-06-03", "2024-06-04"])
    completion = dr.check_request(_request(), db_path=db, today=TODAY)
    assert completion.status == dr.STATUS_PARTIAL
    assert completion.missing_dates == ["2024-06-05", "2024-06-06"]
    assert completion.data_version is None


def test_check_partial_when_rows_exist_but_key_values_null(tmp_path: Path) -> None:
    db = _staging_db(tmp_path)
    _insert_market_rows(db, ["2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06"], close=None)
    completion = dr.check_request(_request(), db_path=db, today=TODAY)
    assert completion.status == dr.STATUS_PARTIAL
    assert "关键字段值空" in completion.reason
    assert completion.field_coverage["sh_index_close"] == 0.0
    assert completion.data_version is None


def test_check_invalid_when_historical_day_written_by_realtime_source(tmp_path: Path) -> None:
    db = _staging_db(tmp_path)
    _insert_market_rows(db, ["2024-06-03", "2024-06-04", "2024-06-05"])
    _insert_market_rows(db, ["2024-06-06"], source="akshare:index_realtime_sw:801010")
    completion = dr.check_request(_request(), db_path=db, today=TODAY)
    assert completion.status == dr.STATUS_INVALID
    assert completion.invalid_rows[0]["trade_date"] == "2024-06-06"
    assert completion.invalid_rows[0]["reason"] == "历史日被实时源覆写"
    assert completion.data_version is None


def test_check_source_failed_when_db_unreadable(tmp_path: Path) -> None:
    completion = dr.check_request(_request(), db_path=tmp_path / "missing.duckdb", today=TODAY)
    assert completion.status == dr.STATUS_SOURCE_FAILED
    assert completion.data_version is None


def test_check_satisfied_gives_stable_data_version_that_changes_with_data(tmp_path: Path) -> None:
    db = _staging_db(tmp_path)
    days = ["2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06"]
    _insert_market_rows(db, days)
    first = dr.check_request(_request(), db_path=db, today=TODAY)
    again = dr.check_request(_request(), db_path=db, today=TODAY)
    assert first.status == dr.STATUS_SATISFIED
    assert first.data_version and first.data_version == again.data_version
    assert first.field_coverage == {"sh_index_close": 1.0}
    # 数据变了（重写一天），版本必须变。
    con = duckdb.connect(str(db))
    con.execute("UPDATE fact_market_daily SET updated_at = ? WHERE trade_date = '2024-06-06'", [datetime(2026, 9, 10, 1, 0)])
    con.close()
    changed = dr.check_request(_request(), db_path=db, today=TODAY)
    assert changed.data_version != first.data_version


def test_check_calendar_unknown_when_no_trading_calendar(tmp_path: Path) -> None:
    db = _staging_db(tmp_path)
    completion = dr.check_request(_request(start="2019-01-01", end="2019-01-31"), db_path=db, today=TODAY)
    assert completion.status == dr.STATUS_CALENDAR_UNKNOWN


# ---------------------------------------------------------------------------
# 完成信号只落一次；恢复只做一次；重放无副作用
# ---------------------------------------------------------------------------


def test_record_completions_and_resume_are_idempotent(tmp_path: Path) -> None:
    users = tmp_path / "users"
    db = _staging_db(tmp_path)
    _insert_market_rows(db, ["2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06"])
    _write_run(users, "u1", "run_1", "2024年6月上证指数月度涨跌幅？", [_gap("market_daily", "2024-06-01", "2024-06-30", ["sh_index_close"])])
    _write_run(users, "u1", "run_2", "2024年6月上证偏离度？", [_gap("market_daily", "2024-06-01", "2024-06-30", ["sh_index_close"])])
    requests = dr.build_requests(dr.collect_gap_events(users), now=NOW)
    completions = dr.check_requests(requests, db_path=db, today=TODAY)
    assert [c.status for c in completions] == [dr.STATUS_SATISFIED]

    first = dr.record_completions(completions, users_dir=users)
    second = dr.record_completions(completions, users_dir=users)
    assert len(first) == 1 and second == []
    receipts = dr.load_receipts(users, "u1")
    assert [r["event"] for r in receipts] == ["completed"]
    assert set(receipts[0]["affected_run_ids"]) == {"run_1", "run_2"}
    assert receipts[0]["satisfied_dependencies"]["stock_daily"] == dr.STATUS_SATISFIED

    calls: list[tuple[str, str]] = []

    def fake_http(url: str, *, method: str = "GET", payload: dict | None = None, timeout: float = 30):
        calls.append((method, url))
        if url.endswith("/messages"):
            return {"run_id": f"run_new_{len(calls)}", "conversation_id": "conv_x"}
        if "/api/runs/" in url:
            return {"status": "completed"}
        return {"conversation_id": "conv_x"}

    actions, skipped = dr.plan_resume(completions, users_dir=users)
    assert len(actions) == 2 and skipped == []
    results = dr.execute_resume(actions, users_dir=users, workbench_url="http://wb", http=fake_http, sleep=lambda _s: None)
    assert [r["status"] for r in results] == ["completed", "completed"]
    assert all(r["conversation_id"] == "conv_x" for r in results)
    posted = [url for method, url in calls if method == "POST"]
    assert posted == ["http://wb/api/conversations/conv_x/messages"] * 2

    # 重放：完成信号不重复、恢复不重复、不再打 Workbench。
    actions_again, skipped_again = dr.plan_resume(completions, users_dir=users)
    assert actions_again == []
    assert {s["run_id"] for s in skipped_again} == {"run_1", "run_2"}
    before = len(calls)
    dr.execute_resume(actions_again, users_dir=users, workbench_url="http://wb", http=fake_http)
    assert len(calls) == before
    events = [r["event"] for r in dr.load_receipts(users, "u1")]
    assert events == ["completed", "resumed", "resumed"]


def test_resume_dry_run_writes_no_receipt_and_calls_nothing(tmp_path: Path) -> None:
    users = tmp_path / "users"
    db = _staging_db(tmp_path)
    _insert_market_rows(db, ["2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06"])
    _write_run(users, "u1", "run_1", "q", [_gap("market_daily", "2024-06-01", "2024-06-30", ["sh_index_close"])])
    completions = dr.check_requests(dr.build_requests(dr.collect_gap_events(users), now=NOW), db_path=db, today=TODAY)
    actions, _ = dr.plan_resume(completions, users_dir=users)

    def boom(*_a, **_k):
        raise AssertionError("dry-run must not call Workbench")

    results = dr.execute_resume(actions, users_dir=users, workbench_url="http://wb", dry_run=True, http=boom)
    assert [r["status"] for r in results] == ["planned"]
    # dry-run 无副作用：不打 Workbench、不落回执，下次真跑仍会恢复。
    assert dr.load_receipts(users, "u1") == []
    assert dr.plan_resume(completions, users_dir=users)[0] == actions


def test_resume_falls_back_to_new_conversation_when_original_missing(tmp_path: Path) -> None:
    import urllib.error

    users = tmp_path / "users"
    db = _staging_db(tmp_path)
    _insert_market_rows(db, ["2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06"])
    _write_run(users, "u1", "run_1", "q", [_gap("market_daily", "2024-06-01", "2024-06-30", ["sh_index_close"])], conversation_id="conv_gone")
    completions = dr.check_requests(dr.build_requests(dr.collect_gap_events(users), now=NOW), db_path=db, today=TODAY)
    actions, _ = dr.plan_resume(completions, users_dir=users)
    calls: list[str] = []

    def fake_http(url: str, *, method: str = "GET", payload: dict | None = None, timeout: float = 30):
        calls.append(f"{method} {url}")
        if method == "GET" and url.endswith("/api/conversations/conv_gone?user=u1"):
            raise urllib.error.HTTPError(url, 404, "gone", hdrs=None, fp=None)
        if method == "POST" and url.endswith("/api/conversations"):
            return {"conversation_id": "conv_new"}
        if url.endswith("/messages"):
            return {"run_id": "run_new"}
        return {"status": "completed"}

    results = dr.execute_resume(actions, users_dir=users, workbench_url="http://wb", http=fake_http, sleep=lambda _s: None)
    assert results[0]["conversation_id"] == "conv_new"
    assert results[0]["new_run_id"] == "run_new"
    assert any(c == "POST http://wb/api/conversations" for c in calls)


# ---------------------------------------------------------------------------
# fill：拒绝生产库；manual / pending_sync 显示真正缺什么
# ---------------------------------------------------------------------------


def test_fill_refuses_production_db(monkeypatch, tmp_path: Path) -> None:
    prod = tmp_path / "db" / "market_feature_store.duckdb"
    monkeypatch.setattr(dr, "production_db_path", lambda: prod.resolve())
    result = dr.fill_request(_request(), db_path=prod, dry_run=True)
    assert result["status"] == "refused"


def test_fill_manual_route_reports_condition_without_retry(tmp_path: Path) -> None:
    result = dr.fill_request(_request(dataset="theme_limit_stock_daily", fields=["limit_up_count"]), db_path=tmp_path / "s.duckdb", dry_run=True)
    assert result["status"] == "manual"
    assert "CDP" in result["really_missing"]
    pending = dr.route_for("l2_moneyflow")
    assert pending["mode"] == "pending_sync"
    assert "pending_sync" in pending["condition"]


def test_fill_dry_run_plans_auto_parts_only(tmp_path: Path) -> None:
    result = dr.fill_request(_request(), db_path=tmp_path / "s.duckdb", dry_run=True)
    assert result["status"] == "planned"
    assert result["plan"]["parts"] == ["sh_index", "aggregates", "industry"]
    assert result["plan"]["historical_workaround"] is True


def test_research_queue_writer_exports_data_requests_sibling(tmp_path: Path) -> None:
    from intelligence.services import research_queue

    payload = {
        "date": "2026-09-09",
        "generated_at": "2026-09-09T20:00:00+08:00",
        "research_queue": {"today_do_ima": [], "today_find_official_evidence": [], "today_wait_market_validation": [], "today_downgrade_or_watch": [], "skipped": {"data_gap_or_unconfirmed": [], "no_clear_action": []}, "summary": {}},
        "data_requests": {"schema_version": dr.SCHEMA_VERSION, "requests": [], "summary": {"requests": 0}},
    }
    written = research_queue.write_research_queue_outputs(payload, json_path=tmp_path / "2026-09-09-research-queue.json")
    sibling = tmp_path / "2026-09-09-data-requests.json"
    assert written["data_requests"] == sibling
    assert json.loads(sibling.read_text(encoding="utf-8"))["schema_version"] == dr.SCHEMA_VERSION


def test_wrap_artifact_and_markdown_render(tmp_path: Path) -> None:
    users = tmp_path / "users"
    db = _staging_db(tmp_path)
    _write_run(users, "u1", "run_1", "q", [_gap("market_daily", "2024-06-01", "2024-06-30", ["sh_index_close"])])
    requests = dr.build_requests(dr.collect_gap_events(users), now=NOW)
    completions = dr.check_requests(requests, db_path=db, today=TODAY)
    artifact = dr.wrap_artifact(requests, completions, runs_root=users, since="all", db_path=db)
    assert artifact["schema_version"] == dr.SCHEMA_VERSION
    assert artifact["summary"]["requests"] == 1
    assert artifact["summary"]["by_status"] == {dr.STATUS_OPEN: 1}
    markdown = dr.render_markdown(artifact)
    assert "market_daily" in markdown and "open" in markdown
    json.dumps(artifact, ensure_ascii=False)
