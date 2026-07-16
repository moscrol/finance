from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from intelligence.services.duckdb_market_snapshot import (
    DuckDbSnapshotUnavailable,
    build_duckdb_snapshot_candidate,
)
from intelligence.services.market_snapshot_contract import (
    validate_market_snapshot_root,
)


BEIJING = ZoneInfo("Asia/Shanghai")
OWNED_SOURCES = {"AkShare", "duckdb:market_feature_store"}
AkShareRunner = Callable[[Path, str], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class ProviderAttempt:
    provider: str
    requested_trade_date: str
    served_trade_date: str | None
    quality: str
    freshness: str | None
    duration_ms: int
    published: bool
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MarketSnapshotSyncResult:
    ok: bool
    quality: str
    requested_trade_date: str
    served_trade_date: str | None
    provider: str | None
    attempts: tuple[ProviderAttempt, ...]
    written_files: tuple[str, ...]
    preserved_existing_snapshot: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def sync_market_snapshot(
    root: str | Path,
    *,
    db_path: str | Path,
    target_date: str | None = None,
    akshare_runner: AkShareRunner | None = None,
    akshare_python: str | Path | None = None,
    code_root: str | Path | None = None,
    akshare_timeout_sec: float = 240.0,
    now: datetime | None = None,
) -> MarketSnapshotSyncResult:
    captured = (now or datetime.now(BEIJING)).astimezone(BEIJING)
    requested_date = target_date or captured.date().isoformat()
    date.fromisoformat(requested_date)
    base = Path(root).expanduser()
    base.mkdir(parents=True, exist_ok=True)

    protected = _protected_complete(base / f"{requested_date}.json")
    if protected is not None:
        attempt = ProviderAttempt(
            provider="existing_complete",
            requested_trade_date=requested_date,
            served_trade_date=requested_date,
            quality="complete",
            freshness=str(protected.get("freshness") or "unknown"),
            duration_ms=0,
            published=False,
            error=f"保留更高优先级来源 {protected.get('source')}",
        )
        result = MarketSnapshotSyncResult(
            ok=True,
            quality="complete",
            requested_trade_date=requested_date,
            served_trade_date=requested_date,
            provider="existing_complete",
            attempts=(attempt,),
            written_files=(),
            preserved_existing_snapshot=True,
        )
        _write_status(base, result)
        return result

    attempts: list[ProviderAttempt] = []
    exact_started = time.monotonic()
    try:
        candidate = build_duckdb_snapshot_candidate(
            db_path,
            target_date=requested_date,
            allow_latest_before=False,
            now=captured,
        )
    except (DuckDbSnapshotUnavailable, ValueError) as exc:
        attempts.append(
            ProviderAttempt(
                provider="duckdb_exact",
                requested_trade_date=requested_date,
                served_trade_date=None,
                quality="unavailable",
                freshness=None,
                duration_ms=_elapsed_ms(exact_started),
                published=False,
                error=_error_text(exc),
            )
        )
    else:
        document = _enrich_document(
            candidate.document,
            requested_date=requested_date,
            provider="duckdb_exact",
        )
        written = _publish_complete_document(base, document)
        attempts.append(
            ProviderAttempt(
                provider="duckdb_exact",
                requested_trade_date=requested_date,
                served_trade_date=candidate.trade_date,
                quality="complete",
                freshness="fresh",
                duration_ms=_elapsed_ms(exact_started),
                published=True,
            )
        )
        return _successful_result(
            base,
            requested_date=requested_date,
            served_date=candidate.trade_date,
            provider="duckdb_exact",
            attempts=attempts,
            written=written,
        )

    runner = akshare_runner
    if runner is None and akshare_python is not None and code_root is not None:
        runner = _subprocess_akshare_runner(
            python=Path(akshare_python).expanduser(),
            code_root=Path(code_root).expanduser(),
            timeout_sec=akshare_timeout_sec,
        )
    akshare_started = time.monotonic()
    if runner is None:
        attempts.append(
            ProviderAttempt(
                provider="akshare_exact",
                requested_trade_date=requested_date,
                served_trade_date=None,
                quality="unavailable",
                freshness=None,
                duration_ms=_elapsed_ms(akshare_started),
                published=False,
                error="AkShare runner 未配置",
            )
        )
    else:
        with tempfile.TemporaryDirectory(
            prefix="market-snapshot-akshare-"
        ) as temporary_name:
            temporary = Path(temporary_name)
            try:
                completed = runner(temporary, requested_date)
                contract = validate_market_snapshot_root(
                    temporary,
                    requested_date,
                )
                quality = str(contract["summary"].get("quality") or "failed")
                freshness = str(
                    contract["summary"].get("freshness") or "unknown"
                )
                if (
                    completed.returncode == 0
                    and contract["status"] == "PASS"
                    and contract["ready"] is True
                ):
                    document = _read_json(
                        temporary / f"{requested_date}.json"
                    )
                    if document is None:
                        raise RuntimeError("AkShare complete 日文件不可读")
                    document = _enrich_document(
                        document,
                        requested_date=requested_date,
                        provider="akshare_exact",
                    )
                    written = _publish_complete_document(base, document)
                    attempts.append(
                        ProviderAttempt(
                            provider="akshare_exact",
                            requested_trade_date=requested_date,
                            served_trade_date=requested_date,
                            quality="complete",
                            freshness=freshness,
                            duration_ms=_elapsed_ms(akshare_started),
                            published=True,
                        )
                    )
                    return _successful_result(
                        base,
                        requested_date=requested_date,
                        served_date=requested_date,
                        provider="akshare_exact",
                        attempts=attempts,
                        written=written,
                    )
                attempts.append(
                    ProviderAttempt(
                        provider="akshare_exact",
                        requested_trade_date=requested_date,
                        served_trade_date=(
                            requested_date
                            if (temporary / f"{requested_date}.json").is_file()
                            else None
                        ),
                        quality=quality,
                        freshness=freshness,
                        duration_ms=_elapsed_ms(akshare_started),
                        published=False,
                        error=_completed_error(completed, contract),
                    )
                )
            except Exception as exc:
                attempts.append(
                    ProviderAttempt(
                        provider="akshare_exact",
                        requested_trade_date=requested_date,
                        served_trade_date=None,
                        quality="failed",
                        freshness=None,
                        duration_ms=_elapsed_ms(akshare_started),
                        published=False,
                        error=_error_text(exc),
                    )
                )

    latest_started = time.monotonic()
    prior_cutoff = (
        date.fromisoformat(requested_date) - timedelta(days=1)
    ).isoformat()
    try:
        candidate = build_duckdb_snapshot_candidate(
            db_path,
            target_date=prior_cutoff,
            allow_latest_before=True,
            now=captured,
        )
    except (DuckDbSnapshotUnavailable, ValueError) as exc:
        attempts.append(
            ProviderAttempt(
                provider="duckdb_latest",
                requested_trade_date=requested_date,
                served_trade_date=None,
                quality="unavailable",
                freshness=None,
                duration_ms=_elapsed_ms(latest_started),
                published=False,
                error=_error_text(exc),
            )
        )
    else:
        document = _enrich_document(
            candidate.document,
            requested_date=requested_date,
            provider="duckdb_latest",
            freshness="historical",
        )
        written = _publish_complete_document(base, document)
        attempts.append(
            ProviderAttempt(
                provider="duckdb_latest",
                requested_trade_date=requested_date,
                served_trade_date=candidate.trade_date,
                quality="complete",
                freshness="historical",
                duration_ms=_elapsed_ms(latest_started),
                published=True,
            )
        )
        return _successful_result(
            base,
            requested_date=requested_date,
            served_date=candidate.trade_date,
            provider="duckdb_latest",
            attempts=attempts,
            written=written,
        )

    result = MarketSnapshotSyncResult(
        ok=False,
        quality="failed",
        requested_trade_date=requested_date,
        served_trade_date=None,
        provider=None,
        attempts=tuple(attempts),
        written_files=(),
        preserved_existing_snapshot=_has_complete_latest(base),
    )
    _write_status(base, result)
    return result


def _successful_result(
    base: Path,
    *,
    requested_date: str,
    served_date: str,
    provider: str,
    attempts: list[ProviderAttempt],
    written: tuple[str, ...],
) -> MarketSnapshotSyncResult:
    result = MarketSnapshotSyncResult(
        ok=True,
        quality="complete",
        requested_trade_date=requested_date,
        served_trade_date=served_date,
        provider=provider,
        attempts=tuple(attempts),
        written_files=written,
        preserved_existing_snapshot=False,
    )
    _write_status(base, result)
    return result


def _subprocess_akshare_runner(
    *,
    python: Path,
    code_root: Path,
    timeout_sec: float,
) -> AkShareRunner:
    def run(
        output_dir: Path,
        trade_date: str,
    ) -> subprocess.CompletedProcess[str]:
        if not python.is_file():
            raise FileNotFoundError(f"AkShare Python 不存在: {python}")
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(code_root)
        for name in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ):
            environment.pop(name, None)
        environment["NO_PROXY"] = "*"
        environment["no_proxy"] = "*"
        return subprocess.run(
            [
                str(python),
                "-m",
                "scripts.sync_akshare_market_snapshot",
                "--date",
                trade_date,
                "--output-dir",
                str(output_dir),
            ],
            cwd=code_root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )

    return run


