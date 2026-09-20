from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from unittest import mock

import pytest

from intelligence.services import kb_rag, rag_generation_identity, rag_worker
from intelligence.services.rag_worker import PersistentRagWorker, WorkerResponse
from intelligence.tests.test_rag_worker import _write_fake_rag


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _managed_generation(tmp_path: Path, name: str) -> dict[str, str]:
    root = tmp_path / "generations-root"
    candidate = root / "generations" / name
    code = candidate / "code"
    source = candidate / "source"
    wiki = source / "wiki"
    standard = candidate / "standard"
    full = candidate / "full"
    for directory in (code, wiki, standard, full):
        directory.mkdir(parents=True, exist_ok=True)
    _write_fake_rag(code)
    marker = {"root": str(root), "generation": name}
    _write_json(candidate / ".rag-generation.json", marker)
    paths = {
        ".": candidate,
        "code": code,
        "source": source,
        "standard": standard,
        "full": full,
    }
    manifest = {
        "schema": 1,
        "state": "validated",
        "generation": name,
        "root": str(root),
        "path_identities": {
            key: [path.stat().st_dev, path.stat().st_ino]
            for key, path in paths.items()
        },
        "runtime": {"executable": sys.executable},
        "sources": {"wiki_name": "wiki"},
        "indexes": {
            "standard": {"path": str(standard)},
            "full": {"path": str(full)},
        },
    }
    manifest_path = candidate / "manifest.json"
    _write_json(manifest_path, manifest)
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return {
        "name": name,
        "root": str(root),
        "candidate": str(candidate),
        "manifest": str(manifest_path),
        "sha": manifest_sha,
        "code": str(code),
        "wiki": str(wiki),
        "standard": str(standard),
        "full": str(full),
        "python": sys.executable,
    }


def _activate(binding: dict[str, str]) -> None:
    _write_json(
        Path(binding["root"]) / "current.json",
        {"generation": binding["name"], "manifest_sha256": binding["sha"]},
    )


