import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence.services.fidelity_contract import contract_errors
from intelligence.services.theme_radar import ThemeRadarService
from intelligence.workflows.theme_radar import (
    ThemeRadarOptions,
    run_theme_radar,
)

_RADAR_SPEC = importlib.util.spec_from_file_location(
    "theme_radar_script",
    Path(__file__).resolve().parents[1] / "skills" / "theme-radar" / "scripts" / "radar.py",
)
radar_script = importlib.util.module_from_spec(_RADAR_SPEC)
assert _RADAR_SPEC and _RADAR_SPEC.loader
sys.modules["theme_radar_script"] = radar_script
_RADAR_SPEC.loader.exec_module(radar_script)


class RelationsFreshnessTests(unittest.TestCase):
    def test_timezone_aware_updated_at_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            relations = vault / "relations"
            relations.mkdir()
            (relations / "meta.json").write_text(
                json.dumps(
                    {
                        "schema_version": radar_script.RELATIONS_SCHEMA_VERSION,
                        "updated_at": "2000-01-01T12:00:00+08:00",
                    }
                ),
                encoding="utf-8",
            )
            warnings = radar_script.relations_freshness_warnings(vault)
            self.assertTrue(any("relations 数据已" in warning for warning in warnings))


SOURCE_META = {
    "table": "fact_sector_daily",
    "entity": "885864.TI",
    "valid_time": "2026-06-11",
    "source_time": "2026-06-11T18:00:00",
    "source": "fixture",
    "source_artifact": "db/market_feature_store.duckdb",
}


class FakeMarketAdapter:
    def get_market_daily(self, date):
        return {
            "found": True,
            "trade_date": date,
            "data": {
                "market_stage": "上升阶段",
                "total_amount": 1000,
                "advancers": 3000,
                "limit_up": 80,
                "limit_down": 2,
            },
            "warnings": [],
            "errors": [],
        }

    def get_capacity_sectors(self, date, top=3):
        return {
            "found": True,
            "trade_date": date,
            "top3_industry_ratio": 45.0,
            "capacity_sectors": [
                {
                    "rank": 1,
                    "name": "电子",
                    "ratio": 20.0,
                    "capacity_type": "capacity",
                    "_source_meta": {
                        **SOURCE_META,
                        "table": "fact_market_daily",
                        "entity": "market",
                    },
                    "_source_fields": {
                        "name": "industry_1",
                        "ratio": "industry_1_ratio",
                    },
                }
            ][:top],
            "warnings": [],
            "errors": [],
        }

    def get_double_red_themes(self, date, top=50):
        return {
            "found": True,
            "trade_date": date,
            "count": 1,
            "themes": [
                {
                    "sector_ts_code": "885864.TI",
                    "sector_name": "光刻胶",
                    "sw_l1": "电子",
                    "pct_chg": 2.21,
                    "diff_ratio": 31.59,
                    "amount": 954.38,
                    "in_capacity_top3": True,
                    "_source_meta": SOURCE_META,
                }
            ][:top],
            "warnings": [],
            "errors": [],
        }

    def get_limit_heat_themes(self, date):
        return self._empty(date)

    def get_limit_advance_clusters(self, date):
        return self._empty(date)

    def get_period_rank_themes(self, date):
        return self._empty(date)

    def get_new_high_directions(self, date):
        return self._empty(date)

    def get_theme_stock_signals(self, date, themes):
        return {
            "found": True,
            "trade_date": date,
            "signals": {},
            "warnings": [],
            "errors": [],
        }

    @staticmethod
    def _empty(date):
        return {
            "found": True,
            "trade_date": date,
            "count": 0,
            "themes": [],
            "warnings": [],
            "errors": [],
        }


class FakeKnowledgeAdapter:
    def get_evidence(self, target, limit=5):
        return {"found": False, "items": [], "warnings": [], "errors": []}

    def get_concept_matches(self, target, limit=5):
        return {"found": False, "items": [], "warnings": [], "errors": []}

    def get_exposure_matches(self, target, limit=5):
        return {"found": False, "items": [], "warnings": [], "errors": []}


