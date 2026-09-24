import json

import pytest

from intelligence.eval import mechanism_workbench as probe


@pytest.fixture
def setup(tmp_path, monkeypatch):
    users = tmp_path / "users"
    h = {"status": "healthy", "runtime": {
        "code_matches_repo": True, "source_revision": "fixed", "loaded_tree_fingerprint": "fixed",
        "users_dir": str(users), "agent_runtime": {"ready": True, "model": "fixed"},
    }}
    monkeypatch.setattr(probe, "health", lambda: h)
    directory = tmp_path / "experiment"
    protocol = probe.prepare(directory, "R-20260916-05")
    posts = []

    def request(method, url, *, payload=None, **kwargs):
        assert method == "POST"
        posts.append((url, payload))
        if url.endswith("/api/conversations"):
            return {"conversation_id": "conversation-test", "user_id": payload["user"]}
        user = payload["user"]
        path = users / user / "runs" / "run-test"
        path.mkdir(parents=True)
        (path / "answer.md").write_text("answer")
        (path / "continuous-episode.json").write_text(json.dumps({"events": [
            {"kind": "tool_result", "payload": {"tool": "financial_data"}},
        ]}))
        return {"run_id": "run-test", "status": "queued"}

    monkeypatch.setattr(probe, "_request_json", request)
    monkeypatch.setattr(probe, "wait_for_run", lambda *a, **k: {"status": "completed"})
    return directory, protocol, posts, h


def test_only_conversation_entry_and_no_repeat(setup):
    directory, protocol, posts, _ = setup
    receipts = probe.run(directory)
    assert len(posts) == 4
    assert all("/api/conversations" in url for url, _ in posts)
    assert all(r["tool_results"] == {"financial_data": 1} for r in receipts)
    assert probe.run(directory) == receipts
    assert len(posts) == 4
    assert len(set(protocol["users"].values())) == 2
    for arm in protocol["order"]:
        assert (directory / arm / "artifacts" / "answer.md").read_text() == "answer"


def test_partial_attempt_cannot_repost(setup, monkeypatch):
    directory, _, posts, _ = setup
    monkeypatch.setattr(probe, "wait_for_run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("crash")))
    with pytest.raises(RuntimeError):
        probe.run(directory)
    assert len(posts) == 2
    with pytest.raises(ValueError, match="never repost"):
        probe.run(directory)
    assert len(posts) == 2


def test_changed_server_cannot_submit(setup, monkeypatch):
    directory, _, posts, h = setup
    h["runtime"]["source_revision"] = "changed"
    with pytest.raises(ValueError, match="server identity changed"):
        probe.run(directory)
    assert not posts


def test_failed_run_stops_batch(setup, monkeypatch):
    directory, _, posts, _ = setup
    monkeypatch.setattr(probe, "wait_for_run", lambda *a, **k: {"status": "failed"})
    result = probe.run(directory)
    assert len(result) == 1
    assert len(posts) == 2
    assert result[0]["status"] == "failed"


def test_wrong_user_cannot_submit_message(setup, monkeypatch):
    directory, _, _, _ = setup
    monkeypatch.setattr(probe, "_request_json", lambda *a, **k: {"user_id": "personal", "conversation_id": "wrong"})
    with pytest.raises(ValueError, match="isolated user"):
        probe.run(directory)
    assert not (directory / "summary" / "submission.json").exists()


def test_copy_does_not_overwrite(tmp_path):
    target = tmp_path / "artifact"
    probe._copy_once(target, b"original")
    with pytest.raises(FileExistsError):
        probe._copy_once(target, b"replacement")
    assert target.read_bytes() == b"original"
