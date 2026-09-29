#!/usr/bin/env python3
"""Explicit, bounded pull from an AIHOT public API; no daemon, models, or paid APIs.

Defaults to dry-run. Caller must supply the AIHOT instance URL and reviewed mappings.
This fetches all *public eligible* items, not only selected picks, and never calls
original article URLs. A failed/incomplete page walk never writes the opinion ledger.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.services.opinion_attention import adapt_aihot, append_observations, default_ledger_path  # noqa: E402

MAX_RESPONSE_BYTES = 4 * 1024 * 1024


def fetch_export(base_url: str, *, pages: int = 10, timeout: float = 15, opener=urlopen) -> dict:
    parts = urlsplit(base_url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("base URL must be credential-free http(s), without query or fragment")
    if not 1 <= pages <= 50:
        raise ValueError("pages must be between 1 and 50")
    endpoint = base_url.rstrip("/") + "/api/v1/items"
    collected, cursors, identities = [], set(), set()
    cursor = None
    for _ in range(pages):
        params = {"mode": "all", "window": "7d", "by": "published", "limit": 100}
        if cursor:
            params["cursor"] = cursor
        request = Request(endpoint + "?" + urlencode(params), headers={"Accept": "application/json", "User-Agent": "FinanceAttentionImporter/1.0"})
        with opener(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("AIHOT page exceeds response byte budget")
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("schemaVersion") != 1 or not isinstance(data.get("items"), list):
            raise ValueError("unsupported or malformed AIHOT schema")
        for item in data["items"]:
            if not isinstance(item, dict) or not item.get("id"):
                raise ValueError("AIHOT item is missing identity")
            if item["id"] not in identities:
                collected.append(item)
                identities.add(item["id"])
        page = data.get("page")
        if not isinstance(page, dict) or not isinstance(page.get("hasMore"), bool):
            raise ValueError("missing pagination completeness metadata")
        if not page["hasMore"]:
            return {"schemaVersion": 1, "items": collected, "scope": "public_eligible_7d", "base_url": base_url}
        cursor = page.get("nextCursor")
        if not isinstance(cursor, str) or not cursor or cursor in cursors:
            raise ValueError("missing or repeated pagination cursor")
        cursors.add(cursor)
    raise ValueError("page budget exhausted; refusing to import an incomplete pull")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
        payload = fetch_export(args.base_url, pages=args.max_pages)
        observations, errors = adapt_aihot(payload, mapping)
        if errors:
            print(json.dumps({"written": False, "errors": errors}, ensure_ascii=False))
            return 2
        result = {"mode": "apply" if args.apply else "dry-run", "scope": payload["scope"], "items": len(observations),
                  "grouped": sum(r["grouping"] == "reviewed" for r in observations),
                  "mapped": sum(bool(r["entities"]) for r in observations),
                  "note": "成功拉取公开条目不代表连续或全市场采集覆盖。"}
        if args.apply:
            result.update(append_observations(args.ledger or default_ledger_path(), observations))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "written": False}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
