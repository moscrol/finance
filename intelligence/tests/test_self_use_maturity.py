from __future__ import annotations

import json
import multiprocessing
import os
import stat
from dataclasses import FrozenInstanceError, asdict
from datetime import datetime
from typing import Any, get_args, get_type_hints

import pytest

from intelligence.services import self_use_maturity
from intelligence.services.run_store import RunStore
from intelligence.services.self_use_maturity import (
    LLM_FALLBACK_DEGRADE,
    SELF_USE_LLM_MODEL,
    SELF_USE_LLM_PROVIDER,
    ApprovalRecord,
    MaturityResult,
    RunBindingError,
    SelfUseApprovalStore,
    SelfUseEvent,
    SelfUseLedger,
    SelfUseLedgerIntegrityError,
    dedupe_events,
    evaluate_maturity,
    ingest_self_use_event,
    verify_run_binding,
)

# 12 个连续的 canonical A 股交易日（工作日，测试语境下视为无节假日），跳过周末
# 6/6、6/7、6/13、6/14。它们是「日历唯一来源」——不在此列表里的任何日期都会被判为
# 非交易日（周末/节假日的统一表现）。
TRADING_DAYS = [
    "2026-06-01",
    "2026-06-02",
    "2026-06-03",
    "2026-06-04",
    "2026-06-05",
    "2026-06-08",
    "2026-06-09",
    "2026-06-10",
    "2026-06-11",
    "2026-06-12",
    "2026-06-15",
    "2026-06-16",
]
# 明显晚于全部日历日期，保证 make_event 默认事件都不是「未来」。
TODAY = "2026-07-01"
WORKFLOW_NAMES = [
    "daily_market",
    "theme_research",
    "stock_research",
    "news_impact",
    "watchlist",
]


def evaluate(
    events: list[SelfUseEvent],
    *,
    trading_days: list[str] | None = TRADING_DAYS,
    today: object = TODAY,
    user_approved: bool = False,
) -> MaturityResult:
    return evaluate_maturity(
        events,
        trading_days=trading_days,
        today=today,  # type: ignore[arg-type]
        user_approved=user_approved,
    )


def _record_from_process(path: str, start_event: Any, index: int) -> None:
    start_event.wait(timeout=10)
    SelfUseLedger(path).record(
        SelfUseEvent(
            trade_date="2026-07-11",
            workflow="daily_market",
            outcome="success",
            manual_rescue=False,
            severe_fact_error=False,
            useful=True,
            run_id=f"run_{index}",
        )
    )


def _record_once_from_process(path: str, start_event: Any) -> None:
    start_event.wait(timeout=10)
    SelfUseLedger(path).record_once(
        SelfUseEvent(
            trade_date="2026-07-11",
            workflow="daily_market",
            outcome="success",
            manual_rescue=False,
            severe_fact_error=False,
            useful=True,
            run_id="same-run",
        )
    )


def make_event(**overrides: object) -> SelfUseEvent:
    values: dict[str, object] = {
        "trade_date": TRADING_DAYS[0],
        "workflow": "daily_market",
        "outcome": "success",
        "manual_rescue": False,
        "severe_fact_error": False,
        "useful": True,
        "recorded_at": "2026-06-01T09:00:00+08:00",
    }
    values.update(overrides)
    return SelfUseEvent(**values)  # type: ignore[arg-type]


def make_complete_maturity_events() -> list[SelfUseEvent]:
    return [
        make_event(trade_date=TRADING_DAYS[day], workflow=workflow)
        for day in range(10)
        for workflow in WORKFLOW_NAMES
    ]


def make_completed_run(
    run_store: RunStore,
    run_id: str,
    *,
    llm_used: bool = True,
    llm_provider: str = SELF_USE_LLM_PROVIDER,
    llm_model: str = SELF_USE_LLM_MODEL,
    report_id: str | None = None,
    report_status: str = "completed",
    report_as_of: str = TRADING_DAYS[0],
    degrade: str | None = None,
    with_stream: bool = True,
    with_report: bool = True,
    with_report_stream: bool = True,
) -> str:
    """在临时 RunStore 里造一个终态成功、带 SSE/报告证据的 run，供 run-binding 测试复用。"""
    run_dir = run_store.run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    from intelligence.services import run_store as run_store_module

    payload = run_store_module.Run(
        run_id=run_id,
        user="tester",
        question="q",
        task_type="conversation",
        status=run_store_module.STATUS_COMPLETED,
        degrades=[degrade] if degrade else [],
    )
    (run_dir / "run.json").write_text(
        json.dumps(asdict(payload), ensure_ascii=False), encoding="utf-8"
    )
    if with_report:
        report = {
            "report_id": report_id or run_id,
            "status": report_status,
            "as_of": report_as_of,
            "llm": {
                "used": llm_used,
                "provider": llm_provider,
                "model": llm_model,
            },
        }
        (run_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8"
        )
    if with_stream:
        run_store.append_stream_event(
            run_id,
            event_id="evt-1",
            event_type="answer",
            payload={"text": "ok"},
        )
        if with_report_stream and with_report:
            run_store.append_stream_event(
                run_id,
                event_id="report:complete",
                event_type="report.complete",
                payload={"report": report},
            )
    return run_id


