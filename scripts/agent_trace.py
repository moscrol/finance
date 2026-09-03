#!/usr/bin/env python3
"""让 agent **直调组件**时也产出与 Workbench 同构的 run 目录，用于跨 harness 对比 loop。

**为什么需要它**：`trace.jsonl` 只有一条产生路径——请求打进 FastAPI 那个进程
（`RunStore.append_step` 的三个生产写入方，构造点全在 `intelligence/api/app.py`）。
agent 在会话里直调 `services/` 里的积木（`ask.answer_query`、`research_tool_registry`
里的工具等）一步也不会留下，于是「Workbench 的 loop」与「agent 自己的 loop」之间
**没有可比的产物**：一边有九步流水，另一边只有聊天记录。

本脚本补的就是这条缺口，且刻意**不新造格式**：

- step 一律过 `run_store.build_trace_step`（schema 的唯一定义处，见其 docstring）；
- 落盘走 `RunStore`，目录布局与 Workbench 完全一致；
- 于是 `intelligence/eval/normalize_harness_trace.py --kind workbench-trace --compare`
  可以直接吃两边，输出 `first_divergence_step`。

三条关键设计（每条对应一个真实踩过的失败形状）：

1. **根必须显式，不猜、不回落。**
   本机同时跑着 6 个 Workbench 服务、5 个不同的 `FORESIGHT_USERS_DIR`
   （2026-08-23 实测）。而 `userspace.users_dir()` 在环境变量缺失时会**静默**
   回落到仓内 `intelligence/users/`。两者相加的失败形状是：run 写进了 A 根，
   对比时从 B 根取 Workbench 的 run，diff 出来的差异全是噪音，而且**看起来完全
   合理**。所以这里三选一（`--from-port` / `--root` / 环境变量），一个都没有
   就报错退出，绝不回落。

2. **run 句柄自带根。**
   `open` 打印的不是裸 run_id，而是 ``<root>::<user>::<run_id>``。后续 `step`
   / `close` 只认这个句柄。CLI 跨多次调用是无状态的，若让调用方每次重新指定根，
   迟早会有一次指错——句柄自带根则**跨根在机制上不可能**。

3. **写入口就校验可映射性。**
   `normalize_harness_trace` 的 mapper 是子串匹配：名字不含它认识的词就落
   `unmapped`。曾经有一份 264 事件的产物 264/264 全 `unmapped`，而它同时报
   `unpaired_tool_requests=0`（分母是 0），读起来像"健康"。所以本脚本在**写之前**
   就把这一步喂给 `normalize_records` 试映射，映不上直接拒写并提示可用词
   （`--allow-unmapped` 可显式放行）。晚一步发现，代价就是整批白跑。

⚠️ **一个必须知道的口径**：`workbench-trace` 这个 mapper **没有 `tool` 分支**，
`retrieve/skill/research/evidence` 全部压成 `retrieve`。这不是本脚本的缺陷，是
两边**共用**的粗粒度——好处是对比公平（同样被压），代价是工具级差异在 L1 层
看不见。要看工具级分叉，读原始 `trace.jsonl` 的 `name` 字段，别读归一化产物。

用法（bash，跨多次调用）::

    handle=$(scripts/agent_trace.py open --from-port 8802 --question "光伏怎么看")
    scripts/agent_trace.py step "$handle" --step-id route.1 --name question_router \\
        --status completed --output "lane=research"
    scripts/agent_trace.py step "$handle" --step-id retrieve.1 --name evidence_search \\
        --status completed --output "hits=6"
    scripts/agent_trace.py close "$handle" --status completed

用法（Python，单进程内；``scripts/`` 不是包，把该目录加进 ``sys.path``）::

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path("scripts").resolve()))
    from agent_trace import AgentRun

    with AgentRun("光伏怎么看", from_port=8802) as run:
        with run.step("route.1", "question_router") as s:
            s.output = "lane=research"

``finance_query`` / ``kb_search`` 这类工具名本身不在 L1 词表里。
``step_id`` 写成 ``retrieve.finance_query`` 就能映上；裸名会被拒写。

对比::

    scripts/agent_trace.py compare "$handle" run_20260823_144802_626720

只读别人的东西：不写 DuckDB、不写飞书、不碰 Workbench 已有用户的 sqlite
（每个 user 自己一个 `workbench.sqlite3`，用独立 user id 即无锁竞争）。
"""
from __future__ import annotations

