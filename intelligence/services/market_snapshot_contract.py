from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_DAILY_TOP_LEVEL = ("schema_version", "trade_date", "market", "themes", "strong_stocks")
REQUIRED_MARKET_FIELDS = (
    "stage",
    "total_amount",
    "amount_ratio",
    "advancers",
    "decliners",
    "limit_up",
    "limit_down",
    "capacity_top3",
)
REQUIRED_THEME_FIELDS = ("concept", "priority_score", "trigger_types")
REQUIRED_STOCK_FIELDS = ("stock_name", "stock_ts_code", "concepts", "pct_chg", "amount")


def validate_market_snapshot_root(root: str | Path, date: str | None = None) -> dict[str, Any]:
    base = Path(root).expanduser()
    errors: list[str] = []
    warnings: list[str] = []
    files = {
        "root": str(base),
        "daily": "",
        "latest": str(base / "latest.json"),
        "meta": str(base / "meta.json"),
    }

    meta = _read_json(base / "meta.json")
    if meta is None:
        warnings.append("missing meta.json")
        meta = {}

    target_date = date or str(meta.get("latest_trade_date") or "").strip()
    if not target_date:
        errors.append("missing date: pass --date or provide meta.latest_trade_date")
        return _result("FAIL", base, "", files, errors, warnings, {}, meta)

    daily_path = base / f"{target_date}.json"
    files["daily"] = str(daily_path)
    daily = _read_json(daily_path)
    if daily is None:
        errors.append(f"missing daily snapshot: {daily_path.name}")
        return _result("FAIL", base, target_date, files, errors, warnings, {}, meta)

    latest = _read_json(base / "latest.json")
    if latest is None:
        warnings.append("missing latest.json")

    _validate_daily_doc(daily, target_date, errors, warnings)
    _validate_meta(meta, target_date, warnings)
    quality, freshness = _validate_quality(daily, meta, errors, warnings)
    if latest and str(latest.get("trade_date") or "") != target_date:
        warnings.append(f"latest.json trade_date mismatch: {latest.get('trade_date')} != {target_date}")

    summary = {
        "theme_count": len(daily.get("themes") or []) if isinstance(daily.get("themes"), list) else 0,
        "strong_stock_count": len(daily.get("strong_stocks") or []) if isinstance(daily.get("strong_stocks"), list) else 0,
        "market_stage": (daily.get("market") or {}).get("stage") if isinstance(daily.get("market"), dict) else None,
        "latest_trade_date": meta.get("latest_trade_date"),
        "requested_trade_date": daily.get("requested_trade_date")
        or meta.get("requested_trade_date")
        or target_date,
        "served_trade_date": daily.get("served_trade_date")
        or meta.get("served_trade_date")
        or target_date,
        "provider": daily.get("provider") or meta.get("provider"),
        "source": daily.get("source") or meta.get("source"),
        "source_updated_at": daily.get("source_updated_at")
        or meta.get("source_updated_at"),
        "quality": quality,
        "freshness": freshness,
    }
    status = "FAIL" if errors else "WARN" if warnings else "PASS"
    return _result(status, base, target_date, files, errors, warnings, summary, meta)


def _validate_daily_doc(doc: dict[str, Any], target_date: str, errors: list[str], warnings: list[str]) -> None:
    for field in REQUIRED_DAILY_TOP_LEVEL:
        if field not in doc:
            errors.append(f"missing daily field: {field}")
    if str(doc.get("trade_date") or "") != target_date:
        errors.append(f"daily trade_date mismatch: {doc.get('trade_date')} != {target_date}")

    market = doc.get("market")
    if not isinstance(market, dict):
        errors.append("market must be an object")
    else:
        for field in REQUIRED_MARKET_FIELDS:
            if field not in market:
                warnings.append(f"missing market.{field}")

    themes = doc.get("themes")
    if not isinstance(themes, list):
        errors.append("themes must be a list")
    else:
        for idx, item in enumerate(themes[:20]):
            if not isinstance(item, dict):
                warnings.append(f"themes[{idx}] must be an object")
                continue
            for field in REQUIRED_THEME_FIELDS:
                if field not in item:
                    warnings.append(f"missing themes[{idx}].{field}")

    stocks = doc.get("strong_stocks")
    if not isinstance(stocks, list):
        errors.append("strong_stocks must be a list")
    else:
        for idx, item in enumerate(stocks[:20]):
            if not isinstance(item, dict):
                warnings.append(f"strong_stocks[{idx}] must be an object")
                continue
            for field in REQUIRED_STOCK_FIELDS:
                if field not in item:
                    warnings.append(f"missing strong_stocks[{idx}].{field}")


def _validate_meta(meta: dict[str, Any], target_date: str, warnings: list[str]) -> None:
    if not meta:
        return
    latest = str(meta.get("latest_trade_date") or "")
    if not latest:
        warnings.append("missing meta.latest_trade_date")
    elif latest != target_date:
        warnings.append(f"meta latest_trade_date mismatch: {latest} != {target_date}")
    if "schema_version" not in meta:
        warnings.append("missing meta.schema_version")
    if "updated_at" not in meta:
        warnings.append("missing meta.updated_at")


def _validate_quality(
    daily: dict[str, Any],
    meta: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> tuple[str, str]:
    quality = str(daily.get("quality") or meta.get("quality") or "").strip()
    freshness = str(
        daily.get("freshness") or meta.get("freshness") or ""
    ).strip()
    if not quality:
        warnings.append("missing snapshot quality")
    elif quality == "failed":
        errors.append("snapshot quality is failed")
    elif quality != "complete":
        warnings.append(f"snapshot quality is not decision-ready: {quality}")
    if not freshness:
        warnings.append("missing snapshot freshness")
    elif freshness not in {"fresh", "historical"}:
        warnings.append(f"snapshot freshness is not decision-ready: {freshness}")
    return quality or "unknown", freshness or "unknown"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _result(
    status: str,
    root: Path,
    date: str,
    files: dict[str, str],
    errors: list[str],
    warnings: list[str],
    summary: dict[str, Any],
    meta: dict[str, Any],
) -> dict[str, Any]:
    quality = str(summary.get("quality") or "unknown")
    freshness = str(summary.get("freshness") or "unknown")
    ready = (
        status == "PASS"
        and quality == "complete"
        and freshness in {"fresh", "historical"}
    )
    return {
        "status": status,
        "ready": ready,
        "root": str(root),
        "date": date,
        "files": files,
        "summary": summary,
        "meta": meta,
        "errors": errors,
        "warnings": warnings,
        "contract": {
            "daily_files": ["YYYY-MM-DD.json", "latest.json", "meta.json"],
            "required_daily_top_level": list(REQUIRED_DAILY_TOP_LEVEL),
            "required_market_fields": list(REQUIRED_MARKET_FIELDS),
            "required_theme_fields": list(REQUIRED_THEME_FIELDS),
            "required_stock_fields": list(REQUIRED_STOCK_FIELDS),
        },
    }