def test_complete_ten_day_workflow_set_is_eligible_but_requires_user_approval() -> None:
    result = evaluate(make_complete_maturity_events())

    assert result.blockers == ()
    assert result.eligible_for_user_decision is True
    assert result.user_approved is False
    assert result.passed is False
    assert result.metrics == {
        "distinct_trade_dates": 10,
        "covered_workflows": [
            "daily_market",
            "news_impact",
            "stock_research",
            "theme_research",
            "watchlist",
        ],
        "core_success_rate": 1.0,
        "useful_rate": 1.0,
        "manual_rescue_rate": 0.0,
        "severe_fact_errors": 0,
        "event_count": 50,
    }
    assert result.fingerprint  # 裁决快照指纹随结果一起产出


def test_new_events_without_recorded_at_can_be_evaluated() -> None:
    events = [
        SelfUseEvent(
            trade_date=TRADING_DAYS[day],
            workflow=workflow,  # type: ignore[arg-type]
            outcome="success",
            manual_rescue=False,
            severe_fact_error=False,
            useful=True,
        )
        for day in range(10)
        for workflow in WORKFLOW_NAMES
    ]

    result = evaluate(events)

    assert result.eligible_for_user_decision is True
    assert result.metrics["event_count"] == 50
    assert all(event.recorded_at is None for event in events)


def test_explicit_user_approval_passes_an_eligible_result() -> None:
    result = evaluate(make_complete_maturity_events(), user_approved=True)

    assert result.eligible_for_user_decision is True
    assert result.user_approved is True
    assert result.passed is True


@pytest.mark.parametrize("user_approved", ["false", 0])
def test_non_boolean_user_approval_is_rejected(user_approved: object) -> None:
    with pytest.raises(TypeError, match="user_approved"):
        evaluate(
            make_complete_maturity_events(),
            user_approved=user_approved,  # type: ignore[arg-type]
        )


def test_severe_fact_error_blocks_maturity() -> None:
    events = make_complete_maturity_events()
    events[0] = make_event(
        trade_date=events[0].trade_date,
        workflow=events[0].workflow,
        severe_fact_error=True,
    )

    result = evaluate(events)

    assert result.metrics["severe_fact_errors"] == 1
    assert result.blockers == ("severe_fact_error",)
    assert result.eligible_for_user_decision is False
    assert result.passed is False


def test_user_approval_cannot_bypass_mechanical_blockers() -> None:
    result = evaluate([make_event()], user_approved=True)

    assert result.user_approved is True
    assert result.eligible_for_user_decision is False
    assert result.passed is False


