from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence.services.answer_orchestrator import (
    QUESTION_FACT_CHECK,
    QUESTION_MARKET_FORECAST,
    QUESTION_STOCK_DEEP_DIVE,
    QUESTION_VALUATION,
    plan_answer_question,
)
from intelligence.services.ask import AskOptions, answer_query
from intelligence.services.l3_evidence import (
    _try_parse_json_items,
    L3LookupConfig,
    L3EvidenceBundle,
    L3EvidenceGap,
    L3EvidenceItem,
    UNRESOLVED_COMPANY_WARNING,
    lookup_l3_company,
    lookup_l3_evidence,
)


class L3EvidenceDetectionTests(unittest.TestCase):
    def test_customer_fact_check_requires_runtime_l3_lookup(self) -> None:
        query = "中际旭创和英伟达是否已确认合作？"
        plan = plan_answer_question(
            query,
            question_type_override=QUESTION_FACT_CHECK,
        )

        bundle = lookup_l3_evidence(
            query,
            plan,
            local_evidence_text="客户/合作证据缺口，尚待公告或合同确认。",
            config=L3LookupConfig(enabled=False),
            company_hint="中际旭创",
        )

        self.assertEqual(plan.question_type, QUESTION_FACT_CHECK)
        self.assertTrue(bundle.gaps)
        self.assertIn("未启用", "\n".join(bundle.warnings))

    def test_stock_deep_dive_detects_p0_l3_gap_when_hard_evidence_missing(self) -> None:
        plan = plan_answer_question("深挖瑞华泰，重点看客户和订单")

        bundle = lookup_l3_evidence(
            "深挖瑞华泰，重点看客户和订单",
            plan,
            local_evidence_text="evidence_index 未命中；客户证据不足；缺口：订单/量产/互动易待验证。",
            config=L3LookupConfig(enabled=False),
        )

        self.assertEqual(plan.question_type, QUESTION_STOCK_DEEP_DIVE)
        self.assertTrue(bundle.gaps)
        self.assertEqual(bundle.gaps[0].priority, "P0")
        self.assertIn("客户/订单/量产", bundle.gaps[0].reason)
        self.assertIn("cninfo", bundle.gaps[0].source_types)
        self.assertIn("sse_einteract", bundle.gaps[0].source_types)
        self.assertIn("未启用", "\n".join(bundle.warnings))

    def test_market_forecast_does_not_trigger_l3_lookup_by_default(self) -> None:
        plan = plan_answer_question("站在6.30视角，7.1行情怎么看")

        bundle = lookup_l3_evidence(
            "站在6.30视角，7.1行情怎么看",
            plan,
            local_evidence_text="市场状态、双红题材、外盘映射。",
            config=L3LookupConfig(enabled=True, cninfo_cmd="mock {query_sh}"),
        )

        self.assertEqual(plan.question_type, QUESTION_MARKET_FORECAST)
        self.assertFalse(bundle.gaps)
        self.assertFalse(bundle.items)
        self.assertIn("本问题类型不需要", "\n".join(bundle.warnings))

    def test_valuation_plan_can_reach_runtime_official_lookup(self) -> None:
        plan = plan_answer_question(
            "某公司估值怎么看",
            question_type_override=QUESTION_VALUATION,
        )

        bundle = lookup_l3_evidence(
            "某公司估值怎么看",
            plan,
            local_evidence_text="最新财务口径缺失，仍需核对定期报告。",
            config=L3LookupConfig(enabled=False),
            company_hint="某公司",
        )

        self.assertTrue(bundle.gaps)
        self.assertEqual(bundle.gaps[0].kind, "valuation_official_gap")
        self.assertIn("未启用", "\n".join(bundle.warnings))


