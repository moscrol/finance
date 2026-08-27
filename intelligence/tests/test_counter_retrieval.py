"""KC-05：反方检索规划——分桶 target、保底槽、无命中披露。"""
from __future__ import annotations

from intelligence.services.counter_retrieval import (
    COUNTER_MARK,
    COUNTER_RISK_BUCKETS,
    COUNTER_SLOT_RESERVE,
    MISSING_COUNTER_EVIDENCE,
    match_counter_bucket,
    plan_counter_targets,
    reserve_counter_slots,
)


def test_plan_counter_targets_emits_entity_and_theme_times_six_buckets() -> None:
    targets = plan_counter_targets("长电科技", "先进封装")
    assert [item.bucket for item in targets[:6]] == [
        name for name, _terms in COUNTER_RISK_BUCKETS
    ]
    assert [item.bucket for item in targets[6:]] == [
        name for name, _terms in COUNTER_RISK_BUCKETS
    ]
    assert [item.subject for item in targets[:6]] == ["长电科技"] * 6
    assert [item.subject for item in targets[6:]] == ["先进封装"] * 6
    assert targets[0].query == "长电科技 产能过剩"
    assert targets[3].query == "长电科技 需求不及预期"
    assert targets[5].query == "长电科技 政策收紧"
    assert targets[6].query == "先进封装 产能过剩"


def test_plan_counter_targets_skips_blank_and_duplicate_subjects() -> None:
    targets = plan_counter_targets("  ", "长电科技", "长电科技", "")
    assert [item.subject for item in targets] == ["长电科技"] * 6
    assert len(targets) == 6


def test_match_counter_bucket_is_typed_not_bare_policy_word() -> None:
    assert match_counter_bucket("扩产过快导致供给过剩") == "产能过剩"
    assert match_counter_bucket("同行打价格战，毛利率承压") == "价格战"
    assert match_counter_bucket("技术路线切换，旧工艺被替代") == "技术替代"
    assert match_counter_bucket("Q2 需求不及预期，订单下滑") == "需求不及"
    assert match_counter_bucket("新进入者涌入，竞争格局恶化") == "竞格恶化"
    assert match_counter_bucket("补贴退坡叠加出口限制") == "政策"
    assert match_counter_bucket("产业政策支持国产替代") is None
    assert match_counter_bucket("营收同比增长 18%") is None


def test_reserve_counter_slots_keeps_two_when_window_is_full() -> None:
    support = [f"s{i}" for i in range(8)]
    counter = ["c0", "c1", "c2"]
    chosen = reserve_counter_slots(support, counter, max_n=8)
    assert [item for item, is_counter in chosen if not is_counter] == [
        "s0",
        "s1",
        "s2",
        "s3",
        "s4",
        "s5",
    ]
    assert [item for item, is_counter in chosen if is_counter] == ["c0", "c1"]
    assert len(chosen) == 8
    assert COUNTER_SLOT_RESERVE == 2


def test_reserve_counter_slots_does_not_empty_occupy_or_cap_when_room() -> None:
    assert reserve_counter_slots(["s0"], [], max_n=8) == [("s0", False)]
    assert reserve_counter_slots(["s0", "s1"], ["c0"], max_n=8) == [
        ("s0", False),
        ("s1", False),
        ("c0", True),
    ]
    assert reserve_counter_slots([], ["c0", "c1", "c2"], max_n=8) == [
        ("c0", True),
        ("c1", True),
        ("c2", True),
    ]


def test_disclosure_constant_is_explicit_not_silent() -> None:
    assert MISSING_COUNTER_EVIDENCE == "未检索到反方证据"
    assert COUNTER_MARK == "[反]"


def test_humanize_keeps_counter_mark_but_still_strips_status_prefix() -> None:
    from intelligence.services.answer_model import humanize

    kept = humanize("[反] 反方线索（待进一步核验）：需求不及预期 [W2]")
    assert kept.startswith("[反]")
    assert "需求不及预期" in kept
    assert "[W2]" not in kept
    assert humanize("[missing] 反方线索（待进一步核验）：需求不及预期").startswith(
        "反方线索"
    )
