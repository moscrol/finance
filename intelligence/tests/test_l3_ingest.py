from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from intelligence import cli
from intelligence.services import l3_ingest
from intelligence.services.l3_evidence import L3EvidenceBundle, L3EvidenceItem
from intelligence.workflows.l3_ingest import L3ApplyWorkflowOptions, L3IngestWorkflowOptions, run_l3_apply, run_l3_ingest


class L3IngestClassifierTests(unittest.TestCase):
    def test_capacity_progress_becomes_l3_candidate(self) -> None:
        item = l3_ingest.L3RawItem(
            source_type="cninfo",
            title="瑞华泰关于募投项目结项的公告",
            summary="公司披露 PI 薄膜募投项目已结项，产能建设进入新阶段。",
            citation="mock",
        )

        candidate = l3_ingest.classify_l3_item("瑞华泰", item)

        self.assertEqual(candidate.disposition, "candidate")
        self.assertEqual(candidate.fact_type, "capacity_or_project_progress")
        self.assertEqual(candidate.hardness, "medium")

    def test_bond_redemption_notice_is_rejected_as_noise(self) -> None:
        item = l3_ingest.L3RawItem(
            source_type="cninfo",
            title="瑞华泰关于实施“瑞科转债”赎回暨摘牌的提示性公告",
            summary="公司发布可转债赎回提示。",
            citation="mock",
        )

        candidate = l3_ingest.classify_l3_item("瑞华泰", item)

        self.assertEqual(candidate.disposition, "reject")
        self.assertEqual(candidate.evidence_layer, "not_l3")
        self.assertEqual(candidate.fact_type, "capital_market_or_governance_noise")

    def test_regulatory_or_risk_item_becomes_boundary_candidate(self) -> None:
        item = l3_ingest.L3RawItem(
            source_type="cninfo",
            title="某公司股票交易异常波动公告",
            summary="公司澄清目前无应披露而未披露重大事项，并提示风险。",
            citation="mock",
        )

        candidate = l3_ingest.classify_l3_item("某公司", item)

        self.assertEqual(candidate.disposition, "risk_boundary")
        self.assertEqual(candidate.evidence_layer, "L3_official")
        self.assertEqual(candidate.hardness, "high")


