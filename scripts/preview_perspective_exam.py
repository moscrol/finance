"""Preview a human-review proposal without saving an exam or approving a rule.

Verify source fingerprints, reuse perspective_exam.score_case, and compare the
current profile with an in-memory boundary proposal. A valid preview always stays
BLOCKED (exit 2): matching tests cannot grant approval. Private profile text and
scoring reasons are represented by hashes/counts, never emitted.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence import userspace  # noqa: E402
from intelligence.services import perspective_exam as exam  # noqa: E402
from intelligence.services import perspective_lab as lab  # noqa: E402
from scripts.verify_perspective_consumption import digest, require  # noqa: E402


def _score(profile: dict, cases: list[dict]) -> dict:
    rows = []
    for case in cases:
        scored = exam.score_case(profile, case)
        ev = scored["evaluation"]
        rows.append({
            "id": scored["id"], "kind": scored["kind"], "passed": scored["passed"],
            "direction": ev["direction"], "abstain": ev["abstain"],
            "opportunity_hit_count": len(ev["opportunity_hits"]),
            "risk_hit_count": len(ev["risk_hits"]),
            "boundary_hit_count": len(ev["matched_boundaries"]),
            "reason_count": len(scored["reasons"]),
            "reason_sha256": [digest(reason.encode()) for reason in scored["reasons"]],
        })
    return {"all_cases_passed": all(row["passed"] for row in rows), "cases": rows}


def preview(us: userspace.UserSpace, proposal_path: Path) -> dict:
    tracked: dict[Path, str] = {}

    def read_input(path: Path) -> bytes:
        data = path.read_bytes()
        tracked[path] = digest(data)
        return data

    proposal = json.loads(read_input(proposal_path))
    require(isinstance(proposal, dict), "Proposal must be an object")
    require(proposal.get("proposal_status") == "pending_human_review", "Not a pending proposal")
    require(proposal.get("user_approval") is None, "This preview cannot process approvals")
    pid = lab.resolve_perspective_id(proposal["perspective_id"])
    root = lab.perspectives_root(us).resolve()
    require(us.root.resolve() == us.root.parent.resolve() / us.user_id, "Redirected user root")
    require(root == us.root.resolve() / "perspectives", "Redirected perspective root")
    profile_path = lab.profile_path(us, pid)
    manifest_path = lab.manifest_path(us, pid)
    live_exam = exam.exam_path(us, pid)
    for path in (profile_path, manifest_path, live_exam):
        require(path.resolve().is_relative_to(root), "Input outside selected user")
    require(not proposal_path.resolve().is_relative_to(us.root.resolve()), "Proposal must stay outside user state")
    profile = json.loads(read_input(profile_path))
    require(isinstance(profile, dict), "Profile must be an object")
    require(profile.get("id") == pid, "Wrong profile identity")
    records = [json.loads(line) for line in read_input(manifest_path).decode().splitlines() if line.strip()]
    require(all(isinstance(record, dict) for record in records), "Invalid manifest record")
    by_id = {record["article_id"]: record for record in records}
    require(len(by_id) == len(records), "Duplicate source identity")
    exam_present = live_exam.exists()
    if exam_present:
        read_input(live_exam)

    verified = []
    sources = proposal["sources"]
    require(isinstance(sources, list) and sources, "Missing proposal sources")
    require(all(isinstance(source, dict) for source in sources), "Invalid proposal source")
    source_ids = {source["article_id"] for source in sources}
    require(len(source_ids) == len(sources), "Duplicate proposal source")
    for source in sources:
        record = by_id.get(source["article_id"])
        require(record is not None and record.get("perspective_id") == pid, "Unknown or wrong-perspective source")
        require(record.get("date") == source["date"] and record.get("title") == source["title"], "Source metadata changed")
        path = Path(record["raw_path"])
        raw_root = root / "articles" / pid / "raw"
        require(path.resolve().is_relative_to(raw_root), "Source outside selected perspective")
        data = read_input(path)
        require(digest(data) == source["raw_sha256"], "Source fingerprint changed")
        lines = data.decode().splitlines()
        start, end = source["line_start"], source["line_end"]
        require(type(start) is int and type(end) is int and 1 <= start <= end <= len(lines), "Invalid source span")
        excerpt = "\n".join(lines[start - 1:end])
        require(digest(excerpt.encode()) == source["excerpt_sha256"], "Source excerpt changed")
        verified.append({key: source[key] for key in ("article_id", "raw_sha256", "line_start", "line_end", "excerpt_sha256")})

    cases = proposal["cases_draft"]
    require(isinstance(cases, list) and cases, "Missing proposal cases")
    require(all(isinstance(case, dict) for case in cases), "Invalid proposal case")
    require(all(case.get("id") for case in cases), "Missing case identity")
    require(len({case["id"] for case in cases}) == len(cases), "Duplicate case identity")
    for index, case in enumerate(cases):
        exam._normalize_case(case, index=index)
        refs = case.get("source_refs")
        require(isinstance(refs, list) and all(isinstance(ref, str) for ref in refs), "Invalid source references")
        require(set(refs).issubset(source_ids), "Unverified case source")
        if case["kind"] == "known_answer":
            require(bool(refs), "Known-answer proposal requires original source")
    require(sum(case["kind"] == "known_answer" for case in cases) >= exam.MIN_KNOWN_ANSWER, "Too few known-answer cases")
    require(sum(case["kind"] == "edge_case" for case in cases) >= exam.MIN_EDGE_CASE, "Missing edge case")
    boundary = proposal["boundary_proposal"]
    require(isinstance(boundary, dict), "Boundary must be an object")
    require(boundary.get("basis") == "proposed_scope_boundary_not_author_quote", "Boundary must disclose proposed scope")
    require(isinstance(boundary.get("text"), str) and bool(boundary["text"].strip()), "Missing proposed boundary")
    current = _score(profile, cases)
    hypothetical = copy.deepcopy(profile)
    hypothetical["honest_boundaries"] = [*profile.get("honest_boundaries", []), boundary["text"]]
    proposed = _score(hypothetical, cases)

    require(live_exam.exists() == exam_present, "Live exam presence changed during preview")
    require(all(digest(path.read_bytes()) == sha for path, sha in tracked.items()), "Input changed during preview")
    return {
        "status": "BLOCKED", "acceptance_passed": False,
        "reason": "human_confirmation_required_even_if_preview_passes",
        "scope": "deterministic_draft_preview_only; no_model_no_apply_no_live_exam_write",
        "user": us.user_id, "perspective_id": pid,
        "proposal_sha256": tracked[proposal_path],
        "profile_sha256": tracked[profile_path],
        "manifest_sha256": tracked[manifest_path],
        "live_exam_present": exam_present,
        "live_exam_sha256": tracked.get(live_exam),
        "honest_boundary_count": len(profile.get("honest_boundaries") or []),
        "sources_verified": verified,
        "current_profile": current,
        "with_proposed_boundary_in_memory": proposed,
        "inputs_unchanged": True,
        "unverified": ["human_approval", "source_semantic_entailment", "model_consumption", "financial_quality", "holdout"],
        "code_sha256": {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in (Path(__file__), Path(exam.__file__), Path(lab.__file__), Path(userspace.__file__), Path(sys.modules[digest.__module__].__file__))},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users-root", type=Path, required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    args = parser.parse_args()
    os.environ[userspace.ENV_USERS_DIR] = str(args.users_root.resolve())
    try:
        report = preview(userspace.user_space(args.user), args.proposal)
    except (ValueError, KeyError, TypeError, OSError):
        # Exceptions may contain private text (e.g. malformed profile/manifest).
        report = {"status": "FAIL", "acceptance_passed": False, "reason": "proposal_or_input_invalid_or_changed"}
    report["audit_revision"] = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
