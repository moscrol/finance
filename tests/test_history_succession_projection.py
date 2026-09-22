"""Saved failure shape -> real projection -> writer/reviewer/recovery consumers.

Scripted consumers test delivery, not a real model's autonomous interpretation.
No production DB, user data or external service is required.
"""

from copy import deepcopy
from dataclasses import replace
import json

import duckdb
import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.episode_finalizer import EpisodeFinalizer
from intelligence.services.agent_research import evidence_content_hash
from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent, ModelToolCall, ModelTurn, OutputEvidenceBinding
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_semantic_verifier import _project_semantic_evidence
from intelligence.services.historical_research.episode import HistorySession, _result
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.run_store import RunStore
from intelligence.tests.test_episode_finalizer import RecordingModel
from tests.test_history_market_anatomy import anatomy_db as _anatomy_db, record, run
from tests.test_history_model_projection import REF, _project

anatomy_db = _anatomy_db


def _legacy_live_payload():
    """Exact six pair rows + calendar/spec excerpt of the rejected fbd8 turn 3.

    Original: run_20260918_092551_590812/history-query-461de0b134934e8e572c5b2677581da6f63992c43fcb255633f1e04531a227f4.json
    File SHA256: 461de0b134934e8e572c5b2677581da6f63992c43fcb255633f1e04531a227f4
    Query ID: 09985a6d9c186e0bcd2f2ccf48876e0368e093ba90a0aeda503e8f9e1fc3f7a5
    This reduced projection fixture is NOT a re-sealed computational original.
    """
    codes = ["990026.FP", "990065.FP", "990078.FP"]
    days = [f"2026-08-{d}" for d in (24, 25, 26, 27, 28, 31)] + [
        f"2026-09-{d:02d}" for d in (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15)
    ]
    rows = [dict(
        record_kind="sector_succession", entity_kind="sector", entity_code=target, source_sector=source,
        anchor_peak_date="2026-09-11" if source == codes[2] else "2026-09-15",
        start="2026-09-14" if source == codes[2] else "2026-09-15", end="2026-09-15",
        source_peak_status="window_peak_unconfirmed", source_peak_confirmation_date=None,
        succession_known_as_of="2026-09-15", target_signal_date="2026-09-09" if target == codes[2] else "2026-09-07",
        lag_trading_days=None, succession_status="immature", causal_status="not_established",
        evidence=dict(source_return_pct=None, target_return_pct=None, target_relative_return_pct=None),
    ) for source in codes for target in codes if source != target]
    return dict(
        query_id="09985a6d9c186e0bcd2f2ccf48876e0368e093ba90a0aeda503e8f9e1fc3f7a5",
        operation="trace_history", status="research_only", total_matched=6, returned_count=6, truncated=False,
        spec=dict(start="2026-08-24", end="2026-09-15", entity_codes=codes),
        analysis_definition={"version": "history-anatomy-v1"},
        calendar_inputs=[dict(stock_dates=days, market_dates=days)], rows=rows, preview=deepcopy(rows),
    )


def _cards(payload):
    model, details = _project(_result(payload, result_ref=REF))
    pairs = [row for row in details if row.get("record_kind") == "sector_succession"]
    assert not any(row.get("projection_status") for row in details)
    return model, pairs


def test_saved_live_pairs_deliver_atomic_status_reason_and_actual_observation_dates():
    payload = _legacy_live_payload()
    frozen = deepcopy(payload)
    _, pairs = _cards(payload)
    states = [r for r in pairs if "succession_status" in r]
    assert len(states) == 6
    assert [r["observed_days"] for r in states] == [0, 0, 0, 0, 2, 2]
    for card in states:
        assert card["source_sector"] != card["entity_code"]
        assert card["succession_status"] == "immature"
        assert card["required_days"] == 5
        assert "尚不能判成败" in card["meaning"] and "无需先回撤确认" in card["meaning"]
        assert "source_peak_confirmation_date" not in card  # Not a null masquerading as a cause.
    windows = [r for r in pairs if "outcome_dates" in r]
    assert [r["outcome_dates"] for r in windows] == [[]] * 4 + [["2026-09-14", "2026-09-15"]] * 2
    assert all("非目标信号后5日" in r["succession_rule"] for r in pairs if "succession_rule" in r)
    assert all(r["return_window"] == "source_peak_next5" for r in pairs if "succession_evidence" in r)
    assert payload == frozen  # Reading old originals must not migrate/reseal them.


