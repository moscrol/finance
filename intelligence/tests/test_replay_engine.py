"""历史重放引擎（INDEX #25）：PIT 分档 / 输入前视门 / 两臂提示词 / 答卷校验 / 判分窗口 / memory_bucket / 分格闸。

变异测试（记进交接）：
① ``outcomes.WINDOW_START_OFFSET`` 改 0（窗口含 D0 = 前视）→ ``test_eval_date_uses_next_trading_day`` 与
   ``test_judge_direction_reads_window_after_d0`` 必须变红（selftest 的前视对照也会红）。
② ``build_anon_map`` 漏掉 dates 映射 → ``test_two_arms_differ_only_at_mapped_positions`` 必须变红
   （匿名臂 fail-closed 断言直接抛错），selftest 的记忆对照失效（两臂都看得到日期，gap → 0）。
"""

from __future__ import annotations

import gzip
import importlib.util
import json
import sys
from pathlib import Path

import duckdb
import pytest

from intelligence.eval import replay_engine as engine
from intelligence.services.checkpoints import DEFAULT_CALIBRATION_MIN_N
from intelligence.services.methodology_backtest.labels import build_labels
from intelligence.services.methodology_backtest.outcomes import build_outcomes

REPO = Path(__file__).resolve().parents[2]
SELFTEST = REPO / "scripts" / "methodology_backtest_selftest.py"
REPLAY_SELFTEST = REPO / "scripts" / "replay_engine_selftest.py"


def _load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    st = _load_script(SELFTEST, "mb_selftest_for_replay_tests")
    root = tmp_path_factory.mktemp("replay-synthetic")
    src = root / "src.duckdb"
    lab = root / "labels.duckdb"
    st.build_sample_db(src, n_days=120, n_sectors=12)
    build_labels(src, lab)
    build_outcomes(src, lab, horizons=(1, 3, 5, 7, 10))
    con = duckdb.connect(str(lab), read_only=True)
    try:
        calendar = [str(r[0])[:10] for r in con.execute("SELECT trade_date FROM history_calendar ORDER BY 1").fetchall()]
    finally:
        con.close()
    (root / "snapshots").mkdir()
    return {"st": st, "src": src, "labels": lab, "calendar": calendar, "snapshots": root / "snapshots", "root": root}


def _node(synthetic, as_of: str) -> dict:
    return {"as_of": as_of, "market_stage": "主升阶段", "pit_grade": "trade_date_only", "grade_meta": {"reason": "no_manifest"}, "forced": False}


@pytest.fixture(scope="module")
def replay_input(synthetic):
    as_of = synthetic["calendar"][40]
    return engine.build_replay_input(_node(synthetic, as_of), db_path=synthetic["src"], labels_db=synthetic["labels"], snapshot_root=synthetic["snapshots"])


# --------------------------------------------------------------------------- #
# pit_grade
# --------------------------------------------------------------------------- #
def test_pit_grade_without_manifest_is_trade_date_only(tmp_path):
    grade, meta = engine.pit_grade_for("2026-07-22", tmp_path)
    assert grade == "trade_date_only" and meta["reason"] == "no_manifest"


def test_pit_grade_with_bad_checksum_is_trade_date_only(tmp_path):
    (tmp_path / "2026-07-22.manifest.json").write_text(json.dumps({"compressed_sha256": "deadbeef"}), encoding="utf-8")
    (tmp_path / "2026-07-22.snapshot.json.gz").write_bytes(gzip.compress(b"{}"))
    grade, meta = engine.pit_grade_for("2026-07-22", tmp_path)
    assert grade == "trade_date_only"
    assert "checksum" in meta["reason"]


def test_pit_grade_strict_when_validation_passes(tmp_path, monkeypatch):
    (tmp_path / "2026-07-22.manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        engine,
        "validate_frozen_snapshot",
        lambda root, as_of: {"manifest_sha": "m" * 64, "snapshot_sha256": "s" * 64, "compressed_sha256": "c" * 64, "replay_eligible": True},
    )
    grade, meta = engine.pit_grade_for("2026-07-22", tmp_path)
    assert grade == "strict" and meta["manifest_sha"] == "m" * 64


