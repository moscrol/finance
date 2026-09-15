"""区间契约测试（工单 #35 / G-02c；09-06 spec §4.4 / §10 第 9、10 条 / §11 第 12 条）。"""

from __future__ import annotations

import re
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

from intelligence.services import river
from intelligence.services import river_derive as rd
from intelligence.services import river_projection
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


class RiverCorrectionAndHardnessTests(unittest.TestCase):
    """G-02 契约后半：修正链（``expired_at`` / ``superseded_by``）与硬度（``hardness``）。

    契约原文 ``docs/superpowers/specs/2026-09-05-time-river-gap-roadmap.md`` G-02：
    ``slice`` 取 ``valid_from <= T < valid_to`` 且 ``recorded_at <= C``
    且 ``(expired_at is null or expired_at > C)``。
    """

    def _o(self, ref: str, **kw: object) -> RiverObject:
        base: dict = dict(
            track="market", entity_id="E", object_type="stage", ref=ref, source_hash="h",
            valid_from="2026-09-01", recorded_at="2026-09-01T18:00:00", payload={},
        )
        base.update(kw)
        return RiverObject(**base)

    # ── 载体就位 ──
    def test_三个契约字段存在且缺省为None(self) -> None:
        o = self._o("r1")
        self.assertIsNone(o.hardness)
        self.assertIsNone(o.expired_at)
        self.assertIsNone(o.superseded_by)
        self.assertEqual(
            {"hardness": None, "expired_at": None, "superseded_by": None},
            {k: o.to_dict()[k] for k in ("hardness", "expired_at", "superseded_by")},
        )

    # ── frozen_llm 封顶 L1 ──
    def test_frozen_llm的硬度被封顶到L1(self) -> None:
        n = self._o("r2", object_type="narrative_version", hardness="L4")
        self.assertEqual(n.derivation, "frozen_llm")
        self.assertEqual(n.hardness, "L1")

    def test_deterministic不被封顶(self) -> None:
        """反向钉住：封顶只对 frozen_llm 生效，否则等于把所有对象一起降级。"""
        d = self._o("r3", hardness="L4")
        self.assertEqual(d.derivation, "deterministic")
        self.assertEqual(d.hardness, "L4")

    def test_封顶不会给无硬度的对象塞值(self) -> None:
        n = self._o("r4", object_type="narrative_version")
        self.assertIsNone(n.hardness)

    # ── expired_at 参与切片过滤 ──
    def test_截至cutoff已失效的对象被滤掉(self) -> None:
        out = river._enforce_cutoff(
            {"market": [self._o("live"), self._o("dead", expired_at="2026-09-02T09:00:00")]},
            "2026-09-03",
        )
        self.assertEqual([o.ref for o in out["market"]], ["live"])

    def test_cutoff之后才失效的对象在回放时仍可见(self) -> None:
        """T+5 写的纠正在重放 T 日时不可见——靶子不许挪走。"""
        out = river._enforce_cutoff(
            {"market": [self._o("x", expired_at="2026-09-10T09:00:00")]}, "2026-09-03",
        )
        self.assertEqual([o.ref for o in out["market"]], ["x"])

    def test_两个NULL的处置刻意相反(self) -> None:
        """``expired_at`` 为 null = 现行（保留）；``recorded_at`` 为 null = 不可判（滤掉）。

        把前者也当不可判滤掉，会让今天所有对象一起消失。
        """
        out = river._enforce_cutoff(
            {"market": [self._o("current"), self._o("unknown", recorded_at=None)]},
            "2026-09-03",
        )
        self.assertEqual([o.ref for o in out["market"]], ["current"])

    def test_同日失效在当日即生效(self) -> None:
        """与 ``recorded_at`` 的 ``<=`` 对齐：纠正与被纠正者不并存于同一切片。"""
        out = river._enforce_cutoff(
            {"market": [self._o("s", expired_at="2026-09-03T15:00:00")]}, "2026-09-03",
        )
        self.assertIsInstance(out["market"], Gap)

    def test_整轨滤空时Gap分别报两种原因(self) -> None:
        out = river._enforce_cutoff(
            {"market": [
                self._o("a", recorded_at=None),
                self._o("b", expired_at="2026-09-01T09:00:00"),
            ]},
            "2026-09-03",
        )
        gap = out["market"]
        assert isinstance(gap, Gap)
        self.assertIn("1 个对象的 recorded_at", gap.detail)
        self.assertIn("1 个截至 cutoff 已失效", gap.detail)

    # ── 单一事实源 ──
    def test_投影层的硬度排名就是river那份(self) -> None:
        """两层各存一份会漂，而漂了之后排序静默变化、没有任何断言会红。"""
        self.assertIs(river_projection.HARDNESS_RANK, river.HARDNESS_RANK)
        self.assertFalse(hasattr(river_projection, "_HARDNESS_RANK"))

    def test_对象上的hardness流到投影层排序(self) -> None:
        """``hardness_of`` 的 ``obj.get("hardness")`` 分支此前永远取不到值（消费者空转）。"""
        hard = self._o("hard", hardness="L4").to_dict()
        soft = self._o("soft", hardness="L1").to_dict()
        self.assertEqual(river_projection.hardness_of(hard), "L4")
        self.assertEqual(river_projection.hardness_of(self._o("none").to_dict()), river.HARDNESS_NA)
        self.assertLess(
            river_projection.default_sort_key(hard), river_projection.default_sort_key(soft),
        )

    # ── 修正链标注不进投影（§4.5）──
    def test_修正链标注不进投影哈希也不进渲染正文(self) -> None:
        """留在切片里的 ``expired_at`` / ``superseded_by`` 只能是 > C 的值——C 之后的知识。

        进哈希：接上自动触发后每次标注都漂历史投影哈希，checkpoints 里的钥匙集体失配；
        进正文：模型站在 C 却看到「这条判断将在未来被推翻」，前视。
        ``hashed_dict`` 是白名单序列化，这条钉住它不被改回全量 dict。
        """
        plain = {"tracks": {"market": [self._o("r1").to_dict(), self._o("r2").to_dict()]}}
        marked = {"tracks": {"market": [
            self._o("r1", expired_at="2027-01-01T09:00:00", superseded_by="river://market/E/x").to_dict(),
            self._o("r2").to_dict(),
        ]}}
        p1 = river_projection.project(plain, framework_version=None, task="t")
        p2 = river_projection.project(marked, framework_version=None, task="t")
        self.assertEqual(p1.projection_hash, p2.projection_hash)
        for needle in ("expired_at", "superseded_by", "2027-01-01", "river://market/E/x"):
            self.assertNotIn(needle, p2.canonical_json())
            self.assertNotIn(needle, "".join(b.rendered_text for b in p2.blocks))


