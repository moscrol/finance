"""偏差目录 v1（INDEX #24）：四条各阳性 / 阴性 / unverifiable；rule_not_firing 用最小旁路库夹具走真编译器。

数据源全部以可注入 callable 形式给出，不连真库、不碰真人台账。

变异测试（记进交接）：把 ``checkpoint_bias.check_rule_not_firing`` 里的 ``if fired_here: return None`` 反过来
（``if not fired_here``），``test_rule_not_firing_positive_when_entity_absent_from_event_set`` 与
``test_rule_not_firing_real_compiler_on_mini_labels_db`` 必须变红；恢复后绿。
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from intelligence.services import checkpoint_bias as cb
from intelligence.services.checkpoint_bias import BiasFlag, RuleFire


# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #
def _weekdays(start: date, n: int) -> list[str]:
    out: list[str] = []
    d = start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


# 2026-08-03（周一）起 25 个交易日：… 08-28(五) 08-31(一) 09-01(二) 09-02(三) 09-03(四) 09-04(五)
CAL = _weekdays(date(2026, 8, 3), 25)
assert CAL[-1] == "2026-09-04" and "2026-09-02" in CAL


def ck(
    cid: str,
    ts: str,
    *,
    category: str | None = "生命周期推演",
    themes: list[str] | None = None,
    stocks: list[str] | None = None,
    rule_id: str | None = None,
) -> dict:
    rec = {"id": cid, "ts": ts, "claim": f"claim {cid}", "due": "2099-01-01", "category": category,
           "themes": list(themes or []), "stocks": list(stocks or [])}
    if rule_id:
        rec["rule_id"] = rule_id
    return rec


def vd(cid: str, verdict: str, checked_at: str) -> dict:
    return {"id": cid, "verdict": verdict, "checked_at": checked_at, "score": 1.0 if verdict == "hit" else 0.0}


def make_label_lookup(table: dict[tuple[str, str, str, str], float | None]):
    """table[(entity_type, entity_id, label, trade_date)] = value_num（None = 行存在但 NULL）。"""

    def lookup(entity_type, entity_ids, label, trade_dates):
        return {
            (e, d): table[(entity_type, e, label, d)]
            for e in entity_ids
            for d in trade_dates
            if (entity_type, e, label, d) in table
        }

    return lookup


def make_entity_lookup(mapping: dict[str, list[str]] | None):
    return lambda themes: (None if mapping is None else {t: list(mapping.get(t, [])) for t in themes})


def make_rule_fire_lookup(fired: set[str], *, entity_type: str = "sector", rule_ref: str = "r1@v1"):
    return lambda rule_id, d0: RuleFire(rule_ref=rule_ref, entity_type=entity_type, trade_date=d0, fired=frozenset(fired))


# 登记时刻：北京时间 2026-09-02 20:00（收盘后）→ D0 = 2026-09-02
TS = "2026-09-02T12:00:00+00:00"
ENT = {"人形机器人": ["886069.TI", "990049.FP"]}


def _codes(flags: list[BiasFlag]) -> list[str]:
    return [f.code for f in flags]


# --------------------------------------------------------------------------- #
# 时间 / 日历
# --------------------------------------------------------------------------- #
def test_resolve_d0_confirmation_day_semantics():
    after_close = cb.parse_ts("2026-09-02T16:00:00+08:00")
    before_close = cb.parse_ts("2026-09-02T10:00:00+08:00")
    weekend = cb.parse_ts("2026-09-05T16:00:00+08:00")  # 周六
    assert cb.resolve_d0(after_close, CAL) == ("2026-09-02", "after_close→same_day")
    assert cb.resolve_d0(before_close, CAL) == ("2026-09-01", "before_close→previous_day")
    assert cb.resolve_d0(weekend, CAL)[0] == "2026-09-04"
    # 无时区按 UTC：12:00Z = 20:00 北京 → 收盘后
    assert cb.resolve_d0(cb.parse_ts("2026-09-02T12:00:00"), CAL)[0] == "2026-09-02"
    assert cb.resolve_d0(cb.parse_ts("2026-01-01T16:00:00+08:00"), CAL) == (None, "after_close→same_day")  # 早于日历起点


def test_days_between_trading_vs_natural():
    assert cb.days_between(CAL, "2026-08-28", "2026-09-02") == (3, cb.CALENDAR_TRADING)  # 08-31, 09-01, 09-02
    assert cb.days_between(None, "2026-08-28", "2026-09-02") == (5, cb.CALENDAR_NATURAL)
    assert cb.days_between(CAL, "2026-09-02", "2026-09-02") == (0, cb.CALENDAR_TRADING)


def test_parse_ts_handles_z_and_garbage():
    assert cb.parse_ts("2026-09-02T12:00:00Z").isoformat() == "2026-09-02T12:00:00+00:00"
    assert cb.parse_ts("") is None
    assert cb.parse_ts("not a date") is None


# --------------------------------------------------------------------------- #
# late_streak
# --------------------------------------------------------------------------- #
def _late(checkpoint, table, mapping=ENT, calendar=CAL):
    return cb.check_late_streak(
        checkpoint,
        label_lookup=make_label_lookup(table),
        entity_lookup=make_entity_lookup(mapping),
        calendar=calendar,
    )


def test_late_streak_positive_dual_red_streak():
    table = {("sector", "990049.FP", "dual_red_streak", "2026-09-02"): 4.0}
    flag = _late(ck("a", TS, themes=["人形机器人"]), table)
    assert flag is not None and flag.code == "late_streak" and flag.severity == "warn"
    assert flag.evidence["d0"] == "2026-09-02"
    assert flag.evidence["dual_red_streak"] == {"990049.FP": 4.0}


def test_late_streak_positive_heat_rank_three_days():
    table = {("theme", "886069.TI", "limit_heat_rank", d): 2.0 for d in ("2026-08-31", "2026-09-01", "2026-09-02")}
    flag = _late(ck("a", TS, themes=["人形机器人"]), table)
    assert flag is not None and flag.code == "late_streak"
    assert "热度前 3" in flag.reason
    assert flag.evidence["heat_days"] == ["2026-08-31", "2026-09-01", "2026-09-02"]


def test_late_streak_negative_below_thresholds():
    table = {
        ("sector", "990049.FP", "dual_red_streak", "2026-09-02"): 3.0,
        ("theme", "990049.FP", "limit_heat_rank", "2026-09-02"): 1.0,  # 只有一天前三
        ("theme", "990049.FP", "limit_heat_rank", "2026-09-01"): 8.0,
    }
    assert _late(ck("a", TS, themes=["人形机器人"]), table) is None


def test_late_streak_d0_uses_previous_day_before_close():
    # 盘中登记（北京 10:00）→ D0 = 09-01；09-02 的 4 连板不能被看到
    table = {
        ("sector", "990049.FP", "dual_red_streak", "2026-09-02"): 4.0,
        ("sector", "990049.FP", "dual_red_streak", "2026-09-01"): 3.0,
    }
    assert _late(ck("a", "2026-09-02T10:00:00+08:00", themes=["人形机器人"]), table) is None
    flag = _late(ck("a", "2026-09-02T16:00:00+08:00", themes=["人形机器人"]), table)
    assert flag is not None and flag.evidence["d0"] == "2026-09-02"


def test_late_streak_unverifiable_variants():
    table = {("sector", "990049.FP", "dual_red_streak", "2026-09-02"): 4.0}
    no_theme = _late(ck("a", TS, themes=[]), table)
    assert no_theme.code == "late_streak_unverifiable" and "themes" in no_theme.evidence["missing"]
    unmapped = _late(ck("a", TS, themes=["CPO"]), table)
    assert unmapped.code == "late_streak_unverifiable" and "CPO" in unmapped.evidence["missing"]
    no_cal = _late(ck("a", TS, themes=["人形机器人"]), table, calendar=None)
    assert no_cal.code == "late_streak_unverifiable" and "history_calendar" in no_cal.evidence["missing"]
    no_rows = _late(ck("a", TS, themes=["人形机器人"]), {})
    assert no_rows.code == "late_streak_unverifiable" and "标签行" in no_rows.evidence["missing"]
    null_rows = _late(ck("a", TS, themes=["人形机器人"]), {("sector", "990049.FP", "dual_red_streak", "2026-09-02"): None})
    assert null_rows.code == "late_streak_unverifiable"
    src_down = _late(ck("a", TS, themes=["人形机器人"]), table, mapping=None)
    assert src_down.code == "late_streak_unverifiable" and "主库不可用" in src_down.evidence["missing"]
    no_lookup = cb.check_late_streak(ck("a", TS, themes=["人形机器人"]), label_lookup=None,
                                     entity_lookup=make_entity_lookup(ENT), calendar=CAL)
    assert no_lookup.code == "late_streak_unverifiable" and "history_labels" in no_lookup.evidence["missing"]
    for f in (no_theme, unmapped, no_cal, no_rows, null_rows, src_down, no_lookup):
        assert f.severity == "info" and f.unverifiable and f.base_code == "late_streak"


# --------------------------------------------------------------------------- #
# post_miss_streak
# --------------------------------------------------------------------------- #
def _post(checkpoint, checkpoints, verdicts, calendar=CAL):
    return cb.check_post_miss_streak(checkpoint, checkpoints=checkpoints, verdicts=verdicts, calendar=calendar)


def _two_prior_misses(category="生命周期推演"):
    cks = [
        ck("p1", "2026-08-20T12:00:00+00:00", category=category, themes=["A"]),
        ck("p2", "2026-08-24T12:00:00+00:00", category=category, themes=["B"]),
    ]
    vds = [vd("p1", "miss", "2026-08-27T12:00:00+00:00"), vd("p2", "miss", "2026-08-31T12:00:00+00:00")]
    return cks, vds


def test_post_miss_streak_positive_two_misses_within_three_trading_days():
    cks, vds = _two_prior_misses()
    me = ck("me", TS, themes=["C"])
    flag = _post(me, cks + [me], vds)
    assert flag is not None and flag.code == "post_miss_streak" and flag.severity == "warn"
    assert flag.evidence["miss_streak"] == 2
    assert flag.evidence["gap_days"] == 2  # 08-31 → 09-02：09-01, 09-02
    assert flag.evidence["calendar"] == cb.CALENDAR_TRADING


def test_post_miss_streak_negative_last_verdict_hit():
    cks, vds = _two_prior_misses()
    vds[-1] = vd("p2", "hit", "2026-08-31T12:00:00+00:00")
    assert _post(ck("me", TS, themes=["C"]), cks, vds) is None


def test_post_miss_streak_negative_only_one_miss():
    cks, vds = _two_prior_misses()
    assert _post(ck("me", TS, themes=["C"]), cks[:1], vds[:1]) is None


def test_post_miss_streak_negative_too_long_ago():
    cks, vds = _two_prior_misses()
    late_ts = "2026-09-04T12:00:00+00:00"  # 08-31 → 09-04 = 4 个交易日 > 3
    assert _post(ck("me", late_ts, themes=["C"]), cks, vds) is None


def test_post_miss_streak_ignores_verdicts_after_registration():
    """过程条件只能用登记当时已知的结果：ts 之后才出的 miss 不算。"""
    cks, vds = _two_prior_misses()
    vds[-1] = vd("p2", "miss", "2026-09-03T12:00:00+00:00")  # 在 TS 之后
    assert _post(ck("me", TS, themes=["C"]), cks, vds) is None


def test_post_miss_streak_other_category_does_not_count():
    cks, vds = _two_prior_misses(category="估值切换")
    assert _post(ck("me", TS, themes=["C"]), cks, vds) is None


def test_post_miss_streak_natural_days_without_calendar():
    cks, vds = _two_prior_misses()
    flag = _post(ck("me", TS, themes=["C"]), cks, vds, calendar=None)
    assert flag is not None and flag.evidence["calendar"] == cb.CALENDAR_NATURAL
    assert flag.evidence["gap_days"] == 2  # 08-31 → 09-02 自然日
    assert "自然日" in flag.reason


def test_post_miss_streak_unverifiable_without_category():
    cks, vds = _two_prior_misses()
    flag = _post(ck("me", TS, category=None, themes=["C"]), cks, vds)
    assert flag.code == "post_miss_streak_unverifiable" and "category" in flag.evidence["missing"]


# --------------------------------------------------------------------------- #
# revenge_reentry
# --------------------------------------------------------------------------- #
def _revenge(checkpoint, checkpoints, verdicts, calendar=CAL):
    return cb.check_revenge_reentry(checkpoint, checkpoints=checkpoints, verdicts=verdicts, calendar=calendar)


def test_revenge_reentry_positive_shared_theme_recent_miss():
    prev = ck("prev", "2026-08-20T12:00:00+00:00", themes=["算力租赁"])
    vds = [vd("prev", "miss", "2026-08-27T12:00:00+00:00")]  # 08-27 → 09-02 = 4 个交易日
    me = ck("me", TS, themes=["算力租赁", "CPO"])
    flag = _revenge(me, [prev, me], vds)
    assert flag is not None and flag.code == "revenge_reentry" and flag.severity == "warn"
    assert flag.evidence["previous_id"] == "prev"
    assert flag.evidence["shared_terms"] == ["算力租赁"]
    assert flag.evidence["gap_days"] == 4


def test_revenge_reentry_matches_stocks_too_and_normalizes():
    prev = ck("prev", "2026-08-20T12:00:00+00:00", themes=[], stocks=["黄河旋风"])
    vds = [vd("prev", "miss", "2026-09-01T12:00:00+00:00")]
    flag = _revenge(ck("me", TS, themes=[], stocks=["黄河 旋风"]), [prev], vds)
    assert flag is not None and flag.evidence["shared_terms"] == ["黄河旋风"]


def test_revenge_reentry_negative_previous_hit():
    prev = ck("prev", "2026-08-20T12:00:00+00:00", themes=["算力租赁"])
    assert _revenge(ck("me", TS, themes=["算力租赁"]), [prev], [vd("prev", "hit", "2026-09-01T12:00:00+00:00")]) is None


def test_revenge_reentry_negative_too_long_ago():
    prev = ck("prev", "2026-08-10T12:00:00+00:00", themes=["算力租赁"])
    vds = [vd("prev", "miss", "2026-08-25T12:00:00+00:00")]  # 08-25 → 09-02 = 6 个交易日 > 5
    assert _revenge(ck("me", TS, themes=["算力租赁"]), [prev], vds) is None


def test_revenge_reentry_negative_no_shared_terms_or_pending():
    prev = ck("prev", "2026-08-20T12:00:00+00:00", themes=["创新药"])
    assert _revenge(ck("me", TS, themes=["算力租赁"]), [prev], [vd("prev", "miss", "2026-09-01T12:00:00+00:00")]) is None
    same = ck("prev2", "2026-08-20T12:00:00+00:00", themes=["算力租赁"])
    assert _revenge(ck("me", TS, themes=["算力租赁"]), [same], []) is None  # 上一条还没终态


def test_revenge_reentry_only_looks_backwards():
    later = ck("later", "2026-09-03T12:00:00+00:00", themes=["算力租赁"])
    vds = [vd("later", "miss", "2026-09-04T12:00:00+00:00")]
    assert _revenge(ck("me", TS, themes=["算力租赁"]), [later], vds) is None


def test_revenge_reentry_natural_days_and_unverifiable():
    prev = ck("prev", "2026-08-20T12:00:00+00:00", themes=["算力租赁"])
    vds = [vd("prev", "miss", "2026-08-29T12:00:00+00:00")]  # 周六判的
    flag = _revenge(ck("me", TS, themes=["算力租赁"]), [prev], vds, calendar=None)
    assert flag is not None and flag.evidence["calendar"] == cb.CALENDAR_NATURAL and flag.evidence["gap_days"] == 4
    unv = _revenge(ck("me", TS, themes=[], stocks=[]), [prev], vds)
    assert unv.code == "revenge_reentry_unverifiable" and "themes / stocks" in unv.evidence["missing"]


# --------------------------------------------------------------------------- #
# rule_not_firing
# --------------------------------------------------------------------------- #
def _rnf(checkpoint, fire_lookup, mapping=ENT, calendar=CAL):
    return cb.check_rule_not_firing(
        checkpoint, rule_fire_lookup=fire_lookup, entity_lookup=make_entity_lookup(mapping), calendar=calendar
    )


def test_rule_not_firing_not_applicable_without_rule_id():
    """无 rule_id → 不产任何 flag（不适用 ≠ unverifiable）。"""
    me = ck("me", TS, themes=["人形机器人"])
    assert _rnf(me, make_rule_fire_lookup(set())) is None
    flags = cb.scan(me, checkpoints=[me], verdicts=[], label_lookup=make_label_lookup({}),
                    rule_fire_lookup=make_rule_fire_lookup(set()), entity_lookup=make_entity_lookup(ENT), calendar=CAL)
    assert not any(f.base_code == "rule_not_firing" for f in flags)
    assert cb.classify(me, flags)["rule_not_firing"] == "not_applicable"


def test_rule_not_firing_positive_when_entity_absent_from_event_set():
    me = ck("me", TS, themes=["人形机器人"], rule_id="r1")
    flag = _rnf(me, make_rule_fire_lookup({"886050.TI", "990306.FP"}))
    assert flag is not None and flag.code == "rule_not_firing" and flag.severity == "warn"
    assert flag.evidence["fired_here"] == [] and flag.evidence["fired_count"] == 2
    assert flag.evidence["d0"] == "2026-09-02" and flag.evidence["rule_ref"] == "r1@v1"


def test_rule_not_firing_negative_when_any_mapped_code_fired():
    me = ck("me", TS, themes=["人形机器人"], rule_id="r1")
    assert _rnf(me, make_rule_fire_lookup({"990049.FP"})) is None


def test_rule_not_firing_unverifiable_variants():
    me = ck("me", TS, themes=["人形机器人"], rule_id="r1")
    no_cal = _rnf(me, make_rule_fire_lookup(set()), calendar=None)
    assert no_cal.code == "rule_not_firing_unverifiable" and "history_calendar" in no_cal.evidence["missing"]
    no_lookup = _rnf(me, None)
    assert no_lookup.code == "rule_not_firing_unverifiable" and "rule_fire_lookup" in no_lookup.evidence["missing"]
    none_fire = _rnf(me, lambda rid, d0: None)
    assert none_fire.code == "rule_not_firing_unverifiable" and "事件集" in none_fire.evidence["missing"]
    stock_rule = _rnf(ck("me", TS, themes=[], stocks=["黄河旋风"], rule_id="r1"),
                      make_rule_fire_lookup({"600172.SH"}, entity_type="stock"))
    assert stock_rule.code == "rule_not_firing_unverifiable" and "stock_ts_code" in stock_rule.evidence["missing"]
    unmapped = _rnf(ck("me", TS, themes=["CPO"], rule_id="r1"), make_rule_fire_lookup({"x"}))
    assert unmapped.code == "rule_not_firing_unverifiable" and "CPO" in unmapped.evidence["missing"]
    no_theme = _rnf(ck("me", TS, themes=[], rule_id="r1"), make_rule_fire_lookup({"x"}))
    assert no_theme.code == "rule_not_firing_unverifiable" and "themes" in no_theme.evidence["missing"]


def test_scan_turns_lookup_unavailable_and_exceptions_into_unverifiable():
    me = ck("me", TS, themes=["人形机器人"], rule_id="r1")

    def missing_rule(rid, d0):
        raise cb.LookupUnavailable(f"规则文件 {rid}.v*.json（不存在）")

    def boom(*a, **k):
        raise RuntimeError("database is locked")

    flags = cb.scan(me, checkpoints=[me], verdicts=[], label_lookup=boom, rule_fire_lookup=missing_rule,
                    entity_lookup=make_entity_lookup(ENT), calendar=CAL)
    by = {f.code: f for f in flags}
    assert "规则文件" in by["rule_not_firing_unverifiable"].evidence["missing"]
    assert "RuntimeError" in by["late_streak_unverifiable"].evidence["missing"]
    assert all(f.severity == "info" for f in flags)


# --------------------------------------------------------------------------- #
# rule_not_firing 走真编译器：最小旁路库夹具（照 methodology_backtest_selftest 的零凭证形状，只建旁路库表）
# --------------------------------------------------------------------------- #
RULE_DOC = {
    "rule_id": "mini_dual_red",
    "version": 1,
    "title": "最小夹具：严格双红且连板 >= 3",
    "scope": {"entity_type": "sector", "universe": "published_snapshot"},
    "condition": {"all": [
        {"label": "dual_red_strict", "op": "==", "value": True, "lag": 0},
        {"label": "dual_red_streak", "op": ">=", "value": 3, "lag": 0},
    ]},
    "outcome": {
        "target": "pct_chg",
        "horizons": [3, 5],
        "metrics": ["fwd_return", "max_return", "days_to_peak", "drawdown_after_peak"],
        "success": {"metric": "fwd_return", "horizon": 5, "op": ">", "value": 0},
    },
    "baseline": {"kind": "same_universe_all_days"},
    "min_n": 20,
}


@pytest.fixture(scope="module")
def mini_sources(tmp_path_factory):
    from intelligence.services.methodology_backtest.store import open_labels_db

    root = tmp_path_factory.mktemp("bias-mini")
    labels_db = root / "history_labels.duckdb"
    rules_dir = root / "rules"
    rules_dir.mkdir()
    (rules_dir / "mini_dual_red.v1.json").write_text(json.dumps(RULE_DOC, ensure_ascii=False), encoding="utf-8")
    con = open_labels_db(labels_db, read_only=False)
    try:
        for i, d in enumerate(CAL):
            con.execute("INSERT INTO history_calendar VALUES (?, ?)", [i, d])
        rows = []
        for d in CAL:
            fires = d == "2026-09-02"
            # S_FIRE 在 09-02 满足两条谓词；S_QUIET 双红但只连 2 天；S_NONE 不双红
            rows += [
                ("sector", "S_FIRE.FP", d, "dual_red_strict", 1.0 if fires else 0.0),
                ("sector", "S_FIRE.FP", d, "dual_red_streak", 3.0 if fires else 0.0),
                ("sector", "S_QUIET.FP", d, "dual_red_strict", 1.0 if fires else 0.0),
                ("sector", "S_QUIET.FP", d, "dual_red_streak", 2.0 if fires else 0.0),
                ("sector", "S_NONE.FP", d, "dual_red_strict", 0.0),
                ("sector", "S_NONE.FP", d, "dual_red_streak", 0.0),
            ]
        con.executemany(
            "INSERT INTO history_labels (entity_type, entity_id, trade_date, label, value_num, value_text, label_version, computed_at) "
            "VALUES (?, ?, ?, ?, ?, NULL, 'vtest', TIMESTAMP '2026-09-04 00:00:00')",
            rows,
        )
        con.execute(
            "INSERT INTO history_build_meta (build_kind, label_version, source_db, source_max_trade_date, source_row_counts, row_count, horizons, computed_at) "
            "VALUES ('labels', 'vtest', 'mini', DATE '2026-09-04', '{}', ?, NULL, TIMESTAMP '2026-09-04 00:00:00')",
            [len(rows)],
        )
    finally:
        con.close()
    src = cb.LedgerDataSources(labels_db=labels_db, market_db=root / "no-main.duckdb", rules_dir=rules_dir)
    yield src
    src.close()


def test_ledger_sources_report_availability(mini_sources):
    avail = mini_sources.availability()
    assert avail["labels_db_ok"] and avail["calendar_days"] == len(CAL) and avail["calendar_end"] == "2026-09-04"
    assert avail["label_version"] == "vtest"
    assert not avail["market_db_ok"] and mini_sources.entity_lookup is None  # 主库缺 → 映射 unverifiable
    assert any("主库不存在" in n for n in avail["notes"])
    assert mini_sources.label_lookup is not None and mini_sources.rule_fire_lookup is not None


def test_rule_fire_lookup_compiles_rule_and_returns_full_event_set(mini_sources):
    fire = mini_sources.rule_fire_lookup("mini_dual_red", "2026-09-02")
    assert fire.rule_ref == "mini_dual_red@v1" and fire.entity_type == "sector"
    assert fire.fired == frozenset({"S_FIRE.FP"})
    assert fire.label_version == "vtest"
    assert mini_sources.rule_fire_lookup("mini_dual_red", "2026-09-01").fired == frozenset()
    with pytest.raises(cb.LookupUnavailable):
        mini_sources.rule_fire_lookup("no_such_rule", "2026-09-02")


def test_rule_not_firing_real_compiler_on_mini_labels_db(mini_sources):
    mapping = make_entity_lookup({"触发板块": ["S_FIRE.FP"], "安静板块": ["S_QUIET.FP"], "无关板块": ["S_NONE.FP"]})
    quiet = ck("q", TS, themes=["安静板块"], rule_id="mini_dual_red")
    flag = cb.check_rule_not_firing(quiet, rule_fire_lookup=mini_sources.rule_fire_lookup,
                                    entity_lookup=mapping, calendar=mini_sources.calendar)
    assert flag is not None and flag.code == "rule_not_firing"
    assert flag.evidence["fired_count"] == 1 and flag.evidence["label_version"] == "vtest"
    fired = ck("f", TS, themes=["触发板块", "无关板块"], rule_id="mini_dual_red")
    assert cb.check_rule_not_firing(fired, rule_fire_lookup=mini_sources.rule_fire_lookup,
                                    entity_lookup=mapping, calendar=mini_sources.calendar) is None


def test_label_lookup_reads_rows_by_entity_and_date(mini_sources):
    got = mini_sources.label_lookup("sector", ["S_FIRE.FP", "S_QUIET.FP"], "dual_red_streak", ["2026-09-01", "2026-09-02"])
    assert got[("S_FIRE.FP", "2026-09-02")] == 3.0 and got[("S_QUIET.FP", "2026-09-02")] == 2.0
    assert got[("S_FIRE.FP", "2026-09-01")] == 0.0
    assert mini_sources.label_lookup("sector", [], "dual_red_streak", ["2026-09-02"]) == {}


def test_ledger_sources_degrade_when_everything_missing(tmp_path: Path):
    src = cb.LedgerDataSources(labels_db=tmp_path / "x.duckdb", market_db=tmp_path / "y.duckdb", rules_dir=tmp_path / "rules")
    assert src.calendar is None and src.label_lookup is None and src.entity_lookup is None and src.rule_fire_lookup is None
    assert len(src.notes) == 3
    me = ck("me", TS, themes=["人形机器人"], rule_id="r1")
    flags = cb.scan(me, checkpoints=[me], verdicts=[], label_lookup=src.label_lookup,
                    rule_fire_lookup=src.rule_fire_lookup, entity_lookup=src.entity_lookup, calendar=src.calendar)
    codes = set(_codes(flags))
    assert {"late_streak_unverifiable", "rule_not_firing_unverifiable"} <= codes
    assert "post_miss_streak" not in codes and "revenge_reentry" not in codes  # 只用台账的两条：自然日照算、这里无历史 → 干净
    src.close()


# --------------------------------------------------------------------------- #
# scan / classify / summarize / render
# --------------------------------------------------------------------------- #
def test_scan_collects_all_four_and_classify_summarize_count():
    prev = ck("prev", "2026-08-20T12:00:00+00:00", themes=["人形机器人"])
    p1 = ck("p1", "2026-08-24T12:00:00+00:00", themes=["A"])
    vds = [vd("prev", "miss", "2026-09-01T12:00:00+00:00"), vd("p1", "miss", "2026-08-31T12:00:00+00:00")]
    me = ck("me", TS, themes=["人形机器人"], rule_id="r1")
    table = {("sector", "990049.FP", "dual_red_streak", "2026-09-02"): 5.0}
    flags = cb.scan(me, checkpoints=[prev, p1, me], verdicts=vds, label_lookup=make_label_lookup(table),
                    rule_fire_lookup=make_rule_fire_lookup(set()), entity_lookup=make_entity_lookup(ENT), calendar=CAL)
    assert _codes(flags) == ["late_streak", "post_miss_streak", "rule_not_firing", "revenge_reentry"]
    assert cb.classify(me, flags) == {c: "flagged" for c in cb.BIAS_CODES}
    clean = ck("clean", TS, category="别的类", themes=["人形机器人"])
    clean_flags = cb.scan(clean, checkpoints=[prev, p1, clean], verdicts=[], label_lookup=make_label_lookup({}),
                          rule_fire_lookup=make_rule_fire_lookup(set()), entity_lookup=make_entity_lookup(ENT), calendar=CAL)
    assert cb.classify(clean, clean_flags) == {
        "late_streak": "unverifiable", "post_miss_streak": "clean", "rule_not_firing": "not_applicable", "revenge_reentry": "clean",
    }
    summary = cb.summarize([(me, flags), (clean, clean_flags)])
    assert summary["scanned"] == 2
    assert summary["by_code"]["late_streak"] == {
        "flagged": 1, "unverifiable": 1, "clean": 0, "not_applicable": 0, "flagged_ids": ["me"],
        "unverifiable_reasons": {clean_flags[0].evidence["missing"]: 1},
    }
    assert summary["by_code"]["rule_not_firing"]["not_applicable"] == 1
    lines = cb.render_flag_lines(flags + clean_flags)
    assert lines[0].startswith("⚠ late_streak：") and lines[-1].startswith("· late_streak_unverifiable：")
    assert flags[0].to_dict()["evidence"]["d0"] == "2026-09-02"


def test_latest_rule_file_picks_highest_version(tmp_path: Path):
    (tmp_path / "r1.v1.json").write_text("{}", encoding="utf-8")
    (tmp_path / "r1.v3.json").write_text("{}", encoding="utf-8")
    (tmp_path / "r1.v2.json").write_text("{}", encoding="utf-8")
    (tmp_path / "r10.v9.json").write_text("{}", encoding="utf-8")
    assert cb.latest_rule_file(tmp_path, "r1").name == "r1.v3.json"
    assert cb.latest_rule_file(tmp_path, "r2") is None
    assert cb.latest_rule_file(tmp_path / "missing", "r1") is None
