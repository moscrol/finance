import hashlib
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from threading import Event
import time

import pytest

from intelligence.services.run_store import Artifact, RunStore, STATUS_CANCELLED


@pytest.fixture
def store(tmp_path: Path) -> RunStore:
    return RunStore(user_id="history-owner", root=tmp_path / "runs")


def test_history_original_is_complete_and_same_content_is_idempotent(store: RunStore):
    run = store.create_run("历史研究", "history")
    payload = {"rows": [{"date": i, "结论": "未知"} for i in range(400)], "version": 1}
    original = json.loads(json.dumps(payload))

    artifact = store.add_history_artifact(run.run_id, "query", payload)
    run_bytes = store.run_path(run.run_id).read_bytes()
    path = store.run_dir(run.run_id) / artifact.path
    original_stat = path.stat()
    repeated = store.add_history_artifact(
        run.run_id, "query", {"version": 1, "rows": payload["rows"]}
    )

    assert isinstance(artifact, Artifact)
    assert artifact.path == f"history-query-{artifact.sha256}.json"
    assert artifact.renderer == "json"
    assert artifact.visibility == "public"
    assert artifact.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert artifact.bytes == len(path.read_bytes())
    assert repeated == artifact
    assert store.load_run(run.run_id).artifacts == [asdict(artifact)]
    assert store.run_path(run.run_id).read_bytes() == run_bytes
    assert path.stat().st_mtime_ns == original_stat.st_mtime_ns
    assert store.read_history_artifact(run.run_id, artifact.path) == original
    assert payload == original


def test_revision_and_kind_each_get_a_new_reference(store: RunStore):
    run = store.create_run("q", "history")
    artifacts = [
        store.add_history_artifact(run.run_id, "query", {"window": 20}),
        store.add_history_artifact(run.run_id, "query", {"window": 40}),
        store.add_history_artifact(run.run_id, "case", {"window": 20}),
        store.add_history_artifact(run.run_id, "hypothesis", {"window": 20}),
    ]
    assert len({artifact.path for artifact in artifacts}) == 4
    assert len(store.load_run(run.run_id).artifacts) == 4
    assert store.read_history_artifact(run.run_id, artifacts[0].path) == {"window": 20}


@pytest.mark.parametrize(
    "kind", ["", "result", "Query", "../query", "query/a", "假设", None]
)
def test_kind_is_controlled_before_any_content_write(store: RunStore, kind):
    run = store.create_run("q", "history")
    with pytest.raises(ValueError):
        store.add_history_artifact(run.run_id, kind, {})
    assert not list(store.run_dir(run.run_id).glob("history-*"))
    assert store.load_run(run.run_id).artifacts == []


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "text",
        {1: "ambiguous key"},
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": object()},
        {"value": (1, 2)},
    ],
)
def test_payload_requires_a_json_object_without_lossy_values(store: RunStore, payload):
    run = store.create_run("q", "history")
    with pytest.raises((ValueError, TypeError)):
        store.add_history_artifact(run.run_id, "query", payload)
    assert not list(store.run_dir(run.run_id).glob("history-*"))


def test_unknown_run_is_not_created(store: RunStore):
    with pytest.raises(FileNotFoundError):
        store.add_history_artifact("run_missing", "query", {})
    assert not store.run_dir("run_missing").exists()


@pytest.mark.parametrize(
    "run_id", ["", ".", "..", "../run_other", "other/run", "other\\run"]
)
def test_run_path_escape_is_rejected(store: RunStore, run_id):
    with pytest.raises(ValueError):
        store.add_history_artifact(run_id, "query", {})
    with pytest.raises(ValueError):
        store.read_history_artifact(run_id, "history-query-" + "a" * 64 + ".json")


