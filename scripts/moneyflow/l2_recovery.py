"""Explicit, dated inputs for a historical L2 scan; no data-source inference."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse


def suspension_exclusions(
    date: str, limitup: list[str], top100: list[str], pct_map: dict[str, float],
    *, database_path: str | Path,
) -> tuple[set[str], str]:
    """Validate an operator-reviewed notice input and retain its exact receipt.

    A missing tick or daily quote is never suspension evidence. The operator
    must review the official notice and supply a date-specific, hashed input;
    the scan additionally rejects contradictory same-day market observations.
    """
    configured = os.environ.get("L2_SUSPENSION_EVIDENCE", "").strip()
    if not configured:
        return set(), ""
    path = Path(configured).expanduser()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("trade_date") != date:
            raise ValueError("date mismatch")
        entries = payload.get("entries")
        if not isinstance(entries, list) or not entries or len(entries) > 100:
            raise ValueError("explicit entries required")
        # A quote with a NULL percentage can still prove trading. Read actual
        # turnover/volume instead of treating the percentage map as all quotes.
        # A retained-price, zero-volume suspension shell is not trading proof.
        import duckdb

        with duckdb.connect(str(database_path), read_only=True) as con:
            traded_codes = {row[0] for row in con.execute(
                "SELECT substr(stock_ts_code, 1, 6) FROM fact_stock_daily "
                "WHERE trade_date = ? AND (coalesce(amount, 0) <> 0 OR coalesce(volume, 0) <> 0)",
                [date],
            ).fetchall()}
        excluded: set[str] = set()
        receipts = []
        official_hosts = {
            "static.cninfo.com.cn", "www.cninfo.com.cn", "www.szse.cn",
            "disc.static.szse.cn", "www.sse.com.cn", "static.sse.com.cn",
        }
        for entry in entries:
            code = str(entry["stock_code"])
            if len(code) != 6 or not code.isdecimal() or code in excluded:
                raise ValueError("invalid or duplicate code")
            if code not in limitup or code in top100 or code in pct_map or code in traded_codes:
                raise ValueError("not an absent prior-limitup candidate")
            source_url = str(entry["source_url"])
            url = urlparse(source_url)
            if url.scheme != "https" or url.hostname not in official_hosts:
                raise ValueError("official notice URL required")
            reason = str(entry.get("reason") or "").strip()
            if not reason or len(reason) > 400:
                raise ValueError("bounded reviewed reason required")
            source = Path(entry["evidence_path"]).expanduser()
            if not source.is_absolute():
                source = path.parent / source
            content = source.read_bytes()
            sha = hashlib.sha256(content).hexdigest()
            if not content or sha != entry["evidence_sha256"]:
                raise ValueError("notice bytes changed")
            excluded.add(code)
            receipts.append({"stock_code": code, "source_url": source_url,
                             "evidence_sha256": sha, "reason": reason})
        return excluded, json.dumps(receipts, ensure_ascii=False, sort_keys=True)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"invalid suspension evidence: {exc}") from exc
