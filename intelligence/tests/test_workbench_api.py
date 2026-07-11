import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from intelligence.api import app as app_module  # noqa: E402
from intelligence.services import run_store as rs  # noqa: E402
from intelligence.services.conversation_store import ConversationStore  # noqa: E402
from intelligence.services.run_store import RunStore  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    users_root = tmp_path / "users"
    repo_root = tmp_path / "repo"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users_root))
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))

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

    def fake_run_conversation_turn(**kwargs: object) -> None:
        run_store = kwargs["run_store"]
        run_id = kwargs["run_id"]
        assert isinstance(run_store, RunStore)
        assert isinstance(run_id, str)
        run_store.finish_run(run_id, rs.STATUS_COMPLETED)

    monkeypatch.setattr(app_module, "_run_ask", fake_run_ask)
    monkeypatch.setattr(
        app_module,
        "_run_conversation_turn",
        fake_run_conversation_turn,
    )
    return TestClient(app_module.create_app(repo_root=repo_root))


def _wait_terminal(client: TestClient, run_id: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in ("completed", "failed", "cancelled"):
            return run
        time.sleep(0.05)
    raise AssertionError("run 未在超时内到终态")


def test_session_byok_api_is_user_scoped_and_never_returns_key(
    client: TestClient,
) -> None:
    configured = client.put(
        "/api/llm/config",
        json={
            "provider": "zhipu",
            "api_key": "glm-secret-value",
            "model": "glm-4-air",
            "user": "alice",
        },
    )

    assert configured.status_code == 200
    assert configured.json() == {
        "mode": "byok",
        "display_name": "自带密钥",
        "ready": True,
        "session_only": True,
        "built_in_ready": configured.json()["built_in_ready"],
        "provider": "zhipu",
        "model": "glm-4-air",
    }
    assert "glm-secret-value" not in configured.text
    assert client.get("/api/llm/config", params={"user": "bob"}).json()["mode"] == "built_in"

    restored = client.delete("/api/llm/config", params={"user": "alice"})
    assert restored.status_code == 200
    assert restored.json()["mode"] == "built_in"
    assert restored.json()["session_only"] is False


def test_session_byok_api_rejects_unknown_provider_and_short_key(
    client: TestClient,
) -> None:
    unknown = client.put(
        "/api/llm/config",
        json={"provider": "custom", "api_key": "long-enough", "user": "alice"},
    )
    short = client.put(
        "/api/llm/config",
        json={"provider": "zhipu", "api_key": "short", "user": "alice"},
    )

    assert unknown.status_code == 422
    assert short.status_code == 422
    assert "short" not in short.text


def test_session_byok_flows_to_the_conversation_worker(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: list[object] = []
    finished = threading.Event()

    def capture_run_conversation_turn(**kwargs: object) -> None:
        captured.append(kwargs["llm_provider"])
        run_store = kwargs["run_store"]
        run_id = kwargs["run_id"]
        assert isinstance(run_store, RunStore)
        assert isinstance(run_id, str)
        run_store.finish_run(run_id, rs.STATUS_COMPLETED)
        finished.set()

    monkeypatch.setattr(
        app_module,
        "_run_conversation_turn",
        capture_run_conversation_turn,
    )
    assert client.put(
        "/api/llm/config",
        json={
            "provider": "zhipu",
            "api_key": "glm-secret-value",
            "user": "alice",
        },
    ).status_code == 200
    conversation_id = client.post(
        "/api/conversations",
        json={"user": "alice"},
    ).json()["conversation_id"]

    response = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "研究半导体", "skill_mode": "auto", "user": "alice"},
    )

    assert response.status_code == 202
    assert finished.wait(timeout=2)
    provider = captured[0]
    assert isinstance(provider, app_module.LLMProvider)
    assert provider.name == "zhipu"
    assert provider.model == "glm-5.2"
    assert provider.api_key == "glm-secret-value"


def test_conversation_worker_passes_selected_model_to_orchestrator(
    monkeypatch,
    tmp_path,
) -> None:
    captured: dict[str, object] = {}

    class CapturingOrchestrator:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def run_turn(self, **kwargs: object) -> None:
            captured["run_turn"] = kwargs

    monkeypatch.setattr(app_module, "TurnOrchestrator", CapturingOrchestrator)
    provider = app_module.LLMProvider(
        "zhipu",
        "secret-value",
        "https://open.bigmodel.cn/api/paas/v4",
        "glm-4-flash",
    )

    app_module._run_conversation_turn(
        repo_root=tmp_path,
        conversation_store=object(),
        run_store=object(),
        conversation_id="conversation",
        run_id="run",
        assistant_message_id="message",
        query="研究低空经济",
        skill_mode="auto",
        selected_skill_ids=[],
        cancellation_signal=app_module.CancellationSignal(),
        llm_provider=provider,
    )

    assert captured["llm_model"] == "glm-4-flash"


