"""生效模型准入（spec 2026-09-02 §3.5.4 硬门 3 的比对半边）。

钉住的契约：
* 期望之外的任何生效模型 → mismatch（exit 1），哪怕只有一个 turn；
* 证明不了 → no_evidence（exit 2）：没有产物、没有带回的 model、读不懂、默认下有「未回」；
* 大小写/空白不算不同模型，但 ``-flash`` 这类后缀算（2026-09-29 的真实事故）；
* 三态：``None``/缺键 = 没到 provider（只计数）；``""`` = 未回；非空 = 生效模型。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.eval import model_admission as ma
from intelligence.services.agent_runtime import ModelTurn


def _turn_event(sequence: int, served: object = "__absent__", kind: str = "model_turn") -> dict:
    payload: dict[str, object] = {"phase": "research", "content": "", "tool_calls": []}
    if served != "__absent__":
        payload["served_model"] = served
    return {"sequence": sequence, "kind": kind, "payload": payload}


def _episode(tmp_path: Path, *served: object, name: str = "run-1") -> Path:
    run_dir = tmp_path / name
    run_dir.mkdir(parents=True)
    events = [{"sequence": 0, "kind": "episode_started", "payload": {}}]
    events += [_turn_event(i + 1, value) for i, value in enumerate(served)]
    (run_dir / ma.EPISODE_FILENAME).write_text(
        json.dumps({"events": events, "outcome": {"status": "completed"}}), encoding="utf-8"
    )
    return run_dir


def _check(paths, expected=("glm-5.3",), **kwargs):
    results = ma.check_paths([str(p) for p in paths], expected, **kwargs)
    return results, ma.overall_exit_code(results)


def test_all_turns_served_by_expected_model_is_admitted(tmp_path):
    results, code = _check([_episode(tmp_path, "glm-5.3", "glm-5.3", "GLM-5.3 ")])
    assert code == 0
    assert results[0].verdict == ma.VERDICT_ADMITTED
    assert results[0].served == {"glm-5.3": 3}


def test_single_flash_turn_voids_the_reading(tmp_path):
    # 2026-09-29 GLM 重写消融：预设 glm-5.3，实际跑的是 glm-5.3-flash。
    results, code = _check([_episode(tmp_path, "glm-5.3", "glm-5.3-flash", "glm-5.3")])
    assert code == 1
    assert results[0].verdict == ma.VERDICT_MISMATCH
    assert results[0].unexpected == {"glm-5.3-flash": 1}
    assert "glm-5.3-flash×1" in results[0].reason


def test_all_unreported_is_no_evidence(tmp_path):
    results, code = _check([_episode(tmp_path, "", "")])
    assert code == 2
    assert results[0].verdict == ma.VERDICT_NO_EVIDENCE
    assert results[0].unreported == 2


def test_partial_unreported_blocks_unless_explicitly_allowed(tmp_path):
    run = _episode(tmp_path, "glm-5.3", "")
    strict, strict_code = _check([run])
    assert strict_code == 2 and "--allow-unreported" in strict[0].reason
    relaxed, relaxed_code = _check([run], allow_unreported=True)
    assert relaxed_code == 0 and relaxed[0].unreported == 1
    assert "已显式放行" in relaxed[0].reason


def test_allow_unreported_never_rescues_zero_evidence(tmp_path):
    _results, code = _check([_episode(tmp_path, "", "")], allow_unreported=True)
    assert code == 2


def test_turns_that_never_reached_provider_are_counted_not_judged(tmp_path):
    results, code = _check([_episode(tmp_path, "__absent__", None, "glm-5.3")])
    assert code == 0
    assert results[0].not_reached == 2


def test_aliases_can_be_accepted_explicitly(tmp_path):
    run = _episode(tmp_path, "glm-5.3", "glm-5.3-20260901")
    assert _check([run])[1] == 1
    assert _check([run], expected=("glm-5.3", "GLM-5.3-20260901"))[1] == 0


def test_real_model_turn_payload_round_trips():
    """产物里的 payload 是 ``{**turn.to_dict(), ...}`` 平铺进去的；形状漂了这里先红。"""

    events = [
        {"sequence": 1, "kind": "model_turn", "payload": {"phase": "research", **ModelTurn("a", (), served_model="glm-5.3").to_dict()}},
        {"sequence": 2, "kind": "model_turn", "payload": {**ModelTurn("b", (), served_model="").to_dict()}},
        {"sequence": 3, "kind": "model_turn", "payload": {**ModelTurn("c", ()).to_dict()}},
    ]
    evidence = ma.collect_from_events(events, "inline")
    assert (evidence.served, evidence.unreported, evidence.not_reached) == ({"glm-5.3": 1}, 1, 1)


def test_sdk_arm_served_models_lists_are_read(tmp_path):
    path = tmp_path / "sdk.json"
    path.write_text(
        json.dumps(
            {
                "events": [
                    {"sequence": 1, "kind": "runtime_result", "payload": {"model": "glm-5.3", "served_models": ["glm-5.3", "glm-5.3"]}},
                    {"sequence": 2, "kind": "model_turn", "payload": {"phase": "repair", "served_models": ["glm-4.6"]}},
                ]
            }
        ),
        encoding="utf-8",
    )
    results, code = _check([path])
    assert code == 1
    assert results[0].served == {"glm-5.3": 2, "glm-4.6": 1}
    # 请求的 ``model`` 字段（配置值）不算证据
    assert results[0].unexpected == {"glm-4.6": 1}


def test_episode_store_events_jsonl_is_read(tmp_path):
    episode_dir = tmp_path / "store" / "ep-1"
    episode_dir.mkdir(parents=True)
    lines = [_turn_event(1, "glm-5.3"), _turn_event(2, "glm-5.3")]
    (episode_dir / ma.EVENTS_FILENAME).write_text(
        "\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8"
    )
    results, code = _check([tmp_path / "store"])
    assert code == 0 and results[0].source.endswith("events.jsonl")


def test_generic_json_falls_back_to_key_scan(tmp_path):
    # scripts/inspect_adaptive_research.py 的汇总就是这种形状
    path = tmp_path / "inspection.json"
    path.write_text(json.dumps({"pair": [{"served_models": ["glm-5.3"]}, {"rounds": [{"served_model": "glm-5.3"}]}]}), encoding="utf-8")
    results, code = _check([path])
    assert code == 0 and results[0].served == {"glm-5.3": 2}


def test_directory_is_searched_recursively(tmp_path):
    _episode(tmp_path / "runs", "glm-5.3", name="a")
    _episode(tmp_path / "runs", "glm-5.3-flash", name="b")
    results, code = _check([tmp_path / "runs"])
    assert len(results) == 2 and code == 1
    assert [r.verdict for r in results] == [ma.VERDICT_ADMITTED, ma.VERDICT_MISMATCH]


def test_missing_paths_and_empty_dirs_fail_closed(tmp_path):
    (tmp_path / "empty").mkdir()
    results, code = _check([tmp_path / "nope", tmp_path / "empty"])
    assert code == 2
    assert all(r.verdict == ma.VERDICT_NO_EVIDENCE for r in results)
    assert all("找不到" in r.reason for r in results)


def test_unreadable_or_malformed_artifacts_fail_closed(tmp_path):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not json", encoding="utf-8")
    wrong_type = tmp_path / "wrong.json"
    wrong_type.write_text(json.dumps({"events": [_turn_event(1, 5.3)]}), encoding="utf-8")
    results, code = _check([bad_json, wrong_type])
    assert code == 2
    assert [r.verdict for r in results] == [ma.VERDICT_NO_EVIDENCE] * 2


def test_mismatch_outranks_malformed_evidence(tmp_path):
    path = tmp_path / "mixed.json"
    path.write_text(json.dumps({"events": [_turn_event(1, 5.3), _turn_event(2, "glm-4.6")]}), encoding="utf-8")
    results, code = _check([path])
    assert code == 1 and results[0].verdict == ma.VERDICT_MISMATCH


def test_overall_exit_code_precedence():
    def result(verdict):
        return ma.AdmissionResult("x", verdict, ("glm-5.3",), {}, {}, 0, 0, "")

    assert ma.overall_exit_code([]) == 2
    assert ma.overall_exit_code([result(ma.VERDICT_ADMITTED)]) == 0
    assert ma.overall_exit_code([result(ma.VERDICT_ADMITTED), result(ma.VERDICT_NO_EVIDENCE)]) == 2
    assert ma.overall_exit_code([result(ma.VERDICT_NO_EVIDENCE), result(ma.VERDICT_MISMATCH)]) == 1


def test_expected_model_is_required():
    with pytest.raises(ValueError):
        ma.judge(ma.ServedModelEvidence("x"), ["  "])


def test_artifact_names_match_their_writers():
    from intelligence.api import credits
    from intelligence.services.episode_store import JsonlEpisodeStore

    assert ma.EPISODE_FILENAME == credits._EPISODE_FILENAME
    assert ma.EVENTS_FILENAME == JsonlEpisodeStore.EVENTS_NAME


def test_cli_exit_codes_and_json(tmp_path, capsys):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_model_admission", Path(__file__).resolve().parents[2] / "scripts" / "check_model_admission.py"
    )
    assert spec is not None and spec.loader is not None
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)

    good = _episode(tmp_path, "glm-5.3", name="good")
    bad = _episode(tmp_path, "glm-5.3-flash", name="bad")
    assert cli.main(["--expect-model", "glm-5.3", str(good)]) == 0
    assert "全部准入" in capsys.readouterr().out
    assert cli.main(["--expect-model", "glm-5.3", "--json", str(good), str(bad)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["exit_code"] == 1
    assert [r["verdict"] for r in payload["results"]] == ["admitted", "mismatch"]
    with pytest.raises(SystemExit):
        cli.main([str(good)])  # --expect-model 必填


def _reference(path, episode_id):
    document = json.loads(path.read_text())
    document['events'].append({'kind': 'branch_completed', 'payload': {
        'episode_ref': {'episode_id': episode_id}, 'llm_calls': 1,
    }})
    path.write_text(json.dumps(document))


def _stored_episode(root, episode_id, model):
    from intelligence.services.episode_store import JsonlEpisodeStore

    directory = JsonlEpisodeStore(root).episode_dir(episode_id)
    directory.mkdir(parents=True, exist_ok=True)
    event = {**_turn_event(1, model), 'episode_id': episode_id}
    path = directory / ma.EVENTS_FILENAME
    path.write_text(json.dumps(event) + '\n')
    return path


def test_direct_parent_artifact_does_not_hide_nested_child(tmp_path):
    parent = _episode(tmp_path, 'glm-5.3')
    _episode(parent / 'branches', 'glm-5.3-flash', name='child')
    assert _check([parent])[1] == 1


def test_parent_file_follows_referenced_child_in_explicit_store(tmp_path):
    parent = _episode(tmp_path, 'glm-5.3') / ma.EPISODE_FILENAME
    _reference(parent, 'invocation:child')
    store = tmp_path / 'store'
    _stored_episode(store, 'invocation:child', 'glm-5.3-flash')
    results, code = _check([parent], episode_store_roots=[store])
    assert code == 1
    assert any(r.unexpected == {'glm-5.3-flash': 1} for r in results)


def test_matching_referenced_child_is_admitted(tmp_path):
    parent = _episode(tmp_path, 'glm-5.3') / ma.EPISODE_FILENAME
    _reference(parent, 'invocation:child')
    store = tmp_path / 'store'
    _stored_episode(store, 'invocation:child', 'glm-5.3')
    results, code = _check([parent], episode_store_roots=[store])
    assert code == 0 and len(results) == 2


def test_referenced_child_missing_is_not_parent_success(tmp_path):
    parent = _episode(tmp_path, 'glm-5.3') / ma.EPISODE_FILENAME
    _reference(parent, 'invocation:missing')
    results, code = _check([parent])
    assert code == 2
    assert any('invocation:missing' in r.source for r in results)


def test_events_store_resolves_sibling_automatically(tmp_path):
    parent = _stored_episode(tmp_path, 'parent:1', 'glm-5.3')
    _stored_episode(tmp_path, 'child:1', 'glm-5.3-flash')
    with parent.open('a') as f:
        f.write(json.dumps({'kind': 'branch_failed', 'payload': {
            'episode_ref': {'episode_id': 'child:1'},
        }}) + '\n')
    assert _check([parent])[1] == 1


def test_grandchild_is_checked_and_repeated_inputs_deduplicated(tmp_path):
    parent = _stored_episode(tmp_path, 'parent:1', 'glm-5.3')
    child = _stored_episode(tmp_path, 'child:1', 'glm-5.3')
    _stored_episode(tmp_path, 'grandchild:1', 'glm-5.3-flash')
    for path, ref in [(parent, 'child:1'), (child, 'grandchild:1')]:
        with path.open('a') as f:
            f.write(json.dumps({'kind': 'branch_completed', 'payload': {
                'episode_ref': {'episode_id': ref},
            }}) + '\n')
    results, code = _check([parent, parent])
    assert code == 1 and len(results) == 3


def test_reference_cycle_fails_closed(tmp_path):
    parent = _stored_episode(tmp_path, 'parent:1', 'glm-5.3')
    with parent.open('a') as f:
        f.write(json.dumps({'kind': 'branch_completed', 'payload': {
            'episode_ref': {'episode_id': 'parent:1'},
        }}) + '\n')
    assert _check([parent])[1] == 2


def test_malformed_reference_fails_closed(tmp_path):
    parent = _episode(tmp_path, 'glm-5.3') / ma.EPISODE_FILENAME
    document = json.loads(parent.read_text())
    document['events'].append({'kind': 'branch_completed', 'payload': {'episode_ref': {}}})
    parent.write_text(json.dumps(document))
    assert _check([parent])[1] == 2
