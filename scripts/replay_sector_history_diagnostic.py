"""Replay the 2026-09-17 sector/history diagnostic without a model or database.

Prevents an archived answer/trace disagreement from becoming an untestable story.
Reads the private diagnostic bundle and imports only the explicitly selected
runtime's deterministic predicates. JSON output describes observed defects;
exit 0 means replay completed, NOT that the answer or production passed QC.

Usage:
    python scripts/replay_sector_history_diagnostic.py \
        --artifacts-root PATH_TO_DIAGNOSTIC_BUNDLE --runtime-root PATH_TO_RUNTIME

Bundle layout: components/, production-hybrid/, production-manual/.
No API calls, database writes, or production configuration changes.
"""

from __future__ import annotations

import argparse
from collections import Counter
import importlib
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def member_rows(path: Path) -> list[dict[str, str]]:
    result = load(path)["result"]
    if result.get("gaps"):
        raise ValueError(f"Incomplete member evidence: {path}")
    return [
        dict(part.split("=", 1) for part in item["detail"].split("；"))
        for item in result["evidence"]
    ]


def replay(bundle: Path, runtime: Path) -> dict:
    sys.path.insert(0, str(runtime))
    verifier = importlib.import_module("intelligence.services.episode_semantic_verifier")
    ranking = importlib.import_module("intelligence.services.ranking_contract")
    for module in (verifier, ranking):
        if not Path(module.__file__).resolve().is_relative_to(runtime.resolve()):
            raise ValueError("Imported module is not from the requested runtime")

    episode = load(bundle / "production-hybrid/continuous-episode.json")
    answer = (bundle / "production-hybrid/answer.md").read_text(encoding="utf-8")
    outcome = episode["outcome"]
    evidence = outcome["evidence"]
    components = bundle / "components"
    members = {
        theme: member_rows(components / f"postcheck-{theme}-limit-members.json")
        for theme in ("storage", "lithium", "solid")
    }
    codes = {row["股票代码"] for rows in members.values() for row in rows}
    market = next(item for item in evidence if "涨跌结构：" in item["detail"])
    match = re.search(r"涨停\s*(\d+)\s*家", market["detail"])
    if match is None:
        raise ValueError("Market limit-up denominator is absent")
    denominator = int(match[1])

    d10 = next(item for item in evidence if "市场情绪环境类比" in item["title"])
    analogues = []
    for line in d10["detail"].splitlines():
        if re.match(r"\| 20\d\d-", line):
            cells = [part.strip() for part in line.strip("|").split("|")]
            analogues.append({"window": cells[0], "distance": float(cells[1])})

    verdicts = episode["semantic_verifier"]["sentence_verdicts"]
    deleted = next(
        item for item in verdicts
        if item["decision"] == "deleted" and "利多不涨" in item["sentence"]
    )
    sentence = deleted["sentence"]
    without_citation = re.sub(r"（E\d+）", "", sentence)
    # Narrow duck-typed adapters for these read-only predicates; not a runtime
    # deserializer or a claim that JSON round-trips every domain type.
    adapted_evidence = [
        SimpleNamespace(**{
            **item,
            "observations": [SimpleNamespace(**obs) for obs in item.get("observations", [])],
        })
        for item in evidence
    ]
    verified = SimpleNamespace(
        outcome=SimpleNamespace(
            evidence=adapted_evidence,
            bindings=[SimpleNamespace(**item) for item in outcome["bindings"]],
        ),
        contract=SimpleNamespace(required_outputs=[
            SimpleNamespace(**item) for item in episode["contract"]["required_outputs"]
        ]),
    )

    def rejected(text: str) -> list[int]:
        return list(verifier._novel_numeric_condition_indexes(
            [{"index": deleted["sentence_index"], "text": text}], verified,
        ))

    calls = [
        event["payload"] for event in episode["events"] if event["kind"] == "tool_request"
    ]
    period_calls = [
        call for call in calls if call["arguments"].get("dataset") == "sector_period_rank_daily"
    ]
    before = load(components / "health.before.json")["runtime"]
    after = load(components / "health.after.json")["runtime"]
    manual = load(bundle / "production-manual/continuous-episode.json")
    return {
        "meaning": "Offline baseline reproduction; not a repaired-runtime pass receipt",
        "runtime_revision": before["source_revision"],
        "runtime_unchanged_during_probe": all(
            before[key] == after[key]
            for key in ("source_revision", "loaded_tree_fingerprint", "dependency_fingerprint")
        ),
        "tool_calls": len(calls),
        "tool_counts": dict(Counter(call["name"] for call in calls)),
        "metrics": episode["metrics"],
        "membership_overlap": {
            "per_theme_rows": {theme: len(rows) for theme, rows in members.items()},
            "membership_rows": sum(map(len, members.values())),
            "unique_stocks": len(codes),
            "market_limit_up_count": denominator,
            "unique_share_pct": len(codes) / denominator * 100,
            "public_answer_claims_81_pct": "约 81%" in answer,
            "boundary": "Tag membership union, not verified causal attribution",
        },
        "history_distance_order": sorted(analogues, key=lambda item: item["distance"]),
        "ranking_contract": {
            "receipt": episode["ranking_contract"],
            "predicate_replay": ranking.parse_ranking_intent(
                episode["task_frame"]["raw_question"], episode["task_frame"]["question_type"],
            ),
        },
        "period_rank_query": {
            "attempts": len(period_calls),
            "arguments": [call["arguments"] for call in period_calls],
            "traces": [trace for trace in episode["traces"] if "invalid_query" in trace["detail"]],
        },
        "citation_number_false_positive": {
            "sentence": sentence,
            "quantity_tokens": verifier._ARABIC_QUANTITY_RE.findall(sentence),
            "rejected_with_citation": rejected(sentence),
            "rejected_without_citation": rejected(without_citation),
        },
        "manual_attempt": {
            "metrics": manual["metrics"],
            "failure": manual["failure"],
            "boundary": "A different probe setting; no mode-level causality established",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(replay(args.artifacts_root, args.runtime_root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
