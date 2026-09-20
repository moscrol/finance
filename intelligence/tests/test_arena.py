from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from intelligence.arena.app import create_app
from intelligence.arena.demo import demo_matches
from intelligence.arena.models import Answer, Match, Strategy
from intelligence.arena.runner import AgentEndpoint, Task, call_agent, load_agents, request_json, run_pair, validate_endpoint
from intelligence.arena.store import ArenaError, ArenaStore, canonical, digest


@pytest.fixture
def store(tmp_path):
    return ArenaStore(tmp_path / "arena.sqlite3")


@pytest.fixture
def client(store):
    with TestClient(create_app(store)) as client:
        client.get("/api/arena/bootstrap")
        yield client


def post(client, path, body):
    boot = client.get("/api/arena/bootstrap").json()
    return client.post("/api/arena/" + path, json=body, headers={"X-Arena-Csrf": boot["csrf"]})


def assign(client, mode="demo"):
    return post(client, "assignments", {"mode": mode}).json()["assignment"]


def live_match(store, suffix="1", publish=True):
    original = demo_matches()[0].model_dump(mode="json")
    record = {"participants": [{"id": "agent-one", "name": "Agent One", "version": "v1", "kind": "agent"}, {"id": "agent-two", "name": "Agent Two", "version": "v1", "kind": "agent"}]}
    run_id = store.create_run(record)
    original.update(id="live-" + suffix, provenance="platform_run", run_id=run_id)
    for index, answer in enumerate(original["answers"]):
        answer["participant"] = record["participants"][index]
    match = Match.model_validate(original)
    record["match_digest"] = digest(canonical(match.model_dump(mode="json")))
    store.finish_run(run_id, record)
    store.add_match(match)
    if publish:
        store.publish(match.id)
    return match


def test_bootstrap_has_no_invented_stats_and_uses_private_cookie(client):
    response = client.get("/api/arena/bootstrap")
    assert response.json()["summary"] == {"live_cases": 0, "demo_cases": 4, "formal_votes": 0, "reviewers": 0}
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "arena_session" in client.cookies


def test_identity_and_run_receipt_hidden_until_vote(client):
    a = assign(client)
    assert "participant" not in a["answers"][0]
    assert "duration_seconds" not in a["answers"][0]
    assert a["receipt"] is None
    assert "sample-a" not in canonical(a)
    revealed = post(client, f"assignments/{a['id']}/vote", {"choice": "left"}).json()
    assert revealed["answers"][0]["participant"]["kind"] == "demo"
    assert revealed["receipt"]["match_sha256"]
    assert not revealed["vote"]["counted"]


def test_duplicate_assignment_resumes_same_randomization(client):
    first = assign(client)
    second = assign(client)
    assert first == second


def test_duplicate_vote_idempotent_and_change_rejected(client, store):
    a = assign(client)
    path = f"assignments/{a['id']}/vote"
    first = post(client, path, {"choice": "left", "reasons": ["evidence"]})
    second = post(client, path, {"choice": "left"})
    assert first.json() == second.json()
    assert post(client, path, {"choice": "right"}).status_code == 409
    with store.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM votes").fetchone()[0] == 1


def test_concurrent_votes_only_record_once(store):
    for m in demo_matches():
        store.add_match(m, published=True)
    s, _ = store.session(None)
    a = store.assign(s["id"], "demo", None)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: store.vote(s["id"], a["id"], "left", []), range(8)))
    assert len({r["vote"]["created_at"] for r in results}) == 1


def test_session_ownership_and_csrf(client, store):
    a = assign(client)
    with TestClient(create_app(store)) as other:
        assert other.get(f"/api/arena/assignments/{a['id']}").status_code == 404
        assert post(other, f"assignments/{a['id']}/vote", {"choice": "right"}).status_code == 404
    assert client.post("/api/arena/assignments", json={"mode": "demo"}).status_code == 403
    token = client.get("/api/arena/bootstrap").json()["csrf"]
    response = client.post("/api/arena/assignments", json={"mode": "demo"}, headers={"X-Arena-Csrf": token, "Origin": "https://evil.example"})
    assert response.status_code == 403