def test_select_nodes_forces_reconciliation_dates_only_in_strict(synthetic, monkeypatch):
    cal = synthetic["calendar"]
    strict_dates = set(cal[30:50])

    def fake_grade(as_of, root):
        return ("strict", {"manifest_sha": "x"}) if as_of in strict_dates else ("trade_date_only", {"reason": "no_manifest"})

    monkeypatch.setattr(engine, "pit_grade_for", fake_grade)
    nodes = engine.select_nodes(synthetic["src"], cal[0], cal[-11], count_per_grade=5, snapshot_root=synthetic["snapshots"], forced_dates=[cal[31], cal[10]])
    by_grade = {g: [n for n in nodes if n["pit_grade"] == g] for g in engine.PIT_GRADES}
    assert len(by_grade["strict"]) == 5 and len(by_grade["trade_date_only"]) == 5
    assert all(n["as_of"] in strict_dates for n in by_grade["strict"])
    assert all(n["as_of"] not in strict_dates for n in by_grade["trade_date_only"])
    assert [n["as_of"] for n in by_grade["strict"] if n["forced"]] == [cal[31]]
    assert not any(n["forced"] for n in by_grade["trade_date_only"])  # cal[10] 不在 strict 档，不占位


# --------------------------------------------------------------------------- #
# 输入构建：前视门 / 标签 / 日历
# --------------------------------------------------------------------------- #
def test_replay_input_has_labels_rules_calendar_and_boundary(replay_input):
    assert replay_input["pit_grade"] == "trade_date_only"
    assert replay_input["source"]["kind"] == "build_input_snapshot" and replay_input["source"]["strict_updated_at"] is False
    assert replay_input["labels"]["sector"] and replay_input["labels"]["theme"]
    assert set(replay_input["labels"]["market"]) >= {"market_stage", "volume_surge"}
    assert len(replay_input["calendar"]) == engine.CALENDAR_LOOKBACK
    assert replay_input["calendar"][0] == {"trade_date": replay_input["as_of"], "offset": "T-0"}
    assert [r["rule_id"] for r in replay_input["rules"]] == [r.rule_id for r in engine.load_lane_a_rules()]
    assert all("notes" not in r and "provenance" not in r for r in replay_input["rules"])
    assert replay_input["boundary"]["max_embedded_date"] == replay_input["as_of"]
    assert len(replay_input["input_sha256"]) == 64


def test_future_row_is_rejected_and_not_written(replay_input, tmp_path):
    body = json.loads(json.dumps(replay_input))
    as_of = body["as_of"]
    body["sector_day"].append({"trade_date": "2099-01-01", "sector_ts_code": "880000.TI"})
    out = tmp_path / "input.json"
    with pytest.raises(ValueError, match="future date"):
        engine.finalize_replay_input(body, as_of, out_path=out)
    assert not out.exists()


# --------------------------------------------------------------------------- #
# 两臂提示词
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("lane", engine.LANES)
def test_two_arms_differ_only_at_mapped_positions(replay_input, lane):
    anon_map = engine.build_anon_map(replay_input)
    named = engine.render_prompt(replay_input, "named", lane=lane, anon_map=anon_map)
    anon = engine.render_prompt(replay_input, "anonymized", lane=lane, anon_map=anon_map)
    assert named != anon
    assert engine.apply_anon_map(named, anon_map) == anon
    assert not engine.ABSOLUTE_DATE_RE.search(anon)
    for name in anon_map["names"]:
        assert name not in anon
    for code in anon_map["codes"]:
        assert code not in anon
    assert "T-0" in anon and replay_input["as_of"] in named


def test_anonymized_prompt_fails_closed_when_dates_missing(replay_input):
    broken = engine.build_anon_map(replay_input)
    broken["dates"] = {}
    with pytest.raises(ValueError, match="absolute dates"):
        engine.render_prompt(replay_input, "anonymized", lane="B", anon_map=broken)


def test_anon_map_is_reversible(replay_input):
    anon_map = engine.build_anon_map(replay_input)
    code = replay_input["labels"]["sector"][0]["entity_id"]
    alias = anon_map["codes"][code]
    assert alias.startswith("S")
    assert engine.reverse_alias(anon_map, alias) == code
    assert engine.reverse_alias(anon_map, f"{code}(名字)") == code
    assert engine.reverse_alias(None, "S01") == "S01"


# --------------------------------------------------------------------------- #
# 答卷校验
# --------------------------------------------------------------------------- #
def _hyp(**over):
    base = {
        "id": "h1",
        "category": "direction",
        "claim": "880000.TI fwd_return@5 > 0",
        "horizon": "T+5",
        "confidence": "medium",
        "confidence_probability": 0.6,
        "evidence_refs": ["labels.sector"],
        "evidence_as_of": "2026-03-04",
        "falsify_when": "880000.TI fwd_return@5 <= 0",
    }
    base.update(over)
    return base


