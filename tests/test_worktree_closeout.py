"""worktree_closeout.py：只在 tmp_path 里的一次性仓上跑（真 git、假 lsof、裸仓当 gitea）。"""
from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from scripts import worktree_closeout as closeout

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "worktree_closeout.py"
DATE = "20260928"


def git(cwd: Path, *args: str, env: dict | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
        env={**os.environ, **(env or {})},
    ).stdout.strip()


class Rig:
    def __init__(self, tmp_path: Path):
        self.home = tmp_path / "home"
        self.home.mkdir()
        self.remote = tmp_path / "gitea.git"
        self.out = tmp_path / "out"
        self.fakebin = tmp_path / "bin"
        self.fakebin.mkdir()
        self.lsof_output = tmp_path / "lsof-output"
        self.lsof_output.write_text("")
        # 两种调用（全量 ^mem 与只看 cwd）都吐同一份夹具输出。
        (self.fakebin / "lsof").write_text(f'#!/bin/sh\ncat "{self.lsof_output}"\nexit 0\n')
        (self.fakebin / "lsof").chmod(0o755)
        git(tmp_path, "init", "-q", "--bare", "-b", "main", str(self.remote))
        self.repo = self.home / "main-repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.name", "Closeout test")
        git(self.repo, "config", "user.email", "closeout@example.test")
        git(self.repo, "config", "commit.gpgsign", "false")
        (self.repo / ".gitignore").write_text(
            "evidence/\n__pycache__/\nnode_modules/\n.venv*/\n.code-review-graph/graph.db\n"
        )
        (self.repo / "src").mkdir()
        (self.repo / "src" / "app.py").write_text("def main():\n    return 'base behaviour stays'\n")
        (self.repo / "README.md").write_text("readme\n")
        git(self.repo, "add", "--", ".gitignore", "src/app.py", "README.md")
        git(self.repo, "commit", "-qm", "base")
        git(self.repo, "remote", "add", "gitea", str(self.remote))
        git(self.repo, "push", "-q", "gitea", "main")
        git(self.repo, "fetch", "-q", "gitea")

    def add_tree(self, name: str, *, push: bool = True, detach: bool = False, path: Path | None = None) -> Path:
        path = path or self.home / name
        if detach:
            git(self.repo, "worktree", "add", "-q", "--detach", str(path), "main")
            return path
        branch = f"feat/{name}"
        git(self.repo, "worktree", "add", "-q", "-b", branch, str(path), "main")
        (path / "src" / f"{name.replace('-', '_')}.py").write_text(f"FEATURE = 'feature {name} does useful work'\n")
        git(path, "add", "--", "src")
        git(path, "commit", "-qm", f"feat: {name}")
        if push:
            git(path, "push", "-q", "gitea", f"{branch}:{branch}")
        return path

    def run(self, *args: str, lsof: str = "") -> subprocess.CompletedProcess:
        self.lsof_output.write_text(lsof)
        env = {**os.environ, "HOME": str(self.home), "PATH": f"{self.fakebin}{os.pathsep}{os.environ['PATH']}"}
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(self.repo), "--out-dir", str(self.out),
             "--date", DATE, "--idle-hours", "0", *args],
            env=env, capture_output=True, text=True, timeout=180,
        )

    @staticmethod
    def receipt(result: subprocess.CompletedProcess | str) -> tuple[Path, dict]:
        # 同一秒写两份时第二份带 -2 后缀、按名排在前面：按 stdout 报的路径取，不按文件名排序取。
        text = result if isinstance(result, str) else result.stdout
        [line] = [line for line in text.splitlines() if line.startswith("收据 ")]
        path = Path(line.removeprefix("收据 "))
        return path, json.loads(path.read_text(encoding="utf-8"))

    def refs(self, pattern: str) -> list[str]:
        out = git(self.repo, "for-each-ref", "--format=%(refname)", pattern)
        return out.splitlines() if out else []

    def remote_refs(self) -> set[str]:
        return {line.split()[1] for line in git(self.repo, "ls-remote", "gitea").splitlines()}


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path)