def test_skip_does_not_reveal_or_vote(client):
    a = assign(client)
    assert post(client, f"assignments/{a['id']}/skip", {}).status_code == 200
    skipped = client.get(f"/api/arena/assignments/{a['id']}").json()
    assert skipped["skipped"] and skipped["answers"][0].get("participant") is None
    assert post(client, f"assignments/{a['id']}/vote", {"choice": "left"}).status_code == 409
    assert assign(client)["id"] != a["id"]
    assert client.get("/api/arena/history").json()["votes"] == []


def test_invite_single_use_and_demo_never_promoted(client, store):
    a = assign(client)
    post(client, f"assignments/{a['id']}/vote", {"choice": "left"})
    code = store.issue_invite("reviewer")
    assert post(client, "join", {"code": code}).status_code == 200
    assert not client.get(f"/api/arena/assignments/{a['id']}").json()["vote"]["counted"]
    with TestClient(create_app(store)) as other:
        assert post(other, "join", {"code": code}).status_code == 403
    assert client.get("/api/arena/leaderboard").json()["formal_votes"] == 0


def test_formal_stats_exclude_guests_ties_are_separate(store):
    live_match(store)
    for index, choice in enumerate(["left", "right", "tie", "both_bad", "left"]):
        with TestClient(create_app(store)) as c:
            if index != 4:
                post(c, "join", {"code": store.issue_invite(str(index))})
            a = assign(c, "live")
            r = post(c, f"assignments/{a['id']}/vote", {"choice": choice})
            assert r.json()["vote"]["counted"] == (index != 4)
    board = store.leaderboard()
    assert board["formal_votes"] == 4
    assert sum(r["wins"] for r in board["rows"]) == 2
    assert sum(r["losses"] for r in board["rows"]) == 2
    for row in board["rows"]:
        assert row["decisive"] == 2
        assert row["ties"] == row["both_bad"] == 1
        assert row["reviewers"] == 4
        assert row["status"] == "collecting"
        assert row["win_rate"] == row["wins"] / 2
    assert board["pairs"][0]["ties"] == 1


def test_repeated_run_of_same_task_does_not_inflate_case_coverage(client, store):
    live_match(store, "first")
    live_match(store, "repeat")
    post(client, "join", {"code": store.issue_invite("coverage")})
    for _ in range(2):
        a = assign(client, "live")
        post(client, f"assignments/{a['id']}/vote", {"choice": "left"})
    assert store.leaderboard()["formal_votes"] == 2
    assert all(row["cases"] == 1 for row in store.leaderboard()["rows"])


def test_orientation_maps_vote_to_correct_agent(client, store):
    match = live_match(store)
    post(client, "join", {"code": store.issue_invite("judge")})
    a = assign(client, "live")
    chosen = 0 if a["answers"][0]["content"] == match.answers[0].content else 1
    post(client, f"assignments/{a['id']}/vote", {"choice": "left"})
    rows = store.leaderboard()["rows"]
    winner = next(r for r in rows if r["id"] == match.answers[chosen].participant.id)
    assert winner["wins"] == 1 and winner["win_rate"] == 1


def test_invalidation_excludes_votes_keeps_receipts(client, store):
    match = live_match(store)
    post(client, "join", {"code": store.issue_invite("judge")})
    a = assign(client, "live")
    post(client, f"assignments/{a['id']}/vote", {"choice": "left"})
    store.invalidate(match.id, "Identity leakage")
    assert store.leaderboard()["formal_votes"] == 0
    assert store.summary()["formal_votes"] == 0
    r = client.get(f"/api/arena/assignments/{a['id']}").json()
    assert not r["vote"]["counted"] and r["receipt"]
    assert r["invalid_reason"] == "Identity leakage"
    with pytest.raises(ArenaError):
        store.publish(match.id)


