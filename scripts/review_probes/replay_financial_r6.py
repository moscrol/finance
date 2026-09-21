"""Read-only R6 archive checks against the current finite financial guards.

No new retrieval/model call, no Episode rerun, no upgrade of the original 0/4
verdict. Reads exact public messages plus their archived evidence/bindings;
checks only known financial/threshold/parser/document boundaries. Any test
writes go to TemporaryDirectory. SHA256 covers every input before/after.
The output must be outside the sealed archive and must not already exist.
"""
from __future__ import annotations

import argparse
from dataclasses import fields
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from intelligence.services import episode_semantic_verifier as semantic  # noqa: E402
from intelligence.services.agent_research import AgentEvidence, StructuredObservation  # noqa: E402
from intelligence.services.agent_runtime import OutputEvidenceBinding  # noqa: E402
from intelligence.services.financial_claim_checks import calculation_ratio_gaps  # noqa: E402
from intelligence.services.financial_report_contract import report_document_binding_gaps  # noqa: E402
from intelligence.services.research_contract import ResearchTaskContract  # noqa: E402
from intelligence.services.track_contract import ingest_next_watch, missing_contract_elements, parse_next_watch_items  # noqa: E402

CASES = ("f1-opt-out", "f2-dated-citation-plan", "f3-calculated-financial", "positive-persistence")
BAD_FRAGMENTS = {
    "f1-opt-out": ("覆盖率较中报的0.132明显回升",),
    "f2-dated-citation-plan": ("本次实际取得并引用的报告",),
    "f3-calculated-financial": ("存货半年内增加约41.5亿元", "同累计长度对照2025全年", "是否回到0.6以上"),
    "positive-persistence": ("净流出约15.66亿元",),
}
SAFE_FRAGMENTS = {
    "f1-opt-out": ("归母净利润136.51", "复核期限：2026-10-22"),
    "f2-dated-citation-plan": ("请于2026-10-22复查", "官方公告通道本次未取得中报原文正文"),
    "f3-calculated-financial": ("营收194.96", "归母净利136.51"),
    "positive-persistence": ("136.51", "2026-10-22"),
}


def decode_evidence(rows):
    allowed = {field.name for field in fields(AgentEvidence)}
    result = []
    for row in rows:
        data = {key: value for key, value in row.items() if key in allowed}
        data["observations"] = tuple(StructuredObservation(**obs) for obs in row.get("observations", ()))
        for name in ("supports", "contradicts", "derived_from"):
            data[name] = tuple(data.get(name, ()))
        result.append(AgentEvidence(**data))
    return tuple(result)


def inspect_case(public, episode, question, *, sink: Path):
    contract = ResearchTaskContract.from_dict(episode["contract"])
    outcome = episode["outcome"]
    evidence = decode_evidence(outcome["evidence"])
    bindings = tuple(OutputEvidenceBinding(**row) for row in outcome["bindings"])
    # Only helpers which consume contract/evidence/bindings are called here.
    # This is deliberately NOT forged VerifiedEpisodeOutcome/semantic approval.
    view = SimpleNamespace(contract=contract, outcome=SimpleNamespace(evidence=evidence, bindings=bindings))
    bound = tuple(dict.fromkeys(h for binding in bindings for h in binding.evidence_hashes))
    sentences = semantic._numbered_sentences(public)
    financial = semantic._financial_claim_mismatch_indexes(sentences, view)
    thresholds = semantic._novel_numeric_condition_indexes(sentences, view)
    rejected = set((*financial, *thresholds))
    findings = [{**row, "reasons": [reason for indexes, reason in (
        (financial, "financial_claim_mismatch"), (thresholds, "novel_numeric_condition"),
    ) if row["index"] in indexes]} for row in sentences if row["index"] in rejected]
    retained = "\n".join(str(row["text"]) for row in sentences if row["index"] not in rejected)
    items = parse_next_watch_items(public, as_of="2026-09-18")
    rows = ingest_next_watch(sink, public, query=question, as_of="2026-09-18", session_id="offline-r6-replay")
    return {
        "findings": findings,
        "retained_for_mechanical_inspection_only": retained,
        "original_watch_structure_missing": list(missing_contract_elements(public)),
        "watch_due": [item.due for item in items],
        "temporary_writer_rows": len(rows),
        "temporary_writer_sessions": [row["session_id"] for row in rows],
        "document_gaps": list(report_document_binding_gaps(question, evidence, bound, subject=contract.subject)),
        "calculation_input_gaps": list(calculation_ratio_gaps(evidence, bound, subject=contract.subject)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.live_root.resolve(), args.output.resolve()
    if output.is_relative_to(root) or output.exists():
        parser.error("output must be new and outside the sealed archive")
    attempts = []

    def denied(*_args, **_kwargs):
        attempts.append("connect")
        raise AssertionError("offline replay must not connect")

    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = denied
    sources = {}

    def read(relative):
        data = (root / relative).read_bytes()
        sources[relative] = hashlib.sha256(data).hexdigest()
        return data.decode("utf-8")

    results = {}
    with tempfile.TemporaryDirectory(prefix="r6-financial-replay-") as tmp:
        for case in CASES:
            prefix = f"cases/{case}"
            public = json.loads(read(f"{prefix}/public-message.json"))["content"]
            episode = json.loads(read(f"{prefix}/artifacts/continuous-episode.json"))
            question = read(f"{prefix}/question.txt")
            result = inspect_case(public, episode, question, sink=Path(tmp) / case / "checkpoints.jsonl")
            rejected = "\n".join(row["text"] for row in result["findings"])
            assert all(fragment in rejected for fragment in BAD_FRAGMENTS[case]), case
            assert all(fragment in result["retained_for_mechanical_inspection_only"] for fragment in SAFE_FRAGMENTS[case]), case
            assert result["calculation_input_gaps"] == [], "correct R6 products must not be rejected"
            assert bool(result["document_gaps"]) == (case == "f2-dated-citation-plan")
            assert result["temporary_writer_rows"] == (1 if case == "positive-persistence" else 0)
            if case in {"f1-opt-out", "positive-persistence"}:
                assert result["original_watch_structure_missing"] == []
                assert result["watch_due"] == ["2026-10-22"]
            results[case] = result
    assert not attempts
    assert all(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest for name, digest in sources.items())
    report = {
        "scope": "finite original-input mechanical replay, not final publication, live acceptance or general financial correctness",
        "original_acceptance": "0/4 not_passed, unchanged",
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "sources_sha256": sources, "sources_unchanged": True,
        "network_connect_attempts": len(attempts), "cases": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"4 archived cases checked; original verdict unchanged; report: {output}")


if __name__ == "__main__":
    main()