def test_owner_is_checked_even_with_an_explicit_shared_test_root(store: RunStore):
    run = store.create_run("q", "history")
    artifact = store.add_history_artifact(run.run_id, "query", {"private": True})
    other = RunStore(user_id="other-user", root=store.root)
    before = store.run_path(run.run_id).read_bytes()
    with pytest.raises(PermissionError):
        other.read_history_artifact(run.run_id, artifact.path)
    with pytest.raises(PermissionError):
        other.add_history_artifact(run.run_id, "case", {"other": True})
    assert store.run_path(run.run_id).read_bytes() == before
    assert len(list(store.run_dir(run.run_id).glob("history-*"))) == 1


@pytest.mark.parametrize(
    "filename",
    [
        "../run.json",
        "/tmp/original.json",
        "run.json",
        "history-query-invalid.json",
        "history-result-" + "a" * 64 + ".json",
    ],
)
def test_only_controlled_history_filenames_can_be_read(store: RunStore, filename):
    run = store.create_run("q", "history")
    with pytest.raises(ValueError):
        store.read_history_artifact(run.run_id, filename)


def test_unregistered_file_cannot_be_read(store: RunStore):
    run = store.create_run("q", "history")
    data = b'{"rows":[]}\n'
    filename = f"history-query-{hashlib.sha256(data).hexdigest()}.json"
    (store.run_dir(run.run_id) / filename).write_bytes(data)
    with pytest.raises(FileNotFoundError):
        store.read_history_artifact(run.run_id, filename)


def test_tampering_is_rejected_without_repair_or_overwrite(store: RunStore):
    run = store.create_run("q", "history")
    artifact = store.add_history_artifact(run.run_id, "query", {"rows": []})
    path = store.run_dir(run.run_id) / artifact.path
    path.write_text('{"rows":["forged"]}\n')
    forged = path.read_bytes()
    with pytest.raises(ValueError, match="integrity"):
        store.read_history_artifact(run.run_id, artifact.path)
    with pytest.raises(ValueError, match="integrity"):
        store.add_history_artifact(run.run_id, "query", {"rows": []})
    assert path.read_bytes() == forged


@pytest.mark.parametrize(
    "field,value", [("sha256", "0" * 64), ("bytes", 1), ("renderer", "html")]
)
def test_registered_metadata_is_verified(store: RunStore, field, value):
    run = store.create_run("q", "history")
    artifact = store.add_history_artifact(run.run_id, "query", {})
    saved = store.load_run(run.run_id)
    saved.artifacts[0][field] = value
    store._write_run(saved)
    with pytest.raises(ValueError, match="integrity"):
        store.read_history_artifact(run.run_id, artifact.path)


def test_registered_missing_content_is_not_silently_recreated(store: RunStore):
    run = store.create_run("q", "history")
    artifact = store.add_history_artifact(run.run_id, "query", {})
    path = store.run_dir(run.run_id) / artifact.path
    path.unlink()
    with pytest.raises(FileNotFoundError):
        store.add_history_artifact(run.run_id, "query", {})
    assert not path.exists()


def test_orphan_from_failed_registration_is_recovered_on_retry(
    store: RunStore, monkeypatch
):
    run = store.create_run("q", "history")
    write_run = store._write_run

    def fail_registration(_run):
        raise OSError("registration interrupted")

    monkeypatch.setattr(store, "_write_run", fail_registration)
    with pytest.raises(OSError, match="registration interrupted"):
        store.add_history_artifact(run.run_id, "query", {"rows": [1]})
    (orphan,) = store.run_dir(run.run_id).glob("history-*")
    initial_stat = orphan.stat()
    with pytest.raises(FileNotFoundError):
        store.read_history_artifact(run.run_id, orphan.name)

    monkeypatch.setattr(store, "_write_run", write_run)
    artifact = store.add_history_artifact(run.run_id, "query", {"rows": [1]})
    assert artifact.path == orphan.name
    assert orphan.stat().st_mtime_ns == initial_stat.st_mtime_ns
    assert store.read_history_artifact(run.run_id, orphan.name) == {"rows": [1]}
    assert not list(store.run_dir(run.run_id).glob(".history-*.tmp"))