def test_manual_live_match_without_run_is_rejected(store):
    data = demo_matches()[0].model_dump(mode="json")
    data.update(provenance="platform_run", run_id="made-up")
    for answer in data["answers"]:
        answer["participant"]["kind"] = "agent"
    with pytest.raises(ArenaError):
        store.add_match(Match.model_validate(data))


def test_published_content_immutable(store):
    match = live_match(store)
    changed = match.model_copy(update={"question": "Can this original task be quietly overwritten?"})
    with pytest.raises(ArenaError):
        store.add_match(changed)


def test_unpublished_run_not_visible(client, store):
    live_match(store, publish=False)
    assert assign(client, "live") is None
    assert store.leaderboard()["rows"] == []


def test_question_consent_rate_limit_and_history(client):
    data = {"question": "请比较现金流与利润之间的差异，以及需要关注哪些风险？", "category": "financial", "consent": True}
    assert post(client, "questions", {**data, "consent": False}).status_code == 422
    for _ in range(5):
        assert post(client, "questions", data).status_code == 201
    assert post(client, "questions", data).status_code == 429
    history = client.get("/api/arena/history").json()
    assert len(history["questions"]) == 5
    assert all(q["status"] == "pending" for q in history["questions"])


def test_report_is_owned_and_idempotent(client, store):
    a = assign(client)
    for _ in range(2):
        assert post(client, f"assignments/{a['id']}/report", {"reason": "numbers", "detail": "Check ratio"}).status_code == 200
    with store.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 1


def test_no_zero_division_and_filters(store):
    live_match(store)
    assert all(r["win_rate"] is None for r in store.leaderboard()["rows"])
    assert store.leaderboard("event")["rows"] == []


def test_strategy_must_be_preregistered_and_not_overwritten(store):
    match = live_match(store)
    now = datetime.now(timezone.utc)
    payload = {"id": "strategy-1", "participant": match.answers[0].participant, "title": "A documented test strategy", "benchmark": "test benchmark", "starts_at": now + timedelta(days=1), "ends_at": now + timedelta(days=5), "holdings": [{"symbol": "600000.SH", "weight": .5}], "rules": "Fixed weight portfolio, explicit rebalance and transaction rules.", "source_run_id": match.run_id}
    strategy = Strategy.model_validate(payload)
    store.add_strategy(strategy)
    with pytest.raises(ArenaError):
        store.add_strategy(strategy)
    with pytest.raises(ArenaError):
        store.add_strategy(Strategy.model_validate({**payload, "id": "late", "starts_at": now - timedelta(days=1)}))
    result = store.strategies()[0]
    assert result["net_return"] is None and result["status"] == "scheduled"
    with pytest.raises(ValidationError):
        Strategy.model_validate({**payload, "holdings": [{"symbol": "600000.SH", "weight": float("nan")}]})


def test_limits_and_invite_expiry(store):
    store.limit("test", 1, 60)
    with pytest.raises(ArenaError, match="频繁"):
        store.limit("test", 1, 60)
    s, _ = store.session(None)
    with pytest.raises(ArenaError):
        store.join(s["id"], store.issue_invite("expired", days=-1))


def test_agent_config_refuses_fake_agent_label(tmp_path):
    path = tmp_path / "agents.json"
    path.write_text(canonical([{"participant": {"id": "one", "name": "one", "version": "v1", "kind": "agent"}, "protocol": "openai", "endpoint": "https://example.com/v1", "model": "x"}]))
    with pytest.raises(ValueError, match="kind=model"):
        load_agents(path)


@pytest.mark.parametrize("url", ["http://example.com", "https://user:password@example.com", "https://127.0.0.1", "https://169.254.169.254", "https://example.com?key=secret"])
def test_endpoint_restrictions(url):
    with pytest.raises(ValueError):
        validate_endpoint(url)


@pytest.mark.parametrize("address", ["8.8.8.8", "2606:4700:4700::1111"])
def test_local_override_does_not_allow_public_http(monkeypatch, address):
    monkeypatch.setattr("intelligence.arena.runner.socket.getaddrinfo", lambda *_args, **_kwargs: [(0, 0, 0, "", (address, 80))])
    with pytest.raises(ValueError, match="loopback"):
        validate_endpoint("http://public.example", allow_local=True)


