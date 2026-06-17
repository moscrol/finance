from __future__ import annotations

import json
import unittest
from unittest import mock

from intelligence.chat import feishu_bot
from intelligence.services.ask import SUBHEAD, AskResult


def _sample_result() -> AskResult:
    r = AskResult(
        query="液冷渗透率拐点何时到？",
        trade_date="2026-06-16",
        matched_theme="液冷",
        candidate_tier="T1",
        priority_score=0.8,
        found_market=True,
        found_graph=True,
    )
    r.sections["结论"] = ["液冷渗透率加速 [S1][G2]"]
    r.sections["证据链"] = [SUBHEAD + "盘面", "成交占比抬升 [S1]"]
    r.sections["分歧反证"] = []
    r.sections["后续验证点"] = ["Q3 机柜招标 [R1]"]
    r.sections["交易含义"] = ["关注温控龙头 [G2]"]
    r.sections["引用来源"] = ["[S1] market exports", "[G2] wiki/relations", "[R1] theme-radar module"]
    return r


class ExtractTextTests(unittest.TestCase):
    def test_plain_text(self) -> None:
        content = json.dumps({"text": "液冷渗透率拐点何时到？"})
        self.assertEqual(feishu_bot.extract_text(content, "text"), "液冷渗透率拐点何时到？")

    def test_text_stripped_and_empty_is_none(self) -> None:
        self.assertEqual(feishu_bot.extract_text(json.dumps({"text": "  hi  "}), "text"), "hi")
        self.assertIsNone(feishu_bot.extract_text(json.dumps({"text": "   "}), "text"))

    def test_post_rich_text_joins_text_segments(self) -> None:
        content = json.dumps(
            {
                "title": "t",
                "content": [
                    [{"tag": "text", "text": "AI"}, {"tag": "a", "href": "x", "text": "link"}],
                    [{"tag": "text", "text": "算力"}],
                ],
            }
        )
        self.assertEqual(feishu_bot.extract_text(content, "post"), "AI 算力")

    def test_non_text_types_return_none(self) -> None:
        for mtype in ("image", "audio", "file", "sticker"):
            self.assertIsNone(feishu_bot.extract_text(json.dumps({"image_key": "x"}), mtype))

    def test_malformed_content_returns_none(self) -> None:
        self.assertIsNone(feishu_bot.extract_text("not-json", "text"))
        self.assertIsNone(feishu_bot.extract_text(None, "text"))
        self.assertIsNone(feishu_bot.extract_text(json.dumps(["list"]), "text"))


class ComposeReplyTests(unittest.TestCase):
    def test_echo_text_verbatim(self) -> None:
        self.assertEqual(feishu_bot.compose_reply("你好", "text"), "你好")

    def test_echo_with_prefix(self) -> None:
        self.assertEqual(feishu_bot.compose_reply("你好", "text", prefix="[echo] "), "[echo] 你好")

    def test_non_text_gets_friendly_notice(self) -> None:
        reply = feishu_bot.compose_reply(None, "image")
        self.assertIn("image", reply)
        self.assertIn("回声", reply)


class CredentialResolutionTests(unittest.TestCase):
    def test_env_takes_priority(self) -> None:
        with mock.patch.dict(
            "os.environ", {"FEISHU_APP_ID": "cli_env", "FEISHU_APP_SECRET": "sec_env"}, clear=False
        ):
            self.assertEqual(feishu_bot.resolve_credentials(), ("cli_env", "sec_env"))

    def test_explicit_args_beat_env(self) -> None:
        with mock.patch.dict(
            "os.environ", {"FEISHU_APP_ID": "cli_env", "FEISHU_APP_SECRET": "sec_env"}, clear=False
        ):
            self.assertEqual(feishu_bot.resolve_credentials("cli_arg", "sec_arg"), ("cli_arg", "sec_arg"))

    def test_config_file_fallback(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True), mock.patch.object(
            feishu_bot, "_load_config_file", return_value={"app_id": "cli_cfg", "app_secret": "sec_cfg"}
        ):
            self.assertEqual(feishu_bot.resolve_credentials(), ("cli_cfg", "sec_cfg"))

    def test_missing_raises_systemexit(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True), mock.patch.object(
            feishu_bot, "_load_config_file", return_value={}
        ):
            with self.assertRaises(SystemExit):
                feishu_bot.resolve_credentials()


