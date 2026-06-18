from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.services import checkpoint_resolvers as resolvers
from intelligence.services import checkpoints


class RegisterTests(unittest.TestCase):
    def test_register_appends_and_returns_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoints.jsonl"
            p, rec = checkpoints.register_checkpoint(
                path,
                claim="铜冠铜箔 60 日涨幅达 15%",
                due="2026-09-30",
                category="估值切换",
                themes=["铜箔", "铜箔"],  # 去重
                stocks=["铜冠铜箔"],
                metric={"type": "stock_return", "op": ">=", "target": 15, "window_days": 60},
                session_id="2026-06-18-1530",
                ts="2026-06-18T10:00:00",
            )
            self.assertEqual(p, path)
            self.assertTrue(rec["id"].startswith("ck-2026-06-18-"))  # id 用注册日，非到期日
            self.assertEqual(rec["due"], "2026-09-30")
            self.assertEqual(rec["category"], "估值切换")
            self.assertEqual(rec["themes"], ["铜箔"])
            self.assertEqual(rec["metric"]["type"], "stock_return")
            self.assertEqual(rec["metric"]["target"], 15.0)
            self.assertEqual(rec["metric"]["window_days"], 60)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["id"], rec["id"])

    def test_id_is_stable_for_same_claim_and_ts(self) -> None:
        a = checkpoints._make_id("同一陈述", "2026-06-18T00:00:00")
        b = checkpoints._make_id("同一陈述", "2026-06-18T00:00:00")
        c = checkpoints._make_id("不同陈述", "2026-06-18T00:00:00")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_empty_claim_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoints.jsonl"
            with self.assertRaises(ValueError):
                checkpoints.register_checkpoint(path, claim="   ", due="2026-09-30")
            self.assertFalse(path.exists())

    def test_bad_due_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoints.jsonl"
            with self.assertRaises(ValueError):
                checkpoints.register_checkpoint(path, claim="x", due="not-a-date")

    def test_manual_metric_normalized(self) -> None:
        self.assertEqual(checkpoints.normalize_metric({"type": "manual"}), {"type": "manual"})
        self.assertIsNone(checkpoints.normalize_metric(None))

    def test_numeric_metric_requires_target(self) -> None:
        with self.assertRaises(ValueError):
            checkpoints.normalize_metric({"type": "stock_return", "op": ">="})

    def test_bad_metric_op_raises(self) -> None:
        with self.assertRaises(ValueError):
            checkpoints.normalize_metric({"type": "stock_return", "op": "≈", "target": 1})


class LoadAndDueTests(unittest.TestCase):
    def test_missing_files_return_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cks, cwarn = checkpoints.load_checkpoints(Path(tmp) / "nope.jsonl")
            vds, vwarn = checkpoints.load_verdicts(Path(tmp) / "nope2.jsonl")
            self.assertEqual((cks, cwarn), ([], None))
            self.assertEqual((vds, vwarn), ([], None))

    def test_due_excludes_future_and_terminal_scored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cpath = Path(tmp) / "checkpoints.jsonl"
            vpath = Path(tmp) / "verdicts.jsonl"
            _, past = checkpoints.register_checkpoint(cpath, claim="过期未判", due="2026-01-01")
            _, future = checkpoints.register_checkpoint(cpath, claim="未到期", due="2099-01-01")
            _, scored = checkpoints.register_checkpoint(cpath, claim="过期已判", due="2026-01-02")
            checkpoints.record_verdict(vpath, id=scored["id"], verdict="hit")
            cks, _ = checkpoints.load_checkpoints(cpath)
            vds, _ = checkpoints.load_verdicts(vpath)
            due = checkpoints.due_checkpoints(cks, vds, today="2026-06-18")
            ids = {c["id"] for c in due}
            self.assertIn(past["id"], ids)
            self.assertNotIn(future["id"], ids)
            self.assertNotIn(scored["id"], ids)

    def test_unverifiable_stays_in_due_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cpath = Path(tmp) / "checkpoints.jsonl"
            vpath = Path(tmp) / "verdicts.jsonl"
            _, ck = checkpoints.register_checkpoint(cpath, claim="待数据", due="2026-01-01")
            checkpoints.record_verdict(vpath, id=ck["id"], verdict="unverifiable")
            cks, _ = checkpoints.load_checkpoints(cpath)
            vds, _ = checkpoints.load_verdicts(vpath)
            due = checkpoints.due_checkpoints(cks, vds, today="2026-06-18")
            self.assertEqual([c["id"] for c in due], [ck["id"]])