def test_symlinked_artifact_is_rejected(store: RunStore, tmp_path: Path):
    run = store.create_run("q", "history")
    artifact = store.add_history_artifact(run.run_id, "query", {})
    path = store.run_dir(run.run_id) / artifact.path
    outside = tmp_path / "outside.json"
    path.replace(outside)
    path.symlink_to(outside)
    with pytest.raises(ValueError, match="path"):
        store.read_history_artifact(run.run_id, artifact.path)
    with pytest.raises(ValueError, match="path"):
        store.add_history_artifact(run.run_id, "query", {})


def test_symlinked_run_directory_is_rejected(store: RunStore, tmp_path: Path):
    run = store.create_run("q", "history")
    path = store.run_dir(run.run_id)
    outside = tmp_path / "outside-run"
    path.rename(outside)
    path.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="path"):
        store.add_history_artifact(run.run_id, "query", {})
    assert not list(outside.glob("history-*"))


def test_internal_visibility_is_retained_and_cannot_be_promoted_by_retry(
    store: RunStore,
):
    run = store.create_run("q", "history")
    artifact = store.add_history_artifact(
        run.run_id, "query", {}, visibility="internal"
    )
    assert artifact.visibility == "internal"
    assert (
        store.add_history_artifact(run.run_id, "query", {}, visibility="internal")
        == artifact
    )
    with pytest.raises(FileNotFoundError):
        store.read_history_artifact(run.run_id, artifact.path)
    with pytest.raises(ValueError, match="conflicting"):
        store.add_history_artifact(run.run_id, "query", {})
    with pytest.raises(ValueError, match="visibility"):
        store.add_history_artifact(run.run_id, "case", {}, visibility="unknown")
    assert store.load_run(run.run_id).artifacts == [asdict(artifact)]


def test_existing_content_survives_cancellation(store: RunStore):
    run = store.create_run("q", "history")
    artifact = store.add_history_artifact(run.run_id, "case", {"pending": ["查反例"]})
    store.finish_run(run.run_id, STATUS_CANCELLED)
    assert store.read_history_artifact(run.run_id, artifact.path) == {
        "pending": ["查反例"]
    }
    assert (
        store.add_history_artifact(run.run_id, "case", {"pending": ["查反例"]})
        == artifact
    )
    assert store.load_run(run.run_id).status == STATUS_CANCELLED


def test_concurrent_store_instances_do_not_lose_or_duplicate_references(
    store: RunStore,
):
    run = store.create_run("q", "history")

    def write(index):
        peer = RunStore(user_id=store.user_id, root=store.root)
        return peer.add_history_artifact(run.run_id, "query", {"index": index % 4})

    with ThreadPoolExecutor(max_workers=4) as pool:
        artifacts = list(pool.map(write, range(16)))
    assert len({artifact.path for artifact in artifacts}) == 4
    assert len(store.load_run(run.run_id).artifacts) == 4
    assert len(list(store.run_dir(run.run_id).glob("history-*"))) == 4
    for artifact in artifacts:
        assert "index" in store.read_history_artifact(run.run_id, artifact.path)


def _write_history_in_process(root: Path, user_id: str, run_id: str, index: int):
    store = RunStore(user_id=user_id, root=root)
    return store.add_history_artifact(run_id, "query", {"index": index % 3}).path