def test_conversation_lifecycle_and_messages_persist(client: TestClient) -> None:
    created = client.post(
        "/api/conversations", json={"title": "盘面讨论", "user": "alice"}
    )
    assert created.status_code == 200
    conversation = created.json()
    conversation_id = conversation["conversation_id"]
    assert conversation["title"] == "盘面讨论"
    assert client.get("/api/conversations", params={"user": "alice"}).json() == [conversation]
    assert client.get(
        f"/api/conversations/{conversation_id}", params={"user": "alice"}
    ).json() == conversation

    renamed = client.patch(
        f"/api/conversations/{conversation_id}",
        json={"title": "收盘复盘", "user": "alice"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "收盘复盘"

    sent = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={
            "content": "今天市场怎么样？",
            "skill_mode": "hybrid",
            "selected_skill_ids": ["daily-review"],
            "user": "alice",
        },
    )
    assert sent.status_code == 202
    response = sent.json()
    assert response["conversation_id"] == conversation_id
    assert set(response) == {
        "conversation_id", "user_message_id", "assistant_message_id", "run_id"
    }
    messages = client.get(
        f"/api/conversations/{conversation_id}/messages", params={"user": "alice"}
    ).json()
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "今天市场怎么样？"
    assert messages[0]["selected_skill_ids"] == ["daily-review"]
    assert messages[1]["status"] == "pending"
    assert messages[1]["run_id"] == response["run_id"]

    run = client.get(f"/api/runs/{response['run_id']}", params={"user": "alice"}).json()
    assert run["session_id"] == conversation_id
    assert run["parent_run_id"] is None
    disk_conversation = client.get(
        f"/api/conversations/{conversation_id}", params={"user": "alice"}
    ).json()
    assert disk_conversation["last_run_id"] == response["run_id"]

    archived = client.post(
        f"/api/conversations/{conversation_id}/archive", json={"user": "alice"}
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"


def test_conversation_message_run_parent_chains_across_turns(client: TestClient) -> None:
    conversation_id = client.post(
        "/api/conversations", json={"user": "alice"}
    ).json()["conversation_id"]
    first = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "第一轮", "skill_mode": "auto", "user": "alice"},
    ).json()
    second = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "第二轮", "skill_mode": "manual", "user": "alice"},
    ).json()
    second_run = client.get(
        f"/api/runs/{second['run_id']}", params={"user": "alice"}
    ).json()
    assert second_run["parent_run_id"] == first["run_id"]
    assert len(client.get(
        f"/api/conversations/{conversation_id}/messages", params={"user": "alice"}
    ).json()) == 4


def test_concurrent_messages_are_paired_and_runs_form_one_linear_chain(
    client: TestClient,
) -> None:
    conversation_id = client.post(
        "/api/conversations", json={"user": "alice"}
    ).json()["conversation_id"]
    original_create_run = RunStore.create_run

    def slow_create_run(self: RunStore, *args: object, **kwargs: object):
        run = original_create_run(self, *args, **kwargs)
        time.sleep(0.02)
        return run

    def send(index: int) -> dict[str, str]:
        response = client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": f"并发-{index}", "skill_mode": "auto", "user": "alice"},
        )
        assert response.status_code == 202
        return response.json()

    with patch.object(RunStore, "create_run", slow_create_run):
        with ThreadPoolExecutor(max_workers=6) as pool:
            responses = list(pool.map(send, range(6)))

    messages = client.get(
        f"/api/conversations/{conversation_id}/messages", params={"user": "alice"}
    ).json()
    assert [message["role"] for message in messages] == ["user", "assistant"] * 6
    assert all(
        messages[index]["run_id"] == messages[index + 1]["run_id"]
        for index in range(0, len(messages), 2)
    )

    runs = {
        response["run_id"]: client.get(
            f"/api/runs/{response['run_id']}", params={"user": "alice"}
        ).json()
        for response in responses
    }
    roots = [run for run in runs.values() if run["parent_run_id"] is None]
    assert len(roots) == 1
    children_by_parent = {
        run_id: [child for child in runs.values() if child["parent_run_id"] == run_id]
        for run_id in runs
    }
    assert sorted(len(children) for children in children_by_parent.values()) == [0, 1, 1, 1, 1, 1]
    assert len(client.app.state.conversation_locks) == 1