def test_legacy_calendar_absence_is_unknown_not_zero_and_later_dates_do_not_expand_window():
    original = _legacy_live_payload()
    extended = deepcopy(original)
    extended["calendar_inputs"][0]["stock_dates"] += ["2026-09-16", "2026-09-17", "2026-09-18"]
    assert _cards(extended) == _cards(original)
    del original["calendar_inputs"]
    _, pairs = _cards(original)
    assert all(r["observed_days"] is None for r in pairs if "succession_status" in r)
    assert all(r["outcome_dates"] is None for r in pairs if "outcome_dates" in r)


@pytest.mark.parametrize(("state", "meaning"), [
    ("not_observed", "未触发"), ("missing", "非0、非条件失败"),
    ("outside_succession_window", "本口径不入选"), ("not_supported", "非永久失败"),
    ("candidate_not_causal", "仅候选"),
])
@pytest.mark.parametrize("confirmed", [False, True])
def test_each_state_and_its_limits_fit_one_citable_card(state, meaning, confirmed):
    payload = _legacy_live_payload()
    payload["analysis_definition"]["version"] = "history-anatomy-v1.1"
    row = dict(payload["rows"][0], succession_status=state,
               outcome_dates=[f"2026-09-{d:02d}" for d in (9, 10, 11, 14, 15)], outcome_required_days=5,
               target_signal_status="observed", anchor_peak_date="2026-09-08",
               source_peak_status="drawdown_confirmed_retrospectively" if confirmed else "window_peak_unconfirmed",
               source_peak_confirmation_date="2026-09-15" if confirmed else None)
    payload.update(rows=[row], preview=[row])
    _, pairs = _cards(payload)
    card = next(r for r in pairs if "succession_status" in r)
    assert card["succession_status"] == state
    assert card["observed_days"] == card["required_days"] == 5
    assert meaning in card["meaning"]
    confirmation = next(r for r in pairs if "source_peak_confirmation_date" in r)
    assert confirmation["source_peak_confirmation_date"] == row["source_peak_confirmation_date"]
    assert "成熟度独立" in confirmation["meaning"]


def test_cross_turn_read_projects_legacy_saved_calendar_without_opening_a_database(tmp_path, monkeypatch):
    from intelligence.services.episode_tools import build_episode_registry

    payload = _legacy_live_payload()
    store = RunStore("succession-read-test", root=tmp_path / "runs")
    old = store.create_run("历史板块接力", "ask", session_id="same-conversation")
    old_session = HistorySession(store, old.run_id, old.session_id)
    ref = old_session.save("query", payload)
    saved_path = store.run_dir(old.run_id) / ref.split("/", 1)[1]
    saved_bytes = saved_path.read_bytes()
    question = "不要联网。以2026-09-15为信息截止日，只研究2026-08-24至2026-09-15。板块见顶后哪些板块接力、有什么证据？"
    current = store.create_run(question, "ask", session_id=old.session_id)
    session = HistorySession(store, current.run_id, current.session_id)
    frame = understand_query(question).task_frame
    context = build_episode_context(frame, task_id=current.run_id, today="2026-09-15", latest_data_date="2026-09-15", capabilities=("finance_query",))
    registry = build_episode_registry(frame, context, finance_root=tmp_path / "no-db", knowledge_wiki=tmp_path / "no-wiki", history_session=session)

    def deny_db(*args, **kwargs):
        pytest.fail("read_history_result must use saved calendar, not a live DB")

    monkeypatch.setattr(duckdb, "connect", deny_db)
    observed = registry.execute("read_history_result", {"result_ref": ref, "offset": 4, "limit": 2}, context=context, step_id="read-old")
    _, details = _project(observed)
    states = [r for r in details if "succession_status" in r]
    assert len(states) == 2 and all(r["observed_days"] == 2 for r in states)
    assert all(r["source_sector"] == "990078.FP" and "尚不能判成败" in r["meaning"] for r in states)
    assert context.history_results[-1]["result_ref"] == ref
    assert saved_path.read_bytes() == saved_bytes


def test_unknown_definition_is_not_explained_using_current_rules():
    payload = _legacy_live_payload()
    payload["analysis_definition"]["version"] = "future-definition"
    _, cards = _cards(payload)
    assert all("未识别" in r["meaning"] for r in cards)
    assert not any("observed_days" in r for r in cards)


