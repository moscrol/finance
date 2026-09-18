"""Deployment must bind KB code, source and index independently on every path."""
from unittest import mock
import sys

import pytest

from intelligence.services import kb_rag, rag_worker


@pytest.fixture
def roots(tmp_path, monkeypatch):
    code = tmp_path / "code"
    data = tmp_path / "data"
    wiki = data / "wiki"
    wiki.mkdir(parents=True)
    script = code / "scripts/rag_index.py"
    script.parent.mkdir(parents=True)
    script.write_text("# frozen code\n")
    index = data / ".rag_index"
    index.mkdir()
    monkeypatch.setenv("KB_RAG_CODE_ROOT", str(code))
    monkeypatch.setenv("KB_RAG_PYTHON", sys.executable)
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    monkeypatch.setenv("KB_VAULT", str(tmp_path / "wrong-wiki"))
    for name in ("RAG_INDEX_DIR", "VECTOR_INDEX_DIR"):
        monkeypatch.delenv(name, raising=False)
    yield code, wiki, index
    rag_worker.close_all()


def test_prewarm_probe_and_cli_use_frozen_code_not_data_tree(roots):
    code, wiki, index = roots
    with mock.patch.object(rag_worker, "prewarm") as warm:
        kb_rag.prewarm(wiki)
    assert warm.call_args.kwargs["kb_root"] == code
    assert warm.call_args.kwargs["kb_wiki"] == wiki
    assert warm.call_args.kwargs["index_dir"] == index
    with mock.patch.object(kb_rag.subprocess, "run", return_value=mock.Mock(
        returncode=0, stdout="[]", stderr="",
    )) as run:
        kb_rag.probe_rag_cli(wiki)
        assert run.call_args.args[0][1] == str(code / "scripts/rag_index.py")
        kb_rag.retrieve("alpha", wiki, worker_enabled=False, mode="bm25")
        assert run.call_args.args[0][1] == str(code / "scripts/rag_index.py")
        assert run.call_args.kwargs["cwd"] == str(code)
        assert run.call_args.kwargs["env"]["KB_VAULT"] == str(wiki)
        assert run.call_args.kwargs["env"]["RAG_INDEX_DIR"] == str(index)


def test_invalid_configured_root_does_not_fall_back_to_old_data_code(roots, monkeypatch):
    code, wiki, _ = roots
    old = wiki.parent / "scripts/rag_index.py"
    old.parent.mkdir()
    old.write_text("# old but present\n")
    monkeypatch.setenv("KB_RAG_CODE_ROOT", str(code / "missing"))
    with mock.patch.object(kb_rag.subprocess, "run") as run:
        assert not kb_rag.probe_rag_cli(wiki).available
        result = kb_rag.retrieve("alpha", wiki)
        assert not result.ok and result.telemetry.status == "skipped"
        with pytest.raises(FileNotFoundError):
            kb_rag.prewarm(wiki)
    run.assert_not_called()
    assert kb_rag._resolve_code_root(wiki.parent, code) == code


def test_worker_data_binding_overrides_environment_and_partitions_pool(roots):
    code, wiki, index = roots
    worker = rag_worker._worker_for(sys.executable, code, index, wiki)
    other = rag_worker._worker_for(sys.executable, code, index, wiki.parent / "other")
    assert other is not worker
    assert rag_worker._worker_for(sys.executable, code, index, wiki) is worker
    with mock.patch.object(rag_worker.subprocess, "Popen") as popen:
        popen.return_value.poll.return_value = 0
        worker._ensure_process()
        assert popen.call_args.kwargs["env"]["KB_VAULT"] == str(wiki)
        assert popen.call_args.args[0][-3] == str(code)
