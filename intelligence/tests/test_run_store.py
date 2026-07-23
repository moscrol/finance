import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from intelligence.services import run_store
from intelligence.services.run_store import RunStore

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "golden_run"

RUN_REQUIRED_KEYS = {
    "run_id",
    "user",
    "question",
    "task_type",
    "status",
    "schema_version",
    "session_id",
    "parent_run_id",
    "created_at",
    "finished_at",
    "source_date",
    "duckdb_cutoff",
    "kb_commit",
    "kb_index_built_at",
    "kb_index_freshness",
    "manifest_ref",
    "degrades",
    "error",
    "artifacts",
}

STEP_REQUIRED_KEYS = {
    "step_id",
    "name",
    "status",
    "started_at",
    "finished_at",
    "input_summary",
    "output_summary",
    "warnings",
}


@pytest.fixture()
def store(tmp_path: Path) -> RunStore:
    return RunStore(user_id="default", root=tmp_path / "runs")


def test_full_run_lifecycle(store: RunStore) -> None:
    run = store.create_run("测试问题", "ask", kb_commit="abc123")
    assert run.status == run_store.STATUS_RUNNING
    assert RUN_REQUIRED_KEYS <= set(
        json.loads(store.run_path(run.run_id).read_text()).keys()
    )

    store.append_step(
        run.run_id,
        step_id="s01",
        name="finance_graph_context",
        status="completed",
        input_summary="浪潮信息 + 国产算力",
        output_summary="命中 4 个概念",
    )
    store.append_step(run.run_id, step_id="s02", name="compose", status="completed")
    store.add_degrade(run.run_id, "ftshare_unavailable")
    store.add_artifact(
        run.run_id, "answer.md", "# 答案\n", renderer="markdown", title="答案"
    )
    done = store.finish_run(run.run_id, run_store.STATUS_COMPLETED)

    assert done.finished_at is not None
    assert done.degrades == ["ftshare_unavailable"]
    assert done.artifacts and done.artifacts[0]["path"] == "answer.md"
    assert done.artifacts[0]["sha256"]

    trace = store.load_trace(run.run_id)
    assert [s["step_id"] for s in trace] == ["s01", "s02"]
    assert STEP_REQUIRED_KEYS <= set(trace[0].keys())


def test_failed_run_records_error(store: RunStore) -> None:
    run = store.create_run("q", "ask")
    done = store.finish_run(run.run_id, run_store.STATUS_FAILED, error="LLM 超时")
    assert done.status == run_store.STATUS_FAILED
    assert done.error == "LLM 超时"


def test_update_provenance_persists_source_and_index_snapshot(store: RunStore) -> None:
    run = store.create_run("q", "ask")
    updated = store.update_provenance(
        run.run_id,
        source_date="2026-07-10",
        duckdb_cutoff="2026-07-10T15:00:00+08:00",
        kb_commit="abc123",
        kb_index_built_at="2026-07-10T12:00:00+00:00",
        kb_index_freshness="fresh",
    )

    assert updated.source_date == "2026-07-10"
    assert updated.duckdb_cutoff == "2026-07-10T15:00:00+08:00"
    assert updated.kb_commit == "abc123"
    assert updated.kb_index_built_at == "2026-07-10T12:00:00+00:00"
    assert updated.kb_index_freshness == "fresh"


def test_finish_rejects_non_terminal_status(store: RunStore) -> None:
    run = store.create_run("q", "ask")
    with pytest.raises(ValueError):
        store.finish_run(run.run_id, run_store.STATUS_RUNNING)


def test_terminal_status_cannot_be_overwritten(store: RunStore) -> None:
    run = store.create_run("q", "ask")
    store.finish_run(run.run_id, run_store.STATUS_CANCELLED, error="cancelled")

    saved = store.finish_run(run.run_id, run_store.STATUS_COMPLETED)

    assert saved.status == run_store.STATUS_CANCELLED
    assert saved.error == "cancelled"


def test_requeue_incomplete_runs_marks_only_active_runs_queued(store: RunStore) -> None:
    interrupted = store.create_run("q1", "ask")
    completed = store.create_run("q2", "ask")
    store.finish_run(completed.run_id, run_store.STATUS_COMPLETED)

    recovered = store.requeue_incomplete_runs(reason="service_restarted")

    assert [run.run_id for run in recovered] == [interrupted.run_id]
    saved = store.load_run(interrupted.run_id)
    assert saved.status == run_store.STATUS_QUEUED
    assert saved.error is None
    assert saved.degrades == ["service_restarted"]
    assert (
        store.load_stream_events(interrupted.run_id)[0]["event_type"] == "run_recovered"
    )
    assert store.load_run(completed.run_id).status == run_store.STATUS_COMPLETED


