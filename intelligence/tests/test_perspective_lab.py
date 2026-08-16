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


class RuntimePerspectiveTests(unittest.TestCase):
    def test_neutral_context_excludes_kol_and_personal_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = perspective_lab.build_runtime_context(
                _us(tmp),
                mode="neutral",
                perspective_ids=[],
                query="今天市场怎么样",
            )

        self.assertIn("数据中立", context.prompt)
        self.assertIn("不得调用或模拟任何 KOL", context.prompt)
        self.assertIn("个人金融记忆", context.prompt)
        self.assertEqual(context.answer_header().splitlines()[0], "当前视角：数据中立")
        self.assertIn("数据提供方", context.answer_header())
        self.assertNotIn("Provider", context.answer_header())

    def test_single_context_retrieves_only_selected_kol_article(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(
                us, "fengyuan94", display_name="风远94", ptype="blogger"
            )
            perspective_lab.init_perspective(
                us, "other", display_name="其他博主", ptype="blogger"
            )
            fengyuan = Path(tmp) / "fengyuan.md"
            fengyuan.write_text("AI硬件第一次分歧时观察核心股成交承接。", encoding="utf-8")
            other = Path(tmp) / "other.md"
            other.write_text("AI硬件只看长期估值。", encoding="utf-8")
            perspective_lab.ingest_article(
                us,
                "fengyuan94",
                fengyuan,
                title="AI硬件复盘",
                date="2026-07-01",
            )
            perspective_lab.ingest_article(
                us,
                "other",
                other,
                title="其他观点",
                date="2026-07-01",
            )

            context = perspective_lab.build_runtime_context(
                us,
                mode="single",
                perspective_ids=["fengyuan94"],
                query="AI硬件核心股怎么看",
            )

        self.assertIn("风远94", context.prompt)
        self.assertIn("成交承接", context.prompt)
        self.assertNotIn("其他博主", context.prompt)
        self.assertNotIn("长期估值", context.prompt)
        self.assertIn("该视角未知", context.prompt)

    def test_single_context_carries_full_cognitive_frame_and_discipline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(us, "kol_fengyuan", ptype="kol_fengyuan")
            context = perspective_lab.build_runtime_context(
                us,
                mode="single",
                perspective_ids=["kol_fengyuan"],
                query="行情怎么看",
            )

        # 画像认知字段完整注入（此前缺证据层级/推理模板/反模式 → 视角名存实薄）
        self.assertIn("证据层级", context.prompt)
        self.assertIn("盘面资金选择", context.prompt)  # evidence_hierarchy 首项
        self.assertIn("推理模板", context.prompt)
        self.assertIn("先定周期位置再谈标的", context.prompt)
        self.assertIn("反模式", context.prompt)
        # 证据纪律：首选证据缺失必须显式声明，不得降格为通用研究结论
        self.assertIn("首选证据", context.prompt)
        self.assertIn("不得因此把视角输出降格为通用研究结论", context.prompt)
        # 种子画像无原文 ≠ 视角未知：镜头已在，不能用「未知」把框架冲掉
        self.assertIn("未召回相关文章", context.prompt)
        self.assertNotIn("未召回相关文章；该视角未知", context.prompt)
        self.assertIn("原文未覆盖的问题必须写“该视角未知”", context.prompt)

    def test_empty_blogger_without_articles_stays_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(
                us, "empty_blogger", display_name="空博主", ptype="blogger"
            )
            context = perspective_lab.build_runtime_context(
                us,
                mode="single",
                perspective_ids=["empty_blogger"],
                query="行情怎么看",
            )

        self.assertIn("未召回相关文章；该视角未知", context.prompt)

    def test_compare_context_keeps_neutral_and_kol_sections_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(
                us, "fengyuan94", display_name="风远94", ptype="blogger"
            )
            perspective_lab.init_perspective(
                us, "other", display_name="其他博主", ptype="blogger"
            )
            context = perspective_lab.build_runtime_context(
                us,
                mode="compare",
                perspective_ids=["fengyuan94", "other"],
                query="复盘",
            )

        self.assertIn("先单列“数据中立”", context.prompt)
        self.assertIn("视角冲突", context.prompt)
        self.assertIn("风远94", context.prompt)
        self.assertIn("其他博主", context.prompt)
        self.assertIn("多视角并列", context.answer_header())

    def test_article_bm25_orders_more_relevant_article_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(us, "blogger_x", ptype="blogger")
            weak = Path(tmp) / "weak.md"
            weak.write_text("今天市场平稳，结尾提到一次液冷。", encoding="utf-8")
            strong = Path(tmp) / "strong.md"
            strong.write_text(
                "液冷服务器需求提升，液冷供应链扩产，液冷订单值得跟踪。",
                encoding="utf-8",
            )
            perspective_lab.ingest_article(
                us, "blogger_x", weak, title="弱相关", date="2026-07-01"
            )
            perspective_lab.ingest_article(
                us, "blogger_x", strong, title="强相关", date="2026-07-02"
            )

            snippets = perspective_lab.retrieve_article_snippets(
                us, "blogger_x", "液冷服务器订单"
            )

        self.assertEqual(snippets[0]["title"], "强相关")
        self.assertIn("液冷服务器", snippets[0]["excerpt"])

    def test_article_retrieval_rejects_manifest_path_outside_userspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(us, "blogger_x", ptype="blogger")
            outside = Path(tmp) / "outside.md"
            outside.write_text("不应读取的液冷内容", encoding="utf-8")
            perspective_lab.manifest_path(us, "blogger_x").write_text(
                json.dumps(
                    {
                        "title": "越界文件",
                        "raw_path": str(outside),
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            snippets = perspective_lab.retrieve_article_snippets(
                us, "blogger_x", "液冷"
            )

        self.assertEqual(snippets, [])

    def test_runtime_selection_rejects_invalid_shape_and_missing_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            with self.assertRaisesRegex(ValueError, "不能选择 KOL"):
                perspective_lab.validate_runtime_selection(
                    us, "neutral", ["fengyuan94"]
                )
            with self.assertRaisesRegex(ValueError, "必须选择 1 个"):
                perspective_lab.validate_runtime_selection(us, "single", [])
            with self.assertRaises(FileNotFoundError):
                perspective_lab.validate_runtime_selection(
                    us, "single", ["missing"]
                )


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

    def test_debate_rejects_duplicate_perspectives(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            self._setup_roles(us)
            with self.assertRaises(ValueError):
                perspective_lab.run_debate(
                    us, query="q", perspective_ids=["trend_trader", "trend_trader"], facts="x",
                )

    def test_debate_id_varies_with_facts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            self._setup_roles(us)
            ids = []
            for facts in ("高位核心放量滞涨。", "估值透支多年成长。"):
                _, record = perspective_lab.run_debate(
                    us, query="q", perspective_ids=["trend_trader", "value_investor"],
                    facts=facts, date="2026-07-03", save=False,
                )
                ids.append(record["debate_id"])
            self.assertNotEqual(ids[0], ids[1])

    def test_debate_missing_profile_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(us, "trend_trader", ptype="trend_trader")
            with self.assertRaises(FileNotFoundError):
                perspective_lab.run_debate(
                    us, query="q", perspective_ids=["trend_trader", "ghost"], facts="x",
                )


class GroundedPerspectiveInjectionTests(unittest.TestCase):
    def test_active_perspective_prompt_gates_by_mode(self) -> None:
        import os
        from unittest import mock

        from intelligence.services import ask_synthesis
        from intelligence.services.ask_types import AskOptions

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"FORESIGHT_USERS_DIR": tmp}):
                us = userspace.user_space("tester")
                perspective_lab.init_perspective(us, "kol_fengyuan", ptype="kol_fengyuan")
                neutral = ask_synthesis._active_perspective_prompt(
                    AskOptions(query="行情怎么看", user="tester")
                )
                single = ask_synthesis._active_perspective_prompt(
                    AskOptions(
                        query="行情怎么看",
                        user="tester",
                        perspective_mode="single",
                        perspective_ids=("kol_fengyuan",),
                    )
                )
                missing = ask_synthesis._active_perspective_prompt(
                    AskOptions(
                        query="行情怎么看",
                        user="tester",
                        perspective_mode="single",
                        perspective_ids=("ghost",),
                    )
                )

        self.assertEqual(neutral, "")  # neutral 不改变 grounded 行为
        self.assertIn("风远框架视角", single)
        self.assertIn("证据层级", single)
        self.assertEqual(missing, "")  # profile 缺失降级为无视角，不炸整轮回答


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


class ContradictionAndBoundaryTests(unittest.TestCase):
    """contradictions / honest_boundaries：人工编辑字段，默认空，注入后才进 prompt。"""

    def test_default_profile_has_empty_meta_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            _, profile = perspective_lab.init_perspective(us, "blogger_x")
            self.assertEqual(profile["contradictions"], [])
            self.assertEqual(profile["honest_boundaries"], [])

    def test_prompt_injects_contradictions_and_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(us, "blogger_x", display_name="某博主")
            profile = perspective_lab.load_profile(us, "blogger_x")
            profile["contradictions"] = ["06-30 提示缩量风险；07-15 同位置看多（同日历周期）"]
            profile["honest_boundaries"] = ["未覆盖可转债与港股题材"]
            perspective_lab._save_profile(us, profile)

            prompt = perspective_lab._profile_prompt(profile, [])

        self.assertIn("已知矛盾", prompt)
        self.assertIn("06-30 提示缩量风险", prompt)
        self.assertIn("不得抹平", prompt)
        self.assertIn("诚实边界", prompt)
        self.assertIn("未覆盖可转债与港股题材", prompt)
        self.assertIn("不得输出其观点", prompt)

    def test_prompt_omits_empty_meta_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(us, "blogger_x")
            profile = perspective_lab.load_profile(us, "blogger_x")
            prompt = perspective_lab._profile_prompt(profile, [])
        self.assertNotIn("已知矛盾", prompt)
        self.assertNotIn("诚实边界", prompt)

    def test_render_profile_text_lists_meta_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            us = _us(tmp)
            perspective_lab.init_perspective(us, "blogger_x")
            profile = perspective_lab.load_profile(us, "blogger_x")
            profile["contradictions"] = ["前空后多，同周期同位置"]
            perspective_lab._save_profile(us, profile)
            text = perspective_lab.render_profile_text(profile)
        self.assertIn("## 已知矛盾", text)
        self.assertIn("前空后多，同周期同位置", text)
        self.assertIn("## 诚实边界", text)
        self.assertIn("- 无", text)  # 空 boundaries 显式渲染「无」


if __name__ == "__main__":
    unittest.main()