class L3IngestWorkflowTests(unittest.TestCase):
    def test_workflow_writes_candidate_payload(self) -> None:
        bundle = L3EvidenceBundle(
            query="瑞华泰",
            items=[
                L3EvidenceItem(
                    source_type="company",
                    title="瑞华泰关于募投项目结项的公告",
                    summary="公司披露 PI 薄膜募投项目已结项，产能建设进入新阶段。",
                    citation="mock cninfo",
                ),
                L3EvidenceItem(
                    source_type="company",
                    title="瑞华泰关于实施“瑞科转债”赎回暨摘牌的提示性公告",
                    summary="公司发布可转债赎回提示。",
                    citation="mock cninfo",
                ),
            ],
            commands=["python -m disclosure_lookup.cli company 瑞华泰"],
        )

        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "intelligence.services.l3_evidence.lookup_l3_company",
            return_value=bundle,
        ):
            out = Path(tmp) / "l3.json"
            summary, result, report = run_l3_ingest(
                L3IngestWorkflowOptions(company="瑞华泰", sources=("cninfo",), days=30, limit=10, out_json=out)
            )
            saved = out.read_text(encoding="utf-8")

        self.assertEqual(summary.status, "PASS")
        self.assertEqual(len(result.raw_items), 2)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(len(result.rejected), 1)
        self.assertIn("候选事实", report)
        self.assertIn("capacity_or_project_progress", saved)

    def test_cli_l3_ingest_company_routes_to_workflow(self) -> None:
        captured: dict[str, object] = {}
        fake_result = l3_ingest.L3IngestResult(company="瑞华泰", sources=("cninfo",), days=30)

        def fake_run(options: L3IngestWorkflowOptions):
            captured["options"] = options
            from intelligence.summary import WorkflowSummary, now_iso

            summary = WorkflowSummary(workflow="l3-ingest", status="WARN", started_at=now_iso())
            summary.finish("WARN")
            return summary, fake_result, "mock report\n"

        with mock.patch("intelligence.workflows.l3_ingest.run_l3_ingest", side_effect=fake_run), redirect_stdout(StringIO()):
            rc = cli.main(["l3-ingest", "company", "瑞华泰", "--source", "cninfo,sse_einteract", "--days", "7"])

        self.assertEqual(rc, 0)
        options = captured["options"]
        self.assertIsInstance(options, L3IngestWorkflowOptions)
        self.assertEqual(options.company, "瑞华泰")
        self.assertEqual(options.sources, ("cninfo", "sse_einteract"))
        self.assertEqual(options.days, 7)

    def test_apply_payload_dry_run_does_not_write_wiki(self) -> None:
        payload = l3_ingest.L3IngestResult(
            company="东方钽业",
            sources=("cninfo",),
            days=30,
            candidates=[
                l3_ingest.L3FactCandidate(
                    company="东方钽业",
                    source_type="cninfo",
                    title="东方钽业股票交易异常波动公告",
                    summary="公司披露异动风险提示。",
                    citation="mock",
                    fact_type="risk_or_regulatory_boundary",
                    evidence_layer="L3_official",
                    hardness="high",
                    disposition="risk_boundary",
                    reason="风险边界。",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            payload_path = Path(tmp) / "payload.json"
            payload.write_json(payload_path)
            summary, result, report = run_l3_apply(
                L3ApplyWorkflowOptions(payload_path=payload_path, kb_wiki=Path(tmp) / "wiki")
            )

            self.assertEqual(summary.status, "PASS")
            self.assertEqual(result.selected_count, 1)
            self.assertFalse(Path(result.source_note_path).exists())
            self.assertIn("dry-run", report)

    def test_apply_payload_writes_source_note_and_entity_section(self) -> None:
        payload = l3_ingest.L3IngestResult(
            company="东方钽业",
            sources=("cninfo",),
            days=30,
            candidates=[
                l3_ingest.L3FactCandidate(
                    company="东方钽业",
                    source_type="cninfo",
                    title="东方钽业股票交易异常波动公告",
                    summary="公司披露异动风险提示。",
                    citation="mock",
                    fact_type="risk_or_regulatory_boundary",
                    evidence_layer="L3_official",
                    hardness="high",
                    disposition="risk_boundary",
                    reason="风险边界。",
                    raw_excerpt="股票交易异常波动公告。",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            entity = wiki / "entities" / "东方钽业.md"
            entity.parent.mkdir(parents=True)
            entity.write_text(
                "---\n"
                "title: 东方钽业\n"
                "updated: 2026-06-21\n"
                "revision: 2\n"
                'sources: ["[[000962_东方钽业_逻辑卡_20260616]]"]\n'
                "---\n\n"
                "# 东方钽业\n",
                encoding="utf-8",
            )
            payload_path = Path(tmp) / "payload.json"
            payload.write_json(payload_path)

            summary, result, _report = run_l3_apply(
                L3ApplyWorkflowOptions(payload_path=payload_path, kb_wiki=wiki, apply=True)
            )
            source_text = Path(result.source_note_path).read_text(encoding="utf-8")
            entity_text = entity.read_text(encoding="utf-8")
            notes = l3_ingest.iter_applied_l3_notes(wiki, ["东方钽业"])
            lines = l3_ingest.format_applied_l3_lines(notes)

        self.assertEqual(summary.status, "PASS")
        self.assertEqual(len(result.created_sources), 1)
        self.assertEqual(len(result.updated_entities), 1)
        self.assertIn("review_required: true", source_text)
        self.assertIn("候选事实表", source_text)
        self.assertIn("## L3 官方证据", entity_text)
        self.assertIn("东方钽业_L3官方证据_", entity_text)
        self.assertEqual(result.landing, "wiki_page")
        self.assertFalse(result.relations_updated)
        self.assertEqual(result.next_gate, "disclosure-archive reviewed apply")
        self.assertEqual(len(notes), 1)
        self.assertTrue(any("landing=wiki_page" in line and "relations=false" in line for line in lines))
        self.assertTrue(any("东方钽业股票交易异常波动公告" in line for line in lines))

    def test_apply_payload_attaches_ticker_to_named_entity(self) -> None:
        payload = l3_ingest.L3IngestResult(
            company="000831",
            sources=("cninfo",),
            days=3,
            candidates=[
                l3_ingest.L3FactCandidate(
                    company="000831",
                    source_type="cninfo",
                    title="持股5%以上股东减持计划预披露",
                    summary="减持预披露。",
                    citation="mock",
                    fact_type="risk_or_regulatory_boundary",
                    evidence_layer="L3_official",
                    hardness="high",
                    disposition="risk_boundary",
                    reason="减持约束预期。",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            named = wiki / "entities" / "中国稀土.md"
            stub = wiki / "entities" / "000831.md"
            named.parent.mkdir(parents=True)
            named.write_text(
                "---\n"
                "title: 中国稀土\n"
                'tickers: ["000831"]\n'
                "updated: 2026-07-10\n"
                "revision: 3\n"
                "sources: []\n"
                "---\n\n"
                "# 中国稀土\n",
                encoding="utf-8",
            )
            stub.write_text("# leftover code stub\n", encoding="utf-8")
            payload_path = Path(tmp) / "payload.json"
            payload.write_json(payload_path)

            _summary, result, _report = run_l3_apply(
                L3ApplyWorkflowOptions(payload_path=payload_path, kb_wiki=wiki, apply=True)
            )

            self.assertTrue(Path(result.entity_path).name == "中国稀土.md")
            self.assertIn("## L3 官方证据", named.read_text(encoding="utf-8"))
            self.assertEqual(stub.read_text(encoding="utf-8"), "# leftover code stub\n")
            self.assertIn("中国稀土_L3官方证据_", Path(result.source_note_path).name)

    def test_cli_l3_apply_routes_to_workflow(self) -> None:
        captured: dict[str, object] = {}
        fake_result = l3_ingest.L3ApplyResult(
            company="瑞华泰",
            kb_wiki="/tmp/wiki",
            payload_path="/tmp/l3.json",
            apply=False,
            reviewed=False,
        )

        def fake_run(options: L3ApplyWorkflowOptions):
            captured["options"] = options
            from intelligence.summary import WorkflowSummary, now_iso

            summary = WorkflowSummary(workflow="l3-ingest-apply", status="PASS", started_at=now_iso())
            summary.finish("PASS")
            return summary, fake_result, "mock apply report\n"

        with mock.patch("intelligence.workflows.l3_ingest.run_l3_apply", side_effect=fake_run), redirect_stdout(StringIO()):
            rc = cli.main(["l3-ingest", "apply", "/tmp/l3.json", "--kb-wiki", "/tmp/wiki", "--apply", "--reviewed"])

        self.assertEqual(rc, 0)
        options = captured["options"]
        self.assertIsInstance(options, L3ApplyWorkflowOptions)
        self.assertEqual(str(options.payload_path), "/tmp/l3.json")
        self.assertEqual(str(options.kb_wiki), "/tmp/wiki")
        self.assertTrue(options.apply)
        self.assertTrue(options.reviewed)


class L3IngestSmokeTests(unittest.TestCase):
    def test_cli_help_imports_without_running_lookup(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "intelligence.cli", "l3-ingest", "company", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("公司名或股票代码", completed.stdout)


if __name__ == "__main__":
    unittest.main()