class L3EvidenceLookupTests(unittest.TestCase):
    def test_from_env_defaults_enable_result_cache(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=False) as env:
            env.pop("FINANCE_L3_CACHE_DIR", None)
            env.pop("FINANCE_L3_CACHE_TTL_SECONDS", None)
            cfg = L3LookupConfig.from_env(enabled=True)

        self.assertEqual(cfg.cache_dir, L3LookupConfig.DEFAULT_CACHE_DIR)
        self.assertEqual(cfg.cache_ttl_seconds, L3LookupConfig.DEFAULT_CACHE_TTL_SECONDS)

    def test_from_env_cache_can_be_disabled_via_env(self) -> None:
        with mock.patch.dict(
            "os.environ", {"FINANCE_L3_CACHE_TTL_SECONDS": "0"}, clear=False
        ):
            cfg = L3LookupConfig.from_env(enabled=True)

        self.assertEqual(cfg.cache_ttl_seconds, 0)

    def test_default_company_command_uses_verified_disclosure_lookup_entrypoint(self) -> None:
        plan = plan_answer_question("深挖瑞华泰，查公告和互动易")
        completed = subprocess.CompletedProcess(
            args=["mock"],
            returncode=0,
            stdout=(
                "2026-07-01T00:00  cninfo         瑞华泰(688323)  [P2] 瑞华泰关于实施“瑞科转债”赎回暨摘牌的第十四次提示性公告\n"
                "2026-06-30T17:45  sse_einteract  瑞华泰(688323)  [P2] 尊敬的董秘您好，目前国内的PI膜生产制造中BPDA是核心原料么？"
            ),
            stderr="",
        )

        with mock.patch("intelligence.services.l3_evidence.subprocess.run", return_value=completed) as run:
            bundle = lookup_l3_evidence(
                "深挖瑞华泰，查公告和互动易",
                plan,
                local_evidence_text="客户证据不足；公告/互动易待验证。",
                config=L3LookupConfig(enabled=True),
            )

        self.assertEqual(run.call_count, 1)
        called = run.call_args.args[0]
        self.assertEqual(called[:4], [sys.executable, "-m", "disclosure_lookup.cli", "company"])
        self.assertIn("瑞华泰", called)
        self.assertIn("--source", called)
        self.assertIn("cninfo,sse_einteract", called)
        self.assertGreaterEqual(run.call_args.kwargs["timeout"], 480)
        self.assertTrue(bundle.items)
        self.assertTrue(any("sse_einteract" in item.summary for item in bundle.items))

    def test_company_hint_overrides_subject_reparsed_from_full_sentence(self) -> None:
        plan = plan_answer_question(
            "天赐材料与楚能新能源签订采购合作协议的公告有什么影响"
        )
        completed = subprocess.CompletedProcess(
            args=["mock"],
            returncode=0,
            stdout=(
                "2026-06-02T00:00  cninfo  天赐材料(002709)  "
                "[P0] 关于采购合作协议的进展公告"
            ),
            stderr="",
        )

        with mock.patch(
            "intelligence.services.l3_evidence.subprocess.run",
            return_value=completed,
        ) as run:
            bundle = lookup_l3_evidence(
                "天赐材料与楚能新能源签订采购合作协议的公告有什么影响",
                plan,
                local_evidence_text="仍需核对公告原文。",
                config=L3LookupConfig(
                    enabled=True,
                    cache_ttl_seconds=0,
                ),
                company_hint="天赐材料",
            )

        called = run.call_args.args[0]
        company_index = called.index("company") + 1
        self.assertEqual(called[company_index], "天赐材料")
        self.assertTrue(bundle.items)

    def test_warning_only_output_is_not_promoted_to_l3_evidence(self) -> None:
        plan = plan_answer_question("某公司公告有什么影响")
        completed = subprocess.CompletedProcess(
            args=["mock"],
            returncode=0,
            stdout="[warn] 无法解析公司：某公司与另一公司",
            stderr="",
        )

        with mock.patch(
            "intelligence.services.l3_evidence.subprocess.run",
            return_value=completed,
        ):
            bundle = lookup_l3_evidence(
                "某公司公告有什么影响",
                plan,
                local_evidence_text="仍需核对公告原文。",
                config=L3LookupConfig(
                    enabled=True,
                    cache_ttl_seconds=0,
                ),
                company_hint="某公司",
            )

        self.assertFalse(bundle.items)
        self.assertIn("没有解析到可用证据", "\n".join(bundle.warnings))

    def test_unresolved_company_becomes_an_instruction_the_model_can_act_on(self) -> None:
        """题材名当公司名送下去：CLI 回「无法解析公司」+ []，警告要说清「这不是公司、换成公司名」。

        2026-09-07 同题五遍 live 父臂 8 次 l3_lookup 全空，一半 query 是「固态电池 量产 产线 公告」。
        只有一句「查询成功但没有解析到可用证据」时，模型下一轮照样用题材名再点一次。
        """

        unresolved = subprocess.CompletedProcess(
            args=["mock"], returncode=0, stdout="[warn] 无法解析公司：固态电池\n[]\n", stderr=""
        )
        with mock.patch("intelligence.services.l3_evidence.subprocess.run", return_value=unresolved):
            bundle = lookup_l3_company(
                "2026年8月 9月 固态电池 量产 产线 公告 互动易 A股",
                config=L3LookupConfig(
                    enabled=True,
                    cache_ttl_seconds=0,
                    company_cmd="{python_sh} -m disclosure_lookup.cli company {company_sh} --json",
                ),
            )
        self.assertFalse(bundle.items)
        self.assertIn(UNRESOLVED_COMPANY_WARNING, bundle.warnings)
        self.assertIn("没有解析到可用证据", "\n".join(bundle.warnings))
        self.assertIn("题材名、产品名不是公司", bundle.to_prompt_block())

        # 真公司、近 90 天只有 P2 定期报告（被低信号门丢掉）：不是「没识别出公司」，不能给这条指令。
        only_periodic = subprocess.CompletedProcess(
            args=["mock"], returncode=0,
            stdout='[{"company_name":"万顺新材","source":"cninfo","title":"2026年半年度报告","summary":"2026年半年度报告","url":"https://x","triage_level":"P2"}]',
            stderr="",
        )
        with mock.patch("intelligence.services.l3_evidence.subprocess.run", return_value=only_periodic):
            resolved = lookup_l3_company(
                "万顺新材 2026年9月 钠离子电池 铝箔 中批量供货",
                config=L3LookupConfig(
                    enabled=True,
                    cache_ttl_seconds=0,
                    company_cmd="{python_sh} -m disclosure_lookup.cli company {company_sh} --json",
                ),
            )
        self.assertFalse(resolved.items)
        self.assertNotIn(UNRESOLVED_COMPANY_WARNING, resolved.warnings)
        self.assertIn("没有解析到可用证据", "\n".join(resolved.warnings))

    def test_interactive_platform_reply_is_the_evidence_not_the_question(self) -> None:
        """互动易行：summary 只是投资者提问，公司答复在 raw_excerpt 的「||答复：」之后。

        2026-09-07 实测盛弘股份 irm_szse P0 行：提问「公司为维谛供应 800V HVDC…」，答复「公司和维谛在
        HVDC 业务上并未合作」（is_reverse=True）。只给提问就把一手反证扔了。"""

        rows = [
            {
                "company_name": "盛弘股份", "company_code": "300693", "source": "irm_szse",
                "title": "尊敬的董秘您好，公司为维谛供应800V HVDC高压直流电源模块，想咨询两点",
                "url": "https://irm.cninfo.com.cn/", "published_at": "2026-08-10T13:18:29+08:00",
                "summary": "尊敬的董秘您好，公司为维谛供应800V HVDC高压直流电源模块，想咨询两点：1、是否适配英伟达",
                "raw_excerpt": "尊敬的董秘您好，公司为维谛供应800V HVDC高压直流电源模块，想咨询两点：1、是否适配英伟达 2、订单是否增长  ||答复：您好，公司和维谛在HVDC业务上并未合作。感谢您的关注。",
                "matched_keywords": [], "triage_level": "P0", "triage_score": 18.0, "is_reverse": True,
            },
            {
                "company_name": "盛弘股份", "source": "cninfo", "title": "关于签订重大合同的公告",
                "summary": "关于签订重大合同的公告", "url": "https://www.cninfo.com.cn/x", "triage_level": "P1",
                "is_reverse": False,
            },
        ]
        items = _try_parse_json_items("company", json.dumps(rows, ensure_ascii=False))

        self.assertEqual(len(items), 2)
        irm, cninfo = items
        self.assertEqual(irm.source_type, "irm_szse")
        self.assertTrue(irm.title.startswith("[反向口径] "))
        self.assertIn("答复：您好，公司和维谛在HVDC业务上并未合作", irm.summary)
        self.assertIn("想咨询两点", irm.summary)  # 提问头保留，让答复有上下文
        self.assertNotIn("[反向口径]", cninfo.title)
        self.assertEqual(cninfo.summary, "关于签订重大合同的公告")

    def test_leading_warning_does_not_hide_or_contaminate_json_evidence(
        self,
    ) -> None:
        plan = plan_answer_question("天赐材料合作协议公告有什么影响")
        completed = subprocess.CompletedProcess(
            args=["mock"],
            returncode=0,
            stdout=(
                "[warn] 源 sse_einteract 失败：No module named 'akshare'\n"
                "[\n"
                '  {"company_name":"天赐材料","source":"cninfo",'
                '"title":"关于采购合作协议的进展公告",'
                '"summary":"关于采购合作协议的进展公告",'
                '"url":"https://www.cninfo.com.cn/example"}\n'
                "]"
            ),
            stderr="",
        )

        with mock.patch(
            "intelligence.services.l3_evidence.subprocess.run",
            return_value=completed,
        ):
            bundle = lookup_l3_evidence(
                "天赐材料合作协议公告有什么影响",
                plan,
                local_evidence_text="仍需核对公告原文。",
                config=L3LookupConfig(
                    enabled=True,
                    cache_ttl_seconds=0,
                ),
                company_hint="天赐材料",
            )

        self.assertEqual(len(bundle.items), 1)
        self.assertEqual(bundle.items[0].source_type, "cninfo")
        self.assertEqual(bundle.items[0].title, "关于采购合作协议的进展公告")
        self.assertNotIn("[warn]", bundle.items[0].summary)

    def test_default_company_command_can_use_env_python_override(self) -> None:
        plan = plan_answer_question("深挖瑞华泰，查公告和互动易")
        completed = subprocess.CompletedProcess(args=["mock"], returncode=0, stdout="ok", stderr="")

        with mock.patch.dict(
            "os.environ",
            {"FINANCE_L3_PYTHON": "/tmp/disclosure-venv/bin/python", "FINANCE_L3_CACHE_TTL_SECONDS": "0"},
        ), mock.patch(
            "intelligence.services.l3_evidence.subprocess.run", return_value=completed
        ) as run:
            lookup_l3_evidence(
                "深挖瑞华泰，查公告和互动易",
                plan,
                local_evidence_text="客户证据不足；公告/互动易待验证。",
                config=L3LookupConfig.from_env(enabled=True),
            )

        called = run.call_args.args[0]
        self.assertEqual(called[0], "/tmp/disclosure-venv/bin/python")

    def test_env_pythonpath_and_cwd_are_passed_to_lookup_process(self) -> None:
        plan = plan_answer_question("深挖瑞华泰，查公告和互动易")
        completed = subprocess.CompletedProcess(args=["mock"], returncode=0, stdout="ok", stderr="")

        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            "os.environ",
            {
                "FINANCE_L3_PYTHONPATH": "~/finhot",
                "FINANCE_L3_CWD": tmp,
                "PYTHONPATH": "/existing/path",
                "FINANCE_L3_CACHE_TTL_SECONDS": "0",
            },
        ), mock.patch(
            "intelligence.services.l3_evidence.subprocess.run", return_value=completed
        ) as run:
            lookup_l3_evidence(
                "深挖瑞华泰，查公告和互动易",
                plan,
                local_evidence_text="客户证据不足；公告/互动易待验证。",
                config=L3LookupConfig.from_env(enabled=True),
            )

        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["cwd"], tmp)
        self.assertTrue(kwargs["env"]["PYTHONPATH"].startswith(str(Path.home() / "finhot")))
        self.assertIn("/existing/path", kwargs["env"]["PYTHONPATH"])

    def test_runtime_cache_reuses_successful_lookup_stdout(self) -> None:
        plan = plan_answer_question("深挖瑞华泰，查公告和互动易")
        completed = subprocess.CompletedProcess(
            args=["mock"],
            returncode=0,
            stdout="2026-07-01T00:00  cninfo  瑞华泰(688323)  [P2] mock公告",
            stderr="",
        )

        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "intelligence.services.l3_evidence.subprocess.run", return_value=completed
        ) as run:
            cfg = L3LookupConfig(enabled=True, cache_dir=tmp, cache_ttl_seconds=86400)
            first = lookup_l3_evidence(
                "深挖瑞华泰，查公告和互动易",
                plan,
                local_evidence_text="客户证据不足；公告/互动易待验证。",
                config=cfg,
            )
            second = lookup_l3_evidence(
                "深挖瑞华泰，查公告和互动易",
                plan,
                local_evidence_text="客户证据不足；公告/互动易待验证。",
                config=cfg,
            )

        self.assertEqual(run.call_count, 1)
        self.assertIn("mock公告", first.items[0].summary)
        self.assertIn("mock公告", second.items[0].summary)

    def test_configured_cninfo_command_is_executed_and_normalized(self) -> None:
        plan = plan_answer_question("深挖688323瑞华泰，查公告验证订单")
        completed = subprocess.CompletedProcess(
            args=["mock"],
            returncode=0,
            stdout="瑞华泰公告：关于聚酰亚胺薄膜项目进展的公告\n披露日期：2026-06-30\n客户验证仍需跟踪",
            stderr="",
        )

        with mock.patch("intelligence.services.l3_evidence.subprocess.run", return_value=completed) as run:
            bundle = lookup_l3_evidence(
                "深挖688323瑞华泰，查公告验证订单",
                plan,
                local_evidence_text="客户证据不足，需要公告验证。",
                config=L3LookupConfig(
                    enabled=True,
                    company_cmd=None,
                    cninfo_cmd="python -m disclosure_lookup cninfo --query {query_sh} --limit {limit}",
                    sse_einteract_cmd=None,
                    timeout=7,
                    limit=3,
                ),
            )

        self.assertEqual(run.call_count, 1)
        called = run.call_args.args[0]
        self.assertIn("disclosure_lookup", called)
        self.assertIn("瑞华泰", " ".join(called))
        self.assertEqual(bundle.items[0].source_type, "cninfo")
        self.assertIn("瑞华泰公告", bundle.items[0].summary)
        self.assertIn("[L1]", bundle.to_prompt_block())

    def test_prompt_block_marks_l3_items_as_runtime_tool_evidence(self) -> None:
        bundle = L3EvidenceBundle(
            query="深挖飞凯材料",
            gaps=[
                L3EvidenceGap(
                    kind="hard_evidence_gap",
                    priority="P0",
                    reason="客户/订单/量产证据缺口",
                    source_types=("cninfo", "sse_einteract"),
                )
            ],
            items=[
                L3EvidenceItem(
                    source_type="sse_einteract",
                    title="飞凯材料互动易",
                    summary="公司确认感光干膜生产情况，但客户和收入占比仍需年报验证。",
                    citation="runtime mock",
                )
            ],
        )

        block = bundle.to_prompt_block()

        self.assertIn("L3 官方证据工具补查", block)
        self.assertIn("运行时工具证据", block)
        self.assertIn("客户/订单/量产", block)
        self.assertIn("飞凯材料互动易", block)