class ThemeRadarLineageTests(unittest.TestCase):
    def test_market_candidate_materializes_claim_level_lineage(self):
        service = ThemeRadarService(
            market_adapter=FakeMarketAdapter(),
            knowledge_adapter=FakeKnowledgeAdapter(),
        )
        report = service.build_market_triggered_candidates(
            "2026-06-11",
            top=10,
        )
        candidate = report["candidates"][0]
        ref_id = candidate["evidence_refs"]["sector_metrics.pct_chg"][0]
        source_ref = report["evidence_catalog"][ref_id]

        self.assertEqual(report["lineage_schema_version"], "claim-lineage-v1")
        self.assertEqual(source_ref["scope"], "claim")
        self.assertEqual(source_ref["table"], "fact_sector_daily")
        self.assertEqual(source_ref["field"], "pct_chg")
        self.assertEqual(source_ref["entity"], "885864.TI")
        self.assertEqual(source_ref["valid_time"], "2026-06-11")
        self.assertEqual(source_ref["source_time"], "2026-06-11T18:00:00")
        self.assertEqual(source_ref["source_unit"], "%")
        derived_ref_id = candidate["evidence_refs"][
            "sector_metrics.in_capacity_top3"
        ][0]
        derived_ref = report["evidence_catalog"][derived_ref_id]
        self.assertEqual(derived_ref["source_kind"], "derived")
        self.assertIn("derivation", derived_ref)
        input_refs = derived_ref["derivation"]["input_evidence_refs"]
        self.assertEqual(len(input_refs), 2)
        self.assertTrue(
            all(ref_id in report["evidence_catalog"] for ref_id in input_refs)
        )
        capacity_ref_id = candidate["evidence_refs"]["capacity_sector.ratio"][0]
        capacity_ref = report["evidence_catalog"][capacity_ref_id]
        self.assertEqual(capacity_ref["field"], "industry_1_ratio")
        capacity_type_ref_id = candidate["evidence_refs"][
            "capacity_sector.capacity_type"
        ][0]
        capacity_type_ref = report["evidence_catalog"][capacity_type_ref_id]
        self.assertEqual(capacity_type_ref["source_kind"], "derived")
        self.assertEqual(
            capacity_type_ref["derivation"]["input_evidence_refs"],
            [capacity_ref_id],
        )
        self.assertNotIn("_source_meta", candidate["market_evidence"])

    def test_theme_workflow_seals_candidate_artifact(self):
        service = ThemeRadarService(
            market_adapter=FakeMarketAdapter(),
            knowledge_adapter=FakeKnowledgeAdapter(),
        )
        result = service.build_market_triggered_candidates(
            "2026-06-11",
            top=10,
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "candidates.json"
            with mock.patch(
                "intelligence.workflows.theme_radar.ThemeRadarService"
            ) as service_type:
                service_type.return_value.build_market_triggered_candidates.return_value = (
                    result
                )
                summary = run_theme_radar(
                    ThemeRadarOptions(
                        date="2026-06-11",
                        market_triggered=True,
                        out_json=str(out),
                    )
                )
            body = json.loads(out.read_text(encoding="utf-8"))
            manifest_payload = {
                "lineage_schema_version": body["lineage_schema_version"],
                "evidence_catalog": body["evidence_catalog"],
                "candidate_evidence_refs": [
                    candidate.get("evidence_refs")
                    for candidate in body["candidates"]
                ],
            }

            self.assertEqual(summary.status, "PASS")
            self.assertEqual(
                body["fidelity_contract_version"],
                "fidelity-contract-1.2",
            )
            self.assertEqual(
                contract_errors(
                    body,
                    manifest_payload=manifest_payload,
                ),
                [],
            )


if __name__ == "__main__":
    unittest.main()
