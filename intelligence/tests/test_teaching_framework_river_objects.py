"""授课框架 → 时间长河：旁路库里的教学标签作盘面轨 ``teaching_*`` 对象；只暴露当日已知的东西。"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from intelligence.services.methodology_backtest.store import open_labels_db
from intelligence.services.teaching_framework.river_objects import teaching_objects

BUILT_AT = datetime(2026, 9, 7, 15, 0, 0)
FW = "tf-v0.2+test"


def _label(day: str, label: str, num=None, text=None):
    return ("market", "market", date.fromisoformat(day), label, num, text, "v-test", FW, "ok", None, BUILT_AT)


@pytest.fixture
def sidecar(tmp_path: Path) -> Path:
    path = tmp_path / "labels.duckdb"
    con = open_labels_db(path, read_only=False)
    evidence = {"scores": {"左底向下": 3}, "hits": [{"stage": "左底向下", "predicate": "E:first_cross_below"}],
                "confidence": {"stage": "左底向下", "hits": 3, "possible": 6, "missing": ["H:in_band:x"], "margin": 1},
                "from": "高位震荡", "entered": ["左底向下"], "eligible": ["左底向下", "高位震荡"], "resolution": "entry", "tied": []}
    rows = [
        _label("2026-01-12", "tf.stage_coarse", text="左底向下"), _label("2026-01-12", "tf.stage_fine", text="左底向下"),
        _label("2026-01-12", "tf.stage_evidence", text=json.dumps(evidence, ensure_ascii=False)),
        _label("2026-01-12", "tf.volume_band", text="shrink"), _label("2026-01-12", "tf.deviation_band", text="below"),
        _label("2026-01-12", "tf.above_week_ma", num=0), _label("2026-01-12", "tf.money_losing_day", num=1),
        _label("2026-01-12", "tf.money_losing_streak", num=2), _label("2026-01-12", "tf.limit_premium_ma5_pct", num=0.8),
        _label("2026-01-12", "tf.turn_down", num=1),
        # A label the slice does not read must not leak into the payload.
        _label("2026-01-12", "tf.stock_price_mean", num=21.0),
        # Neighbouring days only carry the money-losing flag (for the collapse counters).
        _label("2026-01-13", "tf.money_losing_day", num=0), _label("2026-01-14", "tf.money_losing_day", num=1),
        _label("2026-02-06", "tf.money_losing_day", num=1),
    ]
    con.executemany("INSERT INTO history_teaching_labels VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    # Wave 0 peaked on 01-09, collapsed 01-12 → 01-20; wave 1 started 01-21, peaked 02-05, collapse open from 02-06.
    con.executemany(
        """INSERT INTO history_dynasties (wave_idx, rank, wave_start, peak_end, collapse_start, collapse_end, wave_status, stock_ts_code,
           stock_name, wave_gain_pct, sw_l1, max_boards, form, collapse_ret_pct, collapse_max_dd_pct, framework_version, computed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (0, 1, date(2025, 12, 12), date(2026, 1, 9), date(2026, 1, 12), date(2026, 1, 20), "ok", "A", "甲", 180.0, "电子", 5, "连板", -40.0, -45.0, FW, BUILT_AT),
            (0, 2, date(2025, 12, 12), date(2026, 1, 9), date(2026, 1, 12), date(2026, 1, 20), "ok", "B", "乙", 120.0, "通信", None, "趋势", -35.0, -40.0, FW, BUILT_AT),
            (0, 3, date(2025, 12, 12), date(2026, 1, 9), date(2026, 1, 12), date(2026, 1, 20), "ok", "C", "丙", 90.0, "电子", None, "趋势", -20.0, -30.0, FW, BUILT_AT),
            (1, 1, date(2026, 1, 21), date(2026, 2, 5), date(2026, 2, 6), None, "open", "F", "己", 150.0, "电子", None, "趋势", None, None, FW, BUILT_AT),
            (1, 2, date(2026, 1, 21), date(2026, 2, 5), date(2026, 2, 6), None, "open", "G", "庚", 140.0, "医药生物", 4, "连板", None, None, FW, BUILT_AT),
        ],
    )
    con.executemany(
        """INSERT INTO history_dynasty_handoffs (old_wave_idx, new_wave_idx, new_rank, stock_ts_code, stock_name, new_wave_gain_pct, sw_l1, form,
           old_wave_rank, in_old_cohort, l1_in_old_top, collapse_ret_pct, collapse_ret_percentile, collapse_max_dd_pct, first_leg_ret_pct,
           new_high_in_collapse, separation_relative, separation_new_high, losing_days_ret_pct, losing_days_ret_percentile, separation_on_losing_days,
           other_days_ret_pct, other_days_ret_percentile, separation_on_other_days, framework_version, computed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (0, 1, 1, "F", "己", 150.0, "电子", "趋势", 6, False, True, 12.0, 90.0, -3.0, 1.0, True, True, True, -4.0, 50.0, False, 16.7, 95.0, True, FW, BUILT_AT),
            (0, 1, 2, "G", "庚", 140.0, "医药生物", "连板", 7, False, False, 6.0, 80.0, -6.0, -2.0, True, False, True, 1.0, 90.0, True, 5.0, 60.0, False, FW, BUILT_AT),
        ],
    )
    con.executemany(
        """INSERT INTO history_range_leaders (window_days, trade_date, rank, stock_ts_code, stock_name, gain_pct, sw_l1, limit_times, tenure_day,
           prev_rank, framework_version, computed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(20, date(2026, 1, 12), 1, "X", "子", 45.0, "电子", 3, 2, 1, FW, BUILT_AT), (20, date(2026, 1, 12), 2, "Y", "丑", 40.0, "通信", None, 1, 12, FW, BUILT_AT),
         (60, date(2026, 1, 12), 1, "Z", "寅", 120.0, "汽车", None, 9, 1, FW, BUILT_AT)],
    )
    con.close()
    return path