def test_second_message_append_failure_marks_created_run_failed(
    client: TestClient,
) -> None:
    conversation_id = client.post(
        "/api/conversations", json={"user": "alice"}
    ).json()["conversation_id"]
    original_append = ConversationStore.append_message
    append_count = 0

    def fail_second_append(
        self: ConversationStore, *args: object, **kwargs: object
    ):
        nonlocal append_count
        append_count += 1
        if append_count == 2:
            raise RuntimeError("secret persistence detail")
        return original_append(self, *args, **kwargs)

    with patch.object(ConversationStore, "append_message", fail_second_append):
        with pytest.raises(RuntimeError, match="secret persistence detail"):
            client.post(
                f"/api/conversations/{conversation_id}/messages",
                json={"content": "触发追加失败", "skill_mode": "auto", "user": "alice"},
            )
    runs = client.get("/api/runs", params={"user": "alice"}).json()
    assert len(runs) == 1
    assert runs[0]["status"] == "failed"
    assert runs[0]["error"] == "message persistence or submission failed"
    assert "secret persistence detail" not in json.dumps(runs[0])
    messages = client.get(
        f"/api/conversations/{conversation_id}/messages", params={"user": "alice"}
    ).json()
    assert [message["role"] for message in messages] == ["user"]


def test_append_and_failure_state_persistence_errors_surface_generic_runtime_error(
    client: TestClient,
) -> None:
    conversation_id = client.post(
        "/api/conversations", json={"user": "alice"}
    ).json()["conversation_id"]

    def fail_append(*args: object, **kwargs: object) -> None:
        raise RuntimeError("secret append detail")

    def fail_finish(*args: object, **kwargs: object) -> None:
        raise RuntimeError("secret compensation detail")

    with (
        patch.object(ConversationStore, "append_message", fail_append),
        patch.object(RunStore, "finish_run", fail_finish),
        pytest.raises(RuntimeError) as exc_info,
    ):
        client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "触发双重失败", "skill_mode": "auto", "user": "alice"},
        )

    assert str(exc_info.value) == "failed to persist run failure state"
    assert "secret append detail" not in str(exc_info.value)
    assert "secret compensation detail" not in str(exc_info.value)
    persisted = json.dumps(
        client.get("/api/runs", params={"user": "alice"}).json(), ensure_ascii=False
    )
    assert "secret append detail" not in persisted
    assert "secret compensation detail" not in persisted


def test_executor_submit_failure_marks_created_run_failed(client: TestClient) -> None:
    conversation_id = client.post(
        "/api/conversations", json={"user": "alice"}
    ).json()["conversation_id"]

    def fail_submit(*args: object, **kwargs: object) -> None:
        raise RuntimeError("secret executor detail")

    with patch.object(client.app.state.supervisor._executor, "submit", fail_submit):
        with pytest.raises(RuntimeError, match="secret executor detail"):
            client.post(
                f"/api/conversations/{conversation_id}/messages",
                json={"content": "触发提交失败", "skill_mode": "auto", "user": "alice"},
            )
    runs = client.get("/api/runs", params={"user": "alice"}).json()
    assert len(runs) == 1
    assert runs[0]["status"] == "failed"
    assert runs[0]["error"] == "message persistence or submission failed"
    assert "secret executor detail" not in json.dumps(runs[0])
    messages = client.get(
        f"/api/conversations/{conversation_id}/messages", params={"user": "alice"}
    ).json()
    assert [message["role"] for message in messages] == ["user", "assistant"]


