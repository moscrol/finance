from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from intelligence.eval.finance_answer_rubric import (
    QUESTION_MARKET_FORECAST,
    _hypothesis_blocks,
    score_answer,
)


FORECAST_DIM_KEYS = [
    "forecast_source_consensus",
    "forecast_stage_call",
    "forecast_strategy_mapping",
    "forecast_hypotheses",
    "forecast_hypothesis_attribution",
]


STRONG_FORECAST_ANSWER = """
先按本地知识库和金融 repo 的全量盘面复盘看，不把 web 当主来源。

四源合议：全量盘面显示双红题材集中在液冷和 PCB，边际量为正，涨停热度回升，新高集群扩大；
晚间卖方按机构胜率看，头部机构继续加密液冷覆盖密度；隔夜美股方面，纳指和费半收涨，外盘
（SOXX/QQQ）对 AI 硬件链是支持项；晨汇里早间材料提示海外大厂上调资本开支指引。

大盘阶段：指数在周均线上方缩量整理，属于结构性上涨而非普涨；情绪阶段涨家数回升、赚钱效应
扩散；风格判断是高位分歧后向低位切换与主线抱团并存，承接尚可。

证据分层：L1 是卖方对液冷渗透率的产业叙事；L3 是公告级订单与量产事实；L4 是盘面双红与放量。
反方审稿：如果判断错，最可能错在把缩量修复当成主升；证伪条件是次日成交跌破阈值。

策略状态映射：分歧环境下比较策略三主线强势股回流与策略二流动性切换，当前优先策略三、
备选策略二，选择理由是主线题材双红延续且龙头承接未破位。

可验证假设：
- 假设1：液冷板块次日成交额不低于 300 亿且维持双红，支持来源为全量盘面；反证来源为边际量转负。
- 假设2：纳指与费半若隔夜美股回撤超过 2%，A 股 AI 硬件链盘中承接减弱，支持来源为外盘映射。
- 假设3：晚间卖方新增覆盖不足 3 家则视为共识确认而非新 alpha，验证时点为次日盘后，支持来源为晚间卖方。
- 假设4：晨汇提示的资本开支指引若被公告证伪，相关个股收盘回吐超过 5%，反证来源为晨汇与公告。

结论：维持结构性做多观察，后续看订单、成交承接与双红扩散。（非投资建议）
"""


WEAK_FORECAST_ANSWER = """
今天市场整体不错，科技板块很活跃，我认为明天大概率继续上涨，
可以关注 AI 相关方向，风险是外围市场波动。（非投资建议）
"""


class MarketForecastRubricTests(unittest.TestCase):
    def test_forecast_group_appended_only_for_market_forecast_type(self) -> None:
        plain = score_answer("站在7.1视角，7.2行情怎么看", WEAK_FORECAST_ANSWER)
        forecast = score_answer(
            "站在7.1视角，7.2行情怎么看",
            WEAK_FORECAST_ANSWER,
            question_type=QUESTION_MARKET_FORECAST,
        )

        self.assertEqual(len(plain.dimensions), 7)
        self.assertEqual(plain.max_score, 100)
        self.assertIsNone(plain.question_type)
        self.assertEqual(len(forecast.dimensions), 12)
        self.assertEqual(forecast.max_score, 150)
        self.assertEqual(
            [d.key for d in forecast.dimensions[7:]], FORECAST_DIM_KEYS
        )

    def test_strong_forecast_answer_passes_forecast_dimensions(self) -> None:
        scored = score_answer(
            "站在7.1视角，7.2行情怎么看",
            STRONG_FORECAST_ANSWER,
            local_sources=["market_feature_store"],
            question_type=QUESTION_MARKET_FORECAST,
        )

        self.assertEqual(scored.dimension("forecast_source_consensus").score, 12)
        self.assertGreaterEqual(scored.dimension("forecast_stage_call").score, 6)
        self.assertGreaterEqual(scored.dimension("forecast_strategy_mapping").score, 8)
        self.assertGreaterEqual(scored.dimension("forecast_hypotheses").score, 10)
        self.assertEqual(scored.dimension("forecast_hypothesis_attribution").score, 8)
        self.assertGreaterEqual(scored.percent, 75)

    def test_weak_forecast_answer_fails_forecast_dimensions(self) -> None:
        scored = score_answer(
            "站在7.1视角，7.2行情怎么看",
            WEAK_FORECAST_ANSWER,
            question_type=QUESTION_MARKET_FORECAST,
        )

        joined = "\n".join(scored.failures)
        self.assertIn("四源合议", joined)
        self.assertIn("策略状态映射", joined)
        self.assertIn("可验证假设", joined)
        self.assertEqual(scored.dimension("forecast_hypotheses").score, 0)
        self.assertIn(scored.grade, {"D", "F"})

    def test_hypothesis_blocks_parse_numbered_items_not_section_headers(self) -> None:
        blocks = _hypothesis_blocks(STRONG_FORECAST_ANSWER)
        self.assertEqual(len(blocks), 4)

        no_hypothesis = "假设验证：盘前推论必须能在盘后验证，但本回答没有列出编号假设。"
        self.assertEqual(_hypothesis_blocks(no_hypothesis), [])

    def test_auto_eval_derives_market_forecast_type_from_orchestrator(self) -> None:
        from unittest import mock

        from intelligence import userspace
        from intelligence.services import auto_eval

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict("os.environ", {userspace.ENV_USERS_DIR: tmp}):
                outcome = auto_eval.evaluate_answer(
                    "站在7.1视角，7.2行情怎么看",
                    STRONG_FORECAST_ANSWER,
                    user="tester",
                )

            self.assertEqual(outcome.score.question_type, QUESTION_MARKET_FORECAST)
            self.assertEqual(outcome.score.max_score, 150)
            record = json.loads(
                outcome.ledger_path.read_text(encoding="utf-8").splitlines()[-1]
            )
            self.assertEqual(record["question_type"], QUESTION_MARKET_FORECAST)

    def test_cli_auto_detects_question_type_and_reports_forecast_dims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            answer_path = Path(tmp) / "answer.md"
            answer_path.write_text(STRONG_FORECAST_ANSWER, encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "intelligence.cli",
                    "answer-score",
                    "--question",
                    "站在7.1视角，7.2行情怎么看",
                    "--answer-file",
                    str(answer_path),
                    "--local-source",
                    "market_feature_store",
                    "--json",
                ],
                cwd=Path(__file__).resolve().parents[2],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["question_type"], QUESTION_MARKET_FORECAST)
        self.assertIn(
            "forecast_source_consensus", [d["key"] for d in payload["dimensions"]]
        )


if __name__ == "__main__":
    unittest.main()