def test_stage_object_carries_the_days_reading_and_only_the_slice_fields(sidecar: Path) -> None:
    objs = {o.object_type: o for o in teaching_objects(sidecar, "2026-01-12", top=2)}
    assert set(objs) == {"teaching_stage", "teaching_dynasty", "teaching_range_leaders"}
    stage = objs["teaching_stage"]
    assert stage.track == "market" and stage.entity_id == "__market__" and stage.ref == "history_teaching_labels:2026-01-12:market"
    assert stage.valid_from == "2026-01-12" and stage.recorded_at is not None and stage.recorded_at.startswith("2026-09-07")
    p = stage.payload
    assert p["stage_coarse"] == "左底向下" and p["volume_band"] == "shrink" and p["money_losing_day"] == 1 and p["money_losing_streak"] == 2
    assert p["evidence"]["confidence"] == {"stage": "左底向下", "hits": 3, "possible": 6, "missing": ["H:in_band:x"], "margin": 1}
    assert p["evidence"]["from"] == "高位震荡" and p["evidence_hits"] == ["左底向下:E:first_cross_below"]
    assert p["framework_version"] == "tf-v0.2+test" and "stock_price_mean" not in p and "scores" not in p["evidence"]
    assert len(p) <= 20  # 索引层不持有主数据副本
    assert len(stage.source_hash) == 16


