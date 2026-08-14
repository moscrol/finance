from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "dual_blind_forecast",
    Path(__file__).resolve().parents[2] / "scripts" / "dual_blind_forecast.py",
)
dual_blind_forecast = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(dual_blind_forecast)


def _answer(date: str, agent: str, manifest_sha: str, recheck: dict | None = None) -> dict:
    return {
        "schema_version": "1.0",
        "date": date,
        "agent": agent,
        "manifest_sha": manifest_sha,
        "stage": "底部横盘第3天",
        "main_judgment": "扩散修复承接",
        "direction_ranking": ["储能", "创新药"],
        "picks": [{"code": "688323", "name": "瑞华泰", "strategy": "策略三", "reason": "UP回踩"}],
        "thresholds": {"market": "涨家数>3500", "direction": "储能diff>0", "targets": "逐只触发价", "falsify": "缩量跌破"},
        "recheck": recheck or {},
    }


def _answer_v11(date: str, agent: str, manifest_sha: str) -> dict:
    answer = _answer(date, agent, manifest_sha)
    answer["schema_version"] = "1.1"
    answer["evidence_catalog"] = {
        "M1": {
            "level": "L4",
            "source": "fact_market_daily",
            "source_time": "2026-07-02",
            "field": "advancers",
            "value": 3200,
            "direction": "support",
        },
        "R1": {
            "level": "L2",
            "source": "strategy1-matrix",
            "source_time": "2026-07-02",
            "direction": "neutral",
        },
    }
    answer["stage_features"] = {
        "rule_id": "market-stage-v1",
        "as_of": "2026-07-02",
        "metrics": {"advancers": {"value": 3200, "evidence_ref": "M1"}},
        "evidence_refs": ["M1"],
    }
    answer["threshold_provenance"] = {
        field: {
            "origin": origin,
            "evidence_ref": "M1" if field in {"market", "targets"} else "R1",
            "as_of": "2026-07-02",
        }
        for field, origin in {
            "market": "backtest",
            "direction": "fixed_rule",
            "targets": "mechanical",
            "falsify": "heuristic",
        }.items()
    }
    answer["picks"][0]["evidence_refs"] = ["M1"]
    answer["picks"][0]["evidence_as_of"] = "2026-07-02"
    answer["hypotheses"] = [
        {
            "id": "market",
            "category": "market",
            "claim": "T+1 涨家数超过 3500",
            "horizon": "T+1",
            "confidence": "medium",
            "confidence_probability": 0.6,
            "evidence_refs": ["M1"],
            "evidence_as_of": "2026-07-02",
            "falsify_when": "T+1 涨家数低于 2500",
        }
    ]
    return answer


