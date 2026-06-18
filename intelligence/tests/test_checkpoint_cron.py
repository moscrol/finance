"""可证伪点夜间回检 launchd 模板自检。

不依赖 Mac / launchd，只校验模板本身：well-formed plist、跑的是
`checkpoint recheck --apply`、调度错峰（晚于 dream-* 任务）、且不夹带任何 git 动作
（本任务红线：只更新本地 verdicts.jsonl，绝不 commit/push）。
"""
from __future__ import annotations

import plistlib
import unittest
from pathlib import Path

PLIST_PATH = (
    Path(__file__).resolve().parent.parent
    / "dream"
    / "com.financeworkspace.checkpoint-recheck.plist"
)


class CheckpointRecheckPlistTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(PLIST_PATH.is_file(), f"缺少模板：{PLIST_PATH}")
        with PLIST_PATH.open("rb") as fh:
            self.plist = plistlib.load(fh)

    def test_label_and_schedule(self) -> None:
        self.assertEqual(self.plist["Label"], "com.financeworkspace.checkpoint-recheck")
        # 晚于 dream-collect 03:30 / dream-evolve-suggest 03:45，错峰。
        sched = self.plist["StartCalendarInterval"]
        self.assertEqual(sched["Hour"], 3)
        self.assertEqual(sched["Minute"], 50)

    def test_runs_checkpoint_recheck_apply(self) -> None:
        args = self.plist["ProgramArguments"]
        self.assertIn("intelligence.cli", args)
        # 子命令顺序：checkpoint recheck
        self.assertEqual(args[args.index("checkpoint") + 1], "recheck")
        self.assertIn("--apply", args)
        self.assertIn("--user", args)

    def test_no_git_actions(self) -> None:
        # 红线：本任务绝不碰 git。
        joined = " ".join(self.plist["ProgramArguments"])
        for forbidden in ("git", "--push", "commit", "dream-nightly", "dream-evolve-suggest"):
            self.assertNotIn(forbidden, joined)

    def test_env_has_required_path_keys(self) -> None:
        # launchd 极简环境：必须显式给齐路径 env，否则 resolver 找不到 wiki/台账。
        env = self.plist["EnvironmentVariables"]
        self.assertIn("KNOWLEDGE_WIKI", env)
        self.assertIn("FORESIGHT_USERS_DIR", env)
        # 人类可读回检日志落 Obsidian vault（让夜间任务不黑盒）。
        self.assertIn("SUBCONSCIOUS_VAULT", env)

    def test_placeholders_present_for_install(self) -> None:
        raw = PLIST_PATH.read_text(encoding="utf-8")
        for ph in ("__PYTHON__", "__WORKSPACE__", "__USER__", "__KNOWLEDGE_WIKI__", "__SUBCONSCIOUS_VAULT__"):
            self.assertIn(ph, raw)


if __name__ == "__main__":
    unittest.main()
