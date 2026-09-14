"""02 · 排序器验收（spec §7 P01 / P03–P08 / P10 / P13 + 解释卫生）。

全部用可理解的固定输入直接调用真实 ``prioritize``，不 mock 被测 ranker。
时间：evaluation_at 一律显式注入；夹具日期固定在 2026-09-12 / 13，与机器时钟无关。
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import pytest

from intelligence.services import research_priority as rp
from intelligence.services.research_priority import contracts as c

OWNER = "u_test"
EVAL_AT = "2026-09-13T02:00:00Z"  # 北京时间 09-13 10:00
AS_OF = "2026-09-12"
CUTOFF = "2026-09-12T15:30:00+08:00"


def _ref(kind: str, ident: str, *, namespace: str = "judgments", version: str | None = "v1") -> dict[str, Any]:
    return {"kind": kind, "id": ident, "namespace": namespace, "version_or_hash": version, "scope": None}


def _effort(minutes: float, kind: str = "user_estimate") -> dict[str, Any]:
    return {"seconds": minutes * 60, "kind": kind, "source_ref": "test"}


def _task(
    ident: str,
    *,
    effect: str = c.EFFECT_EXPLORE,
    objects: tuple[dict[str, Any], ...] = (),
    evidence: tuple[dict[str, Any], ...] = (),
    condition: Any = None,
    availability: str = c.AVAIL_ACTIONABLE,
    effort: dict[str, Any] | None = None,
    due_at: Any = None,
    available_at: Any = None,
    as_of: str | None = AS_OF,
    cutoff: str | None = CUTOFF,
    question: str | None = None,
    entity_refs: tuple[str, ...] = (),
    status: str | None = None,
    owner: str = OWNER,
    source_namespace: str = "tests",
    **extra: Any,
) -> dict[str, Any]:
    task: dict[str, Any] = {
        "schema_version": c.SCHEMA_TASK,
        "id": ident,
        "owner_user_id": owner,
        "scope": {"conversation_id": "conv_1", "entity_refs": list(entity_refs)},
        "source": _ref("test_source", ident, namespace=source_namespace, version="s1"),
        "object_refs": list(objects),
        "maintenance_item_ids": [],
        "question": question or f"任务 {ident}",
        "discriminating_evidence": "证据 X 的字段 Y",
        "completion_condition": f"读到 {ident} 引用的版本并核对字段 Y",
        "effect_kind": effect,
        "effect_evidence_refs": list(evidence),
        "condition_result": condition,
        "availability": availability,
        "available_at": available_at,
        "due_at": due_at,
        "as_of": as_of,
        "knowledge_cutoff": cutoff,
        "pit_grade": "trade_date_only",
        "effort": effort,
        "gaps": [],
        "legacy_unbound": not objects,
        "management_status": status,
    }
    task.update(extra)
    return task


def _abandon(ident: str, obj: str, *, effort: dict[str, Any] | None = None, status: str | None = None) -> dict[str, Any]:
    return _task(
        ident,
        effect=c.EFFECT_ABANDON,
        objects=(_ref("judgment", obj),),
        evidence=(_ref("condition", f"cond_{obj}", namespace=f"binding:b_{obj}"), _ref("evidence", f"ann_{obj}", namespace="announcement", version="h1")),
        condition=True,
        effort=effort,
        status=status,
    )


def _ids(rows: list[dict[str, Any]]) -> list[str]:
    return [row["task"]["id"] for row in rows]


def _by_source(report: dict[str, Any], source_id: str) -> tuple[str, dict[str, Any]]:
    """按来源 id 找到任务落在哪一组（selected/deferred/blocked）。"""
    for section in ("selected", "deferred", "blocked"):
        for row in report[section]:
            if any(r["id"] == source_id for r in row["task"]["merged_source_refs"]):
                return section, row
    raise AssertionError(f"来源 {source_id} 不在任何一组")


# ---------------------------------------------------------------------------
# P01 · 放弃条件 vs 十项高热度探索
# ---------------------------------------------------------------------------


def test_p01_triggered_abandon_outranks_ten_hot_explorations():
    hot = [
        _task(f"hot_{i}", effect=c.EFFECT_EXPLORE, effort=_effort(1), question=f"热门题材 {i} 今日大涨，继续追踪")
        for i in range(10)
    ]
    abandon = _abandon("ab_1", "j_alpha")  # 耗时未知、也没有热度分
    report = rp.prioritize(hot + [abandon], None, None, EVAL_AT)

    assert report["selected"][0]["group"] == c.GROUP_ABANDON
    section, row = _by_source(report, "ab_1")
    assert section == "selected" and row["rank"] == 1
    # 探索项全在第 5 组，热度不会改变证据等级。
    for row in report["selected"][1:] + report["deferred"]:
        assert row["group"] == c.GROUP_EXPLORE
    assert report["critical_not_selected_ids"] == []


def test_abandon_without_observed_trigger_is_rejected_not_demoted():
    fake = _task(
        "fake_ab",
        effect=c.EFFECT_ABANDON,
        objects=(_ref("judgment", "j_x"),),
        evidence=(_ref("evidence", "e1", namespace="announcement", version="h1"),),
        condition=c.CONDITION_UNKNOWN,
    )
    with pytest.raises(c.ContractError) as excinfo:
        rp.prioritize([fake], None, None, EVAL_AT)
    assert excinfo.value.code == "abandon_without_observed_trigger"


def test_hash_change_stays_in_group_two():
    review = _task(
        "rv_1",
        effect=c.EFFECT_REVIEW_CHANGED,
        objects=(_ref("judgment", "j_beta"),),
        evidence=(_ref("evidence", "report:sw", namespace="sellside_report", version="h_new"),),
        question="卖方报告《利空来袭》内容哈希变了",
    )
    report = rp.prioritize([review], None, None, EVAL_AT)
    assert report["selected"][0]["group"] == c.GROUP_REVIEW_CHANGED
    assert report["critical_not_selected_ids"] == []


# ---------------------------------------------------------------------------
# P03 / P13 · 时间状态只按 evaluation_at 变化
# ---------------------------------------------------------------------------


def test_p03_tomorrow_release_waits_today_condition_selectable():
    release_tomorrow = _task(
        "rel_1",
        effect=c.EFFECT_REVIEW_CHANGED,
        objects=(_ref("judgment", "j_a"),),
        evidence=(_ref("evidence", "ann_future", namespace="announcement", version="h1"),),
        availability=c.AVAIL_WAITING_RELEASE,
        available_at="2026-09-14T01:00:00Z",
        availability_reason="公告 09-14 披露后可读",
    )
    due_today = _task(
        "due_1",
        effect=c.EFFECT_VERIFY_DUE,
        objects=(_ref("checkpoint", "cp_1", namespace="checkpoints"),),
        condition=c.CONDITION_UNKNOWN,
        due_at="2026-09-12",
    )
    report = rp.prioritize([release_tomorrow, due_today], None, None, EVAL_AT)
    assert _by_source(report, "rel_1")[0] == "blocked"
    blocked = report["blocked"][0]
    assert blocked["reason"] == c.AVAIL_WAITING_RELEASE
    assert blocked["release_condition"] == "公告 09-14 披露后可读"
    assert blocked["available_at"] == "2026-09-14T01:00:00Z"
    section, row = _by_source(report, "due_1")
    assert section == "selected" and row["group"] == c.GROUP_VERIFY_DUE


def test_p13_clock_crossing_changes_only_time_status_and_never_reads_machine_clock():
    tasks = [
        _task(
            "not_due",
            effect=c.EFFECT_VERIFY_DUE,
            objects=(_ref("checkpoint", "cp_9", namespace="checkpoints"),),
            condition=c.CONDITION_UNKNOWN,
            due_at="2026-09-14T00:00:00Z",
        ),
        _task(
            "release",
            effect=c.EFFECT_REVIEW_CHANGED,
            objects=(_ref("judgment", "j_r"),),
            evidence=(_ref("evidence", "e_r", namespace="announcement", version="h1"),),
            availability=c.AVAIL_WAITING_RELEASE,
            available_at="2026-09-14T01:00:00Z",
        ),
        _task(
            "future",
            effect=c.EFFECT_FILL_GAP,
            objects=(_ref("judgment", "j_f"),),
            cutoff="2026-09-14T00:00:00Z",  # 资料截止晚于第一次评估：尚不可知
        ),
    ]
    before = rp.prioritize(copy.deepcopy(tasks), None, None, "2026-09-13T02:00:00Z")
    after = rp.prioritize(copy.deepcopy(tasks), None, None, "2026-09-15T02:00:00Z")

    assert {row["reason"] for row in before["blocked"]} == {c.BLOCK_NOT_YET_DUE, c.AVAIL_WAITING_RELEASE, c.BLOCK_FUTURE_RECORD}
    assert before["selected"] == []
    assert after["blocked"] == []
    assert len(after["selected"]) == 3
    # 评估时刻冻结进摘要；同输入不同时刻的报告 id 不同。
    assert before["evaluation_at"] == "2026-09-13T02:00:00Z" and after["evaluation_at"] == "2026-09-15T02:00:00Z"
    assert before["input_digest"] != after["input_digest"]
    assert before["id"] != after["id"]
    # 市场日 / 资料截止不充当时钟：报告仍原样回显输入值。
    assert before["as_of"] == AS_OF and after["as_of"] == AS_OF
    assert before["knowledge_cutoff"] == "2026-09-14T00:00:00Z"

    # 包内不读系统时钟：源码里不能出现 now() / today() / utcnow()。
    package_dir = Path(rp.__file__).resolve().parent
    for path in sorted(package_dir.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert not re.search(r"\.(now|utcnow|today)\(", source), f"{path.name} 读了系统时钟"


def test_evaluation_at_must_be_a_zoned_instant():
    for bad, code in (
        (None, "evaluation_at_required"),
        ("2026-09-13", "invalid_timestamp"),
        ("2026-09-13T02:00:00", "naive_timestamp"),
    ):
        with pytest.raises(c.ContractError) as excinfo:
            rp.prioritize([], None, None, bad, owner_user_id=OWNER)
        assert excinfo.value.code == code


# ---------------------------------------------------------------------------
# P04 / P05 · 预算
# ---------------------------------------------------------------------------


def test_p04_ten_minute_budget_defers_twelve_selects_six_and_four():
    twelve = _abandon("t12", "j_1", effort=_effort(12))
    six = _task(
        "t6",
        effect=c.EFFECT_REVIEW_CHANGED,
        objects=(_ref("judgment", "j_2"),),
        evidence=(_ref("evidence", "e2", namespace="announcement", version="h1"),),
        effort=_effort(6),
    )
    four = _task(
        "t4",
        effect=c.EFFECT_VERIFY_DUE,
        objects=(_ref("checkpoint", "cp_3", namespace="checkpoints"),),
        condition=c.CONDITION_UNKNOWN,
        due_at="2026-09-12",
        effort=_effort(4, kind="observed"),
    )
    report = rp.prioritize([four, six, twelve], None, {"minutes": 10}, EVAL_AT)

    assert [_by_source(report, sid)[0] for sid in ("t12", "t6", "t4")] == ["deferred", "selected", "selected"]
    assert report["deferred"][0]["reason"] == c.DEFER_OVER_BUDGET
    assert [row["estimated_seconds"] for row in report["selected"]] == [360.0, 240.0]
    assert sum(row["estimated_seconds"] for row in report["selected"]) <= 600
    assert report["totals"]["known_seconds"] == 600.0
    # 被省略的第 1 组任务必须点名。
    assert report["critical_not_selected_ids"] == [_by_source(report, "t12")[1]["task"]["id"]]
    assert report["budget"] == {"minutes": 10.0, "max_items": 3, "max_per_object": 1}
    assert any("贪心" in text for text in report["limitations"])


def test_p05_zero_budget_selects_nothing():
    report = rp.prioritize([_abandon("a", "j_a", effort=_effort(1)), _task("b", effort=_effort(0.5))], None, {"minutes": 0}, EVAL_AT)
    assert report["selected"] == []
    assert {row["reason"] for row in report["deferred"]} == {c.DEFER_OVER_BUDGET}
    assert report["critical_not_selected_ids"] == [_by_source(report, "a")[1]["task"]["id"]]


def test_p05_unknown_effort_is_not_zero_under_a_budget():
    unknown = _abandon("unk", "j_u")  # effort 未知
    known = _task(
        "known",
        effect=c.EFFECT_REVIEW_CHANGED,
        objects=(_ref("judgment", "j_k"),),
        evidence=(_ref("evidence", "e_k", namespace="announcement", version="h1"),),
        effort=_effort(5),
    )
    report = rp.prioritize([unknown, known], None, {"minutes": 30}, EVAL_AT)
    section, row = _by_source(report, "unk")
    assert section == "deferred" and row["reason"] == c.DEFER_EFFORT_UNKNOWN
    assert _by_source(report, "known")[0] == "selected"
    assert report["totals"]["unknown_effort_count"] == 1
    assert report["totals"]["known_seconds"] == 300.0
    # 关键项被省略时同样点名，即便原因是耗时未知。
    assert report["critical_not_selected_ids"] == [row["task"]["id"]]
    # 无预算时未知耗时可以入选，但 estimated_seconds 是 None 不是 0。
    free = rp.prioritize([unknown], None, None, EVAL_AT)
    assert free["selected"][0]["estimated_seconds"] is None
    assert free["totals"]["known_seconds"] == 0


def test_p05_empty_input_yields_complete_zero_report():
    report = rp.prioritize([], None, None, EVAL_AT, owner_user_id=OWNER)
    assert report["schema_version"] == c.SCHEMA_REPORT
    assert report["owner_user_id"] == OWNER
    assert report["selected"] == [] and report["deferred"] == [] and report["blocked"] == []
    assert report["critical_not_selected_ids"] == []
    assert report["totals"] == {
        "candidate_count": 0,
        "input_count": 0,
        "merged_count": 0,
        "selected_count": 0,
        "deferred_count": 0,
        "blocked_count": 0,
        "known_seconds": 0,
        "unknown_effort_count": 0,
    }
    assert report["id"].startswith("rp_") and len(report["input_digest"]) == 64
    assert report["as_of"] is None and report["knowledge_cutoff"] is None
    assert report["generated_at"] is None
    with pytest.raises(c.ContractError) as excinfo:
        rp.prioritize([], None, None, EVAL_AT)
    assert excinfo.value.code == "owner_missing"


# ---------------------------------------------------------------------------
# P06 / P07 · 合并与不合并
# ---------------------------------------------------------------------------


def _same_evidence_review(ident: str, obj: str, *, namespace: str = "queue_a") -> dict[str, Any]:
    return _task(
        ident,
        effect=c.EFFECT_REVIEW_CHANGED,
        objects=(_ref("judgment", obj),),
        evidence=(_ref("evidence", "report:sw:2026-09-10", namespace="sellside_report", version="h_rep_1"),),
        source_namespace=namespace,
    )


def test_p06_same_evidence_three_judgments_two_queues_become_one_task_with_all_sources():
    queue_a = [_same_evidence_review(f"a_{obj}", obj, namespace="queue_a") for obj in ("j1", "j2", "j3")]
    queue_b = [_same_evidence_review(f"b_{obj}", obj, namespace="queue_b") for obj in ("j1", "j2", "j3")]
    report = rp.prioritize(queue_a + queue_b, None, None, EVAL_AT)

    assert report["totals"] == {
        "candidate_count": 1,
        "input_count": 6,
        "merged_count": 5,
        "selected_count": 1,
        "deferred_count": 0,
        "blocked_count": 0,
        "known_seconds": 0,
        "unknown_effort_count": 1,
    }
    task = report["selected"][0]["task"]
    assert sorted(r["id"] for r in task["object_refs"]) == ["j1", "j2", "j3"]
    assert sorted(r["id"] for r in task["merged_source_refs"]) == ["a_j1", "a_j2", "a_j3", "b_j1", "b_j2", "b_j3"]
    assert len(task["source_task_ids"]) == 6
    assert "受影响对象 3 个" in " ".join(report["selected"][0]["reasons"])
    assert "同时影响 6 条来源" in task["question"]


def test_p07_same_text_different_entity_or_window_are_not_merged():
    same_text = "配额落地后价格是否继续上行？"
    a = _task("q_a", question=same_text, entity_refs=("theme:制冷剂",))
    b = _task("q_b", question=same_text, entity_refs=("theme:氟化工",))
    c_ = _task("q_c", question=same_text, entity_refs=("theme:制冷剂",), as_of="2026-09-11")
    d = _task("q_d", question=same_text, entity_refs=("theme:制冷剂",))  # 与 a 完全同范围 → 合并
    report = rp.prioritize([a, b, c_, d], None, None, EVAL_AT)
    assert report["totals"]["candidate_count"] == 3
    assert report["totals"]["merged_count"] == 1
    section, row = _by_source(report, "q_a")
    assert sorted(r["id"] for r in row["task"]["merged_source_refs"]) == ["q_a", "q_d"]


# ---------------------------------------------------------------------------
# 评审返修 S5：市场日是否未来，按市场时区（Asia/Shanghai）日历日判断，不按 UTC 日
# ---------------------------------------------------------------------------
def test_market_day_future_check_uses_market_timezone_not_utc():
    """as_of=09-14 的资料 06:00+08 已知：北京时间 09-14 07:00（=UTC 09-13 23:00）评估时
    市场日已经开始，不能因 UTC 日历日还是 09-13 就判 future_record（总合同：市场日 as_of、
    知识截止、事件时间分开；02 §4 窗口只管可知性，不充当时钟）。"""
    task = _task(
        "already_known_monday",
        effect=c.EFFECT_REVIEW_CHANGED,
        objects=(_ref("judgment", "tz_jd"),),
        evidence=(_ref("evidence", "tz_source", namespace="announcement", version="h-new"),),
        as_of="2026-09-14",
        cutoff="2026-09-14T06:00:00+08:00",
        effort=_effort(1),
    )
    # 市场日 09-14 已开场且资料已知的三个等价时刻（23:00Z = 07:00+08）：全部应可选。
    for when in ("2026-09-13T23:00:00Z", "2026-09-14T07:00:00+08:00", "2026-09-14T00:00:00Z"):
        report = rp.prioritize([copy.deepcopy(task)], None, None, when)
        section, _row = _by_source(report, "already_known_monday")
        assert section == "selected", (when, report["blocked"])
    # 市场日已开场（09-14 05:00+08）但资料尚未登记（cutoff 06:00+08）：仍按真实时刻挡。
    not_yet_known = rp.prioritize([copy.deepcopy(task)], None, None, "2026-09-13T21:00:00Z")
    section, row = _by_source(not_yet_known, "already_known_monday")
    assert section == "blocked" and row["reason"] == c.BLOCK_FUTURE_RECORD
    # 市场日还没开始（09-13 23:59+08）：as_of 仍是未来记录。
    before_open = rp.prioritize([copy.deepcopy(task)], None, None, "2026-09-13T15:59:00Z")
    section, row = _by_source(before_open, "already_known_monday")
    assert section == "blocked" and row["reason"] == c.BLOCK_FUTURE_RECORD


# ---------------------------------------------------------------------------
# 评审返修 P2：同证据不同执行窗口（due_at / available_at）是两个机会，合并前必须隔离
# ---------------------------------------------------------------------------
def test_same_evidence_distinct_due_windows_are_not_merged():
    """同证据 / 同 as_of / 同 cutoff、不同 due_at：明日项不得随今日项提前入选，
    到期时刻也不能被合并改写成今天（spec §5.1 可执行性先行；§4 到期各自比较）。"""
    shared = (_ref("evidence", "condition-input", namespace="announcements", version="h1"),)
    today = _task(
        "due_today",
        effect=c.EFFECT_VERIFY_DUE,
        objects=(_ref("checkpoint", "today"),),
        evidence=shared,
        condition="unknown",
        due_at="2026-09-13T01:00:00Z",
        effort=_effort(1),
    )
    tomorrow = _task(
        "due_tomorrow",
        effect=c.EFFECT_VERIFY_DUE,
        objects=(_ref("checkpoint", "tomorrow"),),
        evidence=shared,
        condition="unknown",
        due_at="2026-09-14T01:00:00Z",
        effort=_effort(1),
    )
    report = rp.prioritize([today, tomorrow], None, None, EVAL_AT)
    assert report["totals"]["candidate_count"] == 2 and report["totals"]["merged_count"] == 0
    section_today, row_today = _by_source(report, "due_today")
    section_tomorrow, row_tomorrow = _by_source(report, "due_tomorrow")
    assert section_today == "selected"
    assert row_today["task"]["due_at"] == "2026-09-13T01:00:00Z"
    assert section_tomorrow == "blocked" and row_tomorrow["reason"] == c.BLOCK_NOT_YET_DUE
    assert row_tomorrow["task"]["due_at"] == "2026-09-14T01:00:00Z"


def test_same_evidence_distinct_release_windows_do_not_block_current():
    """负控同根：waiting_release 的 available_at 不同也不合并——今日已发布的来源
    不得陪明日的来源一起等（合并取 max available_at 会把可查项拖进 blocked）。"""
    shared = (_ref("evidence", "condition-input", namespace="announcements", version="h1"),)
    released = _task(
        "rel_today",
        effect=c.EFFECT_REVIEW_CHANGED,
        objects=(_ref("judgment", "j_rel"),),
        evidence=shared,
        availability=c.AVAIL_WAITING_RELEASE,
        available_at="2026-09-13T01:00:00Z",
        effort=_effort(1),
    )
    waiting = _task(
        "rel_tomorrow",
        effect=c.EFFECT_REVIEW_CHANGED,
        objects=(_ref("judgment", "j_rel"),),
        evidence=shared,
        availability=c.AVAIL_WAITING_RELEASE,
        available_at="2026-09-14T01:00:00Z",
        effort=_effort(1),
    )
    report = rp.prioritize([released, waiting], None, None, EVAL_AT)
    assert report["totals"]["candidate_count"] == 2 and report["totals"]["merged_count"] == 0
    section_released, _row_released = _by_source(report, "rel_today")
    section_waiting, row_waiting = _by_source(report, "rel_tomorrow")
    assert section_released == "selected"
    assert section_waiting == "blocked" and row_waiting["reason"] == c.AVAIL_WAITING_RELEASE
    # 同一执行窗口内的同证据仍合成一个任务（合并本意：同窗口重复读取只核查一次）。
    twin = _task(
        "rel_today_twin",
        effect=c.EFFECT_REVIEW_CHANGED,
        objects=(_ref("judgment", "j_rel_twin"),),
        evidence=shared,
        availability=c.AVAIL_WAITING_RELEASE,
        available_at="2026-09-13T01:00:00Z",
        effort=_effort(1),
    )
    same = rp.prioritize([released, twin], None, None, EVAL_AT)
    assert same["totals"]["candidate_count"] == 1 and same["totals"]["merged_count"] == 1


# ---------------------------------------------------------------------------
# P08 · 前三项不能隐去第 4 个关键放弃条件
# ---------------------------------------------------------------------------


def _abandon_window(ident: str, *, as_of: str, cutoff: str) -> dict[str, Any]:
    """同一 binding:b1/c1 条件在不同观测窗口的两次 true 观测（评审 P1 的最小输入）。"""
    return _task(
        ident,
        effect=c.EFFECT_ABANDON,
        objects=(_ref("judgment", "j1"),),
        evidence=(_ref("condition", "c1", namespace="binding:b1"),),
        condition=True,
        effort=_effort(1),
        as_of=as_of,
        cutoff=cutoff,
    )


def test_future_observation_window_does_not_swallow_today_critical_condition():
    """评审 P1：未来观测窗口的同条件记录不得与当天关键条件合并后一起 blocked。"""
    today = _abandon_window("critical_today", as_of="2026-09-12", cutoff="2026-09-12T15:00:00+08:00")
    tomorrow = _abandon_window("critical_tomorrow", as_of="2026-09-14", cutoff="2026-09-14T15:00:00+08:00")
    report = rp.prioritize([today, tomorrow], None, None, EVAL_AT)

    # 两个观测窗口各自成候选，未来那条不吞掉当天那条。
    assert report["totals"]["candidate_count"] == 2
    assert report["totals"]["merged_count"] == 0
    assert report["totals"]["selected_count"] == 1 and report["totals"]["blocked_count"] == 1

    section, row = _by_source(report, "critical_today")
    assert section == "selected" and row["group"] == c.GROUP_ABANDON
    assert row["task"]["as_of"] == "2026-09-12"
    assert row["task"]["knowledge_cutoff"] == "2026-09-12T15:00:00+08:00"

    blocked_section, blocked_row = _by_source(report, "critical_tomorrow")
    assert blocked_section == "blocked" and blocked_row["reason"] == c.BLOCK_FUTURE_RECORD
    # 未来记录只带自己的来源，不把当天那条一起拖进 blocked。
    assert blocked_row["task"]["source_task_ids"] == ["critical_tomorrow"]
    assert [r["id"] for r in blocked_row["task"]["merged_source_refs"]] == ["critical_tomorrow"]
    assert any(g["reason"] == "future_record_excluded" and g["task_ids"] == [blocked_row["task"]["id"]] for g in report["gaps"])


def test_same_evidence_different_observation_window_is_not_merged():
    """spec §5.3「仅文本相似但对象或时间窗不同，不合并」：同证据不同市场日 → 两个候选。"""
    d1 = _same_evidence_review("d1", "j1")
    d2 = dict(copy.deepcopy(d1), id="d2", as_of="2026-09-11", source=_ref("test_source", "d2", namespace="queue_a", version="s1"))
    split = rp.prioritize([d1, d2], {"max_per_object": 2}, None, EVAL_AT)
    assert split["totals"]["candidate_count"] == 2 and split["totals"]["merged_count"] == 0
    assert {row["task"]["as_of"] for row in split["selected"]} == {"2026-09-11", "2026-09-12"}

    # 同一窗口内的同证据仍合成一个任务（P06 口径不变）。
    d3 = dict(copy.deepcopy(d1), id="d3", source=_ref("test_source", "d3", namespace="queue_b", version="s1"))
    same = rp.prioritize([d1, d3], None, None, EVAL_AT)
    assert same["totals"]["candidate_count"] == 1 and same["totals"]["merged_count"] == 1

    # 观测窗口的另一半：市场日相同、资料截止不同，同样不合并。
    d4 = dict(copy.deepcopy(d1), id="d4", knowledge_cutoff="2026-09-12T09:30:00+08:00", source=_ref("test_source", "d4", namespace="queue_c", version="s1"))
    by_cutoff = rp.prioritize([d1, d4], {"max_per_object": 2}, None, EVAL_AT)
    assert by_cutoff["totals"]["candidate_count"] == 2 and by_cutoff["totals"]["merged_count"] == 0


def test_p08_fourth_critical_beyond_max_items_is_named():
    tasks = [_abandon(f"ab_{i}", f"j_{i}") for i in range(4)]
    report = rp.prioritize(tasks, None, None, EVAL_AT)
    assert len(report["selected"]) == 3
    assert len(report["deferred"]) == 1 and report["deferred"][0]["reason"] == c.DEFER_MAX_ITEMS
    assert report["critical_not_selected_ids"] == [report["deferred"][0]["task"]["id"]]


def test_snoozed_critical_is_deferred_but_still_named():
    tasks = [_abandon("ab_open", "j_o"), _abandon("ab_snz", "j_s", status="snoozed")]
    report = rp.prioritize(tasks, None, None, EVAL_AT)
    section, row = _by_source(report, "ab_snz")
    assert section == "deferred" and row["reason"] == c.DEFER_USER_SNOOZED
    assert report["critical_not_selected_ids"] == [row["task"]["id"]]


def test_per_object_limit_and_policy_override():
    review = _task(
        "rv",
        effect=c.EFFECT_REVIEW_CHANGED,
        objects=(_ref("judgment", "j_same"),),
        evidence=(_ref("evidence", "e1", namespace="announcement", version="h1"),),
    )
    gap = _task("gap", effect=c.EFFECT_FILL_GAP, objects=(_ref("judgment", "j_same"),))
    default = rp.prioritize([review, gap], None, None, EVAL_AT)
    section, row = _by_source(default, "gap")
    assert section == "deferred" and row["reason"] == c.DEFER_PER_OBJECT
    widened = rp.prioritize([review, gap], {"max_per_object": 2}, None, EVAL_AT)
    assert len(widened["selected"]) == 2
    assert widened["policy_version"] == c.POLICY_VERSION


# ---------------------------------------------------------------------------
# P10 · 重排、重复读取 → 同输出
# ---------------------------------------------------------------------------


def test_p10_reordered_and_reread_inputs_give_identical_report():
    tasks = [
        _abandon("ab", "j_ab", effort=_effort(3)),
        _same_evidence_review("rv1", "j_1"),
        _same_evidence_review("rv2", "j_2"),
        _task("ex1", question="探索 A", entity_refs=("theme:A",)),
        _task("ex2", question="探索 B", entity_refs=("theme:B",), effort=_effort(1)),
        _task(
            "wait",
            effect=c.EFFECT_REVIEW_CHANGED,
            objects=(_ref("judgment", "j_w"),),
            evidence=(_ref("evidence", "e_w", namespace="announcement", version="h1"),),
            availability=c.AVAIL_WAITING_RELEASE,
        ),
    ]
    baseline = rp.prioritize(copy.deepcopy(tasks), None, {"minutes": 20}, EVAL_AT)
    reversed_order = rp.prioritize(list(reversed(copy.deepcopy(tasks))), None, {"minutes": 20}, EVAL_AT)
    reread = rp.prioritize(copy.deepcopy(tasks) + copy.deepcopy(tasks), None, {"minutes": 20}, EVAL_AT)

    assert baseline == reversed_order
    for key in ("id", "input_digest", "selected", "deferred", "blocked", "critical_not_selected_ids"):
        assert baseline[key] == reread[key], key
    assert reread["totals"]["input_count"] == 12 and reread["totals"]["candidate_count"] == baseline["totals"]["candidate_count"]
    # 每个去重后的候选恰好在三组之一。
    all_ids = _ids(baseline["selected"]) + _ids(baseline["deferred"]) + _ids(baseline["blocked"])
    assert len(all_ids) == len(set(all_ids)) == baseline["totals"]["candidate_count"]


# ---------------------------------------------------------------------------
# 解释卫生与投影
# ---------------------------------------------------------------------------


def test_reasons_are_generated_from_facts_and_never_promise_returns():
    report = rp.prioritize([_abandon("ab", "j_ab", effort=_effort(2)), _task("ex", effort=_effort(1))], None, {"minutes": 5}, EVAL_AT)
    joined = "\n".join(reason for row in report["selected"] for reason in row["reasons"])
    # 不编数、也不荐股：理由与限制里不得出现收益/概率承诺或任何方向性买卖措辞（不荐股只约束渲染输出，scope 不过滤个股）。
    for forbidden in ("概率", "预期收益", "胜率", "%", "买入", "卖出", "加仓", "减仓", "建议持有", "目标价"):
        assert forbidden not in joined, forbidden
    assert any("不构成任何个股买卖建议" in text for text in report["limitations"])
    first = report["selected"][0]["reasons"]
    assert first[0].startswith("第 1 组")
    assert any(text.startswith("依赖判断：judgment:j_ab") for text in first)
    assert any(text.startswith("需要做：") for text in first)
    assert any(text.startswith("结束条件：") for text in first)
    assert any("预算：选入后剩余" in text for text in first)


def test_render_keeps_every_reason_and_click_payload():
    tasks = [_abandon("ab", "j_ab"), _task("wait", availability=c.AVAIL_MISSING_PERMISSION, availability_reason="需开通研报库权限")]
    report = rp.prioritize(tasks, None, None, EVAL_AT)
    view = rp.render_view(report)
    assert view["schema_version"] == c.SCHEMA_VIEW
    assert view["selected"][0]["为什么在前"] == report["selected"][0]["reasons"]
    payload = view["selected"][0]["click_payload"]
    assert payload["task_id"] == report["selected"][0]["task"]["id"]
    assert payload["conversation_id"] == "conv_1"
    assert payload["source_refs"] == report["selected"][0]["task"]["merged_source_refs"]
    assert view["blocked"][0]["解除条件"] == "需开通研报库权限"
    markdown = rp.render_markdown(report)
    assert "## 入选" in markdown and "## 等待区" in markdown and "需开通研报库权限" in markdown
    assert "synthetic" not in markdown  # 没有夹具标记就不能冒出「synthetic」
    # 09-06 终局 §4.5：限制与缺口排在事实块之前。
    assert markdown.index("## 限制与缺口") < markdown.index("## 入选")
    assert "hindsight" not in markdown  # 没有 hindsight 来源就不提它


def test_hindsight_source_is_flagged_isolated_and_never_hidden():
    live = _task(
        "live",
        effect=c.EFFECT_REVIEW_CHANGED,
        objects=(_ref("judgment", "j_h"),),
        evidence=(_ref("evidence", "e_h", namespace="announcement", version="h1"),),
    )
    replay = dict(copy.deepcopy(live), id="replay", hindsight=True, source=_ref("test_source", "replay", namespace="tests", version="s1"))
    # 同对象两项都要入选才都有 reasons，放宽 max_per_object。
    report = rp.prioritize([live, replay], {"max_per_object": 2}, None, EVAL_AT)
    # 同证据但一条是 hindsight 回放：不合并，两条都可见；普通任务的 id 不受 hindsight 字段影响。
    assert report["totals"]["candidate_count"] == 2 and len(report["selected"]) == 2
    assert report["hindsight"] is True
    live_only = rp.prioritize([copy.deepcopy(live)], None, None, EVAL_AT)
    assert live_only["hindsight"] is False
    live_id = live_only["selected"][0]["task"]["id"]
    ids = {row["task"]["id"]: row for row in report["selected"] + report["deferred"]}
    assert live_id in ids and ids[live_id]["task"]["hindsight"] is False
    replay_row = next(row for tid, row in ids.items() if tid != live_id)
    assert replay_row["task"]["hindsight"] is True
    assert any("hindsight" in text for text in (replay_row.get("reasons") or [replay_row.get("detail", "")]))
    assert any(text.startswith("含 hindsight 回放来源") for text in report["limitations"])
    assert any(g["reason"] == "hindsight_source" and g["task_ids"] == [replay_row["task"]["id"]] for g in report["gaps"])
    view = rp.render_view(report)
    assert view["hindsight"] is True
    assert "hindsight 回放来源" in rp.render_markdown(report)
    with pytest.raises(c.ContractError) as excinfo:
        rp.prioritize([dict(live, hindsight="yes")], None, None, EVAL_AT)
    assert excinfo.value.code == "invalid_task"


def test_frozen_llm_evidence_is_labelled_in_reasons():
    prose = _task(
        "prose",
        effect=c.EFFECT_REVIEW_CHANGED,
        objects=(_ref("judgment", "j_p"),),
        evidence=(_ref("evidence", "narrative:refrigerant:v3", namespace="frozen_llm", version="h_n3"),),
    )
    report = rp.prioritize([prose], None, None, EVAL_AT)
    assert any("frozen_llm 散文：可读不可重算" in text for text in report["selected"][0]["reasons"])
    # 分组不因散文而改变：仍是第 2 组的复核任务，不进第 1 组。
    assert report["selected"][0]["group"] == c.GROUP_REVIEW_CHANGED


def test_policy_and_budget_validation():
    with pytest.raises(c.ContractError) as excinfo:
        rp.prioritize([], {"policy_version": "research-priority-policy/v9"}, None, EVAL_AT, owner_user_id=OWNER)
    assert excinfo.value.code == "unknown_policy"
    with pytest.raises(c.ContractError) as excinfo:
        rp.prioritize([], None, {"minutes": -1}, EVAL_AT, owner_user_id=OWNER)
    assert excinfo.value.code == "invalid_budget"
    with pytest.raises(c.ContractError) as excinfo:
        rp.prioritize([], {"max_items": -1}, None, EVAL_AT, owner_user_id=OWNER)
    assert excinfo.value.code == "invalid_policy"
