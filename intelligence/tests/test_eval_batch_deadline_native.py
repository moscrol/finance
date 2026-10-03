"""Native transport + bounded launcher, only a local synthetic HTTP server."""

from pathlib import Path
import json
import subprocess
import sys
import time
from urllib.request import Request

import pytest

from intelligence.eval.batch_deadline import BatchDeadline, run_supervised
from intelligence.services import llm_http_transport
from intelligence.tests.test_llm_tool_response_deadline import local_provider


@pytest.mark.parametrize("slow", [False, True])
def test_native_http_budget_reaches_actual_worker(monkeypatch, slow):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    records = []
    with local_provider(body_seconds=1.0 if slow else 0.01) as provider:
        req = Request(
            provider.base_url + "/offline",
            data=b"{}",
            headers={"User-Agent": "curl/8.4.0"},
        )
        budget = BatchDeadline(0.3 if slow else 3)
        started = time.monotonic()
        if slow:
            with pytest.raises((TimeoutError, llm_http_transport.HTTPDeadlineExceeded)):
                budget.read_http(
                    req,
                    timeout=30,
                    record_response=lambda *x: records.append(x),
                    loopback_only=True,
                )
            assert time.monotonic() - started < 0.85
            assert records == []  # incomplete read is not a fabricated complete body
        else:
            raw = budget.read_http(
                req,
                timeout=30,
                record_response=lambda *x: records.append(x),
                loopback_only=True,
            )
            assert json.loads(raw)["choices"][0]["message"]["content"] == "ok"
            assert records == [(raw, True)]


def test_supervised_native_http_worker_stays_in_owned_group(tmp_path, monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    meta = tmp_path / "worker.json"
    body = tmp_path / "body.bin"
    repo = Path(__file__).resolve().parents[2]
    with local_provider(body_seconds=1.5) as provider:
        code = f"""
import os,json
from pathlib import Path
from urllib.request import Request
from intelligence.eval.batch_deadline import BatchDeadline
from intelligence.services import llm_http_transport as transport
original=transport.HTTPResponse.__init__
def capture(self,process,*args,**kwargs):
    Path({str(meta)!r}).write_text(json.dumps({{'pid':process.pid,'pgid':os.getpgid(process.pid),'owner_pgid':os.getpgrp()}}))
    original(self,process,*args,**kwargs)
transport.HTTPResponse.__init__=capture
b=BatchDeadline.from_environment()
b.read_http(Request({provider.base_url + "/offline"!r},data=b'{{}}',headers={{'User-Agent':'curl/8.4.0'}}),timeout=30,loopback_only=True,record_response=lambda raw,on_time:Path({str(body)!r}).write_bytes(raw))
"""
        with (tmp_path / "stdout.log").open("wb") as output:
            started = time.monotonic()
            result = run_supervised(
                [sys.executable, "-c", code],
                budget=BatchDeadline(0.6),
                stdout=output,
                cwd=repo,
            )
        assert time.monotonic() - started < 1.2
    assert result.status in {"timed_out", "failed"}
    assert meta.exists(), (tmp_path / "stdout.log").read_text()
    saved = json.loads(meta.read_text())
    assert saved["pgid"] == saved["owner_pgid"] == result.pid
    assert not body.exists()
    # A grandchild may briefly be a zombie awaiting OS reaping, but cannot run.
    check = subprocess.run(
        ["ps", "-p", str(saved["pid"]), "-o", "stat="], capture_output=True, text=True
    )
    assert not check.stdout.strip() or check.stdout.strip().startswith("Z")
