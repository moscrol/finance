from intelligence.services.teaching_framework.flags import compute_flags
from intelligence.services.teaching_framework.index_stage import build_index_stage
from intelligence.services.teaching_framework.stage_rules import (
    resolve_stage,
    derive_turns,
)


def test_tie_requires_graph_or_ambiguous():
    scores = {
        "左底向下": 1,
        "左底向上": 1,
        "缩量右底": 0,
        "共建主线阶段": 0,
        "主流主升": 0,
        "高位震荡": 0,
        "回踩周均线": 0,
    }
    assert resolve_stage(scores, None)[0] == "ambiguous"
    assert resolve_stage(scores, "左底向下")[0] == "左底向上"


def test_null_inputs_do_not_infer_flags():
    rows = [
        {
            "trade_date": "2026-01-01",
            "sh_index_close": None,
            "sh_week_ma": 1,
            "sh_deviation_pct": None,
        }
    ]
    got = compute_flags(rows, calendar=["2026-01-01"])[0]
    assert got["above_week_ma"] is None
    assert got["deviation_band"] is None


def test_turns_reset_on_unknown_and_reconcile():
    seq = [
        "左底向上",
        "共建主线阶段",
        "共建主线阶段",
        "ambiguous",
        "高位震荡",
        "左底向下",
    ]
    turns = derive_turns(seq)
    assert sum(x["turn_up"] for x in turns) == 1
    assert sum(x["turn_top"] for x in turns) == 1
    assert sum(x["turn_down"] for x in turns) == 1


def test_stage_evidence_is_structured_json():
    rows = [
        {
            "trade_date": "2026-01-01",
            "sh_index_close": 101,
            "sh_week_ma": 100,
            "sh_deviation_pct": 2,
            "sh_index_open": 100,
            "total_amount": 100,
            "amount_ma20": 90,
            "amount_vs_yesterday_pct": 11,
        }
    ]
    result = build_index_stage(rows, calendar=["2026-01-01"])[0]
    import json

    evidence = json.loads(result["stage_evidence"])
    assert "scores" in evidence and "hits" in evidence