class CliWiringTests(unittest.TestCase):
    def test_build_config_from_args(self) -> None:
        parser = __import__("argparse").ArgumentParser()
        feishu_bot.add_arguments(parser)
        args = parser.parse_args(["--app-id", "a", "--app-secret", "b", "--prefix", "P:"])
        cfg = feishu_bot.build_config(args)
        self.assertEqual((cfg.app_id, cfg.app_secret, cfg.prefix), ("a", "b", "P:"))

    def test_cli_registers_feishu_bot_subcommand(self) -> None:
        from intelligence import cli

        parser = cli.build_parser()
        args = parser.parse_args(["feishu-bot", "--app-id", "a", "--app-secret", "b"])
        self.assertEqual(args.func, cli.cmd_feishu_bot)


class NonTextNoticeTests(unittest.TestCase):
    def test_mentions_type_and_text_only(self) -> None:
        msg = feishu_bot.nontext_notice("image")
        self.assertIn("image", msg)
        self.assertIn("文本", msg)


class RenderAskReplyTests(unittest.TestCase):
    def test_six_sections_and_citations_present(self) -> None:
        out = feishu_bot.render_ask_reply(_sample_result())
        for name in ("结论", "证据链", "分歧反证", "后续验证点", "交易含义", "引用来源"):
            self.assertIn(f"【{name}】", out)
        for tag in ("[S1]", "[G2]", "[R1]"):
            self.assertIn(tag, out)

    def test_subhead_sentinel_stripped_and_rendered(self) -> None:
        out = feishu_bot.render_ask_reply(_sample_result())
        self.assertNotIn(SUBHEAD, out)
        self.assertIn("· 盘面", out)

    def test_empty_section_renders_placeholder(self) -> None:
        out = feishu_bot.render_ask_reply(_sample_result())
        self.assertIn("（无）", out)

    def test_header_has_query_and_theme(self) -> None:
        out = feishu_bot.render_ask_reply(_sample_result())
        self.assertIn("液冷渗透率拐点何时到？", out)
        self.assertIn("液冷", out)

    def test_truncation_caps_length(self) -> None:
        r = _sample_result()
        r.sections["结论"] = ["x" * 5000]
        out = feishu_bot.render_ask_reply(r, max_chars=200)
        self.assertLessEqual(len(out), 200)
        self.assertIn("截断", out)


def _card_text(card: dict) -> str:
    """把卡片所有元素里的文本拼成一个字符串，便于断言内容存在。"""
    parts: list[str] = [card["header"]["title"]["content"]]
    for el in card["elements"]:
        if "text" in el and isinstance(el["text"], dict):
            parts.append(el["text"].get("content", ""))
        for sub in el.get("elements", []) or []:
            parts.append(sub.get("content", ""))
    return "\n".join(parts)