def _answer(*hyps):
    return {"hypotheses": list(hyps), "picks": []}


CODES = ["880000.TI", "880001.TI", "880002.TI"]


def test_valid_answer_passes_and_keeps_dual_blind_field_names():
    answer = _answer(_hyp(), _hyp(id="h2", claim="880001.TI max_return@3 > 1", horizon="T+3"), _hyp(id="h3", category="market", claim="T+1 涨家数 > 2500", horizon="T+1", falsify_when="T+1 涨家数 <= 1500", rule_id="diff_ratio_turn_up_5d"))
    normalized, errors = engine.validate_replay_answer(answer, as_of="2026-03-04", entity_codes=CODES, rule_ids=["diff_ratio_turn_up_5d"])
    assert errors == []
    assert set(engine.HYPOTHESIS_FIELDS) <= set(normalized["hypotheses"][0])
    assert normalized["hypotheses"][0]["parsed"] == {"entity": "880000.TI", "entity_token": "880000.TI", "metric": "fwd_return", "horizon": 5, "op": ">", "value": 0.0}
    assert normalized["hypotheses"][2]["parsed"]["conditions"] == [["advancers", ">", 2500.0, None]]
    assert normalized["hypotheses"][2]["rule_id"] == "diff_ratio_turn_up_5d"


def test_answer_rejects_target_stock_code_and_future_evidence():
    target = _answer(_hyp(), _hyp(id="h2"), _hyp(id="h3", category="target", claim="000001.SZ 收盘 > 10"))
    _, errors = engine.validate_replay_answer(target, as_of="2026-03-04", entity_codes=CODES)
    assert any("target" in e for e in errors)

    stock = _answer(_hyp(), _hyp(id="h2"), _hyp(id="h3", category="market", claim="T+1 涨家数 > 2500，600519 领涨", horizon="T+1"))
    _, errors = engine.validate_replay_answer(stock, as_of="2026-03-04", entity_codes=CODES)
    assert any("个股代码" in e for e in errors)

    future = _answer(_hyp(), _hyp(id="h2"), _hyp(id="h3", evidence_as_of="2026-03-05"))
    _, errors = engine.validate_replay_answer(future, as_of="2026-03-04", entity_codes=CODES)
    assert any("晚于 D0" in e for e in errors)

    picks = {**_answer(_hyp(), _hyp(id="h2"), _hyp(id="h3")), "picks": [{"code": "000001"}]}
    _, errors = engine.validate_replay_answer(picks, as_of="2026-03-04", entity_codes=CODES)
    assert any("picks" in e for e in errors)


def test_answer_rejects_unknown_entity_bad_claim_shape_and_horizon_mismatch():
    bad_entity = _answer(_hyp(), _hyp(id="h2"), _hyp(id="h3", claim="999999.TI fwd_return@5 > 0", falsify_when="x"))
    _, errors = engine.validate_replay_answer(bad_entity, as_of="2026-03-04", entity_codes=CODES)
    assert any("不在输入的实体表里" in e for e in errors)
    mismatch = _answer(_hyp(), _hyp(id="h2"), _hyp(id="h3", claim="880002.TI fwd_return@3 > 0", horizon="T+5"))
    _, errors = engine.validate_replay_answer(mismatch, as_of="2026-03-04", entity_codes=CODES)
    assert any("不一致" in e for e in errors)
    unparsable = _answer(_hyp(), _hyp(id="h2"), _hyp(id="h3", category="market", claim="明天会涨", horizon="T+1"))
    _, errors = engine.validate_replay_answer(unparsable, as_of="2026-03-04", entity_codes=CODES)
    assert any("抽不出数值条件" in e for e in errors)
    too_few = _answer(_hyp(), _hyp(id="h2"))
    _, errors = engine.validate_replay_answer(too_few, as_of="2026-03-04", entity_codes=CODES)
    assert any("数量" in e for e in errors)


