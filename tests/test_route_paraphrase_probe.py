"""路由改写探针的结构守卫：题集每条都指向存在的原题，三种风格齐全。"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from types import SimpleNamespace

CASES = Path(__file__).resolve().parents[1] / "intelligence" / "eval" / "cases"


def test_paraphrase_set_covers_every_seed_with_three_styles() -> None:
    seeds = {json.loads(line)["id"] for line in (CASES / "uq15_questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()}
    rows = [json.loads(line) for line in (CASES / "route_paraphrase_v1.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert {r["seed"] for r in rows} == seeds
    per_seed = Counter((r["seed"], r["style"]) for r in rows)
    assert all(v == 1 for v in per_seed.values())
    assert {r["style"] for r in rows} == {"colloquial", "reordered", "terse"}
    assert len(rows) == 3 * len(seeds)


def test_llm_fallback_annotation_does_not_hide_the_actual_fallback_route(tmp_path, monkeypatch):
    from scripts.route_paraphrase_probe import run
    from intelligence.services.query_resolution import QueryResolver
    from intelligence.services import turn_controller

    monkeypatch.setattr(QueryResolver, "resolve", lambda self, question: SimpleNamespace(anchor=None))
    monkeypatch.setattr(turn_controller, "decide_turn", lambda *a, **kw: SimpleNamespace(
        lane="research", question_type="general_finance_qa", llm_failure_reason="offline", reason="fallback",
    ))
    seeds, paraphrases = tmp_path / "seeds.jsonl", tmp_path / "paraphrases.jsonl"
    seeds.write_text(json.dumps({"id": "one", "question": "seed"}))
    paraphrases.write_text(json.dumps({"seed": "one", "question": "variant", "style": "terse"}))
    report = run(seeds, paraphrases)
    assert report["seed_fallback_rate"] == report["paraphrase_fallback_rate"] == 1
    assert report["llm_fallback_count"] == report["routed_total"] == 2