def _dirty_tree(rig: Rig) -> tuple[Path, bytes]:
    tree = rig.add_tree("fwp-wt-dirty")
    # 首条 porcelain 记录是 " M src/app.py"：前导空格是状态列，strip 会把路径读成 "rc/app.py"。
    (tree / "src" / "app.py").write_text("def main():\n    return 'changed in the tree, never committed'\n")
    (tree / "README.md").unlink()
    (tree / "notes").mkdir()
    (tree / "notes" / "plan.md").write_text("untracked plan worth keeping\n")
    (tree / ".env.local").write_text("TOKEN=not-for-git\n")
    (tree / "intelligence" / "users" / "default").mkdir(parents=True)
    (tree / "intelligence" / "users" / "default" / "state.json").write_text("{}\n")
    (tree / "evidence" / "db").mkdir(parents=True)
    (tree / "evidence" / "report.txt").write_text("forensic notes\n")
    database = b"DUCK" + bytes(range(256)) * 64
    (tree / "evidence" / "db" / "snap.duckdb").write_bytes(database)
    (tree / "src" / "__pycache__").mkdir()
    (tree / "src" / "__pycache__" / "app.cpython-312.pyc").write_bytes(b"cache")
    (tree / "node_modules" / "pkg").mkdir(parents=True)
    (tree / "node_modules" / "pkg" / "index.js").write_text("cache\n")
    return tree, database


def test_dry_run_samples_without_touching_anything(rig):
    tree, _ = _dirty_tree(rig)
    head = git(tree, "rev-parse", "HEAD")
    index_before = (Path(git(tree, "rev-parse", "--git-dir")) / "index").read_bytes()

    result = rig.run("--tree", str(tree), "--reason", "test: feature landed elsewhere")

    assert result.returncode == 0, result.stdout + result.stderr
    dry, receipt = rig.receipt(result)
    [rec] = receipt["trees"]
    assert rec["blockers"] == [] and rec["head"] == head and rec["slug"] == "fwp-wt-dirty"
    inv = rec["inventory"]
    assert set(inv["tracked"]) == {" M src/app.py", " D README.md"}
    assert set(inv["residue"]) == {
        "notes/plan.md", ".env.local", "intelligence/users/default/state.json", "evidence/report.txt",
    }
    assert inv["databases"] == ["evidence/db/snap.duckdb"]
    assert set(inv["salvage"]) == {"src/app.py", "README.md", "notes/plan.md"}
    assert inv["salvage_excluded"]["forbidden"] == [".env.local"]
    assert inv["salvage_excluded"]["noise"] == ["intelligence/users/default/state.json"]
    assert rec["planned"] == {"pin": f"refs/archive/wt-{DATE}/fwp-wt-dirty",
                              "salvage_ref": f"refs/heads/salvage/fwp-wt-dirty-{DATE}"}
    # dry-run：树、索引、ref、远端、归档目录都没动。
    assert tree.is_dir() and (Path(git(tree, "rev-parse", "--git-dir")) / "index").read_bytes() == index_before
    assert rig.refs("refs/archive") == [] and rig.refs("refs/heads/salvage") == []
    assert not any(ref.startswith(("refs/archive", "refs/heads/salvage")) for ref in rig.remote_refs())
    assert [p.name for p in rig.out.iterdir()] == [dry.name]
    assert "--apply --plan" in result.stdout


