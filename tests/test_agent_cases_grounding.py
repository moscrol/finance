from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

import tempfile

from scripts.validate_agent_cases_grounding import (
    DEFAULT_CASES,
    grounding_report_for_kb,
    load_json,
    validate_case,
    validate_grounding,
)

ROOT = Path(__file__).resolve().parents[1]


def _kb_relations() -> Path:
    for var in ("KNOWLEDGE_WIKI", "KB_VAULT", "CONCEPT_VAULT", "ENTITY_VAULT"):
        val = os.environ.get(var)
        if val:
            return Path(val).expanduser() / "relations"
    return Path.home() / "knowledge-base-private" / "wiki" / "relations"


KB_RELATIONS = _kb_relations()


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


class _Spec:
    def __init__(self, **kw):
        self.id = kw.get("id")
        self.expect_concepts = kw.get("expect_concepts", [])
        self.expect_entities = kw.get("expect_entities", [])
        self.forbid_entities = kw.get("forbid_entities", [])
        self.entity_recall_gate = kw.get("entity_recall_gate", 0.5)


class GroundingPreflightTest(unittest.TestCase):
    def _make_kb(self, root: Path) -> Path:
        wiki = root / "wiki"
        rel = wiki / "relations"
        rel.mkdir(parents=True)
        (rel / "entity_exposures.json").write_text(
            json.dumps({"entities": {"世运电路": {"concepts": {"PCB": {}}}}}, ensure_ascii=False),
            encoding="utf-8",
        )
        (rel / "concept_graph.json").write_text(
            json.dumps({"concepts": {"PCB": {}}}, ensure_ascii=False), encoding="utf-8"
        )
        return wiki

    def test_preflight_passes_for_grounded_spec(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            wiki = self._make_kb(Path(td))
            specs = [_Spec(id="pcb", expect_concepts=["PCB"], expect_entities=["世运电路"])]
            report = grounding_report_for_kb(specs, wiki)
            self.assertIsNotNone(report)
            self.assertTrue(report["passed"])

    def test_preflight_fails_for_fabricated_spec(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            wiki = self._make_kb(Path(td))
            specs = [_Spec(id="fake", expect_concepts=["PCB"], expect_entities=["不存在公司A", "不存在公司B"])]
            report = grounding_report_for_kb(specs, wiki)
            self.assertFalse(report["passed"])
            self.assertEqual(report["failed_ids"], ["fake"])

    def test_preflight_skips_when_kb_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            specs = [_Spec(id="pcb", expect_concepts=["PCB"], expect_entities=["世运电路"])]
            self.assertIsNone(grounding_report_for_kb(specs, Path(td) / "no-wiki"))


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
