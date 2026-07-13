"""#7 澄清追问前置门（ask_clarify）+ 子任务并行执行器（ask_planner）单测。"""

from __future__ import annotations

import threading
import time
import unittest

from intelligence.services import ask_clarify, ask_planner


class ClarifyGateTest(unittest.TestCase):
    def test_empty_query_needs_clarification(self):
        d = ask_clarify.clarify_for_query("")
        self.assertTrue(d.needs_clarification)
        self.assertEqual(len(d.questions), 3)

    def test_bare_vague_trigger_needs_clarification(self):
        for q in ("随便", "帮我看看", "分析一下", "看看"):
            d = ask_clarify.clarify_for_query(q)
            self.assertTrue(d.needs_clarification, q)

    def test_vague_plus_filler_needs_clarification(self):
        for q in ("帮我随便看看吧", "麻烦分析一下呢", "帮我看看今天", "看一下最近怎么样"):
            d = ask_clarify.clarify_for_query(q)
            self.assertTrue(d.needs_clarification, q)

    def test_substantive_queries_pass_through(self):
        for q in (
            "液冷服务器",
            "帮我看看人形机器人",
            "分析一下金刚石散热的资金流",
            "英维克 财报",
            "帮我看看 300316",
            "人形机器人 之前的判断验证得怎么样",
        ):
            d = ask_clarify.clarify_for_query(q)
            self.assertFalse(d.needs_clarification, q)

    def test_summary_lines_render_reason_and_questions(self):
        d = ask_clarify.clarify_for_query("随便")
        lines = d.summary_lines()
        self.assertIn("随便", lines[0])
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[1].startswith("1."))


class BlockPlannerTest(unittest.TestCase):
    def test_outcomes_keep_input_order(self):
        def make(tag, delay):
            def build():
                time.sleep(delay)
                return f"block-{tag}", f"cite-{tag}"

            return ask_planner.BlockTask(tag, tag, build)

        # 故意让先提交的任务更慢，验证结果仍按输入顺序返回。
        tasks = [make("A", 0.05), make("B", 0.0), make("C", 0.02)]
        outcomes = ask_planner.run_block_tasks(tasks, parallel=True)
        self.assertEqual([o.tag for o in outcomes], ["A", "B", "C"])
        self.assertEqual([o.block for o in outcomes], ["block-A", "block-B", "block-C"])
        self.assertEqual(outcomes[0].citation, "cite-A")

    def test_tasks_actually_run_concurrently(self):
        barrier = threading.Barrier(3, timeout=5)

        def build():
            barrier.wait()  # 三个任务必须同时在跑才能过 barrier
            return "ok", None

        tasks = [ask_planner.BlockTask(str(i), str(i), build) for i in range(3)]
        outcomes = ask_planner.run_block_tasks(tasks, max_workers=3, parallel=True)
        self.assertTrue(all(o.block == "ok" for o in outcomes))

    def test_single_task_failure_degrades_not_crashes(self):
        def boom():
            raise RuntimeError("db locked")

        tasks = [
            ask_planner.BlockTask("BAD", "坏块", boom),
            ask_planner.BlockTask("OK", "好块", lambda: ("fine", None)),
        ]
        outcomes = ask_planner.run_block_tasks(tasks, parallel=True)
        self.assertIn("db locked", outcomes[0].error)
        self.assertEqual(outcomes[0].block, "")
        self.assertEqual(outcomes[1].block, "fine")

    def test_serial_mode_gives_same_results(self):
        tasks = [ask_planner.BlockTask(t, t, lambda t=t: (f"b-{t}", None)) for t in ("X", "Y")]
        par = ask_planner.run_block_tasks(tasks, parallel=True)
        ser = ask_planner.run_block_tasks(tasks, parallel=False)
        self.assertEqual([(o.tag, o.block) for o in par], [(o.tag, o.block) for o in ser])


class AskIntegrationTest(unittest.TestCase):
    def test_answer_query_short_circuits_on_vague_query(self):
        from intelligence.services.ask import AskOptions, answer_query, render_answer

        result = answer_query(AskOptions(query="帮我看看", use_modules=False, use_wiki_rag=False))
        self.assertIsNotNone(result.clarify)
        self.assertEqual(result.sections, {})
        rendered = render_answer(result)
        self.assertIn("澄清追问", rendered)
        self.assertIn("--no-clarify", rendered)

    def test_no_clarify_flag_disables_gate(self):
        from intelligence.services.ask import AskOptions, answer_query

        result = answer_query(
            AskOptions(query="帮我看看", clarify=False, use_modules=False, use_wiki_rag=False)
        )
        self.assertIsNone(result.clarify)

    def test_substantive_query_not_gated(self):
        from intelligence.services.ask import AskOptions, answer_query

        result = answer_query(
            AskOptions(query="液冷服务器", use_modules=False, use_wiki_rag=False)
        )
        self.assertIsNone(result.clarify)

    def test_answer_query_reports_real_deterministic_and_synthesis_boundaries(self):
        from intelligence.services.ask import AskOptions, answer_query

        progress: list[tuple[str, str]] = []
        answer_query(
            AskOptions(
                query="液冷服务器",
                use_modules=False,
                use_wiki_rag=False,
                progress_callback=lambda stage, status: progress.append(
                    (stage, status)
                ),
            )
        )

        self.assertEqual(
            progress,
            [
                ("deterministic_recall", "running"),
                ("deterministic_recall", "completed"),
                ("synthesis", "running"),
                ("synthesis", "degraded"),
            ],
        )

    def test_throwing_progress_callback_never_interrupts_answer(self):
        from intelligence.services.ask import AskOptions, answer_query

        calls = 0

        def throwing_progress(stage: str, status: str) -> None:
            nonlocal calls
            calls += 1
            raise RuntimeError("progress sink unavailable")

        result = answer_query(
            AskOptions(
                query="液冷服务器",
                use_modules=False,
                use_wiki_rag=False,
                progress_callback=throwing_progress,
            )
        )

        self.assertIsNotNone(result.answer_spec)
        self.assertEqual(calls, 1)

    def test_parallel_and_serial_compose_identical(self):
        """并行 vs 串行：evidence 汇总/引用编号/可观测统计必须逐字节一致。"""
        from intelligence.services.ask import AskOptions, answer_query, render_answer

        base = dict(
            query="液冷服务器 资金流和历史类比怎么样",
            use_modules=False,
            use_wiki_rag=False,
            compose=True,  # 无 LLM key 时降级模板，但取数块照跑
            compose_self_review=False,
        )
        par = answer_query(AskOptions(**base, parallel_blocks=True))
        ser = answer_query(AskOptions(**base, parallel_blocks=False))
        self.assertEqual(
            [(s.tag, s.source, s.generated) for s in par.d_block_stats],
            [(s.tag, s.source, s.generated) for s in ser.d_block_stats],
        )
        self.assertEqual(
            [(c.tag, c.source, c.detail) for c in par.citations],
            [(c.tag, c.source, c.detail) for c in ser.citations],
        )
        self.assertEqual(render_answer(par), render_answer(ser))

    def test_chat_turn1_returns_clarify_questions(self):
        from intelligence.services.ask import AskOptions
        from intelligence.services.ask_chat import AskConversation

        conv = AskConversation(AskOptions(query="随便", use_modules=False, use_wiki_rag=False))
        turn = conv.start()
        self.assertFalse(turn.composed)
        self.assertIn("澄清", turn.warning)
        self.assertIn("1.", turn.answer)
        self.assertFalse(conv.ready)


if __name__ == "__main__":
    unittest.main()