def test_anonymized_answer_resolves_alias_and_relative_date():
    anon_map = {"codes": {"880000.TI": "S01"}, "dates": {"2026-03-04": "T-0", "2026-03-03": "T-1"}}
    answer = _answer(
        _hyp(claim="S01 fwd_return@5 > 0", evidence_as_of="T-1", falsify_when="S01 fwd_return@5 <= 0"),
        _hyp(id="h2", claim="S01 max_return@3 > 0", horizon="T+3", evidence_as_of="T-0"),
        _hyp(id="h3", category="market", claim="涨家数 > 2000", horizon="T+1", evidence_as_of="T-0", falsify_when="涨家数 < 1000"),
    )
    normalized, errors = engine.validate_replay_answer(answer, as_of="2026-03-04", arm="anonymized", anon_map=anon_map, entity_codes=CODES)
    assert errors == []
    assert normalized["hypotheses"][0]["parsed"]["entity"] == "880000.TI"
    assert normalized["hypotheses"][0]["evidence_as_of_resolved"] == "2026-03-03"
    named_with_alias = _answer(_hyp(claim="S01 fwd_return@5 > 0"), _hyp(id="h2"), _hyp(id="h3"))
    _, errors = engine.validate_replay_answer(named_with_alias, as_of="2026-03-04", arm="named", anon_map=anon_map, entity_codes=CODES)
    assert errors


def test_stock_code_detection_ignores_sector_codes():
    assert engine.stock_codes_in("990147.FP fwd_return@5 > 0", known_codes=["990147.FP"]) == []
    assert engine.stock_codes_in("990147 涨", known_codes=["990147.FP"]) == []
    assert engine.stock_codes_in("600519.SH 站稳 1800") == ["600519.SH"]
    assert engine.stock_codes_in("300750 领涨") == ["300750"]


# --------------------------------------------------------------------------- #
# 车道 A / 判分 / 窗口
# --------------------------------------------------------------------------- #
def test_compare_triggers_and_lane_a_parse():
    cmp = engine.compare_triggers(["a", "b", "c"], ["b", "c", "d"])
    assert (cmp["tp"], cmp["fp"], cmp["fn"], cmp["exact"]) == (2, 1, 1, False)
    assert engine.compare_triggers([], [])["exact"] is True and engine.compare_triggers([], [])["precision"] == 1.0
    parsed, errors = engine.parse_lane_a_answer({"rule_triggers": {"r1": ["S01", "S02"]}}, rule_ids=["r1", "r2"], anon_map={"codes": {"880000.TI": "S01", "880001.TI": "S02"}})
    assert parsed == {"r1": ["880000.TI", "880001.TI"], "r2": []}
    assert errors == ["rule_triggers 缺 r2"]


def test_expected_triggers_match_planted_events(synthetic):
    st = synthetic["st"]
    cal = synthetic["calendar"]
    con = duckdb.connect(str(synthetic["labels"]), read_only=True)
    try:
        rules = engine.load_lane_a_rules()
        event_day = cal[st.EVENT_FIRST]
        expected = engine.expected_triggers(con, rules, event_day)
        assert expected["diff_ratio_turn_up_5d"]  # 事件日 diff -5 → +25 就是拐点
        restricted = engine.expected_triggers(con, rules, event_day, restrict_to=expected["diff_ratio_turn_up_5d"][:1])
        assert restricted["diff_ratio_turn_up_5d"] == expected["diff_ratio_turn_up_5d"][:1]
    finally:
        con.close()


def test_eval_date_uses_next_trading_day():
    cal = ["2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05", "2026-03-06"]
    assert engine._eval_date(cal, "2026-03-02", 1) == "2026-03-03"
    assert engine._eval_date(cal, "2026-03-02", 3) == "2026-03-05"
    assert engine._eval_date(cal, "2026-03-05", 3) is None
    assert engine.WINDOW_START_OFFSET == 1


