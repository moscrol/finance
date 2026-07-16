from __future__ import annotations

import json
import math
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast
from zoneinfo import ZoneInfo


BEIJING = ZoneInfo("Asia/Shanghai")
DATE_PATTERN = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
SCHEMA_VERSION = "1.1-akshare"


class FrameLike(Protocol):
    @property
    def empty(self) -> bool: ...

    def to_dict(self, orient: str) -> list[dict[str, object]]: ...


@dataclass(frozen=True)
class SnapshotSyncResult:
    ok: bool
    quality: str
    trade_date: str
    captured_at: str
    written_files: tuple[str, ...]
    errors: tuple[str, ...]
    preserved_existing_snapshot: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def sync_akshare_market_snapshot(
    root: str | Path,
    *,
    trade_date: str | None = None,
    akshare_module: ModuleType | None = None,
    now: datetime | None = None,
) -> SnapshotSyncResult:
    captured = (now or datetime.now(BEIJING)).astimezone(BEIJING)
    date_text = trade_date or captured.date().isoformat()
    if not DATE_PATTERN.fullmatch(date_text):
        raise ValueError("trade_date 必须为 YYYY-MM-DD")
    base = Path(root).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    captured_at = captured.isoformat()
    daily_path = base / f"{date_text}.json"
    existing = _read_json(daily_path)
    if (
        existing is not None
        and str(existing.get("quality") or "") == "complete"
        and str(existing.get("source") or "") not in {"", "AkShare"}
    ):
        result = SnapshotSyncResult(
            ok=True,
            quality="complete",
            trade_date=date_text,
            captured_at=captured_at,
            written_files=(),
            errors=(
                f"已存在更高优先级 complete 快照（{existing.get('source')}），AkShare 未请求、未覆盖",
            ),
            preserved_existing_snapshot=True,
        )
        _write_status(base, result)
        return result
    ak = akshare_module or import_module("akshare")
    errors: list[str] = []
    spot_rows = _fetch_rows(ak, "stock_zh_a_spot_em", errors)
    if not spot_rows:
        spot_rows = _fetch_rows(ak, "stock_zh_a_spot", errors)
    limit_up_rows = _fetch_rows(
        ak,
        "stock_zt_pool_em",
        errors,
        date=date_text.replace("-", ""),
    )
    limit_down_rows = _fetch_rows(
        ak,
        "stock_zt_pool_dtgc_em",
        errors,
        date=date_text.replace("-", ""),
    )
    usable = bool(spot_rows or limit_up_rows or limit_down_rows)
    if not usable:
        result = SnapshotSyncResult(
            ok=False,
            quality="failed",
            trade_date=date_text,
            captured_at=captured_at,
            written_files=(),
            errors=tuple(errors or ["AkShare 未返回可用行情数据"]),
            preserved_existing_snapshot=(base / "latest.json").is_file(),
        )
        _write_status(base, result)
        return result

    quality = "complete" if spot_rows else "partial"
    daily = _build_daily_snapshot(
        date_text,
        captured_at,
        spot_rows,
        limit_up_rows,
        limit_down_rows,
        errors,
        quality,
        (
            "degraded"
            if quality == "partial"
            else "fresh"
            if date_text == captured.date().isoformat()
            else "historical"
        ),
    )
    if (
        quality == "partial"
        and existing is not None
        and str(existing.get("quality") or "complete") == "complete"
    ):
        result = SnapshotSyncResult(
            ok=True,
            quality=quality,
            trade_date=date_text,
            captured_at=captured_at,
            written_files=(),
            errors=tuple(errors),
            preserved_existing_snapshot=True,
        )
        _write_status(base, result)
        return result

    written = [str(_atomic_json_write(daily_path, daily))]
    latest = _read_json(base / "latest.json")
    latest_date = str(latest.get("trade_date") or "") if latest else ""
    if not latest_date or date_text >= latest_date:
        written.append(str(_atomic_json_write(base / "latest.json", daily)))
        meta = {
            "schema_version": SCHEMA_VERSION,
            "latest_trade_date": date_text,
            "updated_at": captured_at,
            "source": "AkShare",
            "source_data_date": date_text,
            "freshness": (
                "degraded"
                if quality == "partial"
                else "fresh"
                if date_text == captured.date().isoformat()
                else "historical"
            ),
            "quality": quality,
            "source_errors": errors,
        }
        written.append(str(_atomic_json_write(base / "meta.json", meta)))
    result = SnapshotSyncResult(
        ok=True,
        quality=quality,
        trade_date=date_text,
        captured_at=captured_at,
        written_files=tuple(written),
        errors=tuple(errors),
    )
    _write_status(base, result)
    return result