@pytest.mark.parametrize("binding", [False, True])
def test_citing_only_pair_status_delivers_reason_to_actual_semantic_review_projection(binding):
    evidence = tuple(replace(e, content_hash=evidence_content_hash(e)) for e in _result(_legacy_live_payload(), result_ref=REF).evidence)
    ordinal, card = next((i, e) for i, e in enumerate(evidence, 1) if '"succession_status"' in e.detail)
    outcome = AgentOutcome(
        task_frame_hash="succession-review", status="partial", draft=f"观察未满，不能判失败 [E{ordinal}]。",
        evidence=evidence, traces=(), gaps=(), stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": "succession-review"}),), usage=AgentUsage(),
        bindings=(OutputEvidenceBinding("direct_assessment", (card.content_hash,)),) if binding else (),
    )
    _, registry, telemetry = _project_semantic_evidence(outcome)
    assert len(registry) == 1  # No global rule cards smuggled into the assertion.
    reviewed = json.loads(registry[0]["detail"])
    assert reviewed["observed_days"] == 0 and reviewed["succession_status"] == "immature"
    assert "尚不能判成败" in reviewed["meaning"]
    assert "无需先回撤确认" in reviewed["meaning"]
    assert registry[0]["evidence_id"] == f"E{ordinal}"
    assert telemetry.cited_unbound_count == (0 if binding else 1)


def _registry(path, tmp_path):
    from intelligence.services.episode_tools import build_episode_registry

    question = "不要联网。以2026-01-29为信息截止日，只研究2026-01-05至2026-01-29。板块见顶后哪些板块接力、有什么证据？"
    frame = understand_query(question).task_frame
    assert frame.history_intent is not None
    root = tmp_path / "finance"
    (root / "db").mkdir(parents=True)
    local = root / "db" / "market_feature_store.duckdb"
    local.write_bytes(path.read_bytes())
    store = RunStore("succession-test", root=tmp_path / "runs")
    run = store.create_run(question, "ask", session_id="succession-test")
    session = HistorySession(store, run.run_id, run.session_id)
    context = build_episode_context(frame, task_id=run.run_id, today="2026-01-29", latest_data_date="2026-01-29", capabilities=("finance_query",))
    registry = build_episode_registry(frame, context, finance_root=root, knowledge_wiki=tmp_path / "wiki", history_session=session)
    return registry, context, frame, session, local


def test_real_episode_consumer_uses_observed_days_not_null_confirmation(anatomy_db, tmp_path):
    registry, context, frame, session, path = _registry(anatomy_db, tmp_path)
    before = path.read_bytes()

    class Model:
        seen = False

        def complete(self, *, messages, tools, timeout):
            observed = [json.loads(m["content"]) for m in messages if m.get("role") == "tool"]
            if not observed:
                return ModelTurn("", (ModelToolCall("trace", "history_query", dict(operation="trace_history", start="2026-01-05", end="2026-01-14", entity_codes=["A.FP", "B.FP"])),), "scripted", "")
            assert len(observed) == 1
            pairs = [(e, json.loads(e["detail"])) for e in observed[0]["evidence"]]
            e, row = next((e, r) for e, r in pairs if r.get("succession_status") == "immature")
            assert row["observed_days"] == 2 and row["required_days"] == 5
            assert "尚不能判成败" in row["meaning"] and "无需先回撤确认" in row["meaning"]
            self.seen = True
            text = f"来源{row['source_sector']}→目标{row['entity_code']}：源峰后仅观察{row['observed_days']}/{row['required_days']}个交易日，接力观察未成熟、不能判失败，也不要求先有10%回撤确认。[{e['evidence_id']}]"
            gap = "未完成条件全集和方法验证；仅验证脚本消费链。"
            content = observed[0]["observation"]
            meta, _ = json.JSONDecoder().raw_decode(content[content.index("{"):])
            return ModelTurn(json.dumps(dict(
                status="partial", draft=text, gaps=[gap],
                bindings=[dict(output_id=o.output_id, evidence_hashes=[e["evidence_id"]]) if o.output_id == "direct_assessment" else dict(output_id=o.output_id, evidence_hashes=[], gap=gap) for o in context.contract.required_outputs],
                history_research=dict(purpose=context.history_intent.purpose, result_refs=[meta["result_ref"]], claim_level="single_case", research_only=True, decision_eligible=False, promotion_eligible=False),
            ), ensure_ascii=False), (), "scripted", "")

    model = Model()
    outcome = ContinuousAgentEpisode(model).run(task_frame=frame, context=context, registry=registry)
    assert model.seen and outcome.stop_reason == "model_finish", [(e.kind, e.payload) for e in outcome.events if e.kind == "invalid_action"]
    assert "2/5个交易日" in outcome.draft and "不能判失败" in outcome.draft
    assert len(session.refs) == 1 and path.read_bytes() == before
    artifact = session.read(next(iter(session.refs)))
    row = next(r for r in artifact["rows"] if r["record_kind"] == "sector_succession")
    assert row["outcome_dates"] == ["2026-01-13", "2026-01-14"]
    assert artifact["knowledge_cutoff"] == "2026-01-29"  # A later cutoff must not lengthen the observation.


