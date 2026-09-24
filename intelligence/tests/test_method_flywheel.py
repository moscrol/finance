"""方法飞轮接线（能力升级 07）：立场派生、选择梯子、观察登记、到期回检分类、记忆召回、日报段。

所有夹具都是临时目录里的小收据 / 小 DuckDB，不读真实用户台账、不调模型。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pytest

from intelligence.api.daily_reports import project_daily_agent
from intelligence.services import checkpoint_resolvers, checkpoints, user_memory
from intelligence.services.method_validation import (
    build_protocol,
    load_protocol,
    read_record,
    register,
    write_record,
)
from intelligence.services.method_validation import flywheel
from intelligence.services.methodology_backtest.labels import build_labels
from intelligence.services.methodology_backtest.outcomes import build_outcomes
from intelligence.tests import test_episode_tools as episode_tests
from market_feature_store.db import init_db

REPO = Path(__file__).resolve().parents[2]
RULE = REPO / "methodology/rules/dual_red_streak3_continuation.v1.json"
NOW = datetime(2026, 9, 8, 8, tzinfo=timezone.utc)
ARMS = ("universe", "dual_red", "streak3")

_spec = importlib.util.spec_from_file_location("method_validation_cli_07", REPO / "scripts/method_validation.py")
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)


# --------------------------------------------------------------------------- #
# 紧凑收据夹具（不依赖 DuckDB）
# --------------------------------------------------------------------------- #
def _protocol():
    return build_protocol(
        RULE,
        history_start="2026-08-31",
        history_end="2026-09-07",
        forward_start="2026-09-09",
        now=NOW,
    )


def _study(users_root: Path, user: str = "u1") -> Path:
    return register(users_root / user / "method_validation", _protocol())


def _day(trade_date, stage, counts, *, means=None, reasons=(), members=None):
    arms = {name: [f"{name[:1].upper()}{i}" for i in range(n)] for name, n in zip(ARMS, counts)}
    status = "paired" if means and not reasons else "not_evaluated"
    return {
        "trade_date": trade_date,
        "stage": stage,
        "status": status,
        "reasons": list(reasons),
        "arms": arms,
        "means": means or {name: None for name in ARMS},
        "drawdown_after_peak": {name: None for name in ARMS},
        "members": members or [],
    }


def _labels_meta():
    return {
        "label_version": "v-test",
        "source_db": "/tmp/source.duckdb",
        "source_max_trade_date": "2026-09-07",
        "computed_at": "2026-09-08T03:52:36+00:00",
    }


def _history_payload(protocol, daily, *, paired, d1, d2):
    return {
        "protocol_id": protocol["protocol_id"],
        "features": {
            "protocol_id": protocol["protocol_id"],
            "start": "2026-08-31",
            "end": "2026-09-07",
            "calendar": [],
            "rows": [],
            "metadata": {"labels": _labels_meta(), "point_in_time": "reconstructed_labels_not_strict_pit"},
        },
        "evaluator_code_sha256": "test",
        "outcomes": {"metadata": {"outcomes": {"source_max_trade_date": "2026-09-07"}}},
        "comparison": {
            "daily": daily,
            "summary": {
                "paired_dates": paired,
                "means": {"universe": -0.7, "dual_red": -2.0, "streak3": -2.6},
                "streak3_minus_dual_red_pp": d1,
                "streak3_minus_universe_pp": d2,
            },
            "coverage": {"calendar_dates": len(daily), "exclusions": {"unknown_label": 1}},
            "limitations": ["descriptive research only"],
        },
    }


def _capture_payload(protocol, trade_date, *, stage="主升", streak3=("A.TI",), dual_red=("A.TI", "B.TI"),
                     universe=("A.TI", "B.TI", "C.TI"), captured_at="2026-09-10T08:10:00+00:00"):
    rows = []
    for entity in universe:
        arms = ["universe"] + (["dual_red"] if entity in dual_red else []) + (["streak3"] if entity in streak3 else [])
        rows.append({
            "trade_date": trade_date, "entity_id": entity, "stage": stage, "dual_red_strict": 1 if entity in dual_red else 0,
            "dual_red_streak": 3 if entity in streak3 else 0, "arms": arms, "exclusion_reasons": [],
            "computed_at": [captured_at], "stage_computed_at": captured_at,
        })
    return {
        "protocol_id": protocol["protocol_id"],
        "features": {
            "protocol_id": protocol["protocol_id"], "start": trade_date, "end": trade_date, "calendar": [trade_date],
            "rows": rows, "metadata": {"labels": {**_labels_meta(), "source_max_trade_date": trade_date}},
        },
        "evaluator_code_sha256": "test",
        "captured_at": captured_at,
    }


def _recheck_payload(protocol, capture_record, day, *, classification, stage_path):
    return {
        "protocol_id": protocol["protocol_id"],
        "features": capture_record["payload"]["features"],
        "evaluator_code_sha256": "test",
        "observation_sha256": capture_record["content_sha256"],
        "outcomes": {"metadata": {"outcomes": {"source_max_trade_date": "2026-09-17"}}},
        "comparison": {"daily": [day], "summary": {"paired_dates": 1 if day["status"] == "paired" else 0}, "coverage": {}},
        "flywheel": {"version": flywheel.FLYWHEEL_VERSION, "classification": classification, "flags": [], "stage_path": stage_path},
    }


def _negative_history(protocol):
    unknown_member = {"entity_id": "881128.TI", "arms": ["universe"], "exclusion_reasons": ["unknown_dual_red_strict"], "outcome_status": "ok"}
    daily = [
        _day("2026-08-31", "主升", (3, 2, 1), reasons=("unknown_label",), members=[unknown_member]),
        _day("2026-09-01", "主升", (3, 2, 1), means={"universe": -0.7, "dual_red": -2.0, "streak3": -2.6}),
        _day("2026-09-02", "下跌", (3, 2, 1), reasons=("stage_not_applicable",)),
        _day("2026-09-03", "主升", (3, 2, 0), reasons=("no_event",)),
        _day("2026-09-04", "反弹", (3, 2, 1), reasons=("pending",)),
        _day("2026-09-07", None, (0, 0, 0), reasons=("no_sector_labels",)),
    ]
    return _history_payload(protocol, daily, paired=1, d1=-0.6, d2=-1.9)


# --------------------------------------------------------------------------- #
# 分类 / 立场 / 选择
# --------------------------------------------------------------------------- #
def test_classify_day_never_lumps_reasons_into_failure():
    stages = ["主升", "反弹"]
    assert flywheel.classify_day(_day("d", "主升", (3, 2, 1), means={"universe": 1.0, "dual_red": 2.0, "streak3": 3.0}), stages) == "supported"
    assert flywheel.classify_day(_day("d", "主升", (3, 2, 1), means={"universe": 1.0, "dual_red": 4.0, "streak3": 3.0}), stages) == "method_error"
    assert flywheel.classify_day(_day("d", "主升", (3, 2, 1), reasons=("unknown_label",)), stages) == "data_insufficient"
    assert flywheel.classify_day(_day("d", "主升", (3, 2, 1), reasons=("missing",)), stages) == "data_insufficient"
    assert flywheel.classify_day(_day("d", "主升", (3, 2, 0), reasons=("no_event",)), stages) == "no_signal"
    assert flywheel.classify_day(_day("d", "下跌", (3, 2, 1), reasons=("stage_not_applicable", "pending")), stages) == "stage_not_applicable"
    assert flywheel.classify_day(_day("d", "主升", (3, 2, 1), reasons=("pending",)), stages) == "pending"
    assert flywheel.classify_day(_day("d", None, (0, 0, 0), reasons=("no_sector_labels",)), stages) == "data_insufficient"
    paired = _day("d", "主升", (3, 2, 1), means={"universe": 1.0, "dual_red": 2.0, "streak3": 3.0})
    protocol = _protocol()
    assert flywheel.classify_forward(paired, {"d1": "主升", "d2": "主升", "d3": "反弹", "d4": "主升", "d5": "主升"}, protocol) == ("supported", [])
    assert flywheel.classify_forward(paired, {"d1": "主升", "d2": "下跌", "d3": "下跌", "d4": "下跌", "d5": "下跌"}, protocol) == ("environment_change", [])
    assert flywheel.classify_forward(paired, {}, protocol) == ("supported", ["environment_unknown"])


def test_standing_is_derived_from_receipts_and_separates_rehearsal_from_forward(tmp_path):
    users_root = tmp_path / "users"
    study = _study(users_root)
    protocol = load_protocol(study)
    write_record(study, "history", _negative_history(protocol))
    with_signal = write_record(study, "capture", _capture_payload(protocol, "2026-09-10"))
    no_signal = write_record(study, "capture", _capture_payload(protocol, "2026-09-11", streak3=(), captured_at="2026-09-11T08:10:00+00:00"))
    off_stage = write_record(study, "capture", _capture_payload(protocol, "2026-09-14", stage="下跌", captured_at="2026-09-14T08:10:00+00:00"))
    standing = flywheel.derive_standing(study, now=NOW)

    history = standing["history_rehearsal"]
    assert history["label"].startswith("历史演练")
    assert history["applicable_days"] == 4 and history["signal_days"] == 3
    assert history["signal_day_categories"] == {"data_insufficient": 1, "method_error": 1, "pending": 1}
    assert history["signal_day_table"][0]["unknown_label_members"] == 1
    forward = standing["forward"]
    assert [item["trade_date"] for item in forward["pending"]] == ["2026-09-10"]
    assert forward["pending"][0]["due"] == "2026-09-17"
    assert {item["trade_date"]: item["classification"] for item in forward["settled"]} == {
        "2026-09-11": "no_signal",
        "2026-09-14": "stage_not_applicable",
    }
    assert forward["first_real_cycle_completed"] is False
    assert standing["selection"]["decision"] == "downgrade"
    assert any("不支持「连续更强」" in reason for reason in standing["selection"]["reasons"])
    assert standing["boundary"]["promotion_eligible"] is False

    # 到期回检落一条 supported：待验对象消失、真实前向计数出现、第一圈完成。
    capture_record = read_record(with_signal)
    day = _day("2026-09-10", "主升", (3, 2, 1), means={"universe": 0.4, "dual_red": 3.0, "streak3": 5.1})
    write_record(study, "recheck", _recheck_payload(protocol, capture_record, day, classification="supported",
                                                     stage_path={"2026-09-11": "主升", "2026-09-12": "主升", "2026-09-15": "主升", "2026-09-16": "主升", "2026-09-17": "主升"}))
    settled = flywheel.derive_standing(study, now=NOW)
    assert settled["forward"]["pending"] == []
    assert settled["forward"]["counts"] == {"no_signal": 1, "stage_not_applicable": 1, "supported": 1}
    assert settled["forward"]["first_real_cycle_completed"] is True
    assert settled["selection"]["evidence_for"] == 1 and settled["selection"]["evidence_against"] == 1
    assert settled["selection"]["decision"] == "candidate"
    assert no_signal.is_file() and off_stage.is_file()


def test_selection_ladder_changes_when_refuted_or_environment_changes(tmp_path):
    study = _study(tmp_path / "users")
    protocol = load_protocol(study)
    write_record(study, "history", _negative_history(protocol))
    standing = flywheel.derive_standing(study, now=NOW)
    assert standing["selection"]["decision"] == "downgrade"
    # 反向验证：前向一次方法错误 → 反证 2、支持 0 → 排除。
    standing["forward"]["counts"] = {"method_error": 1}
    assert flywheel.decide(standing)["decision"] == "exclude"
    # 环境门：当前阶段不在适用集合 → 排除并说明原因，不看正反计数。
    standing["forward"]["counts"] = {"supported": 3}
    verdict = flywheel.decide(standing, current_stage="下跌")
    assert verdict["decision"] == "exclude" and "环境不适用" in verdict["reasons"][0]
    # 支持多于反证且样本≥3 → 采用（仍写不出胜率）。
    adopt = flywheel.decide(standing)
    assert adopt["decision"] == "adopt" and any("不出胜率" in r for r in adopt["reasons"])
    # 环境变化 / 数据不足不进正反计数。
    standing["forward"]["counts"] = {"environment_change": 2, "data_insufficient": 1}
    neutral = flywheel.decide(standing)
    assert neutral["evidence_for"] == 0 and neutral["evidence_against"] == 1 and neutral["decision"] == "downgrade"


def test_standing_digest_is_fingerprinted_and_goes_stale_on_new_receipts(tmp_path):
    study = _study(tmp_path / "users")
    protocol = load_protocol(study)
    write_record(study, "history", _negative_history(protocol))
    path = flywheel.refresh_standing(study, now=NOW)
    assert path.parent.name == "standing" and path.stem == flywheel.fingerprint(study)
    fresh, ok = flywheel.load_standing(study)
    assert ok and fresh["stale"] is False
    write_record(study, "capture", _capture_payload(protocol, "2026-09-10"))
    stale, ok = flywheel.load_standing(study)
    assert not ok and stale["stale"] is True and "未刷新" in stale["stale_reason"]
    again = flywheel.refresh_standing(study, now=NOW)
    assert again != path and flywheel.load_standing(study)[1] is True


# --------------------------------------------------------------------------- #
# 自然语言 → 方法；用户隔离；候选草稿
# --------------------------------------------------------------------------- #
def test_query_match_and_recall_are_isolated_per_user(tmp_path):
    users_root = tmp_path / "users"
    study = _study(users_root, "u1")
    write_record(study, "history", _negative_history(load_protocol(study)))
    flywheel.refresh_standing(study, now=NOW)
    assert flywheel.match_query("连续三天双红的板块，后五天一般怎么走？")["terms"] == ["双红"]
    assert flywheel.match_query("光刻胶现在怎么看") is None
    hits = flywheel.recall_for_query("连续双红的板块第五天还能追吗", users_root=users_root / "u1")
    assert len(hits) == 1
    detail = hits[0]["detail"]
    assert "历史演练" in detail and "真实前向" in detail and "不构成买卖建议" in detail
    assert hits[0]["decision"] == "downgrade"
    assert flywheel.recall_for_query("连续双红的板块第五天还能追吗", users_root=users_root / "u2") == []
    assert flywheel.recall_for_query("光刻胶现在怎么看", users_root=users_root / "u1") == []
    # 当前阶段传进来时环境门先生效。
    gated = flywheel.recall_for_query("双红板块怎么看", users_root=users_root / "u1", current_stage="下跌")
    assert gated[0]["decision"] == "exclude"
    assert flywheel.stage_from_text("大盘处于顶部横盘阶段，量能收缩") == "顶部横盘"


def test_candidate_draft_is_content_addressed_and_not_compiled(tmp_path):
    root = tmp_path / "method_validation"
    first = flywheel.save_candidate(root, "涨停后缩量回踩五日线的题材龙头，三天内再创新高", now=NOW)
    second = flywheel.save_candidate(root, "涨停后缩量回踩五日线的题材龙头，三天内再创新高", now=NOW.replace(hour=9))
    assert first == second and first.parent.name == "candidates"
    saved = flywheel.list_candidates(root)
    assert saved[0]["status"] == "candidate_unconfirmed" and saved[0]["matched_method"] is None
    with pytest.raises(ValueError):
        flywheel.save_candidate(root, "   ", now=NOW)


# --------------------------------------------------------------------------- #
# 观察对象登记 ↔ checkpoint / resolver
# --------------------------------------------------------------------------- #
def test_observation_checkpoint_only_when_signal_and_verdict_mapping(tmp_path):
    study = _study(tmp_path / "users")
    protocol = load_protocol(study)
    ledger = tmp_path / "ledger" / "checkpoints.jsonl"
    with_signal = _capture_payload(protocol, "2026-09-10")["features"]
    record = flywheel.register_observation_checkpoint(
        ledger, protocol=protocol, features=with_signal, observation_path=study / "capture" / "2026-09-10" / ("a" * 64 + ".json"),
        study_dir=study, labels_db=tmp_path / "labels.duckdb", captured_at="2026-09-10T08:10:00+00:00",
    )
    assert record["object_type"] == "method_observation" and record["metric"]["type"] == "method_validation"
    assert record["due"] == "2026-09-17" and record["category"] == flywheel.CATEGORY
    assert checkpoints.object_type_of(record) == "method_observation"
    assert flywheel.register_observation_checkpoint(
        ledger, protocol=protocol, features=_capture_payload(protocol, "2026-09-11", streak3=())["features"],
        observation_path=study / "x.json", study_dir=study, labels_db=tmp_path / "l.duckdb", captured_at="2026-09-11T08:10:00+00:00",
    ) is None
    assert flywheel.register_observation_checkpoint(
        ledger, protocol=protocol, features=_capture_payload(protocol, "2026-09-12", stage="横盘")["features"],
        observation_path=study / "y.json", study_dir=study, labels_db=tmp_path / "l.duckdb", captured_at="2026-09-12T08:10:00+00:00",
    ) is None
    rows, _ = checkpoints.load_checkpoints(ledger)
    assert len(rows) == 1
    assert flywheel.verdict_for("supported")[0] == "hit" and flywheel.verdict_for("method_error")[0] == "miss"
    for classification in ("data_insufficient", "environment_change", "pending", "no_signal"):
        assert flywheel.verdict_for(classification)[0] == "unverifiable"
    verdicts = ledger.with_name("verdicts.jsonl")
    written = flywheel.record_observation_verdict(
        verdicts, record, {"classification": "environment_change", "flags": [], "diffs": {"streak3_minus_dual_red_pp": 1.0}, "record_path": "r"},
    )
    assert written["verdict"] == "unverifiable" and written["degradation"]["impact"].startswith("不计入")
    cal = checkpoints.calibrate(rows, checkpoints.load_verdicts(verdicts)[0])
    assert cal.scored == 0  # 环境变化不进任何分母
    with pytest.raises(ValueError):
        checkpoints.normalize_metric({"type": "method_validation", "study_dir": "x"})


def test_resolver_routes_method_validation_and_degrades_honestly():
    checkpoint = {"id": "c1", "metric": {"type": "method_validation", "study_dir": "/s", "observation": "/s/capture/d/o.json", "labels_db": "/l.duckdb"}}
    hit = checkpoint_resolvers.resolve_checkpoint(checkpoint, method_resolve_fn=lambda *a: {"classification": "supported", "diffs": {"x": 1}})
    assert (hit.verdict, hit.score, hit.data_source) == ("hit", 1.0, "method_validation")
    miss = checkpoint_resolvers.resolve_checkpoint(checkpoint, method_resolve_fn=lambda *a: {"classification": "method_error"})
    assert miss.verdict == "miss"
    pending = checkpoint_resolvers.resolve_checkpoint(checkpoint, method_resolve_fn=lambda *a: {"classification": "pending", "classification_cn": "未到期", "todo": ["等到期"]})
    assert pending.verdict == "unverifiable" and pending.degradation["todo"] == ["等到期"]

    def boom(*_args):
        raise ValueError("outcomes source watermark regressed")

    degraded = checkpoint_resolvers.resolve_checkpoint(checkpoint, method_resolve_fn=boom)
    assert degraded.verdict == "unverifiable"
    assert "watermark" in degraded.degradation["attempted"][0]["status"]
    assert any("method_validation.py daily" in todo for todo in degraded.degradation["todo"])
    spec_gap = checkpoint_resolvers.resolve_checkpoint({"id": "c2", "metric": {"type": "method_validation", "study_dir": "/s"}})
    assert spec_gap.verdict == "unverifiable" and "observation" in spec_gap.degradation["gap"]


# --------------------------------------------------------------------------- #
# 记忆召回：[M] 块与 memory_lookup 工具
# --------------------------------------------------------------------------- #
def test_memory_recall_and_block_carry_method_reading(tmp_path):
    users_root = episode_tests._memory_fixture(tmp_path)
    study = _study(users_root.parent, users_root.name)
    write_record(study, "history", _negative_history(load_protocol(study)))
    flywheel.refresh_standing(study, now=NOW)
    recall = user_memory.relevant_memory_records("连续双红的板块第五天还能追吗", users_root=users_root)
    assert len(recall.methods) == 1 and recall.total == 1
    block = user_memory.memory_block_for_query("连续双红的板块第五天还能追吗", users_root=users_root)
    assert "方法验证读数" in block and "历史演练" in block and "降低权重" in block
    unrelated = user_memory.relevant_memory_records("光刻胶，现在怎么看", users_root=users_root)
    assert unrelated.methods == [] and unrelated.total == 2


def test_memory_lookup_tool_emits_method_evidence_with_boundaries(tmp_path):
    users_root = episode_tests._memory_fixture(tmp_path)
    study = _study(users_root.parent, users_root.name)
    write_record(study, "history", _negative_history(load_protocol(study)))
    flywheel.refresh_standing(study, now=NOW)
    registry, context = episode_tests._memory_registry(tmp_path, users_root=users_root, task_id="memory-lookup-method-07")
    result = registry.execute("memory_lookup", "连续双红的板块第五天还能追吗", context=context, step_id="memory-lookup-method-07:1")
    assert result.trace.status == "success"
    method = [item for item in result.evidence if item.title == "方法验证读数"]
    assert len(method) == 1
    assert "历史演练" in method[0].detail and "不构成买卖建议" in method[0].detail
    assert method[0].evidence_tier == "user_memory" and "非市场事实" in method[0].source
    assert method[0].independent_key == flywheel.METHOD_ID


# --------------------------------------------------------------------------- #
# 日常入口：日报段 + Workbench 投影
# --------------------------------------------------------------------------- #
def test_daily_brief_and_projection_show_signal_and_pending(tmp_path):
    users_root = tmp_path / "users"
    study = _study(users_root, "u1")
    protocol = load_protocol(study)
    write_record(study, "history", _negative_history(protocol))
    observation = write_record(study, "capture", _capture_payload(protocol, "2026-09-10"))
    ledger = tmp_path / "ledger" / "checkpoints.jsonl"
    checkpoint = flywheel.register_observation_checkpoint(
        ledger, protocol=protocol, features=read_record(observation)["payload"]["features"], observation_path=observation,
        study_dir=study, labels_db=tmp_path / "labels.duckdb", captured_at="2026-09-10T08:10:00+00:00",
    )
    flywheel.refresh_standing(study, now=NOW)
    brief = flywheel.daily_brief(users_root=users_root / "u1", today="2026-09-10", checkpoints_path=ledger, verdicts_path=ledger.with_name("verdicts.jsonl"))
    assert brief["available"] is True
    entry = brief["studies"][0]
    assert entry["today"]["has_signal"] is True and entry["today"]["streak3_members"] == ["A.TI"]
    assert entry["pending"][0]["checkpoint_id"] == checkpoint["id"] and entry["pending"][0]["due"] == "2026-09-17"
    lines = flywheel.render_brief_lines(brief)
    assert any("今日信号：连续组 1 个板块" in line for line in lines)
    assert any("待验：2026-09-10" in line for line in lines)
    assert flywheel.render_brief_lines({"available": False, "reason": "没有实验"}) == ["- 没有实验"]

    payload = {"date": "2026-09-10", "decision": {"old_logic_wakeup": [], "new_logic_candidate": [], "data_gap": [], "noise_or_unconfirmed": []},
               "research_queue": {"summary": {"total": 0}}, "method_flywheel": brief, "notes": []}
    projection = project_daily_agent(payload, source_path="exports/2026-09-10-daily-agent.json")
    titles = [section["title"] for section in projection["sections"]]
    assert titles[-1] == "方法信号与待验对象"
    item = projection["sections"][-1]["items"][0]
    assert item["title"] == flywheel.METHOD_TITLE and "今日信号" in item["summary"]
    assert "历史演练" in item["badges"]
    empty = project_daily_agent({**payload, "method_flywheel": {"available": False}}, source_path="x.json")
    assert "方法信号与待验对象" not in [section["title"] for section in empty["sections"]]


# --------------------------------------------------------------------------- #
# 端到端：小 DuckDB 上走 daily（capture → 登记 → 到期 recheck → verdict → 立场）
# --------------------------------------------------------------------------- #
DATES = [date(2026, 2, 2) + timedelta(days=i) for i in range(12) if (date(2026, 2, 2) + timedelta(days=i)).weekday() < 5]
REGISTERED_AT = datetime(2026, 2, 3, 9, tzinfo=timezone.utc)
CAPTURED_AT = datetime(2026, 2, 4, 9, tzinfo=timezone.utc)
LATER = datetime(2026, 2, 11, 9, tzinfo=timezone.utc)


def _extend_source(source, days, *, stage="主升阶段"):
    with duckdb.connect(str(source)) as con:
        init_db(con)
        for day in days:
            con.execute("INSERT INTO fact_market_daily (trade_date, market_stage, total_amount) VALUES (?, ?, 10000)", [day, stage])
            for code, pct in (("A.TI", 1.0), ("B.TI", 0.2), ("C.TI", -1.0)):
                diff = 20 if code == "A.TI" or (code == "B.TI" and day == DATES[2]) else -5
                con.execute(
                    "INSERT INTO fact_sector_daily_generation "
                    "(trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, pct_chg, amount, diff_ratio) "
                    "VALUES (?, 'legacy', ?, ?, ?, 800, ?)",
                    [day, code, code, pct, diff],
                )


def _daily(args_common, capsys):
    code = cli.main(["daily", *args_common])
    out = capsys.readouterr()
    assert code == 0, out.err
    return json.loads(out.out)


@pytest.mark.parametrize("later_stage,expected", [("主升阶段", "supported"), ("下跌阶段", "environment_change")])
def test_daily_orchestrates_capture_checkpoint_recheck_and_verdict(tmp_path, monkeypatch, capsys, later_stage, expected):
    source, labels = tmp_path / "source.duckdb", tmp_path / "labels.duckdb"
    ledger = tmp_path / "ledger" / "checkpoints.jsonl"
    _extend_source(source, DATES[:3])
    build_labels(source, labels, now=CAPTURED_AT)
    build_outcomes(source, labels, now=CAPTURED_AT)
    monkeypatch.setattr(cli, "current_time", lambda: REGISTERED_AT)
    assert cli.main(["register", "--history-start", str(DATES[0]), "--history-end", str(DATES[1]), "--forward-start", str(DATES[2]),
                     "--root", str(tmp_path / "research")]) == 0
    study = Path(json.loads(capsys.readouterr().out)["study_dir"])
    common = ["--study-dir", str(study), "--labels-db", str(labels), "--db-path", str(source), "--checkpoints-path", str(ledger)]

    monkeypatch.setattr(cli, "current_time", lambda: CAPTURED_AT)
    first = _daily(common, capsys)
    steps = {step["step"]: step for step in first["steps"]}
    assert steps["rebuild"]["status"] == "skipped"
    assert steps["capture"]["status"] == "captured" and steps["capture"]["signal"] is True
    checkpoint_id = steps["capture"]["checkpoint"]
    assert checkpoint_id
    assert steps["recheck"]["results"][0]["classification"] == "pending"
    assert steps["recheck"]["results"][0]["record"] is None  # 未到期不写收据
    assert first["selection"]["decision"] == "candidate"
    rows, _ = checkpoints.load_checkpoints(ledger)
    assert rows[0]["id"] == checkpoint_id and rows[0]["object_type"] == "method_observation"
    # 到期前夜间 resolver 只能降级，不会提前结算。
    early = checkpoint_resolvers.resolve_checkpoint(rows[0])
    assert early.verdict == "unverifiable"

    _extend_source(source, DATES[3:8], stage=later_stage)
    monkeypatch.setattr(cli, "current_time", lambda: LATER)
    second = _daily(common, capsys)
    steps = {step["step"]: step for step in second["steps"]}
    assert steps["rebuild"]["status"] == "done"
    results = {item["trade_date"]: item for item in steps["recheck"]["results"]}
    assert results[str(DATES[2])]["classification"] == expected
    assert results[str(DATES[2])]["record"]
    verdicts, _ = checkpoints.load_verdicts(ledger.with_name("verdicts.jsonl"))
    matured = [v for v in verdicts if v["id"] == checkpoint_id]
    if expected == "supported":
        assert matured[-1]["verdict"] == "hit" and results[str(DATES[2])]["diffs"]["streak3_minus_dual_red_pp"] > 0
        assert second["selection"]["evidence_for"] == 1
    else:
        assert matured[-1]["verdict"] == "unverifiable" and matured[-1]["degradation"]["impact"].startswith("不计入")
        assert second["selection"]["evidence_for"] == 0 and second["selection"]["evidence_against"] == 0
        assert set(results[str(DATES[2])]["stage_path"].values()) == {"下跌"}
    # 后一天有信号时又登记了新的待验对象；今天的 capture 也在立场里。
    standing, fresh = flywheel.load_standing(study)
    assert fresh and standing["forward"]["counts"].get(expected) == 1
    assert [item["trade_date"] for item in standing["forward"]["pending"]] == [str(DATES[7])] if later_stage == "主升阶段" else True
    # 幂等：再跑一次不会重复结算、不会重复登记。
    third = _daily(common, capsys)
    steps = {step["step"]: step for step in third["steps"]}
    assert steps["capture"]["status"] == "already_captured"
    assert str(DATES[2]) not in {item["trade_date"] for item in steps["recheck"]["results"]}
    assert len(checkpoints.load_checkpoints(ledger)[0]) == len(rows) + (1 if later_stage == "主升阶段" else 0)
    # 真实 resolver 复判已结算的观察给出同一结论。
    settled = checkpoint_resolvers.resolve_checkpoint(rows[0])
    assert settled.verdict == ("hit" if expected == "supported" else "unverifiable")
    assert cli.main(["status", "--study-dir", str(study), "--today", str(DATES[7])]) == 0
    text = capsys.readouterr().out
    assert "真实前向" in text and "历史演练" in text
    assert cli.main(["match", "--query", "连续双红的板块后面五天怎么样", "--users-root", str(tmp_path / "nobody")]) == 0
    assert "没有可读的立场摘要" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# 中断恢复两点实测（整包集成 spec §I5）
# --------------------------------------------------------------------------- #
def test_interrupted_capture_completes_unique_checkpoint_on_rerun(tmp_path, monkeypatch, capsys):
    """恢复点①：capture 已落盘、checkpoint 尚未登记时中断，重跑沿原观察补齐唯一登记，
    不重做 capture、不修改捕获时间。"""

    source, labels = tmp_path / "source.duckdb", tmp_path / "labels.duckdb"
    ledger = tmp_path / "ledger" / "checkpoints.jsonl"
    _extend_source(source, DATES[:3])
    build_labels(source, labels, now=CAPTURED_AT)
    build_outcomes(source, labels, now=CAPTURED_AT)
    monkeypatch.setattr(cli, "current_time", lambda: REGISTERED_AT)
    assert cli.main(["register", "--history-start", str(DATES[0]), "--history-end", str(DATES[1]),
                     "--forward-start", str(DATES[2]), "--root", str(tmp_path / "research")]) == 0
    study = json.loads(capsys.readouterr().out)["study_dir"]

    # 模拟中断：capture 落盘成功、进程死在 checkpoint 登记之前（--no-checkpoint 复现其留下的状态）。
    monkeypatch.setattr(cli, "current_time", lambda: CAPTURED_AT)
    assert cli.main(["capture", "--study-dir", study, "--labels-db", str(labels), "--no-checkpoint"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["status"] == "captured" and first["checkpoint"] is None
    observation = Path(first["observation"])
    original_bytes = observation.read_bytes()
    assert not ledger.exists()

    # 重跑：不重做 capture，沿原观察补齐唯一登记。
    assert cli.main(["capture", "--study-dir", study, "--labels-db", str(labels),
                     "--checkpoints-path", str(ledger)]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["status"] == "already_captured"
    assert second["observation"] == str(observation)
    assert second["checkpoint"]
    assert observation.read_bytes() == original_bytes
    rows, _ = checkpoints.load_checkpoints(ledger)
    assert [r["id"] for r in rows] == [second["checkpoint"]]
    assert rows[0]["metric"]["observation"] == str(observation.resolve())
    assert rows[0]["ts"] == read_record(observation)["payload"]["captured_at"]

    # 三跑：登记仍唯一，不重复。
    assert cli.main(["capture", "--study-dir", study, "--labels-db", str(labels),
                     "--checkpoints-path", str(ledger)]) == 0
    third = json.loads(capsys.readouterr().out)
    assert third["checkpoint"] == second["checkpoint"]
    assert len(checkpoints.load_checkpoints(ledger)[0]) == 1


def test_daily_retries_data_insufficient_after_rebuild(tmp_path, monkeypatch, capsys):
    """恢复点②研究侧（集成 spec I5）：可恢复的数据不足不是终态。

    全链自然构造：D+1..D+5 只有行情行、没有板块行 → 回检判 data_insufficient
    （unverifiable 非终态）；旁路库水位未动的日子不重复刷不足收据；板块行回填后，
    下一个交易日的 daily 重建旁路库并沿同一观察重试 → supported/hit；
    先前不足记录与 unverifiable verdict 都保留在案。"""

    source, labels = tmp_path / "source.duckdb", tmp_path / "labels.duckdb"
    ledger = tmp_path / "ledger" / "checkpoints.jsonl"
    _extend_source(source, DATES[:3])
    build_labels(source, labels, now=CAPTURED_AT)
    build_outcomes(source, labels, now=CAPTURED_AT)
    monkeypatch.setattr(cli, "current_time", lambda: REGISTERED_AT)
    assert cli.main(["register", "--history-start", str(DATES[0]), "--history-end", str(DATES[1]),
                     "--forward-start", str(DATES[2]), "--root", str(tmp_path / "research")]) == 0
    study = Path(json.loads(capsys.readouterr().out)["study_dir"])
    common = ["--study-dir", str(study), "--labels-db", str(labels), "--db-path", str(source),
              "--checkpoints-path", str(ledger)]

    monkeypatch.setattr(cli, "current_time", lambda: CAPTURED_AT)
    first = _daily(common, capsys)
    observation = Path({s["step"]: s for s in first["steps"]}["capture"]["observation"])

    # D+1..D+5 只有行情行、没有板块行：回检自然判数据不足（no_sector_labels）。
    with duckdb.connect(str(source)) as con:
        for day in DATES[3:8]:
            con.execute(
                "INSERT INTO fact_market_daily (trade_date, market_stage, total_amount) VALUES (?, '主升阶段', 10000)",
                [day],
            )
    monkeypatch.setattr(cli, "current_time", lambda: LATER)
    second = _daily(common, capsys)
    steps = {s["step"]: s for s in second["steps"]}
    assert steps["rebuild"]["status"] == "done"
    insufficient_run = [item for item in steps["recheck"]["results"] if item.get("observation") == str(observation)]
    assert insufficient_run and insufficient_run[0]["classification"] == "data_insufficient"

    # 水位未动：不足记录按已结算处理，不重复刷噪声。
    quiet = _daily(common, capsys)
    quiet_recheck = {s["step"]: s for s in quiet["steps"]}["recheck"]
    assert str(observation) not in {item.get("observation") for item in quiet_recheck["results"]}

    # 板块行回填 + 下一个交易日到来：重建触发，沿同一观察重试并结算。
    extra_day = DATES[-1] + timedelta(days=1)
    with duckdb.connect(str(source)) as con:
        for day in DATES[3:8]:
            for code, pct in (("A.TI", 1.0), ("B.TI", 0.2), ("C.TI", -1.0)):
                con.execute(
                    "INSERT INTO fact_sector_daily_generation "
                    "(trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, pct_chg, amount, diff_ratio) "
                    "VALUES (?, 'legacy', ?, ?, ?, 800, -5)",
                    [day, code, code, pct],
                )
    _extend_source(source, [extra_day])
    monkeypatch.setattr(
        cli, "current_time",
        lambda: datetime(extra_day.year, extra_day.month, extra_day.day, 9, tzinfo=timezone.utc),
    )
    third = _daily(common, capsys)
    steps = {s["step"]: s for s in third["steps"]}
    assert steps["rebuild"]["status"] == "done"
    retried = [item for item in steps["recheck"]["results"] if item.get("observation") == str(observation)]
    assert retried and retried[0]["classification"] == "supported"
    insufficient_records = [
        path for path in cli.list_records(study, "recheck")
        if (read_record(path)["payload"].get("flywheel") or {}).get("classification") == "data_insufficient"
    ]
    assert insufficient_records, "先前不足记录必须保留在案"
    verdicts, _ = checkpoints.load_verdicts(ledger.with_name("verdicts.jsonl"))
    ours = [v for v in verdicts if v["id"] == {s["step"]: s for s in first["steps"]}["capture"]["checkpoint"]]
    assert [v["verdict"] for v in ours][:1] == ["unverifiable"] and ours[-1]["verdict"] == "hit"


# --------------------------------------------------------------- 夜跑接线（shell 层）

NIGHTLY_SH = REPO / "skills" / "daily-full-review" / "scripts" / "nightly_full_review.sh"


def test_flywheel_resolves_its_script_from_the_code_root_not_the_data_root() -> None:
    """飞轮的脚本路径必须跟 CODE_ROOT（运行快照），不能跟 WORKSPACE（=DATA_ROOT，数据仓）。

    夜跑里 ``WORKSPACE="$DATA_ROOT"`` 指主检出，那棵树常年停在别人的任务分支或 detached
    HEAD 上，不保证有任何一个新脚本；``method_validation.py`` 是代码，只在被部署验证过的
    运行快照里。写错根的后果不是报错而是**每夜静默跳过**，且跳过原因写着「合入后自动生效」
    ——一条读起来完全合理的假话，没有任何东西会红。
    """

    body = NIGHTLY_SH.read_text(encoding="utf-8")

    assert '"$CODE_ROOT/scripts/method_validation.py"' in body
    assert '"$WORKSPACE/scripts/method_validation.py"' not in body


def test_flywheel_skip_reason_names_the_root_it_actually_looked_in() -> None:
    """跳过原因要带上真正查过的那个目录，否则下一个人无从判断是哪一层没接上。"""

    body = NIGHTLY_SH.read_text(encoding="utf-8")
    guard = body.split("run_method_flywheel()", 1)[1]

    assert "CODE_ROOT=$CODE_ROOT" in guard


def test_log_dir_is_ready_before_the_binding_is_resolved() -> None:
    """``LOG_DIR`` 必须在解析 active 指针**之前**赋值——否则 `set -u` 让整条命令在 shell
    层就失败，rc=1 被当成「从未配置」，静默跑回旧协议。

    这不是风格问题：夜跑第 11 行是 ``set -uo pipefail``，而绑定解析把 stderr 重定向到
    ``$LOG_DIR/…``。引用未赋值变量时 shell 在**重定向阶段**就放弃，`method_validation.py
    active` 一次都不会执行（跨会话质检实测 `zsh: LOG_DIR: parameter not set`、rc=1、输出为空），
    于是整条指针链在生产路径上等于不存在，而 case 里 1 与 3 的处置相反这件事也白设计了。
    判据用顺序而不是「有没有这一行」：两处都有 LOG_DIR 时只有先后决定行为。
    """

    body = NIGHTLY_SH.read_text(encoding="utf-8")
    assign = body.index('LOG_DIR="$DATA_ROOT/logs"')
    use = body.index('2>>"$LOG_DIR/method-validation-daily.log"')
    assert assign < use, "LOG_DIR 的赋值必须早于绑定解析里对它的引用"
    # 目录也要建好：只赋值不 mkdir，重定向照样失败
    mkdir_at = body.index('mkdir -p "$LOG_DIR"')
    assert assign < mkdir_at < use, "mkdir -p $LOG_DIR 要在赋值之后、引用之前"


def test_binding_resolution_runs_under_set_u_without_log_dir(tmp_path) -> None:
    """真实启动条件（`set -u` + 未预设 LOG_DIR）下跑一遍绑定解析：``active`` 必须真的执行。

    判据是**日志文件被创建**：修复前 shell 在重定向阶段就失败，日志目录是空的；修复后
    命令执行了，stderr 日志一定在。只在设了 LOG_DIR 的交互 shell 里测会全绿，看不出问题。
    """
    import os
    import subprocess

    body = NIGHTLY_SH.read_text(encoding="utf-8")
    head = body[: body.index("2>>\"$LOG_DIR/method-validation-daily.log\"")]
    # 取到绑定解析那一段为止的脚本前缀，够复现启动顺序即可
    data_root = tmp_path / "data"
    users = tmp_path / "users" / "linxiaoqi5111" / "method_validation"
    users.mkdir(parents=True)
    script = tmp_path / "probe.sh"
    script.write_text(
        "#!/bin/zsh\nset -uo pipefail\n"
        f'DATA_ROOT={data_root!s}\n'
        f'CODE_ROOT={REPO!s}\n'
        f'FORESIGHT_USERS_DIR={tmp_path / "users"!s}\n'
        'FORESIGHT_USER="linxiaoqi5111"\n'
        'OPS_PYTHON="$1"\n'
        + ("LOG_DIR=\"$DATA_ROOT/logs\"\nmkdir -p \"$LOG_DIR\"\n" if 'LOG_DIR="$DATA_ROOT/logs"' in head else "")
        + 'DIR="$("$OPS_PYTHON" "$CODE_ROOT/scripts/method_validation.py" active '
        '--user "$FORESIGHT_USER" --print-dir 2>>"$LOG_DIR/method-validation-daily.log")"\n'
        'echo "rc=$?"\n',
        encoding="utf-8",
    )
    script.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k != "LOG_DIR"}
    subprocess.run([str(script), sys.executable], capture_output=True, text=True, env=env)
    assert (data_root / "logs" / "method-validation-daily.log").exists(), (
        "active 命令没有真正执行——LOG_DIR 在引用时还没就位"
    )


_CASE_SEQ = __import__("itertools").count()


def _run_binding(tmp_path, cli_body: str, *, env_extra=None) -> dict:
    """把夜跑**真正的**绑定解析段抽出来执行, 用一份假 CLI 注入场景。

    以前这两条是对脚本正文做字符串断言, 结果是: 管道换个写法测试就红, 而真正的行为
    (help 自己挂了会不会被当成「没有该命令」) 一条也没测到。这里改成跑真的 shell。
    """
    import os
    import subprocess

    body = NIGHTLY_SH.read_text(encoding="utf-8")
    # 从 METHOD_STUDY_DEFAULT 起, 否则 `set -u` 下引用未定义变量直接退出
    segment = body[body.index('METHOD_STUDY_DEFAULT="$FORESIGHT_USERS_DIR'):body.index('METHOD_LABELS_DB=')]

    # 同一个 tmp_path 允许跑多次: 每次一个独立场景目录, 互不污染
    tmp_path = tmp_path / f"case{next(_CASE_SEQ)}"
    tmp_path.mkdir()
    fake_root = tmp_path / "coderoot" / "scripts"
    fake_root.mkdir(parents=True)
    (fake_root / "method_validation.py").write_text(cli_body, encoding="utf-8")

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    script = tmp_path / "probe.sh"
    script.write_text(
        "#!/bin/zsh\nset -uo pipefail\n"
        f'CODE_ROOT={tmp_path / "coderoot"!s}\n'
        f'LOG_DIR={log_dir!s}\n'
        f'FORESIGHT_USERS_DIR={tmp_path / "users"!s}\n'
        'FORESIGHT_USER="u1"\n'
        'OPS_PYTHON="$1"\n'
        + segment
        + '\nprintf "DIR=%s\\nERR=%s\\n" "${METHOD_STUDY_DIR:-}" "$METHOD_BINDING_ERROR"\n',
        encoding="utf-8",
    )
    script.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k != "METHOD_STUDY_DIR"}
    env.update(env_extra or {})
    out = subprocess.run([str(script), sys.executable], capture_output=True, text=True, env=env)
    parsed = dict(ln.split("=", 1) for ln in out.stdout.splitlines() if "=" in ln)
    parsed["log"] = (log_dir / "method-validation-daily.log").read_text(encoding="utf-8") \
        if (log_dir / "method-validation-daily.log").exists() else ""
    return parsed


_OLD_CLI = """import sys
if "--help" in sys.argv[1:2] or sys.argv[1:2] == ["--help"]:
    print("usage: method_validation.py [-h] {register,capture,recheck,status} ...")
    raise SystemExit(0)
