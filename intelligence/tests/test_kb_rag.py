from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence.services import kb_rag


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
