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


class RecheckDigestTests(unittest.TestCase):
    """人类层回检日志（让夜间 recheck 不黑盒）。"""

    def _results(self) -> list[dict[str, object]]:
        return [
            {"id": "ck-1", "claim": "铜冠铜箔 60日涨幅站上15%", "category": "估值切换",
             "verdict": "hit", "data_source": "market", "reason": "实测 18.4% ≥ 15"},
            {"id": "ck-2", "claim": "产能Q3兑现", "category": "产能时点",
             "verdict": "miss", "data_source": "market", "reason": "实测 -3% < 0"},
            {"id": "ck-3", "claim": "出现新证据", "category": "消息面",
             "verdict": "unverifiable", "data_source": "knowledge", "reason": "本机无 wiki"},
        ]

    def test_resolve_vault_priority(self) -> None:
        import os

        # 显式 > env > 回退
        p, fb = checkpoints.resolve_recheck_vault("/fallback", explicit="/x/vault")
        self.assertEqual(p, Path("/x/vault"))
        self.assertFalse(fb)
        old = os.environ.get(checkpoints.ENV_VAULT)
        os.environ[checkpoints.ENV_VAULT] = "/env/vault"
        try:
            p2, fb2 = checkpoints.resolve_recheck_vault("/fallback")
            self.assertEqual(p2, Path("/env/vault"))
            self.assertFalse(fb2)
        finally:
            if old is None:
                os.environ.pop(checkpoints.ENV_VAULT, None)
            else:
                os.environ[checkpoints.ENV_VAULT] = old
        os.environ.pop(checkpoints.ENV_VAULT, None)
        p3, fb3 = checkpoints.resolve_recheck_vault("/fallback")
        self.assertEqual(p3, Path("/fallback") / "_vault")
        self.assertTrue(fb3)

    def test_digest_section_tally_and_lines(self) -> None:
        sec = checkpoints.build_recheck_digest_section(self._results(), applied=True)
        # 终态 2 中 1 命中 → 50%；unverifiable 不计入分母
        self.assertIn("命中率 50%", sec)
        self.assertIn("终态 2 中 1 命中", sec)
        self.assertIn("暂无法判定 1", sec)
        # 逐条带 verdict 中文 + 类别 + claim
        self.assertIn("**命中**｜估值切换｜铜冠铜箔 60日涨幅站上15%", sec)
        self.assertIn("**落空**｜产能时点｜", sec)
        self.assertIn("**暂无法判定**｜消息面｜", sec)
        self.assertIn("`ck-1`", sec)

    def test_digest_section_no_terminal(self) -> None:
        only_unv = [{"id": "ck-9", "claim": "x", "verdict": "unverifiable",
                     "data_source": "market", "reason": "无 DuckDB"}]
        sec = checkpoints.build_recheck_digest_section(only_unv, applied=True)
        self.assertIn("本轮无终态判定", sec)
        self.assertIn("暂无法判定 1", sec)

    def test_write_digest_creates_then_appends(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sec1 = checkpoints.build_recheck_digest_section(self._results(), applied=True)
            note = checkpoints.write_recheck_digest(tmp, sec1, date="2026-09-30")
            self.assertTrue(note.is_file())
            self.assertEqual(note.parent.name, checkpoints.RECHECK_VAULT_SUBDIR)
            self.assertEqual(note.name, "2026-09-30.md")
            body1 = note.read_text(encoding="utf-8")
            self.assertIn("# 可证伪点夜间回检 · 2026-09-30", body1)
            self.assertEqual(body1.count("## "), 1)  # 一轮一节
            # 同日二次回检 → 追加第二节，标题不重复
            note2 = checkpoints.write_recheck_digest(tmp, sec1, date="2026-09-30")
            self.assertEqual(note2, note)
            body2 = note.read_text(encoding="utf-8")
            self.assertEqual(body2.count("# 可证伪点夜间回检 · 2026-09-30"), 1)
            self.assertEqual(body2.count("## "), 2)


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
