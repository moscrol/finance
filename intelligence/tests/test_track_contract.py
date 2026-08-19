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

    def test_merge_track_gaps_into_existing_missing_outputs(self) -> None:
        from intelligence.services.track_contract import merge_track_missing_outputs

        merged = merge_track_missing_outputs(
            ("direct_assessment",),
            self._BARE,
            query="固态电池最新进展如何",
        )
        self.assertEqual(
            merged,
            (
                "direct_assessment",
                "track_quad_or_baseline",
                "track_ttl",
                "track_next_watch",
            ),
        )
        self.assertEqual(
            merge_track_missing_outputs(
                ("direct_assessment",),
                self._BARE,
                query="固态电池产业链全景",
            ),
            ("direct_assessment",),
        )

    def test_contract_rewrite_only_when_gaps_are_track_ids(self) -> None:
        from intelligence.services.track_contract import is_contract_rewrite_only

        self.assertTrue(
            is_contract_rewrite_only(
                ("track_quad_or_baseline", "track_ttl", "track_next_watch")
            )
        )
        self.assertFalse(
            is_contract_rewrite_only(
                ("direct_assessment", "track_ttl"),
            )
        )
        self.assertFalse(
            is_contract_rewrite_only(
                ("track_ttl",),
                rejected_claims=("claim_index:0",),
            )
        )
        self.assertFalse(is_contract_rewrite_only(()))

    def test_receipt_exposes_machine_readable_verdict_and_ttl(self) -> None:
        from intelligence.services.track_contract import contract_receipt

        receipt = contract_receipt(
            self._COMPLETE,
            query="光伏产业链",
            question_type="theme_track",
            as_of="2026-08-19",
        )
        self.assertEqual(receipt["prior_verdict_check"], "信息不足")
        self.assertEqual(receipt["valid_until"], "2026-09-12")
        self.assertEqual(receipt["ttl_status"], "current")
        self.assertTrue(receipt["baseline_declared"])

        expired = contract_receipt(
            "毛利率判断：削弱 [D7]。复核期限：2026-07-01。\n"
            "## 下期关注清单\n- 若中报毛利率 <20% 则削弱扩产逻辑",
            query="固态电池最新进展如何",
            as_of="2026-08-19",
        )
        self.assertEqual(expired["prior_verdict_check"], "削弱")
        self.assertEqual(expired["valid_until"], "2026-07-01")
        self.assertEqual(expired["ttl_status"], "expired")

        missing = contract_receipt(self._BARE, query="固态电池最新进展如何")
        self.assertIsNone(missing["prior_verdict_check"])
        self.assertIsNone(missing["valid_until"])
        self.assertEqual(missing["ttl_status"], "missing")

    def test_expired_ttl_is_annotated_not_deleted(self) -> None:
        from intelligence.services.track_contract import annotate_expired_conclusions

        text = "毛利率判断：信息不足 [D7]。复核期限：2026-07-01。扩产逻辑仍写在这里。"
        annotated = annotate_expired_conclusions(text, as_of="2026-08-19")
        self.assertIn("毛利率判断：信息不足 [D7]", annotated)
        self.assertIn("扩产逻辑仍写在这里", annotated)
        self.assertIn("复核期限：2026-07-01", annotated)
        self.assertIn("已过期，待复核", annotated)
        again = annotate_expired_conclusions(annotated, as_of="2026-08-19")
        self.assertEqual(again.count("已过期，待复核"), 1)
        current = annotate_expired_conclusions(
            "毛利率判断：支持 [D7]。复核期限：2026-09-12。",
            as_of="2026-08-19",
        )
        self.assertNotIn("已过期", current)


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


