import json
import time

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from intelligence.api import app as app_module  # noqa: E402
from intelligence.services import run_store as rs  # noqa: E402
from intelligence.services.run_store import RunStore  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """隔离环境：runs 落 tmp 目录；ask 执行体换成确定性 fake（不依赖 LLM/数据）。"""
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))

    def fake_run_ask(store: RunStore, run_id: str, req) -> None:
        store.append_step(run_id, step_id="s01", name="ask_retrieve_compose",
                          status="completed", input_summary=req.question,
                          output_summary="fake 命中")
        store.add_artifact(run_id, "answer.md", f"# 答\n{req.question}",
                           renderer="markdown", title="研究回答")
        store.finish_run(run_id, rs.STATUS_COMPLETED)

    monkeypatch.setattr(app_module, "_run_ask", fake_run_ask)
    return TestClient(app_module.create_app())


def _wait_terminal(client: TestClient, run_id: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in ("completed", "failed", "cancelled"):
            return run
        time.sleep(0.05)
    raise AssertionError("run 未在超时内到终态")


def test_create_run_and_fetch_artifacts(client: TestClient) -> None:
    resp = client.post("/api/runs", json={"question": "测试问题"})
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    run = _wait_terminal(client, run_id)
    assert run["status"] == "completed"
    assert [a["path"] for a in run["artifacts"]] == ["answer.md"]

    trace = client.get(f"/api/runs/{run_id}/trace").json()
    assert trace[0]["name"] == "ask_retrieve_compose"

    answer = client.get(f"/api/runs/{run_id}/artifacts/answer.md")
    assert answer.status_code == 200
    assert "测试问题" in answer.text

    listed = client.get("/api/runs").json()
    assert listed[0]["run_id"] == run_id


def test_sse_replays_steps_and_ends_with_run(client: TestClient) -> None:
    run_id = client.post("/api/runs", json={"question": "q"}).json()["run_id"]
    _wait_terminal(client, run_id)

    events = []
    with client.stream("GET", f"/api/runs/{run_id}/events") as resp:
        for line in resp.iter_lines():
            if line.startswith("event: "):
                events.append(line.removeprefix("event: "))
            if "event: run" in line:
                break
    assert events[0] == "step"
    assert events[-1] == "run"


def test_missing_run_404(client: TestClient) -> None:
    assert client.get("/api/runs/run_nope").status_code == 404
    assert client.get("/api/runs/run_nope/trace").status_code == 404


def test_artifact_path_traversal_rejected(client: TestClient) -> None:
    run_id = client.post("/api/runs", json={"question": "q"}).json()["run_id"]
    _wait_terminal(client, run_id)
    resp = client.get(f"/api/runs/{run_id}/artifacts/..%2Frun.json")
    assert resp.status_code in (404, 400)


def test_failed_run_surfaces_error(client: TestClient, monkeypatch) -> None:
    def failing(store, run_id, req):
        store.finish_run(run_id, rs.STATUS_FAILED, error="boom")

    monkeypatch.setattr(app_module, "_run_ask", failing)
    c = TestClient(app_module.create_app())
    run_id = c.post("/api/runs", json={"question": "q"}).json()["run_id"]
    run = _wait_terminal(c, run_id)
    assert run["status"] == "failed" and run["error"] == "boom"


def test_followups_endpoint_and_parent_link(client: TestClient, monkeypatch) -> None:
    from intelligence.services import followups as fu_svc

    def fake_run_ask(store: RunStore, run_id: str, req) -> None:
        fu = fu_svc.generate_followups(req.question, matched_theme="液冷", use_llm=False)
        store.add_artifact(run_id, "followups.json", fu.to_json(), renderer="json", title="猜你想问")
        store.finish_run(run_id, rs.STATUS_COMPLETED)

    monkeypatch.setattr(app_module, "_run_ask", fake_run_ask)
    parent_id = client.post("/api/runs", json={"question": "液冷题材怎么看"}).json()["run_id"]
    _wait_terminal(client, parent_id)

    doc = client.get(f"/api/runs/{parent_id}/followups").json()
    assert len(doc["followups"]) == 5
    first = doc["followups"][0]
    assert first["type"] == "evidence" and "液冷" in first["question"]

    child_id = client.post("/api/runs", json={
        "question": first["question"], "parent_run_id": parent_id}).json()["run_id"]
    child = _wait_terminal(client, child_id)
    assert child["parent_run_id"] == parent_id


def test_followups_missing_returns_empty(client: TestClient) -> None:
    run_id = client.post("/api/runs", json={"question": "q"}).json()["run_id"]
    _wait_terminal(client, run_id)
    assert client.get(f"/api/runs/{run_id}/followups").json() == {"followups": []}


def test_index_serves_workbench_page(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Workbench" in resp.text
