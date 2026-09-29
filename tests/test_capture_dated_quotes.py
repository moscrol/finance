"""Synthetic fetcher only: no network, credentials or database."""
from datetime import date, datetime
import hashlib
import json
import stat

import pytest

from scripts.audit_dated_quote_capture import audit_capture
from scripts.capture_dated_quotes import CST, CaptureRefused, classify, parse_args, run

DAY = date(2026, 9, 29)
AFTER_CLOSE = datetime(2026, 9, 29, 15, 5, tzinfo=CST)


def quote(symbol, *, stamp="20260929150003", name="示例", **fields):
    values = [""] * 58
    defaults = {1: name, 2: symbol[2:], 3: "10", 4: "10", 5: "10", 6: "100",
                30: stamp, 32: "0", 33: "11", 34: "9", 35: "10/100/100000", 38: "1", 40: ""}
    defaults.update({int(k[1:]): v for k, v in fields.items()})
    for index, value in defaults.items():
        values[index] = value
    return f'v_{symbol}="' + "~".join(values) + '";\n'


class FakeTencent:
    """按 symbol 返回报价；可设置某只在第 N 次请求后变坏。"""

    def __init__(self, lines, turn_bad_after=None):
        self.lines = lines
        self.turn_bad_after = turn_bad_after or {}
        self.calls = []

    def __call__(self, symbols):
        self.calls.append(list(symbols))
        out = []
        for s in symbols:
            limit = self.turn_bad_after.get(s)
            if limit is not None and sum(s in c for c in self.calls) > limit:
                out.append(quote(s, stamp="20260926150003"))
            elif s in self.lines:
                out.append(self.lines[s])
            else:
                out.append('v_pv_none_match="1";\n')
        return 200, "".join(out).encode("gbk")


def universe(tmp_path, codes):
    path = tmp_path / "codes.txt"
    path.write_text("\n".join(codes), encoding="utf-8")
    return path


def fixture_lines():
    return {
        "sh600001": quote("sh600001", name="浦发示例"),
        "bj920201": quote("bj920201", name="N百瑞吉"),
        "sz000002": quote("sz000002", stamp="20260926150003"),  # 停牌：时间戳是旧日
    }


def test_seals_only_eligible_codes_and_passes_the_auditor(tmp_path):
    codes = universe(tmp_path, ["600001.SH", "000002.SZ", "600999.SH"])
    out = tmp_path / "cap"
    args = parse_args(["--codes-file", str(codes), "--extra-codes", "920201.BJ",
                       "--out-dir", str(out), "--batch-size", "2"])
    result = run(args, fetch=FakeTencent(fixture_lines()), now=lambda: AFTER_CLOSE)

    assert result["captured_code_count"] == 2
    assert result["audit_capture_validated"] is True
    assert result["database_writes"] is False
    receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    assert sorted(receipt["codes"]) == ["600001.SH", "920201.BJ"]
    assert receipt["excluded"] == {"000002.SZ": "stale_quote:20260926", "600999.SH": "no_quote"}
    assert receipt["name_source"] == "tencent:captured-dated-quote"
    assert result["receipt_sha256"] == hashlib.sha256((out / "receipt.json").read_bytes()).hexdigest()
    assert audit_capture(out, DAY)["validated_quote_count"] == 2
    assert not (out.stat().st_mode & stat.S_IWUSR)
    assert all(not (p.stat().st_mode & stat.S_IWUSR) for p in out.iterdir())
    out.chmod(0o755)  # 让 tmp_path 能被清理


def test_code_that_goes_bad_during_seal_is_dropped_and_batch_refetched(tmp_path):
    codes = universe(tmp_path, ["600001.SH", "920201.BJ"])
    out = tmp_path / "cap"
    fake = FakeTencent(fixture_lines(), turn_bad_after={"bj920201": 1})
    result = run(parse_args(["--codes-file", str(codes), "--out-dir", str(out)]),
                 fetch=fake, now=lambda: AFTER_CLOSE)
    receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["codes"] == ["600001.SH"]
    assert receipt["excluded"]["920201.BJ"].startswith("seal_pass:stale_quote")
    assert result["audit_capture_validated"] is True
    out.chmod(0o755)


@pytest.mark.parametrize("now, target", [
    (datetime(2026, 9, 29, 14, 59, tzinfo=CST), None),             # 收盘前
    (AFTER_CLOSE, "2026-09-28"),                                   # 历史日
])
def test_refuses_before_close_or_for_another_day(tmp_path, now, target):
    codes = universe(tmp_path, ["600001.SH"])
    argv = ["--codes-file", str(codes), "--out-dir", str(tmp_path / "cap")]
    if target:
        argv += ["--target-date", target]
    fake = FakeTencent(fixture_lines())
    with pytest.raises(CaptureRefused):
        run(parse_args(argv), fetch=fake, now=lambda: now)
    assert fake.calls == []
    assert not (tmp_path / "cap").exists()


def test_existing_directory_is_never_overwritten(tmp_path):
    codes = universe(tmp_path, ["600001.SH"])
    (tmp_path / "cap").mkdir()
    fake = FakeTencent(fixture_lines())
    with pytest.raises(CaptureRefused, match="already exists"):
        run(parse_args(["--codes-file", str(codes), "--out-dir", str(tmp_path / "cap")]),
            fetch=fake, now=lambda: AFTER_CLOSE)
    assert fake.calls == []


def test_probe_writes_nothing_and_works_before_close(tmp_path):
    codes = universe(tmp_path, ["600001.SH", "000002.SZ"])
    result = run(parse_args(["--codes-file", str(codes), "--probe"]),
                 fetch=FakeTencent(fixture_lines()),
                 now=lambda: datetime(2026, 9, 29, 12, 40, tzinfo=CST))
    assert result["probe_only"] is True
    assert result["eligible_code_count"] == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["codes.txt"]


def test_invalid_codes_in_universe_are_refused(tmp_path):
    codes = universe(tmp_path, ["600001.SH", "600001"])
    with pytest.raises(CaptureRefused, match="invalid code"):
        run(parse_args(["--codes-file", str(codes), "--probe"]), fetch=FakeTencent({}),
            now=lambda: AFTER_CLOSE)


def test_classify_before_close_is_not_confused_with_stale():
    raw = quote("sh600001", stamp="20260929113000").encode("gbk")
    good, bad = classify(raw, ["600001.SH"], DAY)
    assert good == {} and bad == {"600001.SH": "not_after_close"}
