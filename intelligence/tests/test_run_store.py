import json
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
    assert RUN_REQUIRED_KEYS <= set(json.loads(store.run_path(run.run_id).read_text()).keys())

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
    store.add_artifact(run.run_id, "answer.md", "# 答案\n", renderer="markdown", title="答案")
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