def test_rate_thresholds_are_inclusive_at_95_5_and_80_percent() -> None:
    events = [
        make_event(
            trade_date=TRADING_DAYS[index // 2],
            workflow=(
                "daily_market",
                "theme_research",
                "stock_research",
                "news_impact",
                "watchlist",
            )[index % 5],
            outcome="failed" if index == 0 else "success",
            manual_rescue=index == 1,
            useful=index < 16,
        )
        for index in range(20)
    ]

    result = evaluate(events)

    assert result.blockers == ()
    assert result.metrics["core_success_rate"] == 0.95
    assert result.metrics["manual_rescue_rate"] == 0.05
    assert result.metrics["useful_rate"] == 0.8


def test_rates_are_rounded_to_six_decimal_places() -> None:
    events = [
        make_event(
            run_id=f"run-{index}",
            outcome="failed" if index == 2 else "success",
            manual_rescue=index == 0,
            useful=index < 2,
        )
        for index in range(3)
    ]

    result = evaluate(events)

    assert result.metrics["core_success_rate"] == 0.666667
    assert result.metrics["manual_rescue_rate"] == 0.333333
    assert result.metrics["useful_rate"] == 0.666667


def test_empty_events_have_zero_rates_and_expected_blockers() -> None:
    result = evaluate([])

    assert result.metrics == {
        "distinct_trade_dates": 0,
        "covered_workflows": [],
        "core_success_rate": 0.0,
        "useful_rate": 0.0,
        "manual_rescue_rate": 0.0,
        "severe_fact_errors": 0,
        "event_count": 0,
    }
    # 空台账不会被自动补齐 Day 1；只是列出机械阻塞项。
    assert result.blockers == (
        "minimum_trade_dates",
        "missing_workflows",
        "success_rate",
        "useful_rate",
    )


def test_missing_workflow_is_reported_after_minimum_trade_dates_passes() -> None:
    events = [make_event(trade_date=TRADING_DAYS[day]) for day in range(10)]

    result = evaluate(events)

    assert result.blockers == ("missing_workflows",)
    assert result.metrics["covered_workflows"] == ["daily_market"]


def test_weekend_or_holiday_date_is_rejected_as_non_trading_day() -> None:
    # 2026-06-06 是周六、2026-06-19 是（此日历里的）节假日/非交易日：都不在日历里。
    events = make_complete_maturity_events()
    events[0] = make_event(trade_date="2026-06-06", workflow="daily_market")

    result = evaluate(events)

    assert "non_trading_day" in result.blockers
    assert result.eligible_for_user_decision is False


def test_future_trade_date_is_rejected() -> None:
    calendar = TRADING_DAYS + ["2026-07-15"]
    events = make_complete_maturity_events()
    events[0] = make_event(trade_date="2026-07-15", workflow="daily_market")

    result = evaluate(events, trading_days=calendar, today="2026-07-01")

    assert "future_trade_date" in result.blockers
    assert result.eligible_for_user_decision is False


def test_non_contiguous_trading_day_streak_is_rejected() -> None:
    # 用 10 个日历日，但故意跳过中间一个 canonical 交易日 → 非连续段。
    picked = TRADING_DAYS[:5] + TRADING_DAYS[6:11]
    events = [
        make_event(trade_date=day, workflow=workflow)
        for day in picked
        for workflow in WORKFLOW_NAMES
    ]

    result = evaluate_maturity(
        events,
        trading_days=TRADING_DAYS,
        today=TODAY,
        require_consecutive_trading_days=True,
    )

    assert "non_contiguous_streak" in result.blockers
    assert result.eligible_for_user_decision is False


def test_non_contiguous_trading_days_are_allowed_without_explicit_policy() -> None:
    picked = TRADING_DAYS[:5] + TRADING_DAYS[6:11]
    events = [
        make_event(trade_date=day, workflow=workflow)
        for day in picked
        for workflow in WORKFLOW_NAMES
    ]

    result = evaluate(events)

    assert "non_contiguous_streak" not in result.blockers
    assert result.eligible_for_user_decision is True


def test_missing_calendar_fails_closed() -> None:
    for calendar in (None, []):
        result = evaluate(make_complete_maturity_events(), trading_days=calendar)
        assert result.blockers == ("trading_calendar_unavailable",)
        assert result.eligible_for_user_decision is False


def test_duplicate_run_date_workflow_does_not_dilute_rates() -> None:
    events = make_complete_maturity_events()
    bound = [make_event(trade_date=e.trade_date, workflow=e.workflow, run_id=f"r-{i}")
             for i, e in enumerate(events)]
    # 把第一条重复摄入 5 次（相同 run_id/date/workflow）——不得稀释指标或计数。
    duplicated = bound + [bound[0]] * 5

    result = evaluate(duplicated)

    assert result.metrics["event_count"] == 50
    assert result.metrics["distinct_trade_dates"] == 10
    assert result.metrics["core_success_rate"] == 1.0
    assert result.blockers == ()


def test_dedupe_events_keeps_first_and_is_stable() -> None:
    a = make_event(run_id="run-a")
    b = make_event(run_id="run-a")  # same identity
    c = make_event(run_id="run-b")
    assert dedupe_events([a, b, c]) == [a, c]


def test_evaluation_rejects_extra_unvalidated_workflow() -> None:
    events = make_complete_maturity_events()
    events.append(make_event(workflow="freeform"))

    with pytest.raises(ValueError, match="workflow"):
        evaluate(events)


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "message"),
    [
        ("trade_date", "2026-02-30", "trade_date"),
        ("outcome", "partial", "outcome"),
        ("manual_rescue", 0, "manual_rescue"),
        ("severe_fact_error", 0, "severe_fact_error"),
        ("useful", 1, "useful"),
        ("schema_version", 2, "schema_version"),
    ],
)
def test_evaluation_rejects_unvalidated_event_contract_values(
    field_name: str, invalid_value: object, message: str
) -> None:
    event = make_event(**{field_name: invalid_value})

    with pytest.raises(ValueError, match=message):
        evaluate([event])


