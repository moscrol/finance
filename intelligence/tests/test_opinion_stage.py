"""舆论生命周期阶段测试（工单 #36 / G-06）：确定性派生、PIT、五种走法、阈值真源、错位标记、河切片对象。"""

from __future__ import annotations

import datetime as dt
import re
import unittest
from pathlib import Path

from intelligence.services import opinion_stage as os_

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE = dt.date(2026, 1, 5)


def _hit(day: dt.date, *, recorded: dt.date | None = None) -> dict:
    return {"report_date": day, "created_at": recorded or day}


def _weekly(n: int, *, start: dt.date = BASE, per_week: int = 1) -> list[dict]:
    out: list[dict] = []
    d = start
    for _ in range(n):
        for j in range(per_week):
            out.append(_hit(d + dt.timedelta(days=j)))
        d += dt.timedelta(days=7)
    return out


class ThresholdSourceTests(unittest.TestCase):
    def test_thresholds_come_from_consensus_staging_not_literals(self) -> None:
        parsed = os_.load_thresholds()
        self.assertEqual(os_.TH_RESONANCE_SOURCES, parsed["TH_RESONANCE_SOURCES"])
        self.assertEqual(os_.TH_CONSENSUS_SOURCES, parsed["TH_CONSENSUS_SOURCES"])
        self.assertEqual(os_.TH_CONSENSUS_DAYS, parsed["TH_CONSENSUS_DAYS"])
        # 模块里不许出现「= 3」「= 5」这种阈值字面量（工单验收 7）；其它常量（90 / 30 / 10 / 120 / 60）是本模块自己的窗长。
        src = (REPO_ROOT / "intelligence/services/opinion_stage.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"^TH_[A-Z_]+ = \d+", src, flags=re.M), "阈值必须 import/解析自 consensus_staging，不许写死")

    def test_missing_threshold_in_source_raises(self) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
            fh.write("TH_RESONANCE_SOURCES = 3\n")
            path = Path(fh.name)
        with self.assertRaises(RuntimeError):
            os_.load_thresholds(path)


class DeriveTests(unittest.TestCase):
    def test_deterministic_and_stateless(self) -> None:
        hits = _weekly(30)
        a = os_.derive_stage(hits, "2026-06-01")
        b = os_.derive_stage(list(reversed(hits)), "2026-06-01")  # 事件顺序无关
        self.assertEqual(a.to_dict(), b.to_dict())
        self.assertEqual(a.source_hash, b.source_hash)

    def test_walk_sprout_spread_crowded_cooling(self) -> None:
        hits = _weekly(20) + _weekly(8, start=BASE + dt.timedelta(days=140), per_week=3)
        peak = BASE + dt.timedelta(days=140 + 56)
        self.assertEqual(os_.derive_stage(hits, str(BASE + dt.timedelta(days=10))).stage, os_.STAGE_SPROUT)
        # 历史 < 60 观测日、count_90d >= 3：停在扩散，不判拥挤
        early = os_.derive_stage(hits, str(BASE + dt.timedelta(days=40)))
        self.assertEqual(early.stage, os_.STAGE_SPREAD)
        self.assertTrue(any("不判拥挤" in r for r in early.reasons))
        self.assertEqual(os_.derive_stage(hits, str(peak - dt.timedelta(days=3))).stage, os_.STAGE_CROWDED)
        cooling = os_.derive_stage(hits, str(peak + dt.timedelta(days=45)))
        self.assertEqual(cooling.stage, os_.STAGE_COOLING)
        self.assertGreaterEqual(cooling.inputs["cooling_streak"], os_.COOLING_STREAK)
        # 覆盖归零但曾拥挤：仍是退热，不是 unverifiable
        self.assertEqual(os_.derive_stage(hits, str(peak + dt.timedelta(days=130))).stage, os_.STAGE_COOLING)

    def test_sprout_then_unverifiable_when_coverage_vanishes(self) -> None:
        hits = [_hit(BASE), _hit(BASE + dt.timedelta(days=3))]
        self.assertEqual(os_.derive_stage(hits, str(BASE + dt.timedelta(days=10))).stage, os_.STAGE_SPROUT)
        gone = os_.derive_stage(hits, str(BASE + dt.timedelta(days=200)))
        self.assertEqual(gone.stage, os_.UNVERIFIABLE)
        self.assertTrue(any("不断言「无人问津」" in r for r in gone.reasons))

    def test_falsification_is_terminal(self) -> None:
        hits = _weekly(30)
        day = BASE + dt.timedelta(days=100)
        r = os_.derive_stage(hits, str(day), falsification_dates=[str(day - dt.timedelta(days=1))])
        self.assertEqual(r.stage, os_.STAGE_FALSIFIED)
        later = os_.derive_stage(hits, str(day + dt.timedelta(days=60)), falsification_dates=[str(day - dt.timedelta(days=1))])
        self.assertEqual(later.stage, os_.STAGE_FALSIFIED)
        # 证伪日在 as_of 之后 → 还没发生，不算
        before = os_.derive_stage(hits, str(day), falsification_dates=[str(day + dt.timedelta(days=1))])
        self.assertNotEqual(before.stage, os_.STAGE_FALSIFIED)

    def test_recorded_after_cutoff_is_invisible(self) -> None:
        """PIT：created_at 晚于 C 的研报不计入；同一天 C 不同，阈值两侧结果不同。"""
        d = BASE + dt.timedelta(days=30)
        hits = [_hit(BASE + dt.timedelta(days=i), recorded=BASE + dt.timedelta(days=i)) for i in (1, 2)]
        hits.append(_hit(BASE + dt.timedelta(days=3), recorded=BASE + dt.timedelta(days=40)))  # 晚入库
        seen_two = os_.derive_stage(hits, str(d), knowledge_cutoff=str(d))
        self.assertEqual(seen_two.inputs["hits_used"], 2)
        self.assertEqual(seen_two.stage, os_.STAGE_SPROUT)
        seen_three = os_.derive_stage(hits, str(d), knowledge_cutoff=str(BASE + dt.timedelta(days=45)))
        self.assertEqual(seen_three.inputs["hits_used"], 3)
        self.assertEqual(seen_three.stage, os_.STAGE_SPREAD)
        with self.assertRaises(ValueError):
            os_.derive_stage(hits, str(d), knowledge_cutoff=str(d - dt.timedelta(days=1)))

    def test_unknown_recorded_at_is_not_counted(self) -> None:
        hits = [{"report_date": BASE, "created_at": None}, {"report_date": BASE + dt.timedelta(days=1), "created_at": BASE + dt.timedelta(days=1)}]
        r = os_.derive_stage(hits, str(BASE + dt.timedelta(days=5)))
        self.assertEqual(r.inputs["hits_used"], 1)
        self.assertTrue(any("未计入" in x for x in r.reasons))

    def test_backfill_batch_is_named(self) -> None:
        batch_day = BASE + dt.timedelta(days=60)
        hits = [_hit(BASE + dt.timedelta(days=i * 3), recorded=batch_day) for i in range(12)]
        r = os_.derive_stage(hits, str(batch_day + dt.timedelta(days=1)))
        self.assertEqual(r.inputs["backfill_batch_dates"], [str(batch_day)])
        self.assertTrue(any("回填批次" in x for x in r.reasons))

    def test_series_is_pointwise(self) -> None:
        hits = _weekly(12)
        days = [str(BASE + dt.timedelta(days=k)) for k in (10, 40, 70)]
        series = os_.derive_stage_series(hits, days)
        self.assertEqual([r.as_of for r in series], days)
        for r in series:
            self.assertEqual(r.to_dict(), os_.derive_stage(hits, r.as_of, knowledge_cutoff=r.as_of).to_dict())


class DislocationTests(unittest.TestCase):
    def test_four_values_and_module_tables(self) -> None:
        self.assertEqual(os_.dislocation("升温验证", "拥挤"), "opinion_leads")
        self.assertEqual(os_.dislocation("加速定价", "萌芽"), "opinion_lags")
        self.assertEqual(os_.dislocation("发酵", "扩散", theme_module="theme_lifecycle_timeline"), "aligned")
        self.assertEqual(os_.dislocation(None, "萌芽"), os_.UNVERIFIABLE)
        self.assertEqual(os_.dislocation("升温验证", os_.UNVERIFIABLE), os_.UNVERIFIABLE)
        self.assertEqual(os_.dislocation("升温验证", "证伪"), os_.UNVERIFIABLE)  # 终态不在序上
        with self.assertRaises(ValueError):
            os_.dislocation("发酵", "扩散", theme_module="nope")

    def test_vocabulary_does_not_collide_with_theme_stages(self) -> None:
        theme_words = set()
        for table in os_.THEME_STAGE_COARSE.values():
            theme_words |= set(table)
        self.assertEqual(set(os_.STAGES) & theme_words, set())


class RiverOpinionTrackTests(unittest.TestCase):
    def test_opinion_track_emits_stage_object_and_no_placeholder(self) -> None:
        from intelligence.services import river

        hits = [
            {"report_id": 1, "title": "A", "report_date": dt.date(2026, 8, 1), "report_type": "industry", "is_hot": False,
             "sector_tags": '["半导体"]', "concept_tags": "[]", "created_at": "2026-08-01T18:00:00"},
            {"report_id": 2, "title": "B", "report_date": dt.date(2026, 8, 20), "report_type": "industry", "is_hot": True,
             "sector_tags": '["半导体"]', "concept_tags": "[]", "created_at": "2026-08-20T18:00:00"},
        ]
        from unittest import mock

        with mock.patch.object(river, "coverage_hits", return_value=hits), \
             mock.patch.object(river, "_fundamental_docs", return_value=[]):
            out = river._opinion_track(con=None, as_of="2026-09-01", eid="E", ename="半导体")
        types = [o.object_type for o in out]
        self.assertIn("stage", types)
        stage_obj = next(o for o in out if o.object_type == "stage")
        self.assertEqual(stage_obj.payload["stage"], os_.STAGE_SPROUT)
        self.assertEqual(stage_obj.recorded_at, "2026-08-20T18:00:00")
        label = next(o for o in out if o.object_type == "label")
        self.assertNotIn("stage", label.payload)
        self.assertNotIn("stage_reason", label.payload)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
