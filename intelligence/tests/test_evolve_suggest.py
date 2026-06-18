from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from intelligence.dream import evolve_suggest


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def _init_repo(repo: Path) -> None:
    """初始化一个干净的、默认分支为 main 的临时仓（含 .gitignore 忽略 suggestions）。"""
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True, text=True)
    # 默认分支强制为 main（兼容老/新 git）。
    subprocess.run(["git", "-C", str(repo), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
    # 镜像真实仓：evolution/suggestions/ 被 gitignore，故需 force-add。
    (repo / ".gitignore").write_text("evolution/suggestions/\nevolution/params.json\n", encoding="utf-8")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "--", ".gitignore", "README.md")
    _git(repo, "commit", "-m", "seed")


def _write_fake_evolve(repo: Path, mode: str) -> None:
    """写一个假的 scripts/evolve.py，按 mode 模拟 suggest 行为（无需 duckdb/DB）。"""
    scripts = repo / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    bodies = {
        # 正常：产出一个 suggestion-*.md，rc=0
        "ok": """
            import os, sys
            d = os.path.join(os.getcwd(), "evolution", "suggestions")
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "suggestion-20260617-0001.md"), "w").write("# suggest\\n")
            print("wrote suggestion")
        """,
        # 同时偷偷写 params.json（必须被白名单挡住，绝不进暂存区）
        "ok_with_params": """
            import os, sys
            d = os.path.join(os.getcwd(), "evolution", "suggestions")
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "suggestion-20260617-0002.md"), "w").write("# suggest\\n")
            open(os.path.join(os.getcwd(), "evolution", "params.json"), "w").write("{}\\n")
            print("wrote suggestion + params")
        """,
        # DB 被锁：rc=1，不产文件
        "locked": """
            import sys
            sys.stderr.write("duckdb.IOException: Could not set lock on file\\n")
            sys.exit(1)
        """,
        # duckdb 不可用：rc=1，不产文件
        "no_duckdb": """
            import sys
            sys.stderr.write("ModuleNotFoundError: No module named 'duckdb'\\n")
            sys.exit(1)
        """,
    }
    src = "import sys\n" + textwrap.dedent(bodies[mode])
    (scripts / "evolve.py").write_text(src, encoding="utf-8")


def _commit_env() -> dict:
    env = dict(os.environ)
    env.update(
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@example.com",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@example.com",
    )
    return env


class ClassifySkipTests(unittest.TestCase):
    def test_classify_reasons(self) -> None:
        self.assertIsNone(evolve_suggest.classify_skip(0, "ok", ""))
        self.assertEqual(evolve_suggest.classify_skip(1, "", "Could not set lock on file"), "db-locked")
        self.assertEqual(evolve_suggest.classify_skip(1, "", "No module named 'duckdb'"), "duckdb-unavailable")
        self.assertEqual(evolve_suggest.classify_skip(1, "", "database does not exist"), "db-missing")
        self.assertEqual(evolve_suggest.classify_skip(2, "", "boom"), "evolve-rc-2")


class RunEvolveSuggestTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_backup = dict(os.environ)
        os.environ.update(
            GIT_AUTHOR_NAME="t",
            GIT_AUTHOR_EMAIL="t@example.com",
            GIT_COMMITTER_NAME="t",
            GIT_COMMITTER_EMAIL="t@example.com",
        )

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_db_locked_is_graceful_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            _init_repo(repo)
            _write_fake_evolve(repo, "locked")
            summary = evolve_suggest.run_evolve_suggest(
                evolve_suggest.EvolveSuggestOptions(repo_dir=str(repo), date="2026-06-17")
            )
            self.assertTrue(summary["ran"])
            self.assertEqual(summary["evolve_rc"], 1)
            self.assertEqual(summary["skipped_reason"], "db-locked")
            self.assertEqual(summary["new_suggestions"], [])
            self.assertIsNone(summary["branch"])
            self.assertFalse(summary["committed"])
            # 还在 main，没切分支
            self.assertEqual(_git(repo, "branch", "--show-current").stdout.strip(), "main")

    def test_duckdb_unavailable_is_graceful_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            _init_repo(repo)
            _write_fake_evolve(repo, "no_duckdb")
            summary = evolve_suggest.run_evolve_suggest(
                evolve_suggest.EvolveSuggestOptions(repo_dir=str(repo), date="2026-06-17")
            )
            self.assertEqual(summary["skipped_reason"], "duckdb-unavailable")
            self.assertFalse(summary["committed"])

    def test_new_suggestion_committed_to_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            _init_repo(repo)
            _write_fake_evolve(repo, "ok")
            summary = evolve_suggest.run_evolve_suggest(
                evolve_suggest.EvolveSuggestOptions(repo_dir=str(repo), date="2026-06-17")
            )
            self.assertEqual(summary["new_suggestions"], ["suggestion-20260617-0001.md"])
            self.assertEqual(summary["branch"], "dream-loop/evolve-suggest-2026-06-17")
            self.assertTrue(summary["committed"])
            self.assertEqual(summary["staged"], ["evolution/suggestions/suggestion-20260617-0001.md"])
            # 在新分支上，最近一条 commit 含建议文件
            self.assertEqual(_git(repo, "branch", "--show-current").stdout.strip(), "dream-loop/evolve-suggest-2026-06-17")
            files = _git(repo, "show", "--name-only", "--pretty=format:", "HEAD").stdout
            self.assertIn("evolution/suggestions/suggestion-20260617-0001.md", files)

    def test_params_json_never_staged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            _init_repo(repo)
            _write_fake_evolve(repo, "ok_with_params")
            summary = evolve_suggest.run_evolve_suggest(
                evolve_suggest.EvolveSuggestOptions(repo_dir=str(repo), date="2026-06-17")
            )
            self.assertTrue(summary["committed"])
            self.assertTrue(all("params.json" not in s for s in summary["staged"]))
            committed_files = _git(repo, "show", "--name-only", "--pretty=format:", "HEAD").stdout
            self.assertNotIn("params.json", committed_files)
            self.assertIn("suggestion-20260617-0002.md", committed_files)
            # params.json 也不在任何被跟踪文件里
            tracked = _git(repo, "ls-files").stdout
            self.assertNotIn("evolution/params.json", tracked)

    def test_no_run_with_no_new_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            _init_repo(repo)
            summary = evolve_suggest.run_evolve_suggest(
                evolve_suggest.EvolveSuggestOptions(repo_dir=str(repo), date="2026-06-17", run=False)
            )
            self.assertFalse(summary["ran"])
            self.assertEqual(summary["new_suggestions"], [])
            self.assertFalse(summary["committed"])


class CliWiringTests(unittest.TestCase):
    def test_cli_registers_dream_evolve_suggest(self) -> None:
        from intelligence import cli

        parser = cli.build_parser()
        args = parser.parse_args(["dream-evolve-suggest", "--repo-dir", "/tmp/x"])
        self.assertEqual(args.func, cli.cmd_dream_evolve_suggest)
        self.assertEqual(args.base, "main")
        self.assertFalse(args.push)


if __name__ == "__main__":
    unittest.main()
