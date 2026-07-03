from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence import cli, userspace
from intelligence.services import perspective_lab


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


class IdSafetyTests(unittest.TestCase):
    def test_valid_ids(self) -> None:
        for pid in ("blogger_x", "buffett", "a.b-c_1"):
            self.assertEqual(perspective_lab.resolve_perspective_id(pid), pid)

    def test_path_traversal_rejected(self) -> None:
        for bad in ("..", ".", "../x", "a/b", "a\\b", "", "  ", "-lead", ".lead", "x" * 65):
            with self.assertRaises(ValueError):
                perspective_lab.resolve_perspective_id(bad)

    def test_paths_stay_inside_userspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            p = perspective_lab.profile_path(us, "blogger_x")
            self.assertTrue(str(p.resolve()).startswith(str(us.root.resolve())))


class InitTests(unittest.TestCase):
    def test_init_creates_dirs_and_default_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            path, profile = perspective_lab.init_perspective(us, "blogger_x", display_name="某博主", ptype="blogger")
            self.assertTrue(path.is_file())
            self.assertTrue((perspective_lab.articles_dir(us, "blogger_x") / "raw").is_dir())
            self.assertEqual(profile["schema_version"], 1)
            self.assertEqual(profile["display_name"], "某博主")
            self.assertEqual(profile["confidence"]["profile_confidence"], "low")
            self.assertEqual(profile["market_lenses"], [])  # blogger 需 ingest 训练

    def test_init_builtin_type_has_lenses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            _, profile = perspective_lab.init_perspective(us, "trend_trader", ptype="trend_trader")
            self.assertTrue(profile["market_lenses"])
            self.assertTrue(profile["falsification_style"])

    def test_init_existing_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(us, "blogger_x")
            with self.assertRaises(ValueError):
                perspective_lab.init_perspective(us, "blogger_x")

    def test_bad_type_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            with self.assertRaises(ValueError):
                perspective_lab.init_perspective(us, "x", ptype="wizard")


