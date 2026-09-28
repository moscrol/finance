from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence import cli
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

    def test_calibrate_aggregates_by_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cpath = Path(tmp) / "checkpoints.jsonl"
            vpath = Path(tmp) / "verdicts.jsonl"
            _, ck1 = checkpoints.register_checkpoint(
                cpath, claim="生命周期A", due="2026-01-01", category="生命周期推演", source="logic_lifecycle",
            )
            checkpoints.record_verdict(vpath, id=ck1["id"], verdict="hit")
            _, ck2 = checkpoints.register_checkpoint(
                cpath, claim="框架B", due="2026-01-01", category="framework_interpretation", source="framework_interpretation",
            )
            checkpoints.record_verdict(vpath, id=ck2["id"], verdict="miss")
            _, ck3 = checkpoints.register_checkpoint(cpath, claim="手工C", due="2026-01-01", category="X")
            checkpoints.record_verdict(vpath, id=ck3["id"], verdict="hit")
            cks, _ = checkpoints.load_checkpoints(cpath)
            vds, _ = checkpoints.load_verdicts(vpath)
            cal = checkpoints.calibrate(cks, vds, today="2026-06-18")
            by_src = {s.category: s for s in cal.by_source}
            self.assertEqual(set(by_src), {"logic_lifecycle", "framework_interpretation", "未标来源"})
            self.assertEqual(by_src["logic_lifecycle"].hits, 1)
            self.assertEqual(by_src["framework_interpretation"].miss, 1)
            self.assertEqual(cal.by_source[0].category, "framework_interpretation")

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


class MarketDailyResolverTests(unittest.TestCase):
    def _checkpoint(self, conditions: list[dict] | None = None) -> dict:
        return {
            "id": "ck-md",
            "ts": "2026-07-06T00:00:00",
            "due": "2026-07-07",
            "metric": {
                "type": "market_daily",
                "conditions": conditions or [
                    {"field": "advancers", "op": ">=", "target": 3000},
                    {"field": "limit_down", "op": "<=", "target": 25},
                ],
            },
        }

    def test_hit_when_all_conditions_pass(self) -> None:
        row = {"advancers": 3400, "limit_down": 12}
        out = resolvers.MarketDailyResolver(row_fn=lambda d: row).resolve(self._checkpoint())
        self.assertEqual(out.verdict, "hit")
        self.assertEqual(out.score, 1.0)
        self.assertEqual(out.observed["trade_date"], "2026-07-07")

    def test_miss_when_any_condition_fails(self) -> None:
        row = {"advancers": 2400, "limit_down": 12}
        out = resolvers.MarketDailyResolver(row_fn=lambda d: row).resolve(self._checkpoint())
        self.assertEqual(out.verdict, "miss")
        self.assertEqual(out.score, 0.0)

    def test_unverifiable_when_no_row(self) -> None:
        out = resolvers.MarketDailyResolver(row_fn=lambda d: None).resolve(self._checkpoint())
        self.assertEqual(out.verdict, "unverifiable")
        self.assertIn("查无", out.reason)

    def test_unverifiable_when_field_missing(self) -> None:
        out = resolvers.MarketDailyResolver(row_fn=lambda d: {"advancers": 3200}).resolve(self._checkpoint())
        self.assertEqual(out.verdict, "unverifiable")

    def test_graceful_degradation_when_row_fn_raises(self) -> None:
        def boom(date):
            raise ModuleNotFoundError("No module named 'duckdb'")

        out = resolvers.MarketDailyResolver(row_fn=boom).resolve(self._checkpoint())
        self.assertEqual(out.verdict, "unverifiable")
        self.assertIn("盘面数据不可用", out.reason)

    def test_metric_trade_date_overrides_due(self) -> None:
        ck = self._checkpoint()
        ck["metric"]["trade_date"] = "2026-07-06"
        seen: list[str] = []

        def fn(date):
            seen.append(date)
            return {"advancers": 3400, "limit_down": 12}

        resolvers.MarketDailyResolver(row_fn=fn).resolve(ck)
        self.assertEqual(seen, ["2026-07-06"])

    def test_normalize_market_daily_metric(self) -> None:
        metric = checkpoints.normalize_metric({
            "type": "market_daily",
            "conditions": ["advancers>=3000", {"field": "limit_down", "op": "<=", "target": "25"}],
        })
        self.assertEqual(metric["conditions"][0], {"field": "advancers", "op": ">=", "target": 3000.0})
        self.assertEqual(metric["conditions"][1], {"field": "limit_down", "op": "<=", "target": 25.0})

    def test_normalize_rejects_bad_conditions(self) -> None:
        with self.assertRaises(ValueError):
            checkpoints.normalize_metric({"type": "market_daily", "conditions": []})
        with self.assertRaises(ValueError):
            checkpoints.normalize_metric({"type": "market_daily", "conditions": ["DROP TABLE>=1;"]})
        with self.assertRaises(ValueError):
            checkpoints.normalize_metric({"type": "market_daily", "conditions": [{"field": "advancers", "op": "~", "target": 1}]})


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


