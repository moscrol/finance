"""派生计算沙箱两层隔离的行为夹具（spec capability-amplification §3.4）。

进程层（prelude 守卫）的测试在任何机器都跑；系统层（macOS Seatbelt）的测试把 Python
守卫**关掉**只留 sandbox-exec，证明拦截来自操作系统而不是 prelude——没有 sandbox-exec
的机器跳过并如实标 skip，不静默通过。
"""

from __future__ import annotations

import os
import tempfile

import duckdb
import pytest

from intelligence.services import calculation_sandbox as sandbox

_EVIDENCE = [
    {
        "ref": "E1",
        "hash": "a" * 16,
        "tool": "financial_data",
        "as_of": "2025-04-03",
        "observations": [{"metric": "net_profit", "value": 1741.44}],
    },
    {
        "ref": "E2",
        "hash": "b" * 16,
        "tool": "web_fetch",
        "as_of": "2025-05-01",
        "observations": [{"metric": "net_profit", "value": 1740.0}],
    },
]

_NET_SCRIPT = (
    "import socket\n"
    "try:\n"
    "    socket.create_connection(('127.0.0.1', 9), timeout=2)\n"
    "    emit({'connected': True})\n"
    "except Exception as exc:\n"
    "    emit({'connected': False, 'error': type(exc).__name__})\n"
)


def _run(script: str, **kwargs):
    kwargs.setdefault("evidence", _EVIDENCE)
    kwargs.setdefault("seatbelt", False)
    return sandbox.run_script(script, **kwargs)


# ── 进程层 ──────────────────────────────────────────────────────────────


def test_script_reads_evidence_and_emits_a_result() -> None:
    run = _run(
        "a = [e for e in EVIDENCE if e['tool'] == 'financial_data'][0]['observations'][0]['value']\n"
        "b = [e for e in EVIDENCE if e['tool'] == 'web_fetch'][0]['observations'][0]['value']\n"
        "print('debug line for stdout tail')\n"
        "emit({'diff': round(a - b, 2), 'consistent': abs(a - b) < 0.01, 'order': sorted({3, 1, 2})})\n"
    )

    assert run.ok, (run.exit_code, run.stderr_tail)
    assert run.result == {"diff": 1.44, "consistent": False, "order": [1, 2, 3]}
    assert run.enforcement == "process"
    assert "debug line" in run.stdout_tail
    assert run.runtime["prelude_version"] == sandbox.PRELUDE_VERSION


def test_same_script_same_inputs_is_deterministic() -> None:
    script = "emit({'keys': sorted(set('determinism')), 'n': len(EVIDENCE)})"

    assert _run(script).result == _run(script).result


def test_network_is_denied_by_the_prelude() -> None:
    run = _run("import socket\nsocket.create_connection(('127.0.0.1', 9), timeout=1)\nemit({})")

    assert not run.ok
    assert run.exit_code == 1
    assert run.violations == ("network disabled in sandbox",)


def test_blocked_module_import_is_a_violation() -> None:
    run = _run("import urllib.request\nemit({})")

    assert run.violations == ("import blocked: urllib.request",)


def test_process_spawning_is_denied_by_the_prelude() -> None:
    run = _run("import os\nos.system('true')\nemit({})")

    assert run.violations == ("process spawning disabled in sandbox",)


def test_writes_outside_workdir_are_denied_but_workdir_is_writable(tmp_path) -> None:
    escape = tmp_path / "escape.txt"
    denied = _run(f"open({str(escape)!r}, 'w').write('x')\nemit({{}})")
    allowed = _run("open('scratch.txt', 'w').write('ok')\nemit({'back': open('scratch.txt').read()})")

    assert denied.violations == (f"write outside workdir: {escape}",)
    assert not escape.exists()
    assert allowed.ok and allowed.result == {"back": "ok"}


def test_missing_emit_is_no_result_not_a_crash() -> None:
    run = _run("x = 1 + 1\n")

    assert run.exit_code == 0
    assert run.result is None
    assert not run.ok


def test_infinite_loop_is_reported_as_timeout() -> None:
    run = _run("while True:\n    pass\n", timeout=1)

    assert run.timed_out
    assert run.result is None