def test_append_step_rejects_bad_status(store: RunStore) -> None:
    run = store.create_run("q", "ask")
    with pytest.raises(ValueError):
        store.append_step(run.run_id, step_id="s01", name="x", status="bogus")


def test_redaction_on_write(store: RunStore) -> None:
    run = store.create_run("我的 api_key=sk-abcdef1234567890 泄漏了吗", "ask")
    assert "sk-abcdef" not in run.question
    step = store.append_step(
        run.run_id,
        step_id="s01",
        name="x",
        status="completed",
        output_summary="token: ghp_0123456789abcdef0123",
    )
    assert "ghp_" not in step["output_summary"]


def test_redact_removes_complete_bearer_and_secret_assignment_values() -> None:
    secrets = (
        "auth-token-123456789",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.s3cr3tSignature",
        "api-secret-123456789",
        "token-secret-123456789",
        "quoted secret 123456789",
        "password-secret-123456789",
    )
    raw = "\n".join(
        (
            f"Authorization: Bearer {secrets[0]}",
            f"Bearer {secrets[1]}",
            f"api_key={secrets[2]}",
            f"token: {secrets[3]}",
            f"secret='{secrets[4]}'",
            f"password = {secrets[5]}",
        )
    )

    safe = run_store.redact(raw)

    assert safe.count("[REDACTED]") == 6
    for secret in secrets:
        assert secret not in safe


def test_redact_value_recursively_sanitizes_nested_payloads() -> None:
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhYmMifQ.jwtSignature123"
    payload = {
        "message": f"Authorization: Bearer private-auth-token\nBearer {jwt}",
        "nested": [
            {"detail": "api_key=nested-api-secret"},
            ("token=nested-token-secret",),
        ],
        "token": "nested-key-token-secret",
    }

    safe = run_store.redact_value(payload)
    rendered = str(safe)

    for secret in (
        "private-auth-token",
        jwt,
        "nested-api-secret",
        "nested-token-secret",
        "nested-key-token-secret",
    ):
        assert secret not in rendered


def test_redact_value_sanitizes_secret_mapping_keys_without_losing_metrics() -> None:
    payload = {
        "Authorization: Bearer KEY_LEAK_SENTINEL": "header value",
        "nested": {
            "api_key=KEY_API_SENTINEL": "credential value",
            "token_usage": 17,
            "authentication_method": "oauth",
        },
    }

    safe = run_store.redact_value(payload)
    rendered = str(safe)

    assert "KEY_LEAK_SENTINEL" not in rendered
    assert "KEY_API_SENTINEL" not in rendered
    assert safe["nested"]["token_usage"] == 17
    assert safe["nested"]["authentication_method"] == "oauth"


def test_redact_covers_production_secret_names_and_any_authorization_scheme() -> None:
    secrets = {
        "openai_api_key": "OPENAI_SECRET_SENTINEL",
        "FORESIGHT_BUILTIN_LLM_API_KEY": "FORESIGHT_SECRET_SENTINEL",
        "access_token": "ACCESS_SECRET_SENTINEL",
        "client_secret": "CLIENT_SECRET_SENTINEL",
    }
    payload = secrets | {
        "token_usage": 23,
        "authentication_method": "oauth",
    }
    raw_headers = "\n".join(
        (
            "Authorization: Basic dXNlcjpwYXNz",
            "Authorization: Digest DIGEST_SECRET_SENTINEL",
        )
    )

    safe_payload = run_store.redact_value(payload)
    safe_headers = run_store.redact(raw_headers)
    rendered = str((safe_payload, safe_headers))

    for secret in (*secrets.values(), "dXNlcjpwYXNz", "DIGEST_SECRET_SENTINEL"):
        assert secret not in rendered
    assert safe_payload["token_usage"] == 23
    assert safe_payload["authentication_method"] == "oauth"


def test_redact_covers_complex_and_json_authorization_values_to_line_end() -> None:
    secrets = (
        "NONCE_SECRET_SENTINEL",
        "RESPONSE_SECRET_SENTINEL",
        "AWS_CREDENTIAL_SENTINEL",
        "AWS_SIGNATURE_SECRET_SENTINEL",
        "JSON_BEARER_SECRET_SENTINEL",
    )
    raw = "\n".join(
        (
            "Authorization: Digest username=alice, realm=bank, "
            f"nonce={secrets[0]}, response={secrets[1]}",
            "Authorization: AWS4-HMAC-SHA256 "
            f"Credential={secrets[2]}, SignedHeaders=host, "
            f"Signature={secrets[3]}",
            f'{{"Authorization":"Bearer {secrets[4]}"}}',
        )
    )

    safe = run_store.redact(raw)

    for secret in secrets:
        assert secret not in safe
    assert "Authorization" not in safe