def test_dynasty_object_only_exposes_what_the_day_already_knows(sidecar: Path) -> None:
    # Inside wave 0's peak block: no wave has peaked yet as far as that day knows → no dynasty object at all.
    kinds = {o.object_type for o in teaching_objects(sidecar, "2026-01-08", top=2)}
    assert "teaching_dynasty" not in kinds
    # First collapse day of wave 0: the wave is known to have peaked; its members are exposed, nothing about wave 1.
    (d,) = [o for o in teaching_objects(sidecar, "2026-01-12", top=2) if o.object_type == "teaching_dynasty"]
    p = d.payload
    assert p["wave_idx"] == 0 and p["peak_end"] == "2026-01-09" and p["collapse_start"] == "2026-01-12"
    assert [m["stock_ts_code"] for m in p["dynasty_top"]] == ["A", "B"] and p["dynasty_top"][0]["form"] == "连板"
    assert p["labelled_days_since_collapse_start"] == 1 and p["money_losing_days_since_collapse_start"] == 1
    assert "collapse_end" not in p and "last_completed_handoff" not in p and "new_dynasty_top" not in p
    assert d.ref == "history_dynasties:0" and d.recorded_at.startswith("2026-09-07")
    # Two days later the counters move with the labels (01-13 not losing, 01-14 losing).
    (d2,) = [o for o in teaching_objects(sidecar, "2026-01-14", top=2) if o.object_type == "teaching_dynasty"]
    assert d2.payload["labelled_days_since_collapse_start"] == 3 and d2.payload["money_losing_days_since_collapse_start"] == 2
    # Inside wave 1's peak block (01-21 → 02-05) the latest *known* wave is still wave 0: wave 1 has not peaked, so it is invisible.
    (d3,) = [o for o in teaching_objects(sidecar, "2026-02-03", top=2) if o.object_type == "teaching_dynasty"]
    assert d3.payload["wave_idx"] == 0 and "last_completed_handoff" not in d3.payload
    # Wave 1's first collapse day: wave 1 is known, and so is the whole W0→W1 handoff (分离确认 of F and G in W0's collapse).
    (d4,) = [o for o in teaching_objects(sidecar, "2026-02-06", top=2) if o.object_type == "teaching_dynasty"]
    p4 = d4.payload
    assert p4["wave_idx"] == 1 and [m["stock_ts_code"] for m in p4["dynasty_top"]] == ["F", "G"]
    assert p4["labelled_days_since_collapse_start"] == 1 and p4["money_losing_days_since_collapse_start"] == 1
    handoff = p4["last_completed_handoff"]
    assert handoff["old_wave_idx"] == 0 and handoff["old_collapse"] == ["2026-01-12", "2026-01-20"]
    f = handoff["new_members_in_old_collapse"][0]
    assert (f["stock_ts_code"], f["old_wave_rank"], f["collapse_ret_percentile"], f["separation_relative"], f["separation_on_losing_days"], f["separation_on_other_days"]) == ("F", 6, 90.0, True, False, True)


def test_range_leaders_object_groups_by_window_and_is_absent_on_other_days(sidecar: Path) -> None:
    (rl,) = [o for o in teaching_objects(sidecar, "2026-01-12", top=2) if o.object_type == "teaching_range_leaders"]
    assert set(rl.payload["windows"]) == {"20", "60"}
    assert [m["stock_ts_code"] for m in rl.payload["windows"]["20"]] == ["X", "Y"] and rl.payload["windows"]["20"][0]["limit_times"] == 3
    assert rl.payload["windows"]["60"][0]["tenure_day"] == 9 and rl.ref == "history_range_leaders:2026-01-12"
    assert all(o.object_type != "teaching_range_leaders" for o in teaching_objects(sidecar, "2026-01-13", top=2))


def test_missing_sidecar_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        teaching_objects(tmp_path / "nope.duckdb", "2026-01-12")


def test_river_slice_is_byte_identical_without_the_sidecar_and_strict_pit_filters_it(sidecar: Path, tmp_path: Path) -> None:
    """The river switch: no ``teaching_labels_db`` → unchanged slice; with it → market objects; strict PIT drops them (built later)."""
    from intelligence.services.river import slice_river

    db = Path("db/market_feature_store.duckdb")
    if not db.exists():
        pytest.skip("需要真库 db/market_feature_store.duckdb")
    ck = tmp_path / "checkpoints.jsonl"
    ck.write_text("", encoding="utf-8")
    plain = slice_river("2026-01-12", "算力租赁", checkpoints_path=ck).to_dict()
    again = slice_river("2026-01-12", "算力租赁", checkpoints_path=ck, teaching_labels_db=None).to_dict()
    assert json.dumps(plain, sort_keys=True, default=str) == json.dumps(again, sort_keys=True, default=str)
    with_teaching = slice_river("2026-01-12", "算力租赁", checkpoints_path=ck, teaching_labels_db=sidecar)
    kinds = [o.object_type for o in with_teaching.objects if o.object_type.startswith("teaching_")]
    assert kinds == ["teaching_stage", "teaching_dynasty", "teaching_range_leaders"]
    assert with_teaching.pit_grade == "trade_date_only"  # built on 2026-09-07, after as_of
    strict = slice_river("2026-01-12", "算力租赁", checkpoints_path=ck, teaching_labels_db=sidecar, require_strict=True)
    assert not [o for o in strict.objects if o.object_type.startswith("teaching_")]
