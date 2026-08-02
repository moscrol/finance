from __future__ import annotations

from pathlib import Path

import intelligence

from intelligence.services.runtime_provenance import build_runtime_provenance


def test_runtime_provenance_has_revision_and_dependency_fingerprint() -> None:
    payload = build_runtime_provenance(Path(__file__).resolve().parents[2])

    assert payload["source_revision"]
    assert len(str(payload["dependency_fingerprint"])) == 64
    assert payload["python_executable"]
    assert isinstance(payload["dependencies"], dict)


def test_runtime_provenance_reports_actual_import_root() -> None:
    payload = build_runtime_provenance(Path(__file__).resolve().parents[2])

    assert payload["import_root"] == str(
        Path(intelligence.__file__).resolve().parents[1]
    )
    assert str(payload["runtime_instance_id"]).startswith("runtime_")


def test_runtime_instance_id_can_be_frozen_for_one_app() -> None:
    payload = build_runtime_provenance(
        Path(__file__).resolve().parents[2],
        runtime_instance_id="runtime-test",
    )

    assert payload["runtime_instance_id"] == "runtime-test"