def _bind(monkeypatch: pytest.MonkeyPatch, binding: dict[str, str]) -> None:
    values = {
        "KB_RAG_GENERATION": binding["sha"],
        "RAG_GENERATION_MANIFEST": binding["manifest"],
        "RAG_GENERATIONS_ROOT": binding["root"],
        "KB_RAG_CODE_ROOT": binding["code"],
        "KB_RAG_PYTHON": binding["python"],
        "KB_VAULT": binding["wiki"],
        "RAG_INDEX_DIR": binding["standard"],
        "KB_RAG_FULL_INDEX_DIR": binding["full"],
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def _remove_managed_artifact(binding: dict[str, str], missing: str, tmp_path: Path) -> None:
    if missing != "python":
        shutil.rmtree(binding[missing])
        return
    missing_python = tmp_path / "missing-venv" / "bin" / "python"
    binding["python"] = str(missing_python)
    manifest_path = Path(binding["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime"]["executable"] = str(missing_python)
    _write_json(manifest_path, manifest)
    binding["sha"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    _write_json(
        Path(binding["root"]) / "current.json",
        {"generation": binding["name"], "manifest_sha256": binding["sha"]},
    )


def _replace_managed_interpreter_with_symlink_loop(
    binding: dict[str, str], tmp_path: Path
) -> None:
    interpreter = tmp_path / "looped-venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.symlink_to(interpreter)
    binding["python"] = str(interpreter)
    manifest_path = Path(binding["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime"]["executable"] = str(interpreter)
    _write_json(manifest_path, manifest)
    binding["sha"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    _write_json(
        Path(binding["root"]) / "current.json",
        {"generation": binding["name"], "manifest_sha256": binding["sha"]},
    )


@pytest.fixture(autouse=True)
def _clean_workers():
    rag_worker.close_all()
    yield
    rag_worker.close_all()


def test_status_rejects_retired_generation_before_first_new_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alpha = _managed_generation(tmp_path, "alpha")
    beta = _managed_generation(tmp_path, "beta")
    _activate(alpha)
    _bind(monkeypatch, alpha)
    worker = PersistentRagWorker(
        alpha["python"], Path(alpha["code"]), Path(alpha["standard"]), Path(alpha["wiki"])
    )
    try:
        worker.prewarm(["query", "warmup", "--json"], timeout=3)
        assert worker.status()["state"] == "ready"
        process = worker._process

        _activate(beta)
        payload = worker.status()

        assert payload["state"] == "failed"
        assert payload["active"] is False
        assert payload["generation_status"] == "retired"
        assert payload["generation_reason"] == "current_generation_changed"
        assert process is not None and process.poll() is None, "status 必须是纯读"
        with pytest.raises(rag_worker.RagGenerationUnavailable):
            worker.query(["query", "after-switch", "--json"], timeout=3)
        assert process.poll() is not None
    finally:
        worker.close()


def test_status_is_pure_read_and_does_not_spawn_kill_or_recover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alpha = _managed_generation(tmp_path, "alpha")
    beta = _managed_generation(tmp_path, "beta")
    _activate(alpha)
    _bind(monkeypatch, alpha)
    worker = PersistentRagWorker(
        alpha["python"], Path(alpha["code"]), Path(alpha["standard"]), Path(alpha["wiki"])
    )
    worker._state = "ready"
    _activate(beta)

    with (
        mock.patch.object(rag_worker.subprocess, "Popen") as spawn,
        mock.patch.object(rag_worker.subprocess, "run") as subprocess_run,
        mock.patch.object(worker, "_stop_process") as stop,
        mock.patch.object(worker, "_schedule_recovery") as recover,
    ):
        payload = worker.status()

    assert payload["state"] == "failed"
    spawn.assert_not_called()
    subprocess_run.assert_not_called()
    stop.assert_not_called()
    recover.assert_not_called()


def test_managed_launch_uses_frozen_environment_despite_ambient_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alpha = _managed_generation(tmp_path, "alpha")
    beta = _managed_generation(tmp_path, "beta")
    _activate(alpha)
    _bind(monkeypatch, alpha)
    worker = PersistentRagWorker(
        alpha["python"], Path(alpha["code"]), Path(alpha["standard"]), Path(alpha["wiki"])
    )
    assert worker.python == alpha["python"], "venv 入口本身是解释器身份的一部分"
    _bind(monkeypatch, beta)

    payload = worker.status()
    assert payload["state"] == "cold"
    assert payload["generation_status"] == "current"
    with mock.patch.object(rag_worker.subprocess, "Popen") as spawn:
        process = mock.Mock()
        process.poll.return_value = 0
        spawn.return_value = process
        worker._ensure_process()
    launched = spawn.call_args.kwargs["env"]
    assert launched["KB_RAG_GENERATION"] == alpha["sha"]
    assert launched["RAG_GENERATION_MANIFEST"] == alpha["manifest"]
    assert launched["RAG_GENERATIONS_ROOT"] == alpha["root"]


def test_pool_partitions_managed_bindings_and_old_registration_keeps_aggregate_red(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    alpha = _managed_generation(tmp_path, "alpha")
    beta = _managed_generation(tmp_path, "beta")
    _activate(alpha)
    _bind(monkeypatch, alpha)
    old = rag_worker._worker_for(
        alpha["python"], Path(alpha["code"]), Path(alpha["standard"]), Path(alpha["wiki"])
    )
    old.prewarm(["query", "alpha", "--json"], timeout=3)

    _activate(beta)
    _bind(monkeypatch, beta)
    new = rag_worker._worker_for(
        beta["python"], Path(beta["code"]), Path(beta["standard"]), Path(beta["wiki"])
    )
    assert new is not old
    new.prewarm(["query", "beta", "--json"], timeout=3)
    aggregate = rag_worker.status()
    assert aggregate["state"] == "failed"
    assert aggregate["active"] == 1
    assert aggregate["configured_workers"] == 2

    rag_worker.close_all()
    new = rag_worker._worker_for(
        beta["python"], Path(beta["code"]), Path(beta["standard"]), Path(beta["wiki"])
    )
    new.prewarm(["query", "beta", "--json"], timeout=3)
    assert rag_worker.status()["state"] == "ready"


def test_independent_generation_roots_can_remain_ready_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    alpha = _managed_generation(tmp_path / "root-a", "alpha")
    beta = _managed_generation(tmp_path / "root-b", "beta")
    _activate(alpha)
    _activate(beta)
    _bind(monkeypatch, alpha)
    first = rag_worker._worker_for(
        alpha["python"], Path(alpha["code"]), Path(alpha["standard"]), Path(alpha["wiki"])
    )
    first.prewarm(["query", "alpha", "--json"], timeout=3)
    _bind(monkeypatch, beta)
    second = rag_worker._worker_for(
        beta["python"], Path(beta["code"]), Path(beta["standard"]), Path(beta["wiki"])
    )
    second.prewarm(["query", "beta", "--json"], timeout=3)

    payload = rag_worker.status()
    assert payload["state"] == "ready"
    assert payload["active"] == 2
    assert payload["configured_workers"] == 2


def test_managed_standard_and_full_retire_together_then_rollback_uses_new_instances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    alpha = _managed_generation(tmp_path, "alpha")
    beta = _managed_generation(tmp_path, "beta")
    _activate(alpha)
    _bind(monkeypatch, alpha)
    old = [
        rag_worker._worker_for(
            alpha["python"], Path(alpha["code"]), Path(alpha[kind]), Path(alpha["wiki"])
        )
        for kind in ("standard", "full")
    ]
    for worker in old:
        worker.prewarm(["query", "alpha", "--json"], timeout=3)
    assert rag_worker.status()["state"] == "ready"

    _activate(beta)
    assert rag_worker.status()["state"] == "failed"
    assert all(worker.status()["generation_status"] == "retired" for worker in old)

    rag_worker.close_all()
    _activate(alpha)
    _bind(monkeypatch, alpha)
    rolled_back = rag_worker._worker_for(
        alpha["python"], Path(alpha["code"]), Path(alpha["standard"]), Path(alpha["wiki"])
    )
    assert rolled_back not in old
    rolled_back.prewarm(["query", "rollback", "--json"], timeout=3)
    assert rag_worker.status()["state"] == "ready"


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("delete-manifest", "manifest_missing"),
        ("damage-manifest", "manifest_changed"),
        ("replace-root", "generation_root_replaced"),
    ],
)
def test_status_explains_managed_identity_damage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    reason: str,
) -> None:
    alpha = _managed_generation(tmp_path, "alpha")
    _activate(alpha)
    _bind(monkeypatch, alpha)
    worker = PersistentRagWorker(
        alpha["python"], Path(alpha["code"]), Path(alpha["standard"]), Path(alpha["wiki"])
    )
    if mutation == "delete-manifest":
        Path(alpha["manifest"]).unlink()
    elif mutation == "damage-manifest":
        Path(alpha["manifest"]).write_text("{}\n", encoding="utf-8")
    else:
        root = Path(alpha["root"])
        moved = root.with_name("old-root")
        root.rename(moved)
        root.mkdir()

    payload = worker.status()
    assert payload["state"] == "failed"
    assert payload["generation_reason"] == reason


def test_legacy_accepts_ordinary_rag_configuration_but_rejects_managed_marker_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    code = tmp_path / "legacy-code"
    index = tmp_path / "legacy-index"
    wiki = tmp_path / "legacy-wiki"
    _write_fake_rag(code)
    index.mkdir()
    wiki.mkdir()
    monkeypatch.setenv("KB_RAG_TIMEOUT", "30")
    monkeypatch.setenv("KB_RAG_CODE_ROOT", str(code))
    monkeypatch.setenv("RAG_INDEX_DIR", str(index))
    worker = PersistentRagWorker(sys.executable, code, index, wiki)
    assert worker.status()["generation_status"] == "legacy"

    managed = _managed_generation(tmp_path / "managed", "alpha")
    alias = tmp_path / "managed-alias"
    alias.symlink_to(Path(managed["standard"]), target_is_directory=True)
    with pytest.raises(rag_worker.RagGenerationUnavailable, match="managed index"):
        PersistentRagWorker(sys.executable, code, alias, wiki)


def test_partial_managed_binding_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    code = tmp_path / "code"
    index = tmp_path / "index"
    _write_fake_rag(code)
    index.mkdir()
    monkeypatch.setenv("KB_RAG_GENERATION", "a" * 64)
    with pytest.raises(rag_worker.RagGenerationUnavailable, match="incomplete"):
        PersistentRagWorker(sys.executable, code, index)


def test_managed_binding_distinguishes_venv_entries_with_same_python_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alpha = _managed_generation(tmp_path, "alpha")
    _activate(alpha)
    _bind(monkeypatch, alpha)
    alternate = tmp_path / "other-venv-python"
    alternate.symlink_to(Path(alpha["python"]).resolve())

    with pytest.raises(rag_worker.RagGenerationUnavailable, match="does not match"):
        PersistentRagWorker(
            str(alternate),
            Path(alpha["code"]),
            Path(alpha["standard"]),
            Path(alpha["wiki"]),
        )


def test_complete_managed_binding_rejects_index_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alpha = _managed_generation(tmp_path, "alpha")
    _activate(alpha)
    _bind(monkeypatch, alpha)
    alias = tmp_path / "standard-alias"
    alias.symlink_to(Path(alpha["standard"]), target_is_directory=True)

    with pytest.raises(rag_worker.RagGenerationUnavailable, match="symlink or alias"):
        PersistentRagWorker(
            alpha["python"], Path(alpha["code"]), alias, Path(alpha["wiki"])
        )


@pytest.mark.parametrize(
    ("missing", "reason"),
    [
        ("full", "index_directory_replaced"),
        ("code", "code_root_replaced"),
        ("wiki", "source_root_replaced"),
        ("python", "interpreter_replaced"),
    ],
)
def test_first_managed_capture_classifies_missing_bound_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing: str,
    reason: str,
) -> None:
    binding = _managed_generation(tmp_path, "alpha")
    _activate(binding)
    _remove_managed_artifact(binding, missing, tmp_path)
    _bind(monkeypatch, binding)

    with pytest.raises(rag_worker.RagGenerationUnavailable) as excinfo:
        PersistentRagWorker(
            binding["python"],
            Path(binding["code"]),
            Path(binding["standard"]),
            Path(binding["wiki"]),
        )

    assert excinfo.value.reason == reason


@pytest.mark.parametrize(
    ("missing", "reason"),
    [("full", "index_directory_replaced"), ("python", "interpreter_replaced")],
)
def test_first_managed_capture_failure_does_not_fallback_to_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing: str,
    reason: str,
) -> None:
    binding = _managed_generation(tmp_path, "alpha")
    _activate(binding)
    _remove_managed_artifact(binding, missing, tmp_path)
    _bind(monkeypatch, binding)
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    cli_response = WorkerResponse(0, "[]", "")

    with mock.patch.object(kb_rag.subprocess, "run", return_value=cli_response) as cli:
        result = kb_rag.retrieve(
            "identity-bound query",
            Path(binding["wiki"]),
            index_dir=Path(binding["standard"]),
            code_root=Path(binding["code"]),
            python_executable=binding["python"],
            worker_enabled=True,
        )

    cli.assert_not_called()
    assert result.telemetry.fallback_reason == "persistent_worker_generation_unavailable"
    assert result.telemetry.status == "error"
    assert reason in (result.warning or "")
    assert rag_worker.status()["configured_workers"] == 0


def test_looped_managed_interpreter_does_not_fallback_to_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _managed_generation(tmp_path, "alpha")
    _activate(binding)
    _replace_managed_interpreter_with_symlink_loop(binding, tmp_path)
    _bind(monkeypatch, binding)
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    cli_response = WorkerResponse(0, "[]", "")

    with mock.patch.object(kb_rag.subprocess, "run", return_value=cli_response) as cli:
        result = kb_rag.retrieve(
            "identity-bound query",
            Path(binding["wiki"]),
            index_dir=Path(binding["standard"]),
            code_root=Path(binding["code"]),
            python_executable=binding["python"],
            worker_enabled=True,
        )

    cli.assert_not_called()
    assert result.telemetry.fallback_reason == "persistent_worker_generation_unavailable"
    assert result.telemetry.status == "error"
    assert "interpreter_replaced" in (result.warning or "")
    assert rag_worker.status()["configured_workers"] == 0


@pytest.mark.parametrize("field", ["sources", "indexes", "runtime", "path_identities"])
def test_first_managed_capture_classifies_malformed_manifest_shapes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    binding = _managed_generation(tmp_path, "alpha")
    _activate(binding)
    manifest_path = Path(binding["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[field] = []
    _write_json(manifest_path, manifest)
    binding["sha"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    _write_json(
        Path(binding["root"]) / "current.json",
        {"generation": binding["name"], "manifest_sha256": binding["sha"]},
    )
    _bind(monkeypatch, binding)

    with pytest.raises(rag_worker.RagGenerationUnavailable) as excinfo:
        PersistentRagWorker(
            binding["python"],
            Path(binding["code"]),
            Path(binding["standard"]),
            Path(binding["wiki"]),
        )

    assert excinfo.value.reason == "managed_binding_mismatch"


def test_first_managed_capture_translates_residual_permission_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _managed_generation(tmp_path, "alpha")
    _activate(binding)
    _bind(monkeypatch, binding)

    with mock.patch.object(
        rag_generation_identity,
        "_has_symlink_component",
        side_effect=PermissionError("fixture denied"),
    ):
        with pytest.raises(rag_worker.RagGenerationUnavailable) as excinfo:
            PersistentRagWorker(
                binding["python"],
                Path(binding["code"]),
                Path(binding["standard"]),
                Path(binding["wiki"]),
            )

    assert excinfo.value.reason == "managed_identity_io_error"


def test_legacy_capture_does_not_reclassify_permission_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in rag_generation_identity.MANAGED_CORE_KEYS:
        monkeypatch.delenv(key, raising=False)
    code = tmp_path / "code"
    index = tmp_path / "index"
    _write_fake_rag(code)
    index.mkdir()

    with mock.patch.object(
        rag_generation_identity,
        "_managed_marker",
        side_effect=PermissionError("legacy fixture denied"),
    ):
        with pytest.raises(PermissionError, match="legacy fixture denied"):
            PersistentRagWorker(sys.executable, code, index)


def test_retired_generation_does_not_fallback_to_legacy_cli(
    tmp_path: Path,
) -> None:
    wiki = tmp_path / "wiki"
    page = wiki / "concepts" / "liquid.md"
    page.parent.mkdir(parents=True)
    page.write_text("# liquid\n", encoding="utf-8")
    script = tmp_path / kb_rag.RAG_SCRIPT_REL
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# fixture\n", encoding="utf-8")
    (tmp_path / ".rag_index").mkdir()
    with (
        mock.patch.dict(
            os.environ,
            {"RAG_WORKER_ENABLED": "1", "KB_RAG_PYTHON": sys.executable},
            clear=False,
        ),
        mock.patch.object(
            kb_rag.rag_worker,
            "query",
            side_effect=rag_worker.RagGenerationUnavailable(
                "worker generation retired", reason="current_generation_changed"
            ),
        ),
        mock.patch.object(kb_rag.subprocess, "run") as cli,
    ):
        result = kb_rag.retrieve("liquid", wiki)

    cli.assert_not_called()
    assert result.telemetry.status == "error"
    assert result.telemetry.fallback_reason == "persistent_worker_generation_unavailable"


def test_normal_protocol_failure_still_falls_back_to_cli(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    page = wiki / "concepts" / "liquid.md"
    page.parent.mkdir(parents=True)
    page.write_text("# liquid\n", encoding="utf-8")
    script = tmp_path / kb_rag.RAG_SCRIPT_REL
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# fixture\n", encoding="utf-8")
    (tmp_path / ".rag_index").mkdir()
    cli_response = WorkerResponse(0, "[]", "")
    with (
        mock.patch.dict(
            os.environ,
            {"RAG_WORKER_ENABLED": "1", "KB_RAG_PYTHON": sys.executable},
            clear=False,
        ),
        mock.patch.object(
            kb_rag.rag_worker,
            "query",
            side_effect=json.JSONDecodeError("bad protocol", "x", 0),
        ),
        mock.patch.object(kb_rag.subprocess, "run", return_value=cli_response) as cli,
    ):
        result = kb_rag.retrieve("liquid", wiki)

    cli.assert_called_once()
    assert result.telemetry.fallback_reason == "persistent_worker_unavailable"


def test_single_bad_query_does_not_reclassify_worker_as_retired(tmp_path: Path) -> None:
    code = tmp_path / "code"
    index = tmp_path / "index"
    _write_fake_rag(code)
    index.mkdir()
    worker = PersistentRagWorker(sys.executable, code, index)
    try:
        worker.prewarm(["query", "warmup", "--json"], timeout=3)
        process = worker._process
        response = worker.query(["invalid"], timeout=3)

        assert response.returncode != 0
        assert worker.status()["state"] == "ready"
        assert worker.status()["generation_status"] == "legacy"
        assert process is not None and process.poll() is None
    finally:
        worker.close()
