from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence.services import kb_rag


class KbRagRetrieveFilterTests(unittest.TestCase):
    def test_passes_layer_filters_and_parses_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wiki = root / "wiki"
            page = wiki / "concepts" / "光刻机.md"
            script = root / kb_rag.RAG_SCRIPT_REL
            index_dir = root / ".rag_index"
            page.parent.mkdir(parents=True)
            script.parent.mkdir(parents=True)
            index_dir.mkdir()
            script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
            page.write_text("# 光刻机\n\n正文材料。\n", encoding="utf-8")
            payload = [
                {
                    "page_id": "光刻机",
                    "file_path": "wiki/concepts/光刻机.md",
                    "title": "光刻机",
                    "score": 0.9,
                    "best_chunk_id": "wiki/concepts/光刻机.md::2",
                    "section": "供需",
                    "content_hash": "deadbeef",
                    "evidence_text": "命中的供需章节，而不是页面开头。",
                    "index_built_at": "2026-07-10T12:00:00+00:00",
                    "index_source_revision": "abc123",
                    "index_freshness": "fresh",
                    "evidence_layer": "L0_concept",
                    "fact_hardness": "structured_mapping",
                    "source_type": "concept_page",
                }
            ]
            proc = mock.Mock(returncode=0, stdout=json.dumps(payload, ensure_ascii=False), stderr="")

            with mock.patch.dict("os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=False):
                with mock.patch("subprocess.run", return_value=proc) as run:
                    res = kb_rag.retrieve(
                        "光刻机",
                        wiki,
                        k=3,
                        evidence_layer="L0_concept",
                        fact_hardness="structured_mapping",
                        source_type="concept_page",
                    )

            cmd = run.call_args.args[0]
            self.assertIn("--evidence-layer", cmd)
            self.assertIn("L0_concept", cmd)
            self.assertIn("--fact-hardness", cmd)
            self.assertIn("structured_mapping", cmd)
            self.assertIn("--source-type", cmd)
            self.assertIn("concept_page", cmd)
            self.assertTrue(res.ok)
            self.assertIn("filters=", res.command)
            self.assertEqual(res.hits[0].evidence_layer, "L0_concept")
            self.assertEqual(res.hits[0].fact_hardness, "structured_mapping")
            self.assertEqual(res.hits[0].source_type, "concept_page")
            self.assertEqual(res.hits[0].excerpt, "命中的供需章节，而不是页面开头。")
            self.assertEqual(res.hits[0].best_chunk_id, "wiki/concepts/光刻机.md::2")
            self.assertEqual(res.hits[0].section, "供需")
            self.assertEqual(res.telemetry.index_freshness, "fresh")


class KbRagTelemetryTests(unittest.TestCase):
    def _setup_repo(self, td: str) -> Path:
        root = Path(td)
        wiki = root / "wiki"
        page = wiki / "concepts" / "光刻机.md"
        script = root / kb_rag.RAG_SCRIPT_REL
        page.parent.mkdir(parents=True)
        script.parent.mkdir(parents=True)
        script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
        page.write_text("# 光刻机\n\n正文材料。\n", encoding="utf-8")
        return root

    def test_telemetry_populated_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            payload = [
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
                },
                {
                    "page_id": "b",
                    "file_path": "wiki/concepts/光刻机.md",
                    "title": "B",
                    "score": 0.5,
                    "best_chunk_id": "b::0",
                    "content_hash": "hash-b",
                    "evidence_text": "B matched chunk",
                    "index_source_revision": "abc123",
                    "index_freshness": "fresh",
                    "via_neighbor": True,
                },
            ]
            proc = mock.Mock(returncode=0, stdout=json.dumps(payload, ensure_ascii=False), stderr="")
            with mock.patch.dict("os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=True):
                with mock.patch("subprocess.run", return_value=proc):
                    res = kb_rag.retrieve("光刻机", root / "wiki", k=4, mode="hybrid")
            tel = res.telemetry
            self.assertEqual(tel.status, "ok")
            self.assertEqual(tel.mode, "hybrid")
            self.assertIn("BM25", tel.recall_desc)
            self.assertEqual(tel.index_kind, "structured")
            self.assertEqual(tel.k, 4)
            self.assertEqual(tel.hit_count, 2)
            self.assertEqual(tel.neighbor_hits, 1)
            self.assertAlmostEqual(tel.score_max, 0.9)
            self.assertAlmostEqual(tel.score_min, 0.5)
            self.assertAlmostEqual(tel.score_mean, 0.7)
            self.assertIsNotNone(tel.latency_ms)
            self.assertFalse(tel.degraded)
            self.assertIn("检索方式=hybrid", tel.summary_line())

    def test_zero_timeout_returns_without_spawning_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()

            with mock.patch("subprocess.run") as run:
                res = kb_rag.retrieve(
                    "光刻机",
                    root / "wiki",
                    mode="hybrid",
                    timeout=0.0,
                )

            run.assert_not_called()
            self.assertFalse(res.ok)
            self.assertEqual(res.telemetry.status, "timeout")
            self.assertEqual(res.telemetry.dense_initializations, 0)
            self.assertEqual(res.telemetry.timeout_seconds, 0.0)

    def test_hybrid_float_timeout_counts_one_dense_initialization(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            proc = mock.Mock(returncode=0, stdout="[]", stderr="")

            with mock.patch("subprocess.run", return_value=proc) as run:
                res = kb_rag.retrieve(
                    "光刻机",
                    root / "wiki",
                    mode="hybrid",
                    timeout=3.5,
                )

            self.assertEqual(run.call_args.kwargs["timeout"], 3.5)
            self.assertEqual(res.telemetry.dense_initializations, 1)
            self.assertEqual(res.telemetry.timeout_seconds, 3.5)

    def test_bm25_does_not_initialize_dense_model(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            proc = mock.Mock(returncode=0, stdout="[]", stderr="")

            with mock.patch("subprocess.run", return_value=proc):
                res = kb_rag.retrieve(
                    "光刻机",
                    root / "wiki",
                    mode="bm25",
                    timeout=3.5,
                )

            self.assertEqual(res.telemetry.dense_initializations, 0)

    def test_hybrid_dense_dependency_failure_falls_back_to_bm25(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            failed = mock.Mock(
                returncode=1,
                stdout="",
                stderr="ModuleNotFoundError: No module named 'FlagEmbedding'",
            )
            success = mock.Mock(
                returncode=0,
                stdout=json.dumps(self._freshness_payload("fresh"), ensure_ascii=False),
                stderr="",
            )

            with mock.patch("subprocess.run", side_effect=[failed, success]) as run:
                res = kb_rag.retrieve(
                    "光刻机",
                    root / "wiki",
                    mode="hybrid",
                    timeout=5,
                )

            self.assertTrue(res.ok)
            self.assertEqual(run.call_count, 2)
            self.assertIn("hybrid", run.call_args_list[0].args[0])
            self.assertIn("bm25", run.call_args_list[1].args[0])
            self.assertEqual(res.telemetry.requested_mode, "hybrid")
            self.assertEqual(res.telemetry.effective_mode, "bm25")
            self.assertEqual(res.telemetry.fallback_reason, "dense_dependency_missing")

    def test_hybrid_bm25_fallback_still_rejects_stale_hits(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            failed = mock.Mock(
                returncode=1,
                stdout="",
                stderr="ModuleNotFoundError: No module named 'FlagEmbedding'",
            )
            stale = mock.Mock(
                returncode=0,
                stdout=json.dumps(self._freshness_payload("stale"), ensure_ascii=False),
                stderr="",
            )

            with mock.patch("subprocess.run", side_effect=[failed, stale]) as run:
                res = kb_rag.retrieve(
                    "光刻机",
                    root / "wiki",
                    mode="hybrid",
                    timeout=5,
                )

            self.assertEqual(run.call_count, 2)
            self.assertFalse(res.ok)
            self.assertEqual(res.hits, [])
            self.assertEqual(res.telemetry.index_freshness, "stale")
            self.assertIn("非 fresh", res.warning)

    def test_dense_dependency_failure_does_not_retry_without_one_second_budget(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            failed = mock.Mock(
                returncode=1,
                stdout="",
                stderr="ModuleNotFoundError: No module named 'FlagEmbedding'",
            )

            with (
                mock.patch("subprocess.run", return_value=failed) as run,
                mock.patch("time.monotonic", side_effect=[10.0, 14.2]),
            ):
                res = kb_rag.retrieve(
                    "光刻机",
                    root / "wiki",
                    mode="hybrid",
                    timeout=5,
                )

            run.assert_called_once()
            self.assertFalse(res.ok)
            self.assertEqual(res.telemetry.requested_mode, "hybrid")
            self.assertEqual(res.telemetry.effective_mode, "hybrid")

    def test_ordinary_script_failure_does_not_retry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            failed = mock.Mock(returncode=1, stdout="", stderr="unexpected script failure")

            with mock.patch("subprocess.run", return_value=failed) as run:
                res = kb_rag.retrieve(
                    "光刻机",
                    root / "wiki",
                    mode="hybrid",
                    timeout=5,
                )

            run.assert_called_once()
            self.assertFalse(res.ok)
            self.assertEqual(res.telemetry.requested_mode, "hybrid")
            self.assertEqual(res.telemetry.effective_mode, "hybrid")
            self.assertEqual(res.telemetry.fallback_reason, "")

    def test_bm25_dependency_shaped_failure_does_not_retry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            failed = mock.Mock(
                returncode=1,
                stdout="",
                stderr="ModuleNotFoundError: No module named 'FlagEmbedding'",
            )

            with mock.patch("subprocess.run", return_value=failed) as run:
                res = kb_rag.retrieve(
                    "光刻机",
                    root / "wiki",
                    mode="bm25",
                    timeout=5,
                )

            run.assert_called_once()
            self.assertFalse(res.ok)
            self.assertEqual(res.telemetry.requested_mode, "bm25")
            self.assertEqual(res.telemetry.effective_mode, "bm25")
            self.assertEqual(res.telemetry.fallback_reason, "")

    def _freshness_payload(self, freshness: str) -> list[dict]:
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
                "index_freshness": freshness,
            }
        ]

    def _run_retrieve(self, root, payload, *, stderr="", **kwargs):
        proc = mock.Mock(
            returncode=0,
            stdout=json.dumps(payload, ensure_ascii=False),
            stderr=stderr,
        )
        with mock.patch.dict("os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=True):
            with mock.patch("subprocess.run", return_value=proc):
                return kb_rag.retrieve("光刻机", root / "wiki", **kwargs)

    def test_stale_hits_fail_closed_by_default(self) -> None:
        # formal 默认 require_fresh=True：过期命中一律丢弃，不进证据；无 fresh 命中则 ok=False。
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            res = self._run_retrieve(
                root,
                self._freshness_payload("stale"),
                stderr="[query] WARNING 索引过期: age=15.0d>14d\n",
            )

            self.assertFalse(res.ok)
            self.assertEqual(res.hits, [])
            self.assertTrue(res.telemetry.degraded)
            self.assertEqual(res.telemetry.index_freshness, "stale")
            self.assertIn("非 fresh", res.warning)

    def test_unknown_hits_fail_closed_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            res = self._run_retrieve(root, self._freshness_payload("unknown"))

            self.assertFalse(res.ok)
            self.assertEqual(res.hits, [])
            self.assertTrue(res.telemetry.degraded)

    def test_mixed_freshness_keeps_only_fresh_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            payload = [
                {
                    "page_id": "fresh",
                    "file_path": "wiki/concepts/光刻机.md",
                    "title": "Fresh",
                    "score": 0.9,
                    "best_chunk_id": "fresh::0",
                    "content_hash": "hash-fresh",
                    "evidence_text": "fresh chunk",
                    "index_source_revision": "abc123",
                    "index_freshness": "fresh",
                },
                {
                    "page_id": "stale",
                    "file_path": "wiki/concepts/光刻机.md",
                    "title": "Stale",
                    "score": 0.8,
                    "best_chunk_id": "stale::0",
                    "content_hash": "hash-stale",
                    "evidence_text": "stale chunk",
                    "index_source_revision": "abc123",
                    "index_freshness": "stale",
                },
            ]
            res = self._run_retrieve(root, payload)

            self.assertTrue(res.ok)
            self.assertEqual([hit.page_id for hit in res.hits], ["fresh"])
            self.assertTrue(res.telemetry.degraded)

    def test_exploratory_mode_retains_stale_but_is_not_strict(self) -> None:
        # 显式探索模式 require_fresh=False：保留 stale 命中，但标记 degraded 并告警。
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            res = self._run_retrieve(
                root,
                self._freshness_payload("stale"),
                stderr="[query] WARNING 索引过期: age=15.0d>14d\n",
                require_fresh=False,
            )

            self.assertTrue(res.ok)
            self.assertEqual(len(res.hits), 1)
            self.assertTrue(res.telemetry.degraded)
            self.assertIn("新鲜度=stale", res.warning)

    def test_rejects_hits_without_chunk_snapshot_binding(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            payload = [
                {
                    "page_id": "legacy",
                    "file_path": "wiki/concepts/光刻机.md",
                    "title": "Legacy",
                    "score": 0.9,
                    "evidence_text": "Page-level legacy hit",
                }
            ]
            proc = mock.Mock(returncode=0, stdout=json.dumps(payload, ensure_ascii=False), stderr="")
            with mock.patch.dict("os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=True):
                with mock.patch("subprocess.run", return_value=proc):
                    res = kb_rag.retrieve("光刻机", root / "wiki")

            self.assertFalse(res.ok)
            self.assertEqual(res.telemetry.status, "empty")
            self.assertIn("缺少 chunk/hash/快照绑定", res.warning)

    def test_telemetry_skipped_when_index_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)  # no .rag_index dir built
            with mock.patch.dict("os.environ", {}, clear=True):
                res = kb_rag.retrieve("光刻机", root / "wiki")
            self.assertFalse(res.ok)
            self.assertEqual(res.telemetry.status, "skipped")
            self.assertEqual(res.telemetry.index_kind, "structured")
            self.assertEqual(res.telemetry.dense_initializations, 0)

    def test_telemetry_marks_index_degradation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()  # default exists; full index does NOT
            proc = mock.Mock(returncode=0, stdout="[]", stderr="")
            with mock.patch.dict("os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=True):
                with mock.patch("subprocess.run", return_value=proc):
                    res = kb_rag.retrieve(
                        "光刻机", root / "wiki", mode="rerank", index_dir=kb_rag.FULL_INDEX_DIRNAME
                    )
            tel = res.telemetry
            self.assertTrue(tel.degraded)
            self.assertEqual(tel.index_kind, "structured")  # fell back to default
            self.assertTrue(tel.requested_index_dir.endswith(kb_rag.FULL_INDEX_DIRNAME))
            self.assertEqual(tel.status, "empty")


class KbRagIndexResolutionTests(unittest.TestCase):
    def test_prefers_vector_index_dir_over_legacy_rag_index_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch.dict("os.environ", {"VECTOR_INDEX_DIR": "/tmp/vector-index", "RAG_INDEX_DIR": "/tmp/rag-index"}, clear=True):
                self.assertEqual(kb_rag._resolve_index_dir(root), Path("/tmp/vector-index"))

    def test_keeps_legacy_rag_index_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch.dict("os.environ", {"RAG_INDEX_DIR": "/tmp/rag-index"}, clear=True):
                self.assertEqual(kb_rag._resolve_index_dir(root), Path("/tmp/rag-index"))


class KbRagPythonResolutionTests(unittest.TestCase):
    def test_prefers_explicit_python_env(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch.dict("os.environ", {"KB_RAG_PYTHON": "/tmp/rag-python"}, clear=False):
                self.assertEqual(kb_rag._resolve_rag_python(root), "/tmp/rag-python")

    def test_prefers_kb_rag_venv_over_current_python(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            py = root / ".rag_venv" / "bin" / "python"
            py.parent.mkdir(parents=True)
            py.write_text("#!/usr/bin/env python\n", encoding="utf-8")

            with mock.patch.dict("os.environ", {}, clear=True):
                self.assertEqual(kb_rag._resolve_rag_python(root), str(py))


if __name__ == "__main__":
    unittest.main()
