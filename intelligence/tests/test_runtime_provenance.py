from __future__ import annotations

from pathlib import Path

from intelligence.services.runtime_provenance import build_runtime_provenance


def test_runtime_provenance_has_revision_and_dependency_fingerprint() -> None:
    payload = build_runtime_provenance(Path(__file__).resolve().parents[2])

    assert payload["source_revision"]
    assert len(str(payload["dependency_fingerprint"])) == 64
    assert payload["python_executable"]
    assert isinstance(payload["dependencies"], dict)