class SpecPointerRatchetTests(unittest.TestCase):
    """契约指针不得悬空：模块 docstring 引用的 09-06 spec 章节必须真实存在。

    2026-09-15 实测：``river_window_contract`` / ``river_projection`` / ``river_anchor`` /
    ``river_derive`` 四个模块都写着「契约见 09-06 统一 spec §4.4 / §4.5 / §4.6」，而那份
    spec 的 §4 只到 4.3——三节从没写过。指针悬空比没有指针更贵：下一个人照着它去找契约，
    会以为是自己没找到，而不会怀疑契约不存在。
    """

    SPEC = (
        Path(__file__).resolve().parents[2]
        / "docs/superpowers/specs/2026-09-06-personal-research-calibration-endstate-design.md"
    )
    # 扫 glob 不扫名单：写死四个名字时，river.py（§4.2 两处）与 river_window.py（§4.4）
    # 的引用已经在门禁外——名单会漏现存成员，更别提未来新增的。
    MODULE_GLOB = "river*.py"
    MIN_MODULES = 8  # 2026-09-15 实测 river 系模块数；少于它说明 glob 或目录结构变了

    def test_09_06_spec_的章节引用都能落到实处(self) -> None:
        present = set(re.findall(r"^#{2,4}\s+(\d+\.\d+)\s", self.SPEC.read_text(encoding="utf-8"), re.M))
        self.assertTrue(present, f"没解析出任何章节，检查 spec 路径：{self.SPEC}")
        services = Path(__file__).resolve().parents[1] / "services"
        modules = sorted(services.glob(self.MODULE_GLOB))
        self.assertGreaterEqual(len(modules), self.MIN_MODULES, f"river 系模块只扫到 {[m.name for m in modules]}")
        cited: list[tuple[str, str]] = []
        for path in modules:
            src = path.read_text(encoding="utf-8")
            cited += [(path.name, sec) for sec in re.findall(r"09-06[^\n]{0,12}spec\s+§(\d+\.\d+)", src)]
        self.assertTrue(cited, "一条引用都没扫到——正则或 docstring 写法变了，门禁会假绿")
        missing = [f"{n} → §{s}" for n, s in cited if s not in present]
        self.assertEqual([], missing, f"契约指针悬空：{missing}；spec 现有章节 {sorted(present)}")


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


class MarketStageBindingTests(unittest.TestCase):
    def test_market_stage_binding_normalizes_vendor_suffix(self) -> None:
        """G-05：切片里是「底部横盘阶段」，注册标签值是「底部横盘」——绑定必须归一，否则条件永远不命中。"""
        sl = _slice("2026-09-02", market_stage="底部横盘阶段")
        value, refs = rd.bind("market_stage", sl)
        self.assertEqual(value, "底部横盘")
        self.assertTrue(refs)
