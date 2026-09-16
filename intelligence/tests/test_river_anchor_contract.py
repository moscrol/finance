"""``anchor_windows`` 契约直接测试（09-06 spec §4.6 / 最小验收集第 15 条）。

此前该契约只经 ``teaching_framework.leader_succession`` 间接覆盖——2026-09-15 验收对账
（``docs/verification/2026-09-15-endstate-acceptance-9-16.md``）点名的缺口。本文件补：
拒绝路径（未注册标签 / until 与显式 after 互斥）、``forward_end > knowledge_cutoff`` 拒绝
（硬规矩 2）、日历不够 → ``open``、lookback 缺天 → ``unverifiable``、事件到事件的
``open`` / 命中两态。IO（日历 / 切片 / 窗口）全部 mock，不读库。
"""

from __future__ import annotations

import unittest
from unittest import mock

from intelligence.services import river_anchor as ra
from intelligence.services.river import RiverSlice, TRACKS
from intelligence.services.river_window_contract import RiverWindow

REAL_LABEL = sorted(ra.ALL_LABELS)[0]
CAL = [f"2026-09-{d:02d}" for d in range(1, 18)]


def _slice(day: str, cutoff: str) -> RiverSlice:
    return RiverSlice(
        as_of=day, entity_id="E", entity_name="实体", knowledge_cutoff=cutoff,
        tracks={t: [] for t in TRACKS}, hindsight=False,  # type: ignore[arg-type]
    )


def _window(start: str, end: str, cutoff: str) -> RiverWindow:
    return RiverWindow(
        start=start, end=end, entity_id="E", entity_name="实体",
        knowledge_cutoff=cutoff, slices=(), derived=(), hindsight=False,
    )


class RejectionTests(unittest.TestCase):
    """标签注册门在任何 IO 之前——不 mock，直接打。"""

    def test_unregistered_anchor_label_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "不是注册标签"):
            ra.anchor_windows("sector:E", "not_a_label", knowledge_cutoff="2026-09-12")

    def test_unregistered_until_label_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "不是注册标签"):
            ra.anchor_windows(
                "sector:E", REAL_LABEL, until_label="not_a_label", knowledge_cutoff="2026-09-12"
            )

    def test_until_with_explicit_after_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "不能同时用"):
            ra.anchor_windows(
                "sector:E", REAL_LABEL, after=10, until_label=REAL_LABEL,
                knowledge_cutoff="2026-09-12",
            )


class _MockedIO(unittest.TestCase):
    def _run(self, *, anchors, cutoff, after=5, before=0, until=None, bind_true_on=None):
        """bind_true_on：事件到事件模式下目标标签首次为真的日子；None = 恒 False。"""

        def fake_bind(label, sl):
            return (sl.as_of == bind_true_on, None)

        with (
            mock.patch.object(ra, "_calendar", return_value=CAL),
            mock.patch.object(
                ra, "slice_river",
                side_effect=lambda day, entity, **kw: _slice(day, kw.get("knowledge_cutoff", day)),
            ),
            mock.patch.object(
                ra, "window",
                side_effect=lambda start, end, entity, **kw: _window(start, end, kw.get("knowledge_cutoff", end)),
            ),
            mock.patch.object(ra, "bind", side_effect=fake_bind),
        ):
            return ra.anchor_windows(
                "sector:E", REAL_LABEL, before=before, after=after,
                until_label=until, knowledge_cutoff=cutoff, anchors=anchors,
            )


class CutoffTests(_MockedIO):
    def test_forward_end_past_cutoff_rejected(self) -> None:
        # 09-10 后第 5 个交易日 = 09-15 > cutoff 09-11：前瞻窗没走完就没有这条记录
        with self.assertRaisesRegex(ValueError, "前瞻窗没走完"):
            self._run(anchors=["2026-09-10"], cutoff="2026-09-11", after=5)

    def test_anchor_after_cutoff_skipped(self) -> None:
        records = self._run(anchors=["2026-09-13"], cutoff="2026-09-12", after=2)
        self.assertEqual(records, [])


class StatusTests(_MockedIO):
    def test_open_when_calendar_runs_out(self) -> None:
        # 09-15 后日历只剩 2 天，after=5 凑不齐 → open，且 gap 写明原因
        records = self._run(anchors=["2026-09-15"], cutoff="2026-09-17", after=5)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].status, "open")
        self.assertTrue(any("not enough trading days after" in g for g in records[0].gaps))

    def test_lookback_gap_makes_record_unverifiable(self) -> None:
        # 09-02 前只有 1 个交易日，before=3 凑不齐 → 段缺失，整条 unverifiable（§4.6：不用另两段补）
        records = self._run(anchors=["2026-09-02"], cutoff="2026-09-10", after=2, before=3)
        self.assertEqual(records[0].status, "unverifiable")
        self.assertTrue(any("before" in g for g in records[0].gaps))

    def test_ok_record_carries_all_three_parts(self) -> None:
        records = self._run(anchors=["2026-09-05"], cutoff="2026-09-12", after=3, before=2)
        rec = records[0]
        self.assertEqual(rec.status, "ok")
        self.assertEqual(rec.gaps, ())
        self.assertEqual(rec.context.as_of, "2026-09-05")
        self.assertEqual(rec.forward.end, "2026-09-08")
        self.assertEqual(len(rec.lookback), 1)


class EventToEventTests(_MockedIO):
    def test_until_not_observed_is_open_and_out_of_n(self) -> None:
        records = self._run(anchors=["2026-09-10"], cutoff="2026-09-12", until=REAL_LABEL)
        self.assertEqual(records[0].status, "open")
        self.assertTrue(any("not observed" in g for g in records[0].gaps))
        self.assertIsNone(records[0].context_target)

    def test_until_hit_builds_target_context(self) -> None:
        records = self._run(
            anchors=["2026-09-10"], cutoff="2026-09-14", until=REAL_LABEL,
            bind_true_on="2026-09-12",
        )
        rec = records[0]
        self.assertEqual(rec.status, "ok")
        self.assertEqual(rec.forward.end, "2026-09-12")
        self.assertIsNotNone(rec.context_target)
        self.assertEqual(rec.context_target.as_of, "2026-09-12")


if __name__ == "__main__":
    unittest.main()
