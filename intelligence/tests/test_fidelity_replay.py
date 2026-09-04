from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from intelligence.eval.fidelity_replay import (
    aggregate_audits,
    audit_answer,
    build_gold_template,
    build_input_snapshot,
    select_pilot_dates,
)


def _answer(value: int = 3200, source_time: str = "2026-07-02") -> dict:
    return {
        "schema_version": "1.1",
        "date": "2026-07-03",
        "agent": "codex",
        "evidence_catalog": {
            "M1": {
                "level": "L4",
                "source": "fact_market_daily",
                "source_time": source_time,
                "entity": "market",
                "field": "advancers",
                "value": value,
                "direction": "support",
            }
        },
        "stage": "修复阶段",
        "stage_features": {"evidence_refs": ["M1"]},
        "main_judgment": "市场处于扩散修复",
        "direction_ranking": ["储能"],
        "picks": [
            {
                "code": "000001",
                "name": "平安银行",
                "reason": "量价较强",
                "evidence_refs": ["M1"],
            }
        ],
        "thresholds": {"market": "涨家数 > 3000"},
        "threshold_provenance": {"market": {"evidence_ref": "M1"}},
        "hypotheses": [
            {
                "id": "market",
                "claim": "T+1 继续修复",
                "evidence_refs": ["M1"],
            }
        ],
    }


def _manifest() -> dict:
    return {"perspective_date": "2026-07-02"}


class FidelityReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import duckdb
        except Exception:
            self.skipTest("duckdb is not installed")
        self.duckdb = duckdb

    def _db(self, root: Path) -> Path:
        path = root / "market.duckdb"
        con = self.duckdb.connect(str(path))
        try:
            con.execute(
                """
                CREATE TABLE fact_market_daily (
                    trade_date DATE,
                    advancers INTEGER,
                    market_stage VARCHAR,
                    updated_at TIMESTAMP
                )
                """
            )
            con.execute(
                """
                INSERT INTO fact_market_daily VALUES
                ('2026-07-01', 2800, '震荡', '2026-07-01 20:00:00'),
                ('2026-07-02', 3200, '修复', '2026-07-02 20:00:00'),
                ('2026-07-03', 3500, '修复', '2026-07-03 20:00:00')
                """
            )
            con.execute(
                """
                CREATE TABLE fact_sector_daily (
                    trade_date DATE,
                    sector_name VARCHAR,
                    pct_chg DOUBLE,
                    strength DOUBLE,
                    updated_at TIMESTAMP
                )
                """
            )
            con.execute(
                """
                INSERT INTO fact_sector_daily
                VALUES ('2026-07-02', '储能', 2.0, 8.0, '2026-07-02 20:00:00')
                """
            )
            con.execute(
                """
                CREATE TABLE fact_stock_daily (
                    trade_date DATE,
                    stock_ts_code VARCHAR,
                    stock_name VARCHAR,
                    pct_chg DOUBLE,
                    amount DOUBLE,
                    updated_at TIMESTAMP
                )
                """
            )
            con.execute(
                """
                INSERT INTO fact_stock_daily
                VALUES (
                    '2026-07-02', '000001.SZ', '平安银行', 1.0, 100.0,
                    '2026-07-02 20:00:00'
                )
                """
            )
        finally:
            con.close()
        return path

    def test_numeric_match_and_cutoff_are_measured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = self._db(Path(tmp))
            audit = audit_answer(_answer(), _manifest(), db_path=db)
            self.assertEqual(audit["metrics"]["numeric_match_rate"]["value"], 1.0)
            self.assertEqual(audit["metrics"]["cutoff_violation_rate"]["value"], 0.0)

            mismatch = audit_answer(_answer(value=3199), _manifest(), db_path=db)
            self.assertEqual(
                mismatch["metrics"]["numeric_match_rate"]["value"], 0.0
            )

            future = audit_answer(
                _answer(source_time="2026-07-03"), _manifest(), db_path=db
            )
            self.assertEqual(
                future["metrics"]["cutoff_violation_rate"]["value"], 1.0
            )

    def test_human_metrics_remain_pending_until_gold_is_filled(self) -> None:
        answer = _answer()
        template = build_gold_template(answer)
        pending = audit_answer(answer, _manifest(), gold=template)
        self.assertEqual(
            pending["metrics"]["entity_classification_accuracy"]["status"],
            "pending",
        )
        template["claims"]["main_judgment"].update(
            {
                "expected_type": "observation",
                "entity_classification": "fail",
                "timeline_sequence": "pass",
                "causal_evidence_binding": "fail",
            }
        )
        reviewed = audit_answer(answer, _manifest(), gold=template)
        self.assertGreater(
            reviewed["metrics"]["fact_inference_confusion_rate"]["value"], 0
        )
        self.assertEqual(
            reviewed["metrics"]["entity_classification_accuracy"]["value"], 0.0
        )

    def test_v10_answer_exposes_zero_evidence_coverage(self) -> None:
        answer = _answer()
        answer["schema_version"] = "1.0"
        answer.pop("evidence_catalog")
        audit = audit_answer(answer, _manifest())
        self.assertEqual(audit["metrics"]["evidence_coverage_rate"]["value"], 0.0)

    def test_snapshot_contains_no_future_market_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = self._db(Path(tmp))
            case = {
                "case_id": "FR-2026-07-02",
                "as_of": "2026-07-02",
                "target_date": "2026-07-03",
                "kb_snapshot": {"commit": "abc"},
                "status": "ready",
            }
            snapshot = build_input_snapshot(db, case)
            dates = {
                str(row["trade_date"])[:10]
                for row in snapshot["data"]["market_history"]
            }
            self.assertNotIn("2026-07-03", dates)
            self.assertEqual(
                snapshot["boundary"]["max_embedded_date"], "2026-07-02"
            )
            self.assertFalse(snapshot["boundary"]["outcome_data_included"])

    def test_strict_updated_at_default_is_unchanged_and_false_is_explicit(self) -> None:
        """缺省 strict：与旧行为逐字节一致（sha 相同、不多任何键）；显式 False 才放开 updated_at。"""
        with tempfile.TemporaryDirectory() as tmp:
            db = self._db(Path(tmp))
            con = self.duckdb.connect(str(db))
            try:
                # 后补行：trade_date 在 D0 之前，但 updated_at 在 D0 之后——strict 必须排除
                con.execute(
                    """
                    INSERT INTO fact_market_daily VALUES
                    ('2026-06-30', 2500, '震荡', '2026-07-10 20:00:00')
                    """
                )
            finally:
                con.close()
            case = {
                "case_id": "FR-2026-07-02",
                "as_of": "2026-07-02",
                "target_date": "2026-07-03",
                "kb_snapshot": {"commit": "abc"},
                "status": "ready",
            }
            default = build_input_snapshot(db, case)
            explicit_true = build_input_snapshot(db, case, strict_updated_at=True)
            self.assertEqual(default["snapshot_sha256"], explicit_true["snapshot_sha256"])
            self.assertNotIn("pit_grade", default["boundary"])
            self.assertEqual(
                set(default["boundary"]),
                {"max_allowed_date", "outcome_data_included", "max_embedded_date"},
            )
            strict_dates = {
                str(row["trade_date"])[:10] for row in default["data"]["market_history"]
            }
            self.assertNotIn("2026-06-30", strict_dates)

            relaxed = build_input_snapshot(db, case, strict_updated_at=False)
            relaxed_dates = {
                str(row["trade_date"])[:10] for row in relaxed["data"]["market_history"]
            }
            self.assertIn("2026-06-30", relaxed_dates)
            self.assertNotIn("2026-07-03", relaxed_dates)
            self.assertEqual(relaxed["boundary"]["pit_grade"], "trade_date_only")
            self.assertEqual(relaxed["boundary"]["max_embedded_date"], "2026-07-02")
            self.assertNotEqual(relaxed["snapshot_sha256"], default["snapshot_sha256"])

    def test_pilot_selection_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = self._db(Path(tmp))
            first = select_pilot_dates(
                db, "2026-07-01", "2026-07-03", count=2
            )
            second = select_pilot_dates(
                db, "2026-07-01", "2026-07-03", count=2
            )
            self.assertEqual(first, second)
            self.assertEqual(len(first), 2)
            self.assertTrue(any(case["target_date"] for case in first))
            self.assertEqual(
                len(select_pilot_dates(db, "2026-07-01", "2026-07-03", count=1)),
                1,
            )
            self.assertEqual(
                select_pilot_dates(db, "2026-07-01", "2026-07-03", count=0),
                [],
            )
            # only_dates 缺省 = 旧行为；给定子集时只在子集里抽
            self.assertEqual(
                select_pilot_dates(db, "2026-07-01", "2026-07-03", count=2, only_dates=None),
                first,
            )
            subset = select_pilot_dates(
                db, "2026-07-01", "2026-07-03", count=2, only_dates={"2026-07-01"}
            )
            self.assertEqual([case["as_of"] for case in subset], ["2026-07-01"])

    def test_explicit_claim_schema_is_supported(self) -> None:
        answer = {
            "schema_version": "fidelity-replay-answer-1.0",
            "claims": [
                {
                    "id": "F1",
                    "text": "涨家数为 3200",
                    "declared_type": "observation",
                    "evidence_refs": ["M1"],
                }
            ],
            "evidence_catalog": {
                "M1": {
                    "source": "fact_market_daily",
                    "source_time": "2026-07-02",
                    "field": "advancers",
                    "value": 3200,
                }
            },
        }
        audit = audit_answer(answer, _manifest())
        self.assertEqual(audit["counts"]["claims"], 1)
        self.assertEqual(audit["metrics"]["evidence_coverage_rate"]["value"], 1.0)

    def test_numeric_audit_prefers_frozen_snapshot(self) -> None:
        snapshot = {
            "data": {
                "market_history": [
                    {"trade_date": "2026-07-02", "advancers": 3200}
                ]
            }
        }
        audit = audit_answer(
            _answer(), _manifest(), input_snapshot=snapshot
        )
        self.assertEqual(audit["metrics"]["numeric_match_rate"]["value"], 1.0)

    def test_backfilled_database_row_is_not_treated_as_pit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = self._db(Path(tmp))
            con = self.duckdb.connect(str(db))
            try:
                con.execute(
                    """
                    UPDATE fact_market_daily
                    SET updated_at = '2026-07-10 20:00:00'
                    WHERE trade_date = '2026-07-02'
                    """
                )
            finally:
                con.close()
            audit = audit_answer(_answer(), _manifest(), db_path=db)
            metric = audit["metrics"]["numeric_match_rate"]
            self.assertIsNone(metric["value"])
            self.assertEqual(metric["pending"], 1)

    def test_aggregate_preserves_pending_counts(self) -> None:
        audit = audit_answer(_answer(), _manifest())
        report = aggregate_audits([audit])
        self.assertEqual(report["answers"], 1)
        self.assertGreater(
            report["metrics"]["entity_classification_accuracy"]["pending"], 0
        )
        self.assertFalse(report["decision_eligible"])


if __name__ == "__main__":
    unittest.main()
