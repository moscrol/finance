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

    def test_门控实参必须是翻译前的值(self) -> None:
        """AST 钉实参，不是钉文件名。

        「注入点调了 policy」保不住门控——首版三条缝全都调了 policy，其中两条把
        **翻译后**的 ``question_plan.question_type`` 传了进去，门控恒不触发而测试
        全绿。所以断言粒度必须下沉到实参表达式：plan 侧只许传
        ``routed_question_type(...)``，frame 侧只许传 ``task_frame.question_type``
        （那套本就是路由词表）。
        """

        import ast
        from pathlib import Path

        repo = Path(__file__).resolve().parents[2]
        gate_fns = {"reading_guidance_for", "inject_knowledge"}
        expected = {
            "intelligence/services/ask_synthesis.py": "routed_question_type",
            "intelligence/services/ask.py": "routed_question_type",
            "intelligence/services/episode_protocol.py": "task_frame.question_type",
        }
        for rel, want in expected.items():
            tree = ast.parse((repo / rel).read_text(encoding="utf-8"))
            calls = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in gate_fns
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "knowledge_injection_policy"
            ]
            self.assertTrue(calls, f"{rel} 没有门控调用点了——接线被摘掉？")
            for call in calls:
                self.assertTrue(call.args, f"{rel}:{call.lineno} 门控调用没有实参")
                arg = ast.unparse(call.args[0])
                self.assertIn(
                    want,
                    arg,
                    f"{rel}:{call.lineno} 门控实参是 {arg!r}，"
                    f"应含 {want!r}——传翻译后的值门控恒不触发",
                )
                self.assertNotEqual(
                    arg,
                    "question_plan.question_type",
                    f"{rel}:{call.lineno} 传的是被 answer_orchestrator.py:272 翻译掉的值",
                )


class EffectiveValueTests(unittest.TestCase):
    """断言**生效值**，不是配置值。

    首版六条测试全部把字面量 ``"market_watch"`` 喂给策略函数，全绿；但生产真正
    传进去的值经 ``answer_orchestrator.py:272`` 翻译后永远不是 market_watch，
    门控两条缝静默失效。「配置生效」与「生效值正确」是两件事，只测前者的门禁
    会在漏掉那档发绿光。
    """

    #: 系统确定性识别为盘面题的主线问法（`_MARKET_WATCH_RE` 命中）。
    GATED_QUERIES = ("目前市场的主线是什么", "现在市场的主线方向有哪些")
    #: 知识型题，必须继续注入——门控不得扩散。
    UNGATED_QUERIES = ("瑞华泰的合理估值", "液冷服务器这个题材现在处于什么阶段")

    def _plan(self, query: str):
        from intelligence.services.answer_orchestrator import plan_answer_question

        return plan_answer_question(query)

    def _frame(self, query: str):
        from intelligence.services.query_understanding import understand_query
        from intelligence.services.task_frame import build_task_frame

        return build_task_frame(query, understand_query(query))

    def test_engine_b_生效值在盘面题上触发门控(self) -> None:
        for query in self.GATED_QUERIES:
            plan = self._plan(query)
            routed = policy.routed_question_type(plan)
            self.assertEqual(routed, "market_watch", query)
            self.assertEqual(policy.reading_guidance_for(routed), "", query)
            self.assertFalse(policy.inject_knowledge(routed), query)

    def test_翻译后的值读不到钥匙_钉住这次的根因(self) -> None:
        """反向钉：直接读 question_plan.question_type 门控恒不触发。

        这条如果哪天变绿（翻译层被改掉），说明 routed_question_type 那层转换
        可以退休——但在那之前，它是本门控唯一能拿到钥匙的路。
        """

        from intelligence.services.answer_orchestrator import QUESTION_TYPES

        self.assertNotIn("market_watch", QUESTION_TYPES)
        for query in self.GATED_QUERIES:
            translated = self._plan(query).question_type
            self.assertNotEqual(translated, "market_watch", query)
            self.assertTrue(policy.inject_knowledge(translated), query)

    def test_engine_a_生效值同样触发门控(self) -> None:
        """Engine A 的 task_frame 保留路由词表，无需转换即可命中。"""

        for query in self.GATED_QUERIES:
            qt = self._frame(query).question_type
            self.assertEqual(qt, "market_watch", query)
            self.assertEqual(policy.reading_guidance_for(qt), "", query)

    def test_知识型题两个引擎都照常注入(self) -> None:
        for query in self.UNGATED_QUERIES:
            self.assertTrue(policy.reading_guidance_for(policy.routed_question_type(self._plan(query))), query)
            self.assertTrue(policy.reading_guidance_for(self._frame(query).question_type), query)

    def test_routed_question_type_缺_envelope_时回退(self) -> None:
        from types import SimpleNamespace

        self.assertEqual(policy.routed_question_type(SimpleNamespace(question_type="x")), "x")
        self.assertEqual(
            policy.routed_question_type(
                SimpleNamespace(question_type="x", query_envelope=SimpleNamespace(question_type=""))
            ),
            "x",
        )
        self.assertEqual(policy.routed_question_type(SimpleNamespace()), "")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
