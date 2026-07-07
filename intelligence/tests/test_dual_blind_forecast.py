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
            codex = report["agents"]["codex"]
            self.assertEqual(codex["answers"], 1)
            self.assertEqual(codex["rechecked"], 1)
            self.assertEqual(codex["avg_pick_return_t1"], -0.5)
            self.assertEqual(codex["avg_pick_return_t3"], 2.0)
            self.assertEqual(codex["market_threshold_hit_rate"], 1.0)
            claude = report["agents"]["claude"]
            self.assertEqual(claude["rechecked"], 0)
            self.assertIsNone(claude["avg_pick_return_t1"])


if __name__ == "__main__":
    unittest.main()
