"""The rehearsal must reject unsafe inputs before creating any DB copies."""
from argparse import Namespace

import pytest

from scripts.review_probes import rehearse_302132_backfill as rehearsal


def test_dirty_checkout_refused_before_data_access(tmp_path, monkeypatch):
    monkeypatch.setattr(rehearsal, "_code_revision", lambda: ("a" * 40, True))
    with pytest.raises(ValueError, match="clean committed checkout"):
        rehearsal.run(Namespace())
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("case", ["existing", "under_source", "symlink", "wal", "bad_hash"])
def test_rehearsal_preflight_does_not_modify_inputs(tmp_path, monkeypatch, case):
    monkeypatch.setattr(rehearsal, "_code_revision", lambda: ("a" * 40, False))
    data = tmp_path / "data"
    data.mkdir()
    prod, pq = data / "prod.duckdb", data / "frozen.parquet"
    prod.write_bytes(b"production witness")
    pq.write_bytes(b"frozen witness")
    out = tmp_path / "new-run"
    if case == "existing":
        out.mkdir()
    elif case == "under_source":
        out = data / "run"
    elif case == "symlink":
        link = data / "alias.duckdb"
        link.symlink_to(prod)
        prod = link
    elif case == "wal":
        rehearsal.db.wal_path(prod).write_bytes(b"wal witness")
    before = {p: p.read_bytes() for p in data.iterdir() if p.is_file()}
    with pytest.raises(ValueError):
        rehearsal.run(Namespace(production=prod, parquet=pq, output=out))
    assert {p: p.read_bytes() for p in data.iterdir() if p.is_file()} == before
    assert not out.exists() or (case == "existing" and not list(out.iterdir()))