def test_actual_recovery_retains_all_six_saved_pair_states_before_nav_and_members(tmp_path):
    from intelligence.tests.test_episode_finalizer import _context, _frame
    from intelligence.services.historical_research.intent import HistoryIntent

    payload = _legacy_live_payload()
    # Launch metrics used to displace the pair conclusions in the 12-card budget.
    noise = [dict(entity_code="990026.FP", start="2026-08-24", end="2026-09-15", features={f"fixture_metric_{i}": i}, feature_coverage={}) for i in range(12)]
    payload["preview"] = noise + payload["rows"]
    evidence = tuple(replace(e, content_hash=evidence_content_hash(e)) for e in _result(payload, result_ref=REF).evidence)
    frame = replace(_frame(), history_intent=HistoryIntent("historical_comparison"))
    context = replace(_context(frame), history_intent=frame.history_intent)
    priority = FinanceResearchHarness().recovery_evidence_priority(context=context, evidence=evidence)
    model = RecordingModel(ModelTurn("{}", (), "recording", ""))
    EpisodeFinalizer(model).recover(task_frame=frame, context=context, evidence=evidence, gaps=("脚本恢复",), failure_reason="provider_error", evidence_priority=priority)
    sent = json.loads(model.calls[0]["messages"][1]["content"])
    states = [json.loads(r["detail"]) for r in sent["evidence"] if '"succession_status"' in r["detail"]]
    assert len(sent["evidence"]) == 12
    assert len(states) == 6
    assert [r["observed_days"] for r in states] == [0, 0, 0, 0, 2, 2]
    assert all("尚不能判成败" in r["meaning"] for r in states)
    assert sent["evidence_selection"]["omitted"] > 0


def test_calculator_records_same_peak_next5_dates_without_confirmation_prerequisite(anatomy_db):
    with duckdb.connect(str(anatomy_db)) as con:
        con.execute("UPDATE fact_sector_daily SET pct_chg=-1 WHERE sector_ts_code='A.FP' AND trade_date>'2026-01-12'")
        con.execute("UPDATE fact_sector_daily SET pct_chg=-2 WHERE sector_ts_code='B.FP' AND trade_date IN ('2026-01-13', '2026-01-14')")
    original = anatomy_db.read_bytes()
    result = run(anatomy_db, end="2026-01-19")
    row = record(result, "sector_succession", "B.FP")
    assert row["source_peak_status"] == "window_peak_unconfirmed" and row["source_peak_confirmation_date"] is None
    assert row["outcome_dates"] == [f"2026-01-{d}" for d in range(13, 18)]
    assert row["outcome_required_days"] == 5
    assert row["target_signal_date"] == "2026-01-15" and row["target_signal_status"] == "observed"
    assert row["lag_trading_days"] == 3 and row["succession_status"] == "candidate_not_causal"
    # -2%, -2%, +5%, +5%, +5% over SOURCE's post-peak window, not target's.
    # Both 5-day windows are mature and their numeric answers differ.
    assert row["evidence"]["target_return_pct"] == pytest.approx((.98**2 * 1.05**3 - 1) * 100)
    assert row["evidence"]["target_return_pct"] != pytest.approx((1.05**3 * .96**2 - 1) * 100)
    assert row["evidence"]["source_return_pct"] == pytest.approx((.99**5 - 1) * 100)
    assert anatomy_db.read_bytes() == original