def test_duckdb_is_mounted_read_only_and_absent_by_default() -> None:
    db_path = os.path.join(tempfile.mkdtemp(prefix="derived-calc-db-"), "t.duckdb")
    connection = duckdb.connect(db_path)
    connection.execute("create table t as select 42 as v")
    connection.close()

    absent = _run("con = duckdb_connect()\nemit({})")
    read = _run(
        "con = duckdb_connect()\nemit({'v': con.execute('select v from t').fetchone()[0]})",
        db_path=db_path,
    )
    write = _run(
        "con = duckdb_connect()\n"
        "try:\n"
        "    con.execute('insert into t values (1)')\n"
        "    emit({'inserted': True})\n"
        "except Exception as exc:\n"
        "    emit({'inserted': False, 'error': type(exc).__name__})\n",
        db_path=db_path,
    )

    assert absent.exit_code == 1 and "no duckdb snapshot mounted" in absent.stderr_tail
    assert read.result == {"v": 42}
    assert write.result == {"inserted": False, "error": "InvalidInputException"}


def test_forbidden_import_static_scan() -> None:
    assert sandbox.forbidden_import("import json\nemit({})") is None
    assert sandbox.forbidden_import("import socket") == "socket"
    assert sandbox.forbidden_import("from urllib.request import urlopen") == "urllib.request"
    assert sandbox.forbidden_import("import os, subprocess") == "subprocess"
    assert sandbox.forbidden_import("os.system('ls')") == "os.system"
    assert sandbox.forbidden_import("import urllib.parse") is None


def test_missing_interpreter_is_an_environment_failure() -> None:
    with pytest.raises(sandbox.SandboxUnavailable):
        _run("emit({})", python="/nonexistent/python")


# ── 系统层（macOS Seatbelt）────────────────────────────────────────────

seatbelt_only = pytest.mark.skipif(
    not sandbox.seatbelt_available(),
    reason="sandbox-exec 不可用（非 macOS 或 FORESIGHT_SANDBOX_SEATBELT=0）",
)


@seatbelt_only
def test_seatbelt_alone_denies_network_even_with_python_guard_off() -> None:
    run = sandbox.run_script(_NET_SCRIPT, evidence=_EVIDENCE, guard=False, seatbelt=True)

    assert run.enforcement == "seatbelt"
    assert run.result == {"connected": False, "error": "PermissionError"}


@seatbelt_only
def test_seatbelt_alone_denies_writes_outside_workdir_and_fork(tmp_path) -> None:
    escape = tmp_path / "seatbelt-escape.txt"
    write = sandbox.run_script(
        "try:\n"
        f"    open({str(escape)!r}, 'w').write('x')\n"
        "    emit({'wrote': True})\n"
        "except Exception as exc:\n"
        "    emit({'wrote': False, 'error': type(exc).__name__})\n",
        evidence=_EVIDENCE,
        guard=False,
        seatbelt=True,
    )
    fork = sandbox.run_script(
        "import os\n"
        "try:\n"
        "    os.fork()\n"
        "    emit({'forked': True})\n"
        "except Exception as exc:\n"
        "    emit({'forked': False, 'error': type(exc).__name__})\n",
        evidence=_EVIDENCE,
        guard=False,
        seatbelt=True,
    )

    assert write.result == {"wrote": False, "error": "PermissionError"}
    assert not escape.exists()
    assert fork.result == {"forked": False, "error": "PermissionError"}


@seatbelt_only
def test_default_enforcement_on_this_machine_is_both_layers() -> None:
    run = sandbox.run_script("emit({'ok': True})", evidence=_EVIDENCE)

    assert run.enforcement == "seatbelt+process"
    assert run.result == {"ok": True}


def test_seatbelt_flag_zero_turns_the_os_layer_off(monkeypatch) -> None:
    monkeypatch.setenv(sandbox.SEATBELT_ENV_FLAG, "0")

    assert not sandbox.seatbelt_available()
    run = sandbox.run_script("emit({'ok': True})", evidence=_EVIDENCE)
    assert run.enforcement == "process"
