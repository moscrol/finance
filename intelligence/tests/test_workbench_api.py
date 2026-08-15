import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import duckdb

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from intelligence import userspace  # noqa: E402
from intelligence.api import app as app_module  # noqa: E402
from intelligence.services import run_store as rs  # noqa: E402
from intelligence.services.agent_runtime import EpisodeEvent  # noqa: E402
from intelligence.runtime.episode_progress import (  # noqa: E402
    EpisodeProgress,
    RunEpisodeProgressPublisher,
)
from intelligence.services.conversation_store import ConversationStore  # noqa: E402
from intelligence.services import perspective_lab  # noqa: E402
from intelligence.services.llm_refine import LLMProvider  # noqa: E402
from intelligence.services.llm_settings import SessionLLMSettings  # noqa: E402
from intelligence.services.research_policy import (  # noqa: E402
    ResearchExecutionPolicy,
    grounded_deep,
)
from intelligence.services.run_store import RunStore  # noqa: E402
from intelligence.services.self_use_maturity import (  # noqa: E402
    SelfUseEvent,
    SelfUseLedger,
)


def _write_rag_fixture(tmp_path, knowledge_wiki) -> None:
    (tmp_path / ".rag_index").mkdir()
    script = tmp_path / "scripts" / "rag_index.py"
    script.parent.mkdir()
    script.write_text(
        """
import sys

if sys.argv[1:] == ["query", "--help"]:
    print("--json --k K --mode MODE --evidence-chars N")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert knowledge_wiki.is_dir()


def _write_market_snapshot_fixture(root, *, quality="complete", freshness="fresh"):
    date = "2026-07-16"
    doc = {
        "schema_version": "1.1-test",
        "trade_date": date,
        "quality": quality,
        "freshness": freshness,
        "source": "duckdb:market_feature_store",
        "provider": "duckdb_latest",
        "requested_trade_date": "2026-07-17",
        "served_trade_date": date,
        "market": {
            "stage": "震荡",
            "total_amount": 10000,
            "amount_ratio": None,
            "advancers": 2500,
            "decliners": 2400,
            "limit_up": 50,
            "limit_down": 5,
            "capacity_top3": [],
        },
        "themes": [],
        "strong_stocks": [],
    }
    (root / f"{date}.json").write_text(json.dumps(doc), encoding="utf-8")
    (root / "latest.json").write_text(json.dumps(doc), encoding="utf-8")
    (root / "meta.json").write_text(
        json.dumps(
            {
                "schema_version": "1.1-test",
                "latest_trade_date": date,
                "updated_at": "2026-07-16T16:00:00+08:00",
                "source": "duckdb:market_feature_store",
                "provider": "duckdb_latest",
                "requested_trade_date": "2026-07-17",
                "served_trade_date": date,
                "quality": quality,
                "freshness": freshness,
            }
        ),
        encoding="utf-8",
    )


def _write_overview_market_db(path: Path, *, trade_date: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute(
        """
        CREATE TABLE fact_market_daily (
            trade_date DATE,
            market_stage TEXT,
            advancers INTEGER,
            limit_up INTEGER,
            limit_down INTEGER,
            total_amount DOUBLE,
            amount_vs_yesterday_pct DOUBLE,
            amount_ma20 DOUBLE,
            top3_industry_ratio DOUBLE,
            concentration_state TEXT,
            strength_marginal_pct DOUBLE,
            strength_status TEXT
        )
        """
    )
    con.execute(
        """
        INSERT INTO fact_market_daily VALUES (
            CAST(? AS DATE), '轮动', 2800, 52, 6, 18000,
            3.2, 17500, 35.0, '中等集中', 1.8, '正常'
        )
        """,
        [trade_date],
    )
    con.close()


class MemoryCredentialStore:
    def __init__(self) -> None:
        self.providers: dict[str, LLMProvider] = {}
        self.deleted: list[str] = []
        self.load_calls = 0

    def save(self, user_id: str, provider: LLMProvider) -> None:
        self.providers[user_id] = provider

    def load(self, user_id: str) -> LLMProvider | None:
        self.load_calls += 1
        return self.providers.get(user_id)

    def delete(self, user_id: str) -> None:
        self.deleted.append(user_id)
        self.providers.pop(user_id, None)


@pytest.fixture()
def credential_store() -> MemoryCredentialStore:
    return MemoryCredentialStore()


@pytest.fixture()
def client(tmp_path, monkeypatch, credential_store):
    users_root = tmp_path / "users"
    repo_root = tmp_path / "repo"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users_root))
    monkeypatch.setenv("FINANCE_WS", str(repo_root))
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    _write_rag_fixture(tmp_path, knowledge_wiki)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))
    market_snapshot = tmp_path / "market_snapshot"
    market_snapshot.mkdir()
    _write_market_snapshot_fixture(market_snapshot)
    monkeypatch.setenv("MARKET_SNAPSHOT_DIR", str(market_snapshot))

    daily_dir = repo_root / "复盘" / "daily" / "2026-07-09"
    daily_dir.mkdir(parents=True)
    (daily_dir / "2026-07-09-daily-agent.html").write_text(
        "<h1>daily</h1>", encoding="utf-8"
    )
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
                "citations": [
                    {
                        "tag": "S1",
                        "source": "盘面快照",
                        "detail": "已记录引用",
                    }
                ],
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
    llm_settings = SessionLLMSettings(credential_store=credential_store)
    return TestClient(
        app_module.create_app(repo_root=repo_root, llm_settings=llm_settings)
    )


def _wait_terminal(
    client: TestClient,
    run_id: str,
    timeout: float = 5.0,
    *,
    user: str | None = None,
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        params = {"user": user} if user is not None else None
        run = client.get(f"/api/runs/{run_id}", params=params).json()
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
        "credential_persisted": False,
        "saved_credential_available": False,
    }
    assert "glm-secret-value" not in configured.text
    assert (
        client.get("/api/llm/config", params={"user": "bob"}).json()["mode"]
        == "built_in"
    )

    restored = client.delete("/api/llm/config", params={"user": "alice"})
    assert restored.status_code == 200
    assert restored.json()["mode"] == "built_in"
    assert restored.json()["session_only"] is False


def test_session_byok_api_accepts_local_gateway_without_returning_url(
    client: TestClient,
) -> None:
    configured = client.put(
        "/api/llm/config",
        json={
            "provider": "openai",
            "api_key": "openai-secret-value",
            "base_url": "http://localhost:57244/v1",
            "model": "gpt-5.6-sol",
            "user": "alice",
        },
    )

    assert configured.status_code == 200
    assert configured.json()["provider"] == "openai"
    assert configured.json()["model"] == "gpt-5.6-sol"
    assert "base_url" not in configured.json()
    assert "57244" not in configured.text
    assert "openai-secret-value" not in configured.text


def test_remembered_byok_survives_restart_and_requires_explicit_forget(
    client: TestClient,
    credential_store: MemoryCredentialStore,
    tmp_path: Path,
) -> None:
    configured = client.put(
        "/api/llm/config",
        json={
            "provider": "openai",
            "api_key": "openai-secret-value",
            "base_url": "http://localhost:57244/v1",
            "model": "gpt-5.6-sol",
            "remember": True,
            "user": "alice",
        },
    )

    assert configured.status_code == 200
    assert configured.json()["credential_persisted"] is True
    assert configured.json()["saved_credential_available"] is True
    assert configured.json()["session_only"] is False
    assert "openai-secret-value" not in configured.text
    assert "57244" not in configured.text

    disabled = client.delete("/api/llm/config", params={"user": "alice"})
    assert disabled.status_code == 200
    assert disabled.json()["mode"] == "built_in"
    assert disabled.json()["saved_credential_available"] is True
    assert "alice" in credential_store.providers

    restarted_settings = SessionLLMSettings(credential_store=credential_store)
    restarted = TestClient(
        app_module.create_app(
            repo_root=tmp_path / "repo",
            llm_settings=restarted_settings,
        )
    )
    reloaded = restarted.get("/api/llm/config", params={"user": "alice"})
    assert reloaded.status_code == 200
    assert reloaded.json()["mode"] == "byok"
    assert reloaded.json()["credential_persisted"] is True
    assert "openai-secret-value" not in reloaded.text
    assert "57244" not in reloaded.text

    forgotten = restarted.delete(
        "/api/llm/config/saved",
        params={"user": "alice"},
    )
    assert forgotten.status_code == 200
    assert forgotten.json()["mode"] == "built_in"
    assert forgotten.json()["saved_credential_available"] is False
    assert credential_store.deleted == ["alice"]


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
    unsafe_url = client.put(
        "/api/llm/config",
        json={
            "provider": "openai",
            "api_key": "long-enough",
            "base_url": "http://api.openai.com/v1?token=secret",
            "user": "alice",
        },
    )

    assert unknown.status_code == 422
    assert short.status_code == 422
    assert unsafe_url.status_code == 422
    assert "short" not in short.text
    assert "token=secret" not in unsafe_url.text


def test_session_byok_flows_to_the_conversation_worker(
    client: TestClient,
    monkeypatch,
) -> None:
    captured: list[object] = []
    finished = threading.Event()

    def capture_run_conversation_turn(**kwargs: object) -> None:
        captured.append(kwargs["llm_providers"])
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
    assert (
        client.put(
            "/api/llm/config",
            json={
                "provider": "zhipu",
                "api_key": "glm-secret-value",
                "user": "alice",
            },
        ).status_code
        == 200
    )
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
    providers = captured[0]
    assert isinstance(providers, tuple)
    assert len(providers) == 1
    provider = providers[0]
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
    continuous_adapter = object()
    captured_providers: list[tuple[object, ...]] = []

    def build_adapter(**kwargs: object) -> object:
        providers = kwargs["providers"]
        assert isinstance(providers, tuple)
        captured_providers.append(providers)
        assert kwargs["run_id"] == "run"
        assert kwargs["assistant_message_id"] == "message"
        assert kwargs["run_store"] is run_store
        assert kwargs["conversation_id"] == "conversation"
        assert kwargs["event_id_prefix"] == ""
        assert callable(kwargs["is_cancelled"])
        assert 0 < float(kwargs["timeout"]) <= 120
        assert kwargs["deadline_expires_at"] == signal.deadline_expires_at
        assert kwargs["memory_user"] == "selected-model-user"
        return continuous_adapter

    monkeypatch.setattr(
        app_module,
        "_build_continuous_turn_adapter",
        build_adapter,
    )
    provider = app_module.LLMProvider(
        "zhipu",
        "secret-value",
        "https://open.bigmodel.cn/api/paas/v4",
        "glm-4-flash",
    )

    class _RunStoreStub:
        """同上：``run_store`` 必须带 ``user_id``，生产里它恒为真实 ``RunStore``。"""

        user_id = "selected-model-user"

    run_store = _RunStoreStub()
    signal = app_module.CancellationSignal(deadline_expires_at=time.monotonic() + 30.0)
    app_module._run_conversation_turn(
        repo_root=tmp_path,
        conversation_store=object(),
        run_store=run_store,
        conversation_id="conversation",
        run_id="run",
        assistant_message_id="message",
        query="研究低空经济",
        skill_mode="auto",
        selected_skill_ids=[],
        cancellation_signal=signal,
        llm_providers=(provider,),
    )

    assert captured["llm_model"] == "glm-4-flash"
    assert captured["continuous_turn_adapter"] is continuous_adapter
    assert captured_providers == [(provider,)]
    policy = captured["research_policy"]
    assert isinstance(policy, ResearchExecutionPolicy)
    assert policy.max_elapsed_seconds == grounded_deep.root_seconds
    assert policy.synthesis_reserve_seconds == (
        grounded_deep.synthesis_reserve_seconds
    )
    assert policy.grounded_budget_profile is grounded_deep


def test_production_continuous_adapter_shares_provider_client_across_gates(
    tmp_path: Path,
) -> None:
    providers = (
        app_module.LLMProvider(
            "zhipu",
            "primary-secret",
            "https://glm.example.invalid/v1",
            "glm-5.2",
        ),
        app_module.LLMProvider(
            "openai",
            "fallback-secret",
            "https://openai.example.invalid/v1",
            "gpt-5",
        ),
    )

    cancelled = threading.Event()
    is_cancelled = cancelled.is_set
    deadline_expires_at = time.monotonic() + 42.0
    run_store = RunStore(user_id="progress", root=tmp_path / "runs")
    run = run_store.create_run("研究当前市场", "ask", session_id="conversation-a")
    adapter = app_module._build_continuous_turn_adapter(
        providers=providers,
        run_id=run.run_id,
        assistant_message_id="message-b",
        run_store=run_store,
        conversation_id="conversation-a",
        is_cancelled=is_cancelled,
        timeout=42.0,
        deadline_expires_at=deadline_expires_at,
    )

    episode = adapter._runtime._episode
    semantic = adapter._semantic_verifier
    assert episode._model is episode._finalizer._model
    assert episode._finalizer._llm_timeout == episode._llm_timeout
    assert semantic._primary_judge is episode._model
    assert semantic._finalizer is episode._finalizer
    assert episode._model._providers == providers
    assert episode._model._is_cancelled is is_cancelled
    assert episode._is_cancelled is is_cancelled
    assert adapter._is_cancelled is is_cancelled
    assert adapter._deadline_expires_at == deadline_expires_at
    assert 0 < adapter._remaining_timeout() <= 42.0
    assert adapter._timeout == 42.0
    assert adapter._task_id_factory() == f"{run.run_id}:message-b"
    assert callable(adapter._progress_sink)
    assert callable(episode._event_sink)
    episode._event_sink(
        EpisodeEvent(
            3,
            "tool_request",
            {
                "query": "SELECT secret FROM hidden_table",
                "provider": "private-provider",
            },
        )
    )
    adapter._progress_sink(
        EpisodeProgress(
            key="adapter:understanding",
            stage="understanding",
            message="已对齐本轮任务并进入研究。",
            status="completed",
        )
    )
    assert len(run_store.load_trace(run.run_id)) == 1
    public_progress = str(
        (
            run_store.load_trace(run.run_id),
            run_store.load_stream_events(run.run_id),
        )
    )
    assert "正在核对计划所需资料" in public_progress
    assert "SELECT" not in public_progress
    assert "hidden_table" not in public_progress
    assert "private-provider" not in public_progress
    assert (
        adapter._synthesis_reserve_for_task(
            tier="standard",
            question_type="market_forecast",
        )
        == 60.0
    )


def test_production_adapter_composes_sdk_glm_without_changing_verifier(
    monkeypatch,
) -> None:
    from intelligence.runtime.openai_agents_runtime import OpenAIAgentsRuntime

    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "sdk_glm")
    provider = app_module.LLMProvider(
        "zhipu",
        "sdk-secret",
        "https://open.bigmodel.cn/api/coding/paas/v4",
        "glm-5.2",
    )

    adapter = app_module._build_continuous_turn_adapter(
        providers=(provider,),
        run_id="sdk-run",
        assistant_message_id="sdk-message",
        timeout=42.0,
    )

    assert isinstance(adapter._runtime, OpenAIAgentsRuntime)
    assert adapter._runtime_name == "sdk_glm"
    assert adapter._runtime._backend == "sdk_glm"
    assert callable(adapter._runtime._model_factory)
    assert adapter._semantic_verifier._primary_judge._providers == (provider,)
    assert (
        adapter._synthesis_reserve_for_task(
            tier="standard",
            question_type="market_forecast",
        )
        == 0.0
    )


def test_production_adapter_composes_sdk_gpt_from_session_provider(
    monkeypatch,
) -> None:
    from intelligence.runtime.openai_agents_runtime import OpenAIAgentsRuntime

    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "sdk_gpt")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = app_module.LLMProvider(
        "openai",
        "session-secret",
        "http://localhost:57244/v1",
        "gpt-5.6-sol",
    )

    adapter = app_module._build_continuous_turn_adapter(
        providers=(provider,),
        run_id="sdk-gpt-run",
        assistant_message_id="sdk-gpt-message",
        timeout=42.0,
    )

    assert isinstance(adapter._runtime, OpenAIAgentsRuntime)
    assert adapter._runtime_name == "sdk_gpt"
    assert adapter._runtime._backend == "sdk_gpt"
    assert adapter._runtime._model_name == "gpt-5.6-sol"
    assert adapter._runtime._model is None
    assert callable(adapter._runtime._model_factory)
    assert adapter._semantic_verifier._primary_judge._providers == (provider,)
    assert (
        adapter._synthesis_reserve_for_task(
            tier="standard",
            question_type="market_forecast",
        )
        == 0.0
    )


def test_sdk_gpt_adapter_wires_safe_live_episode_progress(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "sdk_gpt")
    provider = app_module.LLMProvider(
        "openai",
        "session-secret",
        "http://localhost:57244/v1",
        "gpt-5.6-sol",
    )
    run_store = RunStore(user_id="sdk-progress", root=tmp_path / "runs")
    run = run_store.create_run(
        "研究当前市场",
        "ask",
        session_id="sdk-conversation",
    )

    adapter = app_module._build_continuous_turn_adapter(
        providers=(provider,),
        run_id=run.run_id,
        assistant_message_id="sdk-message",
        run_store=run_store,
        conversation_id="sdk-conversation",
        timeout=42.0,
    )

    assert callable(adapter._runtime._event_sink)
    adapter._runtime._event_sink(
        EpisodeEvent(
            2,
            "tool_request",
            {
                "query": "SELECT secret FROM hidden_table",
                "provider": "private-provider",
            },
        )
    )
    public_progress = str(
        (
            run_store.load_trace(run.run_id),
            run_store.load_stream_events(run.run_id),
        )
    )
    assert "正在核对计划所需资料" in public_progress
    assert "SELECT" not in public_progress
    assert "hidden_table" not in public_progress
    assert "private-provider" not in public_progress


def test_conversation_worker_allocates_120_seconds_to_continuous_runtime(
    monkeypatch,
    tmp_path,
) -> None:
    captured: dict[str, object] = {}

    class CapturingOrchestrator:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def run_turn(self, **_kwargs: object) -> None:
            return None

    monkeypatch.setattr(app_module, "TurnOrchestrator", CapturingOrchestrator)
    monkeypatch.setattr(
        app_module,
        "_build_continuous_turn_adapter",
        lambda **kwargs: captured.setdefault("adapter_kwargs", kwargs),
    )
    signal = app_module.CancellationSignal(deadline_expires_at=time.monotonic() + 300.0)

    class _RunStoreStub:
        """``run_store`` 至少要带 ``user_id``：生产里它恒为真实 ``RunStore``。

        原先这里传的是裸 ``object()``。那让本函数**读不到身份也照样通过**，于是
        「worker 有没有把 user 传给 adapter」这件事在测试里完全不可见——
        `memory_lookup` 因此在生产静默缺席（见下面那条断言的说明）。
        """

        user_id = "conversation-user"

    app_module._run_conversation_turn(
        repo_root=tmp_path,
        conversation_store=object(),
        run_store=_RunStoreStub(),
        conversation_id="conversation",
        run_id="run",
        assistant_message_id="message",
        query="研究当前市场",
        skill_mode="auto",
        selected_skill_ids=[],
        cancellation_signal=signal,
        llm_providers=(),
    )

    adapter_kwargs = captured["adapter_kwargs"]
    assert isinstance(adapter_kwargs, dict)
    assert adapter_kwargs["timeout"] == pytest.approx(120.0, abs=0.1)
    # 身份必须真的到达 adapter，否则 `build_episode_registry` 的守卫
    # （`episode_tools.py:937`）会拒绝注册 `memory_lookup`，而这**不报错**：
    # contract 里仍授权它、提示词仍教怎么用它、prior_recall 槽位仍开着，
    # 只有模型收到的工具清单里静静少了一个。实测 run_20260808_111451 就是
    # 这个形状（模型看到 7 个工具、不含 memory_lookup）。
    assert adapter_kwargs["memory_user"] == "conversation-user"


def test_conversation_lifecycle_and_messages_persist(client: TestClient) -> None:
    created = client.post(
        "/api/conversations", json={"title": "盘面讨论", "user": "alice"}
    )
    assert created.status_code == 200
    conversation = created.json()
    conversation_id = conversation["conversation_id"]
    assert conversation["title"] == "盘面讨论"
    assert client.get("/api/conversations", params={"user": "alice"}).json() == [
        conversation
    ]
    assert (
        client.get(
            f"/api/conversations/{conversation_id}", params={"user": "alice"}
        ).json()
        == conversation
    )

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
        "conversation_id",
        "user_message_id",
        "assistant_message_id",
        "run_id",
    }
    messages = client.get(
        f"/api/conversations/{conversation_id}/messages", params={"user": "alice"}
    ).json()
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "今天市场怎么样？"
    assert messages[0]["selected_skill_ids"] == ["daily-review"]
    assert messages[0]["perspective_mode"] == "neutral"
    assert messages[0]["selected_perspective_ids"] == []
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


def test_public_run_and_message_payloads_sanitize_diagnostics_without_mutating_store(
    client: TestClient,
) -> None:
    conversation = client.post(
        "/api/conversations",
        json={"title": "公开消息安全", "user": "alice"},
    ).json()
    conversation_store = ConversationStore("alice")
    unsafe_path = 'Traceback File "/Users/alice/private/rag_index.py", line 9'
    stored_message = conversation_store.append_message(
        conversation["conversation_id"],
        "assistant",
        "可核验回答正文保持不变",
        status="completed",
        citations=[
            {
                "title": "公告",
                "system_notices": [unsafe_path, "provider_timeout"],
            }
        ],
        degrades=[
            unsafe_path,
            "provider_timeout",
            "untrusted index freshness: missing",
            "narrow retrieval empty after 1 attempts",
        ],
    )
    run_store = RunStore("alice")
    run = run_store.create_run("公开运行安全", "ask")
    run_store.add_degrade(run.run_id, unsafe_path)
    run_store.add_degrade(run.run_id, "provider_timeout")
    run_store.finish_run(
        run.run_id,
        rs.STATUS_FAILED,
        error=unsafe_path,
    )

    raw_message = conversation_store.load_messages(conversation["conversation_id"])[0]
    raw_run = run_store.load_run(run.run_id)
    assert raw_message.message_id == stored_message.message_id
    assert "Traceback" in json.dumps(asdict(raw_message), ensure_ascii=False)
    assert "Traceback" in json.dumps(asdict(raw_run), ensure_ascii=False)

    messages = client.get(
        f"/api/conversations/{conversation['conversation_id']}/messages",
        params={"user": "alice"},
    )
    run_response = client.get(
        f"/api/runs/{run.run_id}",
        params={"user": "alice"},
    )
    runs_response = client.get("/api/runs", params={"user": "alice"})
    public_body = "\n".join([messages.text, run_response.text, runs_response.text])

    assert messages.status_code == 200
    assert run_response.status_code == 200
    assert runs_response.status_code == 200
    assert "可核验回答正文保持不变" in public_body
    assert "Traceback" not in public_body
    assert "/Users/alice" not in public_body
    assert "rag_index.py" not in public_body
    assert "provider_timeout" not in public_body
    assert "untrusted index freshness" not in public_body
    assert "narrow retrieval empty" not in public_body
    assert "模型精修超时" in public_body
    assert "知识库索引时效无法确认" in public_body
    assert "未检索到可核验的公司专项资料" in public_body


def test_perspective_selection_is_validated_listed_and_persisted(
    client: TestClient,
) -> None:
    us = userspace.user_space("alice")
    perspective_lab.init_perspective(
        us,
        "fengyuan94",
        display_name="风远94",
        ptype="blogger",
    )
    listed = client.get("/api/perspectives", params={"user": "alice"})
    assert listed.status_code == 200
    assert listed.json() == [
        {
            "perspective_id": "fengyuan94",
            "display_name": "风远94",
            "type": "blogger",
            "article_count": 0,
            "profile_confidence": "low",
        }
    ]
    assert client.get("/api/perspectives", params={"user": "bob"}).json() == []
    conversation_id = client.post("/api/conversations", json={"user": "alice"}).json()[
        "conversation_id"
    ]

    sent = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={
            "content": "按风远视角复盘",
            "skill_mode": "auto",
            "perspective_mode": "single",
            "selected_perspective_ids": ["fengyuan94"],
            "user": "alice",
        },
    )

    assert sent.status_code == 202
    messages = client.get(
        f"/api/conversations/{conversation_id}/messages",
        params={"user": "alice"},
    ).json()
    assert messages[0]["perspective_mode"] == "single"
    assert messages[0]["selected_perspective_ids"] == ["fengyuan94"]
    assert messages[1]["perspective_mode"] == "single"
    assert messages[1]["selected_perspective_ids"] == ["fengyuan94"]


@pytest.mark.parametrize(
    "payload",
    [
        {
            "perspective_mode": "neutral",
            "selected_perspective_ids": ["fengyuan94"],
        },
        {"perspective_mode": "single", "selected_perspective_ids": []},
        {"perspective_mode": "single", "selected_perspective_ids": ["missing"]},
        {"perspective_mode": "compare", "selected_perspective_ids": []},
        {
            "perspective_mode": "compare",
            "selected_perspective_ids": ["same", "same"],
        },
        {"perspective_mode": "single", "selected_perspective_ids": ["../escape"]},
        {
            "perspective_mode": "compare",
            "selected_perspective_ids": ["one", "two", "three", "four"],
        },
    ],
)
def test_invalid_perspective_selection_is_rejected(
    client: TestClient,
    payload: dict[str, object],
) -> None:
    conversation_id = client.post("/api/conversations", json={"user": "alice"}).json()[
        "conversation_id"
    ]
    response = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={
            "content": "复盘",
            "skill_mode": "auto",
            "user": "alice",
            **payload,
        },
    )
    assert response.status_code == 422


def test_conversation_message_run_parent_chains_across_turns(
    client: TestClient,
) -> None:
    conversation_id = client.post("/api/conversations", json={"user": "alice"}).json()[
        "conversation_id"
    ]
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
    assert (
        len(
            client.get(
                f"/api/conversations/{conversation_id}/messages",
                params={"user": "alice"},
            ).json()
        )
        == 4
    )


def test_concurrent_messages_are_paired_and_runs_form_one_linear_chain(
    client: TestClient,
) -> None:
    conversation_id = client.post("/api/conversations", json={"user": "alice"}).json()[
        "conversation_id"
    ]
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
    assert sorted(len(children) for children in children_by_parent.values()) == [
        0,
        1,
        1,
        1,
        1,
        1,
    ]
    assert len(client.app.state.conversation_locks) == 1


def test_second_message_append_failure_marks_created_run_failed(
    client: TestClient,
) -> None:
    conversation_id = client.post("/api/conversations", json={"user": "alice"}).json()[
        "conversation_id"
    ]
    original_append = ConversationStore.append_message
    append_count = 0

    def fail_second_append(self: ConversationStore, *args: object, **kwargs: object):
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
    conversation_id = client.post("/api/conversations", json={"user": "alice"}).json()[
        "conversation_id"
    ]

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
    conversation_id = client.post("/api/conversations", json={"user": "alice"}).json()[
        "conversation_id"
    ]

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


@pytest.mark.parametrize(
    "path", ["/api/conversations", "/api/conversations/{conversation_id}"]
)
def test_conversation_titles_reject_blank_whitespace(
    client: TestClient, path: str
) -> None:
    conversation_id = client.post("/api/conversations", json={"user": "alice"}).json()[
        "conversation_id"
    ]
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
        (
            "post",
            "/api/conversations/..%2Falice/messages",
            {"content": "x", "skill_mode": "auto"},
        ),
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
    conversation_id = client.post("/api/conversations", json={"user": "alice"}).json()[
        "conversation_id"
    ]
    for body in (
        {"content": "", "skill_mode": "auto", "user": "alice"},
        {"content": "   ", "skill_mode": "auto", "user": "alice"},
        {"content": "x", "skill_mode": "invalid", "user": "alice"},
    ):
        assert (
            client.post(
                f"/api/conversations/{conversation_id}/messages", json=body
            ).status_code
            == 422
        )
    assert (
        client.get(
            f"/api/conversations/{conversation_id}", params={"user": "bob"}
        ).status_code
        == 404
    )
    assert client.get("/api/conversations", params={"user": "bob"}).json() == []


def test_message_rejects_unknown_product_skill_before_creating_run(
    client: TestClient,
) -> None:
    conversation_id = client.post("/api/conversations", json={"user": "alice"}).json()[
        "conversation_id"
    ]

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

    assert [skill["skill_id"] for skill in skills] == [
        "daily-review",
        "daily-agent",
        "us-ai-drawdown",
        "stock-deep-dive",
        "theme-research",
        "news-impact",
        "financial-analysis",
    ]
    permissions = {skill["skill_id"]: skill["permissions"] for skill in skills}
    assert permissions["us-ai-drawdown"] == ["local_read", "network_read"]
    assert all(
        value == ["local_read"]
        for skill_id, value in permissions.items()
        if skill_id != "us-ai-drawdown"
    )


def test_skills_serializes_only_product_registry_definitions(
    client: TestClient,
) -> None:
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
    run_id = client.post("/api/runs", json={"question": "q", "user": "alice"}).json()[
        "run_id"
    ]
    assert (
        client.post(f"/api/runs/{run_id}/cancel", params={"user": "bob"}).status_code
        == 404
    )
    _wait_terminal(client, run_id, user="alice")
    assert client.app.state.cancellation_registry == {}
    first = client.post(f"/api/runs/{run_id}/cancel", params={"user": "alice"}).json()
    second = client.post(f"/api/runs/{run_id}/cancel", params={"user": "alice"}).json()
    assert (
        first
        == second
        == {
            "run_id": run_id,
            "status": "completed",
            "cancel_requested": True,
        }
    )
    assert client.app.state.cancellation_registry == {}


def test_create_run_and_fetch_artifacts(client: TestClient) -> None:
    resp = client.post("/api/runs", json={"question": "测试问题"})
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    run = _wait_terminal(client, run_id)
    assert run["status"] == "completed"
    assert [artifact["path"] for artifact in run["artifacts"]] == ["answer.md"]

    trace = client.get(f"/api/runs/{run_id}/trace").json()
    assert trace[0]["name"] == "research"

    answer = client.get(f"/api/runs/{run_id}/artifacts/answer.md")
    assert answer.status_code == 200
    assert "测试问题" in answer.text

    listed = client.get("/api/runs").json()
    assert listed[0]["run_id"] == run_id


def test_internal_artifact_is_hidden_from_every_public_artifact_interface(
    client: TestClient,
) -> None:
    created = client.post("/api/runs", json={"question": "private audit"})
    run_id = created.json()["run_id"]
    _wait_terminal(client, run_id)
    RunStore().add_artifact(
        run_id,
        "continuous-episode.json",
        '{"contract": "private"}',
        renderer="json",
        title="连续研究私有审计",
        visibility="internal",
    )

    public_run = client.get(f"/api/runs/{run_id}").json()
    assert all(
        artifact["path"] != "continuous-episode.json"
        for artifact in public_run["artifacts"]
    )
    assert (
        client.get(
            f"/api/runs/{run_id}/artifacts/continuous-episode.json"
        ).status_code
        == 404
    )
    assert client.get(f"/api/runs/{run_id}/artifacts/run.json").status_code == 404
    listed = client.get("/api/artifacts").json()
    assert not any(
        "continuous-episode" in str(artifact.get("source_path") or "")
        for artifact in listed
    )
    assert client.get(f"/api/runs/{run_id}/artifacts/answer.md").status_code == 200


def test_health_endpoints_report_worker_and_storage_state(client: TestClient) -> None:
    health = client.get("/api/health").json()
    assert health["status"] == "healthy"
    assert health["dependencies"]["knowledge_wiki"] is True
    assert health["runtime"]["users_dir"]
    assert Path(health["runtime"]["users_dir"]).is_absolute()
    assert health["runtime"]["continuous_agent"] == {
        "mode": "off",
        "canary_id": "",
        "source_revision": health["runtime"]["source_revision"],
    }

    response = client.get("/api/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["repo_root"] is True
    assert payload["checks"]["run_store_writable"] is True
    assert payload["critical"]["market_snapshot"] is True
    assert payload["market_snapshot"]["ready"] is True
    assert payload["market_snapshot"]["provider"] == "duckdb_latest"
    assert payload["market_snapshot"]["date"] == "2026-07-16"
    assert payload["market_snapshot"]["requested_date"] == "2026-07-17"
    assert payload["missing_critical"] == []
    assert payload["workers"]["capacity"] == 2


def test_readiness_probe_schedules_dead_worker_recovery(
    client: TestClient, monkeypatch
) -> None:
    """readiness 必须携带自愈的写侧半步，不能只是读探针。

    查询失败式自愈覆盖不了「进程死了但后续查询全带 filters 走 CLI」的
    形状（2026-08-13 R23 注入实测：readiness 永久红、只能 kickstart）。
    """
    calls: list[bool] = []
    monkeypatch.setattr(
        app_module.kb_rag.rag_worker,
        "ensure_recovery",
        lambda: calls.append(True),
    )

    response = client.get("/api/readiness")

    assert response.status_code in (200, 503)
    assert calls, "readiness 探针没有调用 ensure_recovery"


def test_continuous_adapter_receives_runtime_and_snapshot_dates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "continuous_glm")
    monkeypatch.setenv("ASK_CONTINUOUS_RUNTIME", "on")
    monkeypatch.setattr(
        app_module,
        "default_paths",
        lambda: SimpleNamespace(
            finance_root=tmp_path / "finance",
            market_snapshot_dir=tmp_path / "market_snapshot",
        ),
    )
    monkeypatch.setattr(
        app_module,
        "validate_market_snapshot_root",
        lambda _root: {
            "ready": True,
            "date": "2026-07-16",
            "summary": {"served_trade_date": "2026-07-16"},
        },
    )
    monkeypatch.setattr(
        app_module.rs,
        "_now_iso",
        lambda: "2026-07-27T12:00:00+08:00",
    )

    adapter = app_module._build_continuous_turn_adapter(
        providers=(),
        run_id="run-freshness",
        assistant_message_id="message-freshness",
    )

    assert adapter._today == "2026-07-27"
    assert adapter._latest_data_date == "2026-07-16"


def test_continuous_readiness_rejects_snapshot_newer_than_market_database(
    tmp_path: Path,
    monkeypatch,
) -> None:
    users_root = tmp_path / "users"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    _write_rag_fixture(tmp_path, knowledge_wiki)
    market_snapshot = tmp_path / "market_snapshot"
    market_snapshot.mkdir()
    _write_market_snapshot_fixture(market_snapshot)
    _write_overview_market_db(
        repo_root / "db" / "market_feature_store.duckdb",
        trade_date="2025-06-30",
    )
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users_root))
    monkeypatch.setenv("FINANCE_WS", str(repo_root))
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))
    monkeypatch.setenv("MARKET_SNAPSHOT_DIR", str(market_snapshot))
    monkeypatch.setenv("ASK_CONTINUOUS_RUNTIME", "on")

    with TestClient(app_module.create_app(repo_root=repo_root)) as probe:
        response = probe.get("/api/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["critical"]["market_data_consistency"] is False
    assert "market_data_consistency" in payload["missing_critical"]
    assert payload["market_database"] == {
        "date": "2025-06-30",
        "snapshot_date": "2026-07-16",
        "consistent_with_snapshot": False,
        "required_by_continuous_runtime": True,
    }


def test_health_reports_continuous_canary_without_credentials(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("ASK_CONTINUOUS_RUNTIME", "canary")
    monkeypatch.setenv("CONTINUOUS_RUNTIME_CANARY_ID", "canary-a17")
    monkeypatch.setenv("FORESIGHT_BUILTIN_LLM_API_KEY", "never-expose-this-key")

    with TestClient(app_module.create_app(repo_root=tmp_path)) as probe:
        response = probe.get("/api/health")

    continuous = response.json()["runtime"]["continuous_agent"]
    assert continuous == {
        "mode": "canary",
        "canary_id": "canary-a17",
        "source_revision": response.json()["runtime"]["source_revision"],
    }
    assert "never-expose-this-key" not in response.text


def test_health_reports_selected_sdk_glm_runtime_without_secret(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "sdk_glm")
    monkeypatch.setenv("FORESIGHT_BUILTIN_LLM_API_KEY", "test-glm-key")
    monkeypatch.setenv("FORESIGHT_BUILTIN_LLM_MODEL", "glm-5.2")

    with TestClient(app_module.create_app(repo_root=tmp_path)) as probe:
        response = probe.get("/api/health")

    runtime = response.json()["runtime"]["agent_runtime"]
    assert runtime == {
        "backend": "sdk_glm",
        "ready": True,
        "reason": "ready",
        "model": "glm-5.2",
        "credential_available": True,
        "benchmark_only": False,
    }
    assert "test-glm-key" not in response.text


def test_health_reports_missing_sdk_gpt_key_without_fallback(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "sdk_gpt")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with TestClient(app_module.create_app(repo_root=tmp_path)) as probe:
        response = probe.get("/api/health")

    runtime = response.json()["runtime"]["agent_runtime"]
    assert runtime["backend"] == "sdk_gpt"
    assert runtime["ready"] is False
    assert runtime["reason"] == "openai_api_key_missing"
    assert runtime["model"] == "gpt-5.6-sol"
    assert runtime["credential_available"] is False
    assert runtime["benchmark_only"] is False


def test_health_reports_sdk_gpt_ready_from_saved_default_provider(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FORESIGHT_USER", "runtime-user")
    monkeypatch.setenv("AGENT_RUNTIME_BACKEND", "sdk_gpt")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    credential_store = MemoryCredentialStore()
    credential_store.save(
        "runtime-user",
        LLMProvider(
            name="openai",
            api_key="never-expose-this-key",
            base_url="http://localhost:57244/v1",
            model="gpt-5.6-sol",
        ),
    )
    llm_settings = SessionLLMSettings(credential_store=credential_store)

    with TestClient(
        app_module.create_app(repo_root=tmp_path, llm_settings=llm_settings)
    ) as probe:
        initial = probe.get("/api/health")
        assert initial.json()["runtime"]["agent_runtime"]["ready"] is False
        assert credential_store.load_calls == 0
        probe.get("/api/llm/config")
        response = probe.get("/api/health")

    runtime = response.json()["runtime"]["agent_runtime"]
    assert runtime["backend"] == "sdk_gpt"
    assert runtime["ready"] is True
    assert runtime["reason"] == "ready"
    assert runtime["model"] == "gpt-5.6-sol"
    assert runtime["credential_available"] is True
    assert "never-expose-this-key" not in response.text
    assert "57244" not in response.text


def test_lifespan_prewarms_enabled_rag_before_ready(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    _write_rag_fixture(tmp_path, knowledge_wiki)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))
    snapshot = tmp_path / "market_snapshot"
    snapshot.mkdir()
    _write_market_snapshot_fixture(snapshot)
    monkeypatch.setenv("MARKET_SNAPSHOT_DIR", str(snapshot))
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    calls: list[tuple[Path, float]] = []
    monkeypatch.setattr(
        app_module.kb_rag,
        "prewarm",
        lambda wiki, *, timeout: calls.append((wiki, timeout)),
    )
    monkeypatch.setattr(
        app_module.kb_rag.rag_worker,
        "status",
        lambda: {
            "enabled": True,
            "state": "ready",
            "active": 1,
            "configured_workers": 1,
            "model_load_count": 1,
            "prewarm_latency_ms": 42000,
            "last_error_type": None,
            "lifecycle": "startup_prewarm",
        },
    )
    monkeypatch.setattr(app_module.kb_rag.rag_worker, "close_all", lambda: None)

    with TestClient(app_module.create_app(repo_root=repo_root)) as probe:
        response = probe.get("/api/health/ready")

    assert calls == [(knowledge_wiki, 90.0)]
    assert response.status_code == 200
    payload = response.json()
    assert payload["critical"]["rag_worker"] is True
    assert payload["workers"]["rag"]["state"] == "ready"


def test_rag_prewarm_failure_keeps_readiness_closed(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    _write_rag_fixture(tmp_path, knowledge_wiki)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))
    snapshot = tmp_path / "market_snapshot"
    snapshot.mkdir()
    _write_market_snapshot_fixture(snapshot)
    monkeypatch.setenv("MARKET_SNAPSHOT_DIR", str(snapshot))
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    def fail_prewarm(_wiki, *, timeout):
        assert timeout == 90.0
        raise TimeoutError("fixture timeout")

    monkeypatch.setattr(app_module.kb_rag, "prewarm", fail_prewarm)
    monkeypatch.setattr(
        app_module.kb_rag.rag_worker,
        "status",
        lambda: {
            "enabled": True,
            "state": "failed",
            "active": 0,
            "configured_workers": 1,
            "model_load_count": 0,
            "prewarm_latency_ms": 90000,
            "last_error_type": "TimeoutError",
            "lifecycle": "startup_prewarm",
        },
    )
    monkeypatch.setattr(app_module.kb_rag.rag_worker, "close_all", lambda: None)

    with TestClient(app_module.create_app(repo_root=repo_root)) as probe:
        response = probe.get("/api/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["critical"]["rag_worker"] is False
    assert "rag_worker" in payload["missing_critical"]
    assert payload["workers"]["rag"]["last_error_type"] == "TimeoutError"


def test_readiness_fails_when_market_snapshot_is_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    _write_rag_fixture(tmp_path, knowledge_wiki)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))
    monkeypatch.setenv(
        "MARKET_SNAPSHOT_DIR",
        str(tmp_path / "missing-market-snapshot"),
    )
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    probe = TestClient(app_module.create_app(repo_root=repo_root))

    response = probe.get("/api/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["critical"]["market_snapshot"] is False
    assert payload["missing_critical"] == ["market_snapshot"]


def test_readiness_fails_when_market_snapshot_is_partial(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    _write_rag_fixture(tmp_path, knowledge_wiki)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))
    snapshot = tmp_path / "market_snapshot"
    snapshot.mkdir()
    _write_market_snapshot_fixture(
        snapshot,
        quality="partial",
        freshness="degraded",
    )
    monkeypatch.setenv("MARKET_SNAPSHOT_DIR", str(snapshot))
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    probe = TestClient(app_module.create_app(repo_root=repo_root))

    response = probe.get("/api/readiness")

    assert response.status_code == 503
    payload = response.json()
    assert payload["critical"]["market_snapshot"] is False
    assert payload["market_snapshot"]["status"] == "WARN"
    assert payload["market_snapshot"]["summary"]["quality"] == "partial"


def test_readiness_fails_when_rag_query_protocol_is_incompatible(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        app_module.kb_rag,
        "probe_rag_cli",
        lambda _wiki: app_module.kb_rag.RagCliProbe(
            available=True,
            query_protocol_compatible=False,
            supported_options=("--k", "--mode"),
            missing_required_options=("--json",),
            warning="RAG CLI 缺少必要 query 参数",
        ),
    )

    response = client.get("/api/readiness")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["checks"]["vector_index"] is True
    assert payload["checks"]["rag_query_protocol"] is False
    assert payload["missing_critical"] == ["rag_query_protocol"]
    assert payload["rag"]["missing_required_options"] == ["--json"]


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


def test_executor_runner_exception_terminalizes_run_and_pending_message(
    client: TestClient,
    monkeypatch,
) -> None:
    def broken_turn(**_kwargs: object) -> None:
        raise RuntimeError("private provider construction detail")

    monkeypatch.setattr(app_module, "_run_conversation_turn", broken_turn)
    conversation_id = client.post(
        "/api/conversations",
        json={"title": "后台异常", "user": "alice"},
    ).json()["conversation_id"]
    run_id = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "触发后台异常", "skill_mode": "auto", "user": "alice"},
    ).json()["run_id"]

    run = _wait_terminal(client, run_id, user="alice")
    messages = client.get(
        f"/api/conversations/{conversation_id}/messages",
        params={"user": "alice"},
    ).json()

    assert run["status"] == "failed"
    assert run["error"] == "executor_failure"
    assert run["degrades"] == ["executor_failure"]
    assert "private provider construction detail" not in json.dumps(run)
    assert messages[-1]["status"] == "failed"
    assert "本轮执行未完成" in messages[-1]["degrades"]


def test_executor_timeout_loser_cannot_fail_message_after_completed_claim(
    tmp_path,
    monkeypatch,
) -> None:
    users_root = tmp_path / "users"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users_root))
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))
    claimed = threading.Event()
    release = threading.Event()

    def completed_then_slow(**kwargs: object) -> None:
        run_store = kwargs["run_store"]
        run_id = kwargs["run_id"]
        assert isinstance(run_store, RunStore)
        assert isinstance(run_id, str)
        _, won = run_store.claim_terminal_run(run_id, rs.STATUS_COMPLETED)
        assert won is True
        claimed.set()
        release.wait(timeout=1)

    monkeypatch.setattr(app_module, "_run_conversation_turn", completed_then_slow)
    with TestClient(
        app_module.create_app(repo_root=tmp_path, run_timeout_sec=0.05)
    ) as timeout_client:
        conversation_id = timeout_client.post(
            "/api/conversations",
            json={"title": "完成与超时竞态"},
        ).json()["conversation_id"]
        run_id = timeout_client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "先完成再超时", "skill_mode": "auto"},
        ).json()["run_id"]
        assert claimed.wait(timeout=1)
        time.sleep(0.1)

        run = timeout_client.get(f"/api/runs/{run_id}").json()
        messages = timeout_client.get(
            f"/api/conversations/{conversation_id}/messages"
        ).json()
        events = RunStore().load_stream_events(run_id)
        release.set()

    assert run["status"] == "completed"
    assert run["error"] is None
    assert messages[-1]["status"] == "pending"
    assert all(event["event_type"] != "message.error" for event in events)


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


def test_create_app_recovers_interrupted_conversation_turn(
    tmp_path, monkeypatch
) -> None:
    users_root = tmp_path / "users"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users_root))
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))
    providers = (
        app_module.LLMProvider(
            "zhipu",
            "recovery-secret",
            "https://glm.example.invalid/v1",
            "glm-recovery",
        ),
        app_module.LLMProvider(
            "openai",
            "fallback-secret",
            "https://openai.example.invalid/v1",
            "gpt-recovery",
        ),
    )
    monkeypatch.setattr(
        app_module.SessionLLMSettings,
        "runtime_providers_for",
        lambda self, user_id: providers,
    )

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
        perspective_mode="compare",
        selected_perspective_ids=["fengyuan94"],
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
    assert captured["perspective_mode"] == "compare"
    assert captured["selected_perspective_ids"] == ["fengyuan94"]
    assert captured["llm_providers"] == providers
    assert str(captured["event_id_prefix"]).startswith("recovery:")


def test_sse_does_not_expose_trace_rows_as_public_events(client: TestClient) -> None:
    run_id = client.post("/api/runs", json={"question": "q"}).json()["run_id"]
    _wait_terminal(client, run_id)

    events = []
    with client.stream("GET", f"/api/runs/{run_id}/events") as resp:
        for line in resp.iter_lines():
            if line.startswith("event: "):
                events.append(line.removeprefix("event: "))
            if "event: run" in line:
                break
    assert events == ["run"]


def test_live_episode_progress_is_replayed_before_one_terminal_run_event(
    client: TestClient,
) -> None:
    store = RunStore()
    run = store.create_run("live progress", "ask")
    publisher = RunEpisodeProgressPublisher(
        run_store=store,
        run_id=run.run_id,
        conversation_id=run.session_id or "default",
        message_id="assistant-progress",
    )
    publisher.publish(
        EpisodeProgress(
            key="adapter:understanding",
            stage="understanding",
            message="已对齐本轮任务并进入研究。",
            status="completed",
        )
    )
    store.finish_run(run.run_id, rs.STATUS_COMPLETED)

    event_types: list[str] = []
    body = ""
    with client.stream("GET", f"/api/runs/{run.run_id}/events") as response:
        body = "\n".join(response.iter_lines())
        event_types = [
            line.removeprefix("event: ")
            for line in body.splitlines()
            if line.startswith("event: ")
        ]

    assert event_types == ["trace.step", "run"]
    assert body.count("event: run") == 1
    assert "已对齐本轮任务并进入研究" in body
    assert "assistant-progress" in body
    assert "SELECT" not in body
    assert "provider=" not in body


def test_public_trace_projection_hides_controller_and_retrieval_control_plane(
    client: TestClient,
) -> None:
    store = RunStore()
    run = store.create_run("public control-plane safety", "ask")
    private_summary = json.dumps(
        {
            "query": "SELECT secret_metric FROM hidden_table",
            "provider": "private-provider",
            "task_frame_hash": "private-task-frame-hash",
            "route": "internal_route",
            "prompt": "private system prompt",
            "message": "raw model message",
        }
    )
    step = store.append_step(
        run.run_id,
        step_id="controller:private-provider",
        name="turn_controller",
        status="completed",
        output_summary=private_summary,
    )
    store.append_stream_event(
        run.run_id,
        event_id="trace:controller",
        event_type="trace.step",
        payload={"step": step},
    )
    store.append_stream_event(
        run.run_id,
        event_id="report:complete",
        event_type="report.complete",
        payload={
            "report": {
                "status": "completed",
                "task_frame_hash": "private-task-frame-hash",
                "turn_intent": {"route": "internal_route"},
                "research_plan": {"prompt": "private system prompt"},
            }
        },
    )
    store.finish_run(run.run_id, rs.STATUS_COMPLETED)

    raw = json.dumps(
        (store.load_trace(run.run_id), store.load_stream_events(run.run_id))
    )
    trace_body = client.get(f"/api/runs/{run.run_id}/trace").text
    event_body = client.get(f"/api/runs/{run.run_id}/events").text
    public = f"{trace_body}\n{event_body}"

    assert "SELECT secret_metric" in raw
    assert "已完成问题理解与任务对齐" in public
    for forbidden in (
        "SELECT",
        "secret_metric",
        "hidden_table",
        "private-provider",
        "private-task-frame-hash",
        "internal_route",
        "private system prompt",
        "raw model message",
        "turn_controller",
    ):
        assert forbidden not in public


def test_trace_and_all_sse_payloads_use_path_aware_public_projection(
    client: TestClient,
) -> None:
    store = RunStore()
    run = store.create_run("canonical event safety", "ask")
    unsafe_path = 'Traceback File "/Users/alice/private/rag_index.py", line 9'
    warnings = [
        "provider_timeout",
        "untrusted index freshness: missing",
        "narrow retrieval empty after 1 attempts",
    ]
    store.append_step(
        run.run_id,
        step_id="unsafe-step",
        name="unsafe diagnostic",
        status="completed",
        input_summary="safe input",
        output_summary=json.dumps(
            {"diagnostic": unsafe_path, "warnings": warnings},
            ensure_ascii=False,
        ),
    )
    store.append_stream_event(
        run.run_id,
        event_id="skill:result",
        event_type="skill.result",
        payload={
            "skill_id": "news-impact",
            "output": {
                "diagnostic": unsafe_path,
                "warnings": warnings,
            },
        },
    )
    store.append_stream_event(
        run.run_id,
        event_id="answer:snapshot:1",
        event_type="answer.snapshot",
        payload={
            "revision": 1,
            "phase": "verified_draft",
            "text": "可核验草稿：英维克",
            "final": False,
        },
    )
    store.append_stream_event(
        run.run_id,
        event_id="message:complete",
        event_type="message.complete",
        payload={
            "message": {
                "status": "completed",
                "content": "可核验终态正文",
                "degrades": warnings,
                "system_notices": [unsafe_path],
            }
        },
    )
    store.append_stream_event(
        run.run_id,
        event_id="report:complete",
        event_type="report.complete",
        payload={
            "report": {
                "status": "completed",
                "llm": {
                    "attempted": True,
                    "used": False,
                    "fallback_reason": "provider_timeout",
                },
            }
        },
    )
    store.finish_run(run.run_id, rs.STATUS_COMPLETED)

    raw_trace = json.dumps(store.load_trace(run.run_id), ensure_ascii=False)
    raw_events = json.dumps(
        store.load_stream_events(run.run_id),
        ensure_ascii=False,
    )
    assert "Traceback" in raw_trace
    assert "Traceback" in raw_events
    assert "/Users/alice" in raw_trace
    assert "/Users/alice" in raw_events

    trace_body = client.get(f"/api/runs/{run.run_id}/trace").text
    event_body = client.get(f"/api/runs/{run.run_id}/events").text
    public_body = f"{trace_body}\n{event_body}"

    assert "Traceback" not in public_body
    assert "/Users/alice" not in public_body
    assert "rag_index.py" not in public_body
    assert "untrusted index freshness" not in public_body
    assert "narrow retrieval empty" not in public_body
    assert "可核验草稿：英维克" in public_body
    assert "可核验终态正文" in public_body
    assert "news-impact" in public_body
    assert "模型精修超时" in public_body
    assert '"fallback_reason": "provider_timeout"' in event_body


def test_sse_replays_structured_report_modules_and_report_endpoint(
    client: TestClient,
) -> None:
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
    assert "event: report.start" in streamed
    assert "event: report.module" in streamed
    assert "event: report_start" not in streamed
    assert "event: report_module" not in streamed
    assert "id: module:l2_moneyflow" in streamed
    resumed = client.get(
        f"/api/runs/{run_id}/events",
        headers={"Last-Event-ID": "report:start"},
    ).text
    assert "event: report.start" not in resumed
    assert "event: report.module" in resumed

    current = client.get(f"/api/runs/{run_id}/report").json()
    assert current["modules"] == [module]


def test_sse_replays_workflow_loaded_and_hides_internal_events(
    client: TestClient,
) -> None:
    run_id = client.post("/api/runs", json={"question": "q"}).json()["run_id"]
    _wait_terminal(client, run_id)
    store = RunStore()
    workflow = {
        "owner": "theme-research",
        "label": "题材研究",
        "execution_mode": "inline",
        "preset": "theme-research",
        "required_skill_ids": ["theme-research"],
        "retrieval_stages": [
            "definition",
            "chain_stages",
            "company_mapping",
            "market_lifecycle",
            "counterevidence",
        ],
        "output_schema": "theme_research.v1",
        "presentation_kind": "research_answer",
        "max_wall_time_seconds": 90,
        "status": "loaded",
    }
    loaded = store.append_stream_event(
        run_id,
        event_id="workflow:theme-research:loaded",
        event_type="workflow.loaded",
        payload=workflow,
    )
    store.append_stream_event(
        run_id,
        event_id="recovery:test",
        event_type="run_recovered",
        payload={"reason": "test"},
    )

    full = client.get(f"/api/runs/{run_id}/events").text
    assert "event: workflow.loaded" in full
    assert "event: run_recovered" not in full
    assert '"owner": "theme-research"' in full

    resumed = client.get(
        f"/api/runs/{run_id}/events",
        params={"after": loaded["seq"] - 1},
    ).text
    assert "event: workflow.loaded" in resumed
    assert "event: run_recovered" not in resumed


def test_sse_canonical_cursor_and_terminal_replay(client: TestClient) -> None:
    run_id = client.post("/api/runs", json={"question": "q"}).json()["run_id"]
    _wait_terminal(client, run_id)
    store = RunStore()
    start = store.append_stream_event(
        run_id,
        event_id="report:start:new",
        event_type="report.start",
        payload={"report": {"modules": []}},
    )
    module = store.append_stream_event(
        run_id,
        event_id="report:module:new",
        event_type="report.module",
        payload={"module": {"module_id": "m1"}},
    )

    full = client.get(f"/api/runs/{run_id}/events").text
    assert "event: report.start" in full
    assert "event: report_start" not in full
    assert full.count(f"id: {start['event_id']}") == 1
    assert "event: step" not in full and "event: run" in full

    after = client.get(
        f"/api/runs/{run_id}/events", params={"after": start["seq"]}
    ).text
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
    assert (
        client.get(f"/api/runs/{run_id}/events", params={"after": -1}).status_code
        == 422
    )


def test_sse_initial_connection_keeps_polling_canonical_events(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RunStore()
    run = store.create_run("live trace", "ask")
    store.append_stream_event(
        run.run_id,
        event_id="trace:s01",
        event_type="trace.step",
        payload={"step": {"step_id": "s01", "name": "first", "status": "completed"}},
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
        store.append_stream_event(
            run.run_id,
            event_id="trace:s02",
            event_type="trace.step",
            payload={
                "step": {"step_id": "s02", "name": "later", "status": "completed"}
            },
        )
        store.finish_run(run.run_id, rs.STATUS_COMPLETED)

    monkeypatch.setattr(app_module.time, "sleep", add_later_step)
    body = client.get(f"/api/runs/{run.run_id}/events").text

    assert body.count("event: trace.step") == 2
    assert "event: step" not in body
    assert "id: trace:s02" in body
    assert '"step_id": "s02"' not in body


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


def test_daily_run_uses_one_pass_llm_and_template_followups(
    tmp_path, monkeypatch
) -> None:
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
    monkeypatch.setattr(
        ask_svc, "render_answer", lambda result: "# 结论\n市场修复延续。"
    )
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
        followups = fu_svc.generate_followups(
            req.question, matched_theme="液冷", use_llm=False
        )
        store.add_artifact(
            run_id,
            "followups.json",
            followups.to_json(),
            renderer="json",
            title="猜你想问",
        )
        store.finish_run(run_id, rs.STATUS_COMPLETED)

    monkeypatch.setattr(app_module, "_run_ask", fake_run_ask)
    parent_id = client.post("/api/runs", json={"question": "液冷题材怎么看"}).json()[
        "run_id"
    ]
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
    assert any(
        item["classification"] == "bound_evidence" and item["label"] == "[S1] 盘面快照"
        for item in context["evidence"]
    )
    assert any(item["label"] == "盘面证据" for item in context["evidence"])
    assert context["memory"] == []
    assert context["review"] == []


def test_ask_entry_coverage_grades_against_the_shared_required_outputs() -> None:
    """POST /api/runs 这条入口从不调 task_fulfillment，也从不传 answer_status。

    它和 TurnOrchestrator 是两个独立入口，`complete_report` 在 answer_status
    不在白名单时会静默回落成 business_status 默认值 "complete"——即「没有任何
    东西检查过答案，报告照报 complete」。这里锁住覆盖判定现在会被记录，
    且用的是与 build_task_frame 同一张 required_outputs 表。
    """

    result = SimpleNamespace(
        question_plan=SimpleNamespace(question_type="market_cause"),
        synthesis="当前主线是资金回流权重。因果链条来自成交额放大。",
    )

    coverage = app_module._ask_answer_coverage("为什么大盘涨了", result, "")

    assert coverage["entry_point"] == "api_runs_ask"
    assert coverage["question_type"] == "market_cause"
    # market_cause 的默认必需输出：direct_assessment / causal_chain /
    # counterpoint / evidence_boundary。前者正文写到了，后三者没有。
    assert coverage["present"] == ["direct_assessment"]
    assert "evidence_boundary" in coverage["absent"]
    assert coverage["marker_coverage"] == "incomplete"
    assert coverage["observation_only"] is True
    # causal_chain 没有 marker 词表，必须算 uncheckable 而不是 absent，
    # 否则仪表盲区会被统计成答案漏写。
    assert "causal_chain" in coverage["uncheckable"]
    assert "causal_chain" not in coverage["absent"]


def test_ask_entry_coverage_prefers_synthesis_over_rendered_markdown() -> None:
    """判的必须是用户看到的正文，不是 render_answer 的模板外壳。

    `render_answer` 会拼上章节标题等脚手架，用它当正文会让 marker 命中
    虚高——量出来的覆盖率会比真实情况好看。
    """

    result = SimpleNamespace(
        question_plan=SimpleNamespace(question_type="general_finance_qa"),
        synthesis=None,
    )

    coverage = app_module._ask_answer_coverage(
        "什么是 ROE",
        result,
        "直接回答：ROE 是净资产收益率。数据截至 2026-08-07。",
    )

    # synthesis 为 None 时回落到 answer_md
    assert coverage["question_type"] == "general_finance_qa"
    assert coverage["marker_coverage"] is not None


def test_ask_entry_coverage_reports_no_verdict_without_question_type() -> None:
    """question_plan 缺失时不能假装检过。

    这条路的 question_plan 是可选的（AskResult 默认 None）。取不到类型时
    required_outputs 落到兜底的 direct_answer/evidence_boundary，
    其中 direct_answer 没有 marker 词表——不能把它记成「答案漏写」。
    """

    result = SimpleNamespace(question_plan=None, synthesis="随便一句话。")

    coverage = app_module._ask_answer_coverage("q", result, "")

    assert coverage["question_type"] is None
    assert "direct_answer" in coverage["uncheckable"]


def test_artifact_api_filters_describes_and_serves_registered_content(
    client: TestClient,
) -> None:
    artifacts = client.get(
        "/api/artifacts", params={"category": "daily_agent", "date": "2026-07-09"}
    ).json()
    html_artifact = next(item for item in artifacts if item["format"] == "html")
    assert not html_artifact["source_path"].startswith("/")
    assert html_artifact["canonical_exists"] is True

    detail = client.get(f"/api/artifacts/{html_artifact['artifact_id']}").json()
    assert detail["artifact_id"] == html_artifact["artifact_id"]

    content = client.get(f"/api/artifacts/{html_artifact['artifact_id']}/content")
    assert content.status_code == 200
    assert "<h1>daily</h1>" in content.text
    assert "sandbox" in content.headers["content-security-policy"]


def test_artifact_content_rejects_unregistered_and_traversal_ids(
    client: TestClient,
) -> None:
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
        projection.json()["provenance"]["original_artifact_id"] != agent["artifact_id"]
    )

    review_projection = client.get(f"/api/artifacts/{review['artifact_id']}/projection")
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


def test_bootstrap_returns_workflows_runs_and_latest_artifact(
    client: TestClient,
) -> None:
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


def test_workbench_overview_is_fail_closed_without_market_database(
    client: TestClient,
) -> None:
    response = client.get("/api/workbench/overview")

    assert response.status_code == 200
    assert response.json()["market"]["stage"] == "数据缺失"
    assert response.json()["data_status"][0]["status"] == "missing"


def test_workbench_overview_uses_configured_finance_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    code_root = tmp_path / "runtime-code"
    finance_root = tmp_path / "private-finance-data"
    wiki = tmp_path / "wiki"
    stale_exports = code_root / "market_feature_store" / "exports"
    current_exports = finance_root / "market_feature_store" / "exports"
    stale_exports.mkdir(parents=True)
    current_exports.mkdir(parents=True)
    wiki.mkdir()
    (stale_exports / "2026-07-01-daily-agent.json").write_text(
        json.dumps({"date": "2026-07-01"}),
        encoding="utf-8",
    )
    (current_exports / "2026-07-20-daily-agent.json").write_text(
        json.dumps({"date": "2026-07-20"}),
        encoding="utf-8",
    )
    _write_overview_market_db(
        finance_root / "db" / "market_feature_store.duckdb",
        trade_date="2026-07-21",
    )
    monkeypatch.setenv("FINANCE_WS", str(finance_root))
    monkeypatch.setenv("KB_VAULT", str(wiki))
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))

    with TestClient(app_module.create_app(repo_root=code_root)) as probe:
        overview = probe.get("/api/workbench/overview").json()
        health = probe.get("/api/health").json()

    assert overview["as_of_date"] == "2026-07-21"
    assert overview["signal_date"] == "2026-07-20"
    database = next(item for item in overview["data_status"] if item["key"] == "market")
    assert database["status"] == "complete"
    assert overview["agent_artifact"] == (
        "market_feature_store/exports/2026-07-20-daily-agent.json"
    )
    assert health["runtime"]["code_root"] == str(code_root.resolve())
    assert health["runtime"]["finance_root"] == str(finance_root.resolve())


def test_workbench_overview_coverage_ignores_orphan_child_themes(
    tmp_path: Path,
) -> None:
    from intelligence.services.workbench_overview import build_workbench_overview

    finance_root = tmp_path / "finance"
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    db_path = finance_root / "db" / "market_feature_store.duckdb"
    _write_overview_market_db(db_path, trade_date="2026-07-24")
    con = duckdb.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE fact_mainline_theme_daily (
            trade_date DATE,
            theme_code TEXT,
            theme_name TEXT,
            sector_count INTEGER,
            min_sort INTEGER
        )
        """
    )
    con.execute(
        """
        INSERT INTO fact_mainline_theme_daily VALUES
            ('2026-07-24', 'T1', '题材一', 1, 1),
            ('2026-07-24', 'T2', '题材二', 1, 2),
            ('2026-07-24', 'T3', '题材三', 1, 3),
            ('2026-07-24', 'T4', '题材四', 1, 4)
        """
    )
    con.execute(
        """
        CREATE TABLE fact_mainline_sector_daily (
            trade_date DATE,
            theme_code TEXT,
            sector_name TEXT,
            cycle_status TEXT,
            sort_no INTEGER
        )
        """
    )
    con.execute(
        """
        INSERT INTO fact_mainline_sector_daily VALUES
            ('2026-07-24', 'T1', '板块一', '启动', 1),
            ('2026-07-24', 'T2', '板块二', '启动', 2),
            ('2026-07-24', 'T3', '板块三', '启动', 3),
            ('2026-07-24', 'T4', '板块四', '启动', 4),
            ('2026-07-24', 'ORPHAN', '孤儿板块', '启动', 5)
        """
    )
    con.close()

    overview = build_workbench_overview(finance_root, wiki)
    sector = next(
        item
        for item in overview["data_status"]
        if item["key"] == "mainline_sector"
    )

    assert sector["coverage"] == {"covered": 4, "total": 4, "missing": 0}


