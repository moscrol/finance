"""Offline dry run of the two #855 gates over the sealed R3/R6 answer sheets.

Reads each ``cases/<name>/`` of the given sealed review roots: the episode's own
contract / draft / evidence / bindings (``artifacts/continuous-episode.json``) and
the delivered public message (``public-message.json``). Calls exactly the two
gates the adapter wires and nothing else: ``track_contract.conclusion_ttl_conflicts``
on the public answer (what ``_track_public_delivery`` discloses) and
``financial_claim_checks.comparison_baseline_gaps`` on the numbered sentences with
the episode's bound evidence (what ``_issue_backfill_plan`` routes to backfill;
computed on the draft as in production and on the public text as a cross-check).

No model call, no network (socket connect is denied), no write into the sealed
archives; SHA256 of every input is recorded and re-checked. The output must be new
and outside the archives. Positive control: temporarily disable the subject
fallback inside ``comparison_baseline_gaps`` and the R3 positive-persistence hit
must disappear; restore and it must return.

    python docs/verification/2026-09-23-financial-ttl-baseline-fwd/dry_run_sealed.py \\
        --cases ~/.finance-runtime/reviews/8792-boundary-retest-20260918 \\
        --cases ~/.finance-runtime/reviews/8792-financial-live-r6-20260918 \\
        --output <new json path outside the archives>
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

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from intelligence.services import episode_semantic_verifier as semantic  # noqa: E402
from intelligence.services.agent_research import AgentEvidence, StructuredObservation  # noqa: E402
from intelligence.services.agent_runtime import OutputEvidenceBinding  # noqa: E402
from intelligence.services.financial_claim_checks import comparison_baseline_gaps  # noqa: E402
from intelligence.services.research_contract import ResearchTaskContract  # noqa: E402
from intelligence.services.track_contract import conclusion_ttl_conflicts  # noqa: E402

GATE_SOURCE = ROOT / "intelligence/services/financial_claim_checks.py"


def decode_evidence(rows) -> tuple[AgentEvidence, ...]:
    allowed = {field.name for field in fields(AgentEvidence)}
    result = []
    for row in rows:
        data = {key: value for key, value in row.items() if key in allowed}
        data["observations"] = tuple(StructuredObservation(**obs) for obs in row.get("observations", ()))
        for name in ("supports", "contradicts", "derived_from"):
            data[name] = tuple(data.get(name, ()))
        result.append(AgentEvidence(**data))
    return tuple(result)


def inspect_case(case_dir: Path, read) -> dict:
    public = str(json.loads(read(case_dir / "public-message.json"))["content"])
    episode_path = case_dir / "artifacts" / "continuous-episode.json"
    if not episode_path.is_file():
        # R3 f2-dated-citation-plan was sealed without an episode: no contract, no
        # bound evidence. The gates then have nothing to anchor and must stay silent;
        # the public text is still checked for TTL conflicts (that gate needs no evidence).
        subject, question_type, evidence, bound, draft = None, None, (), (), ""
    else:
        episode = json.loads(read(episode_path))
        contract = ResearchTaskContract.from_dict(episode["contract"])
        outcome = episode["outcome"]
        subject, question_type = contract.subject, contract.question_type
        evidence = decode_evidence(outcome["evidence"])
        bindings = tuple(OutputEvidenceBinding(**row) for row in outcome["bindings"])
        bound = tuple(dict.fromkeys(h for binding in bindings for h in binding.evidence_hashes))
        draft = str(outcome.get("draft") or "")

    def gaps(text: str) -> list[str]:
        return list(comparison_baseline_gaps(
            semantic._numbered_sentences(text), evidence, bound, subject=subject,
        ))

    return {
        "episode": "present" if episode_path.is_file() else "missing",
        "subject": subject,
        "question_type": question_type,
        "bound_hashes": len(bound),
        "ttl_conflicts": list(conclusion_ttl_conflicts(public)),
        "baseline_gaps_draft": gaps(draft),
        "baseline_gaps_public": gaps(public),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cases", action="append", type=Path, required=True,
                        help="sealed review root that contains cases/<name>/ (repeatable)")
    parser.add_argument("--output", type=Path, required=True, help="new JSON report path outside the archives")
    args = parser.parse_args()
    roots = [root.expanduser().resolve() for root in args.cases]
    output = args.output.expanduser().resolve()
    if output.exists() or any(output.is_relative_to(root) for root in roots):
        parser.error("output must be new and outside the sealed archives")
    attempts: list[str] = []

    def denied(*_args, **_kwargs):
        attempts.append("connect")
        raise AssertionError("offline dry run must not connect")

    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = denied  # type: ignore[assignment]
    sources: dict[str, str] = {}

    def read(path: Path) -> str:
        data = path.read_bytes()
        sources[str(path)] = hashlib.sha256(data).hexdigest()
        return data.decode("utf-8")

    rows = []
    for root in roots:
        for case_dir in sorted(p for p in (root / "cases").iterdir() if p.is_dir()):
            rows.append({"round": root.name, "case": case_dir.name, **inspect_case(case_dir, read)})
    assert not attempts
    assert all(hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest for name, digest in sources.items())
    summary = {
        "cases": len(rows),
        "ttl_conflicts": sum(bool(row["ttl_conflicts"]) for row in rows),
        "baseline_gaps_draft": sum(bool(row["baseline_gaps_draft"]) for row in rows),
        "baseline_gaps_public": sum(bool(row["baseline_gaps_public"]) for row in rows),
    }
    report = {
        "scope": "finite offline replay of two gates over sealed inputs; not a natural acceptance, "
                 "does not change any R3/R6 verdict",
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "financial_claim_checks_sha256": hashlib.sha256(GATE_SOURCE.read_bytes()).hexdigest(),
        "sources_sha256": sources,
        "sources_unchanged": True,
        "network_connect_attempts": len(attempts),
        "summary": summary,
        "cases": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    def mark(items: list[str]) -> str:
        return "命中" if items else "—"

    print(f"{'轮次':<40} {'题':<26} {'主体':<8} {'绑定':>4}  TTL冲突  基线缺口(draft)  基线缺口(public)")
    for row in rows:
        print(f"{row['round']:<40} {row['case']:<26} {str(row['subject']):<8} {row['bound_hashes']:>4}  "
              f"{mark(row['ttl_conflicts']):<7}  {mark(row['baseline_gaps_draft']):<15}  "
              f"{mark(row['baseline_gaps_public'])}")
    print(f"汇总: TTL 冲突 {summary['ttl_conflicts']}/{summary['cases']}, "
          f"基线缺口 draft {summary['baseline_gaps_draft']}/{summary['cases']}, "
          f"public {summary['baseline_gaps_public']}/{summary['cases']}; "
          f"revision {report['revision'][:9]} dirty={report['dirty']} "
          f"gate sha256 {report['financial_claim_checks_sha256'][:12]}; report {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
