"""王朝链（创始人 09-07 第十三段）：按平台阶段切波、每波区间涨幅前 N 是一个王朝、旧王朝覆灭窗里新王朝成员的分离确认。"""

from datetime import date, timedelta

from intelligence.services.teaching_framework.dynasties import build_dynasties, segment_waves

# 16 weekdays; the stage script is: [承接 承接] 左底向下 左底向上 缩量右底 | 共建 共建 主升 承接 2.0 | 左底向下 二次探底 共建 主升 | 承接 承接
CAL = [date(2026, 1, 5) + timedelta(days=i) for i in range(30)]
CAL = [d for d in CAL if d.weekday() < 5][:16]
STAGES = ["承接盘反复", "承接盘反复", "左底向下", "左底向上", "缩量右底", "共建主线", "共建主线", "主流主升", "承接盘反复", "主流主升2.0",
          "左底向下", "二次探底", "共建主线", "主流主升", "承接盘反复", "承接盘反复"]


def test_segment_waves_cuts_peak_blocks_and_collapse_windows():
    waves = segment_waves(zip(CAL, STAGES), CAL)
    assert [w["wave_idx"] for w in waves] == [0, 1, 2]
    w0, w1, w2 = waves
    # The first block starts on the first reference day: no visible start.
    assert w0["status"] == "truncated" and w0["start"] == CAL[0] and w0["peak_end"] == CAL[1] and w0["block"] == ["承接盘反复"]
    assert w0["collapse_start"] == CAL[2] and w0["collapse_end"] == CAL[4] and w0["collapse_days"] == 3 and w0["first_down_end"] == CAL[2]
    assert w0["stages_in_collapse"] == {"左底向下": 1, "左底向上": 1, "缩量右底": 1}
    # Wave 1 starts with the 共建主线 run right before its peak block (主升 → 承接 → 2.0), peaks on the 2.0 day.
    assert w1["status"] == "ok" and w1["start"] == CAL[5] and w1["start_prev"] == CAL[4] and w1["peak_end"] == CAL[9]
    assert w1["block"] == ["主流主升", "承接盘反复", "主流主升2.0"] and w1["block_days"] == 3 and w1["wave_days"] == 5
    assert w1["collapse_start"] == CAL[10] and w1["collapse_end"] == CAL[11] and w1["first_down_end"] == CAL[10]
    # The last wave has nobody after it: open collapse, no end.
    assert w2["status"] == "open" and w2["start"] == CAL[12] and w2["peak_end"] == CAL[15] and w2["collapse_start"] is None and w2["collapse_end"] is None


def _gain(code, gain, l1=None, boards=None, name=None):
    return {"stock_ts_code": code, "stock_name": name or code.lower(), "gain_pct": gain, "sw_l1": l1, "max_boards": boards}


def _stat(code, ret, dd=-5.0, new_high=False, leg=None, losing=None):
    return {"stock_ts_code": code, "ret_pct": ret, "max_dd_pct": dd, "new_high": new_high, "first_leg_ret_pct": leg, "losing_ret_pct": losing}