def test_run_id_path_traversal_rejected(store: RunStore) -> None:
    with pytest.raises(ValueError):
        store.run_dir("../escape")


def test_artifact_reregister_is_idempotent(store: RunStore) -> None:
    run = store.create_run("q", "ask")
    store.add_artifact(run.run_id, "answer.md", "v1", renderer="markdown", title="答案")
    store.add_artifact(run.run_id, "answer.md", "v2", renderer="markdown", title="答案")
    loaded = store.load_run(run.run_id)
    assert len(loaded.artifacts) == 1
    assert (store.run_dir(run.run_id) / "answer.md").read_text() == "v2"


def test_golden_run_fixture_conforms_to_protocol() -> None:
    """golden run 样例（脱敏）作为协议 v1 的回归 fixture：schema 变更必须先过这里。"""
    run_dirs = sorted(FIXTURE_ROOT.glob("run_*"))
    assert run_dirs, "缺 golden run fixture"
    for run_dir in run_dirs:
        payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        assert RUN_REQUIRED_KEYS <= set(payload.keys())
        assert payload["schema_version"] == run_store.SCHEMA_VERSION
        assert payload["status"] in run_store.RUN_STATUSES
        for art in payload["artifacts"]:
            assert (run_dir / art["path"]).exists(), f"产物文件缺失：{art['path']}"
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines():
            step = json.loads(line)
            assert STEP_REQUIRED_KEYS <= set(step.keys())
            assert step["status"] in run_store.STEP_STATUSES


def test_stream_envelope_sequence_cursor_and_idempotency(store: RunStore) -> None:
    run = store.create_run("q", "ask", session_id="conversation-1")
    first = store.append_stream_event(
        run.run_id,
        event_id="e1",
        event_type="report_start",
        message_id="message-1",
        payload={"token": "sk-abcdef1234567890"},
    )
    second = store.append_stream_event(
        run.run_id,
        event_id="e2",
        event_type="report.module",
        payload={"n": 2},
    )
    retry = store.append_stream_event(
        run.run_id,
        event_id="e1",
        event_type="report.start",
        message_id="message-1",
        payload={"token": "sk-abcdef1234567890"},
    )
    assert [first["seq"], second["seq"]] == [1, 2]
    assert first == retry
    assert first["schema_version"] == 1
    assert first["conversation_id"] == "conversation-1"
    assert first["message_id"] == "message-1"
    assert first["event_type"] == "report.start"
    assert "sk-abcdef" not in json.dumps(first)
    assert store.load_stream_events(run.run_id, after=1) == [second]
    with pytest.raises(ValueError, match="cursor"):
        store.load_stream_events(run.run_id, after=-1)
    with pytest.raises(ValueError, match="duplicate"):
        store.append_stream_event(
            run.run_id,
            event_id="e1",
            event_type="report.start",
            payload={"different": True},
        )


@pytest.mark.parametrize("field", ["event_id", "event_type"])
@pytest.mark.parametrize("value", ["", "   "])
def test_append_stream_event_rejects_blank_identity_fields(
    store: RunStore, field: str, value: str
) -> None:
    run = store.create_run("q", "ask")
    kwargs = {"event_id": "e1", "event_type": "report.start", "payload": {}}
    kwargs[field] = value

    with pytest.raises(ValueError, match=field):
        store.append_stream_event(run.run_id, **kwargs)


def test_default_stream_conversation_id_is_redacted(store: RunStore) -> None:
    run = store.create_run("q", "ask", session_id="token=super-secret-value")

    event = store.append_stream_event(
        run.run_id, event_id="e1", event_type="report.start", payload={}
    )

    assert event["conversation_id"] == "[REDACTED]"


