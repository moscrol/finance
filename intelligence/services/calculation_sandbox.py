"""派生计算沙箱：把模型写的一段 Python 放进「不能外呼、不能乱写、有时限」的子进程里跑。

这一层只管**执行隔离**与**结果回收**，不认识证据账本、不认识 ToolSpec——那些归
``derived_calculation.py``。spec `2026-09-02-capability-amplification-output-gate-design.md`
§3.4 的要求是「沙箱只挂 DuckDB 只读副本 + 本回合已绑定的证据集，不给写库、不给外呼」，
理由写死为**可复现**（不可复现的计算进不了证据体系），不是安全。

## 两层，缺一层都不对（2026-09-08 拍板）

1. **进程层（永远开着，跨平台）**：独立解释器进程（``-s -B -P``：不读用户 site、不写
   字节码、不把脚本目录塞进 ``sys.path``）、从零构造的环境变量（没有代理、没有密钥、
   ``PYTHONHASHSEED=0`` 让集合遍历序确定）、cwd 是一次性工作目录、stdin 关闭、CPU / 文件
   大小 / 句柄数 rlimit、墙钟超时。脚本前面拼一段**版本化的 prelude**（``PRELUDE_VERSION``
   进 calc_id）：把 ``socket`` 换成抛异常、拦掉 ``subprocess`` / ``urllib.request`` 等模块
   的 import、写模式 ``open`` 只许落在工作目录内，并给脚本三件东西——``EVIDENCE``（本回合
   证据）、``duckdb_connect()``（只读）、``emit(result)``（唯一的结果出口）。
   它是**确定性的、可测的、任何机器都能跑**，但 Python 层的守卫原则上能被 ``ctypes`` 一类
   绕过——所以还要第二层。
2. **系统层（macOS 有就用）**：``/usr/bin/sandbox-exec`` 加一份 deny-list 风格的 Seatbelt
   profile：``(deny network*)`` ``(deny process-fork)`` ``(deny file-write*)`` 只放开工作目录。
   这是操作系统级的拦截，连 ctypes 直接 syscall 也过不去。它已被 Apple 标为 deprecated
   但至今在位（pi 的 sandbox 扩展、Anthropic sandbox-runtime 都靠它），且只有 macOS 有，
   所以**不能当唯一一层**：生产机是 Mac，测试要能在任何地方跑。

产物里记 ``enforcement``（``seatbelt+process`` / ``process``）——读收据的人要知道这次计算
是在哪一档隔离下算出来的，不能靠猜。

## 没选的方案

- 只用 sandbox-exec：macOS-only、allow-list profile 给 Python + DuckDB 调通是个无底洞、
  离线跑不了测试。
- 只用子进程 + 环境清洗：Python 层守卫可被绕过，生产机上白放着一道系统门不用。
- bwrap / Docker / gVisor / Firecracker：给 90 秒量级的本机 episode 加一整套运维面，不值。
- Pyodide / WASM：没有 duckdb。
- 托管 code interpreter（Responses API）：产物不带本仓的 hash / as_of / source，进不了
  ``admit_finish`` 的绑定（spec §3.5.5）。
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

# 进 calc_id 的 prelude 版本号：prelude 的行为变了（新拦一个模块、换 emit 格式）就升号，
# 否则同脚本同输入会得到「看起来同 id、实际不同环境」的两份产物。
PRELUDE_VERSION = "1"

RESULT_SENTINEL = "__DERIVED_CALCULATION_RESULT__"
SEATBELT_BINARY = "/usr/bin/sandbox-exec"
SEATBELT_ENV_FLAG = "FORESIGHT_SANDBOX_SEATBELT"

DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_TIMEOUT_SECONDS = 60.0
_TAIL_CHARS = 2000
_FILE_SIZE_LIMIT = 16 * 1024 * 1024
_OPEN_FILES_LIMIT = 256
_SIGXCPU = int(getattr(signal, "SIGXCPU", 24))

# 静态扫描在起进程之前就拒掉的形状——给模型一个明确的原因，不烧一次子进程。
# 这不是安全边界（真正的边界是 prelude 与 Seatbelt），只是让「写错了」早点看见。
FORBIDDEN_IMPORT_MODULES: tuple[str, ...] = (
    "socket",
    "ssl",
    "urllib.request",
    "urllib.error",
    "http",
    "requests",
    "httpx",
    "aiohttp",
    "asyncio",
    "subprocess",
    "multiprocessing",
    "socketserver",
    "ftplib",
    "smtplib",
    "telnetlib",
    "xmlrpc",
)
_FORBIDDEN_CALLS: tuple[str, ...] = (
    "os.system",
    "os.popen",
    "os.fork",
    "os.exec",
    "os.spawn",
    "__import__",
)
_IMPORT_RE = re.compile(
    r"^\s*(?:import\s+([\w\.]+(?:\s*,\s*[\w\.]+)*)|from\s+([\w\.]+)\s+import\b)",
    re.MULTILINE,
)


class SandboxUnavailable(RuntimeError):
    """连沙箱子进程都起不来（解释器不存在等）——是环境故障，不是脚本问题。"""


# --------------------------------------------------------------------------- prelude

# 脚本前拼的守卫段。纯标准库、不 import 任何第三方；行为改动必须同步升 PRELUDE_VERSION。
# 注意：这里的每个名字都会出现在脚本的全局命名空间里，故一律加下划线前缀，只暴露
# EVIDENCE / duckdb_connect / emit / SandboxViolation 四个给模型用的名字。
PRELUDE_SOURCE = r'''
import builtins as _builtins
import io as _io
import json as _json
import os as _os
import socket as _socket
import sys as _sys

_REAL_STDOUT = _sys.stdout
_WORKDIR = _os.path.realpath(_os.getcwd())
with open(_os.path.join(_WORKDIR, "params.json"), "r", encoding="utf-8") as _fh:
    _PARAMS = _json.load(_fh)
with open(_os.path.join(_WORKDIR, "evidence.json"), "r", encoding="utf-8") as _fh:
    EVIDENCE = _json.load(_fh)


class SandboxViolation(RuntimeError):
    """脚本试图做沙箱不允许的事（外呼 / 越界写 / 起进程）。"""


def _deny(what):
    def _raise(*_args, **_kwargs):
        raise SandboxViolation(what)
    return _raise


_BLOCKED_MODULES = tuple(_PARAMS.get("blocked_modules") or ())


class _ImportBlocker:
    def find_spec(self, name, path=None, target=None):
        for blocked in _BLOCKED_MODULES:
            if name == blocked or name.startswith(blocked + "."):
                raise SandboxViolation("import blocked: " + name)
        return None


def _inside_workdir(path):
    try:
        real = _os.path.realpath(_os.fspath(path))
    except (TypeError, ValueError):
        return False
    return real == _WORKDIR or real.startswith(_WORKDIR + _os.sep)


_WRITE_MODE_CHARS = set("wax+")
_ORIG_OPEN = _builtins.open
_ORIG_OS_OPEN = _os.open
_WRITE_FLAGS = _os.O_WRONLY | _os.O_RDWR | _os.O_CREAT | _os.O_TRUNC | _os.O_APPEND


def _guarded_open(file, mode="r", *args, **kwargs):
    if isinstance(file, int):
        return _ORIG_OPEN(file, mode, *args, **kwargs)
    if _WRITE_MODE_CHARS.intersection(str(mode)) and not _inside_workdir(file):
        raise SandboxViolation("write outside workdir: " + str(file))
    return _ORIG_OPEN(file, mode, *args, **kwargs)


def _guarded_os_open(path, flags, *args, **kwargs):
    if flags & _WRITE_FLAGS and not _inside_workdir(path):
        raise SandboxViolation("write outside workdir: " + str(path))
    return _ORIG_OS_OPEN(path, flags, *args, **kwargs)


def _guard_path_mutation(name):
    original = getattr(_os, name)

    def _guarded(path, *args, **kwargs):
        if not _inside_workdir(path):
            raise SandboxViolation(name + " outside workdir: " + str(path))
        return original(path, *args, **kwargs)
    return _guarded


if _PARAMS.get("guard", True):
    _sys.meta_path.insert(0, _ImportBlocker())
    _socket.socket = _deny("network disabled in sandbox")
    _socket.create_connection = _deny("network disabled in sandbox")
    _socket.getaddrinfo = _deny("network disabled in sandbox")
    _socket.gethostbyname = _deny("network disabled in sandbox")
    _socket.socketpair = _deny("network disabled in sandbox")
    _builtins.open = _guarded_open
    _io.open = _guarded_open
    _os.open = _guarded_os_open
    for _name in ("remove", "unlink", "rename", "replace", "mkdir", "makedirs", "rmdir", "truncate"):
        setattr(_os, _name, _guard_path_mutation(_name))
    for _name in ("system", "popen", "fork", "forkpty", "execv", "execve", "execvp", "execvpe",
                  "execl", "execle", "execlp", "execlpe", "spawnl", "spawnle", "spawnlp",
                  "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe", "posix_spawn",
                  "posix_spawnp"):
        if hasattr(_os, _name):
            setattr(_os, _name, _deny("process spawning disabled in sandbox"))


def duckdb_connect():
    """只读打开本回合挂进来的 DuckDB 快照；没挂就明确报错，不静默给空库。"""
    db_path = _PARAMS.get("db_path")
    if not db_path:
        raise RuntimeError(
            "no duckdb snapshot mounted for this calculation: call the tool with use_duckdb=true"
        )
    import duckdb  # noqa: PLC0415
    return duckdb.connect(db_path, read_only=True)


_EMITTED = []


def emit(result):
    """唯一的结果出口：一个可 JSON 化的 dict。多次调用以最后一次为准。"""
    if not isinstance(result, dict):
        raise TypeError("emit() expects a dict")
    encoded = _json.dumps(result, ensure_ascii=False, sort_keys=True, default=str)
    _EMITTED.append(encoded)
    _REAL_STDOUT.write("__DERIVED_CALCULATION_RESULT__ " + encoded + "\n")
    _REAL_STDOUT.flush()


del _fh
# ---- model script follows ----
'''


# --------------------------------------------------------------------------- results


@dataclass(frozen=True)
class SandboxRun:
    """一次沙箱执行的原始读数；解释成工具错误码归上层。"""

    enforcement: str
    exit_code: int | None
    duration_ms: int
    result: dict[str, object] | None
    stdout_tail: str
    stderr_tail: str
    timed_out: bool = False
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    runtime: Mapping[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return (
            not self.timed_out
            and not self.violations
            and self.exit_code == 0
            and self.result is not None
        )


# --------------------------------------------------------------------------- helpers


def forbidden_import(script: str) -> str | None:
    """静态扫脚本：命中禁用模块 / 调用就回第一个名字，否则 None。"""

    for match in _IMPORT_RE.finditer(script):
        names = match.group(1) or match.group(2) or ""
        for raw in names.split(","):
            name = raw.strip()
            if not name:
                continue
            for blocked in FORBIDDEN_IMPORT_MODULES:
                if name == blocked or name.startswith(blocked + "."):
                    return blocked
    for call in _FORBIDDEN_CALLS:
        if call in script:
            return call
    return None


def seatbelt_available() -> bool:
    """macOS 且 sandbox-exec 在位且没被 ``FORESIGHT_SANDBOX_SEATBELT=0`` 关掉。"""

    if platform.system() != "Darwin":
        return False
    if os.environ.get(SEATBELT_ENV_FLAG, "").strip() == "0":
        return False
    return os.path.exists(SEATBELT_BINARY) and os.access(SEATBELT_BINARY, os.X_OK)


def seatbelt_profile(workdir: str) -> str:
    """deny-list 风格：默认放行，只拦网络、fork、工作目录之外的写。

    SBPL 里后写的规则优先，所以先 ``(deny file-write*)`` 再对工作目录 ``allow``。
    路径用 realpath——macOS 的 ``/var`` 是 ``/private/var`` 的符号链接，Seatbelt 按
    真实路径匹配。
    """

    real = os.path.realpath(workdir).replace("\\", "\\\\").replace('"', '\\"')
    return "\n".join(
        (
            "(version 1)",
            "(allow default)",
            "(deny network*)",
            "(deny process-fork)",
            "(deny file-write*)",
            f'(allow file-write* (subpath "{real}"))',
            '(allow file-write* (literal "/dev/null"))',
            '(allow file-write-data (regex #"^/dev/tty"))',
        )
    )


def _tail(text: str) -> str:
    text = text or ""
    return text if len(text) <= _TAIL_CHARS else text[-_TAIL_CHARS:]


def _rlimit_preexec(timeout: float):
    def _apply() -> None:
        try:
            import resource  # noqa: PLC0415
        except ImportError:  # pragma: no cover - non-POSIX
            return
        cpu = max(1, int(timeout) + 1)
        for name, value in (
            ("RLIMIT_CPU", (cpu, cpu + 2)),
            ("RLIMIT_FSIZE", (_FILE_SIZE_LIMIT, _FILE_SIZE_LIMIT)),
            ("RLIMIT_NOFILE", (_OPEN_FILES_LIMIT, _OPEN_FILES_LIMIT)),
        ):
            limit = getattr(resource, name, None)
            if limit is None:
                continue
            try:
                resource.setrlimit(limit, value)
            except (ValueError, OSError):
                # 硬上限已经比我们要的低，或平台不允许——不因此放弃执行。
                continue
    return _apply


def _scrubbed_env(workdir: str) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": workdir,
        "TMPDIR": workdir,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
    }


def _parse_stdout(stdout: str) -> tuple[dict[str, object] | None, str]:
    result: dict[str, object] | None = None
    other: list[str] = []
    for line in (stdout or "").splitlines():
        if line.startswith(RESULT_SENTINEL + " "):
            try:
                decoded = json.loads(line[len(RESULT_SENTINEL) + 1 :])
            except json.JSONDecodeError:
                other.append(line)
                continue
            if isinstance(decoded, dict):
                result = decoded
            continue
        other.append(line)
    return result, "\n".join(other)


def _violations_from_stderr(stderr: str) -> tuple[str, ...]:
    found: list[str] = []
    for line in (stderr or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("SandboxViolation:"):
            found.append(stripped[len("SandboxViolation:") :].strip())
        elif "Operation not permitted" in stripped:
            # Seatbelt 拦下的 syscall 在 Python 里长成 PermissionError(EPERM)。
            found.append("os_denied: " + stripped[:160])
    return tuple(dict.fromkeys(found))


def _seatbelt_startup_failure(exit_code: int | None, stderr: str) -> bool:
    return exit_code not in (0, None) and "sandbox-exec:" in (stderr or "")


# --------------------------------------------------------------------------- run


def run_script(
    script: str,
    *,
    evidence: Sequence[Mapping[str, object]],
    db_path: str | os.PathLike[str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    python: str | None = None,
    guard: bool = True,
    seatbelt: bool | None = None,
) -> SandboxRun:
    """跑一段脚本，回 ``SandboxRun``。永不抛脚本侧的错——全部落在读数里。

    ``guard=False`` / ``seatbelt=False`` 只给测试用：前者证明进程层守卫真在拦，
    后者证明系统层真在拦（把 Python 守卫关掉、只留 Seatbelt，外呼仍失败）。
    """

    timeout = max(1.0, min(float(timeout), MAX_TIMEOUT_SECONDS))
    interpreter = python or sys.executable
    if not interpreter or not os.path.exists(interpreter):
        raise SandboxUnavailable(f"sandbox interpreter not found: {interpreter!r}")
    use_seatbelt = seatbelt_available() if seatbelt is None else bool(seatbelt)
    if use_seatbelt and not seatbelt_available():
        raise SandboxUnavailable("seatbelt requested but sandbox-exec is not usable here")

    workdir = os.path.realpath(tempfile.mkdtemp(prefix="derived-calc-"))
    notes: list[str] = []
    try:
        Path(workdir, "evidence.json").write_text(
            json.dumps(list(evidence), ensure_ascii=False, sort_keys=True, default=str),
            encoding="utf-8",
        )
        Path(workdir, "params.json").write_text(
            json.dumps(
                {
                    "db_path": os.fspath(db_path) if db_path else None,
                    "guard": bool(guard),
                    "blocked_modules": list(FORBIDDEN_IMPORT_MODULES),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        script_path = Path(workdir, "script.py")
        script_path.write_text(PRELUDE_SOURCE + script.rstrip() + "\n", encoding="utf-8")

        base_argv = [interpreter, "-s", "-B", "-P", str(script_path)]
        run = _execute(
            base_argv,
            workdir=workdir,
            timeout=timeout,
            seatbelt=use_seatbelt,
        )
        if use_seatbelt and _seatbelt_startup_failure(run.exit_code, run.stderr_tail):
            # profile 没编译过 / sandbox-exec 起不来：退回进程层再跑一次，并把原因记进收据。
            notes.append("seatbelt_unavailable: " + run.stderr_tail.strip()[:200])
            run = _execute(base_argv, workdir=workdir, timeout=timeout, seatbelt=False)
            use_seatbelt = False
        enforcement = _enforcement_label(guard=guard, seatbelt=use_seatbelt)
        return SandboxRun(
            enforcement=enforcement,
            exit_code=run.exit_code,
            duration_ms=run.duration_ms,
            result=run.result,
            stdout_tail=run.stdout_tail,
            stderr_tail=run.stderr_tail,
            timed_out=run.timed_out,
            violations=run.violations,
            notes=tuple(notes),
            runtime={
                "python": platform.python_version(),
                "interpreter": interpreter,
                "prelude_version": PRELUDE_VERSION,
                "platform": platform.system(),
            },
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _enforcement_label(*, guard: bool, seatbelt: bool) -> str:
    if guard and seatbelt:
        return "seatbelt+process"
    if seatbelt:
        return "seatbelt"
    if guard:
        return "process"
    return "none"


@dataclass(frozen=True)
class _RawRun:
    exit_code: int | None
    duration_ms: int
    result: dict[str, object] | None
    stdout_tail: str
    stderr_tail: str
    timed_out: bool
    violations: tuple[str, ...]


def _execute(
    base_argv: list[str],
    *,
    workdir: str,
    timeout: float,
    seatbelt: bool,
) -> _RawRun:
    argv = (
        [SEATBELT_BINARY, "-p", seatbelt_profile(workdir), *base_argv]
        if seatbelt
        else list(base_argv)
    )
    started = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(  # noqa: S603 - argv 由本模块构造，脚本内容只在文件里
            argv,
            cwd=workdir,
            env=_scrubbed_env(workdir),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout + 2.0,
            preexec_fn=_rlimit_preexec(timeout),
        )
        exit_code: int | None = completed.returncode
        stdout, stderr = completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout = _decode(exc.stdout)
        stderr = _decode(exc.stderr)
    if exit_code is not None and exit_code < 0 and -exit_code == _SIGXCPU:
        # RLIMIT_CPU 先于墙钟把进程打死（死循环就是这个形状）：同样算超时，不算脚本崩。
        timed_out = True
    duration_ms = int((time.monotonic() - started) * 1000)
    result, other_stdout = _parse_stdout(stdout)
    return _RawRun(
        exit_code=exit_code,
        duration_ms=duration_ms,
        result=result,
        stdout_tail=_tail(other_stdout),
        stderr_tail=_tail(stderr),
        timed_out=timed_out,
        violations=_violations_from_stderr(stderr),
    )


def _decode(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)