@pytest.mark.parametrize("path", ["/api/conversations", "/api/conversations/{conversation_id}"])
def test_conversation_titles_reject_blank_whitespace(
    client: TestClient, path: str
) -> None:
    conversation_id = client.post(
        "/api/conversations", json={"user": "alice"}
    ).json()["conversation_id"]
    resolved_path = path.format(conversation_id=conversation_id)
    response = client.request(
        "POST" if path == "/api/conversations" else "PATCH",
        resolved_path,
        json={"title": "   ", "user": "alice"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("get", "/api/conversations/..%2Falice", None),
        ("patch", "/api/conversations/..%2Falice", {"title": "x"}),
        ("post", "/api/conversations/..%2Falice/archive", {}),
        ("get", "/api/conversations/..%2Falice/messages", None),
        ("post", "/api/conversations/..%2Falice/messages", {"content": "x", "skill_mode": "auto"}),
        ("post", "/api/runs/..%2Falice/cancel", {}),
    ],
)
def test_all_new_id_routes_reject_traversal(
    client: TestClient, method: str, path: str, json_body: dict | None
) -> None:
    response = client.request(method, path, params={"user": "alice"}, json=json_body)
    assert response.status_code in (404, 422)
    assert "/Users/" not in response.text


def test_conversation_input_validation_and_user_isolation(client: TestClient) -> None:
    conversation_id = client.post(
        "/api/conversations", json={"user": "alice"}
    ).json()["conversation_id"]
    for body in (
        {"content": "", "skill_mode": "auto", "user": "alice"},
        {"content": "   ", "skill_mode": "auto", "user": "alice"},
        {"content": "x", "skill_mode": "invalid", "user": "alice"},
    ):
        assert client.post(
            f"/api/conversations/{conversation_id}/messages", json=body
        ).status_code == 422
    assert client.get(
        f"/api/conversations/{conversation_id}", params={"user": "bob"}
    ).status_code == 404
    assert client.get("/api/conversations", params={"user": "bob"}).json() == []


def test_message_rejects_unknown_product_skill_before_creating_run(
    client: TestClient,
) -> None:
    conversation_id = client.post(
        "/api/conversations", json={"user": "alice"}
    ).json()["conversation_id"]

    response = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={
            "content": "执行未知 skill",
            "skill_mode": "manual",
            "selected_skill_ids": ["unknown"],
            "user": "alice",
        },
    )

    assert response.status_code == 422
    assert client.get("/api/runs", params={"user": "alice"}).json() == []


def test_skills_lists_registered_product_skills(client: TestClient) -> None:
    skills = client.get("/api/skills").json()

    assert [skill["skill_id"] for skill in skills] == ["daily-review", "daily-agent"]
    assert all(skill["permissions"] == ["local_read"] for skill in skills)


def test_skills_serializes_only_product_registry_definitions(client: TestClient) -> None:
    @dataclass(frozen=True)
    class FakeSkillDefinition:
        skill_id: str
        name: str
        description: str
        version: str
        triggers: list[str]
        input_schema: dict[str, object]
        permissions: list[str]
        timeout_seconds: int

    definition = FakeSkillDefinition(
        skill_id="daily-review",
        name="每日复盘",
        description="生成每日市场复盘",
        version="1.0.0",
        triggers=["复盘", "市场"],
        input_schema={"type": "object"},
        permissions=["market:read"],
        timeout_seconds=30,
    )
    imported: list[str] = []

    def fake_import_module(name: str):
        imported.append(name)
        return SimpleNamespace(SKILL_REGISTRY={definition.skill_id: definition})

    with patch.object(app_module, "import_module", fake_import_module):
        assert client.get("/api/skills").json() == [
            {
                "skill_id": "daily-review",
                "name": "每日复盘",
                "description": "生成每日市场复盘",
                "version": "1.0.0",
                "triggers": ["复盘", "市场"],
                "input_schema": {"type": "object"},
                "permissions": ["market:read"],
                "timeout_seconds": 30,
            }
        ]
    assert imported == ["intelligence.workbench_skills.registry"]
    assert all("skill_tools" not in name for name in imported)


def test_cancel_missing_run_and_idempotence(client: TestClient) -> None:
    assert client.post("/api/runs/run_missing/cancel").status_code == 404
    run_id = client.post(
        "/api/runs", json={"question": "q", "user": "alice"}
    ).json()["run_id"]
    assert client.post(
        f"/api/runs/{run_id}/cancel", params={"user": "bob"}
    ).status_code == 404
    assert client.app.state.cancellation_registry == {}
    first = client.post(
        f"/api/runs/{run_id}/cancel", params={"user": "alice"}
    ).json()
    second = client.post(
        f"/api/runs/{run_id}/cancel", params={"user": "alice"}
    ).json()
    assert first == second == {
        "run_id": run_id,
        "status": "completed",
        "cancel_requested": True,
    }
    assert client.app.state.cancellation_registry == {}


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