def _fetch_rows(
    module: ModuleType,
    function_name: str,
    errors: list[str],
    **kwargs: str,
) -> list[dict[str, object]]:
    try:
        function = module.__dict__[function_name]
        frame = cast(FrameLike, function(**kwargs))
        rows = frame.to_dict("records")
    except Exception as exc:
        errors.append(f"{function_name}: {type(exc).__name__}: {exc}")
        return []
    return [
        dict(row)
        for row in rows
        if isinstance(row, dict)
    ]


def _build_daily_snapshot(
    trade_date: str,
    captured_at: str,
    spot_rows: Sequence[Mapping[str, object]],
    limit_up_rows: Sequence[Mapping[str, object]],
    limit_down_rows: Sequence[Mapping[str, object]],
    errors: Sequence[str],
    quality: str,
    freshness: str,
) -> dict[str, object]:
    pct_values = [
        value
        for row in spot_rows
        if (value := _number(row.get("涨跌幅"))) is not None
    ]
    advancers = sum(1 for value in pct_values if value > 0)
    decliners = sum(1 for value in pct_values if value < 0)
    total_amount = sum(
        value
        for row in spot_rows
        if (value := _number(row.get("成交额"))) is not None
    )
    industry_counts: dict[str, int] = {}
    for row in limit_up_rows:
        industry = str(row.get("所属行业") or "未分类").strip() or "未分类"
        industry_counts[industry] = industry_counts.get(industry, 0) + 1
    themes = [
        {
            "concept": industry,
            "priority_score": float(count * 10),
            "trigger_types": ["akshare_limit_up_pool"],
            "limit_up_count": count,
            "new_high_count": None,
            "strong_stock_count": count,
        }
        for industry, count in sorted(
            industry_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    strong_stocks = [
        {
            "stock_name": str(row.get("名称") or ""),
            "stock_ts_code": _stock_code(str(row.get("代码") or "")),
            "concepts": [
                str(row.get("所属行业"))
            ] if row.get("所属行业") else [],
            "pct_chg": _number(row.get("涨跌幅")),
            "amount": (
                amount / 100_000_000
                if (amount := _number(row.get("成交额"))) is not None
                else None
            ),
        }
        for row in sorted(
            limit_up_rows,
            key=lambda item: _number(item.get("成交额")) or 0.0,
            reverse=True,
        )
        if row.get("名称") and row.get("代码")
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "trade_date": trade_date,
        "generated_at": captured_at,
        "source": "AkShare",
        "source_data_date": trade_date,
        "captured_at": captured_at,
        "freshness": freshness,
        "quality": quality,
        "source_errors": list(errors),
        "market": {
            "stage": _market_stage(advancers, decliners, bool(spot_rows)),
            "total_amount": round(total_amount / 100_000_000, 2)
            if spot_rows
            else None,
            "amount_ratio": None,
            "advancers": advancers if spot_rows else None,
            "decliners": decliners if spot_rows else None,
            "limit_up": len(limit_up_rows),
            "limit_down": len(limit_down_rows),
            "capacity_top3": [],
        },
        "themes": themes,
        "strong_stocks": strong_stocks,
    }


def _market_stage(advancers: int, decliners: int, has_spot: bool) -> str:
    if not has_spot:
        return "局部涨跌停快照（全市场行情缺失）"
    breadth = advancers - decliners
    threshold = max(100, (advancers + decliners) // 10)
    if breadth > threshold:
        return "上涨阶段"
    if breadth < -threshold:
        return "下跌阶段"
    return "震荡阶段"


def _stock_code(code: str) -> str:
    cleaned = code.strip()
    if cleaned.startswith(("60", "68")):
        return f"{cleaned}.SH"
    if cleaned.startswith(("00", "30")):
        return f"{cleaned}.SZ"
    if cleaned.startswith(("4", "8", "9")):
        return f"{cleaned}.BJ"
    return cleaned


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _atomic_json_write(path: Path, value: Mapping[str, object]) -> Path:
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


def _write_status(base: Path, result: SnapshotSyncResult) -> None:
    _atomic_json_write(base / "akshare_status.json", result.to_dict())