def test_judge_direction_reads_window_after_d0(synthetic):
    """事件日 e 的板块：D0 = e+5 是最后一个 +2% 日，D0+1 = -15%。fwd_return@1 > 0 必须 miss；
    窗口若含 D0（WINDOW_START_OFFSET=0）就会读到 D0 自己的 +2% 变 hit。"""
    st = synthetic["st"]
    cal = synthetic["calendar"]
    sector = 0
    code = f"{880000 + sector}.TI"
    e = st.event_days(sector, len(cal))[1]
    as_of = cal[e + 5]
    answer = {
        "hypotheses": [
            {"id": "h1", "category": "direction", "horizon": "T+1", "claim": f"{code} fwd_return@1 > 0", "parsed": {"entity": code, "metric": "fwd_return", "horizon": 1, "op": ">", "value": 0.0}},
            {"id": "h2", "category": "direction", "horizon": "T+1", "claim": f"{code} fwd_return@1 < -10", "parsed": {"entity": code, "metric": "fwd_return", "horizon": 1, "op": "<", "value": -10.0}},
            {"id": "h3", "category": "direction", "horizon": "T+1", "claim": "880001.TI fwd_return@1 > 0", "parsed": {"entity": "880001.TI", "metric": "fwd_return", "horizon": 1, "op": ">", "value": 0.0}},
            {"id": "h4", "category": "market", "horizon": "T+1", "claim": "T+1 涨家数 > 0", "falsify_when": "T+1 涨家数 < 0"},
        ]
    }
    lab = duckdb.connect(str(synthetic["labels"]), read_only=True)
    src = duckdb.connect(str(synthetic["src"]), read_only=True)
    try:
        verdicts = engine.judge({"as_of": as_of}, answer, labels_con=lab, db_con=src, entity_types={code: "sector", "880001.TI": "sector"}, calendar=cal)
        actual_next = lab.execute("SELECT fwd_return FROM history_outcomes WHERE entity_id=? AND trade_date=? AND horizon=1", [code, as_of]).fetchone()[0]
    finally:
        lab.close()
        src.close()
    by_id = {v["id"]: v for v in verdicts}
    assert actual_next < -10
    assert by_id["h1"]["verdict"] == "miss"
    assert by_id["h2"]["verdict"] == "hit"
    assert by_id["h3"]["verdict"] in {"hit", "miss"}
    assert by_id["h4"]["verdict"] == "hit" and cal[cal.index(as_of) + 1] in by_id["h4"]["actual"]


def test_judge_marks_missing_outcome_unverifiable(synthetic):
    cal = synthetic["calendar"]
    answer = {"hypotheses": [{"id": "h1", "category": "direction", "horizon": "T+5", "claim": "x", "parsed": {"entity": "880000.TI", "metric": "fwd_return", "horizon": 5, "op": ">", "value": 0.0}}]}
    lab = duckdb.connect(str(synthetic["labels"]), read_only=True)
    src = duckdb.connect(str(synthetic["src"]), read_only=True)
    try:
        pending = engine.judge({"as_of": cal[-2]}, answer, labels_con=lab, db_con=src, entity_types={"880000.TI": "sector"}, calendar=cal)
        no_row = engine.judge({"as_of": cal[40]}, {"hypotheses": [{**answer["hypotheses"][0], "parsed": {**answer["hypotheses"][0]["parsed"], "horizon": 2}}]}, labels_con=lab, db_con=src, entity_types={"880000.TI": "sector"}, calendar=cal)
    finally:
        lab.close()
        src.close()
    assert pending[0]["verdict"] == "unverifiable" and "pending" in pending[0]["actual"]
    assert no_row[0]["verdict"] == "unverifiable" and "无" in no_row[0]["actual"]


def test_market_judge_matches_dual_blind_semantics():
    vals = {"advancers": 3000.0, "limit_up": 50.0, "limit_down": 10.0, "total_amount": 20000.0, "volume_ratio": 1.0, "high_history": 5.0}
    assert engine.judge_market_claim("T+1 涨家数 > 2500", "T+1 涨家数 <= 1500", vals) == "hit"
    assert engine.judge_market_claim("T+1 涨家数 > 3500", "T+1 涨家数 <= 3200", vals) == "miss"
    assert engine.judge_market_claim("T+1 涨家数 > 3500", "成交额 < 10000 亿", vals) == "partial"
    assert engine.judge_market_claim("明天会涨", "跌就错", vals) == "unverifiable"


# --------------------------------------------------------------------------- #
# memory_bucket / 分格 / 臂间差
# --------------------------------------------------------------------------- #
def test_memory_bucket_three_branches():
    cutoffs = [{"model_pattern": "glm-5.2*", "training_cutoff": None}, {"model_pattern": "grok-4.6*", "training_cutoff": "2026-02-01"}]
    assert engine.memory_bucket("glm-5.2", "2026-07-22", cutoffs)[0] == "unknown"
    assert engine.memory_bucket("grok-4.6", "2026-07-22", cutoffs)[0] == "post_cutoff"
    assert engine.memory_bucket("grok-4.6", "2026-02-01", cutoffs)[0] == "pre_cutoff"
    assert engine.memory_bucket("grok-4.6", "2025-05-13", cutoffs)[0] == "pre_cutoff"
    assert engine.memory_bucket("other-model", "2026-07-22", cutoffs)[0] == "unknown"
    assert engine.memory_bucket(None, "2026-07-22", cutoffs)[0] == "unknown"
    shipped = engine.load_model_cutoffs()
    assert {e["model_pattern"] for e in shipped} >= {"glm-5.2*", "grok-4.6*"}
    for entry in shipped:
        assert set(entry) >= {"model_pattern", "training_cutoff", "source_url", "checked_at", "note"}
        assert entry["training_cutoff"] is None or entry["source_url"]


