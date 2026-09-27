from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from unittest import mock

import pytest

from intelligence.services import kb_rag, rag_generation_identity, rag_worker
from intelligence.tests.test_rag_worker_generation import (
    _activate,
    _bind,
    _managed_generation,
)


@pytest.fixture
def split_knowledge_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    rag_worker.close_all()
    kb_rag.clear_result_cache()
    binding = _managed_generation(tmp_path, "workbench")
    _activate(binding)
    _bind(monkeypatch, binding)
    full_wiki = tmp_path / "complete-kb" / "wiki"
    (full_wiki / "relations").mkdir(parents=True)
    for wiki, marker in ((full_wiki, "COMPLETE_ROOT"), (Path(binding["wiki"]), "FROZEN_SOURCE")):
        page = wiki / "concepts" / "liquid.md"
        page.parent.mkdir()
        page.write_text(f"# liquid\n\n## Orders\n\nliquid {marker} orders confirmed.\n")
    script = Path(binding["code"]) / kb_rag.RAG_SCRIPT_REL
    script.write_text('''
import hashlib
import json
import os
import sys
from pathlib import Path

def _load_retriever(model, need_dense, reranker_name=None, store=None, index_freshness=None):
    return object()

def main(argv=None):
    argv = list(argv or [])
    if "--help" in argv:
        print("--json --k --mode --evidence-chars --evidence-layer --fact-hardness --source-type --as-of --receipt")
        return 0
    _load_retriever("hash", False, index_freshness="fresh")
    text = (Path(os.environ["KB_VAULT"]) / "concepts/liquid.md").read_text()
    filters = {key: argv[argv.index(option) + 1] for option, key in (
        ("--evidence-layer", "evidence_layer"), ("--fact-hardness", "fact_hardness"),
        ("--source-type", "source_type"), ("--as-of", "as_of"),
    ) if option in argv}
    hit = {
        "page_id": "liquid", "file_path": "wiki/concepts/liquid.md", "title": "liquid",
        "score": 1.0, "best_chunk_id": "wiki/concepts/liquid.md::0", "section": "Orders",
        "content_hash": hashlib.sha1(text.encode()).hexdigest(), "llm_evidence_text": text,
        "display_excerpt": text,
        "index_source_revision": os.environ.get("KB_RAG_GENERATION", "legacy"),
        "index_freshness": "fresh", "evidence_layer": "L2", "fact_hardness": "baseline",
        "source_type": "annual_report", "available_time": "2026-09-01",
        "content_validity": "valid", "applied_filters": filters,
    }
    if not filters:
        print(json.dumps([hit]))
        return 0
    print(json.dumps({"hits": [hit], "status": "success", "applied_filters": filters,
        "filter_policy": "explicit_chunk_metadata; unknown_excluded; as_of=available_time",
        "metadata_version": 1, "metadata_update_required": False}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
''')
    monkeypatch.setenv("WORKBENCH_KNOWLEDGE_WIKI", str(full_wiki))
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    monkeypatch.delenv("VECTOR_INDEX_DIR", raising=False)
    yield full_wiki, binding
    rag_worker.close_all()
    kb_rag.clear_result_cache()


def test_prewarm_from_complete_root_uses_managed_snapshot(split_knowledge_roots):
    full_wiki, binding = split_knowledge_roots

    status = kb_rag.prewarm(full_wiki, timeout=3)

    assert status["state"] == "ready"
    assert status["configured_workers"] == 1
    assert status["active"] == 1
    assert not (Path(binding["wiki"]) / "relations").exists()


