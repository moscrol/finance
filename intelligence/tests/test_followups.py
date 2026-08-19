import json
import re
import unittest
from unittest import mock

from intelligence.services import answer_model, followups


def _cross_cut(items: list[followups.Followup], *, parent: str | None = None) -> None:
    for item in items:
        assert len(item.label) <= 20
        assert item.full_prompt
        assert (
            "请" in item.full_prompt
            or "？" in item.full_prompt
            or "未完成核验" in item.full_prompt
        )
        assert "双红" not in item.full_prompt
        assert "近几日涨停热度" not in item.full_prompt
        if parent:
            assert re.sub(r"\s+", "", item.full_prompt) != re.sub(r"\s+", "", parent)


class TemplateFallbackTests(unittest.TestCase):
    def test_no_llm_yields_two_to_four_composed_cards(self) -> None:
        result = followups.generate_followups("液冷题材怎么看", matched_theme="液冷", use_llm=False)
        self.assertFalse(result.llm_used)
        self.assertGreaterEqual(len(result.followups), 2)
        self.assertLessEqual(len(result.followups), 4)
        types = [item.type for item in result.followups]
        self.assertIn("evidence", types)
        self.assertIn("alternative", types)
        self.assertIn("counter", types)
        self.assertNotIn("migration", types)
        for item in result.followups:
            self.assertIn("液冷", item.question)
            self.assertLessEqual(len(item.label), 20)
            self.assertEqual(item.full_prompt, item.question)
        _cross_cut(result.followups)

    def test_track_question_skips_first_order_recheck(self) -> None:
        result = followups.generate_followups("固态电池最新进展如何", matched_theme="固态电池", use_llm=False)
        types = [item.type for item in result.followups]
        self.assertNotIn("recheck", types)
        self.assertFalse(any("双红" in item.question and "最近" in item.question for item in result.followups))
        _cross_cut(result.followups)

    def test_no_theme_falls_back_to_question_prefix(self) -> None:
        result = followups.generate_followups("英维克现在贵不贵", use_llm=False)
        self.assertTrue(all("英维克现在贵不贵" in item.question for item in result.followups))

    def test_llm_failure_degrades_to_template_with_warning(self) -> None:
        with mock.patch.object(followups.llm_refine, "complete", return_value=(None, None, "无可用 provider")):
            result = followups.generate_followups("液冷", matched_theme="液冷")
        self.assertFalse(result.llm_used)
        self.assertGreaterEqual(len(result.followups), 2)
        self.assertLessEqual(len(result.followups), 4)
        self.assertTrue(any("无可用 provider" in warn or "followup_polish_dropped" in warn for warn in result.warnings))


class LLMPathTests(unittest.TestCase):
    def test_polish_keeps_selected_type_and_angle(self) -> None:
        payload = json.dumps({"followups": [
            {"label": "核对液冷订单", "full_prompt": "请核对英维克最新液冷订单金额和公告来源？", "type": "evidence", "angle": "A"},
            {"label": "同链下一跳", "full_prompt": "请核液冷同链下一跳的订单或认证？", "type": "alternative", "angle": "B"},
            {"label": "证伪条件", "full_prompt": "出现哪些反证应下调对液冷的判断？", "type": "counter", "angle": "D"},
        ]})
        provider = mock.Mock()
        provider.name = "fake"
        with mock.patch.object(followups.llm_refine, "complete", return_value=(payload, provider, "")):
            result = followups.generate_followups("液冷", matched_theme="液冷")
        self.assertTrue(result.llm_used)
        self.assertEqual(result.llm_provider, "fake")
        self.assertEqual(len(result.followups), 3)
        self.assertEqual([item.angle for item in result.followups], ["A", "B", "D"])
        self.assertEqual(result.followups[0].type, "evidence")
        self.assertEqual(result.followups[0].label, "核对液冷订单")
        self.assertEqual(
            result.followups[0].full_prompt,
            "请核对英维克最新液冷订单金额和公告来源？",
        )

    def test_polish_type_change_is_dropped(self) -> None:
        payload = json.dumps({"followups": [
            {"label": "改类型", "full_prompt": "请随便问？", "type": "migration", "angle": "A"},
            {"label": "x", "full_prompt": "请x？", "type": "alternative", "angle": "B"},
            {"label": "y", "full_prompt": "请y？", "type": "counter", "angle": "D"},
        ]})
        provider = mock.Mock()
        provider.name = "fake"
        with mock.patch.object(followups.llm_refine, "complete", return_value=(payload, provider, "")):
            result = followups.generate_followups("液冷", matched_theme="液冷")
        self.assertFalse(result.llm_used)
        self.assertEqual([item.type for item in result.followups], ["evidence", "alternative", "counter"])
        self.assertTrue(any("followup_polish_dropped" in warn for warn in result.warnings))

    def test_to_json_roundtrip(self) -> None:
        result = followups.generate_followups("液冷", matched_theme="液冷", use_llm=False)
        doc = json.loads(result.to_json())
        self.assertGreaterEqual(len(doc["followups"]), 2)
        self.assertLessEqual(len(doc["followups"]), 4)
        self.assertIn("type_label", doc["followups"][0])
        self.assertIn("label", doc["followups"][0])
        self.assertIn("full_prompt", doc["followups"][0])
        self.assertIn("angle", doc["followups"][0])


