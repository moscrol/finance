from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence.services.answer_orchestrator import (
    QUESTION_MARKET_FORECAST,
    QUESTION_STOCK_DEEP_DIVE,
    plan_answer_question,
)
from intelligence.services.ask import AskOptions, answer_query
from intelligence.services.l3_evidence import (
    L3LookupConfig,
    L3EvidenceBundle,
    L3EvidenceGap,
    L3EvidenceItem,
    lookup_l3_evidence,
)


class L3EvidenceDetectionTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
