"""Exercise the real acquisition loop with mocked HTTP, never a model or live server."""
import json

import pytest

from intelligence.eval import acceptance


class FakeWorkbench:
    def __init__(self):
        self.conversations = []
        self.posts = []
        self.polls = 0
        self.run_status = "completed"
        self.omit_ids = False
        self.target_pending_first = False
        self.empty_target = False
        self.wrong_run_id = False

    def post(self, url, body, **kwargs):
        if url.endswith("/api/conversations"):
            cid = f"conv-{len(self.conversations) + 1}"
            self.conversations.append(cid)
            return {"conversation_id": cid}
        self.posts.append((url, body))
        if self.omit_ids:
            return {}
        return {"run_id": f"run-{len(self.posts)}", "assistant_message_id": f"msg-{len(self.posts)}"}

    def get(self, url, **kwargs):
        if "/api/runs/" in url:
            return {"status": self.run_status, "error": "synthetic failure"}
        self.polls += 1
        target = {
            "message_id": f"msg-{len(self.posts)}", "role": "assistant",
            "run_id": "wrong" if self.wrong_run_id else f"run-{len(self.posts)}",
            "status": "pending" if self.target_pending_first and self.polls == 1 else "completed",
            "content": "" if self.empty_target else "new answer",
        }
        # A late answer from a previous run may appear last; never take it.
        return {"messages": [target, {"message_id": "old", "run_id": "old-run", "role": "assistant", "status": "completed", "content": "STALE"}]}


@pytest.fixture
def api(monkeypatch):
    backend = FakeWorkbench()
    monkeypatch.setattr(acceptance, "_post", backend.post)
    monkeypatch.setattr(acceptance, "_get", backend.get)
    monkeypatch.setattr(acceptance, "_fill_run_detail", lambda *a, **kw: None)
    monkeypatch.setattr(acceptance.time, "sleep", lambda _: None)
    return backend


def test_actual_case_loop_shares_conversation_but_isolates_next_case(api, monkeypatch, tmp_path):
    monkeypatch.setattr(acceptance, "load_cases", lambda: {"cases": [
        {"id": "C10-multi-turn-consistency", "tier": "long_tail", "query": "首问", "followups": ["追问1", "追问2"]},
        {"id": "A1-market-overview", "tier": "high_freq", "query": "另一个用例"},
    ]})
    monkeypatch.setattr(acceptance, "preflight", lambda _: (True, "offline"))
    output = tmp_path / "run.json"
    assert acceptance.main(["run", "--output", str(output)]) == 0
    assert len(api.conversations) == 2
    assert [url.split("/")[-2] for url, _ in api.posts] == ["conv-1"] * 3 + ["conv-2"]
    turns = json.loads(output.read_text())["cases"][0]["turns"]
    assert [t["conversation_id"] for t in turns] == ["conv-1"] * 3
    assert [t["assistant_message_id"] for t in turns] == ["msg-1", "msg-2", "msg-3"]
    assert [t["run_id"] for t in turns] == ["run-1", "run-2", "run-3"]
    assert all(t["answer"] == "new answer" for t in turns)


def test_waits_for_target_message_terminal_not_run_claim_or_late_answer(api):
    api.target_pending_first = True
    trace = acceptance.ask_once("http://offline.invalid", "tester", "question", 10)
    assert api.polls == 2
    assert trace.answer == "new answer"
    assert trace.status == "completed"


@pytest.mark.parametrize("mode", ["omit_ids", "wrong_run_id"])
def test_invalid_identity_fails_closed(api, mode):
    setattr(api, mode, True)
    trace = acceptance.ask_once("http://offline.invalid", "tester", "question", 10)
    assert trace.status == "error"
    assert trace.answer is None


@pytest.mark.parametrize("status", ["failed", "cancelled", "aborted"])
def test_run_failure_cannot_be_replaced_by_old_completed_message(api, status):
    api.run_status = status
    trace = acceptance.ask_once("http://offline.invalid", "tester", "question", 10)
    assert trace.status == status
    assert trace.answer is None
    assert api.polls == 0


def test_completed_run_with_empty_message_times_out(api, monkeypatch):
    api.empty_target = True
    clock = iter(range(100))
    monkeypatch.setattr(acceptance.time, "monotonic", lambda: next(clock))
    trace = acceptance.ask_once("http://offline.invalid", "tester", "question", 8)
    assert trace.status == "timeout"
    assert trace.answer is None


def test_case_stops_after_run_failure(api, monkeypatch, tmp_path):
    api.run_status = "failed"
    monkeypatch.setattr(acceptance, "load_cases", lambda: {"cases": [
        {"id": "C10-multi-turn-consistency", "tier": "long_tail", "query": "首问", "followups": ["不得发送"]},
    ]})
    monkeypatch.setattr(acceptance, "preflight", lambda _: (True, "offline"))
    output = tmp_path / "failed.json"
    assert acceptance.main(["run", "--output", str(output)]) == 0  # failure is preserved in artifact
    assert len(api.posts) == 1
    assert json.loads(output.read_text())["cases"][0]["turns"][0]["status"] == "failed"
