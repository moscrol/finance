from __future__ import annotations

from intelligence.services.teaching_framework.coverage import build_coverage, normalize_hhmmss
from intelligence.services.teaching_framework.leader_succession import build_succession, top_by_day


def _row(day: str, stock: str, boards: int, **extra):
    return {"trade_date": day, "stock_ts_code": stock, "stock_name": stock, "limit_times": boards, **extra}


def test_coverage_distinguishes_empty_and_missing_and_dedupes():
    calendar = ["2026-01-01", "2026-01-02", "2026-01-03"]
    rows = {"2026-01-01": [{"stock_ts_code": "A", "limit_times": 3}, {"stock_ts_code": "A", "limit_times": 3}], "2026-01-02": []}
    cov = build_coverage(calendar, rows)
    assert cov["2026-01-01"].status == "covered"
    assert len(cov["2026-01-01"].rows) == 1
    assert cov["2026-01-02"].status == "covered_empty"
    assert cov["2026-01-03"].status == "missing"


def test_top_tie_is_a_group_and_field_null_is_fail_closed():
    """创始人 09-07：最高标不要求唯一，可以并列多个 — a tie is one leader group, not an error."""
    cov = build_coverage(["2026-01-01", "2026-01-02"], {"2026-01-01": [{"stock_ts_code": "B", "limit_times": 3}, {"stock_ts_code": "A", "limit_times": 3}], "2026-01-02": [{"stock_ts_code": "C", "limit_times": None}]})
    top = top_by_day(cov)
    assert top["2026-01-01"].status == "ok" and top["2026-01-01"].stocks == ("A", "B") and top["2026-01-01"].tie_size == 2
    assert top["2026-01-01"].boards == 3 and top["2026-01-01"].tied_stocks == ("A", "B")
    assert top["2026-01-02"].status == "field_null"


def test_true_handoff_from_low_boards_with_gap_two():
    days = [f"2026-01-0{i}" for i in range(1, 6)]
    rows = [
        _row(days[0], "A", 3),
        _row(days[1], "B", 1),              # A breaks on day 2; B is a low-board candidate
        _row(days[2], "B", 2),
        _row(days[3], "B", 3),              # B becomes the next unique top: birth day 4
        _row(days[4], "B", 4),
    ]
    node = build_succession(days, rows, covered_dates=days)["nodes"][0]
    assert (node.status, node.break_day, node.leader_i) == ("ok", days[1], "A")
    assert (node.leader_next, node.birth_day, node.birth_boards, node.gap_days) == ("B", days[3], 3, 2)
    assert node.handoff is True
    assert {c["stock"] for c in node.candidates} == {"B"}
    assert node.forward == {
        "realized": True, "anchor_as_of": days[1], "target": days[3], "knowledge_cutoff": days[3],
        "leader_next_size": 1, "handoff_members": ["B"],
    }


def test_false_handoff_when_successor_was_already_high():
    days = [f"2026-01-0{i}" for i in range(1, 5)]
    rows = [
        _row(days[0], "A", 5), _row(days[0], "B", 3),
        _row(days[1], "B", 4),              # A breaks; B (already 3 boards yesterday) is the next top, gap 0
        _row(days[2], "B", 5),
        _row(days[3], "B", 6),
    ]
    node = build_succession(days, rows, covered_dates=days)["nodes"][0]
    assert node.status == "ok" and node.gap_days == 0 and node.birth_boards == 4
    assert node.handoff is False  # 高位接力, not 低位衔接
    assert node.candidates == []


