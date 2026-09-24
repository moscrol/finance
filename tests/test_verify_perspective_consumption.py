import json
import re
from pathlib import Path

import pytest

from intelligence import userspace
from intelligence.services import perspective_lab as lab
from intelligence.services import perspective_learning as learning
from scripts.verify_perspective_consumption import verify


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.setenv(userspace.ENV_USERS_DIR, str(tmp_path / "users"))
    us = userspace.user_space("alice")
    lab.init_perspective(us, "sample", ptype="blogger")
    original = tmp_path / "original.md"
    original.write_text("volume must confirm a breakout; volume; before taking risk", encoding="utf-8")
    lab.ingest_article(us, "sample", original, title="Volume", date="2026-09-01")
    record = lab._read_manifest(lab.manifest_path(us, "sample"))[0]
    field = "risk_triggers"
    value = "Check volume before taking risk"
    patch_id = learning._patch_id("sample", field, value)
    path = learning.patch_path(us, "sample", patch_id)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "patch_id": patch_id, "perspective_id": "sample", "field": field,
        "value": value, "status": "pending",
        "evidence": [{"article_id": record["article_id"], "quote": "volume must confirm a breakout"}],
    }), encoding="utf-8")
    learning.review_patch(us, "sample", patch_id, approve=True)
    return us, path, record


def rewrite(path, change):
    value = json.loads(path.read_text(encoding="utf-8"))
    change(value)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_verifies_original_approval_and_context_without_model(sample, monkeypatch):
    us, _, _ = sample
    monkeypatch.setattr(learning, "_default_llm_complete", lambda *_: pytest.fail("Model must not run"))
    result = verify(us, "sample", "volume")
    assert result["status"] == "PASS"
    assert result["article_count"] == 1
    assert result["patch_status_counts"] == {"approved": 1}
    assert result["quotes_checked"] == result["snippets_in_context"] == 1
    assert result["inputs_unchanged"]
    assert result["neutral_excludes_approved_values"]
    assert "model_consumption" in result["unverified"]
    assert "human_review_authority" in result["unverified"]
    assert "volume must confirm a breakout" not in json.dumps(result)


@pytest.mark.parametrize("change,error", [
    (lambda p: p.update(status="pending"), "Unapproved patch"),
    (lambda p: p.update(status="rejected"), "Unapproved patch"),
    (lambda p: p.update(status="unknown"), "Invalid patch status"),
    (lambda p: p.update(perspective_id="other"), "Wrong perspective"),
    (lambda p: p.update(reviewed_at=None), "not applied/reviewed"),
    (lambda p: p.update(evidence=[]), "Missing original evidence"),
    (lambda p: p["evidence"][0].update(quote="unsupported text"), "Quote not in original"),
    (lambda p: p["evidence"][0].update(article_id="unknown"), "Unknown evidence article"),
])
def test_patch_negative_controls(sample, change, error):
    us, path, _ = sample
    rewrite(path, change)
    try:
        result = verify(us, "sample", "volume")
    except ValueError as exc:
        assert re.search(error, str(exc))
    else:
        assert result["status"] == "FAIL"
        assert any(re.search(error, issue) for issue in result["issues"])


def test_missing_history_does_not_pass(sample):
    us, _, _ = sample
    rewrite(lab.profile_path(us, "sample"), lambda p: p.update(patch_history=[]))
    result = verify(us, "sample", "volume")
    assert result["status"] == "FAIL"
    assert any("approval history" in issue for issue in result["issues"])


def test_missing_original_does_not_pass(sample):
    us, _, record = sample
    Path(record["raw_path"]).unlink()
    with pytest.raises(FileNotFoundError):
        verify(us, "sample", "volume")


def test_cross_user_manifest_cannot_supply_original(sample, tmp_path):
    us, _, record = sample
    record["raw_path"] = str(tmp_path / "other-user.md")
    lab.manifest_path(us, "sample").write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="outside selected perspective"):
        verify(us, "sample", "volume")


def test_empty_retrieval_is_not_consumption(sample):
    us, _, _ = sample
    with pytest.raises(ValueError, match="no original snippets"):
        verify(us, "sample", "unmatchabletokenxyz")


def test_input_changes_during_assembly_fail_closed(sample, monkeypatch):
    us, path, _ = sample
    original = lab.build_runtime_context

    def changing_context(*args, **kwargs):
        context = original(*args, **kwargs)
        rewrite(path, lambda p: p.update(review_note="concurrent change"))
        return context

    monkeypatch.setattr(lab, "build_runtime_context", changing_context)
    with pytest.raises(ValueError, match="Input changed"):
        verify(us, "sample", "volume")


def test_unapproved_unapplied_patch_is_reported_not_used(sample):
    us, _, _ = sample
    value = "This candidate must not be applied"
    patch_id = learning._patch_id("sample", "risk_triggers", value)
    learning.patch_path(us, "sample", patch_id).write_text(json.dumps({
        "patch_id": patch_id, "perspective_id": "sample", "field": "risk_triggers",
        "value": value, "status": "pending",
    }), encoding="utf-8")
    result = verify(us, "sample", "volume")
    assert result["patch_status_counts"] == {"approved": 1, "pending": 1}


def test_empty_other_user_does_not_fall_back_to_owner(sample):
    other = userspace.user_space("bob")
    with pytest.raises(FileNotFoundError):
        verify(other, "sample", "volume")
    assert not other.root.exists()


def test_symlinked_user_root_cannot_borrow_another_identity(sample):
    owner, _, _ = sample
    other = userspace.user_space("bob")
    other.root.symlink_to(owner.root, target_is_directory=True)
    with pytest.raises(ValueError, match="another identity"):
        verify(other, "sample", "volume")


def test_invalid_profile_shape_cannot_pass(sample):
    us, _, _ = sample
    rewrite(lab.profile_path(us, "sample"), lambda p: p.update(confidence=None))
    with pytest.raises(ValueError, match="Invalid profile confidence"):
        verify(us, "sample", "volume")


def test_manual_values_have_explicit_unverified_scope(sample):
    us, _, _ = sample
    rewrite(lab.profile_path(us, "sample"), lambda p: p["risk_triggers"].append("Manual rule"))
    result = verify(us, "sample", "volume")
    assert result["status"] == "PASS"
    assert result["profile_values_without_patch_receipt"]["risk_triggers"] == 1
    assert "profile_values_without_patch_receipt" in result["unverified"]
