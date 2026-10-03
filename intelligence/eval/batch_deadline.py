"""Opt-in POSIX evaluation deadlines; no production client or model routing.

Use BOTH a supervisor around the entire batch and a propagated BatchDeadline
inside its worker. Only trusted workers that stay in the owned process group
are supported. This is not hard real-time scheduling, nor provider cancellation.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Callable

ENV_KEY = "FINANCE_EVAL_DEADLINE_SPEC"


class BatchExpired(TimeoutError):
    """The batch may not start another operation or publish a late result."""


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return value


def _positive(value, name):
    value = _number(value, name)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


@dataclass(frozen=True)
class AbsoluteDeadline:
    # Native llm_http_transport consumes this exact expires_at attribute.
    expires_at: float


@dataclass(frozen=True)
class TransportGrant:
    timeout: float
    deadline: AbsoluteDeadline


class BatchDeadline:
    """A non-renewable budget; either clock can exhaust it, neither can refill it.

    Single-controller object: construct a separate instance from the exported
    absolute spec in each subprocess. The supervisor owns the authoritative
    termination boundary even if a worker ignores its cooperative budget.
    """

    def __init__(
        self, seconds, *, wall=time.time, mono=time.monotonic, sleep=time.sleep
    ):
        self.seconds = _positive(seconds, "seconds")
        self.wall, self.mono, self.sleep = wall, mono, sleep
        self.wall_started = _number(wall(), "wall clock")
        self.mono_started = _number(mono(), "monotonic clock")
        self._mono_expires = _number(
            self.mono_started + self.seconds, "monotonic expiry"
        )

    def export(self):
        self._snapshot()
        return {
            "version": 1,
            "seconds": self.seconds,
            "wall_started": self.wall_started,
            "mono_started": self.mono_started,
            "mono_expires": self._mono_expires,
        }

    @classmethod
    def from_spec(cls, spec, *, wall=time.time, mono=time.monotonic, sleep=time.sleep):
        if not isinstance(spec, dict) or set(spec) != {
            "version",
            "seconds",
            "wall_started",
            "mono_started",
            "mono_expires",
        }:
            raise ValueError("invalid deadline spec")
        if type(spec["version"]) is not int or spec["version"] != 1:
            raise ValueError("unsupported deadline version")
        obj = cls.__new__(cls)
        obj.seconds = _positive(spec["seconds"], "seconds")
        obj.wall_started = _number(spec["wall_started"], "wall_started")
        obj.mono_started = _number(spec["mono_started"], "mono_started")
        obj.wall, obj.mono, obj.sleep = wall, mono, sleep
        obj._mono_expires = _number(spec["mono_expires"], "monotonic expiry")
        if obj._mono_expires > obj.mono_started + obj.seconds:
            raise ValueError("deadline spec extends its declared budget")
        return obj

    @classmethod
    def from_environment(cls):
        # Missing spec must not silently start a fresh budget.
        return cls.from_spec(json.loads(os.environ[ENV_KEY]))

    def _snapshot(self):
        now_mono = _number(self.mono(), "monotonic clock")
        now_wall = _number(self.wall(), "wall clock")
        wall_remaining = self.seconds - (now_wall - self.wall_started)
        self._mono_expires = min(
            self._mono_expires, now_mono + max(0.0, wall_remaining)
        )
        remaining = max(0.0, self._mono_expires - now_mono)
        return now_mono, remaining

    def remaining(self):
        return self._snapshot()[1]

    def require(self):
        remaining = self.remaining()
        if remaining <= 0:
            raise BatchExpired("evaluation batch deadline reached")
        return remaining

    def grant(self, requested, *, deadline=None):
        requested = _positive(requested, "requested timeout")
        now, remaining = self._snapshot()
        expires = now + min(requested, remaining)
        if deadline is not None:
            expires = min(expires, _number(deadline.expires_at, "caller deadline"))
        if expires <= now:
            raise BatchExpired("no time for HTTP operation")
        return TransportGrant(expires - now, AbsoluteDeadline(expires))

    def wait_until(self, monotonic_target, *, poll_seconds=0.05):
        target = _number(monotonic_target, "start target")
        poll = _positive(poll_seconds, "poll_seconds")
        while True:
            remaining = self.require()
            delay = target - self.mono()
            if delay <= 0:
                return
            self.sleep(min(delay, remaining, poll))

    def read_http(
        self,
        request,
        *,
        timeout,
        record_response: Callable,
        opener=None,
        deadline=None,
        **kwargs,
    ):
        """Non-streaming eval HTTP: clip native deadline and reject late publication.

        The sink gets immutable raw bytes and `received_in_time`; it must persist
        even late responses. The caller still owns pre-send physical reservation,
        durable receipts, identity checks and request-count caps. A sink failure
        propagates, never returning response bytes as accepted model input.
        """
        if not callable(record_response):
            raise ValueError("response sink is required")
        if opener is None:
            from intelligence.services.llm_http_transport import urlopen

            opener = urlopen
        grant = self.grant(timeout, deadline=deadline)
        with opener(
            request, timeout=grant.timeout, deadline=grant.deadline, **kwargs
        ) as response:
            raw = response.read()
        if not isinstance(raw, bytes):
            raise TypeError("HTTP response must be bytes")
        record_response(raw, self.remaining() > 0)
        self.require()  # Also reject if durable recording itself consumed the budget.
        return raw


@dataclass(frozen=True)
class SupervisedResult:
    status: str
    returncode: int | None
    pid: int | None
    wall_elapsed_seconds: float
    monotonic_elapsed_seconds: float
    cleanup_seconds: float

    def to_dict(self):
        # Explicit external receipt contract, not fields written without a reader.
        return {
            "status": self.status,
            "returncode": self.returncode,
            "pid": self.pid,
            "wall_elapsed_seconds": self.wall_elapsed_seconds,
            "monotonic_elapsed_seconds": self.monotonic_elapsed_seconds,
            "cleanup_seconds": self.cleanup_seconds,
        }


def _group_has_live_members(pgid):
    # PID/group/state only: never inspect or persist another process's argv/env.
    result = subprocess.run(
        ["ps", "-axo", "pid=,pgid=,stat="],
        capture_output=True,
        text=True,
        timeout=0.5,
        check=True,
    )
    if not result.stdout.strip():
        raise OSError("empty process table cannot prove group cleanup")
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 3:
            raise OSError("cannot verify process-group cleanup")
        int(fields[0])
        if int(fields[1]) == pgid and not fields[2].startswith("Z"):
            return True
    return False


def _kill_owned_group(process):
    """Only a process freshly created with start_new_session=True may enter here."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        # macOS can report EPERM during concurrent group exit. Never assume it
        # is harmless: reap our child AND prove no live group member remains.
        # A real denial/live descendant/unreadable process table still fails.
        try:
            process.wait(timeout=0.05)
        except subprocess.TimeoutExpired:
            raise PermissionError("owned process did not terminate") from None
        if _group_has_live_members(process.pid):
            raise PermissionError("owned process group still has live members")
    # Bounded cleanup, not an unbounded wait. Failure propagates: never success.
    process.wait(timeout=1.0)