def test_tied_successor_group_partial_break_and_open_tail():
    days = [f"2026-01-0{i}" for i in range(1, 5)]
    rows = [
        _row(days[0], "A", 3),
        _row(days[1], "B", 3), _row(days[1], "C", 3),   # A breaks into a tied top group {B, C}
        _row(days[2], "B", 4),                          # C breaks but B carries on: the market's highest is still a yesterday-leader
        _row(days[3], "D", 1),                          # B breaks; nothing >= 3 afterwards
    ]
    result = build_succession(days, rows, covered_dates=days)
    by_break = {n.break_day: n for n in result["nodes"]}
    tie_node = by_break[days[1]]
    assert tie_node.status == "ok" and tie_node.leader_i == "A" and tie_node.leader_i_group == ["A"]
    assert tie_node.leader_next == "B|C" and tie_node.leader_next_group == ["B", "C"] and tie_node.birth_boards == 3
    assert tie_node.handoff is False and tie_node.candidates == []  # B and C were already at 3 boards: 高位接力
    assert set(tie_node.path) == {"B", "C"} and set(tie_node.shape_tags) == {"B", "C"}
    assert tie_node.forward["leader_next_size"] == 2 and tie_node.forward["handoff_members"] == []
    assert days[2] not in by_break  # partial break of the {B, C} group is not a break day
    assert result["partial_breaks"] == [{"day": days[2], "group": ["B", "C"], "still_sealed": ["B"]}]
    open_node = by_break[days[3]]
    assert open_node.leader_i == "B" and open_node.status == "open" and open_node.status_reason == "tail_no_successor"
    assert open_node.handoff is None


def test_tied_prior_group_breaks_together_and_handoff_reads_any_member():
    days = [f"2026-01-0{i}" for i in range(1, 6)]
    rows = [
        _row(days[0], "A", 4), _row(days[0], "B", 4), _row(days[0], "C", 1),   # tied leaders {A, B}; C is a low-board candidate
        _row(days[1], "C", 2), _row(days[1], "D", 1),                          # both A and B break on day 2
        _row(days[2], "C", 3), _row(days[2], "E", 3),                          # next top group {C, E}: C came from the candidates, E did not
        _row(days[3], "C", 4), _row(days[3], "E", 4),
        _row(days[4], "C", 5), _row(days[4], "E", 5),
    ]
    node = build_succession(days, rows, covered_dates=days)["nodes"][0]
    assert (node.status, node.break_day, node.leader_i, node.leader_i_group) == ("ok", days[1], "A|B", ["A", "B"])
    assert (node.leader_next, node.birth_day, node.birth_boards, node.gap_days) == ("C|E", days[2], 3, 1)
    assert {c["stock"] for c in node.candidates} == {"C", "D"}   # the broken leaders themselves are excluded
    assert node.handoff is True and node.forward["handoff_members"] == ["C"]


def test_overtaken_requires_prior_top_still_sealed_and_surpassed():
    dates = [f"2026-01-0{i}" for i in range(1, 7)]
    rows = [
        {"trade_date": dates[0], "stock_ts_code": "A", "stock_name": "A", "limit_times": 3},
        {"trade_date": dates[1], "stock_ts_code": "B", "stock_name": "B", "limit_times": 3},  # zero-gap successor
        {"trade_date": dates[2], "stock_ts_code": "B", "stock_name": "B", "limit_times": 3},
        {"trade_date": dates[2], "stock_ts_code": "A", "stock_name": "A", "limit_times": 4},  # B overtaken in day 3
        {"trade_date": dates[3], "stock_ts_code": "C", "stock_name": "C", "limit_times": 1},
        {"trade_date": dates[4], "stock_ts_code": "C", "stock_name": "C", "limit_times": 3},
    ]
    out = build_succession(dates, rows, covered_dates=dates)
    assert out["nodes"][0].status == "ok"
    assert out["nodes"][0].gap_days == 0
    assert out["nodes"][0].handoff is False
    assert out["overtaken"][0]["event_day"] == dates[2]


def test_data_gap_and_open_tail():
    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    rows = {dates[0]: [{"stock_ts_code": "A", "limit_times": 3}], dates[1]: []}
    out = build_succession(dates, rows)
    assert out["nodes"][0].status == "unverifiable"
    assert out["nodes"][0].status_reason == "data_gap"
    rows = {dates[0]: [{"stock_ts_code": "A", "limit_times": 3}]}
    out = build_succession(dates, rows, covered_dates=[dates[0]])
    assert out["nodes"][0].status == "unverifiable"
    assert out["nodes"][0].status_reason == "data_gap"