def _record(i, *, arm, verdict, bucket="unknown", grade="strict", category="direction", horizon="T+5", as_of="2026-07-22"):
    return {"id": f"h{i}", "as_of": as_of, "pit_grade": grade, "memory_bucket": bucket, "arm": arm, "category": category, "horizon": horizon, "verdict": verdict, "claim": "c", "model": "glm-5.2"}


def test_cells_below_min_n_show_only_n_and_buckets_never_merge():
    records = []
    for i in range(12):
        records.append(_record(i, arm="named", verdict="hit" if i < 9 else "miss", bucket="post_cutoff"))
    for i in range(12, 17):
        records.append(_record(i, arm="named", verdict="hit", bucket="pre_cutoff"))
    for i in range(17, 20):
        records.append(_record(i, arm="anonymized", verdict="unverifiable", bucket="unknown"))
    agg = engine.aggregate_lane_b(records)
    cells = {(c["memory_bucket"], c["arm"]): c for c in agg["cells"]}
    big = cells[("post_cutoff", "named")]
    assert big["n"] == 12 and big["hit_rate"] == 0.75 and 0.0 <= big["wilson_95"][0] < 0.75 < big["wilson_95"][1] <= 1.0
    assert big["memory_contaminated"] is False
    small = cells[("pre_cutoff", "named")]
    assert small["n"] == 5 and "hit_rate" not in small and "wilson_95" not in small and small["memory_contaminated"] is True
    only_unverifiable = cells[("unknown", "anonymized")]
    assert only_unverifiable["n"] == 0 and only_unverifiable["unverifiable"] == 3
    assert agg["min_n"] == DEFAULT_CALIBRATION_MIN_N
    # 桶不相加：没有任何一格同时含两个 memory_bucket
    assert all(len({c["memory_bucket"]}) == 1 for c in agg["cells"])
    assert {c["memory_bucket"] for c in agg["cells"]} == {"post_cutoff", "pre_cutoff", "unknown"}


def test_arm_gap_reports_memory_signal_only_with_enough_samples():
    records = [_record(i, arm="named", verdict="hit") for i in range(12)] + [_record(100 + i, arm="anonymized", verdict="hit" if i % 2 else "miss") for i in range(12)]
    gaps = engine.arm_gap(records)
    assert len(gaps) == 1
    assert gaps[0]["gap_named_minus_anonymized"] == 0.5 and "上界" in gaps[0]["memory_signal"]
    thin = engine.arm_gap(records[:12] + records[12:15])
    assert thin[0]["gap_named_minus_anonymized"] is None and "N<" in thin[0]["memory_signal"]


def test_lane_a_aggregate_is_micro_averaged():
    recs = [
        {"pit_grade": "strict", "arm": "named", "rule_id": "r", **engine.compare_triggers(["a", "b"], ["a"])},
        {"pit_grade": "strict", "arm": "named", "rule_id": "r", **engine.compare_triggers(["c"], ["c", "d"])},
    ]
    cell = engine.aggregate_lane_a(recs)[0]
    assert (cell["tp"], cell["fp"], cell["fn"]) == (2, 1, 1)
    assert cell["precision_micro"] == pytest.approx(2 / 3, abs=1e-4) and cell["recall_micro"] == pytest.approx(2 / 3, abs=1e-4)
    assert cell["exact_match_rate"] == 0.0


def test_reconciliation_insufficient_dates_is_written_not_blank(tmp_path):
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    snapshots = tmp_path / "snap"
    snapshots.mkdir()
    for d in ("2026-07-13", "2026-07-14"):
        (ledger / f"{d}.answer.claude.json").write_text("{}", encoding="utf-8")
        (snapshots / f"{d}.manifest.json").write_text("{}", encoding="utf-8")
    (ledger / "2026-07-15.answer.claude.json").write_text("{}", encoding="utf-8")
    nodes = [{"as_of": "2026-07-13", "pit_grade": "strict"}, {"as_of": "2026-07-14", "pit_grade": "strict"}]
    section = engine.build_reconciliation([], nodes, ledger_dir=ledger, snapshot_root=snapshots, subset_dir=tmp_path / "subset")
    assert section["status"] == "insufficient" and "不足对账最小样本" in section["note"]
    assert section["overlap_dates"] == ["2026-07-13", "2026-07-14"] and section["included_dates"] == ["2026-07-13", "2026-07-14"]
    assert sorted(p.name for p in ledger.iterdir()) == ["2026-07-13.answer.claude.json", "2026-07-14.answer.claude.json", "2026-07-15.answer.claude.json"]


