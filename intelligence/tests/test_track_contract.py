from __future__ import annotations

import unittest

from intelligence.services.track_contract import (
    build_track_guidance,
    parse_track_intent,
    track_guidance_for_query,
)


class ParseTrackIntentTests(unittest.TestCase):
    def test_theme_track_question_type_routes(self) -> None:
        self.assertTrue(parse_track_intent("光伏产业链", "theme_track"))

    def test_track_terms_route(self) -> None:
        self.assertTrue(parse_track_intent("动力电池产业链近况跟踪一下"))
        self.assertTrue(parse_track_intent("液冷自上次之后有什么新变化"))
        self.assertTrue(parse_track_intent("固态电池最新进展如何"))
        self.assertTrue(parse_track_intent("相比上次，算力板块怎么样了"))

    def test_plain_questions_do_not_route(self) -> None:
        # 一次性全景/事实题不注入跟踪契约：泛化问法交由 question_type 兜底
        self.assertFalse(parse_track_intent("今天信创板块怎么样", "theme_analysis"))
        self.assertFalse(parse_track_intent("深信服最近一期毛利率是多少"))
        self.assertFalse(parse_track_intent("光伏行业全景分析"))
        self.assertFalse(parse_track_intent(""))


class GuidanceContentTests(unittest.TestCase):
    def test_guidance_contains_q8_contract_pieces(self) -> None:
        g = build_track_guidance()
        # q8 三件套：delta-only / 四态对照 / TTL + 下期关注
        self.assertIn("delta-only", g)
        self.assertIn("支持 / 削弱 / 无变化 / 信息不足", g)
        self.assertIn("复核期限", g)
        self.assertIn("30 天", g)
        self.assertIn("90 天", g)
        self.assertIn("下期关注清单", g)
        # 无基线时禁止虚构
        self.assertIn("无上期基线", g)
        self.assertIn("[M]", g)
        self.assertIn("[V]", g)

    def test_for_query_returns_empty_when_not_routed(self) -> None:
        self.assertEqual(track_guidance_for_query("深信服毛利率多少", "valuation"), "")

    def test_for_query_returns_guidance_when_routed(self) -> None:
        g = track_guidance_for_query("光伏最近一个月有什么新变化", None)
        self.assertIn("跟踪表达契约", g)
        g2 = track_guidance_for_query("光伏产业链", "theme_track")
        self.assertIn("跟踪表达契约", g2)


class AskOptionsWiringTests(unittest.TestCase):
    def test_include_track_guidance_flag_exists_and_defaults_on(self) -> None:
        from intelligence.services.ask import AskOptions

        options = AskOptions(query="q")
        self.assertTrue(options.include_track_guidance)
        off = AskOptions(query="q", include_track_guidance=False)
        self.assertFalse(off.include_track_guidance)


class ContractGuidancePromptTests(unittest.TestCase):
    """契约必须走独立「输出结构契约」段——塞进「历史经验卡片」会被模型当参考忽略
    （2026-08-13 workbench 实测教训）。"""

    def test_contract_guidance_gets_own_system_section(self) -> None:
        from intelligence.services import llm_refine

        msgs = llm_refine.build_synthesis_messages(
            "固态电池最新进展如何",
            "固态电池",
            "## 证据链\n- 双红 [S1]",
            experience_guidance="- 一条经验",
            contract_guidance=build_track_guidance(),
        )
        system = msgs[0]["content"]
        self.assertIn("输出结构契约", system)
        self.assertIn("跟踪表达契约", system)
        # 契约段在经验卡片段之后（独立且更靠近 user 消息）
        self.assertGreater(system.index("输出结构契约"), system.index("历史经验卡片"))

    def test_no_contract_no_section(self) -> None:
        from intelligence.services import llm_refine

        msgs = llm_refine.build_synthesis_messages(
            "q", "t", "## 证据链\n- x [S1]",
        )
        self.assertNotIn("输出结构契约", msgs[0]["content"])