def test_blockers_follow_stable_contract_order() -> None:
    result = evaluate(
        [
            make_event(
                trade_date="2026-06-06",  # 非交易日
                outcome="failed",
                manual_rescue=True,
                severe_fact_error=True,
                useful=False,
            )
        ]
    )

    assert result.blockers == (
        "non_trading_day",
        "minimum_trade_dates",
        "missing_workflows",
        "success_rate",
        "severe_fact_error",
        "manual_rescue_rate",
        "useful_rate",
    )


def test_evaluation_does_not_mutate_events_or_event_list() -> None:
    events = make_complete_maturity_events()
    original_events = list(events)
    original_payloads = [asdict(event) for event in events]

    result = evaluate(events)

    assert events == original_events
    assert [asdict(event) for event in events] == original_payloads
    with pytest.raises(FrozenInstanceError):
        result.passed = True  # type: ignore[misc]
    assert isinstance(result, MaturityResult)


# ---------------------------------------------------------------------------
# gap 2：run 绑定校验（真实、终态成功、llm.used、SSE/报告证据）
# ---------------------------------------------------------------------------


def test_verify_run_binding_accepts_completed_llm_backed_run(tmp_path) -> None:
    store = RunStore("tester", root=tmp_path / "runs")
    make_completed_run(store, "run-ok")

    evidence = verify_run_binding(store, "run-ok")

    assert evidence.status == "completed"
    assert evidence.llm_used is True
    assert evidence.llm_provider == SELF_USE_LLM_PROVIDER
    assert evidence.llm_model == SELF_USE_LLM_MODEL
    assert evidence.report_as_of == TRADING_DAYS[0]
    assert evidence.stream_event_count >= 1


@pytest.mark.parametrize("run_id", [None, "", "   "])
def test_verify_run_binding_rejects_missing_run_id(tmp_path, run_id) -> None:
    store = RunStore("tester", root=tmp_path / "runs")
    with pytest.raises(RunBindingError, match="run_id"):
        verify_run_binding(store, run_id)


def test_verify_run_binding_rejects_fake_run_id(tmp_path) -> None:
    store = RunStore("tester", root=tmp_path / "runs")
    with pytest.raises(RunBindingError, match="not found"):
        verify_run_binding(store, "run-does-not-exist")


@pytest.mark.parametrize("status", ["queued", "running", "failed", "cancelled"])
def test_verify_run_binding_rejects_nonterminal_or_failed_run(tmp_path, status) -> None:
    from intelligence.services import run_store as run_store_module

    store = RunStore("tester", root=tmp_path / "runs")
    run_dir = store.run_dir("run-x")
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = run_store_module.Run(
        run_id="run-x", user="tester", question="q", task_type="conversation", status=status
    )
    (run_dir / "run.json").write_text(json.dumps(asdict(payload)), encoding="utf-8")
    (run_dir / "report.json").write_text(
        json.dumps(
            {
                "report_id": "run-x",
                "status": status,
                "as_of": TRADING_DAYS[0],
                "llm": {
                    "used": True,
                    "provider": SELF_USE_LLM_PROVIDER,
                    "model": SELF_USE_LLM_MODEL,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RunBindingError, match="terminal-successful"):
        verify_run_binding(store, "run-x")


def test_verify_run_binding_rejects_template_fallback_run(tmp_path) -> None:
    store = RunStore("tester", root=tmp_path / "runs")
    make_completed_run(store, "run-fb", degrade=LLM_FALLBACK_DEGRADE)

    with pytest.raises(RunBindingError, match="template"):
        verify_run_binding(store, "run-fb")


def test_verify_run_binding_rejects_llm_unused_report(tmp_path) -> None:
    store = RunStore("tester", root=tmp_path / "runs")
    make_completed_run(store, "run-noml", llm_used=False)

    with pytest.raises(RunBindingError, match="llm.used"):
        verify_run_binding(store, "run-noml")


def test_verify_run_binding_rejects_missing_report(tmp_path) -> None:
    store = RunStore("tester", root=tmp_path / "runs")
    make_completed_run(store, "run-norep", with_report=False)

    with pytest.raises(RunBindingError, match="report.json"):
        verify_run_binding(store, "run-norep")


def test_verify_run_binding_rejects_missing_stream_evidence(tmp_path) -> None:
    store = RunStore("tester", root=tmp_path / "runs")
    make_completed_run(store, "run-nostream", with_stream=False)

    with pytest.raises(RunBindingError, match="SSE|stream"):
        verify_run_binding(store, "run-nostream")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"report_id": "another-run"}, "report_id"),
        ({"report_status": "streaming"}, "report is not completed"),
    ],
)
def test_verify_run_binding_rejects_report_or_model_mismatch(
    tmp_path, overrides, message
) -> None:
    store = RunStore("tester", root=tmp_path / "runs")
    make_completed_run(store, "run-mismatch", **overrides)

    with pytest.raises(RunBindingError, match=message):
        verify_run_binding(store, "run-mismatch")


