"""判断持续维护 · 只读集成（spec 01 §7 第 4 步）：旧读取器 → 适配 → assess，旧文件字节不变。

用真实写入者（judgments.record_judgment / checkpoints.register_checkpoint / record_verdict /
scenario_trees.register）在临时目录造样本，再用旧读取器加载、适配成合同对象跑报告。
临时目录以外不读任何东西；用户态根用 FORESIGHT_USERS_DIR 指到 tmp，不碰真实 users/。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from intelligence import userspace
from intelligence.services import checkpoints, judgments
from intelligence.services import scenario_trees as st
from intelligence.services import judgment_maintenance as jm
from intelligence.services.judgment_maintenance import adapters

OWNER = "tmp-owner"
AS_OF = "2026-09-12"
CREATED_AT = "2026-09-12T20:00:00+08:00"
HASH = "cp:0123456789abcdef"


def _script(**over) -> dict:
    base = {"variables": ["盘面轨：指数阶段、成交与边际量是否延续"], "downgrade_or_abandon_conditions": ["盘面轨该实体的量价对象消失或转为缺口"]}
    base.update(over)
    return base


def _tree_spec() -> dict:
    return {
        "as_of": "2026-09-01",
        "scope": "index",
        "entity_ids": ["上证指数"],
        "max_depth": 2,
        "framework_version": "tf-v0.2",
        "model_id": "m",
        "projection_hash": HASH,
        "user_id": OWNER,
        "nodes": [
            {"node_id": "root", "depth": 0, "parent": None, "condition": None, "script": _script()},
            {"node_id": "a", "depth": 1, "parent": "root", "step_kind": "T+1", "condition": {"all": [{"label": "market_stage", "op": "in", "value": ["反弹"]}]}, "script": _script()},
            {"node_id": "z", "depth": 1, "parent": "root", "step_kind": "T+1", "condition": "otherwise", "script": _script()},
        ],
    }


@pytest.fixture()
def ledgers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """真实写入者写出的三本台账 + 一行 foresight 形状的判断 + 一行无 id 的存量判断。"""
    monkeypatch.setenv(userspace.ENV_USERS_DIR, str(tmp_path / "users"))
    us = userspace.user_space(OWNER)
    us.ensure_dir()
    assert us.root.is_relative_to(tmp_path)
    _, judgment = judgments.record_judgment(us.judgments_path, memo="示例核心判断：板块轮动仍在反弹段", themes=["半导体"], ts="2026-09-01T10:00:00+08:00")
    # foresight 判断行的形状（judgment_extract 写入者）：带 evidence[{ref,hash}] 与自然语言 invalidation
    structured = {
        "ts": "2026-09-02T10:00:00+08:00",
        "id": "j-structured-1",
        "record_type": "foresight_judgment",
        "status": "accepted",
        "memo": "示例：题材进入主升需放量确认",
        "claim": "示例：题材进入主升需放量确认",
        "evidence": [
            {"ref": "fact_market_daily:2026-09-01", "hash": "h-a1"},
            {"ref": "fact_research_report_catalog:r-77", "hash": None},
        ],
        "invalidation": "若连续三日缩量则放弃",
        "context_snapshot": {"query": "示例问题", "as_of": "2026-09-01"},
    }
    legacy = {"memo": "老行：无 id、无 ts", "themes": ["示例"]}
    with us.judgments_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(structured, ensure_ascii=False) + "\n")
        fh.write(json.dumps(legacy, ensure_ascii=False) + "\n")
    _, ck = checkpoints.register_checkpoint(
        us.checkpoints_path,
        claim="示例可证伪点",
        due="2026-09-15",
        category="估值切换",
        themes=["半导体"],
        ts="2026-09-01T10:00:00",
        source_judgment_ts=judgment["ts"],
        session_id="sess-1",
        metric={"type": "market_daily", "conditions": ["advancers>=3000"]},
    )
    checkpoints.record_verdict(us.verdicts_path, id=ck["id"], verdict="unverifiable", reason="数据未到", checked_at="2026-09-10T20:00:00")
    checkpoints.record_verdict(us.verdicts_path, id=ck["id"], verdict="hit", reason="达标", checked_at="2026-09-15T20:00:00")
    tree = st.ensure_valid(_tree_spec())
    trees_path = st.trees_path(us)
    _, tree_rec = st.register(trees_path, tree, checkpoints_path=us.checkpoints_path, recorded_at="2026-09-01T18:00:00+08:00")
    step = st.ResolutionStep(tree_rec["id"], "2026-09-02", "root", "a", "resolving", ("fact_market_daily:2026-09-02",), "cp:step", {"all": [{"label": "market_stage", "op": "in", "value": ["反弹"]}]}, "命中")
    st.append_step(trees_path, step)
    files = [us.judgments_path, us.checkpoints_path, us.verdicts_path, trees_path]
    digests = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    return {"us": us, "files": files, "digests": digests, "judgment": judgment, "checkpoint": ck, "tree_id": tree_rec["id"]}


def _digests(files: list[Path]) -> dict:
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def test_old_readers_to_report_leaves_ledgers_byte_identical(ledgers):
    us = ledgers["us"]
    loaded_judgments, warn = judgments.load_judgments(us.judgments_path, window=0)
    assert warn is None
    loaded_checkpoints, _ = checkpoints.load_checkpoints(us.checkpoints_path)
    loaded_verdicts, _ = checkpoints.load_verdicts(us.verdicts_path)
    tree_records = st.load(st.trees_path(us))
    state = st.current_state(tree_records, ledgers["tree_id"])
    assert state is not None and state["realized_path"][-1]["node_id"] == "a"

    structured = next(r for r in loaded_judgments if r.get("id") == "j-structured-1")
    plain = next(r for r in loaded_judgments if r.get("id") == ledgers["judgment"]["id"])
    legacy = next(r for r in loaded_judgments if not r.get("id"))
    ck = next(r for r in loaded_checkpoints if r["id"] == ledgers["checkpoint"]["id"])

    bindings: list[jm.DependencyBinding] = []
    gaps: list[jm.Gap] = []
    b1, g1 = adapters.candidate_binding_from_judgment(structured, owner_user_id=OWNER, binding_id="bind-structured", created_at=CREATED_AT, baseline_cutoff=AS_OF, scope={"conversation_id": "conv-1"})
    assert b1 is not None and b1.binding_origin == "verified_structured_output"
    assert b1.object_ref.id == "j-structured-1" and b1.object_ref.ref == "judgments.jsonl:j-structured-1"
    assert b1.object_ref.scope == {"conversation_id": "conv-1", "record_type": "foresight_judgment"}
    assert b1.baseline_source_hashes == {"fact_market_daily:2026-09-01": "h-a1", "fact_research_report_catalog:r-77": None}
    assert {g.reason for g in g1} == {"condition_not_deterministic", "dependency_unbound"}
    bindings.append(b1)
    gaps.extend(g1)
    b2, g2 = adapters.candidate_binding_from_judgment(plain, owner_user_id=OWNER, binding_id="bind-plain", created_at=CREATED_AT, baseline_cutoff=AS_OF)
    assert b2 is None and [g.reason for g in g2] == ["dependency_unbound"]
    b3, g3 = adapters.candidate_binding_from_judgment(legacy, owner_user_id=OWNER, binding_id="bind-legacy", created_at=CREATED_AT, baseline_cutoff=AS_OF)
    assert b3 is None and [g.reason for g in g3] == ["object_id_missing", "time_metadata_missing", "dependency_unbound"]
    legacy_ref = adapters.object_ref_from_judgment(legacy, owner_user_id=OWNER)
    assert legacy_ref.id is None and legacy_ref.ref == f"judgments.jsonl:{adapters.record_content_hash(legacy)}"
    b4, g4 = adapters.candidate_binding_from_checkpoint(ck, owner_user_id=OWNER, baseline_cutoff=AS_OF)
    assert b4 is None and [g.reason for g in g4] == ["dependency_unbound"] and "market_daily" in g4[0].detail
    ck_ref = adapters.object_ref_from_checkpoint(ck, owner_user_id=OWNER)
    assert ck_ref.id == ck["id"] and ck_ref.scope == {"session_id": "sess-1", "object_type": "judgment"}
    verdict_versions = adapters.verdict_evidence_versions(ck["id"], loaded_verdicts)
    assert [v.recorded_at for v in verdict_versions] == ["2026-09-10T20:00:00", "2026-09-15T20:00:00"]
    assert all(v.ref.startswith(f"verdicts.jsonl:{ck['id']}@") for v in verdict_versions)
    b5, g5 = adapters.candidate_binding_from_scenario_tree(state, owner_user_id=OWNER, binding_id="bind-tree", created_at=CREATED_AT, baseline_cutoff=AS_OF)
    assert b5 is not None and b5.object_ref.id == ledgers["tree_id"]
    assert b5.baseline_evidence_refs == ("fact_market_daily:2026-09-02",) and b5.baseline_source_hashes == {"fact_market_daily:2026-09-02": None}
    assert b5.conditions == ()  # 节点 a 是叶子：没有子条件可提
    assert [g.reason for g in g5] == ["dependency_unbound"]
    bindings.append(b5)
    gaps.extend(g5)

    versions = [
        {"ref": "fact_market_daily:2026-09-01", "source_hash": "h-a1", "valid_from": "2026-09-01", "recorded_at": "2026-09-01T18:00:00+08:00", "derivation": "deterministic"},
        {"ref": "fact_market_daily:2026-09-01", "source_hash": "h-a2", "valid_from": "2026-09-01", "recorded_at": "2026-09-12T18:00:00+08:00", "derivation": "deterministic"},
        {"ref": "fact_market_daily:2026-09-02", "source_hash": "h-m2", "valid_from": "2026-09-02", "recorded_at": "2026-09-02T18:00:00+08:00", "derivation": "deterministic"},
    ]
    report = jm.assess(owner_user_id=OWNER, as_of=AS_OF, knowledge_cutoff=AS_OF, bindings=bindings, evidence_versions=versions, condition_observations=[], policy=None, generated_at="2026-09-13T00:00:00+00:00")
    by_dep = {(it.binding_id, it.dependency_ref): it for it in report.items}
    assert by_dep[("bind-structured", "fact_market_daily:2026-09-01")].change_type == "content_changed"
    assert by_dep[("bind-structured", "fact_research_report_catalog:r-77")].reason_code == "dependency_unbound"
    assert by_dep[("bind-tree", "fact_market_daily:2026-09-02")].reason_code == "dependency_unbound"
    assert report.counts == {"objects_seen": 2, "objects_bound": 2, "objects_unverifiable": 2, "dependencies_checked": 3, "items_open": 3}
    assert report.pit_grade == "unverifiable"
    # 报告不复制正文：memo / claim 不出现在报告里
    dumped = json.dumps(report.to_dict(), ensure_ascii=False)
    assert "板块轮动仍在反弹段" not in dumped and "示例可证伪点" not in dumped and "题材进入主升" not in dumped
    # 旧文件逐字节不变
    assert _digests(ledgers["files"]) == ledgers["digests"]


def test_tree_child_conditions_become_review_conditions(ledgers):
    us = ledgers["us"]
    records = st.load(st.trees_path(us))
    root_state = dict(st.current_state(records, ledgers["tree_id"]))
    # 回到根：把 realized_path 截到根节点，模拟「刚登记、还没解析」的树（根本身没有 evidence_refs → 不能绑定）
    root_state["realized_path"] = root_state["realized_path"][:1]
    binding, gaps = adapters.candidate_binding_from_scenario_tree(root_state, owner_user_id=OWNER, binding_id="bind-root", created_at=CREATED_AT, baseline_cutoff=AS_OF)
    assert binding is None and [g.reason for g in gaps] == ["dependency_unbound"]
    # 给根补一条 evidence_ref 后：子节点 a 的确定性条件被提为 review 条件，otherwise 不提
    root_state["realized_path"] = [dict(root_state["realized_path"][0], evidence_refs=["fact_market_daily:2026-09-01"])]
    binding, gaps = adapters.candidate_binding_from_scenario_tree(root_state, owner_user_id=OWNER, binding_id="bind-root", created_at=CREATED_AT, baseline_cutoff=AS_OF)
    assert binding is not None
    assert [(c.condition_id, c.role, c.entity_id) for c in binding.conditions] == [(f"{ledgers['tree_id']}:a", "review", "上证指数")]
    observation = {"label": "market_stage", "entity_id": "上证指数", "as_of": AS_OF, "value": "反弹", "recorded_at": f"{AS_OF}T18:00:00+08:00", "label_version": None, "source_ref": f"fact_market_daily:{AS_OF}"}
    report = jm.assess(owner_user_id=OWNER, as_of=AS_OF, knowledge_cutoff=AS_OF, bindings=[binding], evidence_versions=[], condition_observations=[observation], policy=None, generated_at="2026-09-13T00:00:00+00:00")
    cond = next(it for it in report.items if it.change_type == "condition_evaluated")
    assert cond.condition_result == "true" and cond.action == "review_evidence"
    assert _digests(ledgers["files"]) == ledgers["digests"]


def test_adapters_refuse_foreign_user_refs(ledgers):
    record = {"id": "j-x", "ts": "2026-09-01T00:00:00", "memo": "x", "evidence": [{"ref": "users/someone-else/judgments.jsonl:j-1", "hash": "h"}]}
    with pytest.raises(jm.MaintenanceContractError) as info:
        adapters.candidate_binding_from_judgment(record, owner_user_id=OWNER, binding_id="b", created_at=CREATED_AT, baseline_cutoff=AS_OF)
    assert info.value.code == "foreign_user_ref" and "someone-else" not in str(info.value)
    assert _digests(ledgers["files"]) == ledgers["digests"]
