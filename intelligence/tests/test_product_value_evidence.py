"""RunStoreEvidenceReader：对真实 RunStore 只读解析，失败 run 无报告也能计失败；跨用户不泄漏。"""

from __future__ import annotations

import json
from pathlib import Path

from intelligence.services.product_value import contracts as C
from intelligence.services.product_value.evidence import (
    EVIDENCE_CROSS_OWNER,
    EVIDENCE_MISSING,
    EVIDENCE_OK,
    EVIDENCE_TAMPERED,
    EVIDENCE_UNAVAILABLE,
    EVIDENCE_UNREADABLE,
    RunStoreEvidenceReader,
)
from intelligence.services.product_value.measure import measure_pair
from intelligence.services.run_store import STATUS_COMPLETED, STATUS_FAILED, RunStore
from intelligence.tests.product_value_fixtures import HASH_A, OWNER, build_protocol, build_scenario

PROTOCOL = build_protocol()
P_HASH = PROTOCOL["protocol_hash"]


def _store(tmp_path: Path, owner: str) -> RunStore:
    return RunStore(owner, root=tmp_path / owner / "runs")


def _reader(stores: dict[str, RunStore]) -> RunStoreEvidenceReader:
    return RunStoreEvidenceReader(lambda owner: stores.get(owner))


def test_failed_run_without_report_resolves_as_failed(tmp_path: Path) -> None:
    store = _store(tmp_path, "tester")
    run = store.create_run("q", "research")
    store.add_degrade(run.run_id, "kb_unavailable")
    store.finish_run(run.run_id, STATUS_FAILED, error="provider timeout")
    assert not (store.run_dir(run.run_id) / "report.json").exists()
    evidence = _reader({"tester": store}).resolve_run("tester", run.run_id)
    assert evidence["status"] == EVIDENCE_OK
    assert evidence["run_status"] == STATUS_FAILED
    assert evidence["has_error"] is True
    assert evidence["degrades"] == ["kb_unavailable"]
    assert "timeout" not in json.dumps(evidence)  # 错误文本不外泄


def test_missing_unreadable_unavailable_are_distinguished(tmp_path: Path) -> None:
    store = _store(tmp_path, "tester")
    reader = _reader({"tester": store})
    assert reader.resolve_run("tester", "run_does_not_exist")["status"] == EVIDENCE_MISSING
    broken_dir = store.run_dir("run_broken")
    broken_dir.mkdir(parents=True)
    (broken_dir / "run.json").write_text("{not json", encoding="utf-8")
    assert reader.resolve_run("tester", "run_broken")["status"] == EVIDENCE_UNREADABLE
    assert reader.resolve_run("nobody", "run_x")["status"] == EVIDENCE_UNAVAILABLE
    # 路径穿越式 run_id 由 RunStore 拒绝，读取器如实报不可读而不是崩。
    assert reader.resolve_run("tester", "../escape")["status"] == EVIDENCE_UNREADABLE


def test_cross_owner_run_is_flagged_without_details(tmp_path: Path) -> None:
    other = _store(tmp_path, "other")
    run = other.create_run("secret question", "research")
    other.finish_run(run.run_id, STATUS_COMPLETED)
    # 配错的 store_for_owner：不管问谁都给同一个 store——读取器仍要靠 run.user 拦住。
    reader = RunStoreEvidenceReader(lambda owner: other)
    evidence = reader.resolve_run("tester", run.run_id)
    assert evidence["status"] == EVIDENCE_CROSS_OWNER
    assert evidence["run_status"] is None and evidence["artifacts"] == {}
    assert "secret" not in json.dumps(evidence)


def test_artifact_ref_hash_checked(tmp_path: Path) -> None:
    store = _store(tmp_path, "tester")
    run = store.create_run("q", "research")
    artifact = store.add_artifact(run.run_id, "report.md", "# 报告", renderer="markdown", title="报告")
    store.finish_run(run.run_id, STATUS_COMPLETED)
    reader = _reader({"tester": store})
    ref = {"kind": "artifact", "id": artifact.artifact_id, "namespace": "workbench.runs", "version_or_hash": f"sha256:{artifact.sha256}", "scope": {"run_id": run.run_id}}
    assert reader.resolve_ref("tester", ref)["status"] == EVIDENCE_OK
    assert reader.resolve_ref("tester", ref)["hash_checked"] is True
    tampered = {**ref, "version_or_hash": "sha256:" + "0" * 64}
    assert reader.resolve_ref("tester", tampered)["status"] == EVIDENCE_TAMPERED
    missing = {**ref, "id": "artifact_nope"}
    assert reader.resolve_ref("tester", missing)["status"] == EVIDENCE_MISSING
    unsupported = {"kind": "judgment", "id": "j-1", "namespace": "foresight.judgments", "version_or_hash": "v1", "scope": {}}
    assert reader.resolve_ref("tester", unsupported)["status"] == EVIDENCE_UNAVAILABLE


def _rebind_scenario_to_real_run(events: list[dict], run_id: str, artifact_id: str, sha256: str) -> list[dict]:
    text = json.dumps(events, ensure_ascii=False)
    for old, new in (("r-cp-1", run_id), ("art-cp-1", artifact_id), (HASH_A, sha256)):
        text = text.replace(old, new)
    return json.loads(text)


def test_measure_pair_against_real_run_store(tmp_path: Path) -> None:
    store = _store(tmp_path, OWNER)
    run = store.create_run("核对成交额口径", "research")
    artifact = store.add_artifact(run.run_id, "answer.md", "核对单", renderer="markdown", title="核对单")
    store.finish_run(run.run_id, STATUS_COMPLETED)
    events, _, _ = build_scenario("complete_pair", P_HASH)
    events = _rebind_scenario_to_real_run(events, run.run_id, artifact.artifact_id, artifact.sha256)
    receipt = measure_pair(events, PROTOCOL, _reader({OWNER: store}))
    assert receipt["status"] == C.RECEIPT_VALID, receipt["limitations"]
    attempt = receipt["tasks"]["assisted"]["attempts"][0]
    assert attempt["run_id"] == run.run_id and attempt["evidence_status"] == EVIDENCE_OK
    assert receipt["tasks"]["assisted"]["completion_evidence"][0]["status"] == EVIDENCE_OK


def test_measure_pair_keeps_failed_real_run_in_denominator(tmp_path: Path) -> None:
    """反向证伪的正面：把失败 run 过滤掉的实现不可能让这条通过。"""
    store = _store(tmp_path, OWNER)
    run = store.create_run("核对成交额口径", "research")
    store.finish_run(run.run_id, STATUS_FAILED, error="tool exploded")
    events, _, _ = build_scenario("complete_pair", P_HASH)
    events = _rebind_scenario_to_real_run(events, run.run_id, "artifact_answer_md", "1" * 64)
    # 事件流里 run_finished 自报 completed，但真实 store 说 failed：以 store 为准并记冲突。
    receipt = measure_pair(events, PROTOCOL, _reader({OWNER: store}))
    attempt = receipt["tasks"]["assisted"]["attempts"][0]
    assert attempt["run_status"] == STATUS_FAILED and attempt["failed"] is True
    assert "attempt_status_conflict:a-cp-1" in receipt["limitations"]
    assert receipt["tasks"]["assisted"]["failed_attempt_count"] == 1
    assert "t-cp-a" in receipt["denominator_ids"]
    # 完成证据指向一个失败 run 里不存在的产物：缺失 → incomplete，而不是当成功。
    assert receipt["status"] == C.RECEIPT_INCOMPLETE
    assert any(lim.startswith("completion_evidence_missing:t-cp-a") for lim in receipt["limitations"])