def test_report_markdown_renders_all_sections(synthetic):
    st_replay = _load_script(REPLAY_SELFTEST, "replay_selftest_for_tests")
    assert st_replay.N_DIRECTION_CLAIMS + 1 <= engine.MAX_HYPOTHESES
    report = engine.build_report(
        run_id="t",
        run_dir=synthetic["root"],
        nodes=[{"as_of": "2026-07-22", "market_stage": "反弹阶段", "pit_grade": "strict", "forced": True, "grade_meta": {"manifest_sha": "abc"}}],
        lane_a_records=[],
        lane_b_records=[_record(1, arm="named", verdict="hit")],
        calls=[{"model": "glm-5.2", "ok": True, "valid": True, "estimated_input_tokens": 10}],
        conditions={"label_version": "v2", "source_max_trade_date": "2026-09-02", "outcomes_horizons": [3, 5]},
        environment={"worktree": "w", "branch": "b", "revision": "r", "dirty": False, "interpreter": "py"},
        cutoffs=engine.load_model_cutoffs(),
        reconciliation=None,
        config={"arms": ["named"]},
    )
    md = engine.render_report_markdown(report)
    for heading in ("## 成立条件", "## 节点", "## 车道 A", "## 车道 B", "## 臂间差", "## memory_bucket 分布", "## 对账"):
        assert heading in md
    assert "training_cutoff=None" in md and "dirty=false" in md


def test_selftest_passes_end_to_end():
    st_replay = _load_script(REPLAY_SELFTEST, "replay_selftest_main_for_tests")
    assert st_replay.main() == 0


# --------------------------------------------------------------------------- #
# 规则 schema 两加法（工单 §2.10）：provenance.kind=discovered / windows 双窗
# --------------------------------------------------------------------------- #
WINDOWS_RULE = {
    "rule_id": "windows_rule",
    "version": 1,
    "title": "双窗测试规则",
    "scope": {"entity_type": "sector", "universe": "published_snapshot"},
    "condition": {"all": [{"label": "dual_red_strict", "op": "==", "value": True, "lag": 0}]},
    "outcome": {
        "target": "pct_chg",
        "horizons": [3, 5, 7, 10],
        "metrics": ["fwd_return", "max_return", "days_to_peak", "drawdown_after_peak"],
        "success": {"metric": "fwd_return", "horizon": 5, "op": ">", "value": 0},
    },
    "baseline": {"kind": "same_universe_all_days"},
    "min_n": 20,
    "sharing": "shared",
    "owner": "system",
}


def test_discovered_is_legal_provenance_but_nothing_writes_it():
    from intelligence.services.methodology_backtest import propose
    from intelligence.services.methodology_backtest.rules import PROVENANCE_KINDS, validate_rule

    assert "discovered" in PROVENANCE_KINDS
    doc = {**json.loads(json.dumps(WINDOWS_RULE)), "provenance": {"kind": "discovered", "text": "P2 提议者占位"}}
    rule, errors = validate_rule(doc)
    assert errors == [] and rule is not None and rule.raw["provenance"]["kind"] == "discovered"
    bad = {**json.loads(json.dumps(WINDOWS_RULE)), "provenance": {"kind": "invented"}}
    _, errors = validate_rule(bad)
    assert any(e.path == "provenance.kind" for e in errors)
    # propose 仍只产 correction：源码里没有任何 "discovered" 写入点
    source = Path(propose.__file__).read_text(encoding="utf-8")
    assert '"discovered"' not in source and "'discovered'" not in source
    assert "correction" in source


