"""daily-full 环境预检：缺依赖/缺 CDP 必须在第 0 秒说清，不许白跑 7 分钟。

背景（2026-08-12 实测）：`.venv-workbench` 缺 akshare，daily-full 直到第 4 步
才暴露，index/sw-l1/deviation 三步连环 FAIL、同日门必挂、报告必不生成——
前面几分钟的网络抓取全部白花。预检把同一事实提前到开跑前（事实投递 > 提醒）。
"""
from __future__ import annotations

import unittest

from market_feature_store.sync.sync_daily_full import (
    _run_step,
    preflight_daily_update,
)


class PreflightTest(unittest.TestCase):
    def test_all_good_passes(self):
        verdict = preflight_daily_update(
            module_exists=lambda name: True,
            cdp_probe=lambda: True,
        )
        self.assertTrue(verdict["ok"])
        self.assertEqual(verdict["problems"], [])

    def test_missing_akshare_names_the_doomed_steps_and_interpreter(self):
        verdict = preflight_daily_update(
            module_exists=lambda name: name != "akshare",
            cdp_probe=lambda: True,
        )
        self.assertFalse(verdict["ok"])
        joined = " ".join(verdict["problems"])
        self.assertIn("akshare", joined)
        self.assertIn("sync-index-daily", joined)
        self.assertIn("sync-market-deviation", joined)
        # 事实投递：必须点名当前解释器，让「换哪个解释器」可直接行动。
        self.assertIn("python", joined.lower())

    def test_cdp_down_names_the_proxy(self):
        verdict = preflight_daily_update(
            module_exists=lambda name: True,
            cdp_probe=lambda: False,
        )
        self.assertFalse(verdict["ok"])
        self.assertIn("localhost:3456", " ".join(verdict["problems"]))

    def test_swap_lock_that_cannot_exclude_writers_blocks_the_run(self):
        verdict = preflight_daily_update(
            module_exists=lambda name: True,
            cdp_probe=lambda: True,
            swap_lock_probe=lambda: False,
            needs_swap_lock=True,
        )
        self.assertFalse(verdict["ok"])
        joined = " ".join(verdict["problems"])
        self.assertIn("换库锁排不掉 duckdb 写者", joined)
        self.assertIn("scripts/check_swap_lock_platform.py", joined)

    def test_direct_daily_update_does_not_consult_the_swap_lock(self):
        # daily-update 直写不换库：不查锁，也不为它起自检子进程
        def must_not_run():
            raise AssertionError("不换库的链不该跑换库锁自检")

        verdict = preflight_daily_update(
            module_exists=lambda name: True,
            cdp_probe=lambda: True,
            swap_lock_probe=must_not_run,
        )
        self.assertTrue(verdict["ok"])


class RunStepTimingTest(unittest.TestCase):
    def test_ok_step_carries_elapsed(self):
        step = _run_step("demo", lambda: {"rows": 1})
        self.assertTrue(step["ok"])
        self.assertIn("elapsed_s", step)
        self.assertGreaterEqual(step["elapsed_s"], 0)

    def test_failed_step_carries_elapsed_and_error(self):
        def boom():
            raise RuntimeError("炸")

        step = _run_step("demo", boom)
        self.assertFalse(step["ok"])
        self.assertEqual(step["error"], "炸")
        self.assertIn("elapsed_s", step)


if __name__ == "__main__":
    unittest.main()