class AskL3IntegrationTests(unittest.TestCase):
    def test_compose_prompt_includes_l3_evidence_block_when_enabled(self) -> None:
        captured: dict[str, str] = {}
        fake_bundle = L3EvidenceBundle(
            query="深挖瑞华泰",
            gaps=[],
            items=[
                L3EvidenceItem(
                    source_type="cninfo",
                    title="瑞华泰公告",
                    summary="公告显示 PI 薄膜项目仍处于产能建设和客户验证阶段。",
                    citation="mock cninfo",
                )
            ],
        )

        def fake_synthesize(messages: list[dict], **_: object):
            captured["prompt"] = str(messages[1]["content"])
            return None, "mocked"

        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "intelligence.services.ask.l3_evidence.lookup_l3_evidence",
            return_value=fake_bundle,
        ), mock.patch(
            "intelligence.services.ask.llm_refine.synthesize_messages_stream",
            side_effect=fake_synthesize,
        ):
            wiki = Path(tmp) / "wiki"
            (wiki / "relations").mkdir(parents=True)
            result = answer_query(
                AskOptions(
                    query="深挖瑞华泰",
                    exports_dir=tmp,
                    kb_wiki=wiki,
                    use_modules=False,
                    use_wiki_rag=False,
                    compose=True,
                    use_l3_lookup=True,
                    grounded_presenter=False,
                )
            )

        self.assertTrue(result.l3_evidence.items)
        self.assertIn("L3 官方证据工具补查", captured["prompt"])
        self.assertIn("瑞华泰公告", captured["prompt"])


