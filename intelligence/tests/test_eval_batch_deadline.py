from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from intelligence.eval import batch_deadline as mod
from intelligence.eval.batch_deadline import BatchDeadline, BatchExpired


class Clock:
    def __init__(self):
        self.w = 100.0
        self.m = 20.0
        self.sleeps = []

    def wall(self):
        return self.w

    def mono(self):
        return self.m

    def advance(self, seconds):
        self.w += seconds
        self.m += seconds

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.advance(seconds)

    def budget(self, seconds=10):
        return BatchDeadline(seconds, wall=self.wall, mono=self.mono, sleep=self.sleep)


@pytest.mark.parametrize("value", [0, -1, True, float("inf"), float("nan"), "10", None])
def test_invalid_budget(value):
    with pytest.raises(ValueError):
        BatchDeadline(value)


def test_request_grant_is_clipped_to_batch_and_existing_deadline():
    c = Clock()
    b = c.budget()
    c.advance(7)
    g = b.grant(30)
    assert g.timeout == 3 and g.deadline.expires_at == 30
    g = b.grant(30, deadline=SimpleNamespace(expires_at=28))
    assert g.timeout == 1 and g.deadline.expires_at == 28
    assert b.grant(0.5).timeout == 0.5


@pytest.mark.parametrize("value", [0, -1, True, float("inf"), float("nan"), "2"])
def test_invalid_requested_timeout(value):
    with pytest.raises(ValueError):
        Clock().budget().grant(value)


def test_caller_expired_deadline_cannot_be_extended():
    with pytest.raises(BatchExpired):
        Clock().budget().grant(30, deadline=SimpleNamespace(expires_at=19))


def test_wall_forward_simulated_suspend_expires_even_if_monotonic_stopped():
    c = Clock()
    b = c.budget()
    c.w += 11
    with pytest.raises(BatchExpired):
        b.grant(30)


def test_wall_backward_does_not_extend_monotonic_limit():
    c = Clock()
    b = c.budget()
    c.w -= 1000
    c.m += 11
    with pytest.raises(BatchExpired):
        b.require()


def test_forward_then_rollback_irreversibly_tightens_absolute_deadline():
    c = Clock()
    b = c.budget()
    c.w += 6
    assert b.grant(30).deadline.expires_at == 24
    c.w -= 6
    c.advance(2)
    assert b.grant(30).timeout == 2
    assert b.grant(30).deadline.expires_at == 24


def test_expired_budget_cannot_be_revived_by_rollback():
    c = Clock()
    b = c.budget()
    c.w += 11
    assert b.remaining() == 0
    c.w -= 11
    with pytest.raises(BatchExpired):
        b.require()


def test_export_import_preserves_tightened_absolute_deadline():
    c = Clock()
    b = c.budget()
    c.w += 6
    spec = b.export()
    c.w -= 6
    c.advance(2)
    child = BatchDeadline.from_spec(spec, wall=c.wall, mono=c.mono, sleep=c.sleep)
    assert child.grant(30).timeout == 2
    assert child.grant(30).deadline.expires_at == 24


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s.update(version=True),
        lambda s: s.update(seconds=0),
        lambda s: s.update(mono_expires=10000),
        lambda s: s.update(extra=1),
        lambda s: s.update(wall_started=float("nan")),
    ],
)
def test_bad_import_spec_rejected(change):
    spec = Clock().budget().export()
    change(spec)
    with pytest.raises(ValueError):
        BatchDeadline.from_spec(spec)


def test_missing_environment_never_renews_budget(monkeypatch):
    monkeypatch.delenv(mod.ENV_KEY, raising=False)
    with pytest.raises(KeyError):
        BatchDeadline.from_environment()


def test_wait_does_not_sleep_whole_inter_case_gap():
    c = Clock()
    b = c.budget(2)
    with pytest.raises(BatchExpired):
        b.wait_until(110, poll_seconds=0.4)
    assert sum(c.sleeps) == pytest.approx(2)
    assert max(c.sleeps) <= 0.4


def test_wait_ready_and_expired_cases():
    c = Clock()
    b = c.budget(2)
    b.wait_until(21, poll_seconds=0.5)
    assert c.m == 21
    c.advance(2)
    with pytest.raises(BatchExpired):
        b.wait_until(10)


def test_wait_rechecks_wall_after_simulated_host_resume():
    c = Clock()
    b = c.budget(2)

    def resume(_):
        c.w += 100

    b.sleep = resume
    with pytest.raises(BatchExpired):
        b.wait_until(110)


def http_fixture(c, *, delay=0):
    calls = []
    closed = []

    @contextmanager
    def opener(request, **kw):
        calls.append((request, kw))

        class Response:
            def read(self):
                c.advance(delay)
                return b'{"model":"offline-only"}'

        try:
            yield Response()
        finally:
            closed.append(True)

    return opener, calls, closed