def test_health_endpoints_report_worker_and_storage_state(client: TestClient) -> None:
    health = client.get("/api/health").json()
    assert health["status"] == "healthy"
    assert health["dependencies"]["knowledge_wiki"] is True

    response = client.get("/api/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["repo_root"] is True
    assert payload["checks"]["run_store_writable"] is True
    assert payload["workers"]["capacity"] == 2


def test_cancel_run_is_terminal_even_when_worker_finishes_later(
    client: TestClient,
    monkeypatch,
) -> None:
    started = threading.Event()
    release = threading.Event()

    def slow_run(store, run_id, req):
        started.set()
        release.wait(timeout=2)
        store.finish_run(run_id, rs.STATUS_COMPLETED)

    monkeypatch.setattr(app_module, "_run_ask", slow_run)
    run_id = client.post("/api/runs", json={"question": "q"}).json()["run_id"]
    assert started.wait(timeout=1)

    cancelled = client.post(f"/api/runs/{run_id}/cancel")
    release.set()

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    time.sleep(0.05)
    assert client.get(f"/api/runs/{run_id}").json()["status"] == "cancelled"


def test_executor_timeout_marks_run_failed(tmp_path, monkeypatch) -> None:
    users_root = tmp_path / "users"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users_root))
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))
    release = threading.Event()

    def slow_run(store, run_id, req):
        release.wait(timeout=1)
        if not app_module._run_terminal(store, run_id):
            store.finish_run(run_id, rs.STATUS_COMPLETED)

    monkeypatch.setattr(app_module, "_run_ask", slow_run)
    timeout_client = TestClient(
        app_module.create_app(repo_root=tmp_path, run_timeout_sec=0.05)
    )
    run_id = timeout_client.post("/api/runs", json={"question": "q"}).json()["run_id"]

    run = _wait_terminal(timeout_client, run_id)
    release.set()

    assert run["status"] == "failed"
    assert run["error"] == "executor_timeout"
    assert run["degrades"] == ["executor_timeout"]


def test_executor_timeout_marks_pending_conversation_message_failed(
    tmp_path,
    monkeypatch,
) -> None:
    users_root = tmp_path / "users"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users_root))
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))
    release = threading.Event()

    def slow_turn(**kwargs: object) -> None:
        release.wait(timeout=1)

    monkeypatch.setattr(app_module, "_run_conversation_turn", slow_turn)
    with TestClient(
        app_module.create_app(repo_root=tmp_path, run_timeout_sec=0.05)
    ) as timeout_client:
        conversation_id = timeout_client.post(
            "/api/conversations",
            json={"title": "超时对话"},
        ).json()["conversation_id"]
        run_id = timeout_client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "等待超时", "skill_mode": "auto"},
        ).json()["run_id"]

        run = _wait_terminal(timeout_client, run_id)
        messages = timeout_client.get(
            f"/api/conversations/{conversation_id}/messages"
        ).json()
        release.set()

    assert run["status"] == "failed"
    assert run["error"] == "executor_timeout"
    assert messages[-1]["status"] == "failed"
    assert "本轮执行超时" in messages[-1]["degrades"]


def test_cancel_terminalizes_running_conversation_message(
    tmp_path,
    monkeypatch,
) -> None:
    users_root = tmp_path / "users"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users_root))
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))
    started = threading.Event()
    release = threading.Event()

    def slow_turn(**kwargs: object) -> None:
        started.set()
        release.wait(timeout=1)

    monkeypatch.setattr(app_module, "_run_conversation_turn", slow_turn)
    with TestClient(app_module.create_app(repo_root=tmp_path)) as cancel_client:
        conversation_id = cancel_client.post(
            "/api/conversations",
            json={"title": "取消对话"},
        ).json()["conversation_id"]
        run_id = cancel_client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "等待取消", "skill_mode": "auto"},
        ).json()["run_id"]
        assert started.wait(timeout=1)

        cancelled = cancel_client.post(f"/api/runs/{run_id}/cancel").json()
        messages = cancel_client.get(
            f"/api/conversations/{conversation_id}/messages"
        ).json()
        release.set()

    assert cancelled["status"] == "cancelled"
    assert messages[-1]["status"] == "cancelled"
    assert "用户已取消本轮执行" in messages[-1]["degrades"]