def test_learning_feedback_can_be_reviewed_without_editing_verdict(
    client: TestClient,
) -> None:
    root = Path(client.app.state.repo_root)
    learning = root / "docs" / "learning" / "forecast-lessons"
    reflection = learning / "reflections" / "2026-07-01.reflection.codex.duckdb.json"
    reflection.parent.mkdir(parents=True)
    reflection.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "date": "2026-07-01",
                "agent": "codex",
                "source": "duckdb",
                "status": "pending_review",
                "source_fingerprint": "fixture",
                "reflections": [
                    {
                        "id": "direction:semi",
                        "category": "direction",
                        "failure_mode": "A5 场景错位",
                        "reusable_lesson": "轮动期先看相对强度。",
                        "proposed_rule": "方向排序前先横比。",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    rules = learning / "rule_candidates.jsonl"
    rules.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "id": "rule-fixture",
                "status": "pending",
                "date": "2026-07-01",
                "rule": "每次方向排序至少横比三个候选。",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    pending = client.get("/api/workbench/learning-feedback")
    assert pending.status_code == 200
    assert len(pending.json()["pending_reflections"]) == 1
    assert len(pending.json()["pending_rules"]) == 1
    assert (
        client.post(
            f"/api/workbench/learning-feedback/reflections/{reflection.name}/reject",
            json={"hypothesis_ids": []},
        ).status_code
        == 400
    )

    approved = client.post(
        f"/api/workbench/learning-feedback/reflections/{reflection.name}/approve",
        json={"hypothesis_ids": ["direction:semi"]},
    )
    assert approved.status_code == 200
    assert approved.json()["pending_reflections"] == []
    assert approved.json()["approved_lesson_count"] == 1

    rule_approved = client.post(
        "/api/workbench/learning-feedback/rules/rule-fixture/status",
        json={"status": "approved"},
    )
    assert rule_approved.status_code == 200
    assert rule_approved.json()["pending_rules"] == []
    assert rule_approved.json()["approved_rule_count"] == 1
    assert (
        client.post(
            "/api/workbench/learning-feedback/reflections/not-json.txt/approve",
            json={"hypothesis_ids": []},
        ).status_code
        == 400
    )


def test_bootstrap_returns_self_use_maturity_projection(client: TestClient) -> None:
    ledger = SelfUseLedger(
        userspace.user_space("demo").root / "self-use" / "events.jsonl"
    )
    ledger.record(
        SelfUseEvent(
            trade_date="2026-07-11",
            workflow="daily_market",
            outcome="success",
            manual_rescue=False,
            severe_fact_error=False,
            useful=True,
            note="private note",
            run_id="private-run-id",
        )
    )

    response = client.get("/api/workbench/bootstrap", params={"user": "demo"})

    assert response.status_code == 200
    # 测试仓库根目录下没有 market_feature_store.duckdb → 日历不可用 → fail-closed。
    assert response.json()["self_use_maturity"] == {
        "distinct_trade_dates": 1,
        "success_rate": 1.0,
        "useful_rate": 1.0,
        "manual_rescue_rate": 0.0,
        "covered_workflows": ["daily_market"],
        "blockers": [
            "trading_calendar_unavailable",
            "minimum_trade_dates",
            "missing_workflows",
        ],
        "eligible_for_user_decision": False,
        "passed": False,
    }
    assert "private note" not in response.text
    assert "private-run-id" not in response.text


def test_bootstrap_does_not_create_missing_self_use_ledger(
    client: TestClient,
) -> None:
    ledger_path = userspace.user_space("read-only").root / "self-use" / "events.jsonl"
    assert not ledger_path.exists()

    response = client.get(
        "/api/workbench/bootstrap",
        params={"user": "read-only"},
    )

    assert response.status_code == 200
    assert not ledger_path.exists()


def test_bootstrap_reports_malformed_self_use_ledger(client: TestClient) -> None:
    ledger_path = userspace.user_space("corrupt").root / "self-use" / "events.jsonl"
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text('{"workflow": ', encoding="utf-8")

    response = client.get(
        "/api/workbench/bootstrap",
        params={"user": "corrupt"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "自用成熟度台账不可读"}


def test_index_serves_workbench_page(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Workbench" in resp.text


def test_continuous_turn_timeout_is_deployment_configurable(monkeypatch) -> None:
    """回合预算必须能按部署覆盖——它是物理约束，不是偏好。

    这个数经 verification_reserve 与 synthesis_reserve 层层扣减后，最终**就是**
    发给 provider 的 HTTP 请求超时（glm_agent_runtime.py `timeout=remaining`）。
    provider 换了，延迟分布就换了；写死会让「换 provider」变成「必须改代码」。

    2026-08-08 实测：默认 120 时首轮实得约 25s，而中转 P50=28s / P95=50s，
    约一半的 run 死在第一轮且 provider_attempts=1（没预算重试，看起来像重试
    失效，实际是没机会跑）。
    """
    from intelligence.api import app as app_module

    monkeypatch.delenv("WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS", raising=False)
    assert app_module._continuous_turn_timeout_seconds() == 120.0

    monkeypatch.setenv("WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS", "300")
    assert app_module._continuous_turn_timeout_seconds() == 300.0


def test_invalid_turn_timeout_falls_back_instead_of_crashing_startup(monkeypatch) -> None:
    """这是服务启动路径，一个拼错的环境变量不该让服务起不来。

    launchd 是 KeepAlive=true + ThrottleInterval=10：启动期抛异常不会「拒绝
    启动」，会变成每 10 秒重启一次的无限崩溃循环。
    """
    from intelligence.api import app as app_module

    for bad in ("abc", "", "0", "-5"):
        monkeypatch.setenv("WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS", bad)
        assert app_module._continuous_turn_timeout_seconds() == 120.0, bad
