from __future__ import annotations

from intelligence.services.teaching_framework.sector_roles import (
    MONEY_EFFECT_DEFINITIONS,
    SECTOR_LABELS,
    build_sector_roles,
    money_effect_rule_rows,
)

DAYS = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12"]


def _sector(day: str, code: str, sw_l1: str | None, pct: float, amount: float = 300.0, diff: float = 5.0) -> dict:
    return {"trade_date": day, "sector_ts_code": code, "sector_name": code, "sw_l1": sw_l1, "pct_chg": pct, "amount": amount, "diff_ratio": diff}


def _heat(day: str, code: str, count: int, fd: float = 1000.0) -> dict:
    return {"trade_date": day, "sector_ts_code": code, "limit_up_count": count, "fd_amount": fd}


def _market(day: str, *top3: str | None) -> dict:
    return {"trade_date": day, "industry_1": top3[0], "industry_2": top3[1], "industry_3": top3[2]}


def test_rps_ranks_need_contiguous_complete_windows():
    # Three sectors; C is missing on 01-07, so its 3-day rank is NULL on 01-07..01-09 and back on 01-12.
    rows = []
    for i, d in enumerate(DAYS):
        rows.append(_sector(d, "A", "电子", 2.0))
        rows.append(_sector(d, "B", "通信", 1.0))
        if d != "2026-01-07":
            rows.append(_sector(d, "C", None, 3.0))
    out = build_sector_roles(rows, [], [_market(d, "电子", "机械设备", "电力设备") for d in DAYS], calendar=DAYS)
    by = {(str(r["trade_date"]), r["sector_ts_code"]): r for r in out["sectors"]}
    assert by[("2026-01-05", "A")]["rps_3d_rank"] is None  # first day: no 3-day window yet
    assert (by[("2026-01-07", "A")]["rps_3d_rank"], by[("2026-01-07", "B")]["rps_3d_rank"]) == (1, 2)  # C absent → ranked among A, B
    assert by[("2026-01-09", "C")]["rps_3d_rank"] is None  # window 01-07..01-09 has a hole for C
    assert by[("2026-01-12", "C")]["rps_3d_rank"] == 1  # 01-08..01-12 complete again: C's 3% a day is strongest
    assert by[("2026-01-12", "A")]["rps_5d_rank"] == 1 and by[("2026-01-12", "C")]["rps_5d_rank"] is None
    # sw_l1 unknown → 量板块 role unknown, hence 价板块 unknown too.
    assert by[("2026-01-12", "C")]["role_volume_top3"] is None and by[("2026-01-12", "C")]["role_price_top10"] is None
    assert by[("2026-01-12", "A")]["role_volume_top3"] is True and by[("2026-01-12", "A")]["role_price_top10"] is False
    assert by[("2026-01-12", "B")]["role_volume_top3"] is False and by[("2026-01-12", "B")]["role_price_top10"] is True