@pytest.mark.parametrize(("change", "state", "signal_state"), [
    ("diff_ratio=0", "not_observed", "not_observed"),
    ("diff_ratio=CASE WHEN trade_date='2026-01-11' THEN NULL ELSE diff_ratio END", "missing", "observed_with_earlier_gaps"),
    ("pct_chg=CASE WHEN trade_date='2026-01-16' THEN NULL ELSE pct_chg END", "missing", "observed"),
    ("pct_chg=CASE WHEN trade_date='2026-01-13' THEN -50 ELSE pct_chg END", "not_supported", "observed"),
])
def test_mature_observation_does_not_collapse_missing_nontriggered_and_failed_returns(anatomy_db, change, state, signal_state):
    with duckdb.connect(str(anatomy_db)) as con:
        con.execute(f"UPDATE fact_sector_daily SET {change} WHERE sector_ts_code='B.FP'")
    payload = run(anatomy_db)
    row = record(payload, "sector_succession", "B.FP")
    assert row["succession_status"] == state and row["target_signal_status"] == signal_state
    assert len(row["outcome_dates"]) == 5
    _, cards = _cards(payload)
    card = next(r for r in cards if r.get("succession_status") == state and r["entity_code"] == "B.FP")
    assert card["observed_days"] == 5
    if state in {"missing", "not_observed"}:
        assert row["evidence"]["target_return_pct"] is None
    else:
        assert row["evidence"]["target_return_pct"] < 0


@pytest.mark.parametrize(("signal_day", "expected", "lag"), [(12, "outside_succession_window", None), (17, "candidate_not_causal", 5), (18, "outside_succession_window", None)])
def test_target_signal_window_excludes_peak_includes_fifth_but_not_sixth_date(anatomy_db, signal_day, expected, lag):
    with duckdb.connect(str(anatomy_db)) as con:
        con.execute("UPDATE fact_sector_daily SET pct_chg=1, diff_ratio=CASE WHEN trade_date=? THEN 11 ELSE 0 END WHERE sector_ts_code='B.FP'", [f"2026-01-{signal_day}"])
    row = record(run(anatomy_db), "sector_succession", "B.FP")
    assert row["succession_status"] == expected
    assert row["lag_trading_days"] == lag
    assert row["outcome_dates"] == [f"2026-01-{d}" for d in range(13, 18)]


@pytest.mark.parametrize(("end", "expected"), [("2026-01-12", []), ("2026-01-14", ["2026-01-13", "2026-01-14"])])
def test_calculator_observation_calendar_is_not_faked_from_placeholder_dates(anatomy_db, end, expected):
    row = record(run(anatomy_db, end=end), "sector_succession", "B.FP")
    assert row["outcome_dates"] == expected
    assert row["succession_status"] == "immature"
    assert row["outcome_required_days"] == 5


def test_new_observation_fields_are_independently_audited_and_old_definition_is_still_supported(anatomy_db, tmp_path):
    from scripts.audit_historical_research_artifacts import audit_artifact
    from scripts.history_anatomy_arithmetic import TRACE_DEFINITION
    from tests.test_history_artifact_audit import seal

    payload = run(anatomy_db)
    path = tmp_path / "artifact.json"

    def audit(doc):
        source_refs = deepcopy(doc["source_refs"])
        sealed = seal(doc)
        sealed["source_refs"] = source_refs
        sealed["preview"] = deepcopy(sealed["rows"][:sealed["returned_count"]])
        path.write_text(json.dumps(sealed))
        return audit_artifact(path)

    assert not audit(deepcopy(payload))["errors"]
    for field, value in [("outcome_dates", []), ("outcome_required_days", 4), ("target_signal_status", "missing")]:
        bad = deepcopy(payload)
        record(bad, "sector_succession", "B.FP")[field] = value
        assert f"succession.{field}" in {r["field"] for r in audit(bad)["errors"]}
    bad = deepcopy(payload)
    del record(bad, "sector_succession", "B.FP")["outcome_dates"]
    assert "succession.outcome_dates" in {r["field"] for r in audit(bad)["errors"]}
    legacy = deepcopy(payload)
    legacy["analysis_definition"] = deepcopy(TRACE_DEFINITION)
    legacy["feature_definitions"]["trace_history"] = deepcopy(TRACE_DEFINITION)
    for row in legacy["rows"]:
        for field in ("outcome_dates", "outcome_required_days", "target_signal_status"):
            row.pop(field, None)
    assert not audit(legacy)["errors"]