class L3TriageLevelFilterTests(unittest.TestCase):
    """P2/P3 是上游自己判的低信号档，不该被当成证据端上来。

    2026-08-14 实测：运行时模板要了 --sort triage 却没要 --level，于是
    「近 90 天没有相关公告」被降格成「5 条按分数排序的治理噪声」，
    一次公司题捞回 45 条 l3 证据、绑进答案 0 条。
    """

    def _rows(self, *levels: str) -> str:
        rows = [
            {
                "title": f"公告{idx}",
                "summary": f"公告{idx}正文摘要，含订单与客户口径。",
                "url": f"https://www.cninfo.com.cn/example{idx}",
                "source": "cninfo",
                **({"triage_level": lv} if lv else {}),
            }
            for idx, lv in enumerate(levels, start=1)
        ]
        return json.dumps(rows, ensure_ascii=False)

    def test_p2_p3_rows_are_not_minted_as_evidence(self) -> None:
        items = _try_parse_json_items("cninfo", self._rows("P2", "P3"))
        self.assertEqual(items, [])

    def test_p0_p1_rows_survive(self) -> None:
        items = _try_parse_json_items("cninfo", self._rows("P0", "P1"))
        self.assertEqual(len(items), 2)

    def test_rows_without_triage_level_are_kept_fail_open(self) -> None:
        """字段缺失时保留：门禁只拦它认得出的低信号，不因缺字段误杀。"""
        items = _try_parse_json_items("cninfo", self._rows("", ""))
        self.assertEqual(len(items), 2)

    def test_triage_filter_is_load_bearing(self) -> None:
        """变异测试：同一批载荷只改 triage_level，产出必须不同。

        没有这条，任何人把过滤删掉都不会有测试变红。
        """
        noisy = _try_parse_json_items("cninfo", self._rows("P2", "P2"))
        same_rows_unlabelled = _try_parse_json_items("cninfo", self._rows("", ""))
        self.assertEqual(len(noisy), 0)
        self.assertEqual(len(same_rows_unlabelled), 2)


    def test_empty_json_result_does_not_mint_fake_evidence(self) -> None:
        """CLI 合法返回空集时，不得落到纯文本兜底把 `[` 当成证据标题。

        这是先于 triage 过滤就存在的缺陷：`if parsed:` 把「JSON 解析出 0 条」
        和「不是 JSON」并成了一个 falsy 分支。
        """
        from intelligence.services.l3_evidence import _parse_lookup_output

        self.assertEqual(_parse_lookup_output("cninfo", "[]"), [])
        self.assertEqual(_parse_lookup_output("cninfo", self._rows("P2")), [])

    def test_non_json_output_still_falls_back_to_text(self) -> None:
        """兜底本身要留着：真的不是 JSON 时仍按行解析。"""
        from intelligence.services.l3_evidence import _parse_lookup_output

        items = _parse_lookup_output("cninfo", "瑞华泰公告：签订重大采购合同")
        self.assertTrue(items)


if __name__ == "__main__":
    unittest.main()
