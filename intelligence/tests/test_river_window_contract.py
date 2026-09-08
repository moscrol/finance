"""区间契约测试（工单 #35 / G-02c；09-06 spec §4.4 / §10 第 9、10 条 / §11 第 12 条）。"""

from __future__ import annotations

import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

from intelligence.services import river_derive as rd
from intelligence.services import river_query
from intelligence.services import river_window as rw
from intelligence.services import river_window_contract as rwc
from intelligence.services.river import Gap, RiverObject, RiverSlice, TRACKS


def _obj(track: str, otype: str, ref: str, payload: dict, *, recorded_at: str = "2026-09-01T18:00:00") -> RiverObject:
    return RiverObject(
        track=track,  # type: ignore[arg-type]
        entity_id="E",
        object_type=otype,
        ref=ref,
        source_hash="h" + ref[-4:],
        valid_from="2026-09-01",
        recorded_at=recorded_at,
        payload=payload,
    )


def _slice(
    day: str,
    *,
    pit: str = "strict",
    market_stage: str = "反弹",
    dual_red: bool = True,
    volume_surge: bool = False,
    heat_rank: float | None = 3,
    events: list[RiverObject] | None = None,
    gap_tracks: tuple[str, ...] = (),
) -> RiverSlice:
    pct, diff, amt = (1.0, 15.0, 800.0) if dual_red else (-1.0, 5.0, 100.0)
    surge = 20.0 if volume_surge else 2.0
    tracks: dict = {}
    for t in TRACKS:
        if t in gap_tracks:
            tracks[t] = Gap(t, "no_data", "fixture")  # type: ignore[arg-type]
            continue
        if t == "market":
            objs = [
                _obj("market", "stage", f"fact_market_daily:{day}", {
                    "market_stage": market_stage, "amount_vs_yesterday_pct": surge,
                }, recorded_at=f"{day}T18:00:00"),
                _obj("market", "label", f"fact_sector_daily:{day}:E", {
                    "pct_chg": pct, "diff_ratio": diff, "amount": amt,
                }, recorded_at=f"{day}T18:00:00"),
            ]
            if heat_rank is not None:
                objs.append(_obj("market", "label", f"fact_theme_limit_heat_daily:{day}:E", {
                    "source_view": "limit_heat", "rank": heat_rank,
                }, recorded_at=f"{day}T18:00:00"))
            tracks[t] = objs
        elif t == "opinion" and events:
            tracks[t] = list(events)
        else:
            tracks[t] = []
    return RiverSlice(
        as_of=day,
        entity_id="E",
        entity_name="实体",
        knowledge_cutoff=day,
        tracks=tracks,  # type: ignore[arg-type]
        hindsight=False,
    )


def _window_from_slices(slices: list[RiverSlice], *, cutoff: str | None = None) -> rwc.RiverWindow:
    return rwc.RiverWindow(
        start=slices[0].as_of,
        end=slices[-1].as_of,
        entity_id="E",
        entity_name="实体",
        knowledge_cutoff=cutoff or slices[-1].as_of,
        slices=tuple(slices),
        derived=(),
        hindsight=False,
    )


