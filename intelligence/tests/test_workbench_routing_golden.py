from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.query_resolution import QueryResolver
from intelligence.services.research_contract import TurnIntent
from intelligence.services.turn_controller import TurnDecision, decide_turn


CASES_PATH = Path(__file__).parent / "fixtures" / "workbench_routing_golden.json"


def _load_cases() -> list[dict[str, object]]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def _no_llm(_messages: list[dict[str, str]]):
    return None, None, "golden set disables LLM fallback"


@pytest.fixture
def resolver(tmp_path: Path) -> QueryResolver:
    relations = tmp_path / "relations"
    relations.mkdir()
    (relations / "entity_exposures.json").write_text(
        json.dumps(
            {
                "entities": {
                    "中际旭创": {
                        "codes": ["300308.SZ"],
                        "concepts": {"CPO": {}, "光模块": {}},
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (relations / "aliases.json").write_text(
        json.dumps(
            {"aliases": {"光模块代工": "光模块", "光模块": "光模块"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return QueryResolver(KnowledgeAdapter(wiki_root=tmp_path))


def _previous_intent(value: object) -> TurnIntent | None:
    if not isinstance(value, dict):
        return None
    return TurnIntent(
        primary_subject=str(value["subject"]),
        secondary_topics=(),
        question_type=str(value["question_type"]),
        answer_owner=value["owner"],
        comparison_entities=(),
        inherited_from_turn=None,
        evidence_atom_ids=("golden-atom",),
    )


def _assert_expected(expected: dict[str, object], decision: TurnDecision) -> None:
    assert decision.lane == expected["lane"]
    if "question_type" in expected:
        assert decision.question_type == expected["question_type"]
    if "subject" in expected:
        assert decision.subject == expected["subject"]
    owner = decision.turn_intent.answer_owner if decision.turn_intent else None
    assert owner == expected.get("owner")
    if expected.get("inherited"):
        assert decision.turn_intent is not None
        assert decision.turn_intent.inherited_from_turn == "golden-previous"
        assert decision.turn_intent.evidence_atom_ids == ("golden-atom",)
    if "operators" in expected:
        assert decision.turn_intent is not None
        assert set(expected["operators"]).issubset(decision.turn_intent.operators)
    if "capabilities" in expected:
        assert set(expected["capabilities"]).issubset(decision.capabilities)


@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: case["id"])
def test_workbench_routing_golden(
    case: dict[str, object],
    resolver: QueryResolver,
) -> None:
    previous = _previous_intent(case.get("previous"))
    decision = decide_turn(
        str(case["query"]),
        previous_intent=previous,
        previous_turn_id="golden-previous" if previous else None,
        llm_complete=_no_llm,
        resolver=resolver,
    )

    _assert_expected(case["expected"], decision)