def test_http_native_grant_and_flags_reach_opener():
    c = Clock()
    b = c.budget(2)
    opener, calls, closed = http_fixture(c)
    records = []
    result = b.read_http(
        "offline",
        timeout=30,
        opener=opener,
        record_response=lambda *x: records.append(x),
        loopback_only=True,
    )
    assert result == b'{"model":"offline-only"}'
    assert calls[0][1]["timeout"] == 2
    assert calls[0][1]["deadline"].expires_at == 22
    assert calls[0][1]["loopback_only"] is True
    assert records == [(result, True)] and closed == [True]


def test_late_response_is_recorded_but_not_returned():
    c = Clock()
    b = c.budget(2)
    opener, calls, closed = http_fixture(c, delay=3)
    records = []
    with pytest.raises(BatchExpired):
        b.read_http(
            "offline",
            timeout=30,
            opener=opener,
            record_response=lambda *x: records.append(x),
        )
    assert records == [(b'{"model":"offline-only"}', False)]
    assert len(calls) == 1 and closed == [True]


def test_recording_delay_cannot_publish_late_success():
    c = Clock()
    b = c.budget(2)
    opener, _, _ = http_fixture(c)

    def record(*_):
        c.advance(3)

    with pytest.raises(BatchExpired):
        b.read_http("offline", timeout=30, opener=opener, record_response=record)


def test_response_sink_failure_propagates():
    c = Clock()
    opener, _, closed = http_fixture(c)

    def record(*_):
        raise OSError("offline disk error")

    with pytest.raises(OSError):
        c.budget().read_http(
            "offline", timeout=1, opener=opener, record_response=record
        )
    assert closed == [True]


def test_expired_http_never_calls_opener():
    c = Clock()
    b = c.budget(1)
    c.advance(2)
    opener, calls, _ = http_fixture(c)
    with pytest.raises(BatchExpired):
        b.read_http(
            "offline", timeout=30, opener=opener, record_response=lambda *_: None
        )
    assert calls == []


def test_no_sink_never_calls_opener():
    c = Clock()
    opener, calls, _ = http_fixture(c)
    with pytest.raises(ValueError):
        c.budget().read_http("offline", timeout=30, opener=opener, record_response=None)
    assert calls == []


def test_expired_supervisor_does_not_spawn(monkeypatch):
    c = Clock()
    b = c.budget(1)
    c.advance(2)

    def forbidden(*_, **__):
        pytest.fail("must not spawn")

    monkeypatch.setattr(mod.subprocess, "Popen", forbidden)
    result = mod.run_supervised(["unused"], budget=b, stdout=None)
    assert result.status == "not_started" and result.pid is None


def test_exit0_observed_after_cutoff_not_counted_success(monkeypatch):
    c = Clock()
    b = c.budget(2)

    class Process:
        pid = 99
        returncode = 0

        def poll(self):
            c.w += 10
            return 0

    monkeypatch.setattr(mod.subprocess, "Popen", lambda *a, **k: Process())
    killed = []
    monkeypatch.setattr(mod, "_kill_owned_group", lambda p: killed.append(p.pid))
    result = mod.run_supervised(["unused"], budget=b, stdout=None)
    assert result.status == "timed_out" and killed == [99]


@pytest.mark.skipif(os.name != "posix", reason="POSIX group contract")
@pytest.mark.parametrize("code,expected", [(0, "completed"), (7, "failed")])
def test_real_child_exit_and_absolute_spec(tmp_path, code, expected):
    with (tmp_path / "child.log").open("wb") as output:
        result = mod.run_supervised(
            [
                sys.executable,
                "-c",
                f'import os,json; s=json.loads(os.environ[{mod.ENV_KEY!r}]); assert s["version"]==1; print("done"); raise SystemExit({code})',
            ],
            budget=BatchDeadline(3),
            stdout=output,
        )
    assert result.status == expected and result.returncode == code
    assert (tmp_path / "child.log").read_text().strip() == "done"


@pytest.mark.skipif(os.name != "posix", reason="POSIX group contract")
def test_real_slow_child_is_killed_and_reaped(tmp_path):
    with (tmp_path / "child.log").open("wb") as output:
        start = time.monotonic()
        result = mod.run_supervised(
            [sys.executable, "-c", "import time;time.sleep(2)"],
            budget=BatchDeadline(0.15),
            stdout=output,
        )
    assert result.status == "timed_out"
    assert result.returncode < 0
    assert time.monotonic() - start < 1.5
    with pytest.raises(ProcessLookupError):
        os.kill(result.pid, 0)


@pytest.mark.skipif(os.name != "posix", reason="POSIX group contract")
def test_same_group_grandchild_cannot_write_after_batch_timeout(tmp_path):
    marker = tmp_path / "escaped.txt"
    child = f'import time;from pathlib import Path;time.sleep(.7);Path({str(marker)!r}).write_text("bad")'
    worker = f'import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",{child!r}]);print("spawned",flush=True);time.sleep(1.2)'
    with (tmp_path / "child.log").open("wb") as output:
        result = mod.run_supervised(
            [sys.executable, "-c", worker], budget=BatchDeadline(0.25), stdout=output
        )
    assert result.status == "timed_out"
    assert "spawned" in (tmp_path / "child.log").read_text()
    time.sleep(0.8)
    assert not marker.exists()


