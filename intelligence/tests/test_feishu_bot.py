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


def _card_buttons(card: dict) -> list[dict]:
    """从卡片的 ``action`` 元素里取出按钮列表（``_card_text`` 取不到按钮文本/value）。"""
    buttons: list[dict] = []
    for el in card["elements"]:
        if el.get("tag") == "action":
            buttons.extend(el.get("actions", []))
    return buttons


class CardButtonsTests(unittest.TestCase):
    def test_card_has_three_action_buttons(self) -> None:
        buttons = _card_buttons(feishu_bot.render_ask_card(_sample_result()))
        self.assertEqual(len(buttons), 3)
        self.assertTrue(all(b["tag"] == "button" for b in buttons))
        contents = [b["text"]["content"] for b in buttons]
        self.assertTrue(any("深钻" in c for c in contents))
        self.assertTrue(any("换题材" in c for c in contents))
        self.assertTrue(any("证据链" in c for c in contents))

    def test_button_value_payloads(self) -> None:
        buttons = _card_buttons(feishu_bot.render_ask_card(_sample_result()))
        by_action = {b["value"]["action"]: b["value"] for b in buttons}
        self.assertEqual(
            set(by_action),
            {feishu_bot.ACTION_DRILL, feishu_bot.ACTION_THEME, feishu_bot.ACTION_EVIDENCE},
        )
        for value in by_action.values():
            self.assertEqual(value["query"], "液冷渗透率拐点何时到？")
            self.assertEqual(value["theme"], "液冷")

    def test_notice_card_has_no_buttons(self) -> None:
        card = feishu_bot._notice_card("液冷", "检索暂时失败")
        self.assertEqual(_card_buttons(card), [])

    def test_theme_empty_when_unmatched(self) -> None:
        r = _sample_result()
        object.__setattr__(r, "matched_theme", None)
        buttons = _card_buttons(feishu_bot.render_ask_card(r))
        for b in buttons:
            self.assertEqual(b["value"]["theme"], "")


class ParseActionValueTests(unittest.TestCase):
    def test_dict_value_parsed_and_stripped(self) -> None:
        action, query, theme = feishu_bot.parse_action_value(
            {"action": " drill ", "query": " 液冷 ", "theme": " 液冷 "}
        )
        self.assertEqual((action, query, theme), ("drill", "液冷", "液冷"))

    def test_non_dict_returns_empty(self) -> None:
        for value in (None, "drill", ["drill"], 42):
            self.assertEqual(feishu_bot.parse_action_value(value), ("", "", ""))

    def test_missing_fields_default_empty(self) -> None:
        self.assertEqual(feishu_bot.parse_action_value({"action": "theme"}), ("theme", "", ""))


class ActionToastTests(unittest.TestCase):
    def test_known_actions_info_toast(self) -> None:
        for action in (feishu_bot.ACTION_DRILL, feishu_bot.ACTION_THEME, feishu_bot.ACTION_EVIDENCE):
            toast = feishu_bot.action_toast(action)
            self.assertEqual(toast["type"], "info")
            self.assertTrue(toast["content"])

    def test_unknown_action_warning_toast(self) -> None:
        toast = feishu_bot.action_toast("nope")
        self.assertEqual(toast["type"], "warning")
        self.assertIn("未知操作", toast["content"])


class RenderEvidenceCardTests(unittest.TestCase):
    def test_structure_and_title(self) -> None:
        card = feishu_bot.render_evidence_card(_sample_result())
        self.assertEqual(card["header"]["template"], "green")  # PASS
        self.assertIn("证据链 · ", card["header"]["title"]["content"])
        text = _card_text(card)
        self.assertIn("【证据链】", text)
        self.assertIn("成交占比抬升 [S1]", text)
        self.assertNotIn(SUBHEAD, text)

    def test_no_buttons(self) -> None:
        self.assertEqual(_card_buttons(feishu_bot.render_evidence_card(_sample_result())), [])


class RenderThemeSwitchCardTests(unittest.TestCase):
    def test_blue_header_and_guidance(self) -> None:
        card = feishu_bot.render_theme_switch_card("液冷渗透率拐点何时到？", "液冷")
        self.assertEqual(card["header"]["template"], "blue")
        self.assertIn("换题材 · ", card["header"]["title"]["content"])
        text = _card_text(card)
        self.assertIn("液冷", text)
        self.assertIn("回复", text)

    def test_unmatched_theme_placeholder(self) -> None:
        text = _card_text(feishu_bot.render_theme_switch_card("某问题", ""))
        self.assertIn("未匹配到题材", text)