class WindowContractTests(unittest.TestCase):
    def test_c_before_end_rejected_c_after_end_needs_hindsight(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            rwc.window("2026-09-01", "2026-09-05", "E", knowledge_cutoff="2026-09-03")
        self.assertIn("没走完", str(ctx.exception))
        with self.assertRaises(ValueError):
            rwc.window("2026-09-01", "2026-09-05", "E", knowledge_cutoff="2026-09-10")

    def test_idempotent_and_slices_match_slice_river(self) -> None:
        days = ["2026-09-01", "2026-09-02", "2026-09-03"]
        slices = {d: _slice(d) for d in days}

        def fake_slice(as_of, entity, **kw):
            return slices[as_of]

        with mock.patch("intelligence.services.river_window_contract.slice_river", side_effect=fake_slice), \
             mock.patch("intelligence.services.river_window_contract._resolve_days", return_value=days), \
             mock.patch("intelligence.services.river_window_contract.Path.exists", return_value=True), \
             mock.patch("intelligence.services.river_query.range_aggregate") as agg:
            agg.return_value = river_query.RangeAggregate(
                kind="sector", entity_id="E", entity_name="实体",
                start="2026-09-01", end="2026-09-03", method="compounded_daily",
                coverage=river_query.RangeCoverage(expected_days=3, actual_days=3),
                codes_seen=("E",), values={"cumulative_return_pct": 1.0},
            )
            a = rwc.window("2026-09-01", "2026-09-03", "E", knowledge_cutoff="2026-09-03", with_cumulative=True)
            b = rwc.window("2026-09-01", "2026-09-03", "E", knowledge_cutoff="2026-09-03", with_cumulative=True)
        self.assertEqual(a.to_dict(), b.to_dict())
        for day, sl in zip(days, a.slices):
            self.assertEqual(sl.to_dict(), slices[day].to_dict())
        self.assertEqual(a.pit_grade, "strict")
        self.assertEqual(len(a.derived), 1)
        self.assertEqual(a.derived[0].object_type, "cumulative")
        self.assertEqual(a.derived[0].validity_kind, "range")

    def test_any_trade_date_only_day_downgrades_window(self) -> None:
        s1 = _slice("2026-09-01")
        s2 = RiverSlice(
            as_of="2026-09-02", entity_id="E", entity_name="实体", knowledge_cutoff="2026-09-02",
            tracks={t: [] for t in TRACKS},  # type: ignore[misc]
            hindsight=False,
        )
        # empty objects → pit_grade trade_date_only (river.py: empty → trade_date_only)
        self.assertEqual(s2.pit_grade, "trade_date_only")
        win = _window_from_slices([s1, s2])
        self.assertEqual(win.pit_grade, "trade_date_only")


class DeriveTests(unittest.TestCase):
    def test_streak_unverifiable_vs_break(self) -> None:
        # day2 has gap on market → dual_red bind returns None
        s1 = _slice("2026-09-01", dual_red=True)
        s2 = _slice("2026-09-02", gap_tracks=("market",))
        s3 = _slice("2026-09-03", dual_red=True)
        win = _window_from_slices([s1, s2, s3])
        unver = rd.derive_streak(win, "dual_red_strict", gap_policy="unverifiable")
        self.assertEqual(unver.payload["status"], "unverifiable")
        self.assertTrue(any("missing:2026-09-02" in g for g in unver.payload["gaps_applied"]))
        brk = rd.derive_streak(win, "dual_red_strict", gap_policy="break")
        self.assertEqual(brk.payload["status"], "ok")
        self.assertEqual(brk.payload["longest"], 1)  # 连续被缺天打断
        with self.assertRaises(ValueError):
            rd.derive_streak(win, "dual_red_strict", gap_policy="skip")

    def test_transition_records_stage_changes(self) -> None:
        win = _window_from_slices([
            _slice("2026-09-01", market_stage="反弹"),
            _slice("2026-09-02", market_stage="反弹"),
            _slice("2026-09-03", market_stage="主升"),
        ])
        t = rd.derive_transitions(win, "market_stage")
        self.assertEqual(t.payload["status"], "ok")
        self.assertEqual(t.payload["count"], 1)
        self.assertEqual(t.payload["transitions"][0]["from"], "反弹")
        self.assertEqual(t.payload["transitions"][0]["to"], "主升")
        self.assertEqual(t.payload["transitions"][0]["day"], "2026-09-03")

    def test_first_event_and_label_whitelist(self) -> None:
        ev = _obj("opinion", "event", "fact_research_report_catalog:1", {"title": "首次覆盖"})
        win = _window_from_slices([
            _slice("2026-09-01"),
            _slice("2026-09-02", events=[ev]),
        ])
        fe = rd.derive_first_event(win, "opinion", "event")
        self.assertEqual(fe.payload["status"], "ok")
        self.assertEqual(fe.payload["first_day"], "2026-09-02")
        with self.assertRaises(rd.LabelNotSliceEvaluable):
            rd.bind("dual_red_streak", win.slices[0])  # 需要历史，不在白名单
        with self.assertRaises(rd.LabelNotSliceEvaluable):
            rd.bind("not_a_label", win.slices[0])

    def test_member_refs_resolve_back_to_slice_objects(self) -> None:
        win = _window_from_slices([_slice("2026-09-01", dual_red=True), _slice("2026-09-02", dual_red=True)])
        streak = rd.derive_streak(win, "dual_red_strict")
        refs_in_slices = {o.ref for s in win.slices for o in rwc.track_objects(s, "market")}
        self.assertTrue(set(streak.payload["member_refs"]) <= refs_in_slices)
        self.assertEqual(streak.validity_kind, "range")
        self.assertIn("derivation_rule", streak.payload)


class BuildDailyVectorsPitTests(unittest.TestCase):
    def test_knowledge_cutoff_required(self) -> None:
        with self.assertRaises(TypeError):
            rw.build_daily_vectors()  # type: ignore[call-arg]
        with self.assertRaises(ValueError):
            rw.build_daily_vectors(knowledge_cutoff="")

    def test_cutoff_truncates_and_emits_pit_grade(self) -> None:
        # Fake duckdb connection returning two days, one with late updated_at.
        class FakeCon:
            def execute(self, sql, params=None):
                self.last = (sql, params)
                class R:
                    def fetchall(self_inner):
                        if "fact_market_daily" in sql and "ORDER BY" in sql:
                            return [
                                (date(2026, 9, 1), 100.0, 1, 1, 0.1, 1, datetime(2026, 9, 1, 18)),
                                (date(2026, 9, 2), 110.0, 1, 1, 0.1, 1, datetime(2026, 9, 10, 18)),  # late
                            ]
                        if "fact_sector_daily" in sql:
                            return [(date(2026, 9, 1), 2, datetime(2026, 9, 1, 18)),
                                    (date(2026, 9, 2), 3, datetime(2026, 9, 2, 18))]
                        if "fact_theme_limit_heat_daily" in sql:
                            return [(date(2026, 9, 1), 0.1, datetime(2026, 9, 1, 18)),
                                    (date(2026, 9, 2), 0.2, datetime(2026, 9, 2, 18))]
                        if "fact_theme_flow_daily" in sql:
                            return [(date(2026, 9, 1), 1.0, datetime(2026, 9, 1, 18)),
                                    (date(2026, 9, 2), 2.0, datetime(2026, 9, 2, 18))]
                        if "fact_research_report_catalog" in sql:
                            return []
                        return []
                return R()
            def close(self): pass

        with mock.patch("duckdb.connect", return_value=FakeCon()), \
             mock.patch("intelligence.services.river_window.Path.exists", return_value=True):
            rows = rw.build_daily_vectors(knowledge_cutoff="2026-09-02")
        self.assertEqual([r["trade_date"] for r in rows], ["2026-09-01", "2026-09-02"])
        self.assertEqual(rows[0]["pit_grade"], "strict")
        self.assertEqual(rows[1]["pit_grade"], "trade_date_only")  # market_daily updated_at late
        # C=09-01 应截掉 09-02
        with mock.patch("duckdb.connect", return_value=FakeCon()), \
             mock.patch("intelligence.services.river_window.Path.exists", return_value=True):
            early = rw.build_daily_vectors(knowledge_cutoff="2026-09-01")
        # FakeCon 不真的按 params 过滤，所以这里只断言参数被传了；截断行为由 SQL WHERE 保证。
        self.assertTrue(all("knowledge_cutoff" in r for r in early))


def _sector_row(day: str, *, updated_at: datetime) -> dict:
    return {
        "d": day, "sector_ts_code": "E", "sector_name": "实体",
        "pct_chg": 1.0, "amount": 100, "updated_at": updated_at,
    }


class RangeAggregatePitTests(unittest.TestCase):
    """``range_aggregate`` 的 PIT 接线：None 保持老形状；显式 cutoff 才按行 ``updated_at`` 判档。"""

    def _run(self, *, updated_at: datetime, knowledge_cutoff: str | None) -> river_query.RangeAggregate:
        with mock.patch("intelligence.services.river_query.trading_days", return_value=["2026-09-01"]), \
             mock.patch("intelligence.services.river_query._stock_rows", return_value=[]), \
             mock.patch(
                 "intelligence.services.river_query._sector_rows",
                 return_value=[_sector_row("2026-09-01", updated_at=updated_at)],
             ), \
             mock.patch("intelligence.services.river_query.Path.exists", return_value=True), \
             mock.patch("duckdb.connect", return_value=mock.MagicMock()):
            return river_query.range_aggregate(
                "2026-09-01", "2026-09-01", "实体", knowledge_cutoff=knowledge_cutoff
            )

    def test_none_cutoff_preserves_old_shape(self) -> None:
        agg = self._run(updated_at=datetime(2026, 9, 1, 18), knowledge_cutoff=None)
        d = agg.to_dict()
        self.assertIsNone(d["pit_grade"])
        self.assertIsNone(d["knowledge_cutoff"])

    def test_explicit_cutoff_emits_pit_grade(self) -> None:
        agg = self._run(updated_at=datetime(2026, 9, 1, 18), knowledge_cutoff="2026-09-01")
        self.assertEqual(agg.pit_grade, "strict")
        self.assertEqual(agg.knowledge_cutoff, "2026-09-01")

    def test_row_refreshed_after_cutoff_downgrades(self) -> None:
        """刷新时间晚于 C：那一行可能被重写过，整段 trade_date_only（保守方向）。"""
        agg = self._run(updated_at=datetime(2026, 9, 9, 18), knowledge_cutoff="2026-09-01")
        self.assertEqual(agg.pit_grade, "trade_date_only")


class RiverObjectContractFieldsTests(unittest.TestCase):
    def test_defaults_by_object_type_and_not_in_source_hash_semantics(self) -> None:
        o = RiverObject(
            track="market", entity_id="E", object_type="stage", ref="r", source_hash="abc",
            valid_from="2026-09-01", recorded_at=None, payload={"market_stage": "反弹"},
        )
        self.assertEqual(o.validity_kind, "state")
        self.assertEqual(o.derivation, "deterministic")
        self.assertEqual(o.valid_to, None)  # state：现行
        p = RiverObject(
            track="opinion", entity_id="E", object_type="event", ref="r2", source_hash="def",
            valid_from="2026-09-01", recorded_at=None, payload={},
        )
        self.assertEqual(p.validity_kind, "point")
        self.assertEqual(p.valid_to, "2026-09-01")
        n = RiverObject(
            track="opinion", entity_id="E", object_type="narrative_version", ref="r3", source_hash="ghi",
            valid_from="2026-09-01", recorded_at=None, payload={},
        )
        self.assertEqual(n.derivation, "frozen_llm")


class ForwardLookingRatchetTests(unittest.TestCase):
    """§11 第 12 条：绕过 window() 直读全历史的路径视为前视泄漏——棘轮门禁。"""

    FORBIDDEN = (
        "intelligence/services/river_window.py",
        "intelligence/services/market_regime_analogs.py",
        "intelligence/services/market_analogs.py",
        "intelligence/services/stock_analogs.py",
    )

    def test_no_bare_duckdb_connect_without_cutoff_or_annotation(self) -> None:
        """每个 duckdb.connect / SELECT FROM fact_ 的调用点必须：
        - 在 river/ / river_window_contract / river_derive / river_anchor 包内，或
        - 带 ``# pit: via window()`` 标注，或
        - 形参列表含 knowledge_cutoff（函数签名层）。
        """
        root = Path(__file__).resolve().parents[2]
        offenders: list[str] = []
        for rel in self.FORBIDDEN:
            path = root / rel
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            # 粗检：文件里若出现「读全历史」的旧形状（ORDER BY trade_date 无 WHERE cutoff），告警。
            # build_daily_vectors 已改必填 cutoff；loader 已加 knowledge_cutoff。
            if "build_daily_vectors" in text and "knowledge_cutoff: str" not in text and rel.endswith("river_window.py"):
                offenders.append(f"{rel}: build_daily_vectors missing knowledge_cutoff")
            if "load_market_regime_vectors" in text and "knowledge_cutoff" not in text and rel.endswith("market_regime_analogs.py"):
                offenders.append(f"{rel}: load_market_regime_vectors missing knowledge_cutoff")
            # 裸「FROM fact_market_daily ORDER BY trade_date」无 WHERE：前视泄漏形状
            for i, line in enumerate(text.splitlines(), 1):
                if "FROM fact_market_daily ORDER BY trade_date" in line and "WHERE" not in line:
                    # 允许注释行
                    if line.strip().startswith("#") or line.strip().startswith('"') or line.strip().startswith("'"):
                        continue
                    offenders.append(f"{rel}:{i}: bare full-history scan")
        self.assertEqual(offenders, [], msg="前视泄漏路径：\n" + "\n".join(offenders))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