def _publish_complete_document(
    base: Path,
    document: dict[str, object],
) -> tuple[str, ...]:
    if str(document.get("quality") or "") != "complete":
        raise ValueError("只有 complete snapshot 可以发布")
    trade_date = str(document.get("trade_date") or "")
    if not trade_date:
        raise ValueError("snapshot 缺少 trade_date")
    meta = {
        "schema_version": document.get("schema_version"),
        "latest_trade_date": trade_date,
        "requested_trade_date": document.get("requested_trade_date"),
        "served_trade_date": trade_date,
        "updated_at": document.get("captured_at") or document.get("generated_at"),
        "source": document.get("source"),
        "provider": document.get("provider"),
        "source_data_date": document.get("source_data_date") or trade_date,
        "source_updated_at": document.get("source_updated_at"),
        "freshness": document.get("freshness"),
        "quality": "complete",
        "source_errors": document.get("source_errors") or [],
        "provenance": document.get("provenance") or {},
    }
    with tempfile.TemporaryDirectory(
        prefix="market-snapshot-stage-"
    ) as temporary_name:
        stage = Path(temporary_name)
        _atomic_json_write(stage / f"{trade_date}.json", document)
        _atomic_json_write(stage / "latest.json", document)
        _atomic_json_write(stage / "meta.json", meta)
        contract = validate_market_snapshot_root(stage, trade_date)
        if contract["status"] != "PASS" or contract["ready"] is not True:
            raise ValueError(
                "snapshot 发布前 contract 未通过: "
                + json.dumps(contract, ensure_ascii=False)
            )

    base.mkdir(parents=True, exist_ok=True)
    written = [
        str(_atomic_json_write(base / f"{trade_date}.json", document)),
    ]
    latest = _read_json(base / "latest.json")
    latest_date = str(latest.get("trade_date") or "") if latest else ""
    latest_complete = (
        str(latest.get("quality") or "") == "complete" if latest else False
    )
    if not latest_date or trade_date >= latest_date or not latest_complete:
        written.append(str(_atomic_json_write(base / "latest.json", document)))
        written.append(str(_atomic_json_write(base / "meta.json", meta)))
    return tuple(written)