def test_verify_run_binding_rejects_missing_report_complete_stream_event(tmp_path) -> None:
    store = RunStore("tester", root=tmp_path / "runs")
    make_completed_run(store, "run-no-report-event", with_report_stream=False)

    with pytest.raises(RunBindingError, match="report.complete"):
        verify_run_binding(store, "run-no-report-event")


def test_verify_run_binding_rejects_streamed_report_mismatch(tmp_path) -> None:
    store = RunStore("tester", root=tmp_path / "runs")
    make_completed_run(store, "run-stream-mismatch", with_report_stream=False)
    store.append_stream_event(
        "run-stream-mismatch",
        event_id="report:complete",
        event_type="report.complete",
        payload={
            "report": {
                "report_id": "run-stream-mismatch",
                "status": "completed",
                "as_of": TRADING_DAYS[1],
                "llm": {
                    "used": True,
                    "provider": SELF_USE_LLM_PROVIDER,
                    "model": SELF_USE_LLM_MODEL,
                },
            }
        },
    )

    with pytest.raises(RunBindingError, match="does not match"):
        verify_run_binding(store, "run-stream-mismatch")


# ---------------------------------------------------------------------------
# gap 1+2+3：ingest 校验 + 幂等
# ---------------------------------------------------------------------------


def test_ingest_is_idempotent_for_duplicate_run_date_workflow(tmp_path) -> None:
    store = RunStore("tester", root=tmp_path / "runs")
    make_completed_run(store, "run-1")
    ledger = SelfUseLedger(tmp_path / "events.jsonl")
    event = make_event(trade_date=TRADING_DAYS[0], run_id="run-1")

    first = ingest_self_use_event(
        ledger, event, run_store=store, trading_days=TRADING_DAYS, today=TODAY
    )
    second = ingest_self_use_event(
        ledger, event, run_store=store, trading_days=TRADING_DAYS, today=TODAY
    )

    assert (first.run_id, first.trade_date, first.workflow) == (
        second.run_id, second.trade_date, second.workflow
    )
    assert len(ledger.load()) == 1


def test_ingest_rejects_non_trading_day(tmp_path) -> None:
    store = RunStore("tester", root=tmp_path / "runs")
    make_completed_run(store, "run-1")
    ledger = SelfUseLedger(tmp_path / "events.jsonl")

    with pytest.raises(ValueError, match="trading day"):
        ingest_self_use_event(
            ledger,
            make_event(trade_date="2026-06-06", run_id="run-1"),
            run_store=store,
            trading_days=TRADING_DAYS,
            today=TODAY,
        )
    assert ledger.load() == []


def test_ingest_rejects_run_without_binding(tmp_path) -> None:
    store = RunStore("tester", root=tmp_path / "runs")
    ledger = SelfUseLedger(tmp_path / "events.jsonl")

    with pytest.raises(RunBindingError):
        ingest_self_use_event(
            ledger,
            make_event(trade_date=TRADING_DAYS[0], run_id="ghost"),
            run_store=store,
            trading_days=TRADING_DAYS,
            today=TODAY,
        )
    assert ledger.load() == []


def test_ingest_rejects_report_date_mismatch(tmp_path) -> None:
    store = RunStore("tester", root=tmp_path / "runs")
    make_completed_run(store, "run-wrong-date", report_as_of=TRADING_DAYS[1])
    ledger = SelfUseLedger(tmp_path / "events.jsonl")

    with pytest.raises(RunBindingError, match="does not match trade_date"):
        ingest_self_use_event(
            ledger,
            make_event(trade_date=TRADING_DAYS[0], run_id="run-wrong-date"),
            run_store=store,
            trading_days=TRADING_DAYS,
            today=TODAY,
        )
    assert ledger.load() == []


# ---------------------------------------------------------------------------
# gap 5：持久化审批 + 指纹失效
# ---------------------------------------------------------------------------


def test_approval_persists_auditable_record_and_matches_fingerprint(tmp_path) -> None:
    result = evaluate(make_complete_maturity_events())
    store = SelfUseApprovalStore(tmp_path / "approval.json")

    record = store.approve(result, approved_by="a77")

    assert isinstance(record, ApprovalRecord)
    assert record.approved_at
    assert record.approved_by == "a77"
    assert record.eligibility_fingerprint == result.fingerprint
    assert store.is_approved_for(result) is True
    # 复读一次也命中（真正落盘了）
    assert SelfUseApprovalStore(tmp_path / "approval.json").is_approved_for(result) is True


