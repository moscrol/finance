#!/usr/bin/env python3
"""Worktree 收口：点名的树先保全残留、逐棵复核，再 ``git worktree remove --force``。

默认 dry-run（只采样、写收据，不动任何东西）；``--apply --plan <dry-run 收据>`` 才动手；
每轮一份 JSON 收据。**不做**自动 / 定时清理——2026-09-23 用户明确否决了自动清扫：哪些树
该收口是人的判断（或受托代拍、逐条写理由），本脚本只负责「判断之后怎么拆才不丢东西」。

为什么是新脚本，而不是扩现有三件
--------------------------------
- ``worktree_board.py`` 的契约是「只打印，绝不 worktree remove」，SessionStart 每次会话都跑
  它的 ``--this``。收口要写 ref、写归档、拆树，塞进去就把只读看板变成有副作用的入口。
  只读的那一半（内容落地比例）加在了看板上：``worktree_board.py --landed``。
- ``cleanup_gate_trees.sh`` 是全仓扫描器，它的安全来自「只拆干净树，任何内容都算阻塞」——
  没有东西要保全，所以不需要保全。收口正相反：点名的树往往带着未提交内容，要先存补丁、
  打包、封存再拆。把保全逻辑加进扫描器，等于给「全仓自动扫」配上拆脏树的能力，那正是被
  否决的自动清扫。补丁回验、tar 回读、临时索引、JSON 收据用 bash 写，也就是第八轮重写。
- ``worktree_safety.py`` 是三者共用的只读采样。本脚本需要的新只读原语（porcelain 记录解析、
  只看 cwd 的 lsof、Gitea 可达性、改动时间、具名 ref 可达性）都放回了那里，看板与扫描器能用。

它取代 2026-09-23..09-28 七轮各写一遍的一次性脚本（``~/.finance-runtime/reviews/`` 下的
``disk-cleanup-20260923/round5-worktrees.py``、``pi-session-inventory-20260924/cleanup/*.py``、
``unclosed-inventory-20260926/raw/{wt_classify,categorize}.py``、
``legacy-worktree-closeout-20260928/{classify,plan,closeout}.py`` 与 ``ratio.sh``）。口径以
09-28 那版为准，加上它踩过或漏掉的坑（本文末）。分类表（哪棵属于过期快照 / 已落地 / 搁置）
不进脚本：那是每轮的判断，写进 plan 的 ``reason``。

流程
----
1. dry-run：``--tree <路径> --reason <理由>`` 或 ``--plan <计划.json>`` 点名，逐棵采样、列阻塞项，
   写 ``dry-<时刻>.json``。**这份收据就是 apply 的计划**：它记着每棵树采样时的 HEAD 与时刻，
   apply 的复核以它为基准。没写理由也算阻塞项。「无阻塞」（CLEAR）只说明拆了不丢东西、没人在用，
   不说明该拆：回滚锚、保留约定、在途线本脚本认不出（2026-09-28 实测：8792 切走后的上一版快照
   没有任何进程与启动器引用，照样报 CLEAR），去留看理由。
2. apply：``--apply --plan <dry-run 收据>``，只处理采样时没有阻塞项的树，逐棵：

   a. 复核：HEAD 仍是采样值；没有进程打开树里的文件（开轮一次全量 lsof），也没有进程 cwd
      在树里（``lsof -d cwd``，每棵现采）；不被 launchd / ``~/.local/bin`` / 运行时软链引用；
      采样后树里没有文件或目录变过；HEAD 的提交全在 Gitea（``rev-list HEAD`` 减去
      ``git ls-remote`` 报出的全部 sha 为 0）。任一不满足就跳过这棵，一个字节不动。
   b. HEAD 钉到 ``refs/archive/wt-<日期>/<slug>``（slug = 相对家目录的路径，去掉
      ``.finance-runtime/`` 前缀，``/`` 换 ``--``；与 09-28 的钉同名规则）。
   c. 被跟踪文件的改动：``git diff --binary HEAD`` 存 ``<slug>/tracked.patch``，并在临时索引上
      ``git apply --cached --check`` 回验。
   d. 未跟踪 + 被忽略的非缓存文件：打 ``<slug>/residue.tar.gz``，回读核对文件名单与大小。
      缓存与 ``worktree_safety.is_cache_path`` 同一口径：``__pycache__``、``.pytest_cache``、
      ``.ruff_cache``、``.mypy_cache``、``node_modules``、``.code-review-graph``、``.venv*``、
      ``*.pyc``、``.DS_Store``。
   e. 数据库文件（``*.duckdb`` / ``*.db`` / ``*.sqlite*`` 及其 wal / shm / journal）不进 tar：
      clonefile(2) 克隆到 ``<slug>/clones/``，sha256 回读核对，写 ``MANIFEST.sha256``（见下节）。
   f. 真实的未提交源码封存成分支 ``salvage/<slug>-<日期>``：临时 ``GIT_INDEX_FILE`` 从 HEAD
      起 ``add`` → ``write-tree`` → ``commit-tree``，树自己的索引与工作区不动。不带：禁提文件
      （pre-commit block-forbidden-files 与 AGENTS.md 两份清单的并集）、运行噪声（``NOISE_PREFIXES``）、
      缓存、超过 5 MiB 的文件、嵌套仓——它们都还在补丁或残留包里。回验：封存提交与工作区在
      这些路径上逐一相同。
   g. 钉与封存分支推 Gitea（不 force，远端已有同名不同值就失败）。
   h. 最后一道闸：HEAD、cwd 进程、采样后改动再核一次（归档那几分钟里有人进树就不拆）。
   i. 锁树只在计划里写了 ``release_lock`` 时才 ``unlock``；然后 ``git worktree remove --force``。

   任何一步失败就停掉整轮，已做的写进收据。分支一律保留（不 ``branch -d``），不 ``prune``。

APFS 克隆：别按 du 估节省，别压缩 DuckDB
----------------------------------------
本仓的 DuckDB 拷贝是 APFS 克隆（``market_feature_store.db.clone_to_staging`` / ``cp -c``），
物理块与生产库、``db/*.bak-*`` 共用。``du`` 按逻辑大小数，每份都把共享块算一遍，所以**高估
可回收空间**：删一份只释放它独占的块。把克隆压缩成独立文件是**新写数据**，占用反而上升。
2026-09-28 实测：两棵取证树 ``du`` 17.5 GB，拆掉只释放约 0.5 GiB，写下的 zstd 压缩件却是
4.5 GiB 独占数据，数据卷可用 39 → 35 GiB。

所以本脚本不用 ``du`` 估任何节省（``*.duckdb`` 尤其不行），apply 收据只记卷可用空间的前后差
（``statvfs`` 实测）。数据库残留用 clonefile(2) 克隆：不新增数据块，拆树后块由克隆继续持有。
克隆失败（跨卷、非 APFS）就整棵失败，绝不静默退化成整份拷贝——``cp -c`` 在跨卷时会静默
退化，所以这里直接调系统调用。

这几轮一次性脚本踩过的坑（都有测试钉住）
----------------------------------------
- porcelain ``-z`` 输出不能 strip：首条记录 `` M path`` 的前导空格是状态列（咬过两次）。
- ``rev-list <head> --not --stdin`` 不否定 stdin 读进来的 sha（git 2.50 同一仓 6513 vs 1），
  要逐行喂 ``^<sha>``。
- ``ls-remote`` 报出、本机没 fetch 过的 sha 无法遍历：不当作已推（失败即关），先 fetch。
- ``cp -c`` 跨卷静默退化成整份拷贝；按 ``du`` 算节省（上一节）。
- 被 ``git worktree remove`` 拆掉的 detached 树，HEAD 若不在任何具名 ref 上就再也找不回——
  本脚本先钉 ``refs/archive`` 并推 Gitea 再拆；``cleanup_gate_trees.sh`` 那边改为直接跳过。

退出码：0 完成；1 apply 中途失败并停下；3 apply 完成但有树在复核时被跳过；4 安全采样不可用
（lsof / ls-remote / worktree list 失败），一棵没动；5 参数或计划文件错误。

用法：
    python3 scripts/worktree_closeout.py --tree ~/fwp-wt-foo --reason "#123 已合入，内容 97% 在 main"
    python3 scripts/worktree_closeout.py --plan plan.json     # [{"path", "reason", "release_lock"}]
    python3 scripts/worktree_closeout.py --apply --plan <输出目录>/dry-<时刻>.json
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import worktree_board as board
from scripts import worktree_safety as safety

EXIT_FAILED, EXIT_SKIPPED, EXIT_UNSAFE, EXIT_USAGE = 1, 3, 4, 5
SALVAGE_MAX_BYTES = 5 * 1024 * 1024
FREE_SPACE_MARGIN = 1 << 30
LIST_LIMIT = 40  # 收据里的路径清单截断到这么多条；计数始终是全量

# 运行噪声：封存提交不带，仍在补丁 / 残留包里。
NOISE_PREFIXES = (
    ".code-review-graph/",
    "intelligence/users/default/",
    "intelligence/webapp/test-results/",
    "intelligence/webapp/playwright-report/",
    "intelligence/api/static/",
    ".claude/settings.local.json",
    # skills/ 的软链视图；拷贝出来的树里软链被实体化成目录，那不是内容。
    ".claude/skills/",
    "skills/daily-full-review/state/runlog.md",
)
# 禁提文件：pre-commit block-forbidden-files 的正则与 AGENTS.md 清单（sqlite*、pptx、凭证配置、
# AppleDouble）的并集。缓存目录另由 safety.is_cache_path 判。
FORBIDDEN_NAMES = frozenset({"mcp_config.json", "feishu_config.json", ".DS_Store"})
FORBIDDEN_SUFFIXES = (".pem", ".key", ".pdf", ".zip", ".pptx", ".duckdb", ".db", ".pyc", ".log")
FORBIDDEN_DIRS = frozenset({"venv", "env", "__MACOSX", ".ipynb_checkpoints", ".cache"})
_SQLITE = re.compile(r"\.sqlite\d*$", re.IGNORECASE)
# 这些不进 tar，走 clonefile。
_DATABASE = re.compile(r"\.(duckdb|db|sqlite\d*)([.-](wal|shm|journal))?$", re.IGNORECASE)


class CloseoutError(RuntimeError):
    """必须停掉整轮的失败；已写出的归档留在盘上并记进收据。"""


# ---------------------------------------------------------------- git 与小工具


def _run_git(args, *, cwd, timeout, env=None, stdin=None, raw=False):
    """``(code, stdout, stderr)``，永不抛异常。stdout 按 surrogateescape 解码，路径可原样回写。"""

    data = stdin.encode("utf-8", "surrogateescape") if isinstance(stdin, str) else stdin
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            input=data,
            capture_output=True,
            timeout=timeout,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", **(env or {})},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, (b"" if raw else ""), f"{type(exc).__name__}: {exc}"
    out = proc.stdout if raw else proc.stdout.decode("utf-8", "surrogateescape")
    return proc.returncode, out, proc.stderr.decode("utf-8", "replace").strip()


def _git_ok(args, *, cwd, timeout, env=None, stdin=None) -> str:
    code, out, err = _run_git(args, cwd=cwd, timeout=timeout, env=env, stdin=stdin)
    if code:
        raise CloseoutError(f"git {' '.join(str(a) for a in args[:3])} 失败: {err[:300]}")
    return out.rstrip("\n")


def _inside(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def _display(path: str) -> str:
    return board.display_path(path)


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 22), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clip(items: list) -> list:
    return list(items[:LIST_LIMIT])


def slug_for(path: str, home: str) -> str:
    """09-28 的钉名规则：相对家目录、去掉 ``.finance-runtime/``、``/`` 换 ``--``，再按 ref 名规则清洗。"""

    real = os.path.abspath(path)
    rel = os.path.relpath(real, home) if _inside(real, os.path.abspath(home)) else real.lstrip("/")
    rel = rel.removeprefix(".finance-runtime/")
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", rel.replace("/", "--"))
    text = re.sub(r"\.{2,}", ".", text).strip(".-")
    if text.endswith(".lock"):
        text += "-"
    return text or "tree"


def is_noise(rel: str) -> bool:
    return rel.startswith(NOISE_PREFIXES)


def is_database(rel: str) -> bool:
    return bool(_DATABASE.search(rel))


def is_forbidden(rel: str) -> bool:
    parts = rel.split("/")
    name = parts[-1]
    if name.startswith((".env", "._")) or name in FORBIDDEN_NAMES:
        return True
    # 数据库连同 wal / shm / journal 旁车文件一律不进 git（旁车文件两份清单都没写，这里补上）。
    if name.lower().endswith(FORBIDDEN_SUFFIXES) or _SQLITE.search(name) or is_database(rel):
        return True
    return any(part in FORBIDDEN_DIRS for part in parts[:-1]) or safety.is_cache_path(rel)


# ---------------------------------------------------------------- 盘点一棵树


def read_status(root: str, *, timeout: float) -> list[tuple[str, str, str]]:
    """``--ignored=matching``：被忽略的目录整条报 ``dir/``，不像 traditional 那样把
    ``node_modules`` 里十万个文件逐个列出来；目录由 ``expand_entries`` 展开并跳过缓存。"""

    code, raw, err = _run_git(
        ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored=matching"],
        cwd=root,
        timeout=timeout,
    )
    if code:
        raise CloseoutError(f"git status 失败: {err[:200]}")
    try:
        # 原样交给解析器：不 strip（见 safety.status_records）。
        return safety.status_records(raw)
    except ValueError as exc:
        raise CloseoutError(f"git status 输出无法解析: {exc}") from exc


def expand_entries(root: str, entries: list[str]) -> tuple[list[str], list[str]]:
    """porcelain 条目 → 普通文件与符号链接（相对路径，缓存已剔除）；socket / FIFO 等另列。"""

    files: set[str] = set()
    special: set[str] = set()
    errors: list[OSError] = []

    def take(rel: str) -> None:
        mode = os.lstat(os.path.join(root, rel)).st_mode
        (files if stat.S_ISREG(mode) or stat.S_ISLNK(mode) else special).add(rel)

    for entry in entries:
        rel = entry.rstrip("/")
        if not rel or safety.is_cache_path(rel):
            continue
        full = os.path.join(root, rel)
        if os.path.isdir(full) and not os.path.islink(full):
            for current, dirs, names in os.walk(full, onerror=errors.append):
                keep = []
                for name in dirs:
                    sub = os.path.relpath(os.path.join(current, name), root)
                    if safety.is_cache_path(sub):
                        continue
                    if os.path.islink(os.path.join(root, sub)):
                        files.add(sub)  # 指向目录的链接：存链接本身，不跟进去
                    else:
                        keep.append(name)
                dirs[:] = keep
                for name in names:
                    sub = os.path.relpath(os.path.join(current, name), root)
                    if not safety.is_cache_path(sub):
                        take(sub)
        else:
            take(rel)
    if errors:
        raise CloseoutError(f"残留目录读不全: {errors[0]}")
    return sorted(files), sorted(special)


def inventory(root: str, records: list[tuple[str, str, str]]) -> dict:
    tracked, untracked, ignored = [], [], []
    for code, path, source in records:
        if code == "??":
            untracked.append(path)
        elif code == "!!":
            ignored.append(path)
        else:
            tracked.append((code, path, source))
    residue, special = expand_entries(root, untracked + ignored)
    databases = [rel for rel in residue if is_database(rel) and os.path.isfile(os.path.join(root, rel))
                 and not os.path.islink(os.path.join(root, rel))]
    skip = set(databases)
    archive = [rel for rel in residue if rel not in skip]

    candidates: list[str] = []
    for _code, path, source in tracked:
        candidates += [path] + ([source] if source else [])
    nested = [entry for entry in untracked if entry.endswith("/")]
    candidates += [entry for entry in untracked if not entry.endswith("/")]
    salvage: list[str] = []
    excluded: dict[str, list[str]] = {"forbidden": [], "noise": [], "large": []}
    for rel in dict.fromkeys(candidates):
        full = os.path.join(root, rel)
        if is_noise(rel):
            excluded["noise"].append(rel)
        elif is_forbidden(rel):
            excluded["forbidden"].append(rel)
        elif os.path.isfile(full) and not os.path.islink(full) and os.lstat(full).st_size > SALVAGE_MAX_BYTES:
            excluded["large"].append(rel)
        else:
            salvage.append(rel)
    return {
        "tracked": tracked,
        "archive": archive,
        "archive_bytes": sum(os.lstat(os.path.join(root, rel)).st_size for rel in archive),
        "databases": databases,
        "database_bytes": sum(os.lstat(os.path.join(root, rel)).st_size for rel in databases),
        "special": special,
        "salvage": salvage,
        "untracked": {entry for entry in untracked if not entry.endswith("/")},
        "excluded": excluded,
        "nested_repos": nested,
    }


def _inventory_summary(inv: dict) -> dict:
    return {
        "tracked_n": len(inv["tracked"]),
        "tracked": _clip([f"{code} {path}" for code, path, _ in inv["tracked"]]),
        "residue_n": len(inv["archive"]),
        "residue_bytes": inv["archive_bytes"],
        "residue": _clip(inv["archive"]),
        "databases": inv["databases"],
        # 逻辑大小；APFS 克隆共享块，不是可回收空间（见模块文档）。
        "database_logical_bytes": inv["database_bytes"],
        "special_skipped": inv["special"],
        "salvage_n": len(inv["salvage"]),
        "salvage": _clip(inv["salvage"]),
        "salvage_excluded": {key: _clip(value) for key, value in inv["excluded"].items()},
        "nested_repos": inv["nested_repos"],
    }


# ---------------------------------------------------------------- 采样（dry-run）


def open_repo(repo_arg: str | None, *, timeout: float, base_arg: str | None) -> dict:
    cwd = os.path.abspath(os.path.expanduser(repo_arg or os.getcwd()))
    code, top, _ = _run_git(["rev-parse", "--show-toplevel"], cwd=cwd, timeout=timeout)
    if code or not top.strip():
        raise CloseoutError(f"不是 git 仓: {cwd}")
    top = top.strip()
    common = _git_ok(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=top, timeout=timeout)
    code, porcelain, err = _run_git(["worktree", "list", "--porcelain"], cwd=top, timeout=timeout)
    if code or not porcelain:
        raise CloseoutError(f"git worktree list 失败: {err[:200]}")
    base = base_arg or board.resolve_base(top, timeout)
    base_sha = _git_ok(["rev-parse", "--verify", f"{base}^{{commit}}"], cwd=top, timeout=timeout) if base else ""
    specs = {os.path.realpath(spec["path"]): spec for spec in board.parse_worktree_porcelain(porcelain)}
    return {
        "repo": top,
        "main_checkout": os.path.realpath(str(Path(common).resolve().parent)),
        "specs": specs,
        "base": base,
        "base_sha": base_sha,
    }


def _ref_value(repo: str, ref: str, *, timeout: float) -> str:
    code, out, _ = _run_git(["rev-parse", "--verify", "-q", ref], cwd=repo, timeout=timeout)
    return out.strip() if code == 0 else ""


def sample_tree(item: dict, *, ctx: dict, context: dict, tips: dict, date: str, home: str,
                idle_hours: float, timeout: float, seen_slugs: dict) -> dict:
    path = item["path"]
    real = os.path.realpath(path)
    rec: dict = {"path": path, "reason": item["reason"], "release_lock": item["release_lock"], "blockers": []}
    block = rec["blockers"].append
    if not item["reason"]:
        block("没写理由（--reason 或 plan 的 reason）：收据要能回答「为什么拆这棵」")
    spec = ctx["specs"].get(real)
    if spec is None:
        block("不是本仓登记的 worktree")
        return rec
    rec["branch"] = spec.get("branch") or "?"
    rec["locked"] = spec.get("locked", "")
    if real == ctx["main_checkout"]:
        block("主工作树（生产数据根），永不拆")
        return rec
    here = os.path.realpath(os.getcwd())
    if _inside(here, real) or _inside(os.path.realpath(__file__), real):
        block("本脚本 / 本进程就在这棵树里")
    if "/.claude/worktrees/" in real:
        block("Claude Code 会话树：到那个会话里归档，app 会清树；别从外面拆")
    if spec.get("prunable"):
        block(f"worktree prunable: {spec['prunable']}")
        return rec
    if rec["locked"] and not item["release_lock"]:
        block(f"上锁: {rec['locked']}（要拆须在 plan 写 release_lock，并在 reason 里写锁理由为何已失效）")

    slug = slug_for(path, home)
    if _run_git(["check-ref-format", f"refs/archive/wt-{date}/{slug}"], cwd=ctx["repo"], timeout=timeout)[0]:
        slug = "tree-" + hashlib.sha1(real.encode("utf-8", "surrogateescape")).hexdigest()[:12]
    if slug in seen_slugs:
        block(f"slug {slug} 与 {seen_slugs[slug]} 撞名")
    seen_slugs.setdefault(slug, path)
    rec["slug"] = slug

    rec["sampled_at"] = sampled_at = time.time()
    code, head, err = _run_git(["rev-parse", "--verify", "HEAD"], cwd=path, timeout=timeout)
    head = head.strip()
    if code or not head:
        block(f"读不到 HEAD: {err[:120]}")
        return rec
    rec["head"] = head
    try:
        rec["inventory"] = _inventory_summary(inventory(path, read_status(path, timeout=timeout)))
    except (CloseoutError, OSError) as exc:
        block(f"盘点失败: {exc}")
    try:
        newest, where = safety.newest_activity(path)
        rec["newest_entry"], rec["idle_hours"] = where, round((sampled_at - newest) / 3600, 2)
        if sampled_at - newest < idle_hours * 3600:
            block(f"{rec['idle_hours']} 小时前还有改动（{where}），不到 --idle-hours {idle_hours:g}")
    except OSError as exc:
        block(f"改动时间读不全: {exc}")

    for blocker in safety.context_blockers(path, context):
        block(blocker)
    for error in context["errors"]:
        block(f"安全采样不可用: {error}")
    if tips["error"]:
        block(f"Gitea 可达性未知: {tips['error']}")
    else:
        unpushed = safety.unpushed_commits(head, tips["shas"], cwd=ctx["repo"], timeout=timeout)
        rec["unpushed_commits"] = unpushed
        if unpushed:
            hint = f"（本机有 {tips['unknown']} 个远端 sha 没 fetch 过，先 git fetch）" if tips["unknown"] else ""
            block(f"HEAD 有 {unpushed if unpushed > 0 else '未知数量'} 个提交不在远端{hint}；先推分支或钉 ref")

    if ctx["base_sha"]:
        plus, minus, in_base = board.cherry_counts(head, ctx["base_sha"], cwd=ctx["repo"], timeout=timeout)
        rec["cherry"] = {"plus": plus, "minus": minus, "in_base": in_base}
        if plus > 0:
            landed = board.landed_ratio(head, ctx["base_sha"], cwd=ctx["repo"], timeout=timeout)
            rec["landed"] = {"added": landed.added, "found": landed.found, "pct": landed.pct,
                             "files": landed.files, "error": landed.error}

    pin = f"refs/archive/wt-{date}/{slug}"
    salvage_ref = f"refs/heads/salvage/{slug}-{date}"
    rec["planned"] = {"pin": pin, "salvage_ref": salvage_ref if rec.get("inventory", {}).get("salvage_n") else ""}
    existing = _ref_value(ctx["repo"], pin, timeout=timeout)
    if existing and existing != head:
        block(f"{pin} 已存在且指向 {existing[:12]}，不是这棵的 HEAD")
    if rec["planned"]["salvage_ref"] and _ref_value(ctx["repo"], salvage_ref, timeout=timeout):
        block(f"{salvage_ref} 已存在")
    return rec


# ---------------------------------------------------------------- 归档（apply）


def write_patch(root: str, head: str, dest: Path, *, timeout: float) -> dict:
    code, patch, err = _run_git(
        ["diff", "--binary", "--no-color", "--no-ext-diff", "--no-textconv", "--no-relative",
         "--src-prefix=a/", "--dst-prefix=b/", "HEAD"],
        cwd=root, timeout=timeout, raw=True,
    )
    if code:
        raise CloseoutError(f"git diff --binary 失败: {err[:200]}")
    if not patch:
        return {}
    dest.write_bytes(patch)
    with tempfile.TemporaryDirectory(prefix="wt-closeout-check-") as tmp:
        env = {"GIT_INDEX_FILE": os.path.join(tmp, "index")}
        _git_ok(["read-tree", head], cwd=root, timeout=timeout, env=env)
        code, _, err = _run_git(["apply", "--cached", "--check", "--whitespace=nowarn", str(dest)],
                                cwd=root, timeout=timeout, env=env)
    if code:
        raise CloseoutError(f"补丁回验失败（apply --cached --check）: {err[:200]}")
    return {"patch": str(dest), "bytes": len(patch), "sha256": hashlib.sha256(patch).hexdigest()}


def write_residue(root: str, files: list[str], dest: Path) -> dict:
    sizes = {}
    with tarfile.open(dest, "w:gz", compresslevel=6) as archive:
        for rel in files:
            full = os.path.join(root, rel)
            info = os.lstat(full)
            if stat.S_ISREG(info.st_mode):
                sizes[rel] = info.st_size
            archive.add(full, arcname=rel, recursive=False)
    with tarfile.open(dest, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers() if not member.isdir()}
    if set(members) != set(files):
        missing = sorted(set(files) - set(members))[:5]
        extra = sorted(set(members) - set(files))[:5]
        raise CloseoutError(f"残留包文件名单不符：缺 {missing} 多 {extra}")
    for rel, size in sizes.items():
        if members[rel].isfile() and members[rel].size != size:
            raise CloseoutError(f"残留包里 {rel} 大小不符 {members[rel].size} != {size}")
    return {"tar": str(dest), "files": len(files), "bytes": dest.stat().st_size, "sha256": _sha256(str(dest))}


def _clonefile(src: str, dst: str) -> None:
    """clonefile(2)：同卷 APFS 上零新增数据块；做不到就报错，绝不退化成整份拷贝。"""

    libc = ctypes.CDLL(None, use_errno=True)
    clone = getattr(libc, "clonefile", None)
    if clone is None:
        raise CloseoutError("clonefile(2) 不可用（非 macOS）；数据库残留不做整份拷贝，手工处理")
    clone.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
    clone.restype = ctypes.c_int
    if clone(os.fsencode(src), os.fsencode(dst), 1) != 0:  # 1 = CLONE_NOFOLLOW
        raise CloseoutError(f"clonefile 失败（{os.strerror(ctypes.get_errno())}）: {src}")


def clone_databases(root: str, files: list[str], dest: Path) -> dict:
    lines = []
    for rel in files:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        _clonefile(os.path.join(root, rel), str(target))
        source_hash, clone_hash = _sha256(os.path.join(root, rel)), _sha256(str(target))
        if source_hash != clone_hash:
            raise CloseoutError(f"克隆回读 sha256 不符: {rel}")
        lines.append(f"{source_hash}  {rel}\n")
    (dest / "MANIFEST.sha256").write_text("".join(lines), encoding="utf-8")
    return {"clones": str(dest), "files": len(files), "manifest": str(dest / "MANIFEST.sha256")}


def _nul_set(text: str) -> set[str]:
    return {item for item in text.split("\0") if item}


def salvage_commit(root: str, head: str, paths: list[str], untracked: set[str], message: str,
                   *, timeout: float) -> str:
    """在临时索引上把 ``paths`` 的工作区状态提交到 ``head`` 之上；返回提交号，无差异返回空串。

    树自己的索引与工作区一个字节不动（``GIT_INDEX_FILE`` 指向临时文件）。路径清单走 stdin，
    按字面匹配（``GIT_LITERAL_PATHSPECS``），不受 ARG_MAX 与文件名里 ``*[`` 的影响。

    回验：封存提交相对 HEAD 改了哪些路径，必须恰好等于「工作区相对 HEAD 有差异的被跟踪路径 +
    未跟踪文件」落在 ``paths`` 里的那部分——前者取自 ``git diff --name-only HEAD``，git 自己
    按内容（含过滤器）比的，与我们的 add 互相独立。
    """

    env = {"GIT_LITERAL_PATHSPECS": "1"}
    # 只读：比工作区与 HEAD（借树自己的索引认路径，GIT_OPTIONAL_LOCKS=0 不回写）。
    changed = _nul_set(_git_ok(["diff", "--name-only", "-z", "--no-renames", "--no-relative", "HEAD"],
                               cwd=root, timeout=timeout))
    # 暂存区改了、工作区又改回 HEAD 的，和加进索引又删掉的，工作区相对 HEAD 都没有差异：没东西可封。
    live = [p for p in paths if p in changed or (p in untracked and os.path.lexists(os.path.join(root, p)))]
    if not live:
        return ""
    with tempfile.TemporaryDirectory(prefix="wt-closeout-idx-") as tmp:
        index_env = {**env, "GIT_INDEX_FILE": os.path.join(tmp, "index")}
        _git_ok(["read-tree", head], cwd=root, timeout=timeout, env=index_env)
        _git_ok(["add", "--pathspec-from-file=-", "--pathspec-file-nul"], cwd=root, timeout=timeout,
                env=index_env, stdin="\0".join(live) + "\0")
        tree = _git_ok(["write-tree"], cwd=root, timeout=timeout, env=index_env)
    sha = _git_ok(["commit-tree", tree, "-p", head, "-F", "-"], cwd=root, timeout=timeout, stdin=message)
    committed = _nul_set(_git_ok(["diff-tree", "-r", "--no-renames", "--name-only", "-z", head, sha],
                                 cwd=root, timeout=timeout))
    if committed != set(live):
        raise CloseoutError(
            f"封存回验失败：少了 {sorted(set(live) - committed)[:5]}，多了 {sorted(committed - set(live))[:5]}"
        )
    return sha


def _ensure_ref(repo: str, ref: str, sha: str, *, timeout: float) -> None:
    current = _ref_value(repo, ref, timeout=timeout)
    if current == sha:
        return
    if current:
        raise CloseoutError(f"{ref} 已存在且指向 {current[:12]}")
    _git_ok(["update-ref", ref, sha, ""], cwd=repo, timeout=timeout)  # 空旧值 = 只许新建


def recheck(rec: dict, *, ctx: dict, cwd_context: dict, launchers: dict, tips: dict,
            timeout: float) -> list[str]:
    """拆之前的复核；返回问题清单，空 = 可以动。"""

    path = rec["path"]
    real = os.path.realpath(path)
    spec = ctx["specs"].get(real)
    if spec is None or not os.path.isdir(path):
        return ["已不是本仓登记的 worktree 或目录不在（别的会话拆了？）"]
    problems = []
    code, head, _ = _run_git(["rev-parse", "--verify", "HEAD"], cwd=path, timeout=timeout)
    if code or head.strip() != rec["head"]:
        problems.append(f"HEAD 变了 {rec['head'][:12]} → {head.strip()[:12] or '?'}")
    lock = spec.get("locked", "")
    if lock and lock != rec.get("locked", ""):
        # release_lock 只授权采样时看到的那把锁；新锁的理由没人审过。
        problems.append(f"锁在采样后变了: {lock}")
    elif lock and not rec["release_lock"]:
        problems.append(f"上锁: {lock}")
    problems += safety.context_blockers(path, cwd_context) + cwd_context["errors"]
    problems += safety.context_blockers(path, launchers) + launchers["errors"]
    try:
        newest, where = safety.newest_activity(path, since=rec["sampled_at"])
        if newest > rec["sampled_at"]:
            problems.append(f"采样后有改动: {where}" + ("（目录里有文件增删）" if where.endswith("/") else ""))
    except OSError as exc:
        problems.append(f"改动时间读不全: {exc}")
    unpushed = safety.unpushed_commits(rec["head"], tips["shas"], cwd=ctx["repo"], timeout=timeout)
    if unpushed:
        problems.append(f"HEAD 有 {unpushed if unpushed > 0 else '未知数量'} 个提交不在远端")
    return list(dict.fromkeys(problems))


def close_tree(rec: dict, result: dict, *, ctx: dict, args, out_dir: Path, date: str, tips: dict) -> None:
    """归档 → 推送 → 最后一道闸 → 拆，边做边往 ``result`` 里记（失败时收据里有做到哪一步）。

    须停整轮时抛 CloseoutError。
    """

    path, head, slug, timeout = rec["path"], rec["head"], rec["slug"], args.timeout
    dest = out_dir / slug
    if dest.exists():
        raise CloseoutError(f"归档目录已存在：{dest}（换 --out-dir，或先核对上一轮留下的东西）")
    dest.mkdir(parents=True)
    result["archive_dir"] = str(dest)

    pin = f"refs/archive/wt-{date}/{slug}"
    _ensure_ref(ctx["repo"], pin, head, timeout=timeout)
    result["pin"] = pin

    inv = inventory(path, read_status(path, timeout=timeout))
    result["inventory"] = _inventory_summary(inv)
    if inv["tracked"]:
        result["tracked_patch"] = write_patch(path, head, dest / "tracked.patch", timeout=timeout)
    if inv["archive"]:
        free = shutil.disk_usage(dest).free
        if free < inv["archive_bytes"] + FREE_SPACE_MARGIN:
            raise CloseoutError(f"卷上可用 {free} 字节，不够打 {inv['archive_bytes']} 字节的残留包（留 1 GiB 余量）")
        result["residue"] = write_residue(path, inv["archive"], dest / "residue.tar.gz")
    if inv["databases"]:
        result["database_clones"] = clone_databases(path, inv["databases"], dest / "clones")

    refs = [pin]
    if inv["salvage"]:
        message = (
            f"wip(salvage): {slug} 未提交内容封存（{date} worktree 收口）\n\n"
            f"原树 {path}；基于 {head}。拆树前原样封存，未经审阅、未过门禁。\n"
            f"禁提 / 运行噪声 / 缓存 / 大文件不在这里，在 {dest} 的补丁与残留包里。\n\n"
            f"理由：{rec['reason']}\n"
        )
        sha = salvage_commit(path, head, inv["salvage"], inv["untracked"], message, timeout=timeout)
        if sha:
            salvage_ref = f"refs/heads/salvage/{slug}-{date}"
            _ensure_ref(ctx["repo"], salvage_ref, sha, timeout=timeout)
            result["salvage"] = {"ref": salvage_ref, "sha": sha}
            refs.append(salvage_ref)
    code, _, err = _run_git(["push", args.remote, *[f"{ref}:{ref}" for ref in refs]],
                            cwd=ctx["repo"], timeout=max(timeout, 120))
    if code:
        raise CloseoutError(f"推送 {args.remote} 失败（树未拆）: {err[:300]}")
    result["pushed"] = refs
    tips["shas"] = tips["shas"] + [head] + ([result["salvage"]["sha"]] if "salvage" in result else [])

    # 最后一道闸：归档花了时间，这期间有人进树就不拆（归档照留）。启动器引用刚核过，不再采。
    problems = recheck(rec, ctx=ctx, cwd_context=safety.sample_processes(timeout=args.lsof_timeout,
                                                                        descriptors="cwd"),
                       launchers={"references": [], "errors": []}, tips=tips, timeout=timeout)
    if problems:
        result.update(status="skipped", skipped=problems, note="归档已做、树未拆")
        return
    lock = ctx["specs"][os.path.realpath(path)].get("locked", "")
    if lock:
        _git_ok(["worktree", "unlock", "--", path], cwd=ctx["repo"], timeout=timeout)
        result["unlocked"] = lock
    code, _, err = _run_git(["worktree", "remove", "--force", "--", path], cwd=ctx["repo"],
                            timeout=max(timeout, 600))
    if code or os.path.lexists(path):
        raise CloseoutError(f"git worktree remove 失败（归档已做）: {err[:300]}")
    result["status"] = "removed"


# ---------------------------------------------------------------- 入口


def _load_items(args) -> tuple[dict, list[dict]]:
    meta: dict = {}
    raw_items: list = []
    if args.plan:
        data = json.loads(Path(args.plan).expanduser().read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("trees"), list):
            meta, raw_items = data, data["trees"]
        elif isinstance(data, list):
            raw_items = data
        else:
            raise ValueError("plan 必须是列表，或带 trees 列表的对象（dry-run 收据）")
    released = {os.path.abspath(os.path.expanduser(p)) for p in args.release_lock}
    raw_items += [{"path": p, "reason": args.reason or ""} for p in args.tree]
    items = []
    for raw in raw_items:
        if isinstance(raw, str):
            raw = {"path": raw}
        if not isinstance(raw, dict) or not raw.get("path"):
            raise ValueError(f"plan 条目缺 path: {raw!r}")
        item = dict(raw)
        item["path"] = os.path.abspath(os.path.expanduser(str(raw["path"])))
        item["reason"] = str(raw.get("reason") or "").strip()
        item["release_lock"] = bool(raw.get("release_lock")) or item["path"] in released
        items.append(item)
    return meta, items


def _free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free


def _write_receipt(out_dir: Path, mode: str, payload: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    target = out_dir / f"{mode}-{stamp}.json"
    n = 1
    while target.exists():
        n += 1
        target = out_dir / f"{mode}-{stamp}-{n}.json"
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    target.write_bytes(text.encode("utf-8", "backslashreplace"))
    return target


def _tool_revision() -> str:
    code, out, _ = _run_git(["rev-parse", "HEAD"], cwd=str(Path(__file__).resolve().parent), timeout=10)
    return out.strip() if code == 0 else ""


def _print_tree(tag: str, rec: dict) -> None:
    inv = rec.get("inventory") or {}
    bits = [f"{tag:<5} {_display(rec['path'])}  [{rec.get('branch', '?')}]"]
    if inv:
        bits.append(
            f"tracked {inv['tracked_n']} · residue {inv['residue_n']} 文件 {inv['residue_bytes'] / 1e6:.1f} MB"
            f" · db {len(inv['databases'])} · salvage {inv['salvage_n']}"
        )
    landed = rec.get("landed")
    if landed:
        bits.append(f"landed {board.format_landed(board.Landed(**landed))}")
    print("  ".join(bits))
    print(f"        理由: {rec.get('reason') or '-'}")
    for blocker in rec.get("blockers", []) + rec.get("skipped", []):
        print(f"        · {blocker}")


def run_dry(args, ctx: dict, items: list[dict], out_dir: Path, date: str) -> int:
    home = str(Path.home())
    context = safety.sample_context(timeout=args.lsof_timeout)
    tips = safety.remote_tips(ctx["repo"], args.remote, timeout=args.timeout)
    seen: dict = {}
    trees = []
    for item in items:
        if any(item["path"] == other["path"] for other in trees):
            trees.append({**item, "blockers": ["重复点名"]})
            continue
        trees.append(sample_tree(item, ctx=ctx, context=context, tips=tips, date=date, home=home,
                                 idle_hours=args.idle_hours, timeout=args.timeout, seen_slugs=seen))
    eligible = [rec for rec in trees if not rec["blockers"]]
    payload = {
        "mode": "dry-run", "tool": "scripts/worktree_closeout.py", "tool_revision": _tool_revision(),
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "date": date,
        "repo": ctx["main_checkout"], "remote": args.remote, "remote_tips": len(tips["shas"]),
        "remote_unknown": tips["unknown"], "remote_error": tips["error"],
        "base": ctx["base"], "base_sha": ctx["base_sha"], "idle_hours": args.idle_hours,
        "context_errors": context["errors"],
        "space_note": "不按 du 估节省：本仓 DuckDB 是 APFS 克隆，du 高估可回收空间；apply 收据记 statvfs 实测差",
        "summary": {"planned": len(trees), "eligible": len(eligible), "blocked": len(trees) - len(eligible)},
        "trees": trees,
    }
    receipt = _write_receipt(out_dir, "dry", payload)
    print(f"收口 dry-run  仓 {_display(ctx['main_checkout'])}  基线 {ctx['base']}={ctx['base_sha'][:12]}"
          f"  远端 {args.remote}（可遍历 sha {len(tips['shas'])}，未 fetch {tips['unknown']}）  日期 {date}")
    for rec in trees:
        _print_tree("CLEAR" if not rec["blockers"] else "BLOCK", rec)
    print(f"合计 点名 {len(trees)} · 技术上无阻塞 {len(eligible)} · 有阻塞 {len(trees) - len(eligible)}")
    print("「无阻塞」只说明拆了不丢东西、没人在用，不说明该拆：回滚锚、保留约定、在途线本脚本认不出，"
          "去留以每棵的理由为准（例：8792 刚切走的上一版常是新的回滚锚，先查部署账本）。")
    print(f"收据 {receipt}")
    if eligible:
        print(f"下一步（逐棵核对理由之后）：python3 scripts/worktree_closeout.py --apply --plan {receipt}")
    print("不按 du 估节省（APFS 克隆，见 --help）；apply 收据里记卷可用空间的实测前后差。")
    return EXIT_UNSAFE if context["errors"] or tips["error"] else 0


def run_apply(args, ctx: dict, meta: dict, out_dir: Path, date: str) -> int:
    planned = [rec for rec in meta["trees"] if not rec.get("blockers")]
    for rec in planned:
        if not all(key in rec for key in ("head", "sampled_at", "slug", "path")):
            print(f"plan 条目缺采样字段（不是 dry-run 收据？）: {rec.get('path')}", file=sys.stderr)
            return EXIT_USAGE
    context = safety.sample_context(timeout=args.lsof_timeout)
    tips = safety.remote_tips(ctx["repo"], args.remote, timeout=args.timeout)
    if context["errors"] or tips["error"]:
        print("安全采样不可用，一棵没动: " + "; ".join(context["errors"] + [tips["error"]]), file=sys.stderr)
        return EXIT_UNSAFE
    free_before = _free_bytes(out_dir)
    results: list[dict] = []
    stopped = ""
    print(f"收口 apply  计划 {args.plan}  可收口 {len(planned)} / 点名 {len(meta['trees'])}  日期 {date}")
    for rec in planned:
        result: dict = {"path": rec["path"], "slug": rec["slug"], "head": rec["head"],
                        "branch": rec.get("branch"), "reason": rec["reason"], "status": "failed"}
        problems = list(dict.fromkeys(safety.context_blockers(rec["path"], context) + recheck(
            rec, ctx=ctx, cwd_context=safety.sample_processes(timeout=args.lsof_timeout, descriptors="cwd"),
            launchers=safety.sample_launchers(timeout=args.lsof_timeout), tips=tips, timeout=args.timeout)))
        if problems:
            result.update(status="skipped", skipped=problems)
            results.append(result)
            _print_tree("SKIP", result)
            continue
        try:
            close_tree(rec, result, ctx=ctx, args=args, out_dir=out_dir, date=date, tips=tips)
        except (CloseoutError, OSError, tarfile.TarError) as exc:
            result.update(status="failed", error=str(exc))
            stopped = rec["path"]
        results.append(result)
        tag = {"removed": "RM", "skipped": "SKIP"}.get(result["status"], "FAIL")
        _print_tree(tag, {**rec, **result, "blockers": [result["error"]] if "error" in result else []})
        if stopped:
            print("        整轮停止：这棵之后的树一棵没动。", file=sys.stderr)
            break
    free_after = _free_bytes(out_dir)
    counts = {status: sum(1 for r in results if r["status"] == status) for status in ("removed", "skipped", "failed")}
    payload = {
        "mode": "apply", "tool": "scripts/worktree_closeout.py", "tool_revision": _tool_revision(),
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "date": date,
        "plan": str(Path(args.plan).expanduser().resolve()), "repo": ctx["main_checkout"],
        "remote": args.remote, "base": ctx["base"], "base_sha": ctx["base_sha"],
        "free_bytes_before": free_before, "free_bytes_after": free_after,
        "free_bytes_delta": free_after - free_before,
        "space_note": "statvfs 实测；APFS 克隆共享块，拆树只释放独占块，不要拿 du 与它对账",
        "stopped_at": stopped,
        "summary": {"planned": len(meta["trees"]), "eligible": len(planned), **counts,
                    "not_reached": len(planned) - len(results)},
        "trees": results,
    }
    receipt = _write_receipt(out_dir, "apply", payload)
    print(f"合计 拆 {counts['removed']} · 跳过 {counts['skipped']} · 失败 {counts['failed']}"
          f" · 未轮到 {len(planned) - len(results)}")
    print(f"卷可用空间 {free_before / 2**30:.1f} → {free_after / 2**30:.1f} GiB"
          f"（{(free_after - free_before) / 2**30:+.2f} GiB，statvfs 实测）")
    print(f"收据 {receipt}")
    if stopped:
        return EXIT_FAILED
    return EXIT_SKIPPED if counts["skipped"] else 0


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # 参数错与 cleanup_gate_trees.sh 一样退 5（argparse 默认 2）
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(
        description=__doc__.split("\n", 1)[0],
        epilog=__doc__.split("\n", 1)[1],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--tree", action="append", default=[], help="点名一棵树（可多次）")
    parser.add_argument("--reason", default="", help="--tree 的理由（写进收据与封存提交）")
    parser.add_argument("--plan", help="dry-run：计划 JSON；apply：dry-run 收据")
    parser.add_argument("--release-lock", action="append", default=[],
                        help="允许 unlock 这棵上锁的树（可多次；plan 里用 release_lock）")
    parser.add_argument("--apply", action="store_true", help="真动手（只接受 dry-run 收据）")
    parser.add_argument("--repo", help="仓（默认当前目录所在仓）")
    parser.add_argument("--base", help="基线引用（默认 origin/main，缺失时用本地 main）")
    parser.add_argument("--remote", default="gitea", help="备份远端（默认 gitea）")
    parser.add_argument("--out-dir", help="收据与归档目录（默认 ~/.finance-runtime/reviews/worktree-closeout-<日期>；"
                                          "apply 默认用 dry-run 收据所在目录）")
    parser.add_argument("--idle-hours", type=float, default=2.0,
                        help="采样前这么多小时内有改动就算阻塞（默认 2；0 = 不看）")
    parser.add_argument("--date", default=dt.date.today().strftime("%Y%m%d"), help="钉与封存分支的日期段")
    parser.add_argument("--timeout", type=float, default=60.0, help="单次 git 超时秒数")
    parser.add_argument("--lsof-timeout", type=float, default=120.0, help="lsof 超时秒数")
    args = parser.parse_args(argv)

    if not re.fullmatch(r"\d{8}", args.date):
        parser.error("--date 必须是 YYYYMMDD")
    if args.apply and (args.tree or args.release_lock or args.reason or not args.plan):
        parser.error("--apply 只接受 dry-run 收据（点名、理由、解锁都以收据为准）："
                     "先不带 --apply 跑一遍，再 --apply --plan <收据>")
    if not args.apply and not (args.tree or args.plan):
        parser.error("没点名任何树：--tree <路径> 或 --plan <计划.json>")
    try:
        meta, items = _load_items(args)
    except (OSError, ValueError) as exc:
        print(f"plan 读不了: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if args.apply and meta.get("mode") != "dry-run":
        print("--apply 的 --plan 必须是本脚本写的 dry-run 收据（mode=dry-run）", file=sys.stderr)
        return EXIT_USAGE
    try:
        ctx = open_repo(args.repo, timeout=args.timeout, base_arg=args.base)
    except CloseoutError as exc:
        print(f"仓状态读不了，一棵没动: {exc}", file=sys.stderr)
        return EXIT_UNSAFE
    if args.apply and os.path.realpath(str(meta.get("repo") or "")) != ctx["main_checkout"]:
        print(f"收据采样的仓 {meta.get('repo')} 不是当前仓 {ctx['main_checkout']}", file=sys.stderr)
        return EXIT_USAGE
    if args.out_dir:
        out_dir = Path(args.out_dir).expanduser().resolve()
    elif args.apply:
        out_dir = Path(args.plan).expanduser().resolve().parent
    else:
        out_dir = Path.home() / ".finance-runtime" / "reviews" / f"worktree-closeout-{args.date}"
    for item in items:
        if _inside(os.path.realpath(str(out_dir)), os.path.realpath(item["path"])):
            print(f"--out-dir 在要拆的树里，拆树会把归档一起删掉: {out_dir}", file=sys.stderr)
            return EXIT_USAGE
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.apply:
        return run_apply(args, ctx, meta, out_dir, args.date)
    return run_dry(args, ctx, items, out_dir, args.date)


if __name__ == "__main__":
    raise SystemExit(main())
