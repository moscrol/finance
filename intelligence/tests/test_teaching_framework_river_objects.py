"""授课框架 → 时间长河：旁路库里的教学标签作盘面轨 ``teaching_*`` 对象；只暴露当日已知的东西。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.services.teaching_framework.river_objects import teaching_objects

from intelligence.tests.teaching_sidecar_fixture import build_sidecar


@pytest.fixture
def sidecar(tmp_path: Path) -> Path:
    return build_sidecar(tmp_path / "labels.duckdb")


def test_stage_object_carries_the_days_reading_and_only_the_slice_fields(sidecar: Path) -> None:
    objs = {o.object_type: o for o in teaching_objects(sidecar, "2026-01-12", top=2)}
    assert set(objs) == {"teaching_stage", "teaching_capital", "teaching_narrative", "teaching_briefing", "teaching_dynasty", "teaching_range_leaders"}
    assert objs["teaching_narrative"].payload["narrative_cover_rps5_pct"] == 40.0 and objs["teaching_narrative"].ref.endswith(":narrative")
    brief = objs["teaching_briefing"].payload
    # 二维晨汇：盘面共振那一格没有值就没有键（不可知不是 0）；维度、条数、机器对照、写成滞后都在。
    assert (brief["briefing_tier1_items"], brief["briefing_tier2_items"], brief["briefing_dimensions"], brief["briefing_lag_days"]) == (3.0, 5.0, 2.0, 23.0)
    assert "briefing_market_confirmed" not in brief and objs["teaching_briefing"].ref.endswith(":briefing")
    # 两个叙事对象都在的日子，阶段对象上不挂任何缺口原因。
    assert "narrative_gap" not in objs["teaching_stage"].payload and "briefing_gap" not in objs["teaching_stage"].payload
    capital = objs["teaching_capital"]
    assert capital.payload["dragon_buy_sell_ratio_ma5"] == 1.7 and capital.payload["top100_amount_share"] == 0.187 and len(capital.payload) <= 20
    assert capital.ref == "history_teaching_labels:2026-01-12:market:capital"
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
    assert [m["stock_ts_code"] for m in p["dynasty_top"]] == ["600001.SH", "600002.SH"] and p["dynasty_top"][0]["form"] == "连板"
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
    objs_0206 = {o.object_type: o for o in teaching_objects(sidecar, "2026-02-06", top=2)}
    # 02-06 两个叙事源都没有读数：各自的原因挂在阶段对象上，两个对象都不出现。
    assert "teaching_narrative" not in objs_0206 and "teaching_briefing" not in objs_0206
    assert objs_0206["teaching_stage"].payload["narrative_gap"] == "narrative_stale" and objs_0206["teaching_stage"].payload["briefing_gap"] == "briefing_absent_day"
    d4 = objs_0206["teaching_dynasty"]
    p4 = d4.payload
    assert p4["wave_idx"] == 1 and [m["stock_ts_code"] for m in p4["dynasty_top"]] == ["300006.SZ", "300007.SZ"]
    assert p4["labelled_days_since_collapse_start"] == 1 and p4["money_losing_days_since_collapse_start"] == 1
    handoff = p4["last_completed_handoff"]
    assert handoff["old_wave_idx"] == 0 and handoff["old_collapse"] == ["2026-01-12", "2026-01-20"]
    f = handoff["new_members_in_old_collapse"][0]
    assert (f["stock_ts_code"], f["old_wave_rank"], f["collapse_ret_percentile"], f["separation_relative"], f["separation_on_losing_days"], f["separation_on_other_days"]) == ("300006.SZ", 6, 90.0, True, False, True)


def test_range_leaders_object_groups_by_window_and_is_absent_on_other_days(sidecar: Path) -> None:
    (rl,) = [o for o in teaching_objects(sidecar, "2026-01-12", top=2) if o.object_type == "teaching_range_leaders"]
    assert set(rl.payload["windows"]) == {"20", "60"}
    assert [m["stock_ts_code"] for m in rl.payload["windows"]["20"]] == ["000011.SZ", "000012.SZ"] and rl.payload["windows"]["20"][0]["limit_times"] == 3
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
    assert kinds == ["teaching_stage", "teaching_capital", "teaching_narrative", "teaching_briefing", "teaching_dynasty", "teaching_range_leaders"]
    assert with_teaching.pit_grade == "trade_date_only"  # built on 2026-09-07, after as_of
    strict = slice_river("2026-01-12", "算力租赁", checkpoints_path=ck, teaching_labels_db=sidecar, require_strict=True)
    assert not [o for o in strict.objects if o.object_type.startswith("teaching_")]
