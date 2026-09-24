"""显式跨仓验收：KB_RECEIPT_CODE_ROOT 指向待验知识库代码；只写临时 hash 索引。

不设环境变量则不声称跨仓通过；设了但代码过旧/路径错误，真实入口直接失败。
不使用线上索引、embedding 模型或网络。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from intelligence.services import kb_rag, rag_worker


@pytest.fixture
def real_kb(tmp_path, monkeypatch):
    configured = os.environ.get("KB_RECEIPT_CODE_ROOT")
    if not configured:
        pytest.skip("跨仓验收需显式 KB_RECEIPT_CODE_ROOT；未验证生产兼容性")
    code = Path(configured).resolve()
    assert (code / "scripts/rag_index.py").is_file()
    wiki = tmp_path / "wiki"
    sources = wiki / "sources"
    sources.mkdir(parents=True)
    for name, layer, review, available in [
        ("official", "L3", "false", "2026-08-02"),
        ("research", "L1", "false", "2026-08-02"),
        ("pending", "L3", "true", "2026-08-02"),
        ("future", "L3", "false", "2026-09-03"),
    ]:
        (sources / f"{name}.md").write_text(
            f"---\nevidence_layer: {layer}\nfact_hardness: hard_fact\n"
            f"source_type: official_disclosure\nreview_required: {review}\n"
            f"publish_time: 2026-08-01\navailable_time: {available}\n---\n"
            f"# {name}\n\nalpha order {name} confirmed.\n", encoding="utf-8",
        )
    index = tmp_path / "index"
    for key, value in {
        "KB_VAULT": str(wiki), "RAG_INDEX_DIR": str(index), "RAG_MODEL": "hash",
        "KB_ACCESS_LOG_PATH": str(tmp_path / "access.jsonl"),
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "RAG_WORKER_KEEPALIVE_SECONDS": "0",
    }.items():
        monkeypatch.setenv(key, value)
    for key in ("VECTOR_INDEX_DIR", "RAG_MAX_FILES", "RAG_INCLUDE_RAW"):
        monkeypatch.delenv(key, raising=False)
    proc = subprocess.run(
        [sys.executable, str(code / "scripts/rag_index.py"), "build", "--model", "hash"],
        capture_output=True, text=True, timeout=30, cwd=code,
    )
    assert proc.returncode == 0, proc.stderr
    kb_rag.clear_result_cache()
    yield code, wiki, index
    rag_worker.close_all()
    kb_rag.clear_result_cache()


def _retrieve(real_kb, **kwargs):
    code, wiki, index = real_kb
    return kb_rag.retrieve(
        "alpha", wiki, mode="bm25", code_root=code, index_dir=index,
        python_executable=sys.executable, timeout=15, **kwargs,
    )


def test_real_cli_enforces_grade_review_and_available_time(real_kb):
    out = _retrieve(real_kb, worker_enabled=False, evidence_layer="L3", fact_hardness="hard_fact",
                    source_type="official_disclosure", as_of="2026-08-03")
    assert out.ok, out.warning
    assert [hit.page_id for hit in out.hits] == ["sources/official"]
    assert out.telemetry.filter_verification == "verified"
    assert out.telemetry.applied_filters["as_of"] == "2026-08-03"
    assert out.hits[0].deep_read_blocks == ()
    assert "research" not in out.hits[0].llm_evidence
    empty = _retrieve(real_kb, worker_enabled=False, evidence_layer="L3", as_of="2026-07-31")
    assert not empty.ok and empty.telemetry.status == "empty"
    assert empty.telemetry.filter_verification == "verified"


def test_real_worker_and_cli_preserve_context_then_recheck_source_conflict(real_kb):
    cli = _retrieve(real_kb, worker_enabled=False, cache_scope="session")
    worker = _retrieve(real_kb, worker_enabled=True, cache_scope="session")
    assert cli.ok and worker.ok, (cli.warning, worker.warning)
    assert worker.telemetry.receipt_received
    assert worker.telemetry.query_protocol == "persistent_worker"
    assert [(h.page_id, h.llm_evidence, h.evidence_chunk_ids, h.index_source_revision) for h in cli.hits] == [
        (h.page_id, h.llm_evidence, h.evidence_chunk_ids, h.index_source_revision) for h in worker.hits
    ]
    _, wiki, _ = real_kb
    page = wiki / "sources/official.md"
    page.write_text(page.read_text() + "\n||||||| unresolved-base\nalpha conflict\n")
    warm = _retrieve(real_kb, worker_enabled=True, cache_scope="session")
    assert "sources/official" not in [h.page_id for h in warm.hits]
    assert not warm.telemetry.cache_hit
    assert warm.telemetry.receipt_received


def test_deployed_code_root_binds_worker_and_cli_to_argument_wiki(real_kb, monkeypatch, tmp_path):
    code, wiki, index = real_kb
    monkeypatch.setenv("KB_RAG_CODE_ROOT", str(code))
    monkeypatch.setenv("KB_RAG_PYTHON", sys.executable)
    monkeypatch.setenv("RAG_WORKER_ENABLED", "1")
    # This ambient root deliberately has no evidence. Explicit data must win,
    # including prewarm, which used to silently read the code checkout's wiki.
    wrong = tmp_path / "wrong-wiki"
    wrong.mkdir()
    monkeypatch.setenv("KB_VAULT", str(wrong))
    assert kb_rag.probe_rag_cli(wiki).query_protocol_compatible
    kb_rag.prewarm(wiki, timeout=30)
    out = kb_rag.retrieve("alpha", wiki, index_dir=index, mode="bm25", timeout=20)
    assert out.ok, out.warning
    assert out.telemetry.query_protocol == "persistent_worker"
    assert out.telemetry.receipt_received
    assert "sources/official" in [hit.page_id for hit in out.hits]
    filtered = kb_rag.retrieve("alpha", wiki, index_dir=index, mode="bm25", timeout=20,
                               evidence_layer="L3", as_of="2026-08-03")
    assert filtered.ok, filtered.warning
    assert [hit.page_id for hit in filtered.hits] == ["sources/official"]
    page = wiki / "sources/official.md"
    page.write_text(page.read_text() + "\n||||||| unresolved live source\n")
    warm = kb_rag.retrieve("alpha", wiki, index_dir=index, mode="bm25", timeout=20)
    assert "sources/official" not in [hit.page_id for hit in warm.hits]
    assert warm.telemetry.receipt_received


def test_real_old_metadata_empty_receipt_remains_visible(real_kb):
    _, _, index = real_kb
    path = index / "meta.json"
    meta = json.loads(path.read_text())
    meta.pop("evidence_metadata_version")
    path.write_text(json.dumps(meta))
    out = _retrieve(real_kb, worker_enabled=False, evidence_layer="absent-layer")
    assert out.telemetry.metadata_update_required is True
    assert out.telemetry.status == "empty"
    assert "不代表" in out.warning
