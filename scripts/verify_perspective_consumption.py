#!/usr/bin/env python3
"""Read-only original -> approved patch -> context assembly verification.

This invokes the existing perspective reader, never an LLM or a writer. PASS is
limited to the patch-managed fields and context assembly, not human authorization,
manual framework fields, actual model consumption, or financial answer quality.
Similarity candidates never authorize a replacement. Optional known-answer exams
check deterministic reconstruction only, not unseen questions or model quality.
Only identifiers, counts and hashes are emitted, not original articles or prompts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence import userspace  # noqa: E402
from intelligence.services import perspective_exam as exam  # noqa: E402
from intelligence.services import perspective_lab as lab  # noqa: E402
from intelligence.services import perspective_learning as learning  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def drift_candidates(value: str, current: list[str]) -> list[dict]:
    """Rank same-field candidates for review; similarity is not equivalence."""
    ranked = sorted(
        enumerate(current),
        key=lambda item: SequenceMatcher(None, value, item[1], autojunk=False).ratio(),
        reverse=True,
    )
    return [
        {
            "profile_index": index,
            "value_sha256": digest(candidate.encode()),
            "similarity": round(SequenceMatcher(None, value, candidate, autojunk=False).ratio(), 6),
        }
        for index, candidate in ranked[:3]
    ]


def verify(
    us: userspace.UserSpace, perspective_id: str, query: str, *,
    check_exam: bool = False, check_delivery: bool = False,
) -> dict:
    pid = lab.resolve_perspective_id(perspective_id)
    root = lab.perspectives_root(us).resolve()
    require(us.root.resolve() == us.root.parent.resolve() / us.user_id, "User root redirects to another identity")
    require(root.is_relative_to(us.root.resolve()), "Perspectives root outside selected user")
    inputs: dict[Path, str] = {}
    issues: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            issues.append(message)

    def read(path: Path) -> bytes:
        resolved = path.resolve()
        require(resolved.is_relative_to(root), "Input outside selected user perspectives")
        data = resolved.read_bytes()
        inputs[resolved] = digest(data)
        return data

    profile = json.loads(read(lab.profile_path(us, pid)))
    require(isinstance(profile, dict) and profile.get("id") == pid, "Profile identity mismatch")
    require(isinstance(profile.get("confidence"), dict), "Invalid profile confidence")
    for field in learning.ALLOWED_PATCH_FIELDS:
        values = profile.get(field, [])
        require(isinstance(values, list) and all(isinstance(v, str) for v in values), f"Invalid profile field: {field}")
    records = [json.loads(line) for line in read(lab.manifest_path(us, pid)).splitlines() if line.strip()]
    require(bool(records), "No article records")
    articles: dict[str, str] = {}
    raw_root = (lab.articles_dir(us, pid) / "raw").resolve()
    for record in records:
        require(isinstance(record, dict), "Invalid article record")
        aid = record.get("article_id")
        require(isinstance(aid, str) and bool(aid) and aid not in articles, "Invalid/duplicate article identity")
        require(bool(record.get("raw_path")), f"Missing original path: {aid}")
        raw = Path(record["raw_path"]).resolve()
        require(raw.is_relative_to(raw_root), f"Original outside selected perspective: {aid}")
        articles[aid] = read(raw).decode("utf-8")
    require(profile.get("confidence", {}).get("article_count") == len(articles), "Article count mismatch")

    patch_paths = sorted(learning.patches_dir(us, pid).glob("pp-*.json"))
    require(bool(patch_paths), "No patch audit trail")
    patches = [json.loads(read(path)) for path in patch_paths]
    history = profile.get("patch_history")
    require(isinstance(history, list) and all(isinstance(h, dict) for h in history), "Missing/invalid patch history")
    counts: Counter[str] = Counter()
    approved_values: list[str] = []
    drift: list[dict] = []
    approved_by_field: dict[str, set[str]] = {field: set() for field in learning.ALLOWED_PATCH_FIELDS}
    quotes_checked = 0
    quotes_verified = 0
    ids: set[str] = set()
    for path, patch in zip(patch_paths, patches):
        require(isinstance(patch, dict), f"Invalid patch: {path.name}")
        patch_id = patch.get("patch_id")
        require(patch_id == path.stem and patch_id not in ids, f"Patch identity mismatch: {path.name}")
        ids.add(patch_id)
        require(patch.get("perspective_id") == pid, f"Wrong perspective: {patch_id}")
        status = patch.get("status")
        require(status in learning.PATCH_STATUSES, f"Invalid patch status: {patch_id}")
        field, value = patch.get("field"), patch.get("value")
        require(field in learning.ALLOWED_PATCH_FIELDS and isinstance(value, str) and bool(value.strip()), f"Invalid patch content: {patch_id}")
        counts[status] += 1
        in_profile = learning._profile_has_value(profile, field, value)
        if status != "approved":
            check(not in_profile, f"Unapproved patch present in profile: {patch_id}")
            continue
        check(bool(patch.get("reviewed_at")), f"Approved patch not reviewed: {patch_id}")
        check(in_profile, f"Approved patch value differs from current profile: {patch_id}")
        if not in_profile:
            drift.append({
                "patch_id": patch_id,
                "field": field,
                "approved_value_sha256": digest(value.encode()),
                "candidates": drift_candidates(value, profile.get(field, [])),
                "interpretation": "structural_similarity_only; review_required; no_auto_apply",
            })
        matches = [h for h in history if h.get("patch_id") == patch_id]
        check(len(matches) == 1, f"Missing/duplicate approval history: {patch_id}")
        if len(matches) == 1:
            h = matches[0]
            check(h.get("action") == "approved" and h.get("field") == field and h.get("value") == value and h.get("at") == patch.get("reviewed_at"), f"Approval history mismatch: {patch_id}")
        evidence = patch.get("evidence")
        check(isinstance(evidence, list) and bool(evidence), f"Missing original evidence: {patch_id}")
        for item in evidence if isinstance(evidence, list) else []:
            require(isinstance(item, dict) and item.get("article_id") in articles, f"Unknown evidence article: {patch_id}")
            quote = learning._norm(item.get("quote", ""))
            supported = len(quote) >= learning.MIN_QUOTE_CHARS and quote in learning._norm(articles[item["article_id"]])
            check(supported, f"Quote not in original: {patch_id}")
            quotes_checked += 1
            quotes_verified += int(supported)
        approved_values.append(value)
        approved_by_field[field].add(learning._norm(value))
    check(bool(approved_values), "No approved patches to verify")
    check(all(h.get("patch_id") in ids for h in history), "History references missing patch files")

    snippets = lab.retrieve_article_snippets(us, pid, query)
    require(bool(snippets), "Query retrieved no original snippets")
    context = lab.build_runtime_context(us, mode="single", perspective_ids=[pid], query=query)
    check(all(value in context.prompt for value in approved_values), "Approved value missing from context")
    require(all(s["excerpt"] in context.prompt for s in snippets), "Original snippet missing from context")
    current_values = [value for field in learning.ALLOWED_PATCH_FIELDS for value in profile.get(field, [])]
    current_values_present = all(value in context.prompt for value in current_values)
    check(current_values_present, "Current profile value missing from context")
    neutral = lab.build_runtime_context(us, mode="neutral", perspective_ids=[], query=query)
    require(all(value not in neutral.prompt for value in approved_values), "Perspective value leaked into neutral context")
    require(all(value not in neutral.prompt for value in current_values if value), "Current profile value leaked into neutral context")
    exam_result = None
    exam_file = exam.exam_path(us, pid)
    exam_exists = exam_file.exists()
    if check_exam:
        if exam_exists:
            read(exam_file)
        result = exam.run_exam(us, pid)
        exam_result = {
            key: result[key]
            for key in ("passed", "reason", "known_answer", "edge_case")
        }
        exam_result["scope"] = "existing_deterministic_suite_only; no_model_or_holdout"
        exam_result["cases"] = [
            {
                **{key: row[key] for key in ("id", "kind", "passed")},
                "reason_count": len(row["reasons"]),
                "reason_sha256": [digest(reason.encode()) for reason in row["reasons"]],
            }
            for row in result["results"]
        ]
        check(result["passed"], "Known-answer exam not passed")
    delivery_result = None
    if check_delivery:
        from scripts.perspective_request_capture import verify_delivery

        delivery_result = verify_delivery(us, pid, query, context.prompt)
        check(delivery_result["status"] == "PASS", "Offline provider request delivery failed")
    if check_exam:
        require(exam_file.exists() == exam_exists, "Exam presence changed during verification")
    require(all(digest(path.read_bytes()) == sha for path, sha in inputs.items()), "Input changed during verification")
    require(sorted(learning.patches_dir(us, pid).glob("pp-*.json")) == patch_paths, "Patch set changed during verification")
    code_paths = [Path(lab.__file__), Path(learning.__file__), Path(userspace.__file__)]
    if check_exam:
        code_paths.append(Path(exam.__file__))
    if check_delivery:
        for module in (
            "scripts.perspective_request_capture",
            "intelligence.runtime.turn_control_core",
            "intelligence.runtime.continuous_turn_adapter",
            "intelligence.runtime.glm_agent_runtime",
            "intelligence.runtime.agent_episode",
            "intelligence.services.episode_factory",
            "intelligence.services.episode_protocol",
            "intelligence.services.research_harness",
        ):
            code_paths.append(Path(sys.modules[module].__file__))
    return {
        "status": "FAIL" if issues else "PASS",
        "issues": issues,
        "scope": "recorded_patches_and_offline_context_assembly_only"
        + ("; known_answer_exam" if check_exam else "")
        + ("; offline_first_provider_request" if check_delivery else ""),
        "sampled_at": datetime.now(timezone.utc).isoformat(),
        "user": us.user_id,
        "users_root": str(us.root.parent.resolve()),
        "perspective_id": pid,
        "query": query,
        "article_count": len(articles),
        "patch_status_counts": dict(counts),
        "quotes_checked": quotes_checked,
        "quotes_verified": quotes_verified,
        "approved_values_in_context": sum(value in context.prompt for value in approved_values),
        "approved_value_drift": drift,
        "current_profile_assembly": {
            "status": "PASS" if current_values_present else "FAIL",
            "scope": "current_patch_managed_field_values_only; not_approval_or_quality",
            "values": len(current_values),
            "values_in_context": sum(value in context.prompt for value in current_values),
        },
        "known_answer_exam": exam_result,
        "offline_request_delivery": delivery_result,
        "profile_values_without_patch_receipt": {
            field: sum(learning._norm(value) not in approved_by_field[field] for value in profile.get(field, []))
            for field in learning.ALLOWED_PATCH_FIELDS
        },
        "snippets_in_context": len(snippets),
        "context_sha256": digest(context.prompt.encode()),
        "neutral_excludes_approved_values": True,
        "neutral_excludes_current_values": True,
        "inputs_unchanged": True,
        "input_sha256": {str(path.relative_to(root)): sha for path, sha in sorted(inputs.items())},
        "code_sha256": {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in code_paths},
        "unverified": ["manual_framework_fields", "profile_values_without_patch_receipt", "human_review_authority", "api_routing_and_session_selection", "model_consumption", "answer_quality", "historical_cutoff"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users-root", type=Path, required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--perspective", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--check-exam", action="store_true", help="Also run the existing read-only known-answer exam; missing is FAIL")
    parser.add_argument("--check-delivery", action="store_true", help="Capture the first GLM request offline; no network/model/tools")
    args = parser.parse_args()
    os.environ[userspace.ENV_USERS_DIR] = str(args.users_root.resolve())
    try:
        report = verify(
            userspace.user_space(args.user), args.perspective, args.query,
            check_exam=args.check_exam, check_delivery=args.check_delivery,
        )
    except (ValueError, KeyError, TypeError, OSError) as exc:
        report = {"status": "FAIL", "scope": "offline_context_assembly_only", "error": str(exc)}
    report["audit_revision"] = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    report["audit_script_sha256"] = digest(Path(__file__).read_bytes())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