def test_approval_invalidated_when_ledger_changes(tmp_path) -> None:
    base_events = make_complete_maturity_events()
    result = evaluate(base_events)
    store = SelfUseApprovalStore(tmp_path / "approval.json")
    store.approve(result, approved_by="a77")

    # 台账新增一条（改变去重后集合/指标）→ 指纹变化 → 旧审批失效。
    changed = evaluate(base_events + [make_event(trade_date=TRADING_DAYS[10], run_id="extra")])
    assert changed.fingerprint != result.fingerprint
    assert store.is_approved_for(changed) is False


def test_approval_rejects_ineligible_result(tmp_path) -> None:
    result = evaluate([make_event()])  # not eligible
    store = SelfUseApprovalStore(tmp_path / "approval.json")

    with pytest.raises(ValueError, match="eligible"):
        store.approve(result, approved_by="a77")


def test_record_appends_schema_workflow_and_run_id(tmp_path) -> None:
    path = tmp_path / "private" / "self-use" / "events.jsonl"
    ledger = SelfUseLedger(path)

    saved = ledger.record(make_event(run_id="run_20260711_001"))

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["workflow"] == "daily_market"
    assert payload["run_id"] == "run_20260711_001"
    assert saved.run_id == "run_20260711_001"


def test_self_use_event_is_frozen() -> None:
    event = make_event()

    with pytest.raises(FrozenInstanceError):
        event.useful = False  # type: ignore[misc]

    hints = get_type_hints(SelfUseEvent)
    assert get_args(hints["workflow"]) == (
        "daily_market",
        "theme_research",
        "stock_research",
        "news_impact",
        "watchlist",
    )
    assert get_args(hints["outcome"]) == ("success", "degraded", "failed")


@pytest.mark.parametrize(
    "workflow",
    [
        "daily_market",
        "theme_research",
        "stock_research",
        "news_impact",
        "watchlist",
    ],
)
def test_record_accepts_each_supported_workflow(tmp_path, workflow: str) -> None:
    path = tmp_path / f"{workflow}.jsonl"

    SelfUseLedger(path).record(make_event(workflow=workflow))

    assert json.loads(path.read_text(encoding="utf-8"))["workflow"] == workflow


def test_invalid_workflow_does_not_create_file(tmp_path) -> None:
    path = tmp_path / "self-use" / "events.jsonl"

    with pytest.raises(ValueError, match="workflow"):
        SelfUseLedger(path).record(make_event(workflow="freeform"))

    assert not path.exists()
    assert not path.parent.exists()


@pytest.mark.parametrize("outcome", ["partial", "", "SUCCESS"])
def test_invalid_outcome_does_not_create_file(tmp_path, outcome: str) -> None:
    path = tmp_path / "events.jsonl"

    with pytest.raises(ValueError, match="outcome"):
        SelfUseLedger(path).record(make_event(outcome=outcome))

    assert not path.exists()


@pytest.mark.parametrize("trade_date", ["2026-02-30", "2026/07/11", "20260711"])
def test_invalid_trade_date_does_not_create_file(tmp_path, trade_date: str) -> None:
    path = tmp_path / "events.jsonl"

    with pytest.raises(ValueError, match="trade_date"):
        SelfUseLedger(path).record(make_event(trade_date=trade_date))

    assert not path.exists()


def test_invalid_schema_version_does_not_create_file(tmp_path) -> None:
    path = tmp_path / "events.jsonl"

    with pytest.raises(ValueError, match="schema_version"):
        SelfUseLedger(path).record(make_event(schema_version=2))

    assert not path.exists()


