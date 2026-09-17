"""8792 / PR #779+#781 独立边界探针：预期行为作断言，缺陷仍在就非零退出。

防的失败形状：只给冻结原句写回归，普通改写却绕过写入边界；把日期共现误当事实
矛盾；把用户列输出要求的排版误当材料。不是生产写入脚本，不调用真实模型。
只在临时目录调用真实 checkpoint 写入器；socket 外呼硬拒绝；只在本进程移除
日期检测器作因果对照，磁盘源码不改。测试 fixture 来自被审 revision。

用法（指定干净目标树，解释器用主树 .venv-workbench/bin/python）：
    python scripts/review_probes/qc_8792_readiness.py --repo /path/to/reviewed-tree

退出码 1 = 行为断言失败；2 = 环境/加载错误；0 = 全部预期成立。逐项结果在 stderr，
JSON 摘要在 stdout。不是全仓 pytest，不生成/替代其测试收据；源码指纹随摘要记录。
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCES = (
    "intelligence/services/track_contract.py",
    "intelligence/services/ranking_contract.py",
    "intelligence/services/user_task.py",
    "intelligence/services/query_understanding.py",
    "intelligence/services/episode_semantic_verifier.py",
    "intelligence/runtime/conversation_orchestrator.py",
    "intelligence/tests/test_research_intent_boundaries.py",
    "intelligence/tests/test_episode_semantic_verifier.py",
)


def suite() -> unittest.TestSuite:
    from intelligence.runtime import conversation_orchestrator as co
    from intelligence.services import episode_semantic_verifier as verifier, llm_refine
    from intelligence.services.query_understanding import understand_query
    from intelligence.services.research_contract import ResearchDeadline
    from intelligence.services.track_contract import ingest_next_watch, persistence_opt_out
    from intelligence.services.user_task import split_user_message
    from intelligence.tests.test_episode_semantic_verifier import _judge, _structural
    from intelligence.tests.test_research_intent_boundaries import _R05_BODY, _TRACK_ANSWER

    plan = "后续观察：计划在2026-10-21复查 E1 所述需求是否改善。"
    fact = "E1 显示该公告发布于 2026-08-21。"
    tail = "我的基准判断是反弹仍有数日窗口。"

    def verify(text: str, mode: str):
        frame, structural = _structural(
            text + tail, detail="需求改善仍需后续观察。", title="需求跟踪公告", source="公司公告"
        )
        with patch.dict(os.environ, {"ASK_SEMANTIC_JUDGE": mode}), patch.object(
            llm_refine, "judge_provider", return_value=None
        ):
            return verifier.SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
                frame=frame,
                structurally_verified=structural,
                deadline=ResearchDeadline.from_timeout(5),
            )

    class BoundaryTests(unittest.TestCase):
        def test_plain_opt_out_control(self):
            self.assertTrue(persistence_opt_out("不需要登记为长期跟踪"))

        def test_demonstrative_stock_opt_out_does_not_write(self):
            with tempfile.TemporaryDirectory(prefix="qc-8792-") as tmp:
                target = Path(tmp) / "checkpoints.jsonl"
                written = ingest_next_watch(
                    target, _TRACK_ANSWER, query="不需要登记这只股票为长期跟踪",
                    as_of="2026-09-16", session_id="qc-boundary",
                )
                self.assertEqual([], written)
                self.assertFalse(target.exists())

        def test_orchestrator_opt_out_does_not_write(self):
            with tempfile.TemporaryDirectory(prefix="qc-8792-") as tmp:
                target = Path(tmp) / "checkpoints.jsonl"
                with patch.object(co.userspace, "user_space", return_value=SimpleNamespace(
                    checkpoints_path=target
                )), patch.dict(os.environ):
                    os.environ.pop("PYTEST_CURRENT_TEST", None)
                    fake_self = SimpleNamespace(run_store=SimpleNamespace(user_id="qc-isolated"))
                    co.TurnOrchestrator._ingest_track_next_watch(
                        fake_self, query="不需要登记这只股票为长期跟踪", answer=_TRACK_ANSWER,
                        question_type="theme_track", as_of="2026-09-16", theme=None,
                        session_id="qc-boundary",
                    )
                self.assertFalse(target.exists(), "三层共用的判据漏判，真实编排层仍写文件")

        def test_long_but_explicit_opt_out(self):
            self.assertTrue(persistence_opt_out(
                "跟踪一下中际旭创，但不要将这次关于经营质量的研究登记为长期跟踪"
            ))

        def test_actual_date_mismatch_control(self):
            for mode in ("llm", "off"):
                with self.subTest(mode=mode):
                    self.assertNotIn(fact, verify(fact, mode).public_answer)

        def test_matching_date_control(self):
            text = "E1 显示该公告发布于 2026-07-22。"
            self.assertIn(text, verify(text, "off").public_answer)

        def test_future_plan_is_preserved_llm(self):
            self.assertIn(plan, verify(plan, "llm").public_answer)

        def test_future_plan_is_preserved_off(self):
            self.assertIn(plan, verify(plan, "off").public_answer)

        def test_ablation_only_removing_new_date_detector_preserves_plan(self):
            with patch.object(verifier, "_mismatched_evidence_date_indexes", return_value=()):
                self.assertIn(plan, verify(plan, "off").public_answer)

        def test_frozen_question_control(self):
            text = _R05_BODY + "\n请按事实条目逐条整理，再形成判断和下一步。"
            parts = split_user_message(text)
            self.assertEqual((), parts.materials)
            self.assertTrue(parts.question.startswith(_R05_BODY))

        def test_numbered_output_requirements_are_not_material(self):
            text = _R05_BODY + "\n1. 请按事实条目逐条整理。\n2. 请给出后续研究问题。"
            parts = split_user_message(text)
            self.assertEqual((), parts.materials)
            self.assertIn(_R05_BODY, parts.question)

        def test_bracketed_output_requirements_are_not_material(self):
            text = _R05_BODY + "\n【输出要求】请按事实条目逐条整理。"
            parts = split_user_message(text)
            self.assertEqual((), parts.materials)
            self.assertIn(_R05_BODY, parts.question)

        def assert_same_route(self, suffix):
            control = understand_query(_R05_BODY + "\n请按事实条目逐条整理。")
            self.assertEqual("financial_analysis", control.question_type)
            self.assertEqual("中际旭创", control.subject)
            actual = understand_query(_R05_BODY + "\n" + suffix)
            self.assertEqual(control.question_type, actual.question_type)
            self.assertEqual(control.subject, actual.subject)

        def test_bracketed_output_format_keeps_route_and_subject(self):
            self.assert_same_route("【输出要求】请按事实条目逐条整理。")

        def test_numbered_output_format_keeps_route_and_subject(self):
            self.assert_same_route("1. 请按事实条目逐条整理。\n2. 请给出后续研究问题。")

        def test_real_document_still_splits_control(self):
            document = (
                "【卖方摘要｜2026-08-28】固态电池：硫化物路线进入中试放量期\n"
                "一、核心观点：公司 A 硫化物电解质中试线 2026 年 8 月投产，规划产能 200 吨/年。\n"
                "二、关键数据：上半年新签订单 12 亿元，同比增长 40%。"
            )
            question = "这篇研报的核心逻辑站得住吗？"
            parts = split_user_message(document + "\n" + question)
            self.assertEqual(1, len(parts.materials))
            self.assertEqual(question, parts.question)

    return unittest.defaultTestLoader.loadTestsFromTestCase(BoundaryTests)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.expanduser().resolve()
    revision = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    source_status = subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain", "--", "intelligence"], text=True
    ).strip()
    if source_status:
        raise RuntimeError(f"review target intelligence/ must be clean: {source_status}")
    fingerprints = {path: hashlib.sha256((repo / path).read_bytes()).hexdigest() for path in SOURCES}
    sys.path.insert(0, str(repo))
    with ExitStack() as stack:
        stack.enter_context(patch("socket.socket.connect", side_effect=RuntimeError("QC: network forbidden")))
        stack.enter_context(patch("socket.create_connection", side_effect=RuntimeError("QC: network forbidden")))
        tests = suite()
        for module in tuple(sys.modules.values()):
            name = getattr(module, "__name__", "")
            file = getattr(module, "__file__", None)
            if name.startswith("intelligence.") and file:
                if not Path(file).resolve().is_relative_to(repo):
                    raise RuntimeError(f"wrong checkout loaded: {name} {file}")
        result = unittest.TextTestRunner(verbosity=2).run(tests)
    summary = {
        "repo": str(repo), "revision": revision, "python": sys.executable,
        "source_status": source_status,
        "sources_sha256": fingerprints, "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "tests_run": result.testsRun,
        "failed": [test.id() for test, _ in result.failures],
        "errors": [test.id() for test, _ in result.errors],
        "skipped": result.skipped,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if result.errors or result.testsRun == 0 or result.skipped:
        return 2
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    try:
        exit_code = main()
    except Exception as exc:
        print(f"QC environment/loading error: {exc}", file=sys.stderr)
        exit_code = 2
    raise SystemExit(exit_code)
