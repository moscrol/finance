import json
import unittest
from unittest import mock

from intelligence.services import followups


class TemplateFallbackTests(unittest.TestCase):
    def test_no_llm_yields_five_typed_templates(self) -> None:
        result = followups.generate_followups("液冷题材怎么看", matched_theme="液冷", use_llm=False)
        self.assertFalse(result.llm_used)
        self.assertEqual(len(result.followups), 5)
        self.assertEqual([f.type for f in result.followups], followups.FOLLOWUP_TYPES)
        for f in result.followups:
            self.assertIn("液冷", f.question)
            self.assertEqual(f.type_label, followups.TYPE_LABELS[f.type])

    def test_no_theme_falls_back_to_question_prefix(self) -> None:
        result = followups.generate_followups("英维克现在贵不贵", use_llm=False)
        self.assertTrue(all("英维克现在贵不贵" in f.question for f in result.followups))

    def test_llm_failure_degrades_to_template_with_warning(self) -> None:
        with mock.patch.object(followups.llm_refine, "complete", return_value=(None, None, "无可用 provider")):
            result = followups.generate_followups("液冷", matched_theme="液冷")
        self.assertFalse(result.llm_used)
        self.assertEqual(len(result.followups), 5)
        self.assertTrue(any("无可用 provider" in w for w in result.warnings))


class LLMPathTests(unittest.TestCase):
    def test_llm_json_parsed_and_typed(self) -> None:
        payload = json.dumps({"followups": [
            {"question": "英维克最新液冷订单金额多少？", "type": "evidence", "rationale": "锚定公告"},
            {"question": "如果液冷渗透率不及预期，先看什么？", "type": "counter"},
            {"question": "类型非法的会被丢弃", "type": "nope"},
        ]})
        provider = mock.Mock()
        provider.name = "fake"
        with mock.patch.object(followups.llm_refine, "complete", return_value=(payload, provider, "")):
            result = followups.generate_followups("液冷", matched_theme="液冷")
        self.assertTrue(result.llm_used)
        self.assertEqual(result.llm_provider, "fake")
        self.assertEqual(len(result.followups), 2)
        self.assertEqual(result.followups[0].type_label, "证据加深")

    def test_to_json_roundtrip(self) -> None:
        result = followups.generate_followups("液冷", matched_theme="液冷", use_llm=False)
        doc = json.loads(result.to_json())
        self.assertEqual(len(doc["followups"]), 5)
        self.assertIn("type_label", doc["followups"][0])


if __name__ == "__main__":
    unittest.main()
