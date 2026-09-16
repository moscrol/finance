"""02 · 只读适配验收（spec §7 P02 / P06 / P09 / P11 / P12 + 四种来源映射）。

来源全部走真实对象：research_queue 用现役 ``build_research_queue`` 生成；data_requests 用
``DataRequest`` 数据类；research_project 用 ``ResearchProjectState`` / ``ResearchTrigger``；
01 目前只有合同夹具（synthetic），真输出联测见 PROGRESS / BLOCKED。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from intelligence.services import data_requests as dr
from intelligence.services import research_priority as rp
from intelligence.services import research_queue as rq
from intelligence.services.research_priority import contracts as c
from intelligence.services.research_project import ResearchProjectState, ResearchTrigger

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "research_evolution" / "02"
OWNER = "u_test"
EVAL_AT = "2026-09-13T02:00:00Z"
CONTEXT = {"owner_user_id": OWNER, "synthetic": True, "as_of": "2026-09-12", "knowledge_cutoff": "2026-09-12T15:30:00+08:00"}


def _load(name: str) -> dict[str, Any]:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert payload.get("synthetic") is True, "夹具必须标 synthetic"
    return payload


def _maintenance_record() -> dict[str, Any]:
    return {"kind": rp.SOURCE_MAINTENANCE_REPORT, "payload": _load("maintenance_report_synthetic.json")}


def _queue_record() -> dict[str, Any]:
    fixture = _load("research_queue_decision_synthetic.json")
    queue = rq.build_research_queue(fixture["decision"])  # 现役函数，真实生成
    artifact = rq.wrap_research_queue_artifact(queue, date=fixture["date"], generated_at="2026-09-12T22:00:00+08:00")
    return {"kind": rp.SOURCE_RESEARCH_QUEUE, "payload": artifact}


def _data_request_records() -> list[dict[str, Any]]:
    fixture = _load("data_requests_synthetic.json")
    return [{"kind": rp.SOURCE_DATA_REQUEST, "payload": dr.DataRequest(**row)} for row in fixture["requests"]]


def _project_record() -> dict[str, Any]:
    state = _load("research_project_state_synthetic.json")
    triggers = tuple(ResearchTrigger(**{k: (tuple(v) if k == "themes" else v) for k, v in t.items()}) for t in state["triggers"])
    project = ResearchProjectState(
        conversation_id=state["conversation_id"],
        user_id=state["user_id"],
        title=state["title"],
        subject=state["subject"],
        question_type=state["question_type"],
        as_of=state["as_of"],
        updated_at=state["updated_at"],
        current_judgment=state["current_judgment"],
        open_questions=tuple(state["open_questions"]),
        triggers=triggers,
        next_questions=tuple(state["next_questions"]),
        prior_status=state["prior_status"],
        prior_note=state["prior_note"],
    )
    return {"kind": rp.SOURCE_RESEARCH_PROJECT, "payload": project}


def _task_by_source(tasks: list[dict[str, Any]], source_id: str) -> dict[str, Any]:
    for task in tasks:
        if any(r["id"] == source_id for r in task["merged_source_refs"]):
            return task
    raise AssertionError(f"没有来源 {source_id} 的任务")


def _section_of(report: dict[str, Any], source_id: str) -> tuple[str, dict[str, Any]]:
    for section in ("selected", "deferred", "blocked"):
        for row in report[section]:
            if any(r["id"] == source_id for r in row["task"]["merged_source_refs"]):
                return section, row
    raise AssertionError(f"来源 {source_id} 不在任何一组")


# ---------------------------------------------------------------------------
# 01 合同夹具 → P02 / P06 / P12
# ---------------------------------------------------------------------------


def test_p02_hash_only_change_becomes_review_not_abandon():
    candidates = rp.adapt_candidates([_maintenance_record()], CONTEXT)
    task = _task_by_source(candidates["tasks"], "mi_002_hash_only")
    assert task["effect_kind"] == c.EFFECT_REVIEW_CHANGED
    assert task["condition_result"] is None
    report = rp.prioritize(candidates, None, None, EVAL_AT)
    section, row = _section_of(report, "mi_002_hash_only")
    assert section == "selected" and row["group"] == c.GROUP_REVIEW_CHANGED
    # 第 1 组只能是 mi_001（condition_true + role=abandon）；同样 condition_true 但 role=upgrade 的 mi_010 是第 3 组。
    assert [row["task"]["maintenance_item_ids"] for row in report["selected"] if row["group"] == c.GROUP_ABANDON] == [["mi_001_abandon_true"]]
    assert _section_of(report, "mi_010_upgrade_true")[1]["group"] == c.GROUP_VERIFY_DUE


def test_p06_same_evidence_across_three_maintenance_items_merges_with_all_objects():
    candidates = rp.adapt_candidates([_maintenance_record()], CONTEXT)
    report = rp.prioritize(candidates, None, None, EVAL_AT)
    section, row = _section_of(report, "mi_003_same_evidence")
    task = row["task"]
    assert sorted(task["maintenance_item_ids"]) == ["mi_002_hash_only", "mi_003_same_evidence", "mi_004_same_evidence_again"]
    assert sorted(r["id"] for r in task["object_refs"]) == ["j_beta", "j_delta", "j_gamma"]
    assert len(task["merged_source_refs"]) == 3
    assert "mi_003_same_evidence" in task["completion_condition"] and "mi_004_same_evidence_again" in task["completion_condition"]
    # 一条来源 claimed、两条 open → 合成项不算 snoozed，正常入选。
    assert section == "selected" and task["management_status"] in ("claimed", "open")


def test_p12_unknown_and_gaps_survive_and_every_item_reconciles():
    fixture = _load("maintenance_report_synthetic.json")
    candidates = rp.adapt_candidates([{"kind": rp.SOURCE_MAINTENANCE_REPORT, "payload": fixture}], CONTEXT)
    report = rp.prioritize(candidates, None, None, EVAL_AT)

    section, row = _section_of(report, "mi_005_condition_unknown")
    assert section == "blocked" and row["reason"] == c.AVAIL_MISSING_DATA
    assert row["task"]["condition_result"] == c.CONDITION_UNKNOWN
    assert row["task"]["effect_kind"] == c.EFFECT_VERIFY_DUE  # unknown 不升为触发
    assert {g["reason"] for g in row["task"]["gaps"]} == {"ref_unresolved"}
    assert row["task"]["gaps"][0]["ref"] == "price:000001:close"
    assert "ref_unresolved（price:000001:close）" in row["release_condition"]

    section, row = _section_of(report, "mi_006_dependency_missing")
    assert row["task"]["effect_kind"] == c.EFFECT_FILL_GAP and row["group"] == c.GROUP_FILL_GAP

    section, row = _section_of(report, "mi_011_abandon_true_snoozed")
    assert section == "deferred" and row["reason"] == c.DEFER_USER_SNOOZED
    assert row["task"]["id"] in report["critical_not_selected_ids"]

    # 对账：夹具里每个 item 要么进了某个任务的 maintenance_item_ids，要么在 skipped 里，且不重复。
    covered = {mid for t in candidates["tasks"] for mid in t["maintenance_item_ids"]}
    skipped = {s["source"]["id"]: s["reason"] for s in candidates["skipped"]}
    assert not covered & set(skipped)
    assert covered | set(skipped) == {item["id"] for item in fixture["items"]}
    assert skipped == {
        "mi_007_unchanged": "no_change",
        "mi_008_condition_false": "condition_false",
        "mi_009_closed": "management_status_closed",
    }
    assert report["synthetic"] is True and candidates["synthetic"] is True
    all_ids = [row["task"]["id"] for section in ("selected", "deferred", "blocked") for row in report[section]]
    assert len(all_ids) == len(set(all_ids)) == report["totals"]["candidate_count"]


def test_condition_task_keeps_its_observation_window_across_two_01_reports():
    """评审 P1（适配侧）：同一 binding/condition 在两个观测窗口的 01 报告不得并成一条。

    01 的 dedup_key 含「条件/观测窗口」，02 必须保持同一口径：当天那份仍进第 1 组，
    未来那份单独 blocked(future_record)，不把当天的关键条件一起拖走。
    """
    today = _load("maintenance_report_synthetic.json")
    tomorrow = copy.deepcopy(today)
    tomorrow["id"] = "mr_synth_0914"
    tomorrow["as_of"] = "2026-09-14"
    tomorrow["knowledge_cutoff"] = "2026-09-14T15:30:00+08:00"
    for item in tomorrow["items"]:
        item["id"] = item["id"] + "_0914"
        item["as_of"] = "2026-09-14"
        item["knowledge_cutoff"] = "2026-09-14T15:30:00+08:00"

    candidates = rp.adapt_candidates(
        [
            {"kind": rp.SOURCE_MAINTENANCE_REPORT, "payload": today},
            {"kind": rp.SOURCE_MAINTENANCE_REPORT, "payload": tomorrow},
        ],
        CONTEXT,
    )
    report = rp.prioritize(candidates, None, None, EVAL_AT)

    today_section, today_row = _section_of(report, "mi_001_abandon_true")
    future_section, future_row = _section_of(report, "mi_001_abandon_true_0914")
    assert today_section == "selected" and today_row["group"] == c.GROUP_ABANDON
    assert future_section == "blocked" and future_row["reason"] == c.BLOCK_FUTURE_RECORD
    assert today_row["task"]["id"] != future_row["task"]["id"]
    assert today_row["task"]["maintenance_item_ids"] == ["mi_001_abandon_true"]
    assert future_row["task"]["maintenance_item_ids"] == ["mi_001_abandon_true_0914"]

    # 条件证据引用带上观测窗口，06/04 能看出这条 condition 取自哪一次观测。
    condition_ref = next(
        r for r in today_row["task"]["effect_evidence_refs"] if r["kind"] == "condition" and r["id"] == "cond_abandon_alpha"
    )
    assert condition_ref["namespace"] == "binding:b_alpha"
    assert condition_ref["scope"]["as_of"] == "2026-09-12"
    assert condition_ref["scope"]["knowledge_cutoff"] == "2026-09-12T15:30:00+08:00"


def test_maintenance_report_of_another_owner_is_rejected():
    fixture = _load("maintenance_report_synthetic.json")
    with pytest.raises(c.ContractError) as excinfo:
        rp.adapt_candidates([{"kind": rp.SOURCE_MAINTENANCE_REPORT, "payload": fixture}], {**CONTEXT, "owner_user_id": "u_someone"})
    assert excinfo.value.code == "owner_mismatch"
    single = copy.deepcopy(fixture["items"][0])
    single["owner_user_id"] = "u_other"
    with pytest.raises(c.ContractError) as excinfo:
        rp.adapt_candidates([{"kind": rp.SOURCE_MAINTENANCE_ITEM, "payload": single}], CONTEXT)
    assert excinfo.value.code == "owner_mismatch"
    assert "u_other" not in str(excinfo.value)
    with pytest.raises(c.ContractError) as excinfo:
        rp.adapt_candidates([{"kind": "chat_log", "payload": {}}], CONTEXT)
    assert excinfo.value.code == "unknown_source_kind"
    with pytest.raises(c.ContractError) as excinfo:
        rp.adapt_candidates([{"kind": rp.SOURCE_MAINTENANCE_REPORT, "payload": {**fixture, "schema_version": "judgment-maintenance/v2"}}], CONTEXT)
    assert excinfo.value.code == "unknown_schema"


def test_hindsight_flag_of_01_report_propagates_to_every_task():
    fixture = _load("maintenance_report_synthetic.json")
    assert fixture["hindsight"] is False
    live = rp.adapt_candidates([{"kind": rp.SOURCE_MAINTENANCE_REPORT, "payload": fixture}], CONTEXT)
    assert {t["hindsight"] for t in live["tasks"]} == {False}
    replay_fixture = copy.deepcopy(fixture)
    replay_fixture["hindsight"] = True
    replay = rp.adapt_candidates([{"kind": rp.SOURCE_MAINTENANCE_REPORT, "payload": replay_fixture}], CONTEXT)
    assert replay["tasks"] and {t["hindsight"] for t in replay["tasks"]} == {True}
    report = rp.prioritize(replay, None, None, "2026-09-12T10:00:00Z")  # 历史重放：显式给历史评估时刻
    assert report["hindsight"] is True
    assert any(text.startswith("含 hindsight 回放来源") for text in report["limitations"])
    # 回放任务与同证据的当前任务 id 不同，不会互相顶替。
    live_ids = {t["id"] for t in live["tasks"]}
    assert live_ids.isdisjoint({t["id"] for t in replay["tasks"]})


def test_effort_estimates_from_context_attach_by_source():
    context = {**CONTEXT, "effort_estimates": {"maintenance_item:mi_001_abandon_true": {"seconds": 600, "kind": "user_estimate", "source_ref": "user:2026-09-13"}}}
    candidates = rp.adapt_candidates([_maintenance_record()], context)
    task = _task_by_source(candidates["tasks"], "mi_001_abandon_true")
    assert task["effort"] == {"seconds": 600.0, "kind": "user_estimate", "source_ref": "user:2026-09-13"}
    report = rp.prioritize(candidates, None, {"minutes": 10}, EVAL_AT)
    assert report["selected"][0]["task"]["id"] == task["id"] and report["selected"][0]["estimated_seconds"] == 600.0
    assert len(report["selected"]) == 1  # 其余耗时未知，不塞进有限预算
    assert {row["reason"] for row in report["deferred"]} <= {c.DEFER_EFFORT_UNKNOWN, c.DEFER_USER_SNOOZED}


# ---------------------------------------------------------------------------
# P11 · 现役研究队列 → legacy_unbound 第 5 组
# ---------------------------------------------------------------------------


def test_p11_legacy_queue_without_object_refs_is_unbound_group_five():
    record = _queue_record()
    queue = record["payload"]["research_queue"]
    # 现役分类结果：IMA / 找官方证据 / 等盘面 / 降级各一，量子计算因 missing_concept 被队列自己跳过。
    assert queue["summary"]["total"] == 4 and queue["summary"]["skipped"] == 1
    assert [item["目标"] for item in queue[rq.QUEUE_DOWNGRADE]] == ["光伏玻璃"]
    candidates = rp.adapt_candidates([record], CONTEXT)
    assert candidates["tasks"] and all(t["legacy_unbound"] and not t["object_refs"] for t in candidates["tasks"])
    report = rp.prioritize(candidates, None, None, EVAL_AT)
    groups = {row["group"] for section in ("selected", "deferred") for row in report[section]}
    assert groups == {c.GROUP_EXPLORE}
    assert report["critical_not_selected_ids"] == []
    # 「等盘面验证」进等待区；「降级/观察」与 data_gap 不生成任务但可对账。
    section, row = _section_of(report, "2026-09-12:today_wait_market_validation:低空经济")
    assert section == "blocked" and row["reason"] == c.AVAIL_WAITING_RELEASE and row["release_condition"].startswith("等盘面验证：")
    reasons = {s["source"]["id"]: s["reason"] for s in candidates["skipped"]}
    assert reasons["2026-09-12:today_downgrade_or_watch:光伏玻璃"] == "downgrade_observe_only"
    assert reasons["2026-09-12:skipped.data_gap_or_unconfirmed:量子计算"] == "queue_skipped:data_gap_or_unconfirmed"
    for task in candidates["tasks"]:
        assert task["human_review_required"] is True  # 队列的完成条件是散文
        assert task["pit_grade"] == "trade_date_only" and task["as_of"] == "2026-09-12"
        assert any(g["reason"] == "legacy_unbound" for g in report["gaps"])


def test_queue_heat_score_is_never_read():
    hot = _queue_record()
    cold = copy.deepcopy(hot)
    for bucket in rq.ACTION_LABELS:
        for item in cold["payload"]["research_queue"][bucket]:
            item["优先级"] = 0.0
    report_hot = rp.prioritize(rp.adapt_candidates([hot], CONTEXT), None, None, EVAL_AT)
    report_cold = rp.prioritize(rp.adapt_candidates([cold], CONTEXT), None, None, EVAL_AT)
    # 优先级字段进了内容 hash（来源版本），任务 id 与顺序却完全一样。
    assert [r["task"]["question"] for r in report_hot["selected"]] == [r["task"]["question"] for r in report_cold["selected"]]
    assert [r["task"]["id"] for r in report_hot["selected"]] == [r["task"]["id"] for r in report_cold["selected"]]


# ---------------------------------------------------------------------------
# research_project 投影
# ---------------------------------------------------------------------------


def test_research_project_triggers_and_followups():
    candidates = rp.adapt_candidates([_project_record()], CONTEXT)
    report = rp.prioritize(candidates, {"max_items": 10}, None, EVAL_AT)

    section, row = _section_of(report, "conv_1#checkpoint:cp_due_0911")
    assert section == "selected" and row["group"] == c.GROUP_VERIFY_DUE
    assert row["task"]["object_refs"][0] == {"kind": "checkpoint", "id": "cp_due_0911", "namespace": "checkpoints", "version_or_hash": None, "scope": {"conversation_id": "conv_1"}}
    assert row["task"]["condition_result"] == c.CONDITION_UNKNOWN and row["task"]["human_review_required"] is False
    assert {g["reason"] for g in row["task"]["gaps"]} == {"object_version_unknown"}

    section, row = _section_of(report, "conv_1#checkpoint:cp_pending_0920")
    assert section == "blocked" and row["reason"] == c.BLOCK_NOT_YET_DUE and row["available_at"] == "2026-09-20"

    section, row = _section_of(report, "conv_1#checkpoint:cp_unv_0910")
    assert section == "selected" and row["task"]["human_review_required"] is True

    skipped = {s["source"]["id"]: s["reason"] for s in candidates["skipped"]}
    assert skipped["conv_1#checkpoint:cp_hit_0905"] == "verdict_recorded"
    assert [reason for reason in skipped.values() if reason == "duplicate_open_question"] == ["duplicate_open_question"]

    followups = [t for t in candidates["tasks"] if "#followup:" in t["source"]["id"] or "#open_question:" in t["source"]["id"]]
    assert len(followups) == 3
    assert all(t["legacy_unbound"] and t["human_review_required"] for t in followups)
    assert {t["effect_kind"] for t in followups} == {c.EFFECT_EXPLORE, c.EFFECT_FILL_GAP}
    assert all(t["scope"]["conversation_id"] == "conv_1" and t["scope"]["entity_refs"] == ["theme:制冷剂"] for t in followups)
    # 到期已过的两个 checkpoint（第 3 组）按到期日早→晚排在所有未绑定探索项（第 5 组）前面。
    assert [row["task"]["source"]["id"] for row in report["selected"][:2]] == [
        "conv_1#checkpoint:cp_unv_0910",
        "conv_1#checkpoint:cp_due_0911",
    ]
    assert [row["group"] for row in report["selected"]] == [c.GROUP_VERIFY_DUE, c.GROUP_VERIFY_DUE] + [c.GROUP_EXPLORE] * 3

    with pytest.raises(c.ContractError) as excinfo:
        rp.adapt_candidates([_project_record()], {**CONTEXT, "owner_user_id": "u_x"})
    assert excinfo.value.code == "owner_mismatch"


# ---------------------------------------------------------------------------
# data_requests.DataRequest
# ---------------------------------------------------------------------------


def test_data_requests_map_to_fill_gap_with_route_aware_availability():
    candidates = rp.adapt_candidates(_data_request_records(), CONTEXT)
    report = rp.prioritize(candidates, None, None, EVAL_AT)

    section, row = _section_of(report, "dr-aaaaaaaaaa")
    assert section == "selected" and row["group"] == c.GROUP_EXPLORE  # 未绑定判断 → 第 5 组
    task = row["task"]
    assert task["effect_kind"] == c.EFFECT_FILL_GAP and task["legacy_unbound"] is True
    assert task["question"] == "补齐 sector_daily 2026-09-08..2026-09-12 的 pct_chg、amount"
    assert "check_request 判 satisfied" in task["completion_condition"] and task["human_review_required"] is False
    assert task["as_of"] == "2026-09-12" and task["knowledge_cutoff"] == "2026-09-12T21:00:00+08:00"
    assert task["scope"] == {"conversation_id": "conv_1", "entity_refs": ["dataset:sector_daily"]}

    section, row = _section_of(report, "dr-bbbbbbbbbb")
    assert section == "blocked" and row["reason"] == c.AVAIL_MISSING_DATA
    assert row["release_condition"].startswith("题材资金流：pending_sync")

    skipped = {s["source"]["id"]: s for s in candidates["skipped"]}
    assert skipped["dr-cccccccccc"]["reason"] == "no_owner_consumer"
    assert "u_other" not in json.dumps(candidates, ensure_ascii=False)

    # 调用方显式给绑定，才算绑定到判断：进第 4 组。
    bound = rp.adapt_candidates(
        _data_request_records(),
        {**CONTEXT, "request_bindings": {"dr-aaaaaaaaaa": [{"kind": "judgment", "id": "j_flow", "namespace": "judgments", "version_or_hash": "v1", "scope": None}]}},
    )
    bound_report = rp.prioritize(bound, None, None, EVAL_AT)
    section, row = _section_of(bound_report, "dr-aaaaaaaaaa")
    assert row["group"] == c.GROUP_FILL_GAP and row["task"]["legacy_unbound"] is False

    satisfied = rp.adapt_candidates([{"kind": rp.SOURCE_DATA_REQUEST, "payload": _data_request_records()[0]["payload"], "status": dr.STATUS_SATISFIED}], CONTEXT)
    assert satisfied["tasks"] == [] and satisfied["skipped"][0]["reason"] == "already_satisfied"


def test_p12_real_01_assess_output_flows_through_unchanged():
    """01 在途模块的真实 ``assess()`` 产物（合成输入）→ 02，零适配改动。

    与手写夹具的差别：01 真输出的 condition_result 是字符串、knowledge_cutoff 是日期、
    gaps / item 带 02 不认识的额外字段（dependency_ref、condition_evaluation、management…），
    这些都必须被接受而不是拒绝。01 定稿后用其最终 revision 重跑并替换夹具（见 PROGRESS）。
    """
    wrapped = _load("from_01_inflight_assess_report_synthetic.json")
    report01 = wrapped["report"]
    assert report01["schema_version"] == "judgment-maintenance/v1" and wrapped["_provenance"]["producer"].startswith("intelligence.services.judgment_maintenance.assess")
    assert isinstance(report01["knowledge_cutoff"], str) and len(report01["knowledge_cutoff"]) == 10  # 日期粒度，不补假时分
    owner = report01["owner_user_id"]
    candidates = rp.adapt_candidates([{"kind": rp.SOURCE_MAINTENANCE_REPORT, "payload": report01}], {"owner_user_id": owner, "synthetic": True})
    report = rp.prioritize(candidates, None, None, EVAL_AT)

    by_change = {item["change_type"] + ":" + item["reason_code"] + ":" + item["status"]: item["id"] for item in report01["items"]}
    downgrade_true = by_change["condition_evaluated:condition_true:open"]
    section, row = _section_of(report, downgrade_true)
    assert section == "selected" and row["group"] == c.GROUP_ABANDON
    assert row["task"]["condition_result"] is True and row["task"]["effect_kind"] == c.EFFECT_ABANDON
    assert any(r["kind"] == "condition" for r in row["task"]["effect_evidence_refs"])

    skipped = {s["source"]["id"]: s["reason"] for s in candidates["skipped"]}
    assert skipped[by_change["condition_evaluated:condition_false:open"]] == "condition_false"
    assert skipped[by_change["source_expired:validity_ended:superseded"]] == "management_status_superseded"

    for key in ("content_changed:hash_changed:open", "source_corrected:explicit_supersession:open"):
        section, row = _section_of(report, by_change[key])
        assert row["task"]["effect_kind"] == c.EFFECT_REVIEW_CHANGED and row["group"] == c.GROUP_REVIEW_CHANGED
        assert section == "deferred" and row["reason"] == c.DEFER_PER_OBJECT  # 同一判断默认只留一项
    assert report["critical_not_selected_ids"] == []

    covered = {mid for t in candidates["tasks"] for mid in t["maintenance_item_ids"]} | set(skipped)
    assert covered == {item["id"] for item in report01["items"]}
    assert report["synthetic"] is True
    # 01 的 pit_grade / as_of 原样透传，不被 02 改写。
    assert {t["pit_grade"] for t in candidates["tasks"]} == {report01["pit_grade"]}
    assert {t["as_of"] for t in candidates["tasks"]} == {report01["as_of"]}


# ---------------------------------------------------------------------------
# 四源合并的冻结输出
# ---------------------------------------------------------------------------


def _combined_report() -> dict[str, Any]:
    records = [_maintenance_record(), _project_record(), _queue_record(), *_data_request_records()]
    return rp.prioritize(rp.adapt_candidates(records, CONTEXT), None, None, EVAL_AT)


def test_combined_sources_match_frozen_golden():
    report = _combined_report()
    golden = _load("expected_combined_synthetic.json")
    actual = {
        "synthetic": True,
        "input_digest": report["input_digest"],
        "report_id": report["id"],
        "totals": report["totals"],
        "selected": [(row["rank"], row["group"], row["task"]["id"], sorted(r["id"] for r in row["task"]["merged_source_refs"])) for row in report["selected"]],
        "deferred": [(row["reason"], row["task"]["id"]) for row in report["deferred"]],
        "blocked": [(row["reason"], row["task"]["id"]) for row in report["blocked"]],
        "critical_not_selected_ids": report["critical_not_selected_ids"],
    }
    expected = {
        "synthetic": golden["synthetic"],
        "input_digest": golden["input_digest"],
        "report_id": golden["report_id"],
        "totals": golden["totals"],
        "selected": [tuple(x[:3]) + (x[3],) for x in golden["selected"]],
        "deferred": [tuple(x) for x in golden["deferred"]],
        "blocked": [tuple(x) for x in golden["blocked"]],
        "critical_not_selected_ids": golden["critical_not_selected_ids"],
    }
    assert actual == expected
    # 冻结场景本身也要能说得通：第 1 组是放弃条件、第 2 组是三判断共用证据、等待区四类原因各一。
    assert [row["group"] for row in report["selected"]] == [c.GROUP_ABANDON, c.GROUP_REVIEW_CHANGED, c.GROUP_VERIFY_DUE]
    assert sorted(row["reason"] for row in report["blocked"]) == [c.AVAIL_MISSING_DATA, c.AVAIL_MISSING_DATA, c.BLOCK_NOT_YET_DUE, c.AVAIL_WAITING_RELEASE]
    # task_id 是 identity_key 的内容寻址结果，合并口径一变整批都会变；再钉一层「与 id 无关」的
    # 落位，这样 golden 因 id 漂移而重生成时，语义回归不会跟着一起被放过。
    assert sorted((row["reason"], tuple(sorted(r["id"] for r in row["task"]["merged_source_refs"]))) for row in report["blocked"]) == [
        (c.AVAIL_MISSING_DATA, ("dr-bbbbbbbbbb",)),
        (c.AVAIL_MISSING_DATA, ("mi_005_condition_unknown",)),
        (c.BLOCK_NOT_YET_DUE, ("conv_1#checkpoint:cp_pending_0920",)),
        (c.AVAIL_WAITING_RELEASE, ("2026-09-12:today_wait_market_validation:低空经济",)),
    ]
