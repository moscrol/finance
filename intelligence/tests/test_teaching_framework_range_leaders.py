"""区间涨幅高标链（创始人 09-07 第九、十段）：前 N 组、消亡 / 诞生按名次配对成衔接、形式分布。"""

from datetime import date

from intelligence.services.teaching_framework.range_leaders import build_range_leaders, cross_chain, handoff_readouts

DAYS = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]


def _row(day, rank, code, gain, l1, limit_times=None, window=20):
    return {"window_days": window, "trade_date": day, "rank": rank, "stock_ts_code": code, "stock_name": code.lower(),
            "gain_pct": gain, "sw_l1": l1, "limit_times": limit_times}


def _day(day, ordered):
    """ordered = [(code, gain, l1, limit_times), ...] best first; ranks 1..len."""
    return [_row(day, i + 1, code, gain, l1, lt) for i, (code, gain, l1, lt) in enumerate(ordered)]


def test_group_handoffs_pair_exits_and_births_in_rank_order_and_describe_the_relation():
    rows = []
    # Day 1: top-2 = {A, B}; context (rank 3) = C.
    rows += _day(DAYS[0], [("A", 40.0, "电子", 4), ("B", 30.0, "通信", None), ("C", 20.0, "电子", None)])
    # Day 2: C climbs in from the context (递进, same L1 as the exiting A), A drops to rank 3 (滑落).
    rows += _day(DAYS[1], [("B", 32.0, "通信", None), ("C", 31.0, "电子", 3), ("A", 25.0, "电子", 2)])
    # Day 3: D bursts in from outside the context (突入, 跨L1 against the exiting B); B falls out of the context entirely.
    rows += _day(DAYS[2], [("D", 50.0, "医药生物", None), ("C", 33.0, "电子", 3), ("E", 10.0, "汽车", None)])
    # Day 4 has no ranked rows at all (source gap for this window).
    out = build_range_leaders(rows, calendar=DAYS, windows=[20], top=2, context=3)
    leaders = [(r["trade_date"], r["rank"], r["stock_ts_code"], r["tenure_day"], r["prev_rank"]) for r in out["leaders"]]
    assert leaders == [
        (date(2026, 1, 5), 1, "A", 1, None), (date(2026, 1, 5), 2, "B", 1, None),
        (date(2026, 1, 6), 1, "B", 2, 2), (date(2026, 1, 6), 2, "C", 1, 3),
        (date(2026, 1, 7), 1, "D", 1, None), (date(2026, 1, 7), 2, "C", 2, 2),
    ]
    h1, h2 = out["handoffs"]
    assert (h1["trade_date"], h1["birth_stock"], h1["exit_stock"]) == (date(2026, 1, 6), "C", "A")
    assert h1["birth_prev_rank"] == 3 and h1["exit_next_rank"] == 3 and h1["exit_tenure_days"] == 1
    assert h1["same_l1"] is True and h1["form"] == "同L1·递进" and h1["birth_limit_times"] == 3 and h1["exit_limit_times"] == 4
    assert (h2["trade_date"], h2["birth_stock"], h2["exit_stock"]) == (date(2026, 1, 7), "D", "B")
    assert h2["birth_prev_rank"] is None and h2["exit_next_rank"] is None and h2["exit_tenure_days"] == 2
    assert h2["same_l1"] is False and h2["form"] == "跨L1·突入"
    days = out["days"][20]
    assert [d["status"] for d in days] == ["ok", "ok", "ok", "no_ranked_rows"]
    assert days[1]["births"] == 1 and days[1]["entry_gain_pct"] == 31.0 and days[1]["top_gain_pct"] == 32.0 and days[1]["limit_leaders"] == 1
    assert days[2]["l1_distinct"] == 2 and days[2]["forms"] == {"跨L1·突入": 1}
    # Gap day resets tenure: nothing carries over an unknown day.
    readout = handoff_readouts(out)["20"]
    assert readout["handoffs"] == 2 and readout["days_ok"] == 3 and readout["days_gap"] == 1
    assert readout["forms"]["同L1·递进"] == 1 and readout["forms"]["跨L1·突入"] == 1 and readout["form_shares"]["同L1·递进"] == 0.5
    assert readout["birth_is_limit_leader_share"] == 0.5 and readout["exit_was_limit_leader_share"] == 0.5
    assert readout["exit_fell_out_of_context_share"] == 0.5 and readout["exit_tenure_days_median"] == 1.5
    assert readout["entry_gain_pct_quartiles"]["n"] == 3


def test_unknown_l1_and_unequal_counts_are_reported_not_guessed():
    rows = _day(DAYS[0], [("A", 40.0, None, None), ("B", 30.0, "通信", None)])
    # Day 2 has only one ranked stock (the rest failed the window): one exit is left unpaired.
    rows += _day(DAYS[1], [("C", 35.0, "电子", None)])
    out = build_range_leaders(rows, calendar=DAYS[:2], windows=[20], top=2, context=2)
    (h,) = out["handoffs"]
    assert h["birth_stock"] == "C" and h["exit_stock"] == "A" and h["same_l1"] is None and h["form"] == "L1未知"
    assert out["days"][20][1]["unpaired_exits"] == 1 and out["days"][20][1]["members"] == 1


def test_readouts_by_reference_stage_and_cross_chain_membership():
    rows = _day(DAYS[0], [("A", 40.0, "电子", 4), ("B", 30.0, "通信", None)]) + _day(DAYS[1], [("B", 32.0, "通信", None), ("C", 31.0, "电子", 3)])
    out = build_range_leaders(rows, calendar=DAYS[:2], windows=[20], top=2, context=2)
    reference = {DAYS[0]: {"cycle_stage": "主流主升"}, DAYS[1]: {"cycle_stage": "承接盘反复"}}
    readout = handoff_readouts(out, reference)["20"]
    assert readout["by_reference_stage"]["承接盘反复"]["births_per_day_mean"] == 1.0
    assert readout["form_shares_by_reference_stage"] == {"承接盘反复": {"同L1·递进": 0.0, "同L1·突入": 1.0, "跨L1·递进": 0.0, "跨L1·突入": 0.0, "L1未知": 0.0}}
    # 连板 chain node: A broke on day 1 (a range leader that day), successor group {C, Z} born on day 2 (C is a range leader).
    nodes = [{"break_day": DAYS[0], "birth_day": DAYS[1], "leader_i": "A", "leader_i_group_json": '["A"]', "leader_next": "C", "leader_next_group_json": '["C", "Z"]'}]
    cross = cross_chain(out, nodes)
    assert cross["succession_nodes"] == 1
    assert cross["leader_i_in_range_top_on_break_day"] == {"20": 1} and cross["leader_next_in_range_top_on_birth_day"] == {"20": 1}