def _enrich_document(
    document: Mapping[str, object],
    *,
    requested_date: str,
    provider: str,
    freshness: str | None = None,
) -> dict[str, object]:
    enriched = json.loads(json.dumps(document, ensure_ascii=False, default=str))
    served_date = str(enriched.get("trade_date") or "")
    enriched["requested_trade_date"] = requested_date
    enriched["served_trade_date"] = served_date
    enriched["provider"] = provider
    if freshness is not None:
        enriched["freshness"] = freshness
    return enriched


def _protected_complete(path: Path) -> dict[str, object] | None:
    existing = _read_json(path)
    if existing is None:
        return None
    if str(existing.get("quality") or "") != "complete":
        return None
    source = str(existing.get("source") or "")
    return existing if source not in OWNED_SOURCES else None


def _has_complete_latest(base: Path) -> bool:
    latest = _read_json(base / "latest.json")
    return latest is not None and str(latest.get("quality") or "") == "complete"


def _write_status(base: Path, result: MarketSnapshotSyncResult) -> None:
    _atomic_json_write(
        base / "market_snapshot_sync_status.json",
        result.to_dict(),
    )


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _atomic_json_write(
    path: Path,
    value: Mapping[str, object],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))


def _error_text(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"[:1000]


def _completed_error(
    completed: subprocess.CompletedProcess[str],
    contract: Mapping[str, Any],
) -> str:
    parts = [f"exit={completed.returncode}"]
    errors = contract.get("errors") or contract.get("warnings") or []
    if errors:
        parts.append("；".join(str(item) for item in errors))
    stderr = (completed.stderr or "").strip()
    if stderr:
        parts.append(stderr)
    return " | ".join(parts)[:1000]