@pytest.mark.parametrize("scheme", ["http", "https"])
@pytest.mark.parametrize("address", ["127.0.0.1", "::1"])
def test_local_override_keeps_loopback_available(monkeypatch, address, scheme):
    monkeypatch.setattr("intelligence.arena.runner.socket.getaddrinfo", lambda *_args, **_kwargs: [(0, 0, 0, "", (address, 80))])
    validate_endpoint(f"{scheme}://localhost", allow_local=True)


def test_local_override_rejects_mixed_dns_for_http(monkeypatch):
    addresses = [(0, 0, 0, "", (address, 80)) for address in ("127.0.0.1", "8.8.8.8")]
    monkeypatch.setattr("intelligence.arena.runner.socket.getaddrinfo", lambda *_args, **_kwargs: addresses)
    with pytest.raises(ValueError, match="loopback"):
        validate_endpoint("http://mixed.example", allow_local=True)


def test_leaderboard_reads_one_snapshot_during_publication(store, monkeypatch):
    first = live_match(store, "first")
    second = live_match(store, "second", publish=False)
    session, _ = store.session(None)
    store.join(session["id"], store.issue_invite("snapshot-reviewer"))
    assigned = store.assign(session["id"], "live", None)
    assert store.assignment(session["id"], assigned["id"])["receipt"] is None
    store.vote(session["id"], assigned["id"], "left", [])
    original_connect = store.connect
    inserted = []
    errors = []

    def publish_between_reads(statement):
        if "SELECT a.match_id,a.flipped,a.session_id,v.choice" not in statement or inserted:
            return
        inserted.append(True)
        try:
            store.publish(second.id)
            new_assignment = store.assign(session["id"], "live", None)
            store.vote(session["id"], new_assignment["id"], "right", [])
        except Exception as exc:
            errors.append(exc)

    @contextmanager
    def interleaved_connect(write=False):
        with original_connect(write=write) as con:
            if not write:
                con.set_trace_callback(publish_between_reads)
            yield con

    monkeypatch.setattr(store, "connect", interleaved_connect)
    board = store.leaderboard()
    assert inserted and not errors
    assert board["formal_votes"] == 1
    assert {row["key"] for row in board["rows"]} == {a.participant.key for a in first.answers}
    assert store.leaderboard()["formal_votes"] == 2


def test_response_size_is_bounded():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 250001))) as c:
            with pytest.raises(ValueError, match="response budget"):
                await request_json(c, "GET", "https://example.com")
    asyncio.run(run())


def test_runner_records_success_and_requires_publication(store, monkeypatch):
    agents = [AgentEndpoint(participant={"id": f"agent-{i}", "name": f"Test {i}", "version": "v1", "kind": "agent"}, protocol="arena-v1", endpoint="https://example.com") for i in range(2)]
    async def fake(agent, *_args, **_kwargs):
        return Answer(participant=agent.participant, content="A deliberately long raw answer for this deterministic adapter test.", duration_seconds=.1)
    monkeypatch.setattr("intelligence.arena.runner.call_agent", fake)
    task = Task(question="What explains the company's cash flow?", category="financial", as_of="2025-01-01")
    run_id = asyncio.run(run_pair(store, task, agents))
    assert store.summary()["live_cases"] == 0
    store.publish("run-" + run_id)
    assert store.summary()["live_cases"] == 1


