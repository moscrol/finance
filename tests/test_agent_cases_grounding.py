from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.validate_agent_cases_grounding import (
    DEFAULT_CASES,
    load_json,
    validate_case,
    validate_grounding,
)

ROOT = Path(__file__).resolve().parents[1]
KB_RELATIONS = Path("/Users/lbq/Desktop/c c/知识库/wiki/relations")


def _entities() -> dict:
    return {
        "世运电路": {"concepts": {"PCB": {"strength": "core"}}},
        "兴森科技": {"concepts": {"PCB": {"strength": "core"}}},
        "宁德时代": {"concepts": {"固态电池": {"strength": "core"}, "锂电池": {}}},
    }


class GroundingPureLogicTest(unittest.TestCase):
    def test_grounded_case_passes(self) -> None:
        case = {
            "id": "pcb",
            "expect_concepts": ["PCB"],
            "expect_entities": ["世运电路", "兴森科技"],
            "forbid_entities": ["宁德时代"],
            "entity_recall_gate": 0.5,
        }
        r = validate_case(case, _entities(), {"PCB", "固态电池"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["expect_rate"], 1.0)
        self.assertEqual(r["forbid_violations"], [])

    def test_missing_concept_fails(self) -> None:
        case = {"id": "x", "expect_concepts": ["不存在概念"], "expect_entities": ["世运电路"]}
        r = validate_case(case, _entities(), {"PCB"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["concept_missing"], ["不存在概念"])

    def test_forbid_entity_actually_in_theme_is_violation(self) -> None:
        # 宁德时代 is exposed to 固态电池, so listing it as a 固态电池 trap is wrong.
        case = {
            "id": "ssb",
            "expect_concepts": ["固态电池"],
            "expect_entities": ["宁德时代"],
            "forbid_entities": ["宁德时代"],
            "entity_recall_gate": 0.5,
        }
        r = validate_case(case, _entities(), {"固态电池"})
        self.assertFalse(r["ok"])
        self.assertIn("宁德时代", r["forbid_violations"])

    def test_low_expect_recall_fails_gate(self) -> None:
        case = {
            "id": "pcb",
            "expect_concepts": ["PCB"],
            "expect_entities": ["世运电路", "不在库的公司", "另一家不在库"],
            "entity_recall_gate": 0.5,
        }
        r = validate_case(case, _entities(), {"PCB"})
        self.assertFalse(r["rate_ok"])
        self.assertFalse(r["ok"])

    def test_validate_grounding_aggregates(self) -> None:
        cases = [
            {"id": "ok", "expect_concepts": ["PCB"], "expect_entities": ["世运电路"], "entity_recall_gate": 0.5},
            {"id": "bad", "expect_concepts": ["缺"], "expect_entities": ["世运电路"]},
        ]
        report = validate_grounding(cases, _entities(), {"PCB"})
        self.assertFalse(report["passed"])
        self.assertEqual(report["failed_ids"], ["bad"])


@unittest.skipUnless(KB_RELATIONS.exists(), "knowledge base not available on this machine")
class GroundingAgainstRealKbTest(unittest.TestCase):
    def test_bundled_cases_are_grounded_in_kb(self) -> None:
        entities = load_json(KB_RELATIONS / "entity_exposures.json").get("entities", {})
        graph_concepts = set(load_json(KB_RELATIONS / "concept_graph.json").get("concepts", {}))
        cases = json.loads(DEFAULT_CASES.read_text(encoding="utf-8")).get("cases", [])
        report = validate_grounding(cases, entities, graph_concepts)
        self.assertTrue(report["passed"], report["failed_ids"])


if __name__ == "__main__":
    unittest.main()
