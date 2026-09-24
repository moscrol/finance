import json
import socket
from pathlib import Path

import pytest

from intelligence import userspace
from intelligence.services import perspective_exam as exam
from intelligence.services import perspective_lab as lab
from scripts import preview_perspective_exam as probe


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.setenv(userspace.ENV_USERS_DIR, str(tmp_path / "users"))
    monkeypatch.setattr(socket.socket, "connect", lambda *_: pytest.fail("No network in preview"))
    us = userspace.user_space("alice")
    lab.init_perspective(us, "teacher", ptype="blogger")
    profile = lab.load_profile(us, "teacher")
    profile["risk_triggers"] = ["caution"]
    profile["opportunity_preferences"] = ["growth"]
    profile["anti_patterns"] = ["PRIVATE_PROFILE_TEXT"]
    lab.profile_path(us, "teacher").write_text(json.dumps(profile), encoding="utf-8")
    original = tmp_path / "original.md"
    original.write_text("PRIVATE_SOURCE_TEXT\nprivate caution\nprivate growth", encoding="utf-8")
    lab.ingest_article(us, "teacher", original, title="Fixture", date="2026-01-01")
    record = lab._read_manifest(lab.manifest_path(us, "teacher"))[0]
    raw = Path(record["raw_path"])
    source = {
        "article_id": record["article_id"], "date": record["date"], "title": record["title"],
        "raw_sha256": probe.digest(raw.read_bytes()), "line_start": 1, "line_end": 3,
        "excerpt_sha256": probe.digest(raw.read_bytes()),
    }
    cases = [
        {"id": "risk-1", "kind": "known_answer", "question": "Risk?", "facts": "private caution",
         "expected_direction": "risk", "expected_field": "risk_triggers", "expected_terms": ["caution"],
         "source_refs": [record["article_id"]]},
        {"id": "opportunity-1", "kind": "known_answer", "question": "Opportunity?", "facts": "private growth",
         "expected_direction": "opportunity", "expected_field": "opportunity_preferences", "expected_terms": ["growth"],
         "source_refs": [record["article_id"]]},
        {"id": "edge-1", "kind": "edge_case", "question": "uncovered", "source_refs": []},
    ]
    packet = {
        "proposal_status": "pending_human_review", "user_approval": None, "perspective_id": "teacher",
        "sources": [source], "cases_draft": cases,
        "boundary_proposal": {"basis": "proposed_scope_boundary_not_author_quote", "text": "uncovered"},
    }
    proposal = tmp_path / "proposal.json"
    proposal.write_text(json.dumps(packet), encoding="utf-8")
    return us, proposal, raw


def change(path, update):
    value = json.loads(path.read_text())
    update(value)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_readonly_preview_never_approves_even_when_hypothetical_passes(sample):
    us, proposal, _ = sample
    before = {p: p.read_bytes() for p in us.root.rglob("*") if p.is_file()}
    report = probe.preview(us, proposal)
    assert report["status"] == "BLOCKED"
    assert not report["acceptance_passed"]
    assert not report["current_profile"]["all_cases_passed"]
    assert report["with_proposed_boundary_in_memory"]["all_cases_passed"]
    assert not report["live_exam_present"]
    assert {p: p.read_bytes() for p in us.root.rglob("*") if p.is_file()} == before
    encoded = json.dumps(report)
    for text in ("PRIVATE_SOURCE_TEXT", "PRIVATE_PROFILE_TEXT", "private caution", "private growth"):
        assert text not in encoded


def test_proposal_cannot_be_mistaken_for_a_passing_live_exam(sample):
    us, proposal, _ = sample
    target = exam.exam_path(us, "teacher")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(proposal.read_bytes())
    result = exam.run_exam(us, "teacher")
    assert not result["passed"]
    assert result["known_answer"] == result["edge_case"] == 0


@pytest.mark.parametrize("update", [
    lambda p: p.update(proposal_status="approved"),
    lambda p: p.update(user_approval="agent"),
    lambda p: p["cases_draft"][0].update(source_refs=[]),
    lambda p: p["cases_draft"][0].update(source_refs=["unknown"]),
    lambda p: p["cases_draft"][0].update(expected_terms=[]),
    lambda p: p["cases_draft"][1].update(id="risk-1"),
    lambda p: p["cases_draft"].pop(),
    lambda p: p["sources"][0].update(raw_sha256="wrong"),
    lambda p: p["sources"][0].update(excerpt_sha256="wrong"),
    lambda p: p["sources"][0].update(line_end=99),
    lambda p: p["sources"][0].update(line_start=True),
    lambda p: p["boundary_proposal"].update(basis="author_quote"),
])
def test_invalid_proposals_fail_without_writing_user_state(sample, update):
    us, proposal, _ = sample
    change(proposal, update)
    with pytest.raises(ValueError):
        probe.preview(us, proposal)
    assert not exam.exam_path(us, "teacher").exists()


def test_source_cannot_redirect_to_other_user(sample, tmp_path):
    us, proposal, raw = sample
    other = tmp_path / "other.md"
    other.write_bytes(raw.read_bytes())
    manifest = lab.manifest_path(us, "teacher")
    change(manifest, lambda row: row.update(raw_path=str(other)))
    with pytest.raises(ValueError, match="outside selected perspective"):
        probe.preview(us, proposal)


