from __future__ import annotations

import json
import unittest
from unittest import mock

from intelligence.chat import feishu_bot


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


if __name__ == "__main__":
    unittest.main()