class IngestTests(unittest.TestCase):
    def _write_article(self, tmp: str, text: str = "上证指数缩量，AI硬件核心股承接良好。") -> Path:
        p = Path(tmp) / "article.md"
        p.write_text(text, encoding="utf-8")
        return p

    def test_ingest_writes_manifest_and_raw(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(us, "blogger_x")
            art = self._write_article(tmp)
            res = perspective_lab.ingest_article(us, "blogger_x", art, title="某篇复盘", date="2026-07-03")
            self.assertFalse(res["duplicate"])
            self.assertTrue(res["article_id"].startswith("pa-"))
            self.assertTrue(Path(res["raw_path"]).is_file())
            manifest = perspective_lab._read_manifest(perspective_lab.manifest_path(us, "blogger_x"))
            self.assertEqual(len(manifest), 1)
            self.assertEqual(manifest[0]["schema_version"], 1)
            self.assertIn("上证指数", manifest[0]["market_context"]["mentioned_indices"])

    def test_ingest_dedup_by_content_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(us, "blogger_x")
            art = self._write_article(tmp)
            perspective_lab.ingest_article(us, "blogger_x", art, title="A", date="2026-07-03")
            res2 = perspective_lab.ingest_article(us, "blogger_x", art, title="B", date="2026-07-03")
            self.assertTrue(res2["duplicate"])
            manifest = perspective_lab._read_manifest(perspective_lab.manifest_path(us, "blogger_x"))
            self.assertEqual(len(manifest), 1)

    def test_low_sample_confidence_until_three_articles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(us, "blogger_x")
            for i in range(3):
                p = Path(tmp) / f"a{i}.md"
                p.write_text(f"第 {i} 篇：创业板指走强。", encoding="utf-8")
                perspective_lab.ingest_article(us, "blogger_x", p, title=f"t{i}", date="2026-07-03")
                profile = perspective_lab.load_profile(us, "blogger_x")
                expected = "low" if i < 2 else "medium"
                self.assertEqual(profile["confidence"]["profile_confidence"], expected)

    def test_missing_profile_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            art = self._write_article(tmp)
            with self.assertRaises(FileNotFoundError):
                perspective_lab.ingest_article(us, "nobody", art, title="x")

    def test_missing_article_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(us, "blogger_x")
            with self.assertRaises(FileNotFoundError):
                perspective_lab.ingest_article(us, "blogger_x", Path(tmp) / "nope.md", title="x")
            self.assertFalse(perspective_lab.manifest_path(us, "blogger_x").exists())
            profile = perspective_lab.load_profile(us, "blogger_x")
            self.assertEqual(profile["confidence"]["article_count"], 0)


class DebateTests(unittest.TestCase):
    def _setup_roles(self, us: userspace.UserSpace) -> None:
        perspective_lab.init_perspective(us, "trend_trader", ptype="trend_trader")
        perspective_lab.init_perspective(us, "value_investor", ptype="value_investor")

    def test_debate_report_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            self._setup_roles(us)
            facts = "高位核心放量滞涨；估值透支多年成长；成交额维持高位。"
            report, record = perspective_lab.run_debate(
                us, query="明天市场怎么看", perspective_ids=["trend_trader", "value_investor"],
                facts=facts, date="2026-07-03",
            )
            self.assertIn("## 1. 硬事实底座", report)
            self.assertIn("## 2. 角色独立判断（以下均为角色解释，不是事实）", report)
            self.assertIn("反证信号清单", report)
            self.assertIn("## 4. 裁判合议", report)
            self.assertIn("## 5. 可证伪假设", report)
            # 各角色命中各自不同的风险信号 → 有分歧，不触发退化提示
            self.assertFalse(record["degenerate"])
            self.assertIn("高位核心放量滞涨", record["divergent_hits"])
            self.assertIn("估值透支多年成长", record["divergent_hits"])
            # 落档：debates.jsonl 带 schema_version
            lines = perspective_lab.debates_path(us).read_text(encoding="utf-8").splitlines()
            self.assertEqual(json.loads(lines[0])["schema_version"], 1)

    def test_debate_degenerate_warning_when_no_divergence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            self._setup_roles(us)
            report, record = perspective_lab.run_debate(
                us, query="q", perspective_ids=["trend_trader", "value_investor"],
                facts="今日无信号词命中。", date="2026-07-03", save=False,
            )
            self.assertTrue(record["degenerate"])
            self.assertIn("退化提示", report)
            self.assertFalse(perspective_lab.debates_path(us).exists())  # no-save 不落盘

    def test_debate_marks_role_opinions_not_facts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            self._setup_roles(us)
            report, _ = perspective_lab.run_debate(
                us, query="q", perspective_ids=["trend_trader", "value_investor"],
                facts="高位核心放量滞涨。", date="2026-07-03", save=False,
            )
            facts_part = report.split("## 2.")[0]
            roles_part = report.split("## 2.")[1]
            self.assertIn("以下为事实，未经角色改写", facts_part)
            self.assertIn("不是事实", "## 2." + roles_part.split("\n")[0])

    def test_debate_low_sample_blogger_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            self._setup_roles(us)
            perspective_lab.init_perspective(us, "blogger_x", ptype="blogger")
            report, _ = perspective_lab.run_debate(
                us, query="q", perspective_ids=["trend_trader", "blogger_x"],
                facts="高位核心放量滞涨。", date="2026-07-03", save=False,
            )
            self.assertIn("样本不足，只能作为候选视角", report)

    def test_debate_requires_facts_and_two_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            self._setup_roles(us)
            with self.assertRaises(ValueError):
                perspective_lab.run_debate(us, query="q", perspective_ids=["trend_trader"], facts="x")
            with self.assertRaises(ValueError):
                perspective_lab.run_debate(
                    us, query="q", perspective_ids=["trend_trader", "value_investor"], facts="  ",
                )

    def test_debate_missing_profile_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(us, "trend_trader", ptype="trend_trader")
            with self.assertRaises(FileNotFoundError):
                perspective_lab.run_debate(
                    us, query="q", perspective_ids=["trend_trader", "ghost"], facts="x",
                )


class CliParseabilityTests(unittest.TestCase):
    def test_perspective_subcommands_parse(self) -> None:
        parser = cli.build_parser()
        args = parser.parse_args(
            ["perspective", "debate", "--query", "q", "--perspective", "a", "--perspective", "b", "--facts", "f"]
        )
        self.assertEqual(args.perspectives, ["a", "b"])
        for argv in (
            ["perspective", "init", "--id", "blogger_x"],
            ["perspective", "ingest", "--perspective", "blogger_x", "--input", "a.md", "--title", "t"],
            ["perspective", "profile", "--perspective", "blogger_x"],
        ):
            parser.parse_args(argv)


if __name__ == "__main__":
    unittest.main()