@pytest.mark.skipif(sys.platform != "darwin", reason="收口 apply 用 clonefile(2) 拷数据库残留，只有 macOS 有")
def test_apply_archives_everything_then_removes(rig):
    tree, database = _dirty_tree(rig)
    head = git(tree, "rev-parse", "HEAD")
    dry, _ = rig.receipt(rig.run("--tree", str(tree), "--reason", "test: feature landed elsewhere"))

    result = rig.run("--apply", "--plan", str(dry))

    assert result.returncode == 0, result.stdout + result.stderr
    assert not tree.exists() and str(tree) not in git(rig.repo, "worktree", "list")
    assert git(rig.repo, "rev-parse", "feat/fwp-wt-dirty") == head  # 分支保留
    _, receipt = rig.receipt(result)
    [rec] = receipt["trees"]
    assert rec["status"] == "removed" and receipt["summary"]["removed"] == 1
    assert "free_bytes_delta" in receipt

    pin = f"refs/archive/wt-{DATE}/fwp-wt-dirty"
    salvage = f"refs/heads/salvage/fwp-wt-dirty-{DATE}"
    assert git(rig.repo, "rev-parse", pin) == head
    assert {pin, salvage} <= rig.remote_refs()

    # 封存：只带真实源码；删除也封进去；禁提与运行噪声不进 git。
    sha = git(rig.repo, "rev-parse", salvage)
    assert git(rig.repo, "rev-parse", f"{sha}^") == head
    changed = set(git(rig.repo, "diff-tree", "-r", "--name-status", "--no-renames", head, sha).splitlines())
    assert changed == {"M\tsrc/app.py", "D\tREADME.md", "A\tnotes/plan.md"}
    assert "changed in the tree" in git(rig.repo, "show", f"{sha}:src/app.py")

    archive = Path(rec["archive_dir"])
    # 补丁能原样打回 HEAD。
    index = archive.parent / "check.index"
    git(rig.repo, "read-tree", head, env={"GIT_INDEX_FILE": str(index)})
    git(rig.repo, "apply", "--cached", "--check", str(archive / "tracked.patch"), env={"GIT_INDEX_FILE": str(index)})
    # 残留包：非缓存文件逐个在，缓存与数据库都不在。
    with tarfile.open(archive / "residue.tar.gz") as tar:
        names = {m.name for m in tar.getmembers()}
    assert names == {"notes/plan.md", ".env.local", "intelligence/users/default/state.json", "evidence/report.txt"}
    # 数据库走克隆，逐字节一致，清单记 sha256。
    assert (archive / "clones" / "evidence" / "db" / "snap.duckdb").read_bytes() == database
    assert "evidence/db/snap.duckdb" in (archive / "clones" / "MANIFEST.sha256").read_text()


def test_clean_detached_tree_is_pinned_and_removed(rig):
    tree = rig.add_tree("fwp-wt-gate", detach=True)
    head = git(tree, "rev-parse", "HEAD")
    dry, _ = rig.receipt(rig.run("--tree", str(tree), "--reason", "gate tree, verdict stored outside"))

    result = rig.run("--apply", "--plan", str(dry))

    assert result.returncode == 0, result.stdout + result.stderr
    assert not tree.exists()
    assert git(rig.repo, "rev-parse", f"refs/archive/wt-{DATE}/fwp-wt-gate") == head
    [rec] = rig.receipt(result)[1]["trees"]
    assert "salvage" not in rec and "tracked_patch" not in rec and "residue" not in rec


def test_blockers_keep_trees_out_of_the_plan(rig):
    unpushed = rig.add_tree("fwp-wt-unpushed", push=False)
    busy = rig.add_tree("fwp-wt-busy")
    locked = rig.add_tree("fwp-wt-locked")
    git(rig.repo, "worktree", "lock", "--reason", "retain until deploy", str(locked))
    unexplained = rig.add_tree("fwp-wt-noreason")
    plan = rig.out.parent / "plan.json"
    plan.write_text(json.dumps([
        {"path": str(unpushed), "reason": "r"}, {"path": str(busy), "reason": "r"},
        {"path": str(locked), "reason": "r"}, {"path": str(unexplained)}, {"path": str(rig.repo), "reason": "r"},
        {"path": str(rig.home / "not-a-tree"), "reason": "r"},
    ]))

    result = rig.run("--plan", str(plan), lsof=f"p42\ncpython\nfcwd\ntDIR\nn{os.path.realpath(busy)}\n")

    assert result.returncode == 0, result.stdout + result.stderr
    dry, receipt = rig.receipt(result)
    blockers = {Path(rec["path"]).name: " | ".join(rec["blockers"]) for rec in receipt["trees"]}
    assert "不在远端" in blockers["fwp-wt-unpushed"]
    assert "pid=42 python fd=cwd" in blockers["fwp-wt-busy"]
    assert "上锁: retain until deploy" in blockers["fwp-wt-locked"]
    assert "没写理由" in blockers["fwp-wt-noreason"]
    assert "主工作树" in blockers["main-repo"]
    assert "不是本仓登记的 worktree" in blockers["not-a-tree"]
    assert receipt["summary"] == {"planned": 6, "eligible": 0, "blocked": 6}

    applied = rig.run("--apply", "--plan", str(dry))
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert all(path.is_dir() for path in (unpushed, busy, locked, unexplained))
    assert rig.refs("refs/archive") == []