class ComputeActionPayloadTests(unittest.TestCase):
    def _cfg(self) -> feishu_bot.BotConfig:
        return feishu_bot.BotConfig(app_id="a", app_secret="b", reply_format="card")

    def test_empty_query_returns_none(self) -> None:
        self.assertIsNone(
            feishu_bot.compute_action_payload(feishu_bot.ACTION_DRILL, "", "", self._cfg())
        )

    def test_unknown_action_returns_none(self) -> None:
        self.assertIsNone(feishu_bot.compute_action_payload("nope", "液冷", "", self._cfg()))

    def test_theme_does_not_rerun_ask(self) -> None:
        with mock.patch.object(feishu_bot, "_run_ask_workflow") as run:
            msg_type, content, transcript = feishu_bot.compute_action_payload(
                feishu_bot.ACTION_THEME, "液冷渗透率拐点何时到？", "液冷", self._cfg()
            )
        run.assert_not_called()
        self.assertEqual(msg_type, "interactive")
        self.assertEqual(content["header"]["template"], "blue")
        self.assertIn("换题材", transcript)

    def test_drill_reruns_with_modules_and_detail(self) -> None:
        with mock.patch.object(
            feishu_bot, "_run_ask_workflow", return_value=_sample_result()
        ) as run:
            msg_type, content, _ = feishu_bot.compute_action_payload(
                feishu_bot.ACTION_DRILL, "液冷", "液冷", self._cfg()
            )
        self.assertEqual(run.call_args.kwargs, {"use_modules": True, "detail": True})
        self.assertEqual(msg_type, "interactive")
        self.assertIn("header", content)
        self.assertEqual(len(_card_buttons(content)), 3)  # drill 仍是完整卡片，带按钮

    def test_evidence_returns_evidence_card(self) -> None:
        with mock.patch.object(
            feishu_bot, "_run_ask_workflow", return_value=_sample_result()
        ) as run:
            msg_type, content, transcript = feishu_bot.compute_action_payload(
                feishu_bot.ACTION_EVIDENCE, "液冷", "液冷", self._cfg()
            )
        self.assertEqual(run.call_args.kwargs, {})  # evidence 走默认参数
        self.assertEqual(msg_type, "interactive")
        self.assertIn("证据链 · ", content["header"]["title"]["content"])
        self.assertIn("【证据链】", transcript)

    def test_exception_degrades_to_notice_card(self) -> None:
        with mock.patch.object(
            feishu_bot, "_run_ask_workflow", side_effect=RuntimeError("boom")
        ):
            msg_type, content, transcript = feishu_bot.compute_action_payload(
                feishu_bot.ACTION_DRILL, "液冷", "液冷", self._cfg()
            )
        self.assertEqual(msg_type, "interactive")
        self.assertEqual(content["header"]["template"], "grey")
        self.assertIn("检索暂时失败", transcript)


class ParseResourceRefTests(unittest.TestCase):
    def test_image_message(self) -> None:
        ref = feishu_bot.parse_resource_ref(json.dumps({"image_key": "img_v2_abc"}), "image")
        assert ref is not None
        self.assertEqual((ref.kind, ref.file_key, ref.res_type), ("image", "img_v2_abc", "image"))

    def test_image_key_stripped(self) -> None:
        ref = feishu_bot.parse_resource_ref(json.dumps({"image_key": "  k  "}), "image")
        assert ref is not None
        self.assertEqual(ref.file_key, "k")

    def test_png_file_treated_as_image(self) -> None:
        content = json.dumps({"file_key": "file_v3_x", "file_name": "chart.PNG"})
        ref = feishu_bot.parse_resource_ref(content, "file")
        assert ref is not None
        self.assertEqual((ref.kind, ref.res_type, ref.file_name), ("image", "file", "chart.PNG"))

    def test_pdf_file_is_non_image(self) -> None:
        content = json.dumps({"file_key": "file_v3_x", "file_name": "研报.pdf"})
        ref = feishu_bot.parse_resource_ref(content, "file")
        assert ref is not None
        self.assertEqual(ref.kind, "file")
        self.assertEqual(ref.res_type, "file")

    def test_missing_keys_return_none(self) -> None:
        self.assertIsNone(feishu_bot.parse_resource_ref(json.dumps({"foo": "bar"}), "image"))
        self.assertIsNone(feishu_bot.parse_resource_ref(json.dumps({"file_name": "a.png"}), "file"))

    def test_other_types_and_malformed_return_none(self) -> None:
        self.assertIsNone(feishu_bot.parse_resource_ref(json.dumps({"text": "hi"}), "text"))
        self.assertIsNone(feishu_bot.parse_resource_ref("not-json", "image"))
        self.assertIsNone(feishu_bot.parse_resource_ref(None, "image"))
        self.assertIsNone(feishu_bot.parse_resource_ref(json.dumps(["x"]), "image"))


