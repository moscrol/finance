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


def _write_manifest(ledger: Path, date: str, manifest_sha: str) -> None:
    (ledger / f"{date}.manifest.json").write_text(
        json.dumps({"schema_version": "1.0", "date": date, "manifest_sha": manifest_sha}, ensure_ascii=False),
        encoding="utf-8",
    )


class DualBlindForecastTests(unittest.TestCase):
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

    def test_manifest_reads_fact_market_daily_cutoff(self) -> None:
        try:
            import duckdb
        except ImportError:
            self.skipTest("duckdb is not installed")

        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            db_path = ledger / "market.duckdb"
            con = duckdb.connect(str(db_path))
            try:
                con.execute("CREATE TABLE fact_market_daily(trade_date DATE)")
                con.execute("INSERT INTO fact_market_daily VALUES (DATE '2026-07-02')")
            finally:
                con.close()

            rc = dual_blind_forecast.main(
                [
                    "--ledger-dir",
                    str(ledger),
                    "manifest",
                    "--date",
                    "2026-07-03",
                    "--perspective",
                    "2026-07-02",
                    "--db",
                    str(db_path),
                ]
            )

            self.assertEqual(rc, 0)
            manifest = json.loads((ledger / "2026-07-03.manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["duckdb_cutoff"], "2026-07-02")
            self.assertEqual(manifest["warnings"], [])

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
            _write_manifest(ledger, "2026-07-03", "sha-source")
            answer = _answer("2026-07-03", "codex", "sha-source")
            answer["source"] = "twitter"
            path = ledger / "2026-07-03.answer.codex.json"
            path.write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")

            errors = dual_blind_forecast.validate_answer(path, ledger_dir=ledger)
            self.assertIn("source", "\n".join(errors))

    def test_aggregate_splits_by_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            duckdb_answer = _answer("2026-07-01", "codex", "sha1")
            sellside_answer = _answer("2026-07-02", "codex", "sha2")
            sellside_answer["source"] = "sellside"
            (ledger / "2026-07-01.answer.codex.json").write_text(json.dumps(duckdb_answer, ensure_ascii=False), encoding="utf-8")
            (ledger / "2026-07-02.answer.codex.json").write_text(json.dumps(sellside_answer, ensure_ascii=False), encoding="utf-8")

            report = dual_blind_forecast.aggregate(ledger)
            self.assertEqual(report["agents"]["codex/duckdb"]["answers"], 1)
            self.assertEqual(report["agents"]["codex/sellside"]["answers"], 1)

    def test_validate_accepts_forecast_flow_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            _write_manifest(ledger, "2026-07-03", "sha-flow")
            answer = _answer("2026-07-03", "codex", "sha-flow")
            answer["flow_entries"] = [
                {
                    "flow_type": "duckdb_market",
                    "flow_name": "DuckDB 盘面流",
                    "validation_windows": ["T+1"],
                    "hypothesis_ids": ["market:path-20260703"],
                }
            ]
            answer["hypotheses"] = [
                {
                    "id": "market:path-20260703",
                    "flow_type": "duckdb_market",
                    "type": "market_path",
                    "checks": [{"name": "advancers", "metric": "advancers", "operator": ">=", "threshold": 2500}],
                    "falsifiers": [{"name": "path_failed", "condition": "涨停<70且跌停>50"}],
                }
            ]
            path = ledger / "2026-07-03.answer.codex.json"
            path.write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")

            self.assertEqual(dual_blind_forecast.validate_answer(path, ledger_dir=ledger), [])

    def test_validate_rejects_flow_reference_to_missing_hypothesis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            _write_manifest(ledger, "2026-07-03", "sha-flow")
            answer = _answer("2026-07-03", "codex", "sha-flow")
            answer["flow_entries"] = [
                {
                    "flow_type": "duckdb_market",
                    "validation_windows": ["T+1"],
                    "hypothesis_ids": ["market:missing"],
                }
            ]
            answer["hypotheses"] = [{"id": "market:path-20260703", "flow_type": "duckdb_market"}]
            path = ledger / "2026-07-03.answer.codex.json"
            path.write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")

            errors = dual_blind_forecast.validate_answer(path, ledger_dir=ledger)
            self.assertIn("market:missing", "\n".join(errors))

    def test_validate_verdict_rejects_invalid_flow_type_and_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            _write_manifest(ledger, "2026-07-03", "sha-flow")
            answer = _answer("2026-07-03", "codex", "sha-flow")
            answer["hypotheses"] = [{"id": "market:path-20260703", "flow_type": "duckdb_market"}]
            (ledger / "2026-07-03.answer.codex.json").write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
            draft = {
                "date": "2026-07-03",
                "verdicts": [
                    {
                        "id": "market:path-20260703",
                        "agent": "codex",
                        "flow_type": "unknown_flow",
                        "window": "T+9",
                        "verdict": "miss",
                        "actual": "实际路径失败",
                    }
                ],
            }

            errors = dual_blind_forecast.validate_verdict(draft, ledger_dir=ledger)
            joined = "\n".join(errors)
            self.assertIn("flow_type", joined)
            self.assertIn("window", joined)

    def test_aggregate_counts_verdicts_by_flow_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            _write_manifest(ledger, "2026-07-03", "sha-flow")
            answer = _answer("2026-07-03", "codex", "sha-flow")
            answer["hypotheses"] = [
                {"id": "market:path-20260703", "flow_type": "duckdb_market"},
                {"id": "sellside:diamond-heat", "flow_type": "sellside_cross"},
            ]
            (ledger / "2026-07-03.answer.codex.json").write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
            (ledger / "2026-07-03.verdict.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "date": "2026-07-03",
                        "verdicts": [
                            {"id": "market:path-20260703", "agent": "codex", "flow_type": "duckdb_market", "window": "T+1", "verdict": "hit", "actual": "命中"},
                            {"id": "sellside:diamond-heat", "agent": "codex", "flow_type": "sellside_cross", "window": "T+3", "verdict": "miss", "actual": "未确认"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = dual_blind_forecast.aggregate(ledger)
            self.assertEqual(report["flow_stats"]["duckdb_market"]["hit"], 1)
            self.assertEqual(report["flow_stats"]["duckdb_market"]["judged"], 1)
            self.assertEqual(report["flow_stats"]["duckdb_market"]["hit_rate"], 1.0)
            self.assertEqual(report["flow_stats"]["sellside_cross"]["miss"], 1)
            self.assertEqual(report["flow_stats"]["sellside_cross"]["hit_rate"], 0.0)

    def test_recheck_autofill_from_duckdb(self) -> None:
        try:
            import duckdb
        except ImportError:
            self.skipTest("duckdb is not installed")

        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            db_path = ledger / "mini.duckdb"
            con = duckdb.connect(str(db_path))
            try:
                con.execute("CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code TEXT, close DOUBLE, pre_close DOUBLE, pct_chg DOUBLE)")
                con.execute(
                    "INSERT INTO fact_stock_daily VALUES "
                    "(DATE '2026-07-03','688323.SH',102.0,100.0,2.0),"
                    "(DATE '2026-07-06','688323.SH',103.0,102.0,0.98),"
                    "(DATE '2026-07-07','688323.SH',110.0,103.0,6.8)"
                )
                con.execute("CREATE TABLE fact_market_daily (trade_date DATE, sh_index_close DOUBLE)")
                con.execute("INSERT INTO fact_market_daily VALUES (DATE '2026-07-02',3000.0),(DATE '2026-07-07',3030.0)")
            finally:
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
            self.assertTrue(updated["market_threshold_hit"])


if __name__ == "__main__":
    unittest.main()