class NextWatchConsumeTests(unittest.TestCase):
    def test_parse_skips_stub_and_vague_lines(self) -> None:
        from intelligence.services.track_contract import (
            CONTRACT_STUB_HEADING,
            parse_next_watch_items,
        )

        text = (
            "## 下期关注清单\n"
            "- 若 2026-09-12 中报毛利率 <20% 则削弱扩产逻辑\n"
            "- 持续关注市场情绪\n"
            f"\n{CONTRACT_STUB_HEADING}\n"
            "- **下期关注清单**：正文未给出「指标 + 时间节点 + 触发条件」。\n"
        )
        items = parse_next_watch_items(text, as_of="2026-08-19")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].due, "2026-09-12")
        self.assertIn("毛利率", items[0].claim)

    def test_parse_defaults_ttl_when_no_date(self) -> None:
        from intelligence.services.track_contract import parse_next_watch_items

        text = "## 下期关注清单\n- 若周度排产低于 8 万辆则削弱景气判断"
        items = parse_next_watch_items(text, as_of="2026-08-19")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].due, "2026-09-18")

    def test_parse_live_inline_prose_after_heading(self) -> None:
        """2026-08-19 Q2 原文：标题行内联若干「若/则」，下一行是证据边界。"""
        from intelligence.services.track_contract import parse_next_watch_items

        text = (
            "无上期基线，本期建立基线。\n"
            "下期关注清单：月度动力电池装车量公布时，若同比增速转负或环比继续回落，"
            "则削弱需求改善线索；若公布数据维持增长，仍须结合原始发布材料复核。"
            "下一交易日及其后，若锂电池概念转强且进入主线清单，同时电池、材料、回收等"
            "至少多个环节由跌转涨并有成交放大，则支持盘面修复；若继续未入主线且核心板块走弱，"
            "则维持非主线判断。公司中报/公告披露期，若出现经公告确认的出货、订单或盈利改善，"
            "则支持产业传导；若未见该类一手材料，维持待核验。\n"
            "证据边界：盘面数据截至2026-08-18；装车量仅有新闻来源，不能替代行业协会原始材料。"
        )
        items = parse_next_watch_items(text, as_of="2026-08-19")
        claims = "\n".join(item.claim for item in items)
        self.assertGreaterEqual(len(items), 3)
        self.assertTrue(any("装车量" in item.claim and "则" in item.claim for item in items))
        self.assertTrue(any("锂电池概念" in item.claim and "则" in item.claim for item in items))
        self.assertTrue(any("公告" in item.claim and "则" in item.claim for item in items))
        self.assertNotIn("证据边界", claims)
        self.assertNotIn("2026-08-18", claims)
        self.assertTrue(all(item.due == "2026-09-18" for item in items))

    def test_parse_live_fullwidth_numbered_on_heading_line(self) -> None:
        """2026-08-19 Q1 原文：下期关注清单：1）…2）… 全角编号跟标题同一行。"""
        from intelligence.services.track_contract import parse_next_watch_items

        text = (
            "条件化基准判断：未来一个月光伏更可能维持震荡修复。"
            "下期关注清单：1）组件/硅料现货报价，未来数周；若涨价不能延续或被一手数据否定，"
            "则削弱价格触底判断。2）上市公司排产、订单与中报/季报，下一次披露节点；"
            "若排产回升但订单和现金流未同步改善，则削弱需求拐点判断。"
            "3）国内光伏装机数据，下一次官方披露节点；若旺季装机未改善，则排产回升逻辑待证伪。"
            "4）光伏板块相对主线表现，未来数周；若仍无主线地位且持续承压，则削弱交易修复判断。"
        )
        items = parse_next_watch_items(text, as_of="2026-08-19")
        self.assertEqual(len(items), 4)
        self.assertTrue(any("现货报价" in item.claim for item in items))
        self.assertTrue(any("排产" in item.claim for item in items))
        self.assertTrue(any("装机" in item.claim for item in items))
        self.assertTrue(any("主线" in item.claim for item in items))
        self.assertTrue(all("则" in item.claim for item in items))

    def test_non_track_query_does_not_ingest(self) -> None:
        import tempfile
        from pathlib import Path

        from intelligence.services.track_contract import ingest_next_watch

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoints.jsonl"
            written = ingest_next_watch(
                path,
                "## 下期关注清单\n- 若毛利率 <20% 则削弱扩产逻辑",
                query="固态电池产业链全景",
                as_of="2026-08-19",
            )
            self.assertEqual(written, [])
            self.assertFalse(path.exists())

    def test_ingest_dedupes_open_claims_and_foresight_renders(self) -> None:
        import tempfile
        from pathlib import Path

        from intelligence.services.checkpoints import load_checkpoints
        from intelligence.services.track_contract import (
            ingest_next_watch,
            open_next_watch_records,
            render_next_watch_for_prompt,
        )

        answer = (
            "## 下期关注清单\n"
            "- 若 2026-09-12 中报毛利率 <20% 则削弱扩产逻辑"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoints.jsonl"
            first = ingest_next_watch(
                path,
                answer,
                query="固态电池最新进展如何",
                as_of="2026-08-19",
                theme="固态电池",
            )
            second = ingest_next_watch(
                path,
                answer,
                query="固态电池最新进展如何",
                as_of="2026-08-19",
            )
            self.assertEqual(len(first), 1)
            self.assertEqual(second, [])
            rows, _ = load_checkpoints(path)
            open_rows = open_next_watch_records(rows, [])
            self.assertEqual(len(open_rows), 1)
            rendered = render_next_watch_for_prompt(open_rows)
            self.assertIn("due=2026-09-12", rendered)
            self.assertIn("毛利率", rendered)


if __name__ == "__main__":
    unittest.main()