class MultimodalNoticeTests(unittest.TestCase):
    def test_vision_unavailable_mentions_keys(self) -> None:
        msg = feishu_bot.vision_unavailable_notice()
        self.assertIn("视觉模型", msg)
        self.assertIn("--multimodal", msg)

    def test_download_failed_notice(self) -> None:
        self.assertIn("下载失败", feishu_bot.image_download_failed_notice())

    def test_nonimage_file_notice_includes_name(self) -> None:
        self.assertIn("研报.pdf", feishu_bot.nonimage_file_notice("研报.pdf"))
        self.assertIn("后续阶段", feishu_bot.nonimage_file_notice())


class ComputeVisionPayloadTests(unittest.TestCase):
    def _cfg(self, reply_format: str = "card") -> feishu_bot.BotConfig:
        return feishu_bot.BotConfig(app_id="a", app_secret="b", reply_format=reply_format)

    def test_card_path_runs_ask_with_derived_query(self) -> None:
        captured: dict[str, object] = {}

        def fake_ask(query: str, config: feishu_bot.BotConfig, **kwargs: object) -> AskResult:
            captured["query"] = query
            return _sample_result()

        with mock.patch("intelligence.services.vision.describe_image", return_value="液冷 温控"), \
                mock.patch.object(feishu_bot, "_run_ask_workflow", side_effect=fake_ask):
            msg_type, content, transcript = feishu_bot.compute_vision_payload(b"\x89PNG", None, self._cfg())
        self.assertEqual(captured["query"], "液冷 温控")
        self.assertEqual(msg_type, "interactive")
        self.assertIn("header", content)
        self.assertIn("【结论】", transcript)

    def test_no_vision_key_degrades_to_notice_card(self) -> None:
        with mock.patch("intelligence.services.vision.describe_image", return_value=None), \
                mock.patch.object(feishu_bot, "_run_ask_workflow") as run:
            msg_type, content, transcript = feishu_bot.compute_vision_payload(b"x", None, self._cfg())
        run.assert_not_called()
        self.assertEqual(msg_type, "interactive")
        self.assertEqual(content["header"]["template"], "grey")
        self.assertIn("视觉模型", transcript)

    def test_no_vision_key_text_format(self) -> None:
        with mock.patch("intelligence.services.vision.describe_image", return_value=None):
            msg_type, content, _ = feishu_bot.compute_vision_payload(b"x", None, self._cfg("text"))
        self.assertEqual(msg_type, "text")
        self.assertIn("视觉模型", content)

    def test_vision_exception_degrades_to_notice(self) -> None:
        with mock.patch("intelligence.services.vision.describe_image", side_effect=RuntimeError("boom")):
            msg_type, content, _ = feishu_bot.compute_vision_payload(b"x", None, self._cfg("text"))
        self.assertEqual(msg_type, "text")
        self.assertIn("视觉模型", content)


class MultimodalCliTests(unittest.TestCase):
    def _cfg(self, argv: list[str]) -> feishu_bot.BotConfig:
        parser = __import__("argparse").ArgumentParser()
        feishu_bot.add_arguments(parser)
        args = parser.parse_args(["--app-id", "a", "--app-secret", "b", *argv])
        return feishu_bot.build_config(args)

    def test_multimodal_default_off(self) -> None:
        cfg = self._cfg([])
        self.assertFalse(cfg.multimodal)
        self.assertIsNone(cfg.vision_model)
        self.assertEqual(cfg.vision_timeout, 60)

    def test_multimodal_flags_wire_into_config(self) -> None:
        cfg = self._cfg(["--multimodal", "--vision-model", "qwen-vl-max", "--vision-timeout", "30"])
        self.assertTrue(cfg.multimodal)
        self.assertEqual(cfg.vision_model, "qwen-vl-max")
        self.assertEqual(cfg.vision_timeout, 30)


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