@pytest.mark.parametrize("target", ["proposal", "profile", "source", "exam", "existing_exam"])
def test_concurrent_changes_are_rejected(sample, monkeypatch, target):
    us, proposal, raw = sample
    if target == "existing_exam":
        path = exam.exam_path(us, "teacher")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"cases": []}', encoding="utf-8")
    original = exam.score_case

    def changing_score(profile, case):
        if target == "proposal":
            change(proposal, lambda p: p.update(note="changed"))
        elif target == "profile":
            change(lab.profile_path(us, "teacher"), lambda p: p.update(note="changed"))
        elif target == "source":
            raw.write_text("changed", encoding="utf-8")
        else:
            path = exam.exam_path(us, "teacher")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
        return original(profile, case)

    monkeypatch.setattr(exam, "score_case", changing_score)
    with pytest.raises(ValueError, match="changed during preview"):
        probe.preview(us, proposal)


def test_cli_failure_does_not_print_private_exception(sample, monkeypatch, capsys):
    us, proposal, _ = sample
    monkeypatch.setattr("sys.argv", ["preview", "--users-root", str(us.root.parent), "--user", "alice", "--proposal", str(proposal)])
    monkeypatch.setattr(probe, "preview", lambda *_: (_ for _ in ()).throw(ValueError("PRIVATE_REASON")))
    assert probe.main() == 1
    output = capsys.readouterr().out
    assert "PRIVATE_REASON" not in output
    assert json.loads(output)["status"] == "FAIL"


def test_cli_pending_proposal_is_nonzero_not_acceptance(sample, monkeypatch, capsys):
    us, proposal, _ = sample
    monkeypatch.setattr("sys.argv", ["preview", "--users-root", str(us.root.parent), "--user", "alice", "--proposal", str(proposal)])
    assert probe.main() == 2
    assert json.loads(capsys.readouterr().out)["status"] == "BLOCKED"


@pytest.fixture
def candidate(sample, tmp_path):
    us, proposal, _ = sample
    packet = json.loads(proposal.read_text())
    article_id = packet["sources"][0]["article_id"]
    patch = {
        "patch_id": "pp-0123456789ab", "perspective_id": "teacher", "status": "approved",
        "field": "opportunity_preferences", "value": "growth",
        "evidence": [{"article_id": article_id}],
    }
    path = probe.learning.patch_path(us, "teacher", patch["patch_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(patch))
    target = tmp_path / "candidate.json"
    target.write_text(json.dumps({
        "status": "isolated_candidate", "perspective_id": "teacher",
        "proposal_sha256": probe.digest(proposal.read_bytes()),
        "profile_sha256": probe.digest(lab.profile_path(us, "teacher").read_bytes()),
        "entries": [{"patch_id": patch["patch_id"], "patch_sha256": probe.digest(path.read_bytes()),
                     "source_refs": [article_id], "rule": {
                         "field": patch["field"], "value_sha256": probe.digest(b"growth"),
                         "all_of": [["private"], ["growth"]], "none_of": [],
                     }}],
    }))
    return target, path


def test_candidate_rules_are_in_memory_only_and_do_not_grant_approval(sample, candidate):
    us, proposal, _ = sample
    target, _ = candidate
    before = {p: p.read_bytes() for p in us.root.rglob("*") if p.is_file()}
    report = probe.preview(us, proposal, target)
    assert report["with_proposed_rules_and_boundary_in_memory"]["all_cases_passed"]
    assert report["candidate_rule_count"] == 1
    assert report["status"] == "BLOCKED" and not report["acceptance_passed"]
    assert {p: p.read_bytes() for p in us.root.rglob("*") if p.is_file()} == before
    assert "private growth" not in json.dumps(report)
    assert "all_of" not in json.dumps(report)


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(status="approved"),
    lambda p: p.update(perspective_id="another"),
    lambda p: p.update(proposal_sha256="wrong"),
    lambda p: p.update(profile_sha256="wrong"),
    lambda p: p.update(entries=[]),
    lambda p: p["entries"][0].update(patch_sha256="wrong"),
    lambda p: p["entries"][0].update(source_refs=["pa-unknown"]),
    lambda p: p["entries"][0]["rule"].update(value_sha256="wrong"),
    lambda p: p["entries"][0]["rule"].update(field="risk_triggers"),
])
def test_invalid_candidate_rejected(sample, candidate, mutate):
    us, proposal, _ = sample
    target, _ = candidate
    change(target, mutate)
    with pytest.raises(ValueError):
        probe.preview(us, proposal, target)


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(status="pending"),
    lambda p: p.update(perspective_id="another"),
    lambda p: p.update(patch_id="pp-aaaaaaaaaaaa"),
    lambda p: p.update(evidence=[]),
])
def test_candidate_requires_matching_approved_patch(sample, candidate, mutate):
    us, proposal, _ = sample
    target, patch = candidate
    change(patch, mutate)
    change(target, lambda p: p["entries"][0].update(patch_sha256=probe.digest(patch.read_bytes())))
    with pytest.raises(ValueError):
        probe.preview(us, proposal, target)


@pytest.mark.parametrize("which", ["candidate", "patch", "profile", "exam"])
def test_candidate_phase_concurrent_changes_fail_closed(sample, candidate, monkeypatch, which):
    us, proposal, _ = sample
    target, patch = candidate
    original = probe._score

    def mutate_after_loading(profile, cases):
        result = original(profile, cases)
        if profile.get("signal_match_rules"):
            if which == "candidate":
                change(target, lambda p: p.update(note="changed"))
            elif which == "patch":
                change(patch, lambda p: p.update(status="rejected"))
            elif which == "profile":
                change(lab.profile_path(us, "teacher"), lambda p: p.update(note="changed"))
            else:
                path = exam.exam_path(us, "teacher")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}")
        return result

    monkeypatch.setattr(probe, "_score", mutate_after_loading)
    with pytest.raises(ValueError, match="changed during preview"):
        probe.preview(us, proposal, target)