class GapMirrorTests(unittest.TestCase):
    def test_gaps_become_typed_clickable_followups(self) -> None:
        result = followups.gap_mirror_followups(
            "液冷题材",
            ("主线判断依据", "失效条件"),
        )
        self.assertFalse(result.llm_used)
        self.assertEqual(len(result.followups), 2)
        for item, gap in zip(result.followups, ("主线判断依据", "失效条件")):
            self.assertEqual(item.type, "gap")
            self.assertEqual(item.angle, "A")
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
        self.assertEqual(
            [item.full_prompt.count("「") for item in result.followups],
            [1, 1, 1],
        )
        self.assertEqual(len(result.followups), 3)
        self.assertEqual(followups.gap_mirror_followups("X", ()).followups, [])

    def test_blank_subject_gets_placeholder(self) -> None:
        result = followups.gap_mirror_followups("  ", ("反方证据",))
        self.assertIn("该问题", result.followups[0].full_prompt)


class AngleComposerTests(unittest.TestCase):
    def test_gaps_only_keeps_angle_a(self) -> None:
        state = followups.FollowupState(
            subject="液冷",
            question="液冷怎么看",
            question_kind="theme",
            open_gaps=("主线判断依据", "失效条件"),
            status="completed",
            no_action_room=True,
        )
        angles = followups.select_angles(state)
        self.assertGreaterEqual(angles.count("A"), 1)
        result = followups.compose_followups(state)
        self.assertTrue(any(item.type == "gap" and item.angle == "A" for item in result.followups))
        self.assertTrue(any("主线判断依据" in item.full_prompt for item in result.followups))
        self.assertGreaterEqual(len(result.followups), 2)
        self.assertLessEqual(len(result.followups), 4)
        _cross_cut(result.followups)

    def test_d3_present_names_next_hop_once(self) -> None:
        state = followups.FollowupState(
            subject="英维克",
            question="英维克怎么看",
            question_kind="stock",
            alternatives=(followups.AlternativeItem("星网锐捷", reason="P0", source="d3_p0"),),
            listed_names=frozenset({"星网锐捷"}),
            no_action_room=False,
        )
        result = followups.compose_followups(state)
        bees = [item for item in result.followups if item.angle == "B"]
        self.assertEqual(len(bees), 1)
        self.assertIn("星网锐捷", bees[0].full_prompt)
        self.assertNotIn("新发现", bees[0].full_prompt)
        self.assertIn("不要重复列出已有替代名单", bees[0].full_prompt)
        _cross_cut(result.followups)

    def test_project_ask_state_carries_d3_structure(self) -> None:
        """ask 路径 D3 结构直通投影：P0 进 alternatives(d3_p0)，P2 进 bottlenecks。"""

        state = followups.project_ask_state(
            "深挖一下顺络电子",
            subject="顺络电子",
            alternatives=(
                ("超声电子", "(元件) 10.01%、成交18.0亿"),
                ("", "空名字必须丢弃"),
            ),
            bottlenecks=("TLVR", "  ", "钽电容"),
        )
        self.assertEqual(len(state.alternatives), 1)
        self.assertEqual(state.alternatives[0].name, "超声电子")
        self.assertEqual(state.alternatives[0].source, "d3_p0")
        self.assertEqual(state.bottlenecks, ("TLVR", "钽电容"))
        self.assertIn("超声电子", state.listed_names)

        result = followups.compose_followups(state, polish=False)
        bees = [item for item in result.followups if item.angle == "B"]
        self.assertEqual(len(bees), 1)
        self.assertIn("超声电子", bees[0].full_prompt)
        _cross_cut(result.followups)

    def test_project_ask_state_without_d3_keeps_template_b(self) -> None:
        """无 D3 结构时行为不变：B 槽退回 subject 级模板，不假装有队列。"""

        state = followups.project_ask_state("深挖一下顺络电子", subject="顺络电子")
        self.assertEqual(state.alternatives, ())
        self.assertEqual(state.bottlenecks, ())
        self.assertEqual(state.listed_names, frozenset())

    def test_no_action_room_asks_for_window(self) -> None:
        state = followups.FollowupState(
            subject="液冷",
            question="液冷怎么看",
            question_kind="theme",
            open_gaps=("公司级订单",),
            status="partial",
            no_action_room=True,
        )
        result = followups.compose_followups(state)
        self.assertTrue(any(item.angle == "A" for item in result.followups))
        cees = [item for item in result.followups if item.angle == "C"]
        self.assertTrue(cees)
        self.assertTrue(any("信号" in item.full_prompt or "窗口" in item.full_prompt for item in cees))
        self.assertFalse(any("现在该买吗" in item.full_prompt for item in result.followups))
        _cross_cut(result.followups)

    def test_methodology_skips_a_and_alternative(self) -> None:
        state = followups.FollowupState(
            subject="",
            question="框架怎么回测",
            question_kind="methodology",
            produced_framework=True,
            no_action_room=False,
        )
        angles = followups.select_angles(state)
        self.assertNotIn("A", angles)
        self.assertNotIn("B", angles)
        result = followups.compose_followups(state)
        self.assertGreaterEqual(sum(1 for item in result.followups if item.angle == "D"), 2)
        self.assertFalse(any(item.type == "alternative" for item in result.followups))
        self.assertFalse(any(item.angle == "A" for item in result.followups))
        self.assertGreaterEqual(len(result.followups), 2)
        self.assertLessEqual(len(result.followups), 4)
        _cross_cut(result.followups)

    def test_parent_prompt_is_not_echoed(self) -> None:
        parent = "英维克目前最硬的一条公司级证据是什么，出自哪份公告或研报？"
        state = followups.FollowupState(
            subject="英维克",
            question=parent,
            question_kind="stock",
            parent_followup_prompt=parent,
        )
        result = followups.compose_followups(state)
        _cross_cut(result.followups, parent=parent)

    def test_empty_state_still_emits_two_conservative(self) -> None:
        result = followups.compose_followups(followups.FollowupState())
        self.assertGreaterEqual(len(result.followups), 2)
        self.assertLessEqual(len(result.followups), 4)

    def test_null_composer_unloads(self) -> None:
        empty = followups.NullComposer().compose(followups.FollowupState(subject="液冷"))
        self.assertEqual(empty.followups, [])


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

        self.assertGreaterEqual(len(result.followups), 2)
        self.assertLessEqual(len(result.followups), 4)
        self.assertFalse(result.llm_used)
        self.assertTrue(any(item.source == "gap:gap-1" for item in result.followups))
        self.assertTrue(all("海光信息" not in item.question for item in result.followups))
        _cross_cut(result.followups)


if __name__ == "__main__":
    unittest.main()
