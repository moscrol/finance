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
                    "evidence_text": "旧版兼容字段。",
                    "display_excerpt": "供需展示短摘录。",
                    "llm_evidence_text": "命中块 wiki/concepts/光刻机.md::2: 命中的供需章节，而不是页面开头，并保留更多证据。",
                    "evidence_chunk_ids": [
                        "wiki/concepts/光刻机.md::2",
                        "wiki/concepts/光刻机.md::1",
                    ],
                    "evidence_query_terms": ["光刻机", "供需"],
                    "evidence_char_budget": 1200,
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
            self.assertEqual(res.hits[0].excerpt, "供需展示短摘录。")
            self.assertIn("更多证据", res.hits[0].llm_evidence)
            self.assertEqual(
                res.hits[0].evidence_chunk_ids,
                ("wiki/concepts/光刻机.md::2", "wiki/concepts/光刻机.md::1"),
            )
            self.assertEqual(res.hits[0].best_chunk_id, "wiki/concepts/光刻机.md::2")
            self.assertEqual(res.hits[0].section, "供需")
            self.assertEqual(res.telemetry.index_freshness, "fresh")
            self.assertIn("--evidence-chars", cmd)


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
            self.assertIn("LLM证据预算=", tel.summary_line())

    def test_dynamic_budget_prioritizes_order_queries_and_total_cap(self) -> None:
        per_hit, total = kb_rag.evidence_budget_for_query("002837 液冷订单是否兑现")
        quick_hit, _ = kb_rag.evidence_budget_for_query("快速概览液冷")

        self.assertGreater(per_hit, kb_rag.DEFAULT_LLM_EVIDENCE_CHARS)
        self.assertLess(quick_hit, per_hit)

        hits = [
            kb_rag.WikiHit("a", "a.md", "A", 1.0, "短", llm_evidence="A" * 20),
            kb_rag.WikiHit("b", "b.md", "B", 0.9, "短", llm_evidence="B" * 20),
        ]
        kb_rag.apply_total_llm_budget(hits, 25)

        self.assertEqual(len(hits[0].llm_evidence), 20)
        self.assertEqual(hits[1].llm_evidence, "BBBB…")

        exhausted = [
            kb_rag.WikiHit("c", "c.md", "C", 1.0, "展示", llm_evidence="完整证据")
        ]
        kb_rag.apply_total_llm_budget(exhausted, 0)
        self.assertEqual(
            exhausted[0].llm_evidence,
            kb_rag.EVIDENCE_BUDGET_EXHAUSTED,
        )

    def test_neighbor_budget_is_lower_and_official_l3_can_be_higher(self) -> None:
        direct = kb_rag._hit_evidence_limit({}, 1200)
        neighbor = kb_rag._hit_evidence_limit({"via_neighbor": True}, 1200)
        official = kb_rag._hit_evidence_limit(
            {"evidence_layer": "L3", "source_type": "official_disclosure"},
            1200,
        )

        self.assertLess(neighbor, direct)
        self.assertGreater(official, direct)

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

    def test_dense_dependency_failure_falls_back_to_bm25(self) -> None:
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

            with mock.patch.dict(
                "os.environ",
                {"KB_RAG_PYTHON": "/tmp/rag-python"},
                clear=True,
            ):
                with mock.patch(
                    "subprocess.run",
                    side_effect=[failed, success],
                ) as run:
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
            self.assertGreaterEqual(run.call_args_list[1].kwargs["timeout"], 1)
            self.assertLessEqual(run.call_args_list[1].kwargs["timeout"], 5)
            self.assertEqual(res.telemetry.requested_mode, "hybrid")
            self.assertEqual(res.telemetry.effective_mode, "bm25")
            self.assertEqual(res.telemetry.mode, "bm25")
            self.assertEqual(
                res.telemetry.fallback_reason,
                "dense_dependency_missing",
            )
            self.assertTrue(res.telemetry.degraded)
            self.assertIn("已回退 BM25", res.warning)

    def test_legacy_cli_retries_without_evidence_chars(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            unsupported = mock.Mock(
                returncode=2,
                stdout="",
                stderr="error: unrecognized arguments: --evidence-chars 1500",
            )
            success = mock.Mock(
                returncode=0,
                stdout=json.dumps(self._freshness_payload("fresh"), ensure_ascii=False),
                stderr="",
            )

            with mock.patch.dict(
                "os.environ",
                {"KB_RAG_PYTHON": "/tmp/rag-python"},
                clear=True,
            ):
                with mock.patch(
                    "subprocess.run",
                    side_effect=[unsupported, success],
                ) as run:
                    res = kb_rag.retrieve(
                        "光刻机",
                        root / "wiki",
                        mode="hybrid",
                        timeout=5,
                    )

            self.assertTrue(res.ok)
            self.assertEqual(run.call_count, 2)
            self.assertIn("--evidence-chars", run.call_args_list[0].args[0])
            self.assertNotIn("--evidence-chars", run.call_args_list[1].args[0])
            self.assertEqual(res.telemetry.query_protocol, "legacy")
            self.assertEqual(
                res.telemetry.unsupported_options,
                ("--evidence-chars",),
            )
            self.assertEqual(
                res.telemetry.fallback_reason,
                "legacy_cli_missing_evidence_chars",
            )
            self.assertTrue(res.telemetry.degraded)
            self.assertIn("legacy query 协议", res.warning)

    def test_bm25_fallback_still_rejects_stale_hits(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            failed = mock.Mock(
                returncode=1,
                stdout="",
                stderr="ImportError: BGEM3FlagModel unavailable",
            )
            stale = mock.Mock(
                returncode=0,
                stdout=json.dumps(self._freshness_payload("stale"), ensure_ascii=False),
                stderr="",
            )

            with mock.patch.dict(
                "os.environ",
                {"KB_RAG_PYTHON": "/tmp/rag-python"},
                clear=True,
            ):
                with mock.patch("subprocess.run", side_effect=[failed, stale]):
                    res = kb_rag.retrieve(
                        "光刻机",
                        root / "wiki",
                        mode="rerank",
                        timeout=5,
                    )

            self.assertFalse(res.ok)
            self.assertEqual(res.hits, [])
            self.assertEqual(res.telemetry.effective_mode, "bm25")
            self.assertEqual(res.telemetry.status, "empty")
            self.assertIn("非 fresh", res.warning)

    def test_dense_dependency_failure_skips_fallback_without_budget(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            failed = mock.Mock(
                returncode=1,
                stdout="",
                stderr="ModuleNotFoundError: No module named 'torch'",
            )

            with mock.patch.dict(
                "os.environ",
                {"KB_RAG_PYTHON": "/tmp/rag-python"},
                clear=True,
            ):
                with mock.patch("subprocess.run", return_value=failed) as run:
                    with mock.patch(
                        "time.monotonic",
                        side_effect=[10.0, 14.5, 14.5],
                    ):
                        res = kb_rag.retrieve(
                            "光刻机",
                            root / "wiki",
                            mode="dense",
                            timeout=5,
                        )

            self.assertEqual(run.call_count, 1)
            self.assertFalse(res.ok)
            self.assertEqual(res.telemetry.effective_mode, "dense")
            self.assertEqual(res.telemetry.fallback_reason, "dense_dependency_missing")
            self.assertIn("剩余预算不足", res.warning)

    def test_unrelated_retriever_error_does_not_fall_back(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            failed = mock.Mock(
                returncode=2,
                stdout="",
                stderr="ValueError: malformed query arguments",
            )

            with mock.patch.dict(
                "os.environ",
                {"KB_RAG_PYTHON": "/tmp/rag-python"},
                clear=True,
            ):
                with mock.patch("subprocess.run", return_value=failed) as run:
                    res = kb_rag.retrieve(
                        "光刻机",
                        root / "wiki",
                        mode="hybrid",
                        timeout=5,
                    )

            self.assertEqual(run.call_count, 1)
            self.assertFalse(res.ok)
            self.assertEqual(res.telemetry.effective_mode, "hybrid")
            self.assertEqual(res.telemetry.fallback_reason, "")
            self.assertEqual(res.warning, "wiki-rag 检索失败（退出码 2）")
            self.assertNotIn("malformed query arguments", res.warning)


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


class KbRagCliProbeTests(unittest.TestCase):
    def test_accepts_legacy_cli_when_required_options_exist(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wiki = root / "wiki"
            script = root / kb_rag.RAG_SCRIPT_REL
            wiki.mkdir()
            script.parent.mkdir()
            script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
            proc = mock.Mock(
                returncode=0,
                stdout="usage: query --k K --mode MODE --json",
                stderr="",
            )

            with mock.patch("subprocess.run", return_value=proc):
                probe = kb_rag.probe_rag_cli(wiki)

            self.assertTrue(probe.available)
            self.assertTrue(probe.query_protocol_compatible)
            self.assertEqual(probe.missing_required_options, ())
            self.assertIn("--evidence-chars", probe.missing_optional_options)
            self.assertIn("legacy", probe.warning)

    def test_rejects_cli_missing_required_query_options(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wiki = root / "wiki"
            script = root / kb_rag.RAG_SCRIPT_REL
            wiki.mkdir()
            script.parent.mkdir()
            script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
            proc = mock.Mock(
                returncode=0,
                stdout="usage: query --k K --mode MODE",
                stderr="",
            )

            with mock.patch("subprocess.run", return_value=proc):
                probe = kb_rag.probe_rag_cli(wiki)

            self.assertTrue(probe.available)
            self.assertFalse(probe.query_protocol_compatible)
            self.assertEqual(probe.missing_required_options, ("--json",))
            self.assertIn("必要", probe.warning)


class KbRagResultCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        kb_rag.clear_result_cache()

    def tearDown(self) -> None:
        kb_rag.clear_result_cache()

    def test_same_session_reuses_bound_result_but_other_session_does_not(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wiki = root / "wiki"
            page = wiki / "page.md"
            script = root / kb_rag.RAG_SCRIPT_REL
            index_dir = root / ".rag_index"
            wiki.mkdir()
            script.parent.mkdir()
            index_dir.mkdir()
            page.write_text("证据", encoding="utf-8")
            script.write_text("# script", encoding="utf-8")
            (index_dir / "meta.json").write_text(
                '{"revision":"one"}',
                encoding="utf-8",
            )
            payload = [
                {
                    "page_id": "page",
                    "file_path": "wiki/page.md",
                    "title": "Page",
                    "score": 1.0,
                    "best_chunk_id": "page::0",
                    "content_hash": "hash",
                    "evidence_text": "已绑定证据",
                    "index_source_revision": "revision-one",
                    "index_freshness": "fresh",
                }
            ]
            proc = mock.Mock(
                returncode=0,
                stdout=json.dumps(payload, ensure_ascii=False),
                stderr="",
            )
            with mock.patch("subprocess.run", return_value=proc) as run:
                first = kb_rag.retrieve(
                    "同一查询",
                    wiki,
                    cache_scope="user:conv-1",
                )
                second = kb_rag.retrieve(
                    "同一查询",
                    wiki,
                    cache_scope="user:conv-1",
                )
                third = kb_rag.retrieve(
                    "同一查询",
                    wiki,
                    cache_scope="user:conv-2",
                )

            self.assertTrue(first.ok)
            self.assertTrue(second.telemetry.cache_hit)
            self.assertEqual(second.telemetry.latency_ms, 0)
            self.assertFalse(third.telemetry.cache_hit)
            self.assertEqual(run.call_count, 2)

    def test_index_fingerprint_change_invalidates_session_cache(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wiki = root / "wiki"
            script = root / kb_rag.RAG_SCRIPT_REL
            index_dir = root / ".rag_index"
            wiki.mkdir()
            script.parent.mkdir()
            index_dir.mkdir()
            (wiki / "page.md").write_text("证据", encoding="utf-8")
            script.write_text("# script", encoding="utf-8")
            meta = index_dir / "meta.json"
            meta.write_text('{"revision":"one"}', encoding="utf-8")
            payload = [
                {
                    "page_id": "page",
                    "file_path": "wiki/page.md",
                    "title": "Page",
                    "score": 1.0,
                    "best_chunk_id": "page::0",
                    "content_hash": "hash",
                    "evidence_text": "已绑定证据",
                    "index_source_revision": "revision-one",
                    "index_freshness": "fresh",
                }
            ]
            proc = mock.Mock(
                returncode=0,
                stdout=json.dumps(payload, ensure_ascii=False),
                stderr="",
            )
            with mock.patch("subprocess.run", return_value=proc) as run:
                kb_rag.retrieve(
                    "同一查询",
                    wiki,
                    cache_scope="user:conv",
                )
                meta.write_text(
                    '{"revision":"two","changed":true}',
                    encoding="utf-8",
                )
                refreshed = kb_rag.retrieve(
                    "同一查询",
                    wiki,
                    cache_scope="user:conv",
                )

            self.assertFalse(refreshed.telemetry.cache_hit)
            self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