def test_build_dynasties_ranks_members_describes_handoff_and_flags_separation():
    waves = segment_waves(zip(CAL, STAGES), CAL)
    # Wave 1 (old): A leads as a 连板 leader, B and C trail; D–H fill the universe.  Wave 2 (new): F, G, D on top.
    universe = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
    old_gains = [_gain("A", 180.0, "电子", 5), _gain("B", 120.0, "通信", 2), _gain("C", 90.0, "电子", None)] + [_gain(c, 10.0 - i, "汽车") for i, c in enumerate(universe[3:])]
    new_gains = [_gain("F", 150.0, "电子", 1), _gain("G", 140.0, "医药生物", 4), _gain("D", 130.0, "汽车", None)] + [_gain(c, 5.0 - i, "汽车") for i, c in enumerate(["A", "B", "C", "E", "H", "I", "J"])]
    # Collapse of wave 1: the old leaders crash; F and G hold up (top decile is the single best return out of 10 → F only).
    # On the window's two 亏钱效应日 the picture inverts: F falls with the market (−4), G is the only one to rise (+1).
    collapse = [_stat("A", -40.0, -45.0, False, -30.0, losing=-9.0), _stat("B", -35.0, -40.0, False, -25.0, losing=-8.0), _stat("C", -20.0, losing=-5.0),
                _stat("D", -8.0, losing=-3.0), _stat("E", -9.0, losing=-3.5), _stat("F", 12.0, -3.0, True, 1.0, losing=-4.0), _stat("G", 6.0, -6.0, True, -2.0, losing=1.0),
                _stat("H", -10.0, losing=-2.0), _stat("I", -12.0, losing=-6.0), _stat("J", -15.0, losing=-7.0)]
    money_losing = {1: {"peak_block": {"days": 5, "flagged": 0}, "lead": {"days": 4, "flagged": 1}, "collapse": {"days": 2, "flagged": 2},
                        "collapse_days": [CAL[10], CAL[11]]}}
    out = build_dynasties(
        waves, {1: old_gains, 2: new_gains}, {1: collapse}, top=2, cohort=3, separation_percentile=0.9, index_returns={1: -7.5}, min_n=10,
        money_losing=money_losing,
    )
    members = [(m["wave_idx"], m["rank"], m["stock_ts_code"], m["form"], m["collapse_ret_pct"]) for m in out["members"]]
    # Wave 0 has no gains (truncated), wave 1 writes its top-3 with their own collapse return, wave 2 (open) writes its top-3 without.
    assert members == [(1, 1, "A", "连板", -40.0), (1, 2, "B", "趋势", -35.0), (1, 3, "C", "趋势", -20.0),
                       (2, 1, "F", "趋势", None), (2, 2, "G", "连板", None), (2, 3, "D", "趋势", None)]
    h = {row["stock_ts_code"]: row for row in out["handoffs"]}
    assert [row["new_rank"] for row in out["handoffs"]] == [1, 2, 3] and set(h) == {"F", "G", "D"}
    assert (h["F"]["old_wave_idx"], h["F"]["new_wave_idx"]) == (1, 2)
    # F: best collapse return of 10 → percentile 90 → 相对分离; made a new high → 新高分离; ranked 6th in the old wave, 电子 like old leader A.
    assert h["F"]["collapse_ret_percentile"] == 90.0 and h["F"]["separation_relative"] is True and h["F"]["separation_new_high"] is True
    assert h["F"]["old_wave_rank"] == 6 and h["F"]["in_old_cohort"] is False and h["F"]["l1_in_old_top"] is True and h["F"]["first_leg_ret_pct"] == 1.0
    # G: second best (percentile 80) → not 相对分离 at 0.9, but a new high; 医药生物 is not in the old top-2 L1 set.
    assert h["G"]["separation_relative"] is False and h["G"]["separation_new_high"] is True and h["G"]["l1_in_old_top"] is False
    # D came from the old cohort's outside (rank 4 > cohort 3) and did not separate.
    assert h["D"]["old_wave_rank"] == 4 and h["D"]["in_old_cohort"] is False and h["D"]["separation_relative"] is False
    # 亏钱日上的强弱是第三条、独立的分离读数：G is the best of 10 on the losing days (percentile 90) while F sits mid-pack (50).
    assert h["G"]["losing_days_ret_pct"] == 1.0 and h["G"]["losing_days_ret_percentile"] == 90.0 and h["G"]["separation_on_losing_days"] is True
    assert h["F"]["losing_days_ret_percentile"] == 50.0 and h["F"]["separation_on_losing_days"] is False
    readouts = out["readouts"]
    ml = readouts["waves"][1]["money_losing"]
    assert ml["peak_block"] == {"days": 5, "flagged": 0, "share": 0.0} and ml["lead_10d"]["share"] == 0.25 and ml["collapse"]["share"] == 1.0
    assert ml["collapse_first_flagged_day"] == str(CAL[10]) and readouts["waves"][0]["money_losing"] is None
    assert [w["status"] for w in readouts["waves"]] == ["truncated", "ok", "open"]
    assert readouts["waves"][1]["entry_gain_pct"] == {"top2": 120.0, "cohort3": 90.0} and readouts["waves"][1]["forms"]["top2"] == {"连板": 1, "趋势": 1}
    (handoff,) = [x for x in readouts["handoffs"] if x.get("status") == "ok"]
    assert handoff["handoff"] == "W1→W2" and handoff["money_losing"]["index_ret_pct"] == -7.5 and handoff["money_losing"]["median_stock_ret_pct"] == -11.0
    top2 = handoff["top2"]
    assert top2["old_in_collapse"]["ret_pct"]["median"] == -37.5 and top2["old_in_collapse"]["share_positive"] == 0.0
    assert top2["new_in_collapse"]["ret_percentile"]["median"] == 85.0 and top2["new_in_collapse"]["share_above_median"] == 1.0
    assert top2["new_in_collapse"]["share_separation_relative"] == 0.5 and top2["new_in_collapse"]["share_separation_new_high"] == 1.0
    assert top2["relation"]["new_members_from_old_cohort"] == 0 and top2["relation"]["l1_jaccard"] == round(1 / 3, 4)
    assert top2["relation"]["forms_old"] == {"连板": 1, "趋势": 1} and top2["relation"]["forms_new"] == {"趋势": 1, "连板": 1}
    # One stock in the top decile (F), and it became a new member: rate 1.0 against a base of 2/10.
    assert top2["lift_separation_relative"] == {"condition_n": 1, "became_new_member": 1, "rate": 1.0, "base_rate": 0.2, "lift": 5.0}
    # On the losing days the new top-2 (F −4, G +1) sit at percentiles 50 / 90 against an all-stock median of −4.5.
    assert handoff["money_losing"]["losing_days"] == 2 and handoff["money_losing"]["losing_days_ret_pct_all"]["median"] == -4.5
    on = top2["on_losing_days"]
    assert on["old_ret_pct"]["median"] == -8.5 and on["new_ret_pct"]["median"] == -1.5 and on["new_ret_percentile"]["median"] == 70.0
    assert on["new_share_above_median"] == 1.0 and on["new_share_separation"] == 0.5
    gate = readouts["separation_gate"]
    assert gate["cycles"] == 1 and gate["top2"]["n"] == 1 and gate["top2"]["k"] == 1 and gate["top2"]["verdict"] == "insufficient_n"
    assert gate["cohort3"]["baseline_n"] == 10 and gate["cohort3"]["baseline_k"] == 3


def test_handoff_without_collapse_rows_is_reported_not_guessed():
    waves = segment_waves(zip(CAL, STAGES), CAL)
    out = build_dynasties(waves, {1: [_gain("A", 50.0)], 2: [_gain("B", 60.0)]}, {}, top=1, cohort=1, separation_percentile=0.9)
    statuses = [(h["handoff"], h["status"]) for h in out["readouts"]["handoffs"]]
    assert statuses == [("W0→W1", "no_collapse_rows"), ("W1→W2", "no_collapse_rows")]
    assert out["handoffs"] == [] and out["readouts"]["separation_gate"]["cycles"] == 0
