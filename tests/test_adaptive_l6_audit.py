"""L6 must reject known lost claims and refuse incomplete acceptance evidence."""

from copy import deepcopy
import ast
import hashlib
import json
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.request

import pytest

from scripts.review_probes.adaptive_l6_batch import await_source_audit, run_audited_batch
from scripts.review_probes.audit_adaptive_l6 import audit
from scripts.review_probes.prepare_adaptive_l6 import (
    clone,
    manifest,
    validate_authorization,
)


def sample():
    sentence = "Amount below 1295.97 is the proposed invalidation condition."
    episode = {
        "repair_attempts": 1,
        "events": [
            {
                "kind": "model_turn",
                "sequence": i,
                "payload": {
                    "content": json.dumps({"draft": draft}),
                    "served_model": "test-model",
                    "phase": "repair" if i else None,
                },
            }
            for i, draft in enumerate(("first draft", sentence))
        ],
        "outcome": {
            "draft": sentence,
            "evidence": [
                {
                    "content_hash": "e1",
                    "detail": "2026-09-10 amount in 100m CNY: 1295.9673",
                }
            ],
        },
        "semantic_verifier": {
            "judge_status": "repaired",
            "judge_mode": "llm",
            "sentence_verdicts": [{"sentence": sentence, "decision": "deleted"}],
        },
    }
    review = {
        "episode_sha256": "hash",
        "all_numeric_conditions_reviewed": True,
        "claims": [
            {
                "sentence": sentence,
                "evidence_hash": "e1",
                "source_excerpt": "2026-09-10 amount in 100m CNY: 1295.9673",
                "entity_matches": True,
                "date_matches": True,
                "window_matches": True,
                "unit_matches": True,
                "numeric_supported": True,
                "condition_retained_in_public": False,
            }
        ],
        "late_reports": [],
    }
    return episode, review


def test_repaired_status_cannot_hide_a_source_supported_lost_condition():
    episode, review = sample()
    result = audit(episode, review, episode_sha256="hash")
    assert result["verdict"] == "NOT_PASSED"
    assert result["model_revision_observed"]
    assert len(result["supported_conditions_lost"]) == 1


@pytest.mark.parametrize("fault", ["identity", "source", "draft"])
def test_bad_review_binding_fails_closed(fault):
    episode, review = sample()
    if fault == "identity":
        review["episode_sha256"] = "other"
    elif fault == "source":
        review["claims"][0]["source_excerpt"] = "invented support"
    else:
        review["claims"][0]["sentence"] = "another claim"
    with pytest.raises(ValueError):
        audit(episode, review, episode_sha256="hash")


def test_incomplete_review_and_unobserved_mechanisms_are_not_pass():
    episode, review = sample()
    episode["semantic_verifier"]["sentence_verdicts"] = []
    review["claims"][0]["condition_retained_in_public"] = True
    review["all_numeric_conditions_reviewed"] = False
    assert (
        audit(episode, review, episode_sha256="hash")["verdict"]
        == "BLOCKED_CLAIM_REVIEW"
    )
    review["all_numeric_conditions_reviewed"] = True
    assert audit(episode, review, episode_sha256="hash")["verdict"] == "NOT_EXERCISED"
    review["late_reports"] = [{"adopted": False, "artifact_pointer": "fixture:late"}]
    assert audit(episode, review, episode_sha256="hash")["verdict"] == "PASS"
    episode["events"][1] = deepcopy(episode["events"][0])
    assert audit(episode, review, episode_sha256="hash")["verdict"] == "NOT_EXERCISED"


@pytest.mark.parametrize("missing", ["claims", "repair_phase", "served_model"])
def test_no_vacuous_pass_without_supported_claim_or_actual_model_revision(missing):
    episode, review = sample()
    episode["semantic_verifier"]["sentence_verdicts"] = []
    review["late_reports"] = [{"adopted": False, "artifact_pointer": "fixture:late"}]
    if missing == "claims":
        review["claims"] = []
    elif missing == "repair_phase":
        episode["events"][1]["payload"]["phase"] = None
    else:
        episode["events"][1]["payload"]["served_model"] = None
    assert audit(episode, review, episode_sha256="hash")["verdict"] == "NOT_EXERCISED"


def test_adopted_late_report_fails_even_without_repair():
    episode, review = sample()
    episode["repair_attempts"] = 0
    review["claims"] = []
    review["late_reports"] = [{"adopted": True, "artifact_pointer": "fixture:late"}]
    assert audit(episode, review, episode_sha256="hash")["verdict"] == "NOT_PASSED"


