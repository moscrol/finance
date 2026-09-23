"""L6 must reject known lost claims and refuse incomplete acceptance evidence."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

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