def test_runner_failure_is_retained_not_retried(store, monkeypatch):
    agents = [AgentEndpoint(participant={"id": f"agent-{i}", "name": f"Test {i}", "version": "v1", "kind": "agent"}, protocol="arena-v1", endpoint="https://example.com") for i in range(2)]
    calls = []
    async def fake(agent, *_args, **_kwargs):
        calls.append(agent.participant.id)
        if len(calls) == 1:
            raise TimeoutError("No response")
        return Answer(participant=agent.participant, content="The successful peer result is retained even when its opponent fails.", duration_seconds=.1)
    monkeypatch.setattr("intelligence.arena.runner.call_agent", fake)
    task = Task(question="What explains the company's cash flow?", category="financial", as_of="2025-01-01")
    run_id = asyncio.run(run_pair(store, task, agents))
    with store.connect() as con:
        row = con.execute("SELECT status,payload FROM runs WHERE id=?", (run_id,)).fetchone()
    assert row["status"] == "failed" and "successful peer" in row["payload"]
    assert len(calls) == 2 and store.summary()["live_cases"] == 0


def test_question_runs_once_and_can_be_evaluated_after_publication(client, store, monkeypatch):
    question = "请比较两家企业的利润与现金流，哪些证据能够判断盈利质量？"
    q = post(client, "questions", {"question": question, "category": "financial", "consent": True}).json()["id"]
    agents = [AgentEndpoint(participant={"id": f"agent-{i}", "name": f"Runner {i}", "version": "v1", "kind": "agent"}, protocol="arena-v1", endpoint="https://example.com") for i in range(2)]
    async def fake(agent, *_args, **_kwargs):
        return Answer(participant=agent.participant, content="A sufficiently detailed raw response from a controlled test fixture.", duration_seconds=.2)
    monkeypatch.setattr("intelligence.arena.runner.call_agent", fake)
    task = Task(question=question, category="financial", as_of="2025-01-01")
    run_id = asyncio.run(run_pair(store, task, agents, question_id=q))
    assert client.get("/api/arena/history").json()["questions"][0]["status"] == "review"
    with pytest.raises(ArenaError):
        asyncio.run(run_pair(store, task, agents, question_id=q))
    store.publish("run-" + run_id)
    assert client.get("/api/arena/history").json()["questions"][0]["status"] == "published"
    response = post(client, "assignments", {"mode": "live", "question_id": q})
    assert response.status_code == 200 and response.json()["assignment"]["question"] == question
    assert post(client, "assignments", {"mode": "live", "question_id": q}).json() == response.json()
    with TestClient(create_app(store)) as other:
        assert post(other, "assignments", {"mode": "live", "question_id": q}).status_code == 404
    store.invalidate("run-" + run_id, "fixture withdrawal")
    assert client.get("/api/arena/history").json()["questions"][0]["status"] == "withdrawn"


def test_remote_async_contract_and_credential_not_persisted(store, monkeypatch):
    import json
    calls = []
    def upstream(request):
        calls.append(request)
        assert request.headers["authorization"] == "Bearer test-only-key"
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["anonymous"] is True and body["limits"]["deadline"]
            return httpx.Response(200, json={"run_id": "remote-1", "status": "running"})
        return httpx.Response(200, json={"run_id": "remote-1", "status": "completed", "answer": {"content": "A complete raw answer with no participant identity embedded in it."}})
    client_class = httpx.AsyncClient
    monkeypatch.setattr("intelligence.arena.runner.validate_endpoint", lambda *_args: None)
    monkeypatch.setattr("intelligence.arena.runner.httpx.AsyncClient", lambda **kwargs: client_class(transport=httpx.MockTransport(upstream), **kwargs))
    monkeypatch.setenv("TEST_ARENA_KEY", "test-only-key")
    agents = [AgentEndpoint(participant={"id": "same-product", "name": "Test product", "version": version, "kind": "agent"}, protocol="arena-v1", endpoint="https://example.com", api_key_env="TEST_ARENA_KEY") for version in ("v1", "v2")]
    task = Task(question="Compare the evidence supplied for the two businesses.", category="financial", as_of="2025-01-01")
    run_id = asyncio.run(run_pair(store, task, agents))
    posts = [json.loads(r.content) for r in calls if r.method == "POST"]
    assert len(posts) == 2 and posts[0]["request_id"] != posts[1]["request_id"]
    with store.connect() as con:
        run = con.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    assert run["status"] == "completed" and "test-only-key" not in run["payload"]