def test_once_only_launcher_refuses_reuse(tmp_path):
    root = tmp_path / "receipt"
    assert (
        mod.launch([sys.executable, "-c", 'print("done")'], seconds=3, receipt_dir=root)
        == 0
    )
    start = (root / "started.json").read_bytes()
    with pytest.raises(FileExistsError):
        mod.launch(
            [sys.executable, "-c", "raise SystemExit(99)"], seconds=3, receipt_dir=root
        )
    assert (root / "started.json").read_bytes() == start
    assert json.loads((root / "finished.json").read_text())["status"] == "completed"


def test_start_receipt_failure_prevents_spawn(tmp_path, monkeypatch):
    def broken(*_, **__):
        raise OSError("disk error")

    def forbidden(*_, **__):
        pytest.fail("must not spawn")

    monkeypatch.setattr(mod, "write_exclusive_json", broken)
    monkeypatch.setattr(mod.subprocess, "Popen", forbidden)
    with pytest.raises(OSError):
        mod.launch(["unused"], seconds=3, receipt_dir=tmp_path / "receipt")


def test_cli_returns_124_and_terminal_receipt_on_deadline(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    root = tmp_path / "receipt"
    p = subprocess.run(
        [
            sys.executable,
            str(repo / "scripts/run_eval_bounded.py"),
            "--seconds",
            ".15",
            "--receipt-dir",
            str(root),
            "--",
            sys.executable,
            "-c",
            "import time;time.sleep(2)",
        ],
        capture_output=True,
        text=True,
        timeout=4,
    )
    assert p.returncode == 124, p.stderr
    done = json.loads((root / "finished.json").read_text())
    assert done["status"] == "timed_out" and done["returncode"] < 0
    assert "command" not in json.loads((root / "started.json").read_text())


def test_exclusive_json_never_overwrites(tmp_path):
    p = tmp_path / "x.json"
    mod.write_exclusive_json(p, {"ok": True})
    with pytest.raises(FileExistsError):
        mod.write_exclusive_json(p, {"ok": False})
    assert json.loads(p.read_text()) == {"ok": True}


def test_launcher_failure_retains_error_receipt(tmp_path):
    root = tmp_path / "receipt"
    with pytest.raises(OSError):
        mod.launch([str(tmp_path / "missing-command")], seconds=2, receipt_dir=root)
    assert json.loads((root / "error.json").read_text())["status"] == "launcher_error"
    assert not (root / "finished.json").exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX group contract")
def test_normal_exit_cleans_same_group_leftover(tmp_path):
    marker = tmp_path / "leftover.txt"
    child = f'import time;from pathlib import Path;time.sleep(.6);Path({str(marker)!r}).write_text("bad")'
    worker = f'import subprocess,sys;subprocess.Popen([sys.executable,"-c",{child!r}]);print("spawned",flush=True)'
    with (tmp_path / "child.log").open("wb") as output:
        result = mod.run_supervised(
            [sys.executable, "-c", worker], budget=BatchDeadline(3), stdout=output
        )
    assert result.status == "completed"
    assert "spawned" in (tmp_path / "child.log").read_text()
    time.sleep(0.7)
    assert not marker.exists()


@pytest.mark.parametrize("live", [True, False])
def test_group_permission_error_requires_verified_termination(monkeypatch, live):
    class Process:
        pid = 876543

        def wait(self, timeout):
            return 0

    def denied(*args):
        raise PermissionError("denied")

    monkeypatch.setattr(mod.os, "killpg", denied)
    monkeypatch.setattr(mod, "_group_has_live_members", lambda pid: live)
    if live:
        with pytest.raises(PermissionError):
            mod._kill_owned_group(Process())
    else:
        mod._kill_owned_group(Process())


def test_group_permission_error_with_running_child_still_fails(monkeypatch):
    class Process:
        pid = 876543

        def wait(self, timeout):
            raise subprocess.TimeoutExpired("owned", timeout)

    def denied(*args):
        raise PermissionError("denied")

    monkeypatch.setattr(mod.os, "killpg", denied)
    with pytest.raises(PermissionError):
        mod._kill_owned_group(Process())


@pytest.mark.parametrize(
    "text,expected",
    [("1 42 Z\n2 7 S\n", False), ("1 42 S\n", True), ("2 7 S\n", False)],
)
def test_group_liveness_parse_has_no_argv_or_env(monkeypatch, text, expected):
    def ps(args, **kwargs):
        assert args == ["ps", "-axo", "pid=,pgid=,stat="]
        assert kwargs["timeout"] == 0.5 and kwargs["check"]
        return SimpleNamespace(stdout=text)

    monkeypatch.setattr(mod.subprocess, "run", ps)
    assert mod._group_has_live_members(42) is expected


@pytest.mark.parametrize("text", ["", "unparseable"])
def test_group_liveness_invalid_data_fails_closed(monkeypatch, text):
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=text)
    )
    with pytest.raises(OSError):
        mod._group_has_live_members(42)