def test_record_redacts_and_limits_note_and_redacts_run_id(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    secret = "sk-" + "supersecret12345678"

    saved = SelfUseLedger(path).record(
        make_event(
            note=f"  token={secret} " + "x" * 1100,
            run_id=f"authorization={secret}",
        )
    )

    assert secret not in saved.note
    assert saved.note.startswith("[REDACTED]")
    assert len(saved.note) == 1000
    assert saved.run_id == "[REDACTED]"
    assert secret not in path.read_text(encoding="utf-8")


def test_record_appends_to_existing_line_and_loads_validated_events(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    first = make_event(
        workflow="theme_research",
        recorded_at="2026-07-11T09:00:00+08:00",
    )
    path.write_text(json.dumps(first.__dict__, ensure_ascii=False) + "\n", encoding="utf-8")

    SelfUseLedger(path).record(make_event(workflow="stock_research"))

    loaded = SelfUseLedger(path).load()
    assert [event.workflow for event in loaded] == ["theme_research", "stock_research"]
    assert all(event.recorded_at for event in loaded)
    assert datetime.fromisoformat(loaded[1].recorded_at or "").tzinfo is not None


def test_load_missing_file_returns_empty_list(tmp_path) -> None:
    assert SelfUseLedger(tmp_path / "missing.jsonl").load() == []


def test_load_reports_path_line_and_cause_for_malformed_json(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    first = asdict(make_event(recorded_at="2026-07-11T09:00:00+08:00"))
    path.write_text(json.dumps(first) + '\n{"workflow": ', encoding="utf-8")

    with pytest.raises(SelfUseLedgerIntegrityError) as exc_info:
        SelfUseLedger(path).load()

    assert str(path) in str(exc_info.value)
    assert "line 2" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.pop("workflow"),
        lambda payload: payload.pop("recorded_at"),
        lambda payload: payload.update({"unexpected": True}),
        lambda payload: payload.update({"recorded_at": None}),
    ],
    ids=[
        "missing-required-field",
        "missing-recorded-at",
        "extra-field",
        "null-recorded-at",
    ],
)
def test_load_wraps_schema_errors_without_backfilling_recorded_at(
    tmp_path, mutation
) -> None:
    path = tmp_path / "events.jsonl"
    payload = asdict(make_event(recorded_at="2026-07-11T09:00:00+08:00"))
    mutation(payload)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(SelfUseLedgerIntegrityError) as exc_info:
        SelfUseLedger(path).load()

    assert str(path) in str(exc_info.value)
    assert "line 1" in str(exc_info.value)
    assert exc_info.value.__cause__ is not None


def test_failed_replace_leaves_existing_ledger_unchanged(tmp_path, monkeypatch) -> None:
    path = tmp_path / "events.jsonl"
    original = b'{"existing": true}\n'
    path.write_bytes(original)

    def fail_replace(_source, _destination) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(self_use_maturity.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated"):
        SelfUseLedger(path).record(make_event())

    assert path.read_bytes() == original
    assert list(tmp_path.glob(".events.jsonl.*.tmp")) == []


def test_record_fsyncs_file_then_replaces_then_fsyncs_parent(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "events.jsonl"
    calls: list[str] = []
    real_fsync = os.fsync
    real_replace = os.replace

    def tracking_fsync(fd: int) -> None:
        calls.append("dir_fsync" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file_fsync")
        real_fsync(fd)

    def tracking_replace(source, destination) -> None:
        calls.append("replace")
        real_replace(source, destination)

    monkeypatch.setattr(self_use_maturity.os, "fsync", tracking_fsync)
    monkeypatch.setattr(self_use_maturity.os, "replace", tracking_replace)

    SelfUseLedger(path).record(make_event())

    assert calls == ["file_fsync", "replace", "dir_fsync"]
    assert len(SelfUseLedger(path).load()) == 1


def test_concurrent_processes_do_not_lose_appends(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    context = multiprocessing.get_context("spawn")
    start_event = context.Event()
    processes = [
        context.Process(target=_record_from_process, args=(str(path), start_event, index))
        for index in range(8)
    ]
    for process in processes:
        process.start()
    start_event.set()
    for process in processes:
        process.join(timeout=15)

    assert [process.exitcode for process in processes] == [0] * len(processes)
    assert {event.run_id for event in SelfUseLedger(path).load()} == {
        f"run_{index}" for index in range(8)
    }


def test_concurrent_record_once_deduplicates_atomically(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    context = multiprocessing.get_context("spawn")
    start_event = context.Event()
    processes = [
        context.Process(target=_record_once_from_process, args=(str(path), start_event))
        for _ in range(8)
    ]
    for process in processes:
        process.start()
    start_event.set()
    for process in processes:
        process.join(timeout=15)

    assert [process.exitcode for process in processes] == [0] * len(processes)
    assert len(SelfUseLedger(path).load()) == 1


def test_verify_run_binding_accepts_any_named_backend(tmp_path) -> None:
    """门禁证明的是"模型确有参与"，不是"用了哪一家"。

    回归：provider/model 曾硬绑定 zhipu/glm-5.2。用户 Keychain 实际存的是
    openai/gpt-5.6-sol，旧逻辑会以 model binding mismatch 拒收每一条真实
    run，十天台账一条都记不进去；顺带也封死了三路 backend 对比。
    """
    store = RunStore("tester", root=tmp_path / "runs")
    make_completed_run(
        store, "run-gpt", llm_provider="openai", llm_model="gpt-5.6-sol"
    )

    evidence = verify_run_binding(store, "run-gpt")

    assert evidence.llm_provider == "openai"
    assert evidence.llm_model == "gpt-5.6-sol"
    assert evidence.llm_used is True


def test_verify_run_binding_still_requires_a_named_backend(tmp_path) -> None:
    """记不出用了什么模型的 run 无法复核，仍然拒收。"""
    store = RunStore("tester", root=tmp_path / "runs")
    make_completed_run(store, "run-anon", llm_provider="", llm_model="")

    with pytest.raises(RunBindingError, match="provider/model"):
        verify_run_binding(store, "run-anon")


def test_verify_run_binding_can_still_pin_a_backend_on_request(tmp_path) -> None:
    """按 backend 分层验收时可显式限定；默认不限定。"""
    store = RunStore("tester", root=tmp_path / "runs")
    make_completed_run(
        store, "run-gpt2", llm_provider="openai", llm_model="gpt-5.6-sol"
    )

    verify_run_binding(store, "run-gpt2", require_provider="openai")

    with pytest.raises(RunBindingError, match="provider mismatch"):
        verify_run_binding(store, "run-gpt2", require_provider="zhipu")
    with pytest.raises(RunBindingError, match="model mismatch"):
        verify_run_binding(store, "run-gpt2", require_model="glm-5.2")


# ---------------------------------------------------------------------------
# 真实性 vs 成功性：两者绑在一起时，台账只剩好消息
# ---------------------------------------------------------------------------


def _make_failed_run(store: RunStore, run_id: str, *, error: str = "stage timeout") -> str:
    """失败的 run：没有 report.json / SSE report.complete，这是失败的常态形状。"""
    from intelligence.services import run_store as run_store_module

    run_dir = store.run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = run_store_module.Run(
        run_id=run_id,
        user="tester",
        question="q",
        task_type="conversation",
        status="failed",
        degrades=["stage_timeout"],
        error=error,
    )
    (run_dir / "run.json").write_text(
        json.dumps(asdict(payload), ensure_ascii=False), encoding="utf-8"
    )
    return run_id


def test_template_fallback_is_recordable_as_degraded(tmp_path) -> None:
    """模板回退必须能按 degraded 入账。

    它此前被 success 档的规则整条拒收——而「回答都是降级模板」正是用户停用
    产品的原因。记不下停用原因的台账，读数只能是 0。
    """
    store = RunStore("tester", root=tmp_path / "runs")
    make_completed_run(store, "run-tpl", llm_used=False, degrade=LLM_FALLBACK_DEGRADE)

    with pytest.raises(RunBindingError, match="template answer"):
        verify_run_binding(store, "run-tpl", outcome="success")

    evidence = verify_run_binding(store, "run-tpl", outcome="degraded")
    assert evidence.status == "completed"
    assert evidence.llm_used is False


def test_failed_run_is_recordable_without_report_evidence(tmp_path) -> None:
    """失败的 run 没有 report.json，要求它就等于让「失败」这一档不可记录。"""
    store = RunStore("tester", root=tmp_path / "runs")
    _make_failed_run(store, "run-fail")

    with pytest.raises(RunBindingError, match="terminal-successful"):
        verify_run_binding(store, "run-fail", outcome="success")

    evidence = verify_run_binding(store, "run-fail", outcome="failed")
    assert evidence.status == "failed"
    assert evidence.report_as_of == ""


def test_failed_outcome_still_requires_the_run_to_corroborate_failure(tmp_path) -> None:
    """反伪造不能被削弱：不能拿一个成功的 run 去登记一次失败。"""
    store = RunStore("tester", root=tmp_path / "runs")
    make_completed_run(store, "run-ok-2")

    with pytest.raises(RunBindingError, match="completed successfully"):
        verify_run_binding(store, "run-ok-2", outcome="failed")


def test_failed_outcome_requires_error_or_degrades(tmp_path) -> None:
    """非成功终态但既无 error 也无 degrades 的 run，不足以佐证一次失败。"""
    from intelligence.services import run_store as run_store_module

    store = RunStore("tester", root=tmp_path / "runs")
    run_dir = store.run_dir("run-blank")
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = run_store_module.Run(
        run_id="run-blank",
        user="tester",
        question="q",
        task_type="conversation",
        status="failed",
    )
    (run_dir / "run.json").write_text(
        json.dumps(asdict(payload), ensure_ascii=False), encoding="utf-8"
    )

    with pytest.raises(RunBindingError, match="neither error nor degrades"):
        verify_run_binding(store, "run-blank", outcome="failed")