@pytest.mark.parametrize("returned_id", ["another-run", None])
def test_remote_poll_rejects_unrelated_result(monkeypatch, returned_id):
    calls = []
    def upstream(request):
        calls.append(request.method)
        if request.method == "POST":
            return httpx.Response(200, json={"run_id": "expected-run", "status": "running"})
        return httpx.Response(200, json={"run_id": returned_id, "status": "completed", "answer": {"content": "This answer belongs to an unrelated run and must never be accepted."}})
    client_class = httpx.AsyncClient
    monkeypatch.setattr("intelligence.arena.runner.validate_endpoint", lambda *_args: None)
    monkeypatch.setattr("intelligence.arena.runner.httpx.AsyncClient", lambda **kwargs: client_class(transport=httpx.MockTransport(upstream), **kwargs))
    agent = AgentEndpoint(participant={"id": "test-agent", "name": "Test", "version": "v1"}, protocol="arena-v1", endpoint="https://example.com")
    task = Task(question="A research request with a correlated remote result.", category="financial", as_of="2025-01-01")
    with pytest.raises(ValueError, match="run_id"):
        asyncio.run(call_agent(agent, task, "local-run", 5))
    assert calls == ["POST", "GET"]


def test_remote_mismatch_fails_run_without_publishable_match(store, monkeypatch):
    requests = []
    def upstream(request):
        requests.append((request.method, request.url.path))
        remote_id = request.url.host
        if request.method == "POST":
            return httpx.Response(200, json={"run_id": remote_id, "status": "running"})
        return httpx.Response(200, json={"run_id": "unrelated" if remote_id == "bad.example" else remote_id, "status": "completed", "answer": {"content": "A complete answer for this isolated deterministic adapter check."}})
    client_class = httpx.AsyncClient
    monkeypatch.setattr("intelligence.arena.runner.validate_endpoint", lambda *_args: None)
    monkeypatch.setattr("intelligence.arena.runner.httpx.AsyncClient", lambda **kwargs: client_class(transport=httpx.MockTransport(upstream), **kwargs))
    agents = [AgentEndpoint(participant={"id": name, "name": name, "version": "v1"}, protocol="arena-v1", endpoint=f"https://{name}.example") for name in ("bad", "good")]
    task = Task(question="Compare these two research results with a fixed request identity.", category="financial", as_of="2025-01-01")
    session, _ = store.session(None)
    question_id = store.question(session["id"], task.question, task.category)
    run_id = asyncio.run(run_pair(store, task, agents, question_id=question_id))
    with store.connect() as con:
        run = con.execute("SELECT status,payload FROM runs WHERE id=?", (run_id,)).fetchone()
        assert con.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 0
    assert run["status"] == "failed" and "ValueError" in run["payload"]
    assert "complete answer" in run["payload"]
    assert store.history(session["id"])["questions"][0]["status"] == "failed"
    assert len(requests) == 4
    with pytest.raises(ArenaError, match="不存在"):
        store.publish("run-" + run_id)
    with pytest.raises(ArenaError, match="重复"):
        asyncio.run(run_pair(store, task, agents, question_id=question_id))
    assert len(requests) == 4


def test_remote_timeout_requests_cancellation(monkeypatch):
    calls = []
    def upstream(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"run_id": "pending", "status": "running"})
    client_class = httpx.AsyncClient
    monkeypatch.setattr("intelligence.arena.runner.validate_endpoint", lambda *_args: None)
    monkeypatch.setattr("intelligence.arena.runner.httpx.AsyncClient", lambda **kwargs: client_class(transport=httpx.MockTransport(upstream), **kwargs))
    agent = AgentEndpoint(participant={"id": "test-agent", "name": "Test", "version": "v1"}, protocol="arena-v1", endpoint="https://example.com")
    task = Task(question="A long-running research request.", category="financial", as_of="2025-01-01")
    with pytest.raises(TimeoutError):
        asyncio.run(call_agent(agent, task, "local-run", .02))
    assert calls == ["/runs", "/runs/pending/cancel"]
