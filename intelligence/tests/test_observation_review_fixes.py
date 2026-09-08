"""2026-09-06 评审给 #599 提的两条硬伤的回归测试。

1. **回检结果没保留对象类别** → 「观察剧本这类判断准不准」问不出来：
   系统生成经确认的剧本会和用户自己下的判断混在同一个分母里互相稀释。
2. **due 可能落在不开盘的日子** → 盘面 resolver 查无当日行 → ``unverifiable``，
   而 ``unverifiable`` 是**非终态**，于是每晚重判一次、每次都判不了，**永远卡在队列里**。
   resolver 不肯拿相邻交易日顶替是对的（「那是换了个题目在答」），所以修在登记侧。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from intelligence.services import checkpoints
from intelligence.services import observation_script as osc

AS_OF = "2026-09-02"
IN_TIME = "2026-09-03T08:00:00+08:00"


def _script(**over) -> osc.ObservationScript:
    base = dict(
        as_of=AS_OF,
        scope="theme",
        entity_ids=["算力租赁"],
        variables=["题材轨：题材所处阶段是否推进"],
        downgrade_or_abandon_conditions=["题材轨阶段标签回退或转为缺口"],
        recorded_at=IN_TIME,
        # 夹具剧本视为从切片派生：带投影哈希（工单 #34 门禁；用户手写的另测 user_authored）。
        projection_hash="cp:fixture000000001",
        model_id="deterministic",
        status="confirmed",
    )
    base.update(over)
    return osc.make(**base)


class ObjectTypeSplitTests(unittest.TestCase):
    """评审第 3 条：回检后要能按对象类别分开统计。"""

    def _calibrate(self, tmp: str):
        cpath, vpath = Path(tmp) / "c.jsonl", Path(tmp) / "v.jsonl"
        # 一条用户判断 + 一条观察剧本，各判一次，命中率故意不同。
        _, user_ck = checkpoints.register_checkpoint(
            cpath, claim="用户判断", due="2026-09-03", category="估值切换"
        )
        _, os_ck = checkpoints.register_checkpoint(
            cpath, claim="观察剧本", due="2026-09-03", category="observation_script",
            object_type="observation_script",
            projection_hash="cp:fixture000000001",  # 工单 #34：agent 产物无投影哈希台账拒收
        )
        checkpoints.record_verdict(vpath, id=user_ck["id"], verdict="hit")
        checkpoints.record_verdict(vpath, id=os_ck["id"], verdict="miss")
        cks, _ = checkpoints.load_checkpoints(cpath)
        vds, _ = checkpoints.load_verdicts(vpath)
        return checkpoints.calibrate(cks, vds, today="2026-09-10")

    def test_object_types_are_separated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cal = self._calibrate(tmp)
            by = {s.category: s for s in cal.by_object_type}
            self.assertEqual(set(by), {"judgment", "observation_script"})
            self.assertEqual(by["judgment"].hit_rate, 1.0)
            self.assertEqual(by["observation_script"].hit_rate, 0.0)

    def test_not_diluted_into_one_bucket(self) -> None:
        """混算的话两条会变成 50%——那正是「问不出这类判断准不准」的样子。"""
        with tempfile.TemporaryDirectory() as tmp:
            cal = self._calibrate(tmp)
            self.assertNotEqual(
                [s.hit_rate for s in cal.by_object_type], [0.5, 0.5]
            )
            self.assertEqual(sum(s.n for s in cal.by_object_type), 2)

    def test_legacy_records_get_their_own_bucket(self) -> None:
        """存量记录不许被折进「用户判断」——那会让老数据替新维度背书。"""
        with tempfile.TemporaryDirectory() as tmp:
            cpath, vpath = Path(tmp) / "c.jsonl", Path(tmp) / "v.jsonl"
            cpath.write_text(
                '{"id":"ck-old","claim":"存量","due":"2026-09-03"}\n', encoding="utf-8"
            )
            checkpoints.record_verdict(vpath, id="ck-old", verdict="hit")
            cks, _ = checkpoints.load_checkpoints(cpath)
            vds, _ = checkpoints.load_verdicts(vpath)
            cal = checkpoints.calibrate(cks, vds, today="2026-09-10")
            self.assertEqual([s.category for s in cal.by_object_type], ["unknown_legacy"])

    def test_report_shows_the_dimension(self) -> None:
        """字段写了必须有人读——否则它只是个没人看的属性。"""
        with tempfile.TemporaryDirectory() as tmp:
            text = checkpoints.render_report(self._calibrate(tmp))
            self.assertIn("按对象类型", text)
            self.assertIn("观察剧本", text)


class NonTradingDueTests(unittest.TestCase):
    """评审第 4 条：due 落在不开盘的日子。"""

    # 2026-09-30 是交易日；10-01~10-07 国庆休市；10-08 复市。
    TRADING = {"2026-09-29", "2026-09-30", "2026-10-08", "2026-10-09"}

    def test_detects_only_past_nontrading_dues(self) -> None:
        records = [
            {"id": "a", "as_of": "2026-09-30", "due": "2026-10-01", "status": "confirmed", "checkpoint_id": "ck-a"},
            {"id": "b", "as_of": "2026-09-30", "due": "2026-10-08", "status": "confirmed", "checkpoint_id": "ck-b"},
            {"id": "c", "as_of": "2026-09-30", "due": "2099-01-01", "status": "confirmed", "checkpoint_id": "ck-c"},
            {"id": "d", "as_of": "2026-09-30", "due": "2026-10-01", "status": "skipped"},
        ]
        stuck = osc.nontrading_dues(records, self.TRADING, today="2026-10-20")
        self.assertEqual([r["id"] for r in stuck], ["a"])

    def test_future_due_is_not_an_error(self) -> None:
        """未来的 due 日历本来就查不到，不算错——否则每条新剧本一登记就报警。"""
        records = [
            {"id": "x", "as_of": "2026-10-09", "due": "2026-10-12", "status": "confirmed", "checkpoint_id": "ck-x"}
        ]
        self.assertEqual(osc.nontrading_dues(records, self.TRADING, today="2026-10-09"), [])

    def test_repoint_moves_to_next_trading_day(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spath, cpath, vpath = (Path(tmp) / n for n in ("os.jsonl", "c.jsonl", "v.jsonl"))
            _, rec = osc.register(
                spath, _script(as_of="2026-09-30"), checkpoints_path=cpath,
                due="2026-10-01",  # 国庆，不开盘
                next_open=osc.default_next_open("2026-09-30"),
            )
            new = osc.repoint_due(
                spath, rec, checkpoints_path=cpath, verdicts_path=vpath, trading_days=self.TRADING
            )
            assert new is not None
            self.assertEqual(new["due"], "2026-10-08")
            self.assertEqual(new["repointed_from"]["due"], "2026-10-01")
            self.assertNotEqual(new["checkpoint_id"], rec["checkpoint_id"])

    def test_repoint_registers_a_real_checkpoint_on_the_new_day(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spath, cpath, vpath = (Path(tmp) / n for n in ("os.jsonl", "c.jsonl", "v.jsonl"))
            _, rec = osc.register(
                spath, _script(as_of="2026-09-30", machine_conditions=["advancers>=3000"]),
                checkpoints_path=cpath, due="2026-10-01",
                next_open=osc.default_next_open("2026-09-30"),
            )
            osc.repoint_due(spath, rec, checkpoints_path=cpath, verdicts_path=vpath, trading_days=self.TRADING)
            cks, _ = checkpoints.load_checkpoints(cpath)
            new_ck = [c for c in cks if c["due"] == "2026-10-08"]
            self.assertEqual(len(new_ck), 1)
            # 机检规格也要跟着改到新日子，否则还是查那天的空行。
            self.assertEqual(new_ck[0]["metric"]["trade_date"], "2026-10-08")
            self.assertEqual(checkpoints.object_type_of(new_ck[0]), "observation_script")

    def test_old_checkpoint_gets_an_honest_disposition(self) -> None:
        """旧点记 unverifiable + 去向：它本来就判不了，这是实话；且不进胜率。"""
        with tempfile.TemporaryDirectory() as tmp:
            spath, cpath, vpath = (Path(tmp) / n for n in ("os.jsonl", "c.jsonl", "v.jsonl"))
            _, rec = osc.register(
                spath, _script(as_of="2026-09-30"), checkpoints_path=cpath,
                due="2026-10-01", next_open=osc.default_next_open("2026-09-30"),
            )
            osc.repoint_due(spath, rec, checkpoints_path=cpath, verdicts_path=vpath, trading_days=self.TRADING)
            vds, _ = checkpoints.load_verdicts(vpath)
            (v,) = [x for x in vds if x["id"] == rec["checkpoint_id"]]
            self.assertEqual(v["verdict"], "unverifiable")
            self.assertEqual(v["degradation"]["new_due"], "2026-10-08")
            self.assertNotIn(v["verdict"], checkpoints.TERMINAL_VERDICTS, "不许造一个假终态")

    def test_ledger_is_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spath, cpath, vpath = (Path(tmp) / n for n in ("os.jsonl", "c.jsonl", "v.jsonl"))
            _, rec = osc.register(
                spath, _script(as_of="2026-09-30"), checkpoints_path=cpath,
                due="2026-10-01", next_open=osc.default_next_open("2026-09-30"),
            )
            osc.repoint_due(spath, rec, checkpoints_path=cpath, verdicts_path=vpath, trading_days=self.TRADING)
            rows = osc.load(spath)
            self.assertEqual(len(rows), 2, "改点是追加一行，不是改写历史行")
            self.assertEqual(rows[0]["due"], "2026-10-01")

    def test_repoint_is_noop_when_calendar_too_short(self) -> None:
        """日历还没长到那儿就别乱改——改到一个自己也不确定的日子更糟。"""
        with tempfile.TemporaryDirectory() as tmp:
            spath, cpath, vpath = (Path(tmp) / n for n in ("os.jsonl", "c.jsonl", "v.jsonl"))
            _, rec = osc.register(
                spath, _script(as_of="2026-09-30"), checkpoints_path=cpath,
                due="2026-10-01", next_open=osc.default_next_open("2026-09-30"),
            )
            self.assertIsNone(
                osc.repoint_due(spath, rec, checkpoints_path=cpath, verdicts_path=vpath, trading_days={"2026-09-29"})
            )

    def test_resolve_due_falls_back_without_db(self) -> None:
        self.assertEqual(
            osc.resolve_due("2026-09-02", db_path="/tmp/no-such.duckdb"), osc.default_due("2026-09-02")
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
