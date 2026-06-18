"""dream-loop 采集半（nightly）测试：临时 git 仓里验证「从 base 切分支、只提交脱敏
digest/manifest、绝不提交正文、绝不动 base、可选 push」。"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from intelligence.dream import nightly


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), capture_output=True, text=True, check=True)


def _init_repo(root: str) -> None:
    _run("git", "init", root)
    _run("git", "-C", root, "config", "user.email", "dream@test")
    _run("git", "-C", root, "config", "user.name", "dream-test")
    _run("git", "-C", root, "config", "commit.gpgsign", "false")
    gitignore = Path(root) / ".gitignore"
    gitignore.write_text("raw/transcripts/*/*.jsonl\n", encoding="utf-8")
    _run("git", "-C", root, "add", ".gitignore")
    _run("git", "-C", root, "commit", "-m", "init")
    _run("git", "-C", root, "branch", "-M", "main")


def _write_feishu_events(path: Path, date: str) -> None:
    leak_token = "ghp_" + "a" * 36
    events = [
        {"ts": f"{date}T10:00:00+08:00", "chat_id": "oc_demo", "message_type": "text",
         "text": "今天大盘怎么看", "reply": "六段答案……", "direction": "in"},
        {"ts": f"{date}T10:01:00+08:00", "chat_id": "oc_demo", "message_type": "text",
         "text": f"我的 token 是 {leak_token}", "reply": "已收到", "direction": "in"},
        {"ts": f"{date}T10:02:00+08:00", "chat_id": "oc_demo", "message_type": "text",
         "text": "我持仓 600519 成本价 1500", "reply": "ok", "direction": "in"},
    ]
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events), encoding="utf-8")


def _commit_files(root: str) -> list:
    res = _run("git", "-C", root, "show", "--name-only", "--pretty=format:", "HEAD")
    return [ln for ln in res.stdout.splitlines() if ln.strip()]


class RunNightlyTests(unittest.TestCase):
    DATE = "2026-06-17"

    def test_collect_branch_commit_whitelist_and_redaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = str(Path(tmp) / "clone")
            _init_repo(repo)
            events = Path(tmp) / "events.jsonl"
            _write_feishu_events(events, self.DATE)

            summary = nightly.run_nightly(
                nightly.NightlyOptions(
                    repo_dir=repo, events_path=str(events),
                    source="feishu", date=self.DATE, collect=True, push=False,
                )
            )

            self.assertEqual(summary["branch"], f"dream-loop/transcripts-{self.DATE}")
            self.assertTrue(summary["committed"])
            self.assertGreaterEqual(summary["collected"]["records_redacted"], 2)

            files = _commit_files(repo)
            self.assertIn(f"raw/transcripts/digest-{self.DATE}.md", files)
            self.assertIn("raw/transcripts/manifest.jsonl", files)
            # 正文 jsonl 绝不入提交
            self.assertFalse([f for f in files if f.endswith(".jsonl") and "/" + self.DATE + "/" in f])

            digest = (Path(repo) / "raw" / "transcripts" / f"digest-{self.DATE}.md").read_text(encoding="utf-8")
            self.assertNotIn("ghp_" + "a" * 36, digest)
            self.assertNotIn("600519", digest)
            self.assertIn("[REDACTED:", digest)

    def test_does_not_touch_base_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = str(Path(tmp) / "clone")
            _init_repo(repo)
            base_tip_before = _run("git", "-C", repo, "rev-parse", "main").stdout.strip()
            events = Path(tmp) / "events.jsonl"
            _write_feishu_events(events, self.DATE)

            nightly.run_nightly(
                nightly.NightlyOptions(
                    repo_dir=repo, events_path=str(events), date=self.DATE, collect=True,
                )
            )
            base_tip_after = _run("git", "-C", repo, "rev-parse", "main").stdout.strip()
            self.assertEqual(base_tip_before, base_tip_after)

    def test_no_collect_no_digest_yields_no_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = str(Path(tmp) / "clone")
            _init_repo(repo)
            summary = nightly.run_nightly(
                nightly.NightlyOptions(repo_dir=repo, date=self.DATE, collect=False)
            )
            self.assertEqual(summary["staged"], [])
            self.assertFalse(summary["committed"])
            self.assertFalse(summary["pushed"])

    def test_no_collect_stages_only_digest_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = str(Path(tmp) / "clone")
            _init_repo(repo)
            store = Path(repo) / "raw" / "transcripts"
            (store / self.DATE).mkdir(parents=True)
            # 预置正文 jsonl（应被忽略）+ digest + manifest（应被提交）
            (store / self.DATE / "feishu-oc_demo.jsonl").write_text('{"ts":"x"}\n', encoding="utf-8")
            (store / f"digest-{self.DATE}.md").write_text("# 脱敏摘要\n", encoding="utf-8")
            (store / "manifest.jsonl").write_text('{"date":"%s"}\n' % self.DATE, encoding="utf-8")

            summary = nightly.run_nightly(
                nightly.NightlyOptions(repo_dir=repo, date=self.DATE, collect=False)
            )
            self.assertTrue(summary["committed"])
            staged = set(summary["staged"])
            self.assertIn(f"raw/transcripts/digest-{self.DATE}.md", staged)
            self.assertIn("raw/transcripts/manifest.jsonl", staged)
            files = _commit_files(repo)
            self.assertFalse([f for f in files if f.endswith("feishu-oc_demo.jsonl")])

    def test_push_writes_branch_to_remote(self):
        with tempfile.TemporaryDirectory() as tmp:
            remote = str(Path(tmp) / "remote.git")
            _run("git", "init", "--bare", remote)
            repo = str(Path(tmp) / "clone")
            _init_repo(repo)
            _run("git", "-C", repo, "remote", "add", "origin", remote)
            _run("git", "-C", repo, "push", "origin", "main")
            events = Path(tmp) / "events.jsonl"
            _write_feishu_events(events, self.DATE)

            summary = nightly.run_nightly(
                nightly.NightlyOptions(
                    repo_dir=repo, events_path=str(events), date=self.DATE,
                    collect=True, push=True,
                )
            )
            self.assertTrue(summary["pushed"])
            ls = _run("git", "-C", remote, "branch", "--list", f"dream-loop/transcripts-{self.DATE}")
            self.assertIn(f"dream-loop/transcripts-{self.DATE}", ls.stdout)
            # 远端 main 不应被本流程改动（仍指向 init）
            remote_main = _run("git", "-C", remote, "rev-parse", "main").stdout.strip()
            local_main = _run("git", "-C", repo, "rev-parse", "main").stdout.strip()
            self.assertEqual(remote_main, local_main)


class CliWiringTests(unittest.TestCase):
    def test_cli_registers_dream_nightly(self):
        from intelligence.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["dream-nightly", "--repo-dir", "/tmp/x", "--date", "2026-06-17"])
        self.assertEqual(args.repo_dir, "/tmp/x")
        self.assertEqual(args.source, "feishu")
        self.assertFalse(args.push)
        self.assertFalse(args.no_collect)


if __name__ == "__main__":
    unittest.main()
