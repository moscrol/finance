from __future__ import annotations

import json
import tempfile
import unittest
from unittest import mock

from intelligence import userspace
from intelligence.services import auto_eval
from intelligence.eval.capability_monotonicity import evaluate_capability_case


class AutoEvalTests(unittest.TestCase):
    def _run(self, tmp: str, question: str, answer: str) -> auto_eval.AutoEvalOutcome:
        with mock.patch.dict("os.environ", {userspace.ENV_USERS_DIR: tmp}):
            return auto_eval.evaluate_answer(question, answer, user="tester")

    def test_low_score_answer_records_advisory_without_auto_card(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outcome = self._run(tmp, "科技细分里哪个方向还有上涨空间", "科技都很好，可以看好。")

            self.assertLess(outcome.score.total_score, auto_eval.LOW_SCORE_THRESHOLD)
            self.assertTrue(outcome.ledger_path.exists())
            record = json.loads(outcome.ledger_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["question"], "科技细分里哪个方向还有上涨空间")
            self.assertIn("grade", record)
            self.assertEqual(record["role"], "advisory_review")
            self.assertFalse(record["decision_eligible"])
            self.assertTrue(record["flagged_for_review"])

            self.assertIsNone(outcome.card_path)
            self.assertTrue(outcome.flagged_for_review)

            notice = auto_eval.render_notice(outcome)
            self.assertIn("[answer-review/advisory]", notice)
            self.assertIn("未自动回灌", notice)

    def test_high_score_answer_skips_card(self) -> None:
        answer = (
            "结论：先看本地知识库和金融 repo 的证据分层（L1-L4），公司硬事实是订单和客户导入，"
            "盘面处于预期交易向兑现分歧过渡阶段，双红放量但扩散不足；产业链一阶传导到订单和收入，"
            "二阶导看产能利用率与毛利率。反方审稿：老预期可能已被交易，需要证伪点——若缩量则退潮。"
            "后续观察：成交占比环比、客户订单落地、行业容量。若放量新高则主升延续。（非投资建议，"
            "高置信部分是本地数据，不足部分是外部信息）风险：利好兑现后的分歧回撤。生命周期与市场风格切换需跟踪。"
        )
        with tempfile.TemporaryDirectory() as tmp:
            outcome = self._run(tmp, "液冷还有上涨空间吗", answer)

            self.assertGreaterEqual(outcome.score.total_score, auto_eval.LOW_SCORE_THRESHOLD)
            self.assertIsNone(outcome.card_path)
            self.assertFalse(outcome.flagged_for_review)
            self.assertTrue(outcome.ledger_path.exists())

    def test_capability_metrics_stay_advisory_and_do_not_change_auto_eval(self) -> None:
        case = {
            "id": "control-leak",
            "question": "为什么没有回答",
            "answer": "fallback_reason=timeout，详见 /Users/test/run.json",
            "direct_targets": ["回答"],
        }
        metric = evaluate_capability_case(case)
        self.assertGreater(metric.control_plane_leak_score, 0.0)

        with tempfile.TemporaryDirectory() as tmp:
            outcome = self._run(tmp, case["question"], case["answer"])
            record = json.loads(outcome.ledger_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertNotIn("capability_monotonicity", record)
            self.assertEqual(record["role"], "advisory_review")


if __name__ == "__main__":
    unittest.main()