class RenderAskCardTests(unittest.TestCase):
    def test_header_template_by_status(self) -> None:
        passing = _sample_result()
        self.assertEqual(passing.status, "PASS")
        self.assertEqual(feishu_bot.render_ask_card(passing)["header"]["template"], "green")

        warn = _sample_result()
        warn.found_graph = False  # market only -> WARN
        self.assertEqual(warn.status, "WARN")
        self.assertEqual(feishu_bot.render_ask_card(warn)["header"]["template"], "orange")

        fail = _sample_result()
        fail.found_market = False
        fail.found_graph = False
        self.assertEqual(fail.status, "FAIL")
        self.assertEqual(feishu_bot.render_ask_card(fail)["header"]["template"], "grey")

    def test_header_title_has_query(self) -> None:
        card = feishu_bot.render_ask_card(_sample_result())
        self.assertEqual(card["header"]["title"]["tag"], "plain_text")
        self.assertIn("液冷渗透率拐点何时到？", card["header"]["title"]["content"])

    def test_summary_line_has_theme_date_status(self) -> None:
        card = feishu_bot.render_ask_card(_sample_result())
        summary = card["elements"][0]["text"]["content"]
        self.assertIn("液冷", summary)
        self.assertIn("2026-06-16", summary)
        self.assertIn("PASS", summary)

    def test_six_sections_and_citations_present(self) -> None:
        text = _card_text(feishu_bot.render_ask_card(_sample_result()))
        for name in ("结论", "证据链", "分歧反证", "后续验证点", "交易含义", "引用来源"):
            self.assertIn(f"【{name}】", text)
        for tag in ("[S1]", "[G2]", "[R1]"):
            self.assertIn(tag, text)

    def test_subhead_sentinel_stripped(self) -> None:
        text = _card_text(feishu_bot.render_ask_card(_sample_result()))
        self.assertNotIn(SUBHEAD, text)
        self.assertIn("**盘面**", text)

    def test_card_title_capped(self) -> None:
        r = _sample_result()
        object.__setattr__(r, "query", "液" * 500)
        title = feishu_bot.render_ask_card(r)["header"]["title"]["content"]
        self.assertLessEqual(len(title), feishu_bot._CARD_TITLE_MAX)

    def test_truncation_caps_body_and_adds_note(self) -> None:
        r = _sample_result()
        r.sections["结论"] = ["x" * 5000]
        card = feishu_bot.render_ask_card(r, max_chars=200)
        body_len = sum(
            len(el["text"]["content"])
            for el in card["elements"]
            if "text" in el and isinstance(el["text"], dict)
        )
        self.assertLessEqual(body_len, 200 + 50)  # summary line + capped sections
        note_texts = [
            sub["content"]
            for el in card["elements"]
            if el.get("tag") == "note"
            for sub in el.get("elements", [])
        ]
        self.assertTrue(any("截断" in t for t in note_texts))


class ComputeAskPayloadTests(unittest.TestCase):
    def test_card_format_returns_interactive(self) -> None:
        with mock.patch.object(feishu_bot, "_run_ask_workflow", return_value=_sample_result()):
            cfg = feishu_bot.BotConfig(app_id="a", app_secret="b", reply_format="card")
            msg_type, content, transcript = feishu_bot.compute_ask_payload("液冷", cfg)
        self.assertEqual(msg_type, "interactive")
        self.assertIsInstance(content, dict)
        self.assertIn("header", content)
        self.assertIn("【结论】", transcript)  # transcript is always plain text

    def test_text_format_returns_text(self) -> None:
        with mock.patch.object(feishu_bot, "_run_ask_workflow", return_value=_sample_result()):
            cfg = feishu_bot.BotConfig(app_id="a", app_secret="b", reply_format="text")
            msg_type, content, transcript = feishu_bot.compute_ask_payload("液冷", cfg)
        self.assertEqual(msg_type, "text")
        self.assertIsInstance(content, str)
        self.assertEqual(content, transcript)
        self.assertIn("【结论】", content)

    def test_exception_card_degrades_to_notice_card(self) -> None:
        with mock.patch.object(feishu_bot, "_run_ask_workflow", side_effect=RuntimeError("boom")):
            cfg = feishu_bot.BotConfig(app_id="a", app_secret="b", reply_format="card")
            msg_type, content, transcript = feishu_bot.compute_ask_payload("液冷", cfg)
        self.assertEqual(msg_type, "interactive")
        self.assertEqual(content["header"]["template"], "grey")
        self.assertIn("检索暂时失败", _card_text(content))
        self.assertIn("检索暂时失败", transcript)

    def test_exception_text_degrades_to_notice_text(self) -> None:
        with mock.patch.object(feishu_bot, "_run_ask_workflow", side_effect=RuntimeError("boom")):
            cfg = feishu_bot.BotConfig(app_id="a", app_secret="b", reply_format="text")
            msg_type, content, _ = feishu_bot.compute_ask_payload("液冷", cfg)
        self.assertEqual(msg_type, "text")
        self.assertIn("检索暂时失败", content)