@pytest.mark.parametrize("full_index", [False, True])
def test_retrieve_uses_frozen_source_for_hits_deep_read_and_cache(
    split_knowledge_roots, full_index
):
    full_wiki, binding = split_knowledge_roots
    kwargs = {
        "mode": "bm25", "timeout": 3, "cache_scope": "same-request",
        "index_dir": kb_rag.FULL_INDEX_DIRNAME if full_index else None,
    }

    result = kb_rag.retrieve("liquid", full_wiki, **kwargs)

    assert result.ok, result.warning
    assert result.index_dir == binding["full" if full_index else "standard"]
    hit = result.hits[0]
    frozen_page = Path(binding["wiki"]) / "concepts/liquid.md"
    assert hit.content_hash == hashlib.sha1(frozen_page.read_bytes()).hexdigest()
    assert hit.index_source_revision == binding["sha"]
    assert "FROZEN_SOURCE" in " ".join(hit.deep_read_paragraphs)
    assert "COMPLETE_ROOT" not in repr(hit)
    cached = kb_rag.retrieve("liquid", Path(binding["wiki"]), **kwargs)
    assert cached.telemetry.cache_hit is True
    assert cached.hits == result.hits


@pytest.mark.parametrize("full_index", [False, True])
def test_filtered_cli_receipt_uses_frozen_source(split_knowledge_roots, full_index):
    full_wiki, binding = split_knowledge_roots

    result = kb_rag.retrieve(
        "liquid", full_wiki, mode="bm25", timeout=3,
        index_dir=kb_rag.FULL_INDEX_DIRNAME if full_index else None,
        evidence_layer="L2", fact_hardness="baseline", source_type="annual_report",
        as_of="2026-09-27",
    )

    assert result.ok, result.warning
    assert result.telemetry.filter_verification == "verified"
    assert result.index_dir == binding["full" if full_index else "standard"]
    assert "FROZEN_SOURCE" in result.hits[0].llm_evidence
    assert "COMPLETE_ROOT" not in repr(result.hits[0])


@pytest.mark.parametrize("filtered", [False, True])
def test_other_explicit_wiki_is_not_replaced_by_managed_snapshot(
    split_knowledge_roots, tmp_path, filtered
):
    _, _binding = split_knowledge_roots
    other_wiki = tmp_path / "other-kb" / "wiki"
    other_wiki.mkdir(parents=True)
    kwargs = {"evidence_layer": "L2"} if filtered else {}

    with mock.patch.object(
        kb_rag.subprocess, "run", return_value=rag_worker.WorkerResponse(0, "[]", "")
    ) as cli:
        result = kb_rag.retrieve("liquid", other_wiki, mode="bm25", **kwargs)

    assert result.ok is False
    assert "managed_binding_mismatch" in result.warning
    cli.assert_not_called()
    with pytest.raises(rag_worker.RagGenerationUnavailable, match="does not match"):
        kb_rag.prewarm(other_wiki, timeout=3)
    probe = kb_rag.probe_rag_cli(other_wiki)
    assert probe.query_protocol_compatible is False
    assert probe.failure_kind == "generation_unavailable"


@pytest.mark.parametrize("missing", [*rag_generation_identity.MANAGED_BINDING_KEYS, "all_core"])
def test_incomplete_binding_is_rejected_before_cached_results_or_cli(
    split_knowledge_roots, monkeypatch, missing
):
    full_wiki, _binding = split_knowledge_roots
    assert kb_rag.retrieve("liquid", full_wiki, mode="bm25", cache_scope="test").ok
    keys = rag_generation_identity.MANAGED_CORE_KEYS if missing == "all_core" else [missing]
    for key in keys:
        monkeypatch.delenv(key)
    reason = "managed_index_without_binding" if missing == "all_core" else "managed_binding_incomplete"

    with mock.patch.object(kb_rag.subprocess, "run") as cli:
        result = kb_rag.retrieve("liquid", full_wiki, mode="bm25", cache_scope="test")
        filtered = kb_rag.retrieve("liquid", full_wiki, mode="bm25", evidence_layer="L2")

    for response in (result, filtered):
        assert response.ok is False
        assert response.telemetry.cache_hit is False
        assert reason in response.warning
    cli.assert_not_called()
    with pytest.raises(rag_worker.RagGenerationUnavailable) as exc:
        kb_rag.prewarm(full_wiki, timeout=3)
    assert exc.value.reason == reason
    assert kb_rag.probe_rag_cli(full_wiki).failure_kind == "generation_unavailable"


