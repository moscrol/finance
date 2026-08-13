import json
import unittest
from unittest import mock

from intelligence.services import answer_model, followups


class TemplateFallbackTests(unittest.TestCase):
    def test_no_llm_yields_five_typed_templates(self) -> None:
        result = followups.generate_followups("液冷题材怎么看", matched_theme="液冷", use_llm=False)
        self.assertFalse(result.llm_used)
        self.assertEqual(len(result.followups), 5)
        self.assertEqual([f.type for f in result.followups], followups.FOLLOWUP_TYPES)
        for f in result.followups:
            self.assertIn("液冷", f.question)
            self.assertEqual(f.type_label, followups.TYPE_LABELS[f.type])
            self.assertLessEqual(len(f.label), 20)
            self.assertEqual(f.full_prompt, f.question)

    def test_track_question_skips_first_order_recheck(self) -> None:
        result = followups.generate_followups("固态电池最新进展如何", matched_theme="固态电池", use_llm=False)
        types = [f.type for f in result.followups]
        self.assertNotIn("recheck", types)
        self.assertIn("counter", types)
        self.assertFalse(any("双红" in f.question and "最近" in f.question for f in result.followups))

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
            {"label": "核对液冷订单", "full_prompt": "请核对英维克最新液冷订单金额和公告来源？", "type": "evidence", "rationale": "锚定公告"},
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
        self.assertEqual(result.followups[0].label, "核对液冷订单")
        self.assertEqual(
            result.followups[0].full_prompt,
            "请核对英维克最新液冷订单金额和公告来源？",
        )
        self.assertEqual(
            result.followups[1].full_prompt,
            "如果液冷渗透率不及预期，先看什么？",
        )

    def test_to_json_roundtrip(self) -> None:
        result = followups.generate_followups("液冷", matched_theme="液冷", use_llm=False)
        doc = json.loads(result.to_json())
        self.assertEqual(len(doc["followups"]), 5)
        self.assertIn("type_label", doc["followups"][0])
        self.assertIn("label", doc["followups"][0])
        self.assertIn("full_prompt", doc["followups"][0])


class GapMirrorTests(unittest.TestCase):
    """缺口镜像：结构化缺口确定性变「猜你想问」，零模型调用。

    动机（R15 knevo 对照 9:2:0）：多题失分不在缺口本身，在缺口变成句号
    ——「追问负担全在用户」。文案来自任务契约必需输出描述，与公开降级
    声明同一口径。
    """

    def test_gaps_become_typed_clickable_followups(self) -> None:
        result = followups.gap_mirror_followups(
            "液冷题材",
            ("主线判断依据", "失效条件"),
        )
        self.assertFalse(result.llm_used)
        self.assertEqual(len(result.followups), 2)
        for item, gap in zip(result.followups, ("主线判断依据", "失效条件")):
            self.assertEqual(item.type, "gap")
            self.assertEqual(item.type_label, "缺口补齐")
            self.assertIn("液冷题材", item.full_prompt)
            self.assertIn(gap, item.full_prompt)
            self.assertLessEqual(len(item.label), 20)
            self.assertTrue(item.label.startswith("补齐"))

    def test_limit_and_blank_gaps(self) -> None:
        result = followups.gap_mirror_followups(
            "X",
            ("a", "  ", "b", "c", "d"),
            limit=3,
        )
        # 先滤空白再截上限：a/b/c 占满 3 个名额，空白不浪费名额。
        self.assertEqual(
            [item.full_prompt.count("「") for item in result.followups],
            [1, 1, 1],
        )
        self.assertEqual(len(result.followups), 3)
        self.assertEqual(followups.gap_mirror_followups("X", ()).followups, [])

    def test_blank_subject_gets_placeholder(self) -> None:
        result = followups.gap_mirror_followups("  ", ("反方证据",))
        self.assertIn("该问题", result.followups[0].full_prompt)


class AnswerSpecFollowupTests(unittest.TestCase):
    def test_suggestions_only_use_gaps_actions_and_validation_boundaries(self) -> None:
        gap = answer_model.make_claim(
            claim_id="gap-1",
            text="缺少公司公告对真实订单的确认",
            claim_type="gap",
            theme="液冷",
            status=answer_model.ClaimStatus.MISSING,
        )
        trigger = answer_model.make_claim(
            claim_id="trigger-1",
            text="若毛利率连续两个季度下滑则判断降级",
            claim_type="trigger",
            theme="液冷",
            status=answer_model.ClaimStatus.INFERRED,
        )
        spec = answer_model.AnswerSpec(
            research_spec=answer_model.resolve_theme_research_spec("液冷", "液冷"),
            summary=(),
            verified_facts=(),
            company_table=(),
            counter_evidence=(),
            gaps=(gap,),
            triggers=(trigger,),
            next_actions=("核对下一期定期报告的分部收入",),
            sources=(),
            system_notices=(),
        )

        result = followups.generate_answer_spec_followups(
            spec,
            subject="英维克",
        )

        self.assertEqual(len(result.followups), 4)
        self.assertFalse(result.llm_used)
        self.assertTrue(any(item.source == "gap:gap-1" for item in result.followups))
        self.assertTrue(any(item.source == "next_action" for item in result.followups))
        self.assertTrue(all("海光信息" not in item.question for item in result.followups))


if __name__ == "__main__":
    unittest.main()
