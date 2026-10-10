"""Test capture identity and output safety, never require incorrect admission."""
from __future__ import annotations

import hashlib

import pytest

from scripts.review_probes import prior_evidence_boundary_review as probe


REVISION = "a" * 40


@pytest.fixture
def target(tmp_path, monkeypatch):
    tree = tmp_path / "target"
    tree.mkdir()
    for source in probe.SOURCES:
        path = tree / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# synthetic preflight source\n")
    responses = {
        ("rev-parse", "--show-toplevel"): str(tree),
        ("rev-parse", "HEAD"): REVISION,
        ("status", "--porcelain"): "",
    }
    monkeypatch.setattr(probe, "_git", lambda _tree, *args: responses[args])
    return tree, tmp_path / "capture", responses


def test_preflight_fingerprints_sources_before_any_output_is_created(target):
    tree, output, _ = target
    checked, destination, hashes = probe._preflight(tree, REVISION, output)
    assert (checked, destination) == (tree, output)
    assert set(hashes) == set(probe.SOURCES)
    for source, digest in hashes.items():
        assert digest == hashlib.sha256((tree / source).read_bytes()).hexdigest()
    assert not output.exists()


@pytest.mark.parametrize("revision", ["a" * 12, "A" * 40, "HEAD", "a" * 39])
def test_rejects_unpinned_revision(target, revision):
    tree, output, _ = target
    with pytest.raises(ValueError, match="full lowercase"):
        probe._preflight(tree, revision, output)
    assert not output.exists()


@pytest.mark.parametrize("change", ["head", "dirty", "subdirectory"])
def test_rejects_wrong_or_moving_checkout_identity(target, change):
    tree, output, responses = target
    if change == "head":
        responses[("rev-parse", "HEAD")] = "b" * 40
    elif change == "dirty":
        responses[("status", "--porcelain")] = " M product.py"
    else:
        responses[("rev-parse", "--show-toplevel")] = str(tree.parent)
    with pytest.raises(ValueError):
        probe._preflight(tree, REVISION, output)
    assert not output.exists()


@pytest.mark.parametrize("location", ["tree", "child", "parent", "symlink-child"])
def test_output_is_not_inside_or_around_target_checkout(target, location):
    tree, output, _ = target
    if location == "tree":
        output = tree
    elif location == "child":
        output = tree / "capture"
    elif location == "parent":
        output = tree.parent
    else:
        link = output.parent / "target-alias"
        link.symlink_to(tree, target_is_directory=True)
        output = link / "capture"
    with pytest.raises(ValueError, match="outside and separate"):
        probe._preflight(tree, REVISION, output)
    assert not (tree / "capture").exists()


def test_existing_attempt_is_preserved(target):
    tree, output, _ = target
    output.mkdir()
    original = output / "failure.txt"
    original.write_text("keep failed attempt")
    with pytest.raises(ValueError, match="new directory"):
        probe._preflight(tree, REVISION, output)
    assert original.read_text() == "keep failed attempt"


def test_missing_target_capability_fails_before_creating_attempt(target):
    tree, output, _ = target
    (tree / probe.SOURCES[0]).unlink()
    with pytest.raises(FileNotFoundError):
        probe._preflight(tree, REVISION, output)
    assert not output.exists()


def test_case_matrix_keeps_controls_separate_from_changed_boundaries():
    cases = {name: (old, new, expected) for name, old, new, expected in probe.CASES}
    assert len(cases) == 4
    assert cases["same_inclusive_control"][0] == cases["same_inclusive_control"][1]
    assert cases["same_inclusive_control"][2] is True
    for name in ("inclusive_to_exclusive", "from_to_after"):
        old, new, expected = cases[name]
        assert "（含当日）" in old and "（不含当日）" in new
        assert expected is False
    assert cases["different_date_control"][2] is False
    # No test treats actual false-positive admission as desired product behavior.