class CalibrateTests(unittest.TestCase):
    def _seed(self, cpath: Path, vpath: Path) -> None:
        # 估值切换：2 hit + 1 miss → 命中率 0.667（参半）
        for i, v in enumerate(["hit", "hit", "miss"]):
            _, ck = checkpoints.register_checkpoint(
                cpath, claim=f"估值切换{i}", due="2026-01-01", category="估值切换",
                ts=f"2026-06-1{i}T00:00:00",
            )
            checkpoints.record_verdict(vpath, id=ck["id"], verdict=v)
        # 产能时点：1 hit → 命中率 1.0（靠谱）
        _, ck = checkpoints.register_checkpoint(
            cpath, claim="产能时点0", due="2026-01-01", category="产能时点",
            ts="2026-06-15T00:00:00",
        )
        checkpoints.record_verdict(vpath, id=ck["id"], verdict="hit")
        # 情绪扩散：2 miss → 命中率 0.0（偏差大）
        for i in range(2):
            _, ck = checkpoints.register_checkpoint(
                cpath, claim=f"情绪扩散{i}", due="2026-01-01", category="情绪扩散",
                ts=f"2026-06-1{i}T12:00:00",
            )
            checkpoints.record_verdict(vpath, id=ck["id"], verdict="miss")

    def test_calibrate_ranks_by_hit_rate_ascending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cpath = Path(tmp) / "checkpoints.jsonl"
            vpath = Path(tmp) / "verdicts.jsonl"
            self._seed(cpath, vpath)
            cks, _ = checkpoints.load_checkpoints(cpath)
            vds, _ = checkpoints.load_verdicts(vpath)
            cal = checkpoints.calibrate(cks, vds, today="2026-06-18")
            cats = [s.category for s in cal.by_category]
            self.assertEqual(cats, ["情绪扩散", "估值切换", "产能时点"])
            self.assertEqual(cal.scored, 6)
            by = {s.category: s for s in cal.by_category}
            self.assertEqual(by["情绪扩散"].reliability, "偏差大")
            self.assertEqual(by["估值切换"].reliability, "参半")
            self.assertEqual(by["产能时点"].reliability, "靠谱")

    def test_latest_terminal_verdict_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cpath = Path(tmp) / "checkpoints.jsonl"
            vpath = Path(tmp) / "verdicts.jsonl"
            _, ck = checkpoints.register_checkpoint(cpath, claim="改判", due="2026-01-01", category="X")
            checkpoints.record_verdict(vpath, id=ck["id"], verdict="miss")
            checkpoints.record_verdict(vpath, id=ck["id"], verdict="hit")
            cks, _ = checkpoints.load_checkpoints(cpath)
            vds, _ = checkpoints.load_verdicts(vpath)
            cal = checkpoints.calibrate(cks, vds, today="2026-06-18")
            self.assertEqual(cal.by_category[0].hits, 1)
            self.assertEqual(cal.by_category[0].miss, 0)

    def test_render_for_prompt_respects_min_n(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cpath = Path(tmp) / "checkpoints.jsonl"
            vpath = Path(tmp) / "verdicts.jsonl"
            self._seed(cpath, vpath)
            cal, _ = checkpoints.load_calibration(cpath, vpath, today="2026-06-18")
            rendered = checkpoints.render_calibration_for_prompt(cal, min_n=2)
            self.assertIn("情绪扩散", rendered)
            self.assertIn("估值切换", rendered)
            self.assertNotIn("产能时点", rendered)  # n=1 < min_n
            self.assertIn("主动质疑", rendered)
            high = checkpoints.render_calibration_for_prompt(cal, min_n=1)
            self.assertIn("产能时点", high)

    def test_render_report_handles_empty(self) -> None:
        cal = checkpoints.Calibration()
        report = checkpoints.render_report(cal)
        self.assertIn("还没有已回检的判断", report)


class MarketResolverTests(unittest.TestCase):
    def _checkpoint(self, target: float = 15.0, op: str = ">=") -> dict:
        return {
            "id": "ck-x",
            "ts": "2026-06-18T00:00:00",
            "due": "2026-09-30",
            "stocks": ["铜冠铜箔"],
            "metric": {"type": "stock_return", "op": op, "target": target, "window_days": 60},
        }

    def test_hit_when_gain_meets_threshold(self) -> None:
        def fake(stocks, start, end):
            return {"铜冠铜箔": {"interval_gain": 22.5}}

        out = resolvers.MarketResolver(returns_fn=fake).resolve(self._checkpoint())
        self.assertEqual(out.verdict, "hit")
        self.assertEqual(out.score, 1.0)
        self.assertEqual(out.data_source, "market")

    def test_miss_when_gain_below_threshold(self) -> None:
        def fake(stocks, start, end):
            return {"铜冠铜箔": {"interval_gain": 3.0}}

        out = resolvers.MarketResolver(returns_fn=fake).resolve(self._checkpoint())
        self.assertEqual(out.verdict, "miss")
        self.assertEqual(out.score, 0.0)

    def test_unverifiable_when_no_rows(self) -> None:
        out = resolvers.MarketResolver(returns_fn=lambda s, a, b: {}).resolve(self._checkpoint())
        self.assertEqual(out.verdict, "unverifiable")
        self.assertIsNone(out.score)

    def test_graceful_degradation_when_returns_raise(self) -> None:
        def boom(stocks, start, end):
            raise ModuleNotFoundError("No module named 'duckdb'")

        out = resolvers.MarketResolver(returns_fn=boom).resolve(self._checkpoint())
        self.assertEqual(out.verdict, "unverifiable")
        self.assertIn("盘面数据不可用", out.reason)

    def test_unverifiable_when_no_stocks(self) -> None:
        ck = self._checkpoint()
        ck["stocks"] = []
        out = resolvers.MarketResolver(returns_fn=lambda s, a, b: {}).resolve(ck)
        self.assertEqual(out.verdict, "unverifiable")


class KnowledgeResolverTests(unittest.TestCase):
    class _FakeAdapter:
        def __init__(self, items: list[dict]) -> None:
            self._items = items

        def get_evidence(self, target, concept=None, limit=20):
            return {"found": bool(self._items), "target": target, "items": self._items, "errors": []}

    def _checkpoint(self, threshold: float = 1) -> dict:
        return {
            "id": "ck-kb",
            "ts": "2026-06-18T00:00:00",
            "due": "2026-07-01",
            "themes": ["铜箔"],
            "metric": {"type": "kb_evidence", "op": ">=", "target": threshold, "target_name": "铜箔"},
        }

    def test_hit_when_new_evidence_after_registration(self) -> None:
        adapter = self._FakeAdapter([
            {"target": "铜箔", "source_date": "2026-06-25", "evidence": "新催化"},
            {"target": "铜箔", "source_date": "2026-05-01", "evidence": "旧的不算"},
        ])
        out = resolvers.KnowledgeResolver(adapter=adapter).resolve(self._checkpoint())
        self.assertEqual(out.verdict, "hit")
        self.assertEqual(out.observed["new_evidence"], 1)

    def test_miss_when_no_new_evidence(self) -> None:
        adapter = self._FakeAdapter([{"target": "铜箔", "source_date": "2026-05-01"}])
        out = resolvers.KnowledgeResolver(adapter=adapter).resolve(self._checkpoint())
        self.assertEqual(out.verdict, "miss")

    def test_graceful_degradation_when_adapter_raises(self) -> None:
        class Boom:
            def get_evidence(self, *a, **k):
                raise FileNotFoundError("no wiki")

        out = resolvers.KnowledgeResolver(adapter=Boom()).resolve(self._checkpoint())
        self.assertEqual(out.verdict, "unverifiable")
        self.assertIn("知识库不可用", out.reason)


class ResolveDispatchTests(unittest.TestCase):
    def test_manual_returns_unverifiable(self) -> None:
        out = resolvers.resolve_checkpoint({"id": "x", "metric": {"type": "manual"}})
        self.assertEqual(out.verdict, "unverifiable")
        self.assertEqual(out.data_source, "manual")

    def test_no_metric_returns_unverifiable(self) -> None:
        out = resolvers.resolve_checkpoint({"id": "x"})
        self.assertEqual(out.verdict, "unverifiable")

    def test_dispatch_to_market(self) -> None:
        ck = {
            "id": "x", "ts": "2026-06-18T00:00:00", "due": "2026-09-30",
            "stocks": ["A"], "metric": {"type": "stock_return", "op": ">=", "target": 5, "window_days": 30},
        }
        out = resolvers.resolve_checkpoint(ck, market_returns_fn=lambda s, a, b: {"A": {"interval_gain": 9.0}})
        self.assertEqual(out.verdict, "hit")


if __name__ == "__main__":
    unittest.main()
