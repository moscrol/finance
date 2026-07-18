from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb

from intelligence.services.market_snapshot_sync import sync_market_snapshot
from intelligence.tests.test_duckdb_market_snapshot import _build_db


BEIJING = ZoneInfo("Asia/Shanghai")


def _akshare_document(
    trade_date: str,
    *,
    quality: str,
    freshness: str,
) -> dict[str, object]:
    return {
        "schema_version": "1.1-akshare",
        "trade_date": trade_date,
        "generated_at": "2026-07-16T16:20:00+08:00",
        "source": "AkShare",
        "source_data_date": trade_date,
        "captured_at": "2026-07-16T16:20:00+08:00",
        "freshness": freshness,
        "quality": quality,
        "source_errors": [] if quality == "complete" else ["spot unavailable"],
        "market": {
            "stage": "震荡阶段" if quality == "complete" else "局部快照",
            "total_amount": 22000.0 if quality == "complete" else None,
            "amount_ratio": None,
            "advancers": 2800 if quality == "complete" else None,
            "decliners": 2400 if quality == "complete" else None,
            "limit_up": 60,
            "limit_down": 12,
            "capacity_top3": [],
        },
        "themes": [
            {
                "concept": "光模块",
                "priority_score": 80.0,
                "trigger_types": ["akshare_limit_up_pool"],
            }
        ],
        "strong_stocks": [
            {
                "stock_name": "测试股份",
                "stock_ts_code": "600001.SH",
                "concepts": ["光模块"],
                "pct_chg": 10.0,
                "amount": 10.0,
            }
        ],
    }


def _write_akshare_result(
    output_dir: Path,
    trade_date: str,
    *,
    quality: str,
) -> subprocess.CompletedProcess[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    freshness = "fresh" if quality == "complete" else "degraded"
    document = _akshare_document(
        trade_date,
        quality=quality,
        freshness=freshness,
    )
    meta = {
        "schema_version": "1.1-akshare",
        "latest_trade_date": trade_date,
        "updated_at": "2026-07-16T16:20:00+08:00",
        "source": "AkShare",
        "source_data_date": trade_date,
        "freshness": freshness,
        "quality": quality,
    }
    for name, payload in (
        (f"{trade_date}.json", document),
        ("latest.json", document),
        ("meta.json", meta),
    ):
        (output_dir / name).write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
    return subprocess.CompletedProcess(
        args=["fake-akshare"],
        returncode=0 if quality == "complete" else 3,
        stdout=json.dumps({"quality": quality}),
        stderr="",
    )


def _empty_db(path: Path) -> Path:
    _build_db(path)
    connection = duckdb.connect(str(path))
    for table in (
        "fact_market_daily",
        "fact_stock_daily",
        "fact_sector_daily",
        "fact_mainline_sector_daily",
    ):
        connection.execute(f"DELETE FROM {table}")
    connection.close()
    return path


def test_exact_duckdb_short_circuits_akshare(tmp_path: Path) -> None:
    root = tmp_path / "snapshot"
    db_path = _build_db(tmp_path / "market.duckdb")
    called = False

    def forbidden_runner(
        _output_dir: Path,
        _trade_date: str,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal called
        called = True
        raise AssertionError("AkShare must not run")

    result = sync_market_snapshot(
        root,
        db_path=db_path,
        target_date="2026-07-16",
        akshare_runner=forbidden_runner,
        now=datetime(2026, 7, 16, 18, 30, tzinfo=BEIJING),
    )

    assert result.ok is True
    assert result.provider == "duckdb_exact"
    assert result.served_trade_date == "2026-07-16"
    assert [attempt.provider for attempt in result.attempts] == ["duckdb_exact"]
    assert called is False
    assert json.loads((root / "latest.json").read_text())["quality"] == "complete"


def test_akshare_complete_publishes_exact_target(tmp_path: Path) -> None:
    root = tmp_path / "snapshot"
    db_path = _empty_db(tmp_path / "market.duckdb")

    def complete_runner(
        output_dir: Path,
        trade_date: str,
    ) -> subprocess.CompletedProcess[str]:
        return _write_akshare_result(
            output_dir,
            trade_date,
            quality="complete",
        )

    result = sync_market_snapshot(
        root,
        db_path=db_path,
        target_date="2026-07-16",
        akshare_runner=complete_runner,
    )

    assert result.ok is True
    assert result.provider == "akshare_exact"
    assert result.served_trade_date == "2026-07-16"
    latest = json.loads((root / "latest.json").read_text())
    assert latest["provider"] == "akshare_exact"
    assert latest["requested_trade_date"] == "2026-07-16"


def test_partial_akshare_is_not_published_and_uses_prior_duckdb(
    tmp_path: Path,
) -> None:
    root = tmp_path / "snapshot"
    db_path = _build_db(
        tmp_path / "market.duckdb",
        trade_date="2026-07-15",
    )

    def partial_runner(
        output_dir: Path,
        trade_date: str,
    ) -> subprocess.CompletedProcess[str]:
        return _write_akshare_result(
            output_dir,
            trade_date,
            quality="partial",
        )

    result = sync_market_snapshot(
        root,
        db_path=db_path,
        target_date="2026-07-16",
        akshare_runner=partial_runner,
    )

    assert result.ok is True
    assert result.provider == "duckdb_latest"
    assert result.served_trade_date == "2026-07-15"
    assert [attempt.quality for attempt in result.attempts] == [
        "unavailable",
        "partial",
        "complete",
    ]
    assert not (root / "2026-07-16.json").exists()
    latest = json.loads((root / "latest.json").read_text())
    assert latest["trade_date"] == "2026-07-15"
    assert latest["freshness"] == "historical"


def test_total_failure_preserves_existing_complete_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "snapshot"
    root.mkdir()
    existing = _akshare_document(
        "2026-07-15",
        quality="complete",
        freshness="historical",
    )
    (root / "latest.json").write_text(json.dumps(existing), encoding="utf-8")
    before = (root / "latest.json").read_bytes()
    db_path = _empty_db(tmp_path / "market.duckdb")

    def failed_runner(
        _output_dir: Path,
        _trade_date: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["fake-akshare"],
            returncode=1,
            stdout="",
            stderr="remote disconnected",
        )

    result = sync_market_snapshot(
        root,
        db_path=db_path,
        target_date="2026-07-16",
        akshare_runner=failed_runner,
    )

    assert result.ok is False
    assert result.preserved_existing_snapshot is True
    assert (root / "latest.json").read_bytes() == before
    status = json.loads(
        (root / "market_snapshot_sync_status.json").read_text(encoding="utf-8")
    )
    assert status["ok"] is False
    assert status["attempts"][-1]["provider"] == "duckdb_latest"


def test_never_overwrites_higher_priority_complete_target(tmp_path: Path) -> None:
    root = tmp_path / "snapshot"
    root.mkdir()
    protected = _akshare_document(
        "2026-07-16",
        quality="complete",
        freshness="fresh",
    )
    protected["source"] = "daily-full"
    daily_path = root / "2026-07-16.json"
    daily_path.write_text(json.dumps(protected), encoding="utf-8")
    before = daily_path.read_bytes()
    db_path = _build_db(tmp_path / "market.duckdb")

    result = sync_market_snapshot(
        root,
        db_path=db_path,
        target_date="2026-07-16",
        akshare_runner=lambda *_args: (_ for _ in ()).throw(
            AssertionError("provider must not run")
        ),
    )

    assert result.ok is True
    assert result.provider == "existing_complete"
    assert result.preserved_existing_snapshot is True
    assert daily_path.read_bytes() == before
