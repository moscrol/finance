from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence import cli, userspace
from intelligence.services import perspective_exam, perspective_lab


def _us(tmp: str, uid: str = "tester") -> userspace.UserSpace:
    root = Path(tmp) / uid
    return userspace.UserSpace(
        user_id=uid,
        root=root,
        profile_path=root / "profile.json",
        derived_path=root / "profile.derived.json",
        memory_path=root / "foresight_memory.jsonl",
        interactions_path=root / "interactions.jsonl",
        corrections_path=root / "corrections.jsonl",
        experience_cards_path=root / "experience_cards.jsonl",
        answer_scores_path=root / "answer_scores.jsonl",
        judgments_path=root / "judgments.jsonl",
        checkpoints_path=root / "checkpoints.jsonl",
        verdicts_path=root / "verdicts.jsonl",
        strategy_params_path=root / "strategy_params.json",
    )


def _seed_blogger(us: userspace.UserSpace) -> dict:
    _, profile = perspective_lab.init_perspective(us, "blogger_x", display_name="某博主")
    profile["risk_triggers"] = ["产能过剩", "库存历史高位"]
    profile["opportunity_preferences"] = ["核心股缩量回踩关键均线"]
    profile["anti_patterns"] = ["在退潮期抢反弹当主升做"]
    profile["honest_boundaries"] = ["样本只覆盖 AI 硬件主线，未覆盖可转债与港股"]
    perspective_lab._save_profile(us, profile)
    return perspective_lab.load_profile(us, "blogger_x")


def _complete_exam(us: userspace.UserSpace) -> None:
    perspective_exam.add_case(
        us,
        "blogger_x",
        kind="known_answer",
        question="产能过剩时该角色怎么看仓位？",
        facts="行业产能过剩，库存历史高位，需求走弱。",
        expected_direction="risk",
        expected_field="risk_triggers",
        expected_terms=["产能过剩"],
        forbidden=["加仓"],
    )
    perspective_exam.add_case(
        us,
        "blogger_x",
        kind="known_answer",
        question="缩量回踩时有没有机会？",
        facts="核心股缩量回踩关键均线，题材仍有新高扩散。",
        expected_direction="opportunity",
        expected_field="opportunity_preferences",
        expected_terms=["核心股缩量回踩关键均线"],
    )
    perspective_exam.add_case(
        us,
        "blogger_x",
        kind="edge_case",
        question="可转债怎么定价？",
        facts="某可转债溢价率 30%。",
    )


class BoundaryMatchTests(unittest.TestCase):
    def test_unreliable_clause_hits_convertible(self) -> None:
        hits = perspective_lab.matching_boundaries(
            ["样本只覆盖 AI 硬件主线，未覆盖可转债与港股"],
            "可转债怎么定价？",
            "",
        )
        self.assertEqual(len(hits), 1)

    def test_coverage_clause_does_not_abstain_on_ai(self) -> None:
        hits = perspective_lab.matching_boundaries(
            ["样本只覆盖 AI 硬件主线，未覆盖可转债与港股"],
            "AI硬件怎么看？",
            "AI 硬件主线成交活跃",
        )
        self.assertEqual(hits, [])

    def test_short_topic_boundary(self) -> None:
        hits = perspective_lab.matching_boundaries(["可转债"], "可转债怎么定价？", "")
        self.assertEqual(hits, ["可转债"])

    def test_evaluate_role_clears_hits_when_abstain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            profile = _seed_blogger(us)
            ev = perspective_lab.evaluate_role(
                profile,
                question="可转债怎么定价？",
                facts="行业产能过剩，某可转债溢价率 30%。",
            )
        self.assertTrue(ev["abstain"])
        self.assertEqual(ev["direction"], "abstain")
        self.assertEqual(ev["opportunity_hits"], [])
        self.assertEqual(ev["risk_hits"], [])