def test_windows_validation_requires_validation_after_discovery():
    from intelligence.services.methodology_backtest.rules import validate_rule

    ok = {**json.loads(json.dumps(WINDOWS_RULE)), "windows": {"discovery": ["2026-01-05", "2026-03-31"], "validation": ["2026-04-01", "2026-06-30"]}}
    rule, errors = validate_rule(ok)
    assert errors == [] and rule.windows == {"discovery": ("2026-01-05", "2026-03-31"), "validation": ("2026-04-01", "2026-06-30")}

    overlap = {**json.loads(json.dumps(WINDOWS_RULE)), "windows": {"discovery": ["2026-01-05", "2026-03-31"], "validation": ["2026-03-31", "2026-06-30"]}}
    rule, errors = validate_rule(overlap)
    assert rule is None and [e.path for e in errors] == ["windows.validation[0]"]
    assert "必须晚于 discovery.end" in errors[0].message

    for mutate, path in (
        (lambda w: w.__setitem__("validation", ["2026-04-01"]), "windows.validation"),
        (lambda w: w.__setitem__("discovery", ["2026-1-5", "2026-03-31"]), "windows.discovery[0]"),
        (lambda w: w.__setitem__("discovery", ["2026-03-31", "2026-01-05"]), "windows.discovery"),
        (lambda w: w.__setitem__("extra", []), "windows.extra"),
        (lambda w: w.pop("validation"), "windows.validation"),
    ):
        doc = json.loads(json.dumps(ok))
        mutate(doc["windows"])
        rule, errors = validate_rule(doc)
        assert rule is None and any(e.path == path for e in errors), (path, [str(e) for e in errors])
    rule, errors = validate_rule({**json.loads(json.dumps(WINDOWS_RULE)), "windows": "2026"})
    assert rule is None and [e.path for e in errors] == ["windows"]

    # 没有 windows：既有解析路径不变
    plain, errors = validate_rule(json.loads(json.dumps(WINDOWS_RULE)))
    assert errors == [] and plain.windows is None


def test_windows_receipt_has_both_verdicts_and_plain_receipt_is_unchanged(synthetic):
    from intelligence.services.methodology_backtest.receipts import build_receipt, render_receipt_markdown
    from intelligence.services.methodology_backtest.rules import parse_rule
    from intelligence.services.methodology_backtest.runner import run_rule

    cal = synthetic["calendar"]
    disc = (cal[0], cal[55])
    val = (cal[56], cal[-12])
    windows_rule = parse_rule({**json.loads(json.dumps(WINDOWS_RULE)), "windows": {"discovery": list(disc), "validation": list(val)}})
    plain_rule = parse_rule(json.loads(json.dumps(WINDOWS_RULE)))
    con = duckdb.connect(str(synthetic["labels"]), read_only=True)
    try:
        both = run_rule(con, windows_rule)
        plain_val = run_rule(con, plain_rule, start=val[0], end=val[1])
        plain_full = run_rule(con, plain_rule)
        clamped = run_rule(con, windows_rule, start=cal[10], end=cal[-14])
    finally:
        con.close()
    assert both.discovery is not None and plain_full.discovery is None
    assert both.window == val and both.discovery.window == disc
    # 双窗的 validation 读数 == 同一窗口单窗跑法（同一编译器 / 执行器）
    assert both.readout.to_dict() == plain_val.readout.to_dict()
    assert (both.n_matched, both.n_pending, both.n_missing) == (plain_val.n_matched, plain_val.n_pending, plain_val.n_missing)
    assert both.discovery.n_matched + both.n_matched <= plain_full.n_matched
    # 调用方 start / end 只夹紧
    assert clamped.discovery.window == (cal[10], cal[55]) and clamped.window == (cal[56], cal[-14])

    env = {"revision": "test"}
    receipt = build_receipt(both, rule_path=None, rule_sha256=None, environment=env)
    assert receipt["verdict"] == receipt["verdict_validation"] == both.readout.verdict
    assert receipt["verdict_discovery"] == both.discovery.readout.verdict
    assert set(receipt["windows"]) == {"discovery", "validation"}
    assert receipt["windows"]["discovery"]["window"] == {"start": disc[0], "end": disc[1]}
    assert receipt["rule"]["windows"] == {"discovery": list(disc), "validation": list(val)}
    md = render_receipt_markdown(receipt)
    assert "发现窗 / 验证窗" in md and "discovery" in md and "validation" in md

    plain_receipt = build_receipt(plain_full, rule_path=None, rule_sha256=None, environment=env)
    for key in ("windows", "verdict_discovery", "verdict_validation", "windows_note"):
        assert key not in plain_receipt
    assert "windows" not in plain_receipt["rule"]
    assert set(plain_receipt) == set(receipt) - {"windows", "verdict_discovery", "verdict_validation", "windows_note"}
    assert "发现窗" not in render_receipt_markdown(plain_receipt)