import argparse
import contextlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

#: agent 直调的默认用户名。刻意与真人分开：linxiaoqi5111 名下已有 454 个 run，
#: 混进去之后「哪些是我问的」就再也分不出来了。
DEFAULT_AGENT_USER = "agent-adhoc"

_HANDLE_SEP = "::"
_PORT_RE = re.compile(r"^\d{2,5}$")


class TraceSetupError(RuntimeError):
    """根/用户/步骤名不合法。一律 fail closed，不降级继续。"""


# ---------------------------------------------------------------- 根解析


def _pid_listening_on(port: int) -> int | None:
    """找监听该端口的进程。lsof 优先，失败回落到扫 ``--port N`` 命令行。"""

    try:
        out = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        if out:
            return int(out.splitlines()[0])
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    try:
        out = subprocess.run(
            ["ps", "axo", "pid=,args="], capture_output=True, text=True, timeout=10
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        if f"--port {port}" in line and "uvicorn" in line:
            with contextlib.suppress(ValueError):
                return int(line.split(None, 1)[0])
    return None


def _process_env(pid: int) -> dict[str, str]:
    """读活进程的环境变量。

    为什么不读文档/不读 `.env`：同一份 CLAUDE.md 描述的服务，本机跑着 5 个不同
    的 `FORESIGHT_USERS_DIR`。**进程自己说的才算数**，文档只是当时的快照。
    """

    try:
        out = subprocess.run(
            ["ps", "eww", str(pid)], capture_output=True, text=True, timeout=10
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    env: dict[str, str] = {}
    for token in out.split():
        key, sep, value = token.partition("=")
        if sep and key.isupper():
            env[key] = value
    return env


def resolve_users_root(
    *, from_port: int | None = None, root: str | Path | None = None
) -> tuple[Path, str]:
    """定位 users 根，返回 ``(根, 来源说明)``。三个来源都没有则报错。

    刻意**不**调用 `userspace.users_dir()` 的默认分支：那条分支在环境变量缺失时
    回落到仓内 `intelligence/users/`，而这里最不能接受的就是"悄悄换了个根"。
    """

    if root is not None:
        return Path(root).expanduser().resolve(), "--root"
    if from_port is not None:
        pid = _pid_listening_on(from_port)
        if pid is None:
            raise TraceSetupError(
                f"端口 {from_port} 上没有监听进程。先确认服务在跑："
                f"ps axo pid=,args= | grep 'port {from_port}'"
            )
        value = _process_env(pid).get("FORESIGHT_USERS_DIR", "").strip()
        if not value:
            raise TraceSetupError(
                f"pid {pid}（端口 {from_port}）没有设 FORESIGHT_USERS_DIR，"
                "说明它用的是仓内默认根。请显式 --root 指明你要落到哪。"
            )
        return Path(value).expanduser().resolve(), f"pid {pid} @ :{from_port}"
    value = (os.environ.get("FORESIGHT_USERS_DIR") or "").strip()
    if value:
        return Path(value).expanduser().resolve(), "环境变量 FORESIGHT_USERS_DIR"
    raise TraceSetupError(
        "没能确定 users 根。三选一：\n"
        "  --from-port 8802   从活着的 Workbench 进程读它真正在用的根（推荐）\n"
        "  --root <路径>       显式指定\n"
        "  export FORESIGHT_USERS_DIR=<路径>\n"
        "刻意不回落仓内默认根：本机有 5 个不同的根在用，落错根的 diff 全是噪音。"
    )


# ---------------------------------------------------------------- run 句柄


@dataclass(frozen=True)
class RunHandle:
    """``<root>::<user>::<run_id>``——自带根，所以后续步骤跨不到别的根去。"""

    root: Path
    user: str
    run_id: str

    def encode(self) -> str:
        return _HANDLE_SEP.join([str(self.root), self.user, self.run_id])

    @classmethod
    def decode(cls, text: str) -> "RunHandle":
        parts = text.split(_HANDLE_SEP)
        if len(parts) != 3 or not all(part.strip() for part in parts):
            raise TraceSetupError(
                f"非法 run 句柄：{text!r}（应形如 <root>{_HANDLE_SEP}<user>{_HANDLE_SEP}<run_id>，"
                "由 `agent_trace.py open` 打印）"
            )
        return cls(Path(parts[0]), parts[1], parts[2])

    def run_dir(self) -> Path:
        return self.root / self.user / "runs" / self.run_id


@contextlib.contextmanager
def _users_dir_override(root: Path):
    """只在构造 RunStore 的瞬间改环境变量，用完立刻还原。

    不还原的失败形状：pytest 同进程里后续用例、或 agent 接着调
    ``userspace.users_dir()``，会悄悄写进这次对比用的临时根。
    """

    key = "FORESIGHT_USERS_DIR"
    previous = os.environ.get(key)
    os.environ[key] = str(root)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


def _store(root: Path, user: str):
    """构造 RunStore。

    走**环境变量**而不是 `RunStore(root=...)`：后者是给测试用的扁平覆盖
    （`self.root` 直接就是 runs 目录、sqlite 落在它旁边），布局与 Workbench
    不一致，归一化脚本按 `<base>/<uid>/runs/<run_id>` 找不到东西。
    ``RunStore.__init__`` 当时就会把路径钉死，所以 override 可以马上撤。
    """

    from intelligence.services.run_store import RunStore

    with _users_dir_override(root):
        return RunStore(user_id=user)


# ---------------------------------------------------------------- 步骤校验


def check_mappable(step_id: str, name: str) -> str:
    """把一条步骤喂给真 mapper 试映射，返回映到的 L1 步骤名。

    用 `normalize_records` 而不是自己抄一份子串规则：两份定义一旦漂移，
    这里说"能映"而归一化时落 unmapped，就又回到"产出的东西对比工具读不了"
    那个老坑里去了。
    """

    from intelligence.eval.normalize_harness_trace import normalize_records

    events = normalize_records(
        [{"step_id": step_id, "name": name, "status": "completed"}],
        kind="workbench-trace",
    )
    return events[0].step if events else "unmapped"


def _vocabulary_hint() -> str:
    return (
        "step_id/name 里带上这些词即可映射到对应 L1 步骤：\n"
        "  configure  <- configure / assembly\n"
        "  plan       <- plan\n"
        "  intent     <- controller / intent\n"
        "  route      <- route\n"
        "  observe    <- observe / validate / budget / ledger\n"
        "  retrieve   <- retrieve / skill / research / evidence\n"
        "  synthesize <- synth / compose / grounded / shadow\n"
        "  stop       <- stop / complete / finish / terminal / error\n"
        "（注意：workbench-trace 没有 tool 分支，工具调用会被压成 retrieve——\n"
        " 这是两边共用的粗粒度，工具级差异要读原始 trace.jsonl 的 name 字段）"
    )


# ---------------------------------------------------------------- 写入


def open_run(
    question: str,
    *,
    task_type: str = "adhoc",
    user: str = DEFAULT_AGENT_USER,
    from_port: int | None = None,
    root: str | Path | None = None,
) -> tuple[RunHandle, str]:
    resolved, origin = resolve_users_root(from_port=from_port, root=root)
    store = _store(resolved, user)
    run = store.create_run(question, task_type)
    return RunHandle(resolved, user, run.run_id), origin


def append_step(
    handle: RunHandle,
    *,
    step_id: str,
    name: str,
    status: str = "completed",
    input_summary: str = "",
    output_summary: str = "",
    warnings: list[str] | None = None,
    tokens: int | None = None,
    allow_unmapped: bool = False,
) -> str:
    mapped = check_mappable(step_id, name)
    if mapped == "unmapped" and not allow_unmapped:
        raise TraceSetupError(
            f"step_id={step_id!r} name={name!r} 映射不到 L1 词表，写了也进不了对比。\n"
            f"{_vocabulary_hint()}\n"
            "确实要记一条对比时看不见的步骤，加 --allow-unmapped。"
        )
    store = _store(handle.root, handle.user)
    store.append_step(
        handle.run_id,
        step_id=step_id,
        name=name,
        status=status,
        input_summary=input_summary,
        output_summary=output_summary,
        warnings=warnings,
        tokens=tokens,
    )
    return mapped


def close_run(handle: RunHandle, *, status: str = "completed", error: str | None = None):
    store = _store(handle.root, handle.user)
    return store.finish_run(handle.run_id, status, error=error)


# ---------------------------------------------------------------- Python 门面


class _Step:
    def __init__(self, step_id: str, name: str) -> None:
        self.step_id = step_id
        self.name = name
        self.input = ""
        self.output = ""
        self.warnings: list[str] = []
        self.tokens: int | None = None


class AgentRun:
    """上下文管理器版。异常会把该步与整个 run 都标成 failed，不会留下半开的 run。"""

    def __init__(
        self,
        question: str,
        *,
        task_type: str = "adhoc",
        user: str = DEFAULT_AGENT_USER,
        from_port: int | None = None,
        root: str | Path | None = None,
        allow_unmapped: bool = False,
    ) -> None:
        self.handle, self.origin = open_run(
            question, task_type=task_type, user=user, from_port=from_port, root=root
        )
        self.allow_unmapped = allow_unmapped

    @contextlib.contextmanager
    def step(self, step_id: str, name: str):
        record = _Step(step_id, name)
        try:
            yield record
        except Exception as exc:  # noqa: BLE001 - 失败也要留痕，再抛给调用方
            append_step(
                self.handle,
                step_id=step_id,
                name=name,
                status="failed",
                input_summary=record.input,
                output_summary=f"{type(exc).__name__}: {exc}"[:240],
                warnings=record.warnings,
                tokens=record.tokens,
                allow_unmapped=True,
            )
            raise
        append_step(
            self.handle,
            step_id=step_id,
            name=name,
            status="completed",
            input_summary=record.input,
            output_summary=record.output,
            warnings=record.warnings,
            tokens=record.tokens,
            allow_unmapped=self.allow_unmapped,
        )

    def __enter__(self) -> "AgentRun":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        close_run(
            self.handle,
            status="completed" if exc_type is None else "failed",
            error=None if exc is None else f"{exc_type.__name__}: {exc}",
        )
        return False


# ---------------------------------------------------------------- 对比


def _resolve_trace(text: str, *, peer_of: RunHandle | None) -> Path:
    """把「句柄」或「裸 run_id」都解析成 trace.jsonl 路径。

    裸 run_id 按 ``peer_of`` 的根解析——对比的典型场景就是"我的 run vs 同一个根下
    Workbench 的 run"，让第二个参数省掉根是刻意的便利；但**只在有 peer 时**才敢
    这么推断，没有就要求写全句柄。
    """

    if _HANDLE_SEP in text:
        return RunHandle.decode(text).run_dir() / "trace.jsonl"
    candidate = Path(text)
    if candidate.exists():
        return candidate / "trace.jsonl" if candidate.is_dir() else candidate
    if peer_of is None:
        raise TraceSetupError(
            f"{text!r} 既不是句柄也不是存在的路径，且没有可参照的根。"
            "请传完整句柄，或直接给 trace.jsonl 路径。"
        )
    for user_dir in sorted(peer_of.root.iterdir()):
        path = user_dir / "runs" / text / "trace.jsonl"
        if path.exists():
            return path
    raise TraceSetupError(f"在根 {peer_of.root} 下没找到 run {text!r}")


def compare(left: str, right: str) -> int:
    left_handle = RunHandle.decode(left) if _HANDLE_SEP in left else None
    left_path = _resolve_trace(left, peer_of=None)
    right_path = _resolve_trace(right, peer_of=left_handle)
    for path in (left_path, right_path):
        if not path.exists():
            print(f"trace 不存在：{path}", file=sys.stderr)
            return 2
    from intelligence.eval.normalize_harness_trace import main as normalize_main

    print(f"# 左 {left_path}\n# 右 {right_path}", file=sys.stderr)
    # 进程内调用：同一份 mapper，不另起解释器。退出码 0 只表示两边
    # 文件都在、对比算完了——等不等价看 stdout 的 comparison 块。
    return normalize_main(
        [
            str(left_path),
            "--kind",
            "workbench-trace",
            "--compare",
            str(right_path),
            "--compare-kind",
            "workbench-trace",
        ]
    )


# ---------------------------------------------------------------- CLI


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="agent 直调组件时产出与 Workbench 同构的 run/trace，用于对比 loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_vocabulary_hint(),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_root_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--from-port", type=int, help="从监听该端口的 Workbench 进程读它在用的根")
        p.add_argument("--root", help="显式指定 users 根")

    p_open = sub.add_parser("open", help="开一个 run，打印句柄")
    p_open.add_argument("--question", required=True)
    p_open.add_argument("--task-type", default="adhoc")
    p_open.add_argument("--user", default=DEFAULT_AGENT_USER)
    add_root_args(p_open)

    p_step = sub.add_parser("step", help="追加一步")
    p_step.add_argument("handle")
    p_step.add_argument("--step-id", required=True)
    p_step.add_argument("--name", required=True)
    p_step.add_argument("--status", default="completed", choices=("running", "completed", "failed", "skipped"))
    p_step.add_argument("--input", default="")
    p_step.add_argument("--output", default="")
    p_step.add_argument("--warning", action="append", default=[])
    p_step.add_argument("--tokens", type=int)
    p_step.add_argument("--allow-unmapped", action="store_true")

    p_close = sub.add_parser("close", help="收尾")
    p_close.add_argument("handle")
    p_close.add_argument("--status", default="completed", choices=("completed", "failed", "cancelled"))
    p_close.add_argument("--error")

    p_cmp = sub.add_parser("compare", help="与另一个 run 对比控制流")
    p_cmp.add_argument("left", help="句柄 或 trace.jsonl 路径")
    p_cmp.add_argument("right", help="句柄 / 裸 run_id（按左侧的根找）/ trace.jsonl 路径")

    p_roots = sub.add_parser("roots", help="列出本机活着的 Workbench 及其根")

    p_vocab = sub.add_parser("vocab", help="打印 L1 词表与匹配关键词")

    del p_roots, p_vocab
    return parser


def cmd_roots() -> int:
    try:
        out = subprocess.run(
            ["ps", "axo", "pid=,args="], capture_output=True, text=True, timeout=10
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"无法枚举进程：{exc}", file=sys.stderr)
        return 2
    rows: list[tuple[str, str, str]] = []
    for line in out.splitlines():
        if "intelligence.api.app" not in line or "--port" not in line:
            continue
        parts = line.split()
        pid = parts[0]
        port = next((parts[i + 1] for i, tok in enumerate(parts) if tok == "--port"), "?")
        env = _process_env(int(pid))
        rows.append((port, pid, env.get("FORESIGHT_USERS_DIR", "（未设 → 仓内默认根）")))
    if not rows:
        print("没有活着的 Workbench 进程。")
        return 0
    width = max(len(r[2]) for r in rows)
    print(f"{'端口':<6} {'pid':<8} {'FORESIGHT_USERS_DIR':<{width}}")
    for port, pid, root in sorted(rows, key=lambda r: r[0]):
        print(f"{port:<6} {pid:<8} {root:<{width}}")
    distinct = {r[2] for r in rows}
    if len(distinct) > 1:
        print(f"\n⚠ {len(distinct)} 个不同的根在同时用。对比前务必确认两边同根。")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.cmd == "vocab":
            print(_vocabulary_hint())
            return 0
        if args.cmd == "roots":
            return cmd_roots()
        if args.cmd == "open":
            handle, origin = open_run(
                args.question,
                task_type=args.task_type,
                user=args.user,
                from_port=args.from_port,
                root=args.root,
            )
            print(f"# 根来自 {origin} → {handle.root}", file=sys.stderr)
            print(f"# run 目录 {handle.run_dir()}", file=sys.stderr)
            print(handle.encode())
            return 0
        if args.cmd == "step":
            handle = RunHandle.decode(args.handle)
            mapped = append_step(
                handle,
                step_id=args.step_id,
                name=args.name,
                status=args.status,
                input_summary=args.input,
                output_summary=args.output,
                warnings=args.warning or None,
                tokens=args.tokens,
                allow_unmapped=args.allow_unmapped,
            )
            print(f"{args.step_id} → L1:{mapped}")
            return 0
        if args.cmd == "close":
            handle = RunHandle.decode(args.handle)
            run = close_run(handle, status=args.status, error=args.error)
            steps = handle.run_dir() / "trace.jsonl"
            count = sum(1 for _ in steps.open(encoding="utf-8")) if steps.exists() else 0
            print(f"{run.run_id} status={run.status} steps={count}")
            print(f"对比：scripts/agent_trace.py compare '{handle.encode()}' <workbench_run_id>")
            return 0
        if args.cmd == "compare":
            return compare(args.left, args.right)
    except TraceSetupError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
