"""Public method-validation boundaries, with literal worked examples."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from intelligence.services.method_validation import (
    compare,
    read_features,
    read_outcomes,
    validate_capture,
)
from intelligence.services.methodology_backtest.labels import LABEL_SPEC, LABEL_VERSION
from intelligence.services.methodology_backtest.store import open_labels_db, write_meta

from intelligence.services.method_validation import (
    build_protocol,
    load_protocol,
    read_record,
    register,
    validate_protocol,
    write_record,
)

REPO = Path(__file__).resolve().parents[2]
RULE = (
    Path(__file__).resolve().parents[2]
    / "methodology/rules/dual_red_streak3_continuation.v1.json"
)
NOW = datetime(2026, 9, 8, 8, tzinfo=timezone.utc)


def protocol():
    return build_protocol(
        RULE,
        history_start="2026-08-31",
        history_end="2026-09-07",
        forward_start="2026-09-09",
        now=NOW,
    )


def test_protocol_is_content_identified_and_store_is_immutable(tmp_path):
    p = protocol()
    p2 = build_protocol(
        RULE,
        history_start="2026-08-31",
        history_end="2026-09-07",
        forward_start="2026-09-09",
        now=NOW.replace(hour=9),
    )
    assert p["protocol_id"] == p2["protocol_id"]
    directory = register(tmp_path, p)
    assert register(tmp_path, p2) == directory
    assert load_protocol(directory) == p
    record = write_record(
        directory, "history", {"protocol_id": p["protocol_id"], "answer": 2}
    )
    assert (
        write_record(
            directory, "history", {"protocol_id": p["protocol_id"], "answer": 2}
        )
        == record
    )
    assert read_record(record)["payload"]["answer"] == 2
    with pytest.raises(ValueError):
        write_record(directory, "../escape", {})
    p["history"]["end"] = "2026-09-06"
    with pytest.raises(ValueError):
        validate_protocol(p)
    record.write_text("{}")
    with pytest.raises(ValueError):
        read_record(record)


def test_protocol_refuses_backdated_forward_and_foreign_rule(tmp_path):
    with pytest.raises(ValueError):
        build_protocol(
            RULE,
            history_start="2026-08-31",
            history_end="2026-09-07",
            forward_start="2026-09-08",
            now=NOW,
        )
    other = tmp_path / RULE.name
    other.write_text(RULE.read_text().replace('"value": 3', '"value": 4'))
    with pytest.raises(ValueError):
        build_protocol(
            other,
            history_start="2026-08-31",
            history_end="2026-09-07",
            forward_start="2026-09-09",
            now=NOW,
        )


CALENDAR = [
    "2026-08-31",
    "2026-09-01",
    "2026-09-02",
    "2026-09-03",
    "2026-09-04",
    "2026-09-07",
]


def make_db(tmp_path):
    path = tmp_path / "labels.duckdb"
    con = open_labels_db(path, read_only=False)
    con.executemany("INSERT INTO history_calendar VALUES (?, ?)", enumerate(CALENDAR))
    for kind in ("labels", "outcomes"):
        write_meta(
            con,
            build_kind=kind,
            label_version=LABEL_VERSION,
            source_db=tmp_path / "source.duckdb",
            source_max_trade_date=CALENDAR[-1],
            source_row_counts={
                "label_spec": LABEL_SPEC,
                **({"window_start_offset": 1} if kind == "outcomes" else {}),
            },
            row_count=10,
            horizons=(5,) if kind == "outcomes" else None,
            computed_at=NOW,
        )
    con.execute(
        "INSERT INTO history_labels VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            "market",
            "market",
            CALENDAR[0],
            "market_stage",
            None,
            "主升",
            LABEL_VERSION,
            NOW,
        ],
    )
    for entity, strict, streak, ret in [
        ("A", 1, 3, 6),
        ("B", 1, 1, 2),
        ("C", 0, 0, -2),
    ]:
        for label, value in [("dual_red_strict", strict), ("dual_red_streak", streak)]:
            con.execute(
                "INSERT INTO history_labels VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ["sector", entity, CALENDAR[0], label, value, None, LABEL_VERSION, NOW],
            )
        con.execute(
            "INSERT INTO history_outcomes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ["sector", entity, CALENDAR[0], 5, ret, ret, 1, -1.0, "ok", NOW],
        )
    con.close()
    return path


def run_study(path):
    p = protocol()
    features = read_features(path, p, start=CALENDAR[0], end=CALENDAR[0])
    outcomes = read_outcomes(path, p, features)
    return p, features, outcomes, compare(p, features, outcomes)


def test_three_nested_arms_compare_equal_dates_and_freeze_membership(tmp_path):
    path = make_db(tmp_path)
    p, features, outcomes, result = run_study(path)
    assert result["summary"]["means"] == {
        "universe": 2.0,
        "dual_red": 4.0,
        "streak3": 6.0,
    }
    assert result["summary"]["paired_dates"] == 1
    assert result["summary"]["streak3_minus_dual_red_pp"] == 2.0
    assert result["summary"]["streak3_minus_universe_pp"] == 4.0
    assert result["coverage"]["raw_entity_dates"] == 3
    assert result["decision_eligible"] is False
    assert features["calendar"] == [CALENDAR[0]]
    con = open_labels_db(path, read_only=False)
    con.execute("UPDATE history_labels SET value_num=0 WHERE entity_id='A'")
    con.close()
    assert compare(p, features, read_outcomes(path, p, features)) == result
    assert outcomes["calendar"] == CALENDAR


@pytest.mark.parametrize(
    "edit, reason",
    [
        (
            "UPDATE history_outcomes SET status='pending_window' WHERE entity_id='C'",
            "pending",
        ),
        ("DELETE FROM history_outcomes WHERE entity_id='C'", "missing"),
        (
            "UPDATE history_labels SET value_num=NULL WHERE entity_id='C' AND label='dual_red_strict'",
            "unknown_label",
        ),
        (
            "UPDATE history_labels SET value_text='退潮' WHERE entity_type='market'",
            "stage_not_applicable",
        ),
        (
            "UPDATE history_labels SET value_num=1 WHERE label='dual_red_streak'",
            "no_event",
        ),
        (
            "DELETE FROM history_calendar WHERE trade_date='2026-08-31'",
            "missing_calendar",
        ),
        (
            "UPDATE history_outcomes SET fwd_return='NaN'::DOUBLE WHERE entity_id='C'",
            "invalid",
        ),
        (
            "UPDATE history_outcomes SET fwd_return='Infinity'::DOUBLE WHERE entity_id='C'",
            "invalid",
        ),
        ("UPDATE history_outcomes SET fwd_return=-100 WHERE entity_id='C'", "invalid"),
        ("DELETE FROM history_calendar WHERE trade_date='2026-09-07'", "pending"),
    ],
)
def test_incomplete_or_inapplicable_days_never_win_or_lose(tmp_path, edit, reason):
    path = make_db(tmp_path)
    con = open_labels_db(path, read_only=False)
    con.execute(edit)
    con.close()
    _, _, _, result = run_study(path)
    assert result["summary"]["paired_dates"] == 0
    assert result["summary"]["streak3_minus_dual_red_pp"] is None
    assert reason in result["daily"][0]["reasons"]
    import json

    json.dumps(result, allow_nan=False)


def test_more_entities_do_not_increase_paired_dates_and_empty_calendar_days_are_kept(
    tmp_path,
):
    path = make_db(tmp_path)
    con = open_labels_db(path, read_only=False)
    con.execute(
        "INSERT INTO history_labels SELECT entity_type, 'D', trade_date, label, value_num, value_text, label_version, computed_at FROM history_labels WHERE entity_id='B'"
    )
    con.execute(
        "INSERT INTO history_outcomes SELECT entity_type, 'D', trade_date, horizon, fwd_return, max_return, days_to_peak, drawdown_after_peak, status, computed_at FROM history_outcomes WHERE entity_id='B'"
    )
    con.close()
    p = protocol()
    features = read_features(path, p, start=CALENDAR[0], end=CALENDAR[1])
    result = compare(p, features, read_outcomes(path, p, features))
    assert result["summary"]["paired_dates"] == 1
    assert result["coverage"]["raw_entity_dates"] == 4
    assert len(result["daily"]) == 2
    assert result["daily"][1]["reasons"] == ["no_sector_labels"]


@pytest.mark.parametrize(
    "edit",
    [
        "UPDATE history_build_meta SET label_version='old' WHERE build_kind='labels'",
        "UPDATE history_build_meta SET label_version='old' WHERE build_kind='outcomes'",
        "UPDATE history_build_meta SET source_db='/other' WHERE build_kind='outcomes'",
        "UPDATE history_build_meta SET source_max_trade_date='2026-09-04' WHERE build_kind='outcomes'",
        "UPDATE history_build_meta SET source_row_counts='{}' WHERE build_kind='labels'",
        "UPDATE history_labels SET label_version='old' WHERE entity_id='A'",
    ],
)
def test_metadata_and_row_versions_fail_closed(tmp_path, edit):
    path = make_db(tmp_path)
    con = open_labels_db(path, read_only=False)
    con.execute(edit)
    con.close()
    with pytest.raises(ValueError):
        run_study(path)


def test_other_sidecar_cannot_supply_results_and_historical_calendar_cannot_move(
    tmp_path,
):
    import shutil

    path = make_db(tmp_path)
    p, features, _, _ = run_study(path)
    copy_path = tmp_path / "copied.duckdb"
    shutil.copyfile(path, copy_path)
    with pytest.raises(ValueError):
        read_outcomes(copy_path, p, features)
    con = open_labels_db(path, read_only=False)
    con.execute("INSERT INTO history_calendar VALUES (-1, '2026-08-28')")
    con.close()
    with pytest.raises(ValueError):
        compare(p, features, read_outcomes(path, p, features))


def capture_db(tmp_path):
    path = make_db(tmp_path)
    con = open_labels_db(path, read_only=False)
    con.execute("DELETE FROM history_calendar")
    con.execute("INSERT INTO history_calendar VALUES (0, '2026-09-09')")
    con.execute(
        "UPDATE history_labels SET trade_date='2026-09-09', computed_at='2026-09-09 07:30:00'"
    )
    con.execute(
        "UPDATE history_build_meta SET source_max_trade_date='2026-09-09', computed_at='2026-09-09 07:30:00'"
    )
    con.execute("DELETE FROM history_outcomes")
    con.execute("DELETE FROM history_build_meta WHERE build_kind='outcomes'")
    con.close()
    return path


def test_capture_uses_utc_timestamps_and_needs_no_outcomes(tmp_path):
    path = capture_db(tmp_path)
    p = protocol()
    features = read_features(path, p, start="2026-09-09", end="2026-09-09")
    validate_capture(p, features, now=NOW.replace(day=9))
    directory = register(tmp_path / "studies", p)
    stored = write_record(
        directory, "capture", {"protocol_id": p["protocol_id"], "features": features}
    )
    assert stored.parent.name == "2026-09-09"
    assert set(read_record(stored)["payload"]) == {"protocol_id", "features"}
    with pytest.raises(ValueError):
        write_record(
            directory,
            "capture",
            {"protocol_id": p["protocol_id"], "features": features, "outcomes": {}},
        )


@pytest.mark.parametrize(
    "edit",
    [
        "UPDATE history_build_meta SET source_max_trade_date='2026-09-08'",
        "UPDATE history_build_meta SET computed_at='2026-09-09 06:59:00'",
        "UPDATE history_labels SET computed_at='2026-09-08 08:00:00' WHERE entity_id='A'",
        "UPDATE history_labels SET computed_at='2026-09-09 08:01:00' WHERE entity_id='A'",
        "DELETE FROM history_calendar",
        "DELETE FROM history_labels WHERE entity_type='sector'",
    ],
)
def test_capture_refuses_stale_intraday_future_or_unsynchronized_labels(tmp_path, edit):
    path = capture_db(tmp_path)
    con = open_labels_db(path, read_only=False)
    con.execute(edit)
    con.close()
    p = protocol()
    features = read_features(path, p, start="2026-09-09", end="2026-09-09")
    with pytest.raises(ValueError):
        validate_capture(p, features, now=NOW.replace(day=9))


def test_capture_refuses_past_date_and_before_close(tmp_path):
    p = protocol()
    features = read_features(
        capture_db(tmp_path), p, start="2026-09-09", end="2026-09-09"
    )
    for current in (NOW.replace(day=9, hour=6), NOW.replace(day=10)):
        with pytest.raises(ValueError):
            validate_capture(p, features, now=current)


def test_protocol_created_at_is_protected_by_storage_digest(tmp_path):
    import json

    p = protocol()
    directory = register(tmp_path, p)
    path = directory / "protocol.json"
    envelope = json.loads(path.read_text())
    envelope["protocol"]["created_at"] = "2026-09-07T08:00:00+00:00"
    path.write_text(json.dumps(envelope))
    with pytest.raises(ValueError):
        load_protocol(directory)


def test_write_failure_leaves_no_partial_record_and_duplicate_writers_converge(
    tmp_path, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    import os

    p = protocol()
    directory = register(tmp_path, p)
    payload = {"protocol_id": p["protocol_id"], "answer": 2}
    with monkeypatch.context() as patch:

        def fail_sync(_):
            raise OSError("disk failure")

        patch.setattr(os, "fsync", fail_sync)
        with pytest.raises(OSError):
            write_record(directory, "history", payload)
    assert not list((directory / "history").rglob("*.json"))
    assert not list((directory / "history").rglob(".pending-*"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: write_record(directory, "history", payload), range(2))
        )
    assert results[0] == results[1]
    assert read_record(results[0])["payload"] == payload


def test_absent_results_before_d_plus_5_remain_pending(tmp_path):
    path = make_db(tmp_path)
    con = open_labels_db(path, read_only=False)
    con.execute("DELETE FROM history_outcomes")
    con.execute("DELETE FROM history_calendar WHERE trade_date='2026-09-07'")
    con.close()
    _, _, _, result = run_study(path)
    assert result["daily"][0]["reasons"] == ["pending"]
    assert result["summary"]["paired_dates"] == 0


@pytest.mark.parametrize(
    "edit",
    [
        "UPDATE history_build_meta SET source_row_counts='{}' WHERE build_kind='outcomes'",
        "UPDATE history_build_meta SET computed_at='2026-09-08 09:00:00' WHERE build_kind='outcomes'",
        "UPDATE history_build_meta SET computed_at='2026-09-08 09:00:00' WHERE build_kind='labels'",
        "UPDATE history_build_meta SET source_max_trade_date='2026-09-09'",
        "UPDATE history_build_meta SET computed_at='2026-09-07 06:59:00' WHERE build_kind='outcomes'",
        "INSERT INTO history_calendar VALUES (6, '2026-09-08')",
    ],
)
def test_outcomes_reject_future_watermarks_builds_calendar_and_unspecified_window(
    tmp_path, edit
):
    path = make_db(tmp_path)
    p = protocol()
    features = read_features(path, p, start=CALENDAR[0], end=CALENDAR[0])
    con = open_labels_db(path, read_only=False)
    con.execute(edit)
    con.close()
    with pytest.raises(ValueError):
        read_outcomes(path, p, features, now=NOW)


def test_d_plus_5_cannot_mature_before_the_actual_close(tmp_path):
    path = make_db(tmp_path)
    p = protocol()
    features = read_features(path, p, start=CALENDAR[0], end=CALENDAR[0])
    with pytest.raises(ValueError):
        read_outcomes(path, p, features, now=NOW.replace(day=7, hour=6))


def test_static_protocol_identity_does_not_backdate_new_registration():
    from intelligence.services.method_validation import protocol_id_for

    p = protocol()
    assert (
        protocol_id_for(
            RULE,
            history_start="2026-08-31",
            history_end="2026-09-07",
            forward_start="2026-09-09",
        )
        == p["protocol_id"]
    )
    with pytest.raises(ValueError):
        build_protocol(
            RULE,
            history_start="2026-08-31",
            history_end="2026-09-07",
            forward_start="2026-09-09",
            now=NOW.replace(day=10),
        )


def test_archived_records_survive_version_upgrade_but_new_computation_refuses(
    tmp_path, monkeypatch
):
    from intelligence.services.method_validation import protocol as contract

    path = make_db(tmp_path)
    p, features, outcomes, comparison = run_study(path)
    directory = register(tmp_path / "studies", p)
    record_path = write_record(
        directory,
        "history",
        {
            "protocol_id": p["protocol_id"],
            "features": features,
            "outcomes": outcomes,
            "comparison": comparison,
        },
    )
    original = read_record(record_path)
    monkeypatch.setattr(contract, "LABEL_VERSION", "new-label-version")
    monkeypatch.setattr(
        contract,
        "LABEL_SPEC",
        {"label_version": "new-label-version", "new": "definition"},
    )
    monkeypatch.setattr(contract, "EVALUATOR_VERSION", "new-evaluator-version")
    assert load_protocol(directory) == p
    assert read_record(record_path) == original
    validate_protocol(p, require_current=False)
    with pytest.raises(ValueError):
        validate_protocol(p)
    with pytest.raises(ValueError):
        compare(p, features, outcomes)
    with pytest.raises(ValueError):
        read_features(path, p, start=CALENDAR[0], end=CALENDAR[0])


def test_supersede_actually_deactivates_not_just_annotates(tmp_path):
    """封存必须有运行语义：只写标记而消费者照常枚举，等于没封存。"""
    from intelligence.services.method_validation import (
        is_superseded, list_studies, supersede,
    )

    older = build_protocol(
        RULE, history_start="2026-08-24", history_end="2026-09-04",
        forward_start="2026-09-07", now=datetime(2026, 9, 4, 8, tzinfo=timezone.utc),
    )
    d_old = register(tmp_path, older)
    d_new = register(tmp_path, protocol())
    assert len(list_studies(tmp_path)) == 2

    supersede(d_old, successor_id=protocol()["protocol_id"], reason="标签版本迁移")
    assert is_superseded(d_old)
    active = list_studies(tmp_path)
    assert active == [d_new], "封存后消费者仍在枚举旧协议"
    # 审计口径要能看见全部，否则就成了删除
    assert len(list_studies(tmp_path, include_superseded=True)) == 2


def test_activate_switches_binding_and_refuses_superseded(tmp_path):
    """登记 ≠ 切换：绑定要能被显式切换，且不能切到已封存协议。"""
    from intelligence.services.method_validation import (
        active_study, set_active, supersede,
    )

    older = build_protocol(
        RULE, history_start="2026-08-24", history_end="2026-09-04",
        forward_start="2026-09-07", now=datetime(2026, 9, 4, 8, tzinfo=timezone.utc),
    )
    d_old = register(tmp_path, older)
    d_new = register(tmp_path, protocol())
    assert active_study(tmp_path) is None, "未切换时不应凭空产生绑定"

    set_active(tmp_path, d_old)
    assert active_study(tmp_path) == d_old
    set_active(tmp_path, d_new)
    assert active_study(tmp_path) == d_new, "切换未生效"

    supersede(d_new, reason="误操作")
    assert active_study(tmp_path) is None, "指向已封存协议时必须失效, 由调用方回退"
    with pytest.raises(ValueError, match="superseded"):
        set_active(tmp_path, d_new)


def test_active_binding_distinguishes_unset_from_broken(tmp_path):
    """「从未配置」和「配置过但失效」处置相反：前者兼容默认, 后者必须停。"""
    from intelligence.services.method_validation import (
        active_binding, set_active, supersede,
    )

    assert active_binding(tmp_path)["state"] == "unset"

    d_new = register(tmp_path, protocol())
    set_active(tmp_path, d_new)
    assert active_binding(tmp_path)["state"] == "ok"

    supersede(d_new, reason="迁移")
    binding = active_binding(tmp_path)
    assert binding["state"] == "superseded", "封存后仍报可用, 夜跑会拿错协议写新观察"
    assert binding["study_dir"] is None and binding["detail"]

    (tmp_path / "active.json").write_text("{ 不是 json", encoding="utf-8")
    assert active_binding(tmp_path)["state"] == "corrupt"


def test_structurally_valid_json_that_is_not_an_object_is_corrupt_not_unset(tmp_path):
    """`[]` / `null` / `"x"` 都能被 json.loads 解析, 但 doc.get 会抛 AttributeError。

    未捕获就是进程 exit 1, 恰好与旧版「从未配置」的业务码相同, 夜跑于是静默回退旧协议
    （09-12 质检实测）。这类内容必须归 corrupt, 不能归 unset, 更不能抛出去。
    """
    from intelligence.services.method_validation import active_binding

    for payload in ("[]", "null", '"x"', "123"):
        (tmp_path / "active.json").write_text(payload, encoding="utf-8")
        binding = active_binding(tmp_path)
        assert binding["state"] == "corrupt", f"{payload} 被判成 {binding['state']}"
        assert binding["study_dir"] is None


def test_pointer_that_is_not_a_regular_file_is_corrupt_not_unset(tmp_path):
    """目录与悬空软链都会让 is_file() 返回 False——旧实现据此报「没配过」。"""
    from intelligence.services.method_validation import active_binding

    (tmp_path / "active.json").mkdir()
    assert active_binding(tmp_path)["state"] == "corrupt", "指针是目录却报「没配过」"

    (tmp_path / "active.json").rmdir()
    (tmp_path / "active.json").symlink_to(tmp_path / "does-not-exist")
    assert active_binding(tmp_path)["state"] == "corrupt", "悬空软链却报「没配过」"


def test_broken_protocol_is_invalid_in_both_output_modes(tmp_path):
    """有效性不能由展示格式决定: --print-dir 说有效、普通模式说损坏（质检实测 0 vs 2）。"""
    import subprocess
    import sys

    from intelligence.services.method_validation import active_binding, set_active

    study = register(tmp_path, protocol())
    set_active(tmp_path, study)
    (study / "protocol.json").write_text('{"protocol_id": "坏了"}', encoding="utf-8")

    assert active_binding(tmp_path)["state"] == "corrupt"
    cli = [sys.executable, str(REPO / "scripts" / "method_validation.py"), "active", "--root", str(tmp_path)]
    printed = subprocess.run([*cli, "--print-dir"], capture_output=True, text=True)
    plain = subprocess.run(cli, capture_output=True, text=True)
    assert printed.returncode == plain.returncode != 0, \
        f"两种输出模式判定不一致: --print-dir={printed.returncode} 普通={plain.returncode}"
    assert printed.stdout.strip() == "", "判定为坏却仍打印了目录, 夜跑会照用"


def test_set_active_rejects_study_outside_root(tmp_path):
    """指针只存目录名, 跨根写入会「返回成功但读不回」。"""
    from intelligence.services.method_validation import active_study, set_active

    home = tmp_path / "users" / "real" / "method_validation"
    other = tmp_path / "users" / "default" / "method_validation"
    home.mkdir(parents=True)
    other.mkdir(parents=True)
    study = register(home, protocol())

    with pytest.raises(ValueError, match="does not belong to root"):
        set_active(other, study)
    assert active_study(other) is None
    assert not (other / "active.json").exists(), "拒绝后不该留下半条指针"


def test_supersede_is_idempotent_for_same_intent(tmp_path):
    """同一封存意图重试必须幂等: superseded_at 每次都是 now, 否则撞不可覆盖发布。"""
    from intelligence.services.method_validation import supersede

    study = register(tmp_path, protocol())
    first = supersede(study, successor_id=None, reason="口径 v3 → v5")
    stamp = json.loads(first.read_text(encoding="utf-8"))["superseded_at"]

    again = supersede(study, successor_id=None, reason="口径 v3 → v5")
    assert again == first
    assert json.loads(again.read_text(encoding="utf-8"))["superseded_at"] == stamp, \
        "重试刷新了封存时刻, 首次封存的事实被改写"

    with pytest.raises(ValueError, match="different successor/reason"):
        supersede(study, successor_id=None, reason="换个理由")