def test_launcher_naming_an_ancestor_does_not_block_nested_trees(rig, tmp_path):
    # 2026-10-05 dry-20261005T040409：主检出根被约 40 个启动器点名，嵌在它 .worktrees/ 下的
    # capture-quotes-0929 因此被挡；29 份 ima plist 以 /private/tmp 为 WorkingDirectory，其下两棵门禁树同样被挡。
    nested = rig.add_tree("capture-quotes", path=rig.repo / ".worktrees" / "capture-quotes")
    scratch_root = tmp_path / "scratch-root"  # 代 /private/tmp
    scratch = rig.add_tree("pr10-gates", path=scratch_root / "harness-opt" / "tmp" / "pr10-gates")
    code_root = rig.add_tree("fwp-wt-code-root")
    agents = rig.home / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    (agents / "com.financeworkspace.daily-full-review-sync.plist").write_bytes(plistlib.dumps({
        "WorkingDirectory": str(rig.repo), "EnvironmentVariables": {"FINANCE_WS": str(rig.repo)}}))
    (agents / "com.a77.ima-stock-queue-0827.plist").write_bytes(plistlib.dumps({"WorkingDirectory": str(scratch_root)}))
    # 定时任务真正跑的代码根：引用落在树里，照样挡。
    (agents / "com.financeworkspace.code-root.plist").write_bytes(plistlib.dumps({
        "ProgramArguments": ["/usr/bin/python3", str(code_root / "src" / "app.py")]}))
    plan = rig.out.parent / "plan.json"
    plan.write_text(json.dumps([{"path": str(tree), "reason": "r"} for tree in (nested, scratch, code_root)]))

    result = rig.run("--plan", str(plan))

    assert result.returncode == 0, result.stdout + result.stderr
    receipt = rig.receipt(result)[1]
    blockers = {Path(rec["path"]).name: rec["blockers"] for rec in receipt["trees"]}
    assert {name: blockers[name] for name in ("capture-quotes", "pr10-gates")} == {"capture-quotes": [], "pr10-gates": []}
    assert any(b.startswith("被 launchd/启动器引用") and "code-root.plist" in b for b in blockers["fwp-wt-code-root"])
    assert receipt["summary"] == {"planned": 3, "eligible": 2, "blocked": 1}


def test_release_lock_is_explicit_per_tree(rig):
    tree = rig.add_tree("fwp-wt-installer")
    git(rig.repo, "worktree", "lock", "--reason", "留待授权部署", str(tree))
    plan = rig.out.parent / "plan.json"
    plan.write_text(json.dumps([{"path": str(tree), "reason": "deploy used another tree", "release_lock": True}]))
    dry, receipt = rig.receipt(rig.run("--plan", str(plan)))
    assert receipt["trees"][0]["blockers"] == []

    result = rig.run("--apply", "--plan", str(dry))

    assert result.returncode == 0, result.stdout + result.stderr
    assert not tree.exists()
    assert rig.receipt(result)[1]["trees"][0]["unlocked"] == "留待授权部署"