def test_time_normalization_and_unknown_shape():
    assert normalize_hhmmss(92500) == "09:25"
    assert normalize_hhmmss("09:35:00") == "09:35"
    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    rows = [
        {"trade_date": dates[0], "stock_ts_code": "A", "limit_times": 3},
        {"trade_date": dates[1], "stock_ts_code": "B", "limit_times": 1, "open_times": None, "first_limit_time": None},
        {"trade_date": dates[2], "stock_ts_code": "B", "limit_times": 3, "open_times": None, "first_limit_time": None},
    ]
    n = build_succession(dates, rows, covered_dates=dates)["nodes"][0]
    assert n.shape_tags["B"]["reseal"] == "unknown"
    assert n.shape_tags["B"]["one_word_or_instant"] == "unknown"


def test_shape_lookback_starts_before_the_successor_streak():
    """A 4-board successor at gap 0 must still expose its pre-streak history."""
    days = [f"2026-01-{d:02d}" for d in range(1, 12)]
    rows = [
        _row(days[0], "B", 1, open_times=0), _row(days[1], "B", 2, open_times=0),   # B: two boards then off
        _row(days[4], "B", 1, open_times=0), _row(days[5], "B", 2, open_times=0),   # re-entry (断板反包)
        _row(days[6], "B", 3, open_times=0),
        _row(days[6], "A", 6), _row(days[7], "A", 7), _row(days[7], "B", 4, open_times=0),
        _row(days[8], "B", 5, open_times=0),                                        # A breaks; B is top at 5 boards
        _row(days[9], "B", 6, open_times=0), _row(days[10], "B", 7, open_times=0),
    ]
    for d in days:
        rows.append(_row(d, "Z", 1))  # keep every day covered
    node = next(n for n in build_succession(days, rows, covered_dates=days, params={"rebound_window_days": 5})["nodes"] if n.leader_i == "A")
    assert node.status == "ok" and node.leader_next == "B" and node.birth_boards == 5
    path_days = [p["day"] for p in node.path["B"]]
    assert path_days[0] == days[0] and path_days[-1] == days[8]
    assert node.shape_tags["B"]["rebound_after_break"] is True
    assert node.shape_tags["B"]["reseal"] is False


def test_perturbing_a_later_day_does_not_change_anchor_fields_of_earlier_nodes():
    days = [f"2026-01-{d:02d}" for d in range(1, 10)]
    rows = [
        _row(days[0], "A", 3), _row(days[1], "B", 1), _row(days[2], "B", 2), _row(days[3], "B", 3),
        _row(days[4], "B", 4), _row(days[5], "C", 3), _row(days[6], "C", 4), _row(days[7], "D", 1), _row(days[8], "D", 2),
    ]
    for d in days:
        rows.append(_row(d, "Z", 1))
    base = {n.break_day: n for n in build_succession(days, rows, covered_dates=days)["nodes"]}
    assert days[7] in base  # C breaks on day 8 in the unperturbed history
    k = 7  # perturb day 8: C keeps sealing instead of breaking
    perturbed = rows + [_row(days[k], "C", 5)]
    after = {n.break_day: n for n in build_succession(days, perturbed, covered_dates=days)["nodes"]}
    assert days[7] not in after
    compared = 0
    for break_day, node in base.items():
        if node.birth_day is not None and node.birth_day < days[k - 1] and break_day < days[k - 1]:
            other = after[break_day]
            assert (node.leader_i, node.candidates, node.context_break, node.leader_next, node.birth_day, node.handoff) == (
                other.leader_i, other.candidates, other.context_break, other.leader_next, other.birth_day, other.handoff
            )
            compared += 1
    assert compared == 2
