from __future__ import annotations

import unittest
from unittest import mock

from intelligence.services import vision
from intelligence.services.llm_refine import LLMProvider


# 各格式的最小 magic-bytes 样本（仅用于 sniff，不是合法完整图片）。
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 8
_GIF = b"GIF89a" + b"\x00" * 8
_WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 4
_BMP = b"BM" + b"\x00" * 10


class SniffImageMimeTests(unittest.TestCase):
    def test_known_formats(self) -> None:
        self.assertEqual(vision.sniff_image_mime(_PNG), "image/png")
        self.assertEqual(vision.sniff_image_mime(_JPEG), "image/jpeg")
        self.assertEqual(vision.sniff_image_mime(_GIF), "image/gif")
        self.assertEqual(vision.sniff_image_mime(_WEBP), "image/webp")
        self.assertEqual(vision.sniff_image_mime(_BMP), "image/bmp")

    def test_empty_and_unknown_return_none(self) -> None:
        self.assertIsNone(vision.sniff_image_mime(b""))
        self.assertIsNone(vision.sniff_image_mime(b"not-an-image"))


class DetectVisionProviderTests(unittest.TestCase):
    def test_no_env_returns_none(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(vision.detect_vision_provider())

    def test_vision_api_key_defaults_to_gpt4o_mini(self) -> None:
        with mock.patch.dict("os.environ", {"VISION_API_KEY": "k"}, clear=True):
            provider = vision.detect_vision_provider()
        self.assertIsInstance(provider, LLMProvider)
        assert provider is not None
        self.assertEqual(provider.api_key, "k")
        self.assertEqual(provider.model, "gpt-4o-mini")
        self.assertEqual(provider.base_url, "https://api.openai.com/v1")

    def test_vision_base_url_and_model_overrides(self) -> None:
        env = {
            "VISION_API_KEY": "k",
            "VISION_BASE_URL": "https://gw.example.com/v1",
            "VISION_MODEL": "my-vl",
        }
        with mock.patch.dict("os.environ", env, clear=True):
            provider = vision.detect_vision_provider()
        assert provider is not None
        self.assertEqual(provider.base_url, "https://gw.example.com/v1")
        self.assertEqual(provider.model, "my-vl")

    def test_qwen_key_maps_to_qwen_vl(self) -> None:
        with mock.patch.dict("os.environ", {"QWEN_API_KEY": "k"}, clear=True):
            provider = vision.detect_vision_provider()
        assert provider is not None
        self.assertEqual(provider.model, "qwen-vl-plus")
        self.assertIn("dashscope", provider.base_url)

    def test_glm_key_maps_to_glm4v(self) -> None:
        with mock.patch.dict("os.environ", {"GLM_API_KEY": "k"}, clear=True):
            provider = vision.detect_vision_provider()
        assert provider is not None
        self.assertEqual(provider.model, "glm-4v-flash")

    def test_generic_llm_api_key_reused(self) -> None:
        with mock.patch.dict("os.environ", {"LLM_API_KEY": "k"}, clear=True):
            provider = vision.detect_vision_provider()
        assert provider is not None
        self.assertEqual(provider.name, "custom")
        self.assertEqual(provider.api_key, "k")

    def test_model_override_wins(self) -> None:
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "k"}, clear=True):
            provider = vision.detect_vision_provider("forced-model")
        assert provider is not None
        self.assertEqual(provider.model, "forced-model")

    def test_vision_key_priority_over_provider_scan(self) -> None:
        env = {"VISION_API_KEY": "vk", "OPENAI_API_KEY": "ok"}
        with mock.patch.dict("os.environ", env, clear=True):
            provider = vision.detect_vision_provider()
        assert provider is not None
        self.assertEqual(provider.api_key, "vk")


class DescribeImageTests(unittest.TestCase):
    def test_no_provider_returns_none(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(vision.describe_image(_PNG))

    def test_empty_bytes_returns_none(self) -> None:
        with mock.patch.dict("os.environ", {"VISION_API_KEY": "k"}, clear=True):
            self.assertIsNone(vision.describe_image(b""))

    def test_distills_and_strips_query(self) -> None:
        with mock.patch.dict("os.environ", {"VISION_API_KEY": "k"}, clear=True), mock.patch.object(
            vision, "_post_chat", return_value="  `液冷 温控 渗透率`  "
        ):
            query = vision.describe_image(_PNG)
        self.assertEqual(query, "液冷 温控 渗透率")

    def test_collapses_newlines(self) -> None:
        with mock.patch.dict("os.environ", {"VISION_API_KEY": "k"}, clear=True), mock.patch.object(
            vision, "_post_chat", return_value="寒武纪\n业绩预增"
        ):
            self.assertEqual(vision.describe_image(_PNG), "寒武纪 业绩预增")

    def test_caps_query_length(self) -> None:
        long = "题" * 500
        with mock.patch.dict("os.environ", {"VISION_API_KEY": "k"}, clear=True), mock.patch.object(
            vision, "_post_chat", return_value=long
        ):
            query = vision.describe_image(_PNG)
        assert query is not None
        self.assertEqual(len(query), 200)

    def test_empty_model_output_returns_none(self) -> None:
        with mock.patch.dict("os.environ", {"VISION_API_KEY": "k"}, clear=True), mock.patch.object(
            vision, "_post_chat", return_value="   "
        ):
            self.assertIsNone(vision.describe_image(_PNG))

    def test_post_chat_exception_degrades_to_none(self) -> None:
        with mock.patch.dict("os.environ", {"VISION_API_KEY": "k"}, clear=True), mock.patch.object(
            vision, "_post_chat", side_effect=RuntimeError("boom")
        ):
            self.assertIsNone(vision.describe_image(_PNG))

    def test_sends_data_url_with_sniffed_mime(self) -> None:
        captured: dict[str, object] = {}

        def fake_post(provider, messages, timeout):  # noqa: ANN001
            captured["messages"] = messages
            return "ok"

        with mock.patch.dict("os.environ", {"VISION_API_KEY": "k"}, clear=True), mock.patch.object(
            vision, "_post_chat", side_effect=fake_post
        ):
            vision.describe_image(_PNG)
        parts = captured["messages"][1]["content"]  # type: ignore[index]
        image_part = next(p for p in parts if p["type"] == "image_url")
        self.assertTrue(image_part["image_url"]["url"].startswith("data:image/png;base64,"))


if __name__ == "__main__":
    unittest.main()
