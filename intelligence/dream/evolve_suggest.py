"""dream-loop C-1C / 7A：``evolve.py suggest`` 夜间编排（DB 锁感知，suggest-only）。

设计依据 decision1 §5「策略调参建议」：本块在 Mac 夜间（错峰、晚于采集半）跑
``scripts/evolve.py suggest``，把*新产生*的 ``evolution/suggestions/suggestion-*.md``
提到一条 ``dream-loop/evolve-suggest-<date>`` 分支，等用户 review 后再合 main。

铁律（务必遵守）：
- 只读 DuckDB：``evolve.py suggest`` 用 ``connect(read_only=True)``；DB 缺失 / 被排他锁
  占用 / duckdb 不可用 / 退出码非零 → **优雅跳过（no-op），绝不崩、绝不重试写**。
  本线绝不起第二个 DuckDB 写进程。
- 白名单 staging：只 ``git add -f`` ``evolution/suggestions/suggestion-*.md``（该目录被
  ``.gitignore`` 忽略），**绝不 stage ``evolution/params.json``**（suggest 只建议）。
- suggest-only：只 commit 到分支、可选 push，**绝不合并 main、绝不写 params.json**。

main 上还没有 #35 的 ``nightly.py``，故 git 辅助函数在本模块自带（小幅重复可接受，
待 #35 合并后另行 DRY）。launchd 模板见 ``com.financeworkspace.dream-evolve-suggest.plist``。
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

DEFAULT_SUGGEST_SUBDIR = "evolution/suggestions"
DEFAULT_BRANCH_PREFIX = "dream-loop/evolve-suggest"
# 红线：永不出现在暂存区的路径片段。
FORBIDDEN_FRAGMENT = "params.json"


@dataclass(frozen=True)
class EvolveSuggestOptions:
    repo_dir: str
    python: Optional[str] = None  # 解释器（默认当前 sys.executable）
    user: Optional[str] = None  # 透传 evolve.py --user（默认共享基线）
    suggest_subdir: str = DEFAULT_SUGGEST_SUBDIR
    branch_prefix: str = DEFAULT_BRANCH_PREFIX
    base: str = "main"
    remote: str = "origin"
    date: Optional[str] = None
    run: bool = True  # 跑 evolve suggest；False 则只把现有新增建议提交到分支
    timeout: int = 900
    push: bool = False


def _git(repo_dir: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", repo_dir, *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _today(options: EvolveSuggestOptions) -> str:
    return options.date or _date.today().isoformat()


def branch_name(options: EvolveSuggestOptions, today: str) -> str:
    return f"{options.branch_prefix}-{today}"


def _suggest_dir(options: EvolveSuggestOptions) -> Path:
    return Path(options.repo_dir) / options.suggest_subdir


def list_suggestions(suggest_dir: Path) -> Set[str]:
    """目录下现有 ``suggestion-*.md`` 文件名集合（目录不存在则空集）。"""
    p = Path(suggest_dir)
    if not p.is_dir():
        return set()
    return {f.name for f in p.glob("suggestion-*.md") if f.is_file()}


def classify_skip(rc: int, stdout: str, stderr: str) -> Optional[str]:
    """把 evolve.py 非零退出归类成跳过原因（仅用于汇报，绝不抛错）。"""
    if rc == 0:
        return None
    text = ((stdout or "") + "\n" + (stderr or "")).lower()
    if "no module named 'duckdb'" in text or "no module named duckdb" in text:
        return "duckdb-unavailable"
    if "lock" in text:
        return "db-locked"
    if (
        "does not exist" in text
        or "no such file" in text
        or "unable to open database" in text
        or "cannot open" in text
    ):
        return "db-missing"
    return f"evolve-rc-{rc}"


def _run_suggest(options: EvolveSuggestOptions) -> Tuple[int, str, str, Optional[str]]:
    """subprocess 跑 ``scripts/evolve.py suggest``，返回 (rc, stdout, stderr, reason)。

    任何异常都吞掉并归类为跳过原因，绝不向上抛——夜间编排不能因 suggest 崩。
    """
    python = options.python or sys.executable
    script = str(Path(options.repo_dir) / "scripts" / "evolve.py")
    cmd = [python, script, "suggest"]
    if options.user:
        cmd += ["--user", options.user]
    try:
        proc = subprocess.run(
            cmd,
            cwd=options.repo_dir,
            capture_output=True,
            text=True,
            timeout=options.timeout,
        )
    except FileNotFoundError as exc:
        return (127, "", str(exc), "evolve-missing")
    except subprocess.TimeoutExpired as exc:
        return (124, "", str(exc), "evolve-timeout")
    except Exception as exc:  # noqa: BLE001 - 夜间编排绝不因 suggest 崩
        return (1, "", str(exc), "evolve-error")
    reason = classify_skip(proc.returncode, proc.stdout, proc.stderr)
    return (proc.returncode, proc.stdout, proc.stderr, reason)


def _checkout_branch(options: EvolveSuggestOptions, branch: str) -> str:
    """从最新 base 切工作分支；fetch 失败（离线/无凭证）回退本地 base。"""
    fetched = _git(options.repo_dir, "fetch", options.remote, options.base, check=False)
    start = f"{options.remote}/{options.base}" if fetched.returncode == 0 else options.base
    _git(options.repo_dir, "checkout", "-B", branch, start)
    return start


def stage_suggestions(repo_dir: str, suggest_subdir: str, names: List[str]) -> List[str]:
    """force-add 指定 ``suggestion-*.md``（该目录被 .gitignore 忽略，故用 ``-f``）。

    白名单硬门：只接受 ``suggestion-*.md`` 文件名，凡含 ``params.json`` 或不符命名者一律跳过。
    """
    sub = Path(suggest_subdir)
    staged: List[str] = []
    for name in sorted(names):
        if FORBIDDEN_FRAGMENT in name or not name.startswith("suggestion-") or not name.endswith(".md"):
            continue
        rel = (sub / name).as_posix()
        if FORBIDDEN_FRAGMENT in rel:
            continue
        target = Path(repo_dir) / sub / name
        if not target.is_file():
            continue
        _git(repo_dir, "add", "-f", "--", rel)
        staged.append(rel)
    return staged


def _staged_names(repo_dir: str) -> List[str]:
    res = _git(repo_dir, "diff", "--cached", "--name-only", check=False)
    return [line for line in res.stdout.splitlines() if line.strip()]


def _has_staged(repo_dir: str) -> bool:
    return bool(_staged_names(repo_dir))


def run_evolve_suggest(options: EvolveSuggestOptions) -> Dict[str, object]:
    """编排主流程：跑 suggest →（有新增建议才）开分支、白名单提交、可选 push。

    返回机器可读摘要；DB 缺失/被锁等情况下整体为 no-op，绝不抛错。
    """
    repo_dir = options.repo_dir
    today = _today(options)
    suggest_dir = _suggest_dir(options)
    summary: Dict[str, object] = {
        "date": today,
        "repo_dir": repo_dir,
        "suggest_subdir": options.suggest_subdir,
        "branch": None,
        "ran": False,
        "evolve_rc": None,
        "skipped_reason": None,
        "new_suggestions": [],
        "staged": [],
        "committed": False,
        "pushed": False,
    }

    before = list_suggestions(suggest_dir)
    if options.run:
        rc, _out, _err, reason = _run_suggest(options)
        summary["ran"] = True
        summary["evolve_rc"] = rc
        summary["skipped_reason"] = reason
    after = list_suggestions(suggest_dir)
    new = sorted(after - before)
    summary["new_suggestions"] = new

    if not new:
        # 无新增建议 → 整体 no-op（不开分支、不 commit、不 push）
        return summary

    branch = branch_name(options, today)
    _checkout_branch(options, branch)
    summary["branch"] = branch

    staged = stage_suggestions(repo_dir, options.suggest_subdir, new)
    # 红线复核：暂存区绝不能出现 params.json（理论上 stage_suggestions 已过滤）。
    leaked = [n for n in _staged_names(repo_dir) if FORBIDDEN_FRAGMENT in n]
    if leaked:
        _git(repo_dir, "reset", "-q", "HEAD", "--", *leaked, check=False)
        staged = [s for s in staged if FORBIDDEN_FRAGMENT not in s]
    summary["staged"] = staged

    if _has_staged(repo_dir):
        _git(repo_dir, "commit", "-m", f"[dream-loop] evolve suggest {today}")
        summary["committed"] = True
        if options.push:
            _git(repo_dir, "push", options.remote, f"{branch}:{branch}")
            summary["pushed"] = True
    return summary


def render_summary(summary: Dict[str, object]) -> str:
    lines = [
        f"[dream-evolve-suggest] repo={summary.get('repo_dir')} date={summary.get('date')}",
        f"  分支={summary.get('branch')}",
        f"  ran={summary.get('ran')} evolve_rc={summary.get('evolve_rc')} skip={summary.get('skipped_reason')}",
    ]
    new = summary.get("new_suggestions") or []
    if isinstance(new, list):
        lines.append(f"  新增建议={', '.join(new) if new else '(无)'}")
    staged = summary.get("staged") or []
    if isinstance(staged, list):
        lines.append(f"  staged={', '.join(staged) if staged else '(无变更)'}")
    lines.append(f"  committed={summary.get('committed')} pushed={summary.get('pushed')}")
    return "\n".join(lines)