def test_concurrent_processes_keep_all_registered_originals(store: RunStore):
    run = store.create_run("q", "history")
    with ProcessPoolExecutor(
        max_workers=3, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        futures = [
            pool.submit(
                _write_history_in_process, store.root, store.user_id, run.run_id, i
            )
            for i in range(12)
        ]
        filenames = {future.result(timeout=30) for future in futures}
    assert len(filenames) == 3
    assert {row["path"] for row in store.load_run(run.run_id).artifacts} == filenames
    for filename in filenames:
        assert "index" in store.read_history_artifact(run.run_id, filename)


def _write_mixed_metadata_in_process(root: Path, user_id: str, run_id: str, index: int):
    writer = RunStore(user_id=user_id, root=root)
    if index % 4 == 0:
        artifact = writer.add_history_artifact(run_id, "query", {"index": index})
        return "history", artifact.path
    if index % 4 == 1:
        artifact = writer.add_artifact(
            run_id, f"answer-{index}.md", str(index), renderer="markdown", title="答案"
        )
        return "answer", artifact.path
    if index % 4 == 2:
        writer.update_provenance(run_id, kb_commit=f"commit-{index}")
    else:
        writer.finish_run(run_id, STATUS_CANCELLED)
    return "state", None


def test_mixed_process_writers_keep_cancelled_status_and_all_returned_refs(
    store: RunStore,
):
    run = store.create_run("q", "history")
    with ProcessPoolExecutor(
        max_workers=4, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        futures = [
            pool.submit(
                _write_mixed_metadata_in_process,
                store.root,
                store.user_id,
                run.run_id,
                i,
            )
            for i in range(20)
        ]
        results = [future.result(timeout=30) for future in futures]
    saved = store.load_run(run.run_id)
    assert saved.status == STATUS_CANCELLED
    assert {item["path"] for item in saved.artifacts} == {
        filename for _kind, filename in results if filename is not None
    }
    for kind, filename in results:
        if kind == "history":
            assert "index" in store.read_history_artifact(run.run_id, filename)


@pytest.mark.parametrize(
    "first_action,second_action",
    [
        ("history", "cancel"),
        ("cancel", "history"),
        ("history", "answer"),
        ("answer", "history"),
    ],
)
def test_history_and_existing_writers_share_one_run_transaction(
    store: RunStore, monkeypatch, first_action, second_action
):
    run = store.create_run("q", "history")
    peer = RunStore(user_id=store.user_id, root=store.root)
    first_loaded, release_first, second_started, second_finished = (
        Event(),
        Event(),
        Event(),
        Event(),
    )
    original_write = store._write_run

    def pause_after_first_load(value):
        first_loaded.set()
        assert release_first.wait(5)
        original_write(value)

    monkeypatch.setattr(store, "_write_run", pause_after_first_load)

    def invoke(writer, action):
        if action == "history":
            return writer.add_history_artifact(run.run_id, "query", {"rows": [1]})
        if action == "cancel":
            return writer.finish_run(run.run_id, STATUS_CANCELLED)
        return writer.add_artifact(
            run.run_id, "answer.md", "answer", renderer="markdown", title="答案"
        )

    def second_writer():
        second_started.set()
        try:
            return invoke(peer, second_action)
        finally:
            second_finished.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(invoke, store, first_action)
        try:
            assert first_loaded.wait(5)
            second = pool.submit(second_writer)
            assert second_started.wait(5)
            completed_while_first_was_stale = second_finished.wait(0.1)
        finally:
            release_first.set()
        results = {
            first_action: first.result(timeout=5),
            second_action: second.result(timeout=5),
        }

    assert not completed_while_first_was_stale
    artifact = results["history"]
    assert store.read_history_artifact(run.run_id, artifact.path) == {"rows": [1]}
    saved = peer.load_run(run.run_id)
    if "cancel" in results:
        assert saved.status == STATUS_CANCELLED
        assert saved.finished_at is not None
    else:
        assert {row["path"] for row in saved.artifacts} == {artifact.path, "answer.md"}


def test_recovery_rechecks_terminal_status_under_the_same_run_lock(
    store: RunStore, monkeypatch
):
    run = store.create_run("q", "history")
    peer = RunStore(user_id=store.user_id, root=store.root)
    stale_list = store.list_runs()

    def list_then_cancel():
        peer.finish_run(run.run_id, STATUS_CANCELLED)
        return stale_list

    monkeypatch.setattr(store, "list_runs", list_then_cancel)
    assert store.requeue_incomplete_runs(reason="restart") == []
    assert store.load_run(run.run_id).status == STATUS_CANCELLED


def test_general_add_artifact_keeps_its_existing_replace_behavior(store: RunStore):
    run = store.create_run("q", "history")
    first = store.add_artifact(
        run.run_id, "answer.md", "old", renderer="markdown", title="答案"
    )
    second = store.add_artifact(
        run.run_id, "answer.md", "new", renderer="markdown", title="答案"
    )
    assert first.sha256 != second.sha256
    assert (store.run_dir(run.run_id) / "answer.md").read_text() == "new"
    assert store.load_run(run.run_id).artifacts == [asdict(second)]


def test_case_transaction_serializes_precreated_store_instances(store: RunStore):
    peer = RunStore(user_id=store.user_id, root=store.root)
    started, entered = Event(), Event()

    def attempt():
        started.set()
        with peer.history_case_transaction("conv-review", "case-review"):
            entered.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with store.history_case_transaction("conv-review", "case-review"):
            waiting = pool.submit(attempt)
            assert started.wait(5)
            entered_early = entered.wait(0.1)
        waiting.result(timeout=5)
    assert not entered_early
    assert entered.is_set()


def _increment_under_case_transaction(root: Path, counter: Path, repetitions: int):
    writer = RunStore(user_id="case-owner", root=root)
    for _ in range(repetitions):
        with writer.history_case_transaction("conv-review", "case-review"):
            before = int(counter.read_text())
            time.sleep(
                0.002
            )  # Widen a lost-update race if the process lock is missing.
            counter.write_text(str(before + 1))


def test_case_transaction_serializes_processes_without_a_second_index(tmp_path: Path):
    root = tmp_path / "runs"
    RunStore(user_id="case-owner", root=root)
    counter = tmp_path / "test-counter.txt"
    counter.write_text("0")
    with ProcessPoolExecutor(
        max_workers=3, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        futures = [
            pool.submit(_increment_under_case_transaction, root, counter, 10)
            for _ in range(3)
        ]
        for future in futures:
            future.result(timeout=30)
    assert counter.read_text() == "30"
    locks = list((root / ".history-case-locks").iterdir())
    assert len(locks) == 1
    assert locks[0].suffix == ".lock"
    assert len(locks[0].stem) == 64
    assert locks[0].read_bytes() == b""


def test_case_transaction_does_not_block_another_case(store: RunStore):
    peer = RunStore(user_id=store.user_id, root=store.root)

    def other_case():
        with peer.history_case_transaction("conv-review", "case-other"):
            return True

    with ThreadPoolExecutor(max_workers=1) as pool:
        with store.history_case_transaction("conv-review", "case-review"):
            assert pool.submit(other_case).result(timeout=5)


@pytest.mark.parametrize(
    "invalid", [None, "", " ", "../escape", "a/b", "a\\b", "a" * 201]
)
@pytest.mark.parametrize("field", ["conversation", "case"])
def test_case_transaction_rejects_invalid_ids_before_lock_creation(
    store: RunStore, invalid, field
):
    conversation, case = (
        (invalid, "case-review")
        if field == "conversation"
        else ("conv-review", invalid)
    )
    with pytest.raises(ValueError):
        with store.history_case_transaction(conversation, case):
            pytest.fail("invalid case identity acquired a transaction")
    assert not (store.root / ".history-case-locks").exists()


def test_case_lock_directory_cannot_be_redirected(store: RunStore, tmp_path: Path):
    outside = tmp_path / "outside-locks"
    outside.mkdir()
    (store.root / ".history-case-locks").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="path"):
        with store.history_case_transaction("conv-review", "case-review"):
            pytest.fail("redirected case lock was accepted")
    assert not list(outside.iterdir())