def test_limit_ranks_dual_red_and_money_effect_sets():
    day = DAYS[0]
    rows = [
        _sector(day, "A", "电子", 1.0, amount=800.0, diff=12.0),   # 双红
        _sector(day, "B", "通信", 0.5, amount=800.0, diff=12.0),   # 双红
        _sector(day, "C", "医药生物", -0.2, amount=900.0, diff=15.0),  # not 双红: pct ≤ 0
        _sector(day, "D", None, 2.0, amount=100.0, diff=1.0),
    ]
    heat = [_heat(day, "A", 5, 900.0), _heat(day, "B", 5, 1200.0), _heat(day, "C", 2)]
    out = build_sector_roles(rows, heat, [_market(day, "电子", "机械设备", "电力设备")], calendar=[day])
    by = {r["sector_ts_code"]: r for r in out["sectors"]}
    assert (by["B"]["sharpness_limit_rank"], by["A"]["sharpness_limit_rank"], by["C"]["sharpness_limit_rank"]) == (1, 2, 3)  # tie on 5 broken by 封单
    assert by["D"]["sharpness_limit_rank"] is None and by["D"]["limit_up_count"] == 0  # absent from the heat table = no limit-ups that day
    assert [by[c]["dual_red_strict"] for c in "ABCD"] == [True, True, False, False]
    assert by["A"]["money_effect.limit_top10"] is True and by["D"]["money_effect.limit_top10"] is False
    assert by["A"]["money_effect.dual_red"] is True and by["C"]["money_effect.dual_red"] is False
    assert all(by[c]["money_effect.rps5_top10"] is None for c in "ABCD")  # single day: no 5-day window
    assert all(by[c]["money_effect.rank_mean_top10"] is None for c in "ABCD")  # needs all three ranks
    summary = out["days"][0]
    assert summary["status"] == "ok" and summary["top3_l1"] == ["机械设备", "电力设备", "电子"]
    # limit_top10 set = {A, B, C}; sw_l1 known for all three; outside the top three: B (通信), C (医药生物) → 2/3.
    assert summary["limit_top10.size"] == 3 and summary["limit_top10.known_l1"] == 3
    assert abs(summary["limit_top10.outside_top3_share"] - 2 / 3) < 1e-9
    assert summary["dual_red.size"] == 2 and abs(summary["dual_red.outside_top3_share"] - 0.5) < 1e-9
    assert set(SECTOR_LABELS) >= {f"money_effect.{d}" for d in MONEY_EFFECT_DEFINITIONS}


def test_days_without_sector_rows_or_heat_are_reported_not_zeroed():
    rows = [_sector(DAYS[0], "A", "电子", 1.0)]
    out = build_sector_roles(rows, [], [_market(DAYS[0], None, None, None), _market(DAYS[1], "电子", "通信", "银行")], calendar=DAYS[:2])
    first, second = out["days"]
    assert first["status"] == "ok" and first["top3_l1"] is None and first["heat_covered"] is False
    assert first["limit_top10.outside_top3_share"] is None  # no top-three that day → nothing to compare against
    assert second["status"] == "sector_rows_absent"
    rec = out["sectors"][0]
    assert rec["limit_up_count"] is None and rec["sharpness_limit_rank"] is None  # heat table did not cover the day
    assert rec["role_volume_top3"] is None  # top-three unknown


def test_kmeans_hot_cluster_is_deterministic_and_picks_the_strongest_group():
    from intelligence.services.teaching_framework.sector_roles import kmeans_hot_cluster

    table = {}
    # Three obvious groups: hot (H*), middle (M*), cold (C*), each on all five features.
    for i in range(4):
        table[f"H{i}"] = {"pct_chg": 5.0 + i * 0.1, "amount_share_pct": 3.0, "limit_up_count": 6.0, "rps5_gain_pct": 12.0, "diff_ratio": 20.0}
        table[f"M{i}"] = {"pct_chg": 0.5, "amount_share_pct": 1.0, "limit_up_count": 1.0, "rps5_gain_pct": 2.0, "diff_ratio": 3.0}
        table[f"C{i}"] = {"pct_chg": -2.0, "amount_share_pct": 0.3, "limit_up_count": 0.0, "rps5_gain_pct": -4.0, "diff_ratio": -5.0}
    hot = kmeans_hot_cluster(table)
    assert hot == {"H0", "H1", "H2", "H3"}
    assert kmeans_hot_cluster(dict(reversed(list(table.items())))) == hot  # input order does not matter
    assert kmeans_hot_cluster({"A": table["H0"], "B": table["C0"]}) == set()  # fewer rows than k: nothing to cluster