class ExamSuiteTests(unittest.TestCase):
    def test_missing_exam_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            _seed_blogger(us)
            result = perspective_exam.run_exam(us, "blogger_x")
        self.assertFalse(result["passed"])
        self.assertIn("无考卷", result["reason"])

    def test_empty_exam_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            _seed_blogger(us)
            perspective_exam.save_exam(us, perspective_exam.empty_exam("blogger_x"))
            result = perspective_exam.run_exam(us, "blogger_x")
        self.assertFalse(result["passed"])
        self.assertIn("考卷为空", result["reason"])

    def test_bad_json_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            _seed_blogger(us)
            path = perspective_exam.exam_path(us, "blogger_x")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{not-json", encoding="utf-8")
            with self.assertRaises(ValueError):
                perspective_exam.load_exam(us, "blogger_x")

    def test_incomplete_suite_fails_even_if_cases_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            _seed_blogger(us)
            perspective_exam.add_case(
                us,
                "blogger_x",
                kind="known_answer",
                question="产能过剩时该角色怎么看仓位？",
                facts="行业产能过剩，库存历史高位。",
                expected_direction="risk",
                expected_field="risk_triggers",
                expected_terms=["产能过剩"],
            )
            result = perspective_exam.run_exam(us, "blogger_x")
        self.assertFalse(result["passed"])
        self.assertIn("已知题不足", result["reason"])
        self.assertIn("边题不足", result["reason"])
        self.assertTrue(result["results"][0]["passed"])

    def test_complete_suite_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            _seed_blogger(us)
            _complete_exam(us)
            result = perspective_exam.run_exam(us, "blogger_x")
        self.assertTrue(result["passed"], result["reason"])
        self.assertEqual(result["known_answer"], 2)
        self.assertEqual(result["edge_case"], 1)

    def test_known_answer_fails_when_rule_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            profile = _seed_blogger(us)
            profile["risk_triggers"] = ["别的信号"]
            perspective_lab._save_profile(us, profile, allow_regression=True)
            _complete_exam(us)
            result = perspective_exam.run_exam(us, "blogger_x")
        self.assertFalse(result["passed"])
        ka1 = next(r for r in result["results"] if r["id"] == "ka-1")
        self.assertFalse(ka1["passed"])
        self.assertTrue(any("未命中" in x or "方向" in x for x in ka1["reasons"]))

    def test_known_answer_fails_on_forbidden(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            profile = _seed_blogger(us)
            profile["risk_triggers"] = ["产能过剩后建议加仓"]
            perspective_lab._save_profile(us, profile, allow_regression=True)
            perspective_exam.add_case(
                us,
                "blogger_x",
                kind="known_answer",
                question="q",
                facts="行业产能过剩后建议加仓。",
                expected_direction="risk",
                expected_field="risk_triggers",
                expected_terms=["产能过剩"],
                forbidden=["加仓"],
            )
            scored = perspective_exam.score_case(
                perspective_lab.load_profile(us, "blogger_x"),
                perspective_exam.load_exam(us, "blogger_x")["cases"][0],
            )
        self.assertFalse(scored["passed"])
        self.assertTrue(any("禁语" in x for x in scored["reasons"]))

    def test_edge_case_fails_without_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            profile = _seed_blogger(us)
            profile["honest_boundaries"] = []
            perspective_lab._save_profile(us, profile, allow_regression=True)
            _complete_exam(us)
            result = perspective_exam.run_exam(us, "blogger_x")
        self.assertFalse(result["passed"])
        ec = next(r for r in result["results"] if r["kind"] == "edge_case")
        self.assertFalse(ec["passed"])
        self.assertTrue(any("弃权" in x for x in ec["reasons"]))

    def test_add_rejects_known_answer_without_facts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            _seed_blogger(us)
            with self.assertRaises(ValueError):
                perspective_exam.add_case(
                    us,
                    "blogger_x",
                    kind="known_answer",
                    question="只有题没有事实",
                    facts="  ",
                    expected_direction="risk",
                    expected_field="risk_triggers",
                    expected_terms=["产能过剩"],
                )


class ExamCliTests(unittest.TestCase):
    def test_cli_run_empty_exits_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"FORESIGHT_USERS_DIR": tmp}):
                us = userspace.user_space("tester")
                _seed_blogger(us)
                rc = cli.main(
                    [
                        "perspective",
                        "exam",
                        "run",
                        "--user",
                        "tester",
                        "--perspective",
                        "blogger_x",
                    ]
                )
        self.assertEqual(rc, 1)

    def test_cli_add_list_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"FORESIGHT_USERS_DIR": tmp}):
                us = userspace.user_space("tester")
                _seed_blogger(us)
                self.assertEqual(
                    cli.main(
                        [
                            "perspective",
                            "exam",
                            "add",
                            "--user",
                            "tester",
                            "--perspective",
                            "blogger_x",
                            "--kind",
                            "known_answer",
                            "--question",
                            "产能过剩时该角色怎么看仓位？",
                            "--facts",
                            "行业产能过剩，库存历史高位。",
                            "--direction",
                            "risk",
                            "--field",
                            "risk_triggers",
                            "--term",
                            "产能过剩",
                            "--forbidden",
                            "加仓",
                        ]
                    ),
                    0,
                )
                self.assertEqual(
                    cli.main(
                        [
                            "perspective",
                            "exam",
                            "add",
                            "--user",
                            "tester",
                            "--perspective",
                            "blogger_x",
                            "--kind",
                            "known_answer",
                            "--question",
                            "缩量回踩时有没有机会？",
                            "--facts",
                            "核心股缩量回踩关键均线。",
                            "--direction",
                            "opportunity",
                            "--field",
                            "opportunity_preferences",
                            "--term",
                            "核心股缩量回踩关键均线",
                        ]
                    ),
                    0,
                )
                self.assertEqual(
                    cli.main(
                        [
                            "perspective",
                            "exam",
                            "add",
                            "--user",
                            "tester",
                            "--perspective",
                            "blogger_x",
                            "--kind",
                            "edge_case",
                            "--question",
                            "港股怎么定价？",
                        ]
                    ),
                    0,
                )
                self.assertEqual(
                    cli.main(
                        [
                            "perspective",
                            "exam",
                            "list",
                            "--user",
                            "tester",
                            "--perspective",
                            "blogger_x",
                        ]
                    ),
                    0,
                )
                rc = cli.main(
                    [
                        "perspective",
                        "exam",
                        "run",
                        "--user",
                        "tester",
                        "--perspective",
                        "blogger_x",
                    ]
                )
        self.assertEqual(rc, 0)


class DebateAbstainTests(unittest.TestCase):
    def test_debate_marks_abstain_when_query_hits_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(us, "trend_trader", ptype="trend_trader")
            _seed_blogger(us)
            report, _ = perspective_lab.run_debate(
                us,
                query="可转债怎么定价",
                perspective_ids=["trend_trader", "blogger_x"],
                facts="高位核心放量滞涨。",
                date="2026-08-17",
                save=False,
            )
        self.assertIn("弃权", report)
        self.assertIn("可转债", report)
        self.assertIn("无（已弃权）", report)


if __name__ == "__main__":
    unittest.main()
