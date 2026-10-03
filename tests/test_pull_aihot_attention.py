"""Bounded public API contract tests; network tests bind only to loopback."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from intelligence.services.opinion_attention import read_ledger
from scripts import pull_aihot_attention as puller
from scripts.import_aihot_attention import ImportRejected, import_payload

ROOT = Path(__file__).resolve().parents[1]


def item(identity="a", **changes):
    return {"id": identity, "title": "Unreviewed public item", "source": "Example", "summary": "Unverified",
            "publishedAt": "2020-01-01T00:00:00Z", "links": {"original": f"https://example.invalid/{identity}"}, **changes}


def page(items, cursor=None):
    return {"schemaVersion": 1, "items": items, "page": {"hasMore": cursor is not None, "nextCursor": cursor}}


def fake_opener(*values):
    responses = iter(values)

    def open_response(request, timeout):
        return io.BytesIO(json.dumps(next(responses)).encode())

    return open_response


def test_full_public_scope_cursor_walk_and_identical_duplicate_replay():
    calls = []
    open_page = fake_opener(page([item()], "cursor/one?"), page([item(), item("b")]))

    def opener(request, timeout):
        calls.append((request.full_url, timeout))
        return open_page(request, timeout)

    data = puller.fetch_export("https://example.invalid/mounted/", opener=opener)
    assert [row["id"] for row in data["items"]] == ["a", "b"]
    assert data["scope"] == "public_eligible_7d" and data["pages"] == 2
    assert data["page"]["hasMore"] is False
    assert urlsplit(calls[0][0]).path == "/mounted/api/v1/items"
    assert parse_qs(urlsplit(calls[0][0]).query) == {"mode": ["all"], "by": ["published"], "window": ["7d"], "limit": ["100"]}
    assert parse_qs(urlsplit(calls[1][0]).query)["cursor"] == ["cursor/one?"]
    assert all(0 < timeout <= 15 for _, timeout in calls)


@pytest.mark.parametrize("url", [
    "file:///etc", "ftp://example.invalid", "https://user:secret@example.invalid", "https://@example.invalid",
    "https://example.invalid?token=secret", "https://example.invalid?", "https://example.invalid#secret", "https://example.invalid#",
    "https://example.invalid:bad", "https://example.invalid:70000", "https://example.invalid:0", "https://[bad",
    "https://example.invalid\n", " https://example.invalid", "https://example.invalid/has space", "https://example.invalid\\evil",
    "https://user%40secret%40example.invalid", "https://example.invalid%2Fevil", "https://例子.invalid",
])
def test_invalid_base_url_is_rejected_before_io(url):
    with pytest.raises(ImportRejected, match="base URL") as exc:
        puller.fetch_export(url, opener=lambda *a, **k: pytest.fail("must not fetch"))
    assert "secret" not in str(exc.value)


@pytest.mark.parametrize("kwargs", [
    {"pages": 0}, {"pages": 51}, {"pages": True}, {"pages": 1.5},
    {"timeout": 0}, {"timeout": -1}, {"timeout": float("inf")}, {"timeout": float("nan")}, {"timeout": 61},
    {"total_timeout": 0}, {"total_timeout": float("nan")}, {"total_timeout": 301},
])
def test_budget_values_cannot_disable_limits(kwargs):
    with pytest.raises(ImportRejected):
        puller.fetch_export("https://example.invalid", opener=lambda *a, **k: pytest.fail("must not fetch"), **kwargs)


@pytest.mark.parametrize("pages", [1, 10, 50])
def test_page_budget_exhaustion_is_not_complete_success(pages):
    responses = [page([item(str(i))], f"cursor-{i}") for i in range(pages)]
    with pytest.raises(ImportRejected, match="page budget"):
        puller.fetch_export("https://example.invalid", pages=pages, opener=fake_opener(*responses))


@pytest.mark.parametrize("data", [
    {"schemaVersion": 1, "items": []}, {"schemaVersion": 2, "items": [], "page": {"hasMore": False}},
    {"schemaVersion": True, "items": [], "page": {"hasMore": False}}, page(None), [],
    {"schemaVersion": 1, "items": [], "page": {"hasMore": "false"}},
    {"schemaVersion": 1, "items": [], "page": {"hasMore": True}},
    {"schemaVersion": 1, "items": [], "page": {"hasMore": False, "nextCursor": "contradiction"}},
    page([], " "), page([], "x" * 4097), page([], "token\nsecret"), page([], ["secret"]),
    page([None]), page([{"id": []}]), page([{"id": {}}]), page([{"id": True}]), page([{"id": 1}]), page([{"id": ""}]),
    page([item(str(i)) for i in range(101)]),
])
def test_schema_id_count_and_pagination_fail_closed(data):
    with pytest.raises(ImportRejected):
        puller.fetch_export("https://example.invalid", opener=fake_opener(data))


def test_repeated_cursor_and_conflicting_duplicate_fail_instead_of_partial_success():
    for responses, reason in [
        ([page([item()], "same"), page([item("b")], "same")], "repeated"),
        ([page([item()], "next"), page([item(title="Changed")])], "conflicting"),
        ([page([item(), item(summary="Changed")])], "conflicting"),
        ([page([item(selected=True)], "next"), page([item(selected=1)])], "conflicting"),
    ]:
        with pytest.raises(ImportRejected, match=reason):
            puller.fetch_export("https://example.invalid", opener=fake_opener(*responses))


def test_response_byte_limit_is_checked_before_decoding():
    with pytest.raises(ImportRejected, match="byte budget"):
        puller.fetch_export("https://example.invalid", opener=lambda *a, **k: io.BytesIO(b" " * (puller.MAX_RESPONSE_BYTES + 1)))


def test_response_at_byte_limit_is_accepted_and_late_bad_json_is_not():
    raw = json.dumps(page([])).encode()
    raw += b" " * (puller.MAX_RESPONSE_BYTES - len(raw))
    result = puller.fetch_export("https://example.invalid", opener=lambda *a, **k: io.BytesIO(raw))
    assert result["items"] == []
    with pytest.raises(ImportRejected, match="JSON"):
        puller.fetch_export("https://example.invalid", opener=lambda *a, **k: io.BytesIO(b'{"secret": NaN}'))


def test_open_failure_is_safe_and_not_a_traceback():
    def fail(*args, **kwargs):
        raise URLError("https://user:secret@example.invalid")

    with pytest.raises(ImportRejected, match="request failed") as exc:
        puller.fetch_export("https://example.invalid", opener=fail)
    assert "secret" not in str(exc.value)


def test_total_deadline_bounds_blocking_open_without_advancing_page():
    started = Event()
    release = Event()
    calls = []

    def stall(request, timeout):
        calls.append(timeout)
        started.set()
        release.wait(1)
        return io.BytesIO(json.dumps(page([item()], "more")).encode())

    begin = time.monotonic()
    try:
        with pytest.raises(ImportRejected, match="total time budget"):
            puller.fetch_export("https://example.invalid", total_timeout=.05, opener=stall)
        assert started.is_set() and len(calls) == 1 and 0 < calls[0] <= .05
        assert time.monotonic() - begin < .5
    finally:
        release.set()


def test_total_deadline_applies_even_to_successful_slow_reads():
    class SlowBody(io.BytesIO):
        def read1(self, size):
            time.sleep(.04)
            return super().read1(1)

    with pytest.raises(ImportRejected, match="total time budget"):
        puller.fetch_export("https://example.invalid", total_timeout=.06,
                            opener=lambda *a, **k: SlowBody(json.dumps(page([])).encode()))


@contextmanager
def local_instance(reply, *, drip_delay=0):
    paths = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            paths.append(self.path)
            status, body, headers = reply(self.path)
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, str(value))
            if "Content-Length" not in headers:
                self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                if drip_delay:
                    for byte in body:
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(drip_delay)
                else:
                    self.wfile.write(body)
            except OSError:
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", paths
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def run_pull_cli(base_url, tmp_path, *extra):
    map_path = tmp_path / "mapping.json"
    if not map_path.exists():
        map_path.write_text("{}", encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/pull_aihot_attention.py"), "--base-url", base_url,
         "--mapping", str(map_path), *extra], cwd=ROOT,
        env={**os.environ, "OPINION_ATTENTION_LEDGER": str(tmp_path / "private" / "ledger.jsonl")},
        capture_output=True, text=True, timeout=10,
    )


def test_real_loopback_cli_dry_run_apply_and_replay_without_crawling(tmp_path):
    def reply(path):
        assert urlsplit(path).path == "/api/v1/items"
        query = parse_qs(urlsplit(path).query)
        data = page([item(), item("b")]) if "cursor" in query else page([item()], "next")
        return 200, json.dumps(data).encode(), {"Content-Type": "application/json"}

    ledger = tmp_path / "private" / "ledger.jsonl"
    with local_instance(reply) as (base, paths):
        for extra in ([], ["--apply"], ["--apply"]):
            result = run_pull_cli(base, tmp_path, *extra)
            assert result.returncode == 0, result.stderr
            report = json.loads(result.stdout)
            assert (report["accepted"], report["pages"], report["scope"]) == (2, 2, "public_eligible_7d")
            if not extra:
                assert not ledger.parent.exists() and report["written"] is False
        assert len(paths) == 6
    assert len(read_ledger(ledger)) == 2
    assert report["added"] == 0 and report["skipped"] == 2


@pytest.mark.parametrize("late_page", [
    page([item(title="changed")]), {"items": []}, page([item("b")], "next"),
    page([item("b", title=None)]), page([item("b", publishedAt="9999-01-01T00:00:00Z")]),
])
def test_late_page_errors_leave_existing_ledger_untouched(tmp_path, late_page):
    ledger = tmp_path / "private" / "ledger.jsonl"
    import_payload([item("seed")], {}, apply=True, ledger=ledger)
    before = ledger.read_bytes()

    def reply(path):
        data = late_page if "cursor=" in path else page([item()], "next")
        return 200, json.dumps(data).encode(), {}

    with local_instance(reply) as (base, paths):
        result = run_pull_cli(base, tmp_path, "--apply")
        assert result.returncode == 2 and len(paths) == 2
        assert json.loads(result.stderr)["written"] is False
    assert ledger.read_bytes() == before


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_default_transport_never_follows_cross_target_redirects(tmp_path, status):
    with local_instance(lambda path: (200, json.dumps(page([item()])).encode(), {})) as (target, visits):
        with local_instance(lambda path: (status, b"", {"Location": target + "/secret?token=secret"})) as (base, paths):
            result = run_pull_cli(base, tmp_path, "--apply")
            assert result.returncode == 2 and len(paths) == 1
            assert visits == [] and "secret" not in result.stderr and "redirect" in result.stderr
    assert not (tmp_path / "private").exists()


def test_default_transport_rejects_same_target_redirect_and_incomplete_body():
    with local_instance(lambda path: (302, b"", {"Location": "/different"})) as (base, paths):
        with pytest.raises(ImportRejected, match="redirect"):
            puller.fetch_export(base)
        assert len(paths) == 1
    body = json.dumps(page([])).encode()
    with local_instance(lambda path: (200, body, {"Content-Length": len(body) + 10})) as (base, _):
        with pytest.raises(ImportRejected, match="incomplete"):
            puller.fetch_export(base)


def test_bad_mapping_fails_before_network_and_bad_cli_values_are_redacted(tmp_path):
    (tmp_path / "mapping.json").write_text('{"items": []}', encoding="utf-8")
    with local_instance(lambda path: (200, json.dumps(page([])).encode(), {})) as (base, paths):
        result = run_pull_cli(base, tmp_path, "--apply")
        assert result.returncode == 2 and paths == []
    for extra in (["--timeout", "secret"], ["--max-pages", "secret"], ["--secret=secret"]):
        result = run_pull_cli("https://user:secret@example.invalid", tmp_path, *extra)
        assert result.returncode == 2 and "secret" not in result.stderr and "Traceback" not in result.stderr


def test_cli_ignores_proxy_environment_and_only_contacts_explicit_instance(tmp_path, monkeypatch):
    with local_instance(lambda path: (502, b"secret", {})) as (proxy, proxy_paths):
        for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
            monkeypatch.setenv(key, proxy)
        for key in ("no_proxy", "NO_PROXY"):
            monkeypatch.setenv(key, "")
        with local_instance(lambda path: (200, json.dumps(page([item()])).encode(), {})) as (base, paths):
            result = run_pull_cli(base, tmp_path)
            assert result.returncode == 0, result.stderr
            assert len(paths) == 1 and proxy_paths == []
    assert not (tmp_path / "private").exists()


def test_cli_slow_drip_deadline_exits_without_next_page_or_ledger(tmp_path):
    response = json.dumps(page([item()], "next")).encode()
    with local_instance(lambda path: (200, response, {}), drip_delay=.02) as (base, paths):
        before = time.monotonic()
        result = run_pull_cli(base, tmp_path, "--total-timeout", "0.08", "--apply")
        assert result.returncode == 2 and result.stdout == ""
        report = json.loads(result.stderr)
        assert set(report) == {"error", "written"} and report["written"] is False
        # Either the socket timeout or the foreground deadline can win the race.
        assert report["error"] in {
            "AIHOT total time budget exhausted",
            "AIHOT request failed; check instance availability and timeout",
        }
        assert time.monotonic() - before < 1.5
        assert len(paths) == 1
    assert not (tmp_path / "private").exists()


def test_cli_slow_dns_deadline_exits_without_contacting_instance(tmp_path):
    map_path = tmp_path / "mapping.json"
    map_path.write_text("{}", encoding="utf-8")
    # Delay resolution inside a separate CLI process. The normal successful process
    # path is covered above; a stalled DNS worker must not hold Python open on exit.
    bootstrap = """
