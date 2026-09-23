"""Synthetic captured bytes only: no network, credentials or production database."""
from copy import deepcopy
from datetime import date
import hashlib
import json

import pytest

from scripts.audit_dated_quote_capture import audit_capture, main, parse_quotes

DAY = date(2026, 9, 21)


def quote(symbol="sh600001", *, fields=None):
    values = [""] * 58
    defaults = {1: "Example", 2: symbol[2:], 3: "10", 4: "10", 5: "10", 6: "100",
                30: "20260921150001", 32: "0", 33: "11", 34: "9",
                35: "10/100/100000", 38: "1", 40: "0"}
    defaults.update(fields or {})
    for index, value in defaults.items():
        values[index] = value
    return (f'v_{symbol}="' + "~".join(values) + '";\n').encode("gbk")


def capture(tmp_path, raw=None):
    raw = quote() if raw is None else raw
    (tmp_path / "batch.raw").write_bytes(raw)
    entry = {"file": "batch.raw", "sha256": hashlib.sha256(raw).hexdigest(),
             "codes": ["600001.SH"], "http_status": 200}
    receipt = {"target_date": str(DAY), "codes": ["600001.SH"],
               "captured_code_count": 1, "batches": [entry]}
    (tmp_path / "receipt.json").write_text(json.dumps(receipt))
    return receipt


def test_replay_is_evidence_not_publication_authority(tmp_path):
    capture(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = audit_capture(tmp_path, DAY)
    assert result["capture_validated"] is True
    assert result["validated_quote_count"] == 1
    assert result["volume_units"] == {"hands": 1}
    for key in ("production_ready", "database_writes", "publication_attempted",
                "independent_market_universe_verified", "official_suspension_status_verified"):
        assert result[key] is False
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize("symbol", ["sh688001", "sh689009"])
def test_share_unit_and_notional_check(symbol):
    raw = quote(symbol, fields={6: "10000", 35: "10/10000/100000"})
    result = parse_quotes(raw, DAY)[symbol[2:] + ".SH"]
    assert result["volume_shares"] == 10000
    assert result["raw_volume_unit"] == "shares"
    with pytest.raises(ValueError, match="volume unit"):
        parse_quotes(quote(symbol), DAY)


@pytest.mark.parametrize("fields", [
    {30: "20260918150001"}, {30: "20260921145959"}, {2: "600002"},
    {3: "nan"}, {4: "0"}, {6: "-1"}, {6: "1.5"}, {38: "-1"},
    {35: "10/100/1000"}, {35: "10/100/0"}, {35: "10/99/100000"},
    {35: "10/100"}, {33: "8"}, {34: "12"}, {1: ""},
])
def test_bad_quote_is_refused(fields):
    with pytest.raises(ValueError):
        parse_quotes(quote(fields=fields), DAY)


def test_zero_activity_not_inferred_from_status_label():
    fields = {5: "0", 6: "0", 33: "0", 34: "0", 35: "10/0/0", 40: "S"}
    result = parse_quotes(quote(fields=fields), DAY)["600001.SH"]
    assert result["volume_shares"] == 0
    assert "suspended" not in result
    for changes in ({35: "10/0/1"}, {32: "1"}, {4: "9"}, {5: "10"}):
        with pytest.raises(ValueError):
            parse_quotes(quote(fields={**fields, **changes}), DAY)


@pytest.mark.parametrize("raw", [b"", b'v_sh600001="";\n', b"unexpected\n", quote() * 2])
def test_no_silent_skipping_of_empty_malformed_or_duplicate_rows(raw):
    with pytest.raises(ValueError):
        parse_quotes(raw, DAY)


def test_changed_raw_refused(tmp_path):
    capture(tmp_path)
    with (tmp_path / "batch.raw").open("ab") as stream:
        stream.write(b"\n")
    with pytest.raises(ValueError, match="hash changed"):
        audit_capture(tmp_path, DAY)


@pytest.mark.parametrize("mutation", ["date", "duplicate", "missing", "unexpected",
                                     "count", "path", "failed", "same_file"])
def test_receipt_mutations_refused(tmp_path, mutation):
    receipt = capture(tmp_path)
    batch = receipt["batches"][0]
    if mutation == "date":
        receipt["target_date"] = "2026-09-18"
    elif mutation == "duplicate":
        receipt["codes"] *= 2
    elif mutation == "missing":
        receipt["codes"].append("600002.SH")
    elif mutation == "unexpected":
        batch["codes"] = ["600002.SH"]
    elif mutation == "count":
        receipt["captured_code_count"] = 2
    elif mutation == "path":
        batch["file"] = "../batch.raw"
    elif mutation == "failed":
        batch["error_type"] = "TimeoutError"
    else:
        receipt["batches"].append(deepcopy(batch))
    (tmp_path / "receipt.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        audit_capture(tmp_path, DAY)


def test_response_scope_must_equal_batch_even_with_fresh_hash(tmp_path):
    capture(tmp_path, quote("sh600002"))
    with pytest.raises(ValueError, match="identities"):
        audit_capture(tmp_path, DAY)


def test_symlink_refused(tmp_path):
    capture(tmp_path)
    (tmp_path / "batch.raw").rename(tmp_path / "other.raw")
    (tmp_path / "batch.raw").symlink_to("other.raw")
    with pytest.raises(ValueError, match="symlink"):
        audit_capture(tmp_path, DAY)


def test_cli_never_overwrites_evidence_and_returns_failure(tmp_path, capsys):
    capture(tmp_path)
    args = ["--capture-dir", str(tmp_path), "--trade-date", str(DAY),
            "--json", str(tmp_path / "out.json")]
    assert main(args) == 0
    capsys.readouterr()
    original = (tmp_path / "out.json").read_bytes()
    assert main(args) == 2
    assert (tmp_path / "out.json").read_bytes() == original
    result = json.loads(capsys.readouterr().out)
    assert result["error_type"] == "FileExistsError"
    assert result["capture_validated"] is False