class ContractMissingOutputsTests(unittest.TestCase):
    """Q4：契约缺件程序核对进 repair_coordinator.missing_outputs 词表 + EVAL 可读收据。"""

    _BARE = "固态电池还在发酵，可以继续看。"
    _COMPLETE = (
        "无上期基线，本期建立基线。\n"
        "毛利率判断：信息不足 [D7]。复核期限：2026-09-12。\n"
        "## 下期关注清单\n- 中报毛利率 <20% 则削弱扩产逻辑"
    )

    def test_track_intent_maps_missing_elements_to_output_ids(self) -> None:
        from intelligence.services.track_contract import contract_missing_outputs

        missing = contract_missing_outputs(self._BARE, query="固态电池最新进展如何")
        self.assertEqual(
            missing,
            ("track_quad_or_baseline", "track_ttl", "track_next_watch"),
        )

    def test_non_track_query_checks_nothing(self) -> None:
        from intelligence.services.track_contract import contract_missing_outputs

        self.assertEqual(
            contract_missing_outputs(self._BARE, query="固态电池产业链全景"), ()
        )

    def test_complete_track_answer_has_no_missing_outputs(self) -> None:
        from intelligence.services.track_contract import contract_missing_outputs

        self.assertEqual(
            contract_missing_outputs(
                self._COMPLETE, query="光伏产业链", question_type="theme_track"
            ),
            (),
        )

    def test_receipt_field_always_present_and_json_native(self) -> None:
        import json

        from intelligence.services.track_contract import contract_receipt

        # 缺件收据：missing_outputs 在场且列出缺件
        receipt = contract_receipt(self._BARE, query="固态电池最新进展如何")
        self.assertEqual(receipt["check"], "track_contract")
        self.assertTrue(receipt["track_intent"])
        self.assertEqual(
            receipt["missing_outputs"],
            ["track_quad_or_baseline", "track_ttl", "track_next_watch"],
        )
        # 非跟踪题：字段仍在场（空 = 不适用），且整体可 JSON 序列化（EVAL 可读）
        plain = contract_receipt(self._BARE, query="固态电池产业链全景")
        self.assertFalse(plain["track_intent"])
        self.assertEqual(plain["missing_outputs"], [])
        json.dumps(receipt), json.dumps(plain)

    def test_output_ids_compose_into_repair_goal(self) -> None:
        """词表兼容不是口头承诺：缺件 id 能原样进 build_repair_goal 的缺口修复环。"""
        from intelligence.services.evidence_ledger import EvidenceLedgerSnapshot
        from intelligence.services.repair_coordinator import (
            build_repair_goal,
            progress_from_ledger,
        )
        from intelligence.services.track_contract import contract_missing_outputs

        snap = EvidenceLedgerSnapshot(
            evidence_ids=("e1",),
            covered_outputs=(),
            open_gaps=(),
            independent_source_families=("market",),
            evidence_source_families=(("e1", "market"),),
            evidence_targets=(("e1", ()),),
        )
        missing = contract_missing_outputs(self._BARE, query="固态电池最新进展如何")
        goal = build_repair_goal(
            episode_id="episode-1",
            missing_outputs=missing,
            previous_progress=progress_from_ledger(snap, snap),
            remaining_calls=2,
            remaining_seconds=30.0,
        )
        self.assertEqual(goal.missing_answer_elements, missing)


class ContractGateTests(unittest.TestCase):
    def test_complete_answer_has_no_missing_elements(self) -> None:
        from intelligence.services.track_contract import missing_contract_elements

        text = (
            "无上期基线，本期建立基线。\n"
            "毛利率判断：信息不足 [D7]。复核期限：2026-09-12。\n"
            "## 下期关注清单\n- 中报毛利率 <20% 则削弱扩产逻辑"
        )
        self.assertEqual(missing_contract_elements(text), ())

    def test_incomplete_answer_lists_missing_and_stub_appends(self) -> None:
        from intelligence.services.track_contract import (
            CONTRACT_STUB_HEADING,
            append_contract_stub,
            missing_contract_elements,
        )

        text = "固态电池还在发酵，可以继续看。（非投资建议）"
        missing = missing_contract_elements(text)
        self.assertIn("quad_or_baseline", missing)
        self.assertIn("ttl", missing)
        self.assertIn("next_watch", missing)
        patched = append_contract_stub(text, missing)
        self.assertTrue(patched.endswith("（非投资建议）"))
        self.assertIn(CONTRACT_STUB_HEADING, patched)
        self.assertLess(patched.index(CONTRACT_STUB_HEADING), patched.index("（非投资建议）"))

    def test_ensure_visible_only_on_track_intent(self) -> None:
        from intelligence.services.ask_synthesis import ensure_track_contract_visible
        from intelligence.services.ask_types import AskResult
        from intelligence.services.track_contract import CONTRACT_STUB_HEADING

        plain = AskResult(query="固态电池产业链全景", trade_date=None, matched_theme="固态电池", candidate_tier=None, priority_score=None)
        plain.synthesis = "一段没有契约结构的回答"
        ensure_track_contract_visible(plain)
        self.assertNotIn(CONTRACT_STUB_HEADING, plain.synthesis)

        track = AskResult(query="固态电池最新进展如何", trade_date=None, matched_theme="固态电池", candidate_tier=None, priority_score=None)
        track.synthesis = "一段没有契约结构的回答"
        ensure_track_contract_visible(track)
        self.assertIn(CONTRACT_STUB_HEADING, track.synthesis)
        self.assertTrue(any("跟踪契约补全" in w for w in track.warnings))

        off = AskResult(query="固态电池最新进展如何", trade_date=None, matched_theme="固态电池", candidate_tier=None, priority_score=None)
        off.synthesis = "一段没有契约结构的回答"
        ensure_track_contract_visible(off, enabled=False)
        self.assertNotIn(CONTRACT_STUB_HEADING, off.synthesis)


if __name__ == "__main__":
    unittest.main()