def test_create_app_recovers_interrupted_runs(tmp_path, monkeypatch) -> None:
    users_root = tmp_path / "users"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users_root))
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))
    interrupted = RunStore().create_run("q", "ask")
    finished = threading.Event()

    def recovered_run(store, run_id, req):
        store.finish_run(run_id, rs.STATUS_COMPLETED)
        finished.set()

    monkeypatch.setattr(app_module, "_run_ask", recovered_run)
    recovered_client = TestClient(app_module.create_app(repo_root=tmp_path))
    assert finished.wait(timeout=1)
    recovered = recovered_client.get(f"/api/runs/{interrupted.run_id}").json()
    readiness = recovered_client.get("/api/readiness").json()

    assert recovered["status"] == "completed"
    assert recovered["degrades"] == ["workbench_restarted_before_completion"]
    events = RunStore().load_stream_events(interrupted.run_id)
    assert events[0]["event_type"] == "run_recovered"
    assert readiness["recovered_runs"] == 1


def test_create_app_recovers_interrupted_conversation_turn(tmp_path, monkeypatch) -> None:
    users_root = tmp_path / "users"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users_root))
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))

    run_store = RunStore()
    conversation_store = ConversationStore(user_id=run_store.user_id)
    conversation = conversation_store.create_conversation("恢复对话")
    run = run_store.create_run(
        "继续研究",
        "ask",
        session_id=conversation.conversation_id,
    )
    user_message = conversation_store.append_message(
        conversation.conversation_id,
        "user",
        "继续研究",
        run_id=run.run_id,
        skill_mode="manual",
        selected_skill_ids=["daily-agent"],
    )
    assistant_message = conversation_store.append_message(
        conversation.conversation_id,
        "assistant",
        "",
        status="pending",
        run_id=run.run_id,
    )
    conversation_store.update_summary(
        conversation.conversation_id,
        "",
        last_run_id=run.run_id,
    )
    run_store.mark_running(run.run_id)
    run_store.append_stream_event(
        run.run_id,
        event_id="message:start",
        event_type="message.start",
        payload={"status": "running"},
        conversation_id=conversation.conversation_id,
        message_id=assistant_message.message_id,
    )

    finished = threading.Event()
    captured: dict[str, object] = {}

    def recovered_turn(**kwargs: object) -> None:
        captured.update(kwargs)
        recovered_store = kwargs["run_store"]
        recovered_run_id = kwargs["run_id"]
        assert isinstance(recovered_store, RunStore)
        assert isinstance(recovered_run_id, str)
        recovered_store.finish_run(recovered_run_id, rs.STATUS_COMPLETED)
        finished.set()

    def unexpected_legacy_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("conversation recovery must not use the legacy ask runner")

    monkeypatch.setattr(app_module, "_run_conversation_turn", recovered_turn)
    monkeypatch.setattr(app_module, "_run_ask", unexpected_legacy_run)

    with TestClient(app_module.create_app(repo_root=tmp_path)) as recovered_client:
        assert finished.wait(timeout=1)
        recovered = recovered_client.get(f"/api/runs/{run.run_id}").json()

    assert recovered["status"] == "completed"
    assert captured["conversation_id"] == conversation.conversation_id
    assert captured["assistant_message_id"] == assistant_message.message_id
    assert captured["query"] == user_message.content
    assert captured["skill_mode"] == "manual"
    assert captured["selected_skill_ids"] == ["daily-agent"]
    assert str(captured["event_id_prefix"]).startswith("recovery:")


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
    resumed = client.get(
        f"/api/runs/{run_id}/events",
        headers={"Last-Event-ID": "report:start"},
    ).text
    assert "event: report_start" not in resumed
    assert "event: report_module" in resumed

    current = client.get(f"/api/runs/{run_id}/report").json()
    assert current["modules"] == [module]


def test_sse_canonical_alias_cursor_and_terminal_replay(client: TestClient) -> None:
    run_id = client.post("/api/runs", json={"question": "q"}).json()["run_id"]
    _wait_terminal(client, run_id)
    store = RunStore()
    start = store.append_stream_event(
        run_id, event_id="report:start:new", event_type="report.start", payload={"report": {"modules": []}}
    )
    module = store.append_stream_event(
        run_id, event_id="report:module:new", event_type="report.module", payload={"module": {"module_id": "m1"}}
    )

    full = client.get(f"/api/runs/{run_id}/events").text
    assert "event: report.start" in full and "event: report_start" in full
    assert full.count(f"id: {start['event_id']}") == 2
    assert "event: step" in full and "event: run" in full

    after = client.get(f"/api/runs/{run_id}/events", params={"after": start["seq"]}).text
    assert "event: step" not in after
    assert "report:start:new" not in after
    assert "report:module:new" in after

    header = client.get(
        f"/api/runs/{run_id}/events", headers={"Last-Event-ID": start["event_id"]}
    ).text
    assert "report:start:new" not in header and "report:module:new" in header
    numeric = client.get(
        f"/api/runs/{run_id}/events", headers={"Last-Event-ID": str(module["seq"])}
    ).text
    assert "report:module:new" not in numeric