class AnswerTextTests(unittest.TestCase):
    def test_renders_ask_result(self) -> None:
        with mock.patch.object(feishu_bot, "_run_ask_workflow", return_value=_sample_result()):
            cfg = feishu_bot.BotConfig(app_id="a", app_secret="b")
            out = feishu_bot.answer_text("液冷", cfg)
        self.assertIn("【结论】", out)
        self.assertIn("[S1]", out)

    def test_passes_query_and_config_through(self) -> None:
        captured: dict[str, object] = {}

        def fake(query: str, config: feishu_bot.BotConfig) -> AskResult:
            captured["query"] = query
            captured["modules"] = config.ask_use_modules
            return _sample_result()

        with mock.patch.object(feishu_bot, "_run_ask_workflow", side_effect=fake):
            cfg = feishu_bot.BotConfig(app_id="a", app_secret="b", ask_use_modules=True)
            feishu_bot.answer_text("AI 算力", cfg)
        self.assertEqual(captured["query"], "AI 算力")
        self.assertTrue(captured["modules"])

    def test_exception_degrades_to_friendly_notice(self) -> None:
        with mock.patch.object(feishu_bot, "_run_ask_workflow", side_effect=RuntimeError("boom")):
            cfg = feishu_bot.BotConfig(app_id="a", app_secret="b")
            out = feishu_bot.answer_text("液冷", cfg)
        self.assertIn("检索暂时失败", out)
        self.assertIn("RuntimeError", out)


class BotConfigCliTests(unittest.TestCase):
    def _cfg(self, argv: list[str]) -> feishu_bot.BotConfig:
        parser = __import__("argparse").ArgumentParser()
        feishu_bot.add_arguments(parser)
        args = parser.parse_args(["--app-id", "a", "--app-secret", "b", *argv])
        return feishu_bot.build_config(args)

    def test_default_mode_is_ask(self) -> None:
        self.assertEqual(self._cfg([]).mode, "ask")

    def test_echo_flag_switches_mode(self) -> None:
        self.assertEqual(self._cfg(["--echo"]).mode, "echo")

    def test_ask_modules_default_off(self) -> None:
        self.assertFalse(self._cfg([]).ask_use_modules)

    def test_reply_format_default_card(self) -> None:
        self.assertEqual(self._cfg([]).reply_format, "card")

    def test_reply_format_text_flag(self) -> None:
        self.assertEqual(self._cfg(["--reply-format", "text"]).reply_format, "text")

    def test_ask_flags_wire_into_config(self) -> None:
        cfg = self._cfg(
            ["--ask-modules", "--ask-top-companies", "5", "--ask-max-chars", "999", "--kb-wiki", "/tmp/w"]
        )
        self.assertTrue(cfg.ask_use_modules)
        self.assertEqual(cfg.ask_top_companies, 5)
        self.assertEqual(cfg.ask_max_chars, 999)
        self.assertEqual(cfg.kb_wiki, "/tmp/w")


class NoDuckdbImportTests(unittest.TestCase):
    def test_bot_and_ask_import_without_duckdb(self) -> None:
        import subprocess
        import sys
        from pathlib import Path

        root = Path(feishu_bot.__file__).resolve().parents[2]
        code = (
            "import sys\n"
            "import intelligence.chat.feishu_bot\n"
            "import intelligence.services.ask\n"
            "import intelligence.workflows.ask\n"
            "assert 'duckdb' not in sys.modules, 'duckdb imported at module load'\n"
            "print('OK')\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code], cwd=str(root), capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