def test_change_after_the_sample_skips_the_tree(rig):
    touched = rig.add_tree("fwp-wt-touched")
    moved = rig.add_tree("fwp-wt-moved")
    dry_touched, _ = rig.receipt(rig.run("--tree", str(touched), "--reason", "r"))
    dry_moved, _ = rig.receipt(rig.run("--tree", str(moved), "--reason", "r"))
    (touched / "new-file.txt").write_text("someone is still working here\n")
    (moved / "src" / "later.py").write_text("LATER = 'a commit made after the sample'\n")
    git(moved, "add", "--", "src/later.py")
    git(moved, "commit", "-qm", "later")
    git(moved, "push", "-q", "gitea", "feat/fwp-wt-moved")

    reasons = {}
    for dry, tree in ((dry_touched, touched), (dry_moved, moved)):
        result = rig.run("--apply", "--plan", str(dry))
        assert result.returncode == 3, result.stdout + result.stderr
        assert tree.is_dir()
        [rec] = rig.receipt(result)[1]["trees"]
        reasons[tree.name] = " | ".join(rec["skipped"])
    assert "采样后有改动: new-file.txt" in reasons["fwp-wt-touched"]
    assert "HEAD 变了" in reasons["fwp-wt-moved"]
    assert rig.refs("refs/archive") == []  # 复核不过：一步没做


def test_process_entering_after_the_sample_skips_the_tree(rig):
    tree = rig.add_tree("fwp-wt-late-visitor")
    dry, _ = rig.receipt(rig.run("--tree", str(tree), "--reason", "r"))

    result = rig.run("--apply", "--plan", str(dry), lsof=f"p7\nczsh\nfcwd\ntDIR\nn{os.path.realpath(tree)}/src\n")

    assert result.returncode == 3, result.stdout + result.stderr
    assert tree.is_dir()
    assert "pid=7 zsh fd=cwd" in " ".join(rig.receipt(result)[1]["trees"][0]["skipped"])


def test_unreachable_remote_refuses_to_act(rig):
    tree = rig.add_tree("fwp-wt-offline")
    dry, _ = rig.receipt(rig.run("--tree", str(tree), "--reason", "r"))
    git(rig.repo, "remote", "set-url", "gitea", str(rig.home / "gone.git"))

    assert rig.run("--tree", str(tree), "--reason", "r").returncode == 4
    result = rig.run("--apply", "--plan", str(dry))

    assert result.returncode == 4, result.stdout + result.stderr
    assert tree.is_dir() and rig.refs("refs/archive") == []


def test_tree_without_reason_is_sampled_and_blocked(rig):
    # 0 条理由：点名的树照样进收据、各自因没写理由被阻塞；配不到理由不能把树从计划里丢掉（zip 会静默截断）。
    first, second = rig.add_tree("fwp-wt-bare-a"), rig.add_tree("fwp-wt-bare-b")

    result = rig.run("--tree", str(first), "--tree", str(second))

    assert result.returncode == 0, result.stdout + result.stderr
    trees = rig.receipt(result)[1]["trees"]
    assert [Path(rec["path"]).name for rec in trees] == ["fwp-wt-bare-a", "fwp-wt-bare-b"]
    assert all(rec["reason"] == "" and any("没写理由" in b for b in rec["blockers"]) for rec in trees)


def test_one_reason_covers_every_named_tree(rig):
    first, second = rig.add_tree("fwp-wt-shared-a"), rig.add_tree("fwp-wt-shared-b")

    result = rig.run("--tree", str(first), "--tree", str(second), "--reason", "both landed in #12")

    assert result.returncode == 0, result.stdout + result.stderr
    reasons = {Path(rec["path"]).name: rec["reason"] for rec in rig.receipt(result)[1]["trees"]}
    assert reasons == {"fwp-wt-shared-a": "both landed in #12", "fwp-wt-shared-b": "both landed in #12"}


def test_per_tree_reasons_pair_by_position(rig):
    # 2026-10-04 dry-20261004T232659 的形状：--reason 曾是普通 store，只留最后一条并写给两棵树。
    first, second = rig.add_tree("fwp-wt-pair-a"), rig.add_tree("fwp-wt-pair-b")

    result = rig.run("--tree", str(first), "--reason", "A: gate tree, verdict stored outside",
                     "--tree", str(second), "--reason", "B: provenance branch landed in #30")

    assert result.returncode == 0, result.stdout + result.stderr
    receipt = rig.receipt(result)[1]
    reasons = {Path(rec["path"]).name: rec["reason"] for rec in receipt["trees"]}
    assert reasons == {"fwp-wt-pair-a": "A: gate tree, verdict stored outside",
                       "fwp-wt-pair-b": "B: provenance branch landed in #30"}
    assert receipt["summary"]["eligible"] == 2  # 收据就是 apply 的计划：两棵都带着自己的理由进去


