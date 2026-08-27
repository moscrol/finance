from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from intelligence.services.concept_page_gate import (
    ACTION_ESCALATE_MISSING,
    ACTION_ESCALATE_STUB,
    ACTION_SKIP_EXISTING,
    ACTION_SKIP_TOO_WIDE,
    classify_concept_theme,
    should_drop_concept_ingest,
)


class ConceptPageGateTest(unittest.TestCase):
    def test_classifies_complete_stub_missing_and_too_wide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            concepts = Path(tmp) / "concepts"
            concepts.mkdir()
            (concepts / "半导体.md").write_text("# 半导体\n完整叙事。\n", encoding="utf-8")
            (concepts / "Mini LED.md").write_text(
                "---\ntags: [\"待补证\"]\n---\n# Mini LED\n占位概念页\n",
                encoding="utf-8",
            )

            self.assertEqual(classify_concept_theme("半导体", tmp), ACTION_SKIP_EXISTING)
            self.assertEqual(classify_concept_theme("Mini LED", tmp), ACTION_ESCALATE_STUB)
            self.assertEqual(classify_concept_theme("减肥药", tmp), ACTION_ESCALATE_MISSING)
            self.assertEqual(classify_concept_theme("粮食概念", tmp), ACTION_SKIP_TOO_WIDE)
            self.assertTrue(should_drop_concept_ingest("半导体", tmp))
            self.assertFalse(should_drop_concept_ingest("Mini LED", tmp))
            self.assertFalse(should_drop_concept_ingest("减肥药", tmp))


if __name__ == "__main__":
    unittest.main()
