#!/usr/bin/env python3
"""Worktree 合入看板：从 ``git cherry`` 生成，不手抄第二份清单。

失败形状
--------
多 session 并发留下几十棵 worktree。人写的 ``inflight/main.md`` 和项目笔记
「交接记录」会漂（写了「可合未合」之后合进去也不回写）。``git rev-list`` 的
ahead 数也会骗人：同一补丁以 squash / cherry-pick 进了 main，hash 不同仍算
超前。``git cherry`` 比的是补丁，全是 ``-`` 就是已经在基线里。

本脚本只打印。**绝不** ``worktree remove``。

SessionStart 只跑 ``--this``（当前 HEAD 一次 cherry，预算内两三行）。全仓
看板是人/agent 主动跑，不灌进每次会话。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

LEDGER_NAME = "deploy-ledger.jsonl"

# 「底旧」到多少才值得在 SessionStart 里喊一声。
#
# 失败形状（2026-09-13 实测）：主检出树落后 gitea/main 628 提交，而 ``--this``
# 只报 ``cherry+0``（= 我的补丁都进 main 了）。两件事是正交的：cherry 回答
# 「我有没有东西丢在外面」，behind 回答「我读到的代码是不是旧的」。只报前者，
# 一个照章办事的 agent 会把 ``cherry+0`` 读成「一切正常」，然后在旧代码上跑
# graph_audit —— 已合进 main 的能力被报成「在途 / 未进工作树」，据此写出
# 「我们没有 X」的错误负面断言，正是断言纪律要防的那件事。同族前科：夜跑的
# 代码根停在落后 548 提交的共用树，吃掉一个交易日（工单 #51）。
#
# 阈值不取 0：共享仓（harness-reference）那边取 0 是因为那是只读参照仓，不动
# 就不该落后；工作仓按构造天天落后（main 近期约 17 笔合入/天），取 0 会每次
# 会话都喊，喊到 agent 学会忽略它，比不喊更坏。50 ≈ 三天漂移。
# 数字本身无论多少都打印，⚠ 只在过阈值时加。
STALE_BASE_WARN = 50

CODE_DIRTY_PREFIXES = (
    "intelligence/",
    "evolution/",
    "market_feature_store/",
    "scripts/",
    "tests/",
    "conftest.py",
    "pytest.ini",
    "ruff.toml",
    "test-environment.json",
    "requirements-consumer.lock",
)
CODE_DIRTY_SKIP_PREFIXES = ("market_feature_store/exports/",)


@dataclass(frozen=True)
class TreeRow:
    path: str
    head: str
    branch: str
    cherry_plus: int
    cherry_minus: int
    ahead: int
    behind: int
    in_main: bool
    dirty: bool
    code_dirty: bool
    dirty_n: int
    kind: str
    subjects: tuple[str, ...] = field(default_factory=tuple)
    error: str = ""
    locked: str = ""
    prunable: str = ""


def _git(args: list[str], *, cwd: str | None, timeout: float) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return completed.returncode, (completed.stdout or "").strip()


def resolve_base(cwd: str, timeout: float) -> str:
    """合入基线：日常远程是 gitea/main，没有再退 origin/main、main。"""

    for candidate in ("gitea/main", "origin/main", "main"):
        code, _ = _git(["rev-parse", "--verify", "--quiet", candidate], cwd=cwd, timeout=timeout)
        if code == 0:
            return candidate
    return "HEAD"


def parse_worktree_porcelain(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw in text.splitlines():
        if raw.startswith("worktree "):
            if current:
                rows.append(current)
            current = {"path": raw.split(" ", 1)[1]}
        elif raw.startswith("HEAD "):
            current["head"] = raw.split(" ", 1)[1]
        elif raw.startswith("branch "):
            current["branch"] = raw.split(" ", 1)[1].removeprefix("refs/heads/")
        elif raw == "detached":
            current["branch"] = "(detached)"
        elif raw == "locked" or raw.startswith("locked "):
            current["locked"] = raw.partition(" ")[2] or "locked"
        elif raw == "prunable" or raw.startswith("prunable "):
            current["prunable"] = raw.partition(" ")[2] or "prunable"
    if current:
        rows.append(current)
    return rows


def tree_kind(path: str, main_checkout: str) -> str:
    posix = path.replace("\\", "/")
    if "/.finance-runtime/finance-workspace-" in posix:
        return "prod-snapshot"
    if "/fwp-wt-" in posix or "/.worktrees/" in posix:
        return "dev-wt"
    if os.path.abspath(path) == os.path.abspath(main_checkout):
        return "main-checkout"
    return "other"


def _status_paths(porcelain: str) -> list[str]:
    paths: list[str] = []
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        rel = line[3:].strip().strip('"')
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1]
        paths.append(rel)
    return paths


def is_code_dirty(paths: list[str]) -> bool:
    for rel in paths:
        if any(rel.startswith(skip) for skip in CODE_DIRTY_SKIP_PREFIXES):
            continue
        if any(rel.startswith(prefix) for prefix in CODE_DIRTY_PREFIXES):
            return True
    return False


def cherry_counts(head: str, base: str, *, cwd: str, timeout: float) -> tuple[int, int, bool]:
    code, _ = _git(["merge-base", "--is-ancestor", head, base], cwd=cwd, timeout=timeout)
    if code == 0:
        return 0, 0, True
    code, out = _git(["cherry", base, head], cwd=cwd, timeout=timeout)
    if code != 0:
        # Unknown is not zero: keep failed queries visible in JSON and --this.
        return -1, -1, False
    plus = minus = 0
    for line in out.splitlines():
        if line.startswith("+ "):
            plus += 1
        elif line.startswith("- "):
            minus += 1
    return plus, minus, plus == 0


def unique_subjects(head: str, base: str, *, cwd: str, timeout: float, limit: int = 3) -> tuple[str, ...]:
    """只列 cherry+ 的补丁；``base..head`` 的 log 会把已等价进 main 的 hash 也算进去。"""

    code, out = _git(["cherry", "-v", base, head], cwd=cwd, timeout=timeout)
    if code != 0 or not out:
        return ()
    plus_lines = [line[2:] for line in out.splitlines() if line.startswith("+ ")]
    if len(plus_lines) > 80:
        return (f"（独特提交 {len(plus_lines)} 笔，略）",)
    return tuple(plus_lines[:limit])


def _count(args: list[str], *, cwd: str, timeout: float) -> int:
    """``rev-list --count`` 的安全读法：非数字一律当 0。

    直接 ``int(out or 0)`` 会在 git 把话写到 stdout 时抛 ValueError。本脚本
    喂的是 SessionStart，抛出去就是 hook 静默不输出——等于没装（见模块头）。
    """

    code, out = _git(args, cwd=cwd, timeout=timeout)
    if code != 0 or not out.isdigit():
        return 0
    return int(out)


def behind_count(head: str, base: str, *, cwd: str, timeout: float) -> int:
    """base 上有多少提交是 head 没有的 —— 「我读到的代码有多旧」。

    与 ``cherry_counts`` 正交：cherry 回答「我的补丁丢在外面没有」，两者都要
    报。只报 cherry 的后果见 ``STALE_BASE_WARN`` 的注释。
    """

    return _count(["rev-list", "--count", f"{head}..{base}"], cwd=cwd, timeout=timeout)


def classify_worktree(
    spec: dict[str, str],
    *,
    base: str,
    main_checkout: str,
    timeout: float,
) -> TreeRow | None:
    path = spec.get("path") or ""
    head = spec.get("head") or ""
    if not path or not head:
        return None
    code, top = _git(["rev-parse", "--show-toplevel"], cwd=path, timeout=timeout)
    error = ""
    if code != 0 or not top or Path(top).resolve() != Path(path).resolve():
        error = "worktree unavailable or repository root mismatch"
    plus, minus, in_main = cherry_counts(head, base, cwd=path, timeout=timeout)
    if plus < 0:
        error = error or "git cherry failed; merge status unknown"
    ahead = _count(["rev-list", "--count", f"{base}..{head}"], cwd=path, timeout=timeout)
    behind = behind_count(head, base, cwd=path, timeout=timeout)
    status_code, status = _git(["status", "--porcelain"], cwd=path, timeout=timeout)
    if status_code != 0:
        error = error or "git status failed; dirty state unknown"
    paths = _status_paths(status)
    subjects: tuple[str, ...] = ()
    if plus > 0:
        subjects = unique_subjects(head, base, cwd=path, timeout=timeout)
    return TreeRow(
        path=path,
        head=head,
        branch=spec.get("branch") or "?",
        cherry_plus=plus,
        cherry_minus=minus,
        ahead=ahead,
        behind=behind,
        in_main=in_main,
        dirty=bool(paths),
        code_dirty=is_code_dirty(paths),
        dirty_n=len(paths),
        kind=tree_kind(path, main_checkout),
        subjects=subjects,
        error=error,
        locked=spec.get("locked", ""),
        prunable=spec.get("prunable", ""),
    )


def _last_switch_unix(ledger: Path, port: int) -> float:
    """账本里该 port 末次 ``switch`` 行的时刻；没有就 -inf（排在任何有记录的后面）。

    只认写入侧落的 ``unix``（``deploy_ledger.record`` 每行都写），不解析 ``ts``
    字串——两个字段同源，少一套解析就少一处漂。
    """

    latest = float("-inf")
    try:
        text = ledger.read_text(encoding="utf-8")
    except OSError:
        return latest
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or row.get("action") != "switch":
            continue
        if str(row.get("port") or "") != str(port):
            continue
        try:
            unix = float(row.get("unix"))
        except (TypeError, ValueError):
            continue
        latest = max(latest, unix)
    return latest


def resolve_ledger_path(
    repo_root: Path, *, timeout: float = 2.0, port: int = 8792
) -> Path:
    """读取侧解析。唯一的默认家是 ``~/.finance-runtime/deploy-ledger.jsonl``，与
    ``intelligence.runtime.deploy_ledger.default_ledger_path`` 同址——SessionStart 在宿主
    python3 下跑、不 import 包，所以这里抄址不抄模块，改址两处一起改。

    失败形状（2026-09-08 实测）：账本有两个家——主检出树 ``state/`` 那份（带 ``FINANCE_WS``
    的生产启动与部署脚本写的）与 ``~/.finance-runtime`` 那份（链切规程显式 ``--ledger`` 写的）。
    按固定顺序取第一份，SessionStart 就把 8792 报成一天前的 rev，而生产早切了两次。
    2026-09-09 工单 #44 把写入侧收成一个家；读取侧过渡期仍看三个**旧家**（``$FINANCE_WS/state/``、
    ``<repo_root>/state/``、git common-dir 父目录的 ``state/``）——切流前旧代码的生产进程还往那儿
    写 startup。存在的候选里取该 port 末次 switch 最新的那份（#675 的读法，不退）；都没有
    switch 行时唯一家优先。``audit_deploy_ledger.py migrate-homes --apply`` 把旧家并入后旧文件
    改名 ``.migrated-*``，不再被本函数看见。
    """

    override = os.environ.get("FINANCE_DEPLOY_LEDGER", "").strip()
    if override:
        return Path(override).expanduser()
    home = Path.home() / ".finance-runtime" / LEDGER_NAME
    candidates: list[Path] = [home]
    finance_ws = os.environ.get("FINANCE_WS", "").strip()
    if finance_ws:
        candidates.append(Path(finance_ws).expanduser() / "state" / LEDGER_NAME)
    candidates.append(repo_root / "state" / LEDGER_NAME)
    code, common = _git(
        ["rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=str(repo_root),
        timeout=timeout,
    )
    if code == 0 and common:
        candidates.append(Path(common).resolve().parent / "state" / LEDGER_NAME)
    unique: list[Path] = []
    for path in candidates:
        if path not in unique:
            unique.append(path)
    existing = [path for path in unique if path.is_file()]
    if not existing:
        return home
    # 稳定排序：时刻相同（含都没有 switch 行）时唯一家在前、旧家按老顺序。
    return max(existing, key=lambda path: _last_switch_unix(path, port))


def last_switch_for_port(
    ledger: Path, port: int = 8792
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """返回 ``(该 port 末次 switch, 比它更新且没记 port 的 switch)``。

    第二项不为 None 时，第一项**已经不能代表该 port 的现状**——账本里更新的那次
    切换没写 port，读取侧无从归属。这里不替它猜：``deploy_ledger.infer_port`` 在
    写入侧就明写「认不出来就 None，不猜 8792」，读取侧补一个猜测只是把同一个猜测
    藏得更深，而且会猜错——账本里 8796 的末次 switch 后面同样跟着未归属行，按
    「取最新」归属会把 8792 的 rev 报成 8796 的。

    旧实现 ``return matched or fallback`` 的后果：切换时漏 ``--port`` 就落一行
    无归属的 switch，看板回落到上一条带 port 的行，于是**每个会话的 SessionStart
    都把上一版 rev 报成 8792 现状**（09-03 f4c03b9a 被报成 c88c81da；账本里已有
    16 行是这么来的）。源头治理见 ``docs/workflows/acceptance-workflow.md`` 的
    切换命令——执行切换的人是唯一知道端口的人，别把这个信息留给读取侧猜。
    """

    if not ledger.is_file():
        return None, None
    matched: dict[str, Any] | None = None
    unattributed: dict[str, Any] | None = None
    try:
        text = ledger.read_text(encoding="utf-8")
    except OSError:
        return None, None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or row.get("action") != "switch":
            continue
        if not row.get("rev"):
            continue
        row_port = row.get("port")
        if row_port is None or str(row_port).strip() == "":
            unattributed = row
        elif str(row_port) == str(port):
            # 该 port 有了更新的确凿行，之前那条未归属行不再影响判断
            matched = row
            unattributed = None
    return matched, unattributed


def display_path(path: str) -> str:
    home = str(Path.home())
    if path.startswith(home + os.sep) or path.startswith(home + "/"):
        return "~" + path[len(home) :]
    return path


def format_board(rows: list[TreeRow], *, base: str, base_sha: str) -> str:
    uncertain = [row for row in rows if row.error or row.locked or row.prunable]
    known = [row for row in rows if not (row.error or row.locked or row.prunable)]
    unique = [row for row in known if row.cherry_plus > 0]
    prune = [
        row
        for row in known
        if row.in_main and row.kind == "dev-wt" and not row.dirty
    ]
    snapshots = [row for row in known if row.kind == "prod-snapshot"]
    leftover_dirty = [
        row
        for row in known
        if row.in_main and row.kind == "dev-wt" and row.dirty
    ]
    lines = [
        f"基准 {base}={base_sha[:12]}  （合入看 cherry+，不是 ahead 提交数）",
        f"树 {len(rows)} 棵 · 还有补丁 {len(unique)} · 补丁已在基线的干净 dev 树 {len(prune)} · 待核实 {len(uncertain)}",
        "",
        "【还有补丁 — 真没合】",
    ]
    if not unique:
        lines.append("  （无）")
    for row in sorted(unique, key=lambda item: (item.cherry_plus, item.behind, item.branch)):
        flags = []
        if row.code_dirty:
            flags.append("CODE_DIRTY")
        elif row.dirty:
            flags.append("dirty")
        if row.behind:
            flags.append(f"behind:{row.behind}")
        flag = " ".join(flags)
        lines.append(
            f"  +{row.cherry_plus} -{row.cherry_minus}  {row.head[:12]}  "
            f"{row.branch}  {flag}".rstrip()
        )
        lines.append(f"      {display_path(row.path)}")
        for subject in row.subjects:
            lines.append(f"      · {subject}")
    lines += ["", "【补丁已在基线 — 树可拆，本脚本不拆】"]
    if not prune:
        lines.append("  （无）")
    for row in sorted(prune, key=lambda item: item.branch):
        extra = f"  dirty:{row.dirty_n}" if row.dirty else ""
        lines.append(
            f"  {row.head[:12]}  {row.branch}{extra}  {display_path(row.path)}"
        )
    if leftover_dirty:
        lines += ["", "【补丁已在基线，但还有未提交文件 — 先认领再拆】"]
        for row in leftover_dirty:
            lines.append(
                f"  {row.head[:12]}  {row.branch}  {display_path(row.path)}"
            )
    if uncertain:
        lines += ["", "【待核实 — 查询失败、失效目录或锁定；不可据此拆树】"]
        for row in uncertain:
            reason = "; ".join(filter(None, (row.error, row.locked, row.prunable)))
            lines.append(f"  {row.head[:12]}  {row.branch}  {display_path(row.path)}")
            lines.append(f"      {reason}")
    lines += ["", "【生产快照】只留当前 8792 + 一个回滚锚；本脚本不拆"]
    for row in snapshots:
        lines.append(
            f"  {row.head[:12]}  dirty={str(row.dirty).lower()}  {display_path(row.path)}"
        )
    lines += [
        "",
        "拆树（需你确认）：git worktree remove <path>",
        "合入状态不要写进 inflight/main.md 或项目笔记交接记录，下次跑本脚本。",
    ]
    return "\n".join(lines) + "\n"


def this_tree_lines(
    *,
    cwd: str,
    base: str,
    base_sha: str,
    timeout: float,
    repo_root: Path,
) -> list[str]:
    code, head = _git(["rev-parse", "HEAD"], cwd=cwd, timeout=timeout)
    if code != 0 or not head:
        return []
    plus, minus, in_main = cherry_counts(head, base, cwd=cwd, timeout=timeout)
    behind = behind_count(head, base, cwd=cwd, timeout=timeout)
    if plus < 0:
        merge = f"合入: 未知（git cherry 查询失败，基准 {base}={base_sha[:12]}）"
    elif in_main:
        merge = f"合入: 本枝补丁已在 {base}={base_sha[:12]}（cherry+0）"
    else:
        merge = (
            f"合入: 本枝 cherry+{plus} / cherry-{minus} vs {base}={base_sha[:12]}"
        )
    # 追加在同一行而不是新起一行：SessionStart 有 2000 字符预算，实测已在截断
    # 后省略三十余条，多一行就是挤掉另一条事实。落后量始终打印，⚠ 只在过阈值时加。
    if behind > 0:
        merge += f"；底落后 {behind} 提交"
        if behind >= STALE_BASE_WARN:
            merge += (
                f"（≥{STALE_BASE_WARN}）⚠ 本树跑出的门禁 / 能力图谱读数量的是旧代码，"
                "别据此下「我们没有 X」——先 fetch 或另开新树"
            )
    lines = [merge]
    switch, unattributed = last_switch_for_port(
        resolve_ledger_path(repo_root, timeout=timeout)
    )
    if unattributed is not None:
        # 报「不知道」而不是报一个更旧的 rev：后者每个会话都读起来像真值。
        newer = str(unattributed.get("rev") or "")[:12]
        known = str((switch or {}).get("rev") or "")[:12]
        known_bit = f"，末次带 port=8792 的是 {known}" if known else ""
        lines.append(
            f"8792: 账本判不出——更新的 switch {newer} 未记 port{known_bit}"
            "；取真值 scripts/audit_deploy_ledger.py check"
        )
    elif switch:
        rev = str(switch.get("rev") or "")
        port = switch.get("port")
        same = rev.startswith(base_sha[:12]) or base_sha.startswith(rev[:12])
        relation = "与 main 一致" if same else "与 main 不是同一份"
        port_bit = f" port={port}" if port is not None else ""
        lines.append(f"8792: {rev[:12]}（ledger switch{port_bit}；{relation}）")
    lines.append("看板: python3 scripts/worktree_board.py")
    return lines


def collect_rows(*, cwd: str, timeout: float) -> tuple[str, str, str, list[TreeRow]]:
    base = resolve_base(cwd, timeout)
    _, base_sha = _git(["rev-parse", base], cwd=cwd, timeout=timeout)
    _, common = _git(
        ["rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=cwd,
        timeout=timeout,
    )
    main_checkout = str(Path(common).resolve().parent) if common else cwd
    _, porcelain = _git(["worktree", "list", "--porcelain"], cwd=cwd, timeout=timeout)
    rows: list[TreeRow] = []
    for spec in parse_worktree_porcelain(porcelain):
        row = classify_worktree(
            spec, base=base, main_checkout=main_checkout, timeout=timeout
        )
        if row is not None:
            rows.append(row)
    return base, base_sha, main_checkout, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--json", action="store_true", help="机器可读")
    parser.add_argument(
        "--this",
        action="store_true",
        help="只报当前 HEAD（给 SessionStart，不扫全仓）",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="单次 git 超时秒数",
    )
    args = parser.parse_args(argv)
    cwd = os.getcwd()
    repo_root = Path(cwd)
    timeout = max(1.0, float(args.timeout))
    if args.this:
        timeout = min(timeout, 8.0)
        base = resolve_base(cwd, timeout)
        _, base_sha = _git(["rev-parse", base], cwd=cwd, timeout=timeout)
        for line in this_tree_lines(
            cwd=cwd,
            base=base,
            base_sha=base_sha,
            timeout=timeout,
            repo_root=repo_root,
        ):
            print(line)
        return 0
    base, base_sha, _main_checkout, rows = collect_rows(cwd=cwd, timeout=timeout)
    if args.json:
        payload = {
            "base": base,
            "base_sha": base_sha,
            "trees": [asdict(row) for row in rows],
        }
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0
    sys.stdout.write(format_board(rows, base=base, base_sha=base_sha))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
