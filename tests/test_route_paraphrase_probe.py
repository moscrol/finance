"""路由改写探针的结构守卫：题集每条都指向存在的原题，三种风格齐全。"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

CASES = Path(__file__).resolve().parents[1] / "intelligence" / "eval" / "cases"


def test_paraphrase_set_covers_every_seed_with_three_styles() -> None:
    seeds = {json.loads(line)["id"] for line in (CASES / "uq15_questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()}
    rows = [json.loads(line) for line in (CASES / "route_paraphrase_v1.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert {r["seed"] for r in rows} == seeds
    per_seed = Counter((r["seed"], r["style"]) for r in rows)
    assert all(v == 1 for v in per_seed.values())
    assert {r["style"] for r in rows} == {"colloquial", "reordered", "terse"}
    assert len(rows) == 3 * len(seeds)
