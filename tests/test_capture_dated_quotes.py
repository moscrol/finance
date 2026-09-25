"""The live collector is exercised with synthetic bytes and no provider access."""
from datetime import date
from io import BytesIO
import json
import urllib.error

import pytest

from scripts import capture_dated_quotes as capture
from scripts.audit_dated_quote_capture import audit_capture

DAY = date(2026, 9, 24)


def quote(code="600001.SH", stamp="20260924150001"):
    fields = [""] * 58
    for index, value in {1: "Example", 2: code[:6], 3: "10", 4: "10", 5: "10",
                         6: "100", 30: stamp, 32: "0", 33: "11", 34: "9",
                         35: "10/100/100000", 38: "1", 40: "0"}.items():
        fields[index] = value
    return (f'v_{code[-2:].lower()}{code[:6]}="' + "~".join(fields) + '";\n').encode("gbk")


class Response(BytesIO):
    status = 200


@pytest.fixture
def setup(tmp_path, monkeypatch):
    scope = tmp_path / "scope-input.json"
    scope.write_text(json.dumps({"trade_date": str(DAY), "codes": ["600001.SH", "600002.SH"],
                                 "scope_basis": "synthetic declared scope"}))
    calls = []

    def fetch(request, timeout):
        calls.append((request.full_url, timeout))
        symbols = request.full_url.split("q=")[1].split(",")
        return Response(b"".join(quote(s[2:] + "." + s[:2].upper()) for s in symbols))

    monkeypatch.setattr(capture.urllib.request, "urlopen", fetch)
    monkeypatch.setattr(capture.time, "sleep", lambda seconds: None)
    return scope, tmp_path / "capture", calls


def test_capture_and_independent_replay(setup):
    scope, output, calls = setup
    result = capture.capture_quotes(scope, output, DAY, batch_size=1)
    assert result["capture_validated"] is True
    assert result["validated_quote_count"] == 2
    assert len(calls) == 2 and all(timeout == 15 for _, timeout in calls)
    assert result == audit_capture(output, DAY)
    assert (output / "scope.json").read_bytes() == scope.read_bytes()
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["status"] == "complete"
    for key in ("official_historical_universe_verified", "database_writes",
                "publication_attempted", "production_ready"):
        assert receipt[key] is False


def test_existing_evidence_is_untouched_and_no_network(setup):
    scope, output, calls = setup
    output.mkdir()
    (output / "receipt.json").write_text("original")
    with pytest.raises(FileExistsError):
        capture.capture_quotes(scope, output, DAY)
    assert (output / "receipt.json").read_text() == "original"
    assert calls == []


@pytest.mark.parametrize("change", [
    {"trade_date": "2026-09-23"}, {"codes": []}, {"codes": ["bad"]},
    {"codes": ["600001.SH", "600001.SH"]}, {"scope_basis": ""}, {"scope_basis": None},
    {"codes": ["200016.SZ"]}, {"codes": ["600001.SZ"]},
])
def test_invalid_scope_refused_before_creating_output_or_network(setup, change):
    scope, output, calls = setup
    payload = json.loads(scope.read_text())
    scope.write_text(json.dumps({**payload, **change}))
    with pytest.raises(ValueError):
        capture.capture_quotes(scope, output, DAY)
    assert not output.exists() and calls == []


@pytest.mark.parametrize("options", [
    {"batch_size": 0}, {"batch_size": 81}, {"batch_size": True},
    {"sleep_seconds": -1}, {"sleep_seconds": 0}, {"sleep_seconds": float("nan")},
    {"timeout": 0}, {"timeout": 61}, {"timeout": float("inf")},
])
def test_limits_refused_before_network(setup, options):
    scope, output, calls = setup
    with pytest.raises(ValueError):
        capture.capture_quotes(scope, output, DAY, **options)
    assert not output.exists() and calls == []


@pytest.mark.parametrize("error", [
    TimeoutError("connection failed"), urllib.error.URLError("failed"),
    urllib.error.HTTPError("https://provider.test", 429, "limited", {}, None),
])
def test_transport_failure_stops_without_retries_and_retains_prior_batch(setup, monkeypatch, error):
    scope, output, _ = setup
    original = capture.urllib.request.urlopen
    calls = 0

    def fetch(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise error
        return original(request, timeout)

    monkeypatch.setattr(capture.urllib.request, "urlopen", fetch)
    result = capture.capture_quotes(scope, output, DAY, batch_size=1)
    assert result["capture_validated"] is False and calls == 2
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["status"] == "incomplete" and receipt["captured_code_count"] == 1
    assert (output / "000.raw").read_bytes() == quote()
    assert receipt["batches"][1]["error_type"] == type(error).__name__
    if isinstance(error, urllib.error.HTTPError):
        assert receipt["batches"][1]["http_status"] == 429
    with pytest.raises(ValueError):
        audit_capture(output, DAY)


@pytest.mark.parametrize("raw", [
    quote(stamp="20260923150001"), quote("600009.SH"), quote() * 2, b"bad response", b"",
])
def test_semantic_failure_keeps_original_bytes_and_remains_incomplete(setup, monkeypatch, raw):
    scope, output, _ = setup
    monkeypatch.setattr(capture.urllib.request, "urlopen", lambda *a, **k: Response(raw))
    result = capture.capture_quotes(scope, output, DAY)
    assert result["capture_validated"] is False
    assert (output / "000.raw").read_bytes() == raw
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["status"] == "incomplete" and receipt["captured_code_count"] == 0


def test_non_200_success_class_response_stops_remaining_batches(setup, monkeypatch):
    scope, output, _ = setup
    calls = []

    def fetch(*args, **kwargs):
        calls.append(args)
        response = Response(b"")
        response.status = 204
        return response

    monkeypatch.setattr(capture.urllib.request, "urlopen", fetch)
    assert capture.capture_quotes(scope, output, DAY, batch_size=1)["capture_validated"] is False
    assert len(calls) == 1 and (output / "000.raw").read_bytes() == b""


def test_interruption_records_attempted_batch(setup, monkeypatch):
    scope, output, _ = setup

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(capture.urllib.request, "urlopen", interrupt)
    with pytest.raises(KeyboardInterrupt):
        capture.capture_quotes(scope, output, DAY)
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["status"] == "interrupted"
    assert receipt["batches"][0]["codes"] == ["600001.SH", "600002.SH"]
    assert not (output / "audit.json").exists()


def test_oversized_response_kept_bounded_and_refused(setup, monkeypatch):
    scope, output, _ = setup
    monkeypatch.setattr(capture, "MAX_RESPONSE_BYTES", 50)
    monkeypatch.setattr(capture.urllib.request, "urlopen", lambda *a, **k: Response(quote()))
    assert capture.capture_quotes(scope, output, DAY)["capture_validated"] is False
    assert (output / "000.raw").stat().st_size == 51


@pytest.mark.parametrize("day", [date(2026, 9, 26), date(2027, 1, 4)])
def test_nontrading_or_unknown_calendar_refused_before_network(setup, day):
    scope, output, calls = setup
    payload = json.loads(scope.read_text())
    scope.write_text(json.dumps({**payload, "trade_date": str(day)}))
    with pytest.raises(ValueError):
        capture.capture_quotes(scope, output, day)
    assert not output.exists() and calls == []


def test_cli_exit_codes_and_existing_directory(setup):
    scope, output, _ = setup
    args = ["--scope-json", str(scope), "--output-dir", str(output), "--trade-date", str(DAY)]
    assert capture.main(args) == 0
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    assert capture.main(args) == 2
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}
