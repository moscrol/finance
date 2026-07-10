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
    users_root = tmp_path / "users"
    repo_root = tmp_path / "repo"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users_root))

    daily_dir = repo_root / "复盘" / "daily" / "2026-07-09"
    daily_dir.mkdir(parents=True)
    (daily_dir / "2026-07-09-daily-agent.html").write_text("<h1>daily</h1>", encoding="utf-8")
    (daily_dir / "2026-07-09-daily-review.html").write_text(
        """<h2>核心看板</h2><table>
        <tr><th>维度</th><th>结论</th></tr>
        <tr><td>市场性质</td><td>普通交易日</td></tr>
        <tr><td>指数表现</td><td>上证上涨 1%</td></tr>
        </table><h2>市场环境总评</h2><p>市场回暖，等待量能确认。</p>""",
        encoding="utf-8",
    )
    (daily_dir / "chart.png").write_bytes(b"png")
    (repo_root / "复盘" / "secret.txt").write_text("secret", encoding="utf-8")
    exports = repo_root / "market_feature_store" / "exports"
    exports.mkdir(parents=True)
    (exports / "2026-07-09-daily-agent.json").write_text(
        json.dumps(
            {
                "date": "2026-07-09",
                "decision": {
                    "old_logic_wakeup": [],
                    "new_logic_candidate": [],
                    "data_gap": [],
                    "noise_or_unconfirmed": [],
                },
                "research_queue": {
                    "today_do_ima": [],
                    "today_find_official_evidence": [],
                    "today_wait_market_validation": [],
                    "today_downgrade_or_watch": [],
                    "summary": {"total": 0},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (exports / "2026-07-09-daily-workflow-summary.json").write_text(
        '{"date":"2026-07-09"}',
        encoding="utf-8",
    )

    def fake_run_ask(store: RunStore, run_id: str, req) -> None:
        store.append_step(
            run_id,
            step_id="s01",
            name="ask_retrieve_compose",
            status="completed",
            input_summary=req.question,
            output_summary="fake 命中",
            retrieval={
                "sources": ["market"],
                "citation_counts": {"S": 2},
                "trade_date": "2026-07-09",
            },
        )
        store.add_artifact(
            run_id,
            "answer.md",
            f"# 答\n{req.question}",
            renderer="markdown",
            title="研究回答",
        )
        store.finish_run(run_id, rs.STATUS_COMPLETED)

    monkeypatch.setattr(app_module, "_run_ask", fake_run_ask)
    return TestClient(app_module.create_app(repo_root=repo_root))


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
    assert [artifact["path"] for artifact in run["artifacts"]] == ["answer.md"]

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


def test_sse_replays_structured_report_modules_and_report_endpoint(client: TestClient) -> None:
    run_id = client.post("/api/runs", json={"question": "q"}).json()["run_id"]
    _wait_terminal(client, run_id)
    store = RunStore()
    report = {
        "schema_version": 1,
        "report_id": run_id,
        "title": "q",
        "task_type": "daily",
        "status": "streaming",
        "modules": [],
        "warnings": [],
    }
    module = {
        "module_id": "l2_moneyflow",
        "title": "L2 大单资金流",
        "kind": "table",
        "status": "complete",
        "metrics": [],
        "items": [],
        "table": {"columns": [], "rows": []},
        "warnings": [],
        "provenance": {"source": "duckdb"},
    }
    store.append_stream_event(
        run_id,
        event_id="report:start",
        event_type="report_start",
        payload={"report": report},
    )
    store.append_stream_event(
        run_id,
        event_id="module:l2_moneyflow",
        event_type="report_module",
        payload={"module": module},
    )

    streamed = client.get(f"/api/runs/{run_id}/events").text
    assert "event: report_start" in streamed
    assert "event: report_module" in streamed
    assert "id: module:l2_moneyflow" in streamed

    current = client.get(f"/api/runs/{run_id}/report").json()
    assert current["modules"] == [module]


def test_missing_run_404(client: TestClient) -> None:
    assert client.get("/api/runs/run_nope").status_code == 404
    assert client.get("/api/runs/run_nope/trace").status_code == 404
    assert client.get("/api/runs/run_nope/context").status_code == 404


def test_run_artifact_path_traversal_rejected(client: TestClient) -> None:
    run_id = client.post("/api/runs", json={"question": "q"}).json()["run_id"]
    _wait_terminal(client, run_id)
    resp = client.get(f"/api/runs/{run_id}/artifacts/..%2Frun.json")
    assert resp.status_code in (404, 400)


def test_failed_run_surfaces_error(client: TestClient, monkeypatch) -> None:
    def failing(store, run_id, req):
        store.finish_run(run_id, rs.STATUS_FAILED, error="boom")

    monkeypatch.setattr(app_module, "_run_ask", failing)
    failed_client = TestClient(app_module.create_app())
    run_id = failed_client.post("/api/runs", json={"question": "q"}).json()["run_id"]
    run = _wait_terminal(failed_client, run_id)
    assert run["status"] == "failed"
    assert run["error"] == "boom"


def test_followups_endpoint_and_parent_link(client: TestClient, monkeypatch) -> None:
    from intelligence.services import followups as fu_svc

    def fake_run_ask(store: RunStore, run_id: str, req) -> None:
        followups = fu_svc.generate_followups(req.question, matched_theme="液冷", use_llm=False)
        store.add_artifact(
            run_id,
            "followups.json",
            followups.to_json(),
            renderer="json",
            title="猜你想问",
        )
        store.finish_run(run_id, rs.STATUS_COMPLETED)

    monkeypatch.setattr(app_module, "_run_ask", fake_run_ask)
    parent_id = client.post("/api/runs", json={"question": "液冷题材怎么看"}).json()["run_id"]
    _wait_terminal(client, parent_id)

    document = client.get(f"/api/runs/{parent_id}/followups").json()
    assert len(document["followups"]) == 5
    first = document["followups"][0]
    assert first["type"] == "evidence"
    assert "液冷" in first["question"]

    child_id = client.post(
        "/api/runs",
        json={"question": first["question"], "parent_run_id": parent_id},
    ).json()["run_id"]
    child = _wait_terminal(client, child_id)
    assert child["parent_run_id"] == parent_id


def test_followups_missing_returns_empty(client: TestClient) -> None:
    run_id = client.post("/api/runs", json={"question": "q"}).json()["run_id"]
    _wait_terminal(client, run_id)
    assert client.get(f"/api/runs/{run_id}/followups").json() == {"followups": []}


def test_run_context_projects_available_evidence(client: TestClient) -> None:
    run_id = client.post("/api/runs", json={"question": "q"}).json()["run_id"]
    _wait_terminal(client, run_id)
    context = client.get(f"/api/runs/{run_id}/context").json()
    assert context["evidence"][0]["label"] == "盘面快照"
    assert any(item["label"] == "盘面证据" for item in context["evidence"])
    assert context["memory"] == []
    assert context["review"] == []


def test_artifact_api_filters_describes_and_serves_registered_content(client: TestClient) -> None:
    artifacts = client.get("/api/artifacts", params={"category": "daily_agent", "date": "2026-07-09"}).json()
    html_artifact = next(item for item in artifacts if item["format"] == "html")
    assert not html_artifact["source_path"].startswith("/")
    assert html_artifact["canonical_exists"] is True

    detail = client.get(f"/api/artifacts/{html_artifact['artifact_id']}").json()
    assert detail["artifact_id"] == html_artifact["artifact_id"]

    content = client.get(f"/api/artifacts/{html_artifact['artifact_id']}/content")
    assert content.status_code == 200
    assert "<h1>daily</h1>" in content.text
    assert "sandbox" in content.headers["content-security-policy"]


def test_artifact_content_rejects_unregistered_and_traversal_ids(client: TestClient) -> None:
    assert client.get("/api/artifacts/not-registered/content").status_code == 404
    response = client.get("/api/artifacts/..%2Fetc%2Fpasswd/content")
    assert response.status_code in (404, 405)


def test_artifact_projection_and_registered_asset_routes(client: TestClient) -> None:
    artifacts = client.get("/api/artifacts").json()
    agent = next(
        item
        for item in artifacts
        if item["category"] == "daily_agent" and item["format"] == "json"
    )
    review = next(
        item
        for item in artifacts
        if item["category"] == "daily_review" and item["format"] == "html"
    )

    projection = client.get(f"/api/artifacts/{agent['artifact_id']}/projection")
    assert projection.status_code == 200
    assert projection.json()["report_type"] == "daily_agent"
    assert projection.json()["provenance"]["original_report_available"] is True
    assert (
        projection.json()["provenance"]["original_artifact_id"]
        != agent["artifact_id"]
    )

    review_projection = client.get(
        f"/api/artifacts/{review['artifact_id']}/projection"
    )
    assert review_projection.status_code == 200
    assert review_projection.json()["source_mode"] == "legacy_html_projection"

    asset = client.get(f"/api/artifacts/{review['artifact_id']}/chart.png")
    assert asset.status_code == 200
    assert asset.content == b"png"
    traversal = client.get(
        f"/api/artifacts/{review['artifact_id']}/..%2F..%2Fsecret.txt"
    )
    assert traversal.status_code in (403, 404)


def test_artifact_asset_route_rejects_non_legacy_parent(client: TestClient) -> None:
    artifact = next(
        item
        for item in client.get("/api/artifacts").json()
        if item["category"] == "daily_agent" and item["format"] == "json"
    )
    assert (
        client.get(f"/api/artifacts/{artifact['artifact_id']}/anything.png").status_code
        == 403
    )


def test_workflow_summary_does_not_claim_daily_review_projection(
    client: TestClient,
) -> None:
    artifact = next(
        item
        for item in client.get("/api/artifacts").json()
        if item["source_path"].endswith("daily-workflow-summary.json")
    )
    response = client.get(f"/api/artifacts/{artifact['artifact_id']}/projection")
    assert response.status_code == 404


def test_bootstrap_returns_workflows_runs_and_latest_artifact(client: TestClient) -> None:
    run_id = client.post("/api/runs", json={"question": "q"}).json()["run_id"]
    _wait_terminal(client, run_id)
    bootstrap = client.get("/api/workbench/bootstrap").json()
    assert [workflow["id"] for workflow in bootstrap["workflows"]] == [
        "daily",
        "theme",
        "stock_research",
    ]
    assert bootstrap["recent_runs"][0]["run_id"] == run_id
    assert bootstrap["latest_daily_artifact"]["date"] == "2026-07-09"
    assert bootstrap["data_cutoff"] == "2026-07-09"


def test_index_serves_workbench_page(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Workbench" in resp.text