def test_retired_binding_cannot_return_cached_hits(split_knowledge_roots, tmp_path):
    full_wiki, _binding = split_knowledge_roots
    assert kb_rag.retrieve("liquid", full_wiki, mode="bm25", cache_scope="test").ok
    _activate(_managed_generation(tmp_path, "replacement"))

    result = kb_rag.retrieve("liquid", full_wiki, mode="bm25", cache_scope="test")

    assert result.ok is False
    assert result.telemetry.cache_hit is False
    assert "current_generation_changed" in result.warning


@pytest.mark.parametrize("override", ["code_root", "python_executable", "index_dir"])
def test_explicit_executor_override_must_match_the_managed_binding(
    split_knowledge_roots, tmp_path, override
):
    full_wiki, binding = split_knowledge_roots
    other = tmp_path / "other-runtime"
    if override == "code_root":
        shutil.copytree(binding["code"], other)
    elif override == "index_dir":
        other.mkdir()

    with mock.patch.object(
        kb_rag.subprocess, "run", return_value=rag_worker.WorkerResponse(0, "[]", "")
    ) as cli:
        result = kb_rag.retrieve(
            "liquid", full_wiki, mode="bm25", evidence_layer="L2", **{override: other}
        )

    assert result.ok is False
    assert "managed_binding_mismatch" in result.warning
    cli.assert_not_called()


@pytest.mark.parametrize("configured", [False, True])
def test_legacy_retrieval_keeps_the_callers_wiki(split_knowledge_roots, monkeypatch, tmp_path, configured):
    full_wiki, binding = split_knowledge_roots
    script = full_wiki.parent / kb_rag.RAG_SCRIPT_REL
    script.parent.mkdir()
    shutil.copyfile(Path(binding["code"]) / kb_rag.RAG_SCRIPT_REL, script)
    (full_wiki.parent / ".rag_index").mkdir()
    ambient_wiki = tmp_path / "legacy-ambient" / "wiki"
    ambient_wiki.mkdir(parents=True)
    for key in rag_generation_identity.MANAGED_BINDING_KEYS:
        monkeypatch.delenv(key)
    monkeypatch.setenv("KB_VAULT", str(ambient_wiki))
    if not configured:
        monkeypatch.delenv("WORKBENCH_KNOWLEDGE_WIKI")

    assert kb_rag.prewarm(full_wiki, timeout=3)["state"] == "ready"
    result = kb_rag.retrieve("liquid", full_wiki, mode="bm25", timeout=3)

    assert result.ok, result.warning
    assert "COMPLETE_ROOT" in result.hits[0].llm_evidence
    assert result.hits[0].index_source_revision == "legacy"
    assert kb_rag.probe_rag_cli(full_wiki).query_protocol_compatible is True


def test_without_explicit_complete_root_managed_caller_still_must_match(
    split_knowledge_roots, monkeypatch
):
    full_wiki, binding = split_knowledge_roots
    monkeypatch.delenv("WORKBENCH_KNOWLEDGE_WIKI")

    wrong = kb_rag.retrieve("liquid", full_wiki, mode="bm25", timeout=3)
    correct = kb_rag.retrieve("liquid", Path(binding["wiki"]), mode="bm25", timeout=3)

    assert wrong.ok is False
    assert "managed_binding_mismatch" in wrong.warning
    assert correct.ok is True


def test_api_dependencies_use_complete_knowledge_root(
    split_knowledge_roots, monkeypatch, tmp_path
):
    from fastapi.testclient import TestClient

    from intelligence.api.app import create_app

    full_wiki, binding = split_knowledge_roots
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "finance-data"))
    client = TestClient(create_app(repo_root=tmp_path))

    payload = client.get("/api/health").json()

    assert payload["dependencies"]["knowledge_wiki"] is True
    assert payload["dependencies"]["relations"] is True
    assert payload["dependencies"]["vector_index"] is True
    assert (full_wiki / "relations").is_dir()
    assert not (Path(binding["wiki"]) / "relations").exists()