class DualBlindForecastTests(unittest.TestCase):
    def test_namespaced_hypotheses_keep_their_category(self) -> None:
        self.assertEqual(
            dual_blind_forecast._hypothesis_category("direction:medicine"),
            "direction",
        )
        self.assertEqual(
            dual_blind_forecast._hypothesis_category("market:path"),
            "market",
        )
        self.assertEqual(
            dual_blind_forecast._hypothesis_category("target:300308.SZ"),
            "target",
        )

    def test_calibration_metrics_expose_ranking_and_probability_error(self) -> None:
        metrics = dual_blind_forecast._calibration_metrics(
            [(0.9, 1), (0.8, 1), (0.2, 0), (0.1, 0)]
        )
        self.assertEqual(metrics["n"], 4)
        self.assertEqual(metrics["auc"], 1.0)
        self.assertEqual(metrics["brier"], 0.025)
        self.assertFalse(metrics["decision_eligible"])

    def test_manifest_then_validate_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            material = ledger / "material.md"
            material.write_text("盘前材料", encoding="utf-8")
            rc = dual_blind_forecast.main(
                [
                    "--ledger-dir",
                    str(ledger),
                    "manifest",
                    "--date",
                    "2026-07-03",
                    "--perspective",
                    "2026-07-02",
                    "--material",
                    str(material),
                    "--db",
                    str(ledger / "missing.duckdb"),
                ]
            )
            self.assertEqual(rc, 0)
            manifest = json.loads((ledger / "2026-07-03.manifest.json").read_text(encoding="utf-8"))
            self.assertIsNone(manifest["duckdb_cutoff"])
            self.assertTrue(manifest["warnings"])
            self.assertEqual(len(manifest["materials"]), 1)

            answer_path = ledger / "2026-07-03.answer.codex.json"
            answer_path.write_text(
                json.dumps(_answer("2026-07-03", "codex", manifest["manifest_sha"]), ensure_ascii=False),
                encoding="utf-8",
            )
            self.assertEqual(dual_blind_forecast.validate_answer(answer_path, ledger_dir=ledger), [])

    def test_schema_v11_requires_provenance_and_rejects_future_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            dual_blind_forecast.main(
                [
                    "--ledger-dir",
                    str(ledger),
                    "manifest",
                    "--date",
                    "2026-07-03",
                    "--perspective",
                    "2026-07-02",
                    "--db",
                    str(ledger / "x.duckdb"),
                ]
            )
            manifest = json.loads(
                (ledger / "2026-07-03.manifest.json").read_text(encoding="utf-8")
            )
            answer = _answer_v11("2026-07-03", "codex", manifest["manifest_sha"])
            path = ledger / "2026-07-03.answer.codex.json"
            path.write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(
                dual_blind_forecast.validate_answer(path, ledger_dir=ledger), []
            )

            answer["threshold_provenance"]["market"]["origin"] = "guess"
            answer["picks"][0]["evidence_as_of"] = "2026-07-03"
            answer["stage_features"]["metrics"]["advancers"]["value"] = 3100
            path.write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
            errors = "\n".join(
                dual_blind_forecast.validate_answer(path, ledger_dir=ledger)
            )
            self.assertIn("origin", errors)
            self.assertIn("晚于输入截止", errors)
            self.assertIn("数值", errors)

    def test_validate_catches_stale_manifest_and_missing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            dual_blind_forecast.main(
                ["--ledger-dir", str(ledger), "manifest", "--date", "2026-07-03", "--perspective", "2026-07-02", "--db", str(ledger / "x.duckdb")]
            )
            bad = _answer("2026-07-03", "codex", "deadbeef00000000")
            bad["thresholds"].pop("falsify")
            bad_path = ledger / "2026-07-03.answer.codex.json"
            bad_path.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            errors = dual_blind_forecast.validate_answer(bad_path, ledger_dir=ledger)
            joined = "\n".join(errors)
            self.assertIn("manifest_sha 不一致", joined)
            self.assertIn("falsify", joined)

    def test_duckdb_cutoff_prefers_canonical_fact_market_daily(self) -> None:
        try:
            import duckdb
        except Exception:
            self.skipTest("duckdb is not installed")

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "mfs.duckdb"
            con = duckdb.connect(str(db_path))
            try:
                con.execute("CREATE TABLE fact_market_daily (trade_date DATE)")
                con.execute("INSERT INTO fact_market_daily VALUES (DATE '2026-07-03')")
            finally:
                con.close()

            self.assertEqual(dual_blind_forecast._duckdb_max_trade_date(db_path), "2026-07-03")

    def test_aggregate_per_agent_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            (ledger / "2026-07-01.answer.codex.json").write_text(
                json.dumps(
                    _answer(
                        "2026-07-01",
                        "codex",
                        "sha1",
                        recheck={"pick_returns_t1": [1.0, -2.0], "pick_returns_t3": [3.0, 1.0], "beat_benchmark_t3": True, "market_threshold_hit": True},
                    ),
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (ledger / "2026-07-01.answer.claude.json").write_text(
                json.dumps(_answer("2026-07-01", "claude", "sha1"), ensure_ascii=False),
                encoding="utf-8",
            )
            report = dual_blind_forecast.aggregate(ledger)
            codex = report["agents"]["codex/duckdb"]
            self.assertEqual(codex["answers"], 1)
            self.assertEqual(codex["rechecked"], 1)
            self.assertEqual(codex["avg_pick_return_t1"], -0.5)
            self.assertEqual(codex["avg_pick_return_t3"], 2.0)
            self.assertEqual(codex["market_threshold_hit_rate"], 1.0)
            claude = report["agents"]["claude/duckdb"]
            self.assertEqual(claude["rechecked"], 0)
            self.assertIsNone(claude["avg_pick_return_t1"])

    def test_validate_rejects_unknown_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            dual_blind_forecast.main(
                ["--ledger-dir", str(ledger), "manifest", "--date", "2026-07-03", "--perspective", "2026-07-02", "--db", str(ledger / "x.duckdb")]
            )
            manifest = json.loads((ledger / "2026-07-03.manifest.json").read_text(encoding="utf-8"))
            answer = _answer("2026-07-03", "codex", manifest["manifest_sha"])
            answer["source"] = "twitter"
            path = ledger / "2026-07-03.answer.codex.json"
            path.write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
            errors = dual_blind_forecast.validate_answer(path, ledger_dir=ledger)
            self.assertIn("source", "\n".join(errors))

    def test_aggregate_splits_by_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            a1 = _answer("2026-07-01", "codex", "sha1")
            a2 = _answer("2026-07-02", "codex", "sha2")
            a2["source"] = "sellside"
            (ledger / "2026-07-01.answer.codex.json").write_text(json.dumps(a1, ensure_ascii=False), encoding="utf-8")
            (ledger / "2026-07-02.answer.codex.json").write_text(json.dumps(a2, ensure_ascii=False), encoding="utf-8")
            report = dual_blind_forecast.aggregate(ledger)
            self.assertEqual(report["agents"]["codex/duckdb"]["answers"], 1)
            self.assertEqual(report["agents"]["codex/sellside"]["answers"], 1)

    def test_aggregate_splits_verdicts_by_source_category_and_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            answer = _answer("2026-07-01", "codex", "sha1")
            answer["source"] = "sellside"
            answer["hypotheses"] = [
                {
                    "id": "direction",
                    "category": "direction",
                    "confidence": "high",
                    "confidence_probability": 0.8,
                }
            ]
            (ledger / "2026-07-01.answer.codex.sellside.json").write_text(
                json.dumps(answer, ensure_ascii=False), encoding="utf-8"
            )
            verdict = {
                "date": "2026-07-01",
                "verdicts": [
                    {
                        "id": "direction",
                        "agent": "codex",
                        "stream": "卖方",
                        "horizon": "T+3",
                        "verdict": "miss",
                        "actual": "方向未延续",
                    }
                ],
            }
            (ledger / "2026-07-01.verdict.json").write_text(
                json.dumps(verdict, ensure_ascii=False), encoding="utf-8"
            )

            stat = dual_blind_forecast.aggregate(ledger)["agents"]["codex/sellside"]
            self.assertEqual(
                stat["verdicts_by_stream_horizon"]["卖方/T+3"]["miss"], 1
            )
            self.assertEqual(stat["verdicts_by_category"]["direction"]["miss"], 1)
            self.assertEqual(stat["verdicts_by_confidence"]["high"]["miss"], 1)
            self.assertEqual(stat["calibration_metrics"]["n"], 1)
            self.assertEqual(stat["calibration_metrics"]["brier"], 0.64)
            self.assertFalse(stat["calibration_metrics"]["decision_eligible"])

    def test_multi_source_filenames_same_day(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            dual_blind_forecast.main(
                ["--ledger-dir", str(ledger), "manifest", "--date", "2026-07-03", "--perspective", "2026-07-02", "--db", str(ledger / "x.duckdb")]
            )
            manifest = json.loads((ledger / "2026-07-03.manifest.json").read_text(encoding="utf-8"))
            for agent in ("codex", "claude"):
                for source in ("duckdb", "briefing", "sellside"):
                    answer = _answer("2026-07-03", agent, manifest["manifest_sha"])
                    answer["source"] = source
                    path = ledger / f"2026-07-03.answer.{agent}.{source}.json"
                    path.write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
                    self.assertEqual(dual_blind_forecast.validate_answer(path, ledger_dir=ledger), [])
            paths = dual_blind_forecast.answer_paths_for("2026-07-03", ledger)
            self.assertEqual(len(paths), 6)
            self.assertIn("codex.briefing", paths)
            self.assertEqual(dual_blind_forecast.parse_answer_filename("2026-07-03.answer.codex.briefing.json"), ("codex", "briefing"))
            self.assertEqual(dual_blind_forecast.parse_answer_filename("2026-07-03.answer.codex.json"), ("codex", None))
            draft = {
                "date": "2026-07-03",
                "verdicts": [{
                    "id": "market",
                    "agent": "codex",
                    "source": "duckdb",
                    "verdict": "hit",
                    "actual": "涨家数3804",
                }],
            }
            self.assertEqual(dual_blind_forecast.validate_verdict(draft, ledger_dir=ledger), [])

    def test_validate_catches_filename_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            dual_blind_forecast.main(
                ["--ledger-dir", str(ledger), "manifest", "--date", "2026-07-03", "--perspective", "2026-07-02", "--db", str(ledger / "x.duckdb")]
            )
            manifest = json.loads((ledger / "2026-07-03.manifest.json").read_text(encoding="utf-8"))
            answer = _answer("2026-07-03", "codex", manifest["manifest_sha"])
            answer["source"] = "sellside"
            path = ledger / "2026-07-03.answer.codex.briefing.json"
            path.write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
            errors = dual_blind_forecast.validate_answer(path, ledger_dir=ledger)
            self.assertIn("文件名 source=briefing", "\n".join(errors))

    def test_recheck_autofill_from_duckdb(self) -> None:
        try:
            import duckdb
        except ImportError:
            self.skipTest("duckdb 不可用")
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            db_path = ledger / "mini.duckdb"
            con = duckdb.connect(str(db_path))
            con.execute("CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code TEXT, close DOUBLE, pre_close DOUBLE, pct_chg DOUBLE)")
            con.execute(
                "INSERT INTO fact_stock_daily VALUES "
                "('2026-07-03','688323.SH',102.0,100.0,2.0),"
                "('2026-07-06','688323.SH',103.0,102.0,0.98),"
                "('2026-07-07','688323.SH',110.0,103.0,6.8)"
            )
            con.execute("CREATE TABLE fact_market_daily (trade_date DATE, sh_index_close DOUBLE)")
            con.execute("INSERT INTO fact_market_daily VALUES ('2026-07-02',3000.0),('2026-07-07',3030.0)")
            con.close()
            dual_blind_forecast.main(
                ["--ledger-dir", str(ledger), "manifest", "--date", "2026-07-03", "--perspective", "2026-07-02", "--db", str(db_path)]
            )
            manifest = json.loads((ledger / "2026-07-03.manifest.json").read_text(encoding="utf-8"))
            answer = _answer("2026-07-03", "codex", manifest["manifest_sha"])
            answer["recheck"] = {"market_threshold_hit": True}
            path = ledger / "2026-07-03.answer.codex.json"
            path.write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
            rc = dual_blind_forecast.main(["--ledger-dir", str(ledger), "recheck", str(path), "--db", str(db_path)])
            self.assertEqual(rc, 0)
            updated = json.loads(path.read_text(encoding="utf-8"))["recheck"]
            self.assertEqual(updated["recheck_t1_date"], "2026-07-03")
            self.assertEqual(updated["recheck_t3_date"], "2026-07-07")
            self.assertEqual(updated["pick_returns_t1"], [2.0])
            self.assertEqual(updated["pick_returns_t3"], [10.0])
            self.assertEqual(updated["benchmark"], "sh000001")
            self.assertEqual(updated["benchmark_return_t3"], 1.0)
            self.assertTrue(updated["beat_benchmark_t3"])
            self.assertTrue(updated["market_threshold_hit"])  # 人工字段不被覆盖


if __name__ == "__main__":
    unittest.main()
