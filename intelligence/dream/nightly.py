"""dream-loop 采集半（nightly）：collect → 新分支提交脱敏 digest（绝不合并 main）。

设计 decision1 §1/§4「采集半」。本模块只负责把**已脱敏**的 digest/manifest 提交到一个
suggest-only 分支并（可选）push，给推理半（C-1B-S2 Devin 定时 session）当燃料。

铁律（与项目 Git Branch Safety 一致）：
- 永远从最新 base（默认 ``origin/main``）切出 ``dream-loop/transcripts-<date>`` 分支，
  **绝不在 base / 用户工作分支上直接提交**；
- 只显式 ``git add`` ``manifest.jsonl`` 与 ``digest-*.md``，**绝不提交正文 jsonl**
  （正文按 .gitignore ``raw/transcripts/*/*.jsonl`` 忽略，这里再加一道显式白名单）；
- 只 push 分支、**绝不合并 main**（合并由用户/推理半 PR 决定）；
- 不碰 DuckDB。

供 launchd 每晚经 ``intelligence.cli dream-nightly`` 调用；也可手动跑。
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path
from typing import Dict, List, Optional

from intelligence.dream import collector

DEFAULT_STORE_SUBDIR = "raw/transcripts"
DEFAULT_BRANCH_PREFIX = "dream-loop/transcripts"


@dataclass(frozen=True)
class NightlyOptions:
    repo_dir: str
    events_path: Optional[str] = None
    source: str = "feishu"
    store_subdir: str = DEFAULT_STORE_SUBDIR
    branch_prefix: str = DEFAULT_BRANCH_PREFIX
    base: str = "main"
    remote: str = "origin"
    date: Optional[str] = None
    collect: bool = True
    push: bool = False


def _git(repo_dir: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", repo_dir, *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _today(options: NightlyOptions) -> str:
    return options.date or _date.today().isoformat()


def branch_name(options: NightlyOptions, today: str) -> str:
    return f"{options.branch_prefix}-{today}"


def _checkout_branch(options: NightlyOptions, branch: str) -> str:
    """从最新 base 切出工作分支；fetch 失败（离线/无凭证）回退本地 base。"""
    fetched = _git(options.repo_dir, "fetch", options.remote, options.base, check=False)
    start = f"{options.remote}/{options.base}" if fetched.returncode == 0 else options.base
    _git(options.repo_dir, "checkout", "-B", branch, start)
    return start


def stage_digests(repo_dir: str, store_subdir: str) -> List[str]:
    """显式 stage 仅 manifest.jsonl + digest-*.md（白名单），绝不碰正文 jsonl。"""
    sub = Path(store_subdir)
    store_path = Path(repo_dir) / sub
    rels: List[str] = []
    manifest = sub / "manifest.jsonl"
    if (Path(repo_dir) / manifest).is_file():
        rels.append(manifest.as_posix())
    if store_path.is_dir():
        for dg in sorted(store_path.glob("digest-*.md")):
            rels.append((sub / dg.name).as_posix())
    staged: List[str] = []
    for rel in rels:
        _git(repo_dir, "add", "--", rel)
        staged.append(rel)
    return staged


def _has_staged(repo_dir: str) -> bool:
    res = _git(repo_dir, "diff", "--cached", "--name-only", check=False)
    return bool(res.stdout.strip())


def run_nightly(options: NightlyOptions) -> Dict[str, object]:
    """采集半主流程：切分支 → 采集 → 提交 digest →（可选）push。返回机器可读摘要。"""
    repo_dir = options.repo_dir
    today = _today(options)
    summary: Dict[str, object] = {
        "date": today,
        "repo_dir": repo_dir,
        "branch": None,
        "collected": None,
        "staged": [],
        "committed": False,
        "pushed": False,
    }

    branch = branch_name(options, today)
    _checkout_branch(options, branch)
    summary["branch"] = branch

    if options.collect:
        store_dir = str(Path(repo_dir) / options.store_subdir)
        csum = collector.run_collect(
            collector.CollectOptions(
                events_path=options.events_path,
                store_dir=store_dir,
                source=options.source,
            )
        )
        summary["collected"] = {
            "source": csum.get("source"),
            "records_written": csum.get("records_written"),
            "records_redacted": csum.get("records_redacted"),
            "dates": csum.get("dates"),
        }

    staged = stage_digests(repo_dir, options.store_subdir)
    summary["staged"] = staged

    if _has_staged(repo_dir):
        _git(repo_dir, "commit", "-m", f"[dream-loop] transcripts digest {today}")
        summary["committed"] = True
        if options.push:
            _git(repo_dir, "push", options.remote, f"{branch}:{branch}")
            summary["pushed"] = True

    return summary


def render_summary(summary: Dict[str, object]) -> str:
    lines = [
        f"[dream-nightly] repo={summary.get('repo_dir')} date={summary.get('date')}",
        f"  分支={summary.get('branch')}",
    ]
    collected = summary.get("collected")
    if isinstance(collected, dict):
        lines.append(
            f"  采集：源={collected.get('source')} 写记录={collected.get('records_written')} "
            f"命中脱敏={collected.get('records_redacted')}"
        )
    staged = summary.get("staged") or []
    lines.append(f"  staged={', '.join(staged) if staged else '(无变更)'}")
    lines.append(f"  committed={summary.get('committed')} pushed={summary.get('pushed')}")
    return "\n".join(lines)