def test_breadth_vendor_sharpness_and_kmeans_labels_and_jaccard():
    days = [f"2026-01-{d:02d}" for d in (5, 6, 7, 8, 9, 12, 13, 14, 15, 16)]
    rows, heat, highs, vendor = [], [], [], []
    for i, d in enumerate(days):
        # A: strong every day, 电子; B: mid, 通信; C: weak, 医药生物.
        rows += [_sector(d, "A", "电子", 3.0, amount=900.0, diff=15.0), _sector(d, "B", "通信", 1.0, amount=400.0, diff=6.0), _sector(d, "C", "医药生物", -1.0, amount=200.0, diff=-2.0)]
        heat += [_heat(d, "A", 6, 5000.0), _heat(d, "B", 1, 500.0)]
        highs += [{"trade_date": d, "sw_l1": "通信"}, {"trade_date": d, "sw_l1": "通信"}, {"trade_date": d, "sw_l1": "电子"}]
        if i < 3:
            vendor.append({"trade_date": d, "sector_ts_code": "B"})
    out = build_sector_roles(rows, heat, [_market(d, "电子", "机械设备", "电力设备") for d in days], calendar=days, high_rows=highs, vendor_rows=vendor)
    by = {(str(r["trade_date"]), r["sector_ts_code"]): r for r in out["sectors"]}
    last = days[-1]
    # 宽度: 通信 has the most 1y+ new highs → only B carries the breadth-top role.
    assert (by[(last, "B")]["role_breadth_top_l1"], by[(last, "A")]["role_breadth_top_l1"]) == (True, False)
    # 主流两口径: vendor table covers the first three days only → NULL afterwards; volume top-3 is 电子.
    assert by[(days[0], "B")]["mainline_vendor"] is True and by[(days[0], "A")]["mainline_vendor"] is False
    assert by[(last, "B")]["mainline_vendor"] is None and by[(last, "A")]["mainline_volume_top3"] is True
    # 锐度合成: A ranks 1 on both components → mean 1.0 → top; C is absent from the heat table → no composite.
    assert by[(last, "A")]["sharpness_rank_mean"] == 1.0 and by[(last, "A")]["role_sharpness_top10"] is True
    assert by[(last, "C")]["sharpness_rank_mean"] is None and by[(last, "C")]["role_sharpness_top10"] is None
    # k-means on a 3-row cross-section: exactly k rows, A alone in the hot cluster.
    assert by[(last, "A")]["money_effect.kmeans_hot"] is True and by[(last, "C")]["money_effect.kmeans_hot"] is False
    summary = out["days"][-1]
    assert summary["breadth_top_l1"] == "通信" and summary["vendor_covered"] is False and summary["price_top10.count"] == 2
    # rps5_top10 set is {A, B, C} on every day with a window (from day 5): Jaccard against five days back is 1.0 once both
    # sides have a set (day 10 vs day 5) and unknown while the earlier side had no window (day 9 vs day 4).
    assert summary["rps5_top10.jaccard_5d"] == 1.0 and out["days"][8]["rps5_top10.jaccard_5d"] is None
    assert summary["rps5_top10.l1_distinct"] == 3


def test_money_effect_rule_rows_split_by_ma_side_and_exclude_unknowns():
    days = [
        {"trade_date": "2026-01-05", "status": "ok", "limit_top10.outside_top3_share": 0.8},
        {"trade_date": "2026-01-06", "status": "ok", "limit_top10.outside_top3_share": 0.2},
        {"trade_date": "2026-01-07", "status": "ok", "limit_top10.outside_top3_share": 0.9},
        {"trade_date": "2026-01-08", "status": "ok", "limit_top10.outside_top3_share": None},
        {"trade_date": "2026-01-09", "status": "sector_rows_absent"},
        {"trade_date": "2026-01-12", "status": "ok", "limit_top10.outside_top3_share": 0.6},
    ]
    context = {"2026-01-05": {"above_week_ma": 0}, "2026-01-06": {"above_week_ma": 0}, "2026-01-07": {"above_week_ma": 1}, "2026-01-08": {"above_week_ma": 0}}
    parts = money_effect_rule_rows(days, context, definition="limit_top10")
    assert parts["below_ma"] == [True, False] and parts["above_ma"] == [True]
    assert parts["excluded"] == {"no_ma_side": 1, "no_top3_or_empty_set": 1}