def run_supervised(
    command, *, budget: BatchDeadline, stdout, cwd=None, env=None, poll_seconds=0.02
):
    """Run one whole evaluation batch in an owned POSIX process group.

    Kill at expiry (not TERM + unbounded grace). Audit/reaping tail is separate.
    A parent descheduled across the cutoff conservatively rejects an observed
    late exit, even if the child claims exit0. On normal exit, also clean up any
    same-group descendants. Children must not daemonize or create new sessions.
    """
    if os.name != "posix":
        raise RuntimeError("POSIX process groups are required")
    if (
        not isinstance(command, (list, tuple))
        or not command
        or any(not isinstance(x, str) or not x for x in command)
    ):
        raise ValueError("command must be a nonempty argv sequence")
    poll = _positive(poll_seconds, "poll_seconds")
    child_env = dict(os.environ if env is None else env)
    child_env[ENV_KEY] = json.dumps(budget.export(), allow_nan=False)
    process = None
    status = "not_started"
    cleanup = 0.0
    if budget.remaining() > 0:
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=subprocess.STDOUT,
                cwd=cwd,
                env=child_env,
                close_fds=True,
                start_new_session=True,
            )
            while True:
                if budget.remaining() <= 0:
                    status = "timed_out"
                    break
                code = process.poll()
                if code is not None:
                    status = "completed" if code == 0 else "failed"
                    if budget.remaining() <= 0:
                        status = "timed_out"
                    break
                budget.sleep(min(poll, budget.require()))
        except BatchExpired:
            status = "timed_out"
        finally:
            if process is not None:
                started = time.monotonic()
                _kill_owned_group(process)
                cleanup = time.monotonic() - started
    return SupervisedResult(
        status,
        process.returncode if process is not None else None,
        process.pid if process is not None else None,
        max(0.0, budget.wall() - budget.wall_started),
        max(0.0, budget.mono() - budget.mono_started),
        cleanup,
    )


def write_exclusive_json(path, value):
    """Fail closed on duplicate or failed storage; never log argv/environment."""
    data = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode()
    with Path(path).open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    if Path(path).read_bytes() != data:
        raise OSError("receipt readback mismatch")


def launch(command, *, seconds, receipt_dir, cwd=None):
    """Standalone once-only launcher. Receipt directory must not already exist.

    Returns an exit code, not a quality score: 0 completed, 1 child failed,
    124 timeout/not-started. Launcher/storage exceptions are not successful runs.
    stdout.log is private child output; callers must never print credentials.
    """
    budget = BatchDeadline(seconds)
    root = Path(receipt_dir)
    root.mkdir(parents=True, exist_ok=False)
    write_exclusive_json(root / "started.json", {"deadline": budget.export()})
    try:
        with (root / "stdout.log").open("xb") as output:
            result = run_supervised(command, budget=budget, stdout=output, cwd=cwd)
            output.flush()
            os.fsync(output.fileno())
        write_exclusive_json(root / "finished.json", result.to_dict())
    except BaseException as error:
        # A failed filesystem may prevent this too: do not fabricate a receipt.
        try:
            write_exclusive_json(
                root / "error.json",
                {
                    "status": "launcher_error",
                    "exception_type": type(error).__name__,
                },
            )
        except OSError:
            pass
        raise
    return {"completed": 0, "failed": 1, "timed_out": 124, "not_started": 124}[
        result.status
    ]
