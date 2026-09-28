"""spec §10 最小验收集第 7 条：``hindsight=true`` 的对象进不了校准与方法有效性统计。

2026-09-06 自查发现的洞：当天刚给切片加了 ``hindsight`` 标记、让 ``pit_grade`` 永不
``strict``，但**校准侧一处都没读它**。也就是说 spec §4.1 那句「不得进入任何校准」，
当时靠的是「消费方自觉看 pit_grade」——而实测没有任何消费方在看。
这正是同一天修了一整天的形状：**写了标记但没人读**。

这条限定语要活过五跳：

    切片 → 带读草稿 → 观察剧本 → checkpoint → calibrate

中间断在哪一跳，最后那道门就形同虚设。所以本文件**逐跳钉**，不只钉终点。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from intelligence.services import checkpoints
from intelligence.services import guided_reading as gr
from intelligence.services import observation_script as osc

SLICE = {
    "as_of": "2026-09-02",
    "entity_id": "990306.FP",
    "entity_name": "算力租赁",
    "knowledge_cutoff": "2099-01-01",
    "pit_grade": "trade_date_only",
    "hindsight": True,
    "tracks": {
        "market": [
            {
                "object_type": "label",
                "ref": "fact_sector_daily:990306.FP@2026-09-02",
                "source_hash": "abc",
                "payload": {"pct_chg": 1.0},
            }
        ],
    },
}


class Hop1SliceToDraft(unittest.TestCase):
    def test_draft_inherits_hindsight(self) -> None:
        draft = gr.build(SLICE).draft
        assert draft is not None
        self.assertTrue(draft.hindsight)

    def test_clean_slice_does_not(self) -> None:
        draft = gr.build({**SLICE, "hindsight": False}).draft
        assert draft is not None
        self.assertFalse(draft.hindsight)

    def test_reader_is_told(self) -> None:
        """人也要看得见——只有机器知道，用户会以为这份带读和平常一样。"""
        out = gr.build(SLICE)
        self.assertTrue(any("hindsight" in x for x in out.limits))
        self.assertIn("hindsight", gr.render(out))


class Hop2ScriptDoesNotEnterCalibration(unittest.TestCase):
    def test_hindsight_confirmed_script_is_excluded(self) -> None:
        self.assertFalse(osc.enters_calibration({"status": "confirmed", "hindsight": True}))

    def test_clean_confirmed_script_still_counts(self) -> None:
        self.assertTrue(osc.enters_calibration({"status": "confirmed", "hindsight": False}))
        self.assertTrue(osc.enters_calibration({"status": "confirmed"}))


class Hop3ScriptToCheckpoint(unittest.TestCase):
    def _script(self, hindsight: bool) -> osc.ObservationScript:
        return osc.make(
            as_of="2026-09-02",
            scope="theme",
            entity_ids=["算力租赁"],
            variables=["题材轨：题材所处阶段是否推进"],
            downgrade_or_abandon_conditions=["题材轨阶段标签回退或转为缺口"],
            recorded_at="2026-09-03T08:00:00+08:00",
            status="confirmed",
            hindsight=hindsight,
        )

    def test_flag_reaches_the_checkpoint_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spath, cpath = Path(tmp) / "os.jsonl", Path(tmp) / "c.jsonl"
            osc.register(spath, self._script(True), checkpoints_path=cpath)
            (ck,), _ = checkpoints.load_checkpoints(cpath)
            self.assertTrue(ck["hindsight"])

    def test_clean_script_marks_false_not_missing(self) -> None:
        """写 False 而不是省略：省略会让读取方分不清「不是事后」和「老记录没这字段」。"""
        with tempfile.TemporaryDirectory() as tmp:
            spath, cpath = Path(tmp) / "os.jsonl", Path(tmp) / "c.jsonl"
            osc.register(spath, self._script(False), checkpoints_path=cpath)
            (ck,), _ = checkpoints.load_checkpoints(cpath)
            self.assertIn("hindsight", ck)
            self.assertFalse(ck["hindsight"])


class Hop4CalibrateRejects(unittest.TestCase):
    def _calibrate(self, tmp: str):
        cpath, vpath = Path(tmp) / "c.jsonl", Path(tmp) / "v.jsonl"
        _, clean = checkpoints.register_checkpoint(
            cpath, claim="当时就能判的", due="2026-09-03", category="估值切换"
        )
        _, hind = checkpoints.register_checkpoint(
            cpath, claim="事后视角建立的", due="2026-09-03", category="估值切换", hindsight=True
        )
        # 事后那条故意判「命中」：不挡住的话它会把命中率抬上去。
        checkpoints.record_verdict(vpath, id=clean["id"], verdict="miss")
        checkpoints.record_verdict(vpath, id=hind["id"], verdict="hit")
        cks, _ = checkpoints.load_checkpoints(cpath)
        vds, _ = checkpoints.load_verdicts(vpath)
        return checkpoints.calibrate(cks, vds, today="2026-09-10")

    def test_hindsight_does_not_inflate_hit_rate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cal = self._calibrate(tmp)
            self.assertEqual(cal.scored, 1, "只有非事后那条进分母")
            self.assertEqual(cal.overall_rate, 0.0, "挡不住的话会变成 50%")

    def test_exclusion_is_counted_not_silent(self) -> None:
        """静默剔除会让样本莫名变少——「样本少」和「被规则挡了」是两回事。"""
        with tempfile.TemporaryDirectory() as tmp:
            cal = self._calibrate(tmp)
            self.assertEqual(cal.hindsight_excluded, 1)

    def test_report_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            text = checkpoints.render_report(self._calibrate(tmp))
            self.assertIn("事后视角", text)

    def test_object_type_panel_also_excludes(self) -> None:
        """按对象类型分列那张面板同样不能放它进去，否则从另一个入口漏回来。"""
        with tempfile.TemporaryDirectory() as tmp:
            cal = self._calibrate(tmp)
            self.assertEqual(sum(s.n for s in cal.by_object_type), 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