class DegradeDisclosureTests(unittest.TestCase):
    """降级披露完整性（q13：可信度降了，透明度必须升）。

    盯的是一类具体退化：新加一个 ``unverifiable`` 出口，只写一句"数据不可用"就交差。
    半年后回看夜间 recheck，没人知道当时卡在哪、补什么才能判。
    """

    #: (标签, 触发该降级出口的 thunk)。覆盖每个 resolver 的每个降级分支。
    def _cases(self) -> list[tuple[str, object]]:
        def boom(*a, **k):
            raise ModuleNotFoundError("No module named 'duckdb'")

        mr = {"id": "ck-m", "ts": "2026-06-18T00:00:00", "due": "2026-09-30",
              "stocks": ["铜冠铜箔"],
              "metric": {"type": "stock_return", "op": ">=", "target": 15, "window_days": 60}}
        md_cond = [{"field": "advancers", "op": ">=", "target": 3000}]
        md = {"id": "ck-d", "ts": "2026-07-06T00:00:00", "due": "2026-07-07",
              "metric": {"type": "market_daily", "conditions": md_cond}}
        kb = {"id": "ck-k", "ts": "2026-06-18T00:00:00", "due": "2026-07-01",
              "themes": ["铜箔"],
              "metric": {"type": "kb_evidence", "op": ">=", "target": 1, "target_name": "铜箔"}}

        def _mr(ck: dict, fn) -> object:
            return resolvers.MarketResolver(returns_fn=fn).resolve(ck)

        def _md(ck: dict, fn) -> object:
            return resolvers.MarketDailyResolver(row_fn=fn).resolve(ck)

        class _Boom:
            def get_evidence(self, *a, **k):
                raise FileNotFoundError("no wiki")

        class _Errors:
            def get_evidence(self, *a, **k):
                return {"found": False, "items": [], "errors": ["evidence_index.json 解析失败"]}

        return [
            ("market/无个股", lambda: _mr({**mr, "stocks": []}, lambda *a: {})),
            ("market/缺 op-target", lambda: _mr({**mr, "metric": {"type": "stock_return"}}, lambda *a: {})),
            ("market/查询抛错", lambda: _mr(mr, boom)),
            ("market/区间无行情", lambda: _mr(mr, lambda *a: {})),
            ("market_daily/缺 conditions", lambda: _md({**md, "metric": {"type": "market_daily"}}, lambda d: None)),
            ("market_daily/查询抛错", lambda: _md(md, boom)),
            ("market_daily/查无当日行", lambda: _md(md, lambda d: None)),
            ("market_daily/条件缺 target",
             lambda: _md({**md, "metric": {"type": "market_daily",
                                           "conditions": [{"field": "advancers", "op": ">="}]}},
                         lambda d: {"advancers": 3400})),
            ("market_daily/字段无值", lambda: _md(md, lambda d: {"limit_down": 3})),
            ("market_daily/字段非数值", lambda: _md(md, lambda d: {"advancers": "3400家"})),
            ("knowledge/无 target", lambda: resolvers.KnowledgeResolver(adapter=_Errors()).resolve(
                {"id": "ck-k0", "ts": "2026-06-18T00:00:00", "due": "2026-07-01",
                 "metric": {"type": "kb_evidence"}})),
            ("knowledge/适配器抛错", lambda: resolvers.KnowledgeResolver(adapter=_Boom()).resolve(kb)),
            ("knowledge/证据库读失败", lambda: resolvers.KnowledgeResolver(adapter=_Errors()).resolve(kb)),
            ("dispatch/manual", lambda: resolvers.resolve_checkpoint({"id": "x", "metric": {"type": "manual"}})),
            ("dispatch/无 metric", lambda: resolvers.resolve_checkpoint({"id": "x"})),
        ]

    def test_every_degrade_exit_discloses_all_required_fields(self) -> None:
        for label, thunk in self._cases():
            with self.subTest(exit=label):
                out = thunk()
                self.assertEqual(out.verdict, "unverifiable")
                self.assertIsNone(out.score)
                deg = out.degradation
                self.assertIsInstance(deg, dict, "降级出口必须带 degradation")
                for key in resolvers.DEGRADE_FIELDS:
                    self.assertIn(key, deg, f"{label} 缺披露项 {key}")
                # attempted 可以为空（规格不全时一次查询都没发），但不能缺键；
                # 非空时每项都要说清"问了谁、返回什么"。
                self.assertIsInstance(deg["attempted"], list)
                for item in deg["attempted"]:
                    self.assertTrue(str(item.get("source") or "").strip(), f"{label} attempted 缺 source")
                    self.assertTrue(str(item.get("status") or "").strip(), f"{label} attempted 缺 status")
                for key in ("gap", "impact", "fallback"):
                    self.assertTrue(str(deg[key] or "").strip(), f"{label} 的 {key} 是空的")
                self.assertTrue(deg["todo"], f"{label} 没给待补证清单")
                self.assertTrue(all(str(t).strip() for t in deg["todo"]))
                # 来源标注不降级：本该由谁判要留着，看板才能分清"该判没数"和"只能人工判"。
                self.assertTrue(str(deg.get("owed_source") or "").strip(), f"{label} 丢了 owed_source")
                # q13 的 7 项里落在答案生成层的 2 项：显式记 NOT_APPLICABLE，不留空壳。
                self.assertEqual(deg.get("not_applicable"), resolvers.NOT_APPLICABLE_HERE)

    def test_spec_gap_exits_send_no_query(self) -> None:
        """规格不全 → attempted 必须为空：连查都没查，别拿假条目冒充试过。"""
        out = resolvers.MarketResolver(returns_fn=lambda *a: {}).resolve(
            {"id": "x", "ts": "2026-06-18T00:00:00", "due": "2026-09-30", "stocks": [],
             "metric": {"type": "stock_return", "op": ">=", "target": 15}})
        self.assertEqual(out.degradation["attempted"], [])
        self.assertIn("规格缺", out.degradation["gap"])
        self.assertIn("stocks/metric.target_name", out.degradation["todo"][0])

    def test_manual_exit_keeps_owed_source_and_own_impact(self) -> None:
        out = resolvers.resolve_checkpoint({"id": "x", "metric": {"type": "manual"}})
        self.assertEqual(out.degradation["owed_source"], "manual")
        self.assertIn("人工打分", out.degradation["fallback"])
        # manual 的影响口径不同于缺数：不会因为没人打分就变 miss。
        self.assertNotEqual(out.degradation["impact"], resolvers.DEFAULT_IMPACT)

    def test_terminal_verdicts_carry_no_degradation(self) -> None:
        """hit/miss 拿到了真数 → degradation 必须是 None，别伪造披露。"""
        hit = resolvers.MarketResolver(returns_fn=lambda *a: {"铜冠铜箔": {"interval_gain": 22.5}}).resolve(
            {"id": "x", "ts": "2026-06-18T00:00:00", "due": "2026-09-30", "stocks": ["铜冠铜箔"],
             "metric": {"type": "stock_return", "op": ">=", "target": 15, "window_days": 60}})
        self.assertEqual(hit.verdict, "hit")
        self.assertIsNone(hit.degradation)
        miss = resolvers.MarketDailyResolver(row_fn=lambda d: {"advancers": 2400}).resolve(
            {"id": "y", "ts": "2026-07-06T00:00:00", "due": "2026-07-07",
             "metric": {"type": "market_daily", "conditions": [{"field": "advancers", "op": ">=", "target": 3000}]}})
        self.assertEqual(miss.verdict, "miss")
        self.assertIsNone(miss.degradation)

    def test_verdict_record_persists_disclosure(self) -> None:
        """落盘要留住披露：半年后回看才答得出"当时为什么判不了、补什么才能判"。"""
        out = resolvers.MarketResolver(returns_fn=lambda *a: {}).resolve(
            {"id": "ck-p", "ts": "2026-06-18T00:00:00", "due": "2026-09-30",
             "stocks": ["铜冠铜箔"],
             "metric": {"type": "stock_return", "op": ">=", "target": 15, "window_days": 60}})
        with tempfile.TemporaryDirectory() as tmp:
            vpath = Path(tmp) / "verdicts.jsonl"
            _, rec = checkpoints.record_verdict(
                vpath, id="ck-p", verdict=out.verdict, score=out.score,
                observed=out.observed, data_source=out.data_source, reason=out.reason,
                degradation=out.degradation, auto=True,
            )
            on_disk = json.loads(vpath.read_text(encoding="utf-8").strip().splitlines()[-1])
        self.assertEqual(rec["degradation"], out.degradation)
        for key in resolvers.DEGRADE_FIELDS:
            self.assertIn(key, on_disk["degradation"])
        self.assertIn("停牌", on_disk["degradation"]["gap"])

    def test_terminal_record_has_no_degradation_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vpath = Path(tmp) / "verdicts.jsonl"
            _, rec = checkpoints.record_verdict(vpath, id="ck-t", verdict="hit")
        self.assertNotIn("degradation", rec)

    def test_no_unverifiable_exit_bypasses_the_helper(self) -> None:
        """静态兜底：新出口直接 ``ResolveOutcome("unverifiable", ...)`` 会绕过必填校验。

        ``_unverifiable`` 的必填关键字参数只能挡住"走 helper 但漏字段"；
        绕开 helper 自己造 outcome 是另一条路，这里用 AST 堵上。
        """
        import ast

        src = Path(resolvers.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        # _unverifiable 自己当然要造这个 outcome，它是唯一豁免。
        helper = next(n for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef) and n.name == "_unverifiable")
        exempt = set(range(helper.lineno, (helper.end_lineno or helper.lineno) + 1))
        offenders: list[int] = []
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "ResolveOutcome"):
                continue
            if node.lineno in exempt:
                continue
            literals = [a.value for a in node.args if isinstance(a, ast.Constant)]
            literals += [k.value.value for k in node.keywords
                         if k.arg and isinstance(k.value, ast.Constant)]
            if "unverifiable" in literals:
                offenders.append(node.lineno)
        self.assertEqual(
            offenders, [],
            f"这些行直接构造了 unverifiable outcome，绕过 _unverifiable 的必填披露："
            f"{offenders}（改成走 _unverifiable/_spec_gap）",
        )


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

        # 显式 > env > ~/agent-memory > 回退
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
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            vault = home / "agent-memory"
            vault.mkdir(parents=True)
            with mock.patch.dict(os.environ, {"HOME": str(home)}, clear=False):
                os.environ.pop(checkpoints.ENV_VAULT, None)
                os.environ.pop(checkpoints.ENV_AGENT_MEMORY_VAULT, None)
                p3, fb3 = checkpoints.resolve_recheck_vault("/fallback")
        self.assertEqual(p3, vault)
        self.assertFalse(fb3)

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"HOME": tmp}, clear=False):
                os.environ.pop(checkpoints.ENV_VAULT, None)
                os.environ.pop(checkpoints.ENV_AGENT_MEMORY_VAULT, None)
                p4, fb4 = checkpoints.resolve_recheck_vault("/fallback")
        self.assertEqual(p4, Path("/fallback") / "_vault")
        self.assertTrue(fb4)

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

    def test_digest_renders_degradation_disclosure(self) -> None:
        """降级条目在人读日志里要看得见"试过什么/影响/待补"，不能只剩一句缺数据。"""
        out = resolvers.MarketDailyResolver(row_fn=lambda d: None).resolve(
            {"id": "ck-deg", "ts": "2026-07-06T00:00:00", "due": "2026-07-07",
             "metric": {"type": "market_daily",
                        "conditions": [{"field": "advancers", "op": ">=", "target": 3000}]}})
        sec = checkpoints.build_recheck_digest_section([{
            "id": "ck-deg", "claim": "07-07 涨家数站上3000", "category": "市场路径",
            "verdict": out.verdict, "data_source": out.data_source, "reason": out.reason,
            "degradation": out.degradation,
        }], applied=True)
        self.assertIn("试过：duckdb:fact_market_daily→查询成功，无该日行", sec)
        self.assertIn("影响：", sec)
        self.assertIn("（本该由 market 判）", sec)
        self.assertIn("待补：", sec)
        self.assertIn("run_review_sync.py --date 2026-07-07", sec)

    def test_digest_marks_spec_gap_as_no_query_sent(self) -> None:
        out = resolvers.resolve_checkpoint({"id": "ck-man", "metric": {"type": "manual"}})
        sec = checkpoints.build_recheck_digest_section([{
            "id": "ck-man", "claim": "产能Q3兑现", "verdict": out.verdict,
            "data_source": out.data_source, "reason": out.reason, "degradation": out.degradation,
        }], applied=True)
        self.assertIn("试过：未发起查询", sec)
        self.assertIn("本该由 manual 判", sec)

    def test_digest_omits_degradation_lines_for_terminal(self) -> None:
        sec = checkpoints.build_recheck_digest_section(self._results()[:2], applied=True)
        self.assertNotIn("试过：", sec)
        self.assertNotIn("待补：", sec)

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


class CliHelpTests(unittest.TestCase):
    def test_register_help_renders_without_format_error(self) -> None:
        # 回归：--target 的 help 串里字面量 % 必须转义成 %%，否则 argparse
        # 的 `help % params` 会把它当格式化符、撞上后面的全角逗号崩 ValueError。
        parser = cli.build_parser()
        buf = io.StringIO()
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stdout(buf):
            parser.parse_args(["checkpoint", "register", "--help"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("涨幅%", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