import socket
import time
from scripts.pull_aihot_attention import main
original = socket.getaddrinfo
def slow_dns(*args, **kwargs):
    time.sleep(5)
    return original(*args, **kwargs)
socket.getaddrinfo = slow_dns
raise SystemExit(main())
"""
    with local_instance(lambda path: (200, json.dumps(page([item()])).encode(), {})) as (base, paths):
        before = time.monotonic()
        result = subprocess.run(
            [sys.executable, "-c", bootstrap, "--base-url", base, "--mapping", str(map_path),
             "--total-timeout", "0.08", "--ledger", str(tmp_path / "ledger.jsonl"), "--apply"],
            cwd=ROOT, capture_output=True, text=True, timeout=2,
        )
        assert result.returncode == 2 and "total time budget" in result.stderr
        assert time.monotonic() - before < 1.5 and paths == []
    assert not (tmp_path / "ledger.jsonl").exists()


@pytest.mark.parametrize("headers", [
    {"Content-Length": -1}, {"Content-Length": "secret"}, {"Content-Length": puller.MAX_RESPONSE_BYTES + 1},
])
def test_unacceptable_content_length_stops_before_import(tmp_path, headers):
    with local_instance(lambda path: (200, json.dumps(page([item()])).encode(), headers)) as (base, _):
        result = run_pull_cli(base, tmp_path, "--apply")
        assert result.returncode == 2 and "secret" not in result.stderr
    assert not (tmp_path / "private").exists()


def test_upstream_error_body_and_mapping_values_are_never_echoed(tmp_path):
    with local_instance(lambda path: (503, b"upstream secret", {})) as (base, paths):
        result = run_pull_cli(base + "/secret", tmp_path, "--apply")
        assert result.returncode == 2 and len(paths) == 1
        assert "secret" not in result.stderr and "Traceback" not in result.stderr
    (tmp_path / "mapping.json").write_text('{"items":{"secret":{"entity_keys":["secret"]}}}', encoding="utf-8")
    result = run_pull_cli("https://user:secret@example.invalid", tmp_path, "--apply")
    assert result.returncode == 2 and "secret" not in result.stderr
    assert not (tmp_path / "private").exists()
