import io
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts.pull_aihot_attention import fetch_export


def page(items, cursor=None):
    return {"schemaVersion": 1, "items": items, "page": {"hasMore": cursor is not None, "nextCursor": cursor}}


def test_full_public_scope_and_cursor_walk_without_paid_services():
    calls = []
    pages = iter([page([{"id": "a"}], "cursor-1"), page([{"id": "a"}, {"id": "b"}])])
    def opener(request, timeout):
        calls.append(request.full_url)
        return io.BytesIO(json.dumps(next(pages)).encode())
    data = fetch_export("https://example.com", opener=opener)
    assert [r["id"] for r in data["items"]] == ["a", "b"]
    q = parse_qs(urlsplit(calls[0]).query)
    assert q["mode"] == ["all"] and q["by"] == ["published"]
    assert "cursor=cursor-1" in calls[1]


def test_budget_exhaustion_is_not_complete_success():
    with pytest.raises(ValueError, match="budget"):
        fetch_export("https://example.com", pages=1, opener=lambda *a, **k: io.BytesIO(json.dumps(page([], "more")).encode()))


def test_missing_pagination_or_bad_schema_fails_closed():
    for data in [{"schemaVersion": 1, "items": []}, {"schemaVersion": 2, "items": [], "page": {"hasMore": False}}]:
        with pytest.raises(ValueError):
            fetch_export("https://example.com", opener=lambda *a, **k: io.BytesIO(json.dumps(data).encode()))


def test_credentials_and_invalid_schemes_not_accepted():
    for url in ["file:///etc", "https://user:secret@example.com", "https://example.com?token=secret"]:
        with pytest.raises(ValueError):
            fetch_export(url, opener=lambda *a, **k: pytest.fail("must not fetch"))