@pytest.mark.parametrize(("n_trees", "n_reasons"), [(2, 3), (3, 2)])
def test_reason_count_that_pairs_with_nothing_exits_5_writing_nothing(rig, n_trees, n_reasons):
    trees = [rig.add_tree(f"fwp-wt-count-{i}") for i in range(n_trees)]
    args = [arg for tree in trees for arg in ("--tree", str(tree))]
    args += [arg for i in range(n_reasons) for arg in ("--reason", f"reason {i}")]

    result = rig.run(*args)

    assert result.returncode == 5, result.stdout + result.stderr
    assert f"--tree {n_trees} 棵、--reason {n_reasons} 条" in result.stderr
    assert not rig.out.exists()  # 连收据目录都没建


@pytest.mark.parametrize("args", [
    ["--apply", "--tree", "x"],
    ["--apply"],
    ["--apply", "--plan", "PLAN", "--release-lock", "x"],
    [],
    # 计划里的树只认计划自己的 reason：--reason 管不到它们，混进来的 --tree 也说不清该配哪条。
    ["--plan", "PLAN", "--tree", "x"],
    ["--plan", "PLAN", "--reason", "r"],
])
def test_usage_errors_exit_5(rig, args):
    plan = rig.out.parent / "hand-written.json"
    plan.write_text(json.dumps([{"path": "x", "reason": "r"}]))
    result = rig.run(*[str(plan) if a == "PLAN" else a for a in args])
    assert result.returncode == 5, result.stdout + result.stderr
    assert not rig.out.exists()  # 参数错：收据目录都不建


def test_apply_rejects_a_hand_written_plan(rig):
    tree = rig.add_tree("fwp-wt-handplan")
    plan = rig.out.parent / "plan.json"
    plan.write_text(json.dumps({"trees": [{"path": str(tree), "reason": "r", "head": "0" * 40,
                                           "sampled_at": 0, "slug": "x", "blockers": []}]}))
    result = rig.run("--apply", "--plan", str(plan))
    assert result.returncode == 5 and tree.is_dir()


def test_out_dir_inside_a_planned_tree_is_refused(rig):
    tree = rig.add_tree("fwp-wt-self")
    result = rig.run("--tree", str(tree), "--reason", "r", "--out-dir", str(tree / "receipts"))
    assert result.returncode == 5 and not (tree / "receipts").exists()


def test_failed_step_stops_the_round_and_keeps_progress(rig, monkeypatch, capsys):
    first, _ = _dirty_tree(rig)
    second = rig.add_tree("fwp-wt-second")
    plan = rig.out.parent / "plan.json"
    plan.write_text(json.dumps([{"path": str(first), "reason": "r"}, {"path": str(second), "reason": "r"}]))
    dry, _ = rig.receipt(rig.run("--plan", str(plan)))

    def refuse(src, dst):
        raise closeout.CloseoutError("clonefile 失败（Cross-device link）")

    monkeypatch.setattr(closeout, "_clonefile", refuse)
    monkeypatch.setenv("HOME", str(rig.home))
    monkeypatch.setenv("PATH", f"{rig.fakebin}{os.pathsep}{os.environ['PATH']}")
    code = closeout.main(["--repo", str(rig.repo), "--out-dir", str(rig.out), "--date", DATE,
                          "--apply", "--plan", str(dry)])

    assert code == 1
    assert first.is_dir() and second.is_dir()  # 失败那棵没拆，后面的一棵没轮到
    captured = capsys.readouterr()
    receipt = rig.receipt(captured.out)[1]
    [rec] = receipt["trees"]
    assert rec["status"] == "failed" and "Cross-device" in rec["error"]
    assert rec["pin"] == f"refs/archive/wt-{DATE}/fwp-wt-dirty" and "tracked_patch" in rec
    assert receipt["summary"]["not_reached"] == 1 and receipt["stopped_at"] == str(first)
    assert "整轮停止" in captured.err