def test_sse_rejects_negative_after(client: TestClient) -> None:
    run_id = client.post("/api/runs", json={"question": "q"}).json()["run_id"]
    assert client.get(f"/api/runs/{run_id}/events", params={"after": -1}).status_code == 422


def test_sse_initial_connection_keeps_polling_trace_after_report_event(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RunStore()
    run = store.create_run("live trace", "ask")
    store.append_step(
        run.run_id, step_id="s01", name="first", status="completed"
    )
    store.append_stream_event(
        run.run_id,
        event_id="report:start:live",
        event_type="report.start",
        payload={"report": {"modules": []}},
    )
    slept = False

    def add_later_step(_seconds: float) -> None:
        nonlocal slept
        if slept:
            return
        slept = True
        store.append_step(
            run.run_id, step_id="s02", name="later", status="completed"
        )
        store.finish_run(run.run_id, rs.STATUS_COMPLETED)

    monkeypatch.setattr(app_module.time, "sleep", add_later_step)
    body = client.get(f"/api/runs/{run.run_id}/events").text

    assert body.count("event: step") == 2
    assert '"step_id": "s02"' in body


def test_sse_resumed_connection_never_replays_trace(client: TestClient) -> None:
    store = RunStore()
    run = store.create_run("resume", "ask")
    store.append_step(run.run_id, step_id="s01", name="hidden", status="completed")
    event = store.append_stream_event(
        run.run_id,
        event_id="report:start:resume",
        event_type="report.start",
        payload={},
    )
    store.finish_run(run.run_id, rs.STATUS_COMPLETED)

    after = client.get(
        f"/api/runs/{run.run_id}/events", params={"after": event["seq"]}
    ).text
    header = client.get(
        f"/api/runs/{run.run_id}/events",
        headers={"Last-Event-ID": event["event_id"]},
    ).text

    assert "event: step" not in after
    assert "event: step" not in header


def test_daily_run_uses_one_pass_llm_and_template_followups(tmp_path, monkeypatch) -> None:
    from intelligence.services import ask as ask_svc
    from intelligence.services import followups as followups_svc
    from intelligence.services.ask import AskResult

    captured: dict[str, object] = {}

    def fake_answer(options):
        captured["options"] = options
        result = AskResult(
            query=options.query,
            trade_date="2026-07-10",
            matched_theme="算力",
            candidate_tier="watch",
            priority_score=80,
        )
        result.synthesis = "一轮 GLM 综合结果。"
        result.llm_provider = "glm"
        result.warnings = ["输出质检：盘面数据需要复核"]
        result.sections = {"结论": ["市场修复延续。"]}
        return result

    def fake_followups(*args, use_llm=True, **kwargs):
        captured["followups_use_llm"] = use_llm
        return followups_svc.FollowupResult()

    monkeypatch.setattr(ask_svc, "answer_query", fake_answer)
    monkeypatch.setattr(ask_svc, "render_answer", lambda result: "# 结论\n市场修复延续。")
    monkeypatch.setattr(followups_svc, "generate_followups", fake_followups)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    store = RunStore(root=tmp_path / "runs")
    run = store.create_run("今日复盘", "daily")
    request = app_module.CreateRunRequest(
        question="今日复盘",
        task_type="daily",
        repo_root=repo_root,
    )

    app_module._run_ask(store, run.run_id, request)

    options = captured["options"]
    assert options.compose_self_review is False
    assert options.compose_revise_on_warn is False
    assert options.force_moneyflow_block is True
    assert captured["followups_use_llm"] is False
    saved = store.load_run(run.run_id)
    assert saved.status == rs.STATUS_COMPLETED
    assert saved.source_date == "2026-07-10"
    assert "输出质检：盘面数据需要复核" in saved.degrades


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
