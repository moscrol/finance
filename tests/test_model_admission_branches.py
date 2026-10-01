"""生效模型准入要查到子分支：父对、子错不许通过；子分支没证据判无证据；2×2 判定按产物重算。

背景：2026-10-01 审查复现——父运行模型正确、子分支模型错误，``check_model_admission.py``
照样 exit 0。原因是分支的 model turn 记在各自的分支 episode 里，父产物的 ``branch_completed``
只有计量、没有生效模型。修法两头：运行时分支把每轮生效模型带回父事件（``served_models``）；
准入在父产物缺这份证据时去 episode store 补证，补不上就判无证据。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from intelligence.eval import model_admission as ma
from intelligence.eval.model_harness_2x2 import recompute_admission
from intelligence.runtime.sub_research import (
    BranchEpisodeRef,
    BranchResult,
    SubResearchCoordinator,
    branch_served_models_from_events,
)
from intelligence.runtime.sub_research_tool import branch_telemetry
from intelligence.services import episode_store
from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.evidence_ledger import EvidenceLedger
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.tests.test_sub_research import _context, _frame

REPO = Path(__file__).resolve().parents[1]
EXPECTED = "glm-5.3-flash"
REF = {"episode_id": "branches-abc:branch-1", "parent_episode_id": "run_x", "invocation_id": "branches-abc",
       "branch_id": "branch-1", "origin": "plan"}


def _episode(tmp_path: Path, branch_payload: dict, *, parent_model: str = EXPECTED) -> Path:
    run = tmp_path / "run_20261001_090000_000001"
    run.mkdir(parents=True)
    events = [
        {"sequence": 1, "kind": "model_turn", "payload": {"served_model": parent_model}},
        {"sequence": 2, "kind": "branch_completed", "payload": {"branch_id": "branch-1", "llm_calls": 2, **branch_payload}},
        {"sequence": 3, "kind": "model_turn", "payload": {"served_model": parent_model}},
    ]
    (run / "continuous-episode.json").write_text(json.dumps({"events": events}), encoding="utf-8")
    return run


def _verdict(path: Path, store: Path | None = None) -> ma.AdmissionResult:
    (result,) = ma.check_paths([path], [EXPECTED], episode_store=store)
    return result


def test_parent_right_child_wrong_is_a_mismatch(tmp_path):
    """审查复现的那一例：父全对，子分支服务的是别的模型。"""

    run = _episode(tmp_path, {"served_models": ["glm-5.3", "glm-5.3"], "episode_ref": REF})
    result = _verdict(run)
    assert result.verdict == ma.VERDICT_MISMATCH
    assert result.unexpected == {"glm-5.3": 2}


def test_child_that_called_the_model_without_evidence_is_not_admitted(tmp_path):
    run = _episode(tmp_path, {"episode_ref": REF})  # 老产物：分支没带回 served_models
    result = _verdict(run)
    assert result.verdict == ma.VERDICT_NO_EVIDENCE
    assert result.branch_unproven == 1
    assert "子分支" in result.reason


def test_old_artifacts_are_completed_from_the_episode_store(tmp_path):
    run = _episode(tmp_path, {"episode_ref": REF})
    store = tmp_path / "episodes"
    branch_dir = store / ma.episode_directory_name(REF["episode_id"])
    branch_dir.mkdir(parents=True)
    rows = [{"sequence": 1, "kind": "model_turn", "payload": {"served_model": "glm-5.3"}}]
    (branch_dir / "events.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    assert _verdict(run, store).verdict == ma.VERDICT_MISMATCH
    rows[0]["payload"]["served_model"] = EXPECTED
    (branch_dir / "events.jsonl").write_text(json.dumps(rows[0]), encoding="utf-8")
    result = _verdict(run, store)
    assert result.verdict == ma.VERDICT_ADMITTED and result.branch_unproven == 0
    assert result.served == {EXPECTED: 3}


def test_branches_that_never_called_a_model_need_no_evidence(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    events = [
        {"sequence": 1, "kind": "model_turn", "payload": {"served_model": EXPECTED}},
        {"sequence": 2, "kind": "branch_failed", "payload": {"branch_id": "branch-2", "reason": "branch_not_executed"}},
        {"sequence": 3, "kind": "branch_completed", "payload": {"branch_id": "branch-3", "llm_calls": 0}},
    ]
    (run / "continuous-episode.json").write_text(json.dumps({"events": events}), encoding="utf-8")
    assert _verdict(run).verdict == ma.VERDICT_ADMITTED


@pytest.mark.parametrize(
    ("served_model", "use_store", "expected_verdict"),
    [
        ("glm-5.3", True, ma.VERDICT_MISMATCH),
        (EXPECTED, True, ma.VERDICT_ADMITTED),
        (None, True, ma.VERDICT_NO_EVIDENCE),
        ("glm-5.3", False, ma.VERDICT_NO_EVIDENCE),
    ],
)
def test_worker_exception_cannot_erase_model_admission_evidence(
    tmp_path, served_model, use_store, expected_verdict,
):
    store = tmp_path / "episodes"

    class RecordedThenFailedWorker:
        def run(self, request):
            if served_model is not None:
                branch = store / ma.episode_directory_name(request.episode_ref.episode_id)
                branch.mkdir(parents=True)
                (branch / "events.jsonl").write_text(json.dumps({
                    "kind": "model_turn", "payload": {"served_model": served_model},
                }), encoding="utf-8")
            raise RuntimeError("worker did not return its accounting")

    ledger = EvidenceLedger()
    result = SubResearchCoordinator(RecordedThenFailedWorker()).run(
        goals=("查找反方驱动",), task_frame=_frame(), context=_context(),
        registry=ResearchToolRegistry(()), evidence_sink_factory=ledger.branch_sink,
    )
    payload = branch_telemetry(result.branches[0])
    assert payload["llm_calls_known"] is False
    parent = tmp_path / "continuous-episode.json"
    parent.write_text(json.dumps({"events": [
        {"kind": "model_turn", "payload": {"served_model": EXPECTED}},
        {"kind": "branch_failed", "payload": payload},
    ]}), encoding="utf-8")
    assert _verdict(parent, store if use_store else None).verdict == expected_verdict


def test_cancelled_before_worker_starts_needs_no_model_evidence(tmp_path):
    class NeverRunWorker:
        def run(self, request):
            pytest.fail("cancelled branch must not enter the worker")

    checks = iter((False, True))
    ledger = EvidenceLedger()
    result = SubResearchCoordinator(NeverRunWorker(), is_cancelled=lambda: next(checks)).run(
        goals=("查找反方驱动",), task_frame=_frame(), context=_context(),
        registry=ResearchToolRegistry(()), evidence_sink_factory=ledger.branch_sink,
    )
    evidence = ma.collect_from_events([
        {"kind": "model_turn", "payload": {"served_model": EXPECTED}},
        {"kind": "branch_failed", "payload": branch_telemetry(result.branches[0])},
    ], "cancel-before-start")
    assert ma.judge(evidence, [EXPECTED]).verdict == ma.VERDICT_ADMITTED


@pytest.mark.parametrize("error", ["branch_worker_exception:RuntimeError", "storage_failed"])
def test_legacy_worker_failure_zero_is_unknown_not_proof_of_no_calls(error):
    evidence = ma.collect_from_events([
        {"kind": "model_turn", "payload": {"served_model": EXPECTED}},
        {"kind": "branch_failed", "payload": {"llm_calls": 0, "error": error, "episode_ref": REF}},
    ], "legacy-failed-worker")
    assert ma.judge(evidence, [EXPECTED]).verdict == ma.VERDICT_NO_EVIDENCE


def test_parent_storage_failure_before_branch_start_has_known_zero_calls(tmp_path):
    from intelligence.tests.test_sub_research_persistence import ObservedStore, run_tree

    store = ObservedStore(tmp_path, fail_kind="branch_started", fail_child=False)
    outcome, model, _executed, _spent, _runtime = run_tree(store, plan=True)
    assert model.child_calls == 0
    assert outcome.stop_reason == "storage_failed"
    branch_events = [
        {"kind": event.kind, "payload": dict(event.payload)}
        for event in outcome.events if event.kind == "branch_failed"
    ]
    assert branch_events
    parent_event = {"kind": "model_turn", "payload": {"served_model": EXPECTED}}
    evidence = ma.collect_from_events([parent_event, *branch_events], "storage-before-start")
    assert ma.judge(evidence, [EXPECTED]).verdict == ma.VERDICT_ADMITTED
    # 标志加入前的同一早退产物没有 worker 返回的任何调用账。
    for event in branch_events:
        for key in ("llm_calls", "llm_calls_known", "stop_reason"):
            event["payload"].pop(key, None)
    legacy = ma.collect_from_events([parent_event, *branch_events], "legacy-storage-before-start")
    assert ma.judge(legacy, [EXPECTED]).verdict == ma.VERDICT_ADMITTED


def test_directory_naming_matches_the_episode_store():
    for episode_id in ("branches-abc:branch-1", "run_20261001:msg_1", "plain-id", "带中文:x"):
        assert ma.episode_directory_name(episode_id) == episode_store._directory_name(episode_id)


def test_branch_carries_its_served_models_into_the_parent_event():
    events = [
        EpisodeEvent(1, "task", {"task_frame_hash": "h"}),
        EpisodeEvent(2, "model_turn", {"served_model": "glm-5.3-flash"}),
        EpisodeEvent(3, "model_turn", {"served_model": ""}),
        EpisodeEvent(4, "model_turn", {}),
    ]
    served = branch_served_models_from_events(events)
    assert served == ("glm-5.3-flash", "", None)
    branch = BranchResult(
        branch_id="branch-1", goal="查一查", status="completed", evidence=(), traces=(), gaps=(),
        llm_calls=3, tool_calls=0, served_models=served,
        episode_ref=BranchEpisodeRef(**REF),
    )
    payload = branch_telemetry(branch)
    assert payload["served_models"] == ["glm-5.3-flash", "", None]
    # 没调用模型的分支不写这个键：不把「没测到」写成空列表。
    quiet = BranchResult(branch_id="b", goal="g", status="failed", evidence=(), traces=(), gaps=(),
                         llm_calls=0, tool_calls=0)
    assert "served_models" not in branch_telemetry(quiet)
    with pytest.raises(TypeError):
        BranchResult(branch_id="b", goal="g", status="completed", evidence=(), traces=(), gaps=(),
                     llm_calls=1, tool_calls=0, served_models=(42,))  # type: ignore[arg-type]


def test_worker_wires_branch_served_models():
    source = (REPO / "intelligence/runtime/continuous_sub_research.py").read_text(encoding="utf-8")
    assert "served_models=branch_served_models_from_events(outcome.events)" in source


def test_2x2_recomputes_admission_from_artifacts_and_flags_self_report_drift(tmp_path):
    good = _episode(tmp_path / "a", {"served_models": [EXPECTED], "episode_ref": REF})
    bad = _episode(tmp_path / "b", {"served_models": ["glm-5.3"], "episode_ref": REF})
    records = [
        {"seq": 1, "question": "D1", "cell": "PG", "score": 0.5, "admission_exit": 0, "artifact": str(good)},
        {"seq": 2, "question": "D1", "cell": "PG", "score": 0.5, "admission_exit": 0, "artifact": str(bad)},
        {"seq": 3, "question": "D1", "cell": "PG", "score": 0.5, "admission_exit": 0},
    ]
    rows, summary = recompute_admission(records, {"G": EXPECTED, "C": "claude-x"})
    assert [r["admission_exit"] for r in rows] == [0, 1, None]
    assert [r["admission_source"] for r in rows] == ["recomputed", "recomputed", "unverified"]
    assert summary["disagreements"] == [{"seq": 2, "reported": 0, "recomputed": 1}]
    assert summary["self_reported"] == 0 and summary["unverified"] == 1


def test_cli_follows_the_default_episode_store(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("check_model_admission", REPO / "scripts" / "check_model_admission.py")
    cli = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("check_model_admission", cli)
    spec.loader.exec_module(cli)
    run = _episode(tmp_path, {"episode_ref": REF})
    store = tmp_path / "episodes"
    monkeypatch.setenv(episode_store.EPISODE_STORE_ENV, str(store))
    branch_dir = store / ma.episode_directory_name(REF["episode_id"])
    branch_dir.mkdir(parents=True)
    (branch_dir / "events.jsonl").write_text(
        json.dumps({"sequence": 1, "kind": "model_turn", "payload": {"served_model": "glm-5.3"}}), encoding="utf-8"
    )
    assert cli.main(["--expect-model", EXPECTED, str(run)]) == 1
    assert cli.main(["--expect-model", EXPECTED, "--no-episode-store", str(run)]) == 2
    assert "子分支" in capsys.readouterr().out
