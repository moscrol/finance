"""市场态题型知识注入门控测试。

钉住 2026-08-26 三轮消融的实施结论：market_watch 题型不注入判读基线全局
guidance、关闭 W 源；其他题型逐字节不变；env 关门控=恢复门控前行为。
"""

from __future__ import annotations

import unittest

from intelligence.services import knowledge_injection_policy as policy
from intelligence.services import reading_baseline


class PolicyTruthTableTests(unittest.TestCase):
    def test_market_watch_is_gated(self) -> None:
        self.assertFalse(policy.inject_knowledge("market_watch"))
        self.assertEqual(policy.reading_guidance_for("market_watch"), "")

    def test_other_types_inject_unchanged(self) -> None:
        for qt in ("theme_analysis", "stock_valuation", "market_cause", "market_forecast", ""):
            self.assertTrue(policy.inject_knowledge(qt), qt)
        # 非门控题型的 guidance 与直接调用逐字节一致。
        self.assertEqual(
            policy.reading_guidance_for("theme_analysis"),
            reading_baseline.baseline_guidance(),
        )
        self.assertTrue(policy.reading_guidance_for("theme_analysis"))

    def test_env_flag_disables_gate_entirely(self) -> None:
        off = {policy.ENV_FLAG: "0"}
        self.assertTrue(policy.gate_enabled({}) )
        self.assertFalse(policy.gate_enabled(off))
        # 门控关闭 = 恢复旧行为：market_watch 也照常注入。
        self.assertTrue(policy.inject_knowledge("market_watch", off))
        self.assertEqual(
            policy.reading_guidance_for("market_watch", off),
            reading_baseline.baseline_guidance(off),
        )

    def test_gate_respects_reading_baseline_own_switch(self) -> None:
        """门控只是不注入；判读基线自身关闭时非门控题型同样拿到空串（两门独立）。"""

        rb_off = {reading_baseline.ENV_FLAG: "0"}
        self.assertEqual(policy.reading_guidance_for("theme_analysis", rb_off), "")

    def test_scope_is_exactly_measured_types(self) -> None:
        """门控范围=实测为负的题型集合；扩集合必须先有消融读数（防顺手扩大）。"""

        self.assertEqual(
            policy.MARKET_STATE_QUESTION_TYPES,
            frozenset({"market_watch"}),
        )


class EpisodeProtocolWiringTests(unittest.TestCase):
    def test_reading_guidance_for_is_the_single_gate_point(self) -> None:
        """两个引擎的注入点都必须走 policy，不得再直调 baseline_guidance。

        用源码断言钉住接线：ask_synthesis 与 episode_protocol 的注入行引用
        policy.reading_guidance_for；直调会让门控静默失效（配置生效、模型照收）。
        """

        from pathlib import Path

        repo = Path(__file__).resolve().parents[2]
        synthesis = (repo / "intelligence/services/ask_synthesis.py").read_text(
            encoding="utf-8"
        )
        protocol = (repo / "intelligence/services/episode_protocol.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("knowledge_injection_policy.reading_guidance_for", synthesis)
        self.assertIn("knowledge_injection_policy.reading_guidance_for", protocol)
        # 注入点不得再出现直调（模块自身定义处除外）。
        self.assertNotIn("baseline_guidance=reading_baseline.baseline_guidance()", synthesis)
        self.assertNotIn("baseline = reading_baseline.baseline_guidance()", protocol)
        ask_src = (repo / "intelligence/services/ask.py").read_text(encoding="utf-8")
        self.assertIn("knowledge_injection_policy.inject_knowledge", ask_src)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