def test_salvage_uses_a_temporary_index(rig):
    tree = rig.add_tree("fwp-wt-staged")
    (tree / "src" / "app.py").write_text("def main():\n    return 'staged edit kept in the index'\n")
    git(tree, "add", "--", "src/app.py")
    (tree / "src" / "app.py").write_text("def main():\n    return 'worktree edit on top of the staged one'\n")
    (tree / "odd [name].py").write_text("GLOB = 'brackets are literal, not a pathspec class'\n")
    head = git(tree, "rev-parse", "HEAD")
    index = Path(git(tree, "rev-parse", "--git-dir")) / "index"
    quiet = {"GIT_OPTIONAL_LOCKS": "0"}  # 观测本身别刷新索引
    staged_before = git(tree, "diff", "--cached", "--name-only", env=quiet)
    before = index.read_bytes()

    sha = closeout.salvage_commit(str(tree), head, ["src/app.py", "odd [name].py"], {"odd [name].py"},
                                  "wip(salvage): test\n", timeout=30)

    assert index.read_bytes() == before
    assert git(tree, "diff", "--cached", "--name-only", env=quiet) == staged_before == "src/app.py"
    assert "worktree edit on top" in git(tree, "show", f"{sha}:src/app.py")
    assert git(tree, "show", f"{sha}:odd [name].py").startswith("GLOB")


def test_salvage_of_a_staged_change_reverted_in_the_worktree_is_empty(rig):
    tree = rig.add_tree("fwp-wt-reverted")
    original = (tree / "src" / "app.py").read_text()
    (tree / "src" / "app.py").write_text("def main():\n    return 'staged then reverted in the worktree'\n")
    git(tree, "add", "--", "src/app.py")
    (tree / "src" / "app.py").write_text(original)
    assert closeout.salvage_commit(str(tree), git(tree, "rev-parse", "HEAD"), ["src/app.py"], set(),
                                   "wip\n", timeout=30) == ""


@pytest.mark.parametrize(("rel", "home_rel", "slug"), [
    ("fwp-wt-foo", None, "fwp-wt-foo"),
    (".finance-runtime/finance-workspace-326aa553c571", None, "finance-workspace-326aa553c571"),
    (".finance-runtime/reviews/8792-readiness/kb-retry", None, "reviews--8792-readiness--kb-retry"),
    ("wt with spaces/a..b.lock", None, "wt-with-spaces--a.b.lock-"),
])
def test_slug_matches_the_0928_pin_names(tmp_path, rel, home_rel, slug):
    home = tmp_path / "home"
    assert closeout.slug_for(str(home / rel), str(home)) == slug
    assert subprocess.run(["git", "check-ref-format", f"refs/archive/wt-{DATE}/{slug}"]).returncode == 0


def test_slug_outside_home_keeps_the_absolute_shape(tmp_path):
    assert closeout.slug_for("/private/tmp/claude-501/knevo", str(tmp_path)) == "private--tmp--claude-501--knevo"


@pytest.mark.parametrize(("rel", "forbidden"), [
    (".env", True), (".env.local", True), ("config/mcp_config.json", True), ("feishu_config.json", True),
    ("db/market.duckdb", True), ("x/state.sqlite3", True), ("deck.pptx", True), ("a/._resource", True),
    ("run.log", True), ("venv/lib/x.py", True), ("__MACOSX/x", True), ("intelligence/app.py", False),
    ("docs/notes.md", False), ("environment.md", False),
])
def test_forbidden_matches_pre_commit_and_agents_lists(rel, forbidden):
    assert closeout.is_forbidden(rel) is forbidden


def test_database_residue_detection():
    assert closeout.is_database("tmp/recovery/market.duckdb")
    assert closeout.is_database("tmp/recovery/market.duckdb.wal")
    assert closeout.is_database("state/workbench.sqlite3-journal")
    assert not closeout.is_database("tmp/recovery/notes.dbx")
