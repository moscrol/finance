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
                    "snippet": "fallback",
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
