#!/usr/bin/env python3
"""Explicit bounded AIHOT /api/v1/items pull, followed by the offline import contract.

Dry-run still reads the supplied instance; only --apply appends the private ledger.
Only public eligible items in that instance's 7d publication window are requested.
No article crawling, automatic redirects, models, or scheduled/background collection.
"""
from __future__ import annotations

import json
import math
import sys
import time
from concurrent.futures import Future, TimeoutError as FutureTimeout
from http.client import HTTPException
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_aihot_attention import (  # noqa: E402
    MAX_MAPPING_BYTES,
    ImportRejected,
    SafeArgumentParser,
    add_unique_items,
    decode_json,
    import_payload,
    load_json,
    page_cursor,
    print_error,
    validate_mapping,
)

MAX_RESPONSE_BYTES = 4 * 1024 * 1024
PAGE_SIZE = 100
DEFAULT_TIMEOUT = 15.0
DEFAULT_TOTAL_TIMEOUT = 120.0


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        fp.close()
        raise ImportRejected("AIHOT HTTP redirects are refused; supply the final instance URL")


def _endpoint(base_url: str) -> str:
    try:
        # urlsplit normalizes some control/whitespace characters; reject before parsing.
        if (not isinstance(base_url, str) or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in base_url)
                or "?" in base_url or "#" in base_url or "\\" in base_url):
            raise ValueError
        parts = urlsplit(base_url)
        if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username is not None
                or parts.password is not None or parts.port == 0 or parts.query or parts.fragment):
            raise ValueError
        # Percent-encoded hosts can be decoded into a different authority by urllib.
        if "%" in parts.netloc:
            raise ValueError
        base_url.encode("ascii")
    except (ValueError, UnicodeError) as exc:
        raise ImportRejected("base URL must be credential-free ASCII http(s), without query or fragment") from exc
    return base_url.rstrip("/") + "/api/v1/items"


def _seconds(value: Any, *, maximum: float, label: str) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            or not 0 < value <= maximum):
        raise ImportRejected(f"{label} must be finite, positive and at most {maximum:g} seconds")
    return float(value)


def _read_page(request: Request, *, opener, timeout: float, deadline: float) -> bytes:
    """Keep a slow connect/read from defeating the caller's wall-clock budget.

    This one daemon worker only reads one bounded response; it never imports, writes
    or starts another request. read1 checks the deadline between network reads.
    The foreground stops waiting at the deadline even if DNS/socket I/O stalls.
    """
    result: Future[bytes] = Future()

    def read() -> None:
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ImportRejected("AIHOT total time budget exhausted")
            with opener(request, timeout=min(timeout, remaining)) as response:
                if hasattr(response, "geturl") and response.geturl() != request.full_url:
                    raise ImportRejected("AIHOT response changed the requested target")
                if hasattr(response, "status") and response.status != 200:
                    raise ImportRejected("AIHOT response must have HTTP status 200")
                length = response.headers.get("Content-Length") if hasattr(response, "headers") else None
                if length is not None:
                    if not length.isdecimal() or int(length) > MAX_RESPONSE_BYTES:
                        raise ImportRejected("invalid or oversized AIHOT Content-Length")
                    length = int(length)
                chunks: list[bytes] = []
                size = 0
                read_chunk = getattr(response, "read1", response.read)
                while True:
                    if time.monotonic() >= deadline:
                        raise ImportRejected("AIHOT total time budget exhausted")
                    chunk = read_chunk(min(65536, MAX_RESPONSE_BYTES + 1 - size))
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        raise ImportRejected("AIHOT page exceeds response byte budget")
                    chunks.append(chunk)
                if length is not None and size != length:
                    raise ImportRejected("incomplete AIHOT response body")
                result.set_result(b"".join(chunks))
        except ImportRejected as exc:
            result.set_exception(exc)
        except (OSError, HTTPException, ValueError):
            # Never echo upstream reason strings, redirect locations or response bodies.
            result.set_exception(ImportRejected("AIHOT request failed; check instance availability and timeout"))

    Thread(target=read, name="aihot-page-read", daemon=True).start()
    try:
        return result.result(timeout=max(0.0, deadline - time.monotonic()))
    except FutureTimeout as exc:
        raise ImportRejected("AIHOT total time budget exhausted") from exc


def fetch_export(
    base_url: str, *, pages: int = 10, timeout: float = DEFAULT_TIMEOUT,
    total_timeout: float = DEFAULT_TOTAL_TIMEOUT, opener=None,
) -> dict[str, Any]:
    endpoint = _endpoint(base_url)
    if type(pages) is not int or not 1 <= pages <= 50:
        raise ImportRejected("pages must be between 1 and 50")
    timeout = _seconds(timeout, maximum=60, label="timeout")
    total_timeout = _seconds(total_timeout, maximum=300, label="total timeout")
    deadline = time.monotonic() + total_timeout
    # Do not inherit proxy credentials or netrc/auth state from the environment.
    if opener is None:
        opener = build_opener(ProxyHandler({}), NoRedirects()).open
    collected: list[dict[str, Any]] = []
    cursors: set[str] = set()
    identities: dict[str, str] = {}
    cursor = None
    for _ in range(pages):
        if time.monotonic() >= deadline:
            raise ImportRejected("AIHOT total time budget exhausted")
        params = {"mode": "all", "window": "7d", "by": "published", "limit": PAGE_SIZE}
        if cursor:
            params["cursor"] = cursor
        request = Request(endpoint + "?" + urlencode(params), headers={
            "Accept": "application/json", "User-Agent": "FinanceAttentionImporter/1.0",
        })
        raw = _read_page(request, opener=opener, timeout=timeout, deadline=deadline)
        data = decode_json(raw)
        cursor = page_cursor(data, item_limit=PAGE_SIZE)
        add_unique_items(data["items"], identities, collected)
        if time.monotonic() >= deadline:
            raise ImportRejected("AIHOT total time budget exhausted")
        if cursor is None:
            return {"schemaVersion": 1, "items": collected, "page": {"hasMore": False, "nextCursor": None},
                    "scope": "public_eligible_7d", "pages": _ + 1}
        if cursor in cursors:
            raise ImportRejected("repeated pagination cursor")
        cursors.add(cursor)
    raise ImportRejected("page budget exhausted; refusing to import an incomplete pull")


def main(argv: list[str] | None = None) -> int:
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="explicit instance root, optionally including a mount path")
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--max-pages", type=int, default=10, help="1–50 pages, 100 items per page")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="socket timeout, >0 and <=60 seconds")
    parser.add_argument("--total-timeout", type=float, default=DEFAULT_TOTAL_TIMEOUT, help="whole pull deadline, >0 and <=300 seconds")
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--apply", action="store_true", help="append after full validation; default is dry-run")
    args = parser.parse_args(argv)
    try:
        mapping = validate_mapping(load_json(args.mapping, limit=MAX_MAPPING_BYTES))
        payload = fetch_export(args.base_url, pages=args.max_pages, timeout=args.timeout, total_timeout=args.total_timeout)
        report = import_payload(payload, mapping, apply=args.apply, ledger=args.ledger)
        report.update(scope=payload["scope"], pages=payload["pages"])
    except ImportRejected as exc:
        return print_error(str(exc))
    except OSError:
        return print_error("ledger I/O failed; inspect the ledger before retrying", written=None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