def test_concurrent_stream_appends_have_linear_unique_sequences(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    first_store = RunStore(user_id="default", root=root)
    run = first_store.create_run("q", "ask")

    def append(index: int) -> dict:
        return RunStore(user_id="default", root=root).append_stream_event(
            run.run_id,
            event_id=f"e{index}",
            event_type="trace.step",
            payload={"i": index},
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(append, range(40)))
    events = first_store.load_stream_events(run.run_id)
    assert [event["seq"] for event in events] == list(range(1, 41))
    assert len({event["event_id"] for event in events}) == 40


def test_legacy_stream_projection_and_corruption_rules(store: RunStore) -> None:
    run = store.create_run("q", "ask", session_id="conversation-legacy")
    path = store.stream_path(run.run_id)
    legacy = {
        "event_id": "old",
        "event_type": "report_module",
        "created_at": "then",
        "payload": {"x": 1},
    }
    legacy2 = legacy | {"event_id": "old2", "payload": {"x": 2}}
    path.write_text(
        "\n\n"
        + json.dumps(legacy)
        + "\n\n"
        + json.dumps(legacy2)
        + "\n"
        + '{"truncated":',
        encoding="utf-8",
    )
    events = store.load_stream_events(run.run_id)
    assert [event["seq"] for event in events] == [1, 2]
    assert events == [
        {
            "schema_version": 1,
            "event_id": "old",
            "event_type": "report.module",
            "run_id": run.run_id,
            "conversation_id": "conversation-legacy",
            "message_id": None,
            "seq": 1,
            "created_at": "then",
            "payload": {"x": 1},
        },
        {
            "schema_version": 1,
            "event_id": "old2",
            "event_type": "report.module",
            "run_id": run.run_id,
            "conversation_id": "conversation-legacy",
            "message_id": None,
            "seq": 2,
            "created_at": "then",
            "payload": {"x": 2},
        },
    ]
    with pytest.raises(ValueError, match="newline"):
        store.append_stream_event(
            run.run_id, event_id="new", event_type="report.complete", payload={}
        )

    path.write_text(
        json.dumps(legacy)
        + "\nnot-json\n"
        + json.dumps(legacy | {"event_id": "old2"})
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="corrupt"):
        store.load_stream_events(run.run_id)


def test_persisted_stream_sequence_must_start_at_one_and_be_contiguous(
    store: RunStore,
) -> None:
    run = store.create_run("q", "ask", session_id="conversation-native")
    path = store.stream_path(run.run_id)
    envelope = {
        "schema_version": 1,
        "event_id": "e1",
        "event_type": "report.start",
        "run_id": run.run_id,
        "conversation_id": "conversation-native",
        "message_id": None,
        "seq": 2,
        "created_at": "then",
        "payload": {},
    }
    path.write_text(json.dumps(envelope) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"^invalid stream row 1$"):
        store.load_stream_events(run.run_id)

    path.write_text(
        json.dumps(envelope | {"seq": 1})
        + "\n"
        + json.dumps(envelope | {"event_id": "e2", "seq": 3})
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"^invalid stream row 2$"):
        store.load_stream_events(run.run_id)


@pytest.mark.parametrize(
    "bad_row",
    [
        [],
        {"schema_version": 2},
        {"schema_version": "1"},
    ],
)
def test_native_stream_rejects_invalid_row_or_schema(
    store: RunStore, bad_row: object
) -> None:
    run = store.create_run("q", "ask")
    store.stream_path(run.run_id).write_text(
        json.dumps(bad_row) + "\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="stream row 1"):
        store.load_stream_events(run.run_id)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("run_id", "another-run"),
        ("seq", True),
        ("seq", 2),
        ("event_id", ""),
        ("event_id", "   "),
        ("event_type", ""),
        ("event_type", "   "),
        ("created_at", ""),
        ("created_at", 3),
        ("payload", []),
    ],
)
def test_native_stream_rejects_invalid_envelope_fields(
    store: RunStore, field: str, value: object
) -> None:
    run = store.create_run("q", "ask")
    envelope = {
        "schema_version": 1,
        "event_id": "e1",
        "event_type": "report.start",
        "run_id": run.run_id,
        "conversation_id": None,
        "message_id": None,
        "seq": 1,
        "created_at": "then",
        "payload": {},
    }
    envelope[field] = value
    store.stream_path(run.run_id).write_text(
        json.dumps(envelope) + "\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="stream row 1") as exc_info:
        store.load_stream_events(run.run_id)
    assert str(store.stream_path(run.run_id)) not in str(exc_info.value)
    assert "another-run" not in str(exc_info.value)


def test_native_stream_rejects_duplicate_ids_with_safe_row_number(
    store: RunStore,
) -> None:
    run = store.create_run("q", "ask")
    base = {
        "schema_version": 1,
        "event_id": "secret-event-id",
        "event_type": "report.start",
        "run_id": run.run_id,
        "conversation_id": None,
        "message_id": None,
        "seq": 1,
        "created_at": "then",
        "payload": {},
    }
    store.stream_path(run.run_id).write_text(
        json.dumps(base) + "\n" + json.dumps(base | {"seq": 2}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="stream row 2") as exc_info:
        store.load_stream_events(run.run_id)
    assert "secret-event-id" not in str(exc_info.value)
