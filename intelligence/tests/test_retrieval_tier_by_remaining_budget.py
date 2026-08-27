from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import mock

from intelligence.services import kb_rag
from intelligence.services.agent_research import _describe_retrieval_degradation


def test_four_seconds_selects_bm25() -> None:
    mode, reason = kb_rag.select_mode_for_remaining("hybrid", 4.0)
    assert mode == "bm25"
    assert reason == "remaining_budget"


def test_incident_grant_selects_bm25() -> None:
    mode, reason = kb_rag.select_mode_for_remaining("hybrid", 11.955)
    assert mode == "bm25"
    assert reason == "remaining_budget"


def test_twenty_seconds_keeps_hybrid() -> None:
    mode, reason = kb_rag.select_mode_for_remaining("hybrid", 20.0)
    assert mode == "hybrid"
    assert reason is None


def test_already_bm25_is_not_labeled_degraded() -> None:
    mode, reason = kb_rag.select_mode_for_remaining("bm25", 4.0)
    assert mode == "bm25"
    assert reason is None


def _fresh_hit() -> list[dict]:
    return [
        {
            "page_id": "a",
            "file_path": "wiki/concepts/光刻机.md",
            "title": "A",
            "score": 0.9,
            "best_chunk_id": "a::0",
            "content_hash": "hash-a",
            "evidence_text": "A matched chunk",
            "index_source_revision": "abc123",
            "index_freshness": "fresh",
        }
    ]


def _stub_wiki(td: str) -> Path:
    root = Path(td)
    page = root / "wiki" / "concepts" / "光刻机.md"
    script = root / kb_rag.RAG_SCRIPT_REL
    page.parent.mkdir(parents=True)
    script.parent.mkdir(parents=True)
    script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
    page.write_text("# 光刻机\n\n正文材料。\n", encoding="utf-8")
    (root / ".rag_index").mkdir()
    return root


def test_retrieve_four_seconds_never_invokes_hybrid() -> None:
    proc = mock.Mock(
        returncode=0,
        stdout=json.dumps(_fresh_hit(), ensure_ascii=False),
        stderr="",
    )
    with tempfile.TemporaryDirectory() as td:
        root = _stub_wiki(td)
        with mock.patch.dict("os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=True):
            with mock.patch("subprocess.run", return_value=proc) as run:
                res = kb_rag.retrieve(
                    "光刻机",
                    root / "wiki",
                    mode="hybrid",
                    timeout=4,
                )
    assert run.call_count == 1
    cmd = run.call_args.args[0]
    assert "--mode" in cmd
    assert cmd[cmd.index("--mode") + 1] == "bm25"
    assert "hybrid" not in cmd[cmd.index("--mode") + 1]
    assert res.ok
    assert res.hits
    assert res.telemetry.requested_mode == "hybrid"
    assert res.telemetry.effective_mode == "bm25"
    assert res.telemetry.fallback_reason == "remaining_budget"
    assert res.telemetry.degraded is True
    note = _describe_retrieval_degradation(res.telemetry)
    assert "remaining_budget" in note


def test_retrieve_twenty_seconds_keeps_hybrid_command() -> None:
    proc = mock.Mock(
        returncode=0,
        stdout=json.dumps(_fresh_hit(), ensure_ascii=False),
        stderr="",
    )
    with tempfile.TemporaryDirectory() as td:
        root = _stub_wiki(td)
        with mock.patch.dict("os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=True):
            with mock.patch("subprocess.run", return_value=proc) as run:
                res = kb_rag.retrieve(
                    "光刻机",
                    root / "wiki",
                    mode="hybrid",
                    timeout=20,
                )
    cmd = run.call_args.args[0]
    assert cmd[cmd.index("--mode") + 1] == "hybrid"
    assert res.telemetry.fallback_reason != "remaining_budget"
    assert res.telemetry.effective_mode == "hybrid"