@pytest.mark.parametrize("mode", [
    "pass", "lost_condition", "judge_unavailable", "not_exercised", "missing_review",
    "wrong_episode", "malformed_review", "late_pass", "failed_run", "pending_delivery",
])
def test_content_gate_controls_real_loopback_submissions(tmp_path, mode):
    requests = []
    events = []
    clock = [0.0]

    class Peer(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            question = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(question["id"])
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

    def submit(question):
        req = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/submit",
            data=json.dumps(question).encode(), method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as response:
            assert response.status == 200
        return {"id": question["id"], "status": "failed" if mode == "failed_run" else "completed",
                "delivery_pending": mode == "pending_delivery"}

    def check(question, result, deadline):
        assert requests[-1] == result["id"] == question["id"]
        episode, review = sample()
        episode["semantic_verifier"]["sentence_verdicts"] = []
        review["claims"][0]["condition_retained_in_public"] = True
        review["late_reports"] = [{"adopted": False, "artifact_pointer": "fixture:late"}]
        if mode == "lost_condition":
            episode["semantic_verifier"]["sentence_verdicts"] = sample()[0]["semantic_verifier"]["sentence_verdicts"]
            review["claims"][0]["condition_retained_in_public"] = False
        elif mode == "judge_unavailable":
            episode["semantic_verifier"]["judge_status"] = "unavailable"
        elif mode == "not_exercised":
            review["late_reports"] = []
        ep = tmp_path / f"{question['id']}.episode.json"
        source = tmp_path / f"{question['id']}.review.json"
        ep.write_text(json.dumps(episode))
        review["episode_sha256"] = hashlib.sha256(ep.read_bytes()).hexdigest()
        if mode == "wrong_episode":
            review["episode_sha256"] = "wrong"
        if mode != "missing_review":
            source.write_text("{" if mode == "malformed_review" else json.dumps(review))

        def advance(seconds):
            clock[0] += seconds

        checked = await_source_audit(ep, source, deadline=deadline, clock=lambda: clock[0], sleep=advance)
        if mode == "late_pass":
            assert checked["verdict"] == "PASS"
            clock[0] = deadline
        return checked

    server = ThreadingHTTPServer(("127.0.0.1", 0), Peer)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    try:
        result = run_audited_batch(
            [{"id": "N1"}, {"id": "N2"}], submit=submit, audit_question=check,
            record=events.append, audit_seconds=1, clock=lambda: clock[0],
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert requests == (["N1", "N2"] if mode == "pass" else ["N1"])
    assert result["all_passed"] is (mode == "pass")
    if mode == "pass":
        assert [(e["event"], e["question"]) for e in events] == [
            (event, question) for question in ("N1", "N2")
            for event in ("submit_admitted", "awaiting_source_audit", "source_audit_complete")
        ]
    else:
        assert events[-1]["event"] == "batch_stopped"
        assert result["stopped_for"]["question"] == "N1"


@pytest.mark.parametrize("seconds", [0, -1, 301, float("inf"), float("nan")])
def test_content_gate_invalid_budget_sends_nothing(seconds):
    dispatched = []
    with pytest.raises(ValueError):
        run_audited_batch(
            [{"id": "N1"}], submit=dispatched.append,
            audit_question=lambda *_: {"verdict": "PASS"}, record=lambda _: None,
            audit_seconds=seconds,
        )
    assert not dispatched


def test_manifest_refuses_symlinks(tmp_path):
    (tmp_path / "link").symlink_to("/does-not-exist")
    with pytest.raises(ValueError):
        manifest(tmp_path)


def test_clone_never_overwrites_an_existing_input(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.write_text("original")
    target.write_text("frozen")
    with pytest.raises(ValueError):
        clone(source, target)
    assert target.read_text() == "frozen"


def protocol():
    template = (
        Path(__file__).resolve().parents[1]
        / "docs/verification/2026-09-23-adaptive-l6-preflight/protocol.draft.json"
    )
    result = json.loads(template.read_text())
    result["authorization"]["approved"] = True
    result["baseline"]["amendment_approved"] = True
    result["questions"] = [
        {
            "id": str(i),
            "text": str(i),
            "text_sha256": hashlib.sha256(str(i).encode()).hexdigest(),
        }
        for i in range(3)
    ]
    return result


def test_fresh_runner_wires_source_audit_and_inherits_no_receipts(tmp_path):
    from scripts.review_probes.prepare_adaptive_l6_runner import ARCHIVE, prepare

    original = {p: p.read_bytes() for p in ARCHIVE.rglob("*") if p.is_file()}
    root = tmp_path / "fresh"
    receipt = prepare(root, protocol())
    assert receipt["real_model_requests"] == 0
    assert receipt["receipts_inherited"] is False
    tree = ast.parse((root / "run_live_l6.py").read_text())
    compile(tree, "run_live_l6.py", "exec")
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert sum(isinstance(c.func, ast.Name) and c.func.id == "run_audited_batch" for c in calls) == 1
    assert sum(isinstance(c.func, ast.Name) and c.func.id == "await_source_audit" for c in calls) == 1
    admission = [c for c in calls if isinstance(c.func, ast.Name) and c.func.id == "validate_deadline_admission"]
    assert len(admission) == 1
    sidecars = [c for c in calls if isinstance(c.func, ast.Attribute) and c.func.attr == "Popen"]
    assert sidecars and all(admission[0].lineno < call.lineno for call in sidecars)
    assert not any(isinstance(node, ast.For) and isinstance(node.iter, ast.Name) and node.iter.id == "QUESTIONS"
                   for node in ast.walk(tree))
    assert not (root / "source-regression.json").exists()
    assert not (root / "proxy-offline-check.json").exists()
    with pytest.raises(FileExistsError):
        prepare(root, protocol())
    with pytest.raises(ValueError, match="sealed evidence"):
        prepare(ARCHIVE / "must-not-exist", protocol())
    assert original == {p: p.read_bytes() for p in original}


def test_authorized_original_scope_is_valid():
    validate_authorization(protocol())


@pytest.mark.parametrize(
    "fault", ["unauthorized", "order", "resubmit", "question", "hash", "merge"]
)
def test_prepare_rejects_scope_expansion_or_missing_approval(fault):
    value = protocol()
    if fault == "unauthorized":
        value["authorization"]["approved"] = False
    elif fault == "order":
        value["baseline"]["amendment_approved"] = False
    elif fault == "resubmit":
        value["limits"]["resubmissions"] = 1
    elif fault == "question":
        value["questions"].append(value["questions"][0])
    elif fault == "hash":
        value["questions"][0]["text"] = "changed"
    else:
        value["limits"]["merge_main"] = True
    with pytest.raises(ValueError):
        validate_authorization(value)