print("method_validation.py: error: argument command: invalid choice: 'active'", file=sys.stderr)
raise SystemExit(2)
"""


def test_old_cli_falls_back_with_the_true_reason(tmp_path) -> None:
    """链切未做时按「从未配置」走内置默认, 且日志写真话。

    旧 CLI 上 ``active`` 是 argparse ``invalid choice`` → **exit 2**。按退出码解释就会
    报成「指针已配置但失效, 请 activate」——那份 CLI 同样没有 activate, 补救动作不可执行。
    （更正一条曾写进注释与测试的错误原理: 旧 CLI 的 ``active --help`` 并不返回 0,
    它同样是 exit 2 invalid choice; 顶层 ``--help`` 探针是对的, 但不能拿那个理由背书。）
    """
    r = _run_binding(tmp_path, _OLD_CLI)
    assert r["DIR"].endswith("475597e2e017a2eedd3886700cd41d394d3694eba3487e205b8ddc91723b5a2f")
    assert r["ERR"] == "", "这不是「已配置但失效」, 不该设错误态"
    assert "没有 active 子命令" in r["log"] and "链切" in r["log"]


def test_help_failure_is_not_reported_as_missing_capability(tmp_path) -> None:
    """能力**查不出来**不等于能力不存在。

    旧写法 ``CLI --help | grep -q`` 取的是 grep 的退出码: help 进程自己崩了也只是
    「没命中」, 于是有效指针在场时照样静默回退默认协议（质检故障注入复现）。
    """
    broken_help = 'import sys\nprint("boom", file=sys.stderr)\nraise SystemExit(70)\n'
    r = _run_binding(tmp_path, broken_help)
    assert r["ERR"] != "", "help 失败必须停下来, 不能冒充「没有 active 子命令」"
    assert "无法查询 CLI 能力" in r["ERR"] and "70" in r["ERR"]
    assert not r["DIR"].endswith("475597e2e017a2eedd3886700cd41d394d3694eba3487e205b8ddc91723b5a2f"), \
        "查询失败却回退到了内置默认"
    assert "boom" in r["log"], "失败原因要留在日志里"


def test_crash_exit_code_is_not_read_as_never_configured(tmp_path) -> None:
    """业务码与崩溃码不能混用。

    Python 未捕获异常退 **1**。若用 1 表达「从未配置」, 一次崩溃就会被读成「没配过」
    而静默回退旧协议——质检把 active.json 写成 ``[]`` 正是走这条路。
    """
    crashing = ('import sys\n'
                'if sys.argv[1:2] == ["--help"]:\n'
                '    print("usage: x [-h] {active,activate,daily} ...")\n'
                '    raise SystemExit(0)\n'
                'raise AttributeError("\'list\' object has no attribute \'get\'")\n')
    r = _run_binding(tmp_path, crashing)
    assert r["ERR"] != "", "崩溃(exit 1)被当成「从未配置」, 静默回退了旧协议"
    assert not r["DIR"].endswith("475597e2e017a2eedd3886700cd41d394d3694eba3487e205b8ddc91723b5a2f")


def test_only_the_dedicated_unset_code_falls_back(tmp_path) -> None:
    """只有 ACTIVE_UNSET(4) 允许回退内置默认; 3 停、其余非 0 也停。"""
    def cli(rc: int) -> str:
        return ('import sys\n'
                'if sys.argv[1:2] == ["--help"]:\n'
                '    print("usage: x [-h] {active,activate,daily} ...")\n'
                '    raise SystemExit(0)\n'
                f'raise SystemExit({rc})\n')

    assert _run_binding(tmp_path, cli(4))["DIR"].endswith("475597e2" + "e017a2eedd3886700cd41d394d3694eba3487e205b8ddc91723b5a2f")
    assert _run_binding(tmp_path, cli(4))["ERR"] == ""
    for rc in (1, 2, 3, 70):
        r = _run_binding(tmp_path, cli(rc))
        assert r["ERR"] != "", f"active 退出 {rc} 被放行了"


def test_valid_binding_is_used_verbatim(tmp_path) -> None:
    """指针有效时原样采用, 不碰默认值。"""
    chosen = tmp_path / "elsewhere" / ("a" * 64)
    chosen.mkdir(parents=True)
    cli = ('import sys\n'
           'if sys.argv[1:2] == ["--help"]:\n'
           '    print("usage: x [-h] {active,activate,daily} ...")\n'
           '    raise SystemExit(0)\n'
           f'print({str(chosen)!r})\n'
           'raise SystemExit(0)\n')
    r = _run_binding(tmp_path, cli)
    assert r["DIR"] == str(chosen) and r["ERR"] == ""
