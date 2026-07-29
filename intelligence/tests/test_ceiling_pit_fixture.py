from __future__ import annotations

from datetime import date
import hashlib
import os
from pathlib import Path
import subprocess
import textwrap

import duckdb
import pytest

from intelligence.eval.ceiling_pit_fixture import (
    TemporalSchemaError,
    TemporalValueError,
    audit_wiki_export,
    audit_filtered_duckdb,
    build_true_hybrid_index,
    build_filtered_duckdb,
    export_cutoff_wiki,
    select_revision_at_cutoff,
)


AS_OF = "2026-07-24"


def _source_db(path: Path) -> None:
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            "CREATE TABLE prices (trade_date DATE, value INTEGER)"
        )
        connection.execute(
            "INSERT INTO prices VALUES "
            "('2026-07-24', 1), ('2026-07-25', 2), (NULL, 3)"
        )
    finally:
        connection.close()


def _commit_file(
    repo: Path,
    relative: str,
    content: str,
    committed_at: str,
) -> str:
    target = repo / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", relative], check=True)
    environment = {
        **os.environ,
        "GIT_AUTHOR_DATE": committed_at,
        "GIT_COMMITTER_DATE": committed_at,
    }
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "-m",
            relative,
        ],
        check=True,
        env=environment,
    )
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _fake_rag_code(repo: Path, *, reported_path: str | None = None) -> str:
    script = textwrap.dedent(
        """
        from __future__ import annotations
        import gzip
        import hashlib
        import json
        import os
        from pathlib import Path
        import sys
        import numpy as np

        vault = Path(os.environ["KB_VAULT"])
        index = Path(os.environ["RAG_INDEX_DIR"])
        if sys.argv[1] == "build":
            source = vault / "entities" / "before.md"
            raw = source.read_bytes()
            rel = f"{vault.name}/entities/before.md"
            chunk_id = rel + "::0"
            content_hash = hashlib.sha1(raw).hexdigest()
            selection = "include_raw=0;max_files=0\\n"
            manifest = hashlib.sha256()
            manifest.update(selection.encode())
            manifest.update(rel.encode())
            manifest.update(b"\\0")
            manifest.update(hashlib.sha256(raw).hexdigest().encode())
            manifest.update(b"\\n")
            fingerprint = hashlib.sha256()
            fingerprint.update(chunk_id.encode())
            fingerprint.update(b"\\0")
            fingerprint.update(content_hash.encode())
            fingerprint.update(b"\\n")
            index.mkdir(parents=True)
            chunk = {
                "id": chunk_id,
                "file_path": rel,
                "text": raw.decode(),
                "content_hash": content_hash,
            }
            (index / "chunks.jsonl").write_text(json.dumps(chunk) + "\\n")
            np.save(index / "dense.npy", np.ones((1, 2), dtype=np.float16))
            meta = {
                "format_version": 2,
                "model": "bge-m3",
                "num_chunks": 1,
                "dim": 2,
                "built_at": "2026-07-29T12:00:00+08:00",
                "include_raw": False,
                "max_files": 0,
                "source_revision": "manifest:v1:" + manifest.hexdigest(),
                "source_git_revision": "",
                "source_dirty": None,
                "source_fingerprint": fingerprint.hexdigest(),
                "source_file_count": 1,
            }
            (index / "meta.json").write_text(json.dumps(meta))
            with gzip.open(index / "bm25_tokens.jsonl.gz", "wt") as handle:
                handle.write(json.dumps({"format": "bm25-tokens-v1", "num_chunks": 1}) + "\\n")
                handle.write(json.dumps(["before"]) + "\\n")
            print("built")
        elif sys.argv[1] == "query":
            meta = json.loads((index / "meta.json").read_text())
            print(json.dumps([{
                "file_path": f"{vault.name}/entities/before.md",
                "score": 0.2,
                "index_freshness": "fresh",
                "index_source_revision": meta["source_revision"],
                "index_format_version": 2,
            }]))
        else:
            raise SystemExit(2)
        """
    ).strip() + "\n"
    if reported_path is not None:
        script = script.replace(
            'rel = f"{vault.name}/entities/before.md"',
            f"rel = {reported_path!r}",
        )
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "rag_index.py").write_text(script, encoding="utf-8")
    (repo / "scripts" / "rag_freshness.py").write_text("# frozen\n", encoding="utf-8")
    (repo / "skills" / "lib").mkdir(parents=True)
    (repo / "skills" / "lib" / "marker.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "-m",
            "rag-code",
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_filtered_duckdb_rejects_unclassified_temporal_column(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.duckdb"
    target = tmp_path / "target.duckdb"
    _source_db(source)
    connection = duckdb.connect(str(source))
    try:
        connection.execute(
            "CREATE TABLE mystery (id INTEGER, mystery_effective_when VARCHAR)"
        )
    finally:
        connection.close()

    with pytest.raises(
        TemporalSchemaError,
        match="unclassified_temporal_column.*mystery_effective_when",
    ):
        build_filtered_duckdb(source, target, as_of=AS_OF)

    assert not target.exists()


def test_filtered_duckdb_physically_excludes_future_rows(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    target = tmp_path / "target.duckdb"
    _source_db(source)

    receipt = build_filtered_duckdb(source, target, as_of=AS_OF)

    connection = duckdb.connect(str(target), read_only=True)
    try:
        assert connection.execute(
            "SELECT trade_date, value FROM prices ORDER BY value"
        ).fetchall() == [
            (date(2026, 7, 24), 1),
            (None, 3),
        ]
    finally:
        connection.close()
    table = next(item for item in receipt.tables if item.name == "main.prices")
    assert table.source_rows == 3
    assert table.target_rows == 2
    assert table.maxima["trade_date"] == "2026-07-24T00:00:00+08:00"
    assert target.stat().st_mode & 0o777 == 0o444
    assert len(receipt.target_sha256) == 64
    assert receipt.target_sha256 != hashlib.sha256(source.read_bytes()).hexdigest()


def test_filtered_duckdb_derives_cutoff_market_row_from_pit_safe_components(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.duckdb"
    target = tmp_path / "target.duckdb"
    connection = duckdb.connect(str(source))
    try:
        connection.execute(
            """
            CREATE TABLE fact_market_daily (
                trade_date DATE,
                market_stage VARCHAR,
                total_amount DOUBLE,
                advancers INTEGER,
                limit_up INTEGER,
                limit_down INTEGER,
                note VARCHAR,
                source VARCHAR,
                updated_at TIMESTAMP,
                sh_index_close DOUBLE,
                sh_index_pct_chg DOUBLE,
                sh_index_updated_at TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO fact_market_daily VALUES
              ('2026-07-23', '反弹阶段', 100.0, 3, 1, 0, 'safe', 'source',
               '2026-07-23 18:00:00', 3876.7, 0.25, '2026-07-23 18:00:00'),
              ('2026-07-24', '后视阶段标签', 999.0, 999, 999, 999, 'future note', 'source',
               '2026-07-27 12:00:00', 3814.2, -1.61, '2026-07-24 18:00:00'),
              ('2026-07-25', 'future', 888.0, 888, 888, 888, 'future', 'source',
               '2026-07-25 18:00:00', 3800.0, -0.3, '2026-07-25 18:00:00')
            """
        )
        connection.execute(
            """
            CREATE TABLE fact_stock_daily (
                trade_date DATE,
                pct_chg DOUBLE,
                amount DOUBLE,
                updated_at TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO fact_stock_daily VALUES
              ('2026-07-24', 10.0, 120.0, '2026-07-24 20:00:00'),
              ('2026-07-24', 1.0, 80.0, '2026-07-24 20:00:00'),
              ('2026-07-24', -10.0, 100.0, '2026-07-24 20:00:00')
            """
        )
        connection.execute(
            """
            CREATE TABLE feature_market_window (
                as_of_date DATE,
                start_date DATE,
                end_date DATE,
                advancers_end INTEGER,
                amount_avg DOUBLE,
                calculated_at TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO feature_market_window VALUES
              ('2026-07-24', '2026-06-26', '2026-07-24', 2, 400.0,
               '2026-07-24 21:00:00')
            """
        )
    finally:
        connection.close()

    receipt = build_filtered_duckdb(source, target, as_of=AS_OF)

    connection = duckdb.connect(str(target), read_only=True)
    try:
        row = connection.execute(
            """
            SELECT market_stage, total_amount, advancers, limit_up, limit_down,
                   note, source, updated_at, sh_index_close, sh_index_pct_chg
            FROM fact_market_daily
            WHERE trade_date = DATE '2026-07-24'
            """
        ).fetchone()
        assert row[:5] == (None, 300.0, 2, 1, 1)
        assert row[5] == "PIT-safe derived market base; late source fields withheld"
        assert row[6] == (
            "derived:pitsafe_fact_stock_daily+feature_market_window"
        )
        assert str(row[7]).startswith("2026-07-24")
        assert row[8:] == (3814.2, -1.61)
        assert connection.execute(
            "SELECT COUNT(*) FROM fact_market_daily WHERE trade_date > DATE '2026-07-24'"
        ).fetchone() == (0,)
    finally:
        connection.close()
    table = next(
        item for item in receipt.tables if item.name == "main.fact_market_daily"
    )
    assert table.derivation == {
        "kind": "pit_safe_market_base",
        "derived_rows": 1,
        "source_tables": ["fact_stock_daily", "feature_market_window"],
    }


def test_filtered_duckdb_handles_compact_dates_timestamps_empty_tables_and_views(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.duckdb"
    target = tmp_path / "target.duckdb"
    connection = duckdb.connect(str(source))
    try:
        connection.execute(
            "CREATE TABLE compact (report_period VARCHAR, value INTEGER)"
        )
        connection.execute(
            "INSERT INTO compact VALUES "
            "('20260724', 1), ('20260725', 2), (NULL, 3)"
        )
        connection.execute(
            "CREATE TABLE events (published_at TIMESTAMPTZ, value INTEGER)"
        )
        connection.execute(
            "INSERT INTO events VALUES "
            "('2026-07-24T15:59:59Z', 1), "
            "('2026-07-24T16:00:00Z', 2), (NULL, 3)"
        )
        connection.execute("CREATE TABLE empty_dates (end_date DATE)")
        connection.execute("CREATE TABLE base_rows (date DATE, value INTEGER)")
        connection.execute(
            "INSERT INTO base_rows VALUES ('2026-07-24', 1), ('2026-07-25', 2)"
        )
        connection.execute("CREATE VIEW base_view AS SELECT * FROM base_rows")
    finally:
        connection.close()

    receipt = build_filtered_duckdb(source, target, as_of=AS_OF)

    connection = duckdb.connect(str(target), read_only=True)
    try:
        assert connection.execute(
            "SELECT value FROM compact ORDER BY value"
        ).fetchall() == [(1,), (3,)]
        assert connection.execute(
            "SELECT value FROM events ORDER BY value"
        ).fetchall() == [(1,), (3,)]
        assert connection.execute("SELECT COUNT(*) FROM empty_dates").fetchone() == (
            0,
        )
        assert connection.execute("SELECT value FROM base_view").fetchall() == [(1,)]
        assert connection.execute(
            "SELECT table_type FROM information_schema.tables "
            "WHERE table_name = 'base_view'"
        ).fetchone() == ("BASE TABLE",)
    finally:
        connection.close()
    view_receipt = next(item for item in receipt.tables if item.name == "main.base_view")
    assert view_receipt.source_kind == "VIEW"
    assert view_receipt.source_rows == 2
    assert view_receipt.target_rows == 1


def test_filtered_duckdb_rejects_malformed_temporal_values(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    target = tmp_path / "target.duckdb"
    connection = duckdb.connect(str(source))
    try:
        connection.execute(
            "CREATE TABLE reports (report_date VARCHAR, value INTEGER)"
        )
        connection.execute("INSERT INTO reports VALUES ('not-a-date', 1)")
    finally:
        connection.close()

    with pytest.raises(
        TemporalValueError,
        match="malformed_temporal_value:main.reports:report_date:1",
    ):
        build_filtered_duckdb(source, target, as_of=AS_OF)

    assert not target.exists()


def test_filtered_duckdb_audit_detects_target_mutation(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    target = tmp_path / "target.duckdb"
    _source_db(source)
    receipt = build_filtered_duckdb(source, target, as_of=AS_OF)
    target.chmod(0o644)

    audit = audit_filtered_duckdb(receipt)

    assert audit.status == "invalid"
    assert "target_mode" in audit.issues


def test_temporal_classifier_distinguishes_cutoffs_labels_and_intraday_times(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.duckdb"
    target = tmp_path / "target.duckdb"
    connection = duckdb.connect(str(source))
    try:
        connection.execute(
            """
            CREATE TABLE signals (
                trade_date DATE,
                start_date DATE,
                limit_times INTEGER,
                period_type VARCHAR,
                is_realtime BOOLEAN,
                first_limit_time VARCHAR,
                value INTEGER
            )
            """
        )
        connection.execute(
            "INSERT INTO signals VALUES "
            "('2026-07-24', '2026-07-24', 2, '20d', TRUE, '93312', 1), "
            "('2026-07-24', '2026-07-25', 3, '20d', TRUE, '101739', 2), "
            "('2026-07-24', '2026-07-24', 4, '20d', FALSE, '09:25:00', 3), "
            "('2026-07-24', '2026-07-24', 5, '20d', FALSE, '0', 4)"
        )
    finally:
        connection.close()

    build_filtered_duckdb(source, target, as_of=AS_OF)

    connection = duckdb.connect(str(target), read_only=True)
    try:
        assert connection.execute(
            "SELECT limit_times, period_type, is_realtime, first_limit_time, value "
            "FROM signals"
        ).fetchall() == [
            (2, "20d", True, "93312", 1),
            (4, "20d", False, "09:25:00", 3),
            (5, "20d", False, "0", 4),
        ]
    finally:
        connection.close()


def test_intraday_time_requires_date_anchor_and_valid_clock(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    target = tmp_path / "target.duckdb"
    connection = duckdb.connect(str(source))
    try:
        connection.execute(
            "CREATE TABLE signals (trade_date DATE, first_limit_time VARCHAR)"
        )
        connection.execute("INSERT INTO signals VALUES ('2026-07-24', '259999')")
    finally:
        connection.close()

    with pytest.raises(
        TemporalValueError,
        match="malformed_intraday_time:main.signals:first_limit_time:1",
    ):
        build_filtered_duckdb(source, target, as_of=AS_OF)


def test_cutoff_wiki_export_selects_pre_cutoff_revision(tmp_path: Path) -> None:
    repo = tmp_path / "kb"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    before = _commit_file(
        repo,
        "wiki/entities/before.md",
        "before\n",
        "2026-07-24T12:00:00+08:00",
    )
    _commit_file(
        repo,
        "wiki/entities/after.md",
        "after\n",
        "2026-07-25T12:00:00+08:00",
    )

    selected = select_revision_at_cutoff(repo, "2026-07-24")
    receipt = export_cutoff_wiki(
        repo,
        tmp_path / "export",
        as_of="2026-07-24",
    )

    assert selected == before
    assert receipt.selected_revision == before
    assert (receipt.wiki_root / "entities" / "before.md").read_text() == "before\n"
    assert not (receipt.wiki_root / "entities" / "after.md").exists()
    assert not (receipt.wiki_root / ".git").exists()
    assert all(path.stat().st_mode & 0o777 == 0o444 for path in receipt.wiki_root.rglob("*") if path.is_file())
    assert audit_wiki_export(receipt).status == "valid"


def test_cutoff_wiki_export_rejects_links_and_detects_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "kb"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _commit_file(
        repo,
        "wiki/entities/regular.md",
        "regular\n",
        "2026-07-24T12:00:00+08:00",
    )
    link = repo / "wiki" / "entities" / "escape.md"
    os.symlink("../../../outside.md", link)
    subprocess.run(["git", "-C", str(repo), "add", "wiki/entities/escape.md"], check=True)
    environment = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2026-07-24T13:00:00+08:00",
        "GIT_COMMITTER_DATE": "2026-07-24T13:00:00+08:00",
    }
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "-m",
            "link",
        ],
        check=True,
        env=environment,
    )

    with pytest.raises(ValueError, match="regular Git blobs"):
        export_cutoff_wiki(repo, tmp_path / "rejected", as_of="2026-07-24")

    receipt = export_cutoff_wiki(
        repo,
        tmp_path / "accepted",
        as_of="2026-07-24T12:30:00+08:00",
    )
    target = receipt.wiki_root / "entities" / "regular.md"
    target.chmod(0o644)
    target.write_text("mutated\n", encoding="utf-8")

    assert audit_wiki_export(receipt).status == "invalid"


def test_cutoff_wiki_export_rejects_post_cutoff_publication_metadata(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "kb"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _commit_file(
        repo,
        "wiki/sources/future.md",
        "---\nsource_date: 2026-07-25\n---\nForecast written early.\n",
        "2026-07-24T12:00:00+08:00",
    )

    with pytest.raises(ValueError, match="post-cutoff publication date"):
        export_cutoff_wiki(repo, tmp_path / "export", as_of=AS_OF)


def test_cutoff_wiki_export_parses_chinese_publication_dates(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "kb"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _commit_file(
        repo,
        "wiki/raw/sellside/historical.md",
        "发布时间：2026年3月31日\nHistorical report.\n",
        "2026-07-24T12:00:00+08:00",
    )

    receipt = export_cutoff_wiki(repo, tmp_path / "export", as_of=AS_OF)

    assert (receipt.wiki_root / "raw/sellside/historical.md").is_file()


def test_true_hybrid_build_seals_fresh_content_bound_index(tmp_path: Path) -> None:
    kb = tmp_path / "kb"
    kb.mkdir()
    subprocess.run(["git", "init", "-q", str(kb)], check=True)
    _commit_file(
        kb,
        "wiki/entities/before.md",
        "before\n",
        "2026-07-24T12:00:00+08:00",
    )
    wiki_receipt = export_cutoff_wiki(
        kb,
        tmp_path / "fixture" / "wiki",
        as_of=AS_OF,
    )
    code = tmp_path / "rag-code"
    code.mkdir()
    revision = _fake_rag_code(code)

    receipt = build_true_hybrid_index(
        wiki_receipt=wiki_receipt,
        index_root=tmp_path / "fixture" / "index",
        code_root=code,
        code_revision=revision,
        rag_python=Path(
            "/Users/a77/finance-workspace-private/.venv-workbench/bin/python"
        ),
        query="before",
    )

    assert receipt.model == "bge-m3"
    assert receipt.num_chunks == 1
    assert receipt.source_file_count == 1
    assert receipt.query_mode == "hybrid"
    assert receipt.hits[0]["index_freshness"] == "fresh"
    assert not (receipt.code_runtime / ".git").exists()
    assert all(
        path.stat().st_mode & 0o777 == 0o444
        for path in receipt.index_root.rglob("*")
        if path.is_file()
    )


def test_true_hybrid_build_adopts_only_a_byte_identical_prebuilt_index(
    tmp_path: Path,
) -> None:
    kb = tmp_path / "kb"
    kb.mkdir()
    subprocess.run(["git", "init", "-q", str(kb)], check=True)
    _commit_file(
        kb,
        "wiki/entities/before.md",
        "before\n",
        "2026-07-24T12:00:00+08:00",
    )
    wiki_receipt = export_cutoff_wiki(
        kb,
        tmp_path / "fixture" / "wiki",
        as_of=AS_OF,
    )
    code = tmp_path / "rag-code"
    code.mkdir()
    revision = _fake_rag_code(code)
    python = Path(
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python"
    )
    prebuilt = build_true_hybrid_index(
        wiki_receipt=wiki_receipt,
        index_root=tmp_path / "prebuilt" / "index",
        code_root=code,
        code_revision=revision,
        rag_python=python,
        query="before",
    )

    adopted = build_true_hybrid_index(
        wiki_receipt=wiki_receipt,
        index_root=tmp_path / "adopted" / "index",
        code_root=code,
        code_revision=revision,
        rag_python=python,
        query="before",
        prebuilt_index_root=prebuilt.index_root,
    )

    assert [item.to_dict() for item in adopted.index_files] == [
        item.to_dict() for item in prebuilt.index_files
    ]
    assert all(
        path.stat().st_nlink == 1
        for path in adopted.index_root.rglob("*")
        if path.is_file()
    )
    assert adopted.hits[0]["index_freshness"] == "fresh"


def test_true_hybrid_build_accepts_explicit_dependency_interpreter(
    tmp_path: Path,
) -> None:
    kb = tmp_path / "kb"
    kb.mkdir()
    subprocess.run(["git", "init", "-q", str(kb)], check=True)
    _commit_file(
        kb,
        "wiki/entities/before.md",
        "before\n",
        "2026-07-24T12:00:00+08:00",
    )
    wiki_receipt = export_cutoff_wiki(
        kb,
        tmp_path / "fixture" / "wiki",
        as_of=AS_OF,
    )
    code = tmp_path / "rag-code"
    code.mkdir()
    revision = _fake_rag_code(code)

    receipt = build_true_hybrid_index(
        wiki_receipt=wiki_receipt,
        index_root=tmp_path / "fixture" / "index",
        code_root=code,
        code_revision=revision,
        rag_python=Path("/Users/a77/knowledge-base-private/.rag_venv/bin/python3"),
        query="before",
    )

    assert receipt.query_mode == "hybrid"
    assert receipt.python_executable.endswith("/.rag_venv/bin/python3")


def test_true_hybrid_build_rejects_wrong_chunk_source_set(tmp_path: Path) -> None:
    kb = tmp_path / "kb"
    kb.mkdir()
    subprocess.run(["git", "init", "-q", str(kb)], check=True)
    _commit_file(
        kb,
        "wiki/entities/before.md",
        "before\n",
        "2026-07-24T12:00:00+08:00",
    )
    wiki_receipt = export_cutoff_wiki(
        kb,
        tmp_path / "fixture" / "wiki",
        as_of=AS_OF,
    )
    code = tmp_path / "rag-code"
    code.mkdir()
    revision = _fake_rag_code(code, reported_path="wiki/entities/wrong.md")

    with pytest.raises(ValueError, match=r"source (?:manifest|set) mismatch"):
        build_true_hybrid_index(
            wiki_receipt=wiki_receipt,
            index_root=tmp_path / "fixture" / "index",
            code_root=code,
            code_revision=revision,
            rag_python=Path(
                "/Users/a77/finance-workspace-private/.venv-workbench/bin/python"
            ),
            query="before",
        )
